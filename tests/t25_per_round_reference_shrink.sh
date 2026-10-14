#!/usr/bin/env bash
# T25 — progressive-disclosure goal injection (Doc A §3.2/§6.4, Doc C §5.2 #6). Static check that every loop /
# finishing goal-builder injects the PD pointer (so a worker loads ONLY the open concerns' references), and that
# the canonical PD protocol section is present in the phase specs. The behavioral "round-2 names fewer
# references than round-1" test is the live item NEXT-REVIEW C10.
# Run: bash tests/t25_per_round_reference_shrink.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; SPEC="$ROOT/spec/research.js"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

chk "pdPointer helper defined"                           "grep -qF 'function pdPointer(' '$SPEC'"
chk "PD pointer injected into the fan-out goal-builders"  "[ \$(grep -c 'pdPointer(' '$SPEC') -ge 2 ]"  # def + review (spec re-aim: the figures/writing goal-builders retired with the writing engine; experiment is a leaf with a completeness ledger — no concern-PD)
# the in-loop science-record rubric is spec/spawn-prompts/DOSSIER.md (writing-redesign: replaces DRAFT-CONTENT.md);
# the FROZEN-snapshot discipline lives there + dossierGoal POINTS to it DIRECTLY (no config indirection).
chk "dossier maintainer reads the frozen round concern snapshot" "grep -qF 'FROZEN' '$ROOT/spec/spawn-prompts/DOSSIER.md' && grep -qF 'punch-list' '$ROOT/spec/spawn-prompts/DOSSIER.md'"
chk "dossierGoal points to the extracted DOSSIER.md rubric" "grep -qF 'spec/spawn-prompts/DOSSIER.md' '$SPEC'"
# the verifier's resident-sensor PD block is now IN the extracted rubric (spec/spawn-prompts/VERIFY-PROTOCOL.md);
# verifierGoal stays thin (injects <CONCERN_MAP> + appends LEDGER_CONTAINER).
chk "verifier (resident sensor) reads frozen snapshot"   "grep -qF 'PROGRESSIVE DISCLOSURE (sensor role' '$ROOT/spec/spawn-prompts/VERIFY-PROTOCOL.md'"
chk "goal pointer names the concern-reference map"       "grep -qF 'CONCERN_MAP' '$SPEC'"
# the canonical PD protocol section reached every phase spec (inserted by the step-5 workflow).
# review.js is EXCLUDED since 39874f9: it is diagnose-only — its per-round reference disclosure is driven by
# the loop + the resident verifier (research.js), not a PROGRESSIVE DISCLOSURE section in review.js itself.
# seed→HANDOFF authoring is now the root-plugin handoff-authoring skill (not under plugins/) — its SKILL.md carries the PD section
chk "PD protocol section in handoff-authoring SKILL.md"  "grep -qF 'PROGRESSIVE DISCLOSURE' '$ROOT/skills/handoff-authoring/SKILL.md'"
# rewrite.js archived 2026-08-30 (inactive/) with the writing back end; the two STANDALONE specs remain.
for f in paper-polish-ar/spec/polish.js paper-polish-ar/spec/polish-figures.js; do
  chk "PD protocol section in ${f##*/}"                  "grep -qF 'PROGRESSIVE DISCLOSURE' '$ROOT/plugins/$f'"
done
chk "experiment-protocol is a NON-concern-gated completeness-ledger leaf" "grep -qiF 'completeness ledger' '$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md' && grep -qiF 'NOT concern-gated' '$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md'"

echo "----"; echo "t25_per_round_reference_shrink: $pass passed, $fail failed"; [ "$fail" = 0 ]
