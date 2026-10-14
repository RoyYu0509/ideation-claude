"""Tests for scripts/dedup_candidates.py — the post-fetch / pre-ranking dedup
safety net (unique arxiv_id, order-preserving, signal-merging)."""
from dedup_candidates import dedup_candidates


def test_dedup_keeps_first_merges_signals():
    cands = [
        {"arxiv_id": "2606.001", "title": "A", "categories": ["cs.NA"], "links": ["u1"]},
        {"arxiv_id": "2606.002", "title": "B", "categories": ["stat.ML"]},
        {"arxiv_id": "2606.001", "title": "A-dup", "categories": ["math.NA"],
         "links": ["u2"], "pinned": True},
    ]
    out, removed = dedup_candidates(cands)
    assert removed == 1
    assert [c["arxiv_id"] for c in out] == ["2606.001", "2606.002"]  # order preserved
    kept = out[0]
    assert kept["title"] == "A"                              # first record kept
    assert kept["categories"] == ["cs.NA", "math.NA"]        # categories unioned
    assert kept["links"] == ["u1", "u2"]                     # links unioned
    assert kept["pinned"] is True                            # pinned OR-ed in


def test_clean_pool_unchanged():
    cands = [{"arxiv_id": f"2606.{i:03d}", "categories": []} for i in range(5)]
    out, removed = dedup_candidates(cands)
    assert removed == 0
    assert out == cands


def test_missing_id_passes_through():
    cands = [
        {"arxiv_id": "", "title": "no-id-1"},
        {"arxiv_id": None, "title": "no-id-2"},
        {"arxiv_id": "2606.001"},
        {"arxiv_id": "2606.001"},
    ]
    out, removed = dedup_candidates(cands)
    assert removed == 1                       # only the real duplicate collapses
    assert len(out) == 3                      # both id-less records kept
