#!/usr/bin/env bash
# T2 (mechanical companion) — unit-test the vendored freeze hook's DENY logic directly, by feeding
# check_fidelity.py a PreToolUse payload (no subagent spawn needed). The LIVE depth-L2 propagation is
# the real T2 (recorded in tests/TESTS.md); this proves the deny arithmetic is intact in the vendored
# copy and re-runnable without spawning. Run: bash tests/t2_hook_logic.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/plugins/paper-polish-ar/hooks/check_fidelity.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
mkdir -p "$TMP/.polish"
printf '%s' "{\"mode\":\"polish\",\"format\":\"latex\",\"manuscripts\":[\"$TMP/paper.tex\"]}" > "$TMP/.polish/fidelity-manifest.json"
printf 'Our method achieves an accuracy of 92.5\\%% on the benchmark.\n' > "$TMP/paper.tex"

run() { # old_string new_string -> prints hook stdout
  CLAUDE_PROJECT_DIR="$TMP" python3 - "$HOOK" "$1" "$2" <<'PY'
import sys, json, subprocess, os
hook, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
payload = {"tool_name":"Edit","cwd":os.environ["CLAUDE_PROJECT_DIR"],
           "tool_input":{"file_path":os.path.join(os.environ["CLAUDE_PROJECT_DIR"],"paper.tex"),
                         "old_string":old,"new_string":new}}
p = subprocess.run(["python3",hook], input=json.dumps(payload), text=True, capture_output=True)
sys.stdout.write(p.stdout)
PY
}

# 1. Dropping the frozen number 92.5 -> DENY
out="$(run 'accuracy of 92.5\%' 'accuracy of 97.3\%')"
if echo "$out" | grep -q '"permissionDecision": *"deny"' && echo "$out" | grep -q '92.5'; then
  echo "PASS  drop frozen 92.5 -> deny"; pass=$((pass+1)); else echo "FAIL  drop 92.5 (out=$out)"; fail=$((fail+1)); fi

# 2. Rewording AROUND the frozen number (92.5 preserved) -> ALLOW (no deny output)
out="$(run 'achieves an accuracy of 92.5\%' 'attains an accuracy of 92.5\%')"
if echo "$out" | grep -q 'deny'; then echo "FAIL  reword-around wrongly denied (out=$out)"; fail=$((fail+1));
  else echo "PASS  reword preserving 92.5 -> allow"; pass=$((pass+1)); fi

# 3. No manifest -> silent no-op (allow) even when dropping a number
rm -f "$TMP/.polish/fidelity-manifest.json"
out="$(run 'accuracy of 92.5\%' 'accuracy of 97.3\%')"
if echo "$out" | grep -q 'deny'; then echo "FAIL  no-manifest should be no-op (out=$out)"; fail=$((fail+1));
  else echo "PASS  no manifest -> silent no-op"; pass=$((pass+1)); fi

echo "----"; echo "t2_hook_logic: $pass passed, $fail failed"; [ "$fail" = 0 ]
