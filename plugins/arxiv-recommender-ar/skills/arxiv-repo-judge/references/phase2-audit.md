# Phase 2 (audit mode) — Static code-claim audit (NO execution)

Loaded by `arxiv-repo-judge/SKILL.md` when the input JSON has `mode: audit`
(the default on CPU-only / no-GPU hosts). This is the read-only path: REVIEW the
released code for claim coverage, method fidelity, and correctness red flags — do
NOT install, run, train, or download datasets. Do NOT load this file in `execute`
mode — use `phase2-execute.md` (this `references/` directory) instead.

Enter here only after Phase 1 has locked the claim spec.

You REVIEW the released code; you do NOT install, run, train, or download datasets.
The question is not "do the numbers reproduce" (you cannot run) but **"does the
released code credibly implement the claimed method, and is the comparison set up
correctly?"** — an artifact/code-integrity audit, complementary to the claim judge's
paper-internal check.

**Step A3 — Clone, read-only (≤60s)**

```bash
git clone --depth 1 {repo_url} /tmp/repo-{arxiv_id}
```

If the clone fails, the repo is empty, or it is private/unavailable → return
`inconclusive` (this is the ONLY normal route to `inconclusive` in audit mode).

**Step A4 — Locate the MAIN experiment code for C1**

Use the same experiment-selection priority as execute mode's Step 4 (the Priority −1
table-pointer rule is fully specified in `experiment-selection.md`, at the skill root
one directory up from this `references/` file): find the file(s) that produce the
headline contribution-vs-baseline comparison for claim C1.

```bash
find /tmp/repo-{arxiv_id} -name "*.py" -o -name "*.ipynb" | sort
```

Skip `demo`/`tutorial`/`example`/`quickstart` files. Record which file(s) implement
the contribution method, the baseline(s), the training/eval loop, and the metric.

**Step A5 — The five static checks (Read / Glob / grep only, no execution)**

For C1 (and any further claims you have budget to inspect), check:

1. **Claim coverage** — does code for the main experiment behind C1 actually exist
   (not just a demo, a figure-plotting script, or a README promise)?
2. **Method fidelity** — does the code implement the paper's *novel* mechanism, or is
   the contribution a stub / thin wrapper / `TODO` / `NotImplementedError` / a call to a
   stock library that is not the claimed contribution?
3. **Baseline presence** — for a head-to-head claim, is the baseline actually
   implemented or invoked, or are the "baseline" numbers hardcoded constants /
   committed CSV/JSON the comparison just reads back?
4. **Correctness red flags** — read the eval/train split and metric code for:
   evaluating on the training set, train/test leakage, a metric that does not match
   the paper's stated metric, result files committed into the repo and reused as
   "outputs", a single hardcoded/cherry-picked seed, or no real training/optimization
   loop at all (e.g. the "trained model" is a constant).
5. **Reproducible-in-principle** — are dependencies declared (requirements/env file),
   are configs/hyperparameters present, and is the data either bundled or obtainable
   via a documented download? (Data not bundled but clearly obtainable is fine.)

**Step A6 — Verdict**

The major/minor taxonomy and the ≥1-major / ≥3-minor thresholds are the shared
severity rubric in `severity-rubric.md` (this `references/` directory — the same rubric
the claim judge uses; load it if you need the definitions). Applied to this
CODE-integrity audit:

Classify each finding as **major**, **minor**, or **ok**. Only `major`/`minor` ISSUES
count toward the verdict — a clean/positive finding (e.g. "mechanism genuinely
implemented") is `ok` and counts for nothing.

- **major** — the CONTRIBUTION itself is not credibly implemented or is incorrect: its
  main-experiment code is absent or a stub; the claimed mechanism is not actually
  implemented (thin wrapper / `TODO` / `NotImplementedError` / a stock-library call that
  is not the contribution); results are hardcoded/faked or committed and read back as
  "outputs"; evaluation is on the training set or has clear train/test leakage; the
  metric does not match the paper's stated metric.
- **minor** — a reproducibility gap that does NOT impugn the contribution code itself:
  a baseline is not vendored in this repo, data not bundled (but obtainable),
  dependencies unpinned, configs partially missing, single seed with no error bars, a
  secondary claim (e.g. a speedup) lacking its measurement script.

> **Comparative claims** (C1 = "contribution beats baseline"): judge the CONTRIBUTION's
> code. Baselines are commonly run from their own authors' repos — a missing/external
> baseline is **minor**, NOT major, as long as the contribution is genuinely implemented
> and free of correctness red flags. Do not escalate "the head-to-head can't run
> end-to-end from this repo alone" to major.

Then (counting only major/minor ISSUES, not `ok` findings):
- `fail` — **≥1 major** issue.
- `flag` — 0 major AND **≥3 minor** issues (systemic reproducibility weakness) → penalize.
- `pass` — 0 major AND **≤2 minor** issues: contribution implemented, no red flags.
- `inconclusive` — only when the repo could not be obtained/read at all (Step A3).

**Step A7 — Write the audit report**

Write the audit report to `{cache_dir}/repo-{arxiv_id}.md` (fall back to `/tmp/repo-{arxiv_id}.md`)
following the exact template in `report-audit.md` (this `references/` directory; load it now).

**Step A8 — Cleanup**

```bash
rm -rf /tmp/repo-{arxiv_id}
```

Always clean up, even on inconclusive.
