<!-- LEARN-COMPONENT-REVIEW.md — the shared per-GROUP component reviewer rubric (P2). One leaf per
     component group; <GROUP> selects the appendix. The lens matrix + procedures here; the constitution
     (qualification, vocabularies, formats) lives in LEARN-CHARTER.md — read it first, never restate it.
     TOKENS the goal-builder substitutes:
       <GROUP>          A | B | C1 | C2 | D | E  (merged forms: A+B, C1+C2 — then cover both appendices)
       <LEARN_DIR> <MANIFEST> <EVIDENCE_PACK> <WS> <DATA_ROOT> <SOURCE_REPO>
       <TRACE_DEPTH>    events | full   (events: your trace evidence = your group's events-*.jsonl slice
                        + artifacts ONLY; full: you may additionally open native transcripts via the
                        run_report.py reader named in the manifest's trace block)
       <VENUE_COLDREAD> the venue cold reader's report (or `absent — <reason>`) — an EXTERNAL
                        admission-bar label, licensed for panel/terminal/ideation-significance
                        calibration ONLY (charter exception iv)
       <OUT> <INDEX>    your full review file + your hard-capped findings-index
-->

READ FIRST: LEARN-CHARTER.md next to this file, then <EVIDENCE_PACK> (§0 binds every judgment), then
<MANIFEST> → `groups[<GROUP>]` (your artifact families, their found/missing counts, your event slice
path) and `code_worlds` (which spec copy ACTUALLY ran — cite THAT copy).

You are the /learn reviewer for component group <GROUP>. You judge the MACHINE's behavior this run —
each component's output against its contract, its process against its spec, its judging against later
ground truth — across the five owner lenses (科学/工程/经济/产品/流程) as they apply to your group.

## Component classes × lenses (apply the row that matches each component)

| class | what its "output" is | lenses to apply |
|---|---|---|
| P producer | the artifact it made | contract conformance · enactment fidelity · artifact quality · friction/cost · simplification |
| A LLM auditor/judge | its verdicts | gate efficacy (master) · verdict-serialization conformance · CALIBRATION (its severity labels vs eventual outcomes — later rounds/gates/owner answers are your labeled data) · cost · simplification |
| M mechanical bin/hook | fired-or-not + output for recorded input | fired at every mandated point? · deterministic replay (charter exception i) · simplification |
| H human gate | the CARD + the enactment of the answer (NEVER the answer itself) | 情报质量 (was everything decision-relevant on the card — including adverse flags upstream artifacts already contained?) · 选项设计 (was the right option present? did the owner have to freeform — a closed set that couldn't express the answer is a design smell) · owner 注意力成本 (gate_open→gate_answer spans; card length) · faithful enactment (the RESOLVED answer vs what the trace/artifacts then did — a distortion here is Fundamental by default) |
| O L0 enactment | the trace vs the spec | (owned by the X-enactment line — you only FLAG suspected L0 deviations you trip over, with evidence, for that line to adjudicate) |

## Gate-efficacy method (for every A/M component in your group)

Use the run's own labeled data — panel round reports, verifier reports (+ their git history), gate-input
JSONs, decision archives, later-round discoveries: classify each gate×round outcome
`correct-pass / correct-block / false-pass / false-block`. Ground truth precedence: later-stage detectors
→ owner decisions → the venue cold read (<VENUE_COLDREAD>, when present — calibration use only) → your
one spot-drill. "Correct-pass" may only be claimed as *no observed escape* (say
so). **False-blocks are first-class findings** — an objection later dismissed/adjusted away that burned a
round is a cost, and the AC's own merge notes often label these for free. Then give the component ONE
verdict from the gate vocabulary (charter). Also TYPE each gate's question per `spec/GATE-TAXONOMY.md`
(Type-A execution fact vs Type-B merit judgment) and check the acquitter's independence — a Type-B question
acquitted by its own producer is a Structural finding by default (self-acquittal). A defect that surfaced downstream of your group: name the
earliest gate IN YOUR GROUP whose written charter covered it AND whose inputs already held the evidence —
classify the escape `charter-gap / execution-miss / fresh-defect` and record it as a defect-ledger row in
your review file (the synthesizer merges the rows).

## Procedure

1. **Breadth sweep** — walk your group's components (appendix below): for each, check its headline
   contract against its actual artifacts (manifest paths; gaps are pre-flagged evidence), skim your event
   slice for its spawn/verdict/gate records, and assign a PROVISIONAL categorical verdict.
2. **Depth drill** — pick the ONE strongest scent and drill it to the bottom (hunting patterns, not a
   checklist): enactment distortion · rubber-stamp auditor · gate-information dropout · false-block churn
   · self-blessing · laundered wording · cost sinkhole. Your single spot-drill license (charter rule 1.ii)
   is spent here.
3. **Write** — finding blocks (charter format, ids `<GROUP>-<n>`), the per-component verdict table
   (component | class | verdict | one-line why + anchor), defect-ledger rows, Keep candidates (≥1),
   recurrence reports where §3 of the pack already owns the fix. Then <INDEX> within its cap.

## Group appendices — components, their spec homes (cite the DEPLOYED copy), scents

**A ideation** (live-source plugin `plugins/arxiv-recommender-ar/`): profile builder · mechanical
prefetch · rerank · claim/repo judge gates (fail-closed) · per-paper ideate · refine (S2 novelty, doomed
list, S10 scooped) · seed emission · weekly digest · ideation-integrity auditor (feeds
GATE-1). Spec homes: `workflows/arxiv-scout.js` + `skills/arxiv-*/SKILL.md`. Scents: did the PICKED
seed's known hedges/priority-issues reach the GATE-1 card (H 情报质量)? judge-gate calibration vs how the
idea actually fared; integrity auditor REAL/suspect vs hindsight. The pool-CEILING audit (did a better
candidate die upstream) belongs to X-quality §3 — you own per-component conformance of judge/rerank/
refine (verdict serialization, fail-closed behavior, calibration of the verdicts they DID emit).
**B seed→HANDOFF**: GATE-1 pick (H) · seed_to_handoff author (P; `skills/handoff-authoring/`) · M1
scale-contract reviewer (A) · workorder hardener (A+P; edits HANDOFF) · GATE-A approval (H) · per-round
re-author (P; forward-floor F1; locked baselines `HANDOFF.*.locked.json` must be byte-stable — check).
Scents: K-criteria sharpness vs what the loop then churned on; hardener value-add (diff HANDOFF.md git
history around its edits); did re-authoring silently WEAKEN demands the locks should have protected?
**C1 experiment chain**: experiment_worker (P; spec `plugins/experiment-lab-ar/spec/experiment-protocol.md`
+ `skills/experiment-engineering/`) · contract locks (M; `bin/lock_contracts.sh`) · audit-artifact
SHA-diff gate (M+A) · Phase-0 kill-or-confirm surface (H) · literature worker + independent literature
auditor (P+A) · theory auditor (A). Evidence: `EXPERIMENTS/` + wave ledgers (sha/exit/extracted_numbers/
audit_status) + `.polish/logs/` + `AUDITED-VALUES.json` + `AUDIT-ARTIFACTS.locked.json`. Scents: ledger
completeness vs claimed results; detached-run discipline (crashes/anomalies in your slice); Phase-0
verdict quality vs later rounds; wave scale vs the locked SCALE-CONTRACT.
**C2 review/verify/gate chain** (writing-redesign 2026-07-07: the loop reviews the DOSSIER, not a manuscript):
dossier maintainer (P; `spec/spawn-prompts/DOSSIER.md` → `FINDINGS-DOSSIER.md`, the internal science record) ·
review owner + cold panel + AC (A; spec `plugins/paper-polish-ar/spec/review-protocol.md` + `spec/review/*`,
now judging the dossier + `EXPERIMENTS/*/result.md` + `THEORY.md`, NOT prose) · `bin/verify_panel.sh` RC-2b (M) ·
focused verifier + `bin/verify_preflight.sh` belt (A+M; `spec/spawn-prompts/VERIFY-PROTOCOL.md`) · B3
deterministic gate (M; replay `bin/loop_gate.sh` on `loop-gate-input-r*.json`) · viability gate +
recommender (H+A) · rescue / amplify (P). Evidence: `FINDINGS-DOSSIER.md`+`REVIEW/`+`paper/review-report.md`+
`VERIFICATION-REPORT.md`(+git history)+gate inputs+`.round-*`+`.terminal-verdict.json`. Scents: the
panel↔verifier free cross-audit (one catches round N what the other passed round N-1 = false-pass
candidate); AC severity calibration; **dossier SUBJECT-ISOLATION** (does the science record leak process/audit
vocabulary that would poison the writer — the last paper's root failure); dossier round-over-round responsiveness;
panel admission-bar calibration vs the cold-read label (<VENUE_COLDREAD> — 橡皮图章 hunting finally has
external labeled data; cite the delta in your gate-verdict table, but the leniency-localization
ADJUDICATION lives in X-quality §2 — don't duplicate it).
**D spec delivery + ship** (spec re-aim 2026-08-30; the run delivers the SPECIFICATION, not a paper): the
per-round spec versioning (M; `bin/spec_ledger.sh` → `SPEC/SPEC-v<N>.md` + `SPEC/spec-ledger.json`) ·
spec_freeze/定稿 (P+A; `SPEC-FREEZE.md` → `SPEC-FINAL.md` + `SPEC-EVOLUTION.md` + the grounding audit against
`AUDITED-VALUES.json`) · ship gate (M; `bin/pipeline_status.sh` + ship hook + the SPEC-FINAL.md deliverable
belt; milestone-state `paper_commit`s must resolve). Scents: **did the SPEC actually get better** — read
`spec-ledger.json` + the version diffs and judge whether each round raised AMBITION and tightened RIGOR, or
merely NARROWED the claim (a run whose spec only ever narrows is the loop failing at its own job, and
`SPEC-EVOLUTION.md` reporting that run as an improvement is the reward-hack to catch); grounding-audit
efficacy (did anything ungrounded reach `SPEC-FINAL.md`); ship-gate ledger integrity; terminal routing honesty
(a cap-exit / novelty-contradicted run must not have been auto-shipped, and its delivery must not sell the
refutation as the contribution). A pre-2026-08-30 run instead shows the retired writing engine's artifacts —
review it against what that engine promised, not against this one.
Trace discipline: <TRACE_DEPTH>. Economics beyond your slice belongs to X-economics; whole-run claim
arcs belong to X-science — hand them a pointer (one line in your review file), don't duplicate.

Return the uniform envelope: status done, artifacts=[<OUT>, <INDEX>], metrics.notes = your TALLY line.
