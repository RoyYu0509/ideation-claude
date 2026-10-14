"""lib/thread_fusion — how the per-thread lists enter RRF (config prefetch.thread_fusion)."""
import math

import numpy as np
import pytest

import prefetch as PF
from lib import embeddings, rrf
from lib import thread_fusion as TF
from lib.config import load_config

NAMED = [("prf", ["a", "b", "c", "d"]),
         ("thread_1", ["a", "b", "c", "d"]),
         ("thread_2", ["d", "c", "b", "a"]),
         ("thread_3", ["c", "a", "d", "b"]),
         ("bm25", ["b", "d"])]
SIZES = {"thread_1": 9, "thread_2": 4, "thread_3": 1}


def test_config_choices_mirror_the_modes(write_config):
    for m in TF.MODES:
        assert load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.thread_fusion": m})).thread_fusion == m
    with pytest.raises(Exception, match="thread_fusion"):
        load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "prefetch.thread_fusion": "family"})).thread_fusion
    # 出厂默认:EVAL-PLAN 修订 #9(5 份正式画像 + 研究者标注)把它从 per_thread 改成 split
    assert load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False})).thread_fusion == "split"


def test_weights_none_is_bit_identical_to_all_ones():
    lists = [lst for _, lst in NAMED]
    assert rrf.fuse(lists, k=60) == rrf.fuse(lists, k=60, weights=[1.0] * len(lists))
    with pytest.raises(ValueError):
        rrf.fuse(lists, k=60, weights=[1.0])


def test_weight_scales_one_lists_contribution():
    base = dict(rrf.fuse([["a"], ["a", "b"]], k=60))
    half = dict(rrf.fuse([["a"], ["a", "b"]], k=60, weights=[1.0, 0.5]))
    assert half["b"] == pytest.approx(base["b"] / 2)
    assert half["a"] == pytest.approx(1 / 61 + 0.5 / 61)


def test_per_thread_is_the_old_behaviour():
    out, w = TF.apply("per_thread", NAMED)
    assert out == [(n, list(l)) for n, l in NAMED] and w == [1.0] * 5


def test_split_gives_the_thread_channel_one_vote():
    out, w = TF.apply("split", NAMED)
    assert [n for n, _ in out] == [n for n, _ in NAMED]
    assert w == [1.0, 1 / 3, 1 / 3, 1 / 3, 1.0] and math.isclose(sum(w[1:4]), 1.0)


def test_sqrt_weights_have_mean_one_and_follow_member_counts():
    _, w = TF.apply("sqrt", NAMED, SIZES)
    tw = w[1:4]
    assert math.isclose(sum(tw) / 3, 1.0)
    assert tw[0] / tw[1] == pytest.approx(3 / 2) and tw[1] / tw[2] == pytest.approx(2)
    with pytest.raises(ValueError, match="member count"):
        TF.apply("sqrt", NAMED, {"thread_1": 9})


def test_best_collapses_threads_into_one_list_in_place():
    out, w = TF.apply("best", NAMED)
    assert [n for n, _ in out] == ["prf", "thread_best", "bm25"] and w == [1.0] * 3
    # per-paper sorted ranks: a (1,2,4) · b (2,3,4) · c (1,2,3) · d (1,3,4)
    # lexicographic: c (1,2,3) < a (1,2,4) < d (1,3,4) < b (2,3,4)
    assert dict(out)["thread_best"] == ["c", "a", "d", "b"]


def test_best_keeps_a_single_thread_specialist_that_votes_bury():
    """x is #1 on one thread and last on the other two; y is #2 everywhere. Per-thread votes put y first,
    the collapsed list puts x first."""
    named = [("thread_1", ["x", "y", "z"]), ("thread_2", ["z", "y", "x"]), ("thread_3", ["z", "y", "x"])]
    votes = [a for a, _ in rrf.fuse([l for _, l in named], k=60)]
    assert votes.index("y") < votes.index("x")
    out, _ = TF.apply("best", named)
    assert dict(out)["thread_best"][:2] == ["z", "x"]


def test_best_ties_keep_first_appearance_and_missing_ranks_last():
    assert TF.collapse_best([["p", "q"], ["q", "p"]]) == ["p", "q"]           # (1,2) vs (1,2): first seen wins
    assert TF.collapse_best([["p"], ["q", "p"]]) == ["p", "q"]                # q missing from list 1 → rank 2


def test_check_refuses_unsupported_runs():
    TF.check("per_thread", "legacy", "quota")
    for bad in (("split", "legacy", "rrf"), ("best", "v2", "quota"), ("family", "v2", "rrf")):
        with pytest.raises(ValueError):
            TF.check(*bad)


# ── prefetch honours the key ──────────────────────────────────────────────────

_VOCAB = ["rfm", "pde", "vqe", "quantum", "graph", "llm"]


def _fake_encode(model, texts, **kw):
    return np.stack([np.array([t.lower().count(w) for w in _VOCAB], dtype=np.float32) + 1e-3 for t in texts])


def _toy():
    cands = [{"arxiv_id": f"c{i}", "title": t, "abstract": "", "categories": ["cs.LG"]} for i, t in enumerate(
        ["rfm pde solver", "rfm pde", "rfm", "vqe quantum", "quantum", "graph llm", "llm", "graph"])]
    profile = {"schema_version": 2, "finalized_by": "test", "as_of": "2026-06-15", "keywords": ["graph llm"], "threads": [
        {"name": "RFM", "keywords": ["rfm pde"], "papers": ["p1", "p3"], "status": "active", "n_recent": 5},
        {"name": "Quantum", "keywords": ["vqe"], "papers": ["p2"], "status": "active", "n_recent": 1}]}
    papers = [{"key": "p1", "title": "rfm pde", "abstract": "rfm", "categories": ["math.NA"]},
              {"key": "p2", "title": "vqe quantum", "abstract": "quantum", "categories": ["quant-ph"]},
              {"key": "p3", "title": "pde", "abstract": "rfm pde", "categories": ["math.NA"]}]
    return {"week": "2026-W24", "candidates": cands}, profile, papers


def _run(write_config, mode, pool_rule="rrf"):
    cfg = load_config(write_config({"prefetch.bm25_query": "extracted",
                                     "prefetch.use_dense_channel": False, "scout.prefetch_top_k": 6, "scout.top_n_papers": 2,
                                    "prefetch.thread_fusion": mode}))
    cand, profile, papers = _toy()
    return PF.run(cand, profile, papers, cfg, top_k=6, channel_set="v2", ref_abstracts={}, pool_rule=pool_rule,
                  signals=set(), use_citation=False, use_quality=False, use_category=False)


@pytest.mark.parametrize("mode", TF.MODES)
def test_prefetch_fuses_exactly_what_thread_fusion_returns(monkeypatch, write_config, mode):
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    pre, ch = _run(write_config, mode)
    assert ch["thread_fusion"] == mode
    named = [(n, l) for n, l in ch["channels"].items() if n != TF.BEST_NAME]
    sizes = {"thread_1": 2, "thread_2": 1}
    fuse_named, w = TF.apply(mode, named, sizes)
    want = [a for a, _ in rrf.fuse([l for _, l in fuse_named], k=60, weights=w)][:6]
    assert [c["arxiv_id"] for c in pre["candidates"]] == want
    assert {"thread_1", "thread_2"} <= set(ch["channels"])                  # per-thread lists stay visible
    assert (TF.BEST_NAME in ch["channels"]) == (mode == "best")


def test_prefetch_refuses_a_mode_it_cannot_honour(monkeypatch, write_config):
    monkeypatch.setattr(embeddings, "encode", _fake_encode)
    with pytest.raises(SystemExit, match="pool_rule rrf"):
        _run(write_config, "split", pool_rule="quota")
