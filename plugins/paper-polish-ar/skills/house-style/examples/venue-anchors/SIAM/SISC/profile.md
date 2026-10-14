<!-- SISC OVERLAY profile. COMPOSES OVER ../\_core/profile.md — list ONLY the fields that differ from or
     extend the SIAM core. Anything not mentioned here inherits the core verbatim. Resolver loads
     _core/* then this; these fields win. Evidence: ../papers/{2312.15837,2502.05088,2503.01276,2504.18513,2510.14197}.md -->
# Venue profile (OVERLAY) — SIAM Journal on Scientific Computing (SISC)

## identity (delta)
- venue: SIAM Journal on Scientific Computing (SISC)
- stance: COMPUTATION-FORWARD. The deliverable is a numerical method/algorithm and its demonstrated performance; theory is present to JUSTIFY the method, not as the headline.

## register (delta)
Computational-methods emphasis: the prose carries the algorithm, its complexity/cost, and its measured accuracy and speed. Reporting computational performance (hardware, wall-clock, throughput) is expected and is NOT hype — it is evidence. Theorems/propositions appear to ground design choices (error/stability bounds), not to fill the paper.

## conventions (deltas over core)
- theorem apparatus: PRESENT BUT SUBORDINATE — a few lemmas/propositions/theorems that justify the method (error, stability, convergence, complexity). A purely computational SISC paper may have ZERO theorems and instead state an O-notation cost claim (e.g. in the abstract) — both are accepted. Detect per paper; do not force theorems in or out.
- proof placement: short proofs inline; longer proofs deferred to an appendix with a main-text pointer ("The proof of Theorem 3.1 is given in Appendix A.3."). Either is fine.
- algorithms: a formal ruled Algorithm environment with "Input:/Output:" and explicit "end for" is common; a prose "Stage 1:/Stage 2:" or bullet list is equally accepted. Do NOT reformat the author's choice.
- tables: EXPECTED. booktabs style — top/header/bottom rules, NO vertical rules; caption ABOVE the table; numbers in scientific notation X.XX×10^{-k} to ~2 significant figures; train/test (or two paired) errors reported together; best value usually NOT bolded.
- performance reporting: a first-class concern — disclose hardware (CPU/GPU model, core count, memory), wall-clock / throughput, and (for ML-adjacent work) training cost. A dedicated performance subsection is common.
- benchmarks: REPRODUCE-THEN-EXTEND — take test cases from prior papers ("same experimental setup as in [n]"), reproduce the baseline, THEN add the new method; compare fairly on a shared axis/colorbar.
- contributions: an explicit bulleted "our contributions are:" list is optional — common in ML-adjacent SISC papers (and an explicit Related Work subsection may accompany it), absent in classical-numerics ones where the niche is occupied via dense prose. Either is fine.

## acceptance-bar (delta — detail in review/)
- reviewers reward: rigorous numerical validation on canonical/benchmark problems; reproduced & fair baselines; ablations; convergence/error study; a clearly characterized computational cost; reproducibility (seeds, hyperparameters, problem setups, hardware).
- reject triggers: cherry-picked or insufficient numerics; missing/unfair baselines; performance claims without measurement; overselling generality beyond the tested regime.
- novelty/significance bar: a clear computational-methods advance demonstrated QUANTITATIVELY (accuracy and/or cost). Broad appeal not required.

## anchors (this overlay)
- before→after section few-shots: abstract.md, introduction.md, results.md, methods.md, discussion.md
- figure-style guide (→ /polish-figures): figures.md
- panel kit: review/{rubric.md, reviewer-profiles.md, scoring.md}
- exemplar dossiers: ../papers/{2312.15837, 2502.05088, 2503.01276, 2504.18513, 2510.14197}.md
