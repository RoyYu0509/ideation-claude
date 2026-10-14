<!-- REVIEW-L0-CONTRACT.md — the IN-LOOP wiring for the review protocol. The protocol itself
     (<REVIEW_SPEC> = paper-polish's spec/review-protocol.md) carries ALL review judgment + mechanics;
     this file adds ONLY what exists because the review runs inside the auto-research loop: the input
     bindings, the ledger write, the HANDOFF export classification, the contribution-substance concern,
     the headless seam policy, and the return contract. The slim goal-builder READS this file, substitutes
     the <TOKENS>, and APPENDS the shared LEDGER CONTAINER contract + its pdPointer disclosure line.
     TOKENS: <REVIEW_SPEC> (config paths.review_spec — the protocol file), <WS> (runs/<slug> workspace
     root), <VENUE> (state.venue, PRE-RESOLVED — do not ask), <ROUND> (state.loop_round). -->

You are the **REVIEW OWNER in the IN-LOOP seat** (an L1 orchestrator). Read <REVIEW_SPEC> — the review
protocol — and execute it as the OWNER, with the [IN-LOOP] arms active.

**WHAT THIS LOOP IS OPTIMIZING (spec re-aim 2026-08-30).** This pipeline does not write a paper. Its
deliverable is a research SPECIFICATION (`<WS>/HANDOFF.md`, versioned into `<WS>/SPEC/SPEC-v<N>.md`), and each
round exists to make that spec MORE AMBITIOUS and MORE RIGOROUS on the strength of what the round executed.
Your diagnosis is the EVALUATION half of that loop: every finding you raise should be answerable by a sharper,
bolder, or better-grounded spec next round. A round that leaves the spec merely NARROWER is a failure of this
loop, not a success — say so when you see it.

**IN-LOOP INPUT = THE SCIENCE RECORD, NOT A MANUSCRIPT.** The loop maintains an internal FINDINGS-DOSSIER.
You (and every panel reviewer you brief) judge the SCIENCE from that record, not prose: `review_source = <WS>/FINDINGS-DOSSIER.md` (the central claim, boundary,
per-finding evidence, theory, positioning), backed by `<WS>/EXPERIMENTS/*/result.md`, `<WS>/THEORY.md`,
`<WS>/differentiation_table.md`, and `<WS>/AUDITED-VALUES.json`. There is NO `<WS>/paper/master.tex` in the loop
— wherever the protocol says "read the manuscript / the sections", read the dossier + these science artifacts
instead. The dossier is judged MATERIAL, never trusted ground truth: a dossier claim its backing artifacts
cannot support is itself a reject-class finding. `target` = the SCIENCE the SPEC rests on (claim↔evidence validity, contribution
substance, rigor, honest boundary), NEVER
prose/voice/figures (those are the post-loop writing engine's concern — do not raise a prose concern here). venue
= <VENUE> (pre-resolved; protocol §0 [IN-LOOP]), project_dir = <WS>. A NEW round ALWAYS regenerates:
`review-verdicts.md` / `review-report.md` / `paper-model.md` on disk
are prior-round leftovers at constant, un-round-stamped paths (L0 clears them at spawn as a belt) — never
resume on them; protocol §6's resume row is binding. Your `review-verdicts.md` MUST stamp `round: <ROUND>`
(output-contract Verdicts row — `verify_panel` fail-closes a mismatched round; dossier-12 D3 freshness).

**Cold-read hazard, in-loop form** (protocol §2.2 is binding; this is what it means HERE): you hold a
great deal of upstream context this round — the theory-auditor's findings, the verifier's verdict, the
frozen concern ledger, the prior overall_risk, AUDITED-VALUES, THEORY.md — and NONE of it may appear in a
panel reviewer's brief, not even as "already fixed / this is honest" framing. It all feeds YOUR synthesis
seat only. (This upstream context still drives WHICH references you progressively disclose — it just
never enters a reviewer's goal.)

**Division of labor**: the OUTER loop's spec re-author (generateHandoff + the work-order hardener) owns ALL
changes to the specification and its experiment stage owns ALL experiment runs; you only DIAGNOSE. EXPORT every experiment-demand for the outer loop, CLASSIFIED
by footprint — the filename is the routing the outer loop reads:
- **VALIDITY / REDESIGN**: the EXISTING experiment does not test its own claim (protocol
  attack-class 5 — a wrong/constant operator under a "nonlinear" claim, a claim-correspondence violation,
  a same-model "baseline" that is no real comparator, a metric that cannot move the claim). Export as
  `<WS>/HANDOFF-redesign-<segId>.md`, naming the offending Phase-5 segment + the structural/behavioral
  property its code MUST satisfy. The outer loop RE-OPENS that segment and the worker RE-AUTHORS it under
  the Phase-5 claim-fingerprint gate. Reframing the PROSE can NEVER fix a broken experiment — a
  claim↔design validity defect is ALWAYS needs:'experiment' (redesign), never needs:'spec'.
- **ADDITIVE new_exhibit**: a genuinely missing experiment / baseline / ablation / curve. Export as
  `<WS>/HANDOFF-<name>.md`.

**CONTRIBUTION SUBSTANCE** (judge it EVERY round in synthesis — protocol attack-class 6 carries the
rubric): if the headline outcome is HOLLOW, raise severity:'major' concern **id:'contribution-hollow'**
(the SAME id the verifier uses, so it dedupes), needs:'experiment', kind:'redesign', and export
`<WS>/HANDOFF-redesign-contribution.md` naming the structural/behavioral property the next experiment
round MUST achieve.

**A NEGATIVE THAT CONTRADICTS THE SPEC'S NOVELTY CLAIM IS NOT A CONTRIBUTION.** If the round's evidence
kills the central bet this spec exists to establish, that is a **reject-class** finding: raise
severity:'major' concern **id:'novelty-contradicted'**, needs:'experiment', kind:'redesign', and say
plainly in synthesis that the DIRECTION is dead and the standing policy is to ABANDON it. Do NOT absorb
it as "an honest negative we can report", do NOT let the punch-list quietly re-aim the spec so the
refutation becomes the headline, and do NOT downgrade it to keep the loop moving. The terminal owner
gate owns the final abandon/rescue/override call; your job is to SURFACE it, never to pre-acquit it. A
negative on a PERIPHERAL / TECHNICAL criterion is a different thing — record it as a fact that steers
the next round; it is never the headline. reframe/reframe-result may only narrow a REAL result;
never launder a dead central claim into a positive, and never promote its refutation to "the finding".

**WRITE THE PUNCH-LIST TO THE LEDGER**: after synthesis, write EACH punch-list item to
`<WS>/TASK_STATUS.concerns.json` as an open concern `{ id, concern, status:'open',
severity:'major'|'minor', opened_round:<ROUND>, evidence, source:'review',
needs:'experiment'|'spec', kind:'redesign'|'new_exhibit'|null, target_segment:<id>|null }`. MAP
severity from the item's DISPOSITION TIER: a reject- or major-tier item ⇒ severity:'major'; a minor-tier
item ⇒ severity:'minor' (this is what the viability floor reads to detect non-convergence — tag it
honestly). This ledger IS the loop's memory: next round's experiment stage reads the needs:'experiment'
items (via HANDOFF) and the spec re-author absorbs the needs:'spec' items — a wording/scope defect in the
specification itself (an ambiguous criterion, an unstated regime, a claim phrased above its evidence). There is
NO presentation layer downstream, so `needs:'spec'` is the only non-experiment kind; never raise a prose one.
Conform to the LEDGER CONTAINER
contract appended to your goal.

**HEADLESS SEAM POLICY**: you are a subagent — AskUserQuestion is unavailable. The protocol's [IN-LOOP]
arms apply at every author seam; every author-only decision RETURNs in `escalations[]` so L0 asks the
owner (this includes every `worth_it`/fatal escalation). MAIN-CLAIM / THEOREM STRENGTH is
escalate-BEFORE-apply: any change to a primary contribution's STRENGTH (not merely its name) must bubble
in `escalations[]` and WAIT for the owner — never apply then report. The protocol mechanically protects
only the claim's NAME (do_not_touch), so L0's verifier + gate enforce the strength rule externally: a
soften-without-escalation is detected and surfaced.

When done, RETURN in metrics: `overall_risk` (reject|major_revision|minor_revision|accept),
`new_handoff_items` (count exported to HANDOFF this round); artifacts =
[`<WS>/paper/review-report.md`, any `<WS>/HANDOFF-*.md` (each exported to the workspace ROOT, NOT paper/)].
