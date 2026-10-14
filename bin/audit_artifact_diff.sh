#!/usr/bin/env bash
# bin/audit_artifact_diff.sh — the deterministic DETECTION half of the in-round audit-artifact integrity gate
# (research.js::runAuditArtifactGate calls this; the mechanical SHA/lock work lives HERE, not in the thin
# orchestration spec). Reads <ws>/AUDIT-ARTIFACTS.locked.json — the producer's DECLARATION (path code-relative,
# role, criteria_summary). For each registered audit-artifact (a gate/sanity/criterion script):
#   FIRST SIGHT (no L0 `locked_at` yet) -> L0 STAMPS the lock (sha256 + the code/ HEAD commit + a timestamp) and
#     writes it back. The producer NEVER writes the sha; the first-sight test is keyed on L0's OWN `locked_at`,
#     so a producer that pre-writes locked_sha256 cannot bypass the lock. role in {criterion,gate} -> ALSO queued
#     for review (see below) — a "sanity"-role artifact (REUSE library code, not a verdict-gating script) locks
#     silently, no review. [2026-07-18 gap-close] first sight used to be a pure no-op: nothing ever checked
#     whether a producer's OWN gating logic, as authored, is actually grounded in the frozen HANDOFF K/E-hypothesis
#     falsify/support text. A script can silently wire in an extra condition from its FIRST commit (never touched
#     again -> sha never mutates -> the old mutation-only trigger never fires) and gate a verdict on it forever.
#     Real incident: `code/exp/E3_conformal_stopping.py`'s `feasible = frac_stopped >= FRAC_STOPPED_FLOOR` ANDed
#     into `restored` (the top-level verdict) from the artifact's very first commit, self-labeled in its own
#     comment "self-added feasibility threshold (report-labeled)" — i.e. the author KNEW it was ungrounded and
#     labeled it report-only, yet still gated the verdict on it. No mutation ever happened (nothing to diff
#     against), so the old code silently locked it and it drove a bogus S1 escalation. Same review, new trigger.
#   ALREADY LOCKED + content changed -> a MUTATION (unchanged behavior).
# Prints the review-worthy events as a JSON array to stdout ([] if none); research.js spawns the INDEPENDENT
# auditor only when this is non-empty. The JUDGMENT (legitimate vs goalpost-move / self_added_anchor) is NOT
# here — it lives in the asset rubric (spec/spawn-prompts/AUDIT-ARTIFACT-INTEGRITY.md) + the auditor leaf.
#
# Usage: bin/audit_artifact_diff.sh <workspace>
#   stdout = JSON array [ {path, role, criteria_summary, was_sha, now_sha, was_commit, first_sight} ]
#            (first_sight=true entries have was_sha=null, was_commit=null — nothing to diff against; the auditor
#            compares the artifact directly to HANDOFF.md instead)  ([] = nothing to review)
#   exit 0 = ran (stdout is the result); exit 2 = bad args.
set -euo pipefail
WS="${1:-}"
[ -n "$WS" ] || { echo "ERROR audit_artifact_diff: need <workspace>" >&2; exit 2; }
[ -f "$WS/AUDIT-ARTIFACTS.locked.json" ] || { echo "[]"; exit 0; }   # no declaration => nothing to guard

WS="$WS" python3 - <<'PY'
import os, sys, json, hashlib, subprocess, datetime
ws  = os.environ["WS"]
man = os.path.join(ws, "AUDIT-ARTIFACTS.locked.json")
code = os.path.join(ws, "code")
try:
    m = json.load(open(man))
except Exception:
    print("[]"); sys.exit(0)                        # unparseable => defensive no-op (the producer rewrites it)
arts = m.get("artifacts") if isinstance(m.get("artifacts"), list) else []

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()
def head():
    try: return subprocess.check_output(["git","-C",code,"rev-parse","HEAD"], stderr=subprocess.DEVNULL).decode().strip() or None
    except Exception: return None

muts, dirty = [], False
for a in arts:
    if not isinstance(a, dict) or not a.get("path"): continue
    f = os.path.join(code, a["path"])
    if not os.path.isfile(f): continue              # declared-but-unwritten file is not a mutation
    try: sha = sha256(f)
    except Exception: continue
    if not a.get("locked_at"):                      # FIRST SIGHT -> L0 stamps the lock (keyed on L0's own locked_at)
        a["locked_sha256"] = sha
        a["locked_at_commit"] = head()
        a["locked_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        dirty = True
        if a.get("role") in ("criterion", "gate"):   # a verdict-gating artifact's FIRST content is UNREVIEWED —
            muts.append({"path": a["path"], "role": a.get("role"), "criteria_summary": a.get("criteria_summary"),
                         "was_sha": None, "now_sha": sha, "was_commit": None, "first_sight": True})
        continue
    if sha != a.get("locked_sha256"):
        muts.append({"path": a["path"], "role": a.get("role"), "criteria_summary": a.get("criteria_summary"),
                     "was_sha": a.get("locked_sha256"), "now_sha": sha, "was_commit": a.get("locked_at_commit"),
                     "first_sight": False})
if dirty:
    json.dump(m, open(man, "w"), indent=2)
print(json.dumps(muts))
PY
