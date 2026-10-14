"""lib/thread_seed.py — the per-thread seed selection (2026-09-20).

What must hold, in the order the rule states it:

  * ownership is a PARTITION of the delivered list — every paper goes to exactly one thread, so the
    seed walk can never have two threads nominate the same paper and never needs to arbitrate;
  * a paper goes to the thread that ranks it HIGHEST, ties broken by thread key so the partition is
    total and reproducible across runs;
  * inside a thread, papers come best-first on THAT thread's own rank;
  * the delivered list is a prefix — papers below it are not candidates for anything;
  * a paper no thread's channel ranked owns no seed (it was seated by a lexical / category /
    citation signal alone), and it is reported rather than silently dropped.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from lib.thread_seed import owner_thread, thread_orders, write_final  # noqa: E402


def cand(axid, **ranks):
    return {"arxiv_id": axid, "channel_ranks": dict(ranks)}


def fixture(candidates, labels=None, sizes=None):
    labels = labels or {"thread_1": "Alpha", "thread_2": "Beta", "thread_3": "Gamma"}
    sizes = sizes or {"Alpha": 5, "Beta": 3, "Gamma": 1}
    return (
        {"candidates": candidates},
        {"thread_labels": labels},
        {"threads": [{"name": n, "papers": ["x"] * k} for n, k in sizes.items()]},
    )


# ── ownership ────────────────────────────────────────────────────────────────

def test_owner_is_the_thread_that_ranks_it_highest():
    assert owner_thread(cand("a", thread_1=9, thread_2=3, thread_3=35)) == "thread_2"


def test_owner_ignores_non_thread_channels():
    # bm25 rank 1 must not win ownership — only per-thread rankings confer it.
    assert owner_thread(cand("a", bm25=1, thread_1=40)) == "thread_1"


def test_owner_breaks_ties_by_thread_key():
    assert owner_thread(cand("a", thread_2=7, thread_1=7)) == "thread_1"


def test_paper_on_no_thread_ranking_has_no_owner():
    assert owner_thread({"arxiv_id": "a", "channel_ranks": {"bm25": 1, "category": 2}}) is None
    assert owner_thread({"arxiv_id": "a"}) is None


# ── the partition ────────────────────────────────────────────────────────────

def test_ownership_partitions_the_delivered_list():
    pre, ch, prof = fixture([
        cand("p1", thread_1=1, thread_2=50),
        cand("p2", thread_1=80, thread_2=2),
        cand("p3", thread_1=5, thread_2=6, thread_3=4),
        cand("p4", thread_3=9, thread_1=30),
    ])
    orders = thread_orders(pre, ch, prof)
    owned = [axid for t in orders for axid in t["candidates"]]
    assert sorted(owned) == ["p1", "p2", "p3", "p4"]      # nothing lost
    assert len(owned) == len(set(owned))                  # nothing served twice


def test_unowned_papers_are_excluded_and_reported(capsys):
    pre, ch, prof = fixture([cand("p1", thread_1=1), cand("p2", bm25=1)])
    orders = thread_orders(pre, ch, prof)
    assert [axid for t in orders for axid in t["candidates"]] == ["p1"]
    assert "1/2 delivered papers are on no thread's ranking" in capsys.readouterr().err


# ── order within and between threads ─────────────────────────────────────────

def test_within_a_thread_papers_come_best_first_on_its_own_rank():
    pre, ch, prof = fixture([
        cand("far", thread_1=40), cand("near", thread_1=2), cand("mid", thread_1=11),
    ])
    assert thread_orders(pre, ch, prof)[0]["candidates"] == ["near", "mid", "far"]


def test_threads_are_walked_largest_first_then_by_key():
    pre, ch, prof = fixture(
        [cand("p1", thread_1=1), cand("p2", thread_2=1), cand("p3", thread_3=1)],
        sizes={"Alpha": 2, "Beta": 9, "Gamma": 2},
    )
    assert [t["key"] for t in thread_orders(pre, ch, prof)] == ["thread_2", "thread_1", "thread_3"]


def test_a_thread_owning_nothing_this_week_is_still_listed_with_no_candidates():
    pre, ch, prof = fixture([cand("p1", thread_1=1)])
    empty = [t for t in thread_orders(pre, ch, prof) if t["key"] == "thread_2"]
    assert empty and empty[0]["candidates"] == []


# ── the delivered list is a prefix ───────────────────────────────────────────

def test_only_the_delivered_prefix_is_eligible():
    pre, ch, prof = fixture([cand("in", thread_1=9), cand("out", thread_1=1)])
    orders = thread_orders(pre, ch, prof, pool_k=1)
    assert [axid for t in orders for axid in t["candidates"]] == ["in"]   # 'out' ranks better but was not delivered


# ── the handoff file ─────────────────────────────────────────────────────────

def test_write_final_matches_the_shape_the_rationale_skill_reads(tmp_path):
    seeds = [{"arxiv_id": "p1", "thread": "Alpha"}, {"arxiv_id": "p2", "thread": "Beta"}]
    path = write_final("2026-W25", seeds, tmp_path)
    doc = json.loads(Path(path).read_text())
    assert doc["week"] == "2026-W25" and doc["select"] == "thread_seed"
    assert [t["arxiv_id"] for t in doc["top"]] == ["p1", "p2"]
    # No padding exists in this selection, so a thread label can never be null.
    assert all(t["thread"] and t["source"] == "thread_seed" for t in doc["top"])


@pytest.mark.parametrize("bad", [{}, {"channel_ranks": {"thread_1": None}}])
def test_a_missing_or_null_rank_never_confers_ownership(bad):
    assert owner_thread({"arxiv_id": "a", **bad}) is None


# ── the walk: what the seed loop actually does ───────────────────────────────
# The loop used to live in workflows/arxiv-scout.js, where no test could reach it. It is here
# because a hand-enacting orchestrator must not have to hold cursors in its head — the same reason
# compute_gated_pool.py owns the survivor tally.

from lib.thread_seed import walk  # noqa: E402


ORDERS = [
    {"key": "thread_1", "name": "Alpha", "size": 5, "candidates": ["a1", "a2", "a3"]},
    {"key": "thread_2", "name": "Beta", "size": 3, "candidates": ["b1", "b2"]},
    {"key": "thread_3", "name": "Gamma", "size": 1, "candidates": ["c1"]},
]


def test_first_turn_nominates_each_thread_s_best_paper():
    st = walk(ORDERS, {}, {})
    assert [(n["key"], n["arxiv_id"]) for n in st["nominations"]] == [
        ("thread_1", "a1"), ("thread_2", "b1"), ("thread_3", "c1")]
    assert st["done"] is False and st["seeds"] == []


def test_all_pass_seeds_every_thread_and_ends():
    st = walk(ORDERS, {}, {})
    st = walk(ORDERS, st, {"a1": True, "b1": True, "c1": True})
    assert [(s["key"], s["arxiv_id"], s["thread"]) for s in st["seeds"]] == [
        ("thread_1", "a1", "Alpha"), ("thread_2", "b1", "Beta"), ("thread_3", "c1", "Gamma")]
    assert st["done"] is True and st["unseeded"] == []


def test_a_rejection_advances_that_thread_to_its_next_paper():
    st = walk(ORDERS, {}, {})
    st = walk(ORDERS, st, {"a1": False, "b1": True, "c1": True})
    assert [(n["key"], n["arxiv_id"]) for n in st["nominations"]] == [("thread_1", "a2")]
    assert "a1" in st["rejected"]
    assert [s["key"] for s in st["seeds"]] == ["thread_2", "thread_3"]


def test_a_thread_whose_papers_are_all_rejected_ends_with_no_seed():
    st = walk(ORDERS, {}, {})
    st = walk(ORDERS, st, {"a1": True, "b1": False, "c1": False})   # gamma owns only c1
    st = walk(ORDERS, st, {"b2": False})
    assert st["done"] is True
    assert sorted(st["unseeded"]) == ["thread_2", "thread_3"]
    assert [s["key"] for s in st["seeds"]] == ["thread_1"]


def test_a_nomination_without_a_committed_verdict_stands_and_is_not_reinvented():
    # The judge crashed or has not returned: the paper must NOT be treated as a rejection, and the
    # thread must NOT jump ahead to its next paper.
    st = walk(ORDERS, {}, {})
    st = walk(ORDERS, st, {"b1": True, "c1": True})                 # a1 has no verdict
    standing = [(n["key"], n["arxiv_id"]) for n in st["nominations"]]
    assert standing == [("thread_1", "a1")]
    assert st["rejected"] == [] and st["cursor"].get("thread_1", 0) == 0


def test_a_seeded_thread_is_never_nominated_again():
    st = walk(ORDERS, {}, {})
    st = walk(ORDERS, st, {"a1": True, "b1": True, "c1": True})
    st = walk(ORDERS, st, {})
    assert st["nominations"] == [] and st["done"] is True


def test_the_walk_is_idempotent_when_nothing_new_was_judged():
    st1 = walk(ORDERS, {}, {})
    st2 = walk(ORDERS, dict(st1), {})
    assert st1["nominations"] == st2["nominations"]
    assert st2["seeds"] == [] and st2["rejected"] == []


def test_two_threads_can_never_nominate_the_same_paper():
    # Guaranteed upstream by the ownership partition; asserted here so a future edit that lets a
    # paper appear on two threads' orders fails loudly instead of double-seeding it.
    seen = [axid for t in ORDERS for axid in t["candidates"]]
    assert len(seen) == len(set(seen))
    st = walk(ORDERS, {}, {})
    nominated = [n["arxiv_id"] for n in st["nominations"]]
    assert len(nominated) == len(set(nominated))
