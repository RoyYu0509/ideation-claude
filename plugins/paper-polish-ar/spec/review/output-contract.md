<!-- review/output-contract.md — the MECHANICAL half of the review protocol. Every shape here is executed
     EXACTLY (the [[MECH]] tier migrated verbatim-in-substance from the retired spec/review.js; git history
     of that file is the provenance). The REVIEW OWNER judges freely everywhere else; here it copies. -->

# Review output contract

**Path convention**: every relative path in this contract resolves against the PAPER-POLISH plugin root
(the directory holding this `spec/` — NOT the auto-research root the in-loop L1 was spawned from).

## 1. Run scaffolding (in execution order)

- **Manuscript**: resolve via `scripts/resolve_manuscript.py --master <arg> --section-order <order>`; on
  error, pick the real `\documentclass` master from the candidates
  (`--pick-master-from '<JSON array of candidate paths>'` → `{master}` or null) and re-resolve once.
  Never fabricate a path.
- **Venue** (calling shapes for §0): `scripts/venue_resolve.py resolve --require-review-kit --root
  <pluginRoot> [--venue <rel>] [--field <f>]` → a discriminated pack `{status, label, dir, profile,
  reviewDir, coreDir, coreProfile}` — a non-null `coreProfile` means this venue is an OVERLAY that
  COMPOSES over a shared CORE (load and apply BOTH: core contract + overlay deltas, which override).
  `list --require-review-kit --root <pluginRoot>` → `{prepared:[...]}` (the picker's universe).
- **Typeset PDF** (the ladder — pass ALL SEVEN flags; a mis-call silently degrades every reviewer to
  .tex): `bash scripts/resolve_comprehension_pdf.sh --master <master> --paper-dir <paperDir>
  --project-dir <proj> --git-root <gitRoot> --ref <base sha> --format <format> --plugin-root
  <pluginRoot>` → prints the PDF path on stdout (empty = none; only then read the .tex).
- **Manifest (ARM)**: pipe `{mode:"review", root, master, manuscripts, format, proj}` to
  `scripts/build_manifest.py` → writes `<proj>/.polish/fidelity-manifest.json`. The pre-edit hook now
  denies any data/.bib/figure edit and any manuscript overwrite for the whole run.
- **Git** [STANDALONE only]: `git init` the paper dir if needed; create branch `review-<epoch>` from the
  current HEAD; after section scoping, `git add` ONLY the in-scope files and commit
  `review: base (untouched draft)`; record that sha as `base`. The manuscript body on this branch stays
  byte-identical to base — the branch carries only the read-only artifacts below.
  [IN-LOOP]: no new branch — the workspace repos already exist; record `base` = current HEAD of the paper
  repo and commit artifacts onto the current branch.
- **Section scope**: `planned` = section_order ∩ present ∩ ¬sections_to_skip (target `all` unless the
  request names one section).

## 2. Artifacts (what, where, exact shape)

| Artifact | Path | Content |
|---|---|---|
| Paper model | `<paperDir>/paper-model.md` + machine copy `<proj>/.polish/paper-model.json` | authored by the OWNER from its own full read; PAPER_MODEL_SCHEMA below; committed |
| Verdicts | `<paperDir>/review-verdicts.md` | `JSON.stringify({round, panel, ac}, null, 2)` — `round` = the loop round this review ran in ([IN-LOOP]: the round number your goal names; [STANDALONE]: `1` — one diagnose pass), `panel` = the reviewers' returns VERBATIM (never re-summarized), `ac` = YOUR synthesis object (SYNTHESIS_SCHEMA; the key is named `ac` for oracle compatibility — the `verify_panel` code looks it up by that exact top-level key). Committed. The oracle expects `round` == the round it verifies (freshness — a stale file must not prove this round), `panel[]` with ≥2 DISTINCT non-empty `persona` strings and an `ac` carrying the meta-review; reject/major findings must carry quotes (RC-2b) |
| Report | `<paperDir>/review-report.md` | REPORT SHAPE below, assembled from recorded objects only; committed |
| Task files [STANDALONE] | `<paperDir>/TASK_SPEC.md, TASK_PLAN.md, TASK_RUNBOOK.md, TASK_STATUS.md, PAPER_REVISION_PLAN.md` | per the `task-ledger` skill, written at plan time, TASK_STATUS refreshed after synthesis and at emit; committed. This is ONE diagnose pass — never describe rounds |
| HANDOFF export | at **wsRoot = the PARENT of the paper dir** (`dirname(paperDir)`) — the outer loop scans `<WS>/HANDOFF-*.md` at depth 1, so an export NEVER goes under `<paperDir>/`. **Filenames are seat-split**: [STANDALONE] ONE aggregate `<wsRoot>/HANDOFF-<paperBase>.md`; [IN-LOOP] one file PER classified demand, named per REVIEW-L0-CONTRACT (`HANDOFF-redesign-<segId>.md` / `HANDOFF-redesign-contribution.md` / `HANDOFF-<name>.md`) — **the filename IS the outer loop's routing**; the aggregate name would mis-route a redesign as an additive exhibit | rendered via the `experimenter` role from `spec/spawn-prompts/review-handoff.md` + the exported work items + your paper-model preamble; HANDOFF_DOC_SCHEMA. On render failure, write the raw work items as a fallback body — never emit nothing |
| Research protocol | `<paperDir>/REVIEW-EXPERIMENT-PROTOCOL.md` | copy of `assets/review-experiment-protocol.md` (review-experiment flavored — DISTINCT from the auto-research root's WS-root RESEARCH-PROTOCOL.md; renamed 2026-07-06 so the twins can never be cross-read) |
| Commits | each artifact in ITS OWN repo | the WS-root repo tracks the HANDOFF; the paper repo tracks everything else (they are separate git repos — an add in one cannot reach the other). Always `git add -- <named file>`; fail-soft when wsRoot is not a repo (standalone) |

**Advisory sensors (run at emit, surfaced, never acted on):**
- *Sacred-token dilution*: for every `sacred_identity` token in your paper model, `git grep -F` it across
  the in-scope files at `base` — a pinned token appearing NOWHERE in the manuscript is a
  comprehension/paper mismatch; surface it as `pinned_token_absent` (severity major) in the report.
- *Dangling citations*: pipe `{root, files}` to `scripts/lint_citations.py`; report `[{key, files}]` of
  `\cite`/`[@key]` with no defined .bib/`\bibitem` entry. Advisory — never auto-fix, never block emit.
- **Disarm**: `rm -f <proj>/.polish/fidelity-manifest.json` (last act before the final summary/return).

## 3. Schemas (structured-output contracts for every spawned role + your own synthesis)

```js
PAPER_MODEL_SCHEMA = { type:'object', required:['main_method','existing_validation'], properties:{
  problem:{type:'string'}, gap:{type:'string'},
  main_method:{type:'string'},                       // explicit — the thing a reviewer must not misread
  primary_contribution:{ type:'object', required:['what'], properties:{
    what:{type:'string'}, why_novel:{type:'string'},
    sacred_identity:{type:'array', items:{type:'string'}} }},  // tokens NEVER to be renamed/downgraded
  supporting_claims:{type:'array', items:{type:'string'}},     // secondary, scopeable to the evidence
  contributions:{type:'array', items:{type:'string'}},
  evidence_map:{type:'array', items:{type:'object', required:['claim'], properties:{
    claim:{type:'string'}, backing:{type:'string'}, location:{type:'string'} }}},
  existing_validation:{type:'array', items:{type:'object', required:['kind','what'], properties:{
    kind:{enum:['baseline','ablation','convergence','error_analysis','sensitivity','robustness','other']},
    what:{type:'string'}, location:{type:'string'} }}},
  key_terms_notation:{type:'array', items:{type:'string'}},
  read_source:{enum:['image_pdf','tex_fallback']} } }

REVIEWER_SCHEMA = { type:'object', required:['persona','axes_covered','recommendation','findings'], properties:{
  persona:{type:'string'},   // UNIQUE per reviewer (e.g. "R2 — <profile name>"); the oracle counts DISTINCT personas
  lead_axis:{type:'string'},
  axes_covered:{type:'array', items:{type:'string'}},
  recommendation:{enum:['reject','major_revision','minor_revision','accept']},
  findings:{type:'array', items:{type:'object', required:['axis','severity','problem','fix_kind'], properties:{
    axis:{type:'string'}, severity:{enum:['reject','major','minor']},
    claim:{type:'string'}, quote:{type:'string'}, location:{type:'string'},   // quote+location MANDATORY for reject/major (grounding floor)
    problem:{type:'string'}, attack_class:{type:'string'},                    // which attack-classes.md class the deep thread pursued
    fix_kind:{enum:['self_fixable','needs_author']} }}},
  deep_thread:{type:'string'},                       // the single most lethal thread this reviewer sank into
  summary:{type:'string'} } }
// The mechanical matrices (section_structure / caption_axis_fidelity / experiment_coverage /
// literature_coverage) are NOT reviewer fields — they belong to the checklist pass (review/checklist-pass.md).

SYNTHESIS_SCHEMA = { type:'object', required:['meta_review','punch_list'], properties:{   // authored by the OWNER
  meta_review:{type:'string'},
  overall_risk:{enum:['reject','major_revision','minor_revision','accept']},
  top_strengthening_directions:{type:'array', items:{type:'string'}},          // 3-5, ranked
  punch_list:{type:'array', items:{type:'object',
    required:['id','axis','severity','problem','fix_kind','proposed_fix'], properties:{
    id:{type:'string'}, axis:{type:'string'}, severity:{enum:['reject','major','minor']},
    disposition_tier:{enum:['must_fix','strengthen','keep_as_is']},
    claim:{type:'string'}, quote:{type:'string'}, location:{type:'string'}, problem:{type:'string'},
    evidence:{type:'string'},                       // which reviewer(s) / checklist row
    lethality:{enum:['fatal','survivable','unsure']},
    fix_kind:{enum:['self_fixable','needs_author']},
    proposed_fix:{type:'string'},                   // SEMANTIC, never lexical — say WHICH claim changes to WHAT; never a find-replace on a sacred token
    merge_note:{type:'string'},                     // dedupe / dismissed-false-rejection note
    referent:{enum:['definition_identity','guarantee_claim','other']},
    do_not_touch:{type:'string'},                   // sacred name(s) no fix may rename or weaken
    remediation_type:{enum:['theory_proof','missing_experiment','claim_strength','originality','mechanism','bias_confound','presentation','other']},
    author_options:{type:'array', items:{type:'object', required:['label'], properties:{
      label:{type:'string'}, description:{type:'string'},
      executor_kind:{enum:['experiment','author','record']} }}} }}} } }
// A proof/derivation demand is an `author` option (the author constructs it) — NEVER `experiment`.

INVESTIGATION_SCHEMA = { type:'object', required:['findings','recommendation'], properties:{
  findings:{type:'string'}, sources_consulted:{type:'array', items:{type:'string'}},
  concern_holds:{enum:['holds','does_not_hold','partial','unsure']},
  lethality:{enum:['fatal','survivable','unsure']},
  recommendation:{type:'string'},                   // advisory — the human disposes
  recommended_options:{type:'array', items:{type:'object', required:['label'], properties:{
    label:{type:'string'}, description:{type:'string'},
    executor_kind:{enum:['experiment','author','record']} }}} } }

HANDOFF_DOC_SCHEMA = { type:'object', required:['markdown'], properties:{ markdown:{type:'string'} } }
```

## 4. Escalation registry (the CLOSED disposition set — nothing else exists)

| value | executor_kind | meaning |
|---|---|---|
| `run_exp` | experiment | EXPORT the experiment-demand into the HANDOFF (review designs, never runs) |
| `author` | author | the author handles it themselves, outside the tool |
| `keep` | record | record the concern in the report; no further action |
| `worth_it` | kill | **fatal items only** — escalate "is this worth finishing?" to the worth-it/viability path (which researches a rescue FIRST; kill is the residual of a failed rescue). Review only SURFACES this; it never enacts a kill |

Menu-building rules (per item):
- Source priority: the investigator's `recommended_options` (it just researched THIS item) → else the
  synthesis `author_options` → else the FLOOR `{author, keep}`. Validate every option against the
  registry; an executor_kind outside {experiment, author, record} is dropped.
- **Disposition prior**: a reject/major item on the experiments axis that the investigator did NOT judge
  survivable gets the `run_exp` option ensured, FIRST, and marked recommended.
- **Strategic-kill 格**: `lethality: fatal` → ensure the `worth_it` option is present (drop a `keep` to
  stay ≤4 options).
- A MINOR needs_author item is RECORDED (`recorded_suggestion`), never asked, never escalated.
- Every answer is recorded verbatim with its classified value; a freeform answer is classified by the
  OWNER into the closed set (`nothing actionable` → `keep`). An exported item enqueues ONE handoff work
  item `{work_id: EXP-n, punch_item_id, severity, axis, paper_claim, paper_location, reviewer_demand,
  proposed_fix, remediation_type}` — deduped by punch_item_id.

## 5. Report shape (`review-report.md` — JSON, assembled from RECORDED objects only)

`{ venue, branch, base, diagnose_only: true, paper_model, pinned_contribution, overall_risk, meta_review,
top_strengthening_directions, checklist (the checklist pass's four matrices, verbatim), reviewers (the
panel array), final_punch_list, dangling_citations, surfaced_for_author, escalations, handoffs_exported }`

Emit-honesty: every escalation entry carries the author's literal recorded answer; no field asserts a
confirmation that was not made; the report is a diagnosis of an UNCHANGED manuscript.

## 6. Return [IN-LOOP]

Per REVIEW-L0-CONTRACT.md: metrics `{overall_risk, new_handoff_items}`, artifacts
`[<paperDir>/review-report.md, <wsRoot>/HANDOFF-*.md...]`, `escalations[]` for every author-only seam.
