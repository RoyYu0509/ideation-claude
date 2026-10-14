# SISC review rubric

The standard a `/review` panel judges a SISC manuscript against. SISC is computation-forward: the
deliverable is a numerical method/algorithm and its demonstrated performance. Theory (proofs,
error bounds) is subordinate evidence that justifies the method's design; it is neither required
nor sufficient on its own. Each axis maps to a `check-*` skill or a `review-panel` axis.
Composes with `_core/profile.md` (acceptance-bar block); this file is the detail.

## axes

### 1. computational rigor & numerical validation — the dominant axis (maps to check-results)
Is the method's claimed accuracy/cost established by the numerics?
- Convergence or error study on a problem where a rate or bound is claimed or expected.
- Hardware/wall-clock/throughput reporting for any performance claim (CPU/GPU model, core count,
  memory — specific hardware named, not "a modern GPU").
- Error metrics defined and applied consistently (relative L2, L∞, MdAPE, CDET — whichever is
  appropriate; both train and test reported for ML-adjacent papers).
- For ML-adjacent papers: architecture hyperparameters, training parameters (lr, batch, epochs,
  optimizer), and data sizes disclosed — sufficient for reproduction.
Reject-grade failing: a central accuracy or efficiency claim with no supporting error metric,
no hardware specification for a timing claim, or a single lucky run without variance/seeds.

### 2. reproduced & fair baselines (maps to check-results + review-panel: significance axis)
Does the paper adopt the benchmark problems and baselines an informed reader expects?
- "Same experimental setup as in [n]" is the SISC reproduce-then-extend norm: the new method
  is evaluated on a previously published benchmark before any new test cases are added.
- Baselines are the real competitors, run at their published or fairly tuned settings — not
  strawmen or undertuned versions.
- If a new method loses on one benchmark (e.g., Darcy for PODNO), the paper reports this
  honestly and provides a mechanistic hypothesis; it does not omit the benchmark.
Reject-grade failing: the only comparisons shown are those the new method wins; primary baselines
are missing or demonstrably undertuned.

### 3. convergence / error evidence (maps to check-results)
When the method is iterative, adaptive, or claims a rate:
- A convergence table or log–log plot showing the rate, with a reference-slope annotation.
- Error vs. mesh/step/mode count — the parameter that controls accuracy is swept.
- For operator learning / surrogate papers: energy capture ratio, test error vs. number of
  snapshots/modes reported where the truncation error is a design choice.
Reject-grade failing: a rate claimed in the abstract (e.g. O(Lη^{(1-L)d})) with no numerical
evidence of the rate; a convergence plot without a reference slope.

### 4. characterization of computational cost (maps to check-results)
Does the paper describe what the method actually costs, and compare it fairly?
- O(·) complexity analysis with the relevant parameters named (dimension d, levels L,
  coarsening factor η, modes M, etc.).
- Wall-clock comparison must hold architecture constant when comparing models (same parameter
  count, or parameter count reported explicitly for both).
- SVD / offline precomputation cost counted and disclosed (e.g. "the reported times for PODNO
  already include the time required for SVD in generating snapshots").
Major/reject: timing comparison that holds one model at a disadvantage by omitting a cost the
other method incurs, or an O(·) claim with no proof or numerical evidence.

### 5. originality & significance to the computational-methods community (maps to review-panel: significance axis)
Is the methodological advance clear and quantified?
- The SISC bar is a clear computational advance demonstrated quantitatively (accuracy and/or
  cost), not broad societal significance.
- The advance over the closest prior method is stated explicitly (enumerated differences or a
  direct comparison table/figure).
- Generality is calibrated to the tested regime — the paper claims performance on the classes
  it actually tests, not broader.

### 6. reproducibility (maps to check-results)
Could a competent reader reimplement this?
- All hyperparameters, problem setups (domain, boundary conditions, equation parameters,
  initial conditions), data generation procedures, and seeds disclosed.
- Algorithm pseudocode (or a formal Algorithm environment) present for non-trivial methods.
- Hardware environment for timing experiments disclosed (CPU/GPU model, memory, software stack).
- Code availability stated (even if not mandated).

### 7. coherence / clarity for the specialist (maps to review-panel: coherence axis + check-logic)
Does the paper tell one clear computational story?
- Gap → method design choice → validation arc is linear — no orphaned subsections.
- Notation consistent; every symbol defined before first use (the "Notation." paragraph norm).
- Results subsections open with the question they answer ("We assess …", "We explore …").
- The "Setup/Results/Observations" micro-structure is not required but, if used, it must be
  applied consistently across all experiment subsections.

## how to run it
Each panel reviewer foregrounds one axis (see reviewer-profiles.md) but touches all briefly. The
AC synthesizes against this rubric and ranks issues by reject-risk (see scoring.md). Mark
anything not assessable from the manuscript as needs_author.
