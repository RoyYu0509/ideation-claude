#!/usr/bin/env bash
# Compile ONE version of a (possibly multi-file \input) LaTeX manuscript into a plain PDF, read-only.
# This is the no-diff sibling of render_diff_pdf.sh: it git-archives a single ref's manuscript subtree
# into a temp dir, symlinks the repo figures + copies the .bib files, runs pdflatex/bibtex multiple
# passes, and writes the final PDF to --out. The working tree is NEVER touched (the version comes from
# `git archive`, the build happens in a temp dir). Used by /review's Comprehend phase to give a neutral
# comprehension agent the TYPESET paper (figures + rendered equations visible), instead of raw .tex.
#
# Deterministic given (repo, ref). Requires: pdflatex, bibtex (NO latexdiff). Exits non-zero with the
# log tail if the PDF fails to build, so the caller can fall back to reading the .tex.
#
# Usage:
#   render_pdf.sh --repo <gitroot> --master <repo-rel path to main.tex> \
#       [--ref <sha|ref, default HEAD>] --out <out.pdf> [--bib-dir <dir>] [--figures <dir>] [--keep-build]
set -euo pipefail

REPO="" MASTER="" REF="HEAD" OUT="" BIBDIR="" FIGURES="" KEEP_BUILD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --master) MASTER="$2"; shift 2;;
    --ref|--base) REF="$2"; shift 2;;      # accept --base too (mirrors render_diff_pdf.sh's vocabulary)
    --out) OUT="$2"; shift 2;;
    --bib-dir) BIBDIR="$2"; shift 2;;
    --figures) FIGURES="$2"; shift 2;;
    --keep-build) KEEP_BUILD=1; shift;;
    *) echo "render_pdf: unknown arg: $1" >&2; exit 2;;
  esac
done
[ -n "$REPO" ] && [ -n "$MASTER" ] && [ -n "$OUT" ] || { echo "render_pdf: --repo, --master, --out are required" >&2; exit 2; }
REPO="$(cd "$REPO" && pwd)"

for t in pdflatex bibtex; do
  command -v "$t" >/dev/null 2>&1 || { echo "render_pdf: missing '$t' (install texlive)" >&2; exit 3; }
done

PAPERDIR="$(dirname "$MASTER")"                 # e.g. "paper" (repo-relative); "." if master at root
PAPERABS="$REPO/$PAPERDIR"
[ -n "$BIBDIR" ] || BIBDIR="$PAPERABS"
[ -n "$FIGURES" ] || FIGURES="$REPO/figures"

SRC="$(mktemp -d)"; BUILD="$(mktemp -d)"
cleanup() { [ "$KEEP_BUILD" -eq 1 ] || rm -rf "$SRC" "$BUILD"; }
trap cleanup EXIT

# 1. Materialise the manuscript subtree from git (read-only; never the work tree).
git -C "$REPO" archive "$REF" -- "$PAPERDIR" | tar -x -C "$SRC"
SRC_MAIN="$SRC/$MASTER"
[ -f "$SRC_MAIN" ] || { echo "render_pdf: $MASTER not found at $REF" >&2; exit 4; }

# 2. Compile in the build dir: copy the manuscript subtree in, add a figures/ symlink + the .bib copies
#    so \graphicspath{{../figures/}{figures/}} and \bibliography{...} resolve without touching the paper.
cp -R "$SRC/$PAPERDIR/." "$BUILD/" 2>/dev/null || cp -R "$SRC/." "$BUILD/"
ln -s "$FIGURES" "$BUILD/figures" 2>/dev/null || true
cp "$BIBDIR"/*.bib "$BUILD/" 2>/dev/null || true
cd "$BUILD"
JOB="$(basename "$MASTER" .tex)"
pdflatex -interaction=nonstopmode -halt-on-error "$JOB.tex" >/dev/null 2>&1 \
  || pdflatex -interaction=nonstopmode "$JOB.tex" >/dev/null 2>&1 || true
bibtex "$JOB" >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode "$JOB.tex" >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode "$JOB.tex" >/dev/null 2>&1 || true

# 3. Success = a non-empty PDF was written. Report the page count if pdflatex logged it.
if [ ! -s "$BUILD/$JOB.pdf" ]; then
  echo "render_pdf: compile produced no PDF. Log tail:" >&2
  tail -40 "$BUILD/$JOB.log" 2>/dev/null >&2 || true
  exit 6
fi
mkdir -p "$(dirname "$OUT")"
cp "$BUILD/$JOB.pdf" "$OUT"
PAGES="$(grep -oE 'Output written on .*\(([0-9]+) page' "$BUILD/$JOB.log" 2>/dev/null | grep -oE '[0-9]+ page' | head -1 || true)"
echo "render_pdf: wrote $OUT (${PAGES:-? pages}) — ref ${REF:0:8} of $MASTER"
