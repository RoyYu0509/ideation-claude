<!-- SINUM figure-style guide. Consumed by /polish-figures (the figure-repaint pass), research-figure-plotting,
     and check-figure-fidelity (as the "what counts as this venue's style" context). This is the PER-VENUE
     figure stance that specializes the generic research-figure-plotting stance. Figures are FROZEN during
     /review and /polish; they are repainted only by /polish-figures. Evidence read from the rendered PDFs
     and dossiers of ../papers/{2505.22103v1,2507.00193v2,2510.04751v1}. -->
# SINUM — figure & table visual style (→ /polish-figures)

## Figure types this venue expects

- **Log-log convergence curves** with annotated reference-slope lines — the canonical SINUM evidence
  figure. x-axis = mesh size h or domain radius R or number of elements J; y-axis = error norm (L∞,
  ℓ², energy). Reference slope labeled directly: "~R^{-1}", "~R^{-2}", "~h^2", "~h^4". Two-curve
  comparison (baseline i=0 vs higher-order i=1) is the standard layout. [2510.04751v1 Figs. 2–4;
  2507.00193v2 Figs. 5.1–5.2]
- **Convergence-vs-iteration plots** (error vs. Schwarz iteration, semilog-y or log-y scale) with
  multiple lines per panel (one per method/version), reference tolerance line optional. Caption
  identifies all series; panel is identified as "Left:" / "Right:" / "Middle:" in caption.
  [2505.22103v1 Figs. 6, 8, 9, 10-Right]
- **Convergence factor plots** (ρ vs. frequency ω̃, semilog-x scale), used to bridge continuous
  theory to discrete experiments. Minimalist: dashed vertical guide lines at key frequency bounds
  (ω̃₁, ω̃_c, ω̃₂), horizontal dashed lines at theoretical bounds (R_c, R_ext). [2505.22103v1 Fig. 7]
- **Energy-vs-time and mesh-quality-vs-time line plots** — plotted together per example; energy
  decay confirms Theorem 4.3 (unconditional stability), mesh ratio Rᵐ (max/min edge length) confirms
  equidistribution. These two quantities are co-equal validation criteria in geometric-flow papers;
  always report both. [2507.00193v2 Figs. 5.3–5.14]
- **3D mesh surface renders** (solid blue, triangulation visible) for geometric-PDE papers — MATLAB
  default single-color render (blue face + darker blue edges), no colorbar, no axes on the 3D image.
  Shown at multiple time snapshots (t=0, intermediate, final) with no coloring by physical quantity.
  [2507.00193v2 Figs. 5.6–5.14]
- **Scatter plots with envelope** (raw atom data as transparent cloud, solid envelope curve) for
  strain-decay verification. [2510.04751v1 Fig. 2]
- **Schematic / geometry diagrams** — sparse, illustrative, TikZ or MATLAB: domain decomposition
  sketch, geometry of Γ(t) with labeled vectors. Placed in the formulation section, not as decoration.
  [2505.22103v1 Figs. 2–4; 2507.00193v2 Fig. 2.1]
- **Pareto-frontier plots** (error vs. CPU time, log-log) — acceptable when cost is a stated
  theoretical contribution; both geometry error and energy error shown as separate curves.
  [2510.04751v1 Fig. 5b]
- No heatmaps as primary evidence except solution snapshots in applied-context papers (not the core
  analysis figure). [2505.22103v1 Fig. 10-Left: solution heatmap as an illustration, not evidence]

## Palette, lines, markers

- **Two to three series is the norm.** SINUM convergence figures do not need more than three
  distinguishable curves per panel; the analysis is the novelty, not a large ablation grid.
- **Color + linestyle (and/or marker) REDUNDANCY** so the figure survives grayscale printing.
  This is a hard requirement for this venue family:
  - Three versions/methods: Version I = red dotted, Version II = blue dashed, Version III = green
    dash-dot. [2505.22103v1 Figs. 6–10: exact color-linestyle pairing maintained across ALL figures]
  - Two orders (baseline vs higher-order): i=0 = blue solid circles, i=1 = red solid triangles/stars;
    dashed lines reserved for reference slopes. [2510.04751v1 Figs. 2–5]
  - Time-series (boundary conditions): solid / dashed / dash-dot with no markers; color (black,
    red, dashed-black) carries secondary differentiation. [2507.00193v2 Figs. 5.3–5.5]
- **3D surface renders:** single solid blue (MATLAB default 'b'); mesh lines as darker blue; no
  colormap. Raw MATLAB output is venue-acceptable — no post-processing expected. [2507.00193v2]
- **Schematic diagrams:** black curves only; analytical sketches use thin lines, dashed guides,
  labeled key values on axes. No color. [2505.22103v1 Figs. 3–4]
- No matplotlib viridis heatmaps as primary evidence in SINUM; viridis/parula appear only in
  solution-snapshot panels of applied-context papers.

## Panel layout & labeling

- **Caption-based positional labels — the SINUM default.** Panels are identified in the caption as
  "Left:", "Right:", "Middle:", "Top:", "Bottom:", "Left panel", "right panel". NO (a)/(b)/(c)
  letters embedded in the image. [2505.22103v1 Figs. 6–10; 2507.00193v2 Figs. 5.1–5.14;
  2510.04751v1 Figs. 2–4]
  - Exception: stacked sub-figures within a composite figure may use **(a)/(b)** labels with bold
    in the caption ("**(a)**" and "**(b)**"), when panels differ structurally (e.g., CPU scaling vs
    Pareto frontier). [2510.04751v1 Fig. 5]
- **Row/column group titles** as plain text on the image (e.g., "Version I", "Version II") are
  acceptable for multi-row grids. [2505.22103v1 Figs. 8–9]
- **Left = baseline / simpler case; Right = higher-order / larger ratio** is a consistent spatial
  convention in the roster. Do not flip this when repainting panels.
- Paired left/right layout (screw dislocation left, edge dislocation right) is a structural
  signature for comparative experiments — preserve pairing. [2510.04751v1 Figs. 2–5]

## Captions

- **Self-contained captions are the SINUM standard.** A caption must: name all methods/versions in
  each panel, state all fixed discretization parameters (∆x, ∆t, mesh size, tolerance), and identify
  panels explicitly. Caption can run 40–120 words. [2505.22103v1 Fig. 8 caption is the exemplar:
  "Convergence behavior of the three local transmission conditions with a given mesh size ∆x = 1/40
  and four different time steps ∆t = [1/20, 1/40, 1/80, 1/160]. Top: ν₁/ν₂ = 10. Bottom: ν₁/ν₂ =
  10³. Left: Version I. Middle: Version II. Right: Version III."]
- Caption numbering: "Fig. X.Y:" or "Fig. X:" — section-prefixed or flat depending on the paper.
  Do not normalize one to the other.
- Reference slopes labeled DIRECTLY on the plot with annotation (e.g., "~R^{-1}" next to the dashed
  slope line), not only in the caption. [2510.04751v1 Figs. 3–4; 2507.00193v2 Figs. 5.1–5.2]

## Colorbars

- Rare in pure SINUM analysis papers. [2507.00193v2] has zero colorbars (all 3D surfaces are single
  blue). [2505.22103v1] has one colorbar on the heatmap in Fig. 10-Left (MATLAB parula, range 0–50,
  temperature in °C) — per-panel, not shared, since it is the only field plot.
- When a colorbar appears for a field comparison, follow the SISC shared-range rule: share ONE
  colorbar range across panels being compared on the same scale.

## Axes & typography

- Convergence plots: both axes log scale; x-axis label is the independent variable in math mode
  (h, R [Å], J, N_at); y-axis label is the error norm ("Error", "Geometry Error", "Energy Error",
  "Strains"). Physical units in square brackets where applicable.
- Iteration plots: y-axis log scale, x-axis linear integer ("Iteration").
- Energy plots: both axes linear; x-axis "t", y-axis "energy" or "Rᵐ".
- Axis labels and tick labels use LaTeX math mode (serif, Computer Modern or Latin Modern), matching
  the body font. Raw MATLAB output with LaTeX interpreter enabled is the standard toolchain for this
  community. A 2D/3D toolchain inconsistency (MATLAB for 3D, matplotlib for 2D) should be flagged to
  the author rather than silently unified. [dossier 2507.00193v2 off-lens note]

## Tables (SINUM uses few or none)

- Many SINUM papers have ZERO tables: all results in figures. [2507.00193v2, 2510.04751v1]
- When a table exists: booktabs style (top/header/bottom rules only, NO vertical rules); caption
  ABOVE the table; integer or rational values in math notation (∆x = 1/40, not 0.025; µ² = 10²,
  not 100); best value usually NOT bolded. [2505.22103v1 Table 1]
- Do not add tables where the paper uses log-log plots — this is a venue-appropriate choice.
