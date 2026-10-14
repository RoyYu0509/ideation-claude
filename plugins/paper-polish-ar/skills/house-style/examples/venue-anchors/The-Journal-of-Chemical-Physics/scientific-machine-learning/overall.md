# Venue anchor overview — The Journal of Chemical Physics / Scientific Machine Learning

The overview for this venue/field. It carries the **register**, the **how-to-read** conventions, the
**banned-vocabulary** note, and a **coverage roster** — but **no before→after examples**. The section few-shots are not shipped in this release (add your own following `../../_TEMPLATE/`).

> **Venue note.** This is *The Journal of Chemical Physics* (AIP Publishing, chemical physics). It is a
> different journal from the sibling venue *Journal of Computational Physics* (Elsevier); they share the
> "JCP" abbreviation only. When the request names this venue, resolve to
> `The-Journal-of-Chemical-Physics/scientific-machine-learning/`.


## Register — JCP (chemical physics) / SciML

The target register is **chemical-physics / SciML**: confident, concrete, quantitative, mechanism-
forward, and *technical first* — methods, equations, error metrics, and benchmarks carry the prose. It
is the equation- and algorithm-dense pole (a Nature-family register is deliberately far less dense):
define objects precisely, name the system / method / benchmark, report numbers and comparisons, and let
the **physical** mechanism — why the method works and what chemical-physics it captures — be stated
soberly. JCP additionally rewards a crisp statement of the underlying *chemical-physics question* and
the physical insight, with approximations and assumptions made explicit. Avoid broad-audience framing
and hype. (`references/house-voice.md §Register` is the rulebook; the section files' "after" passages
are the concrete anchor.)

## How to read each block

Each section file's entries follow the same shape:
- **After** = the paper's actual published prose, **verbatim**, de-LaTeX'd (math / `\cite` / `\ref`
  dropped or rendered in plain text, `\color` revision markup stripped, `\emph` kept). This is the
  *target*.
- **Before** = the kind of weak draft the polisher receives, carrying the **same science** — here it is
  **constructed for illustration** (same facts, weaker prose); it is *not* something the author wrote.
- **Why** names the principle and tags the rubric/heuristic it teaches.

## Banned-vocabulary note

The "after" passages may use `robust` / `comprehensive` / `crucial` / `underscore` / `consistently`,
which are **venue-acceptable in moderation** for JCP / SciML (see `references/banned-vocabulary.md`).
The "before" passages pile on gratuitous hype on top — that is the contrast to learn, not the technical
words themselves.

## Examples

This release ships the venue's register and review kit without section few-shots. To add your own worked examples, follow `../../_TEMPLATE/` (one `## <paper>` entry per section file).
