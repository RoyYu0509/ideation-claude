"""REC-SYSTEM-V2 profile path: papers helpers, the confirmed-list stage, profile_finalize, the v2 prefetch."""
import argparse
import json
from datetime import date

import numpy as np
import pytest

import build_profile_papers as B
import prefetch as PF
import profile_finalize as F
from lib import channel_spec as CS
from lib import embeddings, s2_client
from lib import keyphrases as KP
from lib import profile_papers as PP
from lib.config import ConfigError, load_config


@pytest.fixture(autouse=True)
def _isolated_data_root(tmp_path, monkeypatch):
    # load_config layers <data_root>/researcher.json — keep a stray one out of these tests
    monkeypatch.setenv("AR_DATA_ROOT", str(tmp_path))


# ── lib/profile_papers ────────────────────────────────────────────────────────

def test_cutoff_names_and_windows():
    c = date(2026, 6, 15)
    assert PP.before_cutoff({"first_date": "2026-06-14"}, c) == (True, False)
    assert PP.before_cutoff({"first_date": "2026-06-15"}, c) == (False, False)
    assert PP.before_cutoff({"year": 2026}, c) == (True, True)       # same year, no date → kept, flagged
    assert PP.before_cutoff({"year": 2027}, c) == (False, False)
    assert PP.same_person("Doe, Jane", "Jane Doe")
    assert not PP.same_person("J. Doe", "Jane Doe")           # initials never match a full name
    assert PP.window_start(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert PP.paper_key({"arxiv_id": "2601.00001"}) == "2601.00001"


def test_title_phrases_add_spelling_variants_without_mangling_short_words():
    from lib import arxiv_client as A
    ps = A.title_phrases("A theoretical case study of the generalization of machine-learned potentials")
    assert ps == ["theoretical case study of the generalization of machine",
                  "theoretical case study of the generalisation of machine"]
    assert A.title_phrases("Size effects in prize models") == ["Size effects in prize models"]
    assert A.title_phrases("Global optimisation of lattices")[-1] == "Global optimization of lattices"


# ── build_profile_papers --from-list ─────────────────────────────────────────

def test_confirmed_stage_needs_every_decision_and_applies_the_cutoff(tmp_path, monkeypatch, write_config):
    monkeypatch.setattr(s2_client, "papers_batch", lambda ids, fields=None: [None] * len(ids))
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False}))
    rows = [
        {"key": "a", "arxiv_id": "2601.00001", "title": "A", "abstract": "x", "first_date": "2026-01-01", "decision": "self"},
        {"key": "b", "arxiv_id": "2607.00002", "title": "B", "abstract": "y", "first_date": "2026-07-01", "decision": "self"},
        {"key": "c", "title": "C", "year": 2026, "decision": "peripheral"},
        {"key": "d", "title": "D", "year": 2020, "decision": None},
    ]
    lst, out = tmp_path / "cands.json", tmp_path / "papers.json"
    lst.write_text(json.dumps({"name": "Ada", "papers": rows}))
    ns = argparse.Namespace(from_list=lst, cutoff="2026-06-15")
    assert B._confirmed_stage(cfg, ns, out) == 1                     # 'd' undecided → refuse
    rows[3]["decision"] = "not"
    lst.write_text(json.dumps({"name": "Ada", "papers": rows}))
    assert B._confirmed_stage(cfg, ns, out) == 0
    doc = json.loads(out.read_text())
    assert [p["key"] for p in doc["papers"]] == ["a", "c"]           # b after the cutoff, d not the researcher
    assert doc["papers"][1]["peripheral"] and doc["papers"][1]["date_uncertain"]
    assert doc["coverage"]["dropped_after_cutoff"] == 1 and doc["author_name"] == "Ada"


def test_scholar_duplicates_merge_and_conflicting_decisions_refuse(tmp_path, monkeypatch, write_config):
    rows = [{"arxiv_id": "2309.1", "scholar_title": "Adaptive QC (journal)", "venue": "J. Comp. Phys.", "year": 2024},
            {"arxiv_id": None, "scholar_title": "Workshop paper", "venue": "Workshop", "year": 2026},
            {"arxiv_id": "2309.1", "scholar_title": "Adaptive QC (preprint)", "venue": "arXiv:2309.1", "year": 2023}]
    merged = B._merge_duplicates([dict(r) for r in rows])
    assert [r["scholar_title"] for r in merged] == ["Adaptive QC (journal)", "Workshop paper"]
    assert merged[0]["scholar_duplicates"][0]["venue"] == "arXiv:2309.1"

    monkeypatch.setattr(s2_client, "papers_batch", lambda ids, fields=None: [None] * len(ids))
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False}))
    lst = tmp_path / "cands.json"
    lst.write_text(json.dumps({"name": "Ada", "papers": [
        {"key": "2309.1", "arxiv_id": "2309.1", "title": "QC", "decision": "self"},
        {"key": "2309.1", "arxiv_id": "2309.1", "title": "QC", "decision": "not"}]}))
    assert B._confirmed_stage(cfg, argparse.Namespace(from_list=lst, cutoff=None), tmp_path / "p.json") == 1


def test_refill_resolves_title_only_rows_and_keeps_decisions(tmp_path, monkeypatch, write_config):
    from lib import arxiv_client
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False}))
    monkeypatch.setattr(arxiv_client, "search_title", lambda t, max_results=3: [])   # e.g. British spelling on arXiv
    monkeypatch.setattr(s2_client, "search_by_title",
                        lambda t, **kw: [{"paperId": "P1", "title": t, "abstract": "s2 abstract",
                                          "externalIds": {"ArXiv": "2305.00001"}}])
    monkeypatch.setattr(arxiv_client, "fetch_by_ids", lambda ids: {"2305.00001": {
        "arxiv_id": "2305.00001", "title": "A framework for a generalisation analysis", "abstract": "arXiv abstract",
        "authors": ["Ada Lovelace"], "submitted": "2023-05-01T00:00:00+00:00",
        "categories": ["math.NA"], "primary_category": "math.NA"}})
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"name": "Ada", "source": {"kind": "url", "url": "u"},
                                "fetched_at_utc": "2026-09-12T00:00:00", "name_forms": [], "papers": [
        {"key": "t:abc", "scholar_title": "A framework for a generalization analysis",
         "title": "A framework for a generalization analysis", "abstract": None, "decision": "self",
         "arxiv_id": None, "paper_id": None, "venue": "MMS", "year": 2023, "resolved_by": None,
         "authors": [], "first_date": None, "categories": [], "primary_category": None},
        {"key": "2601.1", "arxiv_id": "2601.1", "title": "Has abstract", "abstract": "x", "decision": None}]}))
    assert B._refill_stage(cfg, argparse.Namespace(refill=path)) == 0
    p = json.loads(path.read_text())["papers"][0]
    assert (p["key"], p["abstract"], p["first_date"], p["decision"], p["resolved_by"]) == \
        ("2305.00001", "arXiv abstract", "2023-05-01", "self", "s2_title")
    assert (tmp_path / "c.md").exists()


# ── profile_finalize (v3: parts → coverage check → merge) ─────────────────────

def _papers():
    return {"cutoff": "2026-06-15", "papers": [
        {"key": "2601.00001", "arxiv_id": "2601.00001", "title": "RFM for PDEs",
         "abstract": "We develop a random feature method for time-dependent PDEs.", "reference_ids": ["R1", "R2"],
         "first_date": "2026-01-10", "year": 2026, "categories": ["math.NA", "cs.LG"], "primary_category": "math.NA"},
        {"key": "2502.00002", "arxiv_id": "2502.00002", "title": "RFM 2",
         "abstract": "A random feature method with adaptive sampling.", "reference_ids": ["R1"],
         "first_date": "2025-02-01", "year": 2025, "categories": ["math.NA"], "primary_category": "math.NA"},
        {"key": "2409.00003", "arxiv_id": "2409.00003", "title": "VQE trainability",
         "abstract": "Barren plateaus limit variational quantum eigensolvers.", "reference_ids": ["R3"],
         "first_date": "2024-09-01", "year": 2024, "categories": ["quant-ph"], "primary_category": "quant-ph"},
        {"key": "1901.00004", "arxiv_id": "1901.00004", "title": "Old QM/MM",
         "abstract": "An a posteriori error estimate for QM/MM coupling.", "reference_ids": [],
         "first_date": "2019-01-01", "year": 2019, "categories": ["math.NA", "cond-mat.mtrl-sci"], "primary_category": "cond-mat.mtrl-sci"},
        {"key": "2505.00005", "arxiv_id": "2505.00005", "title": "Big collaboration", "abstract": "e",
         "first_date": "2025-05-01", "year": 2025, "categories": ["cs.CL"], "primary_category": "cs.CL", "peripheral": True},
    ]}


def _notes():
    return [
        {"key": "2601.00001", "field": "time-dependent PDEs", "method": "random feature method",
         "keywords": ["random feature method", "PDEs"]},
        {"key": "2502.00002", "field": "adaptive sampling", "method": "random feature method",
         "keywords": ["random feature method"]},
        {"key": "2409.00003", "field": "variational quantum algorithms", "method": "trainability analysis",
         "keywords": ["variational quantum eigensolvers", "barren plateaus"]},
        {"key": "1901.00004", "field": "multiscale coupling", "method": "a posteriori error estimate",
         "keywords": ["a posteriori error estimate", "QM/MM coupling"]},
    ]


def _parts(sha="sha"):
    """What the agent and profile_tools.py write — the agent writes no retrieval phrases at all."""
    return {"paper_notes": _notes(),
            "threads": [{"name": "Random features", "summary": "s", "papers": ["2601.00001", "2502.00002"]},
                        {"name": "Quantum", "summary": "s", "papers": ["2409.00003"]},
                        {"name": "QM/MM", "summary": "s", "papers": ["1901.00004"]}],
            "recent_direction": "Random features continue; quantum is new.",
            "keywords_extracted": {"papers_sha256": sha, "note": "n", "pool": {"file": "w.json"},
                                   "rows": [{"phrase": "random feature method", "own_df": 2, "bg_df": 0, "score": 1.0}]},
            "categories": {"papers_sha256": sha, "chosen": ["math.NA"], "note": "n", "table": {}}}


def _fin(write_config, parts=None, papers=None, cfg_over=None, **kw):
    args = dict(md_text="x" * 100, papers_sha="sha",
                companions={"citation-graph.json": None, "ref_abstracts.json": None},
                ref_abstracts={"R1": {"title": "R1", "abstract": "a reference abstract"}})
    args.update(kw)
    return F.finalize(parts if parts is not None else _parts(), papers or _papers(),
                      load_config(write_config(cfg_over or {})), date(2026, 6, 15), **args)


def test_finalize_v3_merges_every_part_only_when_every_variant_is_derivable(write_config):
    final, rep = _fin(write_config)
    assert rep["ok"], rep["errors"]
    assert all(r["ok"] for r in rep["coverage"]), [r for r in rep["coverage"] if not r["ok"]]
    assert {r["id"] for r in rep["coverage"]} == {v.id for v in CS.VARIANTS}
    t = {x["name"]: x for x in final["threads"]}
    assert (t["Random features"]["status"], t["Random features"]["n_recent"]) == ("active", 2)
    assert t["Quantum"]["status"] == "active" and t["Quantum"]["emerging"] is True
    assert t["QM/MM"]["status"] == "legacy"
    assert final["schema_version"] == CS.SCHEMA_V3
    assert final["finalized_by"].startswith("profile_finalize.py")   # prefetch refuses a profile without the stamp
    assert all(t["keywords"] == [] for t in final["threads"])        # thread-level phrases are retired
    assert final["keywords"] == ["random feature method"] and final["keywords_source"] == "extracted"
    assert final["paper_notes"] == _notes()                          # the agent's notes are carried verbatim
    assert final["arxiv_categories"] == ["math.NA"]                  # from the tools' part, not recomputed
    prod = {r["id"] for r in rep["coverage"] if r["production"]}
    # 生产默认(EVAL-PLAN 修订 #15,2026-09-20,按 K = 100 挑):thread(+refs) + bm25(agent+extracted) + category;
    # 修订 #10 的 dense(paper notes) + thread(members) 那一组退为消融臂
    assert prod == {"thread:members_refs", "bm25:b3", "category:weights"}


def test_finalize_rejects_bad_grouping(write_config):
    parts = _parts()
    parts["threads"][1]["papers"] = []                               # quantum paper unassigned; thread empty
    parts["threads"][2]["papers"] = ["1901.00004", "2601.00001"]     # 2601 now in two threads
    _, rep = _fin(write_config, parts=parts)
    errs = " | ".join(rep["errors"])
    assert not rep["ok"]
    assert "belong to no thread" in errs and "2409.00003" in errs
    assert "exactly one" in errs and "no non-peripheral member" in errs


def test_finalize_rejects_ungrounded_and_missing_notes(write_config):
    parts = _parts()
    parts["paper_notes"][0]["keywords"] = ["random feature method", "neural operators"]   # not in its paper
    del parts["paper_notes"][3]                                                          # a core paper without a note
    _, rep = _fin(write_config, parts=parts)
    errs = " | ".join(rep["errors"])
    assert not rep["ok"]
    assert "2601.00001" in errs and "'neural operators' is not printed" in errs
    assert "1 core paper(s) without a note" in errs and "1901.00004" in errs
    missing = {r["id"] for r in rep["coverage"] if not r["ok"]}
    assert {"dense:dN", "bm25:b1", "bm25:b2", "bm25:b3"} <= missing  # incomplete notes never pass as complete


def test_finalize_refuses_missing_or_stale_tool_parts(write_config):
    parts = _parts()
    del parts["keywords_extracted"]
    _, rep = _fin(write_config, parts=parts, part_problems=["parts/keywords_extracted.json is missing"])
    missing = {r["id"]: r for r in rep["coverage"] if not r["ok"]}
    assert not rep["ok"] and "bm25:b4" in missing and "bm25:b3" in missing
    assert missing["bm25:b4"]["source"] == CS.COMPANION               # never falls back to the agent's phrases
    _, rep = _fin(write_config, parts=_parts(sha="other"))
    assert any("different papers.json" in e for e in rep["errors"])


def test_finalize_refuses_missing_companions(write_config):
    _, rep = _fin(write_config, companions={"citation-graph.json": "citation graph not found",
                                            "ref_abstracts.json": "not built — run scripts/profile_tools.py"},
                  ref_abstracts=None)
    missing = {r["id"] for r in rep["coverage"] if not r["ok"]}
    assert missing == {"citation:graph", "refs:corpus", "thread:members_refs"}
    assert not rep["ok"] and sum("coverage" in e for e in rep["errors"]) == 3


def test_finalize_profile_md_cap_and_absence(write_config):
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False}))
    _, rep = _fin(write_config, md_text="x" * (cfg.profile_md_max_chars + 1))
    assert any("profile.md is" in e for e in rep["errors"])
    _, rep = _fin(write_config, md_text=None)
    assert any("profile.md is missing" in e for e in rep["errors"])


def test_tools_category_rule_needs_two_own_papers_by_default(write_config, tmp_path):
    import profile_tools as T
    T.step_categories(_papers()["papers"], "sha", load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False})), tmp_path / "c.json")
    doc = json.loads((tmp_path / "c.json").read_text())
    assert doc["chosen"] == ["math.NA"] and doc["papers_sha256"] == "sha"   # the only category on >= 2 own papers
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "researcher.arxiv_categories": ["math.NA", "quant-ph"],
                                    "researcher.arxiv_categories_fixed": True}))
    T.step_categories(_papers()["papers"], "sha", cfg, tmp_path / "c.json")
    assert json.loads((tmp_path / "c.json").read_text())["chosen"] == ["math.NA", "quant-ph"]


def test_tools_extracted_phrases_need_a_weekly_pool(write_config, tmp_path):
    import profile_tools as T
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False}))
    with pytest.raises(RuntimeError, match="no weekly candidate pool"):
        T.step_keywords(_papers()["papers"], "sha", None, cfg, tmp_path / "k.json")   # no silent fallback
    pool = tmp_path / "week-2026-W24-candidates.json"
    pool.write_text(json.dumps({"candidates": [{"title": "A random feature method for PDEs", "abstract": ""},
                                               {"title": "Random walks with feature maps", "abstract": ""}]}))
    T.step_keywords(_papers()["papers"], "sha", pool, cfg, tmp_path / "k.json")
    rows = {r["phrase"]: r for r in json.loads((tmp_path / "k.json").read_text())["rows"]}
    assert rows["random feature method"]["own_df"] == 2
    assert rows["random feature method"]["bg_df"] == 1              # adjacent words only, not "random ... feature"
    assert "random walks" not in rows                               # only the own papers supply candidates


def test_check_only_reports_a_v2_profile_honestly_and_writes_nothing(write_config, tmp_path, capsys):
    pdir = tmp_path / "data" / "profile"
    pdir.mkdir(parents=True)
    legacy = {"schema_version": 2, "as_of": "2026-06-15", "keywords": ["random feature method"],
              "recent_direction": "r",
              "threads": [{"name": "RF", "summary": "s", "papers": ["2601.00001", "2502.00002"], "keywords": []}]}
    (pdir / "profile.json").write_text(json.dumps(legacy))
    (pdir / "papers.json").write_text(json.dumps(_papers()))
    before = sorted(x.name for x in pdir.iterdir())
    rc = F.check_only(pdir, load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False})))
    out = capsys.readouterr().out
    assert rc == 1 and sorted(x.name for x in pdir.iterdir()) == before
    rows = {line.split()[0]: line for line in out.splitlines() if ":" in line.split(" ")[0]}
    assert "paper_notes" in rows["dense:dN"] and "MISSING" in rows["dense:dN"]
    assert "ok" in rows["bm25:b1"].split()                          # a 2026-09-12 profile's keywords are the agent's
    assert "MISSING" in rows["bm25:b4"] and "citation-graph.json" in rows["citation:graph"]


def test_config_accepts_scholar_only_and_rejects_bad_v2_keys(write_config):
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "researcher.personal_website": None, "researcher.s2_author_id": None,
                                    "researcher.google_scholar_url": "https://scholar.google.com/citations?user=ExampleID0AJ"}))
    assert cfg.google_scholar_url
    with pytest.raises(ConfigError, match="channel_set"):
        load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.channel_set": "v3"}))
    with pytest.raises(ConfigError, match="pool_quota"):
        load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.pool_quota.bm25": -1}))
    with pytest.raises(ConfigError, match="arxiv_categories_fixed"):
        load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "researcher.arxiv_categories_fixed": True}))


# ── prefetch v2 (fake encoder: bag of words over a tiny vocabulary) ───────────

_VOCAB = ["rfm", "pde", "vqe", "quantum", "graph", "llm"]


def _fake_encode(model, texts, **kw):
    return np.stack([np.array([t.lower().count(w) for w in _VOCAB], dtype=np.float32) + 1e-3 for t in texts])


def _toy():
    cands = [{"arxiv_id": f"c{i}", "title": t, "abstract": "", "categories": ["cs.LG"]} for i, t in enumerate(
        ["rfm pde solver", "rfm pde", "rfm", "vqe quantum", "quantum", "graph llm", "llm", "graph"])]
    profile = {"schema_version": 2, "finalized_by": "test", "as_of": "2026-06-15", "keywords": ["graph llm"], "threads": [
        {"name": "RFM", "keywords": ["rfm pde"], "papers": ["p1"], "status": "active", "n_recent": 5},
        {"name": "Quantum", "keywords": ["vqe"], "papers": ["p2"], "status": "active", "n_recent": 1}]}
    papers = [{"key": "p1", "title": "rfm pde", "abstract": "rfm", "categories": ["math.NA"]},
              {"key": "p2", "title": "vqe quantum", "abstract": "quantum", "categories": ["quant-ph"]}]
    return {"week": "2026-W24", "candidates": cands}, profile, papers


def _cfg(write_config, **over):
    """玩具 v2 画像用的配置:BM25 用抽词表 —— 这个画像没有 agent 关键词,也没有共享的参考文献。"""
    return load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False,
                                     "scout.prefetch_top_k": 6, "scout.top_n_papers": 2,
                                     "prefetch.pool_quota.thread_floor": 2, "prefetch.pool_quota.bm25": 2,
                                     "prefetch.pool_quota.citation": 0} | over))


def test_v2_quota_pool_seats_every_active_thread(monkeypatch, write_config):
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    cand, profile, papers = _toy()
    pre, ch = PF.run(cand, profile, papers, _cfg(write_config, **{"prefetch.thread_fusion": "per_thread"}), top_k=6, channel_set="v2", ref_abstracts={}, pool_rule="quota",
                     signals=set(), use_citation=False, use_quality=False)
    ids = [c["arxiv_id"] for c in pre["candidates"]]
    assert len(ids) == 6
    assert {"c3", "c4"} <= set(ids)                                  # the one-paper thread keeps its floor seats
    assert ch["channels"]["thread_1"][0] in {"c0", "c1"}             # max cosine to the RFM member paper
    assert ch["thread_labels"] == {"thread_1": "RFM", "thread_2": "Quantum"}
    assert pre["seats"]["thread_2"] == 2
    assert all(c["seated_by"] for c in pre["candidates"])
    assert set(pre["candidates"][0]["channel_ranks"]) == set(ch["channels"])


def test_v2_refuses_an_unfinalized_profile(monkeypatch, write_config):
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    cand, profile, papers = _toy()
    profile.pop("schema_version")
    with pytest.raises(SystemExit):
        PF.run(cand, profile, papers, _cfg(write_config), top_k=6, channel_set="v2", ref_abstracts={}, pool_rule="quota",
               signals=set(), use_citation=False, use_quality=False)


def test_v2_refuses_a_draft_that_only_declares_schema_version(monkeypatch, write_config):
    """F6: a hand-written draft used to pass by writing schema_version 2 itself."""
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    cand, profile, papers = _toy()
    profile.pop("finalized_by")
    with pytest.raises(SystemExit, match="finalized_by"):
        PF.run(cand, profile, papers, _cfg(write_config), top_k=6, channel_set="v2", ref_abstracts={}, pool_rule="rrf",
               signals=set(), use_citation=False, use_quality=False)


def test_category_channel_ignores_peripheral_papers_and_averages_ties():
    own = [{"categories": ["math.NA"], "primary_category": "math.NA"},
           {"categories": ["math.NA", "cs.LG"], "primary_category": "math.NA"},
           {"categories": ["cs.CL"], "primary_category": "cs.CL", "peripheral": True}]
    cands = [{"arxiv_id": "hi", "categories": ["math.NA", "cs.LG"]}, {"arxiv_id": "a", "categories": ["math.NA"]},
             {"arxiv_id": "b", "categories": ["math.NA"]}, {"arxiv_id": "lo", "categories": ["cs.LG"]},
             {"arxiv_id": "zero", "categories": ["cs.CL"]}]
    ids, ranks = PF._category_channel(cands, own)
    assert ids[0] == "hi"                                            # math.NA (2) + cs.LG (1) is the highest score
    assert "zero" not in ids                                         # only the peripheral paper carries cs.CL
    assert ranks == [1.0, 2.5, 2.5, 4.0]
    assert PF._category_channel(cands, [{"categories": []}]) is None


def test_v2_category_channel_enters_the_fusion_only_when_enabled(monkeypatch, write_config):
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    cand, profile, papers = _toy()
    papers[0].update({"categories": ["math.NA", "cs.LG"], "primary_category": "math.NA"})
    papers[1].update({"categories": ["math.NA"], "primary_category": "math.NA"})
    for c, cats in zip(cand["candidates"], (["math.NA"], ["cs.LG"], ["hep-th"], ["math.NA", "cs.LG"],
                                            ["hep-th"], ["math.NA"], ["cs.LG"], ["hep-th"])):
        c["categories"] = cats
    cfg = _cfg(write_config)
    pre, ch = PF.run(cand, profile, papers, cfg, top_k=6, channel_set="v2", ref_abstracts={}, pool_rule="rrf", signals=set(),
                     use_citation=False, use_quality=False, use_category=True)
    assert pre["category_channel"] is True
    assert ch["channels"]["category"][0] == "c3"                     # math.NA (2) + cs.LG (1)
    assert set(ch["channels"]["category"]) == {"c3", "c0", "c5", "c1", "c6"}   # hep-th scores 0, never enters
    _, off = PF.run(cand, profile, papers, cfg, top_k=6, channel_set="v2", ref_abstracts={}, pool_rule="rrf", signals=set(),
                    use_citation=False, use_quality=False, use_category=False)
    assert "category" not in off["channels"]


# ── keyphrases: the BM25 query, extracted from the researcher's own papers ────

def test_keyphrases_need_two_own_papers_and_rank_the_rare_ones_first():
    own = ["A random feature method for elliptic problems", "Random feature method with adaptive sampling",
           "Deep learning for weather forecasting", "Deep learning for climate forecasting"]
    bg = ["deep learning for images"] * 30 + ["a lattice model"] * 5
    rows = KP.extract(own, bg, k=20)
    by = {r["phrase"]: r for r in rows}
    assert by["random feature method"]["own_df"] == 2 and by["random feature method"]["bg_df"] == 0
    assert "adaptive sampling" not in by                             # only one own paper prints it
    order = [r["phrase"] for r in rows]
    assert order.index("random feature method") < order.index("deep learning")   # rarer in the background wins


def test_keyphrases_never_start_or_end_with_a_filler_word():
    ph = KP.phrases_of("We propose a fast multipole solver.")
    assert "fast multipole solver" in ph
    assert not any(p.startswith("we ") or p.endswith(" propose") or p == "propose" for p in ph)


def test_keyphrases_fallback_without_a_background_pool():
    rows = KP.own_frequency_fallback(["random feature method", "random feature method"], k=5)
    assert rows[0]["own_df"] == 2 and rows[0]["bg_df"] is None


def test_legacy_rrf_path_is_unchanged(monkeypatch, write_config):
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    cand, profile, papers = _toy()
    pre, ch = PF.run(cand, profile, papers, _cfg(write_config, **{"prefetch.thread_fusion": "per_thread"}), top_k=6, channel_set="legacy", pool_rule="rrf",
                     signals={"thread"}, use_citation=False, use_quality=False)
    assert [c["seated_by"] for c in pre["candidates"]] == ["rrf"] * 6
    assert list(ch["channels"])[:1] == ["dense"] and "bm25" in ch["channels"]
    scores = [c["rrf_score"] for c in pre["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_v2_title_only_members_never_feed_a_channel(monkeypatch, write_config):
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    cand, profile, papers = _toy()
    papers[1]["abstract"] = None                                     # the Quantum thread's only member: title only
    pre, ch = PF.run(cand, profile, papers, _cfg(write_config), top_k=6, channel_set="v2", ref_abstracts={}, pool_rule="rrf",
                     signals=set(), use_citation=False, use_quality=False)
    assert "thread_2" not in ch["channels"] and "thread_2" not in ch["thread_labels"]
    assert "thread_1" in ch["channels"] and "bm25" in ch["channels"]
    d = _papers()
    d["papers"][2]["abstract"] = None                                # finalize says so up front
    _, rep = _fin(write_config, papers=d)
    assert any("no semantic channel" in w for w in rep["warnings"])


def test_v2_prf_channel_leaves_out_peripheral_papers(monkeypatch, write_config):
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    core = {"key": "p1", "title": "rfm pde", "abstract": "rfm", "year": 2026}
    side = {"key": "p3", "title": "graph llm", "abstract": "llm", "year": 2026, "peripheral": True}
    members, weights = CS.prf_members(CS.view({}, [core, side], as_of="2026-06-15",
                                              params={"prf_half_life_months": 24}))
    assert [m["key"] for m in members] == ["p1"] and len(weights) == 1    # v2: core papers only
    assert not np.allclose(PF._prf_vec("m", [core], 2023),
                           PF._prf_vec("m", [core, side], 2023))            # the legacy call keeps it (V1 arm)
    cand, profile, papers = _toy()
    for p in papers:
        p["year"] = 2026
    pre, ch = PF.run(cand, profile, papers, _cfg(write_config), top_k=6, channel_set="v2", ref_abstracts={}, pool_rule="rrf",
                     signals={"prf"}, use_citation=False, use_quality=False)
    assert list(ch["channels"])[0] == "prf"
    assert [c["seated_by"] for c in pre["candidates"]] == ["rrf"] * 6


def test_default_signals_prf_in_both_sets_thread_queries_legacy_only(write_config):
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_prf": True, "prefetch.use_thread_queries": True,
                                    "prefetch.use_category_rebalance": False}))
    assert PF.default_signals(cfg, "v2") == {"prf"}
    assert PF.default_signals(cfg, "legacy") == {"prf", "thread"}


# ── one researcher's identity never leaks into another's instance ─────────────

def test_researcher_json_inherits_no_identity_from_the_shared_config(tmp_path, write_config):
    (tmp_path / "researcher.json").write_text(json.dumps(
        {"researcher": {"google_scholar_url": "https://scholar.google.com/citations?user=EXPERT"}}))
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "researcher.s2_api_key": "k-shared"}))
    assert cfg.google_scholar_url.endswith("user=EXPERT")
    assert (cfg.personal_website, cfg.s2_author_id, cfg.author_aliases, cfg.arxiv_categories_fixed) == \
        (None, None, [], False)                                      # not the owner's website / aliases
    assert cfg.raw["researcher"]["s2_api_key"] == "k-shared"          # the credential still comes from config
    (tmp_path / "researcher.json").write_text(json.dumps({"researcher": {"author_aliases": ["Ada"]}}))
    with pytest.raises(ConfigError, match="requires researcher"):
        load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False}))                                  # no identity source → refuse, never the owner's


def test_set_researcher_pins_every_identity_key(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    script = Path(PF.__file__).resolve().parents[1] / "bin" / "set_researcher.py"
    store = tmp_path / "inst" / "researcher.json"
    subprocess.run([sys.executable, str(script), "--store", str(store), "--scholar", "https://s/x",
                    "--website", "null", "--s2-id", "null", "--aliases", "Ada Lovelace||A. Lovelace",
                    "--categories", "null"], check=True)
    assert json.loads(store.read_text())["researcher"] == {
        "google_scholar_url": "https://s/x", "personal_website": None, "s2_author_id": None,
        "author_aliases": ["Ada Lovelace", "A. Lovelace"], "arxiv_categories": None}
    got = subprocess.run([sys.executable, str(script), "--store", str(store), "--get"],
                         check=True, capture_output=True, text=True).stdout
    assert json.loads(got) == {"personal_website": None, "s2_author_id": None, "google_scholar_url": "https://s/x"}


# ── Phase 0b decisions: relayed mechanically, kept across a Scholar re-read ────

def test_set_paper_decisions_marks_rest_and_refuses_ambiguity(tmp_path):
    import sys
    from unittest.mock import patch
    import set_paper_decisions as SPD
    p = tmp_path / "paper_candidates.json"
    p.write_text(json.dumps({"name": "Ada", "source": {"kind": "url", "url": "u"},
                             "fetched_at_utc": "2026-09-13T00:00:00", "name_forms": [], "papers": [
        {"key": "2601.1", "title": "Random feature methods", "decision": None},
        {"key": "2601.2", "title": "Protein text question answering", "decision": None},
        {"key": "t:abc", "title": "Workshop note on random walks", "decision": None}]}))
    doc = json.loads(p.read_text())
    assert SPD.apply(doc, ["random=not"], "self")                    # 'random' is in two titles → error ...
    assert all(r["decision"] is None for r in doc["papers"])         # ... and nothing applied, not even --rest
    assert SPD.apply(doc, ["protein text=peripheral", "t:abc=not"], "self") == []
    assert [r["decision"] for r in doc["papers"]] == ["self", "peripheral", "not"]
    with patch.object(sys, "argv", ["x", "--candidates", str(p), "--check"]):
        assert SPD.main() == 1                                       # the file itself is still undecided
    with patch.object(sys, "argv", ["x", "--candidates", str(p), "--mark", "Protein text=peripheral", "--rest", "self"]):
        assert SPD.main() == 0
    assert [r["decision"] for r in json.loads(p.read_text())["papers"]] == ["self", "peripheral", "self"]
    assert (tmp_path / "paper_candidates.md").exists()


def test_scholar_reread_carries_decisions_over_by_key(tmp_path, monkeypatch, write_config):
    from lib import arxiv_client, scholar_profile
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False}))
    rows = [{"title": "Old paper", "arxiv_id": "2601.00001", "authors_abbrev": "A Lovelace",
             "venue": "arXiv:2601.00001", "year": 2026, "scholar_citations": 1},
            {"title": "New paper", "arxiv_id": "2609.00002", "authors_abbrev": "A Lovelace",
             "venue": "arXiv:2609.00002", "year": 2026, "scholar_citations": 0}]
    monkeypatch.setattr(scholar_profile, "parse", lambda text: {"name": "Ada Lovelace", "rows": [dict(r) for r in rows]})
    monkeypatch.setattr(arxiv_client, "fetch_by_ids", lambda ids: {i: {
        "arxiv_id": i, "title": i, "abstract": "a", "authors": ["Ada Lovelace"], "submitted": "2026-01-01T00:00:00+00:00",
        "categories": ["math.NA"], "primary_category": "math.NA"} for i in ids})
    html = tmp_path / "page.html"
    html.write_text("<html></html>")
    cpath = tmp_path / "paper_candidates.json"
    cpath.write_text(json.dumps({"papers": [{"key": "2601.00001", "decision": "self"}, {"key": "gone", "decision": "not"}]}))
    ns = argparse.Namespace(scholar_html=html, scholar_url=None, candidates_out=cpath)
    assert B._scholar_stage(cfg, ns, tmp_path) == 0
    got = {p["key"]: p["decision"] for p in json.loads(cpath.read_text())["papers"]}
    assert got == {"2601.00001": "self", "2609.00002": None}          # the known row keeps its decision; only the new one asks
