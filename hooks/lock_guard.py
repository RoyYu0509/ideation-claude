#!/usr/bin/env python3
# auto-research — LOCK GUARD logic (PreToolUse). See lock_guard.sh for the why.
#
# The two ratchet BASELINES — HANDOFF.scale-contract.locked.json and HANDOFF.ambition.locked.json — are frozen at
# Phase 0(C) and owned exclusively by bin/lock_contracts.sh, which writes them through a shell `python3 <<PY`
# (Bash tool) that a Write|Edit|MultiEdit hook does NOT intercept. The per-round verifier diffs the re-authored
# work order against these baselines to catch a silent WEAKEN-TO-PASS, so an actor that overwrites a baseline
# poisons the very comparison the verifier depends on.
#
# This hook makes that structurally impossible: it denies any Write/Edit/MultiEdit whose basename is one of the
# two locked baselines. No legitimate actor uses the Write tool for them — bin/lock_contracts.sh (--ratchet
# TIGHTEN/REDIRECT/RAISE included) and the amplifier's HANDOFF.ambition.target.json write go through other paths,
# so they pass straight through. Deny list = exactly two basenames (NOT a *.locked.json glob), so the
# producing-worker's legitimate Write appends to AUDIT-ARTIFACTS.locked.json are untouched. Blast radius = two
# filenames.
#
# BASH-PATH SCOPE (dossier-12 D1, deliberate): Bash-side writes (`echo >` / heredoc / `python3 -c`) bypass a
# Write|Edit|MultiEdit hook BY DESIGN — the ONE legitimate writer (bin/lock_contracts.sh) IS a Bash heredoc,
# so a Bash matcher would wedge it, and full Bash coverage is unattainable. The Bash surface is prose law:
# agents/producing-worker.md forbids subagents authoring gate/lock/ship files via ANY tool; the wave-boundary
# SHA-diff audit (bin/audit_artifact_diff.sh) catches what prose does not.
import json, os, sys

FROZEN = {"HANDOFF.scale-contract.locked.json", "HANDOFF.ambition.locked.json"}


def allow():
    sys.exit(0)                       # silent allow, exit 0 — the harness proceeds


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        allow()                       # unparseable stdin => fail-open (blast radius stays narrow)
    ti = payload.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("path") or ""
    if not fp:
        allow()
    if os.path.basename(fp) in FROZEN:
        deny("lock_guard: this file is a FROZEN ratchet baseline locked at Phase 0(C) and owned exclusively by "
             "bin/lock_contracts.sh — it may NOT be authored/overwritten with Write/Edit/MultiEdit. Your "
             "re-authored §4b/§4c live ONLY in HANDOFF.md; to move the lock, run bin/lock_contracts.sh --ratchet "
             "(an audited TIGHTEN/REDIRECT/RAISE), never a direct Write/Edit overwrite of the baseline.")
    allow()


if __name__ == "__main__":
    main()
