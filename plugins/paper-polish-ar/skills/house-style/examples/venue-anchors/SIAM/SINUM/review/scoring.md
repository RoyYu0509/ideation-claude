# SINUM scoring reference

How the panel sets severity and the AC ranks the punch-list. Severities match the `/review` schema
(reject | major | minor) and feed the reject-risk ranking. Calibrated to SINUM's proof-forward stance:
a theory paper without a valid proof is categorically different from one with a weaker-than-claimed
rate. Use categorical severity labels — no numeric scores.

## severity calibration

- **reject** — a central theorem is wrong, unproved, or rests on an unstated assumption that would
  materially restrict the scope: proof gap in a main theorem; convergence rate claimed but the
  numerical log-log slope does not match across the paper; scope claimed (e.g., "surfaces in R³")
  but proved only for a strictly smaller case with no acknowledgment; a paper where removing the
  unproved result leaves nothing novel.

- **major** — the case is weakened but salvageable: a missing intermediate lemma whose absence makes
  a proof step non-obvious (the author can supply it); a convergence rate confirmed numerically only
  in a limited regime (pre-asymptotic behavior not discussed); an assumption stated informally that
  needs a precise quantifier; a secondary theorem whose proof has a gap that does not affect the
  main result; a results subsection that does not tie observations to theorem numbers; a mismatch
  between the Introduction's scope claim and what the theorems actually prove, fixable by narrowing
  the claim.

- **minor** — local, editorial: an undefined symbol; a "cf." used for an external citation instead
  of a self-reference; a missing Notation paragraph for a heavy-notation section; a caption that does
  not state fixed parameters; a proof closure marker (□) inconsistently applied; a theorem name
  ("Theorem 3.1") lacking its descriptive parenthetical.

## fix_kind
- **self_fixable** — fixable by editing with existing material: narrow a scope claim to match the
  proved theorems; add a missing hypothesis to a theorem statement; add a bridge sentence from a
  lemma to its downstream theorem; strengthen a "we observe" remark to cite the theorem it confirms;
  define a symbol; add reference-slope annotations to a log-log figure.
- **needs_author** — needs new analytical or computational work: prove a missing lemma; extend the
  analysis to cover a regime the paper claims but does not prove; run additional experiments for a
  parameter regime where the slope deviates from theory; derive a lower bound to justify an optimality
  claim; supply a missing proof for a deferred appendix.

## recommendation posture (per reviewer; reviewer-like, not editorial)
- "supportive if the proof gap in Theorem X is resolved" (R1, major-or-reject level proof issue)
- "promising, but the rate optimality claim is not established from the provided evidence" (R2)
- "the main theorem holds in a narrower regime than stated; the paper is acceptable if the scope is
  narrowed consistently" (R3, self-fixable major)
- "currently not established from the provided evidence" (any reviewer, reject-level gap)
Do not state an editorial decision or claim fit to the venue as settled.

## AC ranking
Rank the punch-list by reject-risk: reject items first, then major, then minor. Within a severity,
order by how central the affected claim is to the paper's thesis — a gap in the stability theorem
ranks above a gap in a secondary rate bound. A proof-correctness reject item from R1 overrides a
rate-sharpness major from R2 in priority.
