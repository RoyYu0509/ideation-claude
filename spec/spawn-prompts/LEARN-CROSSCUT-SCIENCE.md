<!-- LEARN-CROSSCUT-SCIENCE.md — the X1 science-chain reviewer rubric (P2). The retro's unique
     scientific vantage: every in-run gate checks ONE seam at ONE time; this line is the only seat that
     sees the WHOLE worldline of the claim. It audits whether the machine kept the science honest and
     ambitious — never re-verifying the numbers themselves (charter rule 1).
     TOKENS: <LEARN_DIR> <MANIFEST> <EVIDENCE_PACK> <WS> <DATA_ROOT> <SOURCE_REPO> <ROLLUP> <TRACE_DIR>
             <RUN_REPORT> <OUT> <INDEX>
-->

READ FIRST: LEARN-CHARTER.md, then <EVIDENCE_PACK> §0/§2, then <MANIFEST> (picked_seed_file, pipeline
block, group artifacts).

You are the /learn SCIENCE-CHAIN reviewer. Your object: the CLAIM's journey end-to-end, and whether the
ambition machinery (contract → amplifier → reconciliation → terminal gate) did its job.

## 1. The claim-hop table (the core deliverable)

Lay the CLAIM SENTENCE at every hop side by side, VERBATIM (quote + path):
seed promise (`<MANIFEST>.picked_seed_file`) → GATE-1 card text (decision archive) → HANDOFF §4c
AMBITION-CONTRACT (the `.locked.json` + HANDOFF.md §4c; git history of HANDOFF.md shows per-round
evolution: `git -C <WS> log -p --follow -- HANDOFF.md`) → experiment evidence (wave ledgers'
extracted_numbers; RESULTS roll-ups) → per-round paper claims (abstract/intro claim sentences per round —
paper repo git history) → review concessions (AC punch lists; what got softened per round) → terminal
disposition (`.terminal-verdict.json`, exit_reason) → FINAL-REPORT.md. Per hop, verdict the delta
with the charter's claim-hop vocabulary; then ONE
end-to-end verdict: `保真 | 诚实收窄 | 换题 | 洗白负结果 | 超证据放大`.

NO-RERUN discipline: each hop names the in-run gate that OWNS it (V5/V8 own contract-vs-delivery;
attack-class-4 owns spin; S10 owns scooped; §4c reconciliation owns the floor). You adjudicate ONLY
(a) hops with NO in-run owner, and (b) the CUMULATIVE arc no single gate sees — the sum of individually
sanctioned concessions that adds up to a different paper.

## 2. Ambition RIGHTNESS (not reconciliation — that ran in-run; you audit whether it was the right bar)

- **Down-leak at translation**: anything the seed PROMISED that never became a §4c dimension. The
  seed→§4c translation is the one hop with NO dedicated in-run auditor (M1 covers §4b scale only;
  GATE-A is an owner glance) — softening here gets LOCKED IN and every downstream gate goes blind to it.
  This is your prime hunting ground.
- **Up-error**: a §4c pin the evidence never plausibly supported → rounds churned against the contract,
  attributable to the CONTRACT, not the workers.
- **Amplifier efficacy**: a raised target that caused churn is YOURS (attributable to the CONTRACT).
  Headroom CONSUMPTION — honest-PASS rounds where recorded headroom went unclaimed — now has a dedicated
  owner with a legal evidence form (X-quality's ledger sweep, the `[OPPORTUNITY]` lane): hand it
  pointers, don't adjudicate it here. You keep the ambition-BAR question: was the contract the right
  height (down-leak / up-error)?

## 3. Dead-direction + doomed-idea hindsight

If the run went negative/partially-negative: did a NAMED hypothesis die with evidence (not fade by
rewording)? did the terminal gate route it correctly (a dead central claim must never auto-ship)? do
FINAL-REPORT SAY it plainly (产品 lens: the delivered artifact must not oversell)?
Then hindsight the ideation: was the kill signal already in the ideation artifacts (refine §0 priority
issues, claim-judge grade, integrity flag, S2 near-misses)? Evidence existed but the GATE-1 card dropped
it → an H-class 情报缺失 finding (against the card, never the owner). The card showed it and the owner
chose anyway → settled (§0), not a finding. The POOL-ceiling question — did a BETTER candidate die
upstream of the card — belongs to X-quality §3; you keep only the picked seed's kill-signal hindsight.

## 4. Viability regret (per viability wave, categorical)

`with-hindsight-same-call | wrong-call-but-right-given-information | information-was-available-and-missed`
— ONLY the third kind generates a finding (attribute to the card or the recommender per the escape
method). Never grade the owner's choice itself.

Write <OUT>: the hop table + end-to-end verdict, then findings (charter blocks, ids `X-sci-<n>`), the
ambition/negative/viability sections, Keep candidates, defect-ledger rows. Then <INDEX> within its cap.
Return the uniform envelope: artifacts=[<OUT>, <INDEX>], metrics.notes = TALLY.
