#!/usr/bin/env bash
# T3 (mechanism) — the vendored asyncRewake Stop hook's CORE: OS-wait a detached PID at zero token
# cost, then remove the pidfile and `exit 2` (the re-wake signal). This runs the REAL vendored
# rewake-when-done.sh against a real detached job, WITHOUT ending this session's turn. The full
# end-turn -> harness-re-wake roundtrip needs a fresh session in this repo (paper-polish-ar Stop hook
# active) and is recorded as verified pre-fire in tests/TESTS.md. Run: bash tests/t3_detach_rewake.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REWAKE="$ROOT/plugins/paper-polish-ar/hooks/rewake-when-done.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.polish"
pass=0; fail=0

# Case A — no pidfile: hook must be a silent, instant no-op (exit 0).
( CLAUDE_PROJECT_DIR="$TMP" bash "$REWAKE" >/dev/null 2>&1 ); rc=$?
[ "$rc" = 0 ] && { echo "PASS  no pidfile -> exit 0 (silent no-op)"; pass=$((pass+1)); } \
              || { echo "FAIL  no pidfile -> rc=$rc (want 0)"; fail=$((fail+1)); }

# Case B — detach a real short job (start_new_session, the exp_ledger.run-detach pattern), append its
# PID to .polish/.bg-pids, then run the hook: it must OS-wait until the PID exits, remove the pidfile,
# and exit 2. The detached job writes a marker ~2s after launch.
PID="$(python3 - "$TMP" <<'PY'
import sys, subprocess
proj = sys.argv[1]
p = subprocess.Popen(["sh","-c","sleep 2; echo REWAKE_OK > '%s/marker.txt'" % proj], start_new_session=True)
print(p.pid)
PY
)"
echo "$PID" > "$TMP/.polish/.bg-pids"
t0=$(date +%s)
( CLAUDE_PROJECT_DIR="$TMP" bash "$REWAKE" >/dev/null 2>&1 ); rc=$?
t1=$(date +%s); waited=$((t1-t0))
ok=1
[ "$rc" = 2 ] || { echo "FAIL  rewake rc=$rc (want 2 = re-wake signal)"; ok=0; }
[ -f "$TMP/marker.txt" ] && grep -q REWAKE_OK "$TMP/marker.txt" || { echo "FAIL  detached job did not complete"; ok=0; }
[ ! -f "$TMP/.polish/.bg-pids" ] || { echo "FAIL  pidfile not cleaned up"; ok=0; }
if [ "$ok" = 1 ]; then echo "PASS  detached job -> hook OS-waited ${waited}s, removed pidfile, exit 2"; pass=$((pass+1)); else fail=$((fail+1)); fi

# Case C — self-deadline (timeout contract, 2026-07-07): with a still-alive PID and an exhausted
# budget (REWAKE_BUDGET_S=0) the hook must exit 2 with a STILL-RUNNING re-arm message and KEEP the
# pidfile (the next Stop hook resumes the wait) — never be silently timeout-killed mid-wait.
# Use THIS test shell ($$) as the "running experiment": kill -0 $$ is always true, no spawn needed
# (some harness shells reap detached children instantly, so a spawned sleeper would be flaky here).
echo "$$" > "$TMP/.polish/.bg-pids"
err="$( CLAUDE_PROJECT_DIR="$TMP" REWAKE_BUDGET_S=0 bash "$REWAKE" 2>&1 >/dev/null )"; rc=$?
ok=1
[ "$rc" = 2 ] || { echo "FAIL  deadline rc=$rc (want 2 = re-arm signal)"; ok=0; }
printf '%s' "$err" | grep -q "still RUNNING" || { echo "FAIL  deadline stderr lacks STILL-RUNNING re-arm message"; ok=0; }
[ -f "$TMP/.polish/.bg-pids" ] || { echo "FAIL  deadline path removed the pidfile (must keep it for the re-armed wait)"; ok=0; }
if [ "$ok" = 1 ]; then echo "PASS  budget exhausted + live PID -> exit 2 re-arm, pidfile kept"; pass=$((pass+1)); else fail=$((fail+1)); fi

# Case D — hooks.json timeout lock: the harness kills a command hook at `timeout` (default 600s — the
# silent ">10 min experiment never re-wakes" root cause). The Stop hook entry MUST pin a large timeout.
HJ="$ROOT/plugins/paper-polish-ar/hooks/hooks.json"
TOUT="$(python3 - "$HJ" <<'PY'
import json, sys
h = json.load(open(sys.argv[1]))["hooks"]["Stop"][0]["hooks"][0]
print(h.get("timeout", 0) if h.get("asyncRewake") else "not-asyncRewake")
PY
)"
if [ "$TOUT" != "not-asyncRewake" ] && [ "$TOUT" -ge 3600 ] 2>/dev/null; then
  echo "PASS  hooks.json Stop hook: asyncRewake + timeout=$TOUT (>=3600; default-600s kill can't bite)"; pass=$((pass+1))
else
  echo "FAIL  hooks.json Stop hook timeout=$TOUT (want asyncRewake:true with timeout >= 3600)"; fail=$((fail+1))
fi

echo "----"; echo "t3_detach_rewake: $pass passed, $fail failed"; [ "$fail" = 0 ]
