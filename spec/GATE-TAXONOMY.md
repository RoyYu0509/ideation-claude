# Gate Taxonomy (canonical) — who may ACQUIT a result

The single source of truth for classifying every acceptance / exit / verification gate in this system:
what kind of question the gate asks, and who is allowed to answer it. `spec/STATUS-MODEL.md` defines who
RECORDS a state; this file defines who may JUDGE it — two different axes, kept in two files on purpose.
Adapted from ARIS (arXiv:2605.03042, `acceptance-gate.md`); ARIS separates acquittal by model family, we
separate it structurally.

## 0. Core principle

**A goal/loop can DRIVE; it cannot ACQUIT.** The loop may freely drive itself toward a target — schedule
the next round, re-run a failed job, re-open a milestone. It may never acquit its own work: declare the
science sound, the claim supported, the paper good.

## 1. The two gate types

- **Type-A — EXECUTION / OBJECTIVE.** A machine-checkable or externally observable fact about *what
  happened*, with no judgment of merit: an exit code, a file's existence, a git sha that resolves, a
  counter reaching its cap. The producer MAY self-report these — and wherever possible the check should
  be a mechanical oracle (a `bin/` script, a hook), not an LLM assertion.
- **Type-B — QUALITY / CORRECTNESS / ACCEPTANCE.** A judgment of *merit, correctness, or sufficiency*:
  is the claim supported, is the proof valid, is the paper honest, was the anchor met at contract scale.
  The producer may hold an opinion; it may never be the acquitter.

## 2. The dividing question

**"Could a dumb script with no taste answer this gate?"** Yes → Type-A (bookkeeping; mechanize it).
No — it needs taste, correctness, or domain judgment → Type-B (route to an independent acquitter).

## 3. Legitimate Type-B acquitters in this system

Exactly three acquitter shapes are legal, and every verdict is categorical (never a numeric score):

1. **Code-enforced deterministic oracle** — a `bin/` script or fail-closed hook that re-derives the fact
   from disk (`verify_panel.sh`, `loop_gate.sh`, `pipeline_status.sh`, `spec_ledger.sh`,
   `central_ambition_guard.sh`, `concern_prose_lint.sh`).
2. **Fresh independent context** — a cold-read subagent spawned by L0 that did not produce the work and
   whose incentive is reversed (focused/terminal verifier, review panel, literature auditor,
   audit-artifact auditor, run-auditor).
3. **The gate adjudicator** — a cold-read leaf spawned at `gate()` that produced none of the work under
   judgement, answering from the decision file + the artifacts that gate's context names
   (`spec/spawn-prompts/GATE-ADJUDICATION.md`). This is the DEFAULT since 2026-09-02
   (`gates.adjudicator: agent`), so a run completes unattended.
4. **The owner** — the same `gate()`, answered by a human, restored globally with `gates.adjudicator: owner`, or
   per gate KIND with `gates.owner_kinds` — default `direction` since 2026-09-12 (the per-round direction card:
   the call that decides where the research goes next). GATE-1's idea pick (`seed_select`) is the owner's
   unconditionally — no config hands it to shape 3.
5. **The gate's own default** — a kind in `gates.default_kinds` (default `terminal_gate` since 2026-09-23) is a
   rule, not a card: it takes its (Recommended) option with no judge (`defaultGateAnswer`). The loop still does
   not acquit itself — the default was fixed per exit reason before the run, and the decision file is archived.

Note what shape 3 does and does not change. It does NOT let the loop acquit itself: the answer still comes
from a context that did not produce the work, which is the whole content of §0. What it DOES change is that
the acquitter is now a model rather than a person — so the failure mode moves from "the owner rubber-stamps
at 2am" to "the judge rubber-stamps every time". Two things hold it: the judge may only pick an option the
gate itself listed (an unlisted or unparseable answer is replaced by the conservative option and logged as a
`gate_adjudication_fallback`), and every verdict is archived with its rationale and an
`[adjudicated by agent]` marker, so a reader can always tell which decisions no human made.

## 4. Compound gates: split, don't average

A gate that mixes an execution fact with a merit judgment must be SPLIT: the presence/shape half goes to
a mechanical check (a preflight fact, a belt), the correctness half goes to an independent acquitter (a
V-check, a panel axis). Never blend the halves into one self-reported verdict.

## 5. The self-acquittal test

**"If removing the independent reviewer would still let the loop decide to stop, the loop is
self-acquitting."** Apply it to any new gate: delete the verifier/panel/oracle from the picture — if the
loop can still reach EXIT / ship / kill on the producer's say-so, the gate is broken.

## 6. Sensor ≠ gate

A surface-only independent reader (the M1 scale-contract reviewer, the ideation-integrity auditor) is a
SENSOR: it feeds intelligence to a downstream acquitter (V8, the GATE-1 owner card) and gates nothing
itself. A missing sensor is an intelligence gap, not a self-acquittal — but a sensor must never be cited
as if it were the acquitter.

## 7. Verdict persistence

Every Type-B verdict lands as an inspectable on-disk artifact (a verdict JSON / report file), and the
loop continues or stops on the recorded verdict — never on the producer's paraphrase of it.

---
Latest full audit: `dev/review-findings/70-gate-acquittal-ledger.md` (2026-07-09).
