# AI tells (structural / rhythmic)

Beyond word choice, these patterns make prose read as machine-assembled. check-ai-tells flags them;
the reviser avoids them. Most of these come from a generator following a template too literally.

## Template leakage (the subtle, high-priority one)
- Every paragraph opening with the same syntactic frame.
- Every Introduction gap introduced with "However,".
- Abstracts that sound interchangeable across papers (identical "Here we show ... Our findings ..."
  skeleton with the nouns swapped).
- Mechanical "First, ... Second, ... Third, ..." signposting where prose transitions would read better.
- The funnel/seven-sentence logic showing as visible seams instead of staying latent.

## Rhythm and shape
- Uniform sentence length — every sentence the same weight and cadence.
- Uniform paragraph length.
- Rule-of-three lists everywhere (tricolon overuse).
- Excessive parallelism that reads mechanical rather than rhetorical.

## Hedging and padding
- Hedge stacks: "may potentially possibly suggest".
- A grand significance sentence bolted onto the end of every paragraph.
- Restating the same point in two consecutive sentences with different words.
- Over-signposting what the paragraph will do before doing it.

## Over-correction (ironic tells introduced WHILE de-AI-ing)
- Homogenizing the voice toward a single generic "good academic" register.
- Replacing one banned word with another banned word.
- Adding clunky human-sounding hedges that weren't there.

## Code-documentation / lab-notebook register (computational papers)

The manuscript is written for a reader, not for a maintainer. Writing the method as if documenting the
code is an assignment tell — it reads like a README, not a scientific account. Flag:

- **Source files or functions named in the prose** — `\texttt{hamiltonian.py::build\_pmJ\_heisenberg}`,
  "computed by `ground_state.py`", `scaling.py::fit_exponent`. Describe the METHOD (algorithm, model,
  estimator) in prose + math; name a library by name at most ("a dense eigensolver", "SciPy"). Code-to-
  number provenance belongs in the repo / internal registry, NEVER in the manuscript.
- **The pipeline transcribed as an operation log** — "we then call X, which returns Y, passed to Z".
- **Package/version litanies in the running text** instead of one reproducibility sentence.
- **Code identifiers standing in for defined math symbols** (a variable name where a symbol was defined).

---

[FILL IN: more structural tells you and your advisor notice in real outputs. Pair each with a
before/after example where possible.]
