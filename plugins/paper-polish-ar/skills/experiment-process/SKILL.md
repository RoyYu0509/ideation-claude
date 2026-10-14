---
name: experiment-process
description: Conceptual overview of the /review supplementary-experiment phase (DESIGN + export a HANDOFF; never run or write back). Loaded by name by the experimenter agent and the review-handoff spawn-prompt.
user-invocable: false
---

# Experiment process (overview)

This skill explains the design. The **canonical procedure** is the REVIEW OWNER's standing orders in
`spec/review-protocol.md` (+ `spec/review/output-contract.md` for the HANDOFF export shape); there is no
`experiment:` config block — review runs no experiments. Read those to *run the
phase*; read this to *understand*. In `/review` the experimenter only DESIGNs the demand and exports it to
a HANDOFF — the RUN / INTERPRET / write-back modes (in `experiment-run` + the downstream loop spec) execute
later, in the auto-research loop, not in review. This overview holds only the *why* and the safety
invariant.

## Why this phase exists

`/polish` freezes the science. `/review` questions it but still may not fabricate — a reviewer demand
that needs **new work** (a new experiment, a method change, missing data) is marked `needs_author` and
escalated. `/review` is a reviewer, not a research engine: it does the *verification* a careful reviewer
would, and it **hands off** the genuinely new science.

The experimenter still classifies each demand by **footprint** when it designs the experiment — but the
classification only shapes the HANDOFF; **neither footprint runs or writes back in `/review`**:

- **`updates_existing`** — the demand only updates an EXISTING paper number/claim (reproduce a reported
  number; add error-bars to existing cells). Exported as a verify work order (reproduce-before-compare is
  its kill criterion) for the downstream loop to run at full scale and write back.
- **`new_exhibit`** — the demand needs NEW paper real-estate (a new baseline, a new test case/PDE, a new
  table row, a new figure curve, a new section). Running a new baseline weakly, or bolting a new row into a
  table with no figure/prose integration, is exactly the failure this footprint flags. Exported the same
  way, with the integration requirement spelled out.

Both leave as a portable work order — `HANDOFF-<paper>.md` + `REVIEW-EXPERIMENT-PROTOCOL.md` — that the
auto-research loop's experiment+draft stage (or a fresh Claude Code / Codex session) drops in to run at
full scale and integrate coherently. The adversarial reviewer concern becomes the handoff's
**kill/falsification criteria**, so the downstream run stays honest. So when the author answers an
escalation by electing to pursue an experiment, the demand leaves as a handoff regardless of footprint;
nothing fabricated or unintegrated ever lands in the paper from `/review`, because `/review` lands nothing.

## The one rule (the gate lives downstream)

`/review` froze fabrication: no number it diagnoses may enter the paper from here — review writes nothing.
The narrow, provenance-gated channel that lets a real experiment number eventually reach the paper is
opened **downstream**, in the loop's experiment+draft stage, and only when this whole chain holds:

> **(real full-scale run, its products + tee'd stdout on disk) → (INDEPENDENT run-auditor re-derives the
> evidence from disk and returns PASS) → (orchestrator populates the manifest allowlist from that PASS) →
> (the pre-edit hook lets exactly that one token through).**

Break any link and the system stays **fully frozen**, never "open". The anti-fabrication guarantee rests
on **one** independent gate — the auditor re-deriving from disk + a hard-to-forge sanity self-check — not
on a tower of scaffolding. See `run-audit` for that gate and the pre-edit hook's `mode:"experiment"` for
the mechanical lock; both run downstream, not in `/review`.

## No macro loop — diagnose once, export, hand off

Review is diagnose-only, so there is no inner `panel → AC → 大修 → re-review` macro loop and no
`max_macro_rounds` convergence to run (those knobs are retired). The experiment phase here only DESIGNs
the demand and EXPORTS it; running the experiment, writing the audited result back, and re-reviewing the
updated manuscript all happen DOWNSTREAM, in the auto-research loop's experiment+draft stage (driven by
the exported HANDOFF). That loop owns the iterate-to-convergence behaviour; `/review` contributes one
diagnosis per invocation.

## Scope

NO experiment runs in `/review` — both `updates_existing` (verify) and `new_exhibit` demands are exported
to the HANDOFF and run downstream, LOCALLY at full scale, by the auto-research loop's experiment+draft
stage. Short / long tiering, detached long runs, the run-auditor gate, and write-back are all the loop's
concern; `/review` only designs the demand and writes the kill criteria.
