#!/usr/bin/env bash
# auto-research — LOCK GUARD (PreToolUse hook).
#
# WHY THIS EXISTS. The two ratchet baselines (HANDOFF.scale-contract.locked.json, HANDOFF.ambition.locked.json)
# are frozen at Phase 0(C) and owned exclusively by bin/lock_contracts.sh. The per-round verifier diffs the
# re-authored work order against them to catch a silent WEAKEN-TO-PASS, so a producing-worker that overwrites a
# baseline with Write/Edit would poison that comparison. This hook denies any Write/Edit/MultiEdit whose basename
# is one of those two files. The legitimate writer (bin/lock_contracts.sh, --ratchet included) writes via shell,
# which a Write-matcher hook does not intercept, so it passes through; AUDIT-ARTIFACTS.locked.json is deliberately
# NOT in the deny set (the producing-worker legitimately Write-appends it). The real logic + WHY live in the
# sibling Python file; this wrapper just forwards the hook's stdin payload to it.
exec python3 "${BASH_SOURCE%/*}/lock_guard.py"
