#!/usr/bin/env bash
# Idempotent bootstrap for the arxiv-recommender Python environment.
# Safe to rerun: only creates venv if missing, only reinstalls when requirements
# change.
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV="${PLUGIN_ROOT}/.venv"
REQ="${PLUGIN_ROOT}/scripts/requirements.txt"
STAMP="${VENV}/.requirements.sha256"

PY_BIN="${PYTHON:-python3}"

if [[ ! -x "$(command -v "${PY_BIN}")" ]]; then
  echo "[setup_venv] ${PY_BIN} not found on PATH. Set PYTHON=... or install python3." >&2
  exit 1
fi

if [[ ! -d "${VENV}" ]]; then
  echo "[setup_venv] creating venv at ${VENV}"
  "${PY_BIN}" -m venv "${VENV}"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

python -m pip install --quiet --upgrade pip wheel

CURRENT_HASH=$(shasum -a 256 "${REQ}" | awk '{print $1}')
PRIOR_HASH=""
if [[ -f "${STAMP}" ]]; then
  PRIOR_HASH=$(cat "${STAMP}")
fi

if [[ "${CURRENT_HASH}" != "${PRIOR_HASH}" ]]; then
  echo "[setup_venv] installing requirements (first run or requirements.txt changed)"
  pip install --quiet -r "${REQ}"
  echo "${CURRENT_HASH}" > "${STAMP}"
else
  echo "[setup_venv] requirements unchanged; skipping pip install"
fi

echo "[setup_venv] ready. venv at ${VENV}"
