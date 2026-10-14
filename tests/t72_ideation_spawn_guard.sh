#!/usr/bin/env bash
# T72 — hooks/spawn_guard.py L1 (2026-07-12): the ideation-stage waiter/placeholder spawn deny.
# A headless L1 ideation orchestrator has NO self-rewake, so its only correct fan-out is
# "one message, many Task calls, awaited in-turn". A prior run mis-reached for a non-existent
# "detached background fan-out" and spawned a dozen+ noop/placeholder waiter subagents to spin
# (and fabricated verdicts). This guard DENIES such spawns during stage:"ideation" only,
# keyed on the description text (the only observable signal — Task/Agent have no background bit).
# It must NOT touch: real awaited judge/verify batches, any spawn outside ideation, or the
# existing general-purpose nesting deny. Run: bash tests/t72_ideation_spawn_guard.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="$ROOT/hooks/spawn_guard.py"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

# Scratch data root carrying a pipeline-state.json; the hook reads stage from cwd/state/...
# We unset CLAUDE_PROJECT_DIR so the hook falls back to the payload's cwd (deterministic).
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/state"
stage(){ printf '{"stage":"%s"}' "$1" > "$WORK/state/pipeline-state.json"; }
# run <json-without-cwd> : injects cwd=$WORK, runs the guard with CLAUDE_PROJECT_DIR unset.
run(){ echo "$1" | sed "s#}\$#,\"cwd\":\"$WORK\"}#" | env -u CLAUDE_PROJECT_DIR python3 "$GUARD" 2>/dev/null; }
deny(){ run "$1" | grep -q '"permissionDecision": "deny"'; }
allow(){ local o; o="$(run "$1")"; [ -z "$o" ]; }

# ── DENY cases: ideation stage + waiter/placeholder description ───────────────────────
stage ideation
deny '{"tool_name":"Task","tool_input":{"subagent_type":"auto-research:leaf-worker","description":"noop-wait-for-more-notifications-3"}}' \
  && ok "DENY noop-wait waiter during ideation" || no "noop-wait not denied"
deny '{"tool_name":"Task","tool_input":{"subagent_type":"auto-research:leaf-worker","description":"placeholder to await background notification"}}' \
  && ok "DENY placeholder/await-background waiter during ideation" || no "placeholder waiter not denied"

# ── ALLOW cases ──────────────────────────────────────────────────────────────────────
# A real, in-turn-awaited judge leaf must pass straight through (silent, exit 0).
allow '{"tool_name":"Task","tool_input":{"subagent_type":"auto-research:leaf-worker","description":"Claim judge: 2506.04985 FPTQuant"}}' \
  && ok "ALLOW real Claim judge leaf during ideation" || no "real judge leaf wrongly denied"
allow '{"tool_name":"Task","tool_input":{"subagent_type":"auto-research:leaf-worker","description":"Verify: 2607.07740 Jet-Long c1"}}' \
  && ok "ALLOW real Verify leaf during ideation" || no "real verify leaf wrongly denied"

# Same waiter description but the run is NOT in ideation → allow (stage-gated).
stage loop
allow '{"tool_name":"Task","tool_input":{"subagent_type":"auto-research:leaf-worker","description":"noop-wait-for-more-notifications"}}' \
  && ok "ALLOW waiter-worded spawn outside ideation (stage-gated)" || no "waiter denied in non-ideation stage"

# No readable stage / no state file → fail-open allow (never wedge on ambiguity).
rm -f "$WORK/state/pipeline-state.json"
allow '{"tool_name":"Task","tool_input":{"subagent_type":"auto-research:leaf-worker","description":"noop-wait-for-more-notifications"}}' \
  && ok "ALLOW when stage unreadable (fail-open)" || no "did not fail-open on missing state"

# ── Regression: the existing general-purpose nesting deny still fires (any stage) ─────
stage ideation
deny '{"tool_name":"Task","tool_input":{"subagent_type":"general-purpose","description":"anything"}}' \
  && ok "DENY general-purpose (existing nesting guard intact)" || no "general-purpose deny regressed"

# Non-Task/Agent tool is ignored entirely.
allow '{"tool_name":"Bash","tool_input":{"description":"noop-wait","command":"echo hi"}}' \
  && ok "ALLOW non-Task tool (matcher scope)" || no "non-Task tool wrongly gated"

# Registered on the Task|Agent matcher.
grep -q "spawn_guard.sh" "$ROOT/hooks/hooks.json" && ok "spawn_guard.sh registered in hooks.json" || no "not registered in hooks.json"

echo "----"; echo "t72_ideation_spawn_guard: $pass passed, $fail failed"; [ "$fail" = 0 ]
