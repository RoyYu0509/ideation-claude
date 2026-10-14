<!-- SINUM OVERLAY profile. COMPOSES OVER ../_core/profile.md — list ONLY the fields that differ from or
     extend the SIAM core. Anything not mentioned here inherits the core verbatim. Resolver loads
     _core/* then this; these fields win. Evidence: ../papers/{2505.22103v1,2507.00193v2,2510.04751v1}.md -->
# Venue profile (OVERLAY) — SIAM Journal on Numerical Analysis (SINUM)

## identity (delta)
- venue: SIAM Journal on Numerical Analysis (SINUM)
- stance: ANALYSIS/PROOF-FORWARD. The deliverable is a convergence/error/stability theorem and its
  numerical confirmation; an algorithm exists to carry the theory, not as the headline.

## register (delta)
Analysis-forward emphasis: the prose carries theorem statements, proof sketches, and interpretive
commentary on the proofs. Convergence rate — the exponent in R^{-k}, h^p, or ∆t^q — is the
currency of every result claim. Wall-clock, GPU throughput, and hardware benchmarking are NOT
expected and read as off-register for pure theory papers; do not report them unless the paper makes
a computational-cost claim that is part of the theoretical contribution. Theorems with descriptive
parenthetical names ("Theorem 3.1 (Sufficient condition)", "Theorem 4.3 (unconditional stability)")
are the primary structural unit; the surrounding prose — setup paragraph, interpretive paragraph
after the proof — carries the argument. [2505.22103v1, 2507.00193v2, 2510.04751v1]

## conventions (deltas over core)

### theorem apparatus
DENSE and CENTRAL. A SINUM paper without theorems is atypical. Every major claim — stability,
convergence, well-posedness, error bound — is stated as a named environment:
- Label format: "Theorem X.Y (descriptive name)" or "Lemma X.Y (descriptive name)" — the
  parenthetical name is a SINUM signature convention; it should be descriptive, not a mere
  abbreviation. Examples from the roster: "Theorem 3.1 (Sufficient condition)", "Lemma 3.1
  (Restrict parameter p)", "Theorem 3.4 (Optimized transmission parameter: Version II)",
  "Theorem 4.2 (existence and uniqueness)", "Theorem 4.3 (unconditional stability)".
  [2505.22103v1 §3, 2507.00193v2 §4]
- Every theorem is followed immediately by an interpretive prose paragraph that explains what the
  theorem establishes in plain mathematical language. Proofs or interpretations are not left to the
  reader. [2510.04751v1 §2-3]
- Lemmas serve as explicit stepping stones: "With the help of Lemma 3.1 and Lemma 3.2, we can now
  identify…" is the standard bridge sentence. [2505.22103v1 §3]

### proof placement
- Short to medium proofs: inline immediately after the theorem, in the main body. All proofs in
  [2505.22103v1] are inline (no appendix). [2507.00193v2] places most proofs inline and defers one
  technical inequality proof to Appendix B. [2510.04751v1] defers all three major proofs to
  appendices, keeping main text lean.
- Long proofs (those that would interrupt the argument arc for multiple pages): deferred to a lettered
  appendix (A, B, …), with a main-text pointer: "The proof of Theorem 2.1 is given in Appendix A.3."
- Proof blocks begin "Proof." and close with □ (never QED or ⊠ in this roster).
- Inline proofs may be exhaustively case-structured: "Case 1 / Case 2", "(i) / (ii) / (iii)",
  sign-analysis of partial derivatives, sub-case enumeration. "No-hand-waving" is a SINUM expectation.
  [2505.22103v1 §3, Theorem 3.3 proof]

### algorithms
No formal Algorithm environment is the default for analysis-focused SINUM papers — the method is
stated as a displayed system of equations (numbered problem P, P1, P2…) or as a "Stage 1: / Stage 2:"
bold prose block. [2505.22103v1, 2507.00193v2] When a genuine computational algorithm is needed, a
numbered Algorithm box with prose steps (not pseudocode) is acceptable. [2510.04751v1, Algorithm 4.1]
Do NOT reformat the author's choice; do NOT add algorithm boxes to papers that describe methods via
displayed equations.

### tables
RARE or absent in pure theory papers. [2507.00193v2] and [2510.04751v1] have ZERO tables; all
quantitative results are carried in figures. [2505.22103v1] has exactly one table (iteration counts
at a fixed tolerance). When present: booktabs style (top/header/bottom rules, no vertical rules),
caption above, no bolding of best values. Do not add tables to papers that carry results in figures —
this is a deliberate SINUM style choice, not an oversight.

### performance reporting
DO NOT ADD performance-bragging content. Convergence rate (the theoretical exponent confirmed
numerically) is the primary evidence. Wall-clock timing appears only when it is a stated contribution
of the paper (as in [2510.04751v1] §5.2 "Computational efficiency," where the cost claim is
part of the theoretical content). Absent a cost claim, omit timing entirely. Never add GPU/CPU
hardware boasting. [voice.md negative-space rule: "No efficiency/GPU bragging in analysis-leaning work"]

### contributions framing
Contributions are woven into the final paragraphs of the Introduction (not a bulleted list) in
classical theory papers. [2505.22103v1, 2510.04751v1] A bulleted "The main contribution of this
work can be summarized as follows:" list is acceptable when the paper is close to the methods end of
the theory-methods continuum. [2507.00193v2 §1] Either form is fine; do NOT convert prose
contributions to bullets or vice versa.

### "§" and Outline/Notation conventions
Section cross-references use "§" (section sign) universally — never "Section 4" written out, though
"Section" is also tolerated as a variant. An explicit bold "**Outline.**" paragraph at the end of the
Introduction is near-invariant. A bold "**Notation.**" paragraph immediately following, defining all
global symbols before §2, is common in equation-heavy papers. [2510.04751v1] Preserve both.

### convergence-study conventions (numerical experiments)
- Results subsections open with a one-sentence topic statement ("We first verify …", "We then
  consider …") followed by explicit fixed-vs-varied parameter setup, then a figure pointer.
- Convergence is shown as log-log plots with annotated reference-slope lines ("~R^{-1}", "~h^2"),
  color+linestyle redundancy. Rates are stated verbally in the prose ("we observe a second-order
  convergence"), not solely read off the axes. Every claimed rate is tied to a theorem number:
  "consistent with the theoretical prediction of Theorem 3.2." [2510.04751v1 §5]
- Bold run-in lead-ins organize dense experiments sections: "**Decay of strains.**", "**Geometry
  error.**", "**Energy error.**", "**Computational efficiency.**" instead of proliferating
  sub-subsection numbers. [2510.04751v1 §5.2]

## acceptance-bar (delta — detail in review/)
- reviewers reward: rigorous theorem statements with complete proofs; sharp/optimal convergence rates
  with explicit constants or exponents; honest statement of assumptions (regularity, stability) needed
  for each result; numerical experiments that confirm the proved rates (matching slopes on log-log
  plots); honest scope (what the analysis does NOT cover, stated up front).
- reject triggers: theorem stated but proof deferred indefinitely or absent; convergence rate claimed
  but not confirmed numerically; assumptions hidden or unstated; "it can be shown" without a proof or
  a citation; performance claims made in place of a convergence analysis.
- novelty/significance bar: a genuine analytical advance — a new stability result, sharper error
  bound, removal of a restrictive assumption, a new class of problems brought under a rigorous
  framework. Computational speedup alone, without a theoretical contribution, does not clear the bar.

## anchors (this overlay)
- before→after section few-shots: abstract.md, introduction.md, results.md, methods.md, discussion.md
- figure-style guide (→ /polish-figures): figures.md
- panel kit: review/{rubric.md, reviewer-profiles.md, scoring.md}
- exemplar dossiers: ../papers/{2505.22103v1, 2507.00193v2, 2510.04751v1}.md
