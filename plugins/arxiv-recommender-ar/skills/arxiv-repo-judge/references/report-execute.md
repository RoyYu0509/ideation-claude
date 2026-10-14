# Reproducibility Report: {arxiv_id}

## Claims Verified
{List all claims from the input `claims` list, e.g.:}
- **C1**: {description} — TESTED
- **C2**: {description} — TESTED / SKIPPED (budget)
- **C3**: {description} — SKIPPED (budget)

## C1: {claim_id} — {description}

### Identified Claim
**Contribution**: {contribution_method}
**Baseline**: {baseline}
**Primary metric**: {metric}
**Key setting**: {key_experimental_setting}
**README headline figure**: {headline_figure_description}
**Downgrade rationale**: {NONE or reason}
**Expected direction**: {direction}
**Claim summary**: "{claim_summary}"

### Pre-run Declaration
**Computational adjustments** (fixed before any claim was run):
- {e.g. training budget reduced from the paper's setting to fit available compute}
- {e.g. device: CPU only}
**Seed**: 0

### Baseline Integrity
| Baseline | Type | Key param | Verdict | Notes |
|---|---|---|---|---|
| {baseline_1} | {deterministic/stochastic} | {n_samples or —} | fair/sandbagged/cannot_determine | {one sentence} |

### Experiment Selection
**Chosen**: `{chosen_file}` — {reason: priority rule N, claim matched}
**Skipped**: {list of demo/tutorial/lower-dim files skipped and why}

### Results

| Method | {metric_1} | {metric_2 if present} |
|--------|-----------|----------------------|
| {baseline} (seed=0) | ... | ... |
| {contribution} (seed=0) | ... | ... |

**Summary**: {one sentence on the magnitude of the gap and what it means}

### Verdict ({claim_id})
**{PASS / FAIL / INCONCLUSIVE}** — {one sentence: the single most decisive observation}

---

{Repeat the above section for each additional tested claim, headed ## C2: ... etc.}

## Per-Claim Results

| Claim | Description | Verdict | Direction consistent? | Notes |
|-------|-------------|---------|----------------------|-------|
| C1    | {desc}      | PASS/FAIL/INCONCLUSIVE | true/false/null | {rationale} |
| C2    | {desc}      | PASS/FAIL/SKIPPED      | ...             | ... |

## Overall Verdict
**{PASS / FAIL / INCONCLUSIVE}** — {one sentence: decisive reason, noting which claim drove the verdict}

## Verified Contribution
{One paragraph synthesizing what this paper truly contributes based on tested claims.
State which claims passed (cite C1, C2…) and which failed. Describe the mechanism
driving each passing claim: what operation causes the result, under what condition,
and what the paper's genuinely novel element is vs what follows trivially from prior
work. Be precise — name the specific operation that produces the result and the
condition under which it holds ("method X improves metric M because component C performs
operation O under condition K"), not just "method X works better". This section is the
primary input for ideation agents.}

## Notes for Ideation
{1-2 sentences on the open directions this verification reveals — e.g. a claim that
passed but only barely, a condition the method requires that limits its scope, or a
gap between what was verified and what was claimed. Focus on what is ACTIONABLE:
where should follow-up work go?}
