#!/usr/bin/env bash
# paper-polish — mechanical fidelity guard (PreToolUse hook).
#
# Runs on every Edit/Write/MultiEdit. It is the deterministic, zero-token layer
# of the freeze boundary: it blocks edits that mutate a frozen mechanical token
# (a number/unit, a \cite/\ref/\label key, a math span) on the manuscript, and
# blocks any edit to a pure-data file (.bib / data / tables / figures). The
# semantic half of fidelity (claim strength, dropped hedges, citation
# re-attachment, scope) is judged separately by the check-fidelity reviewer.
#
# It reads the run manifest written by the workflow's Phase 0 at
# $CLAUDE_PROJECT_DIR/.polish/fidelity-manifest.json. If that file is absent
# (no active polish run, or before Phase 0), the hook is a silent no-op.
#
# The real logic is in the sibling Python file (robust JSON + token diffing);
# this wrapper just forwards the hook's stdin payload to it.

exec python3 "${BASH_SOURCE%/*}/check_fidelity.py"
