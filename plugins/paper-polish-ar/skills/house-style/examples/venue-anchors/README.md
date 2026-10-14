# Venue anchors — worked examples by venue

Worked examples that show what good looks like for a venue, organized as
`<Venue full name>/<field>/`. Within each venue/field folder the examples are **section-major** — one
file per section, not one file per paper:

```
<Venue full name>/
  <field>/
    profile.md         # machine-read 7-block contract: identity, register, vocabulary, conventions,
                       #   acceptance-bar, limits, anchors — consumed by /polish and /review at runtime
    overall.md         # human narrative: register + how-to-read conventions + banned-vocab note + paper roster
    abstract.md        # one or more papers' abstract before→after (+why)
    introduction.md
    results.md
    methods.md
    discussion.md
    si.md              # (add only if a paper has an SI anchor)
    review/
      rubric.md            # axes + what each maps to; consumed by the /review panel
      reviewer-profiles.md # panel personas (R1–R4) with lead axes; consumed by the /review panel
      scoring.md           # severity calibration (reject/major/minor), fix_kind, AC ranking; consumed by /review
```

`profile.md` is the **machine-read contract** that `/polish` and `/review` resolve from
`config.target_venue` and thread into every reviser, reviewer, and AC goal. It encodes identity,
register, vocabulary exceptions, typographic conventions, acceptance bar, and format limits in one
self-contained file. `overall.md` is the companion human narrative; `review/` is the panel kit.

Each `<section>.md` holds one or more papers' before→after pairs for that section, each under a
`## <paper>  [ex: <paper>-<section>]` heading. The reviser and `check-readability` read the matching
`<section>.md` as a **few-shot** (a weak draft → the polished paper) when a section is hard — and see
every paper's example for that section in one place, so the shared pattern is visible without opening
several per-paper files.

## What's here now

```
venue-anchors/
  _TEMPLATE/
    profile.md              # 7-block schema with [FILL IN] slots — copy to start a new venue
    overall.md              # blanked overall narrative template
    abstract.md             # blanked section few-shot template
    introduction.md
    results.md
    methods.md
    discussion.md
    review/
      rubric.md             # blanked review rubric template
      reviewer-profiles.md  # blanked reviewer personas template
      scoring.md            # blanked scoring reference template

  default/
    profile.md              # conservative generic top-journal fallback (config.target_venue: null)
    overall.md              # fallback register narrative + empty roster
    review/
      rubric.md             # generic 5-axis rubric, evenly weighted
      reviewer-profiles.md  # soundness hawk + originality/significance skeptic + reproducibility/clarity reader
      scoring.md            # generic severity calibration and AC ranking

  Journal-of-Computational-Physics/
    scientific-machine-learning/
      profile.md            # JCP/SciML 7-block contract (machine-read)
      overall.md            # JCP/SciML register + how-to-read + roster
      review/
        rubric.md           # JCP/SciML: technical soundness leads; broad significance not required
        reviewer-profiles.md  # numerics hawk + baselines/originality skeptic + significance/mechanism questioner
        scoring.md          # JCP-calibrated severity + recommendation postures

  The-Journal-of-Chemical-Physics/   # AIP — chemical physics (a DIFFERENT journal from the one above)
    scientific-machine-learning/
      profile.md            # chem-phys/SciML 7-block contract (machine-read)
      overall.md            # register + how-to-read + roster + supplementary exemplars
      review/
        rubric.md           # chem-phys/SciML: technical+physical soundness leads; broad significance not required
        reviewer-profiles.md  # numerics+physics hawk + baselines/originality + significance/mechanism questioner
        scoring.md          # chem-phys-calibrated severity + recommendation postures
```

The `default/` profile is the fallback when `config.target_venue` is null or unset. It inherits the
strict global banned-vocabulary reading with no venue exceptions and applies a generic evenly-weighted
review kit. Use it when you do not know the target venue or when the venue has no dedicated profile yet.

Section few-shots (`abstract.md` … `discussion.md`) are not shipped in this release; each venue keeps its
`profile.md`, `overall.md` and `review/` kit. Add your own worked examples following `_TEMPLATE/`. Note that
`The-Journal-of-Chemical-Physics/` (AIP) is a different journal from *Journal of Computational Physics*
(Elsevier); they share only the "JCP" initials.

## Core + overlay venues (sub-brand families)

A venue FAMILY whose journals share a register but differ by sub-brand (e.g. **SIAM** → SISC / SINUM / MMS)
is factored into a shared **`_core/`** + per-sub-brand **overlays**, instead of duplicating the core:

```
<Venue>/
  _core/    profile.md · voice.md · structure.md · overall.md      # family-wide INVARIANTS + negative space
  <SUB-BRAND>/  profile.md (DELTAS only) · figures.md · <section>.md few-shots · review/   # what varies by sub-brand
  papers/<id>.md                                                   # per-paper evidence dossiers
```

At runtime the resolver composes `_core/` + the chosen `<SUB-BRAND>/` (overlay fields override the core);
`_core/` is never offered as a standalone venue (the picker excludes `*/_core`). A flat venue (no sub-brands)
keeps the original `<Venue>/<field>/` layout with no `_core/`. The first example is **`SIAM/`** (SISC / SINUM /
MMS, built from 10 arXiv math.NA papers). `figures.md` is consumed by `/polish-figures`; the section few-shots
reach the reviser via `venuePreamble`. To BUILD a venue pack from a folder of a journal's papers, use the
**`venue-learning`** skill — it produces exactly this shape.

## How to grow it

- **Another paper, same venue/field:** append a `## <paper>  [ex: <paper>-<section>]` entry to each
  relevant `<section>.md`, and add a row to the roster in `overall.md`.
- **A new venue or field:** copy `_TEMPLATE/` to `<Venue full name>/<field>/`, fill `profile.md` (all
  seven blocks) and `review/` (rubric, reviewer-profiles, scoring), then set
  `config.yaml target_venue: {venue: "<Venue full name>", field: "<field>"}`. Add section few-shots
  to `abstract.md`, `introduction.md`, etc. as papers become available.
- Replace any constructed "before" in an example with a real weak draft if you have one.

[FILL IN: add more papers/venues over time, following the section-major format above.]
