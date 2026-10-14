# Nature Computational Science / SciML scoring reference

How the panel sets severity and the AC ranks the punch-list. Severities match the `/review` schema
(reject | major | minor) and feed the reject-risk arithmetic. The Nature-family difference: a "sound
but not broadly significant" finding is a HIGH-severity item here, not a pass.

## severity calibration (Nature-family)
- reject — the paper fails a top axis: the advance is field-internal / incremental with no
  demonstrated broad interest; the central claim is not established by the evidence; the novelty is
  not distinguished from prior work; or the main text is inaccessible to a non-specialist and the
  significance never lands. The paper would be declined (often without review) on this alone.
- major — salvageable but a top axis is underdeveloped: broad significance asserted but thinly
  supported, a missing load-bearing baseline/ablation (one the central claim depends on, and not
  already in the paper), an accessibility problem confined to one section, an originality claim that
  needs sharper positioning.
- minor — local: an undefined term, an over-technical sentence, a missing seed for a secondary run, a
  completeness / nice-to-have ablation the central claim does not rest on (a real reviewer may still
  suggest it — record it, do not treat it as a blocker).

## fix_kind
- self_fixable — fixable by editing/restructuring with the paper's existing data: sharpen and scope
  the significance/positioning to what is shown, reframe the opening for breadth, fix a logic gap,
  move equation-dense detail to Methods/SI, define a term, tighten the narrative.
- needs_author — needs new work or author intent: run an experiment / add a baseline, supply missing
  data, or DECIDE the broad-significance framing (what wider community, what implication) — which is
  the author's scientific judgment, not something to invent. The panel marks these; never invents data
  or a broad claim the paper cannot support.

## recommendation posture (per reviewer; reviewer-like, not editorial)
- "of potential broad interest if the significance case is substantiated"
- "technically sound but the advance is currently field-internal"
- "promising, but the novelty over [prior work] is not yet established"
- "not yet established from the provided evidence"
Do not state an editorial decision or claim fit to the venue as settled.

## AC ranking
Rank by reject-risk: reject first, then major, then minor. Within a severity, order by how central the
affected axis is to a Nature-family case — a broad-significance or originality failure outranks a local
soundness gap, because at this venue the former is what gets the paper declined.
