#!/usr/bin/env bash
# T76 — the SPEC as the run's product (spec re-aim 2026-08-30). The loop no longer writes a paper: every
# (re-)author of HANDOFF.md is a new version of the run's DELIVERABLE, and the terminal spec_freeze stage
# distils the settled one. This test covers the half t16 does not — the per-round VERSIONING that makes
# "how the specification evolved" a first-class on-disk record rather than something an LLM narrates later:
#   (1) bin/spec_ledger.sh derives every field mechanically, UPSERTs by round, and is tolerant of absent inputs
#   (2) spec/research.js snapshots HANDOFF.md -> SPEC/SPEC-v<N>.md inside generateHandoff, after the hardener
#   (3) the SPEC-FREEZE rubric consumes that chain and must report honestly on whether the spec improved
# Run: bash tests/t76_spec_freeze.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEDGER="$ROOT/bin/spec_ledger.sh"
SPEC="$ROOT/spec/research.js"
SF="$ROOT/spec/spawn-prompts/SPEC-FREEZE.md"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1  --  $2"; fail=$((fail+1)); }
chk(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else no "$1" "$2"; fi }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# assert_row <label> <ws> <round> <<PYX ... PYX — the row is loaded FROM DISK inside the heredoc as `r`,
# so no ledger JSON is ever interpolated through a shell string (that quoting is where this used to break).
assert_row(){
  local label="$1" ws="$2" rnd="$3" body prog out
  body="$(cat)"
  prog="import json, os, hashlib
ws, rnd = os.environ['WS'], int(os.environ['RND'])
d = json.load(open(os.path.join(ws, 'SPEC', 'spec-ledger.json')))
r = [x for x in d['rows'] if x['round'] == rnd][0]
$body"
  if out="$(WS="$ws" RND="$rnd" python3 -c "$prog" 2>&1)"; then ok "$label"; else no "$label" "$(printf '%s' "$out" | tail -2)"; fi
}

# ── (1) bin/spec_ledger.sh ────────────────────────────────────────────────────────────────────────
WS="$TMP/ws"; mkdir -p "$WS/SPEC"
printf '# spec v0\n' > "$WS/SPEC/SPEC-v0.md"

# 1a. every optional input absent -> nulls, never a crash (TOLERANT BY DESIGN)
out="$(bash "$LEDGER" "$WS" 0 2>&1)"; rc=$?
[ $rc -eq 0 ] && [ "${out#OK}" != "$out" ] && ok "bare workspace (no ambition/scale/concern files) -> OK, no crash" \
  || no "bare workspace should not crash" "rc=$rc out=$out"
assert_row "absent inputs yield nulls, not invented values" "$WS" 0 <<'PYX'
assert r['ambition']['source'] == 'none' and r['ambition']['central_result'] is None
assert r['scale']['criteria_n'] is None and r['concerns']['open_n'] == 0
assert r['changed_since_prev'] is None
PYX

# 1b. with the real sidecars present, every field is DERIVED from them (no reasoning, no re-typing)
printf '{"central_result":"X beats Y","title_promise":"T","scope":["a","b"],"named_rivals":["r1"]}' > "$WS/HANDOFF.ambition.locked.json"
printf '{"criteria":{"K1":{},"K2":{},"K3":{}}}' > "$WS/HANDOFF.scale-contract.locked.json"
printf '{"open_concerns":[{"id":"K1","status":"open","severity":"major","closed_round":null},{"id":"K2","status":"open","severity":"minor","closed_round":null},{"id":"K3","status":"open","severity":"major","closed_round":2}]}' > "$WS/TASK_STATUS.concerns.json"
bash "$LEDGER" "$WS" 0 >/dev/null 2>&1
assert_row "ambition/scale/concern fields derived from the on-disk sidecars" "$WS" 0 <<'PYX'
assert r['ambition']['source'] == 'locked' and r['ambition']['central_result'] == 'X beats Y'
assert r['ambition']['scope_n'] == 2 and r['ambition']['named_rivals_n'] == 1
assert r['ambition']['raised_above_floor'] is False
assert r['scale']['criteria_n'] == 3 and r['scale']['criteria_ids'] == ['K1', 'K2', 'K3']
assert r['concerns']['open_n'] == 2, r['concerns']          # the closed_round row is excluded
assert r['concerns']['open_major_n'] == 1 and r['concerns']['open_major_ids'] == ['K1']
PYX

# 1c. an EARNED raise (target.json present) is visible as raised_above_floor
printf '{"central_result":"X beats Y AND Z","title_promise":"T+","scope":["a","b","c"],"named_rivals":["r1","r2"]}' > "$WS/HANDOFF.ambition.target.json"
printf '# spec v1 (bolder)\n' > "$WS/SPEC/SPEC-v1.md"
bash "$LEDGER" "$WS" 1 >/dev/null 2>&1
assert_row "an earned raise (target.json) is recorded as raised_above_floor + the target's own values" "$WS" 1 <<'PYX'
assert r['ambition']['source'] == 'target' and r['ambition']['raised_above_floor'] is True
assert r['ambition']['central_result'] == 'X beats Y AND Z' and r['ambition']['scope_n'] == 3
PYX
assert_row "changed_since_prev is derived from the sha, not asserted" "$WS" 1 <<'PYX'
assert r['changed_since_prev'] is True
PYX

# 1d. UPSERT: re-authoring the SAME round replaces its row (rescue loopback / amplifier re-entry)
before="$(python3 -c "import json;print(len(json.load(open('$WS/SPEC/spec-ledger.json'))['rows']))")"
printf '# spec v1 (re-authored in the same round)\n' > "$WS/SPEC/SPEC-v1.md"
bash "$LEDGER" "$WS" 1 >/dev/null 2>&1
after="$(python3 -c "import json;print(len(json.load(open('$WS/SPEC/spec-ledger.json'))['rows']))")"
[ "$before" = "$after" ] && ok "re-authoring the same round UPSERTs (one row per round, never a duplicate)" \
  || no "same-round re-author duplicated a row" "before=$before after=$after"
assert_row "the UPSERTed row carries the NEW sha (the replacement is real, not a no-op)" "$WS" 1 <<'PYX'
h = hashlib.sha256(open(os.path.join(ws, 'SPEC', 'SPEC-v1.md'), 'rb').read()).hexdigest()
assert r['spec_sha256'] == h
PYX

# 1e. a missing snapshot is a LOUD failure, not a silent empty row
out="$(bash "$LEDGER" "$WS" 9 2>&1)"; rc=$?
[ $rc -eq 2 ] && echo "$out" | grep -q ERROR && ok "missing SPEC-v<N>.md snapshot -> exit 2 + ERROR (fails loud)" \
  || no "missing snapshot should fail loud" "rc=$rc out=$out"
bash "$LEDGER" >/dev/null 2>&1; rc=$?
[ $rc -eq 2 ] && ok "bad args -> exit 2" || no "bad args should exit 2" "rc=$rc"

# ── (2) spec/research.js wiring: the snapshot happens on EVERY (re-)author ────────────────────────
chk "generateHandoff snapshots HANDOFF.md into SPEC/SPEC-v<round>.md" \
  "grep -qF 'SPEC/SPEC-v\${state.loop_round}.md' '$SPEC'"
chk "the snapshot calls bin/spec_ledger.sh (accounting in code, not in an L0 reproduction)" \
  "grep -qF 'bin/spec_ledger.sh' '$SPEC' && test -x '$LEDGER'"
chk "the snapshot runs AFTER the work-order hardener's last edit" \
  "S='$SPEC' python3 - <<'PY'
import os,sys
src=open(os.environ['S']).read()
i=src.find(\"tallyBudget(state, 'workorder_harden'\")
j=src.find('spec_ledger.sh', i)
sys.exit(0 if 0 <= i < j else 1)
PY"
chk "a spec_versioned event is logged per round" "grep -qF \"logEvent('spec_versioned'\" '$SPEC'"

# ── (3) the SPEC-FREEZE rubric consumes the chain and must not flatter it ─────────────────────────
chk "SPEC-FREEZE reads the version chain + the ledger" \
  "grep -qF 'SPEC/spec-ledger.json' '$SF' && grep -qF 'SPEC-v' '$SF'"
chk "SPEC-FREEZE requires a per-round AMBITION and RIGOR delta" \
  "grep -qF 'AMBITION delta' '$SF' && grep -qF 'RIGOR delta' '$SF'"
chk "SPEC-FREEZE forces an honest closing verdict on improved-vs-narrowed" \
  "grep -qF 'did this specification get more ambitious and more rigorous, or' '$SF'"
chk "SPEC-FREEZE names an un-evidenced loosening a defect" \
  "grep -qF 'an un-evidenced loosening is a defect' '$SF'"

echo "----"
echo "t76_spec_freeze: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
