# Plotting Workflow

For setting up or restructuring a research plotting pipeline.

## Pipeline

1. Identify final manuscript figures (incl. supplements).
2. Map each to panels and source data.
3. Locate cached analysis artifacts (CSV / JSON / NPZ / Parquet / HDF5).
4. Build shared helpers (style, loaders, save, panel labels, colors).
5. One small entry script per figure.
6. Add a batch script only when it calls the per-figure builders.
7. Regenerate (PDF + PNG) and inspect.

## Layout

```text
plotting/
  plot_utils.py              # shared style, loaders, save helpers
  panel_plotters.py          # low-level helpers, cached-data loaders
  superplot_plotters.py      # figure-level assembly
  make_figure1.py
  make_figure2.py
  make_supplement_figure1.py
  make_all_figures.py        # optional
figures/
  Figure1. descriptive_name.pdf      # + .png
  Figure2. descriptive_name.pdf      # + .png
  SupplementFigure1. descriptive_name.pdf
```

Entry scripts import + call builders; figure logic stays shared.

## Data rules

- Read explicit cached artifacts. No fabrication, no silent reruns of
  expensive experiments.
- Missing data → report the path and the command that regenerates it.
- Fix seeds for synthetic / bootstrap / jitter / subsampling.
- Preserve units in labels and legends.

## Output rules

- Vector PDF + raster PNG by default (Agg backend; close figures after
  saving). Add SVG only when text will be hand-aligned.
- Names: `Figure1. short_name.pdf` (+ `.png`), `SupplementFigure1. short_name.pdf`.
  Avoid `plot.pdf`, `panelA.png`, `final_final.pdf`.
