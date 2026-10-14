#!/usr/bin/env bash
# Resolve the TYPESET paper for the Comprehend phase of /review and /rewrite — the [[SEAM:comprehension-source]]
# ladder, lifted verbatim out of the two specs (resolveComprehensionPdf) so the one source of truth lives here.
#
# Ladder (FLOOR: only ever return an EXISTING, non-empty PDF; a compile failure degrades to empty — NEVER abort):
#   (1) an existing compiled PDF next to the master (the author's Overleaf/local build); else
#   (2) the single *.pdf in the paper dir (ambiguous => skip); else
#   (3) compile the base commit with render_pdf.sh, IF a TeX toolchain exists and the paper is LaTeX; else
#   (4) print nothing — the caller reads the .tex source instead.
#
# Usage:
#   resolve_comprehension_pdf.sh --master <abs master.tex> --paper-dir <dir> --project-dir <dir> \
#       --git-root <dir> --ref <sha> --format <latex|markdown> --plugin-root <dir>
# Output: the resolved PDF path on stdout (EMPTY if none). Progress/reason on stderr. Always exits 0.
set -u

MASTER="" PAPERDIR="" PROJDIR="" GITROOT="" REF="" FORMAT="" PLUGINROOT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --master) MASTER="$2"; shift 2;;
    --paper-dir) PAPERDIR="$2"; shift 2;;
    --project-dir) PROJDIR="$2"; shift 2;;
    --git-root) GITROOT="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    --format) FORMAT="$2"; shift 2;;
    --plugin-root) PLUGINROOT="$2"; shift 2;;
    *) echo "resolve_comprehension_pdf: unknown arg: $1" >&2; exit 0;;
  esac
done

# (1) existing PDF: the master's sibling .pdf
MASTER_PDF="${MASTER%.tex}.pdf"
if [ -s "$MASTER_PDF" ]; then
  echo "comprehension-source: using existing PDF $MASTER_PDF" >&2
  printf '%s' "$MASTER_PDF"; exit 0
fi

# (2) else the single PDF in the paper dir (ambiguous => skip)
PDFS=$(ls -1 "$PAPERDIR"/*.pdf 2>/dev/null || true)
COUNT=$(printf '%s\n' "$PDFS" | grep -c . || true)
if [ "$COUNT" = "1" ] && [ -s "$PDFS" ]; then
  echo "comprehension-source: using existing PDF $PDFS" >&2
  printf '%s' "$PDFS"; exit 0
fi

# (3) compile the base commit (only if pdflatex+bibtex are present and the paper is LaTeX)
if command -v pdflatex >/dev/null 2>&1 && command -v bibtex >/dev/null 2>&1; then
  HAVE_COMPILE=1
else
  HAVE_COMPILE=0
fi
if [ "$HAVE_COMPILE" = "1" ] && [ "$FORMAT" = "latex" ]; then
  OUT="$PROJDIR/.polish/base.pdf"
  REL=$(python3 -c "import os,sys;print(os.path.relpath(sys.argv[1],sys.argv[2]))" "$MASTER" "$GITROOT")
  if bash "$PLUGINROOT/scripts/render_pdf.sh" --repo "$GITROOT" --master "$REL" --ref "$REF" --out "$OUT" >&2 2>&1; then
    if [ -s "$OUT" ]; then
      echo "comprehension-source: compiled base PDF $OUT" >&2
      printf '%s' "$OUT"; exit 0
    fi
  fi
  echo "comprehension-source: compile failed; reading .tex instead" >&2
  exit 0
fi

# (4) fall back to the .tex
if [ "$FORMAT" != "latex" ]; then REASON="not LaTeX"; elif [ "$HAVE_COMPILE" = "1" ]; then REASON="compile failed"; else REASON="no pdflatex/bibtex"; fi
echo "comprehension-source: no PDF ($REASON); the agent will read the .tex" >&2
exit 0
