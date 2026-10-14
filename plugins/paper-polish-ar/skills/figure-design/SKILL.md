---
name: figure-design
description: Decide WHAT a manuscript figure should show — chart type (archetype), axis windows, panel composition — from the ONE conclusion the reader must take away. Use when designing a new figure, judging whether an existing figure's DESIGN serves its message, writing or implementing a figure DESIGN BRIEF, or fixing design-level defects (invisible flat lines from oversized axes, all-at-ceiling bars, twin-axis charts, a table drawn as a figure panel, a near-empty negative-result panel). NOT a styling skill — rendering, de-AI defaults, legends/typography/code style live in research-figure-plotting.
user-invocable: false
---

# figure-design — the figure contract: conclusion → evidence → archetype

A manuscript figure is an ARGUMENT, not a record. Before any plotting code exists, three questions
must have answers, in this order:

1. **Conclusion** — the ONE sentence the reader must come away with. Write it down first. If you
   cannot write it, the figure should not exist.
2. **Evidence** — which quantities, comparisons, or distributions in the cached results carry that
   sentence. Everything else is clutter; leave it out or send it to the SI.
3. **Archetype** — the chart form that makes that evidence legible at a glance. Choose from
   `references/archetypes.md`; never default to "bar chart of whatever the script logged".

## The reader principle (the #1 failure mode this skill exists to kill)

**The reader of a figure is the paper's reader — never the experiment gate.** A plot whose content
is "did we pass our pre-registered falsify/success thresholds" (threshold lines named `falsify <=0.05`,
`success >=0.15`, `stress floor 0.85`; bars that exist to clear a line) is a RUN ARTIFACT. It belongs
in `EXPERIMENTS/` or `REPORTS/`, and it never ships as a manuscript `FigureN`. The manuscript figure
answers the reader's question ("does the method work, and how well?"), not the pipeline's
("did the gate fire?"). A pre-registered threshold MAY appear in a reader-facing figure — as one
labeled reference line supporting the conclusion — but the figure's SUBJECT is the result, never the
gate check.

## The design brief (the unit of design work)

Design decisions are recorded as a per-figure DESIGN BRIEF — the contract a reviser implements and a
fidelity gate judges against:

```
reader_takeaway     ONE sentence (the conclusion above)
verdict             keep | restyle | redesign        (categorical; never a numeric score)
archetype           a named entry from references/archetypes.md
axis_plan           per axis: window, scale, rationale ("y in [0.88,0.92] hugs the data; line plot → no 0-baseline duty")
panel_plan          per panel: keep | merge | drop | to_si | to_table, with its content
regen_expectations  measurable acceptance checks ("curves occupy >=2/3 of the y-span", "no twinx", "no ax.table")
caption_implication what the caption must now say differently (null if unchanged)
proposed_caption    full replacement \caption text (null if unchanged)
```

`verdict` calibration: `keep` = design already serves the takeaway (styling may still move);
`restyle` = right archetype, presentation-level fixes only; `redesign` = the archetype, axis plan, or
panel composition cannot deliver the takeaway — replot from the same cached data. Any figure showing
a design axiom violation (below) is at least `redesign`-suspect; say so rather than laundering it as
`restyle`.

When a drafter or experiment worker AUTHORS a figure from scratch, put the brief in a comment block
at the top of the plotting script (same fields, prose form) — the figure is born with its contract.

## Design axioms (violations = design defects, not style nits)

- **Data occupies the canvas.** A quantity living in [0.89, 0.91] plotted on a [0, 1] axis is an
  invisible flat line — the axis window is part of the design. See `references/axes-and-density.md`.
- **One y-axis per panel.** `twinx` with mixed units is default-OFF; use the alternatives table in
  `references/archetypes.md`.
- **Never `ax.table`.** Tabular content is a LaTeX (booktabs) table, not pixels.
- **A negative result gets a negative-result design** (difference-vs-zero + CI + equivalence band) —
  not an empty-looking panel of ~0 bars under a distant threshold line.
- **A saturated metric gets a deficit design** (plot 1−metric or the gap, log scale if needed) — never
  a row of indistinguishable full-height bars.
- **Every panel serves the takeaway.** A panel that doesn't moves to the SI or dies
  (`panel_plan: to_si | drop`).

## References (load only what the current task needs)

- `references/archetypes.md` — the takeaway→chart-type decision table + the special-case patterns
  (negative result / equivalence, ceiling metrics, twin-axis alternatives, table-as-figure,
  threshold lines). Load when CHOOSING or JUDGING a chart form.
- `references/axes-and-density.md` — axis-window rules, information density, panel-to-SI / drop-panel
  criteria, set-wide style floors (final-size fonts, figsize per layout slot). Load when writing an
  `axis_plan` / `panel_plan` or judging density defects.

## Boundary with research-figure-plotting

This skill decides **what to draw**; `research-figure-plotting` governs **how it is rendered** —
style-guide, de-AI default-off removals, legends/typography, plot-code naming, and the render-and-look
QA protocol. A reviser implementing a brief retrieves BOTH: this skill for the target design,
research-figure-plotting for the execution standard. On axis-window honesty the two agree by
construction: `axes-and-density.md` here and `style-guide.md`'s axis-hugs-data rule state the same
rule; `check-figure-fidelity` cites it as licensed presentation.
