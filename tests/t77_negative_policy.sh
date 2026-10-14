#!/usr/bin/env bash
# T77 — the NEGATIVE-RESULT POLICY (2026-08-30 flip). The system used to license a rigorous,
# informative negative result as a legitimate deliverable in half a dozen places. Under the
# ArxivIdeator framing the loop optimizes a SPEC, and a negative that CONTRADICTS the spec's
# novelty claim means the DIRECTION is dead: abandon it, never report the refutation as the
# contribution. This test LOCKS that policy at every source that carries it, so a later session
# cannot "helpfully" reinstate the first-class-negative clause.
#
# NOT locked here (deliberately, and must stay untouched):
#   - the transient rule "a died run is NEVER a negative result" (orthogonal; t69 owns it)
#   - the terminal gate's three-way Abandon/Ship/Rescue card (the owner keeps an explicit
#     override path — removing Ship would make the reward-hack behaviour unobservable)
# Run: bash tests/t77_negative_policy.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1  --  $2"; fail=$((fail+1)); }
chk(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else no "$1" "$2"; fi }

VERIFY="$ROOT/spec/spawn-prompts/VERIFY-PROTOCOL.md"
REVIEWC="$ROOT/spec/spawn-prompts/REVIEW-L0-CONTRACT.md"
DOSSIER="$ROOT/spec/spawn-prompts/DOSSIER.md"
ATTACK="$ROOT/plugins/paper-polish-ar/spec/review/attack-classes.md"
EXPROT="$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md"
OPFIRST="$ROOT/plugins/experiment-lab-ar/spec/failure/operational-first.md"
HANDOFF="$ROOT/skills/handoff-authoring/SKILL.md"
RESCUE="$ROOT/skills/research-rescue/SKILL.md"
RPROT="$ROOT/assets/research-protocol.md"
SPEC="$ROOT/spec/research.js"

# ── (1) the retired licences are GONE from every live policy surface ────────────────────────
chk "no 'legitimate deliverable' licence in spec/ skills/ assets/" \
  "! grep -rqiF 'legitimate deliverable' '$ROOT/spec' '$ROOT/skills' '$ROOT/assets'"
chk "no 'Negative results are first-class' clause anywhere live" \
  "! grep -rqiF 'Negative results are first-class' '$ROOT/spec' '$ROOT/skills' '$ROOT/assets' '$ROOT/plugins/experiment-lab-ar' '$ROOT/plugins/paper-polish-ar/spec' '$ROOT/plugins/paper-polish-ar/assets'"
chk "NEGATIVE_INFORMATIVE retired as a live verdict label (VERIFY-PROTOCOL)" \
  "! grep -qF 'NEGATIVE_INFORMATIVE' '$VERIFY'"
chk "review no longer pre-acquits a negative as 'not hollow / non-reject IN-LOOP'" \
  "! grep -qF 'informative negative result is NOT hollow' '$REVIEWC'"

# ── (2) the replacement policy is STATED where the verdict is assigned ──────────────────────
chk "V10 carries the NEGATIVE_CONTRADICTS_NOVELTY class" "grep -qF 'NEGATIVE_CONTRADICTS_NOVELTY' '$VERIFY'"
chk "V10 says it is not a contribution and not a deliverable" \
  "grep -qF 'THIS IS NOT A CONTRIBUTION AND NOT A DELIVERABLE' '$VERIFY'"
chk "V10 routes it to the terminal gate with ABANDON recommended" \
  "grep -qF 'the recommended disposition is ABANDON' '$VERIFY'"
chk "V10 keeps it verdict=PASS on RIGOR ONLY (so the terminal gate still opens)" \
  "grep -qF 'verdict=PASS **on RIGOR ONLY**' '$VERIFY'"
chk "the alive=false BINDING RULE names the new label" "grep -qF 'alive=false IFF contribution_verdict === NEGATIVE_CONTRADICTS_NOVELTY' '$VERIFY'"

# ── (3) the same policy reaches every producing / diagnosing surface ────────────────────────
chk "review contract: novelty-contradicting negative is a reject-class finding" \
  "grep -qF 'A NEGATIVE THAT CONTRADICTS THE SPEC'\\''S NOVELTY CLAIM IS NOT A CONTRIBUTION' '$REVIEWC'"
chk "review contract: raises id:'novelty-contradicted'" "grep -qF \"id:'novelty-contradicted'\" '$REVIEWC'"
chk "attack-class 6 refuses to acquit a novelty-contradicting negative" \
  "grep -qF 'A negative that contradicts the central novelty claim is not a contribution either' '$ATTACK'"
chk "dossier records negatives but never promotes them to the delivered claim" \
  "grep -qF 'is an ABANDON signal, never a finding to headline' '$DOSSIER'"
chk "experiment-protocol: CENTRAL GAMBLE FAIL routes to abandon, not a negative-result deliverable" \
  "grep -qF 'abandon the direction, NOT a negative-result deliverable' '$EXPROT'"
chk "experiment-protocol: peripheral FAIL is a 'recorded fact', not an honest-negative deliverable" \
  "grep -qF 'peripheral / baseline FAIL → recorded fact + advance' '$EXPROT'"
chk "operational-first: central FAIL is not 'a routine negative you can report'" \
  "grep -qF 'not a deliverable — it means the DIRECTION is dead' '$OPFIRST'"
chk "operational-first: peripheral is 'never the headline and never the contribution'" \
  "grep -qF 'never the headline and never the contribution' '$OPFIRST'"
chk "handoff-authoring: GAMBLE K routing ends in abandon, TECHNICAL/EXPECTED is a recorded fact" \
  "grep -qF 'abandon the direction if the rescue fails' '$HANDOFF' && grep -qF 'recorded fact, never the headline' '$HANDOFF'"
chk "research-rescue: a failed rescue is a rescue REPORT, never a scientific contribution" \
  "grep -qF 'It is NOT a scientific contribution' '$RESCUE'"
chk "research-protocol: the ABANDON-signal clause replaced the first-class clause" \
  "grep -qF 'is an ABANDON signal, not a' '$RPROT'"

# ── (4) the terminal gate KEEPS the three-way card (the reward-hack path must stay observable) ──
chk "terminal gate still offers Abandon / Ship / Rescue" \
  "grep -qF \"label: 'Abandon'\" '$SPEC' && grep -qF \"label: 'Ship'\" '$SPEC' && grep -qF \"label: 'Rescue one more round'\" '$SPEC'"
chk "terminal gate recommends Abandon for a dead central claim" \
  "grep -qF \"reason === 'over_claim' ? 'Ship' : 'Abandon'\" '$SPEC'"
chk "the Ship option is labelled an OWNER OVERRIDE against system policy" \
  "grep -qF 'OWNER OVERRIDE — system policy for a novelty-contradicting negative is ABANDON' '$SPEC'"
chk "the Abandon option states it IS the system policy" \
  "grep -qF 'SYSTEM POLICY for a novelty-contradicting negative' '$SPEC'"

# ── (5) the orthogonal transient rule is UNTOUCHED (t69's contract) ─────────────────────────
chk "died-run rule survives: a died run is NEVER a result.md and NEVER a negative result" \
  "grep -qF 'NEVER a result.md and NEVER a negative result' '$EXPROT'"

echo "----"
echo "t77_negative_policy: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
