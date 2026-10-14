#!/usr/bin/env python3
"""Deterministic Phase-3.6 survivor tally → week-<W>-gated-pool.json — ZERO LLM tokens.

WHY THIS EXISTS (2026-07-12). The judge gate used to end with a JS/LLM loop that walked
the coverage-ordered queue and tallied each paper's judge verdict in memory
(arxiv-scout.js `queue.forEach`). When /arxiv-scout-beta is ENACTED by a headless L1
subagent (it reproduces the JS by hand), that in-memory tally is exactly where a run went
wrong: the orchestrator lost track of which judge leaves had actually returned, and
FABRICATED verdicts for ~10 papers to fill the gap (caught only by a lucky self-review).
The per-paper judge verdicts were, however, already persisted to week-<W>-judge-cache.json
by acceptCandidate/persistJudgeEntry. So the fix is to make the survivor tally a
deterministic Python step that reads the CACHE — the LLM can no longer tally from memory.

FAIL-CLOSED: if any coverage-queue member has no committed judge verdict in the cache, this
refuses to compute (exit 3) and names the missing papers — forcing the orchestrator to
actually run (or re-run) those judges rather than paper over them. Pinned papers are
force-included and are NOT judged (they carry no cache entry, by design).

    run_py.sh scripts/compute_gated_pool.py --week <W> --gate-input <file>
        [--judge-cache <path>] [--out <path>]

--gate-input JSON (written by the workflow right after the judge fan-out; FULL paper objects):
    { "queue":            [ <coverage-ordered, pinned excluded> ],
      "pinned":           [ <force-included, never judged> ],
      "ext_pool_ordered": [ <coverage-ordered extensibility pool, for the empty fail-safe> ],
      "n":                 <top_n_papers> }

Mirrors arxiv-scout.js lines 884-935 exactly: seed survivors with pinned (they count toward
N), then take the first N ok-verdict queue members in coverage order, tagging penalize→
quality_tier:'flagged'; if EVERY candidate was rejected, fall back to ext_pool_ordered[:N]
(never emit an empty digest). Writes the gate OUTPUT — the <= top_n_papers survivors that
ARE the Phase-4 ideation set and the resume boundary.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config  # noqa: E402


class GateError(RuntimeError):
    pass


def compute_pool(gate_input: dict, judge_cache: dict) -> dict:
    """Pure function (unit-testable): return {survivors, rejected, missing, failsafe}.
    survivors is a list of FULL paper objects; missing non-empty ⇒ caller must fail-closed."""
    queue = gate_input.get("queue") or []
    pinned = gate_input.get("pinned") or []
    ext_pool = gate_input.get("ext_pool_ordered") or []
    n = int(gate_input.get("n") or 0)
    if n <= 0:
        raise GateError("gate-input.n must be a positive integer (top_n_papers)")

    survivors: list[dict] = []
    seen: set[str] = set()
    for p in pinned:  # force-included, never judged; count toward N
        pid = p.get("arxiv_id")
        if pid and pid not in seen:
            survivors.append(p)
            seen.add(pid)

    rejected: list[dict] = []
    missing: list[str] = []
    for p in queue:
        pid = p.get("arxiv_id")
        if not pid or pid in seen:
            continue
        entry = judge_cache.get(pid)
        result = (entry or {}).get("result")
        if not isinstance(result, dict) or "ok" not in result:
            # No committed verdict for a paper that was supposed to be judged → fabrication vector.
            missing.append(pid)
            continue
        if not result.get("ok"):
            rejected.append({"arxiv_id": pid, "why": result.get("why", "")})
            continue
        if len(survivors) < n:
            survivors.append({**p, "quality_tier": "flagged"} if result.get("penalize") else p)
            seen.add(pid)
        # else: passed but all N slots filled (dropped, like the JS)

    failsafe = False
    if not survivors:
        # Never empty the digest — restore the pre-judge coverage selection (arxiv-scout.js:924).
        survivors = list(ext_pool)[:n]
        failsafe = True

    return {"survivors": survivors, "rejected": rejected, "missing": missing, "failsafe": failsafe}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--week", required=True, help="ISO week, e.g. 2026-W28")
    ap.add_argument("--gate-input", required=True, help="queue/pinned/ext_pool_ordered/n JSON")
    ap.add_argument("--judge-cache", default=None, help="override week-<W>-judge-cache.json path")
    ap.add_argument("--out", default=None, help="override week-<W>-gated-pool.json path")
    args = ap.parse_args()

    cache_dir = config.cache_dir()
    judge_cache_path = Path(args.judge_cache) if args.judge_cache else cache_dir / f"week-{args.week}-judge-cache.json"
    out_path = Path(args.out) if args.out else cache_dir / f"week-{args.week}-gated-pool.json"

    try:
        gate_input = json.loads(Path(args.gate_input).read_text())
    except Exception as e:
        print(f"compute_gated_pool: cannot read --gate-input {args.gate_input}: {e}", file=sys.stderr)
        return 2
    try:
        judge_cache = json.loads(judge_cache_path.read_text()) if judge_cache_path.exists() else {}
    except Exception as e:
        print(f"compute_gated_pool: cannot read judge-cache {judge_cache_path}: {e}", file=sys.stderr)
        return 2

    try:
        r = compute_pool(gate_input, judge_cache)
    except GateError as e:
        print(f"compute_gated_pool: {e}", file=sys.stderr)
        return 2

    if r["missing"]:
        # FAIL-CLOSED: refuse to tally when a judged-queue paper has no committed verdict.
        print(
            "compute_gated_pool: FAIL-CLOSED — no committed judge verdict in "
            f"{judge_cache_path.name} for: {', '.join(r['missing'])}. "
            "These papers were in the coverage queue but were never actually judged (or their "
            "verdict was not persisted). Run the claim/repo judge for each and persist it to the "
            "judge-cache, then re-run — do NOT tally verdicts from memory.",
            file=sys.stderr,
        )
        return 3

    survivors = r["survivors"]
    out_path.write_text(json.dumps(survivors))  # compact, like arxiv-scout.js JSON.stringify(gatedPapers)
    ids = [p.get("arxiv_id") for p in survivors]
    print(json.dumps({
        "week": args.week,
        "survivors": ids,
        "survivor_count": len(survivors),
        "rejected": r["rejected"],
        "failsafe": r["failsafe"],
        "out": str(out_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
