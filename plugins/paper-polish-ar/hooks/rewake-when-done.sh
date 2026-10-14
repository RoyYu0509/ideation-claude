#!/usr/bin/env bash
# asyncRewake Stop hook — re-wakes the /review session when its long background experiment(s) finish.
#
# CONTRACT (see skills/experiment-run): when the /review experiment phase fires a long LOCAL run, the
# orchestrator launches it with `exp_ledger.py run-detach` (which appends the child PID to
# .polish/.bg-pids) and then ENDS ITS TURN — it does NOT poll. This hook does the waiting OUTSIDE the
# agent loop: a pure OS wait that costs ZERO Claude tokens, then `exit 2` re-wakes the session once
# every fired job has finished, so it can finalize → audit → write the results back.
#
# TIMEOUT CONTRACT: the harness KILLS a command hook at hooks.json `timeout` — silently (no transcript
# trace), and the default is 600s. That default was the root cause of every ">10 min experiment never
# re-wakes" failure (2026-07-07, memory rewake-hook-600s-timeout-rootcause). hooks.json therefore sets
# timeout: 86400, and this script SELF-DEADLINES just under it (REWAKE_BUDGET_S, default 86100): on
# expiry it exits 2 with a STILL-RUNNING message — L0's resumeDetached alive-branch re-arms the wait
# (keep state.detached, end turn, a fresh Stop hook resumes), so no wait ever dies silently again.
# Lifecycle is appended to .polish/.rewake-hook.log so the next failure is diagnosable from disk.
#
# It MUST stay silent (exit 0, instantly) whenever there is no PIDFILE, so it never interferes with
# /polish, an ordinary /review turn with no long job, or any other session. The PIDFILE is project-
# scoped, so a session in another project is unaffected.
set -u

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
pidfile="$proj/.polish/.bg-pids"
logf="$proj/.polish/.rewake-hook.log"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$logf" 2>/dev/null || true; }

# No fired jobs → do nothing. This is the common case on every Stop; keep it cheap and silent.
[ -f "$pidfile" ] || exit 0
pids=$(grep -E '^[0-9]+$' "$pidfile" 2>/dev/null)
[ -n "$pids" ] || { rm -f "$pidfile"; exit 0; }

budget="${REWAKE_BUDGET_S:-86100}"
log "armed pid=$$ budget=${budget}s waiting-on: $(printf '%s ' $pids)"

# Wait for every fired PID. They were started in a new session by a now-exited process, so they are NOT
# children of this shell — `wait` cannot reap them; a `kill -0` poll is the portable way. The sleep loop
# blocks INSIDE this single shell invocation (no agent turn is running), so it burns no Claude tokens.
# $SECONDS (time since this shell started ≈ time since the Stop) enforces the self-deadline.
for pid in $pids; do
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$SECONDS" -ge "$budget" ]; then
      alive=$(for p in $pids; do kill -0 "$p" 2>/dev/null && printf '%s ' "$p"; done)
      log "deadline exit=2 still-running: ${alive}(pidfile kept)"
      echo "[paper-polish] rewake watchdog hit its ${budget}s wait budget with experiment PID(s) ${alive}still RUNNING — do NOT finalize: re-arm and end the turn (resumeDetached alive-branch keeps state.detached; the next Stop hook resumes the wait)." >&2
      exit 2
    fi
    sleep 5
  done
done

rm -f "$pidfile"
log "delivered exit=2 all-finished"
echo "[paper-polish] all fired background experiment(s) have finished — resume /review to finalize, audit, and write the results back." >&2
exit 2
