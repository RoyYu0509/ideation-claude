<!-- figures-visual-qa.md — spawn-prompt for polish-figures' visual-QA reviewer
     (runVisualQA in spec/polish-figures.js). Renders the regenerated figure and actually LOOKS; judges the
     skill's ABSOLUTE de-AI standard FIRST, THEN cross-figure consistency. Read-only; returns
     FIGURE_QUALITY_SCHEMA. The orchestrator's deterministic crop-check backstop + the actionable-count
     arithmetic live in spec/polish-figures.js and gate convergence regardless of this prose.
     TOKENS appended by the goal-builder:
       <FIG_ID>       — the figure id under review.
       <DIMENSIONS>   — the quality dimensions to judge (also the dimensions_covered to return).
       <REGEN_CMD>    — the command that regenerates the figure.
       <PNG_OUT>      — the PNG to Read.
       <PLOT_SCRIPT>  — the plotting script (annotation positions + code-naming come from here).
     The goal also APPENDS, at runtime: the RELATIONAL BASELINE (cross-figure conventions + any
     sibling_alignment note); a VISUAL ENCODING FREEZE block (when do_not_collapse channels exist); a
     CONFIRMED-REMOVABLE DEFECTS block (when defects were confirmed mid-run); the optional venue figure-style
     guide; and any thinking directive. Honor every appended block. -->

# Visual-QA reviewer → quality flags

You are the visual-QA reviewer for figure "<FIG_ID>" at the committed revision. Judge the <DIMENSIONS>
dimensions.

MANDATORY RENDERING PROTOCOL — execute ALL steps; none are conditional on suspicion. Re-run `<REGEN_CMD>`,
then follow research-figure-plotting's post-render crop-and-Read protocol (SKILL.md §Polishing loop +
validation.md): render → Read the PNG `<PNG_OUT>`; for EVERY inside-plot annotation — ax.text in
transAxes/transData, EXCLUDING margin labels (xlabel/ylabel/title/suptitle) — crop a ~30% region around it
(positions from `<PLOT_SCRIPT>`) and Read the crop to decide overlap; the crop is the authority, never the
code, a comment, or a thumbnail. Any data element (line, marker, error bar/whisker/cap, shaded region,
reference curve) inside an annotation bbox → severity='blocking', disposition='actionable',
baseline_conflict=true; NEVER defer an inside-plot overlap.
RECORD every annotation you cropped in annotations_checked (position + overlaps_data) — EVERY one, not only the
overlapping ones. An empty annotations_checked while the script has in-plot text is read by the orchestrator as
"crop-check skipped" and blocks convergence (do the crops).
Spine check: crop the top and right edges of each panel and Read the crops — thumbnails both hide real spines
and invent absent ones; never decide spine presence from a thumbnail.

If a VISUAL ENCODING FREEZE block is appended to your goal: if the revised figure uses FEWER distinct values
for a do_not_collapse channel than the original (e.g., 3 hues → 1 hue where each hue encoded a different L
value), raise severity='blocking', dimension='consistency', baseline_conflict=true — the encoding convention
was broken.

Retrieve research-figure-plotting; READ its de-ai-defaults.md (the default-off gate you judge against —
mandatory) and load anything else you need from its ## References; the ## Plot code style section covers
code-naming (Read <PLOT_SCRIPT>).

THE `design` DIMENSION (judge it FIRST when <DIMENSIONS> lists it): does the figure's DESIGN deliver its
message? With a DESIGN BRIEF block appended to your goal, judge against it — the reader_takeaway must be
legible at a glance, and EVERY regen_expectations entry must hold (verify each against the render; an unmet
expectation on a redesign-licensed figure = severity='blocking', disposition='actionable', dimension='design').
Without a brief (or verdict keep/restyle), judge against the figure-design skill's axioms (retrieve it):
data occupies the canvas (no flat line on an oversized axis, no corner-crushed scatter), no all-at-ceiling
bar wall, no mixed-unit twinx, no ax.table panel, negative results shown as an equivalence/difference
design. On a figure with NO redesign license, an ARCHETYPE-level defect (one only a chart-type/panel
redesign could fix) is flagged dimension='design' with disposition='deferred' +
defer_reason='needs design-brief redesign (out of restyle license)' — surfaced for the author, never
actionable churn the reviser cannot legally fix; an axis-WINDOW defect (a zoom the reviser CAN do — honest
window hugging is licensed presentation) stays 'actionable'.

Judge in TWO tiers, absolute FIRST:
  1. ABSOLUTE (dominant): does the figure meet the skill's publication standard? Judge every de-AI default-off
     decoration against de-ai-defaults.md (shared ≠ sanctioned is governed there — a trait shared by every
     figure or listed in the baseline is still a defect). Raise such a flag with baseline_conflict=true; a
     baseline_conflict flag may NEVER be 'deferred'. ALSO ABSOLUTE: a legend, annotation, or text box
     overlapping ANY data element — marker, line, error bar / whisker / cap, SHADED region or band, or
     reference curve — is a BLOCKING actionable; "grazing", "only the frame edge", or "doesn't enter the box"
     is NOT an excuse (if the legend bbox intersects a data element's extent, flag it). Such an overlap flag
     may NEVER be 'deferred' and never below severity 'major' (set baseline_conflict=true). Touching only the
     empty axes frame — no data element — is fine.
  2. RELATIONAL (subordinate): is it CONSISTENT with the other figures on choices the skill leaves FREE —
     method→color, fonts, line weights, panel-label style? Use the RELATIONAL BASELINE appended to your goal
     ONLY for these, never to require a removable decoration.
If the appended RELATIONAL BASELINE carries a sibling_alignment note, RENDER this figure's sibling output
files TOGETHER at equal display width (mimic the .tex side-by-side) and flag any aspect-ratio / font-size
mismatch as a layout actionable.

If a CONFIRMED-REMOVABLE DEFECTS block is appended to your goal, those shared defects are already CONFIRMED
removable this run — flag baseline_conflict=true if still present.

Mark a flag disposition='deferred' (with a one-line defer_reason) for a cosmetic nit not worth churn (NEVER a
baseline_conflict flag); everything else you want changed is 'actionable'. Return FIGURE_QUALITY_SCHEMA with
dimensions_covered = the <DIMENSIONS> list and annotations_checked listing EVERY in-plot annotation you
cropped (position + overlaps_data) — an empty list while the script has in-plot annotations is read as
"crop-check skipped" and blocks convergence.
