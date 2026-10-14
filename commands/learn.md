---
description: Post-run learning/retro for auto-research — the 半递归自我改进 loop's review half. After a run finishes (or for any PAST run), /learn mechanically maps every artifact back to the component that produced it (+ which code version ACTUALLY ran, cache vs source), runs a CONDITIONAL blind venue-bar cold read of the shipped paper (the external calibration instrument), fans out read-only component-group reviewers + four cross-cutting lines (science claim-chain / economics / L0 enactment fidelity / quality-ceiling), adversarially verifies every serious claim by theme, synthesizes ONE dossier (repo dev/learning/) + ONE self-contained owner brief, ratifies proposals with the owner theme-by-theme via decision-file gates, and records accepted proposals as HYPOTHESES + the run's QUALITY-LEDGER record the next /learn must check. Reviews the MACHINE, not the paper; proposes only — fixes are built in a separate session from the ratified dossier. Resumable; runs in the instance DATA_ROOT.
argument-hint: optional target — a run_id prefix, a paper slug under runs/, or a workspace path (absent = the run in state/pipeline-state.json)
allowed-tools: Bash, Read, Write, Task, AskUserQuestion
---

You are the **L0 controller** of a post-run learning/retro pass. The phase sequence, the state model,
the spawn plans, and the ratification gates live in `spec/learn.js`; **reproduce it** (inlined below in
the Preconditions) as a main-session orchestrator, using Task subagents (single-context leaves) + Bash +
AskUserQuestion. This file does NOT restate the state machine — `spec/learn.js` + `config/config.yaml`
(`learning:` block) are the single source of truth. This file only tells you HOW to enact it.

Optional TARGET input (the raw text typed after `/learn`): `$ARGUMENTS`

## Preconditions

- Plugin root: !`echo "${CLAUDE_PLUGIN_ROOT:-unknown}"`
- Data root (= the instance folder /auto-research ran in): !`echo "${CLAUDE_PROJECT_DIR:-$PWD}"`
- Config (SSOT — the `learning:` block holds every /learn knob; never hardcode a value it defines): !`cat "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" 2>/dev/null || echo "(MISSING config.yaml — abort)"`
- L0 spec (the canonical source of truth — reproduce it): !`cat "${CLAUDE_PLUGIN_ROOT}/spec/learn.js"`
- Load-bearing rubrics/bins/assets present (any MISS ⇒ abort): !`r="${CLAUDE_PLUGIN_ROOT}"; for f in spec/spawn-prompts/LEARN-CHARTER.md spec/spawn-prompts/LEARN-EVIDENCE-PACK.md spec/spawn-prompts/LEARN-VENUE-COLDREAD.md spec/spawn-prompts/LEARN-COMPONENT-REVIEW.md spec/spawn-prompts/LEARN-CROSSCUT-SCIENCE.md spec/spawn-prompts/LEARN-CROSSCUT-ECONOMICS.md spec/spawn-prompts/LEARN-CROSSCUT-ENACTMENT.md spec/spawn-prompts/LEARN-CROSSCUT-QUALITY.md spec/spawn-prompts/LEARN-ADVERSARIAL-VERIFY.md spec/spawn-prompts/LEARN-SYNTHESIS.md bin/learn_resolve.sh bin/learn_manifest.py bin/learn_hypotheses.py bin/learn_quality_ledger.py bin/run_report.py bin/archive_decision.sh bin/validate_envelope.sh assets/learn-dossier-template.md assets/learn-hypotheses-schema.json assets/learn-quality-ledger-schema.json assets/decision-file-template.md spec/l1-envelope-schema.json; do test -f "$r/$f" && echo "ok  $f" || echo "MISS $f"; done`
- Run resolution (DETERMINISTIC — trust these KEY lines over any memory of the run; `ERROR` ⇒ surface it and stop): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; r="${CLAUDE_PLUGIN_ROOT}"; bash "$r/bin/learn_resolve.sh" "$d" $ARGUMENTS 2>&1 || true`
- Learn state (absent ⇒ a fresh retro; present ⇒ RESUME from its `phase`): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; r="${CLAUDE_PLUGIN_ROOT}"; ls="$(bash "$r/bin/learn_resolve.sh" "$d" $ARGUMENTS 2>/dev/null | awk '$1=="LEARN_STATE"{print $2}')"; if [ -n "$ls" ] && [ "$ls" != "new" ]; then cat "$ls"; else echo "(no learn-state — fresh retro)"; fi`
- Pending /learn decision file (if present, THIS turn is most likely its INGEST; shown ONLY when learn-state's `pending_gate` is set): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; r="${CLAUDE_PLUGIN_ROOT}"; ls="$(bash "$r/bin/learn_resolve.sh" "$d" $ARGUMENTS 2>/dev/null | awk '$1=="LEARN_STATE"{print $2}')"; if [ -n "$ls" ] && [ "$ls" != "new" ]; then g="$(python3 -c 'import json,sys;print((json.load(open(sys.argv[1])) or {}).get("pending_gate") or "")' "$ls" 2>/dev/null)"; if [ -n "$g" ]; then cat "$(dirname "$ls")/decisions/DECISIONS-PENDING.md" 2>/dev/null || echo "(pending_gate set but no DECISIONS-PENDING.md — re-render it from learn-state)"; else echo "(no pending learn gate)"; fi; else echo "(no pending learn gate)"; fi`

## Workflow

1. Reproduce `${CLAUDE_PLUGIN_ROOT}/spec/learn.js` (inlined above) with `PLUGIN_ROOT = ${CLAUDE_PLUGIN_ROOT}`,
   `PROJECT_DIR = ${CLAUDE_PROJECT_DIR:-$PWD}`, `target = $ARGUMENTS` (a single token; empty = default).
   Take every transition, every bin call, and learn-state persistence verbatim (`[[MECH]]`); reason ONLY
   at the two `[[SEAM:...]]` points (theme clustering; gate previews).
2. **Infer the entry point from the Preconditions**: a pending /learn decision file → INGEST its answer
   (chat wins over the file; archive via `bin/archive_decision.sh` on the LEARN decisions dir; apply;
   continue); else a learn-state → resume its `phase` (each phase skips forward when its output files
   already exist); else → a fresh retro starting at `resolve`.
3. Drive the dispatch loop in `main()` to `phase:done`, persisting learn-state after EVERY transition.
   When a ratification gate ends the turn, END YOUR TURN — the next user turn re-enters here and ingests.

## Orchestration rules (HOW to act as L0 — no JS equivalent)

- **/learn reviews the MACHINE, not the paper.** The run's paper/experiments/reviews are EVIDENCE about
  the pipeline's components. Never re-run in-run machinery's job; never open a new punch-list against the
  paper. The one deliverable is design learning: findings → proposals → owner ratification → hypotheses.
- **READ-ONLY toward the run.** Write ONLY under `state/learning/<run_id>/` (evidence, reviews, verify,
  brief, learn-state, its own decisions/) and `SOURCE_REPO/dev/learning/` (dossier, hypotheses.json,
  README index). NEVER touch `state/pipeline-state.json`, the workspace, or any run artifact. NEVER
  `git commit` — at `record` print the suggested commit command and stop (shared-worktree law).
- **Spawns: single-context leaves only, in ONE message per wave.** Every spawn is
  `auto-research:leaf-worker` (no Agent tool — structurally cannot nest). The review wave (5-9 leaves) and
  the verify wave (1-3 leaves) each go out as ONE message with one Task call per leaf (parallel), then
  collect envelopes. Every goal is "Read `spec/spawn-prompts/LEARN-<X>.md` and do EXACTLY what it says" +
  token substitutions — NEVER restate rubric content in the goal, NEVER "run /<command>".
- **Gates are L0-only, hybrid, and ISOLATED from the pipeline's.** /learn's decision files live under
  `state/learning/<run_id>/decisions/` — never `state/decisions/` (a /learn gate must never collide with a
  pipeline gate). At every gate: write DECISIONS-PENDING.md from `assets/decision-file-template.md`, ALSO
  surface the same questions as a live AskUserQuestion card, then **end your turn**. Card preview =
  **SOURCE-DERIVED, never pre-baked**: read the decision file just written PLUS the dossier section /
  ratify-queue entry the question's context names, and render what is on disk NOW into each option's
  `preview`. Chat wins over file on conflict; an unanswered item is re-presented, never guessed.
- **The brief is delivered VERBATIM.** At `ratify`, print `dossier-brief.md` exactly as written (it is
  composed self-contained for an owner one abstraction layer away). Do not paraphrase, trim, or
  re-summarize it; do not append your own analysis. Then open the first theme gate.
- **Categorical verdicts only; grounding floor.** No numeric scores anywhere. Any Fundamental/Structural
  claim you relay must carry its verbatim evidence anchor from the dossier. A finding that re-litigates
  the evidence pack's §0 SETTLED DECISIONS is auto-invalid — drop it and say so.
- **Proposals name SOURCE paths.** The cache is a frozen copy that drifts; the manifest records which
  world actually ran. Never let a proposal target `~/.claude/plugins/cache/...`.
- **Empty-result recovery.** A 529/overload can empty a leaf's envelope: verify its output files on disk;
  re-spawn ONCE in `[RESUME]` mode; if still bad, surface it — never fabricate a review.
- **The venue cold read is a CALIBRATION INSTRUMENT (charter exception iv).** Spawn it BLIND: its goal
  carries NOTHING beyond the venue pack + the paper dir + the panel/terminal verdict paths — never the
  evidence pack, the manifest, or any review artifact. A skipped/failed/ineligible cold read DEGRADES
  the retro (calibration = 无法比对), it never blocks it. NEVER relay cold-read content as criticism of
  the paper — its only legal use is judging whether the panel/gates judged at the venue's bar.

## Invariants (must hold)

- One retro per run_id: learn-state keys everything; re-running /learn on the same run RESUMES (idempotent
  phases skip on existing outputs). To redo a phase, the owner deletes its output files explicitly.
- A pipeline with a PENDING gate refuses /learn outright; a mid-stage pipeline refuses only the no-arg
  form (an explicit target is consent to retro a past/other run).
- The dossier is the FIX SPEC (dossier-12 idiom): fixes are built in a SEPARATE session from its ratified
  DECISION LEDGER; /learn itself never edits pipeline specs, configs, or code.
- The hypothesis tracker is written ONLY through `bin/learn_hypotheses.py` (schema-validated, atomic).
  A hypothesis gets a real verdict only once its change was DEPLOYED for the reviewed run (the
  cache-drift lesson); otherwise record `unmeasurable`.
- The quality ledger is written ONLY through `bin/learn_quality_ledger.py` (same discipline). Its
  `list`/`trend` output is the ONLY legal cross-run evidence anchor; a verdict without evidence (or an
  unassessed without a reason) is refused by the bin itself.
