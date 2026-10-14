#!/usr/bin/env python3
"""bin/snapshot_ideation_pool.py — durable per-run snapshot of the ideation pool (the D4 evidence base).

The scout's next weekly run deletes data/cache/week-* and data/ideations/* after cache_stale_days (~7d),
so a late /learn retro loses the pool it needs to audit the ideation CEILING (judge near-misses, rerank
commentary, rejected sub-ideas). This bin runs once at seed-pick time (called from setupWorkspace in
spec/research.js) and copies the picked week's pool evidence into the run workspace, where it lives as
long as the run does.

Behavior contract:
- IDEMPOTENT: an existing snapshot-manifest.json means "already taken" -> OK, exit 0 (resume-safe).
- EXPIRY-TOLERANT: every expected-but-missing source is recorded as action:"missing" — never a failure.
- TRIM, never truncate: a JSON over --max-file-bytes whose top level holds candidates[] is projected to
  {week, count, candidates:[{arxiv_id,title}]} written as <name>.index.json (action "trimmed"); an
  oversized file of unknown shape is "skipped-too-large" (a partial JSON on disk would be worse than none).
- Exit 2 ONLY on bad args / underivable week; pool absence is always exit 0.

Usage:
  snapshot_ideation_pool.py --data-root D --ws W --seed-file data/ideations/<week>/refined/<id>.md
                            [--max-file-bytes 1048576] [--max-total-bytes 20971520]
"""
import os, re, sys, json, glob, shutil, argparse
from datetime import datetime, timezone

MANIFEST_SCHEMA = "auto-research-pool-snapshot@1"
# canonical cache files (week-substituted) — absence of any is recorded, never fatal
CACHE_CANON = ["week-{w}-candidates.json", "week-{w}-prefetched.json", "week-{w}-rerank.json",
               "week-{w}-judge-cache.json", "week-{w}-gated-pool.json", "week-{w}-scout.json",
               "week-{w}-quality-gate.json", "week-{w}-ideation-ledger.json",
               "week-{w}-refine-ledger.json"]  # refine-ledger = pre-2026-07-11 vintage (kept for old weeks)

def die(msg):
    print("ERROR pool_snapshot: " + msg); sys.exit(2)

def derive_week(seed_file):
    m = re.search(r"data/ideations/([^/]+)/", seed_file.replace(os.sep, "/"))
    return m.group(1) if m else None

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--ws", required=True)
    ap.add_argument("--seed-file", required=True)
    ap.add_argument("--max-file-bytes", type=int, default=1048576)
    ap.add_argument("--max-total-bytes", type=int, default=20971520)
    try:
        a = ap.parse_args()
    except SystemExit:
        die("bad arguments (need --data-root --ws --seed-file)")

    week = derive_week(a.seed_file)
    if not week:
        die("cannot derive <week> from seed-file %r (expected .../data/ideations/<week>/...)" % a.seed_file)

    dest = os.path.join(a.ws, "ideation-pool-snapshot")
    man_path = os.path.join(dest, "snapshot-manifest.json")
    if os.path.isfile(man_path):
        print("OK pool_snapshot: already taken (%s)" % man_path); return

    cache_dir = os.path.join(a.data_root, "data", "cache")
    idea_dir = os.path.join(a.data_root, "data", "ideations", week)
    files, total = [], 0

    def record(src, rel_dst, action, bsrc=None, bdst=None, reason=None):
        e = {"src": src, "rel_dst": rel_dst, "action": action}
        if bsrc is not None: e["bytes_src"] = bsrc
        if bdst is not None: e["bytes_dst"] = bdst
        if reason: e["reason"] = reason
        files.append(e)

    def take(src, rel_dst):
        """Copy src -> dest/rel_dst honoring trim + budget rules; record the outcome."""
        nonlocal total
        if not os.path.isfile(src):
            record(src, rel_dst, "missing"); return
        size = os.path.getsize(src)
        if size > a.max_file_bytes:
            trimmed = None
            try:
                with open(src) as f: doc = json.load(f)
                if isinstance(doc, dict) and isinstance(doc.get("candidates"), list):
                    trimmed = {"week": week, "count": len(doc["candidates"]),
                               "candidates": [{"arxiv_id": c.get("arxiv_id"), "title": c.get("title")}
                                              for c in doc["candidates"]]}
            except Exception:
                trimmed = None
            if trimmed is None:
                record(src, rel_dst, "skipped-too-large", bsrc=size,
                       reason="over max-file-bytes and not a candidates[] JSON"); return
            rel_dst = re.sub(r"\.json$", "", rel_dst) + ".index.json"
            out = os.path.join(dest, rel_dst)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w") as f:
                json.dump(trimmed, f, ensure_ascii=False, indent=1); f.write("\n")
            bdst = os.path.getsize(out); total += bdst
            record(src, rel_dst, "trimmed", bsrc=size, bdst=bdst); return
        if total + size > a.max_total_bytes:
            record(src, rel_dst, "skipped-budget", bsrc=size,
                   reason="max-total-bytes budget exhausted"); return
        out = os.path.join(dest, rel_dst)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(src, out); total += size
        record(src, rel_dst, "copied", bsrc=size, bdst=size)

    os.makedirs(dest, exist_ok=True)
    # 1. canonical cache files first (deterministic), then any other week-<W>-* stragglers
    canon = [c.format(w=week) for c in CACHE_CANON]
    for name in canon:
        take(os.path.join(cache_dir, name), "cache/" + name)
    for src in sorted(glob.glob(os.path.join(cache_dir, "week-%s-*" % week))):
        if os.path.basename(src) not in canon and os.path.isfile(src):
            take(src, "cache/" + os.path.basename(src))
    # 2. the week's ideation dir: top-level files (ideation + evidence JSONs, .integrity.json,
    #    legacy .seed-verify-*.json verdicts from the retired post-pick gate) + refined/ + the
    #    verification bundles (2026-07-11 verified-kill: bundle.json / prior-art / assets / probes /
    #    recheck outputs — the /learn false-kill audit material).
    if os.path.isdir(idea_dir):
        for src in sorted(glob.glob(os.path.join(idea_dir, "*"))
                          + [os.path.join(idea_dir, ".integrity.json")]
                          + glob.glob(os.path.join(idea_dir, ".seed-verify-*.json"))):
            if os.path.isfile(src):
                take(src, "ideations/" + os.path.basename(src))
        for src in sorted(glob.glob(os.path.join(idea_dir, "refined", "*"))):
            if os.path.isfile(src):
                take(src, "ideations/refined/" + os.path.basename(src))
        for src in sorted(glob.glob(os.path.join(idea_dir, "bundles", "**", "*"), recursive=True)):
            if os.path.isfile(src):
                rel = os.path.relpath(src, idea_dir)
                take(src, "ideations/" + rel.replace(os.sep, "/"))
    else:
        record(idea_dir, "ideations/", "missing", reason="ideation dir absent (expired or never built)")

    tally = {}
    for e in files:
        k = "skipped" if e["action"].startswith("skipped") else e["action"]
        tally[k] = tally.get(k, 0) + 1
    manifest = {"schema": MANIFEST_SCHEMA, "week": week, "seed_file": a.seed_file,
                "taken_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data_root": a.data_root, "files": files,
                "totals": {"copied": tally.get("copied", 0), "trimmed": tally.get("trimmed", 0),
                           "missing": tally.get("missing", 0), "skipped": tally.get("skipped", 0),
                           "bytes": total}}
    tmp = man_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1); f.write("\n")
    os.replace(tmp, man_path)
    t = manifest["totals"]
    print("OK pool_snapshot: week=%s copied=%d trimmed=%d missing=%d skipped=%d bytes=%d"
          % (week, t["copied"], t["trimmed"], t["missing"], t["skipped"], t["bytes"]))

if __name__ == "__main__":
    main()
