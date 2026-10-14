#!/usr/bin/env python3
# auto-research — DECISION GUARD logic (PreToolUse). See decision_guard.sh for the why.
#
# Gates exist at exactly ONE tier (L0, fact #3): an L1/L2 subagent must NEVER resolve a human gate. But the
# decision ARCHIVE was body-less spec prose ("mv PENDING -> RESOLVED-<n>") that the L0 reproduced by hand, so
# (the 2026-06-30 real run) an experiment L1 simply WROTE a DECISIONS-RESOLVED-7.md itself while still
# running — self-applying a K-criterion scope change without L0's validation / state transition / logging.
#
# This hook makes that structurally impossible: it denies any Write/Edit/MultiEdit that MINTS a
# DECISIONS-RESOLVED-*.md. No legitimate actor uses the Write tool for these — they are created by
# bin/archive_decision.sh (a heredoc-python os.replace — an atomic rename), which a Write|Edit|MultiEdit
# hook does NOT intercept. So L0's
# DECISIONS-PENDING.md gate writes and the deterministic bin/ archival both pass straight through; only the
# forbidden agent-authored RESOLVED file is blocked. Blast radius = one filename pattern.
#
# BASH-PATH SCOPE (dossier-12 D1, deliberate): a Bash-side write bypasses this hook BY DESIGN — the ONE
# legitimate writer (bin/archive_decision.sh) IS a Bash heredoc-python, so a Bash matcher would wedge it,
# and full Bash coverage is unattainable (python-write/dd/sed -i…). The Bash surface is prose law:
# research.js gate discipline (L0 only resolves via bin/archive_decision.sh) + agents/producing-worker.md's
# ban on subagents authoring gate/lock/ship files via ANY tool.
import json, os, re, sys

RESOLVED = re.compile(r"^DECISIONS-RESOLVED-.*\.md$")


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
    if RESOLVED.match(os.path.basename(fp)):
        deny("decision_guard: a DECISIONS-RESOLVED-*.md file may NOT be authored with Write/Edit/MultiEdit. "
             "Gates are L0-only (fact #3) and the archive is deterministic: L0 resolves a gate by running "
             "bin/archive_decision.sh (it `mv`s DECISIONS-PENDING.md -> DECISIONS-RESOLVED-<n>.md after "
             "validating the owner's answer). A subagent must NEVER self-resolve a gate; surface the decision "
             "to L0 via your envelope's escalations[] instead.")
    allow()


if __name__ == "__main__":
    main()
