#!/usr/bin/env bash
# bin/milestone_done.sh — RC-3: the REAL definition of milestoneDone() (research.js calls it, but the
# spec never defined it — the idempotent-resume predicate the whole B1 loop rests on). A milestone counts
# as done iff milestone-state.json records it with a completed_at AND a code/paper commit sha (RC-9: a done
# milestone must leave provenance). This makes "did this milestone really finish" disk-checkable, not prose.
#
# RC-12 (provenance hardening): the recorded commit must RESOLVE in its repo (a recorded-but-bogus sha, or
# uncommitted producing scripts, no longer count as done). With --require-segment-commits, EVERY
# EXPERIMENTS/<id>/result.md must additionally carry a code_commit sha that resolves in ws/code — closes the
# "result.md claims PASS but the producing script was never committed" ghost (the E3 ghost).
#
# Usage: bin/milestone_done.sh <workspace> <milestone> [--require-segment-commits]
#   exit 0 = done, exit 1 = not done (re-run it), exit 2 = error (bad args / unparseable state).
set -euo pipefail

WS="${1:-}"; MS="${2:-}"; FLAG="${3:-}"
[ -n "$WS" ] || { echo "ERROR milestone_done: need <workspace>"; exit 2; }
[ -n "$MS" ] || { echo "ERROR milestone_done: need <milestone>"; exit 2; }
MSF="$WS/milestone-state.json"
[ -f "$MSF" ] || exit 1                              # no state yet => nothing is done

# resolve(repo, sha) -> 0 if sha resolves to a commit in <repo>; non-zero otherwise. If <repo> is NOT a git
# repo (e.g. a test fixture), echo SKIP so the caller falls back to the legacy "field present" check.
resolve() {
  local repo="$1" sha="$2"
  git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || { echo SKIP; return 0; }
  git -C "$repo" cat-file -e "${sha}^{commit}" 2>/dev/null && echo OK || echo NO
}

WS="$WS" MS="$MS" python3 - <<'PY' || exit $?
import os, sys, json
ws = os.environ["WS"]; ms = os.environ["MS"]
try:
    d = json.load(open(os.path.join(ws, "milestone-state.json")))
except Exception as e:
    print("ERROR milestone_done: cannot parse milestone-state.json (%s)" % e); sys.exit(2)
m  = (d.get("milestones") or {}).get(ms) or {}
ok = bool(m.get("completed_at")) and bool(m.get("code_commit") or m.get("paper_commit"))
sys.exit(0 if ok else 1)
PY

# At this point the milestone-level fields are PRESENT. Now require the recorded commit to RESOLVE (unless
# its repo is not a git dir — fixture fallback keeps the legacy field-only behavior).
read_field() { python3 -c "import json,sys; print((json.load(open(sys.argv[1])).get('milestones') or {}).get(sys.argv[2],{}).get(sys.argv[3]) or '')" "$MSF" "$MS" "$1"; }
CODE_SHA="$(read_field code_commit)"; PAPER_SHA="$(read_field paper_commit)"
if [ -n "$CODE_SHA" ]; then
  case "$(resolve "$WS/code" "$CODE_SHA")" in NO) exit 1;; esac
fi
if [ -n "$PAPER_SHA" ]; then
  case "$(resolve "$WS/paper" "$PAPER_SHA")" in NO) exit 1;; esac
fi

# --require-segment-commits: every EXPERIMENTS/<id>/result.md must carry a code_commit sha resolving in ws/code.
if [ "$FLAG" = "--require-segment-commits" ] && [ -d "$WS/EXPERIMENTS" ]; then
  if git -C "$WS/code" rev-parse --git-dir >/dev/null 2>&1; then        # only enforce when code/ is a real repo
    while IFS= read -r rm; do
      [ -f "$rm" ] || continue
      sha="$(grep -oiE '[0-9a-f]{7,40}' "$rm" | while read -r h; do
               git -C "$WS/code" cat-file -e "${h}^{commit}" 2>/dev/null && { echo "$h"; break; }; done | head -1)"
      [ -n "$sha" ] || { echo "milestone_done: $rm has no resolvable ws/code commit (uncommitted producer?)"; exit 1; }
    done < <(find "$WS/EXPERIMENTS" -name result.md 2>/dev/null)
  fi
fi
exit 0
