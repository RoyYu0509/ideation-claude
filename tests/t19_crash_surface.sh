#!/usr/bin/env bash
# T19 — detached-crash SURFACE + report + forced re-detach (spec/research.js resumeDetached crash branch,
# recordDetachedCrash, crashSurface, runB1 priorCrash guard). The gap this closes: resumeDetached used to
# finalize/reap a detached run and fall straight back into a blind B1 re-spawn WITHOUT ever inspecting the
# exit code. A crashed (exit!=0) job therefore produced no report and no owner gate, and the reproducing L0
# improvised a FOREGROUND re-run (hours of polling, ~2k tool-calls) that tripped a server rate-limit and
# silently killed the turn. Now: a non-zero exit → durable report (RESEARCH_LOG.md + FAILURES.md +
# .crash-<ms>.json) + state.pending_crash → main() routes to crashSurface (the SAME owner failure gate every
# hard-stop uses) BEFORE any re-spawn; on Resume runB1 reads the
# marker, fixes the bug, and re-runs DETACHED (never foreground). This test proves (A) the spec wiring + parse
# and (B) the crash-detection predicate against a REAL exp_ledger crashed record.
# Run: bash tests/t19_crash_surface.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
ESPEC="$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md"   # B1 goal text extracted out of research.js
LEDGER_CLI="$ROOT/plugins/paper-polish-ar/scripts/exp_ledger.py"
REWAKE="$ROOT/plugins/paper-polish-ar/hooks/rewake-when-done.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
ok=1; bad() { echo "FAIL  $1"; ok=0; }

# ── (A) spec/research.js wiring ────────────────────────────────────────────────────────────────────────
chk "spec: resumeDetached CRASH-SCANS finalized records for non-zero exit" "grep -qF 'Number(rec.exit_code) > 0' '$SPEC'"
chk "spec: resumeDetached arms the surface via recordDetachedCrash"        "grep -qF 'recordDetachedCrash(state, crashes)' '$SPEC'"
chk "spec: recordDetachedCrash is DEFINED"                                 "grep -qE 'function recordDetachedCrash\\(' '$SPEC'"
chk "spec: recordDetachedCrash writes the durable .crash-<ms> marker"      "grep -qF '.crash-' '$SPEC'"
chk "spec: recordDetachedCrash sets state.pending_crash"                   "grep -qF 'state.pending_crash = { ms, marker, crashes: annotated }' '$SPEC'"
chk "spec: recordDetachedCrash appends a durable RESEARCH_LOG report"      "grep -qF 'DETACHED RUN CRASHED' '$SPEC'"
chk "spec: crashSurface is DEFINED"                                        "grep -qE 'function crashSurface\\(' '$SPEC'"
chk "spec: crashSurface routes to the SAME failureSurface gate"            "grep -qF 'pc.ms}-crashed' '$SPEC'"
chk "spec: crashSurface consumes pending_crash (surface-once)"             "grep -qF 'state.pending_crash = null; persist(state)' '$SPEC'"
chk "spec: main() routes pending_crash to crashSurface"                    "grep -qF 'if (state.pending_crash) crashSurface(state)' '$SPEC'"
chk "spec: runB1 reads the priorCrash marker"                              "grep -qF 'const priorCrash = exists(crashMarker)' '$SPEC'"
chk "spec: runB1 FORCES the fixed re-run to stay DETACHED"                 "grep -qF 'You MUST re-run the' '$ESPEC'"
chk "spec: B1 goal: a detached run STAYS DETACHED on resume (no foreground)" "grep -qF 'STAYS DETACHED on resume' '$ESPEC'"
chk "spec: runB1 clears the crash marker on milestone completion"          "grep -qF 'rm -f \"\${crashMarker}\"' '$SPEC'"
chk "spec: per-paper reset clears pending_crash (no cross-paper leak)"     "grep -qF 'state.pending_crash = null' '$SPEC'"
# capture hygiene (failure/transient.md): mechanical cause classification + RESOLVED pairing, no auto-retry
chk "spec: recordDetachedCrash classifies causes via classify_crash.py"    "grep -qF 'classify_crash.py\" annotate' '$SPEC'"
chk "spec: FAILURES.md crash line carries the [cause:*] tag"               "grep -qF '[cause:\${causes}]' '$SPEC'"
chk "spec: crash resolution appends a RESOLVED pairing line"               "grep -qF 'RESOLVED — prior crash cleared' '$SPEC'"
chk "spec: crashSurface card carries the mechanical cause"                 "grep -qF 'Mechanical cause classification' '$SPEC'"
chk "spec: NO auto-retry of a crashed run (owner decision 2026-07-09)"     "! grep -qF 'crash_auto_retry' '$SPEC'"
# startup self-heal (B): a FRESH L0 reconciles from disk+PID, not from the resident-session re-wake.
chk "spec: resumeDetached branches on PID LIVENESS (kill -0)"              "grep -qF 'echo ALIVE || echo DEAD' '$SPEC'"
chk "spec: dead PID + no exitcode → surfaced as interrupted crash"         "grep -qF 'pid_dead_no_exitcode' '$SPEC'"
chk "spec: a LIVE detached run is re-armed (never clobbered/cleared)"      "grep -qF 'state.detached = stillRunning' '$SPEC'"
chk "spec: a LIVE detached run ends the turn (re-arm, like onLongRun)"     "grep -qF 'detached_still_running' '$SPEC'"
chk "spec: parses (node --check)"                                          "node --check '$SPEC'"

# ── (B) mechanism — the crash-detection predicate against a REAL exp_ledger crashed record ───────────────
REPO="$TMP/repo"; mkdir -p "$REPO" "$TMP/.polish"; git -C "$REPO" init -q
LEDGER="$TMP/.polish/run-ledger.json"
PIDFILE="$TMP/.polish/.bg-pids"

python3 "$LEDGER_CLI" init --ledger "$LEDGER" --repo "$REPO" --project "$TMP" >/dev/null 2>&1
# fire a SHORT detached run that CRASHES like a real experiment: a PROCESS exiting non-zero (a python
# AssertionError — the faithful analogue of the sanity-assert abort that started this), NOT the shell `exit`
# builtin (which would kill exp_ledger's wrapper before it records $? — a test artifact, not the real path).
python3 "$LEDGER_CLI" run-detach --ledger "$LEDGER" --repo "$REPO" --ledger-id crash_0001 \
  --cmd "sleep 1; python3 -c 'import sys; sys.stderr.write(\"AssertionError: SANITY(a1) FAIL\n\"); sys.exit(1)'" \
  --logdir "$TMP/.polish/runs" --pidfile "$PIDFILE" >/dev/null 2>&1

# the REAL Stop hook OS-waits the PID + exit-2 re-wakes us (the zero-token wait resumeDetached lands after).
( CLAUDE_PROJECT_DIR="$TMP" bash "$REWAKE" >/dev/null 2>&1 ); rc=$?
[ "$rc" = 2 ] || bad "rewake hook rc=$rc (want 2)"

# resumeDetached's finalize captures the NON-ZERO exit from disk.
python3 "$LEDGER_CLI" finalize --ledger "$LEDGER" --ledger-id crash_0001 >/dev/null 2>"$TMP/final.err" || true
python3 - "$LEDGER" <<'PY' || bad "finalize did not capture finished/exit!=0"
import json,sys
rec=[r for r in json.load(open(sys.argv[1]))["runs"] if r["ledger_id"]=="crash_0001"][0]
assert rec["run_status"]=="finished", rec.get("run_status")
assert int(rec["exit_code"])!=0, rec.get("exit_code")
PY

# THE PREDICATE resumeDetached applies (Number(rec.exit_code) > 0) flags this record as a crash.
node -e '
  const fs=require("fs");
  const runs=JSON.parse(fs.readFileSync(process.argv[1],"utf8")).runs||[];
  const crashes=runs.filter(r=>r.detached && Number(r.exit_code)>0);
  if (crashes.length!==1) { console.error("want 1 crash, got",crashes.length); process.exit(1); }
' "$LEDGER" || bad "crash-detection predicate did not flag the exit!=0 detached record"

if [ "$ok" = 1 ]; then
  echo "PASS  mechanism: run-detach(exit 1) -> hook OS-wait+exit2 -> finalize -> crash-scan flags it"
  pass=$((pass+1))
else
  fail=$((fail+1))
fi

# ── (C) startup self-heal mechanism — PID KILLED mid-run (no exitcode) = the (b) interrupted branch ───────
# The fragile case: a detached run whose process dies (sleep/OOM/kill) BEFORE the wrapper writes its exitcode.
# resumeDetached's (b) branch keys on exactly this: kill -0 == dead AND finalize == "not finished yet".
ok2=1; bad2() { echo "FAIL  $1"; ok2=0; }
LEDGER2="$TMP/.polish/ledger2.json"; PIDFILE2="$TMP/.polish/.bg-pids2"
python3 "$LEDGER_CLI" init --ledger "$LEDGER2" --repo "$REPO" --project "$TMP" >/dev/null 2>&1
python3 "$LEDGER_CLI" run-detach --ledger "$LEDGER2" --repo "$REPO" --ledger-id killed_0001 \
  --cmd "sleep 120" --logdir "$TMP/.polish/runs2" --pidfile "$PIDFILE2" >/dev/null 2>&1
KPID=$(python3 -c "import json;print(json.load(open('$LEDGER2'))['runs'][0]['pid'])" 2>/dev/null)
kill -9 "$KPID" 2>/dev/null; sleep 1                                   # kill mid-run → no exitcode file is ever written
kill -0 "$KPID" 2>/dev/null && bad2 "killed PID $KPID still alive (kill -0 should be DEAD)"
out_nf="$(python3 "$LEDGER_CLI" finalize --ledger "$LEDGER2" --ledger-id killed_0001 2>&1)"
printf '%s' "$out_nf" | grep -q "not finished yet" || bad2 "finalize of a killed (no-exitcode) run should say 'not finished yet' (got: $out_nf)"
if [ "$ok2" = 1 ]; then
  echo "PASS  mechanism: killed-mid-run PID is DEAD + finalize 'not finished yet' = the (b) interrupted-crash branch"
  pass=$((pass+1))
else
  fail=$((fail+1))
fi

echo "----"; echo "t19_crash_surface: $pass passed, $fail failed"; [ "$fail" = 0 ]
