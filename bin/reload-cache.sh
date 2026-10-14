#!/usr/bin/env bash
# reload-cache.sh — one-shot "reload plugin" for the local dev loop.
#
# WHY THIS EXISTS: Claude Code loads 3 of the 4 plugins from a FROZEN CACHE COPY, not the
# monorepo. Installing a directory-source plugin COPIES it into
# ~/.claude/plugins/cache/<market>/<plugin>/<version>/, and CLAUDE_PLUGIN_ROOT points at that
# frozen copy — true today for auto-research (root), paper-polish-ar and experiment-lab-ar.
# EXCEPTION (live-source, no materialized cache — edits take effect without this script):
# arxiv-recommender-ar (its recorded 0.3.0 cache dir was never re-materialized after 0.4.0).
# For the cached three, editing
# files here never touches the loaded copy — that is why every change needs a re-sync. There is no harness command that hot-reloads a
# plugin's files in place; a true reinstall would re-copy from source AND wipe the runs/ state/
# arxiv-data that now live inside the cache dir. This script is the surgical, data-safe re-sync.
#
# WHAT IT DOES (in order):
#   1. apply the key-config control panel (key-config.yaml) into the three runtime configs, here.
#   2. overlay-copy the edited plugin CODE into every installed cache copy Claude Code loads.
#
# DATA-PLANE SAFE BY CONSTRUCTION: only git-tracked CODE is copied (worktree content — no commit
# needed), overlaid via tar (never a delete). runs/ state/ and the arxiv data/ dir live inside the
# cache copies and are NEVER in the tracked set, so they are never touched. state/ (a few tracked
# template files) is also explicitly excluded so an in-flight run's live state is never clobbered.
#
# USAGE:
#   bash bin/reload-cache.sh            # apply key-config + sync every cache copy
#   bash bin/reload-cache.sh --no-key   # sync only (skip key-config)
#   bash bin/reload-cache.sh --check    # dry-run: show pending key-config diff + file counts, write nothing
#
# AFTER RUNNING: slash-command + spec/*.js changes are live on the next command invocation (the
# command markdown cat's them fresh). Skill/agent FRONTMATTER is registered at session start — for
# those to re-register you must restart the Claude Code session.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKET="auto-research"
INSTALLED="$HOME/.claude/plugins/installed_plugins.json"
MP="$REPO/.claude-plugin/marketplace.json"

DO_KEY=1 DRY=0
for a in "$@"; do
  case "$a" in
    --no-key)            DO_KEY=0 ;;
    --check|--dry-run)   DRY=1 ;;
    -h|--help)           sed -n '23,28p' "$0"; exit 0 ;;
    *) echo "usage: reload-cache.sh [--no-key] [--check]" >&2; exit 2 ;;
  esac
done

[ -f "$INSTALLED" ] || { echo "ERROR reload-cache: missing $INSTALLED (plugin not installed?)" >&2; exit 1; }

# ── 1) key-config.yaml → runtime configs (writes into the monorepo source) ──────────────────────
if [ "$DO_KEY" = 1 ]; then
  echo "▶ key-config → runtime configs"
  if [ "$DRY" = 1 ]; then bash "$REPO/bin/apply_key_config.sh" --check; else bash "$REPO/bin/apply_key_config.sh"; fi
  echo
fi

# ── 2) code → cache copies ──────────────────────────────────────────────────────────────────────
if [ "$DRY" = 1 ]; then echo "▶ sync plugin CODE → cache copies (dry-run)"; else echo "▶ sync plugin CODE → cache copies"; fi
EXCLUDE='^(runs|state)/'   # data-plane dirs that live INSIDE a cache copy — keep intact

# (src_subdir <TAB> dest_installPath) for every registered + installed plugin of this marketplace.
while IFS=$'\t' read -r src_rel dest; do
  [ -n "$src_rel" ] || continue
  if [ "$src_rel" = "." ]; then src="$REPO"; else src="$REPO/$src_rel"; fi
  [ -d "$src" ]  || { echo "  skip (no source):  $src_rel"; continue; }
  [ -d "$dest" ] || { echo "  skip (no cache):   $dest"; continue; }

  # NUL-list of tracked + still-existing + non-data files, relative to src (worktree content).
  list="$(mktemp)"
  ( cd "$src" && git ls-files -z | while IFS= read -r -d '' f; do
        case "$f" in runs/*|state/*) continue ;; esac
        [ -e "$f" ] && printf '%s\0' "$f"
    done ) > "$list"
  n=$(tr -cd '\0' < "$list" | wc -c | tr -d ' ')

  pretty="${dest/#$HOME/~}"
  if [ "$DRY" = 1 ]; then
    echo "  would sync $n files:  ${src_rel}  →  ${pretty}"
  else
    ( cd "$src" && tar --null -T "$list" -cf - ) | ( cd "$dest" && tar -xf - )
    # C2 drift stamp: CONTENT fingerprint of what was just synced (worktree-aware — see
    # bin/sync_fingerprint.sh header). /auto-research's preflight compares this ADVISORY-only.
    if fp="$(bash "$REPO/bin/sync_fingerprint.sh" "$src" 2>/dev/null)" && [ -n "$fp" ]; then
      printf '%s synced-at %s\n' "$fp" "$(date -u +%FT%TZ)" > "$dest/.sync-stamp" || true
    fi
    echo "  synced $n files:      ${src_rel}  →  ${pretty}"
  fi
  rm -f "$list"
done < <(python3 - "$MARKET" "$MP" "$INSTALLED" <<'PY'
import json, sys
market, mp_path, inst_path = sys.argv[1], sys.argv[2], sys.argv[3]
def norm(s):
    s = s[2:] if s.startswith("./") else s
    return s.rstrip("/") or "."
src = {p["name"]: norm(p["source"]) for p in json.load(open(mp_path))["plugins"]}
inst = json.load(open(inst_path))["plugins"]
seen = set()
for key, recs in inst.items():
    name, _, m = key.partition("@")
    if m != market or name not in src:
        continue
    for r in recs:
        dest = r.get("installPath")
        if dest and dest not in seen:
            seen.add(dest)
            print(f"{src[name]}\t{dest}")
PY
)

echo
if [ "$DRY" = 1 ]; then
  echo "✓ dry-run only — nothing written."
else
  echo "✓ reload complete. Slash-command + spec changes are live now;"
  echo "  restart the Claude Code session if you changed skill/agent FRONTMATTER."
fi
