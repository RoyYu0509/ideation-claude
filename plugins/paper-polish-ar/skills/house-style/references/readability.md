# Readability (the core goal)

The manuscript's stated goal is prose that **reads like a careful human expert wrote it, not
assembled it**, and is fluent. This file is the checkable rulebook the reviser writes toward and
`check-readability` judges against. It is cross-section, so it lives in the shared `house-style` skill.

Each rule has a **fail-signal** (an observable thing that means the rule is violated) and slots for
`[ex:]` anchors (a `fail` example of the problem and a `success` example of the fix). Anchors are
the robustness mechanism — when a rule fires, the agent should be able to see a concrete instance.
The target voice is set by `house-voice.md` plus the worked examples under the SELECTED venue's
anchors (`examples/venue-anchors/<venue>/<field>/`, named in your goal's TARGET VENUE preamble):
`overall.md` for the register, and one `<section>.md` per section. Read like their "after" passages,
not like generic "good academic English". (The `read-*` ids below are placeholder seeds; fill them
with real before/after pairs over time.)

---

## 1. Sentence rhythm
Vary sentence length and shape. A run of sentences with the same length and the same subject–verb
opening is the single strongest "machine-assembled" signal.
- **Fail-signal:** 4+ consecutive sentences within ~5 words of the same length; or 3+ consecutive
  sentences opening with the same structure (e.g. "We … We … We …", "This … This …").
- **Fix direction:** break one long sentence, fuse two short ones, front a subordinate clause, let a
  short declarative land after a long one. `[ex: read-rhythm-fail-01]` `[ex: read-rhythm-fix-01]`

## 2. Cohesion / through-line
Each sentence should connect to the previous one; each paragraph should have one through-line.
Transitions should be *earned* by the logic, not bolted on with a connector.
- **Fail-signal:** a paragraph whose sentences could be reordered without loss (no through-line);
  transitions carried only by "Moreover/Furthermore/Additionally/In addition" stacked at sentence
  starts; a new paragraph that does not pick up the thread of the last.
- **Fix direction:** use given→new information flow (end a sentence on the idea the next one opens
  on); cut the connector and let the sentences abut if the logic is already clear.
  `[ex: read-cohesion-fail-01]` `[ex: read-cohesion-fix-01]`

## 3. Clunk / nominalization
Unbury verbs; unstack prepositional phrases and abstract-noun chains.
- **Fail-signal:** "performs the optimization of" (→ "optimizes"); "the application of X to Y for
  the purpose of Z"; 3+ "of" in one clause; a sentence whose main verb is "is/are + nominalization".
- **Fail-signal (subject–verb stall):** a comma- or dash-delimited appositive of >8 words wedged
  between a clause's subject and its main verb, *especially* when a second interrupter ("to our
  knowledge", "in general") also splits the verb phrase — the reader must re-hold the open frame and
  re-read to find the spine. `[ex: read-clunk-fail-02]`
- **Fix direction:** turn the nominalization back into a verb, name the agent, split the chain; when
  an appositive splits subject from verb, lift it into its own short sentence.
  `[ex: read-clunk-fail-01]` `[ex: read-clunk-fix-01]`

## 4. Ease of reading
A scientist outside the subfield should be able to follow the opening of each section; the prose
should move, not stall.
- **Fail-signal:** the first sentence of a section needs in-field jargon to parse; a sentence that
  has to be re-read to find its subject; three undefined acronyms before the first finding.
- **Fix direction:** lead with the concrete claim; define on first use; put the agent and action up
  front. `[ex: read-ease-fail-01]` `[ex: read-ease-fix-01]`

## 5. Over-correction (tells introduced *while* de-AI-ing)
De-AI-ing can itself flatten the voice or add new mechanical patterns. Catch this.
- **Fail-signal:** every paragraph now the same length; the voice homogenized to one generic
  register across sections; a banned word swapped for another banned word; clunky human-sounding
  hedges added that were not there.
- **Fix direction:** restore deliberate variation; let sections keep their natural register; prefer
  the version a careful human editor would write over the one that most cleanly satisfies a rule.
  `[ex: read-overcorr-fail-01]` `[ex: read-overcorr-fix-01]`

---

## The "reads-like" verdict
`check-readability` ends with one of: **human-expert** (passes) / **competent-but-flat** (fails) /
**machine-assembled** (fails). A single rough sentence is `partial`; a *recurring* problem (the same
fail-signal across paragraphs) fails the section. Readability outranks ai-tells on conflict: keep
human parallelism and repetition that genuinely aid flow.

---

[FILL IN: add lines as real runs reveal flow problems specific to your writing, each with a `[ex:]`
pair harvested from the run. Tune the fail-signal thresholds (e.g. the "4+ consecutive" counts) to
your taste once you have seen a few outputs.]
