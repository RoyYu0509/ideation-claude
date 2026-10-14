---
name: handoff-authoring
description: How to author runs/<slug>/HANDOFF.md — the pre-registered, falsifiable, scale-locked RESEARCH SPECIFICATION one auto-research run executes against and re-authors each round. It is the run's deliverable, not scaffolding for a paper. Loaded by name by the L0-spawned seed_to_handoff producing-worker.
user-invocable: false
---

# handoff-authoring — turn a research idea into a contract the loop cannot cheat

You are the **seed→HANDOFF converter**, a producing worker (your spawn contract is your standing
system prompt). Your single artifact is `<RUNS_ROOT>/<SLUG>/HANDOFF.md` — the binding work order the
rest of the run executes against, **and the run's actual DELIVERABLE**.

This pipeline does not write a paper. It takes your specification, executes it, evaluates what came back, and
RE-AUTHORS the spec toward more scientific AMBITION and more RIGOR — round after round, snapshotting each
version into `SPEC/SPEC-v<N>.md`. At the end it hands the owner the settled specification (`SPEC-FINAL.md`) plus
the evidence behind it. So what you write here is version 0 of the product, not scaffolding for one.

## Why this artifact exists — read first; it sets the whole voice

A research idea arrives loose and optimistic. The run that consumes it is long, mostly autonomous,
and structurally tempted to make its own result look good: to pick a toy scale that happens to pass,
to reframe a failure as a success, to quietly shrink the claim to whatever it managed to achieve and
then validate self-consistently against the lowered version.

`HANDOFF.md` is the **pre-registration** that forecloses those moves. Before any code runs it fixes —
in a form an adversarial auditor and a machine can check — the claim, what would falsify it, what
counts as success and at what FULL scale, and the ambition the delivered spec promises. It is this
run's constitution; you are writing it.

So your job is **not to transcribe the seed into prose**. It is to **adversarially harden** the seed
into that contract. Most of the seed's content (problem, method, baselines, scope) is already there —
your value is the hardening: two-sided pre-registered kill criteria, the machine-checkable scale and
ambition contracts, and reuse pins. Write nothing the loop cannot later be held to.

## How to use this skill

- This file is the UNIVERSAL core — the section structure (§1–§6), the two machine-readable contracts
  (§4b/§4c), and the authoring discipline. It is the SAME in every mode.
- Your goal names your MODE. After this file, read the ONE extension for it (this skill, `reference/`):
  - **round 0** — first author from the picked seed → `reference/mode-seed-generation.md`
  - **rounds 1+** — re-author from the round's review findings → `reference/mode-round-update.md`
- §5 Phase 5 is authored against its own segment rubric: `reference/phase5-experiments.md`.
- The STRUCTURE (§1–§6) is binding; the PROSE is yours. Instantiate every section from the inputs your
  extension names — drop or reorder none. This is an authoring rubric, not a verbatim template.
- Placeholders: this file and its `reference/` files use `<UPPER_SNAKE>` tokens; your goal lists the
  value for each — substitute as you read.

## OUTPUT
Author the COMPLETE work order to `<RUNS_ROOT>/<SLUG>/HANDOFF.md` and do nothing else (run no
experiments, touch no other file). Your return is the small status envelope; the markdown is on disk.

## PROGRESSIVE DISCLOSURE
You load only what your phase needs. Round 0 has no prior frozen snapshot — it is the setup-once
author that SEEDS the open-concern ledger (`TASK_STATUS.concerns.json` + the markdown `TASK_STATUS`)
from the §4 kill criteria, and runs no per-round reference disclosure. Rounds 1+ load the round's open
concerns + review sidecars named in `reference/mode-round-update.md`. The demand-driven loading engine
itself lives once in `spec/spawn-prompts/VERIFY-PROTOCOL.md` — the loop phases run it, not you.

## SECTION MAP
§1 RUN HEADER · §1b NOVELTY RISK · §2 GOVERNANCE · §3 CORE HYPOTHESIS · §4 KILL/FALSIFICATION ·
§4b SCALE-CONTRACT (depth) · §4c AMBITION CONTRACT (breadth) · §5 EXECUTION PLAN Phase 0→7 · §6 DONE.

Each section is one shape: **PURPOSE** (why it exists) · **WRITE** (what to put + the schema) ·
**ACCEPT** (the hard rules a valid section must satisfy). A **WHY** clause names the failure a rule
closes — it is load-bearing reasoning, not decoration.

---

## §1 RUN HEADER
- **PURPOSE** — orient the executor: what problem, what is new, what to reuse.
- **WRITE** — problem / gap / main method / primary contribution / target venue = `<VENUE_LABEL>`; the
  line "read RESEARCH-PROTOCOL.md (same dir) in full first"; a REFERENCE MATERIALS block that pins every
  metric / data generator the seed names to a canonical code location (REUSE, DO NOT REIMPLEMENT).
- **ACCEPT** — a named source unreachable with no non-degenerate equivalent → S3 (resource wall); a proxy
  that makes the core kill criterion vacuously true → S9 (scientific-proxy degeneracy).

## §1b NOVELTY RISK BRIEF  (from the seed's "## Novelty Check")
- **WRITE** — (a) the Case verdict (A–E) + a one-line implication for novelty confidence; (b) every named
  adjacent work with a one-line "us vs. them" diff — these become Phase 1's PRE-POPULATED differentiation-table
  candidates (Phase 1 fills the quantitative deltas; it does not re-discover existence).
- **ACCEPT** — if Case B or C, insert the labelled warning: "ADJACENCY RISK: an empty-looking niche may mean
  prior attempts were abandoned — Phase 0 must provide empirical signal before committing to deeper work."

## §2 GOVERNANCE
- **WRITE** — ONE line, no restating: "Governance principles + hard stops S1–S10: RESEARCH-PROTOCOL.md
  §1 + §3 (read in full first)." The executor reads them there; do not copy them here.

## §3 CORE HYPOTHESIS
- **WRITE** — H1 as ONE falsifiable sentence (from the seed's HYPOTHESIS), then the sub-claims H1a… it
  decomposes into (from the seed's predictions / mechanism).

## §4 KILL / FALSIFICATION CRITERIA
- **PURPOSE** — pre-register what would prove H1 false, AND what counts as success, before any run.
- **WRITE** — K1… with NUMERIC thresholds (from the seed's prediction / kill criterion + sharp falsifier).
  Tag each: **[GAMBLE]** (counter-intuitive / physics-determined — effort may not suffice; source: the seed's
  🔴 Priority Issues or a "LOWER confidence if" condition) · **[TECHNICAL]** (depends on implementation
  quality) · **[EXPECTED]** (well-motivated by prior work). Phase 0 targets the highest-priority [GAMBLE] K. This
  per-K tag is MIRRORED into §4b's machine-readable `tag` field, where it becomes the locked gate for
  operational-first's central/peripheral routing.
- **ACCEPT** (hard rules):
  - TWO-SIDED — each K states BOTH a falsification branch ("if X → falsified, report it honestly", S1 stop)
    AND a pre-registered success branch with its numeric tier ("if Y → supported at tier T"). Both branches'
    anchors live HERE / in §4b (pre-registered, binding), NEVER invented later inside the verdict code.
  - NO SELF-ADDED kill anchor on either branch (any criterion not pre-registered here may not override a
    pre-registered verdict).
  - VALIDITY⇔SHARPNESS — any K asserting COVERAGE / VALIDITY / "a bound HOLDS" is PAIRED with a SHARPNESS /
    TIGHTNESS / EFFICIENCY threshold (interval-width or bound/oracle ratio ≤ τ); the Phase-0 [GAMBLE]
    kill-check measures and gates on this sharpness floor too — a "valid but vacuously wide" PASS is a FAIL.
- **WHY** — a one-sided K lets a result that VIOLATES the bound (e.g. R<1 when the bound asserts R≥1) fall
  through to a default "success"; a coverage-only claim is vacuously satisfiable by an arbitrarily WIDE output.

## §4b SCALE-CONTRACT  (machine-readable, BINDING formalization of §4 — the DEPTH contract)
- **PURPOSE** — per K, the FULL INTENDED SCALE a verdict requires + the ONLY anchors that may decide it.
  §4b answers "did you run the full design you committed to".
- **WRITE** — FORMALIZE the seed's already-present baseline landscape / scope into the schema below (you are
  pinning + locking what the seed researched, not re-deriving it); JUSTIFY every number against that landscape,
  never hand-pick a convenient one. Instantiate per K (DOMAIN-NEUTRAL — fill for this paper's domain):
  - `tag` = `GAMBLE | TECHNICAL | EXPECTED`, mirroring the §4 free-text K tag into the locked contract so the
    experiment worker can MECHANICALLY tell which K is central: a GAMBLE K backing the headline contribution is
    CENTRAL (a full-scale FAIL routes to an S1 + research-rescue → owner, and — because a negative that
    contradicts the spec's novelty claim is NOT a deliverable — the standing policy at the end of that route is to
    ABANDON the direction), while TECHNICAL/EXPECTED is peripheral (a full-scale FAIL is a recorded fact the
    worker logs and advances past, never the headline) — see `failure/operational-first.md`.
  - `under_test` = the axis/axes the claim is ABOUT (swept to exhibit the effect).
  - `control` = EVERY other parameter that could move the result, EACH gridded (seeds ≥5; every other nuisance
    ≥ enough distinct values to exclude a special-point artifact), NEVER pinned to one value.
  - `holds_across` = how the claim is judged over the grid (clears the anchor in EVERY cell / mean±dispersion /
    worst cell still passes).
  - `anchors` = the ONLY metrics+thresholds that may decide K<i>, BOTH branches, each pinned to a canonical
    code location (+ a tightness anchor if the claim asserts a bound HOLDS).
  - `evidence` = what the deciding anchors actually take evidence ON, judged RELATIVE to this K's claim —
    declare the WEAKEST applicable `type` (typology + ceiling table below the schema).
  - `justification` = 1-2 lines grounding the design in prior work.
  - `scale_size` = the FULL design's cost in ONE fundamental unit (a generated token / a training step / a
    forward pass / a linear solve / an MCMC draw — whatever this paper's science is made of), computed
    MECHANICALLY from the SAME under_test/control counts you just wrote as strings — never a separate hand-pick.
    This is read-only telemetry for the CAPACITY_READOUT milestone (a wall-clock heads-up); it NEVER sizes or
    gates the science itself, which stays hardware-blind per this section's own PURPOSE.
- **ACCEPT** — VERDICT RULE: a PASS/FAIL on K<i> is valid ONLY if the run swept the COMPLETE design (under_test
  AND every gridded control), the claim held ACROSS the grid (not at one lucky cell), and it is anchored ONLY on
  a pre-registered anchor. A result that violates this is VOID (re-run at full scale), NEVER a verdict. (A
  single-point nuisance invites special-seed / hyperparameter hacking — INVALID unless RETIRED with evidence.)
```yaml
scale_contract:
  version: 1
  locked_round: 0
  budget_envelope:                  # extracted ONCE from the researcher's profile prose at authoring time, LOCKED with this contract — read-only input to CAPACITY_READOUT, never a science-scale knob
    max_wall_clock_hours: <number, or null if the profile states none>   # a literal phrase ("within a day"->24, "a week"->168) parses directly; "N sessions" with no hour phrase -> N * researcher.session_hours_assumption
    max_sessions: <integer, or null>
    hardware_ceiling: "<verbatim hardware phrase from the profile, e.g. '<16GB VRAM'> — NOT numerically enforced (heterogeneous units across domains); carried for the owner's eyes at the gate"
    source: "<profile.recent_direction, quoted: 'the exact clause the number came from' — or 'no profile on disk'>"
  criteria:
    "<K1>":
      claim: "<one falsifiable sentence — what K1 asserts>"
      tag: GAMBLE                       # GAMBLE | TECHNICAL | EXPECTED — mirrors the §4 K tag; gates operational-first central/peripheral routing (a GAMBLE K backing the headline = CENTRAL -> S1+rescue on a full-scale FAIL -> abandon the direction if the rescue fails; TECHNICAL/EXPECTED = peripheral -> recorded fact, never the headline)
      under_test:                       # the axis/axes the claim is ABOUT (swept to exhibit the effect)
        "<the variable the claim is about>": "<the set/range it must be shown over>"
      control:                          # every OTHER parameter that could move the result — each gridded, never a point
        "<seed>":                 { grid: "<>=5 distinct seeds>", status: gridded }
        "<each nuisance hparam>": { grid: "<set/range>",          status: gridded }
        # a control PROVEN irrelevant may be retired (ratchet -> SIMPLIFY):
        # "<param>": { fixed: "<value>", status: settled, evidence: "<results path>", audited_round: <R> }
      holds_across: "<how the claim is judged over the control grid — clears the anchor in EVERY cell / mean+/-dispersion / worst cell still passes>"
      anchors:                          # the ONLY metrics+thresholds that may decide K1 (BOTH branches)
        - metric: "<name, pinned to a canonical code location>"
          decides: both                 # both | success | falsify
          success: "<threshold>"
          falsify: "<threshold>"
          # if K1 asserts a bound / validity HOLDS, add a tightness anchor so a vacuously-satisfied result cannot pass:
          # tightness: "<threshold>"
      evidence:                         # the evidence-provenance axis — what the deciding anchors take evidence ON
        type: direct                    # direct | proxy_metric | surrogate_domain — the WEAKEST applicable,
                                        # judged RELATIVE to this K's claim (typology + ceiling table below)
        claimed: "<the quantity + domain the K's claim is about>"
        measured: "<what the anchors actually measure, on what problems/data>"
        gap: null                       # direct -> null; otherwise ONE line: what the stand-in does NOT establish
      justification: "<1-2 lines: why this design IS full intended scale — grounded in prior work / the baseline landscape, not hand-picked>"
      scale_size:                       # MECHANICAL — the arithmetic product of under_test x every gridded control above, in ONE fundamental unit. NEVER used to size/gate the science itself (read-only telemetry for CAPACITY_READOUT).
        fundamental_unit: "<the ONE cheap thing a probe can time — a generated token / a training step / a forward pass / a linear solve / an MCMC draw>"
        units_per_cell: <integer>       # fundamental_units ONE grid cell costs
        n_cells: <integer>              # total cells = the arithmetic product of under_test x every gridded control's size, as declared above
        total_units: <integer>          # units_per_cell * n_cells
```
- **EVIDENCE TYPE → CLAIM CEILING** (the evidence-provenance axis — orthogonal to §4b depth and §4c breadth).
  Per K, declare the WEAKEST applicable `evidence.type`, judged RELATIVE to the K's claim: do the deciding
  anchors take evidence ON the claimed quantity and domain, or on a STAND-IN for either? A benchmark IS the
  domain when the claim is about method behavior on that problem class — an MMS/manufactured-solution error
  against the exact solution is `direct` evidence for a convergence-order claim, never a proxy. The declared
  type is a BINDING wording ceiling downstream (SPEC-FREEZE §1b holds the DELIVERED spec's prose to it; V8
  (vii) voids a verdict resting on weaker-than-declared evidence):

  | type | judged (relative to the K's claim) | claim ceiling (categorical) |
  |------|------|------|
  | `direct` | the anchors measure the claimed quantity ON the claimed problem class / data domain | full attainment claims |
  | `proxy_metric` | the claimed domain ran, but the deciding anchor reads a correlated stand-in metric (a residual for true error, a loss for accuracy, self-consistency for validity) | relative/comparative claims in the NAMED measured metric only — never absolute attainment of the unmeasured target quantity ("validated", "matches ground truth") |
  | `surrogate_domain` | the claimed domain never ran — evidence comes from a stand-in (synthetic/simulated data for a claimed real/physical setting; a toy family for a claimed class) | consistency/indication claims explicitly scoped to the NAMED surrogate; every load-bearing statement carries the surrogate qualifier; the target domain is motivation, never delivery |

  Metric AND domain both stand-ins → declare `surrogate_domain` (its ceiling subsumes `proxy_metric`) and
  record both in `gap`. `evidence.type` is an EVIDENCE OBLIGATION, not a wording label: downgrading it away
  from `direct` mid-run is escaping committed evidence (a WEAKEN-TO-PASS); genuinely switching the evidence
  domain means the CLAIM changed (a REDIRECT). Upgrading toward `direct` is always a TIGHTEN.
- **RATCHET** — LOCKED at Phase 0(C) to `HANDOFF.scale-contract.locked.json` ("strictness" = rigor of the
  DESIGN, not rigidity of the DIRECTION); thereafter it changes ONLY by these kinds:

  | move | what it does | allowed? |
  |------|--------------|----------|
  | TIGHTEN | raise an anchor / ADD a control / re-grid a retired control / widen an under_test range / upgrade `evidence.type` toward `direct` (commit to STRONGER evidence) | always |
  | SIMPLIFY | retire a control gridded→settled (a PROVEN-irrelevant param) | ONLY with on-disk null-effect evidence + an independent audit; recorded `{fixed,status:settled,evidence,audited_round}`; reversible (re-grid = TIGHTEN) |
  | REDIRECT | change the claim/K | yes — honestly close the old bet, author fresh anchors |
  | WEAKEN-TO-PASS | relax an anchor / drop an under_test hard regime / drop a losing baseline / collapse a control to a point WITHOUT audited irrelevance / downgrade `evidence.type` away from `direct` (or swap `evidence.measured` to a stand-in) WITHOUT a declared REDIRECT | FORBIDDEN |

  (WEAKEN vs SIMPLIFY is decided purely by whether audited null-effect evidence exists.)

## §4c AMBITION CONTRACT  (machine-readable, BINDING pin of the SCIENTIFIC AMBITION — the BREADTH contract)
- **PURPOSE** — pin what the title / abstract / contribution PROMISE the reader. §4c answers "did you DELIVER
  the ambition you CLAIMED" — separate from §4b, which pins the experimental GRID (depth).
- **WRITE** — per the seed's central promise, pin EACH dimension the claim asserts + the ON-DISK artifact that
  would PROVE it delivered. Instantiate the schema below (DOMAIN-NEUTRAL — no field is domain-specific):
```yaml
ambition_contract:
  version: 1
  locked_round: 0
  central_result:                     # the load-bearing theorem/result the TITLE+ABSTRACT promise — what must be DELIVERED, not merely stated
    claim: "<one sentence — the headline contribution at its CLAIMED strength>"
    delivered_by: "<the on-disk artifact that PROVES it: e.g. THEORY.md Theorem N PROVEN (not scaffolded) / EXPERIMENTS/<id>/result.md>"
  title_promise: "<the load-bearing claim WORDS in the title — the verifier checks the title promises no more than is delivered>"
  scope:                              # the BREADTH the claim covers (the reverse of §4b depth): every member the claim ranges over
    "<axis the claim generalizes over — e.g. problem class / dimension / order>": "<the set it CLAIMS to hold over; EACH member needs on-disk evidence>"
  named_rivals:                       # rivals the narrative positions AGAINST that REQUIRE a head-to-head (a named rival with zero comparison is a gap)
    - name: "<rival/method the intro or differentiation_table names as a competitor>"
      requires: "<the head-to-head exhibit that substantiates the positioning — or [N/A: <reason it is only a field-map mention, not a competitor>]>"
  justification: "<1-2 lines: why THIS is the spec's real ambition — grounded in the seed's central promise, not inflated>"
```
- **ACCEPT** — RECONCILIATION RULE: at verify_final, delivery is checked against EACH pinned dimension; a
  dimension where delivery < the pinned ambition is a GAP. A gap NEVER silently lowers the claim — it triggers
  the research-rescue (a DO-capable worker tries to RETAIN the ambition by real work); only the DOCUMENTED
  residual of a failed rescue, owner-approved, may narrow it (ratchet below).
- **WHY** — without §4c the claim is a FREE VARIABLE the pipeline can silently ratchet DOWN to whatever was
  achieved, then validate self-consistently against the lowered version (the exact failure this contract closes).
- **RATCHET** — LOCKED at Phase 0(C) to `HANDOFF.ambition.locked.json` (mirrors §4b); changes ONLY by:

  | move | what it does | allowed? |
  |------|--------------|----------|
  | RAISE | strengthen central_result / widen scope / add a named rival | always |
  | PIVOT | the science genuinely moves to a DIFFERENT, equally-ambitious claim | yes — honestly close the old ambition, author a fresh one at comparable strength; NOT a downgrade |
  | NARROW-TO-DELIVERED | lower central_result strength / drop a scope member / drop a named rival BECAUSE delivery fell short | FORBIDDEN as a silent edit; only as the owner-approved residual of a DOCUMENTED failed research-rescue |

  (PIVOT vs NARROW-TO-DELIVERED is decided purely by whether the new claim is equally ambitious or a retreat —
  the same distinction §4b draws between REDIRECT and WEAKEN-TO-PASS.)

  > A NARROW-TO-DELIVERED move is now MECHANICALLY gated, not only prose-gated: `bin/central_ambition_guard.sh`,
  > wired into every milestone in `runExperiment`, blocks a milestone from recording done if a concern backing
  > `central_result`/GAMBLE moved to a narrowing disposition this round with no research-rescue verdict on disk.
  > This applies at EVERY milestone/round — not only at verify_final.

## §5 EXECUTION PLAN — per-paper instantiation of the milestone arc
The generic phase arc (gates, ordering, conduct, integrity rules) lives ONCE in RESEARCH-PROTOCOL.md, which
the executor reads in full first — point to it, do not restate it. This section is the per-paper DATA that arc
consumes: per phase, name THIS paper's CONCRETE deliverable + its acceptance, or mark `[N/A: <reason>]`. A phase
left as generic prose is an unusable work order.

- **Phase 0 — Kill-or-Confirm (HARD GATE).** WRITE: which [GAMBLE] K from §4 this gates + the CHEAPEST toy that
  can FALSIFY it, instantiated from the seed's "Failure signal" (name the toy problem + the single script + the
  CONFIRM/SUSPECT signal it reads — never just "a toy"). ACTION on CONFIRM: LOCK §4b →
  `HANDOFF.scale-contract.locked.json` and §4c → `HANDOFF.ambition.locked.json`; restate H1/K + both locked
  contracts in RESEARCH_LOG.md; Phase 1+ begins only after the lock. `[N/A]` if no [GAMBLE] K exists — perform
  the lock only. (Gate / escalation / toy-FAIL-never-kills semantics: RESEARCH-PROTOCOL §0 + §3.) ALSO NAME
  (for the CAPACITY_READOUT milestone that follows, right after the lock): the `fundamental_unit` this paper's
  §4b `scale_size` is measured in, and the micro-probe recipe — reuse the SAME script/model this Phase-0 toy
  already exercises where the unit matches; otherwise name the smallest new script that runs N real units at
  the run's real full-scale config (real dtype/device/batch shape — just fewer of them, never a shrunk-parameter
  run, per experiment-engineering §2's "engineering probe" contract).
- **Phase 1 — Literature & positioning.** OWNED by the LITERATURE milestone (its method — by ROLE/coverage, the
  citation floors, anti-fabrication — lives in that worker's rubric + RESEARCH-PROTOCOL §6). WRITE here only THIS
  paper's seed for it: the comparators + the 3-5 field-map threads carried from §1b. Deliverables the worker
  produces: `differentiation_table.md` + `references.bib`, built via `<CITATION_SKILLS>`; the
  ≥`<MIN_INTRO_CITATIONS>` intro / ≥`<MIN_TOTAL_CITATIONS>` total floors are a coverage by-product, not the goal.
- **Phase 2 — Theory / method formalization.** WRITE: this paper's theory deliverable, CONCRETELY —
  "THEORY.md: prove <the specific property H1 asserts> for <the named scheme>", with the load-bearing
  lemmas / assumptions named — or `[N/A: empirical-only, no theoretical claim]`. ACCEPT: a named artifact an
  independent THEORY-AUDIT can check; never "formalize the method".
- **Phase 3 — Implementation.** Generic (code + data pipeline + a one-command repro harness, per RESEARCH-PROTOCOL
  §5). WRITE here ONLY a non-obvious per-paper invariant that must be unit-tested; otherwise `[N/A: generic]`.
- **Phase 4 — Validation gates.** WRITE: this paper's REPRODUCE-FIRST references + their pre-registered tolerances
  — the known-good / gold-standard numbers to reproduce (each pinned to a source) BEFORE any new run. ACCEPT: each
  gate here gets a recorded verdict. (Reproduce-before-compare doctrine: RESEARCH-PROTOCOL §6.)
- **Phase 5 — Experiments & ablations.** Author the per-paper ORDERED segment list to
  `reference/phase5-experiments.md` (this skill) and follow that rubric — it carries the per-segment schema,
  the required publication-grade axes, and the discriminative-sanity floor. For the per-segment EXPERIMENT export
  format, retrieve the experiment-process skill; the canonical format lives in `<REVIEW_SPEC>`'s output
  contract (`review/output-contract.md`, next to that protocol file).
- **Phase 6 — Manuscript.** WRITE: this paper's figures — for each §4b / Phase-5 INTEGRATION TARGET, a logged plot
  script (`plotting/<fig>.py`) → `figures/<FigureN>.{pdf,svg}` (every figure from a logged config, never
  hand-drawn), captioned via `<FIGURE_SKILLS>`; venue = `<VENUE_LABEL>`; require_figures=`<REQUIRE_FIGURES>`.
  CLAIMS.md = every claim → its backing exhibit (soften or cut unbacked). (Drafting itself runs in the loop's draft stage.)
- **Phase 7 — Handoff-out.** Generic (package what is proven / fragile / future-work, per RESEARCH-PROTOCOL §7) —
  `[N/A to instantiate]` unless this paper has a specific carry-forward to flag.

## §6 DEFINITION OF DONE
Manuscript draft + reproducible code/data/logs + a passing CLAIMS.md audit + every planned experiment integrated
or honestly reported as negative.
