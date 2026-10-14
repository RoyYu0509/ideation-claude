# Auto-Research Status Model (canonical) — RC-10 / option A

The single source of truth for **every pipeline state, its "done" definition, the on-disk evidence that
proves it, and who records it.** `bin/pipeline_status.sh`, the ship-gate (`assertShipReady`), and any future
verifier-agent all read FROM this model — none of them re-derives a private one. Keep this doc in sync with
`spec/research.js` (the recorders) and `bin/pipeline_status.sh` (the reader).

## 0. Design principles

1. **Single truth.** Each state's `{done-definition, evidence, recorder}` is defined ONCE, here.
2. **Evidence ranking** (the ship-gate trusts only the top tier):
   - **L0 / authoritative** = a `milestone-state.json` entry carrying a **real git commit sha**.
   - **L1 / weak** = a report file exists (an L1 side-effect; can be empty/stub).
   - **L2 / never gate on this** = `state.stage` / `history` (L0 self-report, zero provenance — this is the
     field the 2026-06-20 run faked).
3. **Three tiers.** Batch (many papers) → Pipeline stage (one paper's spine) → Loop internals (milestones +
   rounds). Plus cross-cutting flags.
4. **do-no-harm preserved.** "ran but only surfaced items" → a ledger entry exists (with `surfaced:N`) → it
   ships. "never ran" → no entry → hard stop. The distinction is the presence of the provenance entry.

## 1. Overview

```
RUN     state.stage (one idea per run; no batch / queue)
  └─ PIPELINE (the single spine; state.stage advances):
       ideation → seed_gate⚑ → setup_workspace → gen_handoff → handoff_gate⚑
        → loop → verify_final → spec_freeze → ship
        └─ LOOP internals (the loop OPTIMIZES the SPEC: execute → evaluate → re-author):
             milestones[PHASE0_KILL_OR_CONFIRM, CAPACITY_READOUT, LITERATURE, ENV_READY, EXPERIMENTS_DONE, RESULTS_ON_DISK]
             + per-round{ experiment → dossier → review(+focused verify) → B3 gate → SPEC-v<N> }
  ⚑ = gate           cross-cutting flags: pending_gate · detached · *_verdict
  (who ANSWERS a ⚑ is `gates.adjudicator`: `agent` — a cold-read adjudicator leaf, the default — or `owner`;
   a kind in `gates.owner_kinds` — default `direction` — is always the owner's, a kind in `gates.default_kinds`
   — default `terminal_gate` — takes its own (Recommended) option, and GATE-1's idea pick (`seed_select`) is the
   owner's unconditionally.)
```

## 2. Run-end tier (single idea — there is no batch / queue)

| Field | Values | Recorder | Evidence |
|---|---|---|---|
| `state.final_status` | `shipped` \| `abandoned` | `finishRun` | `pipeline-state.json` |
| `state.exit_reason` | the ship/abandon reason | `finishRun` | `pipeline-state.json` |
| top `state.stage='done'` | the one idea shipped or abandoned | `finishRun` | `runs/<slug>/FINAL-REPORT.md` (viability-kill → `FINAL-REPORT-killed.md`) |

## 3. Pipeline stage tier (single paper) — core table

`state.stage` advances along this spine. 🔒 = part of the **ship gate** (`assertShipReady` →
`pipeline_status.sh --require`). Evidence column is what is on disk **today** (option A is landed).

| # | stage (`state.stage`) | done-definition | authoritative evidence | recorder |
|---|---|---|---|---|
| 1 | `ideation` | refined seeds on disk | `state.ideation_artifacts` + seed `.md` | `phaseIdeation` |
| 2 | `seed_gate` ⚑ | owner picks ONE idea → flat fields set | `state.paper_slug/venue/picked_seed_file` + `DECISIONS-RESOLVED-*` | `gateSeedSelect` → `applyPickedIdea` ingest |
| 3 | `setup_workspace` → `gen_handoff` | workspace bootstrapped (**3 git repos init+baseline**), then HANDOFF (re-)authored | `ledger.stages.seed_to_handoff` (the ledger KEY keeps the historic name) + `.git` baselines (`assertGitInit`) | `setupWorkspace` → `generateHandoff(state, transition=false)` + `recordStage` |
| 4 | `handoff_gate` ⚑ | owner approves work order | `DECISIONS-RESOLVED-*` | `gateHandoffApproval` |
| 5 | `loop` | B3 returns `EXIT`/`EXIT_AT_CAP` | `ledger.stages.loop` + §4 milestones + `REVIEW/round*` | loop body + `recordStage` |
| 6 | `verify_final` 🔒 | independent_verifier `PASS` **+ §4c ambition reconciled** (claim ≤ delivery). DOWN: on a gap the rescue runs FIRST: rescuable→auto-loopback (`reopenLoopWith`, NO gate); not-rescuable→the unified **terminal gate** (§5, reason `over_claim`). A DEAD central claim routes to that gate too (`negative_result`), as does an `EXIT_AT_CAP` (`cap_exit`); only a clean-earned EXIT auto-ships. UP: on an HONEST reconciled paper WITH loop headroom, the **amplifier** (#3) may RAISE the target + loopback to earn it — see §4(d) | `ledger.stages.verify_final{verdict,paper_commit,ambition_reconciled,ambition_gaps}` | `runVerify` → `runResearchRescue` / `runTerminalGate` → (`runAmplify`) → `recordStage` (read-only) |
| 7 | `spec_freeze` 🔒 | the settled spec distilled into the run's ONE deliverable: `SPEC-FINAL.md` (+ `SPEC-EVOLUTION.md` + the grounding audit `SPEC-FREEZE-REPORT.md`). MANDATORY, no toggle | `ledger.stages.spec_freeze{spec,evolution,surfaced,paper_commit}` **and `SPEC-FINAL.md` non-empty on disk** (the oracle checks the deliverable independently of the ledger) | `runSpecFreeze` → `recordStage` |
| 8 | `ship` (terminal action) | gate passed + FINAL-REPORT written | `ledger.stages.ship` + `FINAL-REPORT.md` + `state.final_status='shipped'` | `ship` → `recordStage` + `finishRun` |

`ship()` begins with `assertShipReady`, which runs `pipeline_status.sh --require verify_final,spec_freeze`
and THROWS unless every 🔒 stage has a ledger entry whose `paper_commit` resolves to a real commit + git
provenance is healthy. The 🔒 stages were the silent-collapse hole in the 2026-06-20 run.

## 4. Loop internals

**(a) Experiment milestones** (`config.milestones` — the original gold-standard provenance pattern that
option A copies for finishing):

| milestone | done | authoritative evidence | recorder |
|---|---|---|---|
| `PHASE0_KILL_OR_CONFIRM` | Phase-0 kill/confirm = PASS | `ledger.milestones[ms]={completed_at, code_commit, paper_commit}` + real commits | `runExperiment` |
| `CAPACITY_READOUT` | wall-clock heads-up computed (runs ONCE, right after Phase 0's lock, before LITERATURE) | same + `.capacity-readout.json` (a bounded `spawnL2` leaf's timed micro-probe vs the locked §4b `budget_envelope`; `CONCERN` surfaces the `capacity-` gate, never auto-kills — §4b stays hardware-blind) | `runExperiment` |
| `LITERATURE` | role/coverage bibliography built (HANDOFF Phase 1) | same + `differentiation_table.md`·`paper/references.bib` (independent auditor surfaces padding/miscite/coverage) | `runExperiment` |
| `ENV_READY` | environment reproduces | same | same |
| `EXPERIMENTS_DONE` | all experiments run | same | same |
| `RESULTS_ON_DISK` | results + provenance audit on disk | same + `EXPERIMENTS/results_master.json`·`provenance_audit.md` | same |

> Milestones **refuse to record an unfinished stage** (a `failed` L1 is not `--allow-empty` committed/recorded).
> `recordStage` follows the same discipline for finishing.

**(b) Per-round** (`loop_round`; hard cap `config.max_loop_rounds`):

| sub-phase | evidence | recorder |
|---|---|---|
| round entry | `.round-N.start` + `.round-N.concerns.json` (frozen) + `round_baseline_paper` | loop body |
| experiment | milestone ledger (above) | `runExperiment` |
| draft | `git "round N: content draft"` commit | `runDraft` |
| review(+focused verify) | `REVIEW/roundN_reviews.md` + `state.verify_verdict` | `runReview`/`runFocusedVerify` |
| B3 gate | `logEvent('verdict', loop_gate)` → `CONTINUE`/`EXIT`/`EXIT_AT_CAP` | `runB3` = `bin/loop_gate.sh` |
| concern-prose consistency (advisory) | `bin/concern_prose_lint.sh` flags a `TASK_STATUS.md` "## Editorial direction" bullet that still names a concern-id whose `TASK_STATUS.concerns.json` status has moved on (D12 precedent: never auto-edits, never blocks). Logged every milestone-commit; surfaced in `context.prose_staleness` at every `handoff-approve` gate; escalates to a REQUIRED "Re-author stale Editorial direction now" option after `STALE_ESCALATE_K=3` consecutive rounds with the SAME flag (section sha unchanged) | `.concern-prose-staleness.json` + `logEvent('concern_prose_stale'/'concern_prose_stale_escalated')` | `concernProseStaleness` (called from `gateHandoffApproval`) / `runExperiment` milestone-commit hook |

**(c) Forward-motion guarantee** (the "review→fix→review spin" fix — a CONTINUE that re-opens nothing leaves
every done milestone untouched, so the next round only re-drafts prose and review re-flags the SAME concern).
The loop now makes forward motion DETERMINISTIC at the CONTINUE bridge (`generateHandoff(state, transition=true)` — the per-round HANDOFF re-author that folds the round's `HANDOFF-*.md`):

| guarantee | mechanism | recorder / evidence |
|---|---|---|
| **F1 forward-floor** | when review wrote NO `HANDOFF-*.md`, read the live ledger (`TASK_STATUS.concerns.json`) and FORCE-FORWARD each open **major, non-`spec`** concern into a deterministic `HANDOFF-*.md` stub (verbatim concern text), then re-scan — so the early `if (!handoffs.length) return` no longer ships a spin. A `needs:'spec'` concern (legacy alias `'rewrite'`) is SKIPPED — the next round's HANDOFF re-author owns it, and forcing a segment for a wording defect is exactly the spin this floor exists to prevent. | `generateHandoff` (F1 forward-floor block, BEFORE the early-out) + `.forced-<id>.marker` anti-thrash + `logEvent('forced_forward')` |
| **F2 provable segment** | an ADDITIVE demand mints a first-class EMPTY segment `EXPERIMENTS/<id>/` (`.pending`, NO `result.md`) the worker is FORCED to fill (protocol:119 — a segment without `result.md` is unfinished); a REDESIGN clears the target's `result.md`. | `generateHandoff` (F2 scaffold) + `logEvent('segment_scaffolded'/'segment_reopened')` |
| **F2 no-op-reopen backstop** | the re-open SNAPSHOTs the on-disk `{(<seg>, sha256(result.md))}` set keyed **`loop_round + 1`** (the round the re-opened experiments RUN in); `runExperiment` re-derives the set just before re-marking `EXPERIMENTS_DONE` and REFUSES the `--allow-empty` done re-mark on a byte-identical set (a re-open that produced no new result) — fail-closed `noop-reopen-r<N>` `failureSurface`. A scaffold (no `result.md`) contributes nothing; no snapshot ⇒ nothing re-opened ⇒ never a no-op. | `bin/reopen_noop_diff.sh` (snapshot/check; mechanical SHA-set out of the thin spec) ← `generateHandoff` snapshot / `runExperiment` check + `logEvent('noop_reopen')` |
| **`reopenLoopWith(state)`** | the SHARED primitive a POST-loop stage uses to re-enter the loop with new HANDOFF work: folds `HANDOFF-*.md` via `generateHandoff(state, transition=true)`, then points `state.stage='loop'` so the while-loop re-enters `case 'loop'` (`loop_round+1`). Used by `verify_final`'s rescuable ambition-loopback. | `reopenLoopWith` (spec/research.js) |

**(d) verify_final UPWARD path** (the ambition AMPLIFIER, #3 — research-rescue's dual). The pipeline has many
DOWNWARD forces (review narrows claims; #1 pushes the claim down to delivery; viability can kill) and NO upward
one, so papers shrink into rigorous-but-timid reports. The amplifier is that upward force. It fires at
`verify_final` AFTER #1's §4c reconciliation PASSES (`reconciledFinal===true` — an HONEST paper, never an
over-claimer), WITH loop headroom (`state.loop_round < CFG.max_loop_rounds` — a clean early EXIT has headroom; an
`EXIT_AT_CAP` does not → ships), and once-per-round (a `.round-N.amplify-tried` marker makes a mid-verify_final
resume idempotent; after a loopback the NEXT exit is a NEW round → it can amplify again → repeated climbing).

| outcome | mechanism | recorder / evidence |
|---|---|---|
| **raise earned** | `runAmplify` (ONE producing-worker loading `research-amplify`) returns `can_go_bolder` + `proposed_raise` → `raiseAmbitionTarget` writes the RAISED claim to `HANDOFF.ambition.target.json` (≥ the locked floor; NEVER the locked file) → `reopenLoopWith(state)` re-enters the loop to RUN the authored `HANDOFF-amplify-*.md`. NO `recordStage` — verify_final is NOT recorded; the raise is **AUTO-EARNED** (no owner gate): #1 re-audits the raised claim at the NEXT verify_final against `target.json`. | `raiseAmbitionTarget` (`target.json`) + `logEvent('ambition_amplify', outcome:'raised')`; re-entry via `reopenLoopWith` |
| **at-ceiling / no-headroom / marker-set** | the amplifier honestly cannot earn a bolder claim, or loop_round==max, or the round already amplified → fall through to the UNCHANGED ship-recording → `recordStage(state, 'verify_final', …)` + ship. | `logEvent('ambition_amplify', outcome:'at_ceiling')` + `ledger.stages.verify_final` |

> `target.json` is the RAISED claim (mutable, provenance-stamped per raise); `locked.json` stays the IMMUTABLE
> floor (Phase 0(C)). #1's `verifierGoal` reconciles delivery against `target.json` IF it exists, ELSE the locked
> floor (backward-compat: target.json is absent in the common no-raise case ⇒ the floor, exactly as before).

## 5. Cross-cutting flags (compose with any stage; live in `pipeline-state.json`, NOT the ship-gate ledger)

| flag | meaning | evidence | recorder |
|---|---|---|---|
| `pending_gate` / `gate_resolved` | a gate is open; under `gates.adjudicator: agent` it is answered and cleared within the SAME turn, and a surviving `pending_gate` means a crash interrupted that — it is re-adjudicated on resume. Under `owner`, this turn is likely its INGEST | `state/decisions/DECISIONS-PENDING.md` | `gate()` / `failureSurface` |
| `terminal-gate-<slug>-r<N>` gate | the UNIFIED terminal-exit gate (folds the former `ambition-residual` gate): ONE card for every non-clean exit (answered by the system default under `gates.default_kinds`, by the owner if `terminal_gate` is an owner kind) — reason ∈ {`cap_exit` (max rounds, unresolved), `negative_result` (central claim DEAD), `over_claim` (REAL result over-reaches delivery)}, plus `clean_exit` when `terminal_gate` is an owner kind (`gates.owner_kinds`; default Ship) — options **Abandon** (default for negative → `FINAL-REPORT-killed.md` + `finishRun('abandoned')`) \| **Ship** (default for cap / over_claim since 2026-09-24 = hand the spec back to the researcher; records `verify_final{ambition_reconciled:true}`, sets `ship_reason='terminal_ship_<reason>'`, → spec_freeze; for `negative_result` this is an explicit OWNER OVERRIDE of the standing ABANDON policy) \| **Rescue one more round** (research-rescue + `reopenLoopWith`) \| **Amplify one more round** (owner-directed amplifier → transition re-author → the next round's direction card). Every option has a matching `ingestGateAnswer` branch | `DECISIONS-PENDING.md` + `.terminal-verdict.json` | `runTerminalGate` `gate()` / `ingestGateAnswer('terminal-gate-')` |
| `.round-N.amplify-tried` flag | the once-per-round AMPLIFIER marker (§4(d)) — set BEFORE `runAmplify` so a mid-verify_final resume does NOT re-amplify the same round; cleared implicitly by entering a new round | `${ws}/.round-N.amplify-tried` | `verify_final` (the amplifier block) |
| `detached[]` | a long experiment is running; turn ended; asyncRewake will re-wake | `.polish/.bg-pids` + `state.detached` | `onLongRun` |
| `phase0_verdict` | Phase-0 PASS/FAIL | `state.phase0_verdict` | `runExperiment` |
| `verify_verdict` | PASS/FAIL (per-round focused + terminal) | `state.verify_verdict` | `runVerify`/`runFocusedVerify` |
| `milestone` | current experiment milestone | `state.milestone` + `milestone-state.json` | `runExperiment` |
| `.concern-prose-staleness.json` | per-concern-id consecutive-round counter for the concern-prose staleness advisory (§4(b)) — NOT ship-gated, purely drives the escalation option | `${ws}/.concern-prose-staleness.json` | `concernProseStaleness` |
| `ship_reason` | `clean_exit` / `terminal_ship_<reason>` | `state.ship_reason` | loop exit / terminal-gate Ship ingest |
| `terminal_reason` | `clean_exit` / `cap_exit` / `negative_result` / `over_claim` — the loop/verify terminal-exit reason the terminal-gate ingest reads (persisted BEFORE the gate; crash-safe default `cap_exit`) | `state.terminal_reason` | loop exit / `runVerify` / `runTerminalGate` |

**Per-spawn L1 status** (the L1→L0 return protocol, orthogonal): `done` \| `escalations_pending` \|
`long_run_fired` \| `failed`.

## 6. The authoritative ledger — `milestone-state.json`

```jsonc
{
  "schema": "auto-research-milestone@1",
  "paper_slug": "...",
  "frozen": { "config_sha256": "...", "protocol_sha256": "...", "spec_commit": "...", "at": "..." },

  "milestones": {                       // experiment tier (unchanged)
    "PHASE0_KILL_OR_CONFIRM": { "completed_at": "...", "code_commit": "<sha>", "paper_commit": "<sha>" },
    "CAPACITY_READOUT": { }, "LITERATURE": { }, "ENV_READY": { }, "EXPERIMENTS_DONE": { }, "RESULTS_ON_DISK": { }
  },

  "stages": {                           // pipeline-stage tier (recordStage, RC-10)
    "seed_to_handoff": { "completed_at": "...", "paper_commit": "<sha>", "handoff": "HANDOFF.md" },
    "loop":            { "completed_at": "...", "paper_commit": "<sha>", "rounds": 2, "exited": "EXIT_AT_CAP" },
    "verify_final":    { "completed_at": "...", "paper_commit": "<sha>", "verdict": "PASS", "ambition_reconciled": true, "ambition_gaps": 0 },
    "spec_freeze":     { "completed_at": "...", "paper_commit": "<sha>", "spec": "SPEC-FINAL.md", "evolution": "SPEC-EVOLUTION.md", "surfaced": 0 },
    "ship":            { "completed_at": "...", "paper_commit": "<sha>", "reason": "clean_exit", "final_report": "FINAL-REPORT.md" }
  }
}
```

Entry shape = `{ completed_at, paper_commit, ...stage-specific fields }`. Every entry requires a **real git
commit sha** (content stages make a subject-prefixed commit; read-only stages snapshot the verified HEAD).
Recorded by **L0 at the transition** via `recordStage` (spec/research.js).

## 7. Ship-gate rule (`bin/pipeline_status.sh`)

```
ship_ready(paper) :=
    git provenance OK (ws + paper + code repos, each >=1 commit)
  ∧ ∀ stage ∈ {verify_final, spec_freeze}:        ── both MANDATORY; there are no toggled finishing stages
        ledger.stages[stage] EXISTS ∧ stage.paper_commit RESOLVES to a real commit in ws/paper
  ∧ verify_final.ambition_reconciled ≠ false       ── §4c: the claim must not over-reach delivery
  ∧ nonempty(ws/SPEC-FINAL.md)                     ── the DELIVERABLE BELT: a ledger entry alone must not
                                                   ──   bless a run that produced no specification
  ── entry present (incl. surfaced:N) ⇒ ran ⇒ pass (do-no-harm)
  ── entry absent / sha unresolvable  ⇒ never ran / forged ⇒ block
  ── ambition_reconciled:false (claim > delivery, unresolved by rescue/owner) ⇒ block; absent field ⇒ do-no-harm (legacy)
```

Output contract: per-phase `PRESENT|ABSENT|SKIPPED` lines, then `CURRENT <first-incomplete>`,
`SHIP_READY yes|no`, `MISSING <csv>`. Exit `0` ready / `1` not / `2` error. Surfaced every turn by
`commands/auto-research.md` (the authoritative "which step are we at", trusted over `state.stage`).

## 8. Trust boundary — now closed by the harness hook (RC-11)

RC-10's ledger is L0-cooperative: if L0 skips the whole finishing block it also skips `recordStage` AND
`ship()` (and thus `assertShipReady`) — same class as skipping git init. The 2026-06-21 run hit exactly this:
at EXIT_AT_CAP L0 judged "the science is broken, finishing is pointless", skipped the whole finishing chain
AND `ship()`, and improvised a `FINAL-REPORT.md` to declare the paper shipped.
The in-spec gate never fired because L0 never reached it — "hard to skip by accident" is the wrong threshold
when L0 skips it *on purpose* via mistaken reasoning.

RC-11 closes the last mile this section once named as the only fully L0-proof option: a harness **PreToolUse
hook** (`hooks/ship_gate.{sh,py}`, wired in `hooks/hooks.json` — the auto-research plugin's OWN hook, the
vendored paper-polish hooks stay untouched) that gates the one irreversible ACT marking a paper shipped —
writing the workspace `FINAL-REPORT.md` — on the SAME oracle `assertShipReady` calls (`pipeline_status.sh
--require verify_final,spec_freeze`), and denies any write to the banned combined-finishing file
`FINISHING_REPORT.md`. It is not a second/parallel rule; it moves the existing oracle OUTSIDE the L0
reproduction, where the harness enforces it and L0 cannot reason past it. It fails CLOSED for the ship surface
(oracle unreachable ⇒ refuse) and is a no-op for every other write (blast radius = two filenames). The
commit-sha requirement still raises the forgery cost (an unresolvable sha fails — test t32 case 5); the hook
removes the "skip the whole block" escape entirely. An optional independent verifier-agent can still add depth
on top, but the final block is this deterministic rule + the hook.

## 9. Tests

`tests/t32_pipeline_status.sh` (18 checks, in `run_all.sh`): regression shape, complete ledger, toggle-off,
required-missing, **provenance forgery (unresolvable sha → blocked)**, do-no-harm surfaced, git-ok/stage-missing,
bad args. `tests/t33_ship_gate.sh` (RC-11, in `run_all.sh`): the PreToolUse hook denies `FINISHING_REPORT.md`,
denies a workspace `FINAL-REPORT.md` with an empty finishing ledger, allows it with a complete ledger, and is a
no-op for unrelated / non-workspace writes.
`tests/t38_loop_forward_motion.sh` (Phase-0 forward-motion, in `run_all.sh`): FUNCTIONAL `bin/reopen_noop_diff.sh`
(no-change→`NOOP`, add/change a `result.md`→`PROGRESS`, empty scaffold→`NOOP`, no-snapshot→`PROGRESS`, bad-args→exit 2)
+ STATIC invariants — D1 (fixed `models.rescue`/`budgets.rescue` key, `spawnWorker('rescue'`, no dynamic
`rescue-${…}`), F1 forward-floor (before the early-out, major + skip `needs:'spec'` + re-scan), F2 round-key
alignment (`snapshot … loop_round + 1`) + scaffold + the `noop-reopen-` backstop, D2 three-way partition +
loopback-no-gate/`reopenLoopWith` + not-rescuable→`runTerminalGate(state,'over_claim')` (the old
`ambition-residual` gate + ingest are GONE, folded into the unified `terminal-gate-` ingest), D3 detached
rescue→`onLongRun(…,'RESCUE')`.
`tests/t39_ambition_amplify.sh` (the verify_final UPWARD amplifier §4(d), in `run_all.sh`): STATIC invariants —
S1 (`research-amplify` SKILL: `can_go_bolder`/`proposed_raise`/`at-ceiling` output + the anti-rigor "more seeds"
boundary), C1 (`models.amplify` + `budgets.amplify`), W1 (`amplifyGoal` loads the skill + authors
`HANDOFF-amplify-`; `spawnWorker('amplify'`; detached→`onLongRun(…,'AMPLIFY')`), G1 (the load-bearing gate:
`reconciledFinal && state.loop_round < CFG.max_loop_rounds && !exists(amplifyMark)` — headroom key is
`CFG.max_loop_rounds`; raise→`raiseAmbitionTarget`→`reopenLoopWith`→`return null` with NO `recordStage` in the
raise path; fall-through reaches the UNCHANGED `recordStage(verify_final)`), T1 (`verifierGoal` picks
`target.json` ELSE the locked floor), R1 (`raiseAmbitionTarget` writes `target.json`, NEVER `locked.json`; shape
= central_result/scope/named_rivals/provenance). Each invariant carries a NEGATIVE CONTROL (a mutated copy)
proving the assert catches its regression.
`tests/t51_terminal_gate.sh` (the UNIFIED terminal gate, in `run_all.sh`): the loop tail sets `terminal_reason`
(`cap_exit` vs `clean_exit`) and keeps `ship_reason='clean_exit'` on a clean EXIT (the removed
`max_loop_rounds_unresolved` auto-ship string is GONE); `runVerify` routes a dead claim→`negative_result`, an
un-rescuable gap→`over_claim`, and `cap_exit`→`cap_exit`, each into `runTerminalGate`; the `terminal-gate-`
ingest disposes Abandon/Ship/Rescue (the former `ambition-residual` gate is folded in).
`tests/t73_central_ambition_guard.sh` (§4(b) mid-loop guard, in `run_all.sh`): FUNCTIONAL `bin/
central_ambition_guard.sh` (unchanged central K→`OK`; non-canonical status this round→`NEEDS_RESCUE <id>`;
same K but a `.round-N.rescue-verdicts.json` entry already exists→`OK`; `closed` + narrowing `resolution`
text→`NEEDS_RESCUE`; no `HANDOFF.ambition.locked.json`→`OK` do-no-harm; bad args→exit 2) + STATIC
(`runCentralAmbitionGuard` defined + called in `runExperiment` guarded by
`CFG.checkpoints.central_ambition_guard`; `ingestGateAnswer` has a `central-narrow-gate-` branch with
Confirm/Redirect/Abandon; `config.yaml`/`skills/research-rescue/SKILL.md` mention the guard).
`tests/t74_concern_prose_lint.sh` (§4(b) concern-prose staleness, in `run_all.sh`): FUNCTIONAL `bin/
concern_prose_lint.sh` (open/mentioned→clean; non-open + mentioned + no ack token→stale; ack token present→escape
hatch clean; not mentioned→clean; no Editorial-direction heading→`section_found:false`; missing/malformed
inputs→exit 0 fail-open) + STATIC (`concernProseStaleness` wired into `spec/research.js`, the escalation option
string present, `config.yaml` toggle present).
`tests/t75_capacity_readout.sh` (§4(a) CAPACITY_READOUT milestone, in `run_all.sh`): STATIC invariants —
`milestones` (`config.yaml`) contains `CAPACITY_READOUT` immediately after `PHASE0_KILL_OR_CONFIRM`; `isCap`
three-way goal/spawn/audit-artifact-exemption branches present in `runExperiment`; `capacityReadoutGoal` defined
+ points at `spec/spawn-prompts/CAPACITY-READOUT.md`; the `capacity-` gate reads its verdict from `.capacity-
readout.json` on disk (never `env.metrics`, mirrors `literature_reviewer`); `ingestGateAnswer('capacity-')`
routes Redirect through `gen_handoff` (NOT a marker-clear retry — the hardware-blind rule means there is
nothing to fix about the measurement itself); `HANDOFF.scale-contract.locked.json`'s schema carries
`budget_envelope` + per-K `scale_size`; `seedToHandoffGoal` substitutes `<PROFILE_FILE>`/`<SESSION_HOURS_ASSUMPTION>`.
