# Iteration Playbook

Load when polishing an existing figure against concrete visual complaints.
One panel-level concern per round: smallest viable change → regenerate →
render → report what you visually verified.

Each section: **symptom → root cause → fix**. Recipes are load-bearing —
the prose around them isn't.

---

## Layout & spacing

### Subplot sizes mismatched

Colorbars hung externally (`make_axes_locatable`) give panels different
footprints. Build one `GridSpec` with explicit `width_ratios` /
`height_ratios` where colorbar slots are real cells. Bottom rows can
`add_subplot(gs[1, k_plot:k_cbar+1])` to span the unused cbar slot above.

### Square panels

Use `ax.set_box_aspect(1.0)`. Do not chase squareness via `figsize` or
`set_aspect('equal')` (which distorts data with anisotropic limits).

### Rows too cramped / too far apart

Tune `GridSpec` `hspace` / `wspace` and `subplots_adjust(left/right/top/
bottom)`. Removing a subplot title tightens rows more than `hspace`.

### Visual gaps uneven despite uniform `wspace`

Uniform `wspace` equalizes *cell-edge* gaps, not the whitespace a reader
sees. When one panel carries an in-cell colorbar+label and its neighbor
carries a y-axis label, the visible A↔B gap shrinks (label nearly
touches label) while B↔C stays open — even though `ax.get_position()`
shows symmetric columns. Don't judge parity from axes boxes; measure
tight bboxes in figure coords:

```python
fig.canvas.draw()
r = fig.canvas.get_renderer()
fw = fig.get_size_inches()[0] * fig.dpi
for ax in fig.axes:
    bb = ax.get_tightbbox(r)
    print(ax.get_label(), bb.x0/fw, bb.x1/fw)
# gap_AB = B.x0 - A.x1  (use the colorbar's bbox if A has one)
```

Equalize by splitting into nested gridspecs with per-gap `wspace` —
a single `GridSpec` can't carry different gap sizes:

```python
gs_left  = fig.add_gridspec(1, 1, left=L, right=R1, ...)
gs_right = fig.add_gridspec(1, 2, left=L2, right=R, wspace=w_bc, ...)
```

Pick `R1`, `L2`, `w_bc` so `(L2 - cbar_right) == (C.x0 - B.x1)` in
figure coords. Iterate: draw → measure → adjust.

### `tight_layout` overrides `subplots_adjust`

`fig.tight_layout()` followed by `fig.subplots_adjust(wspace=...)` does
*not* give you the wspace you asked for. Robust pattern:

```python
fig, axes = plt.subplots(1, 3, figsize=(9.2, 2.85),
                         gridspec_kw={"wspace": 1.0})
# draw
fig.subplots_adjust(left=0.065, right=0.975, top=0.96,
                    bottom=0.21, wspace=1.0)
fig.savefig(path, bbox_inches="tight")    # crops outer canvas only
```

Skip `tight_layout` entirely; set wspace in *both* `gridspec_kw` and
`subplots_adjust`; lock all four margins.

### Bottom row misaligns with top row

Use one shared `GridSpec`, not per-row `subplots()` calls. Bottom-row
panels span the column above's plot+cbar slots (`gs[1, k_plot:k_cbar+1]`)
so their right edge lands on the cbar body.

---

## Colorbars

### Cbar height doesn't match its panel

Pre-created `cax` in a sibling GridSpec column sizes to the *cell*, not
to the data axes. After `set_box_aspect` shrinks `ax`, the sibling cax
keeps full cell height and the two diverge. Let matplotlib track the
host axes:

```python
cb = fig.colorbar(cf, ax=ax, fraction=0.046, pad=0.04)
```

Only hand-place a `cax` when the cbar must span multiple panels or sit
at a non-default edge — then sync after `fig.canvas.draw()`.

### Cbar label collides with neighbor's y-label

Multiple compounding fixes; try in this order:

1. Shrink cbar tick precision (`0.000 → 0.0`).
2. Bump `wspace`.
3. Pull labels toward their axis:
   ```python
   ax.set_ylabel("...", labelpad=1)       # positive: closer to axis
   cb.set_label("...", labelpad=-2)       # NEGATIVE: closer to bar (rotated)
   ```
4. As a last resort, move cbar label to top (asymmetric vs sibling panels).

Do *not* fix this by yanking the next panel's y-label inward with
`set_label_coords(-0.10, …)` — that lands the label on top of the tick
numbers. `set_label_coords` is for column-mate alignment, not gutter
reclamation.

### Cbar pointy when sibling is flat

`extend='max'` / `extend='both'` adds a triangle. Drop `extend=...` and
let `vmin`/`vmax` saturate; or apply the same `extend` to every panel
that shares the visual treatment.

### One panel has a cbar, sibling doesn't

Parallel quantities deserve parallel treatment. Match vmin/vmax,
colormap, tick format, extend, label position.

---

## Legends

### Legend overlaps data

Data-filled panels (dense heatmap, lattice scatter, covariance cluster)
have no empty quadrant. Move above the panel:

| Goal                  | `loc` / `bbox_to_anchor`             |
|-----------------------|--------------------------------------|
| Centered above panel  | `"lower center"`, `(0.5, 1.02)`      |
| Left-aligned above    | `"lower left"`,   `(0.0, 1.02)`      |

Always pair with `frameon=False, borderaxespad=0.0, borderpad=0.0,
handletextpad=0.3, columnspacing=0.7`.

### Pick the quadrant from the data shape

Descending log curves → upper-right. Rising diagonals → lower-right.
Data-filled → above. Move a legend out of its panel only when no
quadrant of *that* panel is empty.

Do not pre-emptively replace per-panel legends with one figure-wide top
legend. The user reads that as over-engineering. If one panel is
data-filled and siblings aren't, the data-filled one gets its legend
above; siblings keep theirs in-axes.

**Exception — identical legends across sibling panels.** When every
panel in a row carries the same (or a subset of the same) legend
entries, hoist to one figure-level legend centered above the row and
drop the per-axes legends. Build the shared legend from proxy
`Line2D` / `Patch` handles so a panel missing an entry (e.g. oblique
projection has no metric-shifted line) still appears in the shared key.
Reserve top-strip space with `fig.tight_layout(rect=(0, 0, 1, 0.92))`
or equivalent.

### Asymmetric cost

Moving one top-row panel's legend above shrinks *that* panel's axes.
Accept the asymmetry or treat the row uniformly — don't mix.

### Flush to axis spine ("顶到 plot 的最右边")

With `loc="upper right", borderaxespad=0, borderpad=0`:

| `bbox_to_anchor` x | Where the longest entry's *visible text* lands       |
|--------------------|------------------------------------------------------|
| `1.0`              | 3–5 % inside the spine (matplotlib font side-bearing — not flush). |
| `1.05`             | **On the spine ✓** — default for "plot's right" / "图片". |
| `1.15`–`1.20`      | Past the spine onto the saved-SVG edge. Use only for explicit *saved-figure* requests. |

A flush legend at `(0, 1)` collides with `add_panel_label` at
`(0.02, 0.98)` — offset down (`(0.0, 0.90)`) or move the panel letter
outside the axes.

### Won't fit even horizontally above

Shorten labels (`Pen.`, `AL`, `Stoch.`). Reduce `handlelength`,
`columnspacing`, `handletextpad`. Direct-label traces if entries still
wrap.

### Legend too small

Bump `fontsize` (e.g. 8.5 → 10) and match all other panels in the same
figure to that size.

---

## Axes, ticks, labels

### Y-label too far from / too close to axis

Default `labelpad` budgets for negative-number widths. If ticks are
non-negative, reduce `labelpad` (0–2). Use `tick_params(axis='y',
pad=...)` for the tick-side gap.

### Column-mate y-labels not aligned

```python
ax.yaxis.set_label_coords(x, 0.5)   # same x on every column-mate
```

Use this for *alignment*, not to reclaim gutter horizontal space (see
the cbar-label-collision rule above).

### Log axis: only one labeled tick

Drop scientific-notation minor labels:

```python
ax.yaxis.set_major_locator(LogLocator(base=10))
ax.yaxis.set_major_formatter(LogFormatterMathtext(base=10))
ax.yaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10) * 0.1))
ax.yaxis.set_minor_formatter(NullFormatter())
```

Sub-decade data + "preserve box size" (forbidden to extend `ylim`)
needs a fixed non-decade major tick:

```python
from matplotlib.ticker import FixedLocator, FixedFormatter, LogLocator, NullFormatter

ax.set_yscale("log")
ax.yaxis.set_major_locator(FixedLocator([3e-3, 1e-2]))
ax.yaxis.set_major_formatter(FixedFormatter([r"$3{\cdot}10^{-3}$", r"$1{\cdot}10^{-2}$"]))
ax.yaxis.set_minor_locator(LogLocator(base=10, subs=(2.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)))
ax.yaxis.set_minor_formatter(NullFormatter())
ax.set_ylim(2e-3, 2e-2)
```

Traps:
1. Use `set_major_locator(FixedLocator)` directly. `set_yticks` /
   `set_yticklabels` are silently overridden on log axes during
   `tight_layout` / `bbox_inches="tight"` redraws.
2. Exclude the major mantissa from minor `subs` (drop `3.0` if `3e-3`
   is major) — otherwise a stray default-decade label appears.
3. Lock both `ylim` bounds. One-sided lets matplotlib re-derive and
   pull the labeled tick off-screen.
4. Mantissa-style consistency: if *any* major tick uses an explicit
   mantissa (`3·10^{-3}`), write the decade ticks the same way
   (`1·10^{-2}`, not bare `10^{-2}`). Mixing the two reads as
   不协调 — the user will flag it.

Verify at 2400+ px: narrow mathtext prefixes (the `3` in `3·10^{-3}`)
disappear at thumbnail size.

### Mathtext vs body-font drift

`$\AA$`, `$\mu$`, `$\sigma$`, `$\pi$`, `$^\circ$` render via mathtext;
sibling labels using body Unicode render different glyphs. Use Unicode
directly (`Å`, `μ`, `σ`, `π`, `°`) in plain-text labels; reserve `$…$`
for real math expressions (`$x_1$`, `$\Sigma_F$`, `$\|r_x\|$`).

Same trap shows up in **subplot titles across a row**: `$Gg$` or `$G$`
wrapped inside an otherwise-roman title renders math-italic, while a
sibling title with no math wrapping stays upright — the row reads as
mismatched fonts. For plain letters that aren't variables (matrix
names in prose, descriptive identifiers) drop the `$…$` so all titles
share the body font. Axis labels with genuine math (`$x_1$`, `$\tau$`)
are unaffected and should stay wrapped.

### Categorical tick label case

Title Case words, upper-case acronyms, period on abbreviations:
`Std`, `Pen.`, `AL`, `Metric`, `Diag`, `UA`, `Stoch.`. Sweep every
`set_xticklabels` / `tick_labels=` call site on every polish round —
not just the one the user named.

### Fonts too small after manuscript scaling

Bump `fontsize` on labels and tick labels (e.g. 8 → 11.5). Conservative
defaults print smaller than expected at column width.

---

## Decoration & encoding

### Subplot titles in a heterogeneous figure

Drop `ax.set_title(...)`. Keep titles only when panels are visually
similar enough that the title aids direct comparison.

### Mesh grid in a scalar field / image

Remove `ax.grid(True)` on heatmaps and imshow. Contour lines are
acceptable when they encode the field. Remove grids on compact
line/bar panels unless they materially aid quantitative reading.

### Paired bars indistinguishable except by color

Share color for cross-method comparison, add a *texture overlay* to
distinguish quantities within a group. Texture rules:

1. Distinguishable: `xx` vs `oo` (not `///` vs `\\\`).
2. Muted, not loud: `#4f4f4f` not pure black.
3. Equal visual weight on both sides.

### Hatch in figure ≠ hatch in legend

Matplotlib renders bar hatches in the patch's `edgecolor`; legend hatch
handles are proxy artists whose `edgecolor` may not be set. Mirror
explicitly:

```python
import matplotlib as mpl
mpl.rcParams["hatch.color"]     = "#4f4f4f"
mpl.rcParams["hatch.linewidth"] = 0.6

ax.bar(..., edgecolor="#4f4f4f", hatch="xx")

from matplotlib.patches import Patch
handles = [
    Patch(facecolor=bar_color, edgecolor="#4f4f4f", hatch="xx", label="..."),
    Patch(facecolor=bar_color, edgecolor="#4f4f4f", hatch="oo", label="..."),
]
ax.legend(handles=handles, ...)
```

Always render and compare a bar against its legend handle.

---

## Round discipline

- **One concern per round.** If the user lists five, address all five
  but as focused diffs.
- **Smallest viable change.** No refactors on a polish request.
- **Render before reporting.** `qlmanage -p file.svg` on macOS, or
  `open`. Compiling ≠ validating. And the Edit tool reporting
  "updated successfully" ≠ disk state: if an IDE linter or formatter
  is in the loop (visible via post-edit `system-reminder` blocks
  showing the file reverted to its prior shape), re-grep the actual
  bytes for your change before claiming the edit landed. Re-apply if
  it was reverted.
- **Match siblings.** Bumping panel C's legend to 10pt? Bump B and D.
  The user will ask next round otherwise.
- **State what you visually verified** in the finish summary.
