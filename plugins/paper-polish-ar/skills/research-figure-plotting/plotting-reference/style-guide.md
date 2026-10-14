# Research Figure Style Guide

Defaults for tuning figure appearance, scoped to computational-science /
applied-mathematics journals (JCP, CMAME, SISC). See `iteration-playbook.md`
for the fix recipes that operationalize these defaults. Restrained and
rigorous, never poster-style or Nature-glossy.

## Script header (rcParams)

Set these once at the top of every plotting script, before building axes:

```python
import matplotlib as mpl
mpl.use("Agg")                       # headless/batch: set before importing pyplot
import matplotlib.pyplot as plt
mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "cm",        # math in a matching serif (Computer Modern)
    "svg.fonttype": "none",          # keep SVG text as <text>, not paths
    "pdf.fonttype": 42,              # embeddable TrueType in PDF (selectable text)
    "axes.unicode_minus": False,
})
```

- Plain figure text uses **Times New Roman** (serif). If Times New Roman is
  unavailable on the machine, fall back to another serif and note it — do not
  silently ship sans-serif.
- `mpl.use("Agg")` must precede `import matplotlib.pyplot`; pair every figure
  with `plt.close(fig)` to release memory in batch runs.

## Layout

- One canvas per manuscript figure; all panels assembled together.
- Panel labels `A`, `B`, `C`, … visible but unobtrusive.
- Align by data axes or colorbar bodies — never by label, tick, or
  legend text.
- Treat colorbars and legends as part of a panel's footprint, not as
  appendages.
- Keep subplot sizes consistent inside a figure unless scientific
  content demands otherwise.
- Share axes when comparison matters; separate when scale or quantity
  differs.
- Size for the slot: single-column ≈ 3.3–3.5 in wide, double-column ≈ 6.5–7.2 in,
  multi-panel taller as needed — confirm fonts stay legible at that final size.
  Set `figsize` explicitly; never rely on the default 6.4×4.8.

## Axes & spines

- Drop top and right spines. The remaining **bottom (x) and left (y) axes carry
  a direction arrow** at their far end — a standard convention in computational
  -science figures:

  ```python
  ax.spines[["top", "right"]].set_visible(False)
  ax.plot(1, 0, ">k", transform=ax.get_yaxis_transform(), clip_on=False, ms=5)  # x-axis tip
  ax.plot(0, 1, "^k", transform=ax.get_xaxis_transform(), clip_on=False, ms=5)  # y-axis tip
  ```

  (For a colorbar or image panel where an arrowed frame would mislead, keep a
  plain box instead and note why.)
- y-axis range hugs the data for narrow-band quantities (error decay,
  convergence, accuracy in `[0.80, 0.95]`): set `[v.min()-m, v.max()+m]` with
  `m ≈ 0.1·range` so the trend is visible. Caveat: tightening is honest for
  lines / scatter / log axes, but a **solid bar chart must keep its 0 baseline**
  (or mark a broken axis explicitly) — truncating it exaggerates differences.

## Typography

- Publication-readable sizes; bump labels (≈11pt) and ticks (≈9pt) so
  they survive manuscript scaling.
- Match legend sizes across related panels.
- Drop subplot titles in heterogeneous figures (keep only when panels
  are similar enough that the title aids direct comparison).
- Every axis label states quantity + units.
- Column-mate y-labels: same `ax.yaxis.set_label_coords(x, 0.5)` across
  the column when alignment matters.
- Categorical ticks: Title Case words, upper-case acronyms, period on
  abbreviations (`Std`, `Pen.`, `AL`, `Metric`, `Diag`, `UA`, `Stoch.`).
- **All variables and math symbols render through mathtext** `$…$`
  (`$\alpha$`, `$t$`, `$L^2$`, `$x_1$`, `$\Sigma_F$`) so they appear italic
  and consistent with the body serif. Reserve bare Unicode (`Å`, `°`, `μ` as a
  unit prefix) for non-variable glyphs in otherwise-plain text. Watch the
  Unicode-vs-`$…$` glyph mismatch (see iteration-playbook).

## Color, lines, uncertainty

- Same method = same color across panels.
- Low-saturation, professional, CVD-friendly palette. **No jet/rainbow for
  discrete categories** — those high-saturation maps are misleading and
  unprofessional here. A perceptually-uniform continuous colormap
  (`viridis`/`magma`) is for **continuous scalar fields only** (e.g. a solution
  field over space); compared field panels share one cmap + `vmin`/`vmax`.
- Don't over-encode: if x-position already identifies methods, color
  is for the *main* comparison; reserve texture/alpha for secondary
  distinctions. Use a restrained accent color only for the key result.
- Palettes distinguishable in grayscale or under CVD when feasible.
- Avoid decorative gradients / visual effects that don't encode data.
- **Line hierarchy**: the main result curve is heaviest (solid, ≈2–3 pt,
  modest markers); reference / baseline / threshold lines are thin dashed and
  lower alpha (`ax.axhline(ls="--", alpha=0.3)`), clearly subordinate; raise
  the `zorder` of annotation arrows/markers above the data. A reader should
  tell the "conclusion line" from a "reference line" at a glance.
- **Error bars** use one consistent `error_kw={"elinewidth":…, "capthick":…,
  "capsize":…}` across the figure, in a neutral grey or a darker shade of the
  series color — visible in print, never thicker than the data line.
- **In-fill annotations**: when a number is written on a filled element
  (heatmap cell, solid bar), pick black or white text by the cell's relative
  luminance `0.299R+0.587G+0.114B` (dark fill → white text, light fill → black);
  do not use one fixed text color everywhere.
- Uncertainty bands: state and label the quantity (SD / SEM / CI /
  quantile); guard against nonpositive values on log scales.
- Log axes: at least two labeled major ticks. Use `LogFormatterMathtext`
  + `NullFormatter` on minor ticks; `FixedLocator` + `FixedFormatter`
  for sub-decade data.
- Headroom above bars / markers / error bars; never flush against the
  top spine.
- Paired bar quantities: shared theme color, solid for one, lighter
  hatched for the other; hatch in a muted theme grey (not pure black).
- Colorbar tick decimals consistent across compared panels; no
  misleading `extend` triangles unless clipping is intentional and
  applied symmetrically.

## Legends & annotations

- No text, label, legend, or annotation may overlap a line, data point, or
  axis. Verify in the rendered figure, not from the code.
- **Each text label / annotation sits in its own box**: a light or white
  background with a thin border, placed where it does not occlude data —
  `ax.text(x, y, s, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.5",
  lw=0.5))`. (This is the in-figure annotation rule; legend frames follow the
  legend bullets below.)
- Place in an empty data quadrant; descending → upper-right, rising →
  lower-right, data-filled → above.
- Center over the correct visual object: scalar panel = main axes (or
  axes+cbar deliberately); bar panel = main axes.
- Move outside *that* panel only when it cannot fit anywhere inside;
  do not promote one panel's legend to a figure-wide top legend just
  because another panel needed it outside.
- Legend hatch handles match in-figure hatch color, density, and
  lightness exactly.
- Tune `bbox_to_anchor`, `borderaxespad`, `borderpad`, `handlelength`,
  `columnspacing` deliberately and verify in the rendered SVG.

## Scientific communication

- The figure communicates the comparison directly; decoration must not
  compete with the data.
- The final SVG reads coherently without opening separate panel files.
- No mesh grids inside images or scalar fields (contours are fine when
  they encode the field).
- No grid lines in compact line/bar panels unless they materially aid
  quantitative reading.
