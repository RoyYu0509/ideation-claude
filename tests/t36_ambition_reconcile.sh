#!/usr/bin/env bash
# t36 — §4c AMBITION reconciliation at the ship-gate (bin/pipeline_status.sh).
# The §4c AMBITION CONTRACT (HANDOFF.ambition.locked.json) pins the paper's CLAIMED ambition; verify_final
# records `ambition_reconciled` (claim ≤ delivery) into the ledger. The oracle must REFUSE to ship when the
# claim over-reaches delivery (ambition_reconciled:false), even though every finishing stage ran with a real
# commit — and must stay do-no-harm for legacy ledgers that predate the field (absent ⇒ pass). Run standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk(){ if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
S="$ROOT/bin/pipeline_status.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

run(){ OUT="$(bash "$S" "$@" 2>/dev/null)"; RC=$?; }
has(){ printf '%s\n' "$OUT" | grep -q "$1"; }

mk_git_ws(){ local ws="$1"; mkdir -p "$ws/paper" "$ws/code"
  for d in "$ws" "$ws/paper" "$ws/code"; do
    git -C "$d" init -q; git -C "$d" -c user.email=t@t -c user.name=t commit -qm base --allow-empty; done; }
mk_backbone(){ local ws="$1"; mkdir -p "$ws/EXPERIMENTS/ENV_READY" "$ws/REVIEW" "$ws/SPEC"
  echo x > "$ws/HANDOFF.md"; echo x > "$ws/EXPERIMENTS/results_master.json"
  echo x > "$ws/SPEC/SPEC-v0.md"; echo x > "$ws/SPEC-FINAL.md"; echo x > "$ws/REVIEW/round1_reviews.md"; }
# ledger <ws> <recon>  — recon ∈ {true|false|absent}; both terminal stages @ real HEAD.
ledger(){ local ws="$1" recon="$2"
  WS="$ws" RECON="$recon" python3 - <<'PY'
import os, json, subprocess
ws=os.environ["WS"]; recon=os.environ["RECON"]
head=subprocess.run(["git","-C",os.path.join(ws,"paper"),"rev-parse","HEAD"],
                    capture_output=True,text=True).stdout.strip()
d={"schema":"auto-research-milestone@1","milestones":{},"stages":{}}
for s in ("verify_final","spec_freeze"):
    d["stages"][s]={"completed_at":"t","paper_commit":head}
if recon!="absent":
    d["stages"]["verify_final"]["ambition_reconciled"]=(recon=="true")
    d["stages"]["verify_final"]["ambition_gaps"]=(0 if recon=="true" else 3)
json.dump(d, open(os.path.join(ws,"milestone-state.json"),"w"))
PY
}

# Case 1: reconciled:true (claim ≤ delivery) -> ship-ready
ws1="$TMP/reconciled"; mk_git_ws "$ws1"; mk_backbone "$ws1"; ledger "$ws1" true
run "$ws1"
chk "reconciled:true  -> SHIP_READY yes"          "has '^SHIP_READY yes\$'"
chk "reconciled:true  -> exit 0"                  "[ \"\$RC\" -eq 0 ]"

# Case 2: reconciled:false (claim over-reaches delivery) -> BLOCKED, even with all stages @ real commits
ws2="$TMP/overclaim"; mk_git_ws "$ws2"; mk_backbone "$ws2"; ledger "$ws2" false
run "$ws2"
chk "reconciled:false -> SHIP_READY no"           "has '^SHIP_READY no\$'"
chk "reconciled:false -> exit 1"                  "[ \"\$RC\" -eq 1 ]"
chk "reconciled:false -> MISSING verify_final(ambition)" "has 'verify_final(ambition)'"
chk "reconciled:false -> reason names AMBITION"   "has 'AMBITION NOT reconciled'"

# Case 3: absent field (legacy ledger predates §4c) -> do-no-harm ship-ready
ws3="$TMP/legacy"; mk_git_ws "$ws3"; mk_backbone "$ws3"; ledger "$ws3" absent
run "$ws3"
chk "absent (legacy)  -> SHIP_READY yes (do-no-harm)" "has '^SHIP_READY yes\$'"
chk "absent (legacy)  -> exit 0"                  "[ \"\$RC\" -eq 0 ]"

echo "----"
echo "t36: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
