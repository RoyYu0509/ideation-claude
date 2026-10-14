#!/usr/bin/env python3
"""Fetch arxiv metadata for user-pinned paper IDs.

Usage: python fetch_pinned_papers.py --arxiv-ids 2501.12345 2502.67890
Output: JSON array to stdout, same schema as candidates.json candidates.
Invalid or missing IDs are silently skipped (arxiv API omits them).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

_ATOM = "http://www.w3.org/2005/Atom"
_ARXIV = "http://arxiv.org/schemas/atom"


def _text(el: ET.Element | None) -> str:
    return " ".join((el.text or "").split()) if el is not None else ""


def fetch_arxiv_metadata(arxiv_ids: list[str]) -> list[dict]:
    id_list = ",".join(arxiv_ids)
    url = (
        f"http://export.arxiv.org/api/query"
        f"?id_list={id_list}&max_results={len(arxiv_ids)}"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            xml_data = resp.read()
    except urllib.error.URLError as exc:
        print(f"[fetch_pinned] arxiv API request failed: {exc}", file=sys.stderr)
        return []

    root = ET.fromstring(xml_data)
    papers = []

    for entry in root.findall(f"{{{_ATOM}}}entry"):
        id_el = entry.find(f"{{{_ATOM}}}id")
        if id_el is None:
            continue
        raw_id = id_el.text or ""
        if "/abs/" not in raw_id:
            continue
        arxiv_id = raw_id.split("/abs/")[-1].split("v")[0].strip()

        title = _text(entry.find(f"{{{_ATOM}}}title"))
        abstract = _text(entry.find(f"{{{_ATOM}}}summary"))
        submitted_el = entry.find(f"{{{_ATOM}}}published")
        submitted = (submitted_el.text or "").strip() if submitted_el is not None else None

        authors = [
            _text(a.find(f"{{{_ATOM}}}name"))
            for a in entry.findall(f"{{{_ATOM}}}author")
        ]

        categories: list[str] = []
        primary_category = ""
        for cat in entry.findall(f"{{{_ATOM}}}category"):
            term = cat.attrib.get("term", "")
            if term:
                categories.append(term)
        for cat in entry.findall(f"{{{_ARXIV}}}primary_category"):
            primary_category = cat.attrib.get("term", "")
        if not primary_category and categories:
            primary_category = categories[0]

        if not title:
            print(f"[fetch_pinned] skipping {arxiv_id}: no title (likely invalid ID)", file=sys.stderr)
            continue

        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "submitted": submitted,
            "categories": categories,
            "primary_category": primary_category,
            "url": f"http://arxiv.org/abs/{arxiv_id}v1",
        })

    return papers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arxiv-ids", nargs="+", required=True, help="One or more arxiv IDs")
    args = ap.parse_args()

    ids = [i.strip() for i in args.arxiv_ids if i.strip()]
    if not ids:
        print("[]")
        return 0

    papers = fetch_arxiv_metadata(ids)
    print(json.dumps(papers, indent=2))
    print(f"[fetch_pinned] fetched {len(papers)}/{len(ids)} paper(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
