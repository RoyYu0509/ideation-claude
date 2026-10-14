#!/usr/bin/env bash
# t12 — bin/scan_orphan_stops.sh derives the count of stop-shaped markers an L1 wrote into its OWN logs but
# never returned in escalations[] (surfacing remediation D). Regression for the first run's smoking gun:
# runs/incommensurate-truncation-residual-adaptive/FAILURES.md wrote "Escalation required: K2 falsified ...
# escalations=[...]" while the gate received new_handoff_items:0. Run standalone.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
chk(){ if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
S="$ROOT/bin/scan_orphan_stops.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Case 1: clean workspace (empty living logs) -> COUNT 0
ws="$TMP/clean"; mkdir -p "$ws"; : > "$ws/FAILURES.md"; : > "$ws/RESEARCH_LOG.md"; : > "$ws/DECISIONS.md"
chk "clean logs -> COUNT 0" "[ \"\$(bash '$S' '$ws' | head -1)\" = 'COUNT 0' ]"

# Case 2: the smoking gun — an orphaned escalation written into FAILURES.md -> COUNT > 0
ws2="$TMP/orphan"; mkdir -p "$ws2"
printf 'K2 FAILED: DoF reduction ratio < 10x. Observed result: DoF ratio = 1.0x\n\nEscalation required: K2 falsified. This must be reported in the return envelope as escalations=["K2 falsified: DoF ratio=1.0x"].\n' > "$ws2/FAILURES.md"
chk "orphaned 'Escalation required' + 'escalations=[' -> COUNT >= 1" \
  "n=\$(bash '$S' '$ws2' | head -1 | sed 's/COUNT //'); [ \"\$n\" -ge 1 ]"

# Case 3: a STOP report on disk with no escalation -> counted as orphan evidence
ws3="$TMP/stopfile"; mkdir -p "$ws3/REPORTS"; : > "$ws3/FAILURES.md"
printf '# STOP report\nTrigger: S1\n' > "$ws3/REPORTS/STOP-2026-06-13T12-00-00Z.md"
chk "STOP-*.md on disk -> COUNT >= 1" \
  "n=\$(bash '$S' '$ws3' | head -1 | sed 's/COUNT //'); [ \"\$n\" -ge 1 ]"

# Case 4: NO false positive on a correctly-handled, RESOLVED dead end
ws4="$TMP/resolved"; mkdir -p "$ws4"
printf 'Tried the linear baseline; it underperformed. Abandoned with evidence (resolved). Recorded as a clean peripheral negative outcome in the ablation section.\n' > "$ws4/FAILURES.md"
: > "$ws4/RESEARCH_LOG.md"
chk "resolved dead end (no orphan phrasing) -> COUNT 0" \
  "[ \"\$(bash '$S' '$ws4' | head -1)\" = 'COUNT 0' ]"

# Case 5: monotone — adding a new orphan marker raises COUNT (the 'surface on increase' contract)
printf 'Escalation required: another buried stop.\n' >> "$ws2/FAILURES.md"
chk "appending a new orphan marker raises COUNT (monotone)" \
  "n=\$(bash '$S' '$ws2' | head -1 | sed 's/COUNT //'); [ \"\$n\" -ge 2 ]"

# Case 6: missing workspace files don't crash; exit 0, COUNT 0
ws6="$TMP/empty"; mkdir -p "$ws6"
chk "no log files at all -> exit 0, COUNT 0" \
  "out=\$(bash '$S' '$ws6'); [ \$? -eq 0 ] && [ \"\$(echo \"\$out\" | head -1)\" = 'COUNT 0' ]"

echo "----"; echo "t12_scan_orphan_stops: $pass passed, $fail failed"; [ "$fail" = 0 ]
