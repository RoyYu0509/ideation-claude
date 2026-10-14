#!/usr/bin/env bash
# auto-research — USAGE ROLLUP (Stop hook). Persists bin/run_report.py's token/cache-usage rollup to
# runs/<slug>/usage-log.json on every L0 turn end. The real logic + the WHY live in the sibling Python file;
# this wrapper just forwards the hook's stdin payload to it.
exec python3 "${BASH_SOURCE%/*}/usage_rollup.py"
