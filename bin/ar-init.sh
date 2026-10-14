#!/usr/bin/env bash
# ar-init.sh — scaffold an EXTERNAL data folder for one independent auto-research instance.
#
# The plugin CODE stays shared + read-only in the monorepo (PLUGIN_ROOT); each instance keeps its OWN
# DATA (researcher profile, cache, ideations, state, runs, decisions, papers) in its own folder, so two
# instances run side by side without touching each other or polluting the plugin dir.
#
#   bin/ar-init.sh <folder> [--scholar <url>] [--website <url>] [--s2-id <id>] [--aliases "A; B"]
#
# Plugin availability is GLOBAL (~/.claude/settings.json enables the -ar plugins for any cwd), so this
# only (1) creates the per-instance DATA dirs and (2) optionally pins which researcher this instance runs
# for (writes <folder>/researcher.json, layered over the shared config by scripts/lib/config.py). A pinned
# instance inherits NOTHING of the shared (owner) identity: every identity key is written, null when not
# given. With no --scholar/--website/--s2-id, the instance uses the shared (owner) default identity.
#
# After it prints the recipe:  cd <folder> && claude   →   /auto-research
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SET_RESEARCHER="$PLUGIN_ROOT/plugins/arxiv-recommender-ar/bin/set_researcher.py"

dir="" website="" s2id="" scholar="" aliases=""
while [ $# -gt 0 ]; do
  case "$1" in
    --website) website="${2:-}"; shift 2 ;;
    --s2-id)   s2id="${2:-}";    shift 2 ;;
    --scholar) scholar="${2:-}"; shift 2 ;;
    --aliases) aliases="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "ar-init: unknown flag '$1'" >&2; exit 2 ;;
    *)  dir="$1"; shift ;;
  esac
done
[ -n "$dir" ] || { echo "usage: ar-init.sh <folder> [--scholar <url>] [--website <url>] [--s2-id <id>] [--aliases \"A; B\"]" >&2; exit 2; }

mkdir -p "$dir/state/decisions" "$dir/runs" "$dir/data/profile"
abs="$(cd "$dir" && pwd)"

if [ -n "$scholar" ] || [ -n "$website" ] || [ -n "$s2id" ]; then
  al="$(printf '%s' "$aliases" | sed 's/; */||/g')"
  python3 "$SET_RESEARCHER" --store "$abs/researcher.json" --scholar "${scholar:-null}" \
    --website "${website:-null}" --s2-id "${s2id:-null}" --aliases "$al" --categories null
  echo "ar-init: pinned researcher → $abs/researcher.json"
fi

echo "ar-init: data folder ready → $abs  (state/  runs/  data/profile/$([ -f "$abs/researcher.json" ] && echo '  researcher.json'))"
echo
echo "Next:  cd \"$abs\" && claude        # plugin loads from the shared monorepo; data stays here"
echo "       then:  /auto-research${website:+ $website}"
