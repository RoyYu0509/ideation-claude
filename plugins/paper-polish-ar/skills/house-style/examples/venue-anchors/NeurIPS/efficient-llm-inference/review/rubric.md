# NeurIPS efficient-LLM-inference review rubric

The standard a `/review` panel judges a NeurIPS efficient-inference manuscript against. NeurIPS is a
benchmark-driven ML conference: the deliverable is a method, metric, diagnosis, or benchmark whose value is
established QUANTITATIVELY on named benchmarks against real baselines. Theory is required only for
theory-forward papers (where it IS the contribution); for systems/methods papers it is neither required nor
sufficient. Each axis maps to a `check-*` skill or a `review-panel` axis. Composes with `../profile.md`
(acceptance-bar block); this file is the detail. Severity is CATEGORICAL (reject | major | minor) — see
`scoring.md`; there are NO numeric scores.

## axes

### 1. empirical rigor & benchmark validation — the dominant axis (maps to check-results)
Is the claimed advance established by the numbers?
- Evaluation on the CANONICAL benchmarks for this problem class (e.g. Spec-Bench / MT-bench / HumanEval /
  GSM8K for decoding; WikiText-2 perplexity + zero-shot suite for quantization; LongBench / Needle for
  KV-cache; AUROC/AUPR on free-form QA for UQ; a faithfulness benchmark for RAG), across multiple models.
- Metrics defined precisely and applied consistently; the RIGHT metric for the claim (a lossless decoder
  reports speedup/acceptance-length, NOT a quality delta; a UQ method reports calibration, not accuracy).
- Enough of the grid (models × datasets × settings) that the claim is not a single lucky configuration.
Reject-grade failing: a central accuracy/efficiency/calibration claim with no supporting metric, the wrong
metric for the claim, or a single run presented as a general result.

### 2. reproduced & fair baselines (maps to check-results + review-panel: significance)
Does the paper compare against the real competitors, fairly?
- The primary baselines a knowledgeable reader expects are present (e.g. GPTQ/SmoothQuant/OmniQuant/Atom
  for 4-bit quant; EAGLE-2/Medusa/Hydra/HASS for speculative decoding; semantic entropy / P(true) for UQ).
- Reproduce-then-compare: prior-work numbers are reproduced or fairly extracted at matched settings
  ("same experimental setup as in [n]"), not strawman or undertuned versions.
- If the method loses on a benchmark, the paper reports it and gives a mechanism (it does not omit it).
Reject-grade failing: the only comparisons shown are ones the method wins; a primary baseline is missing or
demonstrably undertuned; a comparison holds one method at an unfair budget.

### 3. ablations that isolate the mechanism (maps to check-results)
Is the SOURCE of the gain established?
- An ablation removes each proposed component and shows its contribution (e.g. EAGLE-3's "remove feature
  constraint" vs "fused features"; QuaRot's random-orthogonal-vs-Hadamard, KV-precision, clipping).
- The mechanism the paper credits for the improvement is the one the ablation actually isolates.
Reject/major: the central claim ("component X is why it works") rests on no ablation that varies X while
holding the rest fixed.

### 4. efficiency claims properly measured (maps to check-results)
Does the paper measure what it claims to save, and account for all costs?
- Hardware named for any timing/throughput claim (A100/H100, memory, framework/version) — not "a modern GPU".
- Deployment-in-a-real-framework (SGLang/vLLM) for a systems throughput claim, across batch sizes.
- All costs counted: offline/preprocessing (SVD, calibration, Hadamard transform overhead), not just the
  favorable phase; memory footprint reported alongside speed.
Major/reject: a throughput/latency claim with unspecified hardware or omitted offline cost; a "faster"
claim with no wall-clock/throughput measurement.

### 5. theory correctness — theory-forward papers only (maps to check-results + check-logic)
When a theorem/bound is a contribution (e.g. To Believe or Not's MI metric):
- Every theorem states its assumptions and has a complete, correct proof (main text or appendix, with a
  proof sketch if deferred) — the checklist's "Theory Assumptions and Proofs" question.
- The empirical results confirm the theory (the derived metric actually detects what it claims).
- The theorem proved is the one USED (not a proxy generalization silently substituted).
Reject-grade: a theoretical claim with no proof or no stated assumptions; a bound claimed but never
confirmed empirically; the proved result differs from the deployed method.

### 6. reproducibility & the NeurIPS checklist (maps to check-results)
Could a competent reader reproduce this, and is the required apparatus present?
- All hyperparameters, training details (lr, batch, epochs, optimizer), data splits, seeds, and problem
  setups disclosed to the level needed to reproduce the main results.
- Code/data availability stated (a repo link, or a documented reproducibility path); a released benchmark
  is documented with construction details and inter-annotator agreement.
- The NeurIPS Paper Checklist is present and honest (its absence is a DESK-REJECT trigger); Limitations and
  Broader Impacts are addressed.
Reject-grade: no reproducibility path for the main results; missing/dishonest checklist. Major: key
hyperparameters or setup details missing from a central experiment.

### 7. originality & significance to the ML community (maps to review-panel: significance axis)
Is the advance clear, and does it matter beyond one benchmark?
- The advance over the closest prior method is stated explicitly and quantified.
- Generality is calibrated to the tested regime — the paper claims what it tests, not more.
- The contribution is of interest to the broad efficient-inference / trustworthiness community, not a
  hyper-narrow tweak.
Major: generality asserted well beyond the tested models/tasks; the delta over the closest baseline is
marginal and not characterized.

### 8. coherence & clarity for the specialist (maps to review-panel: coherence axis + check-logic)
Does the paper tell one clear story at the right altitude?
- Gap (diagnosed mechanism) → method → validation arc is linear; no orphaned subsections.
- Notation consistent, defined before use; Related Work is a standalone section, not woven into the intro.
- Results subsections open with the question they answer; bold-lead-in experimental paragraphs are used
  consistently.
- Main-text page economy respected: the 9-page main text is not padded, and overflow lives in the appendix.

## how to run it
Each panel reviewer foregrounds one axis (see reviewer-profiles.md) but touches all briefly. Detect the
sub-genre first (systems / interp+benchmark / theory-UQ / empirical-UQ) — axis 4 dominates for systems,
axis 5 for theory, axis 1+2 for UQ — and weight accordingly. The AC synthesizes against this rubric and
ranks issues by reject-risk (see scoring.md). Mark anything not assessable from the manuscript as
needs_author.
