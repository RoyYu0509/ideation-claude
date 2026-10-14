#!/usr/bin/env bash
# T57 — figure-design capability (去畏手畏脚 2026-07-06): the polish-figures pass can fully REDESIGN a figure
# under a per-figure DESIGN BRIEF contract, instead of lint-only restyling (W28 real-run diagnosis: 2 rounds ×
# ~16 subagents produced +72/−36 lines of spines/legends/de-jargon while every design-level defect shipped).
# All MECHANICAL/offline greps + yaml asserts:
#   (1) the figure-design SKILL exists (fills the deleted nature-figure slot) + birth contract rewired
#   (2) polish-figures.js: design_brief schema + designer role + stage arg + redesign roundCap + brief-aware
#       fidelity/QA + semantics re-derive + Emit tex-apply under the polish-mode token-freeze + multi-repo
#   (3) three-place loop sync: runFigure / figure-loop.md carry the same brief bindings; figure_converge.py
#       arithmetic untouched (license-agnostic)
#   (4) check-figure-fidelity: honest-zoom license + bar 0-baseline rule + matches-brief / off-brief→HOLD
#   (5) L0: design-briefs gate wired (spawn stage=design → gate → repaint; ingest branch; skip flag; default OFF)
#   (6) knobs: key-config rows + apply_key_config mappings + PP/TOP config values
# Run: bash tests/t57_figure_design.sh
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$ROOT/spec/research.js"
CFG="$ROOT/config/config.yaml"
KEY="$ROOT/key-config.yaml"
AKC="$ROOT/bin/apply_key_config.sh"
VDIR="$ROOT/plugins/paper-polish-ar"
VCFG="$VDIR/config/config.yaml"
PFS="$VDIR/spec/polish-figures.js"
FLOOP="$VDIR/spec/figure-loop.md"
FDSK="$VDIR/skills/figure-design"
CFF="$VDIR/skills/check-figure-fidelity/SKILL.md"
SURV="$VDIR/spec/spawn-prompts/figures-survey.md"
VQA="$VDIR/spec/spawn-prompts/figures-visual-qa.md"
L0C="$ROOT/spec/spawn-prompts/POLISH-FIGURES-L0-CONTRACT.md"
pass=0; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi; }

# ── (1) the figure-design skill + birth contract ──────────────────────────────
chk "skill: figure-design SKILL.md + both references exist" \
    "test -f '$FDSK/SKILL.md' && test -f '$FDSK/references/archetypes.md' && test -f '$FDSK/references/axes-and-density.md'"
chk "skill: carries the reader-not-gate principle + the brief format" \
    "grep -q 'never the experiment gate' '$FDSK/SKILL.md' && grep -qF 'reader_takeaway' '$FDSK/SKILL.md'"
chk "skill: archetypes cover negative-result / ceiling / twinx / table-as-figure" \
    "grep -qi 'equivalence' '$FDSK/references/archetypes.md' && grep -qi 'deficit' '$FDSK/references/archetypes.md' && grep -qi 'twinx' '$FDSK/references/archetypes.md' && grep -qi 'ax.table' '$FDSK/references/archetypes.md'"
chk "birth contract: drafting.figure_skills = [figure-design, paper-polish-ar:research-figure-plotting (namespaced, H7⑤)], nature-figure GONE" \
    "python3 -c \"import yaml; c=yaml.safe_load(open('$CFG')); fs=c['drafting']['figure_skills']; assert fs==['figure-design','paper-polish-ar:research-figure-plotting'], fs\""
chk "birth contract: experiment-protocol names reader-facing figures per figure-design" \
    "grep -q 'figure-design' '$ROOT/plugins/experiment-lab-ar/spec/experiment-protocol.md'"

# ── (2) polish-figures.js: the redesign machinery ─────────────────────────────
chk "spec: design_brief in FIGURE_SURVEY_SCHEMA with categorical verdict enum" \
    "grep -qF \"design_brief: { type: 'object', required: ['reader_takeaway', 'verdict']\" '$PFS' && grep -qF \"enum: ['keep', 'restyle', 'redesign']\" '$PFS'"
chk "spec: panel_plan actions include to_si + to_table"                    "grep -qF \"enum: ['keep', 'merge', 'drop', 'to_si', 'to_table']\" '$PFS'"
chk "spec: stage arg design|repaint|all validated"                        "grep -qF \"['design', 'repaint', 'all'].includes(stage)\" '$PFS'"
chk "spec: designer role runs the survey (roleOpts designer + DEFAULT_SUBAGENT claude)" \
    "grep -qF \"roleOpts('designer', FIGURE_SURVEY_SCHEMA)\" '$PFS' && grep -qF \"designer: 'claude'\" '$PFS'"
chk "spec: REDESIGN_MAX_ROUNDS knob read (figures.redesign_max_rounds, default 3)" \
    "grep -qF 'KNOBS.redesign_max_rounds ?? 3' '$PFS'"
chk "spec: redesign roundCap ternary in BOTH runFigure and figureRunnerGoal (2 sites)" \
    "[ \"\$(grep -cF \"REDESIGN_MAX_ROUNDS : (fig.effort === 'light' ? 1 : MAX_ROUNDS)\" '$PFS')\" -ge 2 ]"
chk "spec: redesignLicensed predicate (restyle_only demotes)"              "grep -qF \"APPROVAL !== 'restyle_only'\" '$PFS'"
chk "spec: briefs persisted + design stage early-returns"                  "grep -qF 'figure-design-briefs.json' '$PFS' && grep -qF \"stage: 'design',\" '$PFS'"
# [dossier-12 G1] pointerized: the re-derive step lives in figure-loop.md §4b; the serial pointer names it.
chk "spec: semantics re-derived after first faithful redesign round"       "grep -qF 're-derive \`SEMANTICS\` after the first faithful round' '$ROOT/plugins/paper-polish-ar/spec/figure-loop.md' && grep -qF 'semantics re-derive' '$PFS'"
chk "spec: fidelity goal carries the brief + design_changes contract"      "grep -qF 'judging against an approved design brief' '$PFS' && grep -qF 'design_changes' '$PFS'"
chk "spec: QA design dimension default-on + brief injection"               "grep -qF \"['design', 'layout', 'legibility', 'consistency', 'code-naming']\" '$PFS' && grep -qF 'DESIGN BRIEF (the ' '$PFS'"
chk "spec: Emit applyTexChanges under polish-mode manifest + compile-fail revert + patches file" \
    "grep -qF 'function applyTexChanges()' '$PFS' && grep -qF \"mode: 'polish'\" '$PFS' && grep -qF 'REVERT tex apply (recompile failed)' '$PFS' && grep -qF 'figure-tex-patches.md' '$PFS'"
chk "spec: reviser never edits .tex (brief applied at Emit)"               "grep -qF 'NEVER edits any \`.tex\`' '$ROOT/plugins/paper-polish-ar/spec/figure-loop.md'"
chk "spec: held_sha recorded on HOLD (one-command manual apply)"           "grep -qF 'held_sha' '$ROOT/plugins/paper-polish-ar/spec/figure-loop.md' && grep -qF 'held_sha' '$PFS'"
chk "spec: multi-repo — per-repo grouping + parallel path forced single-repo" \
    "grep -qF 'function groupByRepo(' '$PFS' && grep -qF 'singleRepo(figures)' '$PFS' && grep -qF 'function headShas(' '$PFS'"

# ── (3) three-place loop sync ─────────────────────────────────────────────────
chk "loop-sync: figure-loop.md carries DESIGN_BRIEF/REDESIGN_LICENSED bindings + re-derive step" \
    "grep -qF 'DESIGN_BRIEF' '$FLOOP' && grep -qF 'REDESIGN_LICENSED' '$FLOOP' && grep -qF 're-derive' '$FLOOP'"
chk "loop-sync: figure-loop.md HOLD records held_sha"                      "grep -qF 'held_sha' '$FLOOP'"
chk "loop-sync: figureRunnerGoal binds DESIGN_BRIEF + REDESIGN_LICENSED"   "grep -qF 'REDESIGN_LICENSED = ' '$PFS' && grep -qF 'DESIGN_BRIEF = ' '$PFS'"
chk "loop-sync: figure_converge.py arithmetic untouched (license-agnostic note; round/best modes intact)" \
    "grep -qF 'license-agnostic' '$VDIR/scripts/figure_converge.py' && grep -qF 'def run_round(' '$VDIR/scripts/figure_converge.py' && grep -qF 'def run_best(' '$VDIR/scripts/figure_converge.py' && python3 -c \"import ast; ast.parse(open('$VDIR/scripts/figure_converge.py').read())\""
chk "loop-sync: figure_converge round mode behaves (PASS+0 actionable → stop clean)" \
    "printf '%s' '{\"mode\":\"round\",\"round\":1,\"round_cap\":3,\"effort\":\"normal\",\"no_improvement_rounds\":2,\"history\":[],\"current\":{\"fidelity_verdict\":\"PASS\",\"actionable\":0}}' | python3 '$VDIR/scripts/figure_converge.py' | grep -q '\"stop\": true'"

# ── (4) check-figure-fidelity recalibration ───────────────────────────────────
chk "fidelity: honest data-hugging window licensed (item 3 rewrite)"       "grep -qF 'hugs the occupied data' '$CFF' && grep -qF 'licensed presentation' '$CFF'"
chk "fidelity: bar 0-baseline / point-exclusion still drift"               "grep -qF 'losing its 0 baseline' '$CFF' && grep -qF 'excludes plotted points' '$CFF'"
chk "fidelity: matches-brief section + off-brief→HOLD + brief-licenses-nothing-frozen" \
    "grep -qF 'Judging against an approved DESIGN BRIEF' '$CFF' && grep -qF 'Off-brief structural change' '$CFF' && grep -qF 'licenses NOTHING frozen' '$CFF'"
chk "fidelity: PASS/HOLD/FAIL three-tier intact + design_changes output"   "grep -qF 'PASS, HOLD, or FAIL' '$CFF' && grep -qF 'design_changes' '$CFF'"

# ── (5) L0 wiring RETIRED 2026-08-30 (spec re-aim): 美化 left the auto-research pipeline with the writing
#      engine, so L0 no longer spawns polish-figures, no longer owns a design-briefs gate, and the
#      figure_design_approval checkpoint is gone. /polish-figures survives as a STANDALONE command, which is
#      what the rest of this file covers. Assert the L0 seam is genuinely GONE (not half-removed). ─────────
chk "L0: the retired design-briefs gate is gone from the spec"             "! grep -qF 'gateFigureDesign' '$SPEC' && ! grep -qF 'polishFiguresGoal' '$SPEC' && ! grep -qF 'figures_skipped' '$SPEC'"
chk "L0: the figure_design_approval checkpoint is gone from config"        "python3 -c \"import yaml; c=yaml.safe_load(open('$CFG')); assert 'figure_design_approval' not in c['checkpoints']\""
chk "L0: spec still parses (node --check)"                                 "node --check '$SPEC'"

# ── (6) knobs: the figure knobs left the control panel with the pipeline stage; they live in the
#      paper-polish plugin config now (same rule as the other standalone-command knobs). ──────────────────
chk "key-config: the retired 美化 rows are gone from the panel" \
    "! grep -qF 'figure_redesign_max_rounds' '$KEY' && ! grep -qF 'figure_designer' '$KEY' && ! grep -qF 'figure_design_approval' '$KEY'"
chk "apply_key_config: the retired 美化 mappings are gone" \
    "! grep -qF 'writing-engine.' '$AKC' && ! grep -qF 'surfacing.figure_design_approval' '$AKC'"
chk "PP config: redesign_max_rounds=3 + designer role (opus) + design dimension" \
    "python3 -c \"import yaml; c=yaml.safe_load(open('$VCFG')); f=c['figures']; assert f['redesign_max_rounds']==3; assert f['roles']['designer']['subagent_type']=='claude'; assert f['roles']['designer']['model']; assert f['quality_dimensions'][0]=='design'\""
chk "survey prompt: authors the brief + forces effort>=normal on redesign + absolute paths" \
    "grep -qF 'design_brief' '$SURV' && grep -q 'FORCES effort' '$SURV' && grep -qF 'ABSOLUTE paths' '$SURV'"
chk "visual-QA prompt: design dimension judged FIRST, archetype defects deferred w/o license" \
    "grep -qF \"THE \\\`design\\\` DIMENSION\" '$VQA' && grep -qF 'needs design-brief redesign' '$VQA'"

echo "----"; echo "t57_figure_design: $pass passed, $fail failed"; [ "$fail" = 0 ]
