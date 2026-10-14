"""How a profile's per-thread channel lists enter the RRF fusion — config prefetch.thread_fusion (2026-09-16).

Every research thread is its own ranked list (lib/channel_spec.thread_members). With K threads the thread
channel therefore casts K votes against one vote for every other channel: on a 9-thread profile the thread
lists carry 72% of the fused top-300's RRF score, and the share grows with profile.max_threads (6 → 10 on
2026-09-16) although nobody chose it. This module is the one definition of the alternatives; prefetch and
the ablation runtime (report-v2/ablation) both call `apply`.

  per_thread  every thread list weighs 1 — the behaviour before this key existed.
  split       every thread list weighs 1/K — the thread channel casts one vote in total.
  sqrt        thread i weighs sqrt(n_i) / mean_j sqrt(n_j), n = the member papers its list is built from
              (profile-diag analyze.py 'sqrt'); the thread total stays K, larger threads count more.
  best        the K lists collapse into ONE list "thread_best" (weight 1), placed where the first thread
              list was: papers ordered by their per-thread ranks sorted ascending — best rank first, ties
              broken by the next-best rank — and, if still tied, by first appearance (as rrf.fuse does).
              A paper strong on a single thread keeps its place instead of being outvoted by papers that
              are mildly similar to every thread.

Evidence before the ablation (researcher labels, batch 1, old 6-thread profiles, off-thread recall@300 —
profile-diag REPORT §2 R3): "the thread family casts one vote" (= split) was WORSE, −0.065 with the interval
excluding 0, and worse on all 10 opus builds; sqrt was +0.009 (interval spanning 0); best was never tested.
The default stays per_thread until EVAL-PLAN amendment #3's ablation decides.

Only the v2 channel set, and only pool_rule rrf: the legacy thread lists are truncated prose queries, and the
quota rule seats each thread list separately.
"""
from __future__ import annotations

import math
from typing import Mapping, Sequence

MODES = ("per_thread", "split", "sqrt", "best")
BEST_NAME = "thread_best"
THREAD_PREFIX = "thread_"


def is_thread(name: str) -> bool:
    return name.startswith(THREAD_PREFIX) and name != BEST_NAME


def check(mode: str, channel_set: str, pool_rule: str) -> None:
    """Raise ValueError for a mode this run cannot honour. Never falls back to per_thread."""
    if mode not in MODES:
        raise ValueError(f"thread_fusion = {mode!r}; must be one of {MODES}")
    if mode != "per_thread" and channel_set != "v2":
        raise ValueError(f"thread_fusion = {mode!r} needs channel_set v2 (got {channel_set!r})")
    if mode != "per_thread" and pool_rule != "rrf":
        raise ValueError(f"thread_fusion = {mode!r} needs pool_rule rrf (quota seats every thread list separately)")


def collapse_best(thread_lists: Sequence[Sequence[str]]) -> list[str]:
    """K ranked lists → one: each paper's per-thread ranks sorted ascending, compared lexicographically.
    A paper missing from a list counts as ranked after that list's last item."""
    per_paper: dict[str, list[float]] = {}
    for lst in thread_lists:                                  # insertion order = first appearance
        for a in lst:
            per_paper.setdefault(a, [])
    for lst in thread_lists:
        pos_of = {a: i + 1 for i, a in enumerate(lst)}
        miss = len(lst) + 1
        for a, ranks in per_paper.items():
            ranks.append(pos_of.get(a, miss))
    return sorted(per_paper, key=lambda a: sorted(per_paper[a]))   # stable: ties keep first appearance


def apply(mode: str, named: Sequence[tuple[str, Sequence[str]]],
          sizes: Mapping[str, int] | None = None) -> tuple[list[tuple[str, list[str]]], list[float]]:
    """named = every channel's list in fusion order → (lists to fuse, their RRF weights).

    Non-thread lists pass through with weight 1. `sizes` (thread list name → member papers) is needed by sqrt."""
    if mode not in MODES:
        raise ValueError(f"thread_fusion = {mode!r}; must be one of {MODES}")
    named = [(n, list(lst)) for n, lst in named]
    threads = [n for n, _ in named if is_thread(n)]
    if mode == "per_thread" or not threads:
        return named, [1.0] * len(named)
    if mode == "best":
        merged = collapse_best([lst for n, lst in named if is_thread(n)])
        out: list[tuple[str, list[str]]] = []
        for n, lst in named:
            if not is_thread(n):
                out.append((n, lst))
            elif n == threads[0]:
                out.append((BEST_NAME, merged))
        return out, [1.0] * len(out)
    if mode == "split":
        w = {n: 1.0 / len(threads) for n in threads}
    else:                                                     # sqrt
        missing = [n for n in threads if not (sizes or {}).get(n)]
        if missing:
            raise ValueError(f"thread_fusion sqrt needs the member count of every thread list; missing {missing}")
        roots = {n: math.sqrt(sizes[n]) for n in threads}
        mean = sum(roots.values()) / len(roots)
        w = {n: r / mean for n, r in roots.items()}
    return named, [w.get(n, 1.0) for n, _ in named]
