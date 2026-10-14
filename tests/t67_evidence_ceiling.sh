#!/usr/bin/env bash
# T67 — the evidence-type → claim-ceiling axis (ARIS item 3, 2026-07-09), as it stands after the spec re-aim
# (2026-08-30). The axis has TWO enforcement points and one declaration point, and all three must stay wired:
#   declare  — §4b per-K `evidence.{type,claimed,measured}` in the locked scale contract (handoff-authoring)
#   verdict  — V8 (vii) EVIDENCE-TYPE CONFORMANCE VOIDs a verdict decided on weaker-than-declared evidence
#   wording  — SPEC-FREEZE §1b holds the DELIVERED spec's prose to the weakest backing evidence type
# The old FINDINGS.json@2 + bin/freeze_lint.sh half of this axis retired with the writing engine (both live in
# inactive/); the fixture-driven lint cases went with them. What survives is the axis itself, and this test is
# what stops it from quietly lapsing now that no lint enforces it mechanically.
# Run: bash tests/t67_evidence_ceiling.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1"; fail=$((fail+1)); }

HA="$ROOT/skills/handoff-authoring/SKILL.md"
VP="$ROOT/spec/spawn-prompts/VERIFY-PROTOCOL.md"
SF="$ROOT/spec/spawn-prompts/SPEC-FREEZE.md"

# ── (1) DECLARE: the typology + the ratchet asymmetry live in the authoring skill ──────────────────────────
grep -q "EVIDENCE TYPE → CLAIM CEILING" "$HA" \
  && grep -q "surrogate_domain" "$HA" && grep -q "proxy_metric" "$HA" \
  && ok "handoff-authoring §4b carries the three-type typology" || no "§4b typology missing"
grep -q 'downgrade `evidence.type` away from `direct`' "$HA" \
  && ok "§4b keeps the ratchet asymmetry (downgrade = weaken-to-pass, upgrade = tighten)" || no "§4b ratchet cells missing"
grep -q "A benchmark IS the" "$HA" \
  && ok "§4b keeps the anti-over-correction rule (a benchmark IS the domain)" || no "benchmark-IS-the-domain rule missing"

# ── (2) VERDICT: V8 (vii) still voids a verdict resting on weaker-than-declared evidence ───────────────────
grep -q "EVIDENCE-TYPE" "$VP" && ok "VERIFY-PROTOCOL V8 carries EVIDENCE-TYPE CONFORMANCE" || no "V8 (vii) missing"
grep -qF "wrong-type evidence renders NO verdict" "$VP" \
  && ok "V8 (vii) VOIDs (neither ship nor kill) rather than silently downgrading" || no "V8 (vii) void semantics missing"

# ── (3) WORDING: the ceiling reaches the DELIVERED spec, which is now the only prose the run emits ─────────
grep -q "EVIDENCE → CLAIM CEILING" "$SF" \
  && ok "SPEC-FREEZE §1b carries the ceiling" || no "SPEC-FREEZE ceiling section missing"
grep -q "proxy_metric" "$SF" && grep -q "surrogate_domain" "$SF" \
  && ok "SPEC-FREEZE names all three types with their wording ceilings" || no "SPEC-FREEZE type table incomplete"
grep -qF "Take the WEAKEST type across the Ks" "$SF" \
  && ok "SPEC-FREEZE binds the ceiling to the WEAKEST backing type (no laundering by averaging)" || no "weakest-type rule missing"
grep -qF "a defect even when every number in it is real" "$SF" \
  && ok "SPEC-FREEZE treats an above-ceiling claim as a defect independent of number provenance" || no "above-ceiling-is-a-defect rule missing"

# ── (4) the declaration side: the seed/round authoring modes + the independent M1 reviewer ────────────────
grep -q "evidence-type" "$ROOT/spec/spawn-prompts/SCALE-CONTRACT-REVIEW.md" \
  && grep -q "evidence" "$ROOT/skills/handoff-authoring/reference/mode-seed-generation.md" \
  && grep -q "evidence.type" "$ROOT/skills/handoff-authoring/reference/mode-round-update.md" \
  && ok "generation side declares + M1 checks the declaration" || no "generation-side wiring missing"
grep -q "evidence basis" "$ROOT/spec/spawn-prompts/DOSSIER.md" \
  && ok "DOSSIER.md records the evidence basis in science language" || no "DOSSIER evidence-basis missing"
grep -q "benchmark IS" "$ROOT/plugins/paper-polish-ar/skills/review-panel/SKILL.md" \
  && ok "review-panel overclaim axis carries the evidence-type criterion + guards" || no "review-panel wiring missing"

# ── (5) the retired half is genuinely gone (no half-removed references that would read as live) ───────────
[ ! -e "$ROOT/spec/FINDINGS.schema.json" ] && [ ! -e "$ROOT/bin/freeze_lint.sh" ] \
  && ok "the retired FINDINGS.json@2 + freeze_lint half is out of the live tree" || no "retired ceiling machinery still present"

echo "----"; echo "t67_evidence_ceiling: $pass passed, $fail failed"; [ "$fail" = 0 ]
