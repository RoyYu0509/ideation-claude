#!/usr/bin/env bash
# t40 — META-LOOP HANDOFF generation, UNIFIED (owner 需求 4/5 + the 2026-06-29 setup/gen split refactor).
# Workspace bootstrap and HANDOFF authoring are now SEPARATE dispatch stages, and ONE function generateHandoff(
# state, transition) serves EVERY HANDOFF generation point — round-0 initial author (transition=false), Revise
# (transition=false), and the per-round CONTINUE/amplify transition (transition=true). Round 0 is the degenerate
# transition=false case. Same idiom as t38/t39: research.js is an LLM-READ SPEC (spawn/agent never run), so the
# suite is STATIC-STRUCTURAL grep + a python ordering check on the spec + the handoff-authoring skill (SKILL.md + reference/ extensions).
#
#   A — STAGE SPLIT: setupWorkspace is its OWN stage ('setup_workspace' → 'gen_handoff'); the mechanical build
#       lives in bin/setup_workspace.sh; the JS guard (exists(milestone-state.json) → return) keeps it one-time.
#   B — RE-AUTHOR wiring: generateHandoff passes reauthor=!isRound0 to seedToHandoffGoal; the reauthorClause
#       flags RE-AUTHOR MODE + routes to reference/mode-round-update.md (the ratchet discipline lives THERE, not restated here).
#   C — UNIFIED generateHandoff(state, transition): `transition` gates the round-transition mechanics; the (P)
#       re-author core ALWAYS runs; surfaceOnFail=isRound0||!transition; append-cat FALLBACK; consume sidecars;
#       re-open GUARDED on (transition && !isRound0 && milestones-done) so round 0 never perturbs round 1's backstop.
#   D — HARDENER on every author (incl round 0): the workorder_hardener spawn sits OUTSIDE the transition block.
#   E — PER-ROUND GATE + Revise: loop CONTINUE/raise route to 'handoff_gate'; Revise routes to 'gen_handoff'
#       (transition=false); gateHandoffApproval builds a report when loop_round>0.
#   F — ADDENDUM: reference/mode-round-update.md carries the §RE-AUTHOR ratchet discipline; the main rubric + goal ROUTE to it.
#   G — Phase 5 segment rubric externalized to reference/phase5-experiments.md (the #9 cut); main rubric routes to it.
#   Run: bash tests/t40_meta_loop_reauthor.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
RUBRIC="$ROOT/skills/handoff-authoring/SKILL.md"
pass=0; fail=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }
# the one-time guard line carries backticks (a template literal) — match it backtick-free with grep -E
GUARD='exists\(.*milestone-state\.json.*\)\) return'

# ── A — setup is its OWN stage, delegates to bin/, and stays one-time-guarded ───────────────────────────
chk "A setupWorkspace is a standalone function"          "grep -qF 'function setupWorkspace(state) {' '$SPEC'"
chk "A setupWorkspace delegates to bin/setup_workspace.sh" "grep -qF 'bin/setup_workspace.sh' '$SPEC'"
chk "A setupWorkspace GUARDED: exists(milestone-state.json) → return (never re-run the destructive build)" \
    "grep -qE '$GUARD' '$SPEC'"
chk "A 'setup_workspace' dispatch stage runs setupWorkspace then routes to gen_handoff" \
    "grep -qF \"case 'setup_workspace': setupWorkspace(state); state.stage = 'gen_handoff'\" '$SPEC'"
chk "A 'gen_handoff' dispatch stage runs generateHandoff(state, false)" \
    "grep -qF 'generateHandoff(state, false)' '$SPEC'"
chk "A the bin script exists and is executable"          "test -x '$ROOT/bin/setup_workspace.sh'"
# [neg] removing the guard line means the destructive build is no longer one-time → the guard assert FAILs
SPB="$(mktemp)"; grep -vE "$GUARD" "$SPEC" > "$SPB"
chk "A [neg] guard assert FAILs if the one-time guard line is removed" "! grep -qE '$GUARD' '$SPB'"
rm -f "$SPB"

# ── B — the RE-AUTHOR wiring ──────────────────────────────────────────────────────────────────────────
chk "B generateHandoff passes reauthor=!isRound0 to seedToHandoffGoal" \
    "grep -qF 'seedToHandoffGoal(state.picked_seed_file, slug, state.venue, state.notes, !isRound0)' '$SPEC'"
chk "B seedToHandoffGoal takes the reauthor param"       "grep -qF 'function seedToHandoffGoal(seedFile, slug, venueLabel, notes, reauthor) {' '$SPEC'"
chk "B seedToHandoffGoal builds the reauthorClause"      "grep -qF 'const reauthorClause = reauthor ?' '$SPEC'"
chk "B reauthorClause routes to the externalized RE-AUTHOR addendum (single home)" "grep -qF 'reference/mode-round-update.md' '$SPEC'"
chk "B reauthorClause flags RE-AUTHOR MODE"              "grep -qF 'RE-AUTHOR MODE (per-round regeneration' '$SPEC'"
chk "B [anti-dup NEW-1] the clause NO LONGER restates the §RE-AUTHOR input list (it lives once in the addendum)" "! grep -qF 'the IMMUTABLE baselines' '$SPEC'"
chk "B reauthorClause is appended to the goal"           "grep -qF 'notesClause + reauthorClause' '$SPEC'"

# ── C — the UNIFIED generateHandoff(state, transition) ─────────────────────────────────────────────────
chk "C generateHandoff(state, transition) is the single function" "grep -qF 'function generateHandoff(state, transition) {' '$SPEC'"
chk "C transition gates the round-transition mechanics"  "grep -qF 'if (transition) {' '$SPEC'"
chk "C (P) re-author core spawns the seed_to_handoff worker" "grep -qF \"spawnWorker('seed_to_handoff', seedToHandoffGoal(\" '$SPEC'"
chk "C surfaceOnFail = isRound0 || !transition (round0/Revise hard-halt; transition falls back)" \
    "grep -qF 'const surfaceOnFail = isRound0 || !transition' '$SPEC'"
chk "C an append-cat survives as the fallback (forward-motion floor)"  "grep -qF 'cat \"\$h\" >> \"\${ws}/HANDOFF.md\"' '$SPEC'"
chk "C sidecars are consumed (rm) after the re-author"   "grep -qF 'rm -f \"\${ws}\"/HANDOFF-*.md' '$SPEC'"
chk "C re-open GUARDED on transition && !isRound0 (陷阱3: round 0 never re-opens)" "grep -qF 'if (transition && !isRound0) {' '$SPEC'"
chk "C re-open further GUARDED on the milestones actually being done" \
    "grep -qF \"if (led.milestones['EXPERIMENTS_DONE'] || led.milestones['RESULTS_ON_DISK']) {\" '$SPEC'"
# [neg] removing the round0-safety guard means round 0 would re-open + snapshot → the assert FAILs
SPC="$(mktemp)"; grep -vF 'if (transition && !isRound0) {' "$SPEC" > "$SPC"
chk "C [neg] re-open-guard assert FAILs if 'if (transition && !isRound0)' is removed" "! grep -qF 'if (transition && !isRound0) {' '$SPC'"
rm -f "$SPC"

# ── D — the workorder hardener runs on EVERY author (incl round 0): it sits OUTSIDE the transition block ─
chk "D the workorder hardener is spawned"                "grep -qF \"spawnL2('workorder_hardener'\" '$SPEC'"
# python ordering check inside generateHandoff: the transition block opens, the consume-rm (unconditional) and
# the hardener come AFTER it closes, and the re-open guard comes after the hardener. If the hardener were nested
# in the transition block it would NOT run on round 0 — this ordering proves it is not.
chk "D hardener spawn is AFTER the consume-rm and BEFORE the re-open guard (⇒ outside transition, runs round 0)" \
    "python3 - '$SPEC' <<'PY'
import sys
src = open(sys.argv[1]).read()
fn = src.index('function generateHandoff(state, transition)')
body = src[fn:]
i_consume = body.index('rm -f \"\${ws}\"/HANDOFF-*.md')
i_harden  = body.index(\"spawnL2('workorder_hardener'\")
i_reopen  = body.index('if (transition && !isRound0) {')
sys.exit(0 if i_consume < i_harden < i_reopen else 1)
PY"

# ── E — the per-round handoff gate + Revise routing + the report ────────────────────────────────────────
chk "E loop CONTINUE/raise route to the per-round handoff gate" \
    "grep -qF \"state.stage = CFG.checkpoints.handoff_approval ? 'handoff_gate' : 'loop'; break\" '$SPEC'"
chk "E Revise routes to gen_handoff (transition=false, (P)-only re-author)" \
    "grep -qF \"if (c === 'Revise')             { state.stage = 'gen_handoff'\" '$SPEC'"
chk "E gateHandoffApproval builds a report when loop_round>0" "grep -qF 'if (state.loop_round > 0) {' '$SPEC'"
chk "E the report object is constructed"                 "grep -qF 'report = {' '$SPEC'"
chk "E the report carries prior_review"                  "grep -qF 'prior_review:' '$SPEC'"
chk "E the report carries the amplifier conclusion"      "grep -qF 'amplifier: raisedThisRound' '$SPEC'"
chk "E the report carries next_work"                     "grep -qF 'next_work:' '$SPEC'"
chk "E the gate context passes round + report"           "grep -qF 'round: state.loop_round, report,' '$SPEC'"

# ── F — the externalized RE-AUTHOR addendum + the routing to it (the mode split) ────────────────────────
REAUTHOR="$ROOT/skills/handoff-authoring/reference/mode-round-update.md"
chk "F mode-round-update.md (round-N extension) exists"  "test -f '$REAUTHOR'"
chk "F addendum has the §RE-AUTHOR section"              "grep -qF '## RE-AUTHOR mode' '$REAUTHOR'"
chk "F addendum points to the hook that hard-denies overwriting the FROZEN ratchet baselines"     "grep -qF 'lock_guard' '$REAUTHOR'"
chk "F addendum forbids a silent WEAKEN-TO-PASS / NARROW-TO-DELIVERED" "grep -qF 'FORBIDDEN: a silent WEAKEN-TO-PASS' '$REAUTHOR'"
chk "F addendum names the legal REDIRECT + RAISE/PIVOT ratchet moves"  "grep -qF 'REDIRECT' '$REAUTHOR' && grep -qF 'RAISE or PIVOT' '$REAUTHOR'"
chk "F the main rubric ROUTES round 1+ to the addendum"  "grep -qF 'mode-round-update.md' '$RUBRIC'"
chk "F [neg] the §RE-AUTHOR section is NO LONGER inline in the main rubric" "! grep -qF '## RE-AUTHOR mode' '$RUBRIC'"

# ── G — Phase 5 segment rubric externalized (the #9 cut) ───────────────────────────────────────────────
PHASE5="$ROOT/skills/handoff-authoring/reference/phase5-experiments.md"
chk "G phase5-experiments.md (segment rubric leaf) exists" "test -f '$PHASE5'"
chk "G it carries the DISCRIMINATIVE SANITY / claim-correspondence rubric" "grep -qF 'DISCRIMINATIVE SANITY' '$PHASE5' && grep -qiF 'CLAIM-CORRESPONDENCE' '$PHASE5'"
chk "G the main rubric Phase 5 ROUTES to it"             "grep -qF 'phase5-experiments.md' '$RUBRIC'"
chk "G [neg] the heavy segment rubric is NO LONGER inline in the main rubric" "! grep -qF 'REQUIRED PUBLICATION-GRADE AXES' '$RUBRIC'"

echo "========================================"
echo "t40_meta_loop_reauthor: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
