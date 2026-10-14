# Nature Computational Science / SciML review rubric

The standard a `/review` panel judges a Nature-family submission against. Each axis maps to a `check-*`
skill the reviewer also retrieves. Adapted from the Nature reviewer axes (originality, scientific
importance, interdisciplinary readership, technical soundness, readability for non-specialists). The
defining difference from JCP: BROAD significance and cross-field interest are top-weighted, not
optional.

## axes

### 1. significance & broad interest — the dominant axis (maps to review-panel: significance axis)
Does the work matter beyond the immediate subfield, and does the paper make that case? Look for a real
implication for a wider community, not just field-internal usefulness. Reject-grade failing: a sound
but incremental / field-internal result with no demonstrated broad relevance (this is the classic
Nature-family rejection that would NOT be a rejection at a specialist venue).

### 2. originality (maps to review-panel: significance axis)
Is the advance genuinely new and explicitly distinguished from the nearest prior work? Flag novelty
asserted but not differentiated, or a known idea repackaged.

### 3. technical soundness (maps to check-results)
Is the central claim established by well-controlled evidence: fair baselines, error/uncertainty
analysis, ablations, statistics where stochastic? A Nature-family paper still needs JCP-grade rigor;
the difference is where the bar additionally demands breadth, not less rigor.

### 4. accessibility for non-specialists (maps to review-panel: coherence axis + check-readability)
Can a scientist outside the subfield follow the opening, grasp what was done, and see why it matters?
Jargon-first openings, undefined notation in the main text, and a thesis only a specialist can parse
fail this axis. This axis carries far more weight here than at JCP.

### 5. reproducibility (maps to check-results)
Methods (at the end) + SI sufficient to reproduce: data, code/availability, hyperparameters, setups.

## how to run it
Each panel reviewer foregrounds one axis (see reviewer-profiles.md) but touches all five briefly. The
AC synthesizes against this rubric and ranks by rejection risk (see scoring.md) — at this venue, a
"sound but not broadly significant" verdict is itself a high-severity item. Mark anything not
assessable from the manuscript as needs_author rather than inventing it.
