#!/usr/bin/env python3
"""bin/count_guard_denials.py — READ-ONLY: how often the spawn guard fired, and whether
being told "no" once was enough.

For the technical report's N1 row. Counts, from the native Claude Code session transcripts,
every attempt to spawn the built-in `general-purpose` subagent (which `hooks/spawn_guard.py`
denies unconditionally, because it carries the Agent tool and can recurse without bound) and
matches each attempt to its tool_result to confirm the deny actually landed.

Counting method matters here, and the loose version is wrong. The deny text appears several
times per incident across the transcript — in the hook record, in the tool result, and again
wherever the model quotes it back. Grepping the text and de-duplicating on any nearby
`tool_use_id` over-counts by ~1.7x (68 vs 39 on the same corpus). The number this script
reports is the defensible one: unique Task/Agent `tool_use` blocks whose input carries
`subagent_type == "general-purpose"`, each joined to its own tool_result.

Usage:
    python3 bin/count_guard_denials.py                    # default project roots
    python3 bin/count_guard_denials.py --root -Users-you-test-1 ...

Note on scope: the ideation-stage waiter/placeholder deny (WAITER_REDIRECT) does NOT show up
here. Those spawns are issued by a headless L1 subagent, whose records live in the sidechain
subdirectories next to each transcript, not in the top-level .jsonl this script reads.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os

DEFAULT_ROOTS = [
    "-Users-you-auto-research",
    "-Users-you-test-1",
    "-Users-you-test-2",
    "-Users-you-test-3",
    "-Users-you-test-6",
]
BLOCKED = "BLOCKED"
TARGET = "general-purpose"


def scan(base: str, roots: list[str]):
    attempts: dict[str, set[str]] = collections.defaultdict(set)   # session -> tool_use ids
    results: dict[str, str] = {}
    sessions = 0
    for r in roots:
        for f in sorted(glob.glob(os.path.join(base, r, "*.jsonl"))):
            sessions += 1
            sid = os.path.basename(f)[:-6]
            for line in open(f, encoding="utf-8", errors="replace"):
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                content = (rec.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use" and c.get("name") in ("Task", "Agent"):
                        if (c.get("input") or {}).get("subagent_type") == TARGET:
                            attempts[sid].add(c["id"])
                    elif c.get("type") == "tool_result" and c.get("tool_use_id"):
                        results[c["tool_use_id"]] = json.dumps(c.get("content"), ensure_ascii=False)
    return attempts, results, sessions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--root", nargs="+", default=DEFAULT_ROOTS)
    a = ap.parse_args()

    attempts, results, sessions = scan(a.base, a.root)
    all_ids = {i for s in attempts.values() for i in s}
    denied = {i for i in all_ids if BLOCKED in results.get(i, "")}
    survived = sorted(all_ids - denied)
    per = sorted((len(v) for v in attempts.values()), reverse=True)

    print(f"scanned {sessions} session transcripts across {len(a.root)} project roots\n")
    print(f"  '{TARGET}' spawn attempts   {len(all_ids)}")
    print(f"  denied by the guard         {len(denied)}")
    print(f"  got through                 {len(survived)}"
          + ("   <-- INVESTIGATE" if survived else ""))
    for i in survived[:5]:
        print(f"      {i}: {results.get(i, '<no result recorded>')[:160]}")
    if not per:
        return 0
    print(f"\n  sessions that attempted it  {len(per)} of {sessions}")
    print(f"  attempts per such session   {per}")
    print(f"  mean {sum(per) / len(per):.1f} · median {sorted(per)[len(per) // 2]} · max {max(per)}")
    again = sum(1 for x in per if x > 1)
    print(f"\n  tried AGAIN after being denied: {again} of {len(per)} sessions")
    print("  -> being refused once does not stop it; the guard has to keep firing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
