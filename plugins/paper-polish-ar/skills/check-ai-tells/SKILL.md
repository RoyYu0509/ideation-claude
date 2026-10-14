---
name: check-ai-tells
description: Hunt for "obviously-AI" surface signals — banned vocabulary, em-dashes, hedging/abstraction/corporate filler, hype/empty-novelty words, AND structural template leakage (every paragraph opening the same way, formulaic "However,"/"First, Second, Third" signposting, tricolon overuse, interchangeable-sounding abstracts, a grand significance closer on every paragraph). Use when reviewing prose for machine-assembled signals. Loads house-style banned-vocabulary.md and ai-tells.md. Flag aggressively. Diagnose only.
user-invocable: false
---

# check-ai-tells — surface and template signals

You scan the revised text for anything that makes it read as AI-generated. Load the
`house-style` skill (`references/banned-vocabulary.md` and `references/ai-tells.md`) and apply it.

## Two layers

1. **Lexical tells** — banned words, em-dashes, hedging/abstraction filler, the defensive /
   corporate / safety register (the originating complaint: `audit`, `diagnostic`, `budget` and
   the whole *class* of procedural-safety filler), hype / empty-novelty words. Grep the banned
   list, and also use judgment for near-variants the list does not enumerate yet — say so when
   you flag one, so it can be added.
2. **Structural / template tells** — the subtle, high-priority one. Flag when the section's
   underlying template has become *visible*: every paragraph opening with the same syntactic
   frame, every gap introduced with "However,", interchangeable-sounding abstracts, mechanical
   "First / Second / Third" signposting where prose transitions would read better, rule-of-three
   lists everywhere, uniform paragraph length, a grand significance sentence closing every
   paragraph. The funnel / seven-sentence logic should be present as latent structure but
   invisible at the surface — your job is to catch when the seams show.

## Thresholds

- **Banned-vocabulary hits and em-dashes: zero tolerance.** Any survivor fails the section.
- **Context-dependent words** the banned list marks "(when …)" — `significant` (statistical
  sense OK), `robust` (defined technical sense OK), `framework` (the paper's actual named
  framework OK), plus the **venue-acceptable set declared in the selected venue profile's
  `## vocabulary`** (named in your goal's TARGET VENUE preamble — that profile section is the
  SSOT for which words the venue tolerates; do NOT rely on any list restated here): judge in
  context, do not flag a legitimate technical use; flag only the vague / over-used / non-technical
  case. With no venue (the `default` profile), use the strict global reading.
- **Template / rhythm tells:** flag every instance. The section fails if a *systematic* tell is
  present (most paragraphs share an opener, every gap uses "However,", the abstract sounds
  interchangeable, a grand closer on most paragraphs) — tag that severity `ai_tells_systematic`.
  One isolated minor tell is severity `minor_tell` (a `partial`, not a fail).
- **A lone isolated tell does not force a rewrite.** Human prose contains the occasional "However,"
  and the occasional parallel pair. When a single `minor_tell` is acceptable to leave — when removing
  it would be a pure *displacement* (a synonym swap or in-place reorder that fixes nothing) rather than
  a real improvement — mark it `disposition: deferred` with a one-line `defer_reason`, not `actionable`.
  Reserve `actionable` for a tell that is **systematic** or that you can remove **without churn**.
  A `However,` ↔ `, however,` shuffle is never a fix; do not demand one to drive the flag count to zero.

## Conflict priority

Where removing a tell would hurt readability (real human prose uses some parallelism and
repetition), **say so and defer to `check-readability`** — do not force a change that flattens
the voice. **When readability and ai-tells conflict, readability wins** (the house rule).

The shared boundary case is **repeated paragraph openings**: *ai-tells* owns it as **template
visibility** — when most paragraphs open with the identical syntactic frame, the template is showing
and that is a machine signal. *check-readability* owns the **rhythm** side — whether the openings vary
enough to read well. Flag the template-visibility case here, but if breaking the repetition would
flatten genuinely fluent prose, defer to readability.

## Output

A list of flagged instances: quote | tell type (lexical / template) | suggested direction, with a
verdict. Name any word not yet in `banned-vocabulary.md` so it can be added. Set
`dimensions_covered: [ai-tells]` (or include `ai-tells` if bundled). Diagnose only.
