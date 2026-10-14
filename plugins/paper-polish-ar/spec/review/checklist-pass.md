<!-- review/checklist-pass.md — the mechanical-matrix pass. ONE cheap neutral context (role `checklist`,
     model/think from config review.roles) sweeps the whole paper and fills four fixed matrices. This work
     was deliberately TAKEN OFF the adversarial reviewers (breadth obligations crowd out the depth hunt)
     and off the OWNER (whose depth belongs to synthesis). Output routes to the OWNER's synthesis ONLY —
     never into a reviewer's brief (cold-read topology). Runs fine in parallel with the panel. -->

# Checklist pass — mechanical breadth, guaranteed coverage

**Brief for the checklist agent**: read the WHOLE paper (typeset PDF page-by-page when available — each
page renders as an image, so figures/tables/equations are visible; else all .tex sources). You are
NEUTRAL: you inventory, you do not judge acceptability. Fill ALL FOUR matrices — every section, every
figure/table, every axis; no sampling. Return CHECKLIST_SCHEMA.

## The four matrices

1. **section_structure** — for EACH section: is its ARGUMENT structure `sound | weak | broken`
   (mis-ordered argument, buried contribution, a section that does not answer its must-answer question,
   intro/discussion/abstract telling different stories), with the one structural fix it most needs.
   Structure, not wording.
2. **caption_axis_fidelity** — for EACH figure/table: do the CAPTION + AXIS LABELS truthfully describe
   what is actually plotted (mislabeled axis, caption claiming more than the panel shows, units/scale that
   misrepresent)? One row per MISMATCH; empty array if all faithful.
3. **experiment_coverage** — against the paper's claims, judge the publication-grade suite over the EIGHT
   fixed axes: `main, baseline, ablation, stability, parameter_sensitivity, error_convergence,
   structure_preservation (only for a structure-preserving claim), cost_efficiency`. Status per axis:
   `present | absent | n_a` + where. **absent ≠ n_a**: an axis the claim admits but the paper neither
   reports nor justifies as N/A is `absent`.
4. **literature_coverage** — are the classic, recent, and DIRECT-COMPETITOR methods cited? For each
   missing category: `{category, why_needed, search_keywords}`. NEVER invent a specific citation.

```js
CHECKLIST_SCHEMA = { type:'object',
  required:['section_structure','caption_axis_fidelity','experiment_coverage','literature_coverage'],
  properties:{
    section_structure:{type:'array', items:{type:'object', required:['section','verdict'], properties:{
      section:{type:'string'}, verdict:{enum:['sound','weak','broken']},
      issue:{type:'string'}, fix:{type:'string'} }}},
    caption_axis_fidelity:{type:'array', items:{type:'object', required:['figure','issue'], properties:{
      figure:{type:'string'}, issue:{type:'string'}, severity:{enum:['reject','major','minor']} }}},
    experiment_coverage:{type:'array', items:{type:'object', required:['axis','status'], properties:{
      axis:{enum:['main','baseline','ablation','stability','parameter_sensitivity','error_convergence','structure_preservation','cost_efficiency']},
      status:{enum:['present','absent','n_a']}, where:{type:'string'}, note:{type:'string'} }}},
    literature_coverage:{type:'object', properties:{
      assessment:{type:'string'},
      missing:{type:'array', items:{type:'object', required:['category'], properties:{
        category:{type:'string'}, why_needed:{type:'string'},
        search_keywords:{type:'array', items:{type:'string'}} }}} }},
    read_source:{enum:['image_pdf','tex_fallback']} } }
```

## How the OWNER consumes it (synthesis-side rules)

- Every `broken` (and load-bearing `weak`) section → a STRUCTURAL punch-list item (axis
  `coherence`/`structure`; the fix is a restructure diagnosis for the author/a later pass — not wording).
- Every caption/axis MISMATCH → a punch-list item (axis `presentation`; proposed_fix = correct the
  caption/axis text to match what the frozen figure shows — never repaint the figure). Keep the row's severity.
- An `absent` experiment_coverage axis that is LOAD-BEARING for the central claim → a reject/major
  needs_author item; a marginal absence stays recorded (minor). This mirrors the plan-side HANDOFF axes
  and the verifier's V9 (absent ≠ N/A) at the review end.
- Missing literature categories → needs_author items carrying the search keywords.
- The matrices also serve as your false-rejection filter: a reviewer demand that the coverage matrix marks
  `present` gets dismissed with a merge_note pointing at `where`.
