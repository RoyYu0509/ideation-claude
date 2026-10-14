#!/usr/bin/env bash
# bin/round_setup.sh — DETERMINISTIC per-round disclosure setup + fail-loud guard (replaces the inline-JS
# block in research.js `case 'loop'` that the L0 could — and this run DID — skip entirely, taking the
# hard-stop `throw` with it).
#
# WHY. Each round must FREEZE its open-concern disclosure set so every goal-builder + every resume reads a
# BYTE-IDENTICAL set (a detach+rewake must not drift). The freeze + its missing-snapshot hard-stop were
# inline JS; when L0 skipped them, .round-N.start / .round-N.concerns.json were never written and nothing
# halted. This makes both the WRITE and the hard-stop a real exit code.
#
# IDEMPOTENT (safe to call on every loop entry, fresh OR mid-round resume):
#   - .round-<n>.start    : created ONLY if absent (its mtime dates "HANDOFF-*.md exported THIS round";
#                           never re-touched, or derive_gate_input's freshness window would drift).
#   - .round-<n>.concerns.json : written ONLY if absent (the freeze is immutable for the round); on resume
#                           the existing snapshot is left byte-identical. Source = TASK_STATUS.concerns.json
#                           .open_concerns (empty set if that file is absent).
#
# Usage: bin/round_setup.sh <workspace> <round>
#   exit 0 = round disclosure set is present (written or already frozen). stdout: OK round_setup: ...
#   exit 2 = error (bad args / could not ensure the snapshot exists = fail-loud hard-stop).
set -euo pipefail

WS="${1:-}"; ROUND="${2:-}"
[ -n "$WS" ] || { echo "ERROR round_setup: need <workspace>"; exit 2; }
[ -n "$ROUND" ] || { echo "ERROR round_setup: need <round>"; exit 2; }
case "$ROUND" in (*[!0-9]*|"") echo "ERROR round_setup: <round> must be a positive integer (got '$ROUND')"; exit 2;; esac

START="$WS/.round-$ROUND.start"
SNAP="$WS/.round-$ROUND.concerns.json"

[ -f "$START" ] || touch "$START" || { echo "ERROR round_setup: cannot create $START"; exit 2; }

if [ ! -f "$SNAP" ]; then
  WS="$WS" ROUND="$ROUND" SNAP="$SNAP" python3 - <<'PY' || { echo "ERROR round_setup: cannot write the concern snapshot"; exit 2; }
import os, sys, json
ws = os.environ["WS"]; rnd = int(os.environ["ROUND"]); snap = os.environ["SNAP"]
live = os.path.join(ws, "TASK_STATUS.concerns.json")
open_c, frozen_from = [], None
if os.path.isfile(live):
    try:
        open_c = (json.load(open(live)) or {}).get("open_concerns") or []
        frozen_from = "TASK_STATUS.concerns.json"
    except Exception as e:
        print("cannot parse TASK_STATUS.concerns.json (%s)" % e, file=sys.stderr); sys.exit(1)
tmp = snap + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump({"round": rnd, "frozen_from": frozen_from, "open_concerns": open_c}, f, indent=2, ensure_ascii=False)
os.replace(tmp, snap)
PY
fi

# fail-loud hard-stop: the snapshot MUST exist now (Doc A §3.3 — never silently re-derive the disclosure set).
[ -f "$SNAP" ] || { echo "ERROR round_setup: concern snapshot still missing at $SNAP"; exit 2; }
echo "OK round_setup: round $ROUND disclosure set frozen ($SNAP)"

DATA_ROOT="$(cd "$WS/../.." 2>/dev/null && pwd || true)"
[ -n "$DATA_ROOT" ] && CLAUDE_PROJECT_DIR="$DATA_ROOT" bash "$(dirname "${BASH_SOURCE[0]}")/log_event.sh" \
  round_setup "{\"round\":$ROUND}" 2>/dev/null || true
