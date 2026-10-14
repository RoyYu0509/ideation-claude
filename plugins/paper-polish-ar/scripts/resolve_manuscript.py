#!/usr/bin/env python3
r"""Resolve a (possibly multi-file) LaTeX/Markdown manuscript into the polish loop's file-unit model.

Input: the MASTER file — the root that ``\input{}``s the section files (e.g. ``main.tex``), or a
self-contained single-file paper. Output (JSON on stdout):

    {format, master, files:[{path, rel, section, rubric, cites, signal}],
     contextFilesList, presentSections}

- **Multi-file** (master has ``\input``/``\include``): one file-unit per included file, classified by
  filename basename (primary signal — the filenames are already canonical) then by the file's own
  ``\section``/``\begin{abstract}`` heading (cross-check). The polish loop edits each file in place.
  ``conclusion.tex`` maps to the ``discussion`` section/rubric. The master itself is NOT a loop unit
  (its figure captions + back-matter are read-only context) but is always kept in ``contextFilesList``.
- **Single-file** (no ``\input``): one unit per distinct section heading present in the master, all
  sharing the master's path — preserves the legacy single-file behaviour.

Non-recursive (v1): a nested ``\input`` inside an included file is not followed. Comment-stripped
(an unescaped ``%`` to end-of-line is dropped before matching), so commented-out inputs are ignored.
"""
import argparse
import glob
import json
import os
import re
import sys

# canonical-section key -> (regex tested against basename/heading, rubric skill name)
SECTION_SYNONYMS = [
    ("introduction", re.compile(r"introduction|\bintro\b", re.I), "introduction"),
    ("results",      re.compile(r"results|experiments?|evaluation", re.I), "results"),
    ("methods",      re.compile(r"methods?|methodology|approach|materials", re.I), "methods"),
    ("discussion",   re.compile(r"discussion|conclusion|concluding|outlook", re.I), "discussion"),
    ("si",           re.compile(r"supplementary|supporting|appendix|appendices", re.I), "si"),
    ("abstract",     re.compile(r"abstract", re.I), "abstract"),
]
INPUT_RE = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
HEADING_RE = re.compile(r"\\section\*?\s*\{([^}]*)\}|\\begin\{abstract\}", re.I)
CITE_RE = re.compile(r"\\cite[a-zA-Z]*\{")


def strip_comment(line):
    """Drop a trailing LaTeX comment: the first unescaped ``%`` to end of line."""
    i = 0
    while i < len(line):
        if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
            return line[:i]
        i += 1
    return line


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def detect_format(text):
    head = text[:4000]
    if re.search(r"\\documentclass|\\begin\{document\}|\\cite\{", head):
        return "latex"
    if re.match(r"^---\n|^#\s|\]\(http", head):
        return "markdown"
    return "markdown"


def classify(text):
    """A basename or heading string -> (canonical_section, rubric), or (None, None)."""
    s = (text or "").lower()
    for key, rx, rubric in SECTION_SYNONYMS:
        if rx.search(s):
            return key, rubric
    return None, None


def resolve_inputs(master):
    """(master_dir, [abspath]) for each \\input/\\include target, in source order, dedup'd,
    comment-stripped, .tex appended when no extension, existing files only."""
    md = os.path.dirname(os.path.abspath(master))
    out, seen = [], set()
    for line in read(master).splitlines():
        for m in INPUT_RE.finditer(strip_comment(line)):
            arg = m.group(1).strip()
            p = arg if os.path.splitext(arg)[1] else arg + ".tex"
            ap = os.path.normpath(os.path.join(md, p))
            if ap in seen:
                continue
            seen.add(ap)
            if os.path.isfile(ap):
                out.append(ap)
    return md, out


def first_heading(text):
    m = HEADING_RE.search(text)
    if not m:
        return ""
    return m.group(1) or "abstract"   # \begin{abstract} has no group(1)


def find_master_in_dir(d):
    r"""Pick the master .tex in directory ``d``: a file containing ``\documentclass``, preferring more
    ``\input`` and the names main/master/paper. Returns (path or None, [candidate .tex paths])."""
    texs = sorted(glob.glob(os.path.join(d, "*.tex")))
    scored = []
    for t in texs:
        try:
            txt = read(t)
        except OSError:
            continue
        if not re.search(r"\\documentclass", txt):
            continue
        name = os.path.splitext(os.path.basename(t))[0].lower()
        name_pref = 3 if name == "main" else 2 if name in ("master", "paper") else 0
        scored.append((name_pref, len(INPUT_RE.findall(txt)), t))
    if not scored:
        return None, texs
    scored.sort(reverse=True)
    return scored[0][2], texs


def pick_master_from_candidates(candidates):
    r"""The [[SEAM:input-resolve]] recovery: pick the existing .tex that is a real master from a list of
    candidates — has ``\documentclass``, prefer one that ``\input{}``s sections, then names main/master/
    paper. First max wins on a tie (input order is preserved). Returns a path or None. This is the
    deterministic logic that used to live inline as pickMasterFromCandidates in every spec; the spec's
    recovery now calls ``resolve_manuscript.py --pick-master-from '<json list>'``."""
    best, best_score = None, -1
    for c in candidates:
        try:
            txt = read(c)
        except OSError:
            continue
        if not re.search(r"\\documentclass", txt):
            continue
        n_input = len(INPUT_RE.findall(txt))
        base = os.path.splitext(os.path.basename(c))[0].lower()
        name_pref = 3 if base == "main" else 2 if base in ("master", "paper") else 0
        score = name_pref * 1000 + n_input
        if score > best_score:      # strict > => first max wins on a tie
            best_score = score
            best = c
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master")
    ap.add_argument("--pick-master-from",
                    help="JSON array of candidate .tex paths; prints {master: pick|null} and exits")
    ap.add_argument("--section-order",
                    default="introduction,results,methods,discussion,si,abstract")
    args = ap.parse_args()

    if args.pick_master_from is not None:
        cands = json.loads(args.pick_master_from)
        print(json.dumps({"master": pick_master_from_candidates(cands)}))
        return

    if not args.master:
        ap.error("--master is required (unless --pick-master-from is given)")

    raw = args.master
    if os.path.isdir(raw):                            # directory given -> auto-select the master .tex
        chosen, cands = find_master_in_dir(raw)
        if not chosen:
            print(json.dumps({"error": r"directory has no master .tex (with \documentclass): %s" % raw,
                              "candidates": cands}))
            raise SystemExit(2)
        sys.stderr.write("[resolve] directory given; selected master: %s\n" % chosen)
        master = os.path.realpath(chosen)
    else:
        master = os.path.realpath(os.path.abspath(raw))
        if not os.path.isfile(master):               # wrong/missing filename -> emit candidates for the seam
            d = os.path.dirname(master) or "."
            cands = sorted(glob.glob(os.path.join(d, "*.tex"))) if os.path.isdir(d) else []
            print(json.dumps({"error": "master file not found: %s" % raw, "candidates": cands}))
            raise SystemExit(2)
    order = [s.strip() for s in args.section_order.split(",") if s.strip()]
    md, inputs = resolve_inputs(master)
    fmt = detect_format(read(master))

    files = []
    if inputs:                                   # ---- multi-file: one unit per included file ----
        for ap in inputs:
            base = os.path.splitext(os.path.basename(ap))[0]
            section, rubric = classify(base)
            signal = "basename"
            if not section:                      # basename uninformative -> try the file's heading
                section, rubric = classify(first_heading(read(ap)))
                signal = "heading"
            if not section:                      # unclassifiable -> context-only, not a loop unit
                continue
            files.append({"path": ap, "rel": os.path.relpath(ap, md),
                          "section": section, "rubric": rubric,
                          "cites": len(CITE_RE.findall(read(ap))), "signal": signal})
    else:                                        # ---- single-file: one unit per section heading ----
        text = read(master)
        cites = len(CITE_RE.findall(text))
        seen = set()
        for m in HEADING_RE.finditer(text):
            heading = m.group(1) or "abstract"
            section, rubric = classify(heading)
            if not section or section in seen:
                continue
            seen.add(section)
            files.append({"path": master, "rel": os.path.basename(master),
                          "section": section, "rubric": rubric,
                          "cites": cites, "signal": "heading"})

    # order by section_order (stable -> source order kept within a section, e.g. discussion before conclusion)
    files.sort(key=lambda f: order.index(f["section"]) if f["section"] in order else 99)

    context = []
    for f in files:
        if f["path"] not in context:
            context.append(f["path"])
    if master not in context:                    # master is always read-only context (multi-file case)
        context.insert(0, master)

    present = []
    for f in files:
        if f["section"] not in present:
            present.append(f["section"])

    print(json.dumps({"format": fmt, "master": master, "files": files,
                      "contextFilesList": context, "presentSections": present}))


if __name__ == "__main__":
    main()
