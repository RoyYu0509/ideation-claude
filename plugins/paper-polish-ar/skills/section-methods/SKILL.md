---
name: section-methods
description: Rubric and writing heuristics for the Methods of a top-journal paper. Loaded by name (section-methods) by the reviser and by check-logic to score.
user-invocable: false
---

# Methods

Heuristics and acceptance criteria for the Methods (problem-definition through reproducibility and scope; define every object before use).

- The full rubric (the checkable acceptance criteria, with verdict + evidence per item) is in
  `references/rubric.md`. Read it before writing or scoring this section.
- Model passages and before/after pairs specific to this section live in `house-style/examples/venue-anchors/`.

## Writing register for this section

**Methods = reproducibility contract.** A reader who has not read any other section should be able
to reconstruct exactly what was done from this section alone.

- **Name every object before use.** No "standard techniques," "common practice," "following [X] we
  proceed," or "analogously" without an explicit definition or a specific citation *plus* a statement
  of exactly what was taken from it. "We use [X]" alone is not sufficient.
- **Every design choice needs a stated reason.** "We use X" → "We use X because Y." If the
  motivation cannot be given in-line, cite it. A methods section with unjustified choices is an
  operation log, not a scientific account.
- **No hand-wavy connectors.** "Similarly," "in the same spirit," "inspired by" require a specific
  citation AND an explicit statement of what was taken and what was changed. "Standard" and
  "conventional" are not justifications.
- **Precision over flow.** When readable prose conflicts with exact naming of scope, assumptions, or
  constraints — choose precision. A sentence can be long and dense if it is rigorous.
- **Assumptions are first-class, not parenthetical.** State approximations, boundary conditions,
  regularization choices, and regime limitations as main claims ("We assume X"). Not as asides
  ("for simplicity, X") or buried caveats. Each non-trivial assumption earns its own sentence.
- **Methodology, not code documentation.** Describe the algorithm, model, and estimator as a scientific
  account a reader can reconstruct — not as the code that implements them. Never name source files or
  functions in the prose (no `\texttt{foo.py::bar}`, no "computed by `scaling.py`"); cite a library by
  name at most. Code-to-number provenance stays in the repo/registry, not the manuscript. (This is an
  assignment tell — see [`house-style/references/ai-tells.md`](../house-style/references/ai-tells.md).)

## Reminders that apply to this section

See [`../house-style/references/section-reminders.md`](../house-style/references/section-reminders.md).
