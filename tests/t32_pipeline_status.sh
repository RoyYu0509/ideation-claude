#!/usr/bin/env bash
# t32 — bin/pipeline_status.sh: the deterministic LEDGER-derived pipeline oracle + ship-gate (RC-10 / option A).
# Regression for the 2026-06-20 run (neural-operator-aposteriori-reliability) where the L0 reproduction
# advanced straight to "ship" while skipping the env-stage `git init` AND the post-review finishing stages.
# Since the spec re-aim (2026-08-30) the finishing chain is TWO mandatory stages — verify_final then
# spec_freeze — and the run's deliverable is SPEC-FINAL.md, not a manuscript. Option A: status is the L0-owned
# ledger milestone-state.json (stages[name]={completed_at, paper_commit}); the oracle requires each required
# stage to have an entry whose paper_commit RESOLVES to a real commit in ws/paper (a fabricated sha fails), AND
# it independently checks the deliverable is on disk (a ledger entry alone must not bless an empty run).
# Run standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk(){ if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
S="$ROOT/bin/pipeline_status.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# capture stdout + exit code WITHOUT piping the oracle into grep (it exits 1 when not-ready, which would
# poison `oracle | grep` under `set -o pipefail`).
run(){ OUT="$(bash "$S" "$@" 2>/dev/null)"; RC=$?; }
has(){ printf '%s\n' "$OUT" | grep -q "$1"; }

mk_git_ws(){   # every paper folder is a git repo (the env-stage guarantee)
  local ws="$1"; mkdir -p "$ws/paper" "$ws/code"
  for d in "$ws" "$ws/paper" "$ws/code"; do
    git -C "$d" init -q
    git -C "$d" -c user.email=t@t -c user.name=t commit -qm base --allow-empty
  done
}
mk_backbone(){  # handoff..review backbone so CURRENT lands on the finishing chain, not earlier
  local ws="$1"; mkdir -p "$ws/EXPERIMENTS/ENV_READY" "$ws/REVIEW" "$ws/SPEC"
  echo x > "$ws/HANDOFF.md"; echo x > "$ws/EXPERIMENTS/results_master.json"
  echo x > "$ws/SPEC/SPEC-v0.md"; echo x > "$ws/REVIEW/round1_reviews.md"
}
mk_deliverable(){ echo x > "$1/SPEC-FINAL.md"; }   # the run's ONE deliverable (checked independently of the ledger)
# ledger <ws> <stages-csv> [--forge <stage>] [--surfaced <stage>:<n>]
# writes milestone-state.json with stages[*].paper_commit = the REAL ws/paper HEAD, except --forge sets a
# bogus (non-resolving) sha for one stage.
ledger(){
  local ws="$1" list="$2"; shift 2
  local forge="" surf=""
  while [ $# -gt 0 ]; do case "$1" in
    --forge) forge="$2"; shift 2;; --surfaced) surf="$2"; shift 2;; *) shift;; esac; done
  WS="$ws" LIST="$list" FORGE="$forge" SURF="$surf" python3 - <<'PY'
import os, json, subprocess
ws=os.environ["WS"]; lst=[s for s in os.environ["LIST"].split(",") if s]
forge=os.environ.get("FORGE",""); surf=os.environ.get("SURF","")
head=subprocess.run(["git","-C",os.path.join(ws,"paper"),"rev-parse","HEAD"],
                    capture_output=True,text=True).stdout.strip()
ss,sn=(surf.split(":")+[""])[:2]
d={"schema":"auto-research-milestone@1","milestones":{},"stages":{}}
for s in lst:
    e={"completed_at":"t","paper_commit":("0"*40 if s==forge else head)}
    if s==ss and sn: e["surfaced"]=int(sn)
    d["stages"][s]=e
json.dump(d, open(os.path.join(ws,"milestone-state.json"),"w"))
PY
}

# Case 1: regression shape — no git + no ledger -> NOT ship-ready (exit 1)
ws1="$TMP/regression"; mkdir -p "$ws1/paper" "$ws1/code"; mk_backbone "$ws1"
run "$ws1"
chk "regression (no git, no ledger) -> SHIP_READY no" "has '^SHIP_READY no\$'"
chk "regression -> exit 1"                            "[ \"\$RC\" -eq 1 ]"
chk "regression -> MISSING git + both terminal stages" \
  "has '^MISSING .*git' && has 'verify_final' && has 'spec_freeze'"
chk "regression -> CURRENT verify_final"              "has '^CURRENT verify_final\$'"
chk "regression -> retired writing stages are NOT reported at all" \
  "! has 'freeze_findings' && ! has '^story ' && ! has '^figures ' && ! has '^edit '"

# Case 2: complete — git + ledger with both terminal stages @ real HEAD + the deliverable -> ship-ready
ws2="$TMP/complete"; mk_git_ws "$ws2"; mk_backbone "$ws2"; mk_deliverable "$ws2"
ledger "$ws2" verify_final,spec_freeze
run "$ws2"
chk "complete (ledger, real commits, deliverable) -> SHIP_READY yes" "has '^SHIP_READY yes\$'"
chk "complete -> exit 0"                                "[ \"\$RC\" -eq 0 ]"
chk "complete -> CURRENT ship"                          "has '^CURRENT ship\$'"
chk "spec version chain reported from SPEC/"            "has '^spec_versions PRESENT'"

# Case 3: DELIVERABLE BELT — the ledger says spec_freeze ran, but SPEC-FINAL.md is gone -> blocks anyway.
# This is the silent-collapse class the oracle exists for: a recorded stage must not bless an empty run.
rm -f "$ws2/SPEC-FINAL.md"
run "$ws2"
chk "ledger complete but deliverable missing -> SHIP_READY no" "has '^SHIP_READY no\$'"
chk "missing deliverable is named in MISSING"                  "has '^MISSING .*SPEC-FINAL.md'"
mk_deliverable "$ws2"

# Case 4: spec_freeze has no ledger entry -> blocks on it
ledger "$ws2" verify_final
run "$ws2"
chk "spec_freeze entry missing -> SHIP_READY no" "has '^SHIP_READY no\$'"
chk "spec_freeze entry missing -> CURRENT spec_freeze" "has '^CURRENT spec_freeze\$'"

# Case 5: PROVENANCE — ledger entry exists but paper_commit is a FORGED sha -> ABSENT (blocks)
ws5="$TMP/forged"; mk_git_ws "$ws5"; mk_backbone "$ws5"; mk_deliverable "$ws5"
ledger "$ws5" verify_final,spec_freeze --forge spec_freeze
run "$ws5"
chk "forged spec_freeze sha (does not resolve) -> SHIP_READY no" "has '^SHIP_READY no\$'"
chk "forged sha -> spec_freeze ABSENT (does not resolve)" "has 'spec_freeze ABSENT .*resolve'"

# Case 6: do-no-harm — a stage that ran-and-surfaced still has a real entry -> ships
ws6="$TMP/surfaced"; mk_git_ws "$ws6"; mk_backbone "$ws6"; mk_deliverable "$ws6"
ledger "$ws6" verify_final,spec_freeze --surfaced spec_freeze:3
run "$ws6"
chk "spec_freeze ran-and-surfaced (real commit) -> SHIP_READY yes" "has '^SHIP_READY yes\$'"
chk "spec_freeze surfaced count shown"                            "has 'spec_freeze PRESENT .*surfaced=3'"

# Case 7: git ok but verify_final missing -> blocks on that stage, not git
ws7="$TMP/noverify"; mk_git_ws "$ws7"; mk_backbone "$ws7"; mk_deliverable "$ws7"
ledger "$ws7" spec_freeze
run "$ws7"
chk "git ok but verify_final entry missing -> MISSING verify_final, not git" \
  "has '^SHIP_READY no\$' && has '^MISSING .*verify_final' && ! has '^MISSING .*git'"

# Case 8: bad args -> exit 2
run;                       chk "no workspace arg -> exit 2"        "[ \"\$RC\" -eq 2 ]"
run "$TMP/does-not-exist"; chk "nonexistent workspace -> exit 2"   "[ \"\$RC\" -eq 2 ]"

echo "----"; echo "t32_pipeline_status: $pass passed, $fail failed"; [ "$fail" = 0 ]
