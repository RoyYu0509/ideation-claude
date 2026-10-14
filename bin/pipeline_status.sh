#!/usr/bin/env bash
# bin/pipeline_status.sh — the deterministic pipeline-PROGRESS oracle + ship-gate (RC-10 / option A).
#
# WHY THIS EXISTS. spec/research.js is a constitution an L0 agent REPRODUCES with harness tools, not executed
# JS. A real run (neural-operator-aposteriori-reliability, 2026-06-20) advanced state.stage to "ship" while
# skipping the env-stage `git init` AND the post-loop terminal stages. `state.stage` is exactly the pointer L0
# can skip past, so status must be
# read from GROUND TRUTH, not from the self-report.
#
# OPTION A: the authoritative status is the L0-owned LEDGER milestone-state.json, written at each transition
# with PROVENANCE — the experiment milestones already do this (milestones[ms] = {completed_at, paper_commit});
# recordStage() now does the same for the pipeline stages (stages[name] = {completed_at, paper_commit, ...}).
# This oracle reads that ledger and VERIFIES each finishing stage's paper_commit RESOLVES to a real commit in
# ws/paper (a fabricated/empty sha fails), plus git provenance. The canonical definition of every state +
# its evidence lives in spec/STATUS-MODEL.md — keep this script and that doc in sync.
#
# IT IS BOTH: (a) the L0 progress tool ("which step are we at, what's left before ship"), surfaced every turn;
# and (b) the SHIP-GATE oracle — ship() refuses unless every config-enabled finishing stage has a ledger entry
# with a resolvable commit (= it ran). A stage that ran-and-only-surfaced STILL has an entry (do-no-harm
# ships); only a TOTALLY ABSENT entry (never ran) blocks. The backbone phases (handoff..review) are shown for
# the progress view but are NOT part of the ship gate (the gate is git + the four finishing stages).
#
# Usage:  bin/pipeline_status.sh <workspace> [--require <csv>]
#   --require defaults to "verify_final,spec_freeze" — BOTH terminal stages are mandatory (spec re-aim
#   2026-08-30: the six writing-engine stages were retired with the engine, and spec_freeze has no toggle).
# Output: "<phase> <PRESENT|ABSENT|SKIPPED> <detail>" per phase, then "CURRENT <phase>", "SHIP_READY <yes|no>",
#   and (only if no) "MISSING <csv>".
# Exit:   0 = ship-ready · 1 = NOT ship-ready · 2 = error (bad args / missing workspace).
set -u

WS="${1:-}"
[ -n "$WS" ] || { echo "ERROR pipeline_status: need <workspace>"; exit 2; }
[ -d "$WS" ] || { echo "ERROR pipeline_status: workspace not found: $WS"; exit 2; }
shift || true

REQUIRE="verify_final,spec_freeze"
while [ $# -gt 0 ]; do
  case "$1" in
    --require)   REQUIRE="${2:-}"; shift 2 ;;
    --require=*) REQUIRE="${1#--require=}"; shift ;;
    *)           shift ;;
  esac
done

WS="$WS" REQUIRE="$REQUIRE" python3 - <<'PY'
import os, sys, json, subprocess

ws      = os.environ["WS"]
require = [s for s in os.environ["REQUIRE"].split(",") if s]
paper   = os.path.join(ws, "paper")

def git_ok(d):                       # a real repo with >=1 commit
    return subprocess.run(["git", "-C", d, "rev-parse", "HEAD"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
def commit_resolves(d, sha):         # the recorded sha is a real commit object in the repo (anti-forgery)
    if not sha:
        return False
    return subprocess.run(["git", "-C", d, "cat-file", "-e", str(sha) + "^{commit}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
def nonempty(p):
    try:    return os.path.getsize(p) > 0
    except OSError: return False
def has_round_reviews():
    d = os.path.join(ws, "REVIEW")
    try:    return any(f.startswith("round") and f.endswith("_reviews.md") for f in os.listdir(d))
    except OSError: return False

ship_ready = True
missing    = []
current    = [None]
def mark(p):
    if current[0] is None: current[0] = p
def need(stage):
    return stage in require

# ── git provenance: every paper folder is a repo from the START ──────────────────────────────────────────
gp = all(git_ok(os.path.join(ws, s)) for s in ("", "paper", "code"))
if gp:
    print("git PRESENT (ws + paper + code repos, each >=1 commit)")
else:
    bad = " ".join(("%s(no-git)" % (s or "/root")) for s in ("", "paper", "code") if not git_ok(os.path.join(ws, s)))
    print("git ABSENT — " + bad + " (env-stage git init was skipped; provenance is unrecoverable for this run)")
    ship_ready = False; missing.append("git")

# ── load the authoritative ledger ────────────────────────────────────────────────────────────────────────
try:    ledger = json.load(open(os.path.join(ws, "milestone-state.json")))
except Exception: ledger = {}
stages = ledger.get("stages") or {}
mids   = ledger.get("milestones") or {}

# ── backbone phases (progress view only — NOT part of the ship gate) ─────────────────────────────────────
# seed_to_handoff
if ("seed_to_handoff" in stages) or nonempty(os.path.join(ws, "HANDOFF.md")):
    print("seed_to_handoff PRESENT (HANDOFF.md)")
else:
    print("seed_to_handoff ABSENT (no HANDOFF.md)"); mark("seed_to_handoff")
# env_ready
if ("ENV_READY" in mids) or os.path.isdir(os.path.join(ws, "EXPERIMENTS", "ENV_READY")) or nonempty(os.path.join(ws, "EXPERIMENTS", "results_master.json")):
    print("env_ready PRESENT")
else:
    print("env_ready ABSENT"); mark("env_ready")
# experiments
if ("RESULTS_ON_DISK" in mids) or nonempty(os.path.join(ws, "EXPERIMENTS", "results_master.json")):
    print("experiments PRESENT (results_master.json)")
else:
    print("experiments ABSENT"); mark("experiments")
# spec versions (the loop's product: one SPEC-v<N>.md per (re-)author + the mechanical ledger)
specd = os.path.join(ws, "SPEC")
try:    nver = len([f for f in os.listdir(specd) if f.startswith("SPEC-v") and f.endswith(".md")])
except OSError: nver = 0
if nver:
    print("spec_versions PRESENT (%d version(s) in SPEC/)" % nver)
else:
    print("spec_versions ABSENT"); mark("spec_versions")
# review
if has_round_reviews():
    print("review PRESENT")
else:
    print("review ABSENT"); mark("review")

# ── finishing chain: ledger-derived + provenance-checked (THIS is the ship gate) ─────────────────────────
def finishing(stage):
    global ship_ready
    e  = stages.get(stage)
    ok = bool(e) and commit_resolves(paper, e.get("paper_commit"))
    # §4c AMBITION reconciliation (verify_final only): a recorded ambition_reconciled:false means the claim
    # over-reaches delivery — block ship even though the stage ran + the commit resolves. Absent field ⇒
    # do-no-harm (legacy runs predate the §4c contract). Resolved by the research-rescue (retain) or owner residual.
    if stage == "verify_final" and need(stage) and e is not None and e.get("ambition_reconciled") is False:
        print("verify_final ABSENT (ran, but §4c AMBITION NOT reconciled: claim over-reaches delivery — rescue/owner must resolve)")
        mark(stage); ship_ready = False; missing.append("verify_final(ambition)")
        return
    if ok:
        sha   = str(e.get("paper_commit", ""))[:10]
        extra = " surfaced=%s" % e.get("surfaced") if e.get("surfaced") else ""
        print("%s PRESENT (ledger @%s%s)" % (stage, sha, extra))
    elif need(stage):
        why = "no ledger entry" if not e else "paper_commit does not resolve in ws/paper"
        print("%s ABSENT (%s — stage did NOT run)" % (stage, why))
        mark(stage); ship_ready = False; missing.append(stage)
    else:
        print("%s SKIPPED (toggled off in config)" % stage)

# The terminal stages, both mandatory: verify_final (the independent science verify) then spec_freeze (the run's
# ONE deliverable, SPEC-FINAL.md). The finishing() helper still honours `require`, so a caller that narrows the
# set sees the excluded stage as SKIPPED rather than silently omitted.
for st in ("verify_final", "spec_freeze"):
    finishing(st)

# DELIVERABLE BELT: the ship gate trusts the ledger for "did it run", but the run's ONE deliverable must also
# BE THERE. A recorded spec_freeze with no SPEC-FINAL.md on disk is exactly the silent-collapse class this
# oracle exists to catch, so it blocks independently of the ledger entry.
if need("spec_freeze") and not nonempty(os.path.join(ws, "SPEC-FINAL.md")):
    print("deliverable ABSENT (SPEC-FINAL.md missing or empty — nothing to ship)")
    mark("spec_freeze"); ship_ready = False; missing.append("SPEC-FINAL.md")

# shipped
if ("ship" in stages) or nonempty(os.path.join(ws, "FINAL-REPORT.md")):
    print("shipped PRESENT (FINAL-REPORT.md)")
else:
    print("shipped ABSENT")

# ── verdict ──────────────────────────────────────────────────────────────────────────────────────────────
if current[0] is None: current[0] = "ship"
print("CURRENT " + current[0])
print("SHIP_READY " + ("yes" if ship_ready else "no"))
if not ship_ready: print("MISSING " + ",".join(missing))
sys.exit(0 if ship_ready else 1)
PY
