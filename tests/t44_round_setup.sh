#!/usr/bin/env bash
# T44 — bin/round_setup.sh: the DETERMINISTIC per-round disclosure freeze + fail-loud hard-stop that
# replaces the inline-JS block the L0 skipped (taking the throw with it, so .round-1.* never existed).
# Run: bash tests/t44_round_setup.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RS="$ROOT/bin/round_setup.sh"
SPEC="$ROOT/spec/research.js"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
WS="$TMP/runs/p"; mkdir -p "$WS"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

# 1) bad args => exit 2
bash "$RS" "$WS" >/dev/null 2>&1; [ $? -eq 2 ] && ok "missing <round> => exit 2" || no "missing round not refused"
bash "$RS" "$WS" abc >/dev/null 2>&1; [ $? -eq 2 ] && ok "non-numeric <round> => exit 2" || no "non-numeric round not refused"

# 2) writes BOTH markers; concern snapshot derived from TASK_STATUS.concerns.json
printf '{"open_concerns":[{"id":"K1","status":"open"},{"id":"K2","status":"open"}]}' > "$WS/TASK_STATUS.concerns.json"
bash "$RS" "$WS" 1 >/dev/null 2>&1 && [ -f "$WS/.round-1.start" ] && [ -f "$WS/.round-1.concerns.json" ] \
  && ok ".round-1.start + .round-1.concerns.json written" || no "round markers not written"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['round']==1 and len(d['open_concerns'])==2" "$WS/.round-1.concerns.json" 2>/dev/null \
  && ok "snapshot froze the 2 open concerns" || no "snapshot content wrong"

# 3) IDEMPOTENT freeze: mutating the live ledger + re-running leaves the snapshot BYTE-IDENTICAL
S1=$(shasum "$WS/.round-1.concerns.json" | cut -d' ' -f1)
M1=$(stat -f %m "$WS/.round-1.start" 2>/dev/null || stat -c %Y "$WS/.round-1.start")
printf '{"open_concerns":[]}' > "$WS/TASK_STATUS.concerns.json"   # live ledger drifts
sleep 1
bash "$RS" "$WS" 1 >/dev/null 2>&1
S2=$(shasum "$WS/.round-1.concerns.json" | cut -d' ' -f1)
M2=$(stat -f %m "$WS/.round-1.start" 2>/dev/null || stat -c %Y "$WS/.round-1.start")
[ "$S1" = "$S2" ] && ok "concern snapshot frozen byte-identical across resume" || no "snapshot DRIFTED on resume"
[ "$M1" = "$M2" ] && ok ".round-1.start NOT re-touched (freshness window stable)" || no ".start mtime drifted"

# 4) absent TASK_STATUS.concerns.json => empty frozen set, still succeeds
WS2="$TMP/runs/q"; mkdir -p "$WS2"
bash "$RS" "$WS2" 1 >/dev/null 2>&1 && python3 -c "import json,sys; assert json.load(open(sys.argv[1]))['open_concerns']==[]" "$WS2/.round-1.concerns.json" 2>/dev/null \
  && ok "absent live ledger => empty frozen set (exit 0)" || no "absent ledger not handled"
# (case 4's graceful absent-ledger handling stays a VALID defensive unit — round_setup must not crash on a missing
#  ledger. FIX A (P1#3) removes the *cause* of that emptiness at round 0 by SEEDING the live ledger; case 5 locks it.)

# 5) FIX A (P1#3) — the round-0 concern-ledger SEED closes the "empty round-1 disclosure set" bug. research.js is an
#    LLM-READ spec (its round-0 seed block cannot be executed here), so this has TWO halves, matching the suite idiom.
# (5a) FUNCTIONAL — a ledger written in FIX A's EXACT open_concerns row schema (one open concern per §4 K) is
#      round_setup-compatible: the freeze copies it VERBATIM into a NON-EMPTY .round-1.concerns.json. This is the
#      contrast to case 4's absent-ledger EMPTY freeze — seeding is precisely what gives round 1 a non-empty
#      disclosure set (the kill criteria the experimenter+drafter must act on).
WS3="$TMP/runs/seeded"; mkdir -p "$WS3"
printf '%s' '{"open_concerns":[{"id":"K1","concern":"H1a bound holds, ratio<=1.1","status":"open","severity":"major","opened_round":1,"closed_round":null,"last_touched_round":1,"evidence":"","source":"seed:kill_criteria (round-0 pre-registration)"},{"id":"K2","concern":"method beats baseline B by >=5%","status":"open","severity":"major","opened_round":1,"closed_round":null,"last_touched_round":1,"evidence":"","source":"seed:kill_criteria (round-0 pre-registration)"}]}' > "$WS3/TASK_STATUS.concerns.json"
bash "$RS" "$WS3" 1 >/dev/null 2>&1 \
  && python3 -c "import json,sys; d=json.load(open(sys.argv[1])); r=d['open_concerns']; assert d['round']==1 and len(r)==2 and {x['id'] for x in r}=={'K1','K2'} and all(x['severity']=='major' and x['opened_round']==1 for x in r)" "$WS3/.round-1.concerns.json" 2>/dev/null \
  && ok "FIX A seed schema freezes a NON-EMPTY .round-1 disclosure set (2 K rows, fields preserved)" || no "FIX A seeded freeze wrong/empty"
# (5b) STATIC — the round-0 seed STEP exists in research.js: ROUND-0-only + idempotent (only-if-absent), sourced from
#      parseHandoff kill_criteria, writing the canonical { open_concerns:[…] } container with the canonical row schema.
grep -qF 'if (isRound0 && !exists(`${ws}/TASK_STATUS.concerns.json`)) {' "$SPEC" \
  && ok "FIX A seed is ROUND-0-only + idempotent (isRound0 && !exists TASK_STATUS.concerns.json)" || no "FIX A guard missing"
grep -qF '(kh.kill_criteria || []).map(' "$SPEC" \
  && ok "FIX A seeds from parseHandoff kill_criteria" || no "FIX A does not source kill_criteria"
grep -qF 'writeJson(`${ws}/TASK_STATUS.concerns.json`, { open_concerns: seeded })' "$SPEC" \
  && ok "FIX A writes the canonical { open_concerns:[…] } container" || no "FIX A container wrong"
grep -qF "status: 'open', severity: 'major', opened_round: 1" "$SPEC" \
  && ok "FIX A rows carry the canonical schema (status/severity/opened_round)" || no "FIX A row schema wrong"

# 6) DE-POISON (P1#3 follow-up) — a round-0 SEED row (source:'seed:*') is PRE-REGISTERED DISCLOSURE, not an
#    OBSERVED non-convergence signal, so it must NOT drive the viability floor (majorNonConverging) OR the F1
#    forward-floor; genuine sensor-raised rows (source:'review'/verifier/…) MUST still count. The exclusion is
#    source-SCOPED (never a blanket disable) — the checks below assert seed-EXCLUDED vs sensor-COUNTED DISTINCTLY.
# (6a) FUNCTIONAL — majorNonConverging is a self-contained JS fn (deps: exists/readJson/VIABILITY_FLOOR_K). Slice
#      it out of the LLM-read spec + drive it in a vm sandbox: a seed-only major row open 3 rounds must NOT trip the
#      floor (=false), while a review-sourced major row open 3 rounds MUST (=true) — and NEITHER trips at round 2 (the
#      K=3 floor stays intact, proving this is a source-scoped exclusion, not a disable of the whole floor).
SPEC="$SPEC" node - <<'NODE' && ok "majorNonConverging EXCLUDES source:'seed:*' (seed@r3=false) yet COUNTS source:'review' (review@r3=true); K=3 floor intact (both false @r2)" || no "majorNonConverging seed-exclusion wrong (not source-scoped, or floor broken)"
const fs=require('fs'), vm=require('vm');
const src=fs.readFileSync(process.env.SPEC,'utf8');
const km=src.match(/const VIABILITY_FLOOR_K\s*=\s*(\d+)/);
if(!km){console.error('no VIABILITY_FLOOR_K const');process.exit(3);}
const start=src.indexOf('function majorNonConverging');
if(start<0){console.error('no majorNonConverging fn');process.exit(3);}
let i=src.indexOf('{',start),depth=0,end=-1;   // brace-match the fn body (its template literals only ever hold balanced ${…})
for(;i<src.length;i++){const c=src[i];if(c==='{')depth++;else if(c==='}'){depth--;if(depth===0){end=i+1;break;}}}
const fnSrc=src.slice(start,end);
function run(ledger,round){
  const ctx={exists:()=>true,readJson:()=>ledger,VIABILITY_FLOOR_K:km[1]|0,result:null};
  vm.createContext(ctx);
  vm.runInContext(fnSrc+'\nresult=majorNonConverging("/ws",'+round+');',ctx);
  return ctx.result;
}
const seed={open_concerns:[{id:'K1',concern:'x',status:'open',severity:'major',opened_round:1,closed_round:null,source:'seed:kill_criteria (round-0 pre-registration)'}]};
const review={open_concerns:[{id:'C1',concern:'x',status:'open',severity:'major',opened_round:1,closed_round:null,source:'review'}]};
const seedR3=run(seed,3), revR3=run(review,3), seedR2=run(seed,2), revR2=run(review,2);
if(seedR3===false && revR3===true && seedR2===false && revR2===false) process.exit(0);
console.error('seedR3='+seedR3+' (want false) revR3='+revR3+' (want true) seedR2='+seedR2+' (want false) revR2='+revR2+' (want false)');
process.exit(1);
NODE
# (6b) STATIC — the F1 FORWARD-FLOOR block force-mints open major concerns into HANDOFF-*/EXPERIMENTS segments; it
#      too must SKIP seed rows so a raw kill-criterion is never turned into a spurious experiment. Slice the F1 block
#      (its comment anchor → the re-scan line) and assert the source-startsWith-'seed:' guard lives INSIDE it.
awk '/F1 FORWARD-FLOOR/{f=1} f{print} /re-scan: stubs we just minted/{f=0}' "$SPEC" | grep -qF "String(r.source || '').startsWith('seed:')" \
  && ok "F1 forward-floor SKIPS source:'seed:*' rows (a pre-registered K never force-mints an experiment)" || no "F1 forward-floor missing the seed-exclusion guard"
# (6c) STATIC belt — majorNonConverging carries the SAME source-scoped predicate, confirming the 'seed:' exclusion is
#      present in BOTH sites (keyed on source startsWith 'seed:'), not a one-off.
awk '/^function runViabilityGate/{f=0} /function majorNonConverging/{f=1} f{print}' "$SPEC" | grep -qF "String(r.source || '').startsWith('seed:')" \
  && ok "majorNonConverging carries the source-scoped 'seed:' exclusion predicate" || no "majorNonConverging missing the seed-exclusion predicate"

echo "----"; echo "t44_round_setup: $pass passed, $fail failed"; [ "$fail" = 0 ]
