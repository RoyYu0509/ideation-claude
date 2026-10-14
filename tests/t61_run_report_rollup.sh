#!/usr/bin/env bash
# t61 — run_report.py `rollup` over the t14-style synthetic trace. Proves: machine JSON with token totals
# by role/model (from transcripts, L0's own session included alongside L1/L2 subagents — schema@2), spawns-
# by-stage (l0 spawns only, hook twins excluded), gate open->answer pairing, detach counters, and stage
# spans — the /learn economics input, and the input the usage_rollup Stop hook persists per run. Standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
RR="$ROOT/bin/run_report.py"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/state" "$TMP/native/S1/subagents"

printf '%s\n' '{"run_id":"R","paper_slug":"demo","stage":"done"}' > "$TMP/state/pipeline-state.json"
printf '%s\n' '{"session_id":"S1","transcript_path":"'"$TMP"'/native/S1.jsonl","run_id":"R"}' > "$TMP/state/sessions.jsonl"
printf '%s\n' '{"type":"assistant","timestamp":"2026-06-13T10:00:00Z","sessionId":"S1","message":{"model":"claude-opus-4-8","usage":{"output_tokens":50},"content":[{"type":"tool_use","name":"Agent","id":"toolu_P","input":{}}]}}' > "$TMP/native/S1.jsonl"
{
 printf '%s\n' '{"type":"assistant","timestamp":"2026-06-13T10:00:10Z","agentId":"axxx","message":{"model":"claude-sonnet-5","usage":{"output_tokens":120},"content":[{"type":"tool_use","name":"Bash","id":"toolu_C","input":{}}]}}'
} > "$TMP/native/S1/subagents/agent-axxx.jsonl"
printf '%s\n' '{"agentType":"claude","description":"review orchestrator","toolUseId":"toolu_P"}' > "$TMP/native/S1/subagents/agent-axxx.meta.json"
{
 printf '%s\n' '{"ts":"2026-06-13T10:00:00Z","run_id":"R","event":"run_start","stage":"ideation"}'
 printf '%s\n' '{"ts":"2026-06-13T10:00:01Z","run_id":"R","event":"agent_spawn","stage":"loop","role":"experiment_worker","model":"opus"}'
 printf '%s\n' '{"ts":"2026-06-13T10:00:02Z","run_id":"R","event":"agent_spawn","stage":"loop","src":"hook","subagent_type":"claude"}'
 printf '%s\n' '{"ts":"2026-06-13T10:00:03Z","run_id":"R","event":"agent_return","stage":"loop","role":"review_orchestrator","agent_id":"axxx"}'
 printf '%s\n' '{"ts":"2026-06-13T10:00:04Z","run_id":"R","event":"gate_open","stage":"loop","id":"viability-r1"}'
 printf '%s\n' '{"ts":"2026-06-13T10:05:04Z","run_id":"R","event":"gate_answer","stage":"loop","id":"viability-r1"}'
 printf '%s\n' '{"ts":"2026-06-13T10:06:00Z","run_id":"R","event":"long_run_fired","stage":"loop"}'
 printf '%s\n' '{"ts":"2026-06-13T11:00:00Z","run_id":"R","event":"detached_finalized","stage":"loop"}'
} > "$TMP/state/run-events.jsonl"

J="$(CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" rollup --run R 2>/dev/null)"

# === Case 1: valid machine JSON with the right totals (L0's session + the one subagent transcript) ===
if echo "$J" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['schema']=='auto-research-rollup@2' and d['run_id']=='R'
assert d['totals']['out_tok']==170, d['totals']   # 50 (L0, S1.jsonl) + 120 (subagent axxx)
assert d['inputs']['agent_transcripts']==1 and d['inputs']['l0_sessions']==1 and d['inputs']['events']==8
" 2>/dev/null; then ok "rollup JSON: schema + token totals from transcripts (L0 + subagents)"; else no "rollup totals  (got: $(echo "$J" | head -c 200))"; fi

# === Case 2: by_role joins the semantic role from events; by_model from the transcript; L0 is its own bucket ===
if echo "$J" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['by_role']['review_orchestrator']['out_tok']==120
assert d['by_role']['L0']['out_tok']==50
assert d['by_model']['claude-sonnet-5']['agents']==1
assert d['by_model']['claude-opus-4-8']['out_tok']==50   # L0's model, from S1.jsonl
" 2>/dev/null; then ok "by_role (semantic join, incl. L0) + by_model"; else no "by_role/by_model"; fi

# === Case 3: spawns_by_stage counts l0 spawns only (hook twin excluded); gates paired; detach counted ===
if echo "$J" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['spawns_by_stage']=={'loop':1}, d['spawns_by_stage']
g=d['gates']; assert g['opened']==1 and g['answered']==1
assert g['by_id']['viability-r1']['opened']=='2026-06-13T10:00:04Z'
assert g['by_id']['viability-r1']['answered']=='2026-06-13T10:05:04Z'
assert d['detached']['long_run_fired']==1 and d['detached']['finalized']==1
assert d['wall']['first_ts']=='2026-06-13T10:00:00Z'
" 2>/dev/null; then ok "spawns (hook excluded) + gate spans + detach counters"; else no "spawns/gates/detach"; fi

# === Case 4: --out writes the same JSON to a file ===
CLAUDE_PROJECT_DIR="$TMP" python3 "$RR" rollup --run R --out "$TMP/rollup.json" >/dev/null 2>&1
if python3 -c "import json;json.load(open('$TMP/rollup.json'))" 2>/dev/null; then
  ok "--out persists the JSON"; else no "--out persists"; fi

echo "----"; echo "t61_run_report_rollup: $pass passed, $fail failed"; [ "$fail" = 0 ]
