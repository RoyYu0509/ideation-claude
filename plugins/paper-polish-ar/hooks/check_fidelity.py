#!/usr/bin/env python3
"""paper-polish — mechanical fidelity guard (the logic behind check-fidelity.sh).

PreToolUse hook for Edit / Write / MultiEdit. Decision rules:

  1. No active run -> no-op. If the manifest
     ($CLAUDE_PROJECT_DIR/.polish/fidelity-manifest.json) is missing, allow
     everything (exit 0, no output).
  2. Data-file denylist -> deny. Any edit whose target is a frozen pure-data
     file (.bib / data / tables / figures, by path or glob) is blocked outright.
  3. Manuscript, Write -> deny. Overwriting the whole manuscript bypasses the
     token check; force the reviser to use Edit/MultiEdit.
  4. Manuscript, Edit/MultiEdit -> token-preservation check. Every frozen
     mechanical token present in old_string must survive verbatim in new_string
     (numbers/units always; \\cite/\\ref/\\label keys and math spans for LaTeX;
     [@key] citations and $...$ math for Markdown). A dropped/changed token is
     denied with an actionable reason; the reviser then rewrites the prose
     *around* the token instead of through it.
  5. Anything else (new files, verdict files, .polish/*) -> allow.

Modes (manifest "mode"): "polish" (default — the rules above), "review" (the freeze is INVERTED:
an edit may drop a frozen token but may not INTRODUCE a new data number/citation), "experiment"
(review + a provenance-gated unfreeze allowlist that lets verified experiment results land in the
paper; see handle_experiment_mode — it FAILS CLOSED, defaulting to fully frozen), "figure" (the
MIRROR of polish — the denylist carries the cached DATA and the manuscript PROSE, while the plotting
scripts and the figure files they regenerate are free to change; see handle_figure_mode), and
"consolidate" (the pre-freeze whole-paper /rewrite consolidation — the prose freeze is LIFTED so the
reviser may reconcile numbers/citations/structure/theory across sections; only the LIGHT protection
stays, the data/.bib denylist + no-Write-on-manuscript, with anti-fabrication enforced POST-HOC by the
provenance auditor against the audited-values registry, since the hook cannot verify a DERIVED number).

Blocking uses the PreToolUse JSON form: permissionDecision "deny" + reason.
Any internal error fails open (exit 0) so the hook can never wedge a session.
"""

import json
import os
import re
import subprocess
import sys
from collections import Counter
from fnmatch import fnmatch


# --- worktree-safe path matching (Step A) ------------------------------------
#
# A reviser running inside a linked git WORKTREE (parallel sections) edits a file whose ABSOLUTE path
# differs from the main tree's, but whose REPO-RELATIVE path is identical. We recognize a protected
# manuscript / denylist file by that relative path so the freeze holds at any worktree depth. Both
# sides are realpath-normalized (macOS /var↔/private/var).
#
# CRITICAL — path matching must NEVER fail-OPEN on a manuscript when git misbehaves (Step A gate). The
# git call (`_repo_rel`) is only the AUTHORITATIVE recognizer when it succeeds; recognition does NOT
# DEPEND on it. Because a linked worktree mirrors the repo tree, a real copy's realpath always ENDS WITH
# its repo-relative path (`_path_matches_rel`) — a git-free check. So:
#   • git resolves a toplevel  → the resolved rel is authoritative (exact set membership; no false
#     positives — a genuine non-manuscript in the repo is correctly allowed);
#   • git CANNOT resolve (timeout / off PATH / nonzero — far likelier under the parallel design's
#     ~cap×3 concurrent git calls) → fall back to the git-free suffix match and treat a match as
#     PROTECTED (fail-CLOSED). A transient git failure can therefore never open the freeze on a worktree
#     manuscript; at worst it applies the (rephrase-allowing) token check to a path that merely shares a
#     repo-relative tail — the safe direction for a freeze.


def _repo_rel(path):
    """Repo-relative path of `path` via ITS OWN git toplevel (the worktree's, when edited inside one).
    realpath-normalized on both sides. None if git can't resolve a toplevel."""
    try:
        d = os.path.dirname(os.path.abspath(path)) or "."
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return os.path.relpath(os.path.realpath(path), os.path.realpath(r.stdout.strip()))
    except Exception:
        return None


def _path_matches_rel(file_path, rels):
    """GIT-FREE, worktree-safe recognizer: True if `file_path` is a copy of one of the repo-relative
    paths in `rels`. A linked worktree mirrors the repo tree, so the realpath of any copy ends with its
    repo-relative path. Used as the fail-CLOSED fallback when git cannot resolve a toplevel."""
    real = os.path.realpath(file_path)
    for rel in rels:
        if rel and (real == rel or real.endswith(os.sep + rel)):
            return True
    return False


def _manuscript_list(manifest):
    """The editable prose files. Multi-file runs list every file in `manuscripts`; single-file
    (back-compat) carries one `manuscript`."""
    ms = manifest.get("manuscripts")
    if not ms:
        m = manifest.get("manuscript")
        ms = [m] if m else []
    return [m for m in ms if m]


def is_manuscript(file_path, manifest):
    """True if `file_path` is a protected manuscript prose file — matched by absolute path (main tree)
    OR by repo-relative path (worktree-safe, Step A). Fail-CLOSED on git failure (see module note)."""
    abspath = os.path.abspath(file_path)
    real = os.path.realpath(file_path)
    for m in _manuscript_list(manifest):
        if abspath == os.path.abspath(m) or real == os.path.realpath(m):
            return True
    rels = manifest.get("manuscripts_rel") or []
    if not rels:
        return False                          # old manifest (abspath-only) — back-compat
    er = _repo_rel(file_path)
    if er is not None:
        return er in set(rels)                # git resolved the worktree rel → authoritative
    return _path_matches_rel(real, rels)      # git failed → fail-CLOSED git-free suffix match


def allow():
    # No decision: defer to normal permission flow.
    sys.exit(0)


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


# --- frozen-token extractors -------------------------------------------------

NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
LATEX_KEY_RE = re.compile(r"\\(?:cite[a-zA-Z]*|ref|eqref|autoref|pageref|nameref|label)\{[^}]*\}")
LATEX_MATH_RE = re.compile(r"\$\$.*?\$\$|\$[^$]+\$|\\\[.*?\\\]|\\\(.*?\\\)", re.DOTALL)
MD_CITE_RE = re.compile(r"\[@[^\]]+\]")
MD_MATH_RE = re.compile(r"\$[^$\n]+\$")


def frozen_tokens(text, fmt):
    """Return {class: Counter(tokens)} of frozen mechanical tokens in `text`.

    Keys and math spans are extracted first and removed from the text before
    numbers, so a year inside \\cite{smith2020} is attributed to the citation
    key, not counted as a free number.
    """
    tokens = {}
    rest = text
    if fmt == "latex":
        tokens["citation/ref/label key"] = Counter(LATEX_KEY_RE.findall(rest))
        rest = LATEX_KEY_RE.sub(" ", rest)
        tokens["math"] = Counter(LATEX_MATH_RE.findall(rest))
        rest = LATEX_MATH_RE.sub(" ", rest)
    elif fmt == "markdown":
        tokens["citation"] = Counter(MD_CITE_RE.findall(rest))
        rest = MD_CITE_RE.sub(" ", rest)
        tokens["math"] = Counter(MD_MATH_RE.findall(rest))
        rest = MD_MATH_RE.sub(" ", rest)
    tokens["number"] = Counter(NUMBER_RE.findall(rest))
    return tokens


def check_pair(old, new, fmt):
    """Return a human reason if a frozen token in `old` is missing from `new`, else None."""
    old_tok = frozen_tokens(old, fmt)
    new_tok = frozen_tokens(new, fmt)
    for cls, old_counter in old_tok.items():
        missing = old_counter - new_tok.get(cls, Counter())
        if not missing:
            continue

        # Citation/ref/label keys: allow the drop when the containing CLAUSE was also cut.
        # This handles "drop aside along with its \cite" without blocking legitimate prose cuts.
        # Numbers and math spans remain strictly frozen — no sentence-cut exception applies.
        if cls in ("citation/ref/label key", "citation"):
            truly_missing = Counter()
            for token, count in missing.items():
                if not _cite_was_cut_with_clause(old, new, token):
                    truly_missing[token] = count
            if not truly_missing:
                continue
            missing = truly_missing

        items = ", ".join(sorted(missing.elements()))
        return (
            f"This edit changes or drops a frozen {cls}: {items}. "
            f"The science is frozen — keep every {cls} verbatim and rewrite "
            f"the prose around it. If you are reordering, keep the token "
            f"inside the edited span; never restate a number, citation/ref "
            f"key, or math differently."
        )
    return None


# --- citation-with-sentence-cut helpers ---------------------------------------
#
# Polish mode blocks any dropped \cite/\ref/\label key. But when the polisher
# CUTS AN ENTIRE ASIDE (sentence or clause), the cite travels with the deleted
# prose — that is not reattachment, it is a legitimate reduction. We allow it
# by checking whether the prose IMMEDIATELY BEFORE the cite in old is absent
# from new. If the surrounding prose is gone too → the clause was cut → allow.
# If the prose is still present but the cite disappeared → provenance stripped →
# block (the original behavior). Numbers and math spans get no such exception.


def _strip_latex_prose(text):
    """Strip LaTeX markup, leaving only prose words for fingerprinting."""
    t = LATEX_KEY_RE.sub("", text)
    t = LATEX_MATH_RE.sub("", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})*", "", t)
    t = re.sub(r"[{}%$~&\\]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _sig_words(text):
    """Significant prose words (≥4 chars after stripping punctuation)."""
    return [w.strip(".,;:!?()[]\"' ") for w in text.split()
            if len(w.strip(".,;:!?()[]\"' ")) >= 4]


def _prose_context_absent(old, new, pos, token):
    """True if the prose immediately surrounding `token` at `pos` in `old` is absent from `new`.

    Uses the last 3 significant words before the token as a fingerprint probe.
    If before-context is too thin, falls back to the first 3 words after the token.
    Conservative (returns False) when context is too short to assess reliably.
    """
    before_raw = old[max(0, pos - 150):pos]
    probe_words = _sig_words(_strip_latex_prose(before_raw))[-3:]

    if len(probe_words) < 2:
        after_raw = old[pos + len(token):min(len(old), pos + len(token) + 150)]
        probe_words = _sig_words(_strip_latex_prose(after_raw))[:3]

    if len(probe_words) < 2:
        return False  # not enough context — conservative: treat as suspicious (block)

    probe = " ".join(probe_words)
    return probe not in new


def _cite_was_cut_with_clause(old, new, cite_token):
    """Return True if every occurrence of `cite_token` that is missing from `new`
    was in a clause whose surrounding prose was also removed.

    Allows 'drop aside along with its \\cite'; blocks 'drop cite, keep the prose'.
    """
    missing_count = old.count(cite_token) - new.count(cite_token)
    if missing_count <= 0:
        return True

    positions = []
    start = 0
    while True:
        pos = old.find(cite_token, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + len(cite_token)

    cut_count = sum(
        1 for pos in positions
        if _prose_context_absent(old, new, pos, cite_token)
    )
    return cut_count >= missing_count


# --- review-mode fabrication guard -------------------------------------------

# Review mode targets DATA numbers (decimals and percentages) — the fabrication-risk result values —
# and deliberately ignores bare integers ("Section 4", "Figure 2", "3 datasets"), which restructuring
# legitimately renumbers. A fabricated integer is rarer and is caught by the semantic VERIFY auditor.
REVIEW_NUM_RE = re.compile(r"\d[\d,]*\.\d+%?|\d[\d,]*%")


def _data_numbers(text):
    return Counter(REVIEW_NUM_RE.findall(text))


def _cite_keys(text):
    keys = set()
    for grp in re.findall(r"\\cite[a-zA-Z]*\{([^}]*)\}", text):
        keys |= {k.strip() for k in grp.split(",") if k.strip()}
    for grp in re.findall(r"\[@([^\]]+)\]", text):
        keys |= {k.strip().lstrip("@") for k in grp.split(";") if k.strip()}
    return keys


def review_fabrication(old, new, base_numbers, base_cite_keys):
    """Review mode: the freeze is INVERTED. An edit may DROP or move a frozen token (claims and
    structure are free to change), but it may NOT INTRODUCE a number or citation key that is not
    already somewhere in the paper's own base (manuscript + data/.bib). That introduction is
    fabrication. Returns a human reason, or None."""
    added_nums = _data_numbers(new) - _data_numbers(old)
    bad = [n for n in added_nums.elements() if n not in base_numbers]
    if bad:
        items = ", ".join(sorted(set(bad)))
        return (
            f"Review mode forbids introducing a DATA value (a measured number / percentage) not already "
            f"in the paper's own data: {items}. Claims and structure are free to change, but invented "
            f"results are not. Use the paper's real value, or state no number and flag it for the author "
            f"(a needs_author item)."
        )
    added_keys = _cite_keys(new) - _cite_keys(old)
    badk = [k for k in added_keys if k not in base_cite_keys]
    if badk:
        items = ", ".join(sorted(set(badk)))
        return (
            f"Review mode forbids introducing a CITATION not already in the paper: {items}. "
            f"Cite only references the paper already contains; adding new scholarship is an author "
            f"decision (escalate it)."
        )
    return None


# --- experiment-mode provenance-gated unfreeze -------------------------------
#
# Experiment mode = review mode (inverted freeze, no new number/citation) PLUS two narrow,
# provenance-backed exceptions, each tied to a run-ledger record that a read-only auditor has
# marked audit_status=="pass":
#   blessed_files[]   - denylist data/result/figure paths a real run legitimately wrote.
#   blessed_numbers[] - specific NEW data values (decimals/percentages) the reviser may write into
#                       a specific paper file (the old->new write-back of an experiment result).
# Defaults are EMPTY, so a fresh experiment manifest behaves exactly like review mode = fully frozen.
# The channel is strictly additive and strictly per-token, and it FAILS CLOSED: if the allowlist
# machinery is missing/garbled, or a referenced ledger record is not "pass", the edit is DENIED
# (frozen), never allowed. (This is distinct from the hook's own internal-error fail-OPEN, which only
# means "behave as if no run is active".)


def _load_ledger(manifest):
    lp = manifest.get("ledger_path")
    if not lp:
        return None
    try:
        with open(lp) as f:
            return json.load(f)
    except Exception:
        return None


def _ledger_ok(ledger, ledger_id):
    """True iff the ledger has a run record with this id whose audit_status is 'pass'."""
    if not ledger or not ledger_id:
        return False
    for r in ledger.get("runs", []) or []:
        if r.get("ledger_id") == ledger_id:
            return r.get("audit_status") == "pass"
    return False


def _allowlist_well_formed(manifest):
    """Empty allowlists are well-formed (= frozen). Non-empty requires an existing ledger file and
    correctly-shaped entries. Anything else => freeze."""
    bf = manifest.get("blessed_files", [])
    bn = manifest.get("blessed_numbers", [])
    if not isinstance(bf, list) or not isinstance(bn, list):
        return False
    for e in bf:
        if not isinstance(e, dict) or "path" not in e or "ledger_id" not in e:
            return False
    for e in bn:
        if not isinstance(e, dict) or "new" not in e or "file" not in e or "ledger_id" not in e:
            return False
    if bf or bn:
        lp = manifest.get("ledger_path")
        if not lp or not os.path.isfile(lp):
            return False
    return True


def _blessed_file(manifest, file_path):
    ap = os.path.abspath(file_path)
    for e in manifest.get("blessed_files", []) or []:
        if e.get("path") and os.path.abspath(e["path"]) == ap:
            return e
    return None


def _blessed_new_numbers(manifest, file_path, ledger):
    """The set of NEW data-number literals the reviser may introduce into `file_path` — only those
    on a blessed_numbers entry for this file whose ledger record is 'pass'. Every such value traces
    to a real, audited run, so introducing it is provenance-backed; every OTHER new data number in
    the same edit still runs the normal review no-fabrication check."""
    ap = os.path.abspath(file_path)
    out = set()
    for e in manifest.get("blessed_numbers", []) or []:
        if not e.get("file") or os.path.abspath(e["file"]) != ap:
            continue
        if not _ledger_ok(ledger, e.get("ledger_id")):
            continue
        out |= set(REVIEW_NUM_RE.findall(str(e.get("new", ""))))
    return out


def handle_experiment_mode(manifest, tool, ti, file_path):
    """Full decision tree for mode=="experiment". Always exits via allow()/deny()."""
    # 0. fail-CLOSED guard: a present-but-broken allowlist freezes everything (one deny, not a crash,
    #    so we never reach the hook's fail-OPEN path).
    if not _allowlist_well_formed(manifest):
        deny(
            "Experiment-mode freeze: the provenance allowlist (run-ledger / blessed_* in the "
            "manifest) is missing or malformed, so the freeze stays fully on — no data file or "
            "number may change. This is fail-closed by design; fix the ledger/manifest and retry."
        )
    ledger = _load_ledger(manifest)

    # 1. denylist data/result/figure file: allow ONLY if this exact path is blessed and its ledger
    #    record passed. Otherwise frozen — a real value comes from RE-RUNNING the experiment (Bash
    #    writes the file), never from a hand Edit/Write.
    if on_denylist(file_path, manifest):
        bf = _blessed_file(manifest, file_path)
        if bf and _ledger_ok(ledger, bf.get("ledger_id")):
            allow()
        deny(
            f"{os.path.basename(file_path)} is a frozen data/result/figure file. In experiment mode "
            f"it changes only by re-running the experiment (a real run writes it) and only when its "
            f"provenance is on the audited allowlist — never by a hand edit. Run the experiment."
        )

    # 2. is this a manuscript prose file? (everything else — experiment code experiments/*.jl,
    #    plot_*.py, new files, .polish/* — is allowed; the runner edits code freely.)
    if not is_manuscript(file_path, manifest):
        allow()

    # 3. Write to the manuscript -> deny (force token-checkable Edit), as in the other modes.
    if tool == "Write":
        deny(
            "Do not overwrite the whole manuscript with Write — it bypasses the provenance check. "
            "Use Edit/MultiEdit so each write-back can be checked."
        )

    # 4. per-edit: the review no-fabrication floor, with blessed new-numbers added to the allowed set.
    allowed_numbers = set(manifest.get("base_numbers", [])) | _blessed_new_numbers(manifest, file_path, ledger)
    base_cite_keys = set(manifest.get("base_cite_keys", []))
    if tool == "Edit":
        reason = review_fabrication(ti.get("old_string", ""), ti.get("new_string", ""), allowed_numbers, base_cite_keys)
        if reason:
            deny(reason)
    elif tool == "MultiEdit":
        for e in ti.get("edits", []) or []:
            reason = review_fabrication(e.get("old_string", ""), e.get("new_string", ""), allowed_numbers, base_cite_keys)
            if reason:
                deny(reason)
    allow()


def handle_figure_mode(manifest, tool, ti, file_path):
    """Full decision tree for mode=="figure" — the MIRROR of polish mode. /polish-figures rewrites the
    plotting scripts and regenerates the figures they produce; it must never touch the DATA behind a
    figure or the paper's PROSE. So the freeze is inverted relative to polish: the denylist carries the
    cached analysis data AND the manuscript prose (the manifest puts *.tex / *.md in denylist_globs),
    while plotting scripts (plot_*.py, *viz*.py, make_figure*.py, shared style helpers …), the
    regenerated figure files (.svg / .pdf / .png — NOT denylisted in this mode), and any new file are
    free. There is NO ledger / provenance gate (that is experiment mode): a figure is polished
    interactively by editing its script and re-running it, not re-derived from an audited run. Always
    exits via allow()/deny()."""
    # 1. denylist (in figure mode: cached data + manuscript prose) -> frozen. The figure depends on
    #    this data and the paper describes it; /polish-figures changes neither.
    if on_denylist(file_path, manifest):
        deny(
            f"{os.path.basename(file_path)} is frozen in figure mode — it is either the cached analysis "
            f"data a figure depends on, or the paper's prose. /polish-figures changes only the plotting "
            f"scripts and the figures they regenerate, never the underlying data or the manuscript text. "
            f"Edit the plotting script (then re-run it to regenerate the figure), not the data/prose."
        )
    # 2. everything else — plotting scripts, regenerated figure files, new files — is free.
    allow()


# --- denylist matching -------------------------------------------------------

def on_denylist(path, manifest):
    abspath = os.path.abspath(path)
    real = os.path.realpath(path)
    base = os.path.basename(abspath)
    for d in manifest.get("denylist", []):
        if abspath == os.path.abspath(d) or real == os.path.realpath(d):
            return True
    # repo-relative (worktree-safe, Step A) — also catches a worktree copy of a denylisted data file
    # whose absolute path differs from the main tree's. (Basename globs below already catch *.bib etc.
    # in any path git-free; this adds the path-specific entries like data/foo.csv.) Fail-CLOSED on git
    # failure, exactly like is_manuscript: git-resolved rel is authoritative, else git-free suffix match.
    rels = manifest.get("denylist_rel") or []
    if rels:
        er = _repo_rel(path)
        if er is not None:
            if er in set(rels):
                return True
        elif _path_matches_rel(real, rels):
            return True
    # Globs (e.g. "*.bib", "data/*") are scoped to the paper's gitroot — a stale manifest from a prior
    # polish run must not block unrelated .bib files in the project (basename matching is otherwise global).
    gitroot = manifest.get("gitroot", "")
    for g in manifest.get("denylist_globs", []):
        if gitroot and not (abspath.startswith(gitroot + "/") or abspath == gitroot):
            continue  # file is outside this paper's tree; skip glob
        if fnmatch(abspath, g) or fnmatch(base, g):
            return True
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        allow()

    proj = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    manifest_path = os.path.join(proj, ".polish", "fidelity-manifest.json")
    if not os.path.isfile(manifest_path):
        allow()  # no active run
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except Exception:
        allow()

    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}
    file_path = ti.get("file_path")
    if not file_path:
        allow()

    # Experiment mode dispatches to its own provenance-gated decision tree (denylist files become
    # conditionally writable, new numbers conditionally land in the paper). It always exits.
    if manifest.get("mode") == "experiment":
        handle_experiment_mode(manifest, tool, ti, file_path)

    # Figure mode is the MIRROR of polish (see handle_figure_mode): the denylist carries the cached
    # data + the manuscript prose, while plotting scripts and the figures they regenerate are free. It
    # always exits.
    if manifest.get("mode") == "figure":
        handle_figure_mode(manifest, tool, ti, file_path)

    # 2. data-file denylist
    if on_denylist(file_path, manifest):
        deny(
            f"{os.path.basename(file_path)} is a frozen data file (citations / "
            f"data / tables / figures) and must never be edited during polishing. "
            f"Polishing only rewrites manuscript prose."
        )

    # is this one of the manuscript prose files? (abspath OR worktree-safe repo-relative match)
    if not is_manuscript(file_path, manifest):
        allow()  # new files, verdict files, .polish/*, master back-matter we don't loop, etc.

    fmt = manifest.get("format", "latex")
    mode = manifest.get("mode", "polish")

    # 3. Write to the manuscript -> deny (force token-checkable Edit) in BOTH modes.
    if tool == "Write":
        deny(
            "Do not overwrite the whole manuscript with Write — it bypasses the "
            "fidelity check. Use Edit/MultiEdit so each change can be checked."
        )

    # 4-pre. CONSOLIDATE mode (the pre-freeze whole-paper /rewrite consolidation — REWRITE-CONSOLIDATION-PLAN
    #     Q5). The prose freeze is LIFTED: to reconcile the cross-section drift that N review rounds accumulate,
    #     the reviser MAY rewrite numbers, citations, paragraph structure, and theory exposition freely. The hook
    #     keeps ONLY the LIGHT protection that already ran above — the data/.bib/results denylist (deny) and the
    #     no-Write-on-manuscript rule (deny) — so a real value still comes from an audited run, never a hand edit
    #     of the data. Anti-fabrication of the prose numbers/citations is enforced POST-HOC by the provenance
    #     auditor against the audited-values registry: the hook CANNOT verify a DERIVED number (a difference /
    #     rounding / percentage of audited values — REWRITE-CONSOLIDATION-PLAN Q2) and so must NOT block it here.
    if mode == "consolidate":
        allow()

    # 4a. REVIEW mode: no-fabrication guard. The freeze is inverted — claims/structure are free, but a
    #     new number or citation not already in the paper is fabrication and is denied.
    if mode == "review":
        base_numbers = set(manifest.get("base_numbers", []))
        base_cite_keys = set(manifest.get("base_cite_keys", []))
        if tool == "Edit":
            reason = review_fabrication(ti.get("old_string", ""), ti.get("new_string", ""), base_numbers, base_cite_keys)
            if reason:
                deny(reason)
        elif tool == "MultiEdit":
            for e in ti.get("edits", []) or []:
                reason = review_fabrication(e.get("old_string", ""), e.get("new_string", ""), base_numbers, base_cite_keys)
                if reason:
                    deny(reason)
        allow()

    # 4b. POLISH mode (default): token preservation — every frozen token in old must survive in new.
    if tool == "Edit":
        reason = check_pair(ti.get("old_string", ""), ti.get("new_string", ""), fmt)
        if reason:
            deny(reason)
    elif tool == "MultiEdit":
        for e in ti.get("edits", []) or []:
            reason = check_pair(e.get("old_string", ""), e.get("new_string", ""), fmt)
            if reason:
                deny(reason)

    allow()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Never wedge a session on an internal error.
        sys.exit(0)
