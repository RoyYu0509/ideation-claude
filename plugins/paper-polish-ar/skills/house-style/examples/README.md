# Examples — the calibration set

The examples calibrate the whole system: they give the reviser and evaluators concrete `[ex:]`
few-shots to imitate when a section is hard.

## What's here

- `venue-anchors/<Venue>/<field>/` — **worked examples by venue, one file per section.** Each
  venue/field folder has `overall.md` (register + how-to-read + paper roster) plus `abstract.md`,
  `introduction.md`, `results.md`, `methods.md`, `discussion.md`, each holding one or more papers'
  **before→after pair** (weak draft → polished) for that section. No filled example ships in this release; copy `venue-anchors/_TEMPLATE/` to add your own.
- `before-after/TEMPLATE.md` — format for any standalone before→after pair you add later.

## How to grow it

Add more worked examples (other papers) by **appending a `## <paper>` entry to the matching
`<section>.md`** (and a row to the roster in `overall.md`); add new venues/fields as sibling folders.
Replace any constructed "before" with a real weak draft when you have one. These examples are how you
tell whether editing a rule improved or regressed the output, and keeping each section's examples in
one file lets the reviser see several papers' patterns side by side.

[FILL IN: add more worked examples as you go. Follow the `_TEMPLATE` section-file format.]
