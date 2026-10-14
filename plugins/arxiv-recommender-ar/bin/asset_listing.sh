#!/usr/bin/env bash
# asset_listing.sh — fetch a REAL file listing for a depended asset and judge
# substantiveness mechanically (allowlist: github/arxiv/hf/zenodo/osf/gitlab).
#
#   bash bin/asset_listing.sh <url> --out <listing.json> [--needed-paths "a/*.py,data/*.h5"]
#
# Exit 0 = live_verified; 1 = stub_or_empty/missing; 2 = usage/network error.
# Thin wrapper over scripts/lib/asset_listing.py (the library verify_bundle.py
# re-uses for its V0 asset re-fetch).
set -euo pipefail
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
exec bash "${PLUGIN_ROOT}/bin/run_py.sh" "${PLUGIN_ROOT}/scripts/lib/asset_listing.py" "$@"
