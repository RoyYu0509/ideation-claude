# Build protocol — emit the pack, wire it, verify it

## The pack schema (core + overlay)
A venue family with sub-brands (e.g. SIAM → SISC/SINUM/MMS) factors into a shared core + per-sub-brand
overlays. A venue with no sub-brands is just one overlay (the existing flat `<Venue>/<field>/` layout — no
`_core/`). Lay out under `house-style/examples/venue-anchors/`:
```
<Venue>/
  _core/                         # shared invariants (Tier A) + negative space (Tier C). OMIT for a flat venue.
    profile.md                   # 7-block machine contract at CORE level (identity/register/vocabulary/conventions/acceptance-bar/limits/anchors)
    voice.md                     # micro prose voice + the NEGATIVE-SPACE list (what the venue does NOT do)
    structure.md                 # invariant macro skeleton + argument arc
    overall.md                   # human narrative + the paper roster (by sub-brand)
  <SUB-BRAND>/                    # = the resolvable <field>; one per sub-brand (or the only dir for a flat venue)
    profile.md                   # OVERLAY: ONLY the fields that differ from _core (Tier B deltas). For a flat venue this is the full 7-block profile.
    figures.md                   # this sub-brand's figure & table visual style (→ /polish-figures)
    abstract.md introduction.md results.md methods.md discussion.md   # before→after section few-shots (verbatim real "after")
    review/ rubric.md reviewer-profiles.md scoring.md                 # the panel kit (CATEGORICAL severity, NO numeric scores)
  papers/<id>.md                 # the per-paper evidence dossiers (loaded on demand for a full-model-paper gestalt)
```

## How it composes at RUNTIME (already wired — do NOT add per-venue logic)
- `venuePack` (spec/polish.js; the /review side composes per spec/review-protocol.md §1) detects a `_core/` sibling of `<Venue>/<SUB-BRAND>` and records it.
- `venuePreamble` loads + COMPOSES `_core/profile.md` + the overlay `profile.md` (overlay overrides core),
  plus `_core/voice.md` + `_core/structure.md`, and points the reviser/reviewers at the matching
  `<SUB-BRAND>/<section>.md` few-shot. (This is the Gap-1 fix: section few-shots reach the reviser.)
- `listPreparedVenues` excludes `*/_core` (it is not a standalone venue); the picker offers the sub-brands.
- spec/polish-figures.js loads `<SUB-BRAND>/figures.md` when the caller passes `args.venue`; the auto-research
  美化 pass passes `state.venue`. Absent → generic research-figure-plotting stance.

## Emit discipline
- Section few-shots: the "after" is VERBATIM published prose (the positive anchor); construct a plausible
  WEAK "before" (AI-tell register) + a "why" tied to a specific core/overlay rule. Format = `_TEMPLATE/<section>.md`.
- Overlay `profile.md`: DELTAS only — never restate a core rule (it composes over the core).
- review kit: categorical (reject/major/minor) + AC ranking. NEVER numeric/LLM scores (owner principle).
- Keep every file lean (progressive disclosure). The core is loaded always; deep files load on demand.

## Wire the LaTeX skeleton (so the pipeline drafts in the right class)
The auto-research pipeline copies `assets/paper-skeleton-<key>/` where `<key>` = the venue rel's first
segment, lowercased (e.g. "SIAM/SISC" → "siam"; all sub-brands of a family share ONE skeleton + class).
Build `assets/paper-skeleton-<key>/`: `master.tex` (FLAT `\input` — resolve_manuscript.py is non-recursive)
+ `sections/{abstract,introduction,methods,results,discussion,macros}.tex` + `references.bib` (write via
Bash — the fidelity hook blocks Write/Edit on .bib) + `figures/.gitkeep`. **If the venue class is NOT in
TeX Live (e.g. siamart), BUNDLE the .cls + .bst in the skeleton dir.** Match an existing skeleton's stubs.

## Verify + sync
- Smoke-compile: `bash tests/t7_skeletons.sh` (auto-discovers every `assets/paper-skeleton-*`; must pass).
- Spot-check the pack: review kits have no numeric scores; few-shot "after" blocks are verbatim; `node --check`
  any spec you edited.
- Re-sync the plugin cache (only `paper-polish-ar` has a cache copy; see the project sync memory): `rsync -a
  --exclude=__pycache__ --exclude='*.pyc' plugins/paper-polish-ar/ ~/.claude/plugins/cache/<active-marketplace>/paper-polish-ar/0.1.0/`
  then `diff -rq` to confirm a mirror. `assets/` + repo-root `spec/research.js` load from the monorepo directly (no sync).
