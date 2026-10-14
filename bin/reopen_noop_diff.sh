#!/usr/bin/env bash
# bin/reopen_noop_diff.sh — the deterministic NO-OP-REOPEN backstop for F2 (the "review→fix→review spin" bug).
# Mirrors the audit_artifact_diff.sh / audit_artifact_dispose.sh paired idiom: the mechanical SHA-set work
# lives HERE, not in the thin orchestration spec (research.js). It snapshots, then diffs, the on-disk set of
# <ws>/EXPERIMENTS/*/result.md so the loop can REFUSE to re-mark EXPERIMENTS_DONE done when a review-driven
# re-open produced NO new experiment result (a re-open masquerading as progress → the spin).
#
# WHY a SET-OF-result.md SHA (not a git diff): EXPERIMENTS_DONE is re-opened by clearing the ledger record,
# not by a git revert, so the working tree of <ws>/code is unchanged at re-open. The thing that MUST change
# for genuine progress is the durable per-segment resume marker the worker writes — EXPERIMENTS/<id>/result.md
# (experiment-protocol.md:119: a segment with no result.md is unfinished, re-entered). So we fingerprint the
# multiset {(<id>, sha256(result.md))} for every segment that HAS a result.md. A scaffolded-but-unfilled
# segment (`.pending`, no result.md) contributes nothing — exactly the "first-class unfinished segment" F2
# mints; the worker MUST fill it for the fingerprint to move.
#
# Subcommands:
#   snapshot <ws> <round>  — write <ws>/.reopen-snapshot-r<round>.json = the pre-open result.md SHA set.
#                            Called from generateHandoff(state, transition=true) at re-open time (CONTINUE).
#   check    <ws> <round>  — compare the CURRENT result.md SHA set to that snapshot. Prints one line:
#                            "NOOP"     => byte-identical to the snapshot (re-open produced NO new result),
#                            "PROGRESS" => the set changed (a result.md added/removed/changed) OR no snapshot
#                                          exists for this round (nothing was re-opened ⇒ never a no-op).
#                            Called in runExperiment just BEFORE the EXPERIMENTS_DONE done re-mark.
# Exit: 0 = ran (stdout is the result); 2 = bad args. A detector never blocks; the spec reads the line.
set -euo pipefail

CMD="${1:-}"; WS="${2:-}"; RND="${3:-}"
[ -n "$CMD" ] && [ -n "$WS" ] && [ -n "$RND" ] || { echo "ERROR reopen_noop_diff: usage: $0 <snapshot|check> <ws> <round>" >&2; exit 2; }
SNAP="$WS/.reopen-snapshot-r$RND.json"

# Emit the canonical fingerprint of the CURRENT on-disk result.md set as a stable, sorted JSON object
# { "<segId>": "<sha256>", ... }. Sorted by segId so the JSON text is order-independent and byte-comparable.
WS="$WS" python3 - "$CMD" "$SNAP" <<'PY'
import os, sys, json, hashlib, glob
ws   = os.environ["WS"]; cmd = sys.argv[1]; snap = sys.argv[2]
exp  = os.path.join(ws, "EXPERIMENTS")

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def fingerprint():
    out = {}
    for r in sorted(glob.glob(os.path.join(exp, "*", "result.md"))):
        seg = os.path.basename(os.path.dirname(r))
        try: out[seg] = sha256(r)
        except Exception: continue            # unreadable mid-write => skip (defensive; never crash)
    return json.dumps(out, sort_keys=True, separators=(",", ":"))

cur = fingerprint()
if cmd == "snapshot":
    open(snap, "w").write(cur)
    # quiet: the spec only needs the side-effect file
elif cmd == "check":
    if not os.path.isfile(snap):
        print("PROGRESS"); sys.exit(0)        # no snapshot for this round => nothing was re-opened => not a no-op
    try: was = open(snap).read().strip()
    except Exception: print("PROGRESS"); sys.exit(0)
    print("NOOP" if cur.strip() == was else "PROGRESS")
else:
    sys.stderr.write("ERROR reopen_noop_diff: unknown subcommand %s\n" % cmd); sys.exit(2)
PY
