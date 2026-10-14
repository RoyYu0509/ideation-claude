# Banned vocabulary

Words and punctuation that read as obviously-AI in academic prose. The reviser must not emit these;
check-ai-tells greps for them. This list is **seeded** from the author's standing preferences and the
common LLM register; extend it as you catch more.

## Punctuation
- **Em-dash (—)** — never. Use a comma, colon, parentheses, or split the sentence.
- Avoid decorative en-dashes used as em-dashes.

## Author-flagged "defensive / corporate / safety" register (the originating complaint) — a CLASS, not just a list
The originating complaint named `audit`, `diagnostic`, `budget` — but these are *examples of a class*:
the hedging, safety-flavored, risk-averse corporate register that reads as obviously-AI in a
research paper. **check-ai-tells must flag the whole class, not only the enumerated words.**
- Seed list: audit, diagnostic, budget (as filler), assessment (as filler), framework (as empty
  filler), mitigate, safeguard, ensure (as filler), caveat, "careful consideration", "it is
  essential to", "in order to ensure", "robustness considerations", "due diligence".
- Test for the class: does the word/phrase add defensive, procedural, or safety flavor without
  adding scientific content? If yes, cut it or replace with the concrete thing. When you flag a
  word by this class-test that is not in the seed list, say so (so it can be added).

## LLM-default abstraction and hype register (extend freely)
- delve, leverage, utilize (use "use"), holistic, multifaceted, nuanced, intricate, meticulous,
  navigate (figuratively), highlight (overuse), pivotal, realm, landscape, tapestry, seamless,
  foster, garner, plethora, myriad, testament, beacon, cornerstone, paradigm (overuse), showcase,
  facilitate, harness (figuratively), unlock, embark, journey, ever-evolving, rapidly evolving

## Venue-acceptable in moderation — defined by the selected venue profile
Some words on the lists above are *venue-acceptable in moderation*. The acceptable set and its
conditions live in the **selected venue profile's `## vocabulary` block**
(`examples/venue-anchors/<venue>/<field>/profile.md`, named in every goal's TARGET VENUE preamble);
apply that set in context and do NOT flag every occurrence of a word it allows. For JCP/SciML, for
example, the profile allows `robust`, `comprehensive`, `crucial`, `underscore`, `significant`,
`consistently` in their technical or clearly-quantified sense and flags only the vague /
non-technical / over-used case. With no venue (the `default` profile), use the strict reading: treat
these as flaggable unless the technical sense is unmistakable. check-ai-tells: respect the selected
profile's conditions.

## Empty-novelty / hype words (top journals dislike these)
- groundbreaking, revolutionary, cutting-edge, state-of-the-art (as adjective filler), novel
  (overuse), unprecedented, remarkable (overuse), significant (when not statistical)

## Formulaic discourse markers (overuse = tell)
- "It is worth noting that", "It is important to note that", "Notably,", "Importantly,",
  "Interestingly,", "In essence,", "At its core,", "It is widely recognized that",
  "plays a crucial role in", "a wide range of", "shed light on"

---

[FILL IN: every new "obviously-AI" word or phrase you or your advisor catch goes here. For each, add
a before/after pair to `../examples/before-after/` so the reviser learns the replacement, not just
the prohibition.]
