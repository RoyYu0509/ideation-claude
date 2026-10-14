#!/usr/bin/env bash
# T33 — unit-test the deterministic SHIP-GATE hook's DENY logic directly (hooks/ship_gate.py), by feeding it
# PreToolUse payloads (no subagent spawn). RC-11: this is the harness-level backstop for the silent
# finishing-collapse that the in-spec assertShipReady (RC-10) could not stop, because the 2026-06-21 run had
# L0 skip ship() entirely and improvise a FINAL-REPORT.md. The hook moves the SAME pipeline_status.sh oracle
# OUTSIDE the L0 reproduction. This test proves: the banned combined-finishing file is always denied; the
# workspace FINAL-REPORT.md is denied when finishing never ran and allowed when the ledger is complete; and
# unrelated / non-workspace writes pass straight through. Run: bash tests/t33_ship_gate.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/hooks/ship_gate.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

gitq() { git -c user.email=t@t.t -c user.name=t -C "$1" "${@:2}" >/dev/null 2>&1; }

# A realistic workspace: runs/<slug> + paper/ + code/ git repos with a baseline commit, plus the L0 ledger.
WS="$TMP/runs/slug"; mkdir -p "$WS/paper" "$WS/code"
gitq "$WS" init; gitq "$WS" commit --allow-empty -m base
gitq "$WS/paper" init; gitq "$WS/paper" commit --allow-empty -m base
gitq "$WS/code" init;  gitq "$WS/code"  commit --allow-empty -m base

run() { # file_path -> hook stdout (CLAUDE_PLUGIN_ROOT points at the repo so bin/ + config are reachable)
  CLAUDE_PLUGIN_ROOT="$ROOT" CLAUDE_PROJECT_DIR="$TMP" python3 - "$HOOK" "$1" <<'PY'
import sys, json, subprocess
hook, fp = sys.argv[1], sys.argv[2]
payload = {"tool_name":"Write","tool_input":{"file_path":fp,"content":"x"}}
p = subprocess.run(["python3",hook], input=json.dumps(payload), text=True, capture_output=True)
sys.stdout.write(p.stdout)
PY
}
denied() { echo "$1" | grep -q '"permissionDecision": *"deny"'; }

# 1. FINISHING_REPORT.md anywhere -> DENY (the regression signature)
out="$(run "$WS/FINISHING_REPORT.md")"
if denied "$out"; then echo "PASS  FINISHING_REPORT.md -> deny"; pass=$((pass+1)); else echo "FAIL  FINISHING_REPORT.md not denied (out=$out)"; fail=$((fail+1)); fi

# 2. Unrelated write -> ALLOW (no output)
out="$(run "$TMP/notes.txt")"
if [ -z "$out" ]; then echo "PASS  unrelated write -> allow"; pass=$((pass+1)); else echo "FAIL  unrelated write not allowed (out=$out)"; fail=$((fail+1)); fi

# 3. FINAL-REPORT.md in a NON-workspace dir (no milestone-state.json) -> ALLOW
out="$(run "$TMP/FINAL-REPORT.md")"
if [ -z "$out" ]; then echo "PASS  FINAL-REPORT.md non-workspace -> allow"; pass=$((pass+1)); else echo "FAIL  non-workspace FINAL-REPORT denied (out=$out)"; fail=$((fail+1)); fi

# 4. FINAL-REPORT.md in a workspace with NO finishing ledger -> DENY (finishing never ran)
echo '{"schema":"auto-research-milestone@1","paper_slug":"slug","stages":{}}' > "$WS/milestone-state.json"
out="$(run "$WS/FINAL-REPORT.md")"
if denied "$out"; then echo "PASS  ws without finishing ledger -> deny"; pass=$((pass+1)); else echo "FAIL  empty-ledger ship not denied (out=$out)"; fail=$((fail+1)); fi

# 5. FINAL-REPORT.md in a workspace with a COMPLETE finishing ledger (resolvable shas) -> ALLOW
SHA="$(git -C "$WS/paper" rev-parse HEAD)"
python3 - "$WS/milestone-state.json" "$SHA" <<'PY'
import json,sys
p,sha=sys.argv[1],sys.argv[2]
d=json.load(open(p)); d["stages"]={s:{"completed_at":"t","paper_commit":sha} for s in
  ["verify_final","freeze_findings","story","write","figures","edit","freeze"]}; json.dump(d,open(p,"w"))
PY
out="$(run "$WS/FINAL-REPORT.md")"
if [ -z "$out" ]; then echo "PASS  ws with complete ledger -> allow"; pass=$((pass+1)); else echo "FAIL  complete-ledger ship denied (out=$out)"; fail=$((fail+1)); fi

echo "----"; echo "t33_ship_gate: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
