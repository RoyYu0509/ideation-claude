---
name: flowchart-diagram
description: Author ONE publication-grade workflow / method / architecture flowchart for a manuscript — the diagram a reviewer scans first to grasp "what was done, in what order, with what inputs and outputs". Use when adding or sharpening a paper's pipeline/method/system flowchart (the auto-research 流程图 finishing pass, or any request to "draw the workflow", "make a method diagram", "pipeline figure"). Vector-only (TikZ native or SVG→PDF), legibility-first, with a built-in visual QA checklist. NOT for data plots (use research-figure-plotting) and NOT for whole-codebase architecture maps (use architecture-diagram-excalidraw). Diagnose + produce.
user-invocable: false
---

# flowchart-diagram — publication-grade workflow/method flowcharts

A great paper flowchart is **read in five seconds and trusted**. It is not decoration: it is the reader's map
of the method. One figure, one process, no clutter.

## When this is the right tool
- The paper describes a PROCESS — a pipeline, method, algorithm, training/eval loop, data flow, or system — in
  prose or pseudocode, and the reader would understand it faster as a diagram.
- You are adding/sharpening exactly ONE such figure. NOT a data chart (→ `research-figure-plotting`), NOT a
  sprawling codebase/component map (→ `architecture-diagram-excalidraw`).

## The grammar (a reviewer should never have to decode your conventions)
1. **One shape per role, used consistently.** Pick a tiny vocabulary and never break it. Typical:
   rounded-rectangle = process/step; rectangle = artifact/data; parallelogram = input/output; diamond =
   decision; cylinder = store/dataset. ≤ 4 shape types in one figure.
2. **One flow direction.** Left→right OR top→down, never both. The "happy path" is a straight spine; branches
   peel off it. Avoid crossing edges — reroute or reorder nodes instead.
3. **Minimal text.** ≤ ~7 words per node; verbs for steps ("Train surrogate", "Filter by KKT"), nouns for
   artifacts ("Labelled set"). No sentences inside a node. Put detail in the caption, not the boxes.
4. **Edges carry meaning.** Label an edge only when the *what-flows* isn't obvious (e.g. "gradients",
   "top-k", "seeds"). Use one arrowhead style for control flow; a distinct style (dashed) only if you have a
   second, genuinely different relation (e.g. feedback). Define any second style in the caption.
5. **Hierarchy by grouping, not rainbow.** Use at most 2–3 muted fills to group phases (e.g. "data", "model",
   "evaluation"); never one colour per box. Colours must survive greyscale printing — pair colour with
   position/label so the figure reads in B&W.
6. **Alignment + whitespace.** Snap nodes to a grid; equal spacing; consistent box widths within a row. Sloppy
   alignment reads as sloppy science.

## Output: vector, LaTeX-native preferred
- **TikZ** is the default — author `figures/flowchart.tex`, `\input` it inside a `figure` environment in the
  manuscript. It is vector, diffable, and compiles with the paper. Use `\usetikzlibrary{positioning,arrows.meta,
  shapes.geometric,fit,backgrounds}`; position with `right=of`/`below=of` (relative, not absolute coordinates,
  so the layout survives edits); define node styles ONCE in a `tikzset`.
- If TikZ is impractical for the layout, author an **SVG** and export `figures/flowchart.pdf`
  (`\includegraphics`); keep the SVG source in the repo. NEVER embed a raster screenshot or a bitmap exported at
  screen DPI — it will look amateur in print.
- Match the manuscript's font where feasible (TikZ inherits it for free; for SVG use a serif/sans matching the
  body) and a text size that is legible at the figure's printed width (≈ caption size, not smaller).

## Caption + reference (required)
- ONE caption sentence stating what the figure shows ("Overview of the <method> pipeline: …"). Expand any
  non-obvious shape/edge convention in a second short sentence if used.
- `\label{fig:flowchart}` and exactly ONE `\ref`/`\autoref` at the point in the text where the process is first
  introduced (usually early in Methods). A figure with no in-text reference is a defect.

## Visual QA checklist (run before committing — be your own harshest reviewer)
- [ ] Compiles; the figure renders at the column/page width without overflow or tiny text.
- [ ] One flow direction; no avoidable crossing edges; nodes grid-aligned with even spacing.
- [ ] ≤ 4 shape types, each used for one role consistently; ≤ 3 muted group fills; legible in greyscale.
- [ ] Every node ≤ ~7 words; every edge either self-evident or labelled; every second-relation style defined.
- [ ] Caption states what it shows; exactly one `\ref` exists; `\label` is unique.
- [ ] The diagram matches the prose method EXACTLY — same steps, same order, no invented or dropped stage
      (the flowchart must not contradict or over-claim beyond the frozen text).

## Anti-patterns (reject on sight)
Boxes-of-paragraphs; a different colour per node; arrows crossing like spaghetti; absolute-coordinate TikZ that
breaks on the next edit; a raster screenshot; a "flowchart" that is really a data plot or an org chart; a
diagram that adds a step the paper never describes (a freeze violation, not just an aesthetic one).
