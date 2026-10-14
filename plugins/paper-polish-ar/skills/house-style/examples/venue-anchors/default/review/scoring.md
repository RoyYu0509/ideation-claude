# Default scoring reference — generic top-journal

How the panel sets severity and the AC ranks the punch-list. Severities match the `/review` schema
(reject | major | minor) and feed the reject-risk arithmetic. Calibrated for a generic top-journal
register: no single axis dominates, so reject-grade failings can arise on any of the five axes.

## severity calibration
- reject — a central claim is not established from the evidence, or a structural flaw undermines the
  paper's core contribution: no evidence for a key accuracy or performance claim; missing or unfair
  primary baseline; conclusions that substantially outrun the experiments; a contradiction between
  claimed contribution and reported results. The paper would require a major new body of work to fix.
- major — the case is weakened but salvageable with the existing data or with a targeted addition: a
  missing load-bearing ablation (one the central claim depends on, and not already in the paper), an
  undertuned baseline, an overstated scope, a reproducibility gap in a key experiment, a mechanism
  asserted without demonstration, a logical inconsistency in the narrative that requires restructuring.
- minor — a local fix that does not affect the core contribution: an undefined symbol, an inconsistent
  term, a missing seed for a secondary result, a completeness / nice-to-have ablation the central claim
  does not rest on (a real reviewer may still suggest it — record it, do not treat it as a blocker), a
  readability snag, a missing citation for a supporting claim.

## fix_kind
- self_fixable — fixable by editing or restructuring with the paper's existing data: weaken an
  oversold claim to match the evidence, fix a logic gap, reorder for coherence, define a symbol, tighten
  the narrative, correct an inconsistency.
- needs_author — needs new work or author intent: run an experiment, add a baseline, supply a missing
  number or setup, decide whether to narrow a claim or defend it with new evidence. The panel marks
  these; it never invents the data.

## recommendation posture (per reviewer; reviewer-like, not editorial)
- "supportive if the evidentiary concerns are resolved"
- "promising, but the advance over [prior method] is not yet established"
- "currently not established from the provided evidence"
Do not state an editorial decision or claim fit to the venue as settled.

## AC ranking
Rank the punch-list by reject-risk: reject items first, then major, then minor. Within a severity,
order by how central the affected claim is to the paper's thesis.
