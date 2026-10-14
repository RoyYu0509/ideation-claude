# Venue anchor overview — default / generic top-journal

The fallback overview, used when `config.target_venue` is null or unset. It carries the **register**,
the **how-to-read** conventions, the **banned-vocabulary** note, and a **coverage roster** — but **no
before→after examples**. The examples live one-per-section in the sibling files (`abstract.md`,
`introduction.md`, `results.md`, `methods.md`, `discussion.md`); each holds one or more papers'
before→after pairs for that section.

When a section is hard, the reviser and evaluators read the matching `<section>.md` here as a
**few-shot** (a weak draft → the polished paper). To hear one paper's **full-paper voice**, read that
paper's entry across the section files.

## Register — generic top-journal

The target register is a **conservative generic top-journal** voice: confident, concrete, quantitative,
restrained, and honest about limits. Evidence and mechanism carry the prose. Report numbers, name the
comparison, state what the method does and why it works. Do not oversell scope or generality beyond
what the experiments show.

This register applies across disciplines. It does not prefer equation density or broad-audience
framing over the other; it defers to the paper's own field conventions. What it demands consistently
is that every claim is supported, every comparison is fair, and the prose sounds like a careful human
expert wrote it. (`references/house-voice.md §Register` is the rulebook.)

## How to read each block

Each section file's entries follow the same shape:
- **After** = the paper's actual target prose, **verbatim** (or close to it), de-LaTeX'd where needed.
  This is the *target*.
- **Before** = the kind of weak draft the polisher receives, carrying the **same science**. For real
  edits, the before is the author's pre-revision text; for illustration, it is constructed from the
  same facts with weaker prose.
- **Why** names the principle and tags the rubric or heuristic it teaches.

## Banned-vocabulary note

This profile inherits the **strict** global banned-vocabulary reading with no venue exceptions. All
words flagged in `references/banned-vocabulary.md` are flagged here without qualification. Consult
that file for the current list. No word is venue-acceptable in moderation under the default profile.

## Coverage roster

| paper | abstract | introduction | results | methods | discussion | si |
|-------|----------|--------------|---------|---------|------------|----|

(no entries yet — add rows as papers are reviewed or polished under the default profile)

[FILL IN: add papers by appending a `## <paper>  [ex: <paper>-<section>]` entry to the matching
`<section>.md`, and a row to the roster above. When a venue is identified, create a dedicated
`<Venue>/<field>/` folder instead and set `config.target_venue` accordingly.]
