#!/usr/bin/env bash
# bin/session_anchor.sh — anchor EVERY native session this run touches, into state/sessions.jsonl.
#
# WHY. A single logical run can span MORE THAN ONE session uuid: an asyncRewake / `--continue` re-wake stays
# in the same session, but if the owner closes the terminal and reopens `/auto-research` to resume, Claude
# Code starts a NEW <session-uuid>.jsonl with NO native link field back to the old one. snapshot_traces.sh +
# run_report.py must harvest ALL of those session dirs (the native L0/L1/L2 trace lives under
# <transcript dir>/subagents/). The L0-generated run_id in run-events.jsonl stitches the sessions into one
# run; THIS file is the index of transcript dirs to gather.
#
# TWO MODES (both dedup by session_id, both fail-open / exit 0):
#   (stdin)   SessionStart HOOK mode — reads the hook payload JSON {session_id, transcript_path, cwd, source}.
#             PRECISE, and the only way to catch a NEW session after a terminal reopen. Needs the hook to be
#             registered in .claude/settings.json (owner-authorized).
#   --self    L0 SELF-ANCHOR mode — no stdin; the running main session cannot read its own session_id (no env
#             var), so it heuristically takes the NEWEST <uuid>.jsonl in this project's ~/.claude dir as its
#             own transcript. Robust for the serial single-owner case; lets the system work even with NO hook.
# Both paths write the SAME dedup'd state/sessions.jsonl, so they compose.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
MODE="${1:-}"
PAYLOAD=""
[ "$MODE" = "--self" ] || PAYLOAD="$(cat 2>/dev/null || true)"

ROOT="$ROOT" MODE="$MODE" PAYLOAD="$PAYLOAD" python3 - <<'PY' 2>/dev/null || true
import os, json, time, glob, re
root = os.environ["ROOT"]
mode = os.environ.get("MODE") or ""

rec_in = None
if mode == "--self":
    # CC project slug: cwd with every non-alnum char -> '-'  (e.g. /Users/<you>/auto-research ->
    # -Users-you-auto-research). Pick the most-recently-written <uuid>.jsonl as L0's own transcript.
    slug = re.sub(r"[^A-Za-z0-9]", "-", root)
    projdir = os.path.expanduser(os.path.join("~/.claude/projects", slug))
    cands = [p for p in glob.glob(os.path.join(projdir, "*.jsonl"))]
    if cands:
        newest = max(cands, key=os.path.getmtime)
        sid = os.path.basename(newest)[:-len(".jsonl")]
        rec_in = {"session_id": sid, "transcript_path": newest, "cwd": root, "source": "self-heuristic"}
else:
    try:    p = json.loads(os.environ.get("PAYLOAD") or "{}")
    except Exception: p = {}
    if p.get("session_id"):
        rec_in = {"session_id": p["session_id"], "transcript_path": p.get("transcript_path") or "",
                  "cwd": p.get("cwd"), "source": p.get("source") or "hook"}

if not rec_in:
    raise SystemExit(0)                              # nothing to anchor

# HOOK mode fires for EVERY session start in this folder — including unrelated sessions the owner may open in a
# DATA_ROOT that has no auto-research run. Only anchor when a run actually exists here (pipeline-state.json), else
# we would pollute a random project's state/. --self mode is L0-driven (only ever called DURING a run) so it is
# TRUSTED and NOT guarded — it also runs at bootstrap BEFORE pipeline-state.json's first persist, which this
# guard would otherwise wrongly skip.
if mode != "--self" and not os.path.exists(os.path.join(root, "state", "pipeline-state.json")):
    raise SystemExit(0)

out = os.path.join(root, "state", "sessions.jsonl")
os.makedirs(os.path.dirname(out), exist_ok=True)
seen = {}                                            # session_id -> record (dedup, preserve insertion order)
if os.path.exists(out):
    for l in open(out):
        try:    d = json.loads(l); seen[d.get("session_id")] = d
        except Exception: pass

now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
run_id = None
try:    run_id = json.load(open(os.path.join(root, "state", "pipeline-state.json"))).get("run_id")
except Exception: pass

sid = rec_in["session_id"]
if sid in seen:
    seen[sid]["last_seen"] = now
    # fill fields a thinner earlier record may have missed
    for k in ("transcript_path", "cwd", "source"):
        if not seen[sid].get(k) and rec_in.get(k): seen[sid][k] = rec_in[k]
    if run_id and not seen[sid].get("run_id"): seen[sid]["run_id"] = run_id
else:
    rec_in.update({"run_id": run_id, "first_seen": now, "last_seen": now})
    seen[sid] = rec_in

with open(out, "w") as f:
    for d in seen.values():
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
PY
exit 0
