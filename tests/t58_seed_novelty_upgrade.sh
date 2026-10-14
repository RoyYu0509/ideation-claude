#!/usr/bin/env bash
# T58 — seed-novelty upgrade (2026-07-06). Owner diagnosis: seeds were incremental and their novelty died in
# round 1 (prior art found in-run), after which the loop ground on a true-but-known mediocre paper. Three fixes
# pinned here: (1) the ideate/refine novelty modality is the MECHANICAL Semantic Scholar script (s2_novelty.py,
# zero-token, citation-graph) with WebSearch demoted to what S2 cannot see; (2) ideate builds a DOOMED LIST
# (author-announced future work) and discards candidates on it — the authors are months ahead on their own
# roadmap; (3) S10 "scooped / novelty collapse" is a hard stop: the literature auditor may return a 'scooped'
# verdict and L0 gates it to the owner (Proceed-with-defense / Reposition / Abandon) instead of grinding on.
# Run: bash tests/t58_seed_novelty_upgrade.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
PROTO="$ROOT/assets/research-protocol.md"
LWORK="$ROOT/spec/spawn-prompts/LITERATURE-WORKER.md"
LAUDIT="$ROOT/spec/spawn-prompts/LITERATURE-AUDIT.md"
IDEATE="$ROOT/plugins/arxiv-recommender-ar/skills/arxiv-generate/SKILL.md"   # renamed 2026-07-11 (verified-kill)
SCREEN="$ROOT/plugins/arxiv-recommender-ar/skills/arxiv-screen/SKILL.md"
REFUTE="$ROOT/plugins/arxiv-recommender-ar/skills/arxiv-refute/SKILL.md"
S2NOV="$ROOT/plugins/arxiv-recommender-ar/scripts/s2_novelty.py"
S2CLI="$ROOT/plugins/arxiv-recommender-ar/scripts/lib/s2_client.py"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── (1) mechanical S2 modality exists and is the primary search in both skills ─────────────────────────
chk "s2_novelty.py exists with search + related modes"    "grep -qF -- '--mode' '$S2NOV' && grep -qF 'related' '$S2NOV' && grep -qF 'search_by_title' '$S2NOV'"
chk "s2_client carries the recommendations endpoint"      "grep -qF 'def recommendations_for_paper(' '$S2CLI'"
chk "ideate Step 2.5 runs s2_novelty as PRIMARY modality" "grep -qF 's2_novelty.py' '$IDEATE' && grep -qiF 'PRIMARY landscape modality' '$IDEATE'"
chk "ideate demotes WebSearch to at most 1 gap-filler"    "grep -qiF 'at most 1 WebSearch' '$IDEATE'"
chk "screen runs s2_novelty with the adversarial hunt-the-killer stance" "grep -qF 's2_novelty.py' '$SCREEN' && grep -qiF 'hunt the paper that kills it' '$SCREEN'"
chk "screen allowed-tools admits the s2_novelty script"   "grep -qE '^allowed-tools:.*s2_novelty' '$SCREEN'"
chk "refutation hunter exists with the REFUTE stance (WebSearch tier)" "grep -qiF 'refutation' '$REFUTE' && grep -qE '^allowed-tools:.*WebSearch' '$REFUTE'"

# ── (2) doomed-followup discipline in ideate ───────────────────────────────────────────────────────────
chk "ideate builds the DOOMED LIST from the authors' own future work" "grep -qF 'DOOMED LIST' '$IDEATE'"
chk "ideate Phase 4b discards doomed candidates into rejected_candidates" "grep -qF 'doomed follow-up:' '$IDEATE'"
chk "ideate anti-pattern pins author-owned follow-ups"    "grep -qiF 'Author-owned follow-up' '$IDEATE'"

# ── (3) S10 scooped hard stop: protocol -> worker honesty -> auditor verdict -> L0 gate ────────────────
chk "protocol defines S10 scooped / novelty collapse"     "grep -qF '(S10) Scooped / novelty collapse' '$PROTO'"
chk "protocol header range is S1–S10"                     "grep -qF 'Hard-stop triggers (S1–S10)' '$PROTO'"
chk "S10 forbids the silent claim-narrow dodge"           "grep -qiF 'Never quietly narrow the claim' '$PROTO'"
chk "literature worker must surface a killing rival, never bury it" "grep -qF 'SCOOPED HONESTY' '$LWORK' && grep -qiF 'NEVER omit or bury' '$LWORK'"
chk "literature auditor may return verdict=scooped with scooped_by evidence" "grep -qF '\"scooped\"' '$LAUDIT' && grep -qF 'scooped_by' '$LAUDIT'"
chk "auditor: scooped OUTRANKS incomplete"                "grep -qiF 'OUTRANKS' '$LAUDIT'"
chk "L0 gates on the scooped verdict (not only incomplete)" "grep -qF \"v.verdict === 'scooped'\" '$SPEC'"
chk "L0 logs the scooped event"                           "grep -qF 'literature_scooped' '$SPEC'"
chk "handoff-authoring governance points at S1–S10"       "grep -qF 'S1–S10' '$ROOT/skills/handoff-authoring/SKILL.md'"
chk "research.js still parses"                            "node --check '$SPEC'"

echo "----------------------------------------"
echo "t58: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
