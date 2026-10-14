#!/usr/bin/env bash
# Render a paper-polishing run into a PDF inline-diff (the standard LaTeX review form): latexdiff
# marks base-vs-head into one .tex (new text = blue underline, deleted = red strike-through), then
# pdflatex+bibtex compile it. Multi-file (\input) manuscripts are flattened. The working tree is
# never touched — both versions come from `git archive` into temp dirs; we compile in a temp build
# dir (with a symlink to the repo figures and a copy of the .bib files) and only the final PDF
# (and, for reuse, the marked-up .tex) is written next to the manuscript.
#
# Deterministic given (repo, base, head). Requires: latexdiff, pdflatex, bibtex (see /polish-report
# for the apt install line). Exits non-zero with the log tail if the PDF fails to build.
#
# Usage:
#   render_diff_pdf.sh --repo <gitroot> --master <repo-rel path to main.tex> \
#       [--base <sha>] [--head <ref>] --out <out.pdf> [--bib-dir <dir>] [--figures <dir>] [--keep-build]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO="" MASTER="" BASE="" HEAD="HEAD" OUT="" BIBDIR="" FIGURES="" KEEP_BUILD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2;;
    --master) MASTER="$2"; shift 2;;
    --base) BASE="$2"; shift 2;;
    --head) HEAD="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    --bib-dir) BIBDIR="$2"; shift 2;;
    --figures) FIGURES="$2"; shift 2;;
    --keep-build) KEEP_BUILD=1; shift;;
    *) echo "render_diff_pdf: unknown arg: $1" >&2; exit 2;;
  esac
done
[ -n "$REPO" ] && [ -n "$MASTER" ] && [ -n "$OUT" ] || { echo "render_diff_pdf: --repo, --master, --out are required" >&2; exit 2; }
REPO="$(cd "$REPO" && pwd)"

for t in latexdiff pdflatex bibtex; do
  command -v "$t" >/dev/null 2>&1 || { echo "render_diff_pdf: missing '$t' (install texlive + latexdiff)" >&2; exit 3; }
done

# Resolve the base commit the same way the HTML renderer does, unless given explicitly.
if [ -z "$BASE" ]; then
  BASE="$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); import render_report as r; print(r.resolve_base('$REPO', '$HEAD', None))")"
fi

PAPERDIR="$(dirname "$MASTER")"                 # e.g. "paper" (repo-relative); "." if master at root
PAPERABS="$REPO/$PAPERDIR"
[ -n "$BIBDIR" ] || BIBDIR="$PAPERABS"
[ -n "$FIGURES" ] || FIGURES="$REPO/figures"

OLD="$(mktemp -d)"; NEW="$(mktemp -d)"; BUILD="$(mktemp -d)"
cleanup() { [ "$KEEP_BUILD" -eq 1 ] || rm -rf "$OLD" "$NEW" "$BUILD"; }
trap cleanup EXIT

# 1. Materialise both versions of the manuscript subtree from git (read-only; never the work tree).
git -C "$REPO" archive "$BASE" -- "$PAPERDIR" | tar -x -C "$OLD"
git -C "$REPO" archive "$HEAD" -- "$PAPERDIR" | tar -x -C "$NEW"
OLD_MAIN="$OLD/$MASTER"; NEW_MAIN="$NEW/$MASTER"
[ -f "$OLD_MAIN" ] || { echo "render_diff_pdf: $MASTER not found at $BASE" >&2; exit 4; }
[ -f "$NEW_MAIN" ] || { echo "render_diff_pdf: $MASTER not found at $HEAD" >&2; exit 4; }

# 2. latexdiff → one marked-up, flattened .tex. VERBATIMENV keeps code listings unmarked; graphics
#    markup off so unchanged figures are not framed. EXTRA_LATEXDIFF lets the caller add e.g.
#    --math-markup=whole if a changed equation trips the default markup.
echo "render_diff_pdf: latexdiff ${BASE:0:8}..$HEAD on $MASTER (flatten)" >&2
latexdiff --flatten --graphics-markup=none --config "VERBATIMENV=lstlisting" \
  ${EXTRA_LATEXDIFF:-} "$OLD_MAIN" "$NEW_MAIN" > "$BUILD/polish-diff.tex" 2> "$BUILD/latexdiff.err" || {
    echo "render_diff_pdf: latexdiff failed:" >&2; tail -20 "$BUILD/latexdiff.err" >&2; exit 5; }

# Markup style: added text = plain blue (strip latexdiff's \uwave wavy underline so it reads like the
# normal paper, just blue); deletions stay red strike-through. Targets only the %DIF PREAMBLE defs.
sed -i.bak '/%DIF PREAMBLE/{/DIFadd/s/\\uwave//g;}' "$BUILD/polish-diff.tex" && rm -f "$BUILD/polish-diff.tex.bak"

# REVTeX preprint encourages a page break (with fil-stretch glue) right before the abstract; a diff
# roughly doubles the abstract's height (old struck-through + new), so that break fires and leaves the
# title page mostly blank with the abstract pushed to the next page. Redefine the abstract producer to
# drop that fil-glue break so the abstract stays with the title and flows across pages like main.pdf.
# Injected only for revtex classes and guarded by \@ifundefined (no-op elsewhere / on future renames).
if grep -qi 'revtex' "$BUILD/polish-diff.tex"; then
  cat > "$BUILD/_absfix.tex" <<'ABSFIX'
\makeatletter
\@ifundefined{frontmatter@abstract@produce}{}{%
 \def\frontmatter@abstract@produce{%
  \par\addvspace{\frontmatter@preabstractspace}%
  \begingroup \dimen@\baselineskip \setbox\z@\vtop{\unvcopy\absbox}%
   \advance\dimen@-\ht\z@\advance\dimen@-\prevdepth \@ifdim{\dimen@>\z@}{\vskip\dimen@}{}%
  \endgroup
  \begingroup \prep@absbox \unvbox\absbox \post@absbox \endgroup
  \@ifx{\@empty\mini@notes}{}{\mini@notes\par}%
  \addvspace\frontmatter@postabstractspace}%
}%
\makeatother
ABSFIX
  awk 'f==0 && /\\begin\{document\}/ {while((getline l < absfix)>0) print l; f=1} {print}' \
    absfix="$BUILD/_absfix.tex" "$BUILD/polish-diff.tex" > "$BUILD/_patched.tex" \
    && mv "$BUILD/_patched.tex" "$BUILD/polish-diff.tex"
  rm -f "$BUILD/_absfix.tex"
fi

# 3. Compile in the build dir. Mirror the real paper directory's asset layout into the build dir so
#    that whatever RELATIVE paths the manuscript uses resolve exactly as they do in the paper dir —
#    figure folders under ANY name (figs/, figures/, images/, ...), local .cls/.sty/.bst, etc. — not
#    just the repo-root figures/ convention. We link the real on-disk entries (the working tree, so
#    even untracked figures render); the master .tex is replaced by the flattened diff, our own
#    output is skipped, and aux/build artifacts and *.bib are skipped (the latter is copied below).
for entry in "$PAPERABS"/*; do
  name="$(basename "$entry")"
  case "$name" in
    "$(basename "$MASTER")"|polish-diff.*|*.bib|*.aux|*.log|*.out|*.bbl|*.blg|*.fls|*.fdb_latexmk|*.synctex.gz|*.spl) continue;;
  esac
  [ -e "$BUILD/$name" ] || ln -s "$entry" "$BUILD/$name" 2>/dev/null || true
done
# Fallback for the repo-root figures convention (\graphicspath{{../figures/}{figures/}}): a figures/
# symlink. The .bib copies satisfy \bibliography{...} without touching the real paper dir.
ln -s "$FIGURES" "$BUILD/$(basename "$FIGURES")" 2>/dev/null || true
ln -s "$FIGURES" "$BUILD/figures" 2>/dev/null || true
cp "$BIBDIR"/*.bib "$BUILD/" 2>/dev/null || true
cd "$BUILD"
JOB=polish-diff
pdflatex -interaction=nonstopmode -halt-on-error "$JOB.tex" >/dev/null 2>&1 \
  || pdflatex -interaction=nonstopmode "$JOB.tex" >/dev/null 2>&1 || true
bibtex "$JOB" >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode "$JOB.tex" >/dev/null 2>&1 || true
pdflatex -interaction=nonstopmode "$JOB.tex" >/dev/null 2>&1 || true

# 4. Success = a non-empty PDF was written. Report the page count if pdflatex logged it.
if [ ! -s "$BUILD/$JOB.pdf" ]; then
  echo "render_diff_pdf: compile produced no PDF. Log tail:" >&2
  tail -40 "$BUILD/$JOB.log" 2>/dev/null >&2 || true
  exit 6
fi
mkdir -p "$(dirname "$OUT")"
cp "$BUILD/$JOB.pdf" "$OUT"
cp "$BUILD/$JOB.tex" "${OUT%.pdf}.tex" 2>/dev/null || true   # keep the marked-up source for reuse
PAGES="$(grep -oE 'Output written on .*\(([0-9]+) page' "$BUILD/$JOB.log" 2>/dev/null | grep -oE '[0-9]+ page' | head -1 || true)"
ADDS="$(grep -c 'DIFadd' "$BUILD/$JOB.tex" 2>/dev/null || echo 0)"
DELS="$(grep -c 'DIFdel' "$BUILD/$JOB.tex" 2>/dev/null || echo 0)"
echo "render_diff_pdf: wrote $OUT (${PAGES:-? pages}; ~$ADDS add / ~$DELS del markup spans) — base ${BASE:0:8} → $HEAD"
