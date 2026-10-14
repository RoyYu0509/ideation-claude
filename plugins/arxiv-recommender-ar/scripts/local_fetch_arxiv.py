#!/usr/bin/env python3
"""Standalone, ZERO-DEPENDENCY arXiv fetcher meant to run on the user's LOCAL
machine (a residential IP), driven over SSH by build_shared_cache.py's off-box
fetch path (config io.arxiv_fetch_via_local) on the VPS.

Why this exists
---------------
arXiv's edge layer (Fastly) rate-limits/blocks the DigitalOcean datacenter IP
the VPS runs on — even a single `max_results=1` request gets `429 Rate
exceeded.`. The rest of the pipeline (rerank/ideate/refine) never touches
arXiv, so the only thing that must run off a clean IP is this fetch. This script
runs on the laptop, writes the candidates JSON, and the VPS scp's it back.

It deliberately uses ONLY the Python standard library (urllib + xml.etree) so
the local machine needs nothing but `python3` — no pip install, no venv, no copy
of this repo. The emitted candidate schema is byte-for-byte the same as
`scripts/lib/arxiv_client.fetch_recent` so `build_shared_cache.py
--candidates-from` can consume it unchanged.

All pipeline-meaningful knobs (categories, window, max_results, page_size,
delay) are passed in by the VPS from config.yaml (the single source of truth).
Only `--retries` is a local robustness default, since this script cannot read
config.yaml.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "arxiv-recommender-localfetch/0.2 (https://github.com/; mailto:" + os.environ.get("AR_CONTACT_EMAIL", "set-AR_CONTACT_EMAIL@example.com") + ")"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def build_query(categories: list[str], start_utc: datetime, end_utc: datetime) -> str:
    """Mirror scripts/lib/arxiv_client._build_query exactly."""
    cat_q = " OR ".join(f"cat:{c}" for c in categories)
    if not cat_q:
        raise ValueError("at least one category required")
    fmt = "%Y%m%d%H%M"
    return f"({cat_q}) AND submittedDate:[{start_utc.strftime(fmt)} TO {end_utc.strftime(fmt)}]"


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    return node.text.strip()


def parse_feed(xml_bytes: bytes) -> tuple[list[dict], int | None]:
    """Parse one Atom page into (candidates, total_results).

    `total_results` is arXiv's opensearch:totalResults for the whole query
    (None if absent). Each candidate matches fetch_recent's schema.
    """
    root = ET.fromstring(xml_bytes)
    total_node = root.find("opensearch:totalResults", NS)
    total = int(total_node.text) if total_node is not None and total_node.text else None

    out: list[dict] = []
    for entry in root.findall("atom:entry", NS):
        entry_id = _text(entry.find("atom:id", NS)) or ""
        # http://arxiv.org/abs/2406.12345v2  ->  2406.12345  (mirrors
        # arxiv.Result.get_short_id().split("v")[0]); old-style ids like
        # cond-mat/0703123v1 -> cond-mat/0703123.
        id_part = entry_id.rsplit("/abs/", 1)[-1]
        arxiv_id = id_part.split("v")[0]

        published = _text(entry.find("atom:published", NS))
        submitted = None
        if published:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            submitted = dt.astimezone(timezone.utc).isoformat()

        primary = entry.find("arxiv:primary_category", NS)
        out.append(
            {
                "arxiv_id": arxiv_id,
                "title": (_text(entry.find("atom:title", NS)) or ""),
                "abstract": (_text(entry.find("atom:summary", NS)) or ""),
                "authors": [
                    _text(a.find("atom:name", NS)) or ""
                    for a in entry.findall("atom:author", NS)
                ],
                "submitted": submitted,
                "categories": [
                    c.get("term") for c in entry.findall("atom:category", NS) if c.get("term")
                ],
                "primary_category": primary.get("term") if primary is not None else None,
                "url": entry_id,
                "comment": _text(entry.find("arxiv:comment", NS)),
                "links": [
                    l.get("href") for l in entry.findall("atom:link", NS) if l.get("href")
                ],
                "doi": _text(entry.find("arxiv:doi", NS)),
            }
        )
    return out, total


def _get_page(query: str, start: int, page_size: int, retries: int, timeout: int) -> bytes:
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": start,
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    url = f"{API_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last_err = e
            code = getattr(e, "code", None)
            # 429 here would mean even the local IP is throttled — surface it.
            wait = min(60, 5 * (attempt + 1))
            print(
                f"[local_fetch] HTTP {code} on start={start} "
                f"(attempt {attempt + 1}/{retries + 1}); sleeping {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
        except Exception as e:  # URLError / timeout / transient
            last_err = e
            wait = min(60, 5 * (attempt + 1))
            print(
                f"[local_fetch] {type(e).__name__} on start={start} "
                f"(attempt {attempt + 1}/{retries + 1}); sleeping {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise RuntimeError(f"arXiv page start={start} failed after {retries + 1} attempts: {last_err}")


def fetch(
    categories: list[str],
    window_days: int,
    max_results: int,
    end_utc: datetime,
    page_size: int,
    delay_seconds: float,
    retries: int,
    timeout: int,
) -> list[dict]:
    start_utc = end_utc - timedelta(days=window_days)
    query = build_query(categories, start_utc, end_utc)
    print(f"[local_fetch] query: {query}", file=sys.stderr)

    collected: list[dict] = []
    total: int | None = None
    start = 0
    while len(collected) < max_results:
        xml_bytes = _get_page(query, start, page_size, retries, timeout)
        entries, page_total = parse_feed(xml_bytes)
        if total is None:
            total = page_total
            print(f"[local_fetch] totalResults={total}", file=sys.stderr)
        if not entries:
            break
        collected.extend(entries)
        print(
            f"[local_fetch] start={start} got {len(entries)} "
            f"(collected {len(collected)})",
            file=sys.stderr,
        )
        start += len(entries)
        if total is not None and start >= total:
            break
        if len(collected) >= max_results:
            break
        time.sleep(delay_seconds)

    return collected[:max_results]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--categories", required=True,
                    help="Comma-separated arXiv categories, e.g. 'cs.NE,stat.ML'.")
    ap.add_argument("--window-days", type=int, required=True)
    ap.add_argument("--max-results", type=int, required=True)
    ap.add_argument("--end-utc", required=True,
                    help="ISO-8601 UTC end of the submission window.")
    ap.add_argument("--page-size", type=int, required=True)
    ap.add_argument("--delay-seconds", type=float, required=True)
    ap.add_argument("--retries", type=int, default=4,
                    help="Per-page HTTP retry attempts (local robustness knob).")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--out", required=True, help="Output JSON path.")
    args = ap.parse_args()

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    if not categories:
        print("[local_fetch] no categories given", file=sys.stderr)
        return 2
    end_utc = datetime.fromisoformat(args.end_utc.replace("Z", "+00:00"))

    candidates = fetch(
        categories=categories,
        window_days=args.window_days,
        max_results=args.max_results,
        end_utc=end_utc,
        page_size=args.page_size,
        delay_seconds=args.delay_seconds,
        retries=args.retries,
        timeout=args.timeout,
    )

    payload = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "end_utc": end_utc.isoformat(),
        "window_days": args.window_days,
        "categories": categories,
        "candidates": candidates,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[local_fetch] wrote {len(candidates)} candidates -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
