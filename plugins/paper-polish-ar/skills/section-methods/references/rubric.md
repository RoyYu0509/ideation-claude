# Methods — rubric

Acceptance criteria for the Methods. Verdict + evidence per item. Not an operation log, and does not
repeat Results findings. Logic: **problem definition → overall framework → core method → design
rationale → implementation detail → validation setup → applicability scope.**

**Few-shot** (a generic "we extend … motivated by …" draft → the polished version that makes the
design *necessary*; a real author revision, when this section is hard): (no example ships in this release; add your own under `house-style/examples/venue-anchors/`).

## Items
1. **Problem definition.** The research problem, inputs/outputs, symbols, variables, assumptions,
   and evaluation metrics are all clearly defined.
2. **Overall framework.** The end-to-end flow is summarized and the relationships among modules are
   clear.
3. **Core method + rationale.** The core model / algorithm / loss / optimization / numerical scheme
   is described in detail, and each key design choice is given a reason and motivation (why this,
   not just what).
4. **Reproducibility.** Data sources, preprocessing, hyperparameters, training or solver details,
   software environment, random seeds, statistical repeats, error computation, and baseline setup
   are all specified.
5. **Validation setup.** Ablation, sensitivity analysis, benchmarks, or control experiments are
   described in terms of how they establish necessity, stability, and generalization.
6. **Assumptions, approximations & scope.** The method's assumptions, approximations,
   discretizations, boundary conditions, regularization, and the regime in which it is meant to
   apply are stated explicitly — not left implicit. (This is a first-class requirement in the
   original prompt — "明确所有假设、近似、限制和适用范围" — and the closing step of the
   problem-definition → … → applicability-scope logic, so it is scored here, not only flagged as an
   anti-pattern.)

## Theory / computational extra checklist (apply when relevant)
- Every mathematical object is defined before it is used.
- Every algorithm step corresponds to the objective, an error metric, or the physical problem.
- Every approximation, discretization, boundary condition, regularization, sampling strategy, and
  stopping criterion is stated.
- Every theorem / proposition / error estimate states its assumptions.
- Every numerical experiment's grid, data size, model size, training strategy, baselines,
  fair-comparison conditions, and error metrics are reproducible.

## The goal (use as the overall verdict)
The Methods is not there to show how good the results are. It is there to make the reader believe
the method is **well-defined, self-consistent, reliably implemented, fairly compared, and
reproducible.** Judge the section against that bar.

## Anti-patterns (flag)
- Operation-log / step-recipe phrasing with no rationale.
- Repeating Results findings.
- Undefined symbols; unstated assumptions, approximations, or limits.
- Unspecified baselines or comparison conditions.

---

[FILL IN: extra Methods/reproducibility criteria you and your advisor apply — e.g. a required
checklist for theorems or numerical experiments in your subfield.]
