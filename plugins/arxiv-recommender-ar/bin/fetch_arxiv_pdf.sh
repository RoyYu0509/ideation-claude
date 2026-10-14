#!/bin/bash
# bin/fetch_arxiv_pdf.sh — Fetch an arXiv PDF to the shared cache.
#
# Usage:
#   bash bin/fetch_arxiv_pdf.sh <arxiv-id>
#
# Behavior:
#   - Strips optional "arXiv:" / "arxiv:" prefix. Preserves v1/v2 suffix.
#   - Writes data/cache/pdfs/<arxiv-id>.pdf relative to ${CLAUDE_PLUGIN_ROOT}
#     (or the repo root, walking up from this script).
#   - Dedup: if the file already exists and is non-empty, prints its path
#     on STDOUT and exits 0 without refetching.
#   - On success prints the absolute PDF path on STDOUT.
#   - On failure exits non-zero with diagnostic on STDERR.
#
# Intended callers: the arxiv-generate skill's Tier-3 path (and the verify/recheck leaves) when an abstract +
# WebSearch are not enough to ground a mechanism-level idea. The agent then
# uses the Read tool with `pages` to read targeted sections (Read supports
# PDFs natively).
#
# Borrowed shape from auto-research/bin/paper_pdf.sh but simplified — no
# sidecar metadata, no jq dependency, no thread-scoped out-dir.

set -u

if [ $# -lt 1 ]; then
  cat >&2 <<'EOF'
Usage: bash bin/fetch_arxiv_pdf.sh <arxiv-id>

Writes data/cache/pdfs/<arxiv-id>.pdf and prints its absolute path.
EOF
  exit 2
fi

arxiv_id="$1"
arxiv_id="${arxiv_id#arXiv:}"
arxiv_id="${arxiv_id#arxiv:}"

case "$arxiv_id" in
  [0-9]*\.[0-9]*) ;;
  */[0-9]*) ;;
  *) echo "fetch_arxiv_pdf.sh: '$arxiv_id' does not look like a canonical arxiv id" >&2; exit 2 ;;
esac

if ! command -v curl >/dev/null 2>&1; then
  echo "fetch_arxiv_pdf.sh: curl not found in PATH" >&2
  exit 2
fi

# Resolve plugin root: prefer ${CLAUDE_PLUGIN_ROOT}; else walk up from this
# script's directory (bin/ → repo root).
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  plugin_root="$CLAUDE_PLUGIN_ROOT"
else
  script_dir="$(cd "$(dirname "$0")" && pwd)"
  plugin_root="$(dirname "$script_dir")"
fi

# Runtime data root (owner principle 2026-07-05): the PDF cache lives under the
# session's runtime folder, never the plugin dir (AR_DATA_ROOT → CLAUDE_PROJECT_DIR → cwd).
data_root="${AR_DATA_ROOT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
cache_dir="$data_root/data/cache/pdfs"
mkdir -p "$cache_dir" 2>/dev/null || { echo "fetch_arxiv_pdf.sh: cannot create $cache_dir" >&2; exit 2; }

pdf_path="$cache_dir/$arxiv_id.pdf"

if [ -s "$pdf_path" ]; then
  printf '%s\n' "$pdf_path"
  exit 0
fi

url="https://arxiv.org/pdf/$arxiv_id"
tmp_pdf=$(mktemp -t fetch_arxiv_pdf.XXXXXX) || { echo "fetch_arxiv_pdf.sh: mktemp failed" >&2; exit 3; }
trap 'rm -f "$tmp_pdf"' EXIT

curl_rc=0
curl \
  --fail \
  --location \
  --silent --show-error \
  --user-agent "arxiv-recommender-ideator/1.0" \
  --output "$tmp_pdf" \
  "$url" 2> >(tee /dev/stderr) || curl_rc=$?

if [ "$curl_rc" -ne 0 ]; then
  echo "fetch_arxiv_pdf.sh: curl failed (rc=$curl_rc) for $url" >&2
  exit 4
fi

if [ ! -s "$tmp_pdf" ]; then
  echo "fetch_arxiv_pdf.sh: fetched empty body from $url" >&2
  exit 5
fi

mv "$tmp_pdf" "$pdf_path" || { echo "fetch_arxiv_pdf.sh: rename failed for $pdf_path" >&2; exit 6; }
trap - EXIT
printf '%s\n' "$pdf_path"
exit 0
