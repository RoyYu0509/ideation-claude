#!/usr/bin/env bash
# bin/audit_artifact_dispose.sh — the deterministic ENACTMENT half of the in-round audit-artifact integrity gate
# (research.js calls this; the mechanical git/manifest work lives HERE, not in the thin orchestration spec).
# Enacts a disposition of a gate change, reading the round's sidecar <ws>/.round-<round>.audit-artifact.json
# (the `mutated` list L0 wrote — entries carry `first_sight: true|false`):
#   revert -> for a true MUTATION (was_commit set): git-checkout the changed gate/criterion back to its LOCKED
#             commit (the producer must then face the real FAIL, not the gate). For a FIRST-SIGHT finding
#             (was_commit is null — the artifact's very first content was ungrounded, nothing to check out TO):
#             UN-LOCK it in the manifest (clear locked_sha256/locked_at_commit/locked_at, so the NEXT edit is
#             reviewed fresh as a new first-sight event) and append a durable note to <ws>/RESEARCH_LOG.md — the
#             producer's own documented resume substrate ("READ first" per experiment-protocol.md §1) — naming
#             the path + why, so the next turn actually sees it instead of the fix silently depending on the
#             producer noticing an unlocked manifest entry on its own.
#             Used by the owner's "Strip the flagged condition".
#   accept -> re-lock the manifest to the new shas at the current HEAD (the change is blessed: either the owner's
#             "Accept the change", or an independent auditor verdict of `legitimate`). Works unchanged for
#             first-sight entries too (re-locks at the content already silently locked moments earlier).
#
# Usage: bin/audit_artifact_dispose.sh <workspace> <revert|accept> <round>
#   exit 0 = enacted; exit 2 = bad args.
set -euo pipefail
WS="${1:-}"; ACT="${2:-}"; RND="${3:-}"
[ -n "$WS" ] && [ -n "$ACT" ] && [ -n "$RND" ] || { echo "ERROR audit_artifact_dispose: need <ws> <revert|accept> <round>" >&2; exit 2; }

WS="$WS" ACT="$ACT" RND="$RND" python3 - <<'PY'
import os, json, subprocess, datetime
ws  = os.environ["WS"]; act = os.environ["ACT"]; rnd = os.environ["RND"]
code = os.path.join(ws, "code")
sc = os.path.join(ws, ".round-%s.audit-artifact.json" % rnd)
try:
    muts = (json.load(open(sc)).get("mutated") or []) if os.path.isfile(sc) else []
except Exception:
    muts = []

if act == "revert":
    man = os.path.join(ws, "AUDIT-ARTIFACTS.locked.json")
    try: m = json.load(open(man))
    except Exception: m = None
    by_path = {a.get("path"): a for a in m["artifacts"]} if m and isinstance(m.get("artifacts"), list) else {}
    log_lines = []
    manifest_dirty = False
    for mm in muts:
        if not mm.get("path"): continue
        if mm.get("was_commit"):                      # true mutation -> checkout the LOCKED (pre-change) content
            subprocess.call(["git", "-C", code, "checkout", mm["was_commit"], "--", mm["path"]], stderr=subprocess.DEVNULL)
        else:                                          # first-sight -> nothing to check out TO; UNLOCK for a fresh review
            a = by_path.get(mm["path"])
            if a is not None:
                a.pop("locked_sha256", None); a.pop("locked_at_commit", None); a.pop("locked_at", None)
                manifest_dirty = True
            log_lines.append(
                "- `%s` (role=%s): owner disposition = STRIP REQUIRED. The independent auditor found this "
                "artifact's FIRST content resting its verdict on a condition with no textual anchor in "
                "HANDOFF.md (declared criteria: \"%s\"). Un-locked in AUDIT-ARTIFACTS.locked.json — remove the "
                "flagged condition from the gating logic, recompute, and re-register (experiment-protocol.md §4) "
                "before this experiment's verdict is trusted downstream." % (mm["path"], mm.get("role"), mm.get("criteria_summary")))
    if manifest_dirty:
        json.dump(m, open(man, "w"), indent=2)
    if log_lines:
        note = ("\n## AUDIT-ARTIFACT INTEGRITY — owner disposition (round %s)\n" % rnd) + "\n".join(log_lines) + "\n"
        with open(os.path.join(ws, "RESEARCH_LOG.md"), "a") as f:
            f.write(note)
elif act == "accept":
    man = os.path.join(ws, "AUDIT-ARTIFACTS.locked.json")
    try: m = json.load(open(man))
    except Exception: m = None
    if m and isinstance(m.get("artifacts"), list):
        try: head = subprocess.check_output(["git", "-C", code, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip() or None
        except Exception: head = None
        by = {mm.get("path"): mm for mm in muts}
        for a in m["artifacts"]:
            mm = by.get(a.get("path"))
            if mm:
                a["locked_sha256"] = mm.get("now_sha"); a["locked_at_commit"] = head
                a["locked_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        json.dump(m, open(man, "w"), indent=2)
PY
