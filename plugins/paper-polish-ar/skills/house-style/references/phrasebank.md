# Phrasebank: positive replacement bank for acceptable prose moves

Complement to banned-vocabulary.md: that file says what NOT to write; this file gives concrete, acceptable phrasings for the moves that appear in every section. Every phrasing here is venue-neutral. The target voice for a given run is set by the selected venue profile (house-voice.md plus the venue's `## register`); pick whichever phrasing fits the specific claim and evidence, and verify that the evidence strength matches the verb before using any phrase.

---

## 1. Stating a gap

Prefer precise statements over dramatic ones. Name the specific system, regime, or condition that has not been studied.

**Acceptable:**
- `... remains poorly understood in the regime of ...`
- `... has not been examined for ...`
- `... has received limited attention in the context of ...`
- `Few studies have addressed ... when ...`
- `Evidence is sparse for ... at ...`
- `Prior work has not characterized ... beyond ...`

**Avoid:** "no one has ever studied", "completely unknown", "entirely ignored by previous work"; these overstate and read as hype.

---

## 2. Hedging: keep only scientifically meaningful hedges

A hedge should signal a real boundary: an assumption, a scope limit, an approximation, or a measurement constraint. Drop hedges that exist only to soften a claim that the data actually support.

### Strong evidence: state it directly
- `X shows ...`
- `X demonstrates ...`
- `X establishes ...`
- `The data reveal ...`
- `The results indicate ...`

Use when the experimental design and statistical power justify a direct claim.

### Moderate evidence: qualified interpretation
- `X suggests that ...`
- `X is consistent with ...`
- `The results support the view that ...`
- `The data point to ...`
- `X appears to ...`

Use when the interpretation is plausible but not the only one the data admit.

### Speculative or mechanism-level inference
- `X may reflect ...`
- `X could arise from ...`
- `One possible explanation is that ...`
- `This is consistent with, though does not prove, ...`

Use when moving beyond direct observation into mechanism or extrapolation.

Do not layer multiple hedges on one claim (e.g., "may possibly suggest"). Pick the right level and commit.

---

## 3. Framing evidence

Match the adjective to the actual state of the literature.

**Quantifying evidence strength:**
- weak/preliminary: `limited`, `scant`, `sparse`, `preliminary`
- developing: `growing`, `emerging`, `accumulating`
- strong: `robust`, `consistent`, `reliable`, `substantial`

**Useful sentence frames:**
- `The evidence presented here suggests that ...`
- `The available data support ...`
- `Across [N] [datasets / cases / benchmarks], X holds for ...`
- `The error decreases monotonically with ... (Table N), which suggests ...`
- `This pattern is consistent across [conditions], with the exception of ...`

Lead with the number or comparison where possible; do not bury it.

---

## 4. Transitions between ideas

Use the smallest connective that signals the relationship. Do not open every sentence with a transition word.

**Contrast:**
- `however` / `by contrast` / `whereas` / `nevertheless` / `despite this`

**Addition:**
- `furthermore` / `in addition` / `also` (plain; use when the addition is minor)

**Consequence:**
- `therefore` / `thus` / `consequently` / `as a result`

**Qualification:**
- `at least for ...` / `in this setting` / `in the low-noise regime`
- `approximately` / `to within ...`

**Paragraph linking without repeating "This suggests":**
- Restate the noun phrase: `Such instability ...` / `This gradient structure ...`
- Definite noun phrase carrying forward: `The resulting residual ...`
- Participial summary (use sparingly, once per section): `Taken together, ...`
- Zero-connective when the logical progression is already clear from the content

Limit one demonstrative-led sentence opening per paragraph.

---

## 5. Stating a contribution

Be specific and bounded. Name the method, quantity, or result; do not claim more than the paper shows.

**Acceptable:**
- `We propose [method], which [specific property] for [specific problem class].`
- `[Method] reduces [error metric] by [X]% relative to [baseline] on [benchmark].`
- `This work characterizes [phenomenon] in the regime of [conditions].`
- `We derive [result], which bounds [quantity] for [class of problems].`
- `To our knowledge, this is the first [specific thing] for [bounded scope].`

**Avoid:** "groundbreaking", "revolutionary", "novel" (without a bounded scope), "unprecedented". Let the specific result carry the claim.

---

## 6. Comparing to prior work

**To align with earlier work:**
- `These results are consistent with [citation].`
- `This finding accords with ...`
- `Our observations broadly agree with ...`
- `[X] confirms the trend reported in [citation] for ...`

**To mark divergence:**
- `In contrast to [citation], we find that ...`
- `This differs from [citation], possibly because [specific reason].`
- `One possible source of the discrepancy is ...; [citation] used [different condition].`

Always name the specific reason for the discrepancy if one is available; do not leave the reader to guess.

---

## 7. Limitation and scope statements

Pair limitation language with the specific source of uncertainty, not with vague modesty.

- `These results hold for [specific scope]; generalization to [other regime] remains to be tested.`
- `A limitation of this study is [specific constraint], which may affect [specific quantity].`
- `We cannot exclude [specific alternative explanation] because [specific gap in the data].`
- `The error bound assumes [specific assumption]; when [assumption fails], the bound need not hold.`

---

## 8. Future-work statements

Ground each future-work claim in a specific limitation or open question from this paper.

- `Further work is needed to determine whether [specific question].`
- `A natural extension is to [specific next step], which would require [specific data/method].`
- `Whether [finding] generalizes to [broader class] is an open question.`
- `Larger [datasets / cohorts / benchmarks] are required to [specific purpose].`
