# Default review rubric — generic top-journal

The standard a `/review` panel judges a manuscript against when no venue-specific profile is set.
Five axes weighted evenly: no single axis dominates, in contrast to a specialist methods journal
(where technical soundness leads) or a flagship (where broad significance leads). Each axis maps
to a `check-*` skill the reviewer also retrieves.

## axes

### 1. technical soundness (maps to check-results)
Is the authors' case established by the evidence? Look for:
- every accuracy or performance claim backed by a reported number, not asserted;
- fair, complete baselines (the obvious competing methods, honestly tuned, not strawmen);
- statistics where the method is stochastic or variable (error bars, seeds, repeats);
- ablations or controls that isolate the claimed contribution, where the central claim depends on that
  isolation (a load-bearing ablation is required; a completeness one the claim does not rest on is a
  minor suggestion);
- any result that contradicts itself across sections.
Reject-grade failing: a central claim with no supporting evidence, or no fair comparison to the
relevant prior work.

### 2. originality (maps to review-panel: significance axis)
Is the contribution genuinely new relative to prior work, and is the distinction stated explicitly?
The paper must identify the closest prior method and say clearly how this work advances on it. Flag
novelty asserted but never distinguished from the obvious baseline.

### 3. significance (maps to review-panel: significance axis)
Does this matter to the paper's own field? A contribution need not be broad to be significant, but
it must advance understanding or practice in a meaningful way. Incremental novelty presented as a
major advance is penalized. A clear, modest, honest contribution is preferred.

### 4. reproducibility (maps to check-results)
Could a competent reader in the field reproduce the key results from the paper plus any supplementary
material? Look for: methods described at sufficient detail; hyperparameters, seeds, and data splits
stated; error definitions given; any result that depends on an undisclosed choice.

### 5. coherence and clarity (maps to check-logic + check-readability)
Does the paper tell one clear story? Does gap → contribution → results → discussion line up? Is
notation consistent throughout? Can a specialist in the field follow it without re-reading? Does the
abstract match the conclusions? Clarity is judged for the paper's own field audience, not a generalist.

## how to run it
Each panel reviewer foregrounds one axis (see reviewer-profiles.md) but touches all five briefly. The
AC synthesizes against this rubric and ranks issues by reject-risk (see scoring.md). Mark anything not
assessable from the manuscript as needs_author rather than inventing it.
