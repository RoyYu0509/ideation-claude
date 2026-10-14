#!/usr/bin/env python3
"""Write the owner's Phase 0b decisions into data/profile/paper_candidates.json.

The owner says which Google Scholar rows are the researcher's own papers. In an interactive
/arxiv-scout-beta session the main agent edits the file; under /auto-research the L0 controller relays the
owner's answer to its paper-list card through THIS script, so the decisions are written mechanically — never
invented by an agent.

  bin/run_py.sh scripts/set_paper_decisions.py [--candidates P] [--mark "<key or title words>=not"]... [--rest self]
  bin/run_py.sh scripts/set_paper_decisions.py [--candidates P] --check

--mark   one row, found by its exact key or else by words its title contains (case-insensitive), with its
         decision (self / peripheral / not). A mark that matches no row or several rows is an error that lists
         them, and then NOTHING is written.
--rest   the decision for every row still undecided after the marks (the owner's "all the others are mine").
--check  change nothing; exit 0 iff every row has a decision.
Exit: 0 written / every row decided · 1 rows still undecided · 2 a bad or ambiguous mark (nothing written).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_profile_papers import _DECISIONS, _candidates_md  # noqa: E402
from lib import config  # noqa: E402


def _match(rows: list[dict], token: str) -> list[dict]:
    t = token.strip().lower()
    exact = [r for r in rows if str(r.get("key") or "").lower() == t]
    if exact:
        return exact
    return [r for r in rows if t and t in f"{r.get('title') or ''} {r.get('scholar_title') or ''}".lower()]


def apply(doc: dict, marks: list[str], rest: str | None) -> list[str]:
    """Apply the marks, then `rest`, to doc in place. Returns the errors — non-empty ⇒ write nothing."""
    rows = doc.get("papers") or []
    errors: list[str] = []
    for m in marks:
        token, _, dec = m.rpartition("=")
        dec = dec.strip().lower()
        if dec not in _DECISIONS or not token.strip():
            errors.append(f"bad mark {m!r} — want '<key or title words>=self|peripheral|not'")
            continue
        hits = _match(rows, token)
        if len(hits) != 1:
            errors.append(f"{token.strip()!r} matches {len(hits)} rows"
                          + (": " + "; ".join(f"{r.get('key')} {(r.get('title') or '')[:60]}" for r in hits[:5])
                             if hits else ""))
            continue
        hits[0]["decision"] = dec
    if not errors and rest:
        for r in rows:
            if r.get("decision") not in _DECISIONS:
                r["decision"] = rest
    return errors


def undecided(doc: dict) -> list[dict]:
    return [r for r in doc.get("papers") or [] if r.get("decision") not in _DECISIONS]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--candidates", type=Path, default=None, help="default: data/profile/paper_candidates.json")
    ap.add_argument("--mark", action="append", default=[],
                    help='"<key or title words>=self|peripheral|not" (repeatable)')
    ap.add_argument("--rest", choices=_DECISIONS, default=None, help="decision for every row still undecided")
    ap.add_argument("--check", action="store_true", help="change nothing; exit 0 iff every row is decided")
    args = ap.parse_args()

    path = args.candidates or (config.profile_dir() / "paper_candidates.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not args.check:
        errors = apply(doc, args.mark, args.rest)
        if errors:
            for e in errors:
                print(f"[set_paper_decisions] ERROR: {e}", file=sys.stderr)
            print(f"[set_paper_decisions] nothing written to {path}", file=sys.stderr)
            return 2
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        path.with_suffix(".md").write_text(_candidates_md(doc), encoding="utf-8")
    left = undecided(doc)
    counts = {d: sum(1 for r in doc.get("papers") or [] if r.get("decision") == d) for d in _DECISIONS}
    print(f"[set_paper_decisions] {path}: {counts} · undecided {len(left)}", file=sys.stderr)
    for r in left[:10]:
        print(f"    undecided: {r.get('key')}  {(r.get('title') or '')[:80]}", file=sys.stderr)
    return 1 if left else 0


if __name__ == "__main__":
    raise SystemExit(main())
