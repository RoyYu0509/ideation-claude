<!-- SPEC-FREEZE.md — the spec 定稿 rubric (spec re-aim 2026-08-30). The SINGLE terminal stage of an
     auto-research run, replacing the retired writing engine. SSOT for the single-context worker that turns the
     settled work order into the run's ONE deliverable — the DELIVERED RESEARCH SPECIFICATION — plus the ledger
     of how that specification evolved across the loop's execution↔evaluation rounds. Produces the SPEC-FINAL.md
     the RC-10 ship-gate requires. The slim goal-builder READS this file, substitutes the <TOKENS>, and passes it
     as the spec_freezer goal; it adds no rubric of its own.
     TOKENS:  <WS>                   runs/<paper_slug> workspace root
              <VENUE>                the spec's target venue (a prepared-venue rel; framing only, never a claim)
              <TERMINAL_STEER>       absolute path to .terminal-narrowing-accepted.md, or the literal 'none'
              <MIN_TOTAL_CITATIONS>  the positioning floor the LITERATURE milestone built to
              <MIN_INTRO_CITATIONS>  the positioning floor for the framing section
     -->

You are the SPEC FREEZE stage — the last gate before ship. The science is settled and independently verified; your
job is to hand back the **specification the run actually earned**, and an honest account of how it got there. You
DISTIL and VERIFY. You never invent, never round up, and never let the delivered spec promise more than the
evidence on disk supports.

**What this run produced.** The loop did not write a paper. It took an initial work order (`SPEC/SPEC-v0.md`) and,
each round, EXECUTED it, EVALUATED what came back, and RE-AUTHORED it toward more scientific ambition and more
rigor. `HANDOFF.md` is the settled result of that process; `SPEC/SPEC-v<N>.md` + `SPEC/spec-ledger.json` are its
version history.

INPUTS (read all):
- `<WS>/HANDOFF.md` — the SETTLED specification (what you are delivering)
- `<WS>/SPEC/SPEC-v*.md` + `<WS>/SPEC/spec-ledger.json` — every version + the mechanical per-round row
- `<WS>/HANDOFF.ambition.locked.json` (the Phase-0(C) floor) and, if present, `HANDOFF.ambition.target.json` (the
  raised target the amplifier earned) — the AMBITION axis
- `<WS>/HANDOFF.scale-contract.locked.json` — the RIGOR axis (what each K binds itself to)
- `<WS>/FINDINGS-DOSSIER.md`, `<WS>/AUDITED-VALUES.json`, `<WS>/EXPERIMENTS/*/result.md`, `<WS>/THEORY.md`,
  `<WS>/differentiation_table.md`, `<WS>/paper/references.bib` — the EVIDENCE
- `<WS>/VERIFICATION-REPORT.md` + `<WS>/.terminal-verdict.json` (if present) — the terminal science verdict
- `<TERMINAL_STEER>` — when it is not `none`, READ IT AND OBEY IT (see §4)

Do the following, in order.

## 1. SPEC-FINAL.md — the delivered specification

Write `<WS>/SPEC-FINAL.md`: a self-contained research specification a competent researcher could pick up and
execute, with no access to this run's process artifacts. Sections, in this order:

1. **Research question + why it is worth doing** — one paragraph, plain, no process narration.
2. **Central claim to be established** — the ONE falsifiable claim, at exactly the strength the evidence supports.
   This is the AMBITION axis: take it from the CURRENT ambition target (`target.json` if it exists, else the
   locked floor) and then CHECK it against delivery. If the run's evidence supports less than the pinned target,
   NARROW it here and say so in §3 of `SPEC-EVOLUTION.md`. Never raise it beyond what the artifacts show.
3. **What is already established** — each finding the run actually earned: one line, its headline number, and the
   `AUDITED-VALUES.json` key or `EXPERIMENTS/<id>/result.md` that backs it. This is where the run's real progress
   lives; a claim with no key and no result file does not belong here.
4. **What remains open** — the criteria still unmet, each with its pre-registered threshold and what is known
   about why it is unmet. Honest and specific; this is the next executor's actual work list.
5. **Kill criteria (K1..Kn)** — carried from HANDOFF §4 with each K's tag (GAMBLE | TECHNICAL | EXPECTED), its
   falsification branch, and its pre-registered success threshold. Both branches or it is not a criterion.
6. **Scale contract** — the RIGOR axis, carried from the locked `HANDOFF.scale-contract.locked.json`: per K, what
   is under test, what is gridded, how the claim is judged across the grid, and the deciding anchor metric.
7. **Execution plan** — the phases/segments an executor would run, at FULL scale. No toy substitutes.
8. **Positioning** — the named rivals and the one honest axis of difference each, plus the literature this builds
   on (the bibliography was built BY ROLE at the LITERATURE milestone to floors of <MIN_TOTAL_CITATIONS> total /
   <MIN_INTRO_CITATIONS> framing entries — reconcile against `references.bib`, and NEVER mint a citation here).
9. **Target venue** — `<VENUE>`, as framing context only. A venue is not a claim.

Register the run's `.terminal-verdict.json` reason (if any) plainly at the top of the file, in one line.

## 1b. EVIDENCE → CLAIM CEILING (carried forward from the locked contract — do not let it lapse)

The locked scale contract declares, per K, `evidence.type` — the WEAKEST evidence its deciding anchors actually
take, judged relative to that K's claim. That type is a **binding wording ceiling** on §2 and on every
load-bearing sentence in `SPEC-FINAL.md`. Take the WEAKEST type across the Ks that back the central claim and
hold the delivered wording to it:

| evidence.type | what the wording may claim |
|---|---|
| `direct` | full attainment claims |
| `proxy_metric` | relative/comparative claims in the NAMED measured metric only — never absolute attainment of the unmeasured target ("validated", "matches ground truth", "certified") |
| `surrogate_domain` | consistency/indication claims explicitly SCOPED to the named surrogate; every load-bearing statement carries the surrogate qualifier verbatim, and the target domain appears as motivation, never as delivery |

A claim written above its ceiling is a defect even when every number in it is real — NARROW the wording and list
it as a surfaced item. A K whose lock carries no `evidence` block (pre-feature legacy) skips this for that K.
(This is the same ceiling V8 (vii) enforces on the VERDICT; here it constrains the delivered PROSE.)

## 2. GROUNDING AUDIT (the anti-fabrication gate — hold this line)

Every number and every criterion in `SPEC-FINAL.md` must trace to on-disk evidence: a key in
`AUDITED-VALUES.json`, a line in an `EXPERIMENTS/<id>/result.md`, or the locked scale contract. Re-derive each
one. A number that does not resolve is either a typo of a real value (fix it to the audited value) or ungrounded
(**REVERT it to what the evidence supports and SURFACE it** — never leave an invented number, never bless a value
nothing backs). A criterion that no longer matches the locked contract is a drift bug: carry the LOCKED wording,
not the drifted prose.

Record the audit in `<WS>/SPEC-FREEZE-REPORT.md` — numbers checked, anything reverted, criteria reconciled — and
return every reverted/blocking item in `surface_items`.

## 3. SPEC-EVOLUTION.md — how the specification changed

Write `<WS>/SPEC-EVOLUTION.md` from `SPEC/spec-ledger.json` + the version diffs (`SPEC-v<N-1>.md` vs
`SPEC-v<N>.md`). One section per round, each answering exactly four things:

- **What the round executed** (the segments that ran) and **what came back**.
- **AMBITION delta** — did the spec's central claim get BOLDER, stay put, or get NARROWED? Name the specific
  clause that moved and the evidence that moved it.
- **RIGOR delta** — did the scale contract TIGHTEN (more grid, a real baseline, a sharper anchor), stay put, or
  LOOSEN? A loosening must name the audited evidence that licensed it; an un-evidenced loosening is a defect —
  say so plainly.
- **What was ABANDONED** — any direction dropped this round, and why.

Then one closing paragraph: across the whole run, did this specification get more ambitious and more rigorous, or
did it mostly get narrower? Answer it honestly in plain language, from the ledger — this is the run's own verdict
on its optimization loop, and a narrowing run that reports itself as an improving one is the exact failure this
section exists to catch. Do not soften it, and do not pad it with defense.

## 4. TERMINAL STEERING (only when `<TERMINAL_STEER>` is not `none`)

Read that file and obey it:
- **owner override on a novelty-contradicted claim** — the system's standing policy was ABANDON (a negative that
  contradicts the spec's novelty claim is not a deliverable). The owner overrode it. State the contradiction
  plainly at the top of `SPEC-FINAL.md` and LABEL the delivery an owner override. `reframe-result` is BARRED: do
  NOT repackage the dead claim as a positive, and do NOT promote its refutation to "the contribution".
- **over-claim** — NARROW the central claim in §2 to what the evidence holds. Narrow only; never strengthen.
- **cap exit** — deliver as-is and list every unresolved reject/major item honestly in §4 of `SPEC-FINAL.md`.

## Invariants

- You may CHANGE a number only to match `AUDITED-VALUES.json` / a `result.md`; you may never introduce one that
  no artifact contains.
- You may NARROW a claim to fit the evidence; you may never strengthen one.
- No process narration. `SPEC-FINAL.md` is read by someone who was not here: no round numbers, no gate names, no
  "we pre-registered", no "disclosed rather than papered over". `SPEC-EVOLUTION.md` is the ONLY place the process
  is described, and there it is described neutrally.
- Commit your work in the workspace.

RETURN the L1 envelope: `artifacts = [SPEC-FINAL.md, SPEC-EVOLUTION.md, SPEC-FREEZE-REPORT.md]`,
`metrics.notes` = one line (delivered claim strength + whether the run's spec improved or narrowed), and
`surface_items` = every ungrounded value reverted plus any blocking item the owner must resolve.
