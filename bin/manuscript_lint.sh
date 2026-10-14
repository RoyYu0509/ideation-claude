#!/usr/bin/env bash
# manuscript_lint.sh — deterministic MACHINE-TELL scanner (writing-redesign 2026-07-07).
#
# WHAT THIS IS. The freeze stage's mechanical gate. It scans a manuscript for the class of artifact that
# desk-rejects a paper on sight — not a matter of judgment, purely mechanical: leaked skeleton/instruction
# comments, bibliography TODO notes, placeholder identity, undefined references, and (from the build log)
# overfull black boxes. The last shipped paper carried "verify … before camera-ready" in its printed
# bibliography, "% Abstract: one paragraph…" in its source, and "University of Somewhere" as its author — every
# one of these is a deterministic grep. The freeze stage runs this and clears every hit before ship.
#
# Usage:  bin/manuscript_lint.sh <paper-dir>          (e.g. runs/<slug>/paper)
# Exit:   0 = clean · 2 = machine-tell(s) found · 1 = usage/no paper dir
set -euo pipefail

PAPER="${1:-}"
[ -z "$PAPER" ] && { echo "usage: manuscript_lint.sh <paper-dir>"; exit 1; }
[ -d "$PAPER" ] || { echo "manuscript_lint: no such dir: $PAPER"; exit 1; }

CLAUDE_LINT_PAPER="$PAPER" python3 - "$PAPER" <<'PY'
import os, re, sys, glob

paper = sys.argv[1]
hits = []

def add(f, n, kind, text):
    hits.append(f"{os.path.relpath(f, paper)}:{n}  [{kind}]  {text.strip()[:100]}")

# --- .tex / .bib source patterns (case-insensitive) ------------------------------------------------------
SRC_PATTERNS = [
    (r"%\s*(abstract:|auto-research|compile:|front matter|placeholder|skeleton|\[fill|todo|fixme)", "skeleton/instruction-comment"),
    (r"before camera-ready|not pinned|verify .*numbering|\bTODO\b|\bFIXME\b|\bXXX\b", "leaked-todo-note"),
    (r"University of Somewhere|\bA\. Author\b|\bB\. Coauthor\b|\bC\. Thirdauthor\b|Alice Author|somewhere\.edu|aauthor@|\[AGENCY\]|\[NUMBER\]|\[PLACEHOLDER", "placeholder-identity"),
    (r"\\includegraphics(\[[^\]]*\])?\{[^}]*(PLACEHOLDER|TODO|example-image)", "placeholder-figure"),
]
# scan the actual manuscript source only — exclude latexdiff byproducts (diff-ladder/, *-diff.tex) and the
# vendored class/style files, which are provenance artifacts / upstream, not the paper we are shipping.
def is_manuscript(p):
    rel = os.path.relpath(p, paper)
    if rel.startswith("diff-ladder" + os.sep) or "diff-ladder/" in rel.replace("\\", "/"):
        return False
    b = os.path.basename(p)
    if b.endswith("-diff.tex") or b.endswith(".diff.tex") or b in ("rewrite-diff.tex",):
        return False
    if b.endswith(".cls") or b.endswith(".sty") or b.endswith(".bst"):
        return False
    return True

src_files = [f for f in (sorted(glob.glob(os.path.join(paper, "**", "*.tex"), recursive=True))
                         + sorted(glob.glob(os.path.join(paper, "**", "*.bib"), recursive=True)))
             if is_manuscript(f)]
for f in src_files:
    try:
        lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
    except Exception:
        continue
    for i, line in enumerate(lines, 1):
        low = line.lower()
        for pat, kind in SRC_PATTERNS:
            if re.search(pat, low):
                add(f, i, kind, line)
                break

# --- build-log patterns (only if a .log is present — undefined refs + overfull boxes) --------------------
for logf in glob.glob(os.path.join(paper, "**", "*.log"), recursive=True):
    try:
        txt = open(logf, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    for i, line in enumerate(txt.splitlines(), 1):
        if "Overfull \\hbox" in line:
            add(logf, i, "overfull-hbox", line)
        if "undefined" in line.lower() and ("reference" in line.lower() or "citation" in line.lower()):
            add(logf, i, "undefined-ref", line)
    # LaTeX prints '??' into the PDF for an unresolved \ref — the .aux/.log carry the warning above; a raw
    # '??' in a .tex source is also suspicious.
# raw ?? in source
for f in src_files:
    if not f.endswith(".tex"):
        continue
    try:
        for i, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
            if "??" in line and "\\" not in line.split("??")[0][-2:]:
                add(f, i, "raw-??", line)
    except Exception:
        pass

if hits:
    print(f"MANUSCRIPT_LINT FAIL — {len(hits)} machine-tell(s):")
    for h in hits:
        print("  " + h)
    print("\nThese desk-reject a paper. Remove/replace every one (real front matter or a single clean TODO the "
          "owner resolves), then re-run.")
    sys.exit(2)
print("MANUSCRIPT_LINT OK — no leaked comments, TODO notes, placeholders, or unresolved refs.")
PY
