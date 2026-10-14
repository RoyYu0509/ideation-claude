<!-- MMS figure-style guide. Consumed by /polish-figures (the figure-repaint pass), research-figure-plotting,
     and check-figure-fidelity (as the "what counts as this venue's style" context). This is the PER-VENUE
     figure stance that specializes the generic research-figure-plotting stance. Figures are FROZEN during
     /review and /polish; they are repainted only by /polish-figures. Evidence read from the rendered PDFs and
     dossiers of ../papers/{2007.05260v1,2210.05573v2}. -->
# MMS — figure & table visual style (→ /polish-figures)

## Figure types this venue expects
- **Convergence / error curves on log-log axes** — the canonical evidence figure. Error (geometry,
  energy, estimator) vs. a physical length or cell-size parameter R (in Å), or vs. computational cost.
  DASHED reference-slope lines annotated with the theoretical rate ("~R^{-1.5}", "~R^{-3}",
  "~Cost^{-0.5}") are REQUIRED whenever a theoretical rate is claimed — they are the visual proof
  that numerics match theory. [2210.05573v2: Figs. 4.3–4.6; 2007.05260v1: Figs. 6–8]
- **Strain / far-field decay log-log scatter** — atomistic data points shown as semi-transparent
  scatter dots with a bold solid envelope curve overlaid; each boundary-condition order gets a
  distinct color+marker; reference slopes as dashed lines. [2210.05573v2: Fig. 4.3]
- **Domain decomposition / defect-core schematics** — colored-dot lattice diagrams showing QM/MM
  regions or defect topologies; no colorbar; minimal or no axes; pure structural illustration.
  [2007.05260v1: Figs. 1, 3, 4; 2210.05573v2: Figs. 2.1, 4.2]
- **Mesh / triangulation plots** — FE mesh with color-coded regions (QM core in red, continuum in
  blue, marked elements in gray shading); legends inside the figure. [2007.05260v1: Figs. 2, 4(b), 5]
- **Algorithm / convergence step sequences** — 4-panel horizontal strip showing mesh evolution across
  adaptation stages. [2007.05260v1: Fig. 5]
- **Multi-panel cost-vs-error grids** — 2×N or 3×2 layouts comparing error and cost-splitting across
  multiple defect types simultaneously. [2007.05260v1: Fig. 8]
- No field heatmaps, no colorbars (these are atomistic/lattice papers; fields live on discrete sites
  or are shown via convergence rates, not spatial color maps). No performance/profiling plots.

## Palette, lines, markers
- **matplotlib default color cycle** (tab10 / similar) — do NOT impose a bespoke palette. Blue,
  orange/red, green, gold are the dominant series colors across both papers.
- **Color + linestyle + marker REDUNDANCY** — color distinguishes series (i=0, i=1, i=2 or
  different error types); additionally use filled markers (●, ■, ▲, ★, ◆) so the figure survives
  grayscale printing. [2210.05573v2: blue●, orange■, green▲ for i=0,1,2]
- **Domain schematics** use high-saturation flat-fill colored circles on white: QM region = red/pink,
  buffer = magenta/blue, MM = blue/green, far-field = green. [2007.05260v1: Figs. 1, 3, 4]
- **Reference/theoretical slope lines**: dashed (or dotted/dash-dot), thin, black or near-black;
  each slope gets a distinct dash pattern when multiple slopes appear. Annotated in legend with the
  rate label ("R^{-1.5}", "Cost^{-0.5}").

## Panel layout & labeling
- **Multi-panel grids**: 5-panel (3 top + 2 bottom) for five-defect benchmark figures is standard.
  2-panel (side by side), 3-panel (horizontal), 4-panel (horizontal strip), and 6-panel (2×3) also
  appear. [2210.05573v2: 5-panel Figs. 4.2–4.6; 2007.05260v1: 6-panel Fig. 8]
- **Subfigure labels**: **(a)/(b)/(c)…** or **(A)/(B)/(C)…** in parentheses below each panel
  (caption-based positional labels). Do NOT draw letters inside the image. [both papers]
- **Italic bold lead-in** mini-subsection titles ("*Decay of strains.*", "*Moments convergence.*",
  "*Geometry error.*") immediately before each result group — no number, no separate subsection.
  [2210.05573v2: §4.2 uses this pattern consistently]
- Each panel is self-contained with its own axes and legend; shared axes across panels are not used.

## Axes & captions
- **Both axes log-scale** for all convergence and decay plots. Physical units (Å) on the x-axis when
  plotting against spatial domain size R or lattice distance |ℓ|; mathematical norm notation on the
  y-axis. [2210.05573v2: x-axis "R [Å]", y-axis "‖Dū − Dūi,R‖_{ℓ²}"]
- **Legends inside the plot area** (upper right or lower left depending on data), small font.
- **No error bars** — computations are deterministic; no stochastic uncertainty.
- **Captions**: "Figure N." (small caps "Figure", period) or "FIGURE N." depending on SIAM LaTeX class
  output; followed by one or two concise sentences. Captions are MODERATELY self-contained (they name
  the quantity and defect type, but may rely on main text for symbol definitions). [both papers]
  Caption opener often names the quantity first: "Convergence of geometry error ‖Dū − Dūi,R‖_{ℓ²}
  for i = 0, 1, 2 against domain size R." [2210.05573v2: Fig. 4.5 caption]

## Tables (MMS reports none in the two exemplars)
- ABSENT in both papers; all quantitative results are in figures or prose. Do not add a results
  table to match SISC norms — it is not expected here.
- If benchmark parameters are tabled (some MMS papers do this), use booktabs style (top/header/bottom
  rules, no vertical rules, caption above) consistent with the SIAM core.

## Toolchain reality (flag, don't silently unify)
- All figures in both exemplars appear to be matplotlib exports with standard sans-serif axis labels.
  No VTK/ParaView or MATLAB figures detected. The "envelope over scatter cloud" style in [2210.05573v2:
  Fig. 4.3] is a distinctive matplotlib technique (semi-transparent scatter + solid envelope) — preserve
  it if repainting. If a schematic (domain decomposition) was hand-composed rather than plotted, do not
  rerender it as a data plot.
