---
name: house-style
description: The manuscript's shared house style — banned vocabulary, AI-tells catalogue, target voice (SSOT under references/). Loaded by name by polish-prose, check-ai-tells, and the section revisers.
user-invocable: false
---

# House style

The shared rules every section depends on. Three reference files plus a growing examples folder.

- `references/banned-vocabulary.md` — words and punctuation that read as obviously-AI. Grep target.
- `references/ai-tells.md` — structural / rhythmic patterns that read as machine-assembled.
- `references/readability.md` — the core-goal rulebook (fluency / rhythm / cohesion), with a
  fail-signal per rule. `check-readability` and the reviser both load it.
- `references/house-voice.md` — what the prose should sound like instead.
- `references/phrasebank.md` — the positive replacement bank (what to write instead); complements banned-vocabulary.
- `references/zh-author-workflow.md` — guidance for a Chinese-native author writing in English.
- `references/latex-layout.md` — ADVISORY float/figure-placement notes (out of the prose-freeze loop).
- `examples/venue-anchors/<Venue>/<field>/` — per-venue resources, selected at runtime from
  `config.target_venue` and named in each goal's TARGET VENUE preamble:
  - `profile.md` — the machine-read contract (register, venue-acceptable vocabulary, conventions,
    acceptance bar) that `/polish` and `/review` load. `default/` is the `target_venue: null`
    fallback; `_TEMPLATE/` is the scaffold for adding a venue.
  - `overall.md` + per-section `abstract.md` / `introduction.md` / `results.md` / `methods.md` /
    `discussion.md` — the register narrative + roster, and one or more papers' **before→after** pairs
    per section (loaded as few-shots when a section is hard).
  - `review/` — the per-venue review kit (`rubric.md` + `reviewer-profiles.md` + `scoring.md`) the
    `/review` adversarial panel consumes.
  This release ships no filled few-shot examples; copy `venue-anchors/_TEMPLATE/` to add your own.
- `examples/before-after/` — `TEMPLATE.md` for any ad-hoc standalone before→after pair you add later.

## Examples as inline rule anchors (`[ex:]`) — the robustness mechanism

Important fail/success instructions in the references and rubrics carry an inline anchor:
`[ex: <stable-id>]`. The id resolves to an example file/entry under `examples/`. For venue anchors a
`[ex: <paper>-<section>]` id (e.g. `<paper>-abstract`) resolves to the `<paper>` entry inside
`venue-anchors/<Venue>/<field>/<section>.md`; when you follow it, **also scan the sibling entries in
the same file** — they are other papers' worked examples for the same section, and the point is to see
the shared pattern. When a rule fires, the agent should be able to follow the anchor to a concrete
instance, so behavior is anchored to examples rather than to abstract instructions alone. Examples are
**not** a runtime gate and **not** the convergence judge — they make the *rules* concrete. Each
anchored example is typed `fail` / `success` / `anchor`. Seed ids exist before their files do; fill the
files in over time.

**Never use the paper currently being polished or reviewed as an example anchor.** Anchors are *other*
papers' worked before→after pairs; pointing a rule at the very manuscript under work leaks the
"answer" into the judge (a test-set leak) and collapses the rule into "make it look like this one
paper". If a needed pattern has no anchor yet, name the rule and leave the `[ex:]` id unfilled.

## The core tension to hold (read this)

The section rubrics prescribe structure (funnel logic, seven-sentence skeletons, evidence chains).
Followed literally, that structure produces exactly the mechanical feel that reads as AI. So: the
structure must be **present as latent logic** and **invisible at the surface**. Use the funnel; do
not let the seams show. When in doubt, prefer the version a careful human editor would have written
over the version that most cleanly fills the template.
