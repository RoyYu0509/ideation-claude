<!-- MMS scoring reference. Categorical severity only (reject / major / minor) — no numeric scores.
     Calibrated to MMS's theory+numerics-in-balance standard. -->
# MMS scoring reference

How the panel sets severity and the AC ranks the punch-list. Severities match the `/review` schema
(reject | major | minor). No numeric scores are assigned — categories and adjectives only.

## severity calibration (MMS)

- **reject** — a central guarantee is missing or wrong: a two-sided estimator result where only one
  bound is proved and the gap is structural (not a minor proof gap fixable by revision); a coupling
  mechanism that is physically inconsistent at the scale interface; a convergence rate claimed in both
  the theorem and the abstract but absent from (or contradicted by) the figures; a generality claim
  (e.g., "arbitrary point defects") for which no anisotropic or non-trivial case is tested; a deferred
  proof section that is genuinely missing (not just sketched). The paper cannot be accepted with these
  defects.

- **major** — the case is weakened but salvageable: a one-sided estimator result where the efficiency
  (lower bound) is claimed informally in the introduction but its proof is incomplete or its constant
  not bounded; missing reference lines in convergence figures (theory-numerics gap cannot be read);
  a pre-asymptotic flattening regime unexplained and potentially masking rate disagreement; one
  defect type missing from an experiment suite that the abstract promises; reproducibility gap (R_dom
  not stated, tolerance not given); proof pointer missing for a deferred lemma.

- **minor** — local, fixable without new experiments or new theory: undefined symbol at first use in
  a theorem statement; British spelling in a venue that requires American ("behaviour" → "behavior",
  "optimisation" → "optimization"); a completeness suggestion (an additional defect geometry the
  central claim does not rest on); "Sketch of the proof" label missing when only a sketch is given;
  a caption that omits the defect type for a multi-panel figure.

## fix_kind
- **self_fixable** — fixable by editing / restructuring with the paper's existing data: weaken an
  oversold generality claim to match the tested cases; add dashed reference lines to an existing
  figure; add the proof pointer sentence ("The proof is given in §6.1."); normalize spelling;
  define a symbol; tighten the Notation paragraph.
- **needs_author** — needs new work or author intent: run an additional defect geometry; prove the
  missing lower bound; state and verify a theorem hypothesis; provide the reference solution radius;
  decide whether to narrow a generality claim or defend it with a new experiment.

## recommendation posture (per reviewer; reviewer-like, not editorial)
- "supportive if the efficiency (lower bound) result is completed or the claim is narrowed"
- "promising, but the theory-numerics agreement is not established without reference lines"
- "the generality claim is not established from the provided numerical evidence"
- "currently not establishable without additional defect types in the experiment suite"
Do not state an editorial decision or claim fit to the venue as settled.

## AC ranking
Rank the punch-list by reject-risk: reject items first, then major, then minor. Within a severity,
order by how central the affected claim is to the paper's thesis. A missing lower bound in a paper
titled as a two-sided-estimator paper ranks above a missing defect type for a secondary experiment.
