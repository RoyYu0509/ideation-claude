#!/usr/bin/env bash
# bin/contract_lock_status.sh — the deterministic LOCKED|ABSENT oracle for the two Phase-0(C) contracts.
#
# WHY. L0 must NOT spawn an experiment milestone (or let V5 pass) while the SCALE/AMBITION baseline is
# unlocked — that is exactly how a post-Phase-0 WEAKEN slips through unseen. This is the cheap check L0
# calls before the experiment precondition and V5 reads to FAIL-CLOSED instead of "legacy-pass".
#
# Usage: bin/contract_lock_status.sh <workspace>
#   stdout line 1: LOCKED  (both .locked.json present + parseable) | ABSENT <which> (one/both missing).
#   exit 0 = LOCKED, exit 1 = ABSENT, exit 2 = error (bad args).
set -euo pipefail
WS="${1:-}"
[ -n "$WS" ] || { echo "ERROR contract_lock_status: need <workspace>"; exit 2; }

missing=""
for f in HANDOFF.scale-contract.locked.json HANDOFF.ambition.locked.json; do
  p="$WS/$f"
  if [ ! -f "$p" ] || ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$p" 2>/dev/null; then
    missing="$missing $f"
  fi
done

if [ -n "$missing" ]; then
  echo "ABSENT$missing"; exit 1
fi
echo "LOCKED"; exit 0
