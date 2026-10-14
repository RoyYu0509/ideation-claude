<!-- NeurIPS / efficient-LLM-inference venue contract. FLAT pack (no _core/ sibling): this file is the
     FULL 7-block machine-read contract, resolved on its own from config.target_venue =
     "NeurIPS/efficient-llm-inference" and threaded into every reviser/reviewer/AC goal. The six source
     papers cluster along ONE axis of variation (systems/methods <-> analysis/theory), documented INSIDE
     this contract rather than split into sub-brand overlays, because the venue register (benchmark-battery
     evidence, 9-page main + unlimited appendix, mandatory checklist, bold-lead-in experimental paragraphs,
     code availability, standalone Related Work) is a strong shared invariant that dominates the split.
     Synthesized from 6 NeurIPS-accepted papers; per-paper evidence in ./papers/. Keep all seven blocks. -->
# Venue profile — NeurIPS / efficient LLM inference

## identity
- venue: NeurIPS (Conference on Neural Information Processing Systems) — the ML flagship conference. Field folder: efficient LLM inference.
- field: efficient large-language-model inference & LLM trustworthiness — speculative decoding, KV-cache compression, low-bit quantization, retrieval-augmented-generation faithfulness, uncertainty quantification.
- type: top-tier ML CONFERENCE (page-limited camera-ready, fixed `.sty` class, double-blind review + rebuttal/discussion period, mandatory paper checklist, unlimited supplementary/appendix). NOT a journal — do not import journal habits (MSC codes, keyword blocks, unlimited main text, "the paper is organized as follows" outlines are optional here).
- audience: ML researchers and practitioners fluent in transformers, attention, quantization, decoding, and calibration. Paragraph 1 assumes that fluency; it does NOT re-teach what an LLM or attention is.
- sub-genre axis (varies WITHIN this field — see `conventions` and the section few-shots): **systems/efficiency-methods** (EAGLE-3, SnapKV, QuaRot) ⟷ **mechanistic-interp + method + benchmark** (ParamMute) ⟷ **uncertainty quantification** (To Believe = theory-forward; Semantic Density = empirical-forward). A reviser detects which pole a draft sits at and calibrates accordingly; the register below is shared.

## register
Technical-first, direct, benchmark-anchored, confident. The deliverable is a METHOD (or metric, or diagnosis+benchmark) whose value is demonstrated by numbers on named benchmarks against real baselines. First-person plural drives the narrative ("we introduce / observe / identify / find"); passive is reserved for mechanisms and defined objects. Claims are calibrated to evidence and scope limits are stated plainly ("Due to the GPU constraint, we are unable to test … the 405B and 671B models"). Contribution framing is more forward and quantitative than a specialist journal: **a systems abstract carries its headline numbers** (speedup, memory, perplexity) and closes on a code link; an analysis/UQ abstract stays conceptual and withholds numbers. Mechanism is explained before it is fixed ("we analyze the reasons behind this phenomenon"). Hype-per-number is low: efficiency and SOTA language is normal WHEN tied to a measured result, empty superlatives are not.

## vocabulary
### venue-acceptable in moderation
Normal ML-conference usage; flag only the vague / untethered / hype case. (See "negative space" in `overall.md` for what this venue refuses.)
- efficient / efficiency — the field's SUBJECT; fine tied to a memory/latency/throughput/FLOP claim; flag as a bare adjective with no measurement.
- significant / significantly — technical or emphatic sense is accepted at NeurIPS ("significantly enhance performance"); still flag as a vague intensifier with no number nearby.
- state-of-the-art / SOTA — accepted when it names an object (a baseline, a model, a benchmark result: "the state-of-the-art technique [22]"); flag as bare self-praise ("our SOTA framework").
- novel / novelty — tolerated once, e.g. a contribution lead-in ("A novel … architecture"); flag repetition or "novel" as the only claimed merit.
- framework / approach / method — plain labels for the contribution; flag marketing use.
- robust / robustness — technical sense OK ("robust with respect to different noise settings"); flag a vague "robust framework".
### venue-stricter
- innovative, remarkable, powerful, seamless / seamlessly, comprehensive (as filler), delve, "a testament to" — flag aggressively; these survive into some accepted papers (SnapKV "innovative", Semantic Density "seamlessly") but read as promotional and are exactly what an AI reviser over-adds.
- em-dash-as-drama and "Importantly,/Notably,/Crucially," as manufactured emphasis — flag.

## conventions
- spelling: American (optimization, behavior, Acknowledgments).
- references: EITHER numbered bracket [n] (SnapKV, QuaRot, ParamMute, Semantic Density) OR author-year natbib (EAGLE-3, To Believe) — NeurIPS accepts both ("Citations may be author/year or numeric, as long as you maintain internal consistency"). Blue hyperlinked; dense clusters (3–8 keys) per claim are normal. Pick ONE and be consistent.
- title: "Name/ACRONYM: descriptive expansion of the mechanism/contribution" is the dominant form (EAGLE-3, SnapKV, QuaRot, ParamMute, Semantic Density). An allusive/rhetorical title (To Believe or Not to Believe Your LLM) is tolerated for analysis/theory papers. No rhetorical-question titles for method papers.
- abstract: single unstructured paragraph, ~150–220 words, funnel shape (problem → prior gap → contribution → result). SYSTEMS papers put headline numbers IN the abstract and end on a code link; ANALYSIS/UQ papers stay conceptual (no numbers). No structured headings. No keywords/MSC block anywhere.
- sections: Introduction (funnel; contributions usually as a bullet list, sometimes bold-lead-in) → Preliminaries/Background (define prior methods + notation before the contribution) → Method → Experiments (each subsection names its question; ablations expected) → **Related Work as a STANDALONE section** (position varies: early §2, or LATE right before the Conclusion) → Conclusion → Acknowledgments (funding + competing-interests disclosure at camera-ready) → References → Appendix/supplementary (unlimited) → **NeurIPS Paper Checklist**. Related work is NOT woven into the intro (that is the journal habit); it is its own section.
- experimental paragraphs: **bold run-in lead-ins** are the NeurIPS signature — "**Models.**", "**Datasets.**", "**Baselines.**", "**Metrics.**", "**Implementation Details.**", "**Evaluation.**" — instead of deep subsection numbering.
- math/display: density is sub-genre-dependent (see acceptance-bar). Define-before-use throughout. Numbered equations for anything referenced later.
- theorem apparatus: **only theory-forward papers carry it** (To Believe: named Assumptions/Definitions/Theorems, proofs in an appendix, "the proof is given in Appendix D"). Systems/methods papers have ZERO theorems and deliver the method as prose "Stage 1/Stage 2" paragraphs, a code listing, or a pipeline schematic — do NOT add theorems to a method paper, and do NOT strip proofs from a theory paper.
- tables: booktabs (top/mid/bottom rules, NO vertical rules); **BEST value in bold** (often second-best underlined); table caption ABOVE the table. Numbers as ratios ("6.5x"), perplexity/accuracy to 2 decimals, calibration metrics (AUROC/AUPR) to 3.
- figures: figure caption BELOW the figure, self-contained. Architecture/pipeline SCHEMATICS are first-class in systems/interp papers (not decorative); line plots (scaling/calibration curves), value-labeled bar charts, and heatmaps are the core idioms. matplotlib-default palette; color+linestyle/marker redundancy for grayscale survival. Single-column NeurIPS layout (5.5in). No (a)/(b)/(c) letters is common; positional/caption labeling instead.
- code / data availability: expected — a repo link in the abstract, intro, or appendix (5 of 6 papers state one). A released benchmark/dataset (ParamMute's CoFaithfulQA) is a first-class contribution with human-agreement validation.
- deployment reporting (systems sub-genre): throughput/latency in a real serving framework (SGLang, vLLM), hardware named (A100/H100), often with third-party-run results credited.

## acceptance-bar
Detailed categorical form in `review/{rubric,reviewer-profiles,scoring}.md` (no numeric scores). Summary (also the keynote effort prior):
- reviewers reward: a clear, quantified advance on named benchmarks; real, fairly-reproduced baselines (reproduce-then-compare); ablations that isolate the mechanism; honest scope + failure reporting; reproducibility (hyperparameters, seeds, hardware, code); a completed, honest paper checklist. For theory papers: correct proofs with stated assumptions AND empirical confirmation. For UQ papers: calibration metrics (AUROC/AUPR/AURAC) across models×datasets with significance. For a benchmark contribution: documented construction + inter-annotator agreement.
- reject triggers: gains only on the benchmarks the method wins; missing/undertuned primary baselines; an efficiency/throughput claim without hardware or with omitted costs; generality claimed beyond the tested regime; a theoretical claim without proof or without empirical confirmation; single-run point estimates where variance is load-bearing; no reproducibility path; a missing or dishonest checklist (checklist absence = desk reject).
- novelty/significance bar: a clear methodological/analytical advance demonstrated quantitatively, of interest to the broad ML community. Broad interdisciplinary appeal is a plus but a strong efficiency/inference result on canonical benchmarks suffices.

## limits
- main text ≤ 9 pages including figures (NeurIPS 2024 rule; acknowledgments + references + appendix do NOT count). Supplementary/appendix is unlimited — overflow (proofs, extra experiments, full benchmark docs) goes there.
- abstract one paragraph, ~150–220 words.
- the NeurIPS Paper Checklist is MANDATORY at submission and camera-ready ("papers not including the checklist will be desk rejected"); Limitations, Broader Impacts, and funding/competing-interests disclosure are part of the venue's required apparatus.
- official single style file `neurips_2024.sty` (bundled in `assets/paper-skeleton-neurips/`); tweaking margins/fonts is grounds for rejection.

## anchors
- register narrative + negative space (what NeurIPS does NOT do) + 6-paper roster (by sub-genre): overall.md
- before→after section few-shots (verbatim published "after"): abstract.md, introduction.md, results.md, methods.md, discussion.md
- panel kit (categorical, no numeric scores): review/{rubric.md, reviewer-profiles.md, scoring.md}
- per-paper evidence dossiers: papers/{2503.01840v3 (EAGLE-3), 2404.14469v2 (SnapKV), 2404.00456v2 (QuaRot), 2502.15543v4 (ParamMute), 2406.02543v2 (To Believe or Not to Believe), 2405.13845v3 (Semantic Density)}.md
- LaTeX skeleton (official class): assets/paper-skeleton-neurips/ (master.tex + neurips_2024.sty bundled)
