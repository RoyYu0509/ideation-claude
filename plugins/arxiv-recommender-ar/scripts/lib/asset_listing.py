#!/usr/bin/env python3
"""Real file-listing fetcher + substantiveness evaluator for depended assets.

The 2026-07 postmortem canon: a promised benchmark repo was a 1KB two-file stub
and cost ~25h downstream because ideation trusted the paper's "we release..."
sentence. This module replaces landing-page impressions with an ACTUAL machine
listing: for a GitHub repo the recursive git tree (path + size per blob); for
HuggingFace / Zenodo the file manifest; for other allowlisted hosts an HTTP
HEAD. The evaluator then decides live_verified / stub_or_empty / missing
MECHANICALLY: every `needed_paths` glob must match and non-doc code bytes must
clear a floor — a stub cannot pass regardless of prose.

Library (imported by verify_bundle.py for V0 re-fetch):
    listing = fetch_listing(url)
    ev = evaluate(listing, needed_paths)

CLI (wrapped by bin/asset_listing.sh):
    asset_listing.py <url> --out out.json [--needed-paths "a/*.py,data/*.h5"]
Writes {"listing": ..., "evaluation": ...} to --out and prints the evaluation
status. Exit 0 = live_verified, 1 = stub_or_empty/missing, 2 = usage/host error.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ALLOWLIST = (
    "github.com", "api.github.com", "raw.githubusercontent.com",
    "arxiv.org", "huggingface.co", "zenodo.org", "osf.io", "gitlab.com",
)
# Non-doc code-bytes floor: below this a repo is a stub no matter what it says.
MIN_CODE_BYTES = 4096
_DOC_RE = re.compile(r"(?i)(^|/)(readme|license|licence|citation|notice|\.git)|\.md$|\.rst$|\.txt$")
_TIMEOUT = 30


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _gh_headers() -> dict:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    h = {"Accept": "application/vnd.github+json", "User-Agent": "arxiv-recommender-asset-listing"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _listing(url: str, host: str, **kw) -> dict:
    base = {
        "url": url, "host": host, "ok": False, "files": [], "total_files": 0,
        "code_bytes": 0, "truncated": False, "error": None, "fetched_utc": _utc(),
    }
    base.update(kw)
    return base


def _finish(lst: dict) -> dict:
    lst["total_files"] = len(lst["files"])
    lst["code_bytes"] = sum(
        (f.get("size") or 0) for f in lst["files"] if not _DOC_RE.search(f["path"])
    )
    return lst


def _fetch_github(url: str) -> dict:
    m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", url)
    if not m:
        return _listing(url, "github.com", error="cannot parse owner/repo")
    owner, repo = m.group(1), m.group(2).removesuffix(".git")
    api = f"https://api.github.com/repos/{owner}/{repo}"
    r = requests.get(api, headers=_gh_headers(), timeout=_TIMEOUT)
    if r.status_code == 404:
        return _listing(url, "github.com", error="404 repo not found")
    r.raise_for_status()
    meta = r.json()
    branch = meta.get("default_branch") or "main"
    t = requests.get(f"{api}/git/trees/{branch}?recursive=1",
                     headers=_gh_headers(), timeout=_TIMEOUT)
    if t.status_code == 404:
        # empty repo (no commits) — a stub by definition
        return _listing(url, "github.com", ok=True, error=None,
                        default_branch=branch, files=[])
    t.raise_for_status()
    tree = t.json()
    files = [{"path": e["path"], "size": e.get("size", 0)}
             for e in tree.get("tree", []) if e.get("type") == "blob"]
    return _finish(_listing(url, "github.com", ok=True, files=files,
                            truncated=bool(tree.get("truncated")), default_branch=branch))


def _fetch_huggingface(url: str) -> dict:
    m = re.search(r"huggingface\.co/(datasets/)?([^/\s]+/[^/\s#?]+)", url)
    if not m:
        return _listing(url, "huggingface.co", error="cannot parse repo id")
    kind = "datasets" if m.group(1) else "models"
    rid = m.group(2)
    # `full=true&blobs=true` is REQUIRED: the bare endpoint omits `size` for every
    # LFS-tracked file, so a real multi-GB dataset comes back as 0 bytes and the
    # evaluator below calls it stub_or_empty. That false negative cost a candidate
    # an integrity_violation kill in 2026-W35 (2608.22504-c0).
    _HF_PARAMS = {"full": "true", "blobs": "true"}
    r = requests.get(f"https://huggingface.co/api/{kind}/{rid}", params=_HF_PARAMS, timeout=_TIMEOUT)
    if r.status_code == 404 and kind == "models":  # a dataset linked without /datasets/
        kind = "datasets"
        r = requests.get(f"https://huggingface.co/api/{kind}/{rid}", params=_HF_PARAMS, timeout=_TIMEOUT)
    if r.status_code == 404:
        return _listing(url, "huggingface.co", error="404 not found")
    r.raise_for_status()
    files = [{"path": s.get("rfilename", ""),
               "size": s.get("size") or (s.get("lfs") or {}).get("size") or 0}
             for s in r.json().get("siblings", [])]
    return _finish(_listing(url, "huggingface.co", ok=True, files=files))


def _fetch_zenodo(url: str) -> dict:
    m = re.search(r"zenodo\.org/(?:records?|record)/(\d+)", url)
    if not m:
        return _listing(url, "zenodo.org", error="cannot parse record id")
    r = requests.get(f"https://zenodo.org/api/records/{m.group(1)}", timeout=_TIMEOUT)
    if r.status_code == 404:
        return _listing(url, "zenodo.org", error="404 not found")
    r.raise_for_status()
    files = [{"path": f.get("key", ""), "size": f.get("size") or 0}
             for f in r.json().get("files", [])]
    return _finish(_listing(url, "zenodo.org", ok=True, files=files))


def _fetch_head(url: str, host: str) -> dict:
    r = requests.head(url, timeout=_TIMEOUT, allow_redirects=True)
    ok = r.status_code < 400
    size = int(r.headers.get("Content-Length") or 0)
    files = [{"path": url.rsplit("/", 1)[-1] or url, "size": size}] if ok else []
    return _finish(_listing(url, host, ok=ok,
                            error=None if ok else f"HTTP {r.status_code}", files=files))


def fetch_listing(url: str) -> dict:
    """Fetch the real file listing for an allowlisted asset URL. Never raises
    on HTTP-level absence (that is data: missing); raises only on network
    failure so callers can distinguish 'asset dead' from 'network down'."""
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
    if not any(host == a or host.endswith("." + a) for a in ALLOWLIST):
        return _listing(url, host, error=f"host not allowlisted: {host}")
    if "github.com" in host:
        return _fetch_github(url)
    if "huggingface.co" in host:
        return _fetch_huggingface(url)
    if "zenodo.org" in host:
        return _fetch_zenodo(url)
    return _fetch_head(url, host)


def evaluate(listing: dict, needed_paths: list[str],
             min_code_bytes: int = MIN_CODE_BYTES) -> dict:
    """Mechanical substantiveness verdict. live_verified requires: fetch ok,
    EVERY needed_paths glob matched by at least one listed file, and non-doc
    code bytes >= floor. No prose can override this."""
    if not listing.get("ok"):
        return {"status": "missing", "matched": {}, "missing_globs": list(needed_paths),
                "code_bytes": 0, "reason": listing.get("error") or "fetch failed"}
    paths = [f["path"] for f in listing.get("files", [])]
    matched, missing = {}, []
    for g in needed_paths:
        hits = [p for p in paths if fnmatch.fnmatch(p, g) or fnmatch.fnmatch(p, g.strip("/"))]
        if hits:
            matched[g] = hits[:20]
        else:
            missing.append(g)
    code_bytes = listing.get("code_bytes", 0)
    if missing or code_bytes < min_code_bytes:
        reason = (f"unmatched needed_paths: {missing}" if missing
                  else f"non-doc code bytes {code_bytes} < floor {min_code_bytes}")
        return {"status": "stub_or_empty", "matched": matched, "missing_globs": missing,
                "code_bytes": code_bytes, "reason": reason}
    return {"status": "live_verified", "matched": matched, "missing_globs": [],
            "code_bytes": code_bytes, "reason": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--needed-paths", default="",
                    help="comma-separated globs the listing must contain")
    ap.add_argument("--min-code-bytes", type=int, default=MIN_CODE_BYTES)
    args = ap.parse_args()

    needed = [g.strip() for g in args.needed_paths.split(",") if g.strip()]
    try:
        listing = fetch_listing(args.url)
    except requests.RequestException as e:
        print(f"[asset_listing] network failure (NOT an asset verdict): {e}", file=sys.stderr)
        return 2
    ev = evaluate(listing, needed, args.min_code_bytes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"listing": listing, "evaluation": ev}, f, indent=2, ensure_ascii=False)
    print(ev["status"])
    return 0 if ev["status"] == "live_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
