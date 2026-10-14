#!/usr/bin/env python3
"""Pull the researcher's full paper list from Semantic Scholar.

Outputs:
  data/profile/papers.json       — merged S2 + supplement (full working list)
  data/profile/papers_supplement.json — persisted non-S2 papers (written by the
                                        arxiv-profile skill's website cross-check).
                                        This file survives re-runs of this script.

This script does NOT generate the NL profile or the threads — those come from
Claude reading the JSON via the arxiv-profile skill. This is the mechanical
fetch step only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import arxiv_client, config, s2_client, scholar_profile  # noqa: E402
from lib import profile_papers as PP  # noqa: E402


# ---------------------------------------------------------------------------
# Title normalisation & similarity helpers (shared by dedup and supplement merge)
# ---------------------------------------------------------------------------

_norm_title = PP.norm_title
_jaccard = PP.jaccard


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _merge_group(papers: list[dict]) -> dict:
    """Merge duplicate records, taking the best field from each version."""
    arxiv_id = next((p["arxiv_id"] for p in papers if p.get("arxiv_id")), None)
    paper_id = next(
        (p["paper_id"] for p in papers if p.get("arxiv_id") and p.get("paper_id")), None
    ) or next((p["paper_id"] for p in papers if p.get("paper_id")), None)
    title = max((p.get("title") or "" for p in papers), key=len)
    abstract = max((p.get("abstract") or "" for p in papers), key=len) or None
    # Prefer a non-arXiv venue (conference/journal) over empty or arXiv
    venue = next(
        (p["venue"] for p in papers
         if p.get("venue") and "arxiv" not in p["venue"].lower()), None
    ) or next((p["venue"] for p in papers if p.get("venue")), None)
    # Year: take the year paired with a real venue; fall back to earliest
    year = next(
        (p["year"] for p in papers
         if p.get("year") and p.get("venue")
         and "arxiv" not in (p["venue"] or "").lower()), None
    ) or min((p["year"] for p in papers if p.get("year")), default=None)
    # categories: ordered union
    seen: set[str] = set()
    cats: list[str] = []
    for p in papers:
        for c in (p.get("categories") or []):
            if c not in seen:
                seen.add(c)
                cats.append(c)
    # reference_ids: union across all versions
    refs = list({r for p in papers for r in (p.get("reference_ids") or []) if r})
    return {
        "paper_id": paper_id,
        "arxiv_id": arxiv_id,
        "title": title,
        "abstract": abstract,
        "year": year,
        "venue": venue,
        "categories": cats,
        "reference_ids": refs,
    }


def _dedup(papers: list[dict]) -> tuple[list[dict], int]:
    """Group duplicates by title and merge each group into one record."""
    # Exact normalized-title groups
    groups: dict[str, list[dict]] = {}
    for p in papers:
        key = _norm_title(p.get("title") or "")
        groups.setdefault(key, []).append(p)

    # Among singleton groups, fuzzy-merge pairs with Jaccard ≥ 0.65.
    # 0.65 catches the common "title" → "title: subtitle" arXiv→journal pattern
    # while staying above the false-positive floor for same-author distinct papers.
    single_keys = [k for k, v in groups.items() if len(v) == 1]
    used: set[int] = set()
    fuzzy_groups: list[list[dict]] = []
    for i in range(len(single_keys)):
        if i in used:
            continue
        cluster = [i]
        for j in range(i + 1, len(single_keys)):
            if j not in used and _jaccard(single_keys[i], single_keys[j]) >= 0.65:
                cluster.append(j)
        if len(cluster) > 1:
            fuzzy_groups.append([groups[single_keys[k]][0] for k in cluster])
            used.update(cluster)

    result: list[dict] = []
    for v in groups.values():
        if len(v) > 1:
            result.append(_merge_group(v))
    for grp in fuzzy_groups:
        result.append(_merge_group(grp))
    for i, k in enumerate(single_keys):
        if i not in used:
            result.append(groups[k][0])

    return result, len(papers) - len(result)


# ---------------------------------------------------------------------------
# Reference enrichment
# ---------------------------------------------------------------------------

def _enrich_references(papers: list[dict]) -> int:
    """For papers with empty reference_ids, try an extra S2 lookup.

    Rate-limit errors for individual papers are logged and skipped so they
    never abort the whole fetch run.
    """
    enriched = 0
    skipped = 0
    for p in papers:
        if p.get("reference_ids"):
            continue
        raw = None
        try:
            if p.get("arxiv_id"):
                raw = s2_client.paper_by_arxiv(
                    p["arxiv_id"], fields=("paperId", "references.paperId")
                )
            elif p.get("paper_id"):
                raw = s2_client.paper_by_id(
                    p["paper_id"], fields=("paperId", "references.paperId")
                )
        except RuntimeError as e:
            print(f"[build_profile_papers] skipping ref enrichment for '{p.get('title','?')[:60]}': {e}",
                  file=sys.stderr)
            skipped += 1
            continue
        if raw:
            refs = [r.get("paperId") for r in (raw.get("references") or []) if r.get("paperId")]
            if refs:
                p["reference_ids"] = refs
                enriched += 1
    if skipped:
        print(f"[build_profile_papers] {skipped} papers skipped during ref enrichment (rate limit)",
              file=sys.stderr)
    return enriched


# ---------------------------------------------------------------------------
# Supplement merge (preserves website cross-check additions across re-runs)
# ---------------------------------------------------------------------------

def _load_supplement(supplement_path: Path) -> list[dict]:
    """Load persisted non-S2 papers written by the arxiv-profile cross-check."""
    if not supplement_path.exists():
        return []
    try:
        data = json.loads(supplement_path.read_text(encoding="utf-8"))
        return data.get("papers") or []
    except Exception as e:
        print(f"[build_profile_papers] warning: could not read supplement: {e}", file=sys.stderr)
        return []


def _merge_supplement(s2_papers: list[dict], supplement: list[dict]) -> list[dict]:
    """Append supplement papers not yet covered by s2_papers.

    A supplement paper is considered "graduated" (already in S2) if:
      - its arxiv_id matches an S2 paper, OR
      - its normalised title has Jaccard ≥ 0.65 with any S2 title.
    Graduated papers are silently skipped; the S2 version is already included.
    """
    if not supplement:
        return s2_papers

    s2_arxiv_ids = {p["arxiv_id"] for p in s2_papers if p.get("arxiv_id")}
    s2_norm_titles = [_norm_title(p.get("title") or "") for p in s2_papers]

    kept: list[dict] = []
    graduated = 0
    for sp in supplement:
        # Check arxiv_id collision
        if sp.get("arxiv_id") and sp["arxiv_id"] in s2_arxiv_ids:
            graduated += 1
            continue
        # Check title collision (exact or fuzzy)
        sp_norm = _norm_title(sp.get("title") or "")
        if any(_jaccard(sp_norm, t) >= 0.65 for t in s2_norm_titles):
            graduated += 1
            continue
        kept.append(sp)

    if graduated:
        print(
            f"[build_profile_papers] {graduated} supplement paper(s) now covered by S2, skipped",
            file=sys.stderr,
        )
    if kept:
        print(
            f"[build_profile_papers] merged {len(kept)} supplement paper(s) not yet in S2",
            file=sys.stderr,
        )

    return s2_papers + kept


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _fetch_from_website(profile_dir: Path, no_enrich: bool) -> tuple[list[dict], str | None, str | None]:
    """Load papers from website_papers.json, match each against S2 by title.

    Returns (papers, s2_author_id=None, author_name=None).
    Matched papers use full S2 metadata; unmatched become Tier-2 stubs.
    """
    website_papers_path = profile_dir / "website_papers.json"
    if not website_papers_path.exists():
        print("[build_profile_papers] ERROR: --website-only requires data/profile/website_papers.json",
              file=sys.stderr)
        raise FileNotFoundError(website_papers_path)

    raw = json.loads(website_papers_path.read_text(encoding="utf-8"))
    website_list = raw if isinstance(raw, list) else raw.get("papers", [])
    print(f"[build_profile_papers] website-only mode: {len(website_list)} papers on site", file=sys.stderr)

    papers: list[dict] = []
    for wp in website_list:
        title = (wp.get("title") or "").strip()
        if not title:
            continue
        try:
            results = s2_client.search_by_title(title)
            best: dict | None = None
            best_sim = 0.0
            for r in results:
                sim = _jaccard(_norm_title(r.get("title") or ""), _norm_title(title))
                if sim > best_sim:
                    best_sim = sim
                    best = r
        except Exception as e:
            print(f"[build_profile_papers] S2 search failed for '{title[:60]}': {e}", file=sys.stderr)
            best = None
            best_sim = 0.0

        if best and best_sim >= 0.65:
            papers.append(s2_client.normalize_paper(best))
        else:
            papers.append({
                "paper_id": None,
                "arxiv_id": wp.get("arxiv_id"),
                "title": title,
                "abstract": None,
                "year": wp.get("year"),
                "venue": wp.get("venue"),
                "categories": [],
                "reference_ids": [],
                "status": "not_in_s2",
            })

    return papers, None, None


# ---------------------------------------------------------------------------
# Google Scholar source (REC-SYSTEM-V2 A1, 2026-09-12)
#   stage 1  --scholar-url / --scholar-html → paper_candidates.json (+ .md) for the owner to confirm
#   stage 2  --from-list <confirmed.json> [--cutoff YYYY-MM-DD] → papers.json
# ---------------------------------------------------------------------------

_DECISIONS = ("self", "peripheral", "not")


def _best_title_match(title: str, hits: list[dict]) -> tuple[dict | None, float]:
    target = PP.norm_title(title)
    best, sim = None, 0.0
    for h in hits:
        s = PP.jaccard(PP.norm_title(h.get("title") or ""), target)
        if s > sim:
            best, sim = h, s
    return best, sim


def _candidates_md(doc: dict) -> str:
    src = doc["source"]
    lines = [
        f"# 论文候选清单 — {doc.get('name') or '?'}", "",
        f"来源:{src.get('url') or src.get('path')}(读取于 {doc['fetched_at_utc'][:19]} UTC)", "",
        "在 `paper_candidates.json` 里把每条的 `decision` 改成 `self`(是本人)、`peripheral`"
        "(边缘:挂名的大合作等,留在记录里但不进语义通道)或 `not`(不是本人),然后跑 `--from-list`。", "",
        "| # | key | 日期 | 标题 | 出处 | arXiv | 摘要 | 怎么找到的 | 被引 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(doc["papers"], 1):
        title = (p.get("title") or "").replace("|", "/")[:90]
        venue = (p.get("venue") or "").replace("|", "/")[:40]
        lines.append(f"| {i} | {p['key']} | {p.get('first_date') or p.get('year') or ''} | {title} | {venue} | "
                     f"{p.get('arxiv_id') or ''} | {'有' if p.get('abstract') else '无'} | "
                     f"{p.get('resolved_by') or '只有标题'} | {p.get('scholar_citations') or ''} |")
    return "\n".join(lines) + "\n"


def _resolve_title(title: str, thr: float, failed: list[str]) -> tuple[str | None, str | None, dict]:
    """A Scholar row whose venue carries no arXiv id (mostly a journal version): arXiv
    title-phrase search first, then S2 title match (S2 through its key ladder). Returns
    (arxiv_id, how, s2_hit). A lookup that ERRORS is appended to `failed` — not "no match"."""
    try:
        best, sim = _best_title_match(title, arxiv_client.search_title(title))
    except Exception as e:  # noqa: BLE001 — one failed lookup must not sink the build
        print(f"[build_profile_papers] arXiv title search failed for '{title[:60]}': {e}", file=sys.stderr)
        failed.append(f"arXiv title: {title[:60]}")
        best, sim = None, 0.0
    if best and sim >= thr:
        return best["arxiv_id"], "arxiv_title", {}
    try:
        best, sim = _best_title_match(title, s2_client.search_by_title(title))
    except Exception as e:  # noqa: BLE001
        print(f"[build_profile_papers] S2 title search failed for '{title[:60]}': {e}", file=sys.stderr)
        failed.append(f"S2 title: {title[:60]}")
        best, sim = None, 0.0
    if best and sim >= thr:
        return (best.get("externalIds") or {}).get("ArXiv"), "s2_title", best
    return None, None, {}


def _merge_duplicates(papers: list[dict]) -> list[dict]:
    """Scholar often lists a journal version and its preprint as two rows that resolve to the
    same arXiv id. Keep the first row (Scholar's newest-first order) and record the others
    under `scholar_duplicates`, so the owner confirms each paper once."""
    out: list[dict] = []
    seen: dict[str, dict] = {}
    for p in papers:
        ax = p.get("arxiv_id")
        if ax and ax in seen:
            seen[ax].setdefault("scholar_duplicates", []).append(
                {k: p.get(k) for k in ("scholar_title", "venue", "year", "scholar_citations")})
            if p.get("decision") and not seen[ax].get("decision"):
                seen[ax]["decision"] = p["decision"]
            continue
        if ax:
            seen[ax] = p
        out.append(p)
    return out


def _scholar_stage(cfg, args, profile_dir: Path) -> int:
    if args.scholar_html:
        text = Path(args.scholar_html).read_text(encoding="utf-8", errors="ignore")
        source = {"kind": "saved_html", "path": str(args.scholar_html)}
    else:
        url = scholar_profile.profile_url(args.scholar_url, cfg.io_scholar_base_url, cfg.io_scholar_pagesize)
        try:
            text = scholar_profile.fetch_html(url, cfg.io_scholar_timeout)
        except scholar_profile.ScholarBlocked as e:
            print(f"[build_profile_papers] {e}\n  Nothing was retried or worked around. Open the profile in "
                  "your own browser, save the page as HTML, and re-run with --scholar-html <file>.",
                  file=sys.stderr)
            return 2
        source = {"kind": "url", "url": url}
    parsed = scholar_profile.parse(text)
    rows = parsed["rows"]
    if not rows:
        print("[build_profile_papers] ERROR: the Scholar page has no paper rows", file=sys.stderr)
        return 1
    thr = cfg.profile_identity_jaccard
    ids = {i: r["arxiv_id"] for i, r in enumerate(rows) if r["arxiv_id"]}
    how = {i: "scholar_venue" for i in ids}
    failed: list[str] = []            # lookups that ERRORED (rate limit, network) — not "no match"
    s2_hit: dict[int, dict] = {}
    for i, r in enumerate(rows):
        if i in ids:
            continue
        ax, found_by, s2 = _resolve_title(r["title"], thr, failed)
        if found_by:
            how[i] = found_by
        if ax:
            ids[i] = ax
        if s2:
            s2_hit[i] = s2
    try:
        meta = arxiv_client.fetch_by_ids(ids.values())
    except Exception as e:  # noqa: BLE001 — without the metadata batch every row would be title-only
        print(f"[build_profile_papers] ERROR: arXiv refused the metadata batch ({e}). Nothing written — "
              "wait a few minutes and re-run (use --scholar-html with a saved page to avoid another Scholar "
              "request).", file=sys.stderr)
        return 3
    papers = []
    for i, r in enumerate(rows):
        m = meta.get(ids.get(i) or "") or {}
        s2 = s2_hit.get(i) or {}
        e = {
            "decision": None, "scholar_title": r["title"], "authors_scholar": r["authors_abbrev"],
            "venue": r["venue"], "year": r["year"], "scholar_citations": r["scholar_citations"],
            "resolved_by": how.get(i) if (m or s2) else None,
            "arxiv_id": m.get("arxiv_id"), "paper_id": s2.get("paperId"),
            "title": m.get("title") or r["title"], "abstract": m.get("abstract") or s2.get("abstract"),
            "authors": m.get("authors") or [], "first_date": (m.get("submitted") or "")[:10] or None,
            "categories": m.get("categories") or [], "primary_category": m.get("primary_category"),
        }
        e["key"] = PP.paper_key(e)
        papers.append(e)
    n_rows = len(papers)
    papers = _merge_duplicates(papers)
    if len(papers) < n_rows:
        print(f"[build_profile_papers] merged {n_rows - len(papers)} duplicate Scholar row(s) "
              "(journal version + preprint of the same arXiv paper)", file=sys.stderr)
    cpath = args.candidates_out or (profile_dir / "paper_candidates.json")
    carried = 0
    if cpath.exists():               # a re-read (profile rebuild) keeps the owner's earlier decisions by key,
        try:                         # so only rows that are NEW on the Scholar page still need one
            prev = {p.get("key"): p.get("decision")
                    for p in json.loads(cpath.read_text(encoding="utf-8")).get("papers") or []}
        except (ValueError, OSError):
            prev = {}
        for p in papers:
            if prev.get(p["key"]) in _DECISIONS:
                p["decision"] = prev[p["key"]]
                carried += 1
    name = parsed.get("name") or ""
    doc = {
        "name": name or None, "source": source, "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "name_forms": sorted({a for p in papers for a in p["authors"] if name and PP.same_person(a, name)}),
        "papers": papers,
    }
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    cpath.with_suffix(".md").write_text(_candidates_md(doc), encoding="utf-8")
    by_how: dict[str, int] = {}
    for p in papers:
        by_how[p["resolved_by"] or "title_only"] = by_how.get(p["resolved_by"] or "title_only", 0) + 1
    print(f"[build_profile_papers] Scholar '{name}': {len(papers)} rows · resolved {by_how} · "
          f"with abstract {sum(1 for p in papers if p['abstract'])} · name forms {doc['name_forms']} · "
          f"decisions carried over {carried}", file=sys.stderr)
    print(f"[build_profile_papers] wrote {cpath} (+ .md). Set every entry's decision to "
          f"{'/'.join(_DECISIONS)}, then run --from-list {cpath}", file=sys.stderr)
    if failed:
        print(f"[build_profile_papers] WARNING: {len(failed)} lookup(s) ERRORED (not 'no match') — those rows "
              f"may be title-only only because of it; re-run before confirming: {failed}", file=sys.stderr)
        return 3
    return 0


def _refill_stage(cfg, args) -> int:
    """Re-resolve ONLY the rows of a candidate list that still have no abstract (e.g. after a
    rate limit), keeping every decision already written. No Scholar request."""
    path = Path(args.refill)
    doc = json.loads(path.read_text(encoding="utf-8"))
    todo = [p for p in doc["papers"] if not p.get("abstract")]
    failed: list[str] = []
    found = [(p, *_resolve_title(p.get("scholar_title") or p.get("title") or "", cfg.profile_identity_jaccard, failed))
             for p in todo]
    try:
        meta = arxiv_client.fetch_by_ids([ax for _, ax, _, _ in found if ax])
    except Exception as e:  # noqa: BLE001
        print(f"[build_profile_papers] ERROR: arXiv refused the metadata batch ({e}); {path} unchanged",
              file=sys.stderr)
        return 3
    filled = 0
    for p, ax, found_by, s2 in found:
        m = meta.get(ax or "") or {}
        if not (m or s2.get("abstract")):
            continue
        p.update({
            "arxiv_id": m.get("arxiv_id") or p.get("arxiv_id"),
            "paper_id": s2.get("paperId") or p.get("paper_id"),
            "title": m.get("title") or p.get("title"),
            "abstract": m.get("abstract") or s2.get("abstract"),
            "authors": m.get("authors") or p.get("authors") or [],
            "first_date": (m.get("submitted") or "")[:10] or p.get("first_date"),
            "categories": m.get("categories") or p.get("categories") or [],
            "primary_category": m.get("primary_category") or p.get("primary_category"),
            "resolved_by": found_by,
        })
        p["key"] = PP.paper_key({k: p.get(k) for k in ("arxiv_id", "paper_id", "title")})
        filled += 1
    doc["papers"] = _merge_duplicates(doc["papers"])
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    path.with_suffix(".md").write_text(_candidates_md(doc), encoding="utf-8")
    print(f"[build_profile_papers] refill: {filled}/{len(todo)} title-only rows now have an abstract "
          f"(decisions kept) → {path}", file=sys.stderr)
    if failed:
        print(f"[build_profile_papers] WARNING: {len(failed)} lookup(s) ERRORED: {failed}", file=sys.stderr)
        return 3
    return 0


def _s2_enrich(papers: list[dict]) -> None:
    """paper_id + reference_ids in one batched S2 call (arXiv id, else S2 paper id)."""
    rows = [p for p in papers if p.get("arxiv_id") or p.get("paper_id")]
    ids = [f"ArXiv:{p['arxiv_id']}" if p.get("arxiv_id") else p["paper_id"] for p in rows]
    try:
        res = s2_client.papers_batch(ids, fields=("paperId", "references.paperId"))
    except Exception as e:  # noqa: BLE001 — the citation channel degrades, the profile does not
        print(f"[build_profile_papers] WARNING: S2 reference lookup failed ({e}); "
              "papers.json has no reference_ids — the citation channel will be empty", file=sys.stderr)
        return
    for p, s in zip(rows, res):
        if s:
            p["paper_id"] = p.get("paper_id") or s.get("paperId")
            p["reference_ids"] = [r.get("paperId") for r in (s.get("references") or []) if r.get("paperId")]


def _confirmed_stage(cfg, args, out_path: Path) -> int:
    data = json.loads(Path(args.from_list).read_text(encoding="utf-8"))
    rows = data.get("papers") or []
    undecided = [p for p in rows if p.get("decision") not in _DECISIONS]
    if undecided:
        print(f"[build_profile_papers] ERROR: {len(undecided)} entries have no decision "
              f"({'/'.join(_DECISIONS)}) — confirm every entry first:", file=sys.stderr)
        for p in undecided[:10]:
            print(f"    {p.get('key')}  {(p.get('title') or '')[:80]}", file=sys.stderr)
        return 1
    by_key: dict[str, dict] = {}
    conflicts: list[str] = []
    for p in rows:                      # a hand-edited list may repeat a paper: same decision → once
        k = p.get("key") or PP.paper_key(p)
        if k in by_key and by_key[k]["decision"] != p["decision"]:
            conflicts.append(f"{k}: {by_key[k]['decision']} vs {p['decision']}")
        by_key.setdefault(k, p)
    if conflicts:
        print(f"[build_profile_papers] ERROR: the same paper carries different decisions: {conflicts}",
              file=sys.stderr)
        return 1
    rows = list(by_key.values())
    cutoff = date.fromisoformat(args.cutoff) if args.cutoff else None
    kept: list[dict] = []
    dropped = 0
    for p in rows:
        if p["decision"] == "not":
            continue
        rec = {
            "key": p.get("key") or PP.paper_key(p), "paper_id": p.get("paper_id"), "arxiv_id": p.get("arxiv_id"),
            "title": p.get("title") or p.get("scholar_title") or "", "abstract": p.get("abstract"),
            "year": p.get("year"), "first_date": p.get("first_date"), "venue": p.get("venue"),
            "categories": p.get("categories") or [], "primary_category": p.get("primary_category"),
            "reference_ids": [], "peripheral": p["decision"] == "peripheral", "date_uncertain": False,
            "source": "scholar",
        }
        if cutoff is not None:
            keep, uncertain = PP.before_cutoff(rec, cutoff)
            if not keep:
                dropped += 1
                continue
            rec["date_uncertain"] = uncertain
        kept.append(rec)
    _s2_enrich(kept)
    core = [p for p in kept if not p["peripheral"]]
    coverage = {
        "n": len(kept), "n_core": len(core), "peripheral": len(kept) - len(core),
        "with_abstract": sum(1 for p in core if p["abstract"]),
        "with_arxiv": sum(1 for p in core if p["arxiv_id"]),
        "with_refs": sum(1 for p in core if p["reference_ids"]),
        "date_uncertain": sum(1 for p in kept if p["date_uncertain"]),
        "dropped_after_cutoff": dropped,
    }
    doc = {
        "s2_author_id": None, "author_name": data.get("name"), "name_forms": data.get("name_forms") or [],
        "source": "scholar", "scholar": data.get("source"), "cutoff": args.cutoff,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(), "coverage": coverage, "papers": kept,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[build_profile_papers] wrote {out_path}: coverage {coverage}", file=sys.stderr)
    if coverage["n_core"] and coverage["with_abstract"] < coverage["n_core"]:
        print(f"[build_profile_papers] note: {coverage['n_core'] - coverage['with_abstract']} core paper(s) have "
              "no abstract — they join their thread by title only", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None,
                    help="Output JSON path (default: data/profile/papers.json)")
    ap.add_argument("--max-papers", type=int, default=2000)
    ap.add_argument("--no-enrich", action="store_true",
                    help="Skip extra S2 calls to fill empty reference_ids")
    ap.add_argument("--verified-author-id", default=None,
                    help="Override researcher.s2_author_id from config (used after identity verification gate)")
    ap.add_argument("--website-only", action="store_true",
                    help="Build papers.json from data/profile/website_papers.json (Tier-2 stubs for unmatched)")
    ap.add_argument("--merged", action="store_true",
                    help="S2 author fetch (--verified-author-id required) plus website_only stubs from identity_check.json")
    ap.add_argument("--scholar-url", default=None,
                    help="Stage 1: read this Google Scholar profile (ONE robots-allowed request) → "
                         "paper_candidates.json for the owner to confirm")
    ap.add_argument("--scholar-html", type=Path, default=None,
                    help="Stage 1 from a Scholar profile page saved in a browser (when Scholar shows a CAPTCHA)")
    ap.add_argument("--candidates-out", type=Path, default=None,
                    help="Stage 1 output (default data/profile/paper_candidates.json)")
    ap.add_argument("--refill", type=Path, default=None,
                    help="Re-resolve only the rows of a candidate list that still lack an abstract "
                         "(e.g. after a rate limit); keeps every decision; no Scholar request")
    ap.add_argument("--from-list", type=Path, default=None,
                    help="Stage 2: build papers.json from a confirmed candidate list "
                         "(every entry's decision = self / peripheral / not)")
    ap.add_argument("--cutoff", default=None,
                    help="Stage 2: keep only papers whose first version is before this date (YYYY-MM-DD)")
    args = ap.parse_args()

    cfg = config.load_config()
    profile_dir = config.profile_dir()
    out_path = args.out or (profile_dir / "papers.json")
    supplement_path = profile_dir / "papers_supplement.json"

    if args.refill:
        return _refill_stage(cfg, args)
    if args.scholar_url or args.scholar_html:
        return _scholar_stage(cfg, args, profile_dir)
    if args.from_list:
        return _confirmed_stage(cfg, args, out_path)

    if args.merged and not args.verified_author_id and not cfg.s2_author_id:
        print("[build_profile_papers] ERROR: --merged requires --verified-author-id or s2_author_id in config",
              file=sys.stderr)
        return 1

    if args.website_only:
        # ── Website-only path ─────────────────────────────────────────────
        papers, s2_author_id, author_name = _fetch_from_website(profile_dir, args.no_enrich)
    elif args.merged:
        # ── Merged path: S2 author papers + website_only stubs ───────────
        effective_author_id = args.verified_author_id or cfg.s2_author_id
        print(f"[build_profile_papers] merged mode: fetching papers for S2 author {effective_author_id} ...",
              file=sys.stderr)
        try:
            author_info = s2_client.author_details(effective_author_id)
            author_name: str | None = author_info.get("name") or None
            if author_name:
                print(f"[build_profile_papers] author name from S2: {author_name!r}", file=sys.stderr)
        except Exception as e:
            print(f"[build_profile_papers] could not fetch author name: {e}", file=sys.stderr)
            author_name = None
        raw_papers = s2_client.author_papers(effective_author_id, max_papers=args.max_papers)
        papers = [s2_client.normalize_paper(p) for p in raw_papers]
        s2_author_id = effective_author_id
        print(f"[build_profile_papers] got {len(papers)} papers from S2", file=sys.stderr)

        # Append website_only_papers from identity_check.json as Tier-2 stubs
        identity_check_path = profile_dir / "identity_check.json"
        if identity_check_path.exists():
            try:
                ic = json.loads(identity_check_path.read_text(encoding="utf-8"))
                website_only = ic.get("website_only_papers") or []
            except Exception as e:
                print(f"[build_profile_papers] warning: could not read identity_check.json: {e}", file=sys.stderr)
                website_only = []
            if website_only:
                jaccard_threshold = cfg.profile_identity_jaccard
                s2_norm_titles = [_norm_title(p.get("title") or "") for p in papers]
                added = 0
                for wp in website_only:
                    title = (wp.get("title") or "").strip()
                    if not title:
                        continue
                    wp_norm = _norm_title(title)
                    if any(_jaccard(wp_norm, t) >= jaccard_threshold for t in s2_norm_titles):
                        continue  # already covered by S2 record
                    papers.append({
                        "paper_id": None,
                        "arxiv_id": wp.get("arxiv_id"),
                        "title": title,
                        "abstract": None,
                        "year": wp.get("year"),
                        "venue": wp.get("venue"),
                        "categories": [],
                        "reference_ids": [],
                        "status": "not_in_s2",
                    })
                    added += 1
                print(f"[build_profile_papers] merged mode: appended {added} website-only stubs",
                      file=sys.stderr)
        else:
            print("[build_profile_papers] merged mode: identity_check.json not found, proceeding with S2 papers only",
                  file=sys.stderr)
    else:
        # ── Standard S2 author fetch ──────────────────────────────────────
        effective_author_id = args.verified_author_id or cfg.s2_author_id
        if not effective_author_id:
            print("[build_profile_papers] ERROR: no s2_author_id in config and --verified-author-id not set. "
                  "Use --website-only or provide an author ID.", file=sys.stderr)
            return 1

        # ── Step 1: fetch from S2 ─────────────────────────────────────────
        print(f"[build_profile_papers] fetching papers for S2 author {effective_author_id} ...",
              file=sys.stderr)
        try:
            author_info = s2_client.author_details(effective_author_id)
            author_name: str | None = author_info.get("name") or None
            if author_name:
                print(f"[build_profile_papers] author name from S2: {author_name!r}", file=sys.stderr)
        except Exception as e:
            print(f"[build_profile_papers] could not fetch author name: {e}", file=sys.stderr)
            author_name = None
        raw_papers = s2_client.author_papers(effective_author_id, max_papers=args.max_papers)
        papers = [s2_client.normalize_paper(p) for p in raw_papers]
        s2_author_id = effective_author_id
        print(f"[build_profile_papers] got {len(papers)} papers from S2", file=sys.stderr)

    # ── Dedup ─────────────────────────────────────────────────────────────
    papers, n_dupes = _dedup(papers)
    print(
        f"[build_profile_papers] {len(papers)} papers after dedup (removed {n_dupes} duplicates)",
        file=sys.stderr,
    )

    # ── Reference enrichment ─────────────────────────────────────────────
    if not args.no_enrich:
        n_enriched = _enrich_references(papers)
        if n_enriched:
            print(
                f"[build_profile_papers] enriched references for {n_enriched} papers",
                file=sys.stderr,
            )

    # ── Merge supplement (backwards-compat: preserves prior cross-check data)
    supplement = _load_supplement(supplement_path)
    if supplement:
        orig_len = len(papers)
        papers = _merge_supplement(papers, supplement)
        new_papers_slice = papers[orig_len:]
        if not args.no_enrich and new_papers_slice:
            n_sup_enriched = _enrich_references(new_papers_slice)
            if n_sup_enriched:
                print(
                    f"[build_profile_papers] enriched references for {n_sup_enriched} supplement papers",
                    file=sys.stderr,
                )

    # ── Write papers.json ─────────────────────────────────────────────────
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "s2_author_id": s2_author_id,
                "author_name": author_name,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "papers": papers,
            },
            f,
            indent=2,
        )
    print(f"[build_profile_papers] wrote {out_path} ({len(papers)} papers total)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
