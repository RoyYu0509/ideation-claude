#!/usr/bin/env bash
# Run a python script under the plugin's venv. Bootstraps venv on first call.
# Usage: bin/run_py.sh scripts/fetch_weekly.py [args...]
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV="${PLUGIN_ROOT}/.venv"

# DATA-ROOT GUARANTEE (chokepoint). Every data-writing script reads its data root from AR_DATA_ROOT
# (scripts/lib/config.py: AR_DATA_ROOT → CLAUDE_PROJECT_DIR → plugin_root). The auto-research orchestrator
# sets AR_DATA_ROOT explicitly on the node/execSync path; this default is the SAFETY NET for the
# agent-reproduce path (its fallback command strings call run_py.sh WITHOUT the inline prefix) and any
# future caller that forgets it. Default to CLAUDE_PROJECT_DIR, else the CALLER's cwd ($PWD — run_py.sh
# never cd's, so $PWD is the launch dir). This guarantees data lands in the run's own folder, NEVER
# silently in the shared plugin dir. Run from the monorepo ⇒ $PWD is the monorepo ⇒ legacy behavior.
export AR_DATA_ROOT="${AR_DATA_ROOT:-${CLAUDE_PROJECT_DIR:-$PWD}}"

if [[ ! -d "${VENV}" ]]; then
  bash "${PLUGIN_ROOT}/bin/setup_venv.sh"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
exec python "$@"
