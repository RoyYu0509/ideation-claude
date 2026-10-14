#!/usr/bin/env bash
# T16 — the post-loop TERMINAL stage (spec re-aim 2026-08-30) + the still-vendored polish-figures assets.
# The loop never writes a manuscript, and since the re-aim it never writes a PAPER either: its product is a
# research SPECIFICATION. After verify_final PASSes, ONE terminal stage runs — spec_freeze — which distils the
# settled HANDOFF into SPEC-FINAL.md + SPEC-EVOLUTION.md and grounds every number, then ships. The six
# writing-engine stages (freeze_findings/story/write/figures/edit/freeze) are RETIRED into inactive/.
# This test proves the wiring, all MECHANICAL/offline:
#   (1) spec/research.js: spec_freeze is the ONLY post-verify dispatch case; verify_final routes to it on
#       science PASS (never ship() directly); the chain ends at ship() inside runSpecFreeze; the retired
#       writing machinery is GONE; the spec still parses (node --check).
#   (2) config/config.yaml: the spec_freezer role + the spec_freeze budget exist, and the retired
#       writing:/writing-role/writing-budget keys do not.
#   (3) plugins/paper-polish-ar: polish-figures.js spec + command + skill deps + config block STILL exist —
#       /polish-figures survives as a STANDALONE command; it is simply no longer called by the pipeline.
#   (4) vendor hook check_fidelity.py: a figure-mode handler + its dispatch are present, and the file parses.
# Run: bash tests/t16_polish_stage.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
CFG="$ROOT/config/config.yaml"
VDIR="$ROOT/plugins/paper-polish-ar"
VCFG="$VDIR/config/config.yaml"
HOOK="$VDIR/hooks/check_fidelity.py"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── (1) spec/research.js wiring ───────────────────────────────────────────────
# [terminal-gate 2026-07-01] EXIT/EXIT_AT_CAP share ONE guarded block: try the per-round amplifier first (a clean
# EXIT that earns a bolder claim converts to one more round via handoff_gate), else BOTH route to verify_final.
chk "spec: loop EXIT/EXIT_AT_CAP both route to 'verify_final' (final science verify before delivery)" "grep -qE \"verdict === 'EXIT' \\|\\| verdict === 'EXIT_AT_CAP'\" '$SPEC' && grep -qF \"state.stage = 'verify_final'; persist(state); break\" '$SPEC'"
chk "spec: loop tail sets terminal_reason cap_exit vs clean_exit" "grep -qF \"state.terminal_reason = (verdict === 'EXIT_AT_CAP') ? 'cap_exit' : 'clean_exit'\" '$SPEC'"
chk "spec: clean EXIT still sets ship_reason=clean_exit at the loop tail" "grep -qF \"if (verdict === 'EXIT') state.ship_reason = 'clean_exit'\" '$SPEC'"
chk "spec: the removed max_loop_rounds_unresolved auto-ship string is GONE" "! grep -qF 'max_loop_rounds_unresolved' '$SPEC'"
chk "spec: verify_final stage present (per-round VERIFY moved here, runs once)" "grep -qF \"case 'verify_final':\" '$SPEC'"
chk "spec: verify_final routes to 'spec_freeze' on science PASS" "grep -qF \"state.stage = 'spec_freeze'; persist(state); break\" '$SPEC'"
chk "spec: spec_freeze is the ONLY post-verify dispatch case" "grep -qF \"case 'spec_freeze':\" '$SPEC'"
chk "spec: loop no longer ships directly on EXIT" "! grep -qF \"ship(state, 'clean_exit')\" '$SPEC'"
chk "spec: the delivery chain ends at ship() inside runSpecFreeze" "awk '/function runSpecFreeze\\(/{f=1} f&&/ship\\(state, reason\\)/{print;exit}' '$SPEC' | grep -q 'ship(state, reason)'"
chk "spec: spec_freeze spawns the spec_freezer leaf via spawnL2" "grep -qF \"spawnL2('spec_freezer'\" '$SPEC'"
chk "spec: specFreezeGoal points at the SPEC-FREEZE rubric" "grep -qF 'specFreezeGoal' '$SPEC' && grep -qF 'spec/spawn-prompts/SPEC-FREEZE.md' '$SPEC' && test -f '$ROOT/spec/spawn-prompts/SPEC-FREEZE.md'"
chk "spec: SPEC-FINAL.md is a HARD deliverable precondition (no silent empty ship)" "grep -qF 'SPEC-FINAL.md' '$SPEC' && grep -qF 'spec-freeze-failed' '$SPEC'"
chk "spec: spec_freeze is MANDATORY on every ship path (shipRequireList)" "grep -qF \"['verify_final', 'spec_freeze']\" '$SPEC'"
chk "spec: the retired writing-engine dispatch cases are GONE" "! grep -qF \"case 'freeze_findings':\" '$SPEC' && ! grep -qF \"case 'story':\" '$SPEC' && ! grep -qF \"case 'write':\" '$SPEC' && ! grep -qF \"case 'figures':\" '$SPEC' && ! grep -qF \"case 'edit':\" '$SPEC'"
chk "spec: the retired WRITING config binding + diff-ladder are GONE" "! grep -qF \"need(CFG, 'writing')\" '$SPEC' && ! grep -qF 'renderDiffLadder' '$SPEC'"
chk "spec: ship_reason carried in state" "grep -qF 'state.ship_reason' '$SPEC'"
chk "spec: parses (node --check)" "node --check '$SPEC'"

# ── (2) config/config.yaml wiring ─────────────────────────────────────────────
chk "config: spec_freezer role + spec_freeze budget wired" \
    "python3 -c \"import yaml; c=yaml.safe_load(open('$CFG')); assert c['models']['spec_freezer']['model']; assert c['budgets']['spec_freeze']['max_subagent_spawns'] >= 1\""
chk "config: the retired writing block + writing roles + writing budgets are GONE" \
    "python3 -c \"import yaml; c=yaml.safe_load(open('$CFG')); assert 'writing' not in c; assert not ({'findings_freezer','paper_architect','paper_writer','paper_editor','paper_freezer','polish_figures_orchestrator'} & set(c['models'])); assert not ({'freeze_findings','story','write','edit','freeze','polish_figures'} & set(c['budgets'])); assert 'polish_figures_spec' not in c['paths']\""

# ── (3) vendored polish-figures spec + command + skill deps + config block ────
chk "vendor: spec/polish-figures.js"                "test -f '$VDIR/spec/polish-figures.js'"
chk "vendor: commands/polish-figures.md"            "test -f '$VDIR/commands/polish-figures.md'"
chk "vendor: research-figure-plotting + de-ai-defaults.md" "test -f '$VDIR/skills/research-figure-plotting/plotting-reference/de-ai-defaults.md'"
chk "research-figure-plotting: Plot code style section"                 "grep -qF '## Plot code style' '$VDIR/skills/research-figure-plotting/SKILL.md'"
chk "vendor: check-figure-fidelity skill"           "test -f '$VDIR/skills/check-figure-fidelity/SKILL.md'"
chk "vendor config: figures block + model pinned + dims" \
    "python3 -c \"import yaml; c=yaml.safe_load(open('$VCFG')); assert c['figures']['roles']['reviser']['model']=='sonnet'; assert c['figures']['roles']['fidelity']['model']=='sonnet'; assert 'layout' in c['figures']['quality_dimensions']\""

# ── (3b) polish-figures PARALLEL path: per-figure fan-out over disjoint figures (mirrors /polish sections) ──
PFS="$VDIR/spec/polish-figures.js"
chk "parallel: allDisjoint gate + runFiguresParallel present"        "grep -qF 'function allDisjoint(' '$PFS' && grep -qF 'runFiguresParallel(' '$PFS'"
chk "parallel: Phase 2 branches parallel-vs-serial on disjointness"  "grep -qF 'allDisjoint(figures)' '$PFS' && grep -qF 'for (const fig of figures) runFigure(fig)' '$PFS'"
chk "parallel: worktree-per-figure + serial assembleFigures"         "grep -qF 'worktree add -b' '$PFS' && grep -qF 'function assembleFigures(' '$PFS'"
chk "parallel: figure_runner spawned via roleOpts + FIGURE_RESULT_SCHEMA" "grep -qF \"roleOpts('figure_runner'\" '$PFS' && grep -qF 'FIGURE_RESULT_SCHEMA' '$PFS'"
chk "parallel: reads the single-source loop spec/figure-loop.md"     "grep -qF 'spec/figure-loop.md' '$PFS' && test -f '$VDIR/spec/figure-loop.md'"
chk "parallel: convergence is DETERMINISTIC via figure_converge.py"  "grep -qF 'scripts/figure_converge.py' '$PFS' && test -f '$VDIR/scripts/figure_converge.py'"
chk "parallel: orchestrator RE-VERIFIES annotation crop-check at assemble" "grep -qF 'countInPlotAnnotations(abs(fig.plot_script))' '$PFS'"
chk "parallel: max_parallel_figures NEED-BASED (0=uncapped) + figure_runner=claude" \
    "python3 -c \"import yaml; c=yaml.safe_load(open('$VCFG')); assert c['figures']['max_parallel_figures']==0; assert c['figures']['roles']['figure_runner']['subagent_type']=='claude'\""
chk "figure_converge.py: parses + has round/best modes"              "python3 -c \"import ast; ast.parse(open('$VDIR/scripts/figure_converge.py').read())\" && grep -qF 'def run_round(' '$VDIR/scripts/figure_converge.py' && grep -qF 'def run_best(' '$VDIR/scripts/figure_converge.py'"
chk "serial runFigure UNCHANGED as the fallback path"                "grep -qF 'function runFigure(fig)' '$PFS'"

# ── (4) vendored fidelity hook: figure mode present + parses ──────────────────
chk "hook: handle_figure_mode defined"              "grep -qF 'def handle_figure_mode(' '$HOOK'"
chk "hook: figure-mode dispatch in main()"          "grep -qE 'mode.\\) == .figure.' '$HOOK'"
chk "hook: parses (python3 ast)"                    "python3 -c \"import ast; ast.parse(open('$HOOK').read())\""

echo "----"; echo "t16_polish_stage: $pass passed, $fail failed"; [ "$fail" = 0 ]
