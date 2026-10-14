"""Quota pool builder (REC-SYSTEM-V2 B3). Pure functions, no I/O.

The reranker reads the WHOLE prefetched pool, so fusion ORDER never reaches the product —
only pool MEMBERSHIP does. Equal-weight RRF let the number of SPECTER2 lists (one per
profile thread) set that family's vote share, and a paper found by one channel alone was
outvoted. Here every channel gets its seats up front:

  * every ACTIVE thread channel gets `floor` seats,
  * the rest of the thread budget is split in proportion to each thread's recent output
    (largest-remainder rounding, ties by thread order — deterministic),
  * the BM25 and citation channels get fixed seats (citation never more than it has hits),

then seats are filled round-robin by rank level, skipping papers already seated, and
anything left over is topped up from the RRF order. The numbers come from config.yaml
(prefetch.pool_quota) and are set a priori — never tuned on the evaluation labels.
"""
from __future__ import annotations

from typing import Mapping, Sequence


def allocate(
    k: int,
    threads: Sequence[tuple[str, int, bool]],
    floor: int,
    bm25_seats: int,
    citation_seats: int,
    citation_available: int,
) -> dict[str, int]:
    """Seats per channel. `threads` = (channel, n_recent, active) in profile order.

    Legacy (inactive) threads get 0 seats: recency weighting lives here now. The sum of
    seats never exceeds k; seats a channel cannot use are filled from RRF by seat_pool().
    """
    seats: dict[str, int] = {name: 0 for name, _, _ in threads}
    cit = max(0, min(citation_seats, citation_available))
    bm = max(0, bm25_seats)
    if cit + bm > k:                                  # tiny k: keep the ratio, favour BM25
        bm = min(bm, k)
        cit = min(cit, k - bm)
    budget = k - cit - bm
    active = [(name, max(0, n)) for name, n, is_active in threads if is_active]
    if active and budget > 0:
        fl = min(max(0, floor), budget // len(active))
        for name, _ in active:
            seats[name] = fl
        rest = budget - fl * len(active)
        if rest > 0:
            total = sum(n for _, n in active)
            shares = [(name, rest * (n / total if total else 1 / len(active))) for name, n in active]
            base = {name: int(x) for name, x in shares}
            left = rest - sum(base.values())
            order = sorted(range(len(shares)), key=lambda i: (-(shares[i][1] - int(shares[i][1])), i))
            for i in order[:left]:
                base[shares[i][0]] += 1
            for name, b in base.items():
                seats[name] += b
    if bm:
        seats["bm25"] = bm
    if cit:
        seats["citation"] = cit
    return seats


def seat_pool(
    channels: Mapping[str, Sequence[str]],
    seats: Mapping[str, int],
    k: int,
    fill: Sequence[str],
    order: Sequence[str],
) -> tuple[list[str], dict[str, str]]:
    """Fill the pool. Each pass visits the channels in `order`; a channel with seats left
    takes its next paper that is not seated yet. When no channel can take another paper,
    top up to k from `fill` (the RRF order). Returns (pool ids in seating order,
    {id: seating channel, or "fill"})."""
    pool: list[str] = []
    by: dict[str, str] = {}
    pos = {c: 0 for c in order}
    left = {c: max(0, int(seats.get(c, 0))) for c in order}
    progressed = True
    while progressed and len(pool) < k:
        progressed = False
        for c in order:
            if left[c] <= 0 or len(pool) >= k:
                continue
            ranked = channels.get(c) or []
            while pos[c] < len(ranked) and ranked[pos[c]] in by:
                pos[c] += 1
            if pos[c] < len(ranked):
                pid = ranked[pos[c]]
                pos[c] += 1
                by[pid] = c
                pool.append(pid)
                left[c] -= 1
                progressed = True
    for pid in fill:
        if len(pool) >= k:
            break
        if pid not in by:
            by[pid] = "fill"
            pool.append(pid)
    return pool, by
