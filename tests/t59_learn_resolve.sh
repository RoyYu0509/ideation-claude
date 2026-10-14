#!/usr/bin/env bash
# t59 — bin/learn_resolve.sh over a SYNTHETIC data root. Proves: state-based default resolution, arg
# resolution (slug / run-id prefix / ws path), busy-pipeline flags (pending gate / mid-stage), degraded
# flags for a traceless run, DOSSIER_HOME source-repo vs outbox split, and loud refusals (unresolvable /
# ambiguous prefix). Standalone; hermetic via AR_LEARN_SOURCE_REPO.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1"; fail=$((fail+1)); }
LR="$ROOT/bin/learn_resolve.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
TMP="$(cd "$TMP" && pwd -P)"   # macOS: /var/... -> /private/var/... so path comparisons match realpath output
SRC="$TMP/srcrepo"; mkdir -p "$SRC/dev/learning"
export AR_LEARN_SOURCE_REPO="$SRC"

D="$TMP/root"; mkdir -p "$D/state/decisions" "$D/runs/demo" "$D/runs/other" "$D/runs/_trace/R1"
printf '%s\n' '{"stage":"done","paper_slug":"demo","pending_gate":null,"loop_round":2}' > "$D/state/pipeline-state.json"
{
 printf '%s\n' '{"ts":"2026-07-01T10:00:00Z","run_id":"R1","event":"run_start","paper":null,"stage":"ideation"}'
 printf '%s\n' '{"ts":"2026-07-01T11:00:00Z","run_id":"R1","event":"verdict","paper":"demo","stage":"loop"}'
} > "$D/state/run-events.jsonl"
printf '%s\n' '{"session_id":"S1","transcript_path":"/tmp/none.jsonl","run_id":"R1"}' > "$D/state/sessions.jsonl"
printf '%s\n' '{"slug":"demo","milestones":{}}' > "$D/runs/demo/milestone-state.json"
printf '%s\n' '{"slug":"other","milestones":{}}' > "$D/runs/other/milestone-state.json"

get(){ echo "$1" | awk -v k="$2" '$1==k{sub($1 FS,"");print;exit}'; }

# === Case 1: no-arg state-based resolution on a done run ===
OUT="$(bash "$LR" "$D")" || OUT=""
if [ "$(get "$OUT" RUN_ID)" = "R1" ] && [ "$(get "$OUT" SLUG)" = "demo" ] && \
   [ "$(get "$OUT" DEGRADED)" = "none" ] && [ "$(get "$OUT" PIPELINE_BUSY)" = "no" ] && \
   [ "$(get "$OUT" RESOLVED_BY)" = "state" ] && [ "$(get "$OUT" SESSIONS_N)" = "1" ] && \
   [ "$(get "$OUT" EVENTS_N)" = "2" ]; then
  ok "state-based default: run_id/slug/degraded/busy all correct"
else no "state-based default  (got: $(echo "$OUT" | tr '\n' '|'))"; fi

# === Case 2: DOSSIER_HOME = <source repo>/dev/learning when resolvable; TRACE_DIR found ===
if [ "$(get "$OUT" DOSSIER_HOME)" = "$SRC/dev/learning" ] && [ "$(get "$OUT" TRACE_DIR)" = "$D/runs/_trace/R1" ]; then
  ok "dossier home -> source repo; trace dir resolved"
else no "dossier home / trace dir  (got: $(get "$OUT" DOSSIER_HOME) / $(get "$OUT" TRACE_DIR))"; fi

# === Case 3: unresolvable source repo -> outbox under LEARN_DIR ===
OUT3="$(AR_LEARN_SOURCE_REPO="$TMP/nonexistent" bash "$LR" "$D")"
case "$(get "$OUT3" DOSSIER_HOME)" in
  "$D/state/learning/R1/repo-outbox") ok "no source repo -> outbox dossier home + SOURCE_REPO none";;
  *) no "outbox fallback  (got: $(get "$OUT3" DOSSIER_HOME))";;
esac

# === Case 4: busy flags — pending gate wins; mid-stage flagged ===
printf '%s\n' '{"stage":"loop","paper_slug":"demo","pending_gate":"viability-r2"}' > "$D/state/pipeline-state.json"
B1="$(bash "$LR" "$D" | awk '$1=="PIPELINE_BUSY"{print $2}')"
printf '%s\n' '{"stage":"loop","paper_slug":"demo","pending_gate":null}' > "$D/state/pipeline-state.json"
B2="$(bash "$LR" "$D" | awk '$1=="PIPELINE_BUSY"{print $2}')"
printf '%s\n' '{"stage":"done","paper_slug":"demo","pending_gate":null}' > "$D/state/pipeline-state.json"
if [ "$B1" = "gate:viability-r2" ] && [ "$B2" = "stage:loop" ]; then
  ok "busy flags: pending gate + mid-stage"
else no "busy flags  (got: $B1 / $B2)"; fi

# === Case 5: arg = slug / run-id prefix / ws path ===
A1="$(bash "$LR" "$D" other | awk '$1=="RESOLVED_BY"{print $2}')"
A2="$(bash "$LR" "$D" R1 | awk '$1=="RESOLVED_BY"{print $2}')"
A3="$(bash "$LR" "$D" "$D/runs/demo" | awk '$1=="RESOLVED_BY"{print $2}')"
if [ "$A1" = "arg-slug" ] && [ "$A2" = "arg-runid" ] && [ "$A3" = "arg-path" ]; then
  ok "arg resolution: slug / run-id prefix / workspace path"
else no "arg resolution  (got: $A1 / $A2 / $A3)"; fi

# === Case 6: mid-stage busy does NOT flag a DIFFERENT (past) target ===
printf '%s\n' '{"stage":"loop","paper_slug":"demo","pending_gate":null}' > "$D/state/pipeline-state.json"
B3="$(bash "$LR" "$D" other | awk '$1=="PIPELINE_BUSY"{print $2}')"
printf '%s\n' '{"stage":"done","paper_slug":"demo","pending_gate":null}' > "$D/state/pipeline-state.json"
if [ "$B3" = "no" ]; then ok "busy scoping: reviewing a PAST run while another is mid-stage is allowed"
else no "busy scoping  (got: $B3)"; fi

# === Case 7: degraded traceless run (no events/sessions/_trace) ===
D2="$TMP/old"; mkdir -p "$D2/runs/legacy"
printf '%s\n' '{"slug":"legacy","milestones":{}}' > "$D2/runs/legacy/milestone-state.json"
OUT7="$(bash "$LR" "$D2")"
if [ "$(get "$OUT7" DEGRADED)" = "events+trace" ] && [ "$(get "$OUT7" RUN_ID)" = "untraced-legacy" ] && \
   [ "$(get "$OUT7" RESOLVED_BY)" = "fallback-mtime" ]; then
  ok "degraded traceless run: flags + synthetic run_id + mtime fallback"
else no "degraded traceless  (got: $(echo "$OUT7" | tr '\n' '|'))"; fi

# === Case 8: loud refusals — empty root exit 2; ambiguous run-id prefix exit 2 ===
D3="$TMP/empty"; mkdir -p "$D3"
bash "$LR" "$D3" >/dev/null 2>&1; R1=$?
printf '%s\n' '{"ts":"t","run_id":"R2","event":"run_start"}' >> "$D/state/run-events.jsonl"
bash "$LR" "$D" R >/dev/null 2>&1; R2=$?
if [ "$R1" = "2" ] && [ "$R2" = "2" ]; then ok "loud refusals: unresolvable + ambiguous prefix"
else no "loud refusals  (got: $R1 / $R2)"; fi

echo "----"; echo "t59_learn_resolve: $pass passed, $fail failed"; [ "$fail" = 0 ]
