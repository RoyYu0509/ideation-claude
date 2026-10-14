#!/usr/bin/env bash
# bin/verify_panel.sh — RC-2 proof-of-work gate: PROVE a real adversarial review panel ran THIS round.
# A monolithic L1 that only NARRATES a review (P2: zero artifacts; P3: a lone report file) must NOT be
# able to reach the B3 exit gate. L0 calls this AFTER B2 returns, BEFORE B3; a non-zero exit = fail loud.
#
# RC-2b (proof-of-READ): proof-of-work alone is not enough — a reviewer can emit a structurally-valid
# verdict WITHOUT ever reading the paper (the Reviewer-3 0-tool-use hallucination: findings with every
# quote/location null). So the gate ALSO requires that any reviewer raising a reject/major finding anchors
# at least one of its findings to the paper with a VERBATIM quote. A serious charge cites the text it
# attacks; a 0-read reviewer cannot. This catches what proof-of-work (persona count) cannot.
#
# Usage:  bin/verify_panel.sh <workspace> <macro_round> [min_personas]
#   Passes (exit 0) iff, for <macro_round>:
#     (1) <ws>/paper/review-verdicts.md exists and parses as JSON, AND
#    (1b) when the file carries a `round` field (output-contract Verdicts row), it EQUALS <macro_round> —
#         a mismatch means the gate is reading a STALE round's artifact (freshness, dossier-12 D3); a
#         missing field passes (pre-round-field runs stay valid), AND
#     (2) it carries a panel[] with >= min_personas DISTINCT personas AND an `ac` synthesis, AND
#    (2b) in that panel, every reviewer that raised a reject/major finding quotes the paper at least once, AND
#     (3) <ws>/paper/review-report.md exists and contains an "Overall risk:" line.
#   Otherwise prints "ERROR verify_panel: ..." and exits 2.
# min_personas defaults to 2 — the review protocol's INDEPENDENCE FLOOR (review-protocol.md §2
# non-negotiable 4: "At least TWO independent cold reads ... There is no config knob for this").
# Panel width ABOVE the floor is the REVIEW OWNER's per-paper call, so the oracle checks only the
# floor. The floor is a protocol INVARIANT baked in here on purpose — there is no config key for it
# (review.reviewer_panel.count was deleted with the review-protocol redesign; dev/review-protocol-design.md D1).
set -euo pipefail

WS="${1:-}"; ROUND="${2:-}"; MIN_PERSONAS="${3:-2}"
[ -n "$WS" ]    || { echo "ERROR verify_panel: need <workspace> argument"; exit 2; }
[ -n "$ROUND" ] || { echo "ERROR verify_panel: need <macro_round> argument"; exit 2; }
[ -d "$WS" ]    || { echo "ERROR verify_panel: workspace not found: $WS"; exit 2; }

WS="$WS" ROUND="$ROUND" MIN_PERSONAS="$MIN_PERSONAS" python3 - <<'PY'
import os, sys, json, re

ws = os.environ["WS"]; rnd = os.environ["ROUND"]; minp = int(os.environ["MIN_PERSONAS"])
def fail(m): print("ERROR verify_panel: " + m); sys.exit(2)

# (1) the ONE flat {round, panel, ac} serialization the REVIEW OWNER writes
#     (spec/review/output-contract.md "Verdicts" row) — a single file, not a per-round glob.
f = os.path.join(ws, "paper", "review-verdicts.md")
if not os.path.exists(f):
    fail("no review-verdicts.md at %s — the B2 panel left no artifact this round "
         "(a narrated review with no real panel; cf. RC-2 P2/P3)" % f)
try:
    obj = json.loads(open(f).read().strip())
except Exception as e:
    fail("review-verdicts.md is not parseable JSON (%s) — not proof a real panel ran" % e)

# (1b) ROUND FRESHNESS (dossier-12 D3): when the artifact stamps its round, it must be THIS round.
if "round" in obj:
    try:
        fresh = int(obj["round"]) == int(rnd)
    except Exception:
        fresh = False   # a present-but-garbled round field is fail-closed, not ignored
    if not fresh:
        fail("review-verdicts.md carries round=%r but the gate is verifying round %s — a STALE round's "
             "artifact must not prove THIS round's panel" % (obj.get("round"), rnd))

# (2) the file proves a real panel: panel[] with >= minp distinct personas + the `ac` synthesis
#     (exact top-level key per the output contract; the review.js-era acFinal/overall_risk aliases are gone).
panel = obj.get("panel")
if not isinstance(panel, list):
    panel = []
personas = set()
for p in panel:
    if isinstance(p, dict):
        nm = p.get("persona") or p.get("role") or p.get("reviewer")
        if nm:
            personas.add(str(nm).strip().lower())
best, best_panel = len(personas), panel
if best < minp:
    fail("review-verdicts.md has only %d distinct panel personas (need >= %d) — panel not proven "
         "to have really run this round" % (best, minp))
if not obj.get("ac"):
    fail("review-verdicts.md carries no Area-Chair synthesis under the top-level `ac` key "
         "(output-contract Verdicts row pins that exact key)")

# (2b) GROUNDING FLOOR (proof-of-READ): a reviewer that never read the paper produces high-severity
# findings anchored to nothing (all quote/location null). Any reviewer that raised a reject/major finding
# MUST quote the paper at least once. Structural floor (quote PRESENT), NOT a content oracle: the quote is
# deliberately NOT matched against the .tex — a reviewer reading the typeset PDF quotes rendered text that
# would not byte-match LaTeX source (math/macros), which would false-FAIL a genuine read. The hard-to-forge
# part is committing a verbatim string at all, on top of the reviewer prompt's mandatory read gate.
def serious(sev):
    return str(sev or "").strip().lower() in ("reject", "major", "major_revision")
def nonempty(x):
    return bool(str(x or "").strip())
ungrounded = []
for p in best_panel:
    if not isinstance(p, dict):
        continue
    findings = p.get("findings")
    if not isinstance(findings, list) or not findings:
        continue                                   # no findings -> nothing to anchor (a clean read is exempt)
    if not any(isinstance(fd, dict) and serious(fd.get("severity") or fd.get("sev")) for fd in findings):
        continue                                   # only minor findings -> low-stakes, exempt
    if not any(isinstance(fd, dict) and nonempty(fd.get("quote")) for fd in findings):
        ungrounded.append(str(p.get("persona") or p.get("role") or p.get("reviewer") or "?"))
if ungrounded:
    fail("reviewer(s) %s raised reject/major findings but quoted NOTHING from the paper (no finding "
         "carries a verbatim quote) — the signature of a verdict written without reading it (cf. the "
         "0-tool-use hallucination). A real adversarial read cites the text it attacks." % ", ".join(ungrounded))

# (3) AC digest exists with an overall_risk verdict. The report's form is the output contract's
# (spec/review/output-contract.md); accept both a raw-JSON `"overall_risk": "..."` key and a
# human-readable "Overall risk:" line so a renderer change can't false-FAIL the gate.
rep = os.path.join(ws, "paper", "review-report.md")
if not os.path.exists(rep):
    fail("review-report.md missing at %s" % rep)
if not re.search(r'(?im)"?overall[ _]risk"?\s*[:：]', open(rep, errors="ignore").read()):
    fail("review-report.md has no 'overall_risk' field/line — not a real AC digest")

print("OK verify_panel: round %s — %d distinct personas, AC present, report OK%s"
      % (rnd, best, " (round-stamped)" if "round" in obj else " (no round stamp — pre-D3 artifact)"))
PY
