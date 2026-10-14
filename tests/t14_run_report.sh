#!/usr/bin/env bash
# t14 — the trace harvest + attribution reader over a SYNTHETIC run. Proves: snapshot_traces.sh true-copies
# the full-depth native trace and it SURVIVES source deletion (anti-GC); run_report.py rebuilds the L0->L1
# tree via meta.toolUseId, dumps one agent's action trace, attributes a string to its emitter, and raises the
# RC health flags (RC-2 no-real-panel, RC-4 gate mismatch, RC-9 no-commit) from events+artifacts. Standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
RR="$ROOT/bin/run_report.py"; SNAP="$ROOT/bin/snapshot_traces.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/state" "$TMP/native/S1/subagents" "$TMP/runs/demo"

# --- pipeline-state + sessions anchor (run R; session S1 transcript at TMP/native/S1.jsonl) ---
printf '%s\n' '{"run_id":"R","paper_slug":"demo","loop_round":1,"stage":"loop"}' > "$TMP/state/pipeline-state.json"
printf '%s\n' '{"session_id":"S1","transcript_path":"'"$TMP"'/native/S1.jsonl","run_id":"R"}' > "$TMP/state/sessions.jsonl"

# --- synthetic native L0 transcript: one assistant whose tool_use (id=toolu_PARENT) spawned the L1 ---
printf '%s\n' '{"type":"assistant","timestamp":"2026-06-13T10:00:00Z","sessionId":"S1","message":{"model":"claude-opus-4-8","usage":{"output_tokens":50},"content":[{"type":"text","text":"spawning review"},{"type":"tool_use","name":"Agent","id":"toolu_PARENT","input":{"prompt":"review demo"}}]}}' > "$TMP/native/S1.jsonl"

# --- synthetic L1 subagent (agent-axxx): parented via meta.toolUseId=toolu_PARENT; embeds SECRET_TOKEN ---
{
 printf '%s\n' '{"type":"user","timestamp":"2026-06-13T10:00:05Z","agentId":"axxx","sessionId":"S1","message":{"role":"user","content":[{"type":"text","text":"You are the review orchestrator. probe SECRET_TOKEN here"}]}}'
 printf '%s\n' '{"type":"assistant","timestamp":"2026-06-13T10:00:10Z","agentId":"axxx","message":{"model":"claude-opus-4-8","usage":{"output_tokens":120},"content":[{"type":"text","text":"reviewing"},{"type":"tool_use","name":"Bash","id":"toolu_CHILD","input":{"command":"ls"}}]}}'
} > "$TMP/native/S1/subagents/agent-axxx.jsonl"
printf '%s\n' '{"agentType":"claude","description":"review orchestrator (demo)","toolUseId":"toolu_PARENT"}' > "$TMP/native/S1/subagents/agent-axxx.meta.json"

# --- a FORBIDDEN nested general-purpose leaf (RC-13 bait): a catch-all grandchild that must never be spawned ---
printf '%s\n' '{"type":"assistant","timestamp":"2026-06-13T10:00:12Z","agentId":"agp","message":{"content":[{"type":"text","text":"extracting fields"}]}}' > "$TMP/native/S1/subagents/agent-agp.jsonl"
printf '%s\n' '{"agentType":"general-purpose","description":"Extract fields","toolUseId":"toolu_CHILD","spawnDepth":3}' > "$TMP/native/S1/subagents/agent-agp.meta.json"

# --- run-events: a verdict for (demo,1) + a review_orchestrator return with subagents_spawned=0 (RC-2 bait) ---
{
 printf '%s\n' '{"ts":"2026-06-13T10:00:00Z","run_id":"R","event":"run_start","paper":null,"round":null}'
 printf '%s\n' '{"ts":"2026-06-13T10:00:01Z","run_id":"R","event":"agent_return","paper":"demo","round":1,"role":"review_orchestrator","agent_id":"axxx","subagents_spawned":0,"status":"done"}'
 printf '%s\n' '{"ts":"2026-06-13T10:00:02Z","run_id":"R","event":"verdict","paper":"demo","round":1,"source":"loop_gate","label":"EXIT"}'
} > "$TMP/state/run-events.jsonl"

# --- workspace artifacts: a mismatch gate-input (RC-4) + a milestone done with NO commit (RC-9) ---
printf '%s\n' '{"round":1,"overall_risk":"minor_revision","new_handoff_items":0,"write_backs":0,"mismatch":true}' > "$TMP/runs/demo/loop-gate-input-r1.json"
printf '%s\n' '{"slug":"demo","milestones":{"ENV_READY":{"completed_at":"2026-06-13T10:00:00Z","code_commit":null,"paper_commit":null}}}' > "$TMP/runs/demo/milestone-state.json"

# === Case 1: snapshot true-copies the trace into runs/_trace/<run_id>/ ===
CLAUDE_PROJECT_DIR="$TMP" bash "$SNAP" R >/dev/null 2>&1
if [ -f "$TMP/runs/_trace/R/S1/S1.jsonl" ] && [ -f "$TMP/runs/_trace/R/S1/subagents/agent-axxx.jsonl" ]; then
  ok "snapshot_traces true-copied L0 jsonl + subagents agent jsonl"; else no "snapshot_traces true-copied trace"; fi

# === Case 2: ANTI-GC — delete the native source; the snapshot survives AND the reader still reads it ===
rm -rf "$TMP/native"
if [ -f "$TMP/runs/_trace/R/S1/subagents/agent-axxx.jsonl" ] && \
   CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" agent axxx --run R 2>/dev/null | grep -q "review orchestrator"; then
  ok "anti-GC: trace survives source deletion + reader reads the snapshot"; else no "anti-GC survives source deletion"; fi

# === Case 3: tree rebuilds L0 -> agent-axxx via meta.toolUseId + the semantic role tag from run-events ===
if CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" tree --run R 2>/dev/null | grep -q "review_orchestrator"; then
  ok "tree rebuilds L0->L1 (toolUseId edge) + semantic role tag"; else no "tree rebuilds L0->L1"; fi

# === Case 4: agent dump shows the per-tool action trace (embedded text + the Bash tool_use) ===
DUMP="$(CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" agent axxx --run R 2>/dev/null)"
if echo "$DUMP" | grep -q "SECRET_TOKEN" && echo "$DUMP" | grep -q "TOOL"; then
  ok "agent dump shows per-tool action trace"; else no "agent dump shows action trace"; fi

# === Case 5: attribute locates which agent emitted SECRET_TOKEN ===
if CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" attribute "SECRET_TOKEN" --run R 2>/dev/null | grep -q "axxx"; then
  ok "attribute locates the agent that emitted a string"; else no "attribute locates emitter"; fi

# === Case 6: health raises RC-4 (mismatch) + RC-9 (no commit) + RC-2 (verdict but 0 reviewer spawn) ===
H="$(CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" health --run R 2>/dev/null)"
if echo "$H" | grep -q "RC-4" && echo "$H" | grep -q "RC-9" && echo "$H" | grep -q "RC-2"; then
  ok "health raises RC-4 + RC-9 + RC-2 from events+artifacts"
else no "health raises RC-4/9/2  (got: $(echo "$H" | tr '\n' '|'))"; fi

# === Case 6b: health raises RC-13 for a forbidden nested general-purpose subagent in the trace ===
if echo "$H" | grep -q "RC-13.*in trace"; then
  ok "health raises RC-13 (forbidden general-purpose subagent in trace)"
else no "health raises RC-13  (got: $(echo "$H" | tr '\n' '|'))"; fi

# === Case 6c: with ZERO agent_spawn events, health prints the explicit event-level skip note (pre-append) ===
if echo "$H" | grep -q "RC-13 (event-level) skipped"; then
  ok "health prints explicit RC-13 event-level skip note when no agent_spawn events"
else no "health prints RC-13 event-level skip note  (got: $(echo "$H" | tr '\n' '|'))"; fi

# === Case 7: timeline renders the run's events ===
if [ "$(CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" timeline --run R 2>/dev/null | grep -cE 'run_start|agent_return|verdict')" -ge 3 ]; then
  ok "timeline renders the run's events"; else no "timeline renders events"; fi

# === Case 6d: event-level RC-13 — a spawn_guard-logged general-purpose agent_spawn (no transcript node) fires ===
printf '%s\n' '{"ts":"2026-06-13T10:00:03Z","run_id":"R","event":"agent_spawn","src":"hook","subagent_type":"general-purpose","description":"summarize decisions","session_id":"S1"}' >> "$TMP/state/run-events.jsonl"
H2="$(CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" health --run R 2>/dev/null)"
if echo "$H2" | grep -q "in run-events (logged-then-DENIED by spawn_guard)" && \
   echo "$H2" | grep -q "RC-13 event-level: 1" && \
   ! echo "$H2" | grep -q "RC-13 (event-level) skipped"; then
  ok "health raises event-level RC-13 for a hook-logged general-purpose spawn + count note, skip note gone"
else no "health raises event-level RC-13  (got: $(echo "$H2" | tr '\n' '|'))"; fi

# === Case 6e: a BLANK subagent_type hook record is flagged without claiming a deny (H-3 pending) ===
printf '%s\n' '{"ts":"2026-06-13T10:00:04Z","run_id":"R","event":"agent_spawn","src":"hook","subagent_type":"","description":"blank type spawn","session_id":"S1"}' >> "$TMP/state/run-events.jsonl"
H3="$(CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" health --run R 2>/dev/null)"
if echo "$H3" | grep -q "NOT denied by current spawn_guard"; then
  ok "health flags a blank-type hook spawn with the NOT-denied wording"
else no "health flags blank-type hook spawn  (got: $(echo "$H3" | tr '\n' '|'))"; fi

echo "----"; echo "t14_run_report: $pass passed, $fail failed"; [ "$fail" = 0 ]
