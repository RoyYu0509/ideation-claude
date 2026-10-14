#!/usr/bin/env bash
# pdf_github_urls.sh <arxiv_id>
# Prints github.com URLs found in the PDF BODY, one per line (sorted, deduped).
#
# References-aware: URLs inside the References / Bibliography section are CITATIONS
# (e.g. a cited "JAX: ... https://github.com/jax-ml/jax" entry), not the paper's own
# code repo, so they are dropped. A URL after the references heading is kept ONLY if
# its surrounding text carries a strong "this is our code" cue (handles journal-style
# "Code availability" statements that follow the bibliography).
#
# Exit 0 always; exit 1 only if the PDF cannot be fetched.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

arxiv_id="${1:?usage: $0 <arxiv_id>}"
# Runtime data root (owner principle 2026-07-05): PDFs cache under the session's
# runtime folder, never the plugin dir. Precedence mirrors bin/run_py.sh:
# AR_DATA_ROOT → CLAUDE_PROJECT_DIR → cwd.
DATA_ROOT="${AR_DATA_ROOT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
pdf_path="$DATA_ROOT/data/cache/pdfs/${arxiv_id}.pdf"

if [[ ! -f "$pdf_path" ]]; then
  bash "$SCRIPT_DIR/fetch_arxiv_pdf.sh" "$arxiv_id" >/dev/null 2>&1 || true
fi
[[ -f "$pdf_path" ]] || { echo "ERROR: PDF not found for $arxiv_id" >&2; exit 1; }

# 1) Extract raw text via whatever tool is available (layout-preserving order matters
#    so the References heading lands before its entries).
txt="$(mktemp "${TMPDIR:-/tmp}/_pdftxt_XXXXXX.txt")"
trap 'rm -f "$txt"' EXIT
if command -v pdftotext &>/dev/null; then
  pdftotext "$pdf_path" "$txt" 2>/dev/null || true
fi
if [[ ! -s "$txt" ]] && command -v python3 &>/dev/null; then
  python3 - "$pdf_path" >"$txt" 2>/dev/null <<'PYEOF' || true
import sys
path = sys.argv[1]; text = ""
try:
    import fitz
    text = "".join(p.get_text() for p in fitz.open(path))
except Exception:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text = "".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        pass
sys.stdout.write(text)
PYEOF
fi
if [[ ! -s "$txt" ]]; then
  strings "$pdf_path" > "$txt" 2>/dev/null || true
fi

# 2) References-aware github URL extraction over the extracted text.
if command -v python3 &>/dev/null; then
  python3 - "$txt" <<'PYEOF'
import sys, re
text = open(sys.argv[1], encoding="utf-8", errors="ignore").read()

# Last standalone "References"/"Bibliography" heading (optionally section-numbered)
# marks where the bibliography starts.
ref_pos = None
for m in re.finditer(r'(?im)^\s*(?:\d+\.?\s+|[ivxlc]+\.?\s+)?(references|bibliography|references\s+and\s+notes)\s*$', text):
    ref_pos = m.start()

# A URL after the references heading is rescued only if a "this is our code" cue sits
# IMMEDIATELY before it (journal "Code availability" sections trail the bibliography).
# Every pattern is tail-anchored (must abut the URL) so a cue belonging to an earlier
# URL cannot leak across into a later bibliography entry.
POSITIVE = re.compile(
    r'(available|released|provided|found|hosted|accessible|reproduced?)\s+at\s*[:\-]?\s*$'
    r'|(our|the)\s+(code|implementation|source\s*code|repository|repo)\b[^.\n]{0,30}$'
    r'|code\s+availability\s*[:\-]?\s*$'
    r'|(code|implementation|repository|repo|source\s*code)\s*[:\-]\s*$'
    r'|github(\.com)?\s*[:\-]?\s*$',
    re.I,
)

urls = set()
for m in re.finditer(r'https://github\.com/[a-zA-Z0-9._/-]+', text):
    url = m.group(0).rstrip('.,;:)}]')
    if ref_pos is not None and m.start() > ref_pos:
        before = text[max(0, m.start() - 100):m.start()]
        if not POSITIVE.search(before):
            continue  # bibliography citation, not the paper's own repo
    urls.add(url)

for u in sorted(urls):
    print(u)
PYEOF
else
  # No python3 — cannot do section analysis; emit everything (legacy behavior).
  grep -oiE 'https://github\.com/[a-zA-Z0-9._/-]+' "$txt" | sed 's/[.,;:)}\]]*$//' | sort -u || true
fi
