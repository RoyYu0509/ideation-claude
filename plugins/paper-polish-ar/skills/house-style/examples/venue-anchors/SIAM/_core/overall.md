# SIAM family — register narrative & paper roster (CORE)

> **Note.** The section few-shot files (`abstract.md` … `discussion.md`) are not shipped in this release; the roster below describes the full calibration set.


## How this pack is organized (core + overlay)
"SIAM" is not one register — it is a **spectrum of sub-brands**. This pack factors that:
- **`_core/`** (this folder) holds what is INVARIANT across the family: citation/title/abstract/voice/macro-structure/cross-reference conventions (profile.md), the micro prose voice + the negative space of things SIAM does NOT do (voice.md), and the macro skeleton + argument arc (structure.md).
- **`<sub-brand>/`** (SISC, SINUM, MMS) holds the DELTAS that vary along the spectrum: theorem density, proof placement, tables-vs-figures, performance reporting, figure conventions — plus that sub-brand's before→after section few-shots, figure-style guide, and review kit.

At runtime the resolver composes `_core/` + the chosen `<sub-brand>/`. Name a sub-brand (or let the picker detect it from the paper); the overlay's fields override the core's.

The three sub-brands, on the spectrum:
- **SISC** (SIAM J. Scientific Computing) — **computation-forward.** Numerical methods, performance/hardware reporting, tables and many figures, algorithm environments; theory exists to justify the method.
- **SINUM** (SIAM J. Numerical Analysis) — **analysis-forward.** Theorems with descriptive names, full inline proofs, convergence analysis; often no tables; convergence rate is the currency, not wall-clock.
- **MMS** (Multiscale Modeling & Simulation) — **multiscale / mixed.** Coupling and upscaling problems; theory + numerics in balance.

## Paper roster (10 arXiv math.NA exemplars; full dossiers in ../papers/)
### SISC (computation-forward)
| id | short title | sub-genre |
|---|---|---|
| 2312.15837 | data-driven Koopman–Schur decomposition (Drmač, Mezić) | theory + algorithm + numerics |
| 2502.05088 | nonlinear manifold approx. via compositional polynomial networks (Bensalah, Nouy, Soffo) | methods + embedded theory |
| 2503.01276 | hierarchical multicontinuum homogenization (high-contrast media) | methods/numerical (MMS-adjacent) |
| 2504.18513 | PODNO: proper-orthogonal-decomposition neural operators (Cheng et al.) | methods + ~10pp analysis |
| 2510.14197 | neural networks for Bayesian inverse problems / FitzHugh–Nagumo (Villalobos, Rudi, Mang) | methods/numerical (ML-adjacent; 0 theorems, 25 tables) |
### SINUM (analysis-forward)
| id | short title | sub-genre |
|---|---|---|
| 2505.22103 | optimized Schwarz methods for heterogeneous heat transfer (Gander, Lu, Wu) | theory/numerical ~60/40 |
| 2507.00193 | energy-stable parametric FEM for Willmore flow (Garcke, Nürnberg, Zhao) | methods + theory (theory-forward) |
| 2510.04751 | higher-order BCs for atomistic dislocation simulations (Wei, Braun, Wang, Zhang) | methods + proof backbone |
### MMS (multiscale / mixed)
| id | short title | sub-genre |
|---|---|---|
| 2007.05260 | a posteriori error estimates for adaptive QM/MM coupling | theory + numerical |
| 2210.05573 | higher-order far-field BCs for crystalline defects (Braun, Ortner, Wang, Zhang) | methods-dominant mixed (SINUM-adjacent) |

## How to read the dossiers
Each `../papers/<id>.md` is a full house-style dissection along the lens (structure / rhetorical moves / prose voice / math & notation / evidence conventions / figure style / citation-title-metadata + off-lens), with every observation tagged **[INVARIANT]** (folded into `_core/`) or **[PAPER-SPECIFIC]** (a sub-genre/idiosyncrasy, kept out of the core). To hear a sub-brand's full-paper voice, read its rostered papers' dossiers together.
