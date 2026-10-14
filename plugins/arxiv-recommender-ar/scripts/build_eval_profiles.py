#!/usr/bin/env python3
"""Build researcher profiles for multi-researcher evaluation.

For each S2 author ID:
  1. Creates data/users/<author_id>/profile/ directory
  2. Fetches paper list directly from Semantic Scholar
  3. Writes papers.json to the author's profile directory
  4. Prints next steps (arxiv-profile skill generates profile.md + profile.json)

Usage:
  bash bin/run_py.sh scripts/build_eval_profiles.py \\
    --authors 102316879,<id2>,<id3> \\
    [--force] [--max-papers 200]

After running this script, for each new author run the arxiv-profile skill
to generate profile.md + profile.json from papers.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import config, s2_client  # noqa: E402


def _fetch_and_normalize(author_id: str, max_papers: int) -> list[dict]:
    fields = (
        "paperId", "title", "abstract", "year", "venue",
        "externalIds", "s2FieldsOfStudy", "references.paperId",
    )
    raw = s2_client.author_papers(author_id, fields=fields, max_papers=max_papers)
    papers = []
    for p in raw:
        papers.append({
            "paper_id": p.get("paperId", ""),
            "arxiv_id": (p.get("externalIds") or {}).get("ArXiv"),
            "title": p.get("title", ""),
            "abstract": p.get("abstract"),
            "year": p.get("year"),
            "venue": p.get("venue", ""),
            "categories": [
                f.get("category", "")
                for f in (p.get("s2FieldsOfStudy") or [])
                if f.get("category")
            ],
            "reference_ids": [
                r.get("paperId", "")
                for r in (p.get("references") or [])
                if r.get("paperId")
            ],
        })
    return papers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--authors", required=True,
                    help="Comma-separated S2 author IDs")
    ap.add_argument("--force", action="store_true",
                    help="Re-fetch even if papers.json already exists")
    ap.add_argument("--max-papers", type=int, default=None,
                    help="default: config eval.profile_max_papers")
    args = ap.parse_args()

    cfg = config.load_config()   # validates config + applies io.* to s2_client
    max_papers = args.max_papers if args.max_papers is not None else cfg.eval_block["profile_max_papers"]
    root = config.data_root()  # runtime-folder principle (2026-07-05): eval artifacts live under the data root, never the plugin dir
    author_ids = [a.strip() for a in args.authors.split(",") if a.strip()]
    print(f"Building profiles for {len(author_ids)} author(s)...")

    succeeded = []
    for author_id in author_ids:
        profile_dir = root / "data" / "users" / author_id / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        papers_out = profile_dir / "papers.json"

        if papers_out.exists() and not args.force:
            print(f"\n[{author_id}] papers.json exists, skipping (--force to re-fetch)")
            succeeded.append(author_id)
            continue

        print(f"\n[{author_id}] Fetching from Semantic Scholar...")
        try:
            papers = _fetch_and_normalize(author_id, max_papers)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        out_data = {"s2_author_id": author_id, "papers": papers}
        papers_out.write_text(json.dumps(out_data, indent=2))
        print(f"  → {len(papers)} papers → {papers_out}")
        succeeded.append(author_id)

    if not succeeded:
        print("\nNo profiles built successfully.")
        return 1

    print("\n" + "=" * 60)
    print("NEXT STEPS: generate profile.md + profile.json for each author")
    print("by invoking the arxiv-profile skill (Claude agent).")
    print("The skill reads papers.json and writes both output files.")
    print()
    for author_id in succeeded:
        profile_dir = root / "data" / "users" / author_id / "profile"
        if (profile_dir / "papers.json").exists():
            print(f"  Author {author_id}:")
            print(f"    papers.json: data/users/{author_id}/profile/papers.json")
            if not (profile_dir / "profile.json").exists():
                print(f"    ⚠ profile.json missing — run arxiv-profile skill")
            else:
                print(f"    ✓ profile.json exists")
    print()
    print("To evaluate after profiles are ready:")
    for author_id in succeeded:
        print(f"  bash bin/run_py.sh scripts/eval_prefetch_quality.py compare \\")
        print(f"    --candidates data/eval_archive/week-<W>-candidates.json \\")
        print(f"    --author {author_id} --systems S0,S4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
