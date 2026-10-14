<!-- MMS review rubric. Each axis maps to a check-* skill or review-panel axis. Specialized to MMS:
     multiscale coupling correctness + two-sided estimator rigor + convergence-rate validation +
     scope honesty are the dominant axes. No numeric scores (owner policy: categories only). -->
# MMS review rubric

The standard a `/review` panel judges a SIAM Multiscale Modeling & Simulation manuscript against.
MMS sits at the intersection of theory and computation; both halves are assessed, and a paper that
excels at one while being absent in the other is incomplete.

## axes

### 1. correctness of the multiscale coupling / estimator (maps to check-results + check-logic)
Is the coupling or upscaling mechanism correctly set up? Is the estimator formula correct and
computable? Where a two-sided (reliability + efficiency) result is claimed, are BOTH bounds proved?
Is the proof sketch in the body consistent with the deferred proof? Is every theorem's hypothesis
checked for the stated application (e.g., strong stability condition for the QM/MM estimator)?

Reject-grade failing: a claimed two-sided estimator where only one bound is proved; a coupling
scheme that is inconsistent at the scale interface (e.g., mismatch between QM energy and MM force
convention); a theorem statement whose hypotheses are not verified for the numerical tests.

### 2. rigor of the a posteriori / error analysis (maps to check-logic + check-results)
Are convergence rates stated with matching reference: (a) a proof (theorem/corollary) giving the
rate analytically, and (b) a numerical experiment with dashed reference lines at that exact rate?
Is the convergence parameter (R, h, N) clearly identified and consistent between theory and figures?
Is the data oscillation or pre-asymptotic regime acknowledged where it appears?

Reject-grade failing: a convergence rate claimed without a theorem or without a reference line in
the log-log plot; a rate that does not appear in the numerical figures; a pre-asymptotic flattening
unexplained in text.

### 3. fairness of the numerical validation across scales / defect types (maps to check-results)
Does the benchmark suite span the relevant range? For coupling/boundary-condition papers: are
multiple defect types or scale regimes tested (not a single cherry-picked geometry)? Are the
reference solution and tolerance stated precisely? For adaptive algorithms: is the quasi-optimal
cost splitting shown, not just the error convergence?

Reject-grade failing: a single defect geometry tested when the method claims generality across
geometries; a reference solution whose accuracy is not verified; adaptive cost-splitting claimed
without a plot.

### 4. significance for the multiscale community (maps to review-panel: significance axis)
Does this advance the practice of multiscale simulation — a new estimator, a new coupling method,
a faster boundary condition? Would researchers in QM/MM, atomistic-continuum, or homogenization
adopt this? Field-internal significance is sufficient; broad interdisciplinary appeal is NOT
required. A side result that is independently useful (e.g., dipole tensor error estimate) counts.

Reject-grade failing: a paper that is an incremental tweak of the closest prior method with no
measurable convergence improvement and no new theoretical guarantee.

### 5. coherence / reproducibility for the specialist (maps to check-logic + check-readability)
Does the paper's argument arc hold — gap → estimator construction → proof → algorithm → validation?
Are all symbols defined (Notation paragraph present, define-before-use discipline)? Are benchmark
parameters (defect geometry, reference radius R_dom, tolerance) stated so a specialist could
reproduce? Sketch-then-defer pointer present for each deferred proof?

Reject-grade failing: missing Notation paragraph in a symbol-heavy paper; benchmark parameters
unstated; a deferred proof section with no pointer from the main text; broken define-before-use.

## how to run it
Each panel reviewer foregrounds one axis (see reviewer-profiles.md) but covers all five briefly.
The AC synthesizes against this rubric and ranks issues by reject-risk (see scoring.md). Mark
anything not assessable from the manuscript as needs_author — never invent data or proof steps.
