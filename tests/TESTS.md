# Smoke tests T1–T7 (+ loop_gate) — runnable artifacts + recorded results

> **⚠️ SLIMMING 2026-06-20:** tests t18_full_auto / t21_rm2_commit_at_finalize / t22_asyncrewake_regression /
> t28_flowchart_phase were DELETED (RM2 + full_auto + flowchart removed); t16/t29 updated. Entries below that
> mention those tests / RM2 / full_auto / flowchart / pipeline polish stage are HISTORICAL.

Every load-bearing platform premise of the architecture is verified by EXECUTION (PROTOCOL §4), not
inspection. These artifacts are kept so the owner can re-run them after any Claude Code upgrade.

**Claude Code version for all results below: `2.1.173`** (`claude --version`). Re-record the version
whenever you re-run.

## How to run

```bash
# Pure-shell tests (run from anywhere; no plugin/session needed):
bash tests/test_loop_gate.sh        # B3 deterministic exit arithmetic
bash tests/t2_hook_logic.sh         # freeze-hook DENY arithmetic (mechanical companion to live T2)
bash tests/t3_detach_rewake.sh      # asyncRewake Stop-hook core: OS-wait + exit 2 + pidfile cleanup
bash tests/t41_detach_pidfile_contract.sh # detach pidfile is a BAKED ABSOLUTE <PIDFILE> (never bare $CLAUDE_PROJECT_DIR,
                                    #   unset in the Bash tool) → writer(worker)==reader(hook); W27 foreground-run regression
bash tests/t17_resume_detached.sh   # the re-wake LANDING: resumeDetached finalizes from disk + clears state
bash tests/t4_decision_roundtrip.sh # decision-file write -> ingest -> archive + resume inference
bash tests/t5_vendored_load.sh      # config load + cfgval + role->model routing + isolation manifests
bash tests/t6_batch.sh              # single-idea select: first-Keep wins / no-keep ends / venue-validate,
                                    #   notes->HANDOFF, finishRun ship+abandon ends run, .polish seal
bash tests/t7_skeletons.sh          # venue skeleton resolution + REAL pdflatex smoke compile of every
                                    #   stocked assets/paper-skeleton*/ (needs TeX Live)
# RC-12 — enactment hardening: the [[MECH]] bookkeeping the L0 used to reproduce (and skip) is now bin/-enforced
bash tests/t42_archive_decision.sh  # deterministic gate archival: atomic mv, no stale PENDING, refuse UNANSWERED
bash tests/t43_lock_contracts.sh    # Phase-0(C) lock of §4b/§4c -> .locked.json; refuse re-lock w/o --ratchet
bash tests/t44_round_setup.sh       # per-round disclosure freeze + fail-loud hard-stop (idempotent, byte-identical)
bash tests/t45_decision_guard_hook.sh # PreToolUse: deny agent-authored DECISIONS-RESOLVED-* (L1 self-resolve)
bash tests/t46_milestone_done_provenance.sh # recorded commit must RESOLVE; --require-segment-commits kills E3 ghost
bash tests/t47_enactment_wiring.sh  # static: research.js calls the new bin/ scripts; V5 fail-closed; V8 metric-conformance
```

T1 and the LIVE halves of T2/T3/T5 need a real session (the `Task`/`Agent` tool, an active hook, or a
fresh plugin load) — their procedures + recorded results are below.

---

## T1 — nested spawn (L0 → L1 → L2) — **✅ RE-VERIFIED 2026-06-14 (Claude Code 2.1.177, live session); was FALSE-VERIFIED 2026-06-11**
> ⚠️ **SUPERSEDED in part (2026-06-25).** The line-38 premise — "BOTH built-in shells carry no Agent/Task tool
> as a subagent" — is NO LONGER reliable: the current harness grants the built-in catch-all worker the full
> `Tools:*` set, and a real run showed a producing-worker's built-in helper recursing into a multi-layer spawn
> tree. The correct, version-independent rule is the one stated below: a subagent CAN spawn IFF `Agent` is in
> its `tools`. The no-nest guarantee for the producing-worker tier is now **capability-defined** (it delegates
> only to types whose frontmatter omits `Agent` — `auto-research:leaf-worker` / `Explore` / `Plan`) **and
> hook-enforced** (`hooks/spawn_guard` hard-denies the built-in catch-all spawn). Do NOT rely on line 38.
**What.** A subagent that itself has the `Agent`/`Task` tool spawns a further subagent (the
subagent-as-orchestrator premise; HANDOFF fact #1, changelog v2.1.172 "max 5 levels").
**The 2026-06-11 "PASS" was INVALID — the root-cause bug.** That test spawned the L1 as
`general-purpose`/`claude` "with the Agent tool" — but AT THE TIME both built-in shells carried **no**
Agent/Task tool when used as a subagent, and PRODUCTION `spawnL1` spawned exactly `subagent_type:'claude'`.
So the recorded PASS exercised a premise the spec's real path never satisfied, then generalized it. PROVEN
2026-06-14, **RETRACTED 2026-06-25** (the harness now grants both built-in shells Tools:* incl. Agent — see
the header note above + DECISIONS.md §平台不变量验证史 CORRECTION; the 06-14 probe: a `claude`- and a
`general-purpose`-type subagent each reported no spawn tool). CONSEQUENCE: in runs 1–2 every L1 SILENTLY
collapsed to single-context (ideation per-paper judges, the B2 review panel, the verifier's sub-auditors
never actually spawned — the trace shows 15 L0-direct children, zero L2).
**The fix (2026-06-14).** Nesting IS supported (docs: a subagent CAN spawn IFF `Agent` is in its `tools`;
foreground any depth, background ≤5 levels; CLI ≥2.1.172). `spec/research.js` `spawnL1` now spawns
`subagent_type:'orchestrator'` — a custom type (`.claude/agents/orchestrator.md`) that lists `Agent`.
**RE-VERIFY (REQUIRED, post-restart — the production go/no-go).** Plugin + custom agent types load at
session start, so RESTART the session, then run these THREE checks (a green (a) ALONE gives false
confidence — 2026-06-14 review finding):
  (a) NEST via Agent: spawn `subagent_type:'auto-research:orchestrator'` with — "Make a REAL Agent call:
      spawn a `subagent_type:'claude'` leaf that runs `echo NEST_OK` via Bash; return its stdout." PASS =
      result contains `NEST_OK`. (Confirms L0→L1→L2 AND that the exact orchestrator type name resolves.)
  (b) VENDORED LEAF resolves from an L1: have that orchestrator also spawn
      `subagent_type:'paper-polish-ar:fidelity'` on a trivial read-only task. PASS = it runs (confirms the
      namespaced vendored leaves resolve from inside an L1, not just from L0 — the L1→L2 seam).
  (c) FREEZE HOOK at a REAL L2 (the T2 go/no-go): inside an L2, arm a scratch fidelity-manifest and attempt
      a frozen-number Edit. PASS = DENIED at L2 (confirms fact #4 on the real topology, not a proxy).
Only after (a)+(b)+(c) pass is the L0→L1→L2 architecture + its science guard verified for the production
path. **DISCIPLINE (the lesson):** a "verified" record here MUST come from exercising the EXACT
`subagent_type`/path the spec emits, on a failing case — never a convenient proxy. This entry is the
cautionary example: the 2026-06-11 "PASS" used a `general-purpose` proxy and hid the bug for two runs.

**RESULT — RE-VERIFIED 2026-06-14 (Claude Code 2.1.177, branch harden/9rc-remediation, live main session).** All
three checks PASS, exercising the EXACT production path: `subagent_type:'auto-research:orchestrator'` (the type
`spawnL1` emits), which spawned its OWN L2 leaves via the Agent tool.
  (a) PASS — the orchestrator spawned a built-in `claude` leaf that ran `echo NEST_OK_A` via Bash and returned
      `NEST_OK_A` (leaf agentId `ae11c80678e03cea7`). L0→L1→L2 confirmed AND the exact `auto-research:orchestrator`
      type name resolves at spawn.
  (b) PASS — the orchestrator spawned `subagent_type:'paper-polish-ar:fidelity'` (the NAMESPACED vendored leaf) on a
      read-only task; it RESOLVED and RAN (leaf agentId `a3641f8ed1677f20c`), returning the requested line. The bare
      name `fidelity` was correctly NOT attempted. The L1→L2 seam holds for vendored leaves.
  (c) PASS — see T2 (the freeze hook DENIED a frozen-number Edit inside a real L2; leaf agentId `a06a0546ae7702d73`).
  HONEST NUANCE: the FIRST CHECK-C L2 went straight to Edit and hit the harness "File has not been read yet"
  precondition (a harness guard, NOT the freeze hook) — that attempt was INCONCLUSIVE and was correctly NOT counted
  as a pass; a Read-then-Edit re-run then triggered the freeze deny.
  COVERAGE (why three checks verify ALL phases): every phase's L2 spawning reduces to these two leaf types —
  `claude` for goal-driven leaves (ideation per-paper judges, B1 experiment_worker / section_drafter, verifier
  sub-auditors) and `paper-polish-ar:*` for the review / polish / polish-figures vendored leaves. (a)+(b) cover both,
  and all phases route through the same `spawnL1`→`auto-research:orchestrator`, so nesting is verified pipeline-wide
  without a full run.

## T2 — anti-fabrication freeze hook fires at depth L2 (THE go/no-go) — **✅ RE-VERIFIED 2026-06-14 (Claude Code 2.1.177) at a real L2**
> ⚠️ The 2026-06-11 "PASS" used a `general-purpose` L0→L1→L2 chain (see T1 — that chain could NOT actually
> nest on the production path) AND the *plugin* `hooks.json` path, then INFERRED the rest. In run
> 20260613T195353Z the freeze hook NEVER fired during the PRODUCER phase: the manifest is armed only at
> B2/polish (never `runB1`), and a main-session PreToolUse hook did not reach the producer L1 — so the
> producer (the highest fabrication-risk surface) was UNGUARDED. Re-verify at a REAL L2 (after the T1 fix)
> with an ARMED producer manifest before trusting fact #4. The mechanical DENY arithmetic (t2_hook_logic.sh)
> still holds; what is UNVERIFIED is that the hook FIRES at the producer's actual depth.

**What.** The paper-polish PreToolUse fidelity hook (the anti-fabrication backbone) must DENY a
frozen-number edit even when the edit is attempted from a depth-L2 subagent. If it does not, HANDOFF §13
fallback (review stays at L0) triggers and the primary architecture changes — so this is the gate
PROTOCOL §1 requires before any L0 spec is written. (S1 hard-stop if it fails on both registration paths.)
**Procedure (live).** Arm the real freeze manifest at `$CLAUDE_PROJECT_DIR/.polish/fidelity-manifest.json`
(`mode:polish`, `manuscripts:[scratch .tex]`, freezing a number). (1) Positive control: L0 itself edits
the frozen number → must be DENIED (proves the hook is active + the manifest is found). (2) The test:
L0→L1→L2; L2 attempts the same edit → must be DENIED at L2; L1 and L0 re-read → number unchanged.
**Result 2026-06-11.** PASS, quadruple agreement: L0 positive-control DENIED; L2 edit DENIED with the
verbatim frozen-number reason; L1 re-read + L0 re-read both confirm `92.5` survived and `97.3` is absent.
**Registration-path detail (per §7).** This used the *plugin* `hooks/hooks.json` path (docs rank it
*lower* priority than project `.claude/settings.json`). The weaker path already propagated to L2, so the
repo's enabled `paper-polish-ar` plugin hook (same path) is at least as reliable. The repo therefore
relies on the `paper-polish-ar` plugin's `hooks/hooks.json` for the freeze hook (see DECISIONS.md D4).
**Mechanical companion.** `tests/t2_hook_logic.sh` (3/3 PASS) unit-tests the DENY arithmetic directly
against the vendored `check_fidelity.py` (drop-frozen→deny, reword-around→allow, no-manifest→no-op),
so the deny logic is re-runnable without a spawn.
**RESULT — RE-VERIFIED 2026-06-14 (Claude Code 2.1.177, live session) at a REAL L2.** Setup: armed
`$CLAUDE_PROJECT_DIR/.polish/fidelity-manifest.json` (mode:polish, one scratch `.tex` manuscript freezing the
number `92.5`). (1) Positive control: L0 itself attempted `92.5`→`97.3` → DENIED with the verbatim frozen-number
reason (proves the paper-polish-ar plugin PreToolUse hook is ACTIVE at L0 and FINDS the manifest). (2) The test:
`auto-research:orchestrator` (L1) spawned a `claude` L2 (agentId `a06a0546ae7702d73`) that attempted the SAME
frozen-number Edit → DENIED at L2 with the verbatim reason; the scratch `.tex` still read `92.5` afterward. Fact #4
holds on the PRODUCTION topology (real `auto-research:orchestrator`→`claude`-leaf chain), not a proxy.
**OBSERVATION (re-examines the run-2 "producer unguarded" diagnosis).** The project-settings tracer hook
(`bin/hook_fire_log.sh`, registered in `.claude/settings.json`) ALSO logged the L2's denied Edit (`.hook-fire.log`,
`manifest_found:true`) — so BOTH a plugin hook AND a project-settings PreToolUse hook fired INSIDE the L2 subagent.
This contradicts hook_fire_log.sh's own comment ("a MAIN-session hook does NOT fire inside L1/L2 subagents"). The
run-2 "producer unguarded" worry conflated "no freeze hook at B1" with "no guard": this hook guards the FREEZE
BOUNDARY (B2 review / polish / polish-figures), and BY DESIGN it does NOT apply to the producer — B1 legitimately
CREATES numbers from real experiment runs (you can't "freeze" a number being born, and a token check can't tell a
real result from a fabricated one). B1's anti-fabrication guard is the independent VERIFIER (runVerify, RC-1):
code-audit (every headline number script-computed, not a hardcoded/floor literal) + V6 artifact-sync + V4
reproduce-first. So no "producer manifest" is needed — the producer is guarded by the verifier, not by this hook.

## T3 — detach + asyncRewake (zero-token multi-hour wait) — **PASS (mechanism live; full roundtrip pre-fire)**
**What.** A long LOCAL experiment is launched DETACHED; L0 ends its turn; the asyncRewake Stop hook
OS-waits the PID at zero Claude-token cost and `exit 2` re-wakes the session (HANDOFF fact #8).
**Runnable here.** `tests/t3_detach_rewake.sh` (2/2 PASS) runs the REAL vendored `rewake-when-done.sh`
against a real `start_new_session` detached job: no-pidfile→silent exit 0; detached-job→OS-wait until
the PID exits, remove the pidfile, `exit 2`. This is the hook's whole mechanism minus the harness's
response to `exit 2`.
**Fresh-session check (owner).** The full end-turn → harness-re-wake roundtrip needs the
`paper-polish-ar` Stop hook active (a fresh session in this repo). Verified pre-fire 2026-06-11
(verified-platform-facts.md): the hook re-woke the interactive session and the post-launch marker was
present on resume. Re-confirm once in a fresh `~/auto-research` session before the first long experiment.

## T17 — resumeDetached: the re-wake LANDING (the other half of T3) — **PASS (mechanical, 2026-06-15)**
**What.** When T3's hook `exit 2` re-wakes L0, `main()` routes the non-empty `state.detached` to
`resumeDetached` (spec/research.js) — the inverse of `onLongRun`. It FINALIZES each detached `exp_ledger`
record FROM DISK (exit code + after-state + extracted numbers; mirrors the retired review.js's `resumeOneDetached` pattern),
reaps the pidfile, and clears `state.detached` so `batchGroundClean`'s quiesce invariant holds; the
dispatch loop then re-enters the same loop sub-phase (B1/VERIFY/B2) in resume mode and the L1 reads the
finalized ledger — it does NOT re-run and does NOT re-finalize.
**The bug this guards.** `resumeDetached` was CALLED at the rewake branch but never DEFINED — any rewake
with `state.detached` threw a `ReferenceError` (the long-experiment detach path, mechanism 6, was a
dead end). `tests/t17_resume_detached.sh` (10/10 PASS) is the regression: 9 spec-wiring asserts (the
function exists + drives `exp_ledger.py finalize` + finalizes only `running` records + clears the state +
reaps the pidfile + the B1 goal pins `state_path`=ledger and forbids re-run/re-finalize + `node --check`),
plus the mechanism end-to-end against the REAL `run-detach → rewake-when-done.sh → finalize` chain,
including the single-finalize guard (a second finalize errors `not finished yet` — why L0 must own it).

## T4 — decision-file roundtrip (+ fresh-session resume) — **PASS (live, mechanical)**
**What.** The durable human-gate backbone (HANDOFF §6): L0 writes `DECISIONS-PENDING.md`, ends turn; the
next turn ingests the answer (validate → archive to `DECISIONS-RESOLVED-<n>.md` → advance state); and a
fresh session infers the right entry point from `pipeline-state.json`.
**Runnable here.** `tests/t4_decision_roundtrip.sh` (4/4 PASS): writes a pending file from the template,
sets `pending_gate`, parses a filled `ANSWER:` (skipping unfilled `<placeholder>` lines), archives,
clears the gate, advances the stage; and asserts the `main()` entry inference
(pending_gate→ingest, detached→resume, else→startup card). The interactive AskUserQuestion *card* is the
live layer on top and is exercised at runtime (it cannot be scripted).

## T5 — vendored-plugin load + config — **PASS (mechanical); LIVE resolution = fresh-session check**
**What.** Skills resolve from the VENDORED `-ar` copies (not the global originals), config loads, cfgval
injection works, and role→model routing produces the configured model per role — with no collision.
**Runnable here.** `tests/t5_vendored_load.sh` (7/7 PASS): L0 config parses; `cfgval.sh` returns a real
key and fails loud on a bogus key; role→model routing matches §9; vendored plugin names are `-ar`;
`settings.json` disables both globals and enables the three `-ar` plugins (+ the marketplaces exist).
**Fresh-session check (owner) — the LIVE resolution.** Plugin enablement is read at session start, so
open a NEW session in `~/auto-research` (or run `/reload-plugins`), then confirm the skill registry
shows the `paper-polish-ar:*` / `arxiv-recommender-ar:*` skills and NOT the global `paper-polish:*` /
`arxiv-recommender:*` (i.e. the globals are shadowed in this project). Expected: only the `-ar` copies
are active. (Project-scope override of user-scope enablement is documented behavior — see DECISIONS.md /
RUNBOOK; confirmed by the claude-code-guide against the 2.1.173 docs.)

## T6 — single-idea selection + run-end mechanics — **PASS (mechanical, 2026-06-28)**
**What.** The single-idea layer (batch/queue REMOVED): GATE-1 ingest (`applyPickedIdea`) takes the ONE
picked idea = the FIRST Keep in presentation order (any other Keep is IGNORED), validates the default
venue against the prepared venues (a bad venue re-presents), ends the run if the owner kept NONE
(`stage='done'`, re-run to choose again), and resolves the per-idea note + `venue:` override into the
seed→HANDOFF goal. `finishRun` seals + records the final status and ends the run (`stage='done'`) on both
ship and abandon — there is no next item. `batchGroundClean` clears `.bg-pids` + `fidelity-manifest.json`
in BOTH the repo-root and the `runs/<slug>/` `.polish/` (V-A), refuses to seal over unquiesced detached
jobs, and KILLS any still-live PID a pidfile tracks before clearing it (never `rm` a live PID blind).
**Runnable here.** `tests/t6_batch.sh` (11/11 PASS) — python3 mirrors of the spec's [[MECH]] single-idea
logic; asserts the `batch` config block is GONE (SSOT). The interactive paginated Keep/Skip card + notes
capture is the live AskUserQuestion layer on top (annotations[question].notes — V-B) and is exercised at
runtime.

## T7 — venue skeleton resolution + smoke compile (HANDOFF stage 3) — **PASS (real compile, 2026-06-12)**
**What.** `resolveSkeleton(venue)` maps a venue rel's top-level name → `assets/paper-skeleton-<key>/`
(fallback: generic `assets/paper-skeleton/`), and EVERY stocked skeleton actually compiles — a broken
skeleton must fail here, not mid-run in a paper's INTEGRATED milestone.
**Runnable here.** `tests/t7_skeletons.sh` (10/10 PASS): key-mapping + fallback assertions, then a real
2-pass `pdflatex` of all four skeletons (generic article / JCP elsarticle / JChemPhys revtex4-2 aip,jcp /
Nature-Comp-Sci article-based — Springer's `sn-jnl.cls` is not in TeX Live; swap in at acceptance).

## loop_gate (B3 exit arithmetic) — **PASS**
`tests/test_loop_gate.sh` (15/15 PASS): EXIT on `accept`/`minor_revision` with 0 handoff + 0 write-backs;
CONTINUE when risk is worse OR there are new handoff items OR write-backs (under the cap, now 6); EXIT_AT_CAP at
`max_loop_rounds`; fail-loud (exit 2) on malformed input. PLUS the advisory `min_loop_rounds` soft floor
(2026-06-18, absorbs the planned t26): a clean EXIT below round 5 still EXITs but is flagged "converged early";
at/after the floor it is not flagged; the floor never forces CONTINUE.

## Loop-Adaptive Progressive Disclosure + RM2 foundation & flag-gated swap (Docs A/B/C §7) — **PASS (2026-06-18)**
The §7 redesign tests. All static-wiring tests are grep/parse assertions over the live spec (the behavioral
runs are the live items NEXT-REVIEW C10–C15); the fixture tests exercise real behavior.
- `tests/t20_round_concern_snapshot.sh` (7/7) — L0 freezes `.round-<N>.concerns.json` at round entry, logs
  `concern_snapshot_written`, fail-louds if the snapshot is missing, and every reader is told to read the
  FROZEN snapshot, never the live ledger (Doc B §6 / Doc A §3.3).
- `tests/t21_rm2_commit_at_finalize.sh` (25/25, FIXTURE+wiring) — PART A (H3): `exp_ledger.py finalize
  --commit-msg` atomically commits the run's products into a throwaway git repo + records `commit_sha` + marks
  finished (finalized ⟺ committed); WITHOUT `--commit-msg` it is capture-only (back-compat). PART B (the
  flag-gated git-revert RESUME swap): `bin/coordinated_revert.sh` reverts code to the latest FINALIZED run's
  `commit_sha` not the milestone sha (闭合②) and REFUSES a non-descendant run commit; `milestone_done.sh` under
  `AR_RM2_REACHABILITY=1` flags a milestone whose recorded commit was rolled past as NOT done (JSON-only would
  LIE); the swap is gated behind `rm2.git_revert_resume` (default false), a cold restart routes to
  `resumeViaGitRevert`, and a lost unit reruns DETACHED via the crash surface. The LIVE cold-crash→restart→rerun
  roundtrip itself is the deferred Doc B §8 item (the static suite cannot exercise it).
- `tests/t23_post_freeze_assertion.sh` (10/10) — `state.post_freeze` set idempotently at loop→rewrite + logged,
  reset per paper, `assertFinishingFreeze` WARN-not-throw at the 3 finishing stages, `polish.js` writes explicit
  `"mode":"polish"` (GAP-1), schema carries the new events (Doc B §3.2).
- `tests/t24_ledger_open_reopen.sh` (10/10) — the task-ledger SKILL pins the open/closed/reopened/deferred
  state machine, the close predicate (verify PASS ∧ B3 EXIT), dimension-agnostic shape, and the concern→map
  link (Doc A §2.1).
- `tests/t25_per_round_reference_shrink.sh` (12/12) — every loop/finishing goal-builder injects the PD pointer
  (`pdPointer`), the section_drafter PD is ALWAYS-ON (the one-time `drafting.concern_disclosure` gate knob was
  deleted 2026-07-06 as a dead, zero-reader key), the verifier reads the frozen
  snapshot as a resident sensor, and the canonical PROGRESSIVE DISCLOSURE section reached all 6 phase specs
  (with experiment-protocol scoping it to the section_drafter, never the experiment_worker) (Doc A §3.2/§6.4).
- `tests/t27_concern_map_presence.sh` — `concern-reference-map.yaml` + `spec/spawn-prompts/VERIFY-PROTOCOL.md`
  exist; EVERY concern reference resolves to a real file; VERIFY-PROTOCOL.md carries V1–V10 + NO-DEMOTION +
  VERDICT + all 8 substitution tokens; `paths.concern_map` is wired AND `verify_spec` is NOT a config path —
  verifierGoal references the rubric directly from `spec/spawn-prompts/` (spawn prompts are not config; Doc A §3.1/§6.5).
- `tests/t16_polish_stage.sh` — updated for the EXIT→`rewrite`-first finishing chain + the Ledger② cross-check.
- `tests/t22_asyncrewake_regression.sh` (8/8) — RM2 must NOT regress the in-session zero-token wait: against a
  REAL live detached run the `anyDetachedAlive` ALIVE predicate is true, so `rm2.git_revert_resume &&
  !anyDetachedAlive` is false (the cold-restart swap is provably NOT entered mid-run) and the proven asyncRewake
  re-arm + Stop-hook OS-wait own the live experiment (Doc B §5.1/§8). `tests/t19_crash_surface.sh` gained a (D)
  section: the cold-restart git-revert resume reruns a LOST unit through the SAME crash surface
  (recordDetachedCrash → crashSurface → forced detached), never blind foreground.
- `tests/t28_flowchart_phase.sh` (23/23) — the 流程图 (flowchart) finishing phase (Doc A §7): a `flowchart`
  stage + `runFlowchart`/`flowchartGoal` (NON-FATAL, config-gated, idempotent on `flowchart-report.md`),
  `shipAfterCrossCheck` routes cross-check→flowchart→ship, the new `-ar` work-spec
  `paper-polish-ar/spec/flowchart.md` + skill `paper-polish-ar/skills/flowchart-diagram` exist + are wired
  (config toggle/spec/model/budget + command preflight), and the MECHANISM: `render_diff_ladder.sh` gives a
  `flowchart:` commit its OWN distinct diff-ladder rung (ORDERING-2). `t16_polish_stage.sh` gained the
  flowchart chain + config assertions.
- t26 (min-loop floor) is merged into `test_loop_gate.sh` (above).
- `tests/t29_polish_ledger_and_state.sh` (21/21) — refinement D (Doc A §10-E, DECISIONS D15): the /polish
  convergence model is now a CATEGORICAL state ladder (`clean > cosmetic-only > has-core > unrecoverable`,
  numeric weighting REMOVED) and /polish writes a deterministic per-SECTION open-items ledger
  `TASK_STATUS.polish.concerns.json` (task-ledger `id/concern/status`). Asserts: (1) the rewritten
  `scripts/polish_converge.py` PASSES `scripts/test_polish_converge.py` — wired into the suite for the FIRST
  time (it ran nowhere before) — and carries the ladder (`RANK`/`round_state`) with NO weighted arithmetic;
  (2) `spec/polish.js` defines `recordSectionLedger`/`writePolishLedger`, emits the `.concerns.json` with a
  derived `open_concerns`, carries the D-2 reviewer rule ("a cosmetic flag earns ≥1 attempt before it may be
  deferred"), feeds the script a STATE history, and has NO `WEIGHTS`/`near_converged`/`all_pass`/`best_weighted`
  left; (3) config `flag_weights` block removed, round knobs kept; (4) `research.js` `polishGoal` reads the
  spec-written ledger (`pdPointer` `specWritten`). NOT covered (owner-deferred): the abstract 1–10 LLM scoring.

- `tests/t30_audited_values_register.sh` (14/14) — the forward-carried `auto-research/audited-values@1` registry
  (DECISIONS D16 P1): `exp_ledger.py register` writes a paper number's provenance INCREMENTALLY at production
  time so a downstream provenance auditor can RE-DERIVE it. Asserts the core CLI subcommand (require-audit on a
  pass record / idempotent re-register / fail-closed on a pending record / B1-path without require-audit / the
  re-derive provenance fields + schema stamp), PLUS — [[D17]] — that `spec/review.js` wires the live production
  caller `registerAudited` (`register --phase B2 --require-audit`) and the retired blessed-swap `bless` is gone.
- `tests/t31_consolidate_mode.sh` (15/15) — the fidelity hook's `consolidate` mode (D16 P2/Q5) + [[D17]] /review's
  adoption of it. Hook level: a new prose number+cite is ALLOWED (post-hoc gated), the .bib denylist + Write-on-
  manuscript stay DENIED, the same new number is DENIED under `review` mode (consolidate ≠ review), absent manifest
  is a no-op. review.js level (D17): both manifest builders emit `mode:"consolidate"` and no live `review`/
  `experiment` mode; the blessed-swap path is retired; the post-hoc `runProvenanceAudit`/`auditNumbersAndRecover`
  + `PROV_AUDIT_SCHEMA` (GROUNDED/DERIVED/UNGROUNDED) + per-wave `EXPERIMENT-RUNBOOK` + `registerAudited` are wired;
  the AC `experiment_coverage` (M1) + reviewer `section_structure` (M7) + `caption_axis_fidelity` (M6) surface; and
  the central-claim gate (`mechanicalDilution` + `runSurfacing`) is KEPT (D17 (F) invariant).

`tests/run_all.sh` runs all of the above: **28/30 PASS** (Claude Code current build; the 2 failures are the
owner-WIP `t5_vendored_load` settings.json + `t16_polish_stage` figures.model-pin, NOT regressions — see
DECISIONS D16/D17 status). 2026-06-18.

- `tests/t59_learn_resolve.sh` (8/8) — /learn run/path resolution (`bin/learn_resolve.sh`): state-based default,
  arg forms (slug / run-id prefix / workspace path), busy-pipeline flags (pending gate refuses; mid-stage refuses
  only the no-arg form), degraded traceless-run flags + synthetic run_id + mtime fallback, DOSSIER_HOME source-repo
  vs outbox split (AR_LEARN_SOURCE_REPO hermetic), loud refusals (unresolvable / ambiguous prefix).
- `tests/t60_learn_manifest.sh` (6/6) — the /learn mechanical manifest (`bin/learn_manifest.py`): glob families
  match BOTH artifact-name vintages (old underscore names + modern), expected-vs-conditional gap semantics,
  per-group event slices (C1/C2 share the loop slice; unknown stage → meta), cache-vs-source spot-sha drift
  detection + run_spec_commit from the frozen block, the 60-line summary cap, honest DEGRADED flags.
- `tests/t61_run_report_rollup.sh` (4/4) — `run_report.py rollup`: machine JSON totals from transcripts (output
  tokens by role via the semantic join, by model), spawns-by-stage excluding hook twins, gate open→answer pairing,
  detach counters, `--out` persistence.
- `tests/t62_learn_hypotheses.sh` (6/6) — the hypothesis tracker (`bin/learn_hypotheses.py`): init/list/validate/
  apply lifecycle, the deployed-before-verdict invariant (pre-deploy runs can only record `unmeasurable` — the
  cache-drift lesson), refusals (dup id / bad enum / unknown id / missing fields), atomic refused-apply.
- `tests/t63_learn_wiring.sh` (5/5) — /learn static wiring: learn.js↔rubric-file bijection, config `learning:`
  block completeness, commands/learn.md MISS-loop coverage (all named files exist), key-config learning mappings
  resolve (`apply_key_config --check` exit 0), rubric token headers ↔ learn.js injections.

`tests/run_all.sh`: **62/62 PASS** (57 pre-existing + t59–t63) after the /learn feature landed. 2026-07-07.
