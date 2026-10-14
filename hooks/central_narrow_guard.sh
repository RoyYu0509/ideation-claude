#!/usr/bin/env bash
# auto-research — CENTRAL-AMBITION-NARROW GUARD (PreToolUse hook).
#
# WHY THIS EXISTS. spec/research.js's runCentralAmbitionGuard (the L0-cooperative check) can be bypassed if
# the interpreting L0 skips it "for a good reason" (the RC-11 shape). This hook is the harness-enforced
# backstop: it denies a subagent's own Write/Edit/MultiEdit to TASK_STATUS.concerns.json if the proposed
# content would narrow a central/GAMBLE K with no research-rescue verdict on disk for it this round — it never
# duplicates the detection logic, it reuses bin/central_ambition_guard.sh's --live-file mode. The real logic +
# WHY live in the sibling Python file; this wrapper just forwards the hook's stdin payload to it.
exec python3 "${BASH_SOURCE%/*}/central_narrow_guard.py"
