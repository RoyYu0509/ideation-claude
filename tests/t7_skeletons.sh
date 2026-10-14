#!/usr/bin/env bash
# T7 — venue skeleton resolution + SMOKE COMPILE (HANDOFF Stage 3). A broken skeleton must fail HERE,
# not mid-run in some paper's INTEGRATED milestone. For every assets/paper-skeleton*/ dir: copy to a
# tmp workspace (the same cp -R the setup_workspace stage / bin/setup_workspace.sh does), assert master.tex + sections are
# present, and compile with pdflatex (2 passes, halt-on-error). Also asserts the resolveSkeleton key
# mapping (venue rel -> skeleton dir, generic fallback). Skips compiles (with a loud note) only if
# pdflatex is absent. Run: bash tests/t7_skeletons.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
chk() { if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── resolveSkeleton key mapping (mirrors spec/research.js resolveSkeleton) ──────────────────────
resolve() { # $1 = venue rel
  local key dir
  key="$(printf '%s' "${1%%/*}" | tr '[:upper:]' '[:lower:]')"
  dir="$ROOT/assets/paper-skeleton-$key"
  if [ -f "$dir/master.tex" ]; then echo "$dir"; else echo "$ROOT/assets/paper-skeleton"; fi
}
chk "venue WITH skeleton resolves to its dir" \
  "[ \"\$(resolve 'Journal-of-Computational-Physics/scientific-machine-learning')\" = \"$ROOT/assets/paper-skeleton-journal-of-computational-physics\" ]"
chk "venue WITHOUT skeleton falls back to generic" \
  "[ \"\$(resolve 'Some-Unstocked-Venue/anything')\" = \"$ROOT/assets/paper-skeleton\" ]"

# ── every stocked skeleton (incl. the generic fallback): existence checks ALWAYS run; the compile
#    additionally runs when pdflatex is available (the HANDOFF's "or at minimum existence-check"). ──
HAVE_TEX=1; command -v pdflatex >/dev/null 2>&1 || HAVE_TEX=0
[ "$HAVE_TEX" = 1 ] || echo "SKIP  pdflatex not found — compiles skipped; existence checks still enforced (install TeX Live for the full gate)"
for d in "$ROOT"/assets/paper-skeleton "$ROOT"/assets/paper-skeleton-*; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  w="$TMP/$name"; mkdir -p "$w"; cp -R "$d/." "$w/"        # same copy the spec performs
  ok_files="[ -f '$w/master.tex' ] && [ -f '$w/references.bib' ] && [ -d '$w/sections' ]"
  chk "$name: master.tex + references.bib + sections/ present" "$ok_files"
  if [ "$HAVE_TEX" = 1 ]; then
    ( cd "$w" && pdflatex -interaction=nonstopmode -halt-on-error master.tex >compile.log 2>&1 \
              && pdflatex -interaction=nonstopmode -halt-on-error master.tex >>compile.log 2>&1 )
    if [ -f "$w/master.pdf" ]; then
      chk "$name: compiles (master.pdf produced)" "true"
    else
      chk "$name: compiles (master.pdf produced)" "false"
      tail -20 "$w/compile.log" 2>/dev/null | sed 's/^/      | /'
    fi
  fi
done

echo "----"; echo "t7_skeletons: $pass passed, $fail failed"; [ "$fail" = 0 ]
