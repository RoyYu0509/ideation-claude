#!/usr/bin/env bash
# t65 — bin/learn_quality_ledger.py roundtrip + refusals. Proves: init/list/validate/apply lifecycle,
# the mechanized grounding rule (a verdict needs evidence; all-unassessed needs a reason), closed-enum
# and unknown-key refusals, record idempotence via if_exists:"amend", atomic refused-apply, and the
# deterministic TREND/ARC lines that make "N of M runs 诚实收窄" a quotable cross-run evidence anchor.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
QL="$ROOT/bin/learn_quality_ledger.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
F="$TMP/quality-ledger.json"

mkrun() {  # mkrun <run_id> <e2e_verdict> -> a full valid record on stdout
  cat <<EOF
{"run_id":"$1","slug":"s-$1","recorded_at":"2026-07-07T00:00:00Z","recorded_by":"backfill",
 "retro_ref":null,
 "run_facts":{"final_status":"shipped","exit_reason":"clean","loop_rounds":3,"venue":"SISC"},
 "claim_arc":{"end_to_end_verdict":"$2","evidence":"dossier quote @ dev/learning/x.md"},
 "ambition":{"seed_to_contract":"faithful","amplifier_arc":"never-fired","evidence":"no amplify events in run-events.jsonl"},
 "terminal":{"route":"clean","outcome":"shipped"},
 "venue_bar":{"cold_verdict":"not-shipped","delta":"无法比对","evidence":"pre-upgrade run: no cold reader existed"},
 "ideation_pool":{"snapshot":"absent-pre-upgrade","ceiling_verdict":"证据过期","evidence":"manifest a-candidate-pool count=0"}}
EOF
}

# === Case 1: init + validate + refuse re-init ===
python3 "$QL" "$F" init >/dev/null && python3 "$QL" "$F" validate >/dev/null
python3 "$QL" "$F" init >/dev/null 2>&1; R=$?
if [ -f "$F" ] && [ "$R" = "2" ]; then ok "init + validate + refuse overwrite"; else no "init/validate/overwrite"; fi

# === Case 2: record roundtrip -> list shows the row ===
printf '{"ops":[{"op":"record","run":%s}]}' "$(mkrun R1 保真)" > "$TMP/p1.json"
python3 "$QL" "$F" apply "$TMP/p1.json" >/dev/null
if python3 "$QL" "$F" list | grep -q "R1.*clean/shipped.*claim=保真"; then
  ok "record roundtrip -> listed"; else no "record roundtrip"; fi

# === Case 3: duplicate run_id refused; if_exists:"amend" merges instead ===
printf '{"ops":[{"op":"record","run":%s}]}' "$(mkrun R1 换题)" > "$TMP/p2.json"
python3 "$QL" "$F" apply "$TMP/p2.json" >/dev/null 2>&1; A=$?
printf '{"ops":[{"op":"record","if_exists":"amend","run":{"run_id":"R1","claim_arc":{"end_to_end_verdict":"诚实收窄","evidence":"corrected quote"}}}]}' > "$TMP/p3.json"
python3 "$QL" "$F" apply "$TMP/p3.json" >/dev/null 2>&1; B=$?
if [ "$A" = "2" ] && [ "$B" = "0" ] && python3 "$QL" "$F" list | grep -q "claim=诚实收窄"; then
  ok "duplicate refused; if_exists:amend merges (section-level)"; else no "record idempotence ($A/$B)"; fi

# === Case 4: grounding rule — verdict without evidence refused; unassessed without reason refused ===
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"claim_arc":{"end_to_end_verdict":"保真"}}}]}' > "$TMP/p4.json"
python3 "$QL" "$F" apply "$TMP/p4.json" >/dev/null 2>&1; A=$?
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"claim_arc":{"end_to_end_verdict":"unassessed"}}}]}' > "$TMP/p5.json"
python3 "$QL" "$F" apply "$TMP/p5.json" >/dev/null 2>&1; B=$?
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"claim_arc":{"end_to_end_verdict":"unassessed","unassessed_reason":"run died pre-loop"}}}]}' > "$TMP/p6.json"
python3 "$QL" "$F" apply "$TMP/p6.json" >/dev/null 2>&1; C=$?
if [ "$A$B$C" = "220" ]; then ok "grounding rule mechanized (evidence / unassessed_reason)"
else no "grounding rule (got: $A$B$C)"; fi

# === Case 5: refusals — bad enum, unknown top-level key, unknown run_id, missing section ===
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"claim_arc":{"end_to_end_verdict":"amazing","evidence":"e"}}}]}' > "$TMP/p7.json"
python3 "$QL" "$F" apply "$TMP/p7.json" >/dev/null 2>&1; A=$?
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"quality_score":9}}]}' > "$TMP/p8.json"
python3 "$QL" "$F" apply "$TMP/p8.json" >/dev/null 2>&1; B=$?
printf '{"ops":[{"op":"amend","run_id":"R9","run":{"notes":"x"}}]}' > "$TMP/p9.json"
python3 "$QL" "$F" apply "$TMP/p9.json" >/dev/null 2>&1; C=$?
printf '{"ops":[{"op":"record","run":{"run_id":"R2","recorded_at":"t","recorded_by":"owner"}}]}' > "$TMP/p10.json"
python3 "$QL" "$F" apply "$TMP/p10.json" >/dev/null 2>&1; D=$?
if [ "$A$B$C$D" = "2222" ]; then ok "refusals: bad enum / unknown key (no numeric scores) / unknown run / missing sections"
else no "refusals (got: $A$B$C$D)"; fi

# === Case 6: refused apply leaves the ledger unchanged (atomicity) ===
if python3 "$QL" "$F" validate >/dev/null && [ "$(python3 "$QL" "$F" list | grep -c '^R')" = "1" ]; then
  ok "refused applies left ledger intact (1 run, still valid)"; else no "atomicity"; fi

# === Case 7: trend prints deterministic TREND + oldest->newest ARC over a 3-run fixture ===
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"claim_arc":{"end_to_end_verdict":"保真","evidence":"q1"}}},{"op":"record","run":%s},{"op":"record","run":%s}]}' \
  "$(mkrun R2 诚实收窄)" "$(mkrun R3 诚实收窄)" > "$TMP/p11.json"
python3 "$QL" "$F" apply "$TMP/p11.json" >/dev/null
T="$(python3 "$QL" "$F" trend)"
if echo "$T" | grep -q "TREND end_to_end: 诚实收窄=2 保真=1" \
   && echo "$T" | grep -q "ARC end_to_end (oldest->newest): 保真,诚实收窄,诚实收窄"; then
  ok "trend: deterministic TREND tally + ARC line (the quotable cross-run anchor)"; else no "trend output"; fi

# === Case 8: capture hygiene — died_mid_run requires its mechanical cause; other routes stay legal ===
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"terminal":{"route":"died_mid_run","outcome":"unfinished"}}}]}' > "$TMP/p12.json"
python3 "$QL" "$F" apply "$TMP/p12.json" >/dev/null 2>&1; A=$?
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"terminal":{"route":"died_mid_run","outcome":"unfinished","cause":"env_transient"}}}]}' > "$TMP/p13.json"
python3 "$QL" "$F" apply "$TMP/p13.json" >/dev/null 2>&1; B=$?
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"terminal":{"route":"died_mid_run","outcome":"unfinished","cause":"transient-ish"}}}]}' > "$TMP/p14.json"
python3 "$QL" "$F" apply "$TMP/p14.json" >/dev/null 2>&1; C=$?
printf '{"ops":[{"op":"amend","run_id":"R1","run":{"terminal":{"route":"clean","outcome":"shipped"}}}]}' > "$TMP/p15.json"
python3 "$QL" "$F" apply "$TMP/p15.json" >/dev/null 2>&1; D=$?
if [ "$A$B$C$D" = "2020" ]; then
  ok "died_mid_run without cause refused; with closed-set cause OK; bad cause refused; cause optional elsewhere"
else no "died_mid_run cause rule (got: $A$B$C$D)"; fi

echo "----"; echo "t65_quality_ledger: $pass passed, $fail failed"; [ "$fail" = 0 ]
