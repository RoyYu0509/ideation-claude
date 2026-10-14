# SINUM review rubric

The standard a `/review` panel judges a SINUM manuscript against. Each axis maps to a `check-*`
skill the reviewer also retrieves. Specialized for SINUM: proof correctness and rigor is the
dominant axis; convergence rate sharpness/optimality is the primary technical result criterion;
assumption completeness is the main scope gate. Numerical soundness is required but secondary —
it confirms theory, not drives it.

## axes

### 1. proof correctness & rigor — the dominant axis (maps to check-logic, check-results)
Is every theorem proved completely and correctly? Look for:
- Every hypothesis stated explicitly and the proof confined to those hypotheses (no hidden regularity
  assumed mid-proof);
- Full case analysis — no "one can show" or "it is easy to see" without a citation or appendix
  pointer for a non-trivial step;
- Inline proofs end with □; deferred proofs are in a lettered appendix with a main-text pointer;
- Lemmas serve as explicit stepping stones; the bridge sentence from lemma to theorem is present;
- Proof steps for sign analysis, monotonicity, and case enumeration are shown, not asserted.
Reject-grade failing: a central theorem with a proof gap or an unstated assumption that, if stated,
would restrict the scope of the result significantly.

### 2. sharpness / optimality of convergence rates (maps to check-results)
Are the theoretical rates optimal, or does there exist a known lower bound that the paper's rates
don't match? Is the order of the method consistent with the classical results in the field?
- State the rate explicitly (R^{-2}, h^p) and compare it to the classical limit for the problem class;
- If sub-optimal, is the sub-optimality explained mechanistically, not apologized for;
- If the rate is claimed to be optimal, is the optimality justified (a lower-bound argument or a
  reference to the standard result);
- The numerical experiments must confirm the theoretical rate — matching slope on log-log — not
  just "approximately agree."
Reject-grade failing: theoretical rate claimed but numerical slope does not match, or optimality
asserted without justification.

### 3. completeness of assumptions (maps to check-logic, check-results)
Are all assumptions needed by each theorem stated explicitly and checked/checkable?
- Regularity assumptions (smoothness class of V, operator coercivity, strong stability) are
  stated with quantifiers (there exists c₀ > 0 such that);
- Problem-specific assumptions (non-overlapping subdomains, mesh non-degeneracy, mesh ratio bound)
  are listed before they are needed, not introduced mid-proof;
- The abstract setting is not tacitly more restrictive than the numerical examples imply;
- Scope limits stated in the Introduction are honored — results not proved for a case are not
  presented as if they are.
Reject-grade failing: a key assumption (e.g., "strongly stable solution") appears in the proof but
is not in the theorem statement, or the numerical examples test a regime the analysis does not cover.

### 4. numerical confirmation of theory (maps to check-results)
Does the numerical section genuinely confirm the proved rates?
- Log-log convergence plots with annotated reference-slope lines for every main rate claim;
- Two-curve comparison (baseline vs higher-order) in parallel so the improvement is visually
  demonstrable;
- Each experiment tied to a specific theorem by name ("consistent with Theorem 3.2");
- Fixed parameters stated (mesh size, time step, tolerance, hardware for cost experiments);
- No comparison against out-of-scope baselines; no cherry-picked problem instances.
Reject-grade failing: convergence claimed but only qualitative/snapshot figures provided (no log-log
slope); rate confirmed on a single problem instance only.

### 5. coherence & mathematical clarity for the specialist (maps to check-logic, check-readability)
Does the paper tell a single clear analytical story; is the notation consistent throughout;
can a specialist fluent in the sub-area follow every step without re-reading?
- Every symbol defined before first use; global conventions in a Notation paragraph;
- Theorem numbers cross-referenced correctly in the proof of each downstream result;
- Bold Outline paragraph closes the Introduction and matches the actual section structure;
- Remark environments used for design commentary and scope clarifications, not for results.

## how to run it
Each panel reviewer foregrounds one axis (see reviewer-profiles.md) but touches all five briefly.
The AC synthesizes against this rubric and ranks issues by reject-risk (see scoring.md). Mark anything
not assessable from the manuscript as needs_author rather than inventing it.
