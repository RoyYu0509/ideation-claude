---
name: venue-learning
description: Build a reusable VENUE house-style pack from a folder of a journal's papers (PDFs) so /polish, /review, /polish-figures, /rewrite, and the auto-research pipeline can emulate that venue's structure, prose, and figure style. OWNER-INVOKED BUILD-TIME PROCESS ONLY (a slash/skill call by the human when adding a venue) — never a pipeline step; disable-model-invocation keeps mid-run auto-triggering off (it has zero by-name loaders, so nothing legitimate is blocked). The OUTPUT is a core+overlay pack under house-style/examples/venue-anchors/<Venue>/.
user-invocable: true
disable-model-invocation: true
---

# Venue learning — build a venue house-style pack from a folder of papers

Turn a folder of one venue's papers (PDFs — published or arXiv) into a **venue house-style pack** the
agentic system plugs into. The pack is pure DATA (progressive-disclosure files); the universal layer
(`venuePreamble` in spec/polish.js, the venue-kit table in spec/review-protocol.md §1, the figure guide
in spec/polish-figures.js) already
knows how to compose + load it. You produce the data; you do not add per-venue logic.

## The one principle
**One paper lies; the venue is the cross-paper invariant.** A single paper's idiosyncrasies (zero theorems,
25 tables, British spelling) are NOT the venue. So the process is grounded-theory: dissect every paper
along a fixed lens, tag each observation INVARIANT vs PAPER-SPECIFIC, then SYNTHESIZE the invariants into a
shared core and FACTOR the variation into sub-brand/sub-genre overlays. Never design the schema top-down
before reading; let it fall out of the dissection.

## The lens (what to extract) — see `references/lens.md`
Seven dimensions × three tiers. Tier A = SIAM-style INVARIANT core (citation/title/abstract/voice/macro-
structure/cross-ref). Tier B = AXES that vary by sub-brand/sub-genre (theorem density, proof placement,
tables-vs-figures, performance reporting, figure conventions). Tier C = NEGATIVE SPACE (what the venue does
NOT do — the most valuable half for an AI reviser, which tends to add exactly those). `lens.md` holds the
per-paper **dossier template** that every reading fills.

## The process (5 phases) — see `references/build-protocol.md`
1. **Per-paper dossier (FAN OUT).** One subagent per PDF fills the dossier template (lens + INVARIANT/PAPER-
   SPECIFIC tags + verbatim-quote evidence + figures read AS IMAGES). Each writes its dossier to disk and
   returns a COMPACT digest. The main agent reads digests, not transcripts — so its synthesis stays sharp.
2. **Cross-paper synthesis (MAIN AGENT, never outsourced).** Fold the ≥threshold invariants into the core;
   collect the negative space; cluster the papers by sub-genre/sub-brand to discover the axes of variation.
3. **Derive the pack schema** from the synthesis (core + overlays + per-paper evidence). The proven shape is
   in `references/build-protocol.md`.
4. **Emit the pack**: `_core/{profile,voice,structure,overall}.md` + `<sub-brand>/{profile,figures,abstract,
   introduction,results,methods,discussion}.md + review/{rubric,reviewer-profiles,scoring}.md` + `papers/`.
   Section few-shots quote VERBATIM real prose as the "after"; review kits are CATEGORICAL (no numeric scores).
5. **Wire + verify**: drop a `paper-skeleton-<key>/` (bundling the venue .cls/.bst if not in TeX Live) so the
   pipeline drafts in the right class; smoke-compile it (`tests/t7_skeletons.sh`); re-sync the plugin cache.

## Fan-out discipline (quality gate)
- Fan out ONLY the per-paper dossiers and the per-sub-brand authoring (mechanical, well-scoped). The
  main agent does the SEED reading and ALL cross-paper synthesis from primary sources — never from a
  subagent's summary. A subagent returns verifiable structured data; it never makes the schema decision.
- The seed paper (the first one) is read by the main agent directly, by hand, before any fan-out — that
  reading is what makes the lens concrete.

## Worked example
The SIAM pack (`house-style/examples/venue-anchors/SIAM/`) was built by this process from 10 arXiv math.NA
papers: one shared `_core/` + three overlays (SISC / SINUM / MMS) + 10 dossiers in `papers/`. Read it to
see the output shape.
