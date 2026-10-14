#!/usr/bin/env bash
# sync_fingerprint.sh — CONTENT fingerprint of a plugin SOURCE tree, for cache-drift detection (C2).
#
# Formula: sha256 over the sorted (path, content-sha256) pairs of every git-TRACKED, still-existing,
# non-data (runs/ state/) file — i.e. exactly the set bin/reload-cache.sh copies into a cache.
# A bare HEAD-SHA stamp is NOT enough: reload-cache syncs WORKTREE content, and the dominant drift
# mode is "sync, then keep editing the uncommitted worktree" — HEAD never moves, content does.
#
# Used by:
#   * bin/reload-cache.sh  — writes the fingerprint to <cache>/.sync-stamp after each sync
#   * /auto-research preflight — recomputes it on the SOURCE and compares to the cache's .sync-stamp,
#     ADVISORY ONLY (source unresolvable / no stamp / any error ⇒ silent skip, never a gate).
#
# Usage: sync_fingerprint.sh <repo-or-plugin-source-dir>     (prints one hex line; exit 0)
set -euo pipefail
d="${1:?usage: sync_fingerprint.sh <repo-or-plugin-source-dir>}"
cd "$d"
git ls-files -z 2>/dev/null | python3 -c '
import sys, hashlib
h = hashlib.sha256()
for n in sorted(p for p in sys.stdin.buffer.read().split(b"\0") if p):
    if n.startswith((b"runs/", b"state/")):
        continue
    try:
        with open(n, "rb") as f:
            digest = hashlib.sha256(f.read()).digest()
    except (IsADirectoryError, FileNotFoundError, PermissionError):
        continue
    h.update(n); h.update(b"\0"); h.update(digest)
print(h.hexdigest())'
