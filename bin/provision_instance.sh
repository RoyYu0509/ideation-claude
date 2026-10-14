#!/usr/bin/env bash
# bin/provision_instance.sh <DATA_ROOT> <PLUGIN_ROOT> — self-provision the per-instance harness config so that
# EVERY session of this run (including a terminal-reopen resume, which is a NEW session uuid) is deterministically
# captured — WITHOUT relying on the L0 model to enact a side-channel anchor call each session.
#
# WHY. A run spans multiple native sessions; the trace snapshot (snapshot_traces.sh) only harvests the session
# dirs listed in state/sessions.jsonl, and that index was fed ONLY by the L0-enacted `session_anchor.sh --self`
# (a [[MECH]] side-channel the model skips on the resume fast-paths). Result: only session 1 was ever anchored,
# and sessions 2..N (their whole subagent trees) never reached runs/_trace/. The airtight fix (RUNBOOK §8) is a
# SessionStart hook → session_anchor.sh, which the HARNESS fires once per session start regardless of what L0
# does. This script writes that hook into the DATA_ROOT's own folder-level settings so it arms automatically for
# this instance — no global pollution, no per-instance manual step.
#
# Timing self-consistency: L0 runs this at main() bootstrap in session 1; the hook it writes then arms sessions
# 2..N (hooks are read at session start, so the hook does NOT fire for the current session — session 1 is still
# covered by the existing anchorSelf() --self call). Idempotent: re-running merges the SAME entry, never dupes.
#
# We write .claude/settings.LOCAL.json (git-ignored, machine-local, auto-generated) and MERGE — we never clobber
# an owner-authored .claude/settings.json, and we preserve any keys/hooks already present in the local file.
# ALWAYS exit 0 (fail-open — a provisioning failure must never kill a run).
set -u
DATA_ROOT="${1:-}"
PLUGIN_ROOT="${2:-}"
[ -n "$DATA_ROOT" ]   || { echo "WARN provision_instance: no <DATA_ROOT> arg; nothing provisioned" >&2; exit 0; }
[ -n "$PLUGIN_ROOT" ] || { echo "WARN provision_instance: no <PLUGIN_ROOT> arg; nothing provisioned" >&2; exit 0; }

DATA_ROOT="$DATA_ROOT" PLUGIN_ROOT="$PLUGIN_ROOT" python3 - <<'PY' 2>/dev/null || true
import os, json
data_root   = os.environ["DATA_ROOT"]
plugin_root = os.environ["PLUGIN_ROOT"]

# ABSOLUTE path baked at provision time — a project-settings hook context does NOT get ${CLAUDE_PLUGIN_ROOT}
# expanded (that var is a plugin-hook nicety), so we must not reference it here. (Same lesson as the detached
# pidfile bug: never let a hook reconstruct a path from an env var that is empty in its context.)
anchor = os.path.join(plugin_root, "bin", "session_anchor.sh")

settings_dir  = os.path.join(data_root, ".claude")
settings_path = os.path.join(settings_dir, "settings.local.json")   # local/auto-generated; merged by CC, git-ignored

cfg = {}
if os.path.exists(settings_path):
    try:    cfg = json.load(open(settings_path)) or {}
    except Exception: cfg = {}                                      # unparseable → start clean (never crash)
if not isinstance(cfg, dict): cfg = {}

hooks = cfg.setdefault("hooks", {})
if not isinstance(hooks, dict): hooks = cfg["hooks"] = {}
ss = hooks.setdefault("SessionStart", [])
if not isinstance(ss, list): ss = hooks["SessionStart"] = []

# Idempotence: an entry whose command IS our anchor already anchors every session — do nothing.
def has_anchor(entry):
    if not isinstance(entry, dict): return False
    for h in entry.get("hooks", []) or []:
        if isinstance(h, dict) and h.get("command") == anchor: return True
    return False

changed = False
if not any(has_anchor(e) for e in ss):
    # No matcher ⇒ fires on EVERY SessionStart source (startup / resume / clear / compact) — we want to anchor
    # every native session uuid this instance ever opens.
    ss.append({"hooks": [{"type": "command", "command": anchor}]})
    changed = True

if changed:
    os.makedirs(settings_dir, exist_ok=True)
    with open(settings_path, "w") as f:
        f.write(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    print(f"provision_instance: armed SessionStart→session_anchor in {settings_path}")
else:
    print("provision_instance: SessionStart anchor already present (no change)")
PY
exit 0
