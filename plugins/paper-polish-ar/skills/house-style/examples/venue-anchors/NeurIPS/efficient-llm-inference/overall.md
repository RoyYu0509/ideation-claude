# Venue anchor overview — NeurIPS / efficient LLM inference

> **Note.** The section few-shot files (`abstract.md` … `discussion.md`) are not shipped in this release; the roster below describes the full calibration set.


The overview for this venue/field. It carries the **register**, the **how-to-read** conventions, the
**negative-space** list (what NeurIPS efficient-LLM-inference prose does NOT do — the highest-value half
for an AI reviser, which tends to ADD exactly these), the **banned-vocabulary note**, and a **coverage
roster** — but no before→after examples. The examples live one-per-section in the sibling files
(`abstract.md`, `introduction.md`, `results.md`, `methods.md`, `discussion.md`); each holds one or more
papers' before→after pairs for that section. To hear one paper's full-paper voice, read that paper's
entry across the section files and its dossier in `papers/`.

This is a **flat pack**: one field, one machine contract (`profile.md`). The six source papers do split
along a real axis of variation, but they share a strong NeurIPS register, so the axis is documented
*inside* the contract rather than broken into sub-brand folders. See "The sub-genre axis" below.

## Register — NeurIPS / efficient LLM inference

Technical-first, direct, and benchmark-anchored. A NeurIPS efficient-inference paper earns acceptance by
showing a concrete advance — a faster decoder, a smaller KV cache, a 4-bit model, a more faithful RAG
system, a better-calibrated uncertainty score — and by proving it with numbers on named benchmarks
against real, fairly-reproduced baselines. The prose is confident but calibrated: claims track the
evidence, mechanisms are explained before they are fixed ("we analyze the reasons behind this
phenomenon"), and scope limits are stated plainly rather than hidden. First-person plural drives the
narrative ("we introduce / observe / identify / find"). The register is more forward and quantitative
than a specialist journal: a systems abstract states its headline speedup and ends on a code link, and
efficiency/SOTA language is fine when it is tethered to a measurement. What a reviewer punishes is not
confidence but untethered confidence — an adjective with no number, a baseline that is quietly the only
one the method beats, a throughput claim with no hardware, a generality claim beyond the tested regime.

The venue's apparatus is part of its voice: a hard 9-page main text pushes everything else into an
unlimited appendix, and a mandatory paper checklist forces the paper to declare its limitations, its
reproducibility path, its compute, and its societal impact. An AI reviser writing toward this venue must
respect the page economy (be terse in the main text, thorough in the appendix) and must not omit the
checklist, the limitations, or the code-availability statement.

## The sub-genre axis (one field, three poles)

Detect which pole a draft sits at and calibrate; the shared register above still applies.

- **Systems / efficiency-methods** — EAGLE-3, SnapKV, QuaRot. The deliverable is a method/algorithm and
  its measured speed/memory/accuracy. Headline numbers in the abstract; architecture/pipeline schematics
  are first-class; deployment/throughput in a real framework (SGLang, vLLM) with named hardware; method
  delivered as prose "Stage 1/Stage 2", a code listing, or a diagram; ZERO theorems (correctness is cited
  from prior work). QuaRot carries the most mathematics (rotation/computational-invariance) but still
  authors no theorem of its own.
- **Mechanistic-interpretation + method + benchmark** — ParamMute. A causal diagnosis (which FFN layers
  cause unfaithful RAG) staged as correlation→intervention, then a fix (suppress + adapt), then a
  RELEASED benchmark (CoFaithfulQA) with human inter-annotator agreement. RQ-as-header analysis; the
  "Preliminaries" section IS the pilot study, not background.
- **Uncertainty quantification** — the trustworthiness wing. Splits again:
  - **theory-forward** (To Believe or Not to Believe Your LLM) — an information-theoretic derivation with
    named Assumptions/Definitions/Theorems and full proofs in the appendix; results are graphical, no
    leaderboard tables.
  - **empirical-forward** (Semantic Density) — a UQ metric defined by construction and validated across a
    large model×dataset grid with calibration metrics (AUROC/AUPR) and paired significance tests.

## How to read each block

Each section file's entries follow the same shape:
- **After** = the paper's actual published prose, **verbatim**, de-LaTeX'd (inline `\cite`/`\ref` dropped,
  display math simplified, `\emph` kept). This is the target. Abstracts are quoted from the authoritative
  arXiv record; body passages from the rendered PDF.
- **Before** = the kind of weak draft the polisher receives, carrying the **same science** in a weaker
  (AI-tell) register. Constructed for illustration unless noted.
- **Why** names the principle and tags the rubric/heuristic it teaches (e.g. `[Abstract: numbers +
  code link]`, `[Systems: deployment reporting]`, `[ai-tells: drop innovative/remarkable]`).

## Negative space — what NeurIPS efficient-LLM-inference prose does NOT do (flag aggressively if present)

- **No MSC codes, no keyword block, no "the paper is organized as follows" mandate.** Those are journal
  habits; NeurIPS has none of them. (An AI reviser importing a keywords line is a tell.)
- **No theorems in a systems/methods paper.** EAGLE-3, SnapKV, QuaRot author zero theorems; the method is
  prose/diagram/code. Do not manufacture a Proposition to look rigorous. Inversely, do not strip proofs
  from a theory paper — for To Believe, the proofs ARE the contribution.
- **No abstract padded with background before the problem** — but, opposite to a physics journal, a
  systems abstract DOES carry headline numbers and a code link. Don't strip those.
- **No untethered hype:** "innovative", "remarkable", "powerful", "seamless / seamlessly", "a testament
  to", empty "comprehensive". (These do slip past review — SnapKV's "innovative", Semantic Density's
  "seamlessly" — and are exactly what an AI reviser over-adds.) "significant", "efficient", "SOTA" are
  fine ONLY when a number or named object is attached.
- **No Related Work woven into the introduction as prose.** NeurIPS uses a STANDALONE Related Work section
  (early §2 or late before the Conclusion). Folding it into the intro is the journal move, not this one.
- **No manufactured emphasis connectors** ("Importantly,/Notably,/Crucially,") and no every-paragraph-
  the-same opening ("Furthermore,/Moreover,/In addition,").
- **No dropped apparatus:** do not omit the code-availability statement, the Limitations discussion, the
  Broader Impacts, or the NeurIPS Paper Checklist — the last is a desk-reject trigger if missing.
- **No invented error bars / significance** the paper does not have (systems papers often report single
  runs) — but a reviewer WILL flag their absence where variance is load-bearing, so a reviser should
  surface the gap, not paper over it.
- **No British spelling; no em-dash-as-drama.**
- **No quality-vs-baseline table for an exactness-preserving method** (EAGLE-3 declines to evaluate
  generation quality because speculative decoding is lossless) — adding one would betray the method's
  own logic.

## Banned-vocabulary note

This venue relaxes the global `banned-vocabulary.md` for the field's own subject words — **efficient/
efficiency, significant/significantly, state-of-the-art/SOTA, robust** are venue-acceptable *when tethered
to a measurement or a named object*, and **novel** is tolerated once (a contribution lead-in). It does NOT
relax the hype tier: **innovative, remarkable, powerful, seamless, delve, comprehensive-as-filler** stay
flagged. See `profile.md` §vocabulary for the per-word conditions.

## Coverage roster

| paper | sub-genre | abstract | introduction | results | methods | discussion |
|-------|-----------|----------|--------------|---------|---------|------------|
| EAGLE-3 (2503.01840, NeurIPS 2025) | systems / speculative decoding | ✓ | ✓ | ✓ | ✓ | ✓ |
| SnapKV (2404.14469, NeurIPS 2024) | systems / KV-cache compression | ✓ | ✓ | ✓ | | |
| QuaRot (2404.00456, NeurIPS 2024) | systems / 4-bit quantization | ✓ | | | ✓ | |
| ParamMute (2502.15543, NeurIPS 2025) | interp + method + benchmark | | ✓ | ✓ | ✓ | |
| To Believe or Not… (2406.02543, NeurIPS 2024) | UQ / theory-forward | ✓ | | | ✓ | ✓ |
| Semantic Density (2405.13845, NeurIPS 2024) | UQ / empirical-forward | ✓ | ✓ | ✓ | | ✓ |

All six were verified NeurIPS-accepted before use (OpenReview / proceedings.neurips.cc / neurips.cc
virtual posters / arXiv Comments). Full house-style dissections — each observation tagged `[INVARIANT]`
(folds into `profile.md`) vs `[PAPER-SPECIFIC]` (a sub-genre idiosyncrasy) vs `[NEGATIVE-SPACE]` — are in
`papers/*.md`. To hear a sub-genre's full-paper voice, read its rostered papers' dossiers together
(e.g. the two UQ dossiers, or the three systems dossiers).
