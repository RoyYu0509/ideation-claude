# Results — rubric

Acceptance criteria for the Results. Verdict + evidence per item. The section must be **organized
around the core scientific question as a progressive evidence chain**, not as a figure-ordered
experiment log.

**Few-shot** (weak "Fig. X shows…, no numbers" draft → the polished, interpreted, number-carrying
version, when this section is hard): (no example ships in this release; add your own under `house-style/examples/venue-anchors/`).

## Seven-part progression
1. **Core result first.** Do not open with minor experiments or technical detail. A conclusion-type
   topic sentence states what the section proves; the most representative result, key quantitative
   metrics, the main comparison, and the most important figure conclusion follow.
2. **Show it is real and significant.** Direct evidence: experimental / numerical results,
   theoretical validation, benchmarks, error analysis, statistical significance. Explain what the
   result *means* and how it supports the claim — not "Fig. X shows".
3. **Explain why you got it.** Mechanism / principle / method advantage; which key design produced
   the gain (accuracy, error reduction, stability, a new phenomenon). Causal explanation, not
   description.
4. **Compare with baselines / prior methods.** Organized around the core bottleneck, not generic.
   State where you break past prior limits — accuracy, stability, efficiency, generalization,
   interpretability, scalability, or theoretical guarantee.
5. **Robustness / ablation / control.** Ablation, parameter study, sensitivity, multi-
   dataset/system/task validation, error bars, statistical repeats, failure cases. Each verification
   states which question it answers (is a module necessary? is an assumption reasonable? does the
   result depend on a specific parameter or sample?).
6. **Generalizability.** Validation across broader systems / tasks / scales / distributions /
   scenarios, showing a general mechanism rather than a single case study.
7. **Per-subsection closing.** Each subsection ends with one sentence stating what it proved and
   leading into the next. No premature grand significance (that belongs in Discussion).

## Style checks
- Finding-centered, not figure-order-centered.
- Each subsection's first sentence is a conclusion-type topic sentence.
- Each figure serves one explicit argument.
- Not an experiment log or method description; does not repeat Introduction background.
- Specific: includes key numbers, errors, comparison targets, and conditions.
- Mechanism explanation present but restrained.
- Honest about negative results, boundary conditions, and failure cases.
- Subsections progress: effective → why → robust → general.

## Anti-patterns (flag)
- "Fig. X shows ..." with no interpretation.
- Figure-by-figure or experiment-by-experiment ordering.
- Over-projection / grand significance inside Results.
- Vague, number-free descriptions.

---

[FILL IN: extra Results criteria you and your advisor apply.]
