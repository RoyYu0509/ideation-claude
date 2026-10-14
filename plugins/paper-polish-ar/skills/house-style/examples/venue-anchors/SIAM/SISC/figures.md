<!-- SISC figure-style guide. Consumed by /polish-figures (the figure-repaint pass), research-figure-plotting,
     and check-figure-fidelity (as the "what counts as this venue's style" context). This is the PER-VENUE
     figure stance that specializes the generic research-figure-plotting stance. Figures are FROZEN during
     /review and /polish; they are repainted only by /polish-figures. Evidence read from the rendered PDFs of
     ../papers/{2312.15837,2502.05088,2503.01276,2504.18513,2510.14197}. -->
# SISC — figure & table visual style (→ /polish-figures)

## Figure types this venue expects
- **Convergence / error curves on log–log (or semilog) axes**, with a DASHED reference-slope line annotated with the rate ("~h^2", "~R^{-n}", machine-precision line) — the canonical numerical-evidence figure.
- **Scalar/vector field heatmaps** of PDE solutions (2D), often as multi-panel grids comparing methods or instances.
- **Parity / scatter plots** (predicted vs. true, with the y=x diagonal reference) — the primary results figure for inference/surrogate papers. [2510.14197]
- **Spectral scatter** (eigenvalues on the unit disk / complex plane). [2312.15837]
- **3D solution surfaces** for geometric/PDE problems. [2503.01276]
- Schematic/pipeline diagrams are occasional, never decorative.

## Palette, lines, markers
- **matplotlib defaults are normal here** — do not impose a bespoke "branded" palette. Scalar fields: **viridis**; signed/complex fields: a diverging map (coolwarm-like). [2503.01276, 2504.18513]
- **Color + linestyle (and/or marker) REDUNDANCY** so a figure survives grayscale printing — method A = solid/circle, method B = dashed/square, etc. Do not rely on color alone. [strong across SINUM too]
- Markers distinguish methods/series; reference lines (theoretical rate, machine precision) are dashed/thin.

## Panel layout & labeling
- **Multi-panel grids** (e.g. 4 columns of PDE realizations; rows = method, columns = case). Two valid labeling styles — pick ONE and be consistent within the paper:
  - **(a)/(b)/(c) embedded in the image**, referenced in the caption. [2504.18513]
  - **Caption-based positional labels** — "Left:/Middle:/Right:", "First row:" — with NO letters drawn on the image. [2312.15837, 2510.14197] (more common in applied-math SIAM)
- **Row/column group titles** as plain text on the image are acceptable.

## Colorbars
- Right-mounted; **share ONE colorbar range across panels that are being compared** so differences are read directly, not rescaled away — a fairness discipline reviewers notice. [2502.05088]
- Per-panel colorbars are acceptable when panels are not meant to be compared on the same scale. [2504.18513]

## Axes & captions
- Convergence plots: log scale, labeled physical units where applicable; axis labels are math, not prose.
- **Captions trend self-contained for computational SISC papers** — list the fixed parameters, identify every panel/line, and state the takeaway (can run 60–150 words). [2510.14197] A terse caption is tolerated for simple field plots but the self-contained form is the target.
- Parenthetical benchmark label first is a common caption opener: "(KdV) Coefficient-wise errors for …". [2502.05088]

## Tables (SISC reports many)
- **booktabs**: top/header/bottom rules only, NO vertical rules. Caption ABOVE the table.
- Scientific notation X.XX×10^{-k}, ~2 significant figures; paired errors (train/test, ε₂/ε∞) reported side by side; group rows with horizontal rules, not heavy \multirow.
- A metadata footer row (e.g. SVD/timing) is acceptable. Best value usually not bolded.

## Toolchain reality (flag, don't silently unify)
- 2D plots are typically matplotlib (viridis); 3D surfaces sometimes come from a different toolchain (VTK/ParaView/MATLAB, jet-ish colormap). If repainting, either match the dominant toolchain or FLAG the 2D/3D inconsistency to the author — do not quietly rerender one in the other's style. [2503.01276]
