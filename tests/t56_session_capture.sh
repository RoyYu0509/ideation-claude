#!/usr/bin/env bash
# T56 — cross-session capture is DETERMINISTIC, not L0-model-enacted (2026-07-05). A run spans many native
# sessions (terminal-reopen resumes = new session uuids); the old observability relied on L0 side-channel calls
# (anchorSelf --self, logEvent agent_spawn) that the resume fast-paths skip, so only session 1 was ever anchored
# and its later sessions' spawns never reached the ledger/trace. This pins the two harness-enforced fixes:
#   (1) provision_instance.sh arms a folder-level SessionStart hook → session_anchor.sh (stdin mode), so EVERY
#       session is anchored by the harness; session_anchor no-ops in a folder with no run (no pollution).
#   (2) spawn_guard.sh (the Task|Agent PreToolUse hook) DETERMINISTICALLY writes an agent_spawn(src:hook) event
#       for every top-level spawn in every session — no L0 enactment needed.
# Run: bash tests/t56_session_capture.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROV="$ROOT/bin/provision_instance.sh"
ANCHOR="$ROOT/bin/session_anchor.sh"
GUARD="$ROOT/hooks/spawn_guard.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── (1a) provision writes a SessionStart→session_anchor hook into <DATA_ROOT>/.claude/settings.local.json ──
D1="$TMP/inst1"; mkdir -p "$D1"
bash "$PROV" "$D1" "$ROOT" >/dev/null 2>&1
SET="$D1/.claude/settings.local.json"
chk "provision creates settings.local.json"          "test -f '$SET'"
chk "provision arms SessionStart → session_anchor.sh (absolute path)" \
    "python3 -c \"import json;h=json.load(open('$SET'))['hooks']['SessionStart'];print('OK') if any(x.get('command')=='$ANCHOR' for e in h for x in e.get('hooks',[])) else 1/0\""
chk "provision writes VALID json"                    "python3 -c \"import json;json.load(open('$SET'))\""

# ── (1b) idempotent: re-run does not duplicate the entry ──
bash "$PROV" "$D1" "$ROOT" >/dev/null 2>&1
chk "provision is idempotent (exactly ONE SessionStart entry)" \
    "test \$(python3 -c \"import json;print(len(json.load(open('$SET'))['hooks']['SessionStart']))\") -eq 1"

# ── (1c) merge preserves owner-authored keys (never clobbers) ──
python3 -c "import json;p='$SET';d=json.load(open(p));d['permissions']={'allow':['Bash(ls)']};d['hooks'].setdefault('PreToolUse',[{'matcher':'Write','hooks':[{'type':'command','command':'/x.sh'}]}]);json.dump(d,open(p,'w'))"
bash "$PROV" "$D1" "$ROOT" >/dev/null 2>&1
chk "provision merge preserves owner permissions key"   "python3 -c \"import json;d=json.load(open('$SET'));1/0 if d.get('permissions',{}).get('allow')!=['Bash(ls)'] else print('OK')\""
chk "provision merge preserves owner PreToolUse hook"   "python3 -c \"import json;d=json.load(open('$SET'));print('OK') if d['hooks'].get('PreToolUse') else 1/0\""

# ── (2a) session_anchor HOOK mode NO-OPS when the folder has no run (no pipeline-state.json) ──
D2="$TMP/norun"; mkdir -p "$D2"
printf '%s' '{"session_id":"S-A","transcript_path":"/tmp/a.jsonl","cwd":"'$D2'","source":"resume"}' | CLAUDE_PROJECT_DIR="$D2" bash "$ANCHOR" >/dev/null 2>&1
chk "session_anchor hook-mode NO-OPS without a run (no sessions.jsonl)"  "! test -f '$D2/state/sessions.jsonl'"

# ── (2b) session_anchor HOOK mode ANCHORS a reopened session when a run exists ──
D3="$TMP/run"; mkdir -p "$D3/state"; printf '%s' '{"run_id":"RID","paper_slug":"p"}' > "$D3/state/pipeline-state.json"
printf '%s' '{"session_id":"S-B","transcript_path":"/tmp/b.jsonl","cwd":"'$D3'","source":"resume"}' | CLAUDE_PROJECT_DIR="$D3" bash "$ANCHOR" >/dev/null 2>&1
chk "session_anchor hook-mode anchors a reopened session when a run exists" \
    "python3 -c \"import json;r=[json.loads(l) for l in open('$D3/state/sessions.jsonl')];print('OK') if any(x['session_id']=='S-B' and x.get('source')=='resume' for x in r) else 1/0\""

# ── (2c) spawn_guard DETERMINISTICALLY logs agent_spawn(src:hook) with the config wrapper filled ──
D4="$TMP/guard"; mkdir -p "$D4/state"
printf '%s' '{"run_id":"RID9","paper_slug":"pz","loop_round":2,"stage":"loop"}' > "$D4/state/pipeline-state.json"
OUT="$(printf '%s' '{"tool_name":"Task","session_id":"S1","agent_type":"claude","tool_input":{"subagent_type":"auto-research:leaf-worker","model":"opus","description":"author script"}}' | CLAUDE_PROJECT_DIR="$D4" bash "$GUARD")"
chk "spawn_guard emits NO deny for a leaf-worker (stdout empty)"  "test -z \"$OUT\""
chk "spawn_guard logged agent_spawn(src:hook) with wrapper (run_id/round from pipeline-state)" \
    "python3 -c \"import json;e=[json.loads(l) for l in open('$D4/state/run-events.jsonl')][-1];assert e['event']=='agent_spawn' and e['src']=='hook' and e['subagent_type']=='auto-research:leaf-worker' and e['model']=='opus' and e['run_id']=='RID9' and e['round']==2;print('OK')\""

# ── (2d) the deny path STILL fires for the forbidden catch-all AND logs it (deny on stdout, event on disk) ──
OUT2="$(printf '%s' '{"tool_name":"Task","session_id":"S1","agent_type":"claude","tool_input":{"subagent_type":"general-purpose","description":"x"}}' | CLAUDE_PROJECT_DIR="$D4" bash "$GUARD")"
chk "spawn_guard still DENIES the forbidden catch-all (stdout has deny)"  "echo '$OUT2' | grep -qF '\"permissionDecision\": \"deny\"'"
chk "spawn_guard logged the denied spawn too (deterministic record)" \
    "test \$(grep -c 'agent_spawn' '$D4/state/run-events.jsonl') -eq 2"

echo "----"; echo "t56_session_capture: $pass passed, $fail failed"; [ "$fail" = 0 ]
