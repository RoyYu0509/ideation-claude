"""lib/thread_seed.py — per-thread seed selection over the delivered reading list (2026-09-20).

Replaces the G1 → TOP select (lib/rerank_llm.py, kept intact because report-v2/ablation imports it
to reproduce the evaluated reranking arms). The rule this module implements has NO free parameters:

    Every paper in the delivered reading list belongs to the thread that ranks it highest. Each
    thread's seed is the highest-ranked paper it owns that passes the checks.

The ownership is a partition, so a paper serves at most one thread by construction and there is
nothing to arbitrate; a thread that owns no paper this week simply has no seed.

What the G1 → TOP select needed and this does not: a promotion target (40), a returned-set size
(2 x top_n_papers), one blinded call per group, one final ranking call, and a padding rule for a
short list. A thread whose papers are all rejected by the gate has no seed, and the vacancy is
reported rather than filled.

Nothing here judges a paper. The caller (workflows/arxiv-scout.js) walks the orders this module
emits, spawns the gate for the nominated papers, and assigns. This module is a pure function over
two files the recommender already wrote:

    week-<W>-prefetched.json   every candidate carries `channel_ranks` = {thread_i: rank, ...}
    week-<W>-channels.json     `thread_labels` = {thread_i: <the profile thread's name>}

so the partition and the per-thread orders are sorts, not new computations. A paper no thread's
channel listed (seated by a lexical, category or citation signal alone) owns no seed.

Subcommands:
    order  --week <W>              the per-thread candidate orders (stdout JSON), threads sorted
                                   by the order they are served in
    final  --week <W> --seeds ...  write week-<W>-rerank-llm/final.json in the shape the
                                   arxiv-rerank skill already consumes, so the rationale step's
                                   contract is unchanged
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config  # noqa: E402
from lib.rerank_llm import TOP_K  # noqa: E402  — the delivered reading list's length, one definition


def _load(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def owner_thread(cand: dict[str, Any]) -> str | None:
    """The thread that ranks this paper highest — the thread it belongs to.

    Per-thread ranks are positions in the same full-pool ordering, one per thread, so they compare
    directly. Ties break by thread key, which makes the partition total and reproducible.
    """
    ranks = {k: v for k, v in (cand.get("channel_ranks") or {}).items()
             if k.startswith("thread_") and v is not None}
    if not ranks:
        return None
    return min(ranks, key=lambda k: (ranks[k], k))


def thread_orders(prefetched: dict[str, Any], channels: dict[str, Any], profile: dict[str, Any],
                  pool_k: int = TOP_K) -> list[dict[str, Any]]:
    """Each thread's own papers from the delivered list, best first.

    Threads come back in the order they are walked: larger threads first (a thread's size is its
    member-paper count in the profile), ties by thread key. Because ownership partitions the list
    the walk order changes nothing about the outcome; it only fixes the logs and the served order.
    """
    pool = prefetched["candidates"][:pool_k]
    labels = channels.get("thread_labels") or {}
    sizes = {t.get("name"): len(t.get("papers") or []) for t in (profile.get("threads") or [])}

    owned: dict[str, list[tuple[int, str]]] = {k: [] for k in labels if k.startswith("thread_")}
    unowned = 0
    for c in pool:
        key = owner_thread(c)
        if key is None or key not in owned:
            unowned += 1
            continue
        owned[key].append((c["channel_ranks"][key], c["arxiv_id"]))

    orders: list[dict[str, Any]] = []
    for key, items in owned.items():
        items.sort()
        orders.append({
            "key": key,
            "name": labels[key],
            "size": int(sizes.get(labels[key], 0)),
            "candidates": [axid for _, axid in items],
        })
    orders.sort(key=lambda t: (-t["size"], t["key"]))
    if unowned:
        print(f"[thread_seed] {unowned}/{len(pool)} delivered papers are on no thread's ranking "
              f"(seated by a non-thread signal) and own no seed", file=sys.stderr)
    return orders


def walk(orders: list[dict[str, Any]], state: dict[str, Any],
         verdicts: dict[str, bool], exempt: set[str] | None = None) -> dict[str, Any]:
    """One turn of the seed walk: bank the verdicts we have, then nominate the next papers.

    `verdicts` is read from the judge CACHE by the caller, never from an enactor's memory — the same
    anti-fabrication boundary compute_gated_pool.py draws. A nomination with no committed verdict is
    left standing and re-nominated, so a crash mid-round costs nothing and invents nothing.

    Returns the new state plus this turn's nominations; `done` means every thread is either seeded
    or out of papers.
    """
    by_key = {t["key"]: t for t in orders}
    exempt = exempt or set()          # pinned papers: force-included elsewhere, never judged here
    cursor: dict[str, int] = dict(state.get("cursor") or {})
    seeds: list[dict[str, str]] = list(state.get("seeds") or [])
    rejected: list[str] = list(state.get("rejected") or [])
    seeded = {s["key"] for s in seeds}

    # 1) bank every standing nomination that now carries a verdict
    standing = []
    for nom in (state.get("nominations") or []):
        key, axid = nom["key"], nom["arxiv_id"]
        if key in seeded:
            continue
        if axid not in verdicts:
            standing.append(nom)                     # no committed verdict yet — keep it standing
            continue
        cursor[key] = cursor.get(key, 0) + 1
        if verdicts[axid]:
            seeds.append({"key": key, "arxiv_id": axid, "thread": by_key[key]["name"]})
            seeded.add(key)
        else:
            rejected.append(axid)

    # 2) nominate the next unseen paper for every thread still without a seed
    nominations = list(standing)
    pending = {n["key"] for n in standing}
    for t in orders:
        if t["key"] in seeded or t["key"] in pending:
            continue
        i = cursor.get(t["key"], 0)
        while i < len(t["candidates"]) and t["candidates"][i] in exempt:
            i += 1                     # a pinned paper is already in the set; it does not seed a thread
        cursor[t["key"]] = i
        if i < len(t["candidates"]):
            nominations.append({"key": t["key"], "arxiv_id": t["candidates"][i]})

    return {
        "cursor": cursor,
        "seeds": seeds,
        "rejected": rejected,
        "nominations": nominations,
        "done": not nominations,
        "unseeded": [t["key"] for t in orders if t["key"] not in seeded],
    }


def write_final(week: str, seeds: list[dict[str, str]], out_dir: Path) -> Path:
    """Write final.json in the shape the arxiv-rerank skill already reads.

    `top` = the seeds in served order, each with the thread it was seeded for. `source` is
    'thread_seed' for every entry: unlike the select this replaces, nothing here is padded, so a
    null thread can no longer occur.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "final.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "week": week,
            "select": "thread_seed",
            "top": [{"arxiv_id": s["arxiv_id"], "thread": s["thread"], "source": "thread_seed"}
                    for s in seeds],
        }, f, indent=2)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_order = sub.add_parser("order")
    p_order.add_argument("--week", required=True)
    p_order.add_argument("--pool-k", type=int, default=TOP_K)

    p_walk = sub.add_parser("walk")
    p_walk.add_argument("--week", required=True)
    p_walk.add_argument("--state", required=True, help="JSON state file; created on the first turn")
    p_walk.add_argument("--judge-cache", default=None,
                        help="week-<W>-judge-cache.json; verdicts are read from it, never passed in")
    p_walk.add_argument("--pool-k", type=int, default=TOP_K)
    p_walk.add_argument("--exempt", default="", help="comma-separated pinned ids: never nominated")

    p_final = sub.add_parser("final")
    p_final.add_argument("--week", required=True)
    p_final.add_argument("--seeds", required=True,
                         help="JSON file: [{arxiv_id, thread}, ...] in served order")
    p_final.add_argument("--out-dir", default=None)

    args = ap.parse_args()
    cache = config.cache_dir()

    if args.cmd == "order":
        prefetched = _load(cache / f"week-{args.week}-prefetched.json")
        channels = _load(cache / f"week-{args.week}-channels.json")
        profile = _load(config.data_root() / "data" / "profile" / "profile.json")
        orders = thread_orders(prefetched, channels, profile, pool_k=args.pool_k)
        print(json.dumps({"pool_k": args.pool_k, "threads": orders}))
        return 0

    if args.cmd == "walk":
        prefetched = _load(cache / f"week-{args.week}-prefetched.json")
        channels = _load(cache / f"week-{args.week}-channels.json")
        profile = _load(config.data_root() / "data" / "profile" / "profile.json")
        orders = thread_orders(prefetched, channels, profile, pool_k=args.pool_k)

        state_path = Path(args.state)
        state = _load(state_path) if state_path.exists() else {}
        cache_path = Path(args.judge_cache) if args.judge_cache else (
            cache / f"week-{args.week}-judge-cache.json")
        raw = _load(cache_path) if cache_path.exists() else {}
        verdicts = {axid: bool((e.get("result") or {}).get("ok"))
                    for axid, e in raw.items() if e.get("result")}

        exempt = {x.strip() for x in args.exempt.split(",") if x.strip()}
        state = walk(orders, state, verdicts, exempt)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        print(json.dumps(state))
        return 0

    seeds = _load(Path(args.seeds))
    out_dir = Path(args.out_dir) if args.out_dir else (cache / f"week-{args.week}-rerank-llm")
    path = write_final(args.week, seeds, out_dir)
    print(json.dumps({"final_path": str(path), "n_top": len(seeds)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
