#!/usr/bin/env python3
"""Thread-aware deep-dive selection — the single source of truth for the
Phase 3→4 funnel cut, shared by the live workflow (called via CLI) and the
agent-as-judge experiment (imported).

The funnel today is a thread-blind ``slice(0, N)`` over the rerank-ordered,
extensibility-gated pool — which is why a few high-volume threads monopolise the
N deep-dive slots and the digest oscillates week to week. These mechanical
selectors choose WHICH N gate-passing papers get deep-dived, generically over
however many threads the profile declares.

Hard invariants (all modes), designed to never repeat the category-rebalance
failure (which displaced the top pick and tanked dp@1):
  * the single best relevance pick (pool[0]) is ALWAYS selected first;
  * selection only reorders an already-relevant, already-gated pool — it never
    mutates scores, never promotes an off-profile paper to fill a quota, and
    never forces a uniform distribution;
  * a thread with no gate-passing paper simply gets no slot (no weak paper is
    promoted to hit balance).

Modes:
  off       — baseline: pool[:n] (thread-blind, current behaviour).
  stratify  — pool[0], then the best paper of each NEW thread in rerank order,
              then fill remaining slots by rerank order.
  mmr       — pool[0], then greedy Maximal-Marginal-Relevance with thread
              redundancy: score = λ·rel − (1−λ)·redundancy. λ tunes
              relevance↔diversity (no hard quota).

Agentic modes (soft_calibrate / prior / critic) are NOT here — they change the
reranker/critic agent's behaviour, not a deterministic post-rerank selection.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _thread(p: dict[str, Any]) -> str:
    return p.get("thread") or "?"


def _staleness(label: str, rotation: dict[str, Any] | None, current_week_idx: int) -> float:
    """How long since this thread was last deep-dived (bigger = staler). Never
    dived → +inf (highest priority). Used only as a TIE-BREAK among threads
    competing for leftover slots — never reorders by relevance."""
    if not rotation:
        return 0.0
    last = (rotation.get("last_deep_dive") or {}).get(label)
    if last is None:
        return float("inf")
    return float(current_week_idx - last)


def _select_stratify(pool, n, rotation, current_week_idx):
    picked = [pool[0]]
    used = {_thread(pool[0])}
    # best (first-in-rerank-order) paper per thread, excluding rank-1's thread
    first_by_thread: dict[str, dict] = {}
    for p in pool:
        first_by_thread.setdefault(_thread(p), p)
    candidates = [p for t, p in first_by_thread.items() if t not in used]
    if rotation and rotation.get("rotation_enabled"):
        # stale-first tie-break, stable within tier (preserve rerank order)
        idx = {id(p): i for i, p in enumerate(pool)}
        candidates.sort(key=lambda p: (-_staleness(_thread(p), rotation, current_week_idx), idx[id(p)]))
    for p in candidates:
        if len(picked) >= n:
            break
        picked.append(p)
        used.add(_thread(p))
    if len(picked) < n:
        chosen_ids = {p["arxiv_id"] for p in picked}
        for p in pool:
            if len(picked) >= n:
                break
            if p["arxiv_id"] not in chosen_ids:
                picked.append(p)
                chosen_ids.add(p["arxiv_id"])
    return picked


def _select_mmr(pool, n, mmr_lambda):
    picked = [pool[0]]
    remaining = pool[1:]
    npool = len(pool)
    while remaining and len(picked) < n:
        picked_threads = [_thread(p) for p in picked]
        best, best_score, best_i = None, None, None
        for i, p in enumerate(remaining):
            rank = pool.index(p)
            rel = 1.0 - rank / npool  # rerank-order relevance proxy, rank-1 highest
            same = picked_threads.count(_thread(p))
            redundancy = same / len(picked)  # fraction of already-picked sharing this thread
            score = mmr_lambda * rel - (1.0 - mmr_lambda) * redundancy
            if best_score is None or score > best_score:
                best, best_score, best_i = p, score, i
        picked.append(best)
        remaining.pop(best_i)
    return picked


def select(
    pool: list[dict[str, Any]],
    n: int,
    *,
    mode: str = "off",
    rotation: dict[str, Any] | None = None,
    current_week_idx: int = 0,
    mmr_lambda: float = 0.5,
    rank_all: bool = False,
) -> list[dict[str, Any]]:
    """Return the chosen sub-list (≤ n), selection order (rank-1 first).

    ``pool`` must be sorted best-first (rerank order). Pure & deterministic for
    a fixed pool (+ fixed rotation). Unknown mode → 'off'.

    When ``rank_all`` is set, ``n`` is ignored and the FULL pool is returned as a
    coverage-ordered permutation (the fill-to-N walk order: rank-1, then one per
    new thread, then the rerank tail). ``mode == 'off'`` + ``rank_all`` is plain
    rerank order."""
    if not pool:
        return []
    if rank_all:
        n = len(pool)
    if mode == "off" or (not rank_all and len(pool) <= n):
        return pool[:n]
    if mode == "stratify":
        return _select_stratify(pool, n, rotation, current_week_idx)
    if mode == "mmr":
        return _select_mmr(pool, n, mmr_lambda)
    return pool[:n]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=Path, required=True, help="JSON file: list of gate-passing papers, rerank order")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--mode", default="off")
    ap.add_argument("--mmr-lambda", type=float, default=0.5)
    ap.add_argument("--rotation", type=Path, default=None, help="optional thread-coverage-history.json")
    ap.add_argument("--current-week-idx", type=int, default=0)
    ap.add_argument("--rank-all", action="store_true",
                    help="ignore --n and return a FULL coverage-ordered permutation of the pool "
                         "(the fill-to-N walk order)")
    args = ap.parse_args()

    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    rotation = None
    if args.rotation and args.rotation.exists():
        try:
            rotation = json.loads(args.rotation.read_text(encoding="utf-8"))
            rotation["rotation_enabled"] = True
        except Exception as e:
            print(f"[coverage_select] WARNING: rotation history unreadable ({e}); "
                  "staleness tie-break disabled, falling back to rerank order", file=sys.stderr)
            rotation = None
    chosen = select(pool, args.n, mode=args.mode, rotation=rotation,
                    current_week_idx=args.current_week_idx, mmr_lambda=args.mmr_lambda,
                    rank_all=args.rank_all)
    # Emit just the arxiv_ids in selection order (the caller maps back to papers).
    print(json.dumps([p["arxiv_id"] for p in chosen]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
