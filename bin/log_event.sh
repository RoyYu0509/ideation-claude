#!/usr/bin/env bash
# bin/log_event.sh — append ONE structured event to state/run-events.jsonl (the unified L0 event stream).
#
# This is the single sanctioned writer-helper for the run-events stream (spec/run-event-schema.json). The
# L0 spec calls it at every semantic seam; the existing bin scripts (derive_gate_input / scan_orphan_stops /
# hook_fire_log) reuse it so EVERY runtime signal lands in ONE grep-able place ("统一回收"). The stream is a
# PURE SIDE-CHANNEL — no control-flow ever reads it back; logging must therefore NEVER block a run.
#
# Usage:  bin/log_event.sh <event> [<payload-json>]
#   <event>         one of the enum in spec/run-event-schema.json.
#   <payload-json>  optional JSON OBJECT; its keys are merged at the event's top level (event-specific fields).
#
# WRAPPER fields are auto-filled: ts (UTC ISO8601), run_id, paper, round, milestone, stage — read from
# state/pipeline-state.json, each overridable via env AR_RUN_ID / AR_PAPER / AR_ROUND / AR_MILESTONE / AR_STAGE
# (run_start passes AR_RUN_ID because pipeline-state.json has no run_id yet at that instant).
#
# ALWAYS exits 0 (fail-open). A logging failure is warned to stderr, never propagated.
set -u
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
EVENT="${1:-}"
PAYLOAD="${2:-}"; [ -n "$PAYLOAD" ] || PAYLOAD='{}'
[ -n "$EVENT" ] || { echo "WARN log_event: no <event> given; nothing logged" >&2; exit 0; }

ROOT="$ROOT" EVENT="$EVENT" PAYLOAD="$PAYLOAD" \
AR_RUN_ID="${AR_RUN_ID:-}" AR_PAPER="${AR_PAPER:-}" AR_ROUND="${AR_ROUND:-}" \
AR_MILESTONE="${AR_MILESTONE:-}" AR_STAGE="${AR_STAGE:-}" \
python3 - <<'PY' 2>/dev/null || true
import os, json, time
root = os.environ["ROOT"]
st = {}
try:    st = json.load(open(os.path.join(root, "state", "pipeline-state.json")))
except Exception: st = {}

def pick(env_key, state_key):
    v = os.environ.get(env_key) or ""
    return v if v != "" else st.get(state_key)

rec = {
    "ts":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),   # single clock source (UTC)
    "run_id":    pick("AR_RUN_ID", "run_id"),
    "event":     os.environ["EVENT"],
    "paper":     pick("AR_PAPER", "paper_slug"),
    "round":     pick("AR_ROUND", "loop_round"),
    "milestone": pick("AR_MILESTONE", "milestone"),
    "stage":     pick("AR_STAGE", "stage"),
}
# merge event-specific payload at top level (payload keys win for their own names)
try:
    pl = json.loads(os.environ.get("PAYLOAD") or "{}")
    if isinstance(pl, dict):
        rec.update(pl)
    else:
        rec["_payload_not_object"] = True
except Exception as e:
    rec["_payload_parse_error"] = str(e)
    rec["_payload_raw"] = (os.environ.get("PAYLOAD") or "")[:500]

out = os.path.join(root, "state", "run-events.jsonl")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "a") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
exit 0
