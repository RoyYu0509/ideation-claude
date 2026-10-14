#!/usr/bin/env bash
# bin/scan_orphan_stops.sh — surfacing remediation (D): make the log→envelope seam UN-BURYABLE.
#
# The first run's smoking gun (runs/incommensurate-truncation-residual-adaptive/FAILURES.md:42-44): a B1
# L1 wrote "Escalation required: K2 falsified ... report ... as escalations=[...]" INTO ITS OWN LOG, yet
# every loop-gate input carried new_handoff_items:0 and no STOP report ever reached the owner — the
# recognition died at the seam between the L1's log and the envelope. L0 trusts escalations[] on faith.
#
# This DERIVES, from disk, the count of stop-shaped markers the L1 wrote into its own append-only logs —
# the same RC-4 disk-derivation idiom (derive_gate_input.sh) applied to the experimenting interior. L0
# compares the count to what the owner has already acknowledged (state.orphan_ack_count) and SURFACES any
# INCREASE. Deliberately HIGH-PRECISION (an agent recognizing a stop and even formatting the escalation),
# so a RESOLVED dead end ("tried X, abandoned with evidence") does not trip it.
#
# Usage:  bin/scan_orphan_stops.sh <workspace>
# Output: line 1 = "COUNT <n>"; following lines = evidence ("<file>:<lineno>: <text>" + "STOP-REPORT: <path>").
# Exit:   ALWAYS 0 — a detector never blocks; L0 reads <n>, compares to the ack count, and decides.
set -u
WS="${1:?usage: scan_orphan_stops.sh <workspace>}"

# An agent that RECOGNIZED a stop and (often) pre-formatted the escalation it never returned. Narrow on
# purpose — these phrasings do not occur in a correctly-handled negative outcome that WAS reported. A bare
# "K<n> falsified" is deliberately NOT matched: under the S1/S2 OPERATIONAL-FIRST protocol a falsified
# PERIPHERAL criterion is auto-handled (recorded, never escalated), so it must not trip this net;
# a genuinely-buried S3/S9/Phase-0 stop still carries the explicit escalation language below.
PAT='escalation required|escalations *[:=] *\[|must be reported in the return envelope|REPORTS/STOP-'

files=()
for f in FAILURES.md RESEARCH_LOG.md DECISIONS.md; do
  [ -f "$WS/$f" ] && files+=("$WS/$f")
done

hits=""
[ "${#files[@]}" -gt 0 ] && hits="$(grep -nEi "$PAT" "${files[@]}" 2>/dev/null || true)"

# A STOP report on disk is itself orphan evidence: protocol §4.1 requires mirroring its essence into the
# escalation, so a STOP-*.md with no surfaced escalation is exactly the buried-stop case.
stopfiles="$(ls -1 "$WS"/REPORTS/STOP-*.md 2>/dev/null || true)"

n=0
[ -n "$hits" ]      && n=$(( n + $(printf '%s\n' "$hits"      | grep -c .) ))
[ -n "$stopfiles" ] && n=$(( n + $(printf '%s\n' "$stopfiles" | grep -c .) ))

echo "COUNT $n"
[ -n "$hits" ]      && printf '%s\n' "$hits"
[ -n "$stopfiles" ] && printf '%s\n' "$stopfiles" | sed 's#^#STOP-REPORT: #'
exit 0
