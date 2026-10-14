#!/usr/bin/env bash
# T20 — round-entry concern snapshot (Doc B §6 / Doc A §3.3, Doc C §5.2 #1). Static wiring check that L0 FREEZES
# the open-concern set at round entry and that every reader is pointed at the FROZEN snapshot, never the live
# ledger (the byte-identical-across-detach guarantee). The behavioral byte-identity test is the live item
# NEXT-REVIEW C12. Run: bash tests/t20_round_concern_snapshot.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; SPEC="$ROOT/spec/research.js"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

chk "round-entry writes .round-<N>.concerns.json"        "grep -qF '.round-\${state.loop_round}.concerns.json' '$SPEC'"
chk "snapshot frozen inside the !round_in_progress block" "awk '/if \\(!state.round_in_progress\\)/{f=1} f&&/concerns.json/{print;exit}' '$SPEC' | grep -q concerns.json"
# RC-12: the freeze + its fail-loud hard-stop MOVED from inline JS (which the L0 could skip) into the
# deterministic bin/round_setup.sh; research.js now CALLS it and throws on its ERROR exit. (round_setup.sh's
# own behavior — idempotent byte-identical freeze, exit-2 hard-stop — is covered by tests/t44_round_setup.sh.)
chk "round freeze is deterministic (bin/round_setup.sh)"  "grep -qF 'bin/round_setup.sh' '$SPEC'"
chk "fail-loud hard-stop on round_setup ERROR"            "grep -qF 'round_setup failed' '$SPEC'"
chk "readers told FROZEN snapshot, NEVER the live ledger" "grep -qF 'NEVER the live ledger' '$SPEC'"
chk "frozen-snapshot discipline cites Doc A §3.3"        "grep -qF '3.3' '$SPEC'"
chk "spec still parses (node --check)"                   "node --check '$SPEC'"

echo "----"; echo "t20_round_concern_snapshot: $pass passed, $fail failed"; [ "$fail" = 0 ]
