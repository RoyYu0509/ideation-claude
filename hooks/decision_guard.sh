#!/usr/bin/env bash
# auto-research — DECISION GUARD (PreToolUse hook).
#
# WHY THIS EXISTS. Human gates are L0-only (fact #3), but the decision ARCHIVE was body-less spec prose the
# L0 reproduced by hand. In the 2026-06-30 real run an experiment L1 wrote a DECISIONS-RESOLVED-7.md itself
# while still running — self-resolving a K-criterion scope change with no L0 validation, state transition, or
# logging. This hook moves the invariant OUTSIDE the reproduction: it denies any Write/Edit/MultiEdit that
# mints a DECISIONS-RESOLVED-*.md (those are created only by bin/archive_decision.sh via shell `mv`, which a
# Write-matcher hook does not intercept). The real logic + WHY live in the sibling Python file; this wrapper
# just forwards the hook's stdin payload to it.
exec python3 "${BASH_SOURCE%/*}/decision_guard.py"
