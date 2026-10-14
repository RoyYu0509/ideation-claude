#!/usr/bin/env python3
"""Mechanical prefetch: build the candidate pool the reranker reads.

Input:  data/cache/week-<YYYY-Www>-candidates.json + data/profile/{papers.json,profile.json}
Output: data/cache/week-<YYYY-Www>-prefetched.json — the pool: top-K candidates with rrf_score,
        per-channel ranks and the channel that seated each one; ordered by rrf_score desc.
        data/cache/week-<YYYY-Www>-channels.json   — every channel's ranking + the seat allocation.
        Offline ablations / the bench read this file; they never re-derive the channels.

The bi-encoder lives here and NOWHERE else in the pipeline.

Channel sets (config prefetch.channel_set; --channel-set overrides it for ablation arms):
  v2      prf (use_prf: time-decayed SPECTER2 centroid of EVERY core paper, prefetch.prf_half_life_months)
          + one SPECTER2 channel per profile thread — a candidate's score is its MAX cosine to that
          thread's own member papers WITH an abstract (paper→paper, the model's training use; a
          title-only record never feeds a channel) + whole-phrase BM25 over the phrase list chosen by
          prefetch.bm25_query + the citation channel + the category channel. Every channel selects its
          inputs through lib/channel_spec — the same rules as the profile's coverage check and the
          ablation runtime — and needs a profile finalized by scripts/profile_finalize.py.
  legacy  the pre-2026-09-12 towers: dense prose query, PRF centroid, per-thread prose queries,
          unigram BM25, citation (+ optional dual encoder). Kept so the V1 arm stays reproducible.
Pool rules (config prefetch.pool_rule; --pool-rule overrides):
  rrf     equal-weight RRF top-K — the default since 2026-09-13 (owner).
  quota   seats per channel (lib/pool_select.py, prefetch.pool_quota), then RRF fill — an ablation
          arm; prf gets no seats of its own there, it only shapes the RRF fill.
Citation modes (config prefetch.citation_mode; --citation-mode overrides):
  coupling  exact reference overlap with the researcher's papers (lib/citation_signal.py).
  graph     personalized PageRank over the 2-hop reference graph + 1/log(1+citations) hub discount;
            needs data/profile/citation-graph.json (scripts/build_citation_graph.py) whose papers.json
            sha matches — otherwise prefetch REFUSES to run (a stale graph never degrades silently).

Signal tokens (--signals, comma-separated; default = default_signals(cfg, channel_set)):
  prf           MB1: PRF centroid — mean of the researcher's recent paper vectors (either set; v2
                leaves out the owner-marked peripheral papers)
  thread        MB2: per-thread prose dense queries, one list per thread (legacy set only)
  cat-rebalance MB6: per-category RRF-score discount post-fusion (either set)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import bm25, citation_graph, citation_signal, config, embeddings, pool_select, profile_io, rrf, thread_fusion  # noqa: E402
from lib import channel_spec as CS  # noqa: E402
from lib import profile_papers as PP  # noqa: E402


def _warn(msg: str) -> None:
    """Loud, unmissable warning for silent-degradation points (a dropped signal
    means the ranking is degraded — never let that pass quietly)."""
    bar = "!" * 72
    print(f"\n{bar}\n[prefetch] WARNING: {msg}\n{bar}", file=sys.stderr)


def _candidate_text(c: dict) -> str:
    title = c.get("title") or ""
    abstract = c.get("abstract") or ""
    return f"{title}. {abstract}".strip()


def _profile_query_text(profile_json: dict) -> str:
    return CS.d0_text(profile_json)          # the dense query rule lives in lib/channel_spec


def _profile_keywords(profile_json: dict) -> list[str]:
    kws = list(profile_json.get("keywords") or [])
    for t in profile_json.get("threads") or []:
        kws.extend(t.get("keywords") or [])
    return kws


# ── Signal helpers ────────────────────────────────────────────────────────────

def _prf_vec(model: str, profile_papers: list[dict], min_year: int, **enc_kwargs) -> np.ndarray | None:
    """LEGACY channel set only: mean SPECTER2 vector over the researcher's papers with an abstract and
    year >= min_year, peripheral ones included so the V1 arm stays bit-exact. The v2 channel selects its
    members through lib/channel_spec.prf_members (see _v2_prf)."""
    recent = [p for p in profile_papers if p.get("abstract") and (p.get("year") or 0) >= min_year]
    if not recent:
        return None
    texts = [f"{p.get('title', '')}. {p.get('abstract', '')}" for p in recent]
    vecs = embeddings.encode(model, texts, **enc_kwargs)
    return vecs.mean(axis=0).astype(np.float32)


def _thread_vecs(model: str, profile_json: dict, **enc_kwargs) -> list[tuple[str, np.ndarray]]:
    """One query vector per research thread (MB2)."""
    items = []
    for t in profile_json.get("threads") or []:
        # The profile writer emits `name`; ARCHITECTURE.md's older schema said `label`.
        # Accept both, and NEVER fall back to a constant: a silent default made every
        # thread list share the name "thread", which collapsed the five per-thread
        # entries of the rank-lookup dict in main() into one. Ranking was unaffected
        # (RRF fuses positionally) but the diagnostic ranks were wrong.
        label = t.get("name") or t.get("label")
        if not label:
            _warn("a profile thread has neither 'name' nor 'label' — per-thread rank "
                  "diagnostics for it will be unattributable; fix data/profile/profile.json")
            label = "unnamed"
        text = (t.get("summary") or "") + ". " + " ".join(t.get("keywords") or [])
        if text.strip(". "):
            items.append((label, text))
    if not items:
        return []
    labels, texts = zip(*items)
    vecs = embeddings.encode(model, list(texts), **enc_kwargs)
    return list(zip(labels, vecs))


def _max_cosine(member_vecs: np.ndarray, cand_matrix: np.ndarray) -> np.ndarray:
    """Per candidate: the highest cosine to any member paper (multi-interest, no averaging)."""
    m = member_vecs.astype(np.float32)
    c = cand_matrix.astype(np.float32)
    m = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-12)
    c = c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-12)
    return (c @ m.T).max(axis=1)


def _apply_cat_rebalance(candidates: list[dict]) -> list[dict]:
    """Discount over-represented categories post-RRF (MB6)."""
    cat_count: Counter = Counter()
    for c in candidates:
        for cat in c.get("categories") or []:
            cat_count[cat] += 1
    total = sum(cat_count.values())
    if not total or len(cat_count) < 2:
        return candidates
    ideal = 1.0 / len(cat_count)
    for c in candidates:
        cats = c.get("categories") or []
        if cats:
            actual = cat_count[cats[0]] / total
            c["rrf_score"] = c["rrf_score"] * min(1.0, ideal / actual)
    return sorted(candidates, key=lambda x: -x["rrf_score"])


def _citation_channel(cand_axids: list[str], profile_papers: list[dict], cfg,
                      citation_mode: str = "coupling", citation_graph_doc: dict | None = None) -> list[str] | None:
    """The `citation` channel in either mode (config prefetch.citation_mode). A missing or stale
    graph is a HARD error raised by run()/main() before we get here — this try/except only
    covers the S2 fetch, whose failure degrades to 'no citation channel' (loudly)."""
    if citation_mode == "graph" and citation_graph_doc is None:
        raise SystemExit("[prefetch] citation_mode=graph but no citation graph was loaded (programming error)")
    fetch_stats: dict = {}
    try:                                     # ONLY the network fetch may degrade the channel
        refs = citation_signal.fetch_candidate_refs(cand_axids, stats=fetch_stats)
    except Exception as e:  # noqa: BLE001
        _warn(f"citation signal DROPPED — no citation channel, pool degraded: {e}")
        return None
    print(f"[prefetch] citation refs: on S2 {fetch_stats.get('found')}/{fetch_stats.get('n')} · with references "
          f"{fetch_stats.get('with_refs')} · retried {fetch_stats.get('retried')} (recovered {fetch_stats.get('recovered')}) "
          f"· unresolved {fetch_stats.get('unresolved')}", file=sys.stderr)
    weights = None
    if citation_mode == "graph":             # scoring is pure: an error here is a bug or a bad graph → raise
        weights = citation_graph.weights_of(citation_graph_doc)
        cit = citation_signal.score_graph(refs, citation_graph_doc, weights)
    else:
        cit = citation_signal.score_coupling(
            refs, CS.coupling_papers(profile_papers),       # core papers only — the rule lives in lib/channel_spec
            direct_weight=cfg.citation_direct_weight,
            shared_weight=cfg.citation_shared_weight,
        )
    ids = [cand_axids[i] for i, _ in cit]
    n_refs = sum(1 for r in refs if r)
    print(f"[prefetch] citation ({citation_mode}): {len(ids)} hits of {n_refs} candidates with a non-empty reference list",
          file=sys.stderr)
    if citation_mode == "graph" and ids:
        # mechanical hub diagnostic — reported, never optimized (see lib/citation_graph.concentration)
        conc = citation_graph.concentration(refs, weights, top=10)
        print(f"[prefetch] citation (graph): top-10 references carry {conc['top_share']:.0%} of the score mass",
              file=sys.stderr)
    return ids or None


_category_weights = CS.category_weights    # the weight rule lives in lib/channel_spec


def _category_channel(candidates: list[dict], profile_papers: list[dict]) -> tuple[list[str], list[float]] | None:
    """MB7 (2026-09-16): the discipline signal the profile never used. A candidate scores the sum of the
    weights of its own categories; a score of 0 never enters the list; ties take the mean rank (EVAL-PLAN §3).
    Evidence: adding this channel beat the production set on 15 of 15 profile builds, out-of-thread recall
    +0.047 (profile-diag REPORT §8.4); it is the only change that helped every single build. Cost: it demotes
    papers from broad categories the researcher does not publish in (cs.AI recall 0.35 → 0.14, REPORT §2 R5)."""
    w = _category_weights(profile_papers)
    if not w:
        return None
    scored: list[tuple[str, float]] = []
    for c in candidates:
        cats = {x for x in (c.get("categories") or []) if x}
        if c.get("primary_category"):
            cats.add(c["primary_category"])
        s = float(sum(w.get(x, 0) for x in cats))
        if s > 0:
            scored.append((c["arxiv_id"], s))
    if not scored:
        return None
    scored.sort(key=lambda p: -p[1])
    ids = [a for a, _ in scored]
    return ids, rrf.tied_ranks(ids, dict(scored))


# ── Channel builders ──────────────────────────────────────────────────────────
# Each returns (named lists in fusion order, {channel: thread label}, [(channel, n_recent, active)],
# {channel: explicit ranks} — the last one only for channels whose score ties a lot, i.e. category).

def _legacy_channels(cand_axids, cand_texts, cand_matrix, profile, profile_papers, cfg,
                     enc_kwargs, signals, oversample_k, use_citation,
                     citation_mode="coupling", citation_graph_doc=None):
    model = cfg.embedding_model
    query_text = _profile_query_text(profile) or cfg.empty_profile_query
    qv = embeddings.encode(model, [query_text], **enc_kwargs)[0]
    named = [("dense", [cand_axids[i] for i, _ in embeddings.cosine_topk(qv, cand_matrix, k=oversample_k)])]
    labels: dict[str, str] = {}
    threads_meta: list[tuple[str, int, bool]] = []

    if "prf" in signals:                                           # MB1
        pv = _prf_vec(model, profile_papers, cfg.prf_min_year, **enc_kwargs)
        if pv is not None:
            named.append(("prf", [cand_axids[i] for i, _ in embeddings.cosine_topk(pv, cand_matrix, k=oversample_k)]))
            print(f"[prefetch] PRF centroid: {len(named[-1][1])} candidates", file=sys.stderr)
        else:
            print("[prefetch] PRF skipped: no recent papers with abstract", file=sys.stderr)

    if "thread" in signals:                                        # MB2
        by_label = {(t.get("name") or t.get("label")): t for t in profile.get("threads") or []}
        tvecs = _thread_vecs(model, profile, **enc_kwargs)
        for i, (label, tvec) in enumerate(tvecs, 1):
            name = f"thread_{i}"
            labels[name] = label
            named.append((name, [cand_axids[j] for j, _ in embeddings.cosine_topk(tvec, cand_matrix, k=oversample_k)]))
            t = by_label.get(label) or {}
            # a pre-v2 profile has no status → every thread active, equal split
            threads_meta.append((name, int(t.get("n_recent") or 1), t.get("status", "active") == "active"))
        print(f"[prefetch] per-thread: {len(tvecs)} thread queries added", file=sys.stderr)

    if cfg.dual_encoder_model:                                     # MB5 (optional)
        q2 = embeddings.encode(cfg.dual_encoder_model, [query_text], **enc_kwargs)[0]
        m2 = embeddings.encode(cfg.dual_encoder_model, cand_texts, **enc_kwargs)
        named.append(("dense2", [cand_axids[i] for i, _ in embeddings.cosine_topk(q2, m2, k=oversample_k)]))
        print(f"[prefetch] dual encoder {cfg.dual_encoder_model}: added", file=sys.stderr)

    kw = _profile_keywords(profile)                                # unigram BM25
    bm25_tokens = bm25.tokenize(" ".join(kw)) or bm25.tokenize(query_text)
    named.append(("bm25", [cand_axids[i] for i, _ in bm25.rank(bm25_tokens, cand_texts, top_k=cfg.bm25_top_k)]))

    if use_citation:
        cit = _citation_channel(cand_axids, profile_papers, cfg, citation_mode, citation_graph_doc)
        if cit:
            named.append(("citation", cit))
    return named, labels, threads_meta, {}


def _v2_prf(model: str, sv: "CS.View", cand_matrix, enc_kwargs) -> np.ndarray:
    """The v2 PRF channel's scores: the time-decayed centroid of lib/channel_spec.prf_members."""
    members, weights = CS.prf_members(sv)
    vecs = embeddings.encode(model, [CS.text_of(p) for p in members], **enc_kwargs)
    centroid = np.average(vecs, axis=0, weights=weights).astype(np.float32)
    return _max_cosine(centroid[None, :], cand_matrix)


def _v2_channels(cand_axids, cand_texts, cand_matrix, profile, profile_papers, cfg, enc_kwargs, use_citation,
                 citation_mode="coupling", citation_graph_doc=None, signals=frozenset(), candidates=None,
                 use_category=False, ref_abstracts=None, use_dense=False):
    """The v2 channel set. Every channel selects its inputs through lib/channel_spec — the same rules the
    profile's coverage check and the ablation runtime use — and a production channel whose input the
    profile cannot supply stops the run instead of silently dropping out."""
    if profile.get("schema_version") not in (2, CS.SCHEMA_V3) or not profile.get("finalized_by"):
        raise SystemExit("[prefetch] channel_set v2 needs a profile FINALIZED by scripts/profile_finalize.py "
                         "(schema_version 2 or 3 + finalized_by). A hand-written draft that merely declares a "
                         "schema version is refused — it would run with inputs nobody checked. "
                         "Re-run profile_finalize.py; for the pre-v2 towers pass --channel-set legacy.")
    model = cfg.embedding_model
    try:
        sv = CS.view(profile, profile_papers, params=CS.params_from_config(cfg),
                     companions={"ref_abstracts.json": None} if ref_abstracts is not None else None,
                     ref_abstracts=ref_abstracts)
    except CS.Unavailable as e:
        raise SystemExit(f"[prefetch] v2 profile unusable: {e}")
    named: list[tuple[str, list[str]]] = []
    labels: dict[str, str] = {}
    threads_meta: list[tuple[str, int, bool]] = []

    def need(what, fn):
        try:
            return fn()
        except CS.Unavailable as e:
            raise SystemExit(f"[prefetch] v2 {what}: the profile cannot supply it — missing [{e.source}] {e.what}. "
                             f"Run scripts/profile_finalize.py --check-only for the full coverage table.")

    if use_dense:                                                  # 融合顺序里 dense 在最前(与消融一致)
        texts, average = need("dense", lambda: CS.dense_query(sv, cfg.dense_query))
        vecs = embeddings.encode(model, texts, **enc_kwargs)
        if average:
            vecs = vecs.mean(axis=0, keepdims=True)
        order = np.argsort(-_max_cosine(vecs, cand_matrix), kind="stable")
        named.append(("dense", [cand_axids[j] for j in order]))
        what = "the profile text" if cfg.dense_query == "profile_text" else f"{len(texts)} paper notes, averaged"
        print(f"[prefetch] v2: dense channel ({what})", file=sys.stderr)

    if "prf" in signals:                                           # MB1 over the core papers
        scores = need("prf", lambda: _v2_prf(model, sv, cand_matrix, enc_kwargs))
        named.append(("prf", [cand_axids[j] for j in np.argsort(-scores, kind="stable")]))
        print(f"[prefetch] v2: PRF centroid channel (every core paper, half-life {cfg.prf_half_life_months:g} months)",
              file=sys.stderr)

    thread_list = profile.get("threads") or []
    for i, label, texts in need("thread channels", lambda: CS.thread_members_refs(sv)):
        name = f"thread_{i}"
        t = thread_list[i - 1]
        labels[name] = label
        vecs = embeddings.encode(model, texts, **enc_kwargs)
        order = np.argsort(-_max_cosine(vecs, cand_matrix), kind="stable")
        named.append((name, [cand_axids[j] for j in order]))
        threads_meta.append((name, int(t.get("n_recent") or 0), t.get("status") == "active"))
    for i, t in enumerate(thread_list, 1):
        if f"thread_{i}" not in labels:
            _warn(f"thread '{t.get('name') or i}' has no member paper with an abstract — no semantic channel")
    print(f"[prefetch] v2: {len(threads_meta)} thread channels (max cosine to member papers + their shared "
          f"references with an abstract)",
          file=sys.stderr)

    variant = CS.BM25_QUERY_SOURCES[cfg.bm25_query]
    terms = bm25.phrase_terms(need(f"bm25 ({cfg.bm25_query} = {variant})", lambda: CS.bm25_phrases(sv, variant)))
    ranked = bm25.rank(terms, cand_texts, top_k=len(cand_texts), phrases=True)
    named.append(("bm25", [cand_axids[j] for j, s in ranked if s > 0]))
    print(f"[prefetch] v2: phrase BM25 ({cfg.bm25_query}) — {len(terms)} terms, {len(named[-1][1])} matching papers",
          file=sys.stderr)

    if use_citation:
        cit = _citation_channel(cand_axids, profile_papers, cfg, citation_mode, citation_graph_doc)
        if cit:
            named.append(("citation", cit))

    rank_override: dict[str, list[float]] = {}
    if use_category and candidates:
        need("category", lambda: CS.category(sv))
        cat = _category_channel(candidates, profile_papers)
        if cat:
            ids, ranks = cat
            named.append(("category", ids))
            rank_override["category"] = ranks
            print(f"[prefetch] v2: category channel — {len(ids)} candidates carry one of the researcher's "
                  f"categories (ties take the mean rank)", file=sys.stderr)
        else:
            _warn("category channel: no candidate this week carries any of the researcher's categories")
    return named, labels, threads_meta, rank_override


def _thread_sizes(profile: dict, profile_papers: list[dict], cfg) -> dict[str, int]:
    """thread list name → the member papers it is built from (lib/thread_fusion 'sqrt' weights by these)."""
    sv = CS.view(profile, profile_papers, params=CS.params_from_config(cfg))
    return {f"thread_{i}": len(members) for i, _, members in CS.thread_members(sv)}


def _graph_required(citation_mode: str, use_citation: bool) -> bool:
    """main() loads the graph iff the citation channel will actually run in graph mode —
    every off-switch (--no-citation, config use_citation_signal: false) must agree with run()."""
    return citation_mode == "graph" and bool(use_citation)


def default_signals(cfg, channel_set: str) -> set[str]:
    """Signal tokens the config turns on: prf in either channel set (config use_prf), the prose
    thread queries only in legacy (v2's thread channels are the member-paper channels), and
    cat-rebalance in either. main() and profile_selfcheck.py share it, so both run one set."""
    signals: set[str] = set()
    if cfg.use_prf:
        signals.add("prf")
    if channel_set == "legacy" and cfg.use_thread_queries:
        signals.add("thread")
    if cfg.use_category_rebalance:
        signals.add("cat-rebalance")
    return signals


# ── The pool ──────────────────────────────────────────────────────────────────

def run(cand_data: dict, profile: dict, profile_papers: list[dict], cfg, *, top_k: int,
        channel_set: str, pool_rule: str, signals: set[str], pinned_ids: set[str] = frozenset(),
        use_citation: bool | None = None, use_quality: bool | None = None, use_category: bool | None = None,
        citation_mode: str | None = None, citation_graph_doc: dict | None = None,
        ref_abstracts: dict | None = None, use_dense: bool | None = None) -> tuple[dict, dict]:
    """Build the pool. Returns (prefetched payload, channels payload); no file I/O.

    citation_mode / citation_graph_doc: config prefetch.citation_mode unless overridden; in graph
    mode the caller passes the graph ALREADY validated against papers.json (lib/citation_graph.
    load_graph) — a missing graph is a hard error here, never a silently dropped channel.
    ref_abstracts: data/profile/ref_abstracts.json's `refs`, ALREADY checked against papers.json
    (lib/profile_io.load_companions). The thread channels need it; leaving it None stops the run."""
    use_citation = cfg.use_citation_signal if use_citation is None else use_citation
    use_quality = cfg.use_quality_signal if use_quality is None else use_quality
    use_category = cfg.use_category_channel if use_category is None else use_category
    use_dense = cfg.use_dense_channel if use_dense is None else use_dense
    citation_mode = citation_mode or cfg.citation_mode
    thread_fusion_mode = cfg.thread_fusion
    try:
        thread_fusion.check(thread_fusion_mode, channel_set, pool_rule)
    except ValueError as e:
        raise SystemExit(f"[prefetch] {e}")
    if citation_mode not in ("coupling", "graph"):
        raise SystemExit(f"[prefetch] unknown citation_mode {citation_mode!r} (coupling | graph)")
    if use_citation and citation_mode == "graph" and citation_graph_doc is None:
        raise SystemExit("[prefetch] citation_mode=graph needs data/profile/citation-graph.json — run "
                         "scripts/build_citation_graph.py after building papers.json (a stale graph is refused too)")
    base = {"week": cand_data["week"], "prefetch_top_k": top_k, "rrf_k": cfg.rrf_k,
            "embedding_model": cfg.embedding_model, "channel_set": channel_set, "pool_rule": pool_rule,
            "citation_mode": citation_mode if use_citation else None, "thread_fusion": thread_fusion_mode,
            "category_channel": bool(use_category) and channel_set == "v2",
            "dense_channel": (cfg.dense_query if use_dense else None) if channel_set == "v2" else None}
    candidates = cand_data["candidates"]
    if not candidates:
        print("[prefetch] no candidates; emitting empty prefetch", file=sys.stderr)
        return ({**base, "signals": sorted(signals), "seats": {}, "used_citation_signal": False,
                 "used_quality_signal": use_quality, "candidates": []},
                {**base, "thread_labels": {}, "seats": {}, "channels": {}})

    cand_axids = [c["arxiv_id"] for c in candidates]
    cand_texts = [_candidate_text(c) for c in candidates]
    enc_kwargs = {
        "backend": cfg.embedding_backend,
        "pooling": cfg.embedding_pooling,
        "batch_size": cfg.embedding_batch_size,
        "max_age_days": cfg.embedding_cache_stale_days,
    }
    cand_matrix = embeddings.encode(cfg.embedding_model, cand_texts, **enc_kwargs)
    if channel_set == "v2":
        named, labels, threads_meta, rank_override = _v2_channels(
            cand_axids, cand_texts, cand_matrix, profile, profile_papers, cfg, enc_kwargs, use_citation,
            citation_mode, citation_graph_doc, signals, candidates=candidates, use_category=use_category,
            ref_abstracts=ref_abstracts, use_dense=use_dense)
    else:
        named, labels, threads_meta, rank_override = _legacy_channels(
            cand_axids, cand_texts, cand_matrix, profile, profile_papers, cfg, enc_kwargs, signals,
            top_k * cfg.oversample_factor, use_citation, citation_mode, citation_graph_doc)
    sizes = _thread_sizes(profile, profile_papers, cfg) if thread_fusion_mode == "sqrt" else {}
    fuse_named, weights = thread_fusion.apply(thread_fusion_mode, named, sizes)
    names = [n for n, _ in fuse_named]
    channels = dict(named)                       # every per-thread list stays visible (diagnostics, quota)
    channels.update(fuse_named)                  # + thread_best when the lists were collapsed
    ranks_arg = [rank_override.get(n) for n in names] if rank_override else None
    fused, rank_lookups = rrf.fuse_with_ranks([lst for _, lst in fuse_named], k=cfg.rrf_k, ranks=ranks_arg,
                                              weights=weights)
    lookup = {n: rank_lookups[i] for i, n in enumerate(names)}
    score = dict(fused)

    if pool_rule == "quota":
        seats = pool_select.allocate(
            top_k, threads_meta, cfg.pool_quota_thread_floor,
            cfg.pool_quota_bm25 if "bm25" in channels else 0,
            cfg.pool_quota_citation, len(channels.get("citation") or []),
        )
        order = [n for n, _, _ in threads_meta] + [c for c in ("bm25", "citation") if c in channels]
        pool_ids, seated_by = pool_select.seat_pool(channels, seats, top_k, [a for a, _ in fused], order)
        pool_ids.sort(key=lambda a: -score.get(a, 0.0))
        used = Counter(seated_by.values())
        print(f"[prefetch] quota pool: seats {seats} · seated {dict(used)}", file=sys.stderr)
    else:
        seats = {}
        pool_ids = [a for a, _ in fused[:top_k]]
        seated_by = {a: "rrf" for a in pool_ids}

    by_axid = {c["arxiv_id"]: c for c in candidates}

    def _row(axid: str) -> dict:
        c = dict(by_axid[axid])
        c["rrf_score"] = score.get(axid, 0.0)
        for legacy in ("dense", "bm25", "prf", "citation"):
            c[f"{legacy}_rank"] = lookup.get(legacy, {}).get(axid)
        c["channel_ranks"] = {n: lookup[n].get(axid) for n in names}
        c["seated_by"] = seated_by.get(axid)
        return c

    out_candidates = [_row(a) for a in pool_ids]

    # ── Pinned-paper guarantee: force-include user-specified IDs ─────────────
    if pinned_ids:
        included = set(pool_ids)
        top_score = out_candidates[0]["rrf_score"] if out_candidates else 1.0
        for pid in sorted(pinned_ids):
            if pid in by_axid and pid not in included:
                c = _row(pid)
                c["rrf_score"] = top_score + cfg.pinned_score_boost
                c["seated_by"] = "pinned"
                out_candidates.append(c)
        for c in out_candidates:
            if c["arxiv_id"] in pinned_ids:
                c["pinned"] = True
        print(f"[prefetch] pinned papers ensured: {sorted(pinned_ids & {c['arxiv_id'] for c in out_candidates})}",
              file=sys.stderr)

    # ── Quality signal (optional; STAGED annotate — NEVER enters the pool rule) ──
    # Runs AFTER pinned handling so pinned papers are exempt from any dead-repo
    # filter. Only appends fields (+ optional dead-repo filter); never reorders
    # by quality — that is the cat-rebalance mistake this design avoids.
    if use_quality:
        try:
            from lib import quality_signal
            targets = (out_candidates if cfg.quality_annotate_scope == "prefetched"
                       else out_candidates[:cfg.rerank_return_n])
            anns = quality_signal.annotate(
                targets,
                use_author_prior=cfg.quality_use_author_prior,
                use_paper_influence=cfg.quality_use_paper_influence,
                use_repo_check=cfg.use_repo_check,
                author_h_strong=cfg.quality_author_h_strong,
                infl_strong=cfg.quality_infl_strong,
                repo_active_min_stars=cfg.quality_repo_active_min_stars,
                cache_dir=config.cache_dir() / "quality",
                cache_max_age_days=cfg.quality_cache_stale_days,
            )
            action = cfg.repo_dead_action
            for c in out_candidates:
                a = anns.get(c["arxiv_id"])
                if not a:
                    continue
                for k, v in asdict(a).items():
                    if v is None or v == []:
                        continue
                    c[k] = v
                # flag-only mode: expose repo_status but do NOT demote the tier
                if a.repo_status == quality_signal.REPO_DEAD and action == "flag":
                    c["quality_tier"] = quality_signal.TIER_NEUTRAL
            if action == "filter":
                before = len(out_candidates)
                out_candidates = [
                    c for c in out_candidates
                    if c.get("repo_status") != quality_signal.REPO_DEAD or c.get("pinned")
                ]
                print(f"[prefetch] quality: filtered {before - len(out_candidates)} dead-repo papers",
                      file=sys.stderr)
            n_weak = sum(1 for c in out_candidates if c.get("quality_tier") == "weak")
            n_strong = sum(1 for c in out_candidates if c.get("quality_tier") == "strong")
            print(f"[prefetch] quality annotated: {len(anns)} (strong={n_strong}, weak={n_weak}, "
                  f"action={action})", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            _warn(f"quality signal DROPPED — tiers/repo flags missing from candidates: {e}")

    # ── MB6: category rebalancing ─────────────────────────────────────────────
    if "cat-rebalance" in signals:
        out_candidates = _apply_cat_rebalance(out_candidates)
        print("[prefetch] category rebalancing applied", file=sys.stderr)

    prefetched = {**base, "signals": sorted(signals), "seats": seats,
                  "used_citation_signal": "citation" in lookup, "used_quality_signal": use_quality,
                  "candidates": out_candidates}
    channels_payload = {**base, "thread_labels": labels, "seats": seats, "channels": channels}
    return prefetched, channels_payload


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--profile-json", type=Path, default=None)
    ap.add_argument("--profile-papers", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--channels-out", type=Path, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--channel-set", choices=("v2", "legacy"), default=None,
                    help="override prefetch.channel_set (ablation arms)")
    ap.add_argument("--pool-rule", choices=("quota", "rrf"), default=None,
                    help="override prefetch.pool_rule (ablation arms)")
    ap.add_argument("--no-citation", action="store_true",
                    help="drop the citation channel for this run (evaluation reports with and without it)")
    ap.add_argument("--citation-mode", choices=("coupling", "graph"), default=None,
                    help="override prefetch.citation_mode (ablation arms); graph needs citation-graph.json")
    ap.add_argument("--citation-graph", type=Path, default=None,
                    help="graph file for --citation-mode graph (default: <profile dir>/citation-graph.json)")
    ap.add_argument(
        "--signals",
        default=None,
        help="Comma-separated legacy signal set override. "
             "Tokens: prf, thread, cat-rebalance. "
             "Default: derived from config flags.",
    )
    ap.add_argument(
        "--pinned-ids",
        default="",
        help="Comma-separated arxiv IDs that must survive the top-K cutoff.",
    )
    args = ap.parse_args()

    cfg = config.load_config()
    profile_json_path = args.profile_json or (config.profile_dir() / "profile.json")
    profile_papers_path = args.profile_papers or (config.profile_dir() / "papers.json")
    with open(args.candidates, "r", encoding="utf-8") as f:
        cand_data = json.load(f)
    with open(profile_json_path, "r", encoding="utf-8") as f:
        profile = json.load(f)
    with open(profile_papers_path, "r", encoding="utf-8") as f:
        profile_papers = json.load(f).get("papers", [])

    channel_set = args.channel_set or cfg.channel_set
    citation_mode = args.citation_mode or cfg.citation_mode
    comp, ref_abstracts = profile_io.load_companions(profile_papers_path.parent,
                                                     profile_io.sha256_file(profile_papers_path))
    if comp.get("ref_abstracts.json"):
        print(f"[prefetch] ref_abstracts.json: {comp['ref_abstracts.json']}", file=sys.stderr)
    citation_graph_doc = None
    if _graph_required(citation_mode, cfg.use_citation_signal and not args.no_citation):
        graph_path = args.citation_graph or (profile_papers_path.parent / "citation-graph.json")
        try:
            citation_graph_doc = citation_graph.load_graph(graph_path, profile_papers_path)
        except citation_graph.CitationGraphError as e:
            raise SystemExit(f"[prefetch] {e}") from e
        print(f"[prefetch] citation graph: {citation_graph_doc['n_nodes']} nodes, "
              f"{citation_graph_doc['n_edges']} edges, built {citation_graph_doc['built_utc']}", file=sys.stderr)
    if args.signals is not None:
        signals = {s.strip() for s in args.signals.split(",") if s.strip()}
    else:
        signals = default_signals(cfg, channel_set)

    prefetched, channels = run(
        cand_data, profile, profile_papers, cfg,
        top_k=args.top_k or cfg.prefetch_top_k,
        channel_set=channel_set,
        pool_rule=args.pool_rule or cfg.pool_rule,
        signals=signals,
        pinned_ids={p.strip() for p in args.pinned_ids.split(",") if p.strip()},
        use_citation=False if args.no_citation else None,
        citation_mode=citation_mode, citation_graph_doc=citation_graph_doc,
        ref_abstracts=ref_abstracts,
    )

    out = args.out or (config.cache_dir() / f"week-{cand_data['week']}-prefetched.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(prefetched, f, indent=2)
    ch_out = args.channels_out or (out.with_name(out.name.replace("-prefetched.json", "-channels.json"))
                                   if out.name.endswith("-prefetched.json") else out.with_suffix(".channels.json"))
    with open(ch_out, "w", encoding="utf-8") as f:
        json.dump(channels, f)
    print(f"[prefetch] wrote {out}: {len(prefetched['candidates'])} candidates "
          f"(channels {prefetched['channel_set']}, pool {prefetched['pool_rule']}, "
          f"signals {prefetched['signals'] or ['baseline']}) + {ch_out.name}", file=sys.stderr)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
