#!/usr/bin/env bash
# t13 — bin/log_event.sh appends schema-valid events to state/run-events.jsonl. The wrapper (ts UTC / run_id
# / paper / round / milestone / stage) is auto-filled from pipeline-state.json (AR_* env overrides); the
# payload merges at top level; bad input is fail-open. Each line is validated against spec/run-event-schema.json.
# This is the foundation of the trace/event logging system. Run standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
LE="$ROOT/bin/log_event.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/state"
printf '%s\n' '{"run_id":"RID1","paper_slug":"demo","loop_round":2,"milestone":"ENV_READY","stage":"loop"}' > "$TMP/state/pipeline-state.json"
export EV="$TMP/state/run-events.jsonl" SCHEMA="$ROOT/spec/run-event-schema.json"

# Case 1: wrapper auto-filled from pipeline-state.json; UTC ts; payload merged at top level
CLAUDE_PROJECT_DIR="$TMP" bash "$LE" agent_spawn '{"role":"experiment_worker"}'
if python3 - <<'PY'
import json,re,os
d=json.loads(open(os.environ["EV"]).readlines()[-1])
assert re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', d['ts']), d['ts']
assert d['run_id']=='RID1' and d['paper']=='demo' and d['round']==2 and d['stage']=='loop', d
assert d['event']=='agent_spawn' and d['role']=='experiment_worker', d
PY
then ok "wrapper auto-filled from pipeline-state + UTC ts + payload merged"; else no "wrapper auto-filled from pipeline-state"; fi

# Case 2: AR_* env overrides the state-derived wrapper
CLAUDE_PROJECT_DIR="$TMP" AR_RUN_ID="RID2" AR_PAPER="other" bash "$LE" ship '{"reason":"clean_exit"}'
if python3 - <<'PY'
import json,os
d=json.loads(open(os.environ["EV"]).readlines()[-1])
assert d['run_id']=='RID2' and d['paper']=='other' and d['reason']=='clean_exit', d
PY
then ok "AR_* env overrides state wrapper"; else no "AR_* env overrides state wrapper"; fi

# Case 3: every line validates against the event schema (required keys + event enum)
if python3 - <<'PY'
import json,os
sch=json.load(open(os.environ["SCHEMA"])); enum=set(sch['properties']['event']['enum']); req=sch['required']
for l in open(os.environ["EV"]):
    d=json.loads(l)
    assert all(k in d for k in req), ("missing required", d)
    assert d['event'] in enum, ("event not in enum", d['event'])
PY
then ok "every line satisfies spec/run-event-schema.json (required + event enum)"; else no "lines satisfy event schema"; fi

# Case 4: bad payload (not JSON) is fail-open — still writes a line, captures the parse error, exit 0
CLAUDE_PROJECT_DIR="$TMP" bash "$LE" verdict 'NOT JSON {'; rc=$?
if [ "$rc" -eq 0 ] && python3 - <<'PY'
import json,os
d=json.loads(open(os.environ["EV"]).readlines()[-1])
assert d['event']=='verdict' and '_payload_parse_error' in d, d
PY
then ok "bad payload fail-open (exit 0 + _payload_parse_error captured)"; else no "bad payload fail-open"; fi

# Case 5: missing <event> arg writes nothing, exits 0
before=$(wc -l < "$EV"); CLAUDE_PROJECT_DIR="$TMP" bash "$LE"; rc=$?; after=$(wc -l < "$EV")
if [ "$rc" -eq 0 ] && [ "$before" -eq "$after" ]; then ok "no <event> arg -> exit 0, nothing appended"; else no "no <event> arg -> exit 0, nothing appended"; fi

echo "----"; echo "t13_log_event: $pass passed, $fail failed"; [ "$fail" = 0 ]
