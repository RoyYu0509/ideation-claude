<!-- SIAM-family CORE venue contract. NOT resolved on its own: it is COMPOSED with a sub-brand overlay
     (SISC | SINUM | MMS) whose own profile.md OVERRIDES/EXTENDS the fields below. The resolver loads
     SIAM/_core/* + SIAM/<sub-brand>/* and threads the composed contract into every reviser/reviewer/AC.
     This file holds only what is INVARIANT across the SIAM applied-/computational-math family (Tier A),
     plus the negative-space pointer (Tier C). Anything that VARIES by sub-brand (theorem density, proof
     placement, tables-vs-figures, performance reporting, figure conventions) lives in the overlay, NOT here.
     Synthesized from 10 arXiv math.NA papers; per-paper evidence in ../papers/. Keep all seven blocks. -->
# Venue profile (CORE) — SIAM family / applied & computational mathematics

## identity
- venue: SIAM journals (applied & computational mathematics family). Resolve WITH a sub-brand overlay.
- sub-brands: SISC (Scientific Computing — computation-forward) · SINUM (Numerical Analysis — analysis/proof-forward) · MMS (Multiscale Modeling & Simulation — multiscale/mixed). Pick the overlay; this core is shared.
- field: applied math, numerical analysis, scientific computing, scientific ML.
- type: specialist methods/analysis journals (NOT broad-audience).
- audience: applied mathematicians & computational scientists; assume PDE / numerics / functional-analysis fluency.

## register
Technical-first, precise, restrained, quantitative. Definitions, equations, error/convergence behavior, and
benchmarks carry the prose. First-person plural drives the narrative ("we propose / derive / observe");
passive voice is reserved for mathematical objects and attributed prior results. Mechanism is stated
soberly; claims are calibrated to evidence and failures are reported honestly. No broad-audience framing,
no hype. (How equation-vs-experiment weight is balanced is set by the sub-brand overlay.)

## vocabulary
### venue-acceptable in moderation
Normal technical usage here; flag only the vague / non-technical / over-used case. (See voice.md "negative space" for what this venue refuses outright.)
- robust / robustness — technical sense OK ("robust to noise"); flag a vague "robust framework" with no referent.
- efficient / efficiency — OK when tied to a complexity or wall-clock claim; flag as a bare adjective.
- framework / approach / method — OK as plain labels for the contribution; flag only marketing use.
- significant / significantly — quantified/statistical sense OK; flag as a vague intensifier.
- comprehensive / systematic — OK for a genuinely exhaustive study; flag as empty filler.
### venue-stricter
- novel / novelty — used sparingly here; prefer to let the contribution speak. Flag "novel" as self-praise.
- (no "breakthrough" / "state-of-the-art" as hype — see voice.md negative space.)

## conventions
- spelling: American (Acknowledgments, not Acknowledgement; optimization, not optimisation).
- references: NUMBERED BRACKET [n], author-sorted list; dense clusters (3–8 keys) per claim are normal; sub-item precision is expected ("[4, Theorem 5.6]", "[11, Sec. 7.2]"). No author-year.
- title: descriptive "Method for Problem" or "ACRONYM: expansion". NOT a declarative finding-title; no rhetorical question.
- abstract: single unstructured paragraph, funnel shape, ~150–220 words, opens "We propose/analyze/…"; "Abstract." small-caps lead-in; key qualitative or quantitative claim, no marketing.
- front matter: "MSC codes." + "Key words." block immediately after the abstract (bold label + period). (Some preprints omit; the submission version requires them.)
- sections: Introduction (funnel → ends with a "the paper is organized as follows" outline paragraph) → Formulation/Methods → Results/Numerical Experiments → Conclusions. Related work is WOVEN INTO the introduction (method-family survey, often bold-lead-in paragraphs), NOT a standalone section (exception: ML-adjacent papers may use an explicit Related Work subsection). Conclusions = past-tense summary + advantages + brief future work; NO broader-impact statement.
- math/display: display equations frequent and grammatically INTEGRATED into sentences (lead-in colon/comma, "where …" clause after); every symbol defined before first use; an explicit "Notation." paragraph up front is common.
- micro-structure: bold non-numbered RUN-IN lead-ins ("**Setup:**", "**Decay of strains.**", "Mark./Refine.") organize dense passages instead of proliferating sub-subsection numbers.
- cross-reference & typography: "§" and "Section N" both used; "cf." points to the authors' OWN results, not external citations; proofs end with □ (occasionally ⊠); internal hyperlinks rendered blue and survive into the published version.

## acceptance-bar
Detailed, calibrated form lives in the sub-brand overlay's review/ kit. Core summary (also the keynote effort prior):
- reviewers reward: rigorous validation appropriate to the sub-brand (convergence/error analysis OR numerical benchmarks OR proved guarantees); fair, reproduced baselines; honest scope; reproducibility.
- reject triggers: insufficient or cherry-picked evidence; missing/unfair baselines or analysis; claims not backed by error metrics or proof; overselling generality beyond what is shown.
- novelty/significance bar: a clear methodological/analytical advance demonstrated rigorously. Broad interdisciplinary appeal is NOT required (specialist venue).
- panel kit: <sub-brand>/review/{rubric.md, reviewer-profiles.md, scoring.md}.

## limits
- abstract ~150–220 words; concision rewarded; no hard main-text page limit. (Format specifics per overlay.)

## anchors
- micro prose voice + NEGATIVE SPACE (what SIAM does NOT do): voice.md
- invariant macro skeleton + argument arc: structure.md
- register narrative + 10-paper roster (by sub-brand): overall.md
- per-sub-brand: profile.md (deltas) + before→after section few-shots + figures.md + review/ kit
- per-paper evidence dossiers: ../papers/*.md
