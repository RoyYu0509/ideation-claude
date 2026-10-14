# Section skeletons + content requirements (no tiers)

The tier ladders of the old scoring-rubrics.md are RETIRED (2026-07-11
verified-kill redesign): nothing gates on section scores anymore — convergence
happened upstream, on verification artifacts. What survives here is the CONTENT
requirement per section and its output skeleton. Every quantitative value in
any section carries a `src:` anchor (bundle probe / paper table+page / checked
derivation step / URL) — the plan EXPANDS verified evidence; it never invents.

## 0. Significance & Contribution

Answers three diagnostics in prose (ambition, never rigor): new mechanism vs
re-application; field-level consequence if true; venue view. Then restate the
recheck's confrontation: the strongest rival row and why the residual delta
clears it.

```
## 0. Significance & Contribution
**New mechanism vs re-application:** [1-2 sentences]
**Field-level consequence if true:** [1 sentence — what changes in the field]
**Venue view:** [1 sentence]
**Strongest-rival confrontation:** [rival + residual delta + why it clears — from the verification record]
```

## 1. Claim & Grounding

The claim VERBATIM (it is frozen), plus the mechanism-level grounding: which
paper result carries it, cited by page + section (quotes were PDF-checked
upstream).

```
## 1. Claim & Grounding
**Claim:** [verbatim — identical to '## Verified Claim']
**Grounding:** [1-2 sentences citing p.X §Y: "<quote>" — the mechanism step the claim stands on]
```

## 2. Formal Proposition

Form: "Under [A1], [A2], …, [the NEW mechanism] achieves [guarantee] on
[benchmark D]." Assumptions are ACTUAL falsifiable conditions, each sourced
("from the paper (Assumption X / Lemma Y)" or "standard [field] result (cite)"
or "premise P<n> (probed)"). Guarantee quantitative (probability/rate/bound
with units). Claim type stated.

```
## 2. Formal Proposition
**Proposition:** Under [A1], [A2], ..., [method] achieves [guarantee] on [benchmark D].
**Claim type:** theoretical | empirical | both
**Assumptions:**
- A1: [...] (source: ...)
- A2: [...] (source: ...)
```

## 3. Baseline Landscape

Four roles, every row with a metric and a source anchor; naming a baseline
without a number is not acceptable. Strongest competitor comes from the
bundle's diff table (first row = the closest rival).

```
## 3. Baseline Landscape
| Role              | Name | Source | Metric on benchmark | Result (src-anchored) |
|---|---|---|---|---|
| Strongest comp.   | ... | src: arXiv:XXXX Table K p.P | ... | ... |
| Trivial lower bd. | ... | — | ... | ... |
| Ablation target   | ... | — | remove [X] | expected delta: [Y] (src: ...) |
| Oracle upper bd.  | ... | — | ... | ... |

**Expected delta:** [justified from Section 2 OR a src-anchored paper number OR a probe output]
```

## 4. Validation Plan + Scope

≥2 experiments, each: specific dataset (named precisely), metric with units,
expected range (justified), failure signal — the failure signals ARE the frozen
`falsifier_thresholds`, copied verbatim with their src anchors. Scope follows
from Section 2's assumptions; OOD gate if cross-domain, else "N/A".

```
## 4. Validation Plan + Scope
**Experiment 1: [name]**
- Dataset: [...]
- Metric: [... with units]
- Expected: [... and where it comes from]
- Failure signal: [the frozen threshold, verbatim, with its src]

**Experiment 2: [name]**
[same format]

**Transfers to:** [domain X] under [condition from Section 2]
**Does NOT transfer to:** [domain Z] because [which assumption breaks]
**OOD gate:** [specific experiment] | N/A
```
