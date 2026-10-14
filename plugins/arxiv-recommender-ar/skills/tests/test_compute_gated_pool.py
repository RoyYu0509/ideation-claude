"""Unit tests for the deterministic Phase-3.6 survivor tally (compute_gated_pool.compute_pool).

The point of the driver is that survivors are derived from the on-disk judge-cache, never
tallied from an LLM's memory — so these tests pin the tally rules AND the FAIL-CLOSED behavior
that makes fabrication impossible (a queued-but-unjudged paper must block, not be papered over).
"""
import pytest

from compute_gated_pool import GateError, compute_pool


def _paper(pid, **extra):
    return {"arxiv_id": pid, "title": f"paper {pid}", **extra}


def _ok(penalize=False, why="pass"):
    return {"result": {"ok": True, "why": why, "penalize": penalize}}


def _reject(why="claim inconclusive"):
    return {"result": {"ok": False, "why": why}}


def test_basic_tally_keeps_ok_drops_rejected():
    gi = {"queue": [_paper("a"), _paper("b"), _paper("c")],
          "pinned": [], "ext_pool_ordered": [_paper("a"), _paper("b"), _paper("c")], "n": 3}
    cache = {"a": _ok(), "b": _reject("repo fail"), "c": _ok()}
    r = compute_pool(gi, cache)
    assert [p["arxiv_id"] for p in r["survivors"]] == ["a", "c"]
    assert r["missing"] == [] and r["failsafe"] is False
    assert [x["arxiv_id"] for x in r["rejected"]] == ["b"]


def test_penalize_tags_flagged():
    gi = {"queue": [_paper("a")], "pinned": [], "ext_pool_ordered": [_paper("a")], "n": 3}
    r = compute_pool(gi, {"a": _ok(penalize=True)})
    assert r["survivors"][0]["quality_tier"] == "flagged"


def test_n_cap_stops_after_n_survivors():
    q = [_paper("a"), _paper("b"), _paper("c")]
    gi = {"queue": q, "pinned": [], "ext_pool_ordered": q, "n": 2}
    cache = {"a": _ok(), "b": _ok(), "c": _ok()}
    r = compute_pool(gi, cache)
    assert [p["arxiv_id"] for p in r["survivors"]] == ["a", "b"]  # coverage order; c dropped


def test_pinned_force_included_and_counts_toward_n():
    q = [_paper("a"), _paper("b")]
    gi = {"queue": q, "pinned": [_paper("z")], "ext_pool_ordered": q, "n": 2}
    cache = {"a": _ok(), "b": _ok()}
    r = compute_pool(gi, cache)
    # pinned z seeds the pool and consumes one of the 2 slots → only a joins.
    assert [p["arxiv_id"] for p in r["survivors"]] == ["z", "a"]


def test_pinned_never_needs_a_judge_verdict():
    gi = {"queue": [], "pinned": [_paper("z")], "ext_pool_ordered": [], "n": 3}
    r = compute_pool(gi, {})  # empty cache, but z is pinned → no missing
    assert r["missing"] == [] and [p["arxiv_id"] for p in r["survivors"]] == ["z"]


def test_fail_closed_on_unjudged_queue_member():
    # 'b' is in the coverage queue but has NO committed verdict → must surface as missing
    # (the caller then exits 3). This is the anti-fabrication guarantee.
    gi = {"queue": [_paper("a"), _paper("b")], "pinned": [],
          "ext_pool_ordered": [_paper("a"), _paper("b")], "n": 3}
    r = compute_pool(gi, {"a": _ok()})
    assert r["missing"] == ["b"]


def test_fail_closed_on_malformed_verdict():
    gi = {"queue": [_paper("a")], "pinned": [], "ext_pool_ordered": [_paper("a")], "n": 3}
    # entry exists but result lacks 'ok' → treated as unjudged (missing), never as a pass.
    assert compute_pool(gi, {"a": {"result": {"why": "half-written"}}})["missing"] == ["a"]


def test_failsafe_when_everything_rejected():
    q = [_paper("a"), _paper("b")]
    gi = {"queue": q, "pinned": [], "ext_pool_ordered": q, "n": 1}
    r = compute_pool(gi, {"a": _reject(), "b": _reject()})
    assert r["failsafe"] is True
    assert [p["arxiv_id"] for p in r["survivors"]] == ["a"]  # ext_pool_ordered[:1]


def test_invalid_n_raises():
    with pytest.raises(GateError):
        compute_pool({"queue": [], "pinned": [], "ext_pool_ordered": [], "n": 0}, {})
