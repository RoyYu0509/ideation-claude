# axes-and-density — axis windows, information density, panel decisions, style floors

## Axis windows (the window is part of the design)

- **Hug the data.** For lines / scatter / log axes, the window is `[min−m, max+m]` with `m ≈ 0.1·range`
  — the same rule as research-figure-plotting `style-guide.md` ("y-axis range hugs the data for
  narrow-band quantities"), and `check-figure-fidelity` treats an honest hug as licensed presentation
  (PASS). The worked failure: coverage in [0.89, 0.91] drawn on [0, 1] renders as an information-free
  flat line — [0.88, 0.92] is the HONEST window, [0, 1] is the misleading one.
- **Bars keep their 0 baseline** — or mark a broken axis explicitly. Truncating a solid bar
  exaggerates differences; that stays forbidden. (When the interesting variation is far from 0, the
  archetype is wrong — switch to a dot plot or plot the deficit; see `archetypes.md`.)
- **Never exclude plotted points** with a window/clip, and never pick a window that manufactures a
  difference the statistics don't support.
- **linear↔log** changes the read, not the numbers: legitimate when the brief names it (ratios,
  decades-spanning data); misuse (hiding zeros/negatives, flattening a trend reversal) is drift.

## Information density

- **Data occupies ≥ ~2/3 of each axis span.** A scatter crushed into a corner of the canvas (the rest
  empty except a reference diagonal) is a design defect: window to the occupied region, or change
  quantity (e.g. plot the ratio to the reference instead of raw vs raw).
- Empty space is only legitimate when it IS the message (e.g. "far below threshold" — then annotate
  the gap so the emptiness reads as intended).
- Density has a ceiling too: >~6 curves on one panel → small multiples or an ECDF.

## Panel decisions (panel_plan)

A panel earns its place by carrying part of the `reader_takeaway`. Per panel decide:
- `keep` — carries the takeaway (possibly restyled).
- `merge` — two panels making one comparison the reader must do mentally → one panel making it visually.
- `to_si` — real but secondary evidence (robustness sweeps, per-stratum breakdowns that repeat the
  main pattern): move to the SI figure and cite it.
- `drop` — pipeline self-checks, redundant views, decoration. (State what is dropped and why in the
  brief — never silently.)
- `to_table` — tabular content (see `archetypes.md`, table-as-figure).
Moving/dropping a panel implies a caption change and possibly prose `\ref` updates — record them in
`caption_implication` / `proposed_caption`; never leave the caption describing a panel that no longer exists.

## Set-wide style floors (design-level; rendering details live in research-figure-plotting)

- **Fonts survive final size**: after LaTeX scales the figure to its slot, tick/legend text ≥ ~8pt,
  axis labels ≥ ~9pt. Design the figsize FOR the slot (single column ≈ 3.4in, double ≈ 7in wide)
  instead of shrinking a large canvas.
- **One figsize/aspect per layout slot** across the paper — siblings displayed at equal width share
  aspect and font sizes (the survey's sibling_alignment note enforces this set-wide).
- **A shared method→color map across all figures**; reference/threshold lines styled uniformly
  (thin, dashed, low-alpha, labeled).
