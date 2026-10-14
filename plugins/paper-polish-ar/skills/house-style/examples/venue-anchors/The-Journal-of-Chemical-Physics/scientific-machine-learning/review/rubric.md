# JCP (chemical physics) / SciML review rubric

The standard a `/review` panel judges a chemical-physics / SciML manuscript against for *The Journal of
Chemical Physics*. Each axis maps to a `check-*` skill the reviewer also retrieves. Tuned for a
specialist chemical-physics methods journal: technical / physical rigor dominates; broad
interdisciplinary interest is NOT a requirement, but the work must answer a genuine chemical-physics
question.

## axes

### 1. technical / physical soundness — the dominant axis (maps to check-results)
Is the authors' case established by the evidence, and is the physics handled honestly? Look for:
- error and uncertainty analysis, and convergence studies (basis set, sampling, time step, finite size)
  wherever an accuracy claim is made;
- explicit approximations and assumptions — stated, and their effect bounded, not buried;
- fair, complete baselines (the obvious competing methods / reference data, tuned honestly, not strawmen);
- statistics where the method is stochastic (seeds, repeats, error bars), not single lucky runs;
- ablations that isolate the claimed mechanism, where the central claim depends on that isolation (a
  load-bearing ablation is required; a completeness one the claim does not rest on is a minor suggestion);
- every claim backed by a reported number, not asserted.
Reject-grade failing: a central accuracy claim with no error/uncertainty analysis, unstated
approximations that could control the result, or no fair baseline / reference.

### 2. originality / methodological advance (maps to review-panel: significance axis)
Is the contribution genuinely new vs prior chemical-physics & SciML work, and is the distinction
explicit? Flag novelty asserted but not distinguished from the obvious prior method or model.

### 3. significance to chemical physics (maps to review-panel: significance axis)
Does this matter to the chemical-physics community — a method or physical insight people would adopt,
not an incremental tweak — and does it answer a real chemical-physics question rather than a bare
chemistry/materials *application*? Field-internal significance is enough; do NOT demand broad
general-science reach (that is a Nature axis, not JCP).

### 4. reproducibility (maps to check-results)
Could a competent reader reproduce this from the paper + SI? System setups, Hamiltonians/levels of
theory, hyperparameters, training data, seeds, and error definitions present? Is there a Data
Availability statement?

### 5. coherence / clarity for the specialist (maps to review-panel: coherence axis + check-logic)
Does the paper tell one clear story; do question → method → results → discussion line up; is notation
consistent; can a chemical physicist (not a generalist) follow it without re-reading?

## how to run it
Each panel reviewer foregrounds one axis (see reviewer-profiles.md) but touches all five briefly. The
AC synthesizes against this rubric and ranks issues by reject-risk (see scoring.md). Mark anything not
assessable from the manuscript as needs_author rather than inventing it.
