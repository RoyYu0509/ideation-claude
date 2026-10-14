# section-loop — the canonical per-section revise→evaluate→converge loop

SINGLE SOURCE OF TRUTH for polishing ONE section file. Two callers reproduce this loop and MUST stay in
sync with it:

- **Serial path** — `spec/polish.js :: runBodySection(file)`: the orchestrator READS this file and runs
  the loop in its own context, on the main working tree, editing the file in place. ([dossier-12 G1] the
  old inline copy is RETIRED — this file is the only encoding.)
- **Parallel path** — `spec/polish.js :: sectionRunnerGoal(...)`: an L2 `section_runner` subagent runs the
  SAME loop one level down, INSIDE an isolated git worktree, and RETURNS `SECTION_RESULT_SCHEMA`.

They differ ONLY in (a) who drives it (orchestrator vs a spawned runner) and (b) the paths/`git -C` target
(main tree vs the worktree). Everything below — the step sequence, the freeze discipline, and the
deterministic-converge contract — is identical. **When the loop changes, edit THIS file** — neither
caller carries a copy to mirror. The "how" of writing quality (prose, fidelity, the section rubric) lives in the
skills each sub-agent retrieves, NOT here; this file carries only the LOOP STRUCTURE.

## Bindings (supplied by the caller)

| binding | meaning |
|---|---|
| `SECTION` / `RUBRIC` | the section name + its `section-<rubric>` skill |
| `FILE` | absolute path of the one file to edit (serial: the file in the main tree; parallel: `wfile` in the worktree) |
| `REL` | the file's repo-relative path (blob path) |
| `GIT_C` | the `git -C` target dir (serial: paperDir; parallel: the worktree root) |
| `BASE_SHA` | this file's LOCAL base sha (W0) — its untouched original |
| `SIBLINGS` | sibling section files, READ-ONLY context (may be "(none)") |
| `CONVERGE` | `python3 <pluginRoot>/scripts/polish_converge.py` — the deterministic decider |
| `ROUND_CAP` | `1` when keynote effort is `light`, else `MAX_ROUNDS` |
| `NO_IMPROVE`, `DIMENSIONS` | convergence knobs (no weights — convergence is CATEGORICAL) |
| `KEYNOTE_EFFORT` | `light` / `normal` / `heavy` / `n/a` (the whole-paper read's prior for this section) |
| `ARC_FLAGS` | global argument-arc issues to resolve from WITHIN this section (may be empty) |

Convergence + best-round are decided ONLY by `CONVERGE` — NEVER judge them yourself (invariant 6).

## Loop

Keep a `rounds` array; each entry is `{round, state, verdicts:{quality}}`. For `round = 1..ROUND_CAP`:

### 1. REVISE — spawn/run ONE reviser that edits ONLY `FILE`
Reviser goal:
> You are the reviser for round R of polishing the `SECTION`. Your file to edit: `FILE`. FIRST read it;
> retrieve context-scope + polish-prose + house-style + section-`RUBRIC` and decide whether you also need
> the read-only siblings (`SIBLINGS`). EDIT ONLY `FILE` with Edit/MultiEdit — NEVER Write, NEVER
> sed/printf/bare-bash on prose (the freeze hook is tool-scoped). Freeze the science; edit in proportion to
> need. Commit ONLY your file: `git -C "GIT_C" add -- "FILE"` then commit with the structured message.
> Return REVISE_SCHEMA (hunk rule-tags + answered_flags + could_not_fix).

- Round 1: also pass the keynote — target effort = `KEYNOTE_EFFORT`. If effort is `light`, this section
  already reads well: make ONLY the minimal necessary changes; a near-empty diff is the CORRECT result, not
  a failure; you get exactly ONE pass. If `ARC_FLAGS` is non-empty, tell the reviser to resolve those global
  argument-arc issues from WITHIN this section (no new material).
- Round >1: instead pass the OPEN flags from the previous round (core flags first, then the reviewers'
  highest_leverage_fix); every open flag must be passed through, none silently dropped.
- After it returns: `roundSha = git -C "GIT_C" rev-parse HEAD`. Capture its could_not_fix items.

### 2. EVALUATE — spawn/run the quality reviewer(s) (role reviewer)
(Default ONE reviewer covering all `DIMENSIONS`; the caller's `evaluate.spawn_mode: parallel` knob may
split this into one reviewer per dimension — identical goals + schema either way, merged before §3.)
D1: there is NO per-round semantic-fidelity gate in this loop — drift is checked ONCE, advisory, at the very
end of the whole run by the orchestrator (NOT here); the deterministic token/provenance hook still arms every
edit. Do NOT spawn a fidelity gate.
Quality reviewer goal:
> Review the `DIMENSIONS` dimensions of the `SECTION` at the committed revision `FILE`. Retrieve
> check-logic/check-results/check-readability/check-ai-tells + section-`RUBRIC` + house-style + context-scope.
> DEPTH MANDATE: do NOT spread effort uniformly — first sweep ALL `DIMENSIONS` so coverage is complete, then
> SINK the bulk of your diagnostic into the SINGLE most lethal writing thread of this section and go deep on
> it; name that thread as highest_leverage_fix. Breadth is the floor; a thorough kill of the worst thread
> beats shallow uniform passes.
> disposition='deferred' (with a defer_reason) for an intentionally-kept structure, a needs-author item, OR a
> TRIVIAL cosmetic nitpick that has already had ≥1 fix attempt and is not worth another round; a cosmetic flag
> NOT yet tried is 'actionable' (it earns one attempt before it may be deferred). Everything else you genuinely
> want changed is 'actionable'. Return EVAL_QUALITY_SCHEMA with dimensions_covered = `DIMENSIONS` and each flag
> tagged severity + disposition.

### 3. CONVERGE — DETERMINISTIC; call the script, do NOT judge
Build a COMPACT single-line JSON and run (heredoc avoids shell-escaping the verdict text):
```
CONVERGE <<'JSON'
{"mode":"round","round":R,"round_cap":<ROUND_CAP>,
 "dimensions":<DIMENSIONS>,"no_improvement_rounds":<NO_IMPROVE>,
 "history":[{"state":<each prior round's state>}],
 "current":{"verdicts":{"quality":[<the quality object(s)>]}}}
JSON
```
Read back `{state, open_count, stop, stop_reason}`. Push `{round:R, state, verdicts:{quality}}` onto `rounds`.
If `stop` is true, break.

### 4. SHIP BEST — after the loop, run the script in best mode
```
CONVERGE <<'JSON'
{"mode":"best","rounds":[{"round":R,"state":S} for every round]}
JSON
```
→ `{best_round, best_state}`. ALWAYS ship the best round: if best_round's sha != current HEAD, restore `FILE`
to that sha and commit (no do-no-harm — never fall back to the original). `shipped_sha = git -C "GIT_C" rev-parse HEAD`.

## Freeze discipline (non-negotiable — enforced by the pre-edit hook at any worktree depth, Step A)
The reviser edits ONLY `FILE`, ONLY via Edit/MultiEdit; all git is `git -C "GIT_C"` and commits ONLY `FILE`
(sweep forms — `git add -A`/`-a`, `commit -a` — are DENIED by the plugin's git_sweep_guard hook while the
manifest is armed; never amend/squash). Do NOT write a manifest. Surface any git failure — no `|| true`.

## Parallel return (section_runner only)
Return SECTION_RESULT_SCHEMA: `{section, rel, branch, shipped_sha, best_round, state (=best_state),
stop_reason, rounds (each {round, state, verdicts:{quality}}), could_not_fix (all reviser could_not_fix),
deferred_flags (the SHIPPED round's deferred quality flags: {severity, dimension, issue, defer_reason})}`. Do
not return prose. (D1: no close_calls — drift is the orchestrator's one advisory end-of-run sweep.)
