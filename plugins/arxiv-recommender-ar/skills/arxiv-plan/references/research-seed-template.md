# /research Seed template

The final section of the output file. Structured block copy-pasteable verbatim into
`/research <paste>`. Use this exact template — the field labels and `---` delimiters
are required. The `---` line before and after the seed block marks the copy-paste boundary.

```
---

## /research Seed

CONTEXT:
You are helping investigate a research hypothesis in [field].
The parent paper is "[title]" (arXiv:[arxiv_id]).
Significance (Section 0): [significance_status] — [the field-level contribution in 1 sentence].
Closest competitor to beat: [strongest competitor from Section 3, name + result].
Researcher's relevant background (positioning only — not a reason the idea is novel): [thread or prior paper that makes the researcher able to execute this]. (Omit line entirely if none.)

HYPOTHESIS:
[Formal proposition from Section 2, verbatim. Must be a complete sentence.]

FIRST EXPERIMENT:
[Fill based on contribution_type:
  • new_empirical_finding / new_application → Dataset + metric + expected result range from Section 4 Experiment 1.
  • new_theorem / new_method → First formal step: the specific lemma to prove, or the specific algorithmic component to implement and unit-test, from Section 4 Experiment 1.]

BASELINES TO BEAT:
- [Strongest competitor: name, paper, metric or formal result]
- [Ablation: "remove [X], expect delta [Y]" OR for theoretical work: "weaken assumption [A], expect rate to drop from [R1] to [R2]"]

SCOPE CONSTRAINTS:
- Applies to: [from Section 4 "Transfers to"]
- Does not apply to: [from Section 4 "Does NOT transfer to"]

OPEN QUESTIONS (resolve during proposing phase):
1. [Question 1 from Step 4 — question only, no RAISE/LOWER]
2. [Question 2]

---
```
