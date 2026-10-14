#!/usr/bin/env bash
# apply_key_config.sh — propagate the owner control panel (key-config.yaml) into the three
# runtime configs, IN PLACE, preserving every comment.
#
#   bash bin/apply_key_config.sh            # apply: write the values back + print every change
#   bash bin/apply_key_config.sh --check    # dry-run: print what WOULD change, write nothing
#   bash bin/apply_key_config.sh --dry-run  # alias of --check
#
# WHY a control panel: the tunable knobs were scattered across config/config.yaml,
# plugins/paper-polish-ar/config/config.yaml, and plugins/arxiv-recommender-ar/config/config.yaml,
# in three different inline-map dialects (think / inject_thinking / effort) and at different paths.
# key-config.yaml is ONE phase-ordered edit surface; this script routes each value home.
#
# DESIGN: the runtime configs stay the SSOT (standalone /review /polish /arxiv-scout read them
# directly). This script only rewrites VALUES, never structure — so loaders are untouched. It does
# a path-aware, comment-preserving in-place edit (NOT a yaml load+dump, which would destroy the
# heavy documentation comments). System python3 + PyYAML only (no ruamel), matching bin/cfgval.sh.
#
# FAIL-LOUD (config SSOT discipline): a key-config knob whose target path is absent in the target
# file prints "<MISSING PATH: file:a.b.c>" and exits non-zero — drift (a renamed config key) is
# immediately visible, never silently skipped.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="apply"
case "${1:-}" in
  --check|--dry-run) MODE="check" ;;
  "") ;;
  *) echo "usage: apply_key_config.sh [--check|--dry-run]" >&2; exit 2 ;;
esac

ROOT="$ROOT" MODE="$MODE" python3 - <<'PY'
import os, re, sys, yaml

ROOT = os.environ["ROOT"]
DRY  = os.environ["MODE"] == "check"

KEY = os.path.join(ROOT, "key-config.yaml")
TOP = "config/config.yaml"
PP  = "plugins/paper-polish-ar/config/config.yaml"
ARX = "plugins/arxiv-recommender-ar/config/config.yaml"

# ── MAPPING: key-config dotted path -> target(s) in the runtime configs ─────────────────────────
# Scalars:  (kc_path) -> ("scalar", file, yaml_path)
# Models :  (kc_path) -> ("model",  file, parent_yaml_path, dialect), one tuple per fan-out target.
#   dialect picks the think sub-key the target uses:
#     "think" (config/config.yaml) | "inject_thinking" (paper-polish) | "effort" (arxiv)
#     | "model_only" (set model only; ignore the think field — target has no such knob)
# Ordered list so the change report reads top-to-bottom by pipeline phase.
SCALARS = [
    ("weekly-arxiv-ideation.prefetch_pool_size",               ARX, "scout.prefetch_top_k"),
    # scout.rerank_return_n (the Phase 3.6 gate candidate pool) is NOT a panel knob and NOT a config key —
    # since 2026-07-05 lib/config.py derives it at load (min(prefetch, 2*top_n+1)); nothing to write here.
    ("weekly-arxiv-ideation.top_papers_to_ideate_on",          ARX, "scout.top_n_papers"),
    # ideas_per_paper_max / ideate_brainstorm_count / idea_refine_rounds / section_quality_bar RETIRED
    # 2026-07-11 (verified-kill redesign): brainstorm count is DERIVED (2*candidates_per_round+1) by
    # lib/config.py; tier bars are gone — convergence gates on verification artifacts.
    ("weekly-arxiv-ideation.ideation_rounds",                  ARX, "scout.ideation_rounds_max"),
    ("weekly-arxiv-ideation.candidates_per_round",             ARX, "scout.candidates_per_round"),
    ("weekly-arxiv-ideation.probe_fanout",                     ARX, "scout.verify_fanout"),
    ("weekly-arxiv-ideation.survivors_per_paper",              ARX, "scout.survivor_target"),
    ("weekly-arxiv-ideation.extensibility_gate",               ARX, "scout.extensibility_gate"),
    ("weekly-arxiv-ideation.require_working_repo",             ARX, "scout.require_repo"),
    ("weekly-arxiv-ideation.coverage_mode",                    ARX, "scout.coverage_mode"),
    ("weekly-arxiv-ideation.mmr_lambda",                       ARX, "scout.mmr_lambda"),
    ("weekly-arxiv-ideation.claim_gate",                       ARX, "claim_judge.use_claim_judge"),
    ("weekly-arxiv-ideation.claim_gate_action",                ARX, "claim_judge.flag_action"),
    ("weekly-arxiv-ideation.repo_gate",                        ARX, "repo_judge.use_repo_judge"),
    ("weekly-arxiv-ideation.repo_gate_mode",                   ARX, "repo_judge.mode"),
    ("weekly-arxiv-ideation.repo_gate_action",                 ARX, "repo_judge.flag_action"),
    ("weekly-arxiv-ideation.fetch_window_days",                ARX, "ingest.window_days"),
    ("weekly-arxiv-ideation.ingest_method",                    ARX, "io.ingest_method"),
    ("weekly-arxiv-ideation.embedding_backend",                ARX, "prefetch.embedding_backend"),
    ("experiment-review-loop.max_rounds",                      TOP, "max_loop_rounds"),
    ("experiment-review-loop.min_rounds",                      TOP, "min_loop_rounds"),
    ("experiment-review-loop.ship_exit_risk",                  TOP, "loop_gate.exit_risk"),
    ("experiment-review-loop.min_total_citations",             TOP, "drafting.min_total_citations"),
    ("experiment-review-loop.min_intro_citations",             TOP, "drafting.min_intro_citations"),
    ("experiment-review-loop.require_figures",                 TOP, "drafting.require_figures"),
    ("surfacing.gate_adjudicator",                             TOP, "gates.adjudicator"),
    ("surfacing.owner_gates",                                  TOP, "gates.owner_kinds"),
    ("surfacing.default_gates",                                TOP, "gates.default_kinds"),
    ("surfacing.handoff_approval",                             TOP, "checkpoints.handoff_approval"),
    ("surfacing.phase0_surface",                               TOP, "checkpoints.phase0_surface"),
    ("surfacing.literature_surface",                           TOP, "checkpoints.literature_surface"),
    ("surfacing.audit_artifact_surface",                       TOP, "checkpoints.audit_artifact_surface"),
    ("surfacing.orphan_stop_scan",                             TOP, "checkpoints.orphan_stop_scan"),
    # SPEC re-aim 2026-08-30: the post-loop WRITING ENGINE is retired (the run delivers SPEC-FINAL.md, not a
    # manuscript), so writing.* / figures.* / standalone-rewrite knobs are no longer panel knobs. spec_freeze has
    # no toggles at all — only a model tier, mapped in MODELS below. /polish + /polish-figures survive as
    # standalone commands, tuned directly in paper-polish config (polish.* / figures.*), same rule as before.
    ("learning.max_component_reviewers",                       TOP, "learning.max_component_reviewers"),
    ("learning.verify_themes_max",                             TOP, "learning.verify_themes_max"),
    ("learning.proposals_max",                                 TOP, "learning.proposals_max"),
    ("learning.trace_depth",                                   TOP, "learning.trace_depth"),
    # finishing-passes.prose_polish_max_rounds mapping RETIRED 2026-06-30 — the auto-research pipeline has NO prose-polish
    # stage (per-section 精修 merged into rewrite); polish.max_rounds now tunes ONLY the standalone /polish command, so it
    # is no longer an auto-research control-panel knob. standalone-review.{revise_rounds, macro_rounds, supplementary_experiment}
    # mappings RETIRED 2026-06-24 — review.js is diagnose-only; review.{max_review_rounds, max_macro_rounds, experiment.*} no longer exist.
]
MODELS = [
    ("weekly-arxiv-ideation.models.profile_gen",      [(ARX, "profile.phases.profile_gen", "effort")]),
    ("weekly-arxiv-ideation.models.scout_rerank",     [(ARX, "scout.phases.rerank", "effort")]),
    # scout_ideate / scout_refine RETIRED 2026-07-11 → generate/verify/recheck/plan (verified-kill redesign).
    # screen/refute/regenerate/recheck_theory stay plugin-config-only (finer per-role control → edit ARX directly).
    ("weekly-arxiv-ideation.models.scout_generate",   [(ARX, "scout.phases.generate", "effort")]),
    ("weekly-arxiv-ideation.models.scout_verify",     [(ARX, "scout.phases.verify", "effort")]),
    ("weekly-arxiv-ideation.models.scout_recheck",    [(ARX, "scout.phases.recheck", "effort")]),
    ("weekly-arxiv-ideation.models.scout_plan",       [(ARX, "scout.phases.plan", "effort")]),
    ("weekly-arxiv-ideation.models.candidate_judges", [(ARX, "claim_judge.phases.claim_judge", "model_only"),
                                                        (ARX, "repo_judge.phases.repo_judge", "model_only")]),
    ("weekly-arxiv-ideation.models.orchestrator",     [(TOP, "models.ideation_orchestrator", "think")]),
    ("weekly-arxiv-ideation.models.ideation_auditor", [(TOP, "models.ideation_auditor", "think")]),
    ("seed-to-handoff.models.author",                 [(TOP, "models.seed_to_handoff", "think")]),
    ("seed-to-handoff.models.scale_contract_reviewer", [(TOP, "models.scale_contract_reviewer", "think")]),
    ("seed-to-handoff.models.workorder_hardener",     [(TOP, "models.workorder_hardener", "think")]),
    ("experiment-review-loop.models.experiment_worker",     [(TOP, "models.experiment_worker", "think")]),
    ("experiment-review-loop.models.literature_worker",     [(TOP, "models.literature_worker", "think")]),
    ("experiment-review-loop.models.literature_reviewer",   [(TOP, "models.literature_reviewer", "think")]),
    ("experiment-review-loop.models.dossier_writer",        [(TOP, "models.dossier_writer", "think")]),
    ("experiment-review-loop.models.theory_auditor",        [(TOP, "models.theory_auditor", "think")]),
    ("experiment-review-loop.models.independent_verifier",  [(TOP, "models.independent_verifier", "think")]),
    ("experiment-review-loop.models.viability_recommender", [(TOP, "models.viability_recommender", "think")]),
    ("experiment-review-loop.models.audit_artifact_auditor", [(TOP, "models.audit_artifact_auditor", "think")]),
    ("experiment-review-loop.models.rescue",                [(TOP, "models.rescue", "think")]),
    ("experiment-review-loop.models.amplify",               [(TOP, "models.amplify", "think")]),
    ("experiment-review-loop.models.review_orchestrator",   [(TOP, "models.review_orchestrator", "think")]),
    ("experiment-review-loop.models.adversarial_reviewer",  [(PP, "review.roles.reviewer", "inject_thinking")]),
    # NOTE: review.roles.fidelity / reviser / run-auditor were RETIRED 2026-06-24 (review.js is diagnose-only) and
    # comprehender was RETIRED 2026-07-05 (REVIEW-PROTOCOL redesign — owner reads the paper directly), so those
    # knobs are gone. review's experimenter / investigator are not exposed here either — tune them directly in
    # paper-polish config (review.roles.*). adversarial_reviewer also drives the Area Chair (review.js runAreaChair
    # reuses roleOpts('reviewer')), so one knob covers panel + AC.
    # SPEC DELIVERY (spec re-aim 2026-08-30): ONE terminal role replaces the whole writing engine. The retired
    # fan-outs (findings_freezer / paper_architect / paper_writer / paper_editor / paper_freezer /
    # polish_figures_orchestrator, plus the paper-polish reviser/reviewer/fidelity/designer mirrors) are gone
    # with it; the paper-polish roles they wrote to still exist for the STANDALONE /polish + /polish-figures
    # commands and are tuned in that plugin's own config.
    ("spec-delivery.models.spec_freezer",          [(TOP, "models.spec_freezer", "think")]),
    # /learn (阶段⑥): ONE panel knob covers the three reviewer-tier roles; the two judgment seats are separate.
    ("learning.models.learn_reviewers",      [(TOP, "learning.models.evidence_packer", "think"),
                                              (TOP, "learning.models.component_reviewer", "think"),
                                              (TOP, "learning.models.crosscut_reviewer", "think")]),
    ("learning.models.adversarial_verifier", [(TOP, "learning.models.adversarial_verifier", "think")]),
    ("learning.models.synthesizer",          [(TOP, "learning.models.synthesizer", "think")]),
]

# ── key-config source ────────────────────────────────────────────────────────────────────────
with open(KEY, "r", encoding="utf-8") as f:
    KC = yaml.safe_load(f)

def kc_get(path):
    node = KC
    for seg in path.split("."):
        if not isinstance(node, dict) or seg not in node:
            sys.stderr.write(f"key-config.yaml is missing required knob '{path}'.\n")
            sys.exit(3)
        node = node[seg]
    return node

# ── target files loaded once, edited in memory ─────────────────────────────────────────────────
LINES, ORIG = {}, {}
for rel in (TOP, PP, ARX):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as f:
        LINES[rel] = f.readlines()
    ORIG[rel] = list(LINES[rel])

KEY_RE = re.compile(r'(\s*)([\w.\-]+):(?:\s|$)')

def find_line(lines, ypath):
    """Index of the line whose FULL indentation path == ypath, else -1. Path-aware (never a
    leaf-name grep): a duplicate leaf at a different path is disambiguated by its ancestors."""
    target = ypath.split(".")
    stack = []  # (indent, key)
    for i, raw in enumerate(lines):
        s = raw.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        m = KEY_RE.match(s)
        if not m:
            continue
        indent = len(m.group(1)); key = m.group(2)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        if [k for _, k in stack] == target:
            return i
    return -1

def fmt_scalar(v):
    if isinstance(v, bool):  return "true" if v else "false"
    if v is None:            return "null"
    if isinstance(v, list):  return "[" + ", ".join(fmt_scalar(x) for x in v) + "]"   # YAML flow seq, bare tokens (matches runtime exit_risk style)
    return str(v)

def think_token(v, dialect):
    if v is None:            return "~" if dialect == "effort" else "null"
    return str(v)

missing, changes = [], []   # changes: (file, ypath, old, new)

def set_scalar(rel, ypath, value):
    lines = LINES[rel]; i = find_line(lines, ypath)
    if i < 0:
        missing.append(f"{rel}:{ypath}"); return
    raw = lines[i].rstrip("\n")
    pm = re.match(r'(\s*[\w.\-]+:\s*)(.*)$', raw)
    body = pm.group(2)
    cm = re.search(r'(\s+#.*)$', body)
    comment = cm.group(1) if cm else ""
    oldval = body[:len(body) - len(comment)] if comment else body
    newval = fmt_scalar(value)
    if oldval.strip() == newval:
        return
    lines[i] = pm.group(1) + newval + comment + "\n"
    changes.append((rel, ypath, oldval.strip(), newval))

def set_model(rel, parent, dialect, model, think, has_think):
    lines = LINES[rel]; i = find_line(lines, parent)
    if i < 0:
        missing.append(f"{rel}:{parent}"); return
    raw = lines[i]
    # model sub-key: replace the identifier, KEEP the surrounding quotes as-is.
    mm = re.search(r'(\bmodel:\s*)(["\']?)([A-Za-z0-9_.\-\[\]]+)(["\']?)', raw)
    if not mm:
        missing.append(f"{rel}:{parent}.model"); return
    old_model = mm.group(3)
    new = raw[:mm.start(3)] + str(model) + raw[mm.end(3):]
    old_think = new_think = None
    if dialect != "model_only" and has_think:
        sub = dialect  # think | inject_thinking | effort
        tm = re.search(r'(\b' + re.escape(sub) + r':\s*)([^,}\n]+?)(\s*[,}])', new)
        if not tm:
            missing.append(f"{rel}:{parent}.{sub}"); return
        old_think = tm.group(2).strip()
        new_think = think_token(think, dialect)
        new = new[:tm.start(2)] + new_think + new[tm.end(2):]
    if new == raw:
        return
    lines[i] = new
    old_repr = old_model + ("" if old_think is None else f"/{old_think}")
    new_repr = str(model) + ("" if new_think is None else f"/{new_think}")
    changes.append((rel, parent, old_repr, new_repr))

# ── apply ────────────────────────────────────────────────────────────────────────────────────
for kc_path, rel, ypath in SCALARS:
    set_scalar(rel, ypath, kc_get(kc_path))

# rerank_return_n is no longer written here: since 2026-07-05 it is DERIVED at load time by
# plugins/arxiv-recommender-ar/scripts/lib/config.py (min(prefetch_top_k, 2*top_n_papers); 2026-09-19 修订 #11) —
# there is no yaml key for it, so there is nothing for the panel to patch.

for kc_path, targets in MODELS:
    src = kc_get(kc_path)
    if not isinstance(src, dict) or "model" not in src:
        sys.stderr.write(f"key-config.yaml knob '{kc_path}' must be a map with a 'model' key.\n")
        sys.exit(3)
    has_think = "think" in src
    for rel, parent, dialect in targets:
        set_model(rel, parent, dialect, src["model"], src.get("think"), has_think)

# ── fail-loud on any unresolved target path (drift) ────────────────────────────────────────────
if missing:
    sys.stderr.write("FAIL: target path(s) not found in the runtime configs (config drift?):\n")
    for m in missing:
        sys.stderr.write(f"  <MISSING PATH: {m}>\n")
    sys.exit(1)

# ── report + write ─────────────────────────────────────────────────────────────────────────────
label = "WOULD CHANGE" if DRY else "CHANGED"
if not changes:
    print("all values already in sync — nothing to do (unchanged).")
else:
    for rel, ypath, old, new in changes:
        print(f"  [{label}] {rel}  {ypath}: {old} -> {new}")
    if not DRY:
        touched = sorted({rel for rel, *_ in changes})
        for rel in touched:
            if LINES[rel] != ORIG[rel]:
                with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
                    f.writelines(LINES[rel])
        print(f"\nwrote {len(changes)} change(s) across {len(touched)} file(s).")
    else:
        print(f"\n--check: {len(changes)} change(s) pending; nothing written.")
PY
