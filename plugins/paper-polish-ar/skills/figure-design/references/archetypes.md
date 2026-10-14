# archetypes — the takeaway→chart-type decision table

Start from the `reader_takeaway` sentence. Its grammatical shape names the archetype; the data's
shape only refines it. "The script logged bars" is never a reason.

## Decision table

| takeaway shape | archetype | notes |
|---|---|---|
| "A is better/tighter/cheaper than B (by this much)" | dot plot with CI, or grouped bars (few groups) | dot+CI beats bars when the differences are small relative to the scale; label the gap, not just the levels |
| "X grows/decays/converges like f(n)" | line on log or log-log axes + a labeled reference-slope guide | reference slope drawn as a short offset guide line, never a full-frame diagonal |
| "X stays flat / is insensitive to Y" | line with the y-window hugged to the data + a stated total-variation annotation ("<0.4% over the sweep") | flatness on a [0,1] axis is invisible AND unfalsifiable to the eye; hug the window and SAY the variation |
| "the distribution of X is ..." | ECDF (preferred for comparisons) or violin/histogram | ECDFs overlay cleanly; histograms need identical binning to compare |
| "coverage/accuracy meets the target across strata" | dot plot per stratum with CI, target as ONE labeled reference line | see ceiling pattern below if everything sits at the target |
| "the bound/certificate envelops the truth" | scatter of bound vs truth with the y=x diagonal, windowed to the occupied region | 95% empty canvas around a corner blob is a design defect — zoom, or plot the RATIO bound/truth instead |
| "cost/overhead is negligible relative to Z" | horizontal bar or dot on a log scale of RATIOS, annotated | ratios (x/Z) carry the sentence; raw times need a second read |

## Special-case patterns (the shapes that get mis-designed most)

### Negative result / equivalence ("the ablation changes nothing")
Plot the DIFFERENCE against zero: Δ per condition with its CI, a zero line, and — when a
pre-registered margin exists — a shaded equivalence band. The takeaway "everything is inside the
band" is then visible. NEVER a panel of ~0-height bars under a distant threshold line (reads as an
empty/broken plot); annotate the magnitude explicitly ("|Δ| < 0.001, margin 0.15").

### Ceiling / saturated metric ("all strata at 1.0" / "all at target")
A row of full-height identical bars carries zero information. Plot the DEFICIT — `1 − metric` or
`metric − target` — on a scale where the residual variation is visible (log if it spans decades). If
the honest message is "exactly saturated, nothing to resolve", say it in one annotated dot-plot row
or a sentence in the caption, and consider `panel_plan: drop | to_si`.

### Two quantities, two units ("condition number grows while the bound stays flat")
`twinx` is default-OFF: dual y-scales invite false correlation reads, and "magnitude" axes with
negative tick labels confuse readers. Alternatives, in preference order:
1. **Stacked panels sharing x** — two small panels, one quantity each; the shared x carries the comparison.
2. **Normalize/index both** to their value at a reference point (both dimensionless → one axis).
3. **Small multiples** when there are more than two quantities.
Use twinx ONLY when both series share the same unit family and the brief names it.

### Table-as-figure
`ax.table` / text-grid panels are never manuscript figures. `panel_plan: to_table` — emit the content
as a LaTeX booktabs table (the venue kit's table style applies) and re-lay the figure without the
panel. If the tabular content is load-bearing next to a plot, it is still a table — floats can sit
side by side.

### Threshold / target lines
A reference line is an ANNOTATION serving the takeaway: thin, dashed, lower-alpha, labeled with its
meaning and value in reader vocabulary ("target 0.90"), never in pipeline vocabulary
("falsify if freq>0.20 & gap>10pp"). More than ~2 reference lines on one panel means the panel is a
gate dashboard — redesign (see SKILL.md, the reader principle).
