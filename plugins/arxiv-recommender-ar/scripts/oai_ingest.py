#!/usr/bin/env python3
"""VPS-native fixed-window arXiv ingest via OAI-PMH — the DEFAULT fetch path.

arXiv's edge hard-blocks `export.arxiv.org/api/query` for datacenter IPs, but the
OAI-PMH endpoint is open and supports an arbitrary `from`/`until` window. This
gives a STATELESS "last N days" fetch (set by ingest.window_days) that runs
entirely on the VPS — no Mac/VPN/tunnel, and no daily-accumulation state (unlike
the retired RSS path).

Per run: resolve each profile category to its OAI fine set (e.g. cs.CE→cs:cs:CE),
harvest each set for the window, keep only records whose FIRST version was
submitted inside the half-open window [end − window_days, end) (UTC dates; drops
re-versioned old papers — the old API's submittedDate semantics; the v1 date comes
from arXivRaw, see arxiv_oai.harvest), dedup by arxiv_id, self-author filter, and write
`data/cache/week-<YYYY-Www>-candidates.json` (the file the scout reads).

Idempotent + cheap to re-run: a freshness gate skips the harvest if the cache is
younger than ingest.cache_fresh_hours (use --force to override). The scout's
Phase 1 calls this; no separate cron is needed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_shared_cache import (  # noqa: E402  (reuse profile + filter helpers)
    _discover_profiles,
    _exclude_self_authored,
    _union_categories,
    _week_label,
)
from lib import arxiv_oai, config  # noqa: E402


def _is_fresh(cache_path: Path, max_age_hours: float) -> tuple[bool, str | None]:
    if not cache_path.exists():
        return False, None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        ts = data.get("fetched_at_utc")
        fetched_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return False, None
    age = datetime.now(timezone.utc) - fetched_at
    return age < timedelta(hours=max_age_hours), ts


def _submitted_in_window(cand: dict, start_date, end_date) -> bool:
    """Keep only papers whose FIRST version was submitted in [start_date, end_date)
    (UTC dates), dropping re-versioned old papers that share the datestamp range.
    Half-open, so a window ending on day D and the next one starting on D never
    share a day. An unknown first-version date (record absent from the arXivRaw
    pass) is dropped: the pool must hold only papers verified to be new, and the
    caller logs how many were dropped this way."""
    submitted = cand.get("submitted")
    if not submitted:
        return False
    return start_date <= datetime.fromisoformat(submitted).date() < end_date


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window-days", type=int, default=None,
                    help="Override config.ingest.window_days for this run.")
    ap.add_argument("--force", action="store_true",
                    help="Bypass the freshness gate and re-harvest.")
    ap.add_argument("--profile-glob", type=str, default=None,
                    help="Override profile discovery (glob relative to the data root).")
    ap.add_argument("--end-utc", type=str, default=None,
                    help="BACKFILL: treat this UTC date (YYYY-MM-DD) as 'now'. The harvest window becomes "
                         "[end-utc − window_days, end-utc) and the output is labelled with THAT date's ISO "
                         "week, so a past week can be reconstructed instead of waiting for it to arrive. "
                         "Omit for normal operation.")
    args = ap.parse_args()

    cfg = config.load_config()
    root = config.data_root()   # profiles are per-instance runtime data — NEVER discovered from the plugin dir (owner principle 2026-07-05; the old plugin_root() read silently harvested the owner's profile for external instances)
    # `now` drives THREE things below — the harvest window, the ISO week label, and the cache filename — so
    # overriding it here is all a backfill needs; nothing else in this file assumes wall-clock time. (The
    # freshness gate deliberately keeps using the real clock: it compares a cache file's age, not the window.)
    # CAVEAT, by design: OAI from/until filter on DATESTAMP (last record update) and the results are then
    # narrowed to first-version date in [start, end). A paper submitted in the target week but re-versioned AFTER it has
    # a later datestamp and is therefore invisible to a backfill — so a reconstructed week skews slightly
    # against later-revised papers. Acceptable in slow-moving fields; state it if the week is used as evidence.
    now = datetime.now(timezone.utc)
    if args.end_utc:
        try:
            now = datetime.fromisoformat(args.end_utc).replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"[oai_ingest] --end-utc must be YYYY-MM-DD (got {args.end_utc!r})", file=sys.stderr)
            return 2
        print(f"[oai_ingest] BACKFILL mode: treating {now.date().isoformat()} as now", file=sys.stderr)
    window_days = args.window_days if args.window_days is not None else cfg.window_days

    profile_paths = (
        sorted(root.glob(args.profile_glob)) if args.profile_glob
        else _discover_profiles(root)
    )
    if not profile_paths:
        print("[oai_ingest] no profiles registered (data/profile/profile.json or "
              "data/users/*/profile/profile.json).", file=sys.stderr)
        return 2
    cats = _union_categories(profile_paths)
    if not cats:
        print("[oai_ingest] no arxiv_categories across profiles.", file=sys.stderr)
        return 2

    week = _week_label(now)
    cache_path = config.cache_dir() / f"week-{week}-candidates.json"
    if not args.force:
        fresh, ts = _is_fresh(cache_path, cfg.cache_fresh_hours)
        if fresh:
            print(f"[oai_ingest] fresh, skipping (last fetch {ts}, "
                  f"< {cfg.cache_fresh_hours}h). Use --force.", file=sys.stderr)
            print(str(cache_path))
            return 0

    end_date = now.date()
    start_date = end_date - timedelta(days=window_days)
    # OAI `until` is inclusive and filters on DATESTAMP, which trails submission (a paper
    # submitted on day end−1 is announced on day `end` at the earliest), so harvesting
    # datestamps [start, end] reaches the window's last day; _submitted_in_window then
    # keeps first-version dates in [start, end).
    from_date, until_date = start_date.isoformat(), end_date.isoformat()
    print(f"[oai_ingest] window [{from_date}, {until_date}) ({window_days}d, by first-version "
          f"date), {len(cats)} categories: {cats}", file=sys.stderr)

    # Resolve each category → OAI fine set (one ListSets call).
    try:
        setspecs = arxiv_oai.list_sets()
        cat_sets = {c: arxiv_oai.resolve_set(c, setspecs) for c in cats}
    except Exception as e:
        print(f"[oai_ingest] FAILED resolving OAI sets: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 1
    # Harvest each distinct set (cs.NA/math.NA may map to distinct sets; dedup later).
    by_id: dict[str, dict] = {}
    try:
        for setspec in sorted(set(cat_sets.values())):
            recs = arxiv_oai.harvest(setspec, from_date, until_date)
            kept = [r for r in recs if _submitted_in_window(r, start_date, end_date)]
            unverified = sum(1 for r in recs if not r.get("submitted"))
            for r in kept:
                aid = r["arxiv_id"]
                if aid in by_id:
                    by_id[aid]["categories"] = list(dict.fromkeys(
                        [*by_id[aid]["categories"], *r["categories"]]))
                else:
                    by_id[aid] = r
            note = f", {unverified} dropped (no arXivRaw v1 date)" if unverified else ""
            print(f"[oai_ingest]   {setspec}: {len(recs)} in datestamp range, "
                  f"{len(kept)} first-submitted in window{note}", file=sys.stderr)
    except Exception as e:
        print(f"[oai_ingest] HARVEST FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    candidates, self_exclusion = _exclude_self_authored(list(by_id.values()), cfg)

    config.cache_dir().mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({
        "week": week,
        "window_days": window_days,
        "fetched_at_utc": now.isoformat(),
        "end_utc": now.isoformat(),
        "categories": cats,
        "self_exclusion": self_exclusion,
        "candidates": candidates,
    }, indent=2), encoding="utf-8")
    print(f"[oai_ingest] wrote {len(candidates)} candidates -> {cache_path}",
          file=sys.stderr)

    marker = config.cache_dir() / f"week-{week}-FETCH-FAILED.json"
    if marker.exists():
        marker.unlink()
    print(str(cache_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
