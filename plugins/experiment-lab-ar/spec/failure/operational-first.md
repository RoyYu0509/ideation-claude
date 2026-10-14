# Operational-first failure handling — S1 / S2 / G2

Read this when a **kill criterion FAILs (S1)**, a **baseline beats your method (S2)**, or a **sanity item is
wrong (G2)**. You do all of this in your own context — no sub-spawn, no laundering.

**The zeroth check — did the run COMPLETE at all?** A run that DIED (crashed, was killed, never finalized) is
not a FAILED criterion — falsification requires a COMPLETED run's measured numbers. Triage the death per
`transient.md` FIRST (an environment-transient death is not evidence of anything); only a completed full-scale
run enters G1–G3 below.

**S1/S2 are operational until proven otherwise.** A failed kill criterion (S1) or a winning baseline (S2) is
almost always operational, NOT a science failure — most often the run was under-scaled, or a parameter / metric /
split was wrong. Do not try to classify "is this a real science failure?" — that judgment is unreliable. Instead
rule out the operational causes **by action**; only what survives every one of them is genuine. Before a
falsification may be called genuine, ALL of these must already hold (each re-run fires DETACHED, per the
protocol's §4 mechanical contract):

- **(G1) full intended scale.** The failing run met the locked SCALE-CONTRACT (HANDOFF §4b) in FULL: the
  `under_test` sweep AND every gridded control, NOT a reduced / smoke / toy / single-point run. An under-scaled
  or single-control run that fails is never a science failure → re-plan to the full contract (`remediation.md`)
  and re-run. This is the single most common false alarm — check it FIRST. (The L0 scale audit enforces this
  mechanically: a verdict whose run missed the contract is VOID — neither a FAIL nor a PASS.)
- **(G2) sanity checklist passes.** Correct metric, correct train/test split, no off-by-one, seed variance ruled
  out (≥ this run's §4b SCALE-CONTRACT seed floor), parameters inside the planned range (a hyperparameter sweep was tried). Any item wrong →
  operational → fix and re-run.
- **(G3) your own diagnosed fix applied and re-run.** The fix you would otherwise have recommended is actually
  executed and re-run, not merely noted. SCOPE: a G3 fix is a change to a **producing-artifact** (the experiment /
  model / config / harness), never to an **audit-artifact**. If the failing thing is a gate / sanity /
  pre-registered criterion (it told you the science did not hold), do NOT rewrite it — see `gate-integrity.md`.

**Auto-fixing operational causes (G1–G3) never surfaces to the owner — that is the entire point of this loop.**

**Genuine failure** (survives G1–G3 — the same hypothesis is still falsified at full scale, with correct setup,
after the fix was tried): now the routing splits by WHICH criterion fell — central or peripheral. This is the one
branch operational-first does NOT collapse into a single reflex.

- **CENTRAL — a `[GAMBLE]` K, or the K backing the headline contribution.** A genuine full-scale,
  contract-audited, pre-registered-anchor FAIL of a central K is NOT yours to absorb. Do NOT mark the milestone
  DONE and do NOT record it as a routine negative you can report. A negative that CONTRADICTS the spec's novelty
  claim is not a deliverable — it means the DIRECTION is dead. RETURN it as an **S1 in `escalations[]`** (at the
  wave boundary, per the protocol's §2.3) so L0 runs `research-rescue` — the system tries HARD to retain the
  ambition by real work BEFORE anything narrows, and only the documented residual of a FAILED rescue reaches the
  owner for the kill-or-redirect decision. You record the evidence (what was tried at full scale, the exact
  numbers, why it failed) in RESEARCH_LOG.md so the rescue worker can read it; you do not yourself narrow,
  reframe, pivot, or kill the claim.
- **PERIPHERAL — a `[TECHNICAL]` / `[EXPECTED]` K, or an S2 baseline loss on a non-headline axis.** Record it as
  a **fact** in RESEARCH_LOG.md (what was tried at full scale, the exact numbers, why it failed) and record the
  segment's `result.md` as a negative outcome. It is a steering signal for the next round —
  **never the headline and never the contribution**. You do not reframe the spec around it — that is the
  downstream review stage's job; you only record it and advance. Treat the milestone as DONE; the owner reads it at the review
  stage, not now. A peripheral S1/S2 is NOT placed in `escalations[]`.

**The honest hard-stop (a confidently-falsified central contribution).** When the central novel contribution is
CONFIDENTLY falsified — it survived operational ruling-out (G1–G3) AND a `research-rescue` attempt FAILED to
retain it — the pipeline does NOT continue and does NOT pivot. It STOPS and surfaces to the owner a CLEAR
statement of EXACTLY HOW the central contribution was falsified: the criterion, its pre-registered threshold, and
the observed numbers. The owner manually confirms the stop (kill) or chooses redirect. The system already
attempts rescue before surfacing, so a confidently-falsified central contribution that reaches the owner is very
likely genuinely not viable — surface it honestly, never bury it or reframe it as a smaller win.

**Phase 0 is not an exception.** The toy probe is sub-full-scale, so it may confirm-to-proceed or fail-fast on an
operational catastrophe (NaN / divergence / wrong-sign / broken setup), but it may NOT render a science kill: a
toy that looks falsified routes into REMEDIATION (confirm the `[GAMBLE]` K at the full SCALE-CONTRACT, cleared by
the L0 scale audit) before any S1. This is the same central rule as above, reached the long way: only a
full-scale, contract-audited, pre-registered-anchor FAIL of a central K is returned as an S1 in `escalations[]`
(→ L0 rescue → owner) — never a toy FAIL, which alone never kills the idea.

**S3 / S9** (resource wall / scientific-proxy degeneracy) are different — RETURN them in `escalations[]`, do not
guess. See `remediation.md` (S3) and `claim-correspondence-fail.md` (S9).
