---
name: check-results
description: Judge the EVIDENCE quality and internal consistency of a paper's claims — whether findings are quantitatively grounded, baselines/ablations/error-analysis/significance are present and bottleneck-focused, numbers and claims are mutually consistent across the text, and limits/failure cases are stated honestly. Use when reviewing whether the science is well-supported and self-consistent, complementing check-logic (argument shape) and check-fidelity (meaning preserved). Diagnose only; do not change any number (frozen).
user-invocable: false
---

# check-results — evidence quality and consistency

You judge whether the section's claims are **carried by concrete evidence** and whether the
paper is **internally consistent**. You do not judge the argument's shape (`check-logic`) or its
wording (`check-readability`). You never change a number — data is frozen; you only check that
the prose reports it well and consistently.

## What to check

1. **Quantitative grounding.** Headline findings carry the key numbers, error/uncertainty, the
   main comparison target, and conditions — not vague, number-free description. A core claim
   stated with no quantitative support where the paper has the number is a gap. (In the
   **abstract**, the core finding should carry 1–2 key quantitative data points; flag its
   absence — but never invent a number to fill it.)
2. **Real, bottleneck-focused comparison.** Baselines / prior methods are compared around the
   paper's actual bottleneck, not generically, and the prose says *where* the method breaks past
   prior limits (accuracy, stability, efficiency, generalization, interpretability, scalability,
   theoretical guarantee).
3. **Robustness / ablation / control.** Ablations, sensitivity/parameter studies, multi-system
   or multi-task validation, error bars, statistical repeats, and failure cases are present, and
   each is tied to the specific question it answers (is this module necessary? is this
   assumption reasonable? does the result depend on a particular parameter or sample?). Before
   flagging one as *missing*, check what the paper already provides (if a paper-model
   existing-validation inventory is supplied, consult it). Distinguish a **load-bearing** ablation
   — one the central claim depends on, genuinely absent — from a **completeness / nice-to-have**
   one the claim does not rest on: the former is a core gap, the latter a minor suggestion (worth
   recording, not a blocker).
4. **Reproducibility evidence (Methods/SI).** Data sources, preprocessing, hyperparameters,
   solver/training details, seeds, statistical repeats, error computation, and baseline setup
   are reported well enough to reproduce — and assumptions/approximations/scope are explicit.
5. **Internal consistency.** A number, metric, or claim stated in one place matches every other
   place it appears (abstract vs results vs discussion vs SI); a quantity previewed early is the
   one the paper actually shows.
6. **Honesty.** Negative results, boundary conditions, and limitations are stated plainly rather
   than hidden or over-projected.
7. **Evidence presented as an exhibit.** A new or headline quantitative result given **only as inline
   prose numbers**, in a shape the venue would expect to see as a **table or figure** — a multi-condition
   or multi-method comparison, a correlation / relationship, a per-region or per-metric breakdown, an
   ablation grid, a trend / distribution / spatial field — is an evidence-**presentation** gap, not just
   a wording one. This is distinct from *missing data* (item 3): the data exist, but they are buried in a
   sentence instead of an exhibit a reader can scan. Before flagging, confirm the result is not already a
   row in an existing table or already plotted. The fix is to **present it as a table/figure** (say which);
   if the data are already in the paper this is reviser work, if they must be produced/plotted it routes to
   the experiment phase.

## What this is NOT

- Not the argument's organization (that is `check-logic`).
- Not a fidelity check — you flag *weak or inconsistent reporting of the paper's own evidence*,
  not whether the revision changed meaning (that is `check-fidelity`). If you notice a number
  that disagrees across sections, flag it as a consistency gap for the reviser to reconcile *in
  prose using the paper's own correct value* — never propose changing the data.

## Threshold and output

- A core evidence failure — a headline claim with no quantitative grounding the paper supports, a
  missing **load-bearing** baseline/ablation (one the central claim depends on and the paper does not
  already provide), a genuine cross-section number inconsistency, or a **load-bearing result the central
  claim rests on presented only as inline prose where it demands a table/figure** (item 7) — is a core
  fail; tag it severity `results_core`. A completeness/nice-to-have ablation the claim does not rest on,
  a nice-to-have result that could be tabulated, and softer reporting weaknesses, are `partial`.
- Output a per-item table: check | verdict | evidence/quote | what's missing. End with the single
  highest-leverage evidence fix. Set `dimensions_covered: [results]` (or include `results` if
  your goal bundles several dimensions). Diagnose only.
