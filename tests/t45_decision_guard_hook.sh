#!/usr/bin/env bash
# T45 — hooks/decision_guard.py: the PreToolUse guard that makes a subagent-authored gate resolution
# structurally impossible (this run: an L1 wrote DECISIONS-RESOLVED-7.md itself while running). It denies a
# Write/Edit to DECISIONS-RESOLVED-* but leaves L0's DECISIONS-PENDING.md writes + the bin/ `mv` untouched.
# Run: bash tests/t45_decision_guard_hook.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="$ROOT/hooks/decision_guard.py"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

deny_p(){ echo "$1" | python3 "$GUARD" 2>/dev/null | grep -q '"permissionDecision": "deny"'; }

# 1) DENY a RESOLVED write (the L1 self-resolve)
deny_p '{"tool_input":{"file_path":"/x/state/decisions/DECISIONS-RESOLVED-7.md"}}' \
  && ok "DENY Write to DECISIONS-RESOLVED-7.md" || no "RESOLVED write not denied"

# 2) DENY DECISIONS-RESOLVED-12.md too (pattern, any index)
deny_p '{"tool_input":{"file_path":"/a/b/DECISIONS-RESOLVED-12.md"}}' \
  && ok "DENY any DECISIONS-RESOLVED-*.md" || no "RESOLVED-12 not denied"

# 3) ALLOW DECISIONS-PENDING.md (L0's legitimate gate write) — silent exit 0, no deny json
out="$(echo '{"tool_input":{"file_path":"/x/state/decisions/DECISIONS-PENDING.md"}}' | python3 "$GUARD" 2>/dev/null)"; rc=$?
[ -z "$out" ] && [ $rc -eq 0 ] && ok "ALLOW DECISIONS-PENDING.md (silent, exit 0)" || no "PENDING write wrongly gated (out='$out' rc=$rc)"

# 4) ALLOW an unrelated file
out="$(echo '{"tool_input":{"file_path":"/x/runs/p/HANDOFF.md"}}' | python3 "$GUARD" 2>/dev/null)"
[ -z "$out" ] && ok "ALLOW unrelated write (HANDOFF.md)" || no "unrelated write gated"

# 5) fail-open on unparseable stdin (blast radius stays narrow)
out="$(echo 'not json' | python3 "$GUARD" 2>/dev/null)"; rc=$?
[ -z "$out" ] && [ $rc -eq 0 ] && ok "unparseable stdin => fail-open allow" || no "unparseable stdin not fail-open"

# 6) registered in hooks/hooks.json under a Write|Edit|MultiEdit matcher
grep -q "decision_guard.sh" "$ROOT/hooks/hooks.json" && ok "decision_guard.sh registered in hooks.json" || no "not registered in hooks.json"

echo "----"; echo "t45_decision_guard_hook: $pass passed, $fail failed"; [ "$fail" = 0 ]
