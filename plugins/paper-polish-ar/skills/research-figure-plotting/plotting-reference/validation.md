# Plotting Validation

Run before finishing any plotting change.

## Commands

```bash
python -m py_compile <changed plotting scripts>
python <make_figureN_script.py>
python <make_all_figures.py>      # only when shared helpers changed
```

If matplotlib can't write its cache:
`MPLCONFIGDIR=/private/tmp/mpl-cache python …`.

## Output checks

- Expected **PDF + PNG** written (SVG only when hand-alignment was needed);
  filenames start with `FigureN.` / `SupplementFigureN.`.
- Plain text renders in Times New Roman (serif); all variables/math went
  through mathtext `$…$`.
- Bottom/left axes carry direction arrows; top/right spines dropped (except
  colorbar/image panels that keep a plain box).
- All data came from intended cached sources (no silent re-runs); the data,
  numbers, statistics, and conclusion the figure conveys are unchanged.
- No text clipped; no legend or annotation hides important data.
- Aligned panels share data-axis or cbar-body boundaries; cbar label
  doesn't collide with neighbor's y-label. When inter-panel gap parity
  matters, verify with `ax.get_tightbbox(renderer)` (which includes
  labels and colorbars) rather than `ax.get_position()` — uniform
  `wspace` does not guarantee equal *visible* gaps when one panel
  carries a colorbar+label and a sibling carries only a y-label.
- Column-mate y-labels share `set_label_coords` `x` (only where
  alignment matters — don't yank labels into ticks to free gutter
  space).
- Categorical ticks follow one case convention.
- Log axes show ≥2 labeled major ticks; sub-decade ranges use
  `FixedLocator` + `FixedFormatter` with both `ylim` bounds locked
  (`set_yticks` / `set_yticklabels` get silently overridden on log
  axes).
- Variables/math through mathtext `$…$`; bare Unicode (`Å`, `°`) only for
  non-variable glyphs.
- No text / label / legend / annotation overlaps a line, data point, or axis;
  in-figure annotations sit in a light/white box with a thin border.
- Hatch color/density in legend handle matches the bar.
- Flush legends: `bbox_to_anchor=(1.05, …)` with `borderaxespad=0`,
  `borderpad=0` for axes-spine ("plot's right" / "图片"); `(1.0, …)`
  leaves a 3–5 % gap; `(1.15–1.20, …)` only for explicit saved-SVG
  edge requests. No flush legend sits on top of an
  `add_panel_label`.
- If any panel uses `set_box_aspect`, its colorbar comes from
  `fig.colorbar(cf, ax=ax, fraction=..., pad=...)` — not a sibling
  `cax` slot.

## Statistics honesty (every quantitative panel)

- Error interval is labeled for what it is (SD / SEM / CI / quantile) — never
  a bare whisker; center statistic (mean / median) stated.
- Sample/replicate count `n` (independent runs, seeds, mesh-refinement levels)
  is traceable in figure, caption, or source data.
- Any claimed difference records its test and multiple-comparison handling.
- Numerical experiments also note: how many seeds/folds the spread covers,
  the metric definition, the baseline definition, and the train/val/test split.
- Source data traces back to a clean CSV / script output.

## Visual inspection

Open the PDF/PNG (`open file.pdf`, or `Read` the PNG) and check for: blank
canvases, missing fonts, sans-serif slip (should be Times New Roman),
clipped or overlapping text, missing axis arrows, misordered panels,
inconsistent method colors, rainbow/jet on discrete categories,
unreadable log ticks, misleading cbar
extensions, leftover subplot titles, mesh grids in scalar fields,
grids on compact line/bar panels, leftover top/right spines,
decorative gradients, no headroom, mismatched mathtext-vs-Unicode
glyphs, ragged y-label column. The de-AI default-off decorations
([de-ai-defaults.md](de-ai-defaults.md)) are defects even when every
figure shares them — do not excuse them as consistency.

**Don't trust `qlmanage -t` for layout.** It writes a square-canvas
PNG regardless of SVG aspect — wide multi-panel figures appear
clipped on the right when they're actually fine. For inline visual
verification, render through matplotlib:

```python
fig.savefig("/tmp/preview.png", bbox_inches="tight", dpi=240)
```

then `Read` the PNG. `rsvg-convert` and `cairosvg` also respect
aspect when available.

## Finish summary

Report: scripts changed, figures regenerated (PDF + PNG), validation
commands run, visual checks performed, and any missing data or checks
that could not be completed.
