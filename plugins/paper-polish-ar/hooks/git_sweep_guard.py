#!/usr/bin/env python3
"""paper-polish — git-sweep guard (structural backstop for the freeze discipline).

PreToolUse hook for Bash. During a polish/figure finishing run the reviser must commit ONLY its own
named file (`git -C <dir> add -- <file>`); a `git add -A/-a/--all` (or `git commit -a/-am/--all`) in a
SHARED worktree would sweep unrelated files into the commit. This hook denies those sweep forms while a
polish/figure run is armed, replacing the repeated "never git add -A" prose in the specs.

Decision rules (mirrors check_fidelity.py's contract):

  1. No active run -> no-op. If the manifest ($CLAUDE_PROJECT_DIR/.polish/fidelity-manifest.json) is
     missing, allow everything (exit 0, no output).
  2. Only polish/figure modes are guarded. In review/consolidate/experiment mode the L0 orchestrator
     legitimately uses `git add -A` in its isolated workspace, so this hook is a NO-OP there — blocking
     it would fail-closed the whole pipeline. If mode is not in {polish, figure} -> allow.
  3. Non-Bash tool or empty command -> allow.
  4. A sweep form -> deny with an actionable reason. Sweep = add -A/-a/-u/--all/--update (ANY option
     position — flag insertion like `add -v -A` no longer bypasses), a bare `.`/`..` or trailing-slash
     dir pathspec (even after `--`), or commit -a/--all/--include anywhere in the OPTIONS. Detection is
     a shell-token parse (see command_sweeps below), so `-a` inside a commit MESSAGE is never matched,
     and the reviser's legitimate `add -- <files>` / `--patch` / `commit --allow-empty` / `--amend` /
     `-m` all pass.

Blocking uses the PreToolUse JSON form: permissionDecision "deny" + reason.
Any internal error fails open (exit 0) so the hook can never wedge a session.
"""

import json
import os
import re
import shlex
import sys


# ── Sweep detection: TOKEN-level parse (2026-07-06, dossier-12 D2). The old regexes required the sweep
# flag IMMEDIATELY after the subcommand, so `git add -v -A` / `git commit -m x -a` slipped through, and
# `git add .` / `-u/--update` / `dir/` were never covered at all. The parser below walks shell tokens:
#   * skips git GLOBAL opts (`-C <dir>` / `-c <kv>` / other leading `-*`) before the subcommand;
#   * add: DENIES a sweep option ANYWHERE (`-A/--all/-u/--update/--no-ignore-removal`, or any short
#     cluster containing A/u), a bare `.`/`..`, or a trailing-slash directory pathspec. The explicit
#     `git [-C dir] add -- <named files>` form stays WHITELISTED — but `--` does NOT launder `.`,
#     `..` or `dir/` pathspecs.
#   * commit: DENIES `-a/--all/--include` as an OPTION token anywhere, including inside a short
#     cluster (`-am`, `-av`); the ARGUMENT of `-m/-F/--message/--file/--fixup/--squash/-C/-c` is
#     skipped first, so `-a` inside a commit MESSAGE is never matched; tokens after `--` are paths.
# Unparseable commands (unbalanced quotes etc.) fall back to the old anchored regexes rather than
# allowing everything. Compound commands are split on unquoted `; && || | &` separators.
ADD_SWEEP_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)*add\s+(?:-A\b|-a\b|--all\b)")
COMMIT_SWEEP_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)*commit\s+(?:-a\b|-am\b|--all\b)")

_SEPARATORS = {";", "&&", "||", "|", "&", "(", ")"}
_GIT_GLOBAL_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_ADD_SWEEP_LONG = {"--all", "--update", "--no-ignore-removal"}
_COMMIT_ARG_OPTS = {"-m", "-F", "-C", "-c", "--message", "--file", "--fixup", "--squash", "--author", "--date"}


def _split_tokens(command):
    """Shell tokens with separators kept as their own tokens; None if unparseable."""
    try:
        lx = shlex.shlex(command, posix=True, punctuation_chars=True)
        lx.whitespace_split = True
        return list(lx)
    except ValueError:
        return None


def _git_invocations(tokens):
    """Yield the token list of each `git …` invocation inside a possibly-compound command."""
    i = 0
    while i < len(tokens):
        if tokens[i] == "git" or tokens[i].endswith("/git"):
            j = i + 1
            inv = []
            while j < len(tokens) and tokens[j] not in _SEPARATORS:
                inv.append(tokens[j]); j += 1
            yield inv
            i = j
        else:
            i += 1


def _subcommand_args(inv):
    """(subcommand, args-after-it) with git global options skipped; (None, []) if none found."""
    i = 0
    while i < len(inv):
        t = inv[i]
        if t in _GIT_GLOBAL_WITH_ARG:
            i += 2
        elif t.startswith("--git-dir=") or t.startswith("--work-tree=") or t.startswith("-"):
            i += 1
        else:
            return t, inv[i + 1:]
    return None, []


def _add_sweeps(args):
    seen_ddash = False
    for t in args:
        if t == "--":
            seen_ddash = True
            continue
        if not seen_ddash and t.startswith("-"):
            if t in _ADD_SWEEP_LONG:
                return True
            if re.fullmatch(r"-[a-zA-Z]+", t) and ("A" in t or "u" in t or t == "-a"):
                return True  # -A/-u anywhere in a short cluster (-vA, -au…); legacy bare -a kept denied
            continue
        # pathspec (before or after --): `--` never launders a sweep pathspec
        if t in (".", "..") or t.endswith("/"):
            return True
    return False


def _commit_sweeps(args):
    i = 0
    while i < len(args):
        t = args[i]
        if t == "--":
            return False  # everything after -- is paths
        if t in _COMMIT_ARG_OPTS:
            i += 2
            continue
        if t.startswith("--"):
            if t in ("--all", "--include"):
                return True
            i += 1
            continue
        if t.startswith("-") and len(t) > 1:
            if re.fullmatch(r"-[a-zA-Z]+", t) and "a" in t:
                return True  # -a and clusters like -am / -av
            i += 2 if t[-1] in "mFCc" else 1  # trailing arg-taking short opt consumes the next token
            continue
        i += 1
    return False


def command_sweeps(command):
    """True iff any git invocation in the command is a sweep form."""
    tokens = _split_tokens(command)
    if tokens is None:  # unparseable -> the old anchored regexes as a floor, never a free pass
        return bool(ADD_SWEEP_RE.search(command) or COMMIT_SWEEP_RE.search(command))
    for inv in _git_invocations(tokens):
        sub, args = _subcommand_args(inv)
        if sub == "add" and _add_sweeps(args):
            return True
        if sub == "commit" and _commit_sweeps(args):
            return True
    return False


DENY_REASON = (
    "git add -A/-a/-u/--all/--update/./dir/ (or git commit -a/--all) is blocked during a polish/figure "
    "run — commit ONLY your own named files: `git -C <dir> add -- <file>`. (Enforced while "
    ".polish/fidelity-manifest.json mode=polish|figure is armed.)"
)


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

    # Only polish/figure runs are guarded; L0's workspace add -A in the other modes is legitimate.
    if manifest.get("mode", "polish") not in ("polish", "figure"):
        allow()

    if payload.get("tool_name", "") != "Bash":
        allow()
    command = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not command.strip():
        allow()

    if command_sweeps(command):
        deny(DENY_REASON)

    allow()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Never wedge a session on an internal error.
        sys.exit(0)
