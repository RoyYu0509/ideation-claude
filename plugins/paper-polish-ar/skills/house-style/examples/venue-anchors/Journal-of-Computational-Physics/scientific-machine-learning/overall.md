# Venue anchor overview — Journal of Computational Physics / Scientific Machine Learning

The overview for this venue/field. It carries the **register**, the **how-to-read** conventions, the
**banned-vocabulary** note, and a **coverage roster** — but **no before→after examples**. The section few-shots are not shipped in this release (add your own following `../../_TEMPLATE/`).


## Register — JCP / SciML

The target register is **JCP / SciML**: confident, concrete, quantitative, restrained, and *technical
first* — methods, equations, error metrics, and benchmarks carry the prose. It is more equation- and
algorithm-dense than a Nature-family register: define objects precisely, name the PDE/benchmark,
report numbers and comparisons, and let mechanism (why the method works) be stated soberly. Avoid
broad-audience framing and hype. (`references/house-voice.md §Register` is the rulebook; the section
files' "after" passages are the concrete anchor.)

## How to read each block

Each section file's entries follow the same shape:
- **After** = the paper's actual published prose, **verbatim**, de-LaTeX'd (math / `\cite` / `\ref`
  dropped, `\color` revision markup stripped, `\emph` kept). This is the *target*.
- **Before** = the kind of weak draft the polisher receives, carrying the **same science**. For
  **methods** the before is the author's *real* pre-revision text (preserved as a comment in the
  source); for the other sections the before is **constructed for illustration** (same facts, weaker
  prose) — it is *not* something the author wrote.
- **Why** names the principle and tags the rubric/heuristic it teaches.

## Banned-vocabulary note

The "after" passages use `robust` / `comprehensive` / `underscore` / `consistently`, which are
**venue-acceptable in moderation** for JCP/SciML (see `references/banned-vocabulary.md`). The "before"
passages pile on gratuitous hype on top — that is the contrast to learn, not the technical words
themselves.

## Examples

This release ships the venue's register and review kit without section few-shots. To add your own worked examples, follow `../../_TEMPLATE/` (one `## <paper>` entry per section file).
