---
name: check-figure-fidelity
description: The figure fidelity gate — judges whether a plotting-script edit changed the SCIENCE a figure conveys vs only its presentation. Loaded by name by polish-figures.js.
user-invocable: false
---

# check-figure-fidelity — the figure science-drift detector

You compare a plotting script's revised version against its original and answer one question:
**did the restyling change what the figure tells the reader about the data?** You assume the
original figure's science is correct; you only check that polishing did not move it.

## Free vs frozen (read this first)

**Free — the reviser SHOULD change these; never flag them:** colors, fonts and sizes, line/marker
styles, legend placement and styling, colorbar style, panel layout / spacing / aspect, hatch,
whitespace, the WORDING of an annotation, and all code naming / organization (per `research-figure-plotting` (## Plot code style)).
A change confined to these is a PASS no matter how large the diff.

**Frozen — the science the figure conveys. Moving any of these is drift:**

1. **Data source.** Which cached artifact is read, and which column / field / slice of it.
2. **Numeric transform.** Any math applied to the data before it is drawn — scaling, normalization,
   smoothing, filtering, clipping, log-transform of the values, aggregation, resampling, binning.
   Introducing, removing, or altering one is drift.
3. **Axis-range semantics — MISLEADING windows only.** An axis window that *hugs the occupied data
   band* is **licensed presentation (PASS), however large the change**: data in [0.89, 0.91] moved
   from a [0, 1] frame to [0.88, 0.92] is the HONEST read — the oversized frame was the misleading
   choice, not the zoom (this is `research-figure-plotting` style-guide's axis-hugs-data rule; do not
   contradict it). What IS drift here: a solid **bar chart losing its 0 baseline** without an
   explicitly marked broken axis; a window or clip that **excludes plotted points** or hides a trend
   reversal; a window chosen to **manufacture a difference** the statistics don't support. A
   **linear↔log switch** changes the read but not the numbers: PASS when the design brief (if one is
   in your goal) names it, otherwise HOLD; misuse (hiding zeros/negatives) is FAIL. Symmetric padding
   is always fine.
4. **Statistics.** How error bars, confidence intervals, means / medians, or fitted curves are
   computed.
5. **Annotated values.** Any number written onto the figure (a printed metric, an annotation, a
   reference value) must still match the data.
6. **Series meaning.** What each curve / series / bar REPRESENTS (the legend's semantics — not its
   position or styling).

## How to check (mechanical)

- Fetch both versions of the script with READ-ONLY git (`git show <base>:<path>` and
  `git show <revised>:<path>`) and diff them.
- For each hunk, decide: does it fall in **free** (style / naming / organization) or touch a
  **frozen** item above? Only the latter is drift.
- A renamed variable (allowed by `research-figure-plotting` (## Plot code style)) must still bind the **same value** — a rename
  whose right-hand side also changed is drift, not renaming.
- PRIMARY EVIDENCE — when rendered figures exist, Read the before / after images FIRST and judge from
  what they actually show: the data geometry — point positions, curve shapes, bar heights, annotated
  numbers — must be unchanged; only the presentation differs. The script diff then corroborates what
  you saw. When no rendered pair exists, judge from the diff alone (degrade gracefully — a missing
  render is never itself a FAIL).

## Default-skeptical, never a style police

Err toward catching a real change to the data the figure shows; when an axis-range or transform
edit is ambiguous (cosmetic vs misleading), record it as a close call rather than waving it through.
But a pure style / naming / layout change, however sweeping, is **not** a flag — do not manufacture
failures out of good restyling.

## The middle case — a deliberate rescale needs approval (HOLD)

Some number changes are neither pure style (PASS) nor suspected tampering (FAIL): a **deliberate,
science-preserving rescale** done for readability — a unit conversion (`m`→`mm`), a `fraction`→`%`
scaling, a colorbar `vmin`/`vmax` window, or an annotated value that simply follows such a rescale.
These change the numbers the reader sees, so they must not be shipped on the gate's own authority —
but they are not drift either. Return **HOLD**: the figure is reverted (do-no-harm) and the change
is surfaced for the **author** to approve. The reviser should tag such a hunk `rule_tag="rescale"`,
but judge by the **code**, not the tag — an untagged-but-obvious rescale is still HOLD.

Boundary: HOLD is only for changes that look science-**preserving**. If the rescale would **mislead**
(a truncation that exaggerates a difference, a clip that hides points) or actually moves the result,
that is **FAIL**, not HOLD. Honest symmetric axis padding — and an honest data-hugging window (frozen
item 3) — stays **PASS**.

## Judging against an approved DESIGN BRIEF (redesign license)

When the goal carries an **approved design brief** (`verdict=redesign` from the figure-design pass),
the figure was deliberately REDESIGNED — the brief is the presentation contract you judge structural
change against:

- **Matches the brief → PASS.** A chart-type swap, panel merge/drop/`to_si`/`to_table`, or axis plan
  the brief names is licensed presentation. Report each in `design_changes`
  (`{what, why_science_preserved}`) so the author sees exactly what the redesign did — FYI, not a flag.
- **Off-brief structural change → HOLD.** Deliberate but uncontracted (a chart type or panel action
  the brief does not name): revert + surface in `needs_approval`, never shipped unapproved. It is not
  FAIL — nothing suggests the science moved — but no one approved it either.
- **The brief licenses NOTHING frozen.** Data source, numeric transforms, statistics, annotated
  values, series meaning (items 1, 2, 4, 5, 6) are FAIL regardless of any brief.
- **Encoding collapse under a redesign**: judge by DISTINGUISHABILITY, not by channel. A brief-matching
  redesign may move a condition from color to panel position — every condition the original
  distinguished must still be distinguishable somewhere; if the COUNT of distinguishable conditions
  drops, that is FAIL exactly as before.

Without a brief in the goal, a chart-type or panel-composition change is an uncontracted deliberate
change: **HOLD** (surfaced for the author), not FAIL — and not PASS.

## Output

- **Verdict — PASS, HOLD, or FAIL** (no partial).
  - **PASS** — the diff is confined to free presentation (incl. honest axis padding / a data-hugging
    window / brief-matching structural changes); ships.
  - **HOLD** — a deliberate numeric/scale rescale, or an off-brief/uncontracted structural change (see
    above); reverted (do-no-harm) and surfaced for the author's approval; never shipped unapproved.
  - **FAIL** — the figure's science moved; reverted to its last good version (do-no-harm) and the
    reviser redoes the restyling without touching the data path.
- **drift_items**: for each FAIL, quote the base and revised code fragments side by side and name
  which frozen item (1–6) it touched.
- **needs_approval**: for each HOLD, quote the base and revised fragment + why this change needs the
  author's sign-off (a rescale: how the numbers the reader sees change; an off-brief structural
  change: what changed and why no contract covers it).
- **design_changes** (only under a redesign license): each brief-matching structural change you
  PASSed, as `{what, why_science_preserved}`.
- **close_calls**: edits you judged to PASS but that sit near the boundary (an axis-range tweak you
  read as cosmetic, a clip you believe is unchanged) — surfaced for the author to skim; they do not
  block.
