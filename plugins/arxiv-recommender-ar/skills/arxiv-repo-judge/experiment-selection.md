# Experiment Selection — Priority −1 (testability_note table pointer)

This file defines the full rule for Step 4 Priority −1 in `SKILL.md`.

## Trigger condition

Priority −1 fires when **both** of the following are true in `claims[0].testability_note`:

**(a) Table/Figure reference** — the note contains one of these patterns (case-insensitive):
- `Table N`, `Table N.N`, `Tab. N`, `Figure N`, `Fig. N`, `Appendix Table N`
  where N is a digit or digit range (e.g. "Table 3", "Fig. 2b", "Table B.1")

**(b) Numeric targets** — the note contains at least one pair of numbers that look like
metric values for contribution vs baseline (e.g. "Table N: baseline=<num>, contribution=<num>",
"<metric>: contrib=<num> vs baseline=<num>").

If only (a) is present (the note says "see Table 3" without numbers) → do NOT trigger.
If only numbers are present without a Table/Figure anchor → do NOT trigger.
Both conditions must be met.

## File selection logic

1. Extract the Section reference from the note (e.g. "Section 5.2.1", "Section 4",
   "Appendix B").
2. Scan the repo file list for a file whose name or README description matches that
   section's topic (if the section runs "<task> on <dataset>", look for filename tokens
   matching that task or dataset — the task name, the dataset name, or abbreviations of either).
3. If exactly one file matches → select it.
4. If multiple files match → prefer the one explicitly mentioned in the note
   (e.g. a filename that spells out the section's task), then fall back to the highest-priority
   match by filename specificity.
5. If no file matches → fall through to Priority 0 (README headline).

## Downgrade rationale format

When Priority −1 fires, write:
```
Downgrade rationale: claim-judge table pointer: Table N (Section X.Y.Z)
```

## Why this rule exists

The claim judge reads the paper's PDF and identifies which specific table contains the
primary quantitative claim. This is more reliable than the README headline for
experiment selection because:
- The README may highlight a visual/qualitative figure rather than the key numeric table
- Running the wrong experiment forces the repo judge to reconstruct the data generation
  pipeline from scratch, introducing deviation from the paper's exact setup
- The claim judge's testability_note is a first-class pointer into the paper's own
  quantitative evidence

## What NOT to do

- Do NOT apply this rule to vague notes like "results are in Section 5" — no numbers.
- Do NOT override Priority 0 when the testability_note describes a weaker secondary
  experiment than the README headline (e.g. "a 1D toy example in Table 1" when the
  README headline is a full 3D benchmark).
- If the testability_note references a table in the Appendix and the repo has no
  file that clearly maps to it, fall through to Priority 0.
