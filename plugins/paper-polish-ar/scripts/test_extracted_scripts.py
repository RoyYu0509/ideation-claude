#!/usr/bin/env python3
"""Unit tests for the WG-C extracted determinism scripts:
  build_manifest.py   — the four fidelity-manifest modes (review / consolidate / polish / figure)
  lint_citations.py   — the dangling-citation advisory lint
  venue_resolve.py    — venue list / resolve / pack, incl. the --require-review-kit branch + core overlay

Each test builds a tiny on-disk fixture and drives the script exactly as the spec does (stdin-JSON or
CLI flags -> stdout-JSON). Pure subprocess; no import of the scripts. Run: python3 scripts/test_extracted_scripts.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build_manifest.py")
LINT = os.path.join(HERE, "lint_citations.py")
VENUE = os.path.join(HERE, "venue_resolve.py")

failures = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"        got : {got!r}")
        print(f"        want: {want!r}")
        failures.append(label)


def check_true(label, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        failures.append(label)


def run_stdin(script, payload):
    r = subprocess.run([sys.executable, script], input=json.dumps(payload),
                       capture_output=True, text=True)
    assert r.returncode == 0, f"{script} exited {r.returncode}: {r.stderr}"
    return json.loads(r.stdout)


def run_args(script, *args):
    r = subprocess.run([sys.executable, script, *args], capture_output=True, text=True)
    assert r.returncode == 0, f"{script} {args} exited {r.returncode}: {r.stderr}"
    return json.loads(r.stdout)


def make_paper(d):
    """A small multi-file LaTeX paper with data/figure files + a .bib."""
    os.makedirs(os.path.join(d, "data"))
    os.makedirs(os.path.join(d, "figures"))
    open(os.path.join(d, "main.tex"), "w").write(
        "\\documentclass{article}\\begin{document}\n"
        "\\begin{abstract}12.5% gain on 3,000 items \\cite{smith2020}\\end{abstract}\n"
        "\\input{intro}\n\\input{methods}\n\\end{document}\n")
    open(os.path.join(d, "intro.tex"), "w").write(
        "\\section{Introduction}\n\\cite{jones2019,missing_key} \\citep{nope}. [@mdkey]\n")
    open(os.path.join(d, "methods.tex"), "w").write(
        "\\section{Methods}\n99.9% acc. \\bibitem{localbib} x\n")
    open(os.path.join(d, "refs.bib"), "w").write(
        "@article{smith2020,title={A}}\n@book{jones2019,title={B}}\n@string{foo=\"bar\"}\n")
    open(os.path.join(d, "data", "d.csv"), "w").write("x,y\n")
    open(os.path.join(d, "figures", "f.png"), "w").write("png\n")
    return os.path.join(d, "main.tex")


def test_manifest():
    print("build_manifest.py")
    with tempfile.TemporaryDirectory() as d:
        master = make_paper(d)
        cfl = [master, os.path.join(d, "intro.tex"), os.path.join(d, "methods.tex")]
        proj = os.path.join(d, "proj")
        base = {"root": d, "master": master, "manuscripts": cfl, "format": "latex", "proj": proj}

        rev = run_stdin(BUILD, {**base, "mode": "review"})
        con = run_stdin(BUILD, {**base, "mode": "consolidate"})
        # review & consolidate differ ONLY by the mode string
        check("review mode string", rev["mode"], "review")
        check("consolidate mode string", con["mode"], "consolidate")
        rev_nomode = {k: v for k, v in rev.items() if k != "mode"}
        con_nomode = {k: v for k, v in con.items() if k != "mode"}
        check("review==consolidate except mode", rev_nomode, con_nomode)
        # review records base numbers + cite keys; data/bib/figure files are denylisted.
        # NUM regex matches decimal%/percent only -> "12.5%","99.9%" (NOT "3,000": no decimal, no %).
        check("review base_numbers", rev["base_numbers"], ["12.5%", "99.9%"])
        # cite keys come from \cite + [@..] + .bib @entry{} — NOT from \bibitem (localbib is excluded).
        check_true("review base_cite_keys has the bib + cited keys",
                   {"smith2020", "jones2019", "missing_key"} <= set(rev["base_cite_keys"]))
        check_true("review base_cite_keys excludes \\bibitem-only key",
                   "localbib" not in set(rev["base_cite_keys"]))
        deny_names = sorted(os.path.basename(p) for p in rev["denylist"])
        check("review denylist files", deny_names, ["d.csv", "f.png", "refs.bib"])
        check_true("review writes manifest file",
                   os.path.isfile(os.path.join(proj, ".polish", "fidelity-manifest.json")))

        pol = run_stdin(BUILD, {**base, "mode": "polish"})
        check("polish mode string", pol["mode"], "polish")
        check_true("polish has worktree-safe fields",
                   all(k in pol for k in ("gitroot", "manuscripts_rel", "denylist_rel")))
        check_true("polish has NO base_numbers (semantic freeze)", "base_numbers" not in pol)
        check_true("polish manuscripts_rel are relative",
                   all(not p.startswith("/") for p in pol["manuscripts_rel"]))

        fig = run_stdin(BUILD, {"mode": "figure", "root": d, "proj": proj})
        check("figure mode string", fig["mode"], "figure")
        check_true("figure forces latex format", fig["format"] == "latex")
        check_true("figure freezes data dir contents", any(p.endswith("data/d.csv") or p.endswith("data\\d.csv") for p in fig["denylist"]))
        check_true("figure does NOT freeze the .png figure", not any(p.endswith("f.png") for p in fig["denylist"]))
        check_true("figure has no manuscripts field", "manuscripts" not in fig)


def test_lint():
    print("lint_citations.py")
    with tempfile.TemporaryDirectory() as d:
        master = make_paper(d)
        files = [master, os.path.join(d, "intro.tex"), os.path.join(d, "methods.tex")]
        out = run_stdin(LINT, {"root": d, "files": files})
        keys = {row["key"] for row in out}
        # defined: smith2020, jones2019 (.bib) + localbib (\bibitem). 'foo' is an @string -> NOT a key.
        check_true("dangling = missing_key, nope, mdkey", keys == {"missing_key", "nope", "mdkey"})
        check_true("defined keys are NOT flagged", not ({"smith2020", "jones2019", "localbib"} & keys))
        row = next(r for r in out if r["key"] == "missing_key")
        check("missing_key located in intro.tex", row["files"], ["intro.tex"])
        # robustness: bad input degrades to []
        r = subprocess.run([sys.executable, LINT], input="not json", capture_output=True, text=True)
        check("bad input -> []", json.loads(r.stdout), [])


def test_venue():
    print("venue_resolve.py")
    with tempfile.TemporaryDirectory() as root:
        vb = os.path.join(root, "skills", "house-style", "examples", "venue-anchors")
        for sub in ["JCP", "SIAM/_core", "SIAM/SISC/review", "Nature/review", "default/review", "_TEMPLATE"]:
            os.makedirs(os.path.join(vb, sub), exist_ok=True)
        open(os.path.join(vb, "JCP", "profile.md"), "w").write("p")            # profile, NO review kit
        open(os.path.join(vb, "SIAM", "_core", "profile.md"), "w").write("p")  # shared core
        open(os.path.join(vb, "SIAM", "SISC", "profile.md"), "w").write("p")
        open(os.path.join(vb, "SIAM", "SISC", "review", "rubric.md"), "w").write("r")
        open(os.path.join(vb, "Nature", "profile.md"), "w").write("p")
        open(os.path.join(vb, "Nature", "review", "rubric.md"), "w").write("r")
        open(os.path.join(vb, "default", "profile.md"), "w").write("p")
        open(os.path.join(vb, "default", "review", "rubric.md"), "w").write("r")
        open(os.path.join(vb, "_TEMPLATE", "profile.md"), "w").write("p")

        # list: --require-review-kit drops JCP (no kit); both drop default/_TEMPLATE/_core
        polish_list = run_args(VENUE, "list", "--root", root)["prepared"]
        review_list = run_args(VENUE, "list", "--root", root, "--require-review-kit")["prepared"]
        check("polish list (no kit)", sorted(polish_list), ["JCP", "Nature", "SIAM/SISC"])
        check("review list (+kit) drops JCP", sorted(review_list), ["Nature", "SIAM/SISC"])

        # resolve: JCP ok for polish, missing for review (the intentional difference, now explicit)
        check("resolve JCP polish ok", run_args(VENUE, "resolve", "--root", root, "--venue", "JCP")["status"], "ok")
        check("resolve JCP review missing",
              run_args(VENUE, "resolve", "--root", root, "--venue", "JCP", "--require-review-kit")["status"], "missing")

        # core+overlay detection on SIAM/SISC
        sisc = run_args(VENUE, "resolve", "--root", root, "--venue", "SIAM", "--field", "SISC", "--require-review-kit")
        check("resolve SISC ok", sisc["status"], "ok")
        check("resolve SISC label", sisc["label"], "SIAM/SISC")
        check_true("resolve SISC core overlay detected", sisc["coreProfile"].endswith("SIAM/_core/profile.md"))

        # discriminated branches
        check("resolve unknown -> missing",
              run_args(VENUE, "resolve", "--root", root, "--venue", "Bogus")["status"], "missing")
        check("resolve none -> needs-picker",
              run_args(VENUE, "resolve", "--root", root)["status"], "needs-picker")

        # pack (post-picker materialization) keeps the chosen status + detects core overlay
        pk = run_args(VENUE, "pack", "--root", root,
                      "--rel", "skills/house-style/examples/venue-anchors/SIAM/SISC",
                      "--label", "SIAM/SISC", "--status", "picked")
        check("pack status picked", pk["status"], "picked")
        check_true("pack core overlay", pk["coreProfile"].endswith("SIAM/_core/profile.md"))


def main():
    test_manifest()
    test_lint()
    test_venue()
    print()
    if failures:
        print(f"FAILED ({len(failures)}): {failures}")
        sys.exit(1)
    print("all extracted-script tests passed")


if __name__ == "__main__":
    main()
