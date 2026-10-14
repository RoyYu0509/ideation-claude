<!-- polish-abstract-score.md — the abstract+title candidate JUDGING rubric (/polish runAbstractSection).
     SSOT for the reviewer that judges ONE candidate (or the original) with TWO disqualifying gates
     (fidelity + ai-tells) BEFORE the comparison is weighed, then returns ONE CATEGORICAL head-to-head
     verdict vs the ORIGINAL (dossier-12 G3 — no numeric scores anywhere; owner doctrine). The JS picks
     categorically (do-no-harm: only clearly_better ships over a clean original). Extracted out of
     spec/polish.js (runAbstractSection's per-candidate judging goal-builder); the slim goal READS this
     file, substitutes the <TOKENS> below, appends the venue preamble + the reviewer thinking block, and
     passes it as the reviewer goal. It returns ABSTRACT_SCORE_SCHEMA (enforced at the call site).
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <CAND_ID>        the candidate id being judged (an emitted candidate or "original")
       <TITLE>          the candidate title
       <ABSTRACT>       the candidate abstract
       <ORIG_TITLE>     the ORIGINAL title (the head-to-head baseline)
       <ORIG_ABSTRACT>  the ORIGINAL abstract (the head-to-head baseline)
-->

Judge this abstract+title candidate (id=<CAND_ID>) for the paper against section-abstract
+ house-style. TWO disqualifying gates run BEFORE the comparison is weighed:
  (1) fidelity — meaning preserved vs the paper; if it drifts, set fidelity_ok=false.
  (2) ai-tells — retrieve check-ai-tells and apply its ZERO-TOLERANCE gate: any surviving
      em-dash or banned-vocabulary hit, or an interchangeable / template-leaked abstract, sets
      ai_tells_clean=false. This DISQUALIFIES the candidate exactly like a fidelity drift — no
      head-to-head win rescues a dirty candidate.
Then return ONE categorical verdict `vs_original` — the candidate compared to the ORIGINAL below,
as a whole (logic, results-truthfulness, readability, venue register; do NOT reward number-dumping —
a precise qualitative finding is not penalized for lacking a quantitative point):
  - `clearly_better`    — a reader at this venue would visibly prefer it; the improvement is
                          load-bearing (sharper gap/mechanism/claim), not cosmetic.
  - `marginally_better` — better, but the difference is cosmetic/taste; replacing would be churn.
  - `not_better`        — equal or worse on any load-bearing axis.
  - `baseline`          — ONLY when <CAND_ID> is `original` (you are judging the original itself:
                          gates still apply; the comparison is vacuous).
Ground the verdict in `why` (one sentence — which axis carried it). NO numeric scores. Return the schema.

TITLE: <TITLE>

ABSTRACT: <ABSTRACT>

ORIGINAL TITLE (baseline): <ORIG_TITLE>

ORIGINAL ABSTRACT (baseline): <ORIG_ABSTRACT>
