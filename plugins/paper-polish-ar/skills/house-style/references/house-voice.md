# House voice (target)

What the prose should sound like. The reviser writes toward this; evaluators judge against it.

## Register: set by the selected venue profile

The target register is defined by the **selected venue profile**:
`examples/venue-anchors/<venue>/<field>/profile.md`, resolved at runtime from `config.target_venue`
and named in every goal's TARGET VENUE preamble. Read its `## register`, `## vocabulary`, and
`## conventions` and write toward them; with no venue set, the conservative `default` profile applies.
The universal **Principles** below are venue-independent and always hold.

**Anchor the voice to the selected venue's worked examples:** start at that venue's `overall.md`
(register, how-to-read conventions, paper roster), then read the matching `<section>.md`
(`abstract.md`, `introduction.md`, `results.md`, `methods.md`, `discussion.md`), each a
**before→after pair per paper**, as few-shots when a section is hard (the "after" is the target; the
"before" is the kind of weak draft to fix). To hear one paper's full voice, read its entry across the
section files. No filled anchor ships in this release; add your own under `examples/venue-anchors/`.

## Principles
- **Confident, not hedging.** State findings directly. Keep only hedges that carry real scientific
  meaning (assumptions, scope, approximation), drop defensive ones.
- **Concrete, not abstract.** Prefer specific mechanisms, quantities, and objects over abstract
  nouns. Name the thing.
- **Quantitative.** Lead with numbers where they carry the claim.
- **Restrained.** No hype, no empty novelty, no grand closers on every paragraph. Let the result
  carry the weight.
- **Funnel logic, latent.** Broad → specific → finding → significance, but as the underlying shape,
  not as visible scaffolding.
- **Honest about limits.** Boundaries and failure cases stated plainly; this reads as human and
  builds trust.
- **Reads like a careful human expert wrote it, not assembled it.** This is the bar.

---

[FILL IN: no worked example ships in this release. Add examples (other papers / venues) over time by appending a `## <paper>` entry to
the matching `<section>.md`; replace any constructed "before" with a real weak draft if you have one.]
