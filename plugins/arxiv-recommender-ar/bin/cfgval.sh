#!/usr/bin/env bash
# Print one or more config values from config/config.yaml by dotted key path.
# Purpose: feed Claude Code's `!`<command>`` dynamic-context injection so SKILL.md
# files show LIVE config values at skill-activation time instead of a stale lookup
# note. Source markdown keeps showing the directive; the model/reader sees the value.
#
# Usage:  bin/cfgval.sh scout.top_n_papers              -> 3   (no trailing newline)
#         bin/cfgval.sh scout.top_n_papers scout.extensibility_gate  -> one value per line
#
# Uses SYSTEM python3 + PyYAML (no venv bootstrap) so per-activation cost stays low,
# matching the .claude/commands/arxiv-eval.md pattern.
#
# FAIL-LOUD (config SSOT rule): a missing key prints "<MISSING KEY: a.b>" and exits 1.
# It never silently prints an empty string — drift or a typo is immediately visible.
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONFIG_PATH="${PLUGIN_ROOT}/config/config.yaml"

CONFIG_PATH="${CONFIG_PATH}" PLUGIN_ROOT="${PLUGIN_ROOT}" python3 - "$@" <<'PY'
import os, sys, yaml

config_path = os.environ["CONFIG_PATH"]
keys = sys.argv[1:]
if not keys:
    sys.stderr.write("cfgval: need at least one dotted key path\n")
    sys.exit(2)

with open(config_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)

out, missing = [], False
for path in keys:
    node = cfg
    ok = True
    for seg in path.split("."):
        if isinstance(node, dict) and seg in node:
            node = node[seg]
        else:
            ok = False
            break
    DERIVED = {  # keys not stored in config.yaml — resolved through lib/config.py's
                 # Config properties, each formula's single home (2026-07-05 / 2026-07-11)
        "scout.rerank_return_n": "rerank_return_n",
        "scout.ideate_brainstorm_count": "ideate_brainstorm_count",
    }
    if not ok and path in DERIVED:
        try:
            sys.path.insert(0, os.path.join(os.environ["PLUGIN_ROOT"], "scripts"))
            from lib.config import Config
            node = getattr(Config(raw=cfg), DERIVED[path])
            ok = True
        except Exception:
            ok = False
    if ok:
        out.append(fmt(node))
    else:
        out.append(f"<MISSING KEY: {path}>")
        missing = True

# Single value: no trailing newline (keeps inline `... ≥ !`...`` on one line).
sys.stdout.write("\n".join(out))
sys.exit(1 if missing else 0)
PY
