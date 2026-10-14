#!/usr/bin/env bash
# t62 — bin/learn_hypotheses.py roundtrip + refusals. Proves: init/list/validate/apply lifecycle, the
# deployed-before-verdict invariant (the cache-drift lesson: a run on pre-change code can only record
# `unmeasurable`), duplicate-id and bad-enum refusals, and atomic writes that never corrupt the tracker.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
LH="$ROOT/bin/learn_hypotheses.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
F="$TMP/hypotheses.json"

# === Case 1: init + validate + refuse re-init ===
python3 "$LH" "$F" init >/dev/null && python3 "$LH" "$F" validate >/dev/null
python3 "$LH" "$F" init >/dev/null 2>&1; R=$?
if [ -f "$F" ] && [ "$R" = "2" ]; then ok "init + validate + refuse overwrite"; else no "init/validate/overwrite"; fi

# === Case 2: apply add -> list shows it open ===
cat > "$TMP/p1.json" <<'EOF'
{"ops":[{"op":"add","hypothesis":{"id":"H-1","statement":"V6 materiality rule stops headline mismatches",
 "proposal_ref":"01-run-retro#P2","born_run":"R1",
 "expected_signal":"no headline-number mismatch survives any FOCUSED PASS",
 "how_to_check":"diff paper headline numbers vs wave ledgers at each verify PASS"}}]}
EOF
python3 "$LH" "$F" apply "$TMP/p1.json" >/dev/null
if python3 "$LH" "$F" list | grep -q "H-1.*ratified-pending-build"; then
  ok "apply add -> listed as ratified-pending-build"; else no "apply add"; fi

# === Case 3: verdict on a NON-deployed hypothesis is refused (except unmeasurable) ===
printf '%s\n' '{"ops":[{"op":"check","id":"H-1","run_id":"R2","verdict":"helped","evidence":"e"}]}' > "$TMP/p2.json"
python3 "$LH" "$F" apply "$TMP/p2.json" >/dev/null 2>&1; R1=$?
printf '%s\n' '{"ops":[{"op":"check","id":"H-1","run_id":"R2","verdict":"unmeasurable","evidence":"pre-change code ran"}]}' > "$TMP/p3.json"
python3 "$LH" "$F" apply "$TMP/p3.json" >/dev/null 2>&1; R2=$?
if [ "$R1" = "2" ] && [ "$R2" = "0" ]; then
  ok "deployed-before-verdict invariant (unmeasurable allowed pre-deploy)"; else no "deploy invariant ($R1/$R2)"; fi

# === Case 4: status walk to deployed, then a real verdict lands ===
cat > "$TMP/p4.json" <<'EOF'
{"ops":[{"op":"status","id":"H-1","status":"built","commit":"abc1234"},
        {"op":"status","id":"H-1","status":"deployed"},
        {"op":"check","id":"H-1","run_id":"R3","verdict":"helped","evidence":"zero mismatches r1-r3"}]}
EOF
if python3 "$LH" "$F" apply "$TMP/p4.json" >/dev/null && python3 "$LH" "$F" list | grep -q "helped"; then
  ok "status walk + deployed verdict recorded"; else no "status walk"; fi

# === Case 5: refusals — duplicate id, bad verdict enum, unknown id, missing field ===
printf '%s\n' '{"ops":[{"op":"add","hypothesis":{"id":"H-1","statement":"s","proposal_ref":"p","born_run":"r","expected_signal":"e","how_to_check":"h"}}]}' > "$TMP/p5.json"
python3 "$LH" "$F" apply "$TMP/p5.json" >/dev/null 2>&1; A=$?
printf '%s\n' '{"ops":[{"op":"check","id":"H-1","run_id":"R4","verdict":"amazing","evidence":"e"}]}' > "$TMP/p6.json"
python3 "$LH" "$F" apply "$TMP/p6.json" >/dev/null 2>&1; B=$?
printf '%s\n' '{"ops":[{"op":"status","id":"H-9","status":"built"}]}' > "$TMP/p7.json"
python3 "$LH" "$F" apply "$TMP/p7.json" >/dev/null 2>&1; C=$?
printf '%s\n' '{"ops":[{"op":"add","hypothesis":{"id":"H-2","statement":"s"}}]}' > "$TMP/p8.json"
python3 "$LH" "$F" apply "$TMP/p8.json" >/dev/null 2>&1; D=$?
if [ "$A$B$C$D" = "2222" ]; then ok "refusals: dup id / bad enum / unknown id / missing fields"
else no "refusals  (got: $A$B$C$D)"; fi

# === Case 6: a refused apply leaves the tracker unchanged (atomicity) ===
if python3 "$LH" "$F" validate >/dev/null && python3 "$LH" "$F" list | grep -c "^H-" | grep -q "^1$"; then
  ok "refused apply left tracker intact (1 hypothesis, still valid)"; else no "atomicity"; fi

echo "----"; echo "t62_learn_hypotheses: $pass passed, $fail failed"; [ "$fail" = 0 ]
