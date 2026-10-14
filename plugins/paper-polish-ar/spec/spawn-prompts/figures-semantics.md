<!-- figures-semantics.md — spawn-prompt for polish-figures' read-only figure-semantics extractor
     (runFigureSemantics in spec/polish-figures.js). A read-only pass that builds the VISUAL FREEZE
     MANIFEST: what each visual encoding MEANS, so the reviser knows what cannot be collapsed/relocated and
     the fidelity gate can catch encoding collapses (e.g. 3-color cross-panel L indexing → 1 color).
     TOKENS appended by the goal-builder:
       <FIG_ID>       — the figure id being mapped.
       <PNG_OUT>      — the figure's PNG output (the ground-truth image to Read first).
       <REGEN_CMD>    — the exact command that regenerates the figure (only if the PNG is missing).
       <PAPER_DIR>    — where the manuscript lives (caption + prose searches run here).
       <CAPTION_CTX>  — pre-grepped \caption{...} context for this figure. -->

# Figure-semantics extractor → visual freeze manifest

You are the figure-semantics extractor for figure "<FIG_ID>". One read-only pass; return a structured map of
every visual encoding that carries scientific meaning in the ORIGINAL figure. This map is the visual freeze
manifest used by the reviser (what must not be changed) and the fidelity gate (encoding-collapse check). Do
not edit anything.

STEP 1 — Read the original figure image FIRST (this is mandatory):
The original PNG is <PNG_OUT>. Read it with the Read tool now. This is the ground truth for what encodings are
present. If the PNG does not exist yet, re-run <REGEN_CMD> to produce it, then Read it.

STEP 2 — Read the LaTeX caption for this figure:
Caption context from grep is given as <CAPTION_CTX> in your goal. Search <PAPER_DIR> for the full
\caption{...} block that belongs to this figure if that snippet is incomplete
(`grep -r -n 'caption' "<PAPER_DIR>" --include='*.tex'`).

STEP 3 — Find the prose paragraph(s) that reference this figure:
`grep -r -n 'Figure.*<FIG_ID>\|\\ref{fig:' "<PAPER_DIR>" --include='*.tex' | head -20`
Read those paragraphs — they tell you what the figure MUST convey to the reader.

From the rendered image + caption + prose, fill in the schema:

VISUAL ENCODINGS — for each channel (color, linestyle, marker_shape, position):
  - What does this channel encode? Method identity? Experimental parameter (L, N, ε, depth)?
  - List each distinct value and what it represents, e.g.:
      "#1f77b4 solid line = L=1 Overlap method"
      "#2ca02c solid line = L=3 Overlap method"
      "#d62728 solid line = L=5 Overlap method"
  - CRITICAL do_not_collapse rule: if N distinct values of a channel each encode a DIFFERENT experimental
    condition (not just "method A vs method B" but also "L=1 vs L=3 vs L=5"), set do_not_collapse=true. This
    fires when color is also indexing the experimental parameter on top of method identity — collapsing to
    fewer values would destroy cross-panel readability. It does NOT fire for genuinely redundant
    double-encoding (same thing encoded twice).

ANNOTATIONS — for EACH text element visible in the figure:
  - placement_type: above_axes (ax.set_title), figure_title (fig.suptitle / fig.text at top),
    inside_plot_area (ax.text with transAxes/transData), or axis_label (xlabel/ylabel).
  - If placement_type is above_axes or figure_title, set move_inside_requires_clear_space=true: a reviser who
    relocates this text INSIDE the plot area MUST render the figure and confirm the bounding box does not
    overlap any data element — no exceptions.

STRUCTURAL CHOICES — layout decisions that encode scientific structure:
  E.g., "3 panels, one per L∈{1,3,5}, lets the reader compare L-dependence directly" → do_not_change=true.
  E.g., "left panel carries the y-label, others share the scale" → do_not_change=false (style).
  PRECEDENCE NOTE (you extract; the caller enforces): under an APPROVED design brief with verdict=redesign,
  the brief outranks do_not_change for STRUCTURE (the old structure is exactly what is being redesigned) —
  but encoding MEANING stays binding in its new form: every condition the original distinguished must remain
  distinguishable, and do_not_collapse dimensions may never shrink. Extract faithfully either way; do not
  soften an entry because a redesign is planned.

Return FIGURE_SEMANTICS_SCHEMA. Document only what the original actually shows — no edits.
