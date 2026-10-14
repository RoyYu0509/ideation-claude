#!/usr/bin/env python3
"""Agent-as-a-judge harness for the Phase 3→4 deep-dive SELECTION problem.

Closes the loop on "which coverage_mode best reflects the researcher's breadth
without hurting per-paper quality", extending the existing eval culture
(eval_prefetch_quality.py / "S4 wins") with an LLM judge for the calibration
dimension that proxy metrics (dp/kw/tc) cannot fully capture.

Split of labour (deterministic harness here; agents elsewhere):
  prepare   — given a week's reranked pool + profile, apply each coverage_mode
              (off|stratify|mmr) via the shared coverage_select, compute proxy
              metrics, and emit BLIND pairwise judge tasks (mode identity hidden,
              A/B order shuffled deterministically). Pure Python, no agents.
  aggregate — read the judge verdicts back, tally win-rates per mode, cross-check
              against proxies, and print a ranking + conclusion.

The judging itself (and any agentic selection arm) is run by the controller
agent or the coverage-judge workflow over the emitted tasks — Python cannot
spawn Claude. This keeps the deterministic logic in code and the reasoning in
agents, per the project's design principle.

Proxy metrics per mode (over the selected deep-dive set of size N):
  digest_tc      — number of distinct threads (the breadth signal to maximise)
  rank1_id       — selected[0]; MUST be identical across modes (the structural
                   anti-cat-rebalance guarantee: rank-1 is never displaced, so
                   dp@1 cannot regress)
  concentration  — max papers in any one thread / N (lower = less monopolised)
  (with --prefetched) n_dead_repo / n_strong / mean_author_h over the set
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config, coverage_select  # noqa: E402

MODES = ["off", "stratify", "mmr"]


def _load_pool(path: Path) -> list[dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    return d if isinstance(d, list) else (d.get("top_papers") or [])


def _profile_summary(profile_path: Path) -> dict:
    p = json.loads(profile_path.read_text(encoding="utf-8"))
    return {
        "threads": [t.get("label") for t in (p.get("threads") or []) if t.get("label")],
        "recent_direction": p.get("recent_direction") or "",
    }


def _proxy(selected: list[dict], n: int, prefetch_by_id: dict | None) -> dict:
    threads = [p.get("thread") or "?" for p in selected]
    distinct = sorted(set(threads))
    counts: dict[str, int] = {}
    for t in threads:
        counts[t] = counts.get(t, 0) + 1
    out = {
        "n": len(selected),
        "digest_tc": len(distinct),
        "distinct_threads": distinct,
        "rank1_id": selected[0]["arxiv_id"] if selected else None,
        "concentration": round(max(counts.values()) / max(1, len(selected)), 3) if selected else 0,
    }
    if prefetch_by_id:
        tiers = [prefetch_by_id.get(p["arxiv_id"], {}).get("quality_tier") for p in selected]
        hs = [prefetch_by_id.get(p["arxiv_id"], {}).get("author_h_max") for p in selected]
        hs = [h for h in hs if isinstance(h, int)]
        out["n_dead_repo"] = sum(
            1 for p in selected
            if prefetch_by_id.get(p["arxiv_id"], {}).get("repo_status") == "repo_claimed_but_dead"
        )
        out["n_strong"] = sum(1 for t in tiers if t == "strong")
        out["mean_author_h"] = round(sum(hs) / len(hs), 1) if hs else None
    return out


def _digest_view(selected: list[dict]) -> list[dict]:
    """Anonymised paper view for the judge (no mode identity)."""
    return [{
        "arxiv_id": p.get("arxiv_id"),
        "title": p.get("title"),
        "thread": p.get("thread"),
        "why_it_matters": p.get("why_it_matters") or p.get("extensibility_rationale") or "",
    } for p in selected]


JUDGE_RUBRIC = (
    "You are evaluating two candidate weekly research digests (Digest 1 and Digest 2) "
    "for a single researcher, each a small set of papers selected for deep follow-up.\n\n"
    "Researcher profile:\n"
    "- Active research threads: {threads}\n"
    "- Recent direction: {recent}\n\n"
    "Judge which digest better serves THIS researcher this week, weighing:\n"
    "1. Calibration / breadth — does the set reflect the researcher's portfolio of "
    "threads rather than over-concentrating on one? Penalise BOTH over-concentration "
    "AND padding with off-profile papers.\n"
    "2. Per-paper relevance & quality — are these strong, on-profile papers (not "
    "churn)?\n"
    "3. Overall usefulness — would this be a valuable week for the researcher?\n\n"
    "Digest 1:\n{d1}\n\nDigest 2:\n{d2}\n\n"
    "Respond with strict JSON: {{\"winner\": \"1\"|\"2\"|\"tie\", \"reason\": \"<=2 sentences\"}}."
)


def _fmt_digest(view: list[dict]) -> str:
    return "\n".join(
        f"  {i+1}. {p['title']} [thread: {p['thread']}] — {p['why_it_matters']}"
        for i, p in enumerate(view)
    )


def cmd_prepare(args: argparse.Namespace) -> int:
    pool = _load_pool(args.pool)
    if not pool:
        print("empty pool", file=sys.stderr); return 1
    prof = _profile_summary(args.profile) if args.profile and args.profile.exists() else {"threads": [], "recent_direction": ""}
    prefetch_by_id = None
    if args.prefetched and args.prefetched.exists():
        pj = json.loads(args.prefetched.read_text(encoding="utf-8"))
        prefetch_by_id = {c["arxiv_id"]: c for c in pj.get("candidates", [])}

    n = args.n
    per_mode = {}
    for mode in MODES:
        sel = coverage_select.select(pool, n, mode=mode, mmr_lambda=args.mmr_lambda)
        per_mode[mode] = {"ids": [p["arxiv_id"] for p in sel], "view": _digest_view(sel),
                          "proxy": _proxy(sel, n, prefetch_by_id)}

    # Proxy table
    print(f"\n{'='*64}\nCOVERAGE SELECTION — proxy metrics (week {args.week}, N={n})\n{'='*64}")
    print(f"{'mode':<10}{'digest_tc':<11}{'concentration':<15}{'rank1_id':<14}{'threads'}")
    for mode in MODES:
        px = per_mode[mode]["proxy"]
        print(f"{mode:<10}{px['digest_tc']:<11}{px['concentration']:<15}{str(px['rank1_id']):<14}{px['distinct_threads']}")
    r1 = {per_mode[m]['proxy']['rank1_id'] for m in MODES}
    print(f"\nrank-1 identical across modes: {len(r1) == 1}  (structural dp@1 guarantee)")
    if prefetch_by_id:
        print("\nquality over selected set:")
        for mode in MODES:
            px = per_mode[mode]["proxy"]
            print(f"  {mode:<10} dead_repo={px.get('n_dead_repo')} strong={px.get('n_strong')} mean_author_h={px.get('mean_author_h')}")

    # Blind pairwise judge tasks for modes whose selected set DIFFERS.
    rng = random.Random(f"{args.week}-{n}")
    tasks = []
    for i in range(len(MODES)):
        for j in range(i + 1, len(MODES)):
            ma, mb = MODES[i], MODES[j]
            if per_mode[ma]["ids"] == per_mode[mb]["ids"]:
                continue  # identical selection — judging is uninformative
            # deterministic blind A/B assignment
            swap = rng.random() < 0.5
            first, second = (mb, ma) if swap else (ma, mb)
            prompt = JUDGE_RUBRIC.format(
                threads=", ".join(prof["threads"]) or "(unknown)",
                recent=(prof["recent_direction"] or "(unknown)")[:400],
                d1=_fmt_digest(per_mode[first]["view"]),
                d2=_fmt_digest(per_mode[second]["view"]),
            )
            tasks.append({
                "task_id": f"{args.week}:{ma}-vs-{mb}",
                "digest_1_mode": first, "digest_2_mode": second,  # hidden from judge; for aggregation
                "judge_prompt": prompt,
            })

    out = {
        "week": args.week, "n": n, "modes": per_mode,
        "n_pairwise_tasks": len(tasks), "pairwise": tasks,
        "note": "Run each judge_prompt with a blind judge agent; collect "
                "{task_id, winner:'1'|'2'|'tie'} into a verdicts JSON, then `aggregate`.",
    }
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {len(tasks)} pairwise judge task(s) → {args.out}")
    if not tasks:
        print("(no informative pairs this week — modes selected identical sets; "
              "breadth section still shows full portfolio regardless)")
    return 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
    verdicts = json.loads(args.verdicts.read_text(encoding="utf-8"))
    vmap = {v["task_id"]: v for v in (verdicts if isinstance(verdicts, list) else verdicts.get("verdicts", []))}

    wins: dict[str, float] = {m: 0.0 for m in MODES}
    games: dict[str, int] = {m: 0 for m in MODES}
    for t in tasks.get("pairwise", []):
        v = vmap.get(t["task_id"])
        if not v:
            continue
        m1, m2 = t["digest_1_mode"], t["digest_2_mode"]
        games[m1] += 1; games[m2] += 1
        w = str(v.get("winner", "tie")).lower()
        if w == "1":
            wins[m1] += 1
        elif w == "2":
            wins[m2] += 1
        else:
            wins[m1] += 0.5; wins[m2] += 0.5

    print(f"\n{'='*52}\nAGENT-AS-JUDGE — coverage_mode win rates\n{'='*52}")
    rank = sorted(MODES, key=lambda m: (wins[m] / games[m]) if games[m] else -1, reverse=True)
    for m in rank:
        wr = (wins[m] / games[m]) if games[m] else float("nan")
        print(f"  {m:<10} win_rate={wr:.2f}  ({wins[m]:.1f}/{games[m]} games)")
    played = [m for m in rank if games[m]]
    if played:
        print(f"\nCONCLUSION: judge prefers '{played[0]}' "
              f"(win_rate {wins[played[0]]/games[played[0]]:.2f}). "
              "Cross-check the proxy table: the winner should also hold rank-1 "
              "(dp@1) and not raise concentration.")
    else:
        print("\nNo verdicts matched — nothing to aggregate.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="agent-as-a-judge harness for coverage_mode selection")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--pool", type=Path, required=True, help="phase3 reranked pool JSON (list w/ thread+why)")
    p.add_argument("--profile", type=Path, default=config.profile_dir() / "profile.json")
    p.add_argument("--prefetched", type=Path, default=None, help="optional prefetched.json for quality proxies")
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--mmr-lambda", type=float, default=0.5)
    p.add_argument("--week", default="unknown")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(fn=cmd_prepare)

    a = sub.add_parser("aggregate")
    a.add_argument("--tasks", type=Path, required=True)
    a.add_argument("--verdicts", type=Path, required=True)
    a.set_defaults(fn=cmd_aggregate)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
