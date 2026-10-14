---
name: research-figure-plotting
description: Use when creating, editing, polishing, or regenerating manuscript figures for computational-science / applied-mathematics journals (JCP, CMAME, SISC and similar) — multi-panel scientific figures (PDF + PNG, optional SVG) that need careful layout, legends, colorbars, typography, hatch textures, and visual QA. Trigger on requests about "figure 1", "subplot", "legend overlap", "colorbar", "panel alignment", "polish the figure", "convergence/error curve", or any plotting-script edits inside `figure_editing/`, `plotting/`, or similar manuscript-figure directories. Also contains the plotting-code style standard (the `## Plot code style` section) — how to name and organise a plotting script so it reads as researcher-written, not AI-generated.
user-invocable: false
---

# Research Figure Plotting

Cross-project skill for research figure work, scoped to **computational-science
and applied-mathematics journals (JCP, CMAME, SISC and similar)**. Project-specific
constraints belong in that project's `AGENTS.md` / `CLAUDE.md`.

## Target-venue stance

- The figure exists to make **numerical results, error/convergence trends,
  algorithm comparisons, and physical/mathematical meaning** legible — not to
  look striking. Restraint, rigour, reproducibility.
- **Do NOT apply a Nature / glossy-journal figure aesthetic**: no poster-style
  hero panels, no decorative visual narrative, no template-driven page
  composition. Never retrieve or imitate a `nature-figure` workflow or any
  Nature-family figure template. The bar is JCP/CMAME/SISC, not Nature.
- Backend is **Python only — matplotlib / seaborn** (and their compatible
  helpers). No other plotting stack.

## Essence

- One figure at a time; size each for its slot (single-column, double-column,
  or multi-panel) so text stays legible at final manuscript size.
- **Export at least vector PDF + raster PNG** (`fig.savefig(name+".pdf",
  bbox_inches="tight")` and `fig.savefig(name+".png", dpi=300, bbox_inches="tight")`);
  add SVG only when text will be hand-aligned later (then set
  `svg.fonttype="none"`). PNG drives `\includegraphics`/review; PDF is the
  vector master.
- One entry script per figure; optional batch script calls those builders.
- Output: `Figure1. short_name.pdf` (+ `.png`), `SupplementFigure2. short_name.pdf`.
- Read cached/versioned analysis data; never silently rerun experiments, and
  never change the data, numbers, statistics, or conclusions a figure conveys
  (that science is frozen — only its visual presentation and code naming change).
- Interpretation before decoration: legends, cbars, labels readable after
  scaling; align by data axes or cbar bodies, not by text.
- De-AI defaults — REMOVE unless it earns its place: grid on compact
  line/bar panels, mesh grids on images/heatmaps, top/right spines (the
  remaining left/bottom axes carry direction arrows — see style-guide),
  subplot titles in heterogeneous figures, decorative gradients, rainbow/jet
  colormaps for discrete categories, redundant color double-encoding. A trait
  shared by *every* figure is still a defect to strip, not a convention to
  keep. Full checklist: [de-ai-defaults.md](plotting-reference/de-ai-defaults.md).

## Polishing loop

Polish requests usually take several rounds. Each round converges only
when the change is small and actually rendered.

1. Read the figure builder and the relevant reference; confirm this figure's
   paper location, plotting script, input-data path, output path, and the core
   conclusion it must convey before editing.
2. State the figure's problem list + fix plan, then make the smallest code
   change that addresses it — one panel-level concern per round, no
   opportunistic refactors.
3. Regenerate the figure (PDF + PNG).
4. **Read the PNG with the Read tool** (never `qlmanage -t` — it misrepresents wide layouts;
   never judge from the code or a comment in the script). Mandatory post-render protocol:
   - For **every text/annotation inside the plot area** — `ax.text` with `transform=ax.transAxes`
     or `transData` (this excludes `xlabel`, `ylabel`, `ax.set_title`, `suptitle` which are in
     the margin) — crop a ~30% region centred on the annotation and **Read the crop**. Confirm
     no data element (line, marker, error bar, shaded region, reference curve) lies within the
     bounding box. This is **mandatory for every inside-plot text element**, not conditional on
     suspicion — a code comment claiming the corner is "clean" does not substitute for the crop.
   - Spine check: crop the top and right edges and Read the crops before deciding spine presence
     (thumbnails both hide real spines and invent absent ones).
5. Run the project's batch script if shared helpers changed.
6. Report scripts changed, figures regenerated, and what you visually
   verified.

## References

Load only what the current task needs.

- [workflow.md](plotting-reference/workflow.md) — setting up or
  restructuring a plotting pipeline.
- [style-guide.md](plotting-reference/style-guide.md) — defaults for
  layout, typography, color, legends, log axes.
- [de-ai-defaults.md](plotting-reference/de-ai-defaults.md) — the
  remove-by-default decoration checklist; run it against every figure
  (it OVERRIDES "stay consistent" when a shared trait is a default-off
  decoration).
- [examples.md](plotting-reference/examples.md) — naming, minimal
  matplotlib pattern, GridSpec recipes.
- [iteration-playbook.md](plotting-reference/iteration-playbook.md) —
  symptom → fix recipes for concrete visual complaints. **Highest
  leverage during polishing rounds.**
- [validation.md](plotting-reference/validation.md) — pre-finish
  checks.

## Completion criteria

- Intended figures regenerated as PDF + PNG (SVG only if hand-alignment needed).
- Filenames start with `FigureN.` / `SupplementFigureN.`.
- Figure reads as one coherent unit at final manuscript size.
- Figure visually inspected (not just compiled): no text/line/legend overlap,
  fonts and mathtext render, palette and line hierarchy correct.
- Finish summary names scripts changed, figures regenerated, and visual
  checks performed.

## Plot code style

The house style for **plotting code** — name and organise the script so it reads like a domain
researcher wrote it by hand, not a batch-generated AI script. This is a WRITING standard, not a
checker. Apply while editing any plotting script.

### The hard boundary

Govern **naming and organisation only**. Never change what the code computes: the data it loads,
any numeric transform, axis-range semantics, statistics, or values annotated on the figure — that
is frozen science guarded by `check-figure-fidelity`. Renaming `d1` to `relative_error` is your
job; changing the value it holds is a fidelity violation. When a name and its value disagree, fix
the **name**, never the value.

### Naming — domain semantics, not placeholders

- **Functions**: named for the action + domain object drawn, not the figure slot —
  `plot_error_vs_resolution(...)`, `plot_field_snapshot(...)`, `add_reference_curve(...)` —
  NOT `plot_figure_3()`, `make_plot()`, `do_fig()`.
- **Variables**: carry the quantity they hold — `relative_error`, `grid_spacing`, `measured_flux`,
  `baseline_scores` — NOT `data1`, `arr`, `tmp`, `x2`, `res`, `out`.
- **Module-level config**: named for what it controls — `METHOD_COLORS`, `PANEL_LABEL_SIZE`,
  `FIGURE_DIR` — NOT `c`, `sz`, `cfg`, `params`.
- **Files / scripts / outputs**: follow the `FigureN.short_name.pdf` convention already above;
  never `plot.py`, `final.svg`, or one monolithic script building several unrelated figures.

### Structure — not a copy-paste template

- Factor shared style / data-loading / save / panel-label logic into helpers (`save_svg`,
  `add_panel_label`, a `load_*` per artifact); let each figure's entry function read like a
  description of THAT figure.
- One entry function per figure.
- No dead scaffolding: drop unused `if __name__` config blocks, commented-out earlier attempts,
  and `try: ... except Exception: pass` that swallows real errors.

### Comments — say WHY, not what

- Comment **decisions a reader would question**: why a log axis, why this clip range, why two
  panels share a scale. NOT `# create the figure`, `# plot the data`, `# set the label`.
- A short module docstring naming which figure(s) the script builds and which cached artifact
  each reads is worth more than line-by-line narration.
