# NeurIPS efficient-LLM-inference scoring reference

How the panel sets severity and the AC ranks the punch-list. Severities match the `/review` schema
(reject | major | minor) and feed the reject-risk arithmetic. This is CATEGORICAL — there are NO numeric
scores, no 1–10 ratings, no "soundness 3/contribution 2" tuples (owner principle: the panel reasons about
reject-risk, not points). Calibrated for NeurIPS efficient inference: the primary currency is benchmark
evidence (speedup/memory/perplexity/calibration on named benchmarks vs real baselines), plus the venue's
required apparatus (reproducibility, checklist, limitations).

## severity calibration

- reject — a central claim is not established, or a desk-reject trigger is present:
  - A central accuracy/efficiency/calibration claim with no supporting metric, or the WRONG metric for the
    claim (e.g. a lossless decoder "evaluated" on generation quality; a UQ method judged on task accuracy).
  - An efficiency/throughput claim with hardware unspecified or offline costs (SVD/calibration/Hadamard,
    memory) omitted.
  - Missing or demonstrably undertuned PRIMARY baseline; comparisons shown only where the method wins.
  - Generality claimed well beyond every tested regime (e.g. "general for long-context inference" from one
    model family and one length).
  - A theoretical claim (theory-forward paper) with no proof or no stated assumptions, or a bound never
    confirmed empirically, or the proved result differing from the deployed method.
  - The NeurIPS Paper Checklist is absent (desk-reject) or materially dishonest.
  - Results that contradict the paper's own stated claims without explanation.

- major — the case is weakened but salvageable:
  - A load-bearing ablation missing — one that isolates the component the paper credits for the gain (vary
    that component, hold the rest fixed) — and not already shown.
  - Key hyperparameters / training details / seeds / problem setup missing from a central experiment, so
    reproduction is blocked.
  - Hardware or serving-framework details disclosed only partially for a main timing/throughput result.
  - A mechanism asserted ("the advantage comes from X") without evidence even at a hypothesis level.
  - A baseline present but at an unfair budget — fixable by re-running at matched parameter/compute count.
  - Generality asserted beyond the tested models/tasks — fixable by narrowing the claim or adding evidence.

- minor — local, does not block the central claims:
  - Undefined symbol, inconsistent notation, a term used before introduction.
  - A missing seed for a secondary/supplementary run.
  - A completeness ablation the central claim does not rest on (record it; a real reviewer may suggest it).
  - Related Work woven into the intro instead of a standalone section; a bold-lead-in experimental
    paragraph applied inconsistently.
  - Hype vocabulary ("innovative", "remarkable", "seamlessly") — flag and de-hype, not a blocker.
  - Figure caption above / table caption below the wrong way; missing value labels on a speedup bar chart.

## fix_kind
- self_fixable — fixable by editing with the paper's existing data: weaken an oversold claim to match the
  evidence, define a symbol, fix notation, move Related Work into its own section, de-hype, add a value
  label to an existing figure, rewrite an assertion as a hypothesis, restate a claim to match the tested
  regime, add the code-availability sentence.
- needs_author — needs new work: run an experiment, add a baseline, run at matched budget, disclose missing
  hardware/hyperparameters, produce the isolating ablation, add a proof or empirical confirmation of a
  bound, complete the checklist honestly, run in a real serving framework, decide whether to narrow or
  defend a generality claim. The panel marks these; it never invents data.

## recommendation posture (per reviewer; reviewer-like, not editorial)
- "supportive if the missing primary baseline is added and reproduced at matched settings"
- "promising, but the efficiency claim is not established without the hardware environment and offline-cost
  accounting"
- "the mechanism claim is not established from the provided experiments without the isolating ablation"
- "the theoretical bound is not usable as stated until Assumption 4.1 is made explicit and the bound is
  confirmed empirically"
Do not state an editorial accept/reject decision or claim venue fit as settled — that is the AC's synthesis,
and ultimately the human's.

## AC ranking
Rank the punch-list by reject-risk: reject items first, then major, then minor. Within a severity, order by
how central the affected claim is to the paper's thesis, weighting by sub-genre (an unmeasured efficiency
claim ranks highest for a systems paper; an unproven/​unconfirmed bound ranks highest for a theory paper; a
missing primary baseline or wrong calibration metric ranks highest for a UQ paper). A missing checklist is a
standing reject-risk regardless of sub-genre.
