<!-- SIAM-family CORE prose voice (micro level) + NEGATIVE SPACE (Tier C). Consumed by polish-prose (to
     write toward), check-readability (fluency), and check-ai-tells (to flag). Invariant across SISC/SINUM/MMS.
     The negative-space list is the highest-value half for an AI reviser, which tends to ADD exactly these.
     Evidence: 10 math.NA papers in ../papers/. -->
# SIAM family — prose voice & negative space (CORE)

## The voice (what to write toward)
- **First-person plural drives the narrative.** "We propose / derive / construct / observe / report." Singular "I" never; impersonal "one" rare. Passive is reserved for (a) mathematical objects ("the operator is defined by …") and (b) attributed prior results ("it is shown in [11] that …").
- **Equations are parts of sentences, not interruptions.** A display equation is introduced with a colon/comma and followed by a "where …" clause that defines its symbols. The prose reads continuously through the math.
- **Calibrated hedging, never vague hedging.** Uncertainty is stated precisely and tied to a mechanism, not sprinkled as filler. The paper says exactly how strong a claim is.
- **Honesty about limits and failure is a feature.** Authors state where the method loses, why, and what is out of scope — often in the introduction, not buried.
- **Restraint.** The contribution is allowed to speak; adjectives are earned by numbers or proofs.
- **Sentence rhythm varies** — short declarative claims interleaved with longer setup/derivation sentences. Not uniform, not list-like.

## Verbatim exemplars (paper id in brackets)
- Calibrated hedge tied to evidence: "experimental evidence … seems to suggest that the predictions are for the most part in good agreement with the data, especially when an additive noise model is considered." [2510.14197]
- Precise priority claim, not hype: "The simultaneous estimation of all of those quantities of interest … has not been demonstrated to our knowledge." [2510.14197]
- Parallel "We"-led contribution bullets: "We computationally learn an observation-to-parameter map …" / "We develop a computational framework …" / "We provide a detailed performance analysis …" [2510.14197]
- Honest reporting of a loss (calibrated honesty): the authors explicitly report and explain the case where the baseline (FNO) outperforms their method, hedged mechanistically ("may be attributed to …"). [2504.18513]
- Differentiation from the closest competitor by enumerated points: "The differences between our approach and NPE are that, first … Second … Third …" [2510.14197]

## NEGATIVE SPACE — what SIAM prose does NOT do (flag aggressively if present)
- **No marketing superlatives:** "breakthrough", "state-of-the-art", "remarkable", "powerful", "cutting-edge", "novel" as self-praise.
- **No broader-impact / significance inflation:** no closing paragraph selling societal/transformative importance; conclusions stay technical (summary + advantages + future work).
- **No hype connectors as glue:** "Importantly,", "Notably,", "Crucially," used to manufacture emphasis.
- **No efficiency/GPU bragging in analysis-leaning work** (SINUM/MMS theory papers): convergence rate is the currency, not wall-clock. (SISC computational papers DO report performance — that is an overlay rule, not hype.)
- **No British spelling** (normalize -ise→-ize, "Acknowledgement"→"Acknowledgments", "behaviour"→"behavior").
- **No interchangeable AI-template openings** (every paragraph starting "Furthermore,/Moreover,/In addition,"; mechanical "First, Second, Third" when not enumerating a real list).
- **No claim untethered from evidence:** an adjective ("accurate", "robust", "efficient") with no number, proof, or referent behind it.
