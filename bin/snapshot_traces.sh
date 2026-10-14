#!/usr/bin/env bash
# bin/snapshot_traces.sh [<run_id>] — TRUE-COPY this run's full-depth native trace into runs/_trace/<run_id>/.
#
# WHY. Claude Code's native per-agent transcripts (L0 <session>.jsonl + the FLAT
# <session>/subagents/agent-<id>.jsonl for every L1/L2/… + tool-results/) are the ONLY complete action trace,
# but they live OUTSIDE the repo and are GC'd after cleanupPeriodDays (default 30). A run can finish long
# after — so we snapshot a TRUE COPY (independent of the GC unlink) into runs/_trace/ (already .gitignore'd
# via runs/, so it never bloats git). run_report.py reads from here OR from the live native dir.
#
# Anchors via state/sessions.jsonl (written by session_anchor.sh, hook- or --self-mode). If that's empty it
# self-anchors first. Filters to THIS run's sessions (run_id match, or null = early self-anchor before run_id
# was set). Idempotent: re-running overwrites/updates the snapshot (incremental via shutil dirs_exist_ok).
# ALWAYS exit 0 (fail-open — a snapshot failure must never kill a run).
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RUN_ID_ARG="${1:-}"
[ -s "$ROOT/state/sessions.jsonl" ] || bash "$ROOT/bin/session_anchor.sh" --self 2>/dev/null || true

ROOT="$ROOT" RUN_ID_ARG="$RUN_ID_ARG" python3 - <<'PY' 2>/dev/null || true
import os, json, shutil
root = os.environ["ROOT"]
run_id = os.environ.get("RUN_ID_ARG") or ""
if not run_id:
    try:    run_id = json.load(open(os.path.join(root, "state", "pipeline-state.json"))).get("run_id") or ""
    except Exception: pass
run_id = run_id or "unknown-run"

sessions = []
sf = os.path.join(root, "state", "sessions.jsonl")
if os.path.exists(sf):
    for l in open(sf):
        try:    sessions.append(json.loads(l))
        except Exception: pass
# keep this run's sessions (+ null run_id = self-anchored before run_id was persisted); fallback to all
sess = [s for s in sessions if s.get("run_id") in (run_id, None)] or sessions

dest_root = os.path.join(root, "runs", "_trace", run_id)

def cptree(src, dst):
    try:    shutil.copytree(src, dst, dirs_exist_ok=True)        # py3.8+: incremental overwrite
    except TypeError:                                            # older py: rebuild
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst)

n_sess = n_agent = 0
for s in sess:
    sid = s.get("session_id"); tp = s.get("transcript_path") or ""
    if not sid: continue
    dest = os.path.join(dest_root, sid); os.makedirs(dest, exist_ok=True)
    if tp and os.path.exists(tp):
        shutil.copy2(tp, os.path.join(dest, os.path.basename(tp)))         # L0 main transcript
    sessdir = tp[:-6] if tp.endswith(".jsonl") else os.path.join(os.path.dirname(tp), sid)
    for sub in ("subagents", "tool-results", "workflows"):                  # L1/L2 trace + overflow + workflows
        srcsub = os.path.join(sessdir, sub)
        if os.path.isdir(srcsub):
            cptree(srcsub, os.path.join(dest, sub))
    n_sess += 1
    sa = os.path.join(dest, "subagents")
    if os.path.isdir(sa):
        n_agent += len([f for f in os.listdir(sa) if f.endswith(".jsonl")])

total = 0
for dp, _, fs in os.walk(dest_root):
    for f in fs:
        try: total += os.path.getsize(os.path.join(dp, f))
        except Exception: pass
print("SNAPSHOT run_id=%s sessions=%d agent_jsonl=%d size=%.1fMB dest=runs/_trace/%s"
      % (run_id, n_sess, n_agent, total / 1e6, run_id))
PY
exit 0
