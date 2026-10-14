# JCP / SciML review rubric

The standard a `/review` panel judges a JCP-SciML manuscript against. Each axis maps to a `check-*`
skill the reviewer also retrieves. Adapted from the Nature reviewer axes, retuned for a specialist
methods journal: numerical rigor dominates; broad interdisciplinary interest is NOT a requirement.

## axes

### 1. technical / numerical soundness — the dominant axis (maps to check-results)
Is the authors' case established by the numerics? Look for:
- error analysis and a convergence study wherever a numerical method claims accuracy or convergence;
- fair, complete baselines (the obvious competing methods, tuned honestly, not strawmen);
- statistics where the method is stochastic (seeds, repeats, error bars), not single lucky runs;
- ablations that isolate the claimed mechanism, where the central claim depends on that isolation (a
  load-bearing ablation is required; a completeness one the claim does not rest on is a minor suggestion);
- every claim backed by a reported number, not asserted.
Reject-grade failing: a central claim with no supporting error metric, or no fair baseline.

### 2. originality / methodological advance (maps to review-panel: significance axis)
Is the contribution genuinely new vs prior SciML / numerics work, and is the distinction explicit?
Flag novelty asserted but not distinguished from the obvious prior method.

### 3. significance to the field (maps to review-panel: significance axis)
Does this matter to the computational-physics / SciML community — a method people would adopt, not an
incremental tweak? Field-internal significance is enough; do NOT demand broad interdisciplinary reach
(that is a Nature axis, not JCP).

### 4. reproducibility (maps to check-results)
Could a competent reader reproduce this from the paper + SI? Hyperparameters, problem setups, data,
seeds, error definitions present?

### 5. coherence / clarity for the specialist (maps to review-panel: coherence axis + check-logic)
Does the paper tell one clear story; do gap → method → results → discussion line up; is notation
consistent; can a specialist (not a generalist) follow it without re-reading?

## how to run it
Each panel reviewer foregrounds one axis (see reviewer-profiles.md) but touches all five briefly. The
AC synthesizes against this rubric and ranks issues by reject-risk (see scoring.md). Mark anything not
assessable from the manuscript as needs_author rather than inventing it.
