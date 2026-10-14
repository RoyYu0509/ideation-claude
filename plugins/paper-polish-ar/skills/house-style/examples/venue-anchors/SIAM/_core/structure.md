<!-- SIAM-family CORE macro-structure & argument arc (invariant across SISC/SINUM/MMS). Consumed by the
     keynote pass (to set the structural target), the reviser (to restructure toward it), and check-logic
     (to judge argument shape). Sub-brand-dependent structure (theorem density, proof placement,
     tables-vs-figures, performance section) is in the overlay, NOT here. Evidence: ../papers/. -->
# SIAM family — macro skeleton & argument arc (CORE)

## The invariant skeleton
```
Title (descriptive "Method for Problem" / "ACRONYM: expansion")
Abstract (single funnel paragraph, ~150–220 words)
MSC codes. + Key words.
1. Introduction
     · establish the territory (the problem & why it matters, technically)
     · survey related work BY METHOD FAMILY, woven in (often bold-lead-in paragraphs) — not a separate section
     · establish the GAP / what existing methods cannot do
     · state the contribution (prose, or an explicit bullet list in ML-adjacent papers)
     · (optional) explicit Limitations / scope paragraph
     · close with a "the paper is organized as follows" OUTLINE paragraph
     · (common) a "Notation." paragraph defining global symbols before §2
2. Formulation / Methods / Material  (the objects, assumptions, and method, define-before-use)
3. Results / Numerical Experiments   (the evidence; each subsection = one question)
4. Conclusions  (past-tense summary + properties/advantages + brief future work; NO broader impact)
References (numbered, author-sorted)
Appendix (long proofs / derivations deferred here — placement is sub-brand-dependent)
```

## Argument arc (Swales CARS, applied-math idiom)
1. **Territory** — name the problem and its technical/computational challenges concretely (often with a motivating equation or figure).
2. **Gap** — survey the method families that attack it and show precisely where each falls short (this IS the related-work, in-line).
3. **Niche** — state what this paper does that closes the gap; differentiate from the CLOSEST prior method explicitly (enumerated points are common).
4. **Evidence** — formulation → method → validation, each claim tied to a proof, error metric, or benchmark.
5. **Honest close** — restate what was achieved and its limits; future work; no significance inflation.

## Micro-structure devices (invariant)
- **Bold run-in lead-ins** organize dense method/results passages ("**Setup:**", "**Dimension lifting.**", "Mark./Refine./Estimate.") instead of deep sub-subsection numbering.
- **"Notation." paragraph** up front for global symbols; symbols defined before first use everywhere else.
- **Each Results subsection opens by stating the question it answers** ("We assess the performance of …", "We explore the sensitivity of …").

## Sub-brand-dependent (see the overlay, do NOT assume here)
- theorem density & naming; proof placement (inline vs appendix); tables-vs-figures-only; a dedicated performance/HPC section; formal Algorithm environments vs prose "Stage 1:/Stage 2:"; explicit Contributions bullet list.
