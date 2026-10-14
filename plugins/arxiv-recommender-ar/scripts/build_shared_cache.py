#!/usr/bin/env python3
"""Centralized weekly arXiv fetch into a shared raw cache.

Walks all registered user profiles, unions their `arxiv_categories`, fetches
one batch from arXiv, writes `data/cache/week-<YYYY-Www>-candidates.json`
(same schema as `fetch_weekly.py`).

Profile discovery order:
  1. `data/users/<name>/profile/profile.json` (multi-user mode)
  2. `data/profile/profile.json` (single-user fallback)

Designed to be run from cron / launchd / Claude Code `/schedule`. Idempotent:
if the current week's cache exists and was fetched <6 days ago, exits 0
without hitting arXiv. Use `--force` to override.

Robust to arXiv HTTP 429: on rate-limit error, backs off 60s -> 180s -> 600s
before giving up. On final failure writes a `FETCH-FAILED.json` marker and
exits 1 so cron can detect the breakage.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import arxiv  # noqa: E402

from lib import arxiv_client, config  # noqa: E402
from lib import profile_papers as PP  # noqa: E402


# arXiv rate-limit windows are typically 5–15 min; use minute-scale waits.
BACKOFF_SCHEDULE_SECONDS = [300, 900, 3600]


def _week_label(when: datetime) -> str:
    iso = when.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _discover_profiles(plugin_root: Path) -> list[Path]:
    users_root = plugin_root / "data" / "users"
    multi = sorted(users_root.glob("*/profile/profile.json"))
    if multi:
        return multi
    legacy = plugin_root / "data" / "profile" / "profile.json"
    if legacy.exists():
        return [legacy]
    return []


def _union_categories(profile_paths: list[Path]) -> list[str]:
    cats: set[str] = set()
    for p in profile_paths:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        for c in data.get("arxiv_categories") or []:
            if c:
                cats.add(c)
    return sorted(cats)


def _is_fresh(cache_path: Path, max_age_days: float = 6.0) -> tuple[bool, str | None]:
    if not cache_path.exists():
        return False, None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("fetched_at_utc")
        if not ts:
            return False, None
        fetched_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return False, None
    age = datetime.now(timezone.utc) - fetched_at
    return age < timedelta(days=max_age_days), ts


def _http_status_int(e: Exception) -> int | None:
    """Extract numeric HTTP status from an arxiv or urllib exception."""
    for attr in ("status", "status_code", "code"):
        val = getattr(e, attr, None)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
    return None


def _is_retryable(e: Exception) -> bool:
    """True for transient arXiv errors worth backing off and retrying."""
    if isinstance(e, arxiv.HTTPError):
        status = _http_status_int(e)
        # Retry on 429 (rate-limit) and all 5xx (server-side transient).
        # Permanent client errors below 429 (e.g. 400 bad query) are not retryable.
        return status is None or status == 429 or status >= 500
    # UnexpectedEmptyPageError is a sporadic arXiv server glitch; always retry.
    if isinstance(e, arxiv.ArxivError):
        return True
    if isinstance(e, (urllib.error.URLError, ConnectionError, OSError, TimeoutError)):
        return True
    return False


def _fetch_with_backoff(
    categories: list[str],
    window_days: int,
    max_results: int,
    end_utc: datetime,
    max_wait_seconds: int,
) -> list[dict]:
    """Call arxiv_client.fetch_recent with outer retry/backoff."""
    total_waited = 0
    last_err: Exception | None = None
    waits = [0, *BACKOFF_SCHEDULE_SECONDS]
    for attempt, wait in enumerate(waits):
        if wait:
            if total_waited + wait > max_wait_seconds:
                raise TimeoutError(
                    f"backoff would exceed --max-wait-seconds={max_wait_seconds} "
                    f"(would wait {wait}s after {total_waited}s already)"
                )
            status_hint = _http_status_int(last_err) if last_err else None
            print(
                f"[build_shared_cache] arXiv error (HTTP {status_hint or '?'}: "
                f"{type(last_err).__name__}) — sleeping {wait}s before retry "
                f"{attempt}/{len(BACKOFF_SCHEDULE_SECONDS)} (waited {total_waited}s so far)",
                file=sys.stderr,
            )
            time.sleep(wait)
            total_waited += wait
        try:
            return arxiv_client.fetch_recent(
                categories,
                window_days=window_days,
                max_results=max_results,
                end_utc=end_utc,
            )
        except Exception as e:
            if not _is_retryable(e):
                raise
            last_err = e
    raise RuntimeError(
        f"arXiv kept failing after {len(BACKOFF_SCHEDULE_SECONDS)} "
        f"outer backoffs (total wait {total_waited}s): {last_err}"
    )


def _build_excluded_names(cfg: config.Config) -> set[str]:
    """Build the lowercase author-name exclusion set.

    From data/profile/papers.json: `author_name` (the Scholar / S2 name; null for a website-only
    profile) and `name_forms` (how the name is printed on the researcher's own arXiv papers,
    collected at profile build); plus researcher.author_aliases (config.yaml or the instance's
    researcher.json), the only source when papers.json has neither.
    """
    names: list[str] = []
    papers_path = config.profile_dir() / "papers.json"
    if papers_path.exists():
        try:
            data = json.loads(papers_path.read_text(encoding="utf-8"))
            author_name = data.get("author_name")
            if author_name:
                names.append(str(author_name))
            names.extend(str(n) for n in (data.get("name_forms") or []))
        except Exception:
            pass
    names.extend(cfg.author_aliases)
    return {n.lower() for n in names if n and n.strip()}


def _exclude_self_authored(candidates: list[dict], cfg: config.Config) -> tuple[list[dict], dict]:
    """Drop the researcher's own papers; return (kept, record).

    `record` = {"names": [...], "dropped": [arxiv_id, ...]} goes into the week's
    candidates file, so the pool itself says whether exclusion ran. An empty name
    set warns loudly instead of passing silently.
    """
    excluded = _build_excluded_names(cfg)
    if not excluded:
        print(
            "[self-exclusion] WARNING: no researcher name known — papers.json author_name is "
            "empty (always, for a website-only profile) and researcher.author_aliases is []. "
            "The researcher's OWN papers stay in the pool. Set researcher.author_aliases in "
            "config/config.yaml or <data root>/researcher.json.",
            file=sys.stderr,
        )
        return candidates, {"names": [], "dropped": []}
    keys = {PP.name_key(n) for n in excluded} - {()}   # order / case / accent / punctuation-free
    kept, dropped = [], []
    for c in candidates:
        if any(PP.name_key(a) in keys for a in (c.get("authors") or [])):
            dropped.append(c["arxiv_id"])
        else:
            kept.append(c)
    if dropped:
        print(f"[self-exclusion] removed {len(dropped)} paper(s): {dropped}", file=sys.stderr)
    return kept, {"names": sorted(excluded), "dropped": dropped}


def _load_candidates_file(path: Path) -> list[dict]:
    """Load candidates produced off-box by scripts/local_fetch_arxiv.py.

    Accepts either a {"candidates": [...]} payload or a bare list. Raises
    loudly on anything else — no silent fallback to an empty pool.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        cands = data.get("candidates")
    elif isinstance(data, list):
        cands = data
    else:
        cands = None
    if not isinstance(cands, list):
        raise ValueError(
            f"{path}: expected a candidates list or {{'candidates': [...]}}, "
            f"got {type(data).__name__}"
        )
    return cands


def _write_failure_marker(cache_dir: Path, week: str, err: Exception) -> Path:
    marker = cache_dir / f"week-{week}-FETCH-FAILED.json"
    marker.write_text(
        json.dumps(
            {
                "week": week,
                "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": f"{type(err).__name__}: {err}",
                "traceback": traceback.format_exc(),
            },
            indent=2,
        )
    )
    return marker


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-days", type=int, default=None,
                    help="Override config.ingest.window_days")
    ap.add_argument("--end-utc", type=str, default=None,
                    help="ISO-8601 UTC end of window (default: now). For backfill.")
    ap.add_argument("--force", action="store_true",
                    help="Bypass freshness check and refetch.")
    ap.add_argument("--max-wait-seconds", type=int, default=1800,
                    help="Cap on cumulative 429 backoff time (default: 1800).")
    ap.add_argument("--profile-glob", type=str, default=None,
                    help="Override profile discovery; glob relative to plugin root. "
                         "Example: 'data/users/*/profile/profile.json'.")
    ap.add_argument("--archive", action="store_true",
                    help="Also copy output to data/eval_archive/ for evaluation dataset.")
    ap.add_argument("--candidates-from", type=str, default=None,
                    help="Skip the fetch entirely and load candidates from this JSON "
                         "file. Still applies the self-author filter and writes the "
                         "cache payload. Manual escape hatch for pre-fetched data.")
    args = ap.parse_args()

    cfg = config.load_config()
    root = config.data_root()   # profiles are per-instance runtime data — NEVER discovered from the plugin dir (owner principle 2026-07-05)

    if args.profile_glob:
        profile_paths = sorted(root.glob(args.profile_glob))
    else:
        profile_paths = _discover_profiles(root)
    if not profile_paths:
        print(
            "[build_shared_cache] no profiles registered. Create either:\n"
            "  - data/profile/profile.json (single-user), or\n"
            "  - data/users/<name>/profile/profile.json (multi-user)",
            file=sys.stderr,
        )
        return 2

    print(
        f"[build_shared_cache] {len(profile_paths)} profile(s): "
        + ", ".join(str(p.relative_to(root)) for p in profile_paths),
        file=sys.stderr,
    )

    cats = _union_categories(profile_paths)
    if not cats:
        print(
            "[build_shared_cache] no arxiv_categories across registered profiles. "
            "Each profile.json must set 'arxiv_categories: [...]'.",
            file=sys.stderr,
        )
        return 2
    print(f"[build_shared_cache] union categories: {cats}", file=sys.stderr)

    window_days = args.window_days if args.window_days is not None else cfg.window_days
    end_utc = (
        datetime.fromisoformat(args.end_utc.replace("Z", "+00:00"))
        if args.end_utc
        else datetime.now(timezone.utc)
    )
    week = _week_label(end_utc)
    cache_path = config.cache_dir() / f"week-{week}-candidates.json"

    if not args.force:
        fresh, ts = _is_fresh(cache_path)
        if fresh:
            print(
                f"[build_shared_cache] fresh, skipping (last fetch: {ts}). "
                "Use --force to refetch.",
                file=sys.stderr,
            )
            print(str(cache_path))
            return 0

    try:
        if args.candidates_from:
            candidates = _load_candidates_file(Path(args.candidates_from))
            print(
                f"[build_shared_cache] loaded {len(candidates)} candidates from "
                f"{args.candidates_from} (fetch skipped)",
                file=sys.stderr,
            )
        else:
            print(
                f"[build_shared_cache] fetching window={window_days}d "
                f"end={end_utc.isoformat()} max={cfg.max_candidates}",
                file=sys.stderr,
            )
            candidates = _fetch_with_backoff(
                cats,
                window_days=window_days,
                max_results=cfg.max_candidates,
                end_utc=end_utc,
                max_wait_seconds=args.max_wait_seconds,
            )
    except Exception as e:
        marker = _write_failure_marker(config.cache_dir(), week, e)
        print(
            f"[build_shared_cache] FETCH FAILED: {type(e).__name__}: {e}\n"
            f"[build_shared_cache] marker written: {marker}",
            file=sys.stderr,
        )
        return 1

    print(f"[build_shared_cache] fetched {len(candidates)} candidates", file=sys.stderr)

    candidates, self_exclusion = _exclude_self_authored(candidates, cfg)
    print(f"[build_shared_cache] {len(candidates)} candidates after self-author filter", file=sys.stderr)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "week": week,
        "window_days": window_days,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "end_utc": end_utc.isoformat(),
        "categories": cats,
        "self_exclusion": self_exclusion,
        "candidates": candidates,
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[build_shared_cache] wrote {cache_path}", file=sys.stderr)

    fail_marker = config.cache_dir() / f"week-{week}-FETCH-FAILED.json"
    if fail_marker.exists():
        fail_marker.unlink()

    if args.archive:
        import shutil
        archive_dir = root / "data" / "eval_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"week-{week}-candidates.json"
        shutil.copy2(cache_path, archive_path)
        print(f"[build_shared_cache] archived to {archive_path}", file=sys.stderr)

    print(str(cache_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
