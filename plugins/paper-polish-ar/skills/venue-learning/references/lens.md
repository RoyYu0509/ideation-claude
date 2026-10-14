# The extraction lens + the per-paper dossier template

A venue's house style decomposes into **7 dimensions**, each observation tagged across **3 tiers**.

## The 7 dimensions
1. **Macro-structure** — section ordering + each section's job + the argument arc (territory→gap→
   contribution→evidence→close); where contributions/limitations/related-work/outline live.
2. **Section rhetorical moves** — abstract shape; intro move-structure (Swales CARS); how related work is
   organized; how each results subsection OPENS; conclusion moves; characteristic micro-patterns (bold
   run-in lead-ins, bulleted contributions).
3. **Prose voice (micro)** — sentence rhythm; connective tissue; hedging / claim-strength calibration;
   first-person-plural vs passive; equation-in-sentence integration; venue-acceptable-but-AI-flaggable
   vocabulary; the target voice's verbatim exemplars.
4. **Math & notation** — notation system; define-before-use; equation density; theorem-environment style
   + proof placement (inline vs appendix), if any.
5. **Evidence / results conventions** — the standard validation battery; how numbers are reported; table
   style; reproduce-then-extend; baselines / ablations / error-analysis / convergence present?
6. **Figure / visual style** (→ /polish-figures) — figure types; palette; line/marker styles; panel layout
   & subfigure labeling; colorbar conventions; caption detail; table visual style. READ THE FIGURES AS IMAGES.
7. **Citation / title / metadata** — citation style + density; title style; MSC/keywords; abstract format.

## The 3 tiers (tag EVERY observation)
- **Tier A — INVARIANT core**: holds across (nearly) all papers → folds into `_core/`.
- **Tier B — AXIS of variation**: differs by sub-brand/sub-genre (e.g. theory-forward vs computation-
  forward) → becomes an overlay delta. Record the axis AND its values.
- **Tier C — NEGATIVE SPACE**: what the venue does NOT do (no hype/SOTA, no broader-impact, no GPU-bragging
  in theory papers, spelling). Goes in `_core/voice.md`. The highest-value half for an AI reviser.

## Per-paper dossier template (each fan-out subagent fills this, writes to `papers/<id>.md`, returns a digest)
```
0 Metadata — title; authors; arxiv id+class; journal/sub-brand (or inferred); pages; counts
  {figures, tables, theorem-like envs, algorithms, numbered display eqs, references}; sub-genre verdict
  {theory/proof | methods/numerical | mixed} + evidence.
1 Macro-structure — verbatim section tree; argument arc; contributions/limitations/related-work/outline; INVARIANT vs PAPER-SPECIFIC.
2 Section rhetorical moves — abstract shape; intro CARS; related-work organization; section openers (1-2 verbatim each); micro-patterns.
3 Prose voice — rhythm; connectives; hedging/claim calibration; we/passive; equation integration; 3-5 verbatim exemplar sentences; AI-flaggable vocabulary observed.
4 Math & notation — notation; define-before-use; equation density; theorem style + proof placement.
5 Evidence/results — validation battery; number reporting; table style; baselines/ablations/error-analysis/convergence; how claims tie to numbers.
6 Figure/visual style [FROM THE IMAGES] — inventory & types; palette; lines/markers; panel layout & labeling; fonts; colorbar; caption detail; table style; per-figure note for 2-4 figures.
7 Citation/title/metadata — citation style + density; title style; MSC/keywords; abstract format & length.
8 Off-lens — venue signals the 7 dimensions did NOT capture (these GROW the lens).
```
Evidence rule: every observation carries a verbatim quote (≤25 words) or a precise location. Tag INVARIANT
vs PAPER-SPECIFIC. Leave an **off-lens** slot so the data can reveal dimensions you did not predict
(cross-reference/typography conventions and the negative-space tier both emerged this way for SIAM).
