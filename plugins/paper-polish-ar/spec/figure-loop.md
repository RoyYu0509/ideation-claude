# figure-loop — the canonical per-FIGURE revise→regenerate→evaluate→converge loop

SINGLE SOURCE OF TRUTH for the loop STRUCTURE of polishing ONE figure. The MIRROR of `spec/section-loop.md`
(which does the same for /polish sections). Two callers reproduce this loop and MUST stay in sync with it:

- **Serial path** — `spec/polish-figures.js :: runFigure(fig)`: the orchestrator READS this file and runs
  the loop in its own context, on the main working tree, editing the figure's plotting script in place.
  ([dossier-12 G1] the old inline reference implementation is RETIRED — this file is the only encoding.)
- **Parallel path** — `spec/polish-figures.js :: figureRunnerGoal(...)`: an L2 `figure_runner` subagent runs
  the SAME loop one level down, INSIDE an isolated git worktree, and RETURNS `FIGURE_RESULT_SCHEMA`.

They differ ONLY in (a) who drives it (orchestrator vs a spawned runner) and (b) the paths / `git -C` target
(main tree vs the worktree). Everything below — the step sequence, the freeze discipline, the THREE-WAY
fidelity gate, the mandated annotation crop-check backstop, and the deterministic-converge contract — is
identical. **When the loop changes, edit THIS file** — neither caller carries a copy to mirror. The "how" of
making a figure good (layout, legends, de-AI defaults, plot-code naming) lives in the `research-figure-plotting`
skill each sub-agent retrieves; the reviser / fidelity / visual-QA sub-goals themselves live in the shared
`spec/spawn-prompts/figures-{semantics,visual-qa}.md` files BOTH paths inject — this file carries only the LOOP.

Convergence, the actionable-flag arithmetic, and best-round selection are DETERMINISTIC and decided ONLY by
`scripts/figure_converge.py` — NEVER judged by an LLM (spec/polish-figures.js:19-21, the figure analogue of
polish's invariant 6). The redesign license (below) changes NONE of that arithmetic — `figure_converge.py`
is unchanged; `ROUND_CAP` is a caller-supplied input, and in a redesign flow round 1 IS the redesign, so
there is no pre-redesign round the best-round pick could mistakenly ship.

## Bindings (supplied by the caller)

| binding | meaning |
|---|---|
| `FIG_ID` / `PLOT_SCRIPT` | the figure id + its plotting script (the ONE file the reviser edits) |
| `OUTPUT_FILES` / `REGEN_CMD` | the figure files it regenerates + the command that regenerates them |
| `GIT_C` | the `git -C` target dir (serial: gitRoot; parallel: the worktree root) |
| `FIG_BASE_SHA` | this figure's LOCAL base sha — its untouched script + outputs |
| `SEMANTICS` | the visual-freeze manifest (encodings that must not collapse, annotation placements) |
| `SURVEY` | the whole-set taste baseline + shared default-off defects to strip set-wide |
| `DESIGN_BRIEF` / `REDESIGN_LICENSED` | this figure's design brief (figure-design pass) + whether its `verdict=redesign` is licensed (briefs approved, not `restyle_only`) |
| `CONVERGE` | `python3 <pluginRoot>/scripts/figure_converge.py` — the deterministic decider |
| `ROUND_CAP` | `REDESIGN_MAX_ROUNDS` when `REDESIGN_LICENSED`, else `1` when the survey marks this figure effort `light`, else `MAX_ROUNDS` |
| `DIMENSIONS` / `NO_IMPROVE` | the visual-QA dimensions + the stagnation threshold (categorical; no weights) |

## Loop

First run the read-only **semantics** pre-pass (`figures-semantics.md`) to build `SEMANTICS` if not supplied.
Keep a `rounds` array; each entry is `{round, fidelity_verdict, actionable, quality, revise}`. For
`round = 1..ROUND_CAP`:

### 1. REVISE + REGENERATE — ONE reviser edits ONLY `PLOT_SCRIPT`, then re-runs `REGEN_CMD`
Reviser goal (round 1 records problem_list + fix_plan BEFORE editing; round >1 addresses the previous round's
OPEN flags): edit ONLY `PLOT_SCRIPT` with Edit/MultiEdit (NEVER Write), apply every de-AI default-off rule +
the reader-comprehension rules from `research-figure-plotting`, obey the `SEMANTICS` visual-encoding freeze
(do_not_collapse channels, annotation placement), and strip the `SURVEY` shared defects. When
`REDESIGN_LICENSED`: round 1 IS the redesign round — the reviser IMPLEMENTS `DESIGN_BRIEF` (chart type /
axis windows / panel composition may change per the brief; same cached data, statistics, series meanings;
retrieve `figure-design` for the target archetype), `SEMANTICS.structural_choices` `do_not_change` entries
are ADVISORY (brief > old structure; encoding MEANING stays binding — every condition the original
distinguished must remain distinguishable), later rounds POLISH the new design and never re-litigate the
brief, and the reviser NEVER edits any `.tex` (the brief's caption/tex changes are the orchestrator's Emit
step). Then re-run `REGEN_CMD` and OPEN/RENDER the output to self-check. **REGEN IS A HARD GATE** (脚本失败先修复,不进入下一轮):
if the script errors or does not write every output, FIX it before committing; NEVER commit a script that
fails to regenerate; if it cannot be made to run, return `committed=false` (blocker) instead. Set
`regen_ok=true` ONLY on a clean run. FREEZE vs RESCALE, from the reviser's side (the gate's three-way
verdict in step 2 mirrors this): an HONEST axis window (symmetric padding, or hugging the occupied data
band; a solid bar keeps its 0 baseline) is FREE style; a GENUINELY needed numeric rescale (unit
conversion, fraction→%, a colorbar vmin/vmax window, annotated values following it) is allowed but MUST
be tagged `rule_tag="rescale"` with a rationale — the gate HOLDs it for author approval; an UNTAGGED
rescale reads as drift and FAILs; data source/transforms/statistics/misleading truncation are FORBIDDEN.
Commit ONLY this figure's files, each in ITS OWN repo when they span several: `git -C "GIT_C" add --
PLOT_SCRIPT OUTPUT_FILES` then commit with a structured message. `roundSha = git -C "GIT_C" rev-parse HEAD`. Return
`FIGURE_REVISE_SCHEMA`.

- `committed=false` → record the blocker, stop this figure (ship original via do-no-harm below).
- `committed=true` but `regen_ok=false` → restore to the last good sha, commit the revert, record the blocker,
  stop this figure. NEVER evaluate (let alone ship) a figure that did not regenerate.

### 2. EVALUATE — fidelity gate + visual-QA reviewer, IN PARALLEL
Run both concurrently (`CONVERGE` decides nothing here; these only produce verdicts):
- **check-figure-fidelity** (`figures` fidelity role, read-only): THREE-WAY verdict — `PASS` (only presentation
  moved, incl. a structural change MATCHING `DESIGN_BRIEF` under `REDESIGN_LICENSED` — reported in
  `design_changes`) / `HOLD` (a deliberate numeric/scale RESCALE, or an OFF-brief structural change — the
  author must approve) / `FAIL` (suspected data/transform/misleading-window drift, or fewer DISTINGUISHABLE
  conditions than the original). Inject `DESIGN_BRIEF` into its goal when licensed (the skill's
  "judging against an approved design brief" section). Compare BASE↔REVISED renders + code diff.
- **visual-QA** (`figures-visual-qa.md`): render + LOOK; judge `DIMENSIONS` (the `design` dimension FIRST,
  against `DESIGN_BRIEF`'s reader_takeaway + regen_expectations when present); return `FIGURE_QUALITY_SCHEMA`
  with `annotations_checked` (every in-plot transAxes/transData annotation you cropped-and-Read).

### 3. [[MECH]] ANNOTATION CROP-CHECK BACKSTOP — deterministic, do NOT skip
Count the script's in-plot annotations: `grep -oE 'transform=[A-Za-z_.]*\.(transAxes|transData)' PLOT_SCRIPT |
wc -l`. If that count is `>0` AND visual-QA returned an EMPTY `annotations_checked`, the mandated crop-and-Read
did not happen: INJECT a `blocking`/`actionable` legibility flag ("QA reported checking 0 of N in-plot
annotations — cannot certify no annotation overlaps a data element") so the figure cannot converge unverified.
(This backstop is re-verified by the orchestrator at assemble time — it is not left to agent honesty.)

### 4. [[MECH]] THREE-WAY FIDELITY GATE
`FAIL` or `HOLD` → this round is do-no-harm REVERTED: `git -C "GIT_C" checkout <last-good-sha> -- PLOT_SCRIPT
OUTPUT_FILES`, commit the revert. Record `HOLD` → `needs_approval` (await author sign-off — include
`held_sha` = the reverted round's commit, so an approved change is applied with one
`git checkout <held_sha> -- PLOT_SCRIPT OUTPUT_FILES`), `FAIL` → `fidelity_reverts` (drift). A PASS under
`REDESIGN_LICENSED` rolls the gate's `design_changes` into the return. A reverted round is un-shippable.

### 4b. REDESIGN ONLY — re-derive `SEMANTICS` after the first faithful round
When `REDESIGN_LICENSED` and this round is the FIRST fidelity-`PASS`: re-run the semantics pre-pass
(`figures-semantics.md`) on the NEW figure and use that manifest for every later round — the old manifest
describes a structure that no longer exists. (Once per figure.)

### 5. [[MECH]] ACTIONABLE COUNT + baseline propagation
`actionable` = count of visual-QA flags with `disposition != 'deferred'` OR `baseline_conflict==true`; a
reverted round's actionable is ∞ (un-shippable). Collect every `baseline_conflict` flag (a default-off
decoration the survey baseline wrongly kept) into `baseline_conflicts` — the caller propagates it set-wide.
Push `{round, fidelity_verdict, actionable, quality, revise}` onto `rounds`.

### 6. CONVERGE — DETERMINISTIC; call the script, do NOT judge
```
CONVERGE <<'JSON'
{"mode":"round","round":R,"round_cap":<ROUND_CAP>,"effort":<effort>,"no_improvement_rounds":<NO_IMPROVE>,
 "history":[{"fidelity_verdict":<each prior round's verdict>,"actionable":<its actionable>}, ...],
 "current":{"fidelity_verdict":<this round's verdict>,"actionable":<this round's actionable, 0 if reverted>}}
JSON
```
Read back `{state, stop, stop_reason}`. If `stop` is true, break.

### 7. SHIP BEST — after the loop, run the script in best mode
```
CONVERGE <<'JSON'
{"mode":"best","rounds":[{"round":R,"fidelity_verdict":V,"actionable":A} for every round]}
JSON
```
→ `{best_round, do_no_harm}`. If `do_no_harm` (no round both preserved the data AND produced a figure), restore
the ORIGINAL (`FIG_BASE_SHA`) and ship shippedVersion 0. Else if `best_round`'s sha != current HEAD, restore
`PLOT_SCRIPT OUTPUT_FILES` to that round's sha and commit. `shipped_sha = git -C "GIT_C" rev-parse HEAD`.

## Freeze discipline (non-negotiable — the pre-edit hook, figure mode, enforces it at any worktree depth)
The reviser edits ONLY `PLOT_SCRIPT` via Edit/MultiEdit; the cached DATA + the manuscript PROSE are FROZEN
(the hook denies edits to them); the .py script + the figure outputs are FREE. All git is `git -C "GIT_C"`
and commits ONLY this figure's files (no `git add -A`; never amend/squash). Never rerun the experiment — read
cached data only. Surface any git failure — no `|| true`.

## Parallel return (figure_runner only)
Return `FIGURE_RESULT_SCHEMA`: `{id, plot_script, branch, shipped_sha, shipped_version, actionable,
stop_reason, rounds (each {round, sha, fidelity_verdict, actionable, annotations_checked_n, hunks}),
blockers, design_changes (brief-matching structural changes fidelity PASSed), needs_approval (each with its
held_sha), fidelity_reverts, close_calls, deferred_flags (the SHIPPED round's deferred QA flags),
baseline_conflicts, semantics}`. Do not return prose.
