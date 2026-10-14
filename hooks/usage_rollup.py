#!/usr/bin/env python3
# auto-research — USAGE ROLLUP (Stop hook).
#
# WHY THIS EXISTS. bin/run_report.py rollup already derives token/cache usage (in/cache_w/cache_r/out,
# per role incl. L0, per model) from the native transcripts, but it's a PURE READER invoked by hand — nothing
# persists it automatically, and "token/model stats exist only while transcripts survive" (its own caveat).
# This hook makes that snapshot durable: every time L0's turn ends, re-derive the CURRENT run's rollup and
# overwrite runs/<slug>/usage-log.json with it, so the run's token/cache-write spend survives transcript
# pruning and is on disk the moment the run finishes (or crashes) — no manual step, no waiting for `/learn`.
#
# Cheap and idempotent by construction: rollup only reads local files (no LLM call), and each write is a full
# re-derive + overwrite (not an append), so a crash mid-write just leaves the PREVIOUS snapshot in place.
# Debounced (USAGE_ROLLUP_MIN_INTERVAL_S) so a chatty round doesn't re-glob every subagent transcript on every
# single Stop. Fails OPEN on anything unexpected — logging must never wedge a run (same contract as every
# other hook here: spawn_guard/ship_gate/decision_guard/lock_guard/writer_isolation).
import json
import os
import subprocess
import sys
import time

MIN_INTERVAL_S = int(os.environ.get("USAGE_ROLLUP_MIN_INTERVAL_S", "20"))
SUBPROCESS_TIMEOUT_S = 25


def _root():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_state(root):
    try:
        with open(os.path.join(root, "state", "pipeline-state.json")) as f:
            return json.load(f) or {}
    except Exception:
        return {}


def main():
    try:
        json.load(sys.stdin)   # consume stdin per hook hygiene; we don't need any of its fields (see below)
    except Exception:
        pass  # unparseable stdin is not fatal here — everything we need comes from state/pipeline-state.json

    root = _root()
    st = _read_state(root)
    run_id = st.get("run_id")
    if not run_id:
        return  # no active/ever-started run in this project -> nothing to log (silent, matches every other
                # hook's "no readable active-run state -> no-op" convention, e.g. spawn_guard.py)

    workspace = st.get("workspace")            # e.g. "runs/<slug>" — set once a paper is picked (applyPickedIdea)
    if workspace:
        out_path = os.path.join(root, workspace, "usage-log.json")
    else:
        # PRE-PICK FALLBACK (2026-09-03). This used to `return`, on the reasoning that pre-pick turns get
        # counted anyway "once rollup runs against this run_id after a paper is picked". That reasoning is
        # false for a WEEKLY IDEATION run, which never picks a paper at all: state.workspace stays null for
        # the entire run, so the rollup never fired even once and runs/ stayed an empty directory. The
        # 2026-W36 run therefore recorded ZERO token/cost data — its real spend (422K out / 13.5M cache-write
        # / 176M cache-read across 102 agents) existed only inside ~400MB of native transcripts that the
        # harness GCs after ~30 days. Write to a run-level path instead so a paperless run is still observable.
        out_path = os.path.join(root, "state", "usage-log.json")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        if time.time() - os.path.getmtime(out_path) < MIN_INTERVAL_S:
            return  # debounce: a snapshot this fresh is not worth re-deriving on every single Stop
    except OSError:
        pass  # file doesn't exist yet -> proceed

    run_report = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "run_report.py")
    try:
        subprocess.run(
            [sys.executable, run_report, "rollup", "--run", run_id, "--out", out_path],
            cwd=root, env={**os.environ, "CLAUDE_PROJECT_DIR": root},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=SUBPROCESS_TIMEOUT_S,
        )
    except Exception:
        pass  # logging must NEVER wedge a Stop


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)   # always allow Stop — this hook only observes, never gates
