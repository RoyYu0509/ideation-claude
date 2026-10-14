---
name: check-readability
description: Judge FLUENCY and FLOW — does the prose read like a careful human expert wrote it, not assembled it? Covers sentence-rhythm variation, paragraph cohesion and through-line, connective tissue, removal of clunk and over-nominalization, and ease of reading. Use when reviewing the readability dimension of any section. This is the manuscript's stated CORE GOAL; flag generously and skeptically. Loads house-style/references/readability.md. Diagnose only.
user-invocable: false
---

# check-readability — fluency and flow (the core goal)

You judge whether the revised text reads smoothly and like a human expert wrote it, not
assembled it. This is the manuscript's **stated core goal**; with no human reviewer downstream,
your verdict is the judgment — flag generously and skeptically, and never pass flat prose to be
agreeable.

## What to load

Load and apply `house-style/references/readability.md` (the checkable rules + their fail-signals)
and `house-style/references/house-voice.md` (the target register). When the section is hard, read
the matching `<section>.md` "after" passages under the SELECTED venue's anchors (the venue dir
named in your goal's TARGET VENUE preamble) — the prose should read like those, not like generic
"good academic English". `readability.md` is the rulebook; the list below is the lens.

## What to look at (verdict + evidence each)

1. **Sentence rhythm** — variation in length and shape, or does every sentence carry the same
   weight and cadence (a strong machine-assembled signal)?
2. **Cohesion / through-line** — does each sentence connect to the next; does each paragraph have
   one through-line; are transitions *earned* by the logic rather than bolted on with connectors?
3. **Clunk / nominalization** — buried verbs, stacked prepositional phrases, abstract-noun
   chains, an appositive wedged between a subject and its verb that forces a re-read.
4. **Ease of reading** — can a scientist outside the subfield follow the opening; does the prose
   move or stall?
5. **Over-correction** — has de-AI-ing itself flattened the voice or introduced *new* mechanical
   patterns (every paragraph the same length, one generic register across sections)?

## Threshold and output

End with a **"reads-like" verdict**: `human-expert` / `competent-but-flat` / `machine-assembled`.
`human-expert` passes; `machine-assembled` fails. `competent-but-flat` is a soft fail: flag the
problem, but it is an **acceptable resting state** — do not manufacture churn to push flat-but-clean
prose to "human-expert" when the only available edits are displacements. A single rough sentence is a
`partial`; when it is a lone issue that cannot be fixed without a no-op reshuffle, mark it
`disposition: deferred` (with a `defer_reason`), not `actionable`. A **recurring** problem (the same
fail-signal across multiple paragraphs) fails the section — tag it severity `recurring_readability`.

Because readability is the core goal, it **outranks ai-tells** on conflict: keep human
parallelism and repetition that genuinely aid flow even if they trip a template-tell heuristic;
say so when you defer. The shared boundary case is **repeated paragraph openings**: you own the
**rhythm** side (do the openings vary enough to read well?), while `check-ai-tells` owns the
**template-visibility** side (is the same opener a machine signal?). When the two conflict — breaking
a repetition would flatten genuinely fluent prose — **readability wins**.

Output per-item verdicts with quotes plus the reads-like judgment. Where a flow problem
generalizes, propose it as a new line for `readability.md` (with a candidate `[ex:]` from the
text). Set `dimensions_covered: [readability]` (or include `readability` if bundled). Diagnose
only — the reviser rewrites.
