# LaTeX float / figure / table placement (advisory typesetting notes)

ADVISORY, OUT OF THE PROSE-FREEZE LOOP. This file concerns typesetting, not prose. The polish loop must not auto-apply these notes; treat them as science_advisory items, surfaced to the author for manual action. No polish hunk should reference this file.

---

## Scope

These notes address layout problems that appear after compilation: loose float pages, stranded section headings, figures that fail to fill a portrait page, and `Float too large` errors. They are not prose issues and are not in scope for the reviser or any check-* evaluator.

---

## General principle

**Compile, render to image, look, iterate.** Do not judge layout from the `.tex` source alone. Render the PDF to images (e.g., at 90 dpi) and inspect every page before and after each change. A contact sheet of all pages at once makes whitespace, stranded headings, and split floats easy to spot.

---

## Loose float pages

**Symptom.** A page holding only floats has a visible band of whitespace in the middle, with content spread apart.

**Cause.** LaTeX's default float-page glue is elastic and spreads floats to fill the page height.

**Advisory.** Top-align float-page glue so slack collects at the bottom rather than between floats. In the preamble:

```latex
\makeatletter
\setlength{\@fptop}{0pt}
\setlength{\@fpsep}{14pt}
\setlength{\@fpbot}{0pt plus 1fil}
\makeatother
\renewcommand{\topfraction}{0.95}
\renewcommand{\bottomfraction}{0.95}
\renewcommand{\textfraction}{0.06}
\renewcommand{\floatpagefraction}{0.80}
\setlength{\textfloatsep}{16pt plus 3pt minus 3pt}
\setlength{\floatsep}{14pt plus 3pt minus 3pt}
```

Apply in the SI preamble first; confirm on a contact-sheet render before applying to the main file.

---

## Wide-and-short figures

**Symptom.** A figure at full text width is short (aspect ratio 3:1 or wider), leaving 40-50% of the page empty below it.

**Cause.** The figure is width-bound at `\textwidth`. LaTeX cannot make it taller without distorting it.

**Advisory.** Regenerate the figure with a taller aspect ratio (target approximately 1.9:1 to 2.2:1) so that two stacked panels plus caption fill a portrait page. In matplotlib, this is a change to `figsize` height only.

Before changing the figure, re-run the pipeline at the original size and pixel-diff against the shipped PDF to confirm the pipeline is deterministic. Only then change the height. Change only the SI branch if main-text and SI figures are produced by different code paths.

Note: making a figure taller does not enlarge tick labels or axis fonts. On-page font size is set by the display width (the figure is scaled to `\textwidth`). To enlarge labels, narrow the figure (more scale-up to `\textwidth`) or increase the in-plot font size directly.

Caption budget: a 5-6 line caption is approximately 80 pt. Size the figure so that heading + short intro + figure + caption fits within the usable text height (approximately 620-650 pt for a 1-inch-margin article on US Letter).

---

## Landscape figures

**Advisory.** Landscape figures (rotated 90 degrees) force the reader to turn the page. Prefer a taller upright redraw over `\rotatebox` or `sidewaysfigure`. Landscape is acceptable in supplementary information for figures that genuinely cannot be redrawn upright, but try the upright redraw first.

---

## Stranded section headings

**Symptom.** Two or more section headings pile at the top of a page above a large empty gap; their figures appear pages later.

**Cause.** Large floats defer; body text and the next `\section` continue flowing and accumulate. Headings outrun their figures.

**Advisory.** Bind each figure section into a heading-plus-figure unit:

1. Make the figure short enough to share a page with its heading and short intro paragraph.
2. Place `\clearpage` immediately before the `\section` to guarantee a full page is available.
3. Pin the figure with `[H]` (requires `\usepackage{float}`) directly after the intro, so it cannot float away.

```latex
\clearpage
\section{Section title}
Figure~\ref{fig:x} shows ...   % short intro, one or two sentences
\begin{figure}[H]
  ...
  \caption{...}\label{fig:x}
\end{figure}
```

Also pin the trailing figure of the preceding section with `[H]` and size it to fit. A `\clearpage` flushes the page early; if the previous section's figure is still floating at that point, its intro text strands instead.

---

## `[H]` placement: sharp edges

`[H]` does not float. If the figure does not fit in the remaining vertical space, LaTeX either page-breaks before the figure (stranding preceding text) or overflows (`Overfull \vbox`). Use `[H]` only when you have verified that there is enough room: size-to-fit first, then pin.

`\usepackage[section]{placeins}` inserts a `\FloatBarrier` at every `\section`, which prevents floats from crossing section boundaries. Useful against float backlog, but it flushes the preceding float and can strand the current heading alone on a page if that section's figure is too tall to share. Use in combination with figure resizing, not as a standalone fix.

Do not add `\clearpage` at every section boundary. Section-boundary clearpages create near-empty pages when a section is short. Use `\clearpage` surgically at figure-heavy sections only.

---

## Multi-panel figures

For wide panels, a single-column vertical stack (panel a above panel b above panel c) at full text width on a dedicated float page (`[p]`) reads larger than a 2x2 grid and is easier for the reader. Tune inter-panel spacing with `\vspace` between `subfigure` environments (0.3 em to 0.8 em is a typical range).

If `Float too large for page by X pt` and X is small (under 5 pt), reduce inter-panel `\vspace` or trim the figure width by approximately 2% before touching the figure source.

---

## What to optimize

Optimize for even page density and no stranded headings, not for the smallest page count. A supplementary section where every page is comfortably full is better than one that is one page shorter but has half-empty figure pages.

---

## Checklist (author action, not polish-loop action)

- [ ] Float-page glue top-aligned in the preamble.
- [ ] Wide-short figures regenerated to approximately 2:1 aspect; faithfulness pixel-checked against original before submission.
- [ ] Figures upright, not landscape (unless genuinely un-squarable).
- [ ] Each figure-heavy section: `\clearpage` before `\section`, `[H]` pin after intro, figure sized to fit with caption.
- [ ] Trailing figure of the preceding section also `[H]` and sized to fit.
- [ ] No blanket `\clearpage` at every section; no stranded headings.
- [ ] Final compile clean: no `Float too large`, no `Overfull \vbox`, no undefined references.
- [ ] Contact-sheet render of the final PDF; every page inspected visually.
