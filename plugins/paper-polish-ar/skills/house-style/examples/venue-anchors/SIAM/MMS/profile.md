<!-- MMS OVERLAY profile. COMPOSES OVER ../_core/profile.md — lists ONLY the fields that differ from or
     extend the SIAM core. Anything not mentioned here inherits the core verbatim. Resolver loads
     _core/* then this; these fields win. Evidence: ../papers/{2007.05260v1,2210.05573v2}.md -->
# Venue profile (OVERLAY) — SIAM Multiscale Modeling & Simulation (MMS)

## identity (delta)
- venue: SIAM Multiscale Modeling & Simulation (MMS / SIAM Multiscale Model. Simul.)
- stance: THEORY + NUMERICS IN BALANCE. The deliverable is a method or analysis at the interface of
  multiple scales; both rigorous error guarantees AND numerical validation carry equal weight. Neither
  is subordinate to the other — a paper that proves an estimator without numerical tests, or that
  benchmarks without any theoretical bound, is incomplete for this venue. The coupling or upscaling
  mechanism itself is typically the scientific object.

## register (delta)
Multiscale/coupling emphasis: the prose frames the problem as a scale-bridging challenge (QM↔MM,
atomistic↔continuum, micro↔macro), motivates why a single-scale approach is insufficient, and
explains what the coupling/upscaling buys. Error analysis is not background — it is the argument:
a posteriori estimates, two-sided (reliability + efficiency) bounds, and convergence rates w.r.t. a
physical length or cell-size parameter are the primary evidence currency. Physical units (e.g., Å)
appear on convergence axes alongside mathematical norms. No wall-clock or GPU performance reporting
(SINUM/MMS culture: convergence rate is the currency). [2007.05260v1, 2210.05573v2]

## conventions (deltas over core)
- theorem apparatus: EXPECTED AND PROMINENT — theorems, lemmas, propositions, corollaries are central
  deliverables, not justifications for a computational method. A typical MMS paper has 5–10 named
  theorem-like environments covering reliability (upper bound), efficiency (lower bound), and
  convergence rate. Two-sided estimator results (BOTH upper and lower bounds proved simultaneously)
  are a recurring pattern. [2007.05260v1: Theorem 3.4 = two-sided; 2210.05573v2: Corollary 3.1]
- proof placement — SKETCH THEN DEFER: the dominant pattern is a "Sketch of the proof." inline
  in the body (typically 3–8 sentences naming the key steps) followed by "The details are given in
  Appendix A.N." or a numbered "Proofs and Extensions" section. Short lemmas may be proved fully
  inline; the longest proofs are always deferred. Do NOT silently move a sketch into an appendix or
  expand it to a full proof — the sketch IS the pedagogical signal that the author chose. [2007.05260v1:
  §3.2 Lemma 3.2 has explicit "Sketch of the proof." + "The details are given in Appendix A.2.";
  2210.05573v2: §3.2 "we provide a sketch of the proof" + "The detailed proof will be given in Section 6.1."]
- proof section naming: a stand-alone "Proofs and Extensions" numbered section (not an Appendix) is
  acceptable and appeared in [2210.05573v2] as §6. Either labeling (Appendix A / §N) is venue-valid;
  do not normalize one to the other.
- adaptive-algorithm presentation: SOLVE–ESTIMATE–MARK–REFINE loop is the canonical structure;
  each step is presented as a bold run-in heading within a formal Algorithm box or as bold lead-ins in
  prose. The Estimate step references the a posteriori estimator from the theory section. The Mark step
  names a specific marking strategy (e.g., Dörfler's strategy) with its parameter. [2007.05260v1: Algorithms 1 & 2]
- Outline + Notation paragraphs: INVARIANT for MMS. Both appear as bold unnumbered pseudo-subsections
  at the end of the Introduction. Outline = one sentence per section. Notation = pre-defines all
  global symbols (≲, abstract duality pair ⟨·,·⟩, function spaces, constants C, ≃). Both papers show
  this pattern identically. [2007.05260v1, 2210.05573v2]
- tables: RARE TO ABSENT. Both MMS exemplars have zero tables; all quantitative results appear in
  figures, and benchmark parameters are stated in prose. Do not add a results table to match SISC
  norms — if the author used figures + inline numbers, that is the correct MMS presentation style.
  [2007.05260v1: 0 tables; 2210.05573v2: 0 tables]
- contributions: stated as PROSE in the introduction body ("In the present work, we construct …"),
  NOT as a bullet list. The niche is occupied via dense prose with one or two "In the present work /
  The purpose of the present paper is to" sentences. [2007.05260v1, 2210.05573v2]
- related work: WOVEN into the introduction by method family, with citation-dense paragraphs.
  Not a standalone section. [2007.05260v1, 2210.05573v2]
- scope qualification: an explicit "As a proof of concept, we will restrict ourselves to …" or
  "Our presentation here is restricted to …" sentence appears near the end of the introduction body,
  before the Outline paragraph. This is how MMS papers bound their claims without undermining them.
  [2007.05260v1: "As a proof of concept, we will restrict ourselves to the tight binding model…";
   2210.05573v2: "Our presentation here is restricted to simple lattices and point defects."]
- physical + mathematical dual register: axes labeled in Å alongside norms such as ‖Dū − Dūi,R‖_{ℓ²}.
  The paper navigates this without explicit comment — both registers are natural to this community.
  [2210.05573v2: Figs. 4.3–4.6 x-axis in Å]
- extensions / side results: a "Proofs and Extensions" section or appendix containing bonus rigorous
  derivations of known formulae (Green's function derivation, stress formula) that fall naturally from
  the framework is venue-appropriate and valued. [2210.05573v2: §6.2–6.3]

## acceptance-bar (delta — detail in review/)
- reviewers reward: rigorous error analysis with BOTH upper and lower bounds; well-motivated
  multiscale/coupling setting; convergence experiments that match theoretical rates (reference lines on
  log-log axes for every claimed rate); honest scope qualification; reproducibility details (tolerance,
  defect geometry, reference solution size).
- reject triggers: one-sided estimator claimed as efficient without a lower bound proof; convergence
  plots that show improvement without dashed reference lines; physical multiscale motivation absent
  (could be a single-scale paper in disguise); missing scope qualifier that oversells generality.
- novelty/significance bar: a clear advance in coupling/estimator/upscaling theory OR a practical
  algorithm with provable guarantees that the multiscale community would adopt. Field-internal
  significance is enough — MMS is a specialist venue.

## anchors (this overlay)
- before→after section few-shots: abstract.md, introduction.md, results.md, methods.md, discussion.md
- figure-style guide (→ /polish-figures): figures.md
- panel kit: review/{rubric.md, reviewer-profiles.md, scoring.md}
- exemplar dossiers: ../papers/{2007.05260v1, 2210.05573v2}.md
