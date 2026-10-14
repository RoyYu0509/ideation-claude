"""Quota pool builder (REC-SYSTEM-V2 B3)."""
from lib import pool_select as P


def test_allocate_floors_then_split_by_recent_output_and_fixed_seats():
    seats = P.allocate(100, [("thread_1", 6, True), ("thread_2", 2, True), ("thread_3", 0, False)],
                       floor=5, bm25_seats=20, citation_seats=10, citation_available=4)
    assert seats["citation"] == 4                 # capped by its hits
    assert seats["bm25"] == 20
    assert seats["thread_3"] == 0                 # legacy thread: recency lives in the seats
    # budget 76 = 5 + 5 floors + 66 split 6:2 (49.5 / 16.5, tie on .5 → thread order)
    assert (seats["thread_1"], seats["thread_2"]) == (55, 21)
    assert sum(seats.values()) == 100


def test_allocate_without_active_threads_leaves_the_budget_to_the_fill():
    assert P.allocate(50, [("thread_1", 0, False)], 5, 20, 10, 10) == {"thread_1": 0, "bm25": 20, "citation": 10}


def test_allocate_shrinks_the_floor_when_the_budget_is_tight():
    seats = P.allocate(12, [(f"t{i}", 1, True) for i in range(4)], floor=5, bm25_seats=4,
                       citation_seats=0, citation_available=0)
    assert [seats[f"t{i}"] for i in range(4)] == [2, 2, 2, 2]
    assert sum(seats.values()) == 12


def test_seat_pool_round_robin_skips_seated_papers_then_fills():
    channels = {"a": ["p1", "p2", "p3"], "b": ["p1", "p4", "p5"], "bm25": ["p6"]}
    pool, by = P.seat_pool(channels, {"a": 2, "b": 2, "bm25": 1}, k=6, fill=["p9", "p1", "p8"],
                           order=["a", "b", "bm25"])
    # pass 1: a→p1, b→p4 (p1 already seated), bm25→p6; pass 2: a→p2, b→p5; fill → p9
    assert pool == ["p1", "p4", "p6", "p2", "p5", "p9"]
    assert (by["p1"], by["p4"], by["p9"]) == ("a", "b", "fill")


def test_seat_pool_never_exceeds_k_and_survives_short_channels():
    pool, by = P.seat_pool({"a": ["x"]}, {"a": 5}, k=3, fill=["y", "z", "w"], order=["a"])
    assert pool == ["x", "y", "z"]
    assert by == {"x": "a", "y": "fill", "z": "fill"}
