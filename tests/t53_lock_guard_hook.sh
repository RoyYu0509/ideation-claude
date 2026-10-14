#!/usr/bin/env bash
# T53 — hooks/lock_guard.py: the PreToolUse guard that makes overwriting a FROZEN ratchet baseline
# structurally impossible (B4-17). It denies Write/Edit/MultiEdit to the two Phase-0(C) locked baselines
# (owned exclusively by bin/lock_contracts.sh) but leaves the producing-worker's legitimate
# AUDIT-ARTIFACTS.locked.json appends, HANDOFF.md writes, and the amplifier's target.json untouched.
# Run: bash tests/t53_lock_guard_hook.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="$ROOT/hooks/lock_guard.py"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

deny_p(){ echo "$1" | python3 "$GUARD" 2>/dev/null | grep -q '"permissionDecision": "deny"'; }

# 1) DENY a Write to the scale-contract baseline (the WEAKEN-TO-PASS poisoning vector)
deny_p '{"tool_input":{"file_path":"/x/runs/p/HANDOFF.scale-contract.locked.json"}}' \
  && ok "DENY Write to HANDOFF.scale-contract.locked.json" || no "scale-contract baseline not denied"

# 2) DENY the ambition baseline too
deny_p '{"tool_input":{"file_path":"/x/runs/p/HANDOFF.ambition.locked.json"}}' \
  && ok "DENY Write to HANDOFF.ambition.locked.json" || no "ambition baseline not denied"

# 3) ALLOW AUDIT-ARTIFACTS.locked.json (producing-worker's legitimate register append — NOT a glob deny)
out="$(echo '{"tool_input":{"file_path":"/x/runs/p/AUDIT-ARTIFACTS.locked.json"}}' | python3 "$GUARD" 2>/dev/null)"; rc=$?
[ -z "$out" ] && [ $rc -eq 0 ] && ok "ALLOW AUDIT-ARTIFACTS.locked.json (silent, exit 0)" || no "audit-artifact register wrongly gated (out='$out' rc=$rc)"

# 4) ALLOW HANDOFF.md (the re-authored work order itself) + the amplifier's target file
out="$(echo '{"tool_input":{"file_path":"/x/runs/p/HANDOFF.md"}}' | python3 "$GUARD" 2>/dev/null)"
[ -z "$out" ] && ok "ALLOW HANDOFF.md" || no "HANDOFF.md wrongly gated"
out="$(echo '{"tool_input":{"file_path":"/x/runs/p/HANDOFF.ambition.target.json"}}' | python3 "$GUARD" 2>/dev/null)"
[ -z "$out" ] && ok "ALLOW HANDOFF.ambition.target.json (amplifier write)" || no "amplifier target wrongly gated"

# 5) fail-open on unparseable stdin (blast radius stays narrow)
out="$(echo 'not json' | python3 "$GUARD" 2>/dev/null)"; rc=$?
[ -z "$out" ] && [ $rc -eq 0 ] && ok "unparseable stdin => fail-open allow" || no "unparseable stdin not fail-open"

# 6) registered in hooks/hooks.json under the Write|Edit|MultiEdit matcher
grep -q "lock_guard.sh" "$ROOT/hooks/hooks.json" && ok "lock_guard.sh registered in hooks.json" || no "not registered in hooks.json"

echo "----"; echo "t53_lock_guard_hook: $pass passed, $fail failed"; [ "$fail" = 0 ]
