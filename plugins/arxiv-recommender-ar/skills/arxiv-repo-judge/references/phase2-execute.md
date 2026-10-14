# Phase 2 (execute mode) — Clone, run, verify

Loaded by `arxiv-repo-judge/SKILL.md` when the input JSON has `mode: execute`
(GPU hosts). This is the clone-and-RUN path: reproduce the contribution-vs-baseline
experiment at the claimed seed and record a verdict. Do NOT load this file in
`audit` mode — use `phase2-audit.md` (this `references/` directory) instead.

Enter here only after Phase 1 has locked the claim spec.

**Step 3 — Clone (≤60s)**

```bash
git clone --depth 1 {repo_url} /tmp/repo-{arxiv_id}
```

If this fails → return `inconclusive`.

**Claim iteration protocol (applies to Steps 4–7):**

Work through `claims` (or the wrapped single-claim agenda) in order, starting at C1.
For each testable claim:
- Run Steps 4–7 targeting THAT claim's baseline and metric.
- Declare all computational adjustments (Step 6 pre-run declaration) once per claim,
  before running that claim. Adjustments declared for C1 do NOT carry over
  to C2 — declare fresh each time.
- Record a per-claim verdict: `pass | fail | inconclusive`.
- Do NOT re-use outputs from a prior claim's run for a different claim — each claim
  targets different experiment files or configurations.
- Stop iterating when the remaining wall-clock budget (`timeout_sec` minus elapsed)
  would not cover a minimal run of the next claim (budget floor: 15 min per claim).

Use the freed budget to cover as many claims as possible — test C2, C3 after C1 if
time allows. The goal is to understand what the paper delivers across ALL its stated
contributions, not just the innermost one.

When all targeted claims are complete (or budget exhausted), aggregate in Step 7.

**Step 4 — Select the experiment that validates the claim (≤3min)**

```bash
find /tmp/repo-{arxiv_id} -name "*.ipynb" -o -name "*.py" | sort
```

List ALL candidates. Then select by this priority (highest first):

-1. **(Highest) If `claims[0].testability_note` cites a specific Table/Figure N
    AND includes at least one pair of numeric targets (e.g. "Table N: baseline=<v1>,
    contribution=<v2>" — a table anchor plus a numeric pair), select the file whose
    experiment produces those numbers —
    overriding the README headline. Full rule: see `experiment-selection.md` (the skill
    root, one directory up from this `references/` file).**

0. The file that runs the experiment shown in the README headline figure. If multiple files share the same headline setting, prefer
   higher-dimensional (3D > 2D > 1D).
1. The file whose name or README description matches the key experimental setting
   from the claim spec (match a filename token to the claim's setting — a token
   echoing the claim spec's dataset or task).
2. The file that runs BOTH the contribution method AND the baseline in one execution
   (so the comparison is produced by a single run, not two separate scripts).
3. The file highlighted in the README as the featured result (the figure/table shown
   as the main result).

**Explicitly skip** files named or described as `demo`, `tutorial`, `example`,
`quickstart`, or "get started" — these are onboarding aids, not validation experiments.
Only select them if they are the only runnable option.

**Do NOT choose a lower-dimensional experiment for compute budget reasons.** If
the 2D/3D version exists and matches the claim spec, run it. If it truly exceeds
`timeout_sec`, return `inconclusive` — do NOT silently fall back to 1D.

State your chosen file and your reasoning (which priority rule and claim-spec field
it matches). If `Downgrade rationale` in your claim spec is not NONE, explain here
why the headline setting is unavailable.
If no file matches the claim spec → return `inconclusive`.

**Step 4.5 — Baseline integrity scan (before installing or running anything)**

For each baseline method present in the selected experiment, read its implementation
file (`utils_*/`, `baselines/`, or equivalent). Check three things:

1. **Budget-tunable baselines** (any baseline whose strength depends on a compute knob —
   number of samples/draws, chain length, ensemble size, search iterations, refinement
   steps): extract that knob from the source. Flag as sandbagged if it is set **far below
   the method's normal range** — low enough to cripple the baseline rather than reflect a
   fair default. Compare against the method's standard setting if you know it; otherwise
   judge whether the value is plausibly a good-faith default or an obviously starved one.
   *Reference (one common family — apply the same "far below normal" test to whatever
   baseline the paper actually uses): for Monte-Carlo / Bayesian baselines, sub-50 MC
   samples or sub-100 chain warmup-or-draws are typical sandbag signals.*

2. **Shared base model**: verify the baseline and contribution use the SAME trained
   base model (same architecture, same optimizer, same training data). If the
   contribution gets a larger or longer-trained model, flag it.

3. **Evaluation parity**: verify both methods are evaluated on the SAME test set,
   same α / confidence level, and the same metric functions.

For each baseline, assign one verdict: `fair` | `sandbagged:<reason>` |
`cannot_determine`.

**If ANY baseline is `sandbagged` → return `inconclusive`** with the sandbag finding
as the rationale. Do not proceed to Step 5.

This step does NOT count toward `timeout_sec` (it is read-only file inspection).

**Step 5 — Install dependencies (≤5min)**

```bash
python -m venv /tmp/venv-{arxiv_id}
source /tmp/venv-{arxiv_id}/bin/activate
pip install -r requirements.txt  # or: conda env create, poetry install, etc.
```

If installation fails or takes > 5min → return `inconclusive`.

**Step 6 — Pre-run declaration, then run at the paper's claimed seed**

**Pre-run declaration (required before running anything):**
State ALL computational adjustments upfront — epoch reductions, device (CPU/GPU),
alpha subset, dataset size reductions, etc. These are FIXED for ALL claims.
You may NOT change them after seeing any result. Declare once, apply uniformly.

**Epoch reduction rule — do NOT silently degrade the base model:**
If the paper's training requires more epochs than CPU can complete within `timeout_sec`,
return `inconclusive` with rationale "full training requires GPU (≥N epochs), cannot
complete in budget." Do NOT reduce epochs so aggressively that the base model fails to
converge — a degenerate base predictor makes the contribution-vs-baseline comparison
meaningless and wastes the entire timeout budget. This is the training analogue of the
dimensionality rule: just as you return `inconclusive` instead of silently downgrading
2D→1D, return `inconclusive` instead of silently downgrading 20k epochs→5k epochs to
the point of base-model failure. The only safe epoch reduction is one where you have
evidence the base model still converges (e.g. ≥70% of paper epochs, or a quick
convergence check before the full run).

**Seed**: always use seed 0 for all runs.

**Run the experiment at seed 0 for BOTH methods:**
Record for each (contribution AND baseline):
- The primary metric value
- The secondary metric value if present

If the experiment runs only ONE method in a single execution:
- Try to find a flag (e.g. `--method <contribution>` vs `--method <baseline>`) to run both.
- If no flag exists, run the script twice.

If the run crashes or times out → return `inconclusive`.

**Step 7 — Compare results and record verdict**

For the PRIMARY metric (first metric named in the claim's `metric` field):

- `direction_consistent`: does the contribution outperform the baseline at the paper's
  claimed seed? True or false. This is a single-run binary check.

Additional metrics are recorded in the report Notes but do not affect the verdict.

**Scope validity check** (after confirming direction_consistent):

Ask: *"What assumption must hold for this advantage to be genuine? Is there a
measurement—using outputs already computed, without re-training—that would test
that assumption?"*

If YES and it fits in ≤5 min wall-clock: run it and record what you found in one
sentence. Common patterns, for illustration only:

- Method claims advantage in a specific subset (hard region, noisy area, OOD split):
  compute the same metric over the full test set using outputs already in memory.
  The question is whether the local gain trades off against the complement.
- Convergence-rate claim (O(hᵖ) scaling): a single grid size cannot estimate the
  rate — note "rate untested: only one resolution run."
- Speed/efficiency claim: verify accuracy is maintained alongside the speedup, not
  just speed alone.
- Standard benchmark claim: no additional check needed if the test set is already
  the canonical held-out split.

If no meaningful assumption-test exists: write `Scope validity: N/A`.

This is **informational only** and does NOT affect `direction_consistent` or the verdict.

Verdict rules (per claim):
- `fail` if `direction_consistent` is false
- `pass` if `direction_consistent` is true
- `inconclusive` in any other case (crashes, timeouts, methods not identifiable)

**Per-claim verdict aggregation (overall verdict):**
After all targeted claims are tested (or budget exhausted):
- Overall `verdict` = `fail` if ANY per-claim verdict is `fail`.
- Overall `verdict` = `inconclusive` if no claim reached a `pass` or `fail` verdict.
- Overall `verdict` = `pass` only if ALL tested claims are `pass` AND ≥1 was tested.
- Claims not attempted due to budget are recorded as `verdict: "skipped"` in
  `claims_tested`. Skipped claims do NOT affect the overall verdict.

**Step 8 — Write the verification report**

Determine the report path:
- If `cache_dir` is in your input JSON: `{cache_dir}/repo-{arxiv_id}.md`
- Otherwise: `/tmp/repo-{arxiv_id}.md`

Write the verification report to that path using the exact template in `report-execute.md`
(this `references/` directory; load it now).

**Step 9 — Cleanup**

```bash
rm -rf /tmp/repo-{arxiv_id} /tmp/venv-{arxiv_id}
```

Always clean up, even on inconclusive.
