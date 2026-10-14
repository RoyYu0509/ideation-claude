#!/usr/bin/env bash
# T6X — unit-test the deterministic verdict-fidelity oracle (bin/verdict_fidelity.py), the teeth behind
# spec/research.js collectVerdicts/enforceVerdictFidelity (P-3/H-17: the 2026-07-05 retro's C1-1 — the
# terminal FINAL-REPORT flattened K2_VOID_SANITY into "differentiation CONFIRMED"). Proves: collect harvests
# the enum + its boolean siblings from code/**/results/*.json; check FAILS a report whose BODY misses the
# enum verbatim (or flattens it into confirmed/passed/clean language) and PASSES one that quotes it + carries
# the machine-verdict appendix; corrupt JSON skips NON-FATALLY; an empty workspace passes trivially
# ("none found" — a kill/abandon exit is never blocked). Run: bash tests/t6x_verdict_fidelity.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORACLE="$ROOT/bin/verdict_fidelity.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { echo "PASS  $1"; pass=$((pass+1)); }
bad() { echo "FAIL  $1"; fail=$((fail+1)); }

# A fixture workspace with a fake manifest: the audited-run shape (enum + boolean siblings), minimized.
WS="$TMP/runs/slug"; mkdir -p "$WS/code/results"
cat > "$WS/code/results/E0_manifest.json" <<'JSON'
{"schema":"x","k2_verdict":{"verdict":"K2_VOID_SANITY","all_L_hat_gt_1":true,"ours_valid_past_vacuity_all":false},"n_cells":5}
JSON

# 1. collect harvests the enum + its boolean siblings, exit 0
out="$(python3 "$ORACLE" collect "$WS")"; rc=$?
if [ $rc -eq 0 ] && echo "$out" | grep -q '"value": "K2_VOID_SANITY"' \
   && echo "$out" | grep -q '"key": "k2_verdict.ours_valid_past_vacuity_all"'; then
  ok "collect -> enum + boolean sibling, exit 0"
else bad "collect missed enum/sibling or exited $rc (out=$out)"; fi

# 2. BODY missing the enum (the C1-1 flattening signature) -> check exit 1, itemized
cat > "$TMP/flat.md" <<'MD'
# FINAL-REPORT
K2 (E0 head-to-head) = differentiation CONFIRMED on the anchors.
MD
out="$(python3 "$ORACLE" check "$TMP/flat.md" "$WS")"; rc=$?
if [ $rc -eq 1 ] && echo "$out" | grep -q 'CLAUSE(i).*K2_VOID_SANITY' && echo "$out" | grep -q 'CLAUSE(ii)'; then
  ok "flattened report -> exit 1 with CLAUSE(i)+(ii) itemized"
else bad "flattened report not caught (rc=$rc, out=$out)"; fi

# 3. BODY quotes the enum verbatim + complete appendix -> exit 0
cat > "$TMP/good.md" <<'MD'
# FINAL-REPORT
K2 (E0 head-to-head) rendered K2_VOID_SANITY (operationally void; ours_valid_past_vacuity_all=false).

## Machine verdicts (verbatim)
| file | key | value |
| code/results/E0_manifest.json | k2_verdict.verdict | K2_VOID_SANITY |
| code/results/E0_manifest.json | k2_verdict.all_L_hat_gt_1 | true |
| code/results/E0_manifest.json | k2_verdict.ours_valid_past_vacuity_all | false |
MD
out="$(python3 "$ORACLE" check "$TMP/good.md" "$WS")"; rc=$?
if [ $rc -eq 0 ]; then ok "enum-verbatim + appendix -> exit 0"
else bad "faithful report rejected (rc=$rc, out=$out)"; fi

# 4. enum in BODY but a flattening line elsewhere (token + happy word, no enum) -> CLAUSE(ii) only
cat > "$TMP/mixed.md" <<'MD'
# FINAL-REPORT
K2 rendered K2_VOID_SANITY on the corrected run.
Still, K2 differentiation was cleanly demonstrated: K2 confirmed on all anchors.

## Machine verdicts (verbatim)
| code/results/E0_manifest.json | k2_verdict.verdict | K2_VOID_SANITY |
| code/results/E0_manifest.json | k2_verdict.all_L_hat_gt_1 | true |
| code/results/E0_manifest.json | k2_verdict.ours_valid_past_vacuity_all | false |
MD
out="$(python3 "$ORACLE" check "$TMP/mixed.md" "$WS")"; rc=$?
if [ $rc -eq 1 ] && echo "$out" | grep -q 'CLAUSE(ii)' && ! echo "$out" | grep -q 'CLAUSE(i):'; then
  ok "per-verdict flattening line -> CLAUSE(ii) flagged, exit 1"
else bad "flattening line not scoped-flagged (rc=$rc, out=$out)"; fi

# 5. corrupt JSON -> NON-FATAL skip: collect still exit 0, good manifest still harvested, skipped listed
echo '{not json' > "$WS/code/results/corrupt.json"
out="$(python3 "$ORACLE" collect "$WS")"; rc=$?
if [ $rc -eq 0 ] && echo "$out" | grep -q '"value": "K2_VOID_SANITY"' \
   && echo "$out" | grep -q 'corrupt.json'; then
  ok "corrupt JSON -> non-fatal skip, harvest intact, exit 0"
else bad "corrupt JSON broke collect (rc=$rc, out=$out)"; fi
rm -f "$WS/code/results/corrupt.json"

# 6. empty workspace (no manifests at all) -> check trivially passes with 'none found'
WS2="$TMP/runs/empty"; mkdir -p "$WS2"
out="$(python3 "$ORACLE" check "$TMP/flat.md" "$WS2")"; rc=$?
if [ $rc -eq 0 ] && echo "$out" | grep -qi 'none found'; then
  ok "empty ws -> exit 0, 'none found' (terminal exit never blocked)"
else bad "empty ws blocked or missing 'none found' (rc=$rc, out=$out)"; fi

echo "----"; echo "t6x_verdict_fidelity: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
