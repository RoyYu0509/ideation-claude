# SISC scoring reference

How the panel sets severity and the AC ranks the punch-list. Severities match the `/review` schema
(reject | major | minor) and feed the reject-risk arithmetic. Calibrated for SISC: the primary
currency is computational evidence (convergence rates, timing, error metrics), not theoretical depth
alone.

## severity calibration (SISC)

- reject — a central computational claim is not established:
  - An accuracy or convergence claim with no error metric or convergence study to support it.
  - A timing/efficiency claim with hardware environment unspecified or costs omitted (e.g. offline
    SVD excluded from reported wall-clock).
  - Missing primary baselines — the canonical competing method for this problem class absent or
    demonstrably undertuned.
  - Generality claimed beyond all tested regimes (e.g. "outperforms FNO for high-frequency
    problems" but only two test cases shown and both from the same equation family).
  - A rate or complexity stated in the abstract (e.g. O(·)) with no proof and no numerical
    confirmation.
  - Results that contradict the stated claims elsewhere in the paper without explanation.

- major — the case is weakened but salvageable:
  - A load-bearing ablation missing — one on which the central claim depends and that is not
    already in the paper (e.g. the paper claims POD basis is the reason for improvement but
    provides no ablation swapping the basis while holding architecture constant).
  - Key hyperparameters or problem-setup details missing from a central experiment (learning
    rate, mesh size, boundary conditions, seeds) such that reproduction is blocked.
  - Hardware environment disclosed only partially for a timing experiment that is a main result.
  - A mechanism asserted ("the advantage may be attributed to …") without supporting evidence
    even at a hypothesis level.
  - Baseline present but run at an unfair parameter budget — fixable by re-running at matched
    parameter count.

- minor — local, does not block the central claims:
  - An undefined symbol, inconsistent notation, a term used before introduction.
  - A missing seed for a secondary/supplementary run.
  - A completeness ablation the central claim does not rest on (record it, do not treat as
    blocker — a real reviewer may suggest it).
  - Caption missing the benchmark name "(Problem)" opener per SISC caption convention.
  - Shared colorbar missing for panels that are being compared on the same scale (figures.md
    norm); per-panel colorbars acceptable when panels are not on the same comparison axis.

## fix_kind
- self_fixable — fixable by editing with the paper's existing data: weaken an oversold claim
  to match the evidence shown, define a symbol, fix a notation inconsistency, add a reference
  slope annotation to an existing log–log plot, rewrite an assertion as a hypothesis, reorder
  for coherence.
- needs_author — needs new work: run an experiment, add a baseline, disclose missing hardware
  specs, supply missing hyperparameters, generate a convergence table for a claimed rate, decide
  whether to narrow or defend a generality claim. The panel marks these; it never invents data.

## recommendation posture (per reviewer; reviewer-like, not editorial)
- "supportive if the convergence evidence and hardware specification are added"
- "promising, but the advance over [baseline] is not yet established from the provided experiments"
- "the efficiency claim is not established from the provided evidence without the missing hardware
  environment and offline-cost accounting"
Do not state an editorial decision or claim fit to the venue as settled.

## AC ranking
Rank the punch-list by reject-risk: reject items first, then major, then minor. Within a severity,
order by how central the affected claim is to the paper's thesis. A missing convergence study for
the paper's headline rate claim ranks above a missing secondary ablation at major severity.
