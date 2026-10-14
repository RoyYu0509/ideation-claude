#!/usr/bin/env bash
# T17 — the asyncRewake re-wake LANDING (spec/research.js resumeDetached). onLongRun records a detached
# long experiment + ends the turn; the vendored Stop hook OS-waits the PID at zero token cost and exit-2
# re-wakes the session; main() then routes the non-empty state.detached to resumeDetached, which FINALIZES
# each detached exp_ledger record FROM DISK (mirrors review.js resumeOneDetached) and clears state.detached
# so batchGroundClean's quiesce invariant holds. Before this, resumeDetached was CALLED but never DEFINED —
# any rewake with state.detached threw a ReferenceError (mechanism 6, the long-experiment detach path).
# This test proves (A) the spec wiring (the function exists + drives exp_ledger finalize + clears state +
# pins the no-re-run/no-re-finalize re-wake contract + the spec parses) and (B) the underlying mechanism
# end-to-end against the REAL exp_ledger.py run-detach -> hook -> finalize chain that resumeDetached drives.
# Run: bash tests/t17_resume_detached.sh
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

# ── (A) spec/research.js wiring — the regression guard for the ReferenceError ──────────────────────────
chk "spec: resumeDetached is DEFINED (was the undefined-call bug)" "grep -qE 'function resumeDetached\\(' '$SPEC'"
chk "spec: resumeDetached is CALLED on the rewake branch"         "grep -qF 'resumeDetached(state)' '$SPEC'"
chk "spec: resumeDetached drives exp_ledger.py finalize"          "grep -qF 'finalize --ledger' '$SPEC'"
chk "spec: resumeDetached finalizes only still-running records"   "grep -qF \"rec.run_status === 'running'\" '$SPEC'"
chk "spec: resumeDetached clears state.detached (quiesce)"        "grep -qF 'state.detached = []' '$SPEC'"
chk "spec: resumeDetached reaps the tracked pidfile"              "grep -qE 'rm -f .\\\$\\{d.pidfile\\}' '$SPEC'"
chk "spec: B1 goal pins state_path = run-detach LEDGER"           "grep -qF 'state_path is the run-detach LEDGER' '$ESPEC'"
chk "spec: B1 goal forbids re-run + re-finalize on re-wake"       "grep -qF 'do NOT call exp_ledger.py finalize' '$ESPEC'"
chk "spec: parses (node --check)"                                 "node --check '$SPEC'"

# ── (B) mechanism — REAL exp_ledger run-detach -> vendored hook -> finalize (the chain resumeDetached drives)
REPO="$TMP/repo"; mkdir -p "$REPO" "$TMP/.polish"; git -C "$REPO" init -q
LEDGER="$TMP/.polish/run-ledger.json"           # === the L1's detached.state_path
PIDFILE="$TMP/.polish/.bg-pids"                 # === the L1's detached.pidfile (the hook reads $PROJ/.polish/.bg-pids)
RESULTS="$REPO/results.json"

python3 "$LEDGER_CLI" init --ledger "$LEDGER" --repo "$REPO" --project "$TMP" >/dev/null 2>&1
# fire a SHORT detached run that produces a real results.json + exit 0 (stand-in for an hours-long segment).
python3 "$LEDGER_CLI" run-detach --ledger "$LEDGER" --repo "$REPO" --ledger-id run_0001 \
  --cmd "sleep 1; printf '{\"value\": 0.42}' > '$RESULTS'" \
  --logdir "$TMP/.polish/runs" --pidfile "$PIDFILE" \
  --products "$RESULTS" --results "$RESULTS" --extract "metric=value" >/dev/null 2>&1

# the detached record exists and is still 'running' (this is what resumeDetached scans the ledger for).
python3 - "$LEDGER" <<'PY' || bad "run-detach did not register a running detached record"
import json,sys
r=json.load(open(sys.argv[1]))["runs"][0]
assert r["detached"] is True and r["run_status"]=="running", r
PY

# the REAL Stop hook OS-waits the PID, removes the pidfile, and exit-2 re-wakes us (the zero-token wait).
( CLAUDE_PROJECT_DIR="$TMP" bash "$REWAKE" >/dev/null 2>&1 ); rc=$?
[ "$rc" = 2 ]            || bad "rewake hook rc=$rc (want 2 = re-wake signal)"
[ ! -f "$PIDFILE" ]     || bad "rewake hook did not remove the pidfile"

# resumeDetached's core primitive: finalize captures the after-state FROM DISK (exit code + product + number).
python3 "$LEDGER_CLI" finalize --ledger "$LEDGER" --ledger-id run_0001 > "$TMP/final.json" 2>"$TMP/final.err"; frc=$?
[ "$frc" = 0 ] || bad "finalize exited $frc (want 0); err=$(cat "$TMP/final.err")"
python3 - "$TMP/final.json" <<'PY' || bad "finalize did not capture finished/exit0/the extracted number"
import json,sys
rec=json.load(open(sys.argv[1]))
assert rec["run_status"]=="finished", rec.get("run_status")
assert rec["exit_code"]==0, rec.get("exit_code")
assert any(e.get("token")=="metric" and e.get("value")=="0.42" for e in rec.get("extracted_numbers",[])), rec.get("extracted_numbers")
PY

# the no-DOUBLE-finalize invariant the B1 goal-note enforces: once L0 finalizes, a SECOND finalize (e.g. a
# resume L1 that wrongly re-finalizes) errors "not finished yet" — proving L0 must own the single finalize.
out2="$(python3 "$LEDGER_CLI" finalize --ledger "$LEDGER" --ledger-id run_0001 2>&1)"; frc2=$?
[ "$frc2" != 0 ] && printf '%s' "$out2" | grep -q "not finished yet" \
  || bad "second finalize should error 'not finished yet' (rc=$frc2, out=$out2)"

if [ "$ok" = 1 ]; then
  echo "PASS  mechanism: run-detach -> hook OS-wait+exit2 -> finalize (after-state from disk) -> single-finalize guard"
  pass=$((pass+1))
else
  fail=$((fail+1))
fi

echo "----"; echo "t17_resume_detached: $pass passed, $fail failed"; [ "$fail" = 0 ]
