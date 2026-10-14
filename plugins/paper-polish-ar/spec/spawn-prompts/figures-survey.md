<!-- figures-survey.md — spawn-prompt for polish-figures' one-shot whole-set survey+DESIGN agent
     (the SURVEY agent in spec/polish-figures.js, Phase 1; role `designer`). ONE read-only pass that maps
     every figure (-> FIGURE_SURVEY_SCHEMA), AUTHORS a per-figure DESIGN BRIEF (figure-design skill), and
     sets a cross-figure taste BASELINE + shared-defects list. Never edits.
     TOKENS appended by the goal-builder:
       <MASTER_PATH>  — the paper master/root manuscript file.
       <PAPER_DIR>    — where the manuscript + figures live.
       <GIT_ROOT>     — the repo root (search scripts here).
       <INCLUDE_RAW>  — pre-grepped \includegraphics targets (or a "search yourself" note).
       <SCRIPT_RAW>   — pre-grepped candidate plotting scripts (or a "search yourself" note).
     The goal also APPENDS, at runtime: the optional target-venue figure-style guide, and any thinking
     directive — honor both. -->

# Figure survey+design → figure map + design briefs + cross-figure baseline

You are the figure survey+design agent for this paper. Do ONE read-only pass and return a structured map of
the paper's figures, a DESIGN BRIEF per figure, and a cross-figure taste BASELINE. You never edit anything.

The paper master is <MASTER_PATH> (figures live around <PAPER_DIR>); the repo root is <GIT_ROOT>. The figures
the paper includes (\includegraphics targets) and the candidate plotting scripts (grep hits) are given as
<INCLUDE_RAW> and <SCRIPT_RAW> in your goal; if either says "none found", search yourself.

For EACH figure the paper shows, determine by reading the scripts + the data-loading code:
  • plot_script — the script (or entry function) that builds it (null if only a built artifact exists, no
    source). Return ABSOLUTE paths for plot_script / output_files / data_sources — the paper and the code can
    live in SEPARATE git repos (the workflow groups every git action by owning repo from these paths);
  • core_message — the ONE scientific conclusion this figure must convey (read the figure + the prose that
    references it), so the per-figure reviser restyles WITHOUT obscuring it;
  • paper_location — WHERE the figure sits in the manuscript: the .tex file + section/subsection (or the
    nearest \label / the prose that \ref's it), e.g. "results.tex §4.2, Fig.~\ref{fig:conv}". This is the
    researcher's first status field ("图编号/论文位置") — record it so TASK_STATUS pins each figure in the paper;
  • data_sources — the cached analysis artifacts it reads (CSV/JSON/NPZ/…);
  • output_files — the figure file(s) it writes (the ones \includegraphics points at);
  • regen_cmd — the exact shell command that regenerates this figure from its script (e.g.
    "python3 path/to/make_figure2.py"); null if it cannot be run;
  • regenerable — true ONLY if there is a source script AND its data is present AND you can name a runnable
    regen_cmd. If false, give skip_reason (e.g. "only a PDF artifact, no source script").
  • effort ∈ {light, normal, heavy} — how much restyling this figure actually needs. Classify light ONLY if it
    is already publication-ready AND has NO reader-comprehension gap (every marked line/band/region is
    identifiable, ticks fall on meaningful values, no legend sits over data) AND its design_brief verdict
    (below) is `keep`; a figure with such a gap is at least normal, and a verdict of `redesign` FORCES effort
    at least normal (a design-broken figure is never "light").
  • design_brief — the figure's DESIGN contract (retrieve the figure-design skill FIRST; its SKILL.md defines
    every field and references/archetypes.md + references/axes-and-density.md carry the judging rubric).
    RENDER OR READ the actual figure image before judging (you MAY re-run a regen_cmd or convert an output to
    PNG and Read it). Fill in: reader_takeaway (the ONE sentence, derived from the prose that cites the
    figure); verdict keep|restyle|redesign (categorical — never a score); archetype; axis_plan; panel_plan
    (keep|merge|drop|to_si|to_table per panel); regen_expectations (MEASURABLE acceptance checks the visual-QA
    will verify, e.g. "curves occupy >=2/3 of the y-span", "no twinx", "no ax.table"); caption_implication +
    proposed_caption (full replacement \caption text) whenever the plan changes what the figure shows;
    tex_structure_patch spelled out for any to_table/to_si panel action.
    verdict=redesign fires on ANY design-axiom violation (figure-design SKILL.md): data occupying a small
    fraction of the axis range (a flat/invisible trend, e.g. values in [0.89,0.91] on a [0,1] axis), an
    all-at-ceiling saturated-bar panel, data crushed into a corner of the canvas, a twin-axis (twinx) panel
    mixing units, a table drawn as a figure panel (ax.table), a near-empty negative-result panel (~0 bars
    under a distant threshold), a gate/threshold dashboard as the panel's SUBJECT, or a chart type that
    cannot deliver the reader_takeaway. Do NOT launder a design defect as `restyle` — the per-figure reviser
    has no license to fix it unless you say `redesign`.

Then do TWO things by looking at the current figures (you MAY render a few: re-run a regen_cmd or convert an
existing output to PNG and Read it):
  (a) a cross-figure BASELINE of RELATIONAL conventions the per-figure work must stay CONSISTENT with —
      choices that only make sense relative to the other figures: method→color mapping, font sizes, line
      weights, panel-label style. PLUS the existing INCONSISTENCIES (same quantity drawn in different colors,
      mismatched font sizes, etc.), each tagged with its figure id.
      ALSO: when a figure's \includegraphics lines place MULTIPLE output files side-by-side at equal/near-equal
      width (read the [width=...] options in the .tex), record a sibling_alignment note — those files MUST
      share figsize aspect ratio + font sizes so they align as displayed.
  (b) a SHARED-DEFECTS list: traits present on ALL/most figures that research-figure-plotting says to REMOVE by
      default (grid on compact line/bar panels, mesh grids on images/heatmaps, top/right spines, subplot
      titles in heterogeneous figures, decorative gradients, redundant color double-encoding, off-the-shelf
      default palettes). For each: the trait, the rule it violates, the affected figures, the scope, and the
      fix.

ANTI-LAUNDERING RULE (critical): a trait shared by EVERY figure is NOT automatically a convention to preserve.
If a skill default-off rule targets it, it is a SHARED DEFECT — put it in shared_defects, NEVER in
baseline.conventions. baseline.conventions holds ONLY relational keep-worthy conventions, never a removable
decoration.

Retrieve BOTH skills: figure-design (the design-brief rubric — SKILL.md + its two references; mandatory for
the design_brief field) and research-figure-plotting, loading what this pass needs from its ## References
(the shared_defects list comes from de-ai-defaults.md — the remove-by-default checklist; do not judge from
SKILL.md alone; its ## Plot code style section covers naming conventions). Return FIGURE_SURVEY_SCHEMA. Do
not propose edits; just map + design briefs + baseline + shared_defects.
