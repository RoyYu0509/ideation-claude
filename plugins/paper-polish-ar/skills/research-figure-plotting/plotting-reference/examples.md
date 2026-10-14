# Plotting Examples

Naming and minimal patterns.

## Output naming

```text
Figure1. method_comparison.pdf   (+ .png)
Figure2. ablation_summary.pdf    (+ .png)
SupplementFigure1. sensitivity_sweep.pdf  (+ .png)
```

Avoid: `plot.pdf`, `result.png`, `panel_A.pdf`, `new_plot_final.png`.

## Script naming

```text
make_figure1.py
make_figure2.py
make_supplement_figure1.py
make_all_figures.py
```

Avoid one monolithic script for several figures with different data
and layout.

## Minimal matplotlib pattern

```python
from pathlib import Path
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt

mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "cm",
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
})

FIGURE_DIR = Path("figures")


def save_pub(fig: plt.Figure, name: str, svg: bool = False) -> list[Path]:
    """At least vector PDF + raster PNG; SVG only when text is hand-aligned."""
    FIGURE_DIR.mkdir(exist_ok=True)
    paths = []
    for ext, kw in (("pdf", {}), ("png", {"dpi": 300})):
        p = FIGURE_DIR / f"{name}.{ext}"
        fig.savefig(p, bbox_inches="tight", **kw)
        paths.append(p)
    if svg:
        p = FIGURE_DIR / f"{name}.svg"
        fig.savefig(p, bbox_inches="tight")
        paths.append(p)
    plt.close(fig)
    return paths


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(0.02, 0.98, label, transform=ax.transAxes,
            ha="left", va="top", fontweight="bold")


def add_axis_arrows(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.plot(1, 0, ">k", transform=ax.get_yaxis_transform(), clip_on=False, ms=5)
    ax.plot(0, 1, "^k", transform=ax.get_xaxis_transform(), clip_on=False, ms=5)
```

## Grouped bars (methods × datasets)

Compute positions; don't hand-tune x coordinates.

```python
import numpy as np

K = len(methods)
w = 0.8 / K
for d, dataset in enumerate(datasets):          # +1 leaves a gap between groups
    start = d * (K + 1)
    for i, method in enumerate(methods):
        ax.bar(start + (i - (K - 1) / 2) * w, values[d][i], width=w,
               color=color[method], error_kw={"elinewidth": 1, "capsize": 2})
centers = [d * (K + 1) for d in range(len(datasets))]
ax.set_xticks(centers)
ax.set_xticklabels(datasets)
```

## GridSpec with mixed cbar / non-cbar panels

Colorbars become real cells; bottom rows span the unused cbar slot
above so their right edge aligns to the cbar body.

```python
from matplotlib.gridspec import GridSpec

fig = plt.figure(figsize=(7.5, 6.0))
gs = GridSpec(
    nrows=2, ncols=4,
    width_ratios=[1.0, 0.05, 1.0, 0.05],
    height_ratios=[1.0, 1.0],
    wspace=0.30, hspace=0.30, figure=fig,
)

ax_A  = fig.add_subplot(gs[0, 0])
cax_A = fig.add_subplot(gs[0, 1])
ax_B  = fig.add_subplot(gs[0, 2])
cax_B = fig.add_subplot(gs[0, 3])
ax_C  = fig.add_subplot(gs[1, 0:2])   # spans plot + cbar slot
ax_D  = fig.add_subplot(gs[1, 2:4])
```

## Square panels + colorbar

When a panel uses `set_box_aspect(1.0)`, get the cbar from the host axes
so it tracks the shrunk box height — *not* from a sibling GridSpec slot:

```python
ax.set_box_aspect(1.0)
cb = fig.colorbar(cf, ax=ax, fraction=0.046, pad=0.04)
```
