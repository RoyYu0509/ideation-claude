#!/usr/bin/env python3
"""Validating writer for a single ideation JSON — the WRITE-side schema gate.

The arxiv-generate skill drafts the ideation dict, writes it to a scratch file,
then calls this CLI instead of writing the final JSON by hand. That kills the
two failure modes a hand-written file has:

  (a) broken JSON — unescaped quotes in Chinese strings, trailing commas, etc.
      Here the draft is parsed with json.load (loud error) and re-serialized
      with json.dump (always valid, properly escaped).
  (b) schema drift — a missing `paper_summary`, an old `title`/`falsifier`
      field name. normalize_ideation maps legacy names; validate_ideation then
      fails LOUDLY (exit 1) on anything still missing, so the agent gets an
      actionable message and can fix-and-retry instead of silently leaving a
      file the renderer would have to drop.

It also writes to the CANONICAL name `<arxiv_id>.json` in the output dir,
stripping any legacy `-ideation` suffix a caller passed — the renderer and the
Workflow resume logic both expect the unsuffixed name. A `-r<N>` ROUND suffix
(verified-kill regeneration rounds: `<id>-r2.json` / `evidence-<id>-r2.json`)
is PRESERVED: normalizing it away made every round-2+ write silently clobber
the round-1 canonical file (2026-07-12 shakedown F1, 4/4 reproduction).

Usage:
  ideate_save.py --in DRAFT.json --out OUTPUT_PATH [--week W] [--arxiv-id ID] [--title T]
                 [--kind ideation|evidence]   # evidence: validate the sidecar, write evidence-<id>.json

  --in   scratch file holding the drafted ideation dict (JSON)
  --out  the output_path from the skill's input JSON (absolute). Only its
         DIRECTORY is used; the basename is normalized to <arxiv_id>.json.
  --week / --arxiv-id / --title  optional defaults filled into the dict if it
         omits them (title = the PAPER title from the skill's input JSON).

Exit 0 on success (prints the written path); exit 1 on bad JSON or schema
failure (prints the reason to stderr); exit 2 on usage/IO error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import ideate_io  # noqa: E402


def round_suffix(out_name: str) -> str:
    """The '-r<N>' regeneration-round suffix of an --out basename, or ''.
    Preserved through basename normalization — stripping it clobbers the
    round-1 canonical file (shakedown F1)."""
    import re
    m = re.search(r"-r(\d+)\.json$", out_name)
    return f"-r{m.group(1)}" if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", type=Path, required=True,
                    help="scratch file with the drafted ideation dict (JSON)")
    ap.add_argument("--out", type=Path, required=True,
                    help="output_path from the skill input; its dir is used, "
                         "basename normalized to <arxiv_id>.json")
    ap.add_argument("--week", type=str, default=None)
    ap.add_argument("--arxiv-id", dest="arxiv_id", type=str, default=None)
    ap.add_argument("--title", type=str, default=None,
                    help="paper title from the skill input; filled in if the draft omits it")
    ap.add_argument("--kind", choices=("ideation", "evidence"), default="ideation",
                    help="which schema gate to apply; 'evidence' validates the sidecar "
                         "and writes evidence-<arxiv_id>.json")
    args = ap.parse_args()

    if not args.infile.exists():
        print(f"[ideate_save] draft file not found: {args.infile}", file=sys.stderr)
        return 2

    try:
        with open(args.infile, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ideate_save] FAIL — draft is not valid JSON: {e}\n"
              f"  Fix the JSON (most often an unescaped ASCII \" inside a "
              f"Chinese string) and rerun.", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(f"[ideate_save] FAIL — draft top level is "
              f"{type(data).__name__}, expected an object.", file=sys.stderr)
        return 1

    if args.week:
        data.setdefault("week", args.week)
    if args.arxiv_id:
        data.setdefault("arxiv_id", args.arxiv_id)

    if args.kind == "evidence":
        try:
            ideate_io.validate_evidence(data, context=data.get("arxiv_id", "?"))
        except ideate_io.IdeationSchemaError as e:
            print(f"[ideate_save] FAIL — evidence schema: {e}\n"
                  f"  Fix the field named above (see the arxiv-generate "
                  f"references/evidence-schema.md) and rerun. Required top-level: "
                  f"{ideate_io.REQUIRED_EVIDENCE_TOP}.", file=sys.stderr)
            return 1
        arxiv_id = data["arxiv_id"]
        out_path = args.out.parent / f"evidence-{arxiv_id}{round_suffix(args.out.name)}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(str(out_path))
        return 0

    data = ideate_io.normalize_ideation(data)
    if args.title:
        data.setdefault("title", args.title)

    try:
        ideate_io.validate_ideation(data, context=data.get("arxiv_id", "?"), strict_new=True)
    except ideate_io.IdeationSchemaError as e:
        print(f"[ideate_save] FAIL — schema: {e}\n"
              f"  Add/rename the field named above (see the arxiv-generate Step 5a "
              f"schema) and rerun. Required top-level: {ideate_io.REQUIRED_TOP}; "
              f"required per idea: {ideate_io.REQUIRED_IDEA} + "
              f"{ideate_io.REQUIRED_IDEA_GROUNDING} + one of "
              f"{ideate_io.EITHER_IDEA}.", file=sys.stderr)
        return 1

    arxiv_id = data["arxiv_id"]
    out_path = args.out.parent / f"{arxiv_id}{round_suffix(args.out.name)}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
