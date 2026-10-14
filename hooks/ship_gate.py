#!/usr/bin/env python3
# auto-research — deterministic SHIP-GATE logic (PreToolUse). See ship_gate.sh for the why (RC-11).
#
# It gates the one irreversible ACT that marks a paper shipped — writing the workspace FINAL-REPORT.md — on
# the already-canonical readiness oracle (bin/pipeline_status.sh), and it forbids the combined-finishing file
# (FINISHING_REPORT.md) that is the collapse regression's signature. It does NOT add a second/parallel rule:
# it is the SAME oracle assertShipReady already calls, moved OUTSIDE the L0 reproduction so the harness — not
# L0's reasoning — enforces it. Blast radius is exactly two filenames; every other edit passes straight through.
#
# Two denials:
#   1. ANY write whose basename is FINISHING_REPORT.md — the writing-engine stages each write their OWN report;
#      a single combined "finishing" file is never legal.
#   2. A workspace FINAL-REPORT.md write when pipeline_status.sh does NOT report SHIP_READY yes. Fails CLOSED
#      for this one surface: if the oracle is unreachable we still refuse the ship-report rather than let a
#      premature ship through.
#
# BASH-PATH SCOPE (dossier-12 D1, deliberate): this hook sees Write|Edit|MultiEdit ONLY. A Bash-side write
# (`echo >` / heredoc / `python3 -c`) bypasses it BY DESIGN — the legitimate writer (L0's ship()) writes the
# FINAL-REPORT via Bash, so a Bash matcher would wedge the one sanctioned path, and full Bash coverage is
# unattainable anyway (python-write/dd/sed -i…). The Bash surface is covered by PROSE LAW instead:
# research.js:2588 forbids L0 hand-writing it off-path; agents/producing-worker.md forbids every subagent
# from authoring gate/lock/ship files via ANY tool.
import json, os, sys, subprocess


def allow():
    # Silent allow: no output, exit 0 (the harness proceeds with the tool call).
    sys.exit(0)


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
    for _ in range(6):
        d = os.path.dirname(d)
        if os.path.isfile(os.path.join(d, rel)):
            return os.path.join(d, rel)
    return None


def require_list(ws):
    """Mirror spec/research.js shipRequireList(): verify_final + freeze_findings + story + write + freeze are
    MANDATORY; figures/edit only if their config toggle is on. Dependency-free line scan of the `writing:` block."""
    toggles = {"figures": True, "edit": True}  # config defaults (both on)
    cfg = find(os.path.join("config", "config.yaml"), ws)
    if cfg:
        try:
            inblk = False
            for line in open(cfg, encoding="utf-8"):
                if line.startswith("writing:"):
                    inblk = True
                    continue
                if inblk:
                    if line[:1] not in (" ", "\t", "#", "\n", "\r"):  # next top-level key ends the block
                        break
                    s = line.strip()
                    for k in toggles:
                        if s.startswith(k + ":"):
                            toggles[k] = "true" in s.split("#", 1)[0].split(":", 1)[1].lower()
        except Exception:
            pass
    require = ["verify_final", "freeze_findings", "story", "write"]
    if toggles["figures"]:
        require.append("figures")
    if toggles["edit"]:
        require.append("edit")
    require.append("freeze")
    return require


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        allow()  # unparseable stdin => behave as if no relevant tool call (fail-open for non-ship writes)
    ti = payload.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("path") or ""
    if not fp:
        allow()
    base = os.path.basename(fp)

    # (1) The banned combined-finishing artifact — deny unconditionally.
    if base == "FINISHING_REPORT.md":
        deny("FINISHING_REPORT.md is never a legal artifact — it is the signature of the silent "
             "finishing-collapse regression (the post-loop writing stages compressed into one improvised pass). "
             "Run verify_final -> freeze_findings -> story -> write -> figures -> edit -> freeze as SEPARATE "
             "stages; each records its OWN ledger entry. Do not write a combined finishing file.")

    # (2) The workspace ship report — gate on the deterministic readiness oracle.
    if base != "FINAL-REPORT.md":
        allow()
    ws = os.path.dirname(os.path.abspath(fp))
    # Only gate an auto-research workspace ship (the L0 ledger lives there); anything else is unrelated.
    if not os.path.isfile(os.path.join(ws, "milestone-state.json")):
        allow()

    oracle = find(os.path.join("bin", "pipeline_status.sh"), ws)
    if not oracle:
        deny("ship-gate: bin/pipeline_status.sh (the readiness oracle) is not reachable from "
             "CLAUDE_PLUGIN_ROOT / CLAUDE_PROJECT_DIR / the workspace. Refusing to write FINAL-REPORT.md "
             "without verifying the finishing stages ran. Ensure bin/ is synced to the active plugin root.")

    try:
        out = subprocess.run(["bash", oracle, ws, "--require", ",".join(require_list(ws))],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        deny("ship-gate: could not run the readiness oracle (%s). Refusing the FINAL-REPORT.md write." % e)

    if "SHIP_READY yes" in out:
        allow()
    deny("ship-gate: REFUSING to write FINAL-REPORT.md — bin/pipeline_status.sh reports the paper is NOT "
         "ship-ready (a required finishing stage left no on-disk ledger entry = it never ran, or git provenance "
         "is missing). Do NOT improvise the ship: run each missing stage (verify_final / freeze_findings / "
         "story / write / figures / edit / freeze) to completion via spec/research.js so it records its ledger "
         "entry, THEN ship.\nOracle output:\n" + out)


if __name__ == "__main__":
    main()
