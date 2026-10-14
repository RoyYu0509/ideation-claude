"""lib/citation_graph.py + the graph citation mode (mirrors test_citation_signal.py: S2 is patched)."""
import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import citation_graph as CG
from lib import citation_signal


def _make_paper(refs: list[str], paper_id: str | None = None) -> dict:
    return {"references": [{"paperId": r} for r in refs], "paperId": paper_id}


# P1 → A → X ; P1 → Adam ; A → Adam   (Adam = the tool paper everyone cites)
PROFILE_PAPERS = [{"paper_id": "P1", "reference_ids": ["A", "Adam"], "year": 2024, "categories": ["math.NA"]}]
REFS_BY_NODE = {"P1": ["A", "Adam"], "A": ["X", "Adam"]}
COUNTS = {"P1": 5, "A": 40, "X": 20, "Adam": 170_000}


def _graph(alpha=0.85, counts=None):
    return CG.build_graph_doc(["P1"], REFS_BY_NODE, counts or COUNTS, papers_sha256="abc", built_utc="t", alpha=alpha)


# ── pure math ─────────────────────────────────────────────────────────────────

def test_build_edges_sorted_deduped_no_self_loops():
    nodes, edges = CG.build_edges(["P1"], {"P1": ["A", "A", "P1", "Adam"], "A": ["X"]})
    assert nodes == ["A", "Adam", "P1", "X"]
    assert edges == [("A", "X"), ("P1", "A"), ("P1", "Adam")]


def test_ppr_mass_sums_to_one_with_dangling_layer3():
    nodes, edges = CG.build_edges(["P1"], REFS_BY_NODE)
    pr = CG.personalized_pagerank(nodes, edges, ["P1"])
    assert math.isclose(sum(pr.values()), 1.0, abs_tol=1e-9)
    assert pr["P1"] > pr["A"] > pr["X"] > 0          # seed > 1 hop > 2 hops


def test_ppr_rejects_unknown_seed_and_bad_alpha():
    nodes, edges = CG.build_edges(["P1"], REFS_BY_NODE)
    with pytest.raises(CG.CitationGraphError):
        CG.personalized_pagerank(nodes, edges, ["nope"])
    with pytest.raises(CG.CitationGraphError):
        CG.personalized_pagerank(nodes, edges, ["P1"], alpha=1.0)


def test_discount_is_inverse_log_and_finite_for_missing():
    assert CG.discount(170_000) == pytest.approx(1 / math.log1p(170_000))
    assert CG.discount(None) == CG.discount(0) == CG.discount(1) == pytest.approx(1 / math.log(2))
    assert CG.discount(20) > CG.discount(170_000)


def test_adam_type_node_weighs_less_than_a_rare_node_of_equal_ppr():
    ppr = {"rare": 0.1, "Adam": 0.1}
    w = CG.node_weights(ppr, {"rare": 20, "Adam": 170_000})
    assert w["rare"] > 3 * w["Adam"]


def test_ubiquitous_reference_is_a_constant_offset_not_a_ranking_signal():
    """Every candidate cites Adam: Adam adds the same constant to all, so the ORDER is set
    by the other references only."""
    doc = _graph()
    w = CG.weights_of(doc)
    refs = [{"Adam", "X"}, {"Adam", "A"}, {"Adam"}]
    scores = [CG.score_candidate(r, w) for r in refs]
    diffs = [s - w["Adam"] for s in scores]
    assert diffs == pytest.approx([w["X"], w["A"], 0.0])
    assert scores[1] > scores[0] > scores[2]


def test_graph_scores_two_hop_only_candidate_where_coupling_gives_zero():
    doc = _graph()
    refs = [{"X"}]                                   # cites only a paper two steps away
    assert citation_signal.score_coupling(refs, PROFILE_PAPERS) == []
    assert citation_signal.score_graph(refs, doc) == [(0, pytest.approx(CG.weights_of(doc)["X"]))]


def test_same_input_same_order_bit_for_bit():
    a = _graph(); b = _graph()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    refs = [{"X", "Adam"}, {"A"}, {"Adam"}, {"A", "X"}]
    assert citation_signal.score_graph(refs, a) == citation_signal.score_graph(refs, b)


def test_concentration_top_share():
    doc = _graph()
    c = CG.concentration([{"Adam", "A"}, {"Adam"}, {"X"}], CG.weights_of(doc), top=1)
    assert c["top"][0]["paper_id"] == "Adam" or c["top"][0]["paper_id"] == "A"
    assert 0.0 < c["top_share"] <= 1.0


# ── fetch once, score twice ───────────────────────────────────────────────────

def test_both_modes_share_one_s2_call_and_rank_graph_matches():
    doc = _graph()
    batch = [_make_paper(["X"]), None, _make_paper(["A", "Adam"])]
    with patch("lib.s2_client.papers_batch", return_value=batch) as m:
        refs = citation_signal.fetch_candidate_refs(["a1", "a2", "a3"])
        n_fetch_calls = m.call_count                      # the fetch (1 pass here: no referenceCount → no retry)
        coupling = citation_signal.score_coupling(refs, PROFILE_PAPERS)
        graph = citation_signal.score_graph(refs, doc)
    assert n_fetch_calls == 1 and m.call_count == n_fetch_calls   # scoring twice adds no S2 call
    assert refs[1] is None and [i for i, _ in coupling] == [2] and [i for i, _ in graph] == [2, 0]
    with patch("lib.s2_client.papers_batch", return_value=batch):
        assert citation_signal.rank_graph(["a1", "a2", "a3"], doc) == graph
        assert citation_signal.rank(["a1", "a2", "a3"], PROFILE_PAPERS) == coupling


# ── the graph file: sha lock ──────────────────────────────────────────────────

def test_load_graph_refuses_stale_papers_sha(tmp_path):
    papers = tmp_path / "papers.json"
    papers.write_text('{"papers": []}')
    doc = CG.build_graph_doc(["P1"], REFS_BY_NODE, COUNTS, papers_sha256=CG.sha256_file(papers), built_utc="t")
    gpath = tmp_path / "citation-graph.json"
    gpath.write_text(json.dumps(doc))
    assert CG.load_graph(gpath, papers)["n_nodes"] == 4          # matches → loads
    papers.write_text('{"papers": [{"paper_id": "P9"}]}')         # profile rebuilt, graph not
    with pytest.raises(CG.CitationGraphError, match="different papers.json"):
        CG.load_graph(gpath, papers)
    with pytest.raises(CG.CitationGraphError, match="not found"):
        CG.load_graph(tmp_path / "missing.json", papers)


def test_prefetch_graph_mode_without_graph_is_a_hard_error_not_a_dropped_channel(write_config):
    import prefetch
    from lib import config as cfg_mod
    cfg = cfg_mod.load_config(write_config({"prefetch.thread_fusion": "per_thread", "prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True, "prefetch.citation_mode": "graph"}))
    assert cfg.citation_mode == "graph"
    cand = {"week": "2026-W24", "candidates": [{"arxiv_id": "2406.00001", "title": "t", "abstract": "a"}]}
    with pytest.raises(SystemExit, match="citation-graph.json"):
        prefetch.run(cand, {"schema_version": 2, "finalized_by": "test", "threads": []}, PROFILE_PAPERS, cfg, top_k=10,
                     channel_set="v2", ref_abstracts={}, pool_rule="quota", signals=set())


def test_config_alpha_must_be_in_unit_interval(write_config):
    from lib import config as cfg_mod
    with pytest.raises(cfg_mod.ConfigError, match="citation_graph_alpha"):
        cfg_mod.load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True, "prefetch.citation_graph_alpha": 1.0}))
    with pytest.raises(cfg_mod.ConfigError, match="citation_mode"):
        cfg_mod.load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True, "prefetch.citation_mode": "idf"}))


def test_graph_mode_keeps_channel_name_and_seats(write_config):
    """In graph mode the channel is still called `citation` and pool_select still gives it
    pool_quota.citation seats — nothing downstream changes."""
    import numpy as np
    import prefetch
    from lib import config as cfg_mod
    # BM25 gets no quota here so the assertion below isolates the citation channel's seats
    cfg = cfg_mod.load_config(write_config({"prefetch.thread_fusion": "per_thread", "prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True, "prefetch.citation_mode": "graph", "prefetch.pool_quota.bm25": 0}))
    doc = _graph()
    cands = [{"arxiv_id": f"2406.0000{i}", "title": f"t{i}", "abstract": f"a{i}"} for i in range(4)]
    cand = {"week": "2026-W24", "candidates": cands}
    profile = {"schema_version": 2, "finalized_by": "test", "as_of": "2026-06-15", "keywords": ["seed"], "threads": [{"name": "line", "summary": "s", "papers": ["k1"], "n_recent": 1, "status": "active"}]}
    papers = [{"paper_id": "P1", "key": "k1", "title": "seed", "abstract": "seed abstract",
               "reference_ids": ["A", "Adam"], "year": 2024, "categories": ["math.NA"]}]
    batch = [_make_paper(["X"]), _make_paper(["A", "Adam"]), None, _make_paper(["Adam"])]
    vec = np.eye(4, dtype=np.float32)
    with patch("lib.s2_client.papers_batch", return_value=batch), \
         patch("lib.embeddings.encode", side_effect=lambda model, texts, **kw: vec[: len(texts)]):
        prefetched, channels = prefetch.run(cand, profile, papers, cfg, top_k=4, channel_set="v2", ref_abstracts={},
                                            pool_rule="quota", signals=set(), use_quality=False,
                                            citation_mode="graph", citation_graph_doc=doc)
    assert prefetched["citation_mode"] == "graph"
    assert "citation" in channels["channels"]                     # same channel name
    assert set(channels["channels"]["citation"]) == {"2406.00000", "2406.00001", "2406.00003"}
    assert channels["channels"]["citation"][0] == "2406.00001"    # A + Adam outranks X-only
    assert prefetched["seats"]["citation"] == min(cfg.pool_quota_citation, 3)   # quota unchanged, capped by hits


# ── added after the 2026-09-12 adversarial round ──────────────────────────────

def test_dangling_mass_returns_to_seeds_not_uniform():
    """Chain P1 → A → X: X is a sink. With restart-to-seeds the seed keeps the most mass;
    a uniform-dangling walk flips the order (X > P1). This is the one invariant a mutant
    that passes `dangling=uniform` would violate."""
    import networkx as nx
    nodes, edges = CG.build_edges(["P1"], {"P1": ["A"], "A": ["X"]})
    pr = CG.personalized_pagerank(nodes, edges, ["P1"])
    assert pr["P1"] > pr["A"] > pr["X"]
    g = nx.DiGraph(); g.add_nodes_from(nodes); g.add_edges_from(edges)
    uniform = nx.pagerank(g, alpha=0.85, personalization={"P1": 1.0, "A": 0.0, "X": 0.0},
                          dangling={n: 1.0 for n in nodes}, tol=CG.PPR_TOL, max_iter=CG.PPR_MAX_ITER)
    assert uniform["X"] > uniform["P1"]                       # the mutant's signature
    to_seed = nx.pagerank(g, alpha=0.85, personalization={"P1": 1.0, "A": 0.0, "X": 0.0},
                          dangling={"P1": 1.0}, tol=CG.PPR_TOL, max_iter=CG.PPR_MAX_ITER)
    assert all(abs(pr[n] - to_seed[n]) < 1e-12 for n in nodes)


def test_alpha_changes_the_walk_and_small_alpha_concentrates_on_seeds():
    nodes, edges = CG.build_edges(["P1"], REFS_BY_NODE)
    lo = CG.personalized_pagerank(nodes, edges, ["P1"], alpha=0.3)
    hi = CG.personalized_pagerank(nodes, edges, ["P1"], alpha=0.9)
    assert lo != hi and lo["P1"] > hi["P1"]
    tiny = CG.personalized_pagerank(nodes, edges, ["P1"], alpha=0.01)
    assert tiny["P1"] > 0.98


def test_score_candidate_and_concentration_dedupe_and_skip_none():
    w = {"X": 0.5, "Adam": 0.1}
    assert CG.score_candidate(["X", "X", "X"], w) == 0.5
    c = CG.concentration([["Adam", "Adam", "X"], None, ["X"]], w, top=2)
    assert c["total"] == pytest.approx(0.1 + 0.5 + 0.5)
    assert c["top"][0]["paper_id"] == "X" and c["top"][0]["mass"] == pytest.approx(1.0)


def test_graph_doc_identical_under_shuffled_inputs_and_across_hash_seeds(tmp_path):
    import os, random, subprocess, sys
    base = {"P1": ["A", "Adam", "B"], "A": ["X", "Adam"], "B": ["Y", "X"], "P2": ["B", "C"], "C": ["Z"]}
    counts = {"A": 40, "B": 7, "C": 3, "X": 20, "Y": 1, "Z": 0, "Adam": 170_000}
    ref = json.dumps(CG.build_graph_doc(["P1", "P2"], base, counts, "s", "t"), sort_keys=True)
    rng = random.Random(7)
    for _ in range(5):
        keys = list(base); rng.shuffle(keys)
        shuffled = {k: list(reversed(base[k])) if rng.random() < 0.5 else list(base[k]) for k in keys}
        seeds = ["P2", "P1"] if rng.random() < 0.5 else ["P1", "P2"]
        assert json.dumps(CG.build_graph_doc(seeds, shuffled, counts, "s", "t"), sort_keys=True) == ref
    # cross-process: a different PYTHONHASHSEED changes set/dict iteration order upstream
    script = tmp_path / "h.py"
    script.write_text(
        "import json, sys; sys.path.insert(0, sys.argv[1])\n"
        "from lib import citation_graph as CG\n"
        f"base = {base!r}; counts = {counts!r}\n"
        "refs = {k: set(v) for k, v in base.items()}\n"          # sets: iteration order depends on the hash seed
        "print(json.dumps(CG.build_graph_doc(set(['P1', 'P2']), refs, counts, 's', 't'), sort_keys=True))\n")
    scripts_dir = str(Path(CG.__file__).resolve().parents[1])
    outs = []
    for seed in ("1", "999"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        outs.append(subprocess.run([sys.executable, str(script), scripts_dir], env=env, check=True,
                                   capture_output=True, text=True).stdout)
    assert outs[0] == outs[1] == ref + "\n"


def test_check_graph_rejects_broken_node_table_seeds_and_edges(tmp_path):
    papers = tmp_path / "papers.json"; papers.write_text('{"papers": []}')
    good = CG.build_graph_doc(["P1"], REFS_BY_NODE, COUNTS, papers_sha256=CG.sha256_file(papers), built_utc="t")
    CG.check_graph(good, papers)
    for mutate, msg in [
        (lambda d: d.__setitem__("nodes", {}), "no `nodes`"),
        (lambda d: d["nodes"]["A"].pop("weight"), "numeric ppr/weight"),
        (lambda d: d["nodes"].pop("P1"), "seeds are missing"),
        (lambda d: d["out_edges"]["P1"].pop(), "does not match n_edges"),
        (lambda d: d.__setitem__("schema_version", 1), "schema_version"),
    ]:
        doc = json.loads(json.dumps(good)); mutate(doc)
        with pytest.raises(CG.CitationGraphError, match=msg):
            CG.check_graph(doc, papers)


def test_fetch_layers_never_backfills_seed_refs_from_s2():
    """A seed with empty reference_ids stays a dangling seed: S2's list for it is ignored, so no
    reference can enter the walk without a citation count and a layer-3 expansion."""
    import build_citation_graph as B
    seed_refs = {"S_ok": ["A"], "S_empty": []}
    # papers_batch returns a list ALIGNED with its input: ids = sorted seeds + sorted layer 2
    batch1 = [{"paperId": "S_empty", "citationCount": 1, "references": [{"paperId": "FromS2only"}]},
              {"paperId": "S_ok", "citationCount": 2, "references": [{"paperId": "Ignored"}]},
              {"paperId": "A", "citationCount": 40, "references": [{"paperId": "X"}]}]
    batch2 = [{"paperId": "X", "citationCount": 20}]
    with patch("lib.s2_client.papers_batch", side_effect=[batch1, batch2]) as m:
        refs_by_node, counts = B.fetch_layers(seed_refs)
    assert m.call_args_list[0].args[0] == ["S_empty", "S_ok", "A"]           # seeds sorted + layer 2 (refs pass)
    assert "referenceCount" in m.call_args_list[0].kwargs["fields"]
    assert m.call_args_list[1].args[0] == ["X"]                              # layer 3 only (counts)
    assert refs_by_node == {"S_ok": ["A"], "S_empty": [], "A": ["X"]}
    assert "FromS2only" not in refs_by_node and "Ignored" not in str(refs_by_node)
    assert counts == {"A": 40, "S_empty": 1, "S_ok": 2, "X": 20}
    doc = CG.build_graph_doc(list(seed_refs), refs_by_node, counts, "s", "t")
    assert doc["n_seeds_without_refs"] == 1 and set(doc["nodes"]) == {"S_ok", "S_empty", "A", "X"}
    assert all(v["citation_count"] is not None for v in doc["nodes"].values())   # no max-weight orphans


def test_citation_channel_degrades_only_on_fetch_errors(write_config):
    """The S2 fetch may drop the channel (loudly); a scoring error in graph mode must propagate."""
    import prefetch
    from lib import config as cfg_mod
    cfg = cfg_mod.load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True}))
    doc = _graph()
    with patch("lib.citation_signal.fetch_candidate_refs", side_effect=RuntimeError("S2 down")):
        assert prefetch._citation_channel(["a"], PROFILE_PAPERS, cfg, "graph", doc) is None
    with patch("lib.citation_signal.fetch_candidate_refs", return_value=[{"X"}]), \
         patch("lib.citation_signal.score_graph", side_effect=KeyError("weight")):
        with pytest.raises(KeyError):
            prefetch._citation_channel(["a"], PROFILE_PAPERS, cfg, "graph", doc)


def test_main_requires_graph_only_when_citation_channel_runs(write_config, tmp_path):
    """Both off-switches (config use_citation_signal: false, --no-citation) must agree with run():
    no graph is loaded or demanded when the channel is off; with the channel on, a missing graph
    is a hard error naming the fix."""
    import numpy as np
    import prefetch
    from lib import config as cfg_mod
    assert prefetch._graph_required("graph", True) and not prefetch._graph_required("graph", False)
    assert not prefetch._graph_required("coupling", True)
    cand = tmp_path / "cand.json"
    cand.write_text(json.dumps({"week": "2026-W24", "candidates": [
        {"arxiv_id": f"2406.0000{i}", "title": f"t{i}", "abstract": f"a{i}"} for i in range(3)]}))
    pj = tmp_path / "profile.json"; pj.write_text(json.dumps({"schema_version": 2, "finalized_by": "test", "as_of": "2026-06-15", "keywords": ["seed"], "threads": [
        {"name": "line", "papers": ["k1"], "n_recent": 1, "status": "active"}]}))
    pp = tmp_path / "papers.json"; pp.write_text(json.dumps({"papers": [
        {"paper_id": "P1", "key": "k1", "title": "seed", "abstract": "s", "reference_ids": ["A"], "year": 2024,
         "categories": ["math.NA"]}]}))
    from lib import profile_io                                               # 线通道要参考文献摘要(可以为空)
    (tmp_path / "ref_abstracts.json").write_text(json.dumps({"papers_sha256": profile_io.sha256_file(pp), "refs": {}}))
    vec = np.eye(3, dtype=np.float32)
    common = ["prefetch.py", "--candidates", str(cand), "--profile-json", str(pj), "--profile-papers", str(pp),
              "--out", str(tmp_path / "out.json")]

    def run_main(cfg_path, extra=()):
        cfg = cfg_mod.load_config(cfg_path)
        with patch("prefetch.config.load_config", return_value=cfg), \
             patch("lib.embeddings.encode", side_effect=lambda model, texts, **kw: vec[: len(texts)]), \
             patch("lib.s2_client.papers_batch", return_value=[None, None, None]), \
             patch("sys.argv", common + list(extra)):
            return prefetch.main()

    off = write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True, "prefetch.citation_mode": "graph", "prefetch.use_citation_signal": False})
    assert run_main(off) == 0                                                # channel off → no graph needed
    on = write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True, "prefetch.citation_mode": "graph", "prefetch.use_citation_signal": True})
    assert run_main(on, ["--no-citation"]) == 0                              # CLI off-switch agrees
    with pytest.raises(SystemExit, match="citation graph not found"):
        run_main(on)                                                          # channel on, no graph → hard error


def test_build_if_stale_keeps_a_matching_graph_and_rebuilds_a_stale_one(tmp_path, monkeypatch):
    """arxiv-scout runs build_citation_graph --if-stale before every graph-mode prefetch: a graph that
    matches papers.json is kept without touching S2; once papers.json changes it is rebuilt."""
    import build_citation_graph as B
    monkeypatch.setenv("AR_DATA_ROOT", str(tmp_path))
    papers = tmp_path / "papers.json"
    papers.write_text(json.dumps({"papers": PROFILE_PAPERS}))
    out = tmp_path / "citation-graph.json"
    out.write_text(json.dumps(CG.build_graph_doc(["P1"], REFS_BY_NODE, COUNTS,
                                                 papers_sha256=CG.sha256_file(papers), built_utc="t")))
    argv = ["build_citation_graph.py", "--papers", str(papers), "--out", str(out), "--if-stale"]
    with patch("sys.argv", argv), patch.object(B, "fetch_layers", side_effect=AssertionError("S2 called")):
        assert B.main() == 0                                                  # up to date → no S2 call
    papers.write_text(json.dumps({"papers": PROFILE_PAPERS, "cutoff": "2026-06-15"}))   # papers.json changed
    with patch("sys.argv", argv), patch.object(B, "fetch_layers", return_value=(REFS_BY_NODE, COUNTS)) as m:
        assert B.main() == 0
    assert m.called and CG.load_graph(out, papers)["papers_sha256"] == CG.sha256_file(papers)


def test_papers_references_retries_under_delivered_and_reports_unresolved():
    """S2's batch endpoint caps nested references per request: a paper returned with fewer
    references than its referenceCount is retried once in small chunks; what stays short is
    counted as unresolved, never silently 'no references'."""
    from lib import s2_client
    def paper(pid, count, refs):
        return {"paperId": pid, "referenceCount": count, "references": [{"paperId": r} for r in refs]}
    # p1: shorter than its count is NORMAL (unlinked references) → not retried; p2/p4: empty → retried
    pass1 = [paper("p1", 3, ["a", "b"]), paper("p2", 5, []), None, paper("p4", 3, []), paper("p5", 0, [])]
    pass2 = [paper("p2", 5, ["c", "d", "e", "f", "g"]), paper("p4", 3, [])]         # p4 = S2 data limit
    with patch("lib.s2_client.papers_batch", side_effect=[pass1, pass2]) as m:
        refs, extras, st = s2_client.papers_references(["p1", "p2", "p3", "p4", "p5"], extra_fields=("citationCount",))
    assert m.call_args_list[1].args[0] == ["p2", "p4"]
    assert m.call_args_list[1].kwargs["chunk_size"] == s2_client.REFS_RETRY_CHUNK_SIZE
    assert refs == [{"a", "b"}, {"c", "d", "e", "f", "g"}, None, set(), set()]
    assert st == {"n": 5, "found": 4, "with_refs": 2, "retried": 2, "recovered": 1, "unresolved": 1}
    assert extras[0] == {"citationCount": None} and extras[2] is None


def test_build_citation_graph_main_end_to_end_with_mocked_s2(write_config, tmp_path, monkeypatch):
    """The whole CLI: papers.json → two S2 passes (mocked) → citation-graph.json that load_graph
    accepts, with the hub report printed. Catches wiring errors fetch_layers-only tests miss."""
    import build_citation_graph as B
    from lib import config as cfg_mod
    cfg = cfg_mod.load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True}))
    papers = tmp_path / "papers.json"
    papers.write_text(json.dumps({"papers": [
        {"paper_id": "P1", "reference_ids": ["A", "Adam"]}, {"paper_id": "P2", "reference_ids": []},
        {"title": "no s2 id"}]}))
    out = tmp_path / "citation-graph.json"
    def paper(pid, count, refs, cites):
        return {"paperId": pid, "referenceCount": count, "citationCount": cites,
                "references": [{"paperId": r} for r in refs]}
    pass1 = [paper("P1", 2, [], 3), paper("P2", 0, [], 0), paper("A", 2, ["X", "Adam"], 40),
             paper("Adam", 1, ["Y"], 170_000)]                       # ids = sorted seeds + sorted layer 2
    counts = [{"paperId": "X", "citationCount": 20}, {"paperId": "Y", "citationCount": 2}]
    monkeypatch.setattr(B.config, "load_config", lambda: cfg)
    monkeypatch.setattr("sys.argv", ["build_citation_graph.py", "--papers", str(papers), "--out", str(out), "--top", "3"])
    retry = [paper("P1", 2, ["ignored", "ignored2"], 3)]          # P1 came back EMPTY with count 2 → one retry pass
    with patch("lib.s2_client.papers_batch", side_effect=[pass1, retry, counts]) as m:
        assert B.main() == 0
    assert m.call_args_list[1].args[0] == ["P1"] and m.call_args_list[2].args[0] == ["X", "Y"]
    doc = CG.load_graph(out, papers)
    assert doc["seeds"] == ["P1", "P2"] and doc["n_seeds_without_refs"] == 1
    assert set(doc["nodes"]) == {"P1", "P2", "A", "Adam", "X", "Y"}
    assert doc["out_edges"] == {"A": ["Adam", "X"], "Adam": ["Y"], "P1": ["A", "Adam"]}   # seed edges from papers.json only
    assert doc["nodes"]["Adam"]["citation_count"] == 170_000 and doc["nodes"]["X"]["citation_count"] == 20
    assert abs(sum(v["ppr"] for v in doc["nodes"].values()) - 1.0) < 1e-9


def test_peripheral_papers_are_never_graph_seeds(write_config, tmp_path, monkeypatch):
    """2026-09-17: a peripheral paper (owner-marked, outside the research core) seeded the graph and pulled
    46 unrelated LLM papers into the channel's top 300. Seeds are the core papers only, like every channel."""
    import build_citation_graph as B
    from lib import channel_spec as CS
    from lib import config as cfg_mod
    papers = [{"paper_id": "P1", "reference_ids": ["A"]},
              {"paper_id": "PERI", "peripheral": True, "reference_ids": ["LLM"]},
              {"title": "no s2 id"}]
    assert [p["paper_id"] for p in CS.graph_seed_papers(papers)] == ["P1"]
    cfg = cfg_mod.load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.use_citation_signal": True}))
    pj = tmp_path / "papers.json"
    pj.write_text(json.dumps({"papers": papers}))
    out = tmp_path / "citation-graph.json"
    monkeypatch.setattr(B.config, "load_config", lambda: cfg)
    monkeypatch.setattr("sys.argv", ["build_citation_graph.py", "--papers", str(pj), "--out", str(out)])
    with patch.object(B, "fetch_layers", return_value=({"P1": ["A"], "A": []}, {"P1": 1, "A": 5})) as m:
        assert B.main() == 0
    assert list(m.call_args.args[0]) == ["P1"]                          # the peripheral paper never reaches S2
    doc = CG.load_graph(out, pj)
    assert doc["seeds"] == ["P1"] and "PERI" not in doc["nodes"] and "LLM" not in doc["nodes"]
    assert doc["seed_rule"] == CG.SEED_RULE == "core"


def test_a_graph_built_under_the_old_seed_rule_is_refused_and_rebuilt(tmp_path, monkeypatch):
    import build_citation_graph as B
    monkeypatch.setenv("AR_DATA_ROOT", str(tmp_path))
    papers = tmp_path / "papers.json"
    papers.write_text(json.dumps({"papers": PROFILE_PAPERS}))
    out = tmp_path / "citation-graph.json"
    old = CG.build_graph_doc(["P1"], REFS_BY_NODE, COUNTS, papers_sha256=CG.sha256_file(papers), built_utc="t")
    old["schema_version"] = 2
    old.pop("seed_rule")
    out.write_text(json.dumps(old))
    with pytest.raises(CG.CitationGraphError, match="schema_version"):
        CG.load_graph(out, papers)
    argv = ["build_citation_graph.py", "--papers", str(papers), "--out", str(out), "--if-stale"]
    with patch("sys.argv", argv), patch.object(B, "fetch_layers", return_value=(REFS_BY_NODE, COUNTS)) as m:
        assert B.main() == 0
    assert m.called and CG.load_graph(out, papers)["schema_version"] == CG.SCHEMA_VERSION
    doc = json.loads(out.read_text())
    doc["seed_rule"] = "all"
    with pytest.raises(CG.CitationGraphError, match="seed_rule"):
        CG.check_graph(doc, papers)
