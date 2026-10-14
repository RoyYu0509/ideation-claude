# Chinese-author English-writing guide: L1-interference patterns and self-check routine

Practical reference for a Chinese-native author writing technical English for a top journal. Covers the most common places where Chinese sentence logic leaks into English drafts, and a short self-check pass to run before handing off to the polish loop.

---

## 1. Translate intent, not syntax

Chinese academic writing often packs background, motivation, method, and implication into one long sentence, ordered by the author's mental flow rather than by the rhetorical need of the section. Before writing English, decompose the Chinese note into:

- **claim**: what the result is
- **evidence**: what supports it
- **condition**: the scope or assumption under which it holds
- **comparison**: the baseline or prior-work reference
- **implication**: what follows from it
- **limitation**: what it does not cover

Then write in the order the English section requires (e.g., gap before method in an introduction; observation before interpretation in results), not in the order of the Chinese sentence.

---

## 2. Common L1-interference patterns

### 2.1 Article and number agreement

Chinese has no articles and does not mark plural on nouns, so drafts often omit "the" / "a" or mis-match singular and plural.

| Draft pattern | Repair |
|---|---|
| "model converges faster" (missing article) | "the model converges faster" or "our model converges faster" |
| "we test on three dataset" | "we test on three datasets" |
| "result shows that" | "the results show that" or "our results show that" |
| "experiment are conducted" | "experiments are conducted" |

Quick test: every count noun in a sentence needs either a determiner (the / a / this / our / ...) or explicit plural. Read each sentence and check.

### 2.2 Topic-comment vs. subject-prominent structure

Chinese sentences often start with the topic (what the sentence is about) as a bare noun phrase, then comment on it. English expects a grammatical subject that matches the verb.

| Draft pattern | Repair |
|---|---|
| "As for the accuracy, it is improved by ..." | "The accuracy improves by ..." or "We improve the accuracy by ..." |
| "Regarding training cost, the method reduces it" | "The method reduces training cost by ..." |
| "For the boundary condition, we enforce it via ..." | "We enforce the boundary condition via ..." |

### 2.3 Over-nominalization

Chinese academic writing favors noun phrases; translated directly, English sentences pile abstract nouns and lose the verb.

| Draft pattern | Repair |
|---|---|
| "The performance improvement of the proposed method is significant" | "The proposed method improves [metric] by X%" |
| "Realization of error reduction is achieved through ..." | "The error decreases through ..." or "We reduce the error by ..." |
| "The application of the algorithm enables the acceleration of convergence" | "Applying the algorithm accelerates convergence" |

Prefer an active verb over a noun derived from that verb. Name the specific quantity rather than "improvement" or "performance".

### 2.4 Redundant connectives

Chinese prose uses connectives in correlated pairs (虽然...但是, 因为...所以, 不仅...而且). Translating both halves produces grammatically incorrect or redundant English.

| Draft pattern | Repair |
|---|---|
| "Although X, but Y" | "Although X, Y" or "X; however, Y" |
| "Because X, so Y" | "Because X, Y" or "X; therefore, Y" |
| "Not only X, but also Y" | Keep as-is (this is correct English) or "X and also Y" |
| "On one hand... On another hand..." | "On one hand... On the other hand..." |

### 2.5 Scope claims translated from 首次 / 创新性

Chinese drafts often carry 首次 ("first time") or 创新性 ("innovative") without specifying scope. In English, an unbounded "first" claim reads as overclaiming.

| Draft pattern | Repair |
|---|---|
| "For the first time, we propose ..." | "To our knowledge, this is the first [specific thing] for [bounded scope]." |
| "Our innovative method ..." | Name the specific property: "Our method, which [specific property], ..." |
| "显著提高" without a baseline | Add the comparator: "reduces X by Y% relative to [baseline]" or soften: "reduces X" |

### 2.6 Mechanism inferred from correlation

Chinese notes sometimes state causal mechanism when the data only show correlation.

| Draft pattern | Repair |
|---|---|
| "X improves because of Y" (Y not measured) | "X improves; one possible explanation is Y" |
| "The reason is that ..." (no mechanistic data) | "This is consistent with Y, though the mechanism is not directly measured here." |

---

## 3. "Drafted in Chinese, then translated" pitfalls

When the full draft is written in Chinese first and then translated (rather than drafted section-by-section in English), watch for these structural problems:

- **Background before object.** The Chinese draft often starts with why the field matters before naming what the paper studies. English readers want the object (the PDE, the benchmark, the model) named early. Move it forward.
- **Method before gap.** Chinese structure often lists what was done, then explains why it matters. English introductions state the gap first, then the method that addresses it.
- **Results and implications mixed.** In Chinese lab-note style, observation and meaning appear in the same sentence. In English, keep observations in Results and interpretation in Discussion.
- **Passive voice as politeness.** Chinese academic writing avoids "we" and overuses passive for modesty. English technical prose can and should use "we" for actions the authors took. "We find / We show / We propose" is preferred over "it was found / it was shown".
- **Long parenthetical chains.** A single Chinese sentence with multiple embedded parenthetical clauses should be broken into two or three English sentences, each with one main claim.

---

## 4. Self-check routine (run before handing off to the polish loop)

This is a quick pass, not a rewrite. If any item fails, fix it before polishing.

1. **Subject-verb agreement.** Read each sentence: does the grammatical subject match the verb number?
2. **Articles.** Every singular count noun: is it preceded by a determiner?
3. **Connective pairs.** Search for "although ... but", "because ... so", "though ... but". Remove the redundant half.
4. **Scope claims.** Search for "first", "innovative", "significantly better". Is each paired with a specific comparator or bounded scope?
5. **Mechanism vs. correlation.** For each causal claim ("X because Y", "the reason is"), confirm that the mechanism is directly measured. If not, downgrade to "consistent with" or "suggests".
6. **Nominalization.** For each "-tion / -ment / -ance" noun, ask: is there a verb that does the same job more directly?
7. **We vs. passive.** For each passive verb, consider whether "we [verb]" is more direct and equally accurate.
