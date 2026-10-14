#!/usr/bin/env bash
# T73 — bin/central_ambition_guard.sh + spec/research.js wiring: the MID-LOOP central/GAMBLE-K disposition guard.
# research-rescue was wired ONLY at verify_final's §4c reconciliation and the per-wave viability gate. Real
# incident (gate-invariant-relaxed-speculative-decoding, 2026-07-16): K1 (HANDOFF.ambition.locked.json's
# central_result) moved to "descoped_infeasible_at_scale" mid EXPERIMENTS_DONE via a free-text owner decision —
# research-rescue never ran. This guard mechanically catches that class of omission before ANY milestone is
# recorded done. Run: bash tests/t73_central_ambition_guard.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="$ROOT/bin/central_ambition_guard.sh"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1  --  $2"; fail=$((fail+1)); }

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

ambition(){ printf '{"content": "%s"}' "$1" > "$WORK/HANDOFF.ambition.locked.json"; }
scale(){ printf '{"content": "%s"}' "$1" > "$WORK/HANDOFF.scale-contract.locked.json"; }
before(){ printf '%s' "$1" > "$WORK/.round-1.concerns.json"; }
live(){ printf '%s' "$1" > "$WORK/TASK_STATUS.concerns.json"; }
run(){ bash "$GUARD" check "$WORK" 1; }

AMB='ambition_contract:\n  central_result:\n    delivered_by: \"EXPERIMENTS/E2/result.md (accuracy, K1)\"\n'
SC='scale_contract:\n  criteria:\n    \"K1\":\n      claim: \"x\"\n      tag: GAMBLE\n'
ambition "$AMB"; scale "$SC"
before '{"open_concerns":[{"id":"K1","status":"open"}]}'

# ── (1) K1 unchanged this round → OK ────────────────────────────────────────────────────
live '{"open_concerns":[{"id":"K1","status":"open"}]}'
[ "$(run)" = "OK" ] && ok "K1 unchanged -> OK" || no "K1 unchanged -> OK" "$(run)"

# ── (2) K1 -> non-canonical status, no rescue on disk → NEEDS_RESCUE K1 ────────────────
live '{"open_concerns":[{"id":"K1","status":"descoped_infeasible_at_scale"}]}'
[ "$(run)" = "NEEDS_RESCUE K1" ] && ok "K1 descoped, no rescue -> NEEDS_RESCUE K1" || no "K1 descoped, no rescue" "$(run)"

# ── (3) same, but a rescue-verdicts record already exists for K1 → OK (rescue already tried) ─
printf '[{"item":"K1","verdict":"not_retained"}]' > "$WORK/.round-1.rescue-verdicts.json"
[ "$(run)" = "OK" ] && ok "K1 descoped + rescue already on disk -> OK" || no "already-rescued case" "$(run)"
rm -f "$WORK/.round-1.rescue-verdicts.json"

# ── (4) K1 canonically 'closed' but resolution text narrates a narrow, no rescue → NEEDS_RESCUE ─
live '{"open_concerns":[{"id":"K1","status":"closed","resolution":"narrowed to the surviving regime"}]}'
[ "$(run)" = "NEEDS_RESCUE K1" ] && ok "K1 closed + narrowing resolution, no rescue -> NEEDS_RESCUE K1" \
  || no "resolution-text branch" "$(run)"

# ── (5) K1 closed with a genuinely non-narrowing resolution (e.g. clean pass) → OK ─────
live '{"open_concerns":[{"id":"K1","status":"closed","resolution":"reproduced cleanly, matches the pre-registered bound"}]}'
[ "$(run)" = "OK" ] && ok "K1 closed + non-narrowing resolution -> OK" || no "non-narrowing closed" "$(run)"

# ── (6) no HANDOFF.ambition.locked.json at all → OK (do-no-harm, contract not locked yet) ─
rm -f "$WORK/HANDOFF.ambition.locked.json"
live '{"open_concerns":[{"id":"K1","status":"descoped_infeasible_at_scale"}]}'
[ "$(run)" = "OK" ] && ok "no ambition lock -> OK (do-no-harm)" || no "missing lock file" "$(run)"
ambition "$AMB"

# ── (7) bad args → exit 2 ───────────────────────────────────────────────────────────────
bash "$GUARD" check >/dev/null 2>&1
[ $? -eq 2 ] && ok "bad args -> exit 2" || no "bad args should exit 2" ""

# ── Phase-2 hardening: hooks/central_narrow_guard.py fail-closed backstop ──────────────
HOOK="$ROOT/hooks/central_narrow_guard.py"
mkdir -p "$WORK/state"; printf '{"loop_round": 1}' > "$WORK/state/pipeline-state.json"
live '{"open_concerns":[{"id":"K1","status":"open"}]}'
hook_payload(){ python3 -c "
import json
print(json.dumps({'tool_name':'Write','tool_input':{'file_path':'$WORK/TASK_STATUS.concerns.json','content':json.dumps($1)}}))
"; }
hook_run(){ hook_payload "$1" | env CLAUDE_PLUGIN_ROOT="$ROOT" CLAUDE_PROJECT_DIR="$WORK" python3 "$HOOK"; }
out="$(hook_run '{"open_concerns":[{"id":"K1","status":"descoped_infeasible_at_scale"}]}')"
echo "$out" | grep -q '"permissionDecision": "deny"' && ok "hook DENY: proposed Write narrows K1 with no rescue" \
  || no "hook should deny the narrowing write" "$out"
out="$(hook_run '{"open_concerns":[{"id":"K1","status":"open"}]}')"
[ -z "$out" ] && ok "hook ALLOW: proposed Write keeps K1 open" || no "hook should silently allow" "$out"
out="$(echo '{"tool_name":"Write","tool_input":{"file_path":"'"$WORK"'/some-other-file.json","content":"{}"}}' \
  | env CLAUDE_PLUGIN_ROOT="$ROOT" CLAUDE_PROJECT_DIR="$WORK" python3 "$HOOK")"
[ -z "$out" ] && ok "hook ALLOW: unrelated file" || no "hook should ignore unrelated files" "$out"
grep -q "central_narrow_guard.sh" "$ROOT/hooks/hooks.json" && ok "central_narrow_guard.sh registered in hooks.json" \
  || no "not registered in hooks.json" ""

# ── Static: wired into spec/research.js + config.yaml + skills ─────────────────────────
grep -q "^function runCentralAmbitionGuard" "$ROOT/spec/research.js" && ok "runCentralAmbitionGuard defined" \
  || no "runCentralAmbitionGuard missing" ""
grep -q "runCentralAmbitionGuard(state, ws) === 'gated'" "$ROOT/spec/research.js" \
  && ok "runCentralAmbitionGuard called in runExperiment" || no "call site missing" ""
grep -q "central-narrow-gate-" "$ROOT/spec/research.js" && ok "central-narrow-gate- id present" || no "gate id missing" ""
grep -q "id.startsWith('central-narrow-gate-')" "$ROOT/spec/research.js" && ok "ingestGateAnswer branch present" \
  || no "ingestGateAnswer branch missing" ""
grep -q "central_ambition_guard" "$ROOT/config/config.yaml" && ok "checkpoints.central_ambition_guard present" \
  || no "config.yaml missing checkpoint" ""
grep -q "central-ambition guard" "$ROOT/skills/research-rescue/SKILL.md" && ok "research-rescue SKILL.md mentions the guard" \
  || no "SKILL.md not updated" ""
# D1 invariant preserved (t38 already locks this at the spawnWorkersParallel call site): no dynamic role key
# was introduced by this feature — runCentralAmbitionGuard calls the EXISTING runResearchRescue, not a new spawn path.
grep -q "runResearchRescue(state, 'mid-loop-central-narrow'" "$ROOT/spec/research.js" \
  && ok "reuses the existing runResearchRescue (fixed 'rescue' role, no new spawn path)" || no "rescue call missing" ""

echo; echo "t73: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
