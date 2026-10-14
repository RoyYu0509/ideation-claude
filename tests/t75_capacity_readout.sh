#!/usr/bin/env bash
# T75 — CAPACITY_READOUT milestone: an early, cheap wall-clock heads-up right after Phase 0 locks §4b/§4c,
# instead of discovering an order-of-magnitude infeasible campaign one milestone late (the historical incident:
# gate-invariant-relaxed-speculative-decoding's "~19 days" was only measured at the START of EXPERIMENTS_DONE,
# after LITERATURE + ENV_READY had already run). Mostly STATIC invariants (like t39_ambition_amplify.sh) — the
# actual arithmetic runs inside a per-paper spawned probe script, not a fixed repo bin/ script.
# Run: bash tests/t75_capacity_readout.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RJS="$ROOT/spec/research.js"
CFG="$ROOT/config/config.yaml"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1  --  $2"; fail=$((fail+1)); }

# ── config.yaml: CAPACITY_READOUT is in the milestones array, immediately after PHASE0_KILL_OR_CONFIRM ──
grep -q "milestones: \[PHASE0_KILL_OR_CONFIRM, CAPACITY_READOUT, LITERATURE" "$CFG" \
  && ok "CAPACITY_READOUT immediately follows PHASE0_KILL_OR_CONFIRM in milestones[]" \
  || no "milestone ordering" "$(grep '^milestones:' "$CFG")"
grep -q "capacity_milestone: CAPACITY_READOUT" "$CFG" && ok "checkpoints.capacity_milestone present" || no "checkpoint missing" ""
grep -q "capacity_surface:" "$CFG" && ok "checkpoints.capacity_surface present" || no "checkpoint missing" ""
grep -q "capacity_gap_ratio_threshold:" "$CFG" && ok "checkpoints.capacity_gap_ratio_threshold present" || no "checkpoint missing" ""
grep -q "^researcher:" "$CFG" && grep -q "session_hours_assumption:" "$CFG" \
  && ok "researcher.session_hours_assumption present" || no "researcher block missing" ""
grep -q "capacity_probe_worker:" "$CFG" && ok "models.capacity_probe_worker present" || no "models entry missing" ""
grep -q "capacity_readout: { max_subagent_spawns" "$CFG" && ok "budgets.capacity_readout present" || no "budgets entry missing" ""

# ── spec/research.js: the isCap three-way branches ──────────────────────────────────────
grep -q "const isCap = ms === CFG.checkpoints.capacity_milestone" "$RJS" && ok "isCap flag computed in runExperiment" \
  || no "isCap flag missing" ""
grep -q "isCap ? capacityReadoutGoal(ws, capOut)" "$RJS" && ok "goal dispatch includes isCap branch" \
  || no "goal dispatch missing isCap" ""
grep -q "!isLit && !isCap && CFG.checkpoints.audit_artifact_surface" "$RJS" \
  && ok "CAPACITY_READOUT exempted from audit-artifact-surface (like isLit)" || no "audit-artifact exemption missing" ""
grep -q "isCap ? spawnL2('capacity_probe_worker', goal)" "$RJS" && ok "CAPACITY_READOUT spawns via spawnL2 (bounded leaf tier)" \
  || no "spawn dispatch missing isCap branch" ""
grep -q "tallyBudget(state, isCap ? 'capacity_readout' : 'b1_per_round', env)" "$RJS" \
  && ok "budget tally routes to capacity_readout bucket" || no "budget tally not isCap-aware" ""

# ── capacityReadoutGoal + the spawn-prompt it points at ─────────────────────────────────
grep -q "^function capacityReadoutGoal" "$RJS" && ok "capacityReadoutGoal defined" || no "capacityReadoutGoal missing" ""
grep -q "spec/spawn-prompts/CAPACITY-READOUT.md" "$RJS" && ok "capacityReadoutGoal points at the spawn-prompt" \
  || no "spawn-prompt reference missing" ""
[ -f "$ROOT/spec/spawn-prompts/CAPACITY-READOUT.md" ] && ok "spec/spawn-prompts/CAPACITY-READOUT.md exists" \
  || no "CAPACITY-READOUT.md missing" ""
grep -q '"verdict": "FITS" | "CONCERN"' "$ROOT/spec/spawn-prompts/CAPACITY-READOUT.md" \
  && ok "CAPACITY-READOUT.md pins the FITS|CONCERN verdict contract" || no "verdict contract missing" ""

# ── the capacity- gate reads from disk (capOut), never env.metrics (mirrors literature_reviewer) ──
grep -q "const capEvidence = isCap && exists(capOut) ? readJson(capOut) : null" "$RJS" \
  && ok "capacity verdict read from disk (capOut), not env.metrics" || no "disk-read pattern missing" ""
grep -q "capEvidence && capEvidence.verdict === 'CONCERN'" "$RJS" && ok "gate fires only on verdict:CONCERN" \
  || no "CONCERN condition missing" ""

# ── ingestGateAnswer('capacity-'): Proceed / Redirect->gen_handoff / Abandon ────────────
grep -q "id.startsWith('capacity-')" "$RJS" && ok "ingestGateAnswer has a capacity- branch" || no "branch missing" ""
grep -qF "if (c === 'Redirect — I will clarify') { state.stage = 'gen_handoff'; persist(state); return }" "$RJS" \
  && ok "capacity- Redirect routes through full re-author (gen_handoff), not a marker-clear retry" \
  || no "Redirect routing wrong shape" ""
grep -q "owner_abandoned_at_capacity" "$RJS" && ok "capacity- Abandon reaches finishRun" || no "Abandon path missing" ""

# ── §4b schema: budget_envelope + per-K scale_size ──────────────────────────────────────
HA="$ROOT/skills/handoff-authoring/SKILL.md"
grep -q "budget_envelope:" "$HA" && ok "§4b schema carries budget_envelope" || no "budget_envelope missing from SKILL.md" ""
grep -q "scale_size:" "$HA" && grep -q "total_units:" "$HA" && ok "§4b schema carries per-K scale_size/total_units" \
  || no "scale_size missing from SKILL.md" ""

# ── seedToHandoffGoal substitutes the new profile tokens ───────────────────────────────
grep -q '<PROFILE_FILE> = \${PROJECT_DIR}/data/profile/profile.json' "$RJS" && ok "seedToHandoffGoal substitutes <PROFILE_FILE>" \
  || no "<PROFILE_FILE> substitution missing" ""
grep -q '<SESSION_HOURS_ASSUMPTION> = \${CFG.researcher.session_hours_assumption}' "$RJS" \
  && ok "seedToHandoffGoal substitutes <SESSION_HOURS_ASSUMPTION>" || no "<SESSION_HOURS_ASSUMPTION> substitution missing" ""
grep -q '<PROFILE_FILE>' "$ROOT/skills/handoff-authoring/reference/mode-seed-generation.md" \
  && ok "mode-seed-generation.md documents <PROFILE_FILE> input" || no "mode-seed-generation.md not updated" ""

# ── STATUS-MODEL.md documents the new milestone ─────────────────────────────────────────
grep -q "CAPACITY_READOUT" "$ROOT/spec/STATUS-MODEL.md" && ok "STATUS-MODEL.md documents CAPACITY_READOUT" \
  || no "STATUS-MODEL.md not updated" ""

echo; echo "t75: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
