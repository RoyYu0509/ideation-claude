# MODE: round-update (rounds 1+) — re-author HANDOFF.md from the round's findings

You are in **rounds 1+**: a `HANDOFF.md` already exists and a review just finished. The L0 state machine
re-spawned you to RE-AUTHOR the work order from this round's findings. Read the skill's `SKILL.md` first
(same §1–§6 structure + the §4b/§4c contracts you evolve); this file adds the per-round ratchet discipline
on top of it.

## RE-AUTHOR mode — the meta-loop's significance engine

The work order is authored TWICE-over: once at round 0 (the initial seed→HANDOFF conversion) and again on
EVERY loop round after a review. Both modes produce the SAME STRUCTURE; this mode adds the rules below.

- **WHY RE-AUTHOR, not append** — a loop that merely appends each round's demands produces trivial,
  incremental, "preventive" rounds (the exact failure this mode fixes). Each round must be a SIGNIFICANT step.
  Hold the WHOLE prior work order in context and RE-AIM it at the round's root finding.

## INPUTS (read every one that exists, all under `<RUNS_ROOT>/<SLUG>/`)
- `HANDOFF.md` — the PRIOR work order; the version you evolve (do not start from a blank).
- `HANDOFF-*.md` — this round's review-demanded sidecars: `HANDOFF-redesign-<seg>.md` = a validity defect to
  RE-AUTHOR that segment around; `HANDOFF-<id>.md` = a new exhibit / missing work item; `HANDOFF-amplify-*.md` =
  the amplifier's EARNED ambition raise; `HANDOFF-ambition-*.md` = a research-rescue gap. FOLD every one in.
- `TASK_STATUS.concerns.json` + `VERIFICATION-REPORT.md` — the open-concern ledger + verifier findings. Use them
  to locate the ROOT cause (a hypothesis that is actually WRONG; an experiment that DRIFTED off the claim it was
  meant to test; a missing baseline / regime) and re-aim the work order at it — do not paper over the symptom.
- `HANDOFF.ambition.target.json` — if present, the amplifier's earned target; RAISE the §4c claim to it.
- `EXPERIMENTS/*/result.md` — each segment's durable marker; read its **`OBSERVATIONS`** note for any off-plan
  positive anomaly the experiment worker flagged (an unexpected regime, a next question). When one genuinely earns
  a re-aim, fold it in as a §4b REDIRECT (honestly close the old bet + author a fresh anchor), NEVER as a
  WEAKEN-TO-PASS.
- The researcher's profile at `<PROFILE_FILE>` — re-read `recent_direction`; if the stated budget genuinely
  changed since round 0 (the owner widened it at a `CAPACITY_READOUT`/`central-narrow` gate, say), re-stamp
  §4b's `budget_envelope` (a RAISE if widening, always allowed; a narrowing needs the same owner-approved
  disposition any other §4b WEAKEN would).

## THE RATCHET — what you MAY and MAY NOT change
The locked baselines are IMMUTABLE; a PreToolUse hook + the verifier enforce this.
- `HANDOFF.scale-contract.locked.json` and `HANDOFF.ambition.locked.json` are the FROZEN ratchet baselines
  (locked at Phase 0(C), bin/-owned). A `hooks/lock_guard` PreToolUse hook hard-denies any Write/Edit to them, so
  overwriting is structurally impossible; your re-authored §4b/§4c live ONLY in HANDOFF.md.
- Your re-authored **§4b** may legally differ from its baseline by: TIGHTEN, an evidence-backed SIMPLIFY, or a
  declared REDIRECT (change the claim/K — honestly close the old bet, author fresh anchors) — see SKILL.md §4b.
  `evidence.type` may move only TOWARD `direct` (a TIGHTEN); away from it is a WEAKEN-TO-PASS unless part of a
  declared REDIRECT.
- Your re-authored **§4c** may legally RAISE or PIVOT (a different, EQUALLY-ambitious claim) — see SKILL.md §4c.
- **FORBIDDEN: a silent WEAKEN-TO-PASS (§4b) or NARROW-TO-DELIVERED (§4c).** The per-round verifier diffs your
  work order against the untouched baselines and FAILs any un-evidenced loosening. When the evidence genuinely
  demands a RETREAT, do NOT enact it here — leave the claim; the verify_final reconciliation + research-rescue
  own any honest narrowing (owner-approved), never this re-author.

## OUTPUT
Overwrite `HANDOFF.md` with the complete re-authored work order (same section shape as a first authoring). Touch
NOTHING else — not the drafted `paper/`, not the living logs, not any `EXPERIMENTS/`
result. The L0 machine consumes the sidecars (rm) and re-opens the experiment milestones after you return.
