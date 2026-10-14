from lib import rrf


def test_fuse_basic_known_output():
    # Two lists. Item "a" is rank 1 in list1 and rank 2 in list2 => high score.
    list1 = ["a", "b", "c", "d"]
    list2 = ["b", "a", "e"]
    fused = rrf.fuse([list1, list2], k=60)
    # "a" should be on top: 1/(60+1) + 1/(60+2) = ~0.0325
    # "b" close second:     1/(60+2) + 1/(60+1) = same
    # tie broken by insertion order in dict, but the top two are {a, b}.
    items = [i for i, _ in fused]
    assert set(items[:2]) == {"a", "b"}
    assert "c" in items
    assert "d" in items
    assert "e" in items


def test_fuse_score_monotonic_in_rank():
    list1 = ["a", "b", "c"]
    fused = dict(rrf.fuse([list1], k=60))
    assert fused["a"] > fused["b"] > fused["c"]


def test_fuse_missing_from_list_contributes_zero():
    list1 = ["a", "b"]
    list2 = ["a"]
    fused = dict(rrf.fuse([list1, list2], k=60))
    # b is only in list1 -> score = 1/(60+2)
    assert fused["b"] == 1.0 / (60 + 2)
    # a is in both -> score = 1/(60+1) + 1/(60+1) = 2/(61)
    assert fused["a"] == 1.0 / 61 + 1.0 / 61


def test_fuse_with_ranks_lookups():
    fused, lookups = rrf.fuse_with_ranks([["x", "y"], ["y", "x", "z"]], k=60)
    assert lookups[0] == {"x": 1, "y": 2}
    assert lookups[1] == {"y": 1, "x": 2, "z": 3}
    assert dict(fused)["z"] == 1.0 / 63


def test_tied_ranks_average_and_fuse_uses_them():
    """A channel with many equal scores (category) must not have its ties broken by the sort order."""
    ids, score = ["a", "b", "c", "d"], {"a": 5.0, "b": 3.0, "c": 3.0, "d": 1.0}
    ranks = rrf.tied_ranks(ids, score)
    assert ranks == [1.0, 2.5, 2.5, 4.0]
    fused = dict(rrf.fuse([ids], k=60, ranks=[ranks]))
    assert fused["b"] == fused["c"]
    assert fused["a"] > fused["b"] > fused["d"]
    _, lookups = rrf.fuse_with_ranks([ids], k=60, ranks=[ranks])
    assert lookups[0]["c"] == 2.5
