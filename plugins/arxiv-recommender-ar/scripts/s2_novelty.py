#!/usr/bin/env python3
"""Mechanical scholarly search for the ideate/refine novelty steps.

Replaces WebSearch as the PRIMARY prior-art modality: a Semantic Scholar query
costs zero LLM tokens and returns dense scholarly hits (title/year/venue/
abstract) instead of SERP noise. Two modes:

  --mode search  --query "closed-form coordinate lift operator learning" [--limit 8]
      Relevance search over S2's corpus (the /paper/search endpoint).
  --mode related --arxiv-id 2606.29440 [--limit 8]
      S2's related-paper recommendations for the parent paper — the citation-
      graph neighborhood a keyword search misses. [] when S2 doesn't know the
      paper yet (very new); callers fall back to --mode search.

Output: compact JSON array to stdout (abstracts truncated) — small enough to
paste into an agent context whole. Warnings go to stderr.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config, s2_client  # noqa: E402

_ABSTRACT_CHARS = 400
_FIELDS = ("paperId", "title", "abstract", "year", "venue", "externalIds")


def _compact(p: dict) -> dict:
    ext = p.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv")
    abstract = (p.get("abstract") or "").strip()
    if len(abstract) > _ABSTRACT_CHARS:
        abstract = abstract[:_ABSTRACT_CHARS].rsplit(" ", 1)[0] + " …"
    return {
        "title": p.get("title") or "",
        "year": p.get("year"),
        "venue": p.get("venue") or None,
        "arxiv_id": arxiv_id,
        "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
               else f"https://www.semanticscholar.org/paper/{p.get('paperId')}",
        "abstract": abstract or None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("search", "related"), required=True)
    ap.add_argument("--query", help="search mode: the relevance query")
    ap.add_argument("--arxiv-id", help="related mode: parent paper arXiv id")
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()

    config.load_config()  # validates config + applies io.* knobs to s2_client

    if args.mode == "search":
        if not args.query:
            ap.error("--mode search requires --query")
        hits = s2_client.search_by_title(args.query, fields=_FIELDS, limit=args.limit)
    else:
        if not args.arxiv_id:
            ap.error("--mode related requires --arxiv-id")
        hits = s2_client.recommendations_for_paper(
            f"ArXiv:{args.arxiv_id}", fields=_FIELDS, limit=args.limit
        )
        if not hits:
            print(
                f"[s2_novelty] no recommendations for {args.arxiv_id} "
                "(paper too new for S2?) — fall back to --mode search",
                file=sys.stderr,
            )

    print(json.dumps([_compact(p) for p in hits[: args.limit]],
                     indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
