#!/usr/bin/env python3
# auto-research — CENTRAL-AMBITION-NARROW GUARD logic (PreToolUse). See central_narrow_guard.sh for the why.
#
# WHY THIS EXISTS. spec/research.js's runCentralAmbitionGuard is an L0-COOPERATIVE check: it re-derives
# whether a concern backing HANDOFF.ambition.locked.json's central_result/GAMBLE set is narrowing this round
# with no research-rescue verdict on disk, BEFORE L0 records a milestone done. That is the primary path. But
# research.js is an LLM-READ SPEC, not a literally-executed program — an L0 that skips the check "for a good
# reason" bypasses it, exactly the RC-11 ship-gate collapse shape (STATUS-MODEL.md §8). This hook is the
# harness-enforced backstop: it engages on a subagent's OWN Write/Edit/MultiEdit to TASK_STATUS.concerns.json
# (a resumed experiment_worker writing a status change directly, invisible to L0's own runCentralAmbitionGuard
# call if L0 skipped it) and re-runs the SAME deterministic oracle (bin/central_ambition_guard.sh) against the
# PROPOSED content before it lands. It never duplicates the detection logic — it reuses the script's
# --live-file mode built for exactly this reuse.
#
# On the cooperative path (L0 already ran the guard and a rescue verdict is already on disk), the reconstructed
# proposed content is already past-rescue, so this hook is a silent no-op — it only ever engages when something
# bypassed layer 1.
#
# BASH-PATH SCOPE (mirrors lock_guard/ship_gate's note): a Bash-side write bypasses this hook by design; the
# LEDGER_CONTAINER prose (spec/research.js) instructs every writer to go through Write/Edit/MultiEdit for this
# file, so the residual leak surface mirrors the sibling hooks' documented residual.
import json, os, sys, subprocess, tempfile

TARGET = "TASK_STATUS.concerns.json"


def allow():
    sys.exit(0)  # silent allow — the harness proceeds


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.exit(0)


def find(rel, ws):
    """Locate a repo/plugin-root-relative path via env roots, then by walking up from the workspace."""
    for root in (os.environ.get("CLAUDE_PLUGIN_ROOT"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if root and os.path.isfile(os.path.join(root, rel)):
            return os.path.join(root, rel)
    d = ws
    for _ in range(7):
        d = os.path.dirname(d)
        if not d:
            break
        if os.path.isfile(os.path.join(d, rel)):
            return os.path.join(d, rel)
    return None


def find_state(ws):
    """Locate state/pipeline-state.json (mirrors writer_isolation.py's find_state) — reads loop_round."""
    rel = os.path.join("state", "pipeline-state.json")
    for root in (os.environ.get("CLAUDE_PROJECT_DIR"), os.environ.get("CLAUDE_PLUGIN_ROOT")):
        if root and os.path.isfile(os.path.join(root, rel)):
            return os.path.join(root, rel)
    d = ws
    for _ in range(7):
        d = os.path.dirname(d)
        if not d:
            break
        if os.path.isfile(os.path.join(d, rel)):
            return os.path.join(d, rel)
    return None


def apply_edit(text, old, new, replace_all):
    if old == "":
        return None  # a create-style empty old_string is not a content narrowing we can reason about here
    if replace_all:
        return text.replace(old, new)
    idx = text.find(old)
    if idx == -1:
        return None
    return text[:idx] + new + text[idx + len(old):]


def reconstruct(tool_name, ti, fp):
    """Best-effort reconstruction of the PROPOSED file content. Any failure -> None (caller fails open —
    this is a backstop, not the primary detection path; the L0-cooperative layer is)."""
    try:
        if tool_name == "Write":
            c = ti.get("content")
            return c if isinstance(c, str) else None
        current = open(fp, encoding="utf-8").read() if os.path.isfile(fp) else "{}"
        if tool_name == "Edit":
            return apply_edit(current, ti.get("old_string", ""), ti.get("new_string", ""),
                               bool(ti.get("replace_all")))
        if tool_name == "MultiEdit":
            for e in (ti.get("edits") or []):
                nxt = apply_edit(current, e.get("old_string", ""), e.get("new_string", ""),
                                  bool(e.get("replace_all")))
                if nxt is None:
                    return None
                current = nxt
            return current
    except Exception:
        return None
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        allow()
    tool_name = payload.get("tool_name") or ""
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        allow()
    ti = payload.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("path") or ""
    if not fp or os.path.basename(fp) != TARGET:
        allow()
    fp = os.path.abspath(fp)
    ws = os.path.dirname(fp)

    proposed = reconstruct(tool_name, ti, fp)
    if proposed is None:
        allow()  # could not reconstruct with confidence -> fail open, this is a backstop not the primary path

    state_path = find_state(ws)
    round_no = None
    if state_path:
        try:
            round_no = (json.load(open(state_path, encoding="utf-8")) or {}).get("loop_round")
        except Exception:
            round_no = None
    if round_no is None:
        allow()  # cannot confirm the round -> fail open (the oracle needs a round to find the before-snapshot)

    oracle = find(os.path.join("bin", "central_ambition_guard.sh"), ws)
    if not oracle:
        allow()  # oracle unreachable -> fail open (backstop only; the L0-cooperative layer is primary)

    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(proposed)
            tmp = f.name
        out = subprocess.run(
            ["bash", oracle, "check", ws, str(round_no), "--live-file", tmp],
            capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        allow()  # oracle failed to run -> fail open
    finally:
        if tmp and os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

    if out.startswith("NEEDS_RESCUE"):
        ids = out.replace("NEEDS_RESCUE", "", 1).strip()
        deny("central-ambition-guard: this write would narrow %s (a concern backing "
             "HANDOFF.ambition.locked.json's central_result/GAMBLE set) with no research-rescue verdict on "
             "disk for it this round. A central K's disposition must not be self-applied by a resumed worker — "
             "surface it as an escalation so L0's runCentralAmbitionGuard can spawn research-rescue first "
             "(禁止轻易放弃或降低目标)." % ids)
    allow()


if __name__ == "__main__":
    main()
