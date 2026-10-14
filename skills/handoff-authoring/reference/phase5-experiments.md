# Phase 5 — Experiments & ablations (segment rubric)

Authored against `SKILL.md` §5 Phase 5. Render Phase 5 of `HANDOFF.md` as the ORDERED segment list
specified below.

**PURPOSE** — turn the seed's experimental plan into the binding work unit the experiment milestones execute:
an ORDERED list of bounded SEGMENTS (E1, E2, …), one per experiment/ablation, each a self-contained unit a
single worker finishes and checkpoints in one pass.

**WRITE** — one segment per experiment/ablation drawn from the seed's FIRST EXPERIMENT / BASELINES / SCOPE /
OPEN QUESTIONS. Order them so dependencies run earlier; tag each `INDEPENDENT` (may run in a parallel batch) or
`DEPENDS-ON:<id>`.

## Required publication-grade axes (completeness, not code-validation)
Beyond the main experiment + baselines + ablations, Phase 5 MUST carry a segment for EACH axis the claim type
admits:
- stability / robustness
- parameter-sensitivity
- error / convergence analysis
- structure-preservation properties (for a structure-preserving claim)
- computational-cost / efficiency

Mark an axis the claim genuinely does not admit `[N/A: <reason>]`. **Absent ≠ N/A** — an axis with neither a
segment nor an explicit N/A reason is an INCOMPLETE work order (the verifier FAILs it). Each axis must serve the
core claim, never pad.

## Per-segment schema
Each segment carries:
- **SEGMENT ID** — stable (E1, E2, …).
- **CORE HYPOTHESIS** tested.
- **KILL criterion.**
- **EXECUTION PLAN** — script/template, FULL config, expected_result, evidence argument.
- **INTEGRATION TARGET** — which table/figure/section + a body paragraph that argues it.
- **METRIC DEFINITIONS** — pinned to code (REUSE, do not reimplement).
- **DISCRIMINATIVE SANITY** — must include ALL of:
  - (a) cross-validation of two independent computation paths;
  - (b) an INPUT non-degeneracy assertion — the data source must not be analytically trivial for the claim
    being tested (not exact-linear / zero-variance / rank-zero);
  - (c) a CLAIM-CORRESPONDENCE assertion — name the ONE load-bearing structural property the segment's CORE
    HYPOTHESIS asserts of the METHOD, and a deterministic in-code check the AUTHORED code actually exhibits it,
    evaluated at the EARLIEST point it is decidable (a STRUCTURAL property → on the code at author time, before
    the science run; a BEHAVIORAL one → on the run output). Examples: a "nonlinear" claim ⇒ the forward operator
    is state-dependent, assert A(u1) ≠ A(u2) for distinct states; an "assimilation lowers error" claim ⇒ adding
    the observations must reduce the metric vs the no-observation run; a "structure-preserving" claim ⇒ the named
    invariant stays conserved.
- **PRE-DECLARED STOP POINTS** — exactly where THIS segment may halt and surface (which Sx + on what evidence):
  kill-criterion fail → S1, baseline ≥ method → S2, resource/credential wall → S3, proxy degeneracy → S9.
- **DONE MARKER** — finished only when `EXPERIMENTS/<id>/result.md` exists + a commit bundles its
  code/result/paper edit.

**WHY discriminative sanity is mandatory** — a real number from a method that does NOT satisfy its own
claim-correspondence assertion is the worst failure mode: it clears every provenance gate yet tests nothing the
claim is about, so a violation is S9 (the experiment does not implement the claim), surfaced — NEVER a silently
reported number. (b) catches a degenerate INPUT; (c) catches a method whose STRUCTURE/BEHAVIOR does not match
the claim's load-bearing word — both are required, neither substitutes for the other. A sanity check that only
verifies two implementations agree on a degenerate input is not discriminative.
