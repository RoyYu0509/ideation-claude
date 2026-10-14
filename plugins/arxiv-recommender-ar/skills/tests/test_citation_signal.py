from unittest.mock import patch

from lib import citation_signal


def _make_paper(refs: list[str], paper_id: str | None = None) -> dict:
    return {"references": [{"paperId": r} for r in refs], "paperId": paper_id}


PROFILE_PAPERS = [
    {"paper_id": "P1", "reference_ids": ["R1", "R2", "R3"], "year": 2024},
    {"paper_id": "P2", "reference_ids": ["R2", "R4"], "year": 2023},
]


def test_rank_empty_candidates():
    result = citation_signal.rank([], PROFILE_PAPERS)
    assert result == []


def test_rank_no_overlap_returns_empty():
    batch_return = [_make_paper(["X1", "X2"])]
    with patch("lib.s2_client.papers_batch", return_value=batch_return):
        result = citation_signal.rank(["arxiv1"], PROFILE_PAPERS)
    assert result == []


def test_rank_direct_cite_scores():
    # Candidate cites P1 directly → direct=1, shared counted via refs overlap
    batch_return = [_make_paper(["P1", "R1"])]
    with patch("lib.s2_client.papers_batch", return_value=batch_return):
        result = citation_signal.rank(["arxiv1"], PROFILE_PAPERS)
    assert len(result) == 1
    idx, score = result[0]
    assert idx == 0
    # direct=1 → contributes direct_weight=2.0; shared=R1 in user_refs → 1.0
    assert score == 2.0 + 1.0


def test_rank_shared_only():
    batch_return = [_make_paper(["R2"])]
    with patch("lib.s2_client.papers_batch", return_value=batch_return):
        result = citation_signal.rank(["arxiv1"], PROFILE_PAPERS)
    assert len(result) == 1
    _, score = result[0]
    assert score == 1.0


def test_rank_custom_weights():
    batch_return = [_make_paper(["P1"])]
    with patch("lib.s2_client.papers_batch", return_value=batch_return):
        result = citation_signal.rank(
            ["arxiv1"], PROFILE_PAPERS,
            direct_weight=1.0, shared_weight=0.0,
        )
    assert len(result) == 1
    _, score = result[0]
    assert score == 1.0


def test_rank_sorting():
    # Two candidates; second has higher score
    batch_return = [_make_paper(["R1"]), _make_paper(["P1", "R1", "R2"])]
    with patch("lib.s2_client.papers_batch", return_value=batch_return):
        result = citation_signal.rank(["a1", "a2"], PROFILE_PAPERS)
    assert len(result) == 2
    assert result[0][1] > result[1][1]


def test_rank_null_paper_entries():
    batch_return = [None, _make_paper(["P1"])]
    with patch("lib.s2_client.papers_batch", return_value=batch_return):
        result = citation_signal.rank(["a1", "a2"], PROFILE_PAPERS)
    assert len(result) == 1
    assert result[0][0] == 1
