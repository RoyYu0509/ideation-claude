# JCP / SciML scoring reference

How the panel sets severity and the AC ranks the punch-list. Severities match the `/review` schema
(reject | major | minor) and feed the reject-risk arithmetic.

## severity calibration (JCP)
- reject — a central claim is not established: no error / convergence evidence for an accuracy claim;
  missing or unfair primary baseline; generality claimed but never tested; a result that contradicts
  itself across sections. The paper would be rejected or sent for major revision on this alone.
- major — the case is weakened but salvageable: a missing load-bearing ablation (one the central claim
  depends on, and not already in the paper), an undertuned baseline, an unstated assumption that limits
  scope, a mechanism asserted without support, reproducibility gaps in a key experiment.
- minor — local: an undefined symbol, an inconsistent term, a missing seed for a secondary run, a
  completeness / nice-to-have ablation the central claim does not rest on (a real reviewer may still
  suggest it — record it, do not treat it as a blocker), a readability snag for a specialist.

## fix_kind
- self_fixable — fixable by editing / restructuring with the paper's existing data: weaken an oversold
  claim to match the evidence, fix a logic gap, reorder for coherence, define a symbol, tighten the
  narrative.
- needs_author — needs new work or author intent: run an experiment, add a baseline, supply a missing
  number / setup, decide whether to narrow a claim or defend it. The panel marks these; it never
  invents the data.

## recommendation posture (per reviewer; reviewer-like, not editorial)
- "supportive if the numerical concerns are resolved"
- "promising, but the advance over [baseline] is not yet established"
- "currently not established from the provided evidence"
Do not state an editorial decision or claim fit to the venue as settled.

## AC ranking
Rank the punch-list by reject-risk: reject items first, then major, then minor. Within a severity,
order by how central the affected claim is to the paper's thesis.
