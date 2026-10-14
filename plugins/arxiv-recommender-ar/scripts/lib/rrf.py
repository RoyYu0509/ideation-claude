"""Reciprocal Rank Fusion.

Given several ranked lists over a shared item universe, produce a fused ranking:

    score(d) = sum_i 1 / (k + rank_i(d))   (rank_i is 1-indexed)

Items missing from a list contribute nothing from that list.

A list may carry EXPLICIT ranks instead of positional ones. That is what a channel whose score has many ties
needs: the category channel scores a candidate by the weight of its arXiv categories, so hundreds of papers
share a score, and each of them must take the MEAN of the ranks the tie spans (EVAL-PLAN 2026-09-14 §3) —
otherwise an arbitrary sort order inside a tie would decide the fused ranking.
"""
from __future__ import annotations

from typing import Mapping, Sequence


def tied_ranks(ids: Sequence[str], score: Mapping[str, float]) -> list[float]:
    """1-based ranks of an already score-sorted list, with each tie taking the mean of its ranks."""
    out: list[float] = []
    i = 0
    while i < len(ids):
        j = i
        while j + 1 < len(ids) and score[ids[j + 1]] == score[ids[i]]:
            j += 1
        out.extend([(i + 1 + j + 1) / 2.0] * (j - i + 1))
        i = j + 1
    return out


def fuse(
    ranked_lists: Sequence[Sequence[str]],
    k: int = 60,
    ranks: Sequence[Sequence[float] | None] | None = None,
    weights: Sequence[float] | None = None,
) -> list[tuple[str, float]]:
    """ranks[i] (when given) holds list i's rank for each of its items; None = positional 1-indexed.
    weights[i] (when given) multiplies list i's contribution; None = every list weighs 1
    (lib/thread_fusion sets them — 2026-09-16)."""
    if weights is not None and len(weights) != len(ranked_lists):
        raise ValueError(f"rrf.fuse: {len(weights)} weights for {len(ranked_lists)} lists")
    scores: dict[str, float] = {}
    for i, ranked in enumerate(ranked_lists):
        rk = ranks[i] if ranks is not None and i < len(ranks) else None
        w = 1.0 if weights is None else float(weights[i])
        for idx, item in enumerate(ranked):
            rank = rk[idx] if rk is not None else idx + 1
            scores[item] = scores.get(item, 0.0) + w / (k + rank)
    return sorted(scores.items(), key=lambda p: -p[1])


def fuse_with_ranks(
    ranked_lists: Sequence[Sequence[str]],
    k: int = 60,
    ranks: Sequence[Sequence[float] | None] | None = None,
    weights: Sequence[float] | None = None,
) -> tuple[list[tuple[str, float]], list[dict[str, float]]]:
    """Same as fuse(), but also returns per-list rank lookups for diagnostics."""
    rank_lookups = []
    for i, ranked in enumerate(ranked_lists):
        rk = ranks[i] if ranks is not None and i < len(ranks) else None
        rank_lookups.append({item: (rk[idx] if rk is not None else idx + 1) for idx, item in enumerate(ranked)})
    return fuse(ranked_lists, k=k, ranks=ranks, weights=weights), rank_lookups
