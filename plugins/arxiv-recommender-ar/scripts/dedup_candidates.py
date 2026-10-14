#!/usr/bin/env python3
"""Deduplicate a candidates pool by arxiv_id — a safety net between fetch and
mechanical ranking.

Runs AFTER Phase 1 fetch (+ any pinned-paper injection) and BEFORE Phase 2
prefetch, guaranteeing the pool fed to ranking has no duplicate records —
independent of how the pool was produced (OAI ingest, off-box fallback, pinned
injection, manual --candidates-from). This deliberately does NOT touch the fetch
stage, so changing the fetch source or the researcher profile can't change its
behavior.

Why it matters: prefetch.py builds `cand_axids` as a positional list parallel to
the candidate rows, so a duplicate arxiv_id would be embedded twice and could
double-count in RRF fusion. Dedup keeps the FIRST occurrence (preserving order),
unions `categories`/`links` across duplicates, and OR-s the `pinned` flag so no
signal is lost. Idempotent: re-running on a clean pool removes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def dedup_candidates(candidates: list[dict]) -> tuple[list[dict], int]:
    """Return (deduped, n_removed). Dedup by arxiv_id, keeping the first record
    and merging list-valued signals from later duplicates. Records with a
    missing/empty arxiv_id are passed through untouched (never collapsed)."""
    seen: dict[str, dict] = {}
    out: list[dict] = []
    removed = 0
    for c in candidates:
        aid = c.get("arxiv_id")
        if not aid:
            out.append(c)
            continue
        if aid not in seen:
            seen[aid] = c
            out.append(c)
            continue
        # Duplicate: merge into the kept record without losing information.
        removed += 1
        kept = seen[aid]
        kept["categories"] = list(dict.fromkeys(
            [*(kept.get("categories") or []), *(c.get("categories") or [])]))
        kept["links"] = list(dict.fromkeys(
            [*(kept.get("links") or []), *(c.get("links") or [])]))
        if c.get("pinned"):
            kept["pinned"] = True
    return out, removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", type=Path, required=True,
                    help="Path to week-<W>-candidates.json (rewritten in place).")
    args = ap.parse_args()

    if not args.candidates.exists():
        print(f"[dedup_candidates] not found: {args.candidates}", file=sys.stderr)
        return 1
    data: dict[str, Any] = json.loads(args.candidates.read_text(encoding="utf-8"))
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        print(f"[dedup_candidates] {args.candidates}: no 'candidates' list",
              file=sys.stderr)
        return 1

    deduped, removed = dedup_candidates(candidates)
    if removed:
        data["candidates"] = deduped
        args.candidates.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"[dedup_candidates] removed {removed} duplicate record(s); "
              f"{len(deduped)} unique candidates -> {args.candidates}",
              file=sys.stderr)
    else:
        print(f"[dedup_candidates] no duplicates ({len(candidates)} candidates)",
              file=sys.stderr)
    print(str(args.candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
