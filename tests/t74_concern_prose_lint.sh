#!/usr/bin/env bash
# T74 — bin/concern_prose_lint.sh: TASK_STATUS.md "## Editorial direction" staleness lint.
# Real incident (gate-invariant-relaxed-speculative-decoding, 2026-07-16): K1's structured status moved to
# "descoped_infeasible_at_scale" while the same file's Editorial-direction prose still called it "the whole
# paper" — zero code caught it. This lint is advisory (D12 precedent): flags, never auto-edits, never blocks.
# Run: bash tests/t74_concern_prose_lint.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINT="$ROOT/bin/concern_prose_lint.sh"
pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }; no(){ echo "FAIL  $1  --  $2"; fail=$((fail+1)); }

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

concerns(){ printf '%s' "$1" > "$WORK/TASK_STATUS.concerns.json"; }
status_md(){ printf '%s' "$1" > "$WORK/TASK_STATUS.md"; }
run(){ bash "$LINT" "$WORK"; }
field(){ run | python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

# ── (1) K1 open, mentioned in prose → NOT stale ─────────────────────────────────────────
concerns '{"open_concerns":[{"id":"K1","status":"open"}]}'
status_md $'# TASK_STATUS\n\n## Editorial direction (top strengthening needs)\n1. K1 is the whole paper.\n'
[ "$(field "['stale']")" = "[]" ] && ok "K1 open + mentioned -> not stale" || no "K1 open + mentioned -> not stale" "$(run)"

# ── (2) K1 descoped, prose still calls it central, no ack words → STALE ────────────────
concerns '{"open_concerns":[{"id":"K1","status":"descoped_infeasible_at_scale"}]}'
status_md $'# TASK_STATUS\n\n## Editorial direction (top strengthening needs)\n1. K1 is the whole paper — Phase 0 must de-risk the substitute-pair logit gap before the campaign.\n'
out="$(run)"
echo "$out" | grep -q '"id": "K1"' && echo "$out" | grep -q '"status": "descoped_infeasible_at_scale"' \
  && ok "K1 descoped + stale prose -> flagged" || no "K1 descoped + stale prose -> flagged" "$out"

# ── (3) K1 descoped, but prose ALREADY says so (escape hatch) → NOT stale ──────────────
concerns '{"open_concerns":[{"id":"K1","status":"descoped_infeasible_at_scale"}]}'
status_md $'# TASK_STATUS\n\n## Editorial direction (top strengthening needs)\n1. K1 was descoped as infeasible at scale; no longer the headline.\n'
[ "$(field "['stale']")" = "[]" ] && ok "K1 descoped + prose already acknowledges -> not stale (escape hatch)" \
  || no "escape hatch" "$(run)"

# ── (4) K1 not mentioned at all in prose → NOT stale (nothing to contradict) ────────────
concerns '{"open_concerns":[{"id":"K1","status":"descoped_infeasible_at_scale"}]}'
status_md $'# TASK_STATUS\n\n## Editorial direction (top strengthening needs)\n1. Tighten the K2 speed bound.\n'
[ "$(field "['stale']")" = "[]" ] && ok "K1 descoped but never mentioned -> not stale" || no "unmentioned id" "$(run)"

# ── (5) no "## Editorial direction" heading → section_found:false, never crashes ───────
concerns '{"open_concerns":[{"id":"K1","status":"descoped_infeasible_at_scale"}]}'
status_md $'# TASK_STATUS\n\n## Some Other Heading\nnothing relevant here\n'
[ "$(field "['section_found']")" = "False" ] && ok "no Editorial-direction heading -> section_found=false" \
  || no "missing heading handling" "$(run)"

# ── (6) missing TASK_STATUS.md / concerns.json entirely → defensive skip, exit 0 ───────
rm -f "$WORK/TASK_STATUS.md" "$WORK/TASK_STATUS.concerns.json"
run >/dev/null 2>&1
[ $? -eq 0 ] && ok "missing files -> exit 0 (never blocks)" || no "missing files should exit 0" ""

# ── (7) malformed concerns.json → defensive skip, exit 0, not a crash ──────────────────
printf 'not json' > "$WORK/TASK_STATUS.concerns.json"
status_md $'## Editorial direction (top strengthening needs)\n1. K1.\n'
run >/dev/null 2>&1
[ $? -eq 0 ] && ok "malformed concerns.json -> exit 0 (fail-open)" || no "malformed json should exit 0" ""

# ── Static: registered in config.yaml + wired into spec/research.js ────────────────────
grep -q "concern_prose_lint" "$ROOT/config/config.yaml" && ok "checkpoints.concern_prose_lint present in config.yaml" \
  || no "config.yaml missing checkpoints.concern_prose_lint" ""
grep -q "concernProseStaleness" "$ROOT/spec/research.js" && ok "concernProseStaleness wired into spec/research.js" \
  || no "spec/research.js missing concernProseStaleness" ""
grep -q "Re-author stale Editorial direction now" "$ROOT/spec/research.js" && ok "escalation option present in gateHandoffApproval" \
  || no "spec/research.js missing the escalation option" ""

echo; echo "t74: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
