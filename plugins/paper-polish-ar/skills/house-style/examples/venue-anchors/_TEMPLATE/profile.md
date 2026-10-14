<!-- Venue profile TEMPLATE. To add a venue: copy this whole _TEMPLATE/ folder to
     venue-anchors/<Venue>/<field>/ and fill every [FILL IN]. The profile is resolved at runtime from
     config.target_venue and threaded into every reviser / reviewer / AC goal. Keep it self-contained:
     this file is the machine-read contract; overall.md is the human narrative + roster. Keep all seven
     blocks; leave a block's body empty only if it genuinely does not apply. -->
# Venue profile — [FILL IN: Venue] / [FILL IN: field]

## identity
- venue: [FILL IN: full journal / conference name]
- field: [FILL IN: subfield this folder targets]
- type: [FILL IN: e.g. broad-audience flagship | specialist methods journal | CS conference]
- audience: [FILL IN: who must understand paragraph 1 — any scientist | the specialist subfield]

## register
[FILL IN: 2-4 sentences. The target voice. e.g. technical-first vs broad-audience; equation density;
how mechanism is stated; hype tolerance. This is what the reviser writes toward and check-readability
judges against.]

## vocabulary
### venue-acceptable in moderation
[FILL IN: words the global banned-vocabulary.md flags that ARE normal here, each with its condition.
This OVERRIDES the global list for this venue. Leave empty to inherit the strict global reading.]
- [word] — [when it is OK; when it still gets flagged]

### venue-stricter
[FILL IN: words this venue treats MORE strictly than the global list. Optional.]

## conventions
- spelling: [FILL IN: American | British]
- abstract: [FILL IN: unstructured funnel | structured headings | Nature summary paragraph]; [word limit if any]
- title: [FILL IN: declarative finding-title | descriptive method+problem | ...]
- references: [FILL IN: numbered superscript | numbered bracket | author-year]
- sections: [FILL IN: ordering / placement norms, e.g. Methods at end (Nature) | Methods inline early (JCP)]
- math/display: [FILL IN: equation density, define-before-use, etc.]
- figures: [FILL IN: what figures reviewers expect; multi-panel norms]

## acceptance-bar
The detailed form for the /review panel lives in review/. Summarize here so the keynote effort prior
and a quick read have the bar inline.
- reviewers reward: [FILL IN: what earns acceptance at this venue]
- reject triggers: [FILL IN: what gets a paper rejected here]
- novelty / significance bar: [FILL IN: how high, and measured against what]
- panel kit: review/rubric.md + review/reviewer-profiles.md + review/scoring.md

## limits
- [FILL IN: word / page limits, figure count caps, abstract length — anything format-enforced]

## anchors
- register narrative + paper roster: overall.md
- before→after few-shots: abstract.md, introduction.md, results.md, methods.md, discussion.md
- example paper(s): [FILL IN]
