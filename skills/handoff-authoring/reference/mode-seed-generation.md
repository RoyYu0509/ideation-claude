# MODE: seed-generation (round 0) — first author of HANDOFF.md from the picked seed

You are in **round 0**: there is no prior `HANDOFF.md` and no review ledger on disk. You author the
work order for the FIRST time, straight from the one seed the owner picked. Read the skill's `SKILL.md`
(§1–§6 + the §4b/§4c contracts + the authoring discipline) first; this file gives you only this mode's
INPUTS and the round-0-specific BEHAVIOR on top of it.

## INPUTS
- The picked /research seed at `<SEED_FILE>` — the single source for the work order's content.
- The substitution values your goal lists (`<RUNS_ROOT>`, `<SLUG>`, `<VENUE_LABEL>`, `<REVIEW_SPEC>`,
  `<CITATION_SKILLS>`, `<MIN_INTRO_CITATIONS>`, `<MIN_TOTAL_CITATIONS>`, `<FIGURE_SKILLS>`, `<REQUIRE_FIGURES>`).
- The researcher's profile at `<PROFILE_FILE>` — read `recent_direction`; extract ONLY numbers/phrases actually
  stated (a "within a day"/"a week" phrase parses directly; an "N sessions" phrase with no hour phrase becomes
  `N * <SESSION_HOURS_ASSUMPTION>` hours) into §4b's `budget_envelope`, NEVER invent one. If the file is absent,
  `budget_envelope` is all-null with `source: "no profile on disk"`.

## BEHAVIOR
1. **Read the seed in full, then author the COMPLETE `<RUNS_ROOT>/<SLUG>/HANDOFF.md`** per the skill's
   §1–§6 — drop or reorder no section. The seed's fields map onto the sections field-for-field:
   - WORKING TITLE / problem / gap → §1 RUN HEADER (+ pin every metric & data generator it names to a
     canonical code location: REUSE, DO NOT REIMPLEMENT).
   - "## Novelty Check" → §1b NOVELTY RISK.
   - "## Premise Ledger" (+ its `### Falsifier Analysis`) → §3's assumption ledger (each `P<n>` row becomes a
     named, sourced assumption; VERIFIED rows carry their quote, UNVERIFIED rows carry their probe) AND §4:
     every UNVERIFIED premise's probe is authored as a premise-check K criterion + a Phase 0 check in §5, so
     PHASE0_KILL_OR_CONFIRM tests the PREMISE before the method. Asset rows (`A<n>`) pin §5's reuse/fallback.
   - the seed's `## Verification Record` block (2026-07-11 verified-kill vintage — machine-derived from the
     weekly loop's bundle + independent recheck) is BINDING INPUT on the same sections: probe-VERIFIED
     premises cite their executed-probe evidence (probe dir + values); every UNVERIFIED row (= a deferred
     probe) is ALWAYS MANDATORY — a two-sided §4 K + a Phase-0 check in §5; the frozen falsifier thresholds
     (with src anchors) are the §4 kill numbers, never re-anchored or relaxed; the Record's kill history names
     DEAD adjacent directions the work order must not drift toward. (Pre-redesign seeds carry no Record — the
     generic Premise Ledger rule above already covers them.)
   - HYPOTHESIS + PREDICTIONS / mechanism → §3 CORE HYPOTHESIS (H1 + sub-claims H1a…).
   - KILL CRITERION + sharp falsifier + 🔴 Priority Issues → §4 (two-sided, numeric, [GAMBLE]/[TECHNICAL]/[EXPECTED] tags).
   - BASELINES + SCOPE + FIRST EXPERIMENT → §4b SCALE-CONTRACT and §5 EXECUTION PLAN (incl. each K's
     `evidence` block — declare the WEAKEST applicable type, judged relative to the K's claim domain per
     SKILL.md §4b; the seed's validation plan names what the anchors will actually measure, on what; ALSO
     compute each K's `scale_size` mechanically from the SAME under_test/control counts you just wrote, and
     stamp §4b's top-level `budget_envelope` from `<PROFILE_FILE>` per the INPUTS note above).
   - the central promise behind the WORKING TITLE → §4c AMBITION CONTRACT.
   - FIRST EXPERIMENT / BASELINES / SCOPE / OPEN QUESTIONS → §5 Phase 5 segments
     (author them via `reference/phase5-experiments.md`).
2. **The contracts are DRAFTS this round, not yet locked.** Author §4b/§4c by FORMALIZING the baseline
   landscape + scope the seed already carries — pin and grid them into the machine-readable schemas; do not
   re-research what the seed researched. They are LOCKED only at Phase 0(C) (per §4b/§4c), after the Phase-0
   toy confirms the riskiest [GAMBLE]; until then they are the binding design, refinable by Phase 0.
3. **Seed the open-concern ledger.** Round 0 is the SETUP-ONCE role: derive the initial
   `TASK_STATUS.concerns.json` + markdown `TASK_STATUS` from the §4 kill criteria (one open concern per K),
   in the canonical container your goal's LEDGER CONTAINER contract pins (`{ "open_concerns": [ … ] }` — a
   bare array or any other shape is read as EMPTY downstream and silently drops your kill criteria).
   Run no per-round reference disclosure — there is no prior frozen snapshot yet.
4. **§4b deserves the most care** — it is the binding, machine-checkable definition of FULL INTENDED SCALE
   the whole loop rests on. Follow the skill's §4b in full; never author a secretly-toy or single-point grid.

## OUTPUT
The complete `<RUNS_ROOT>/<SLUG>/HANDOFF.md` on disk. Return the small status envelope only.
