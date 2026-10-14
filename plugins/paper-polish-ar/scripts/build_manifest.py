#!/usr/bin/env python3
r"""Build the .polish/fidelity-manifest.json that ARMS the pre-edit freeze hook.

ONE script replaces the four near-duplicate inline python heredocs that used to live in the specs
(buildReviewManifest / buildFidelityManifest×2 / buildFigureManifest). The four modes are NOT
interchangeable — each freezes a different surface — so the differences are made explicit here:

  review       — /review is diagnose-only: freeze EVERYTHING. Records the data/.bib/figure denylist
                 + base_numbers/base_cite_keys (for the citation lint). The hook then DENIES any write
                 to a denylisted file and any Write-overwrite of a manuscript.
  consolidate  — /rewrite pre-freeze pass: the PROSE freeze is lifted (numbers/citations/structure are
                 reconciled across sections) but the data/.bib denylist + no-Write-on-manuscript stay.
                 Same fields as review, only the mode string differs (anti-fabrication of derived
                 numbers is POST-HOC by the provenance auditor, not by this manifest).
  polish       — /polish prose freeze. Adds the WORKTREE-SAFE fields gitroot / manuscripts_rel /
                 denylist_rel so a reviser editing inside a linked git worktree (parallel sections) is
                 still recognized by repo-RELATIVE path. Does NOT record base_numbers (polish fidelity
                 is semantic, not number-diff).
  figure       — MIRROR of polish: FREEZE the cached data + manuscript prose, FREE the plotting scripts
                 + the figures they regenerate. Denylist = every file under data dirs (recursive) +
                 extension globs (data types + *.tex/*.md). Figures (.svg/.pdf/.png) and scripts (.py)
                 are deliberately NOT frozen.

Input  (JSON on stdin):
  {mode, root, master, manuscripts, format, proj}
    mode        one of review|consolidate|polish|figure
    root        review/polish/consolidate: dirname(master); figure: the git toplevel
    master      absolute master path                     (ignored for figure)
    manuscripts contextFilesList — every editable file + master (ignored for figure)
    format      "latex"|"markdown"                        (figure forces "latex")
    proj        projectDir — manifest is written to <proj>/.polish/fidelity-manifest.json
Output: writes <proj>/.polish/fidelity-manifest.json AND prints the manifest JSON to stdout.
"""
import glob
import json
import os
import re
import subprocess
import sys

DATA_GLOBS = ["*.bib", "data/*", "tables/*", "figures/*", "figs/*", "*.csv"]
NUM = re.compile(r"\d[\d,]*\.\d+%?|\d[\d,]*%")
CITE = re.compile(r"\\cite[a-zA-Z]*\{([^}]*)\}")
MDC = re.compile(r"\[@([^\]]+)\]")
BIB = re.compile(r"@[A-Za-z]+\{([^,\s]+)")

# figure mode: data file TYPES (frozen anywhere by basename) + the manuscript prose
FIG_EXT_GLOBS = ["*.bib", "*.csv", "*.tsv", "*.json", "*.npz", "*.npy", "*.parquet",
                 "*.feather", "*.h5", "*.hdf5", "*.pkl", "*.mat", "*.tex", "*.md", "*.bbl"]
FIG_DATA_DIRS = ["data", "data_external", "datasets", "raw", "cache", "artifacts"]


def read(p):
    try:
        return open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""


def scan_numbers_and_cites(srcs):
    """base_numbers + base_cite_keys over the manuscript + denylisted source files (review/consolidate)."""
    nums, cites = set(), set()
    for p in srcs:
        t = read(p)
        if not t:
            continue
        nums |= set(NUM.findall(t))
        for grp in CITE.findall(t):
            cites |= set(k.strip() for k in grp.split(",") if k.strip())
        for grp in MDC.findall(t):
            cites |= set(k.strip().lstrip("@") for k in grp.split(";") if k.strip())
        cites |= set(BIB.findall(t))
    return sorted(nums), sorted(cites)


def expand_denylist(root):
    deny = []
    for g in DATA_GLOBS:
        deny += [os.path.abspath(p) for p in glob.glob(os.path.join(root, g))]
    return sorted(set(deny))


def gitroot_of(d):
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return os.path.realpath(r.stdout.strip())
    except Exception:
        pass
    return os.path.realpath(d)


def build_review_like(cfg, mode):
    root = cfg["root"]
    manuscripts = [os.path.abspath(p) for p in cfg["manuscripts"]]
    deny = expand_denylist(root)
    nums, cites = scan_numbers_and_cites(manuscripts + deny)
    return {
        "manuscripts": manuscripts,
        "manuscript": os.path.abspath(cfg["master"]),
        "format": cfg["format"],
        "mode": mode,
        "denylist": deny,
        "denylist_globs": DATA_GLOBS,
        "base_numbers": nums,
        "base_cite_keys": cites,
    }


def build_polish(cfg):
    root = cfg["root"]
    gitroot = gitroot_of(root)
    cfl = cfg["manuscripts"]
    manuscripts = [os.path.abspath(p) for p in cfl]
    manuscripts_rel = sorted(set(os.path.relpath(os.path.realpath(p), gitroot) for p in cfl))
    deny = expand_denylist(root)
    deny_rel = sorted(set(os.path.relpath(os.path.realpath(p), gitroot) for p in deny))
    return {
        "manuscripts": manuscripts,
        "manuscripts_rel": manuscripts_rel,
        "manuscript": os.path.abspath(cfg["master"]),
        "gitroot": gitroot,
        "format": cfg["format"],
        "mode": "polish",
        "denylist": deny,
        "denylist_rel": deny_rel,
        "denylist_globs": DATA_GLOBS,
    }


def build_figure(cfg):
    root = os.path.realpath(cfg["root"])
    deny = []
    for d in FIG_DATA_DIRS:
        for p in glob.glob(os.path.join(root, "**", d, "**", "*"), recursive=True):
            if os.path.isfile(p):
                deny.append(os.path.abspath(p))
    deny = sorted(set(deny))
    deny_rel = sorted(set(os.path.relpath(os.path.realpath(p), root) for p in deny))
    globs = FIG_EXT_GLOBS + [d + "/*" for d in FIG_DATA_DIRS]
    return {
        "mode": "figure",
        "gitroot": root,
        "format": "latex",
        "denylist": deny,
        "denylist_rel": deny_rel,
        "denylist_globs": globs,
    }


def main():
    cfg = json.load(sys.stdin)
    mode = cfg["mode"]
    if mode in ("review", "consolidate"):
        m = build_review_like(cfg, mode)
    elif mode == "polish":
        m = build_polish(cfg)
    elif mode == "figure":
        m = build_figure(cfg)
    else:
        sys.stderr.write("build_manifest: unknown mode %r\n" % mode)
        raise SystemExit(2)

    out = json.dumps(m, indent=2)
    proj = cfg.get("proj")
    if proj:
        d = os.path.join(proj, ".polish")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "fidelity-manifest.json"), "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
