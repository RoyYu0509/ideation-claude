# Severity rubric — shared by arxiv-repo-judge (audit mode) and arxiv-claim-judge

Both judges classify findings on the same two-level severity scale (major | minor, plus
`ok` for non-issues) and apply the same two counting thresholds. The definitions below are stated at the level both share; each judge
specializes them to its own domain — repo-judge audit → released-code integrity;
claim-judge → paper-internal claim-vs-evidence consistency — and maps the thresholds onto
its own verdict vocabulary.

## Finding severities

Classify every finding as one of:

- **major** — the finding strikes at the credibility of the paper's central
  contribution/claim itself: the claim is directly unsupported or contradicted by the
  evidence, or the contribution is not credibly implemented (absent code, a stub, a
  faked/hardcoded result, evaluation on the training set or clear train/test leakage, a
  metric that does not match the paper's stated metric).
- **minor** — a partial, peripheral, or reproducibility gap that does NOT impugn the
  core contribution/claim: evidence present but narrower/ambiguous than the claim, a
  missing or external baseline, data not bundled (but obtainable), unpinned
  dependencies, a single seed with no error bars, a secondary claim lacking its
  measurement script.
- **ok** — a clean or positive finding. `ok` findings count for NOTHING toward the
  verdict; only `major`/`minor` ISSUES are counted.

## Thresholds (count only major/minor ISSUES, not `ok` findings)

- **≥1 major** issue → escalate to the judge's harsher verdict.
- **0 major AND ≥3 minor** issues → escalate to `flag` (a systemic weakness across
  multiple checks/claims).
- **0 major AND ≤2 minor** issues → `pass`.

## What `flag` means (not a drop)

`flag` is NOT a keep/drop decision — the judge only reports the raw verdict; the JS
caller owns keep/drop. A flagged paper is penalized/filtered by the caller, never
silently dropped by the judge. Each judge maps the thresholds onto its own vocabulary:

- **repo-judge audit** distinguishes two escalation levels: `≥1 major → fail`;
  `0 major AND ≥3 minor → flag → penalize`.
- **claim-judge** has no `fail`; it collapses both triggers into `flag`
  (`≥1 major OR ≥3 minor → flag → filter` by default).
