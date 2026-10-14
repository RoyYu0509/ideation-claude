#!/usr/bin/env python3
"""Step-A acceptance probe — the freeze PreToolUse hook must recognize a protected manuscript
(and a denylisted data file) even when the reviser edits it inside a linked git WORKTREE.

Runs check_fidelity.py as a subprocess against a THROWAWAY temp repo + worktree + temp manifest. It
never touches the project's real .polish/fidelity-manifest.json (it points CLAUDE_PROJECT_DIR + the
payload cwd at the temp repo). Self-cleaning; exits nonzero on any failed assertion.

What it asserts (mirrors 06-execution-protocol §3 · Step A gate):
  1. main-tree edit that DROPS a frozen number  -> DENY (no regression)
  2. worktree edit that DROPS a frozen number   -> DENY (the worktree freeze — the whole point)
  3. worktree edit that PRESERVES the number     -> ALLOW (rephrasing is always free)
  4. main-tree edit that PRESERVES the number    -> ALLOW (no regression)
  5. worktree edit to a denylisted *.bib file    -> DENY (data files frozen in any tree)
  6. /var ↔ /private/var must not cause a miss   -> implied by (2)/(5): macOS $TMPDIR is under
     /var/folders, reported by realpath as /private/var, so a passing (2) exercises G2 directly.

  Fail-CLOSED under git failure (the parallel design fires ~cap×3 concurrent `git` calls, so a
  rev-parse timeout / git-off-PATH is reachable; recognition must NOT depend on git succeeding):
  7. worktree drops a frozen number, GIT UNAVAILABLE  -> DENY (git-free suffix match, fail-closed)
  8. worktree NEW non-manuscript file, GIT UNAVAILABLE -> ALLOW (suffix miss -> not protected)
  9. worktree edits a path-prefix denylisted data file (data/*, NOT caught by a basename glob),
     git OK -> DENY; and the SAME file with GIT UNAVAILABLE -> DENY (fail-closed).

Run:  python3 hooks/test_freeze_worktree.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_fidelity.py")

failures = []


def sh(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def run_hook(proj, file_path, old, new, tool="Edit", break_git=False):
    """Invoke the hook exactly as the harness does. Returns (denied: bool, reason: str).
    break_git=True strips git from PATH so the hook's `git rev-parse` fails (simulates a
    timeout / git-off-PATH) — recognition must then fall back to the git-free path, fail-closed."""
    payload = {"tool_name": tool, "cwd": proj,
               "tool_input": {"file_path": file_path, "old_string": old, "new_string": new}}
    env = dict(os.environ, CLAUDE_PROJECT_DIR=proj)
    if break_git:
        env["PATH"] = ""   # python is launched via sys.executable (absolute); only the hook's git lookup breaks
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    out = (r.stdout or "").strip()
    if not out:
        return False, ""
    try:
        dec = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
        return dec == "deny", json.loads(out)["hookSpecificOutput"].get("permissionDecisionReason", "")
    except Exception:
        return False, out


def check(label, got_denied, want_denied):
    ok = (got_denied == want_denied)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: "
          f"{'DENY' if got_denied else 'ALLOW'} (wanted {'DENY' if want_denied else 'ALLOW'})")
    if not ok:
        failures.append(label)


def main():
    tmp = tempfile.mkdtemp(prefix="polish-freeze-probe-")
    try:
        repo = os.path.join(tmp, "repo")
        sub = os.path.join(repo, "sections")
        os.makedirs(sub)
        os.makedirs(os.path.join(repo, ".polish"))
        intro = os.path.join(sub, "intro.tex")
        bibf = os.path.join(repo, "refs.bib")
        os.makedirs(os.path.join(repo, "data"))
        dataf = os.path.join(repo, "data", "results.dat")   # path-prefix denylist, NOT a basename glob
        with open(intro, "w") as f:
            f.write("We report an accuracy of 0.953 on the held-out set \\cite{smith2020}.\n")
        with open(bibf, "w") as f:
            f.write("@article{smith2020, title={X}}\n")
        with open(dataf, "w") as f:
            f.write("0.953\n")

        sh(["git", "init", "-q"], cwd=repo)
        sh(["git", "config", "user.email", "probe@test"], cwd=repo)
        sh(["git", "config", "user.name", "probe"], cwd=repo)
        sh(["git", "add", "sections/intro.tex", "refs.bib", "data/results.dat"], cwd=repo)
        sh(["git", "commit", "-q", "-m", "base"], cwd=repo)

        # Build the manifest exactly as buildFidelityManifest (Step A) writes it.
        gitroot = os.path.realpath(repo)
        manifest = {
            "manuscripts": [os.path.abspath(intro)],
            "manuscripts_rel": [os.path.relpath(os.path.realpath(intro), gitroot)],
            "manuscript": os.path.abspath(intro),
            "gitroot": gitroot,
            "format": "latex",
            "denylist": [os.path.abspath(bibf), os.path.abspath(dataf)],
            "denylist_rel": [os.path.relpath(os.path.realpath(bibf), gitroot),
                             os.path.relpath(os.path.realpath(dataf), gitroot)],
            "denylist_globs": ["*.bib", "data/*", "tables/*", "figures/*", "figs/*", "*.csv"],
        }
        with open(os.path.join(repo, ".polish", "fidelity-manifest.json"), "w") as f:
            json.dump(manifest, f)

        # Add a linked worktree at HEAD — its absolute paths differ from the main tree's.
        wt = os.path.join(tmp, "wt")
        sh(["git", "worktree", "add", "-q", wt, "HEAD"], cwd=repo)
        wt_intro = os.path.join(wt, "sections", "intro.tex")
        wt_bib = os.path.join(wt, "refs.bib")
        wt_data = os.path.join(wt, "data", "results.dat")
        wt_new = os.path.join(wt, "sections", "brand_new.tex")   # not in the manifest at all

        # Sanity: macOS $TMPDIR is under /var/folders -> realpath rewrites to /private/var (exercises G2).
        print(f"  (gitroot realpath = {gitroot})")
        print(f"  (worktree abspath = {wt})  [differs from main tree -> abspath match would MISS]")

        drop = ("accuracy of 0.953", "accuracy of 0.94")          # drops the frozen number -> must DENY
        keep = ("an accuracy of 0.953", "a held-out accuracy of 0.953")  # preserves it -> must ALLOW

        # The CLAUDE_PROJECT_DIR / cwd stays at the MAIN repo for every call (the worker never cd's into
        # the worktree — G5), so the hook finds the single main manifest, exactly like the real run.
        denied, _ = run_hook(repo, intro, *drop);     check("1. main-tree drops number", denied, True)
        denied, _ = run_hook(repo, wt_intro, *drop);  check("2. worktree drops number", denied, True)
        denied, _ = run_hook(repo, wt_intro, *keep);  check("3. worktree preserves number", denied, False)
        denied, _ = run_hook(repo, intro, *keep);     check("4. main-tree preserves number", denied, False)
        denied, _ = run_hook(repo, wt_bib, "title={X}", "title={Y}")
        check("5. worktree edits denylisted .bib", denied, True)

        # Fail-CLOSED under git failure (the review's confirmed finding): recognition must not depend on git.
        denied, _ = run_hook(repo, wt_intro, *drop, break_git=True)
        check("7. worktree drops number, GIT BROKEN -> fail-closed", denied, True)
        denied, _ = run_hook(repo, wt_intro, *keep, break_git=True)
        check("7b. worktree preserves number, GIT BROKEN -> ALLOW", denied, False)
        denied, _ = run_hook(repo, wt_new, "", "We hit 0.99 accuracy.", break_git=True)
        check("8. worktree NEW non-manuscript, GIT BROKEN -> ALLOW (suffix miss)", denied, False)
        denied, _ = run_hook(repo, wt_data, "0.953", "0.94")
        check("9a. worktree path-prefix denylist (data/*), git OK -> DENY", denied, True)
        denied, _ = run_hook(repo, wt_data, "0.953", "0.94", break_git=True)
        check("9b. worktree path-prefix denylist (data/*), GIT BROKEN -> fail-closed", denied, True)

        # Cite-with-sentence-cut: the polisher may drop a \cite when the whole clause is also cut.
        # 10. Drop aside (clause + cite together) -> ALLOW
        old_aside = ("The variance scales with N \\cite{jones2021}.\n"
                     "Metric-aware optimizers leverage momentum \\cite{smith2020}.\n"
                     "The overlap gap is the key contribution.")
        new_aside = ("The variance scales with N \\cite{jones2021}.\n"
                     "The overlap gap is the key contribution.")
        denied, _ = run_hook(repo, intro, old_aside, new_aside)
        check("10. cite dropped WITH its clause (aside cut) -> ALLOW", denied, False)

        # 11. Drop cite but KEEP the prose -> DENY (provenance stripped)
        old_kept = "Metric-aware optimizers leverage momentum \\cite{smith2020}."
        new_kept = "Metric-aware optimizers leverage momentum."
        denied, _ = run_hook(repo, intro, old_kept, new_kept)
        check("11. cite dropped, prose kept (provenance stripped) -> DENY", denied, True)

        print()
        if failures:
            print(f"FAILED: {len(failures)} assertion(s): {', '.join(failures)}")
            return 1
        print("Step A probe: ALL PASS — freeze holds in main tree AND worktree (no regression).")
        return 0
    finally:
        # remove the worktree's git registration best-effort, then nuke the temp dir
        subprocess.run(["git", "-C", os.path.join(tmp, "repo"), "worktree", "prune"],
                       capture_output=True, text=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
