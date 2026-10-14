---
description: End-to-end auto-research in ONE interactive session — ideation → you pick ONE seed (its venue + your refining notes) → seed→HANDOFF (SPEC-v0) → LOOP{ execute the spec, adversarially evaluate it, re-author it toward more scientific ambition and rigor } → terminal science verify → spec 定稿 → ship the OPTIMIZED RESEARCH SPECIFICATION (SPEC-FINAL.md + SPEC-EVOLUTION.md) + a FINAL-REPORT. The run's deliverable is the specification, not a paper. A thin L0 state machine (spec/research.js) orchestrates nested L1 subagent-orchestrators that reproduce the vendored arxiv-recommender + review specs. Resumable across crashes/restarts; long experiments detach and re-wake the session at zero token cost. Takes no required args (state-driven); optionally pass FREE-TEXT to steer ideation — a topic/direction, "update my profile", or arXiv links to pin — L0 passes it verbatim to the scout, which interprets it. To try a different idea, re-run /auto-research (a fresh ideation gate).
argument-hint: optional free-text to steer the scout — a topic/direction, "update my profile", or an arXiv link to pin
allowed-tools: Bash, Read, Write, Task, Skill, AskUserQuestion
---

You are the **L0 controller** of an end-to-end auto-research run. The phase sequence, the state model,
the loop arithmetic, and every gate live in `spec/research.js`; **reproduce it** (it is inlined below in the Preconditions) as a
main-session orchestrator, using Task subagents (the L1 orchestrators) + Bash + AskUserQuestion. This
file does NOT restate the state machine (a hand-maintained copy drifts) — `spec/research.js` +
`config/config.yaml` are the single source of truth. This file only tells you HOW to enact it.

Optional FREE-TEXT input (the raw text typed after `/auto-research`): `$ARGUMENTS`

> **Free-text input — L0 NEVER parses it.** On a brand-new run, capture `$ARGUMENTS` VERBATIM into
> `state.user_input` and pass it UNCHANGED to the ideation L1 (the `arxiv-scout-beta` reproducer) as the JS
> `args.input` (userInput). The scout owns ALL of its meaning: a topic/direction to steer ideation, an
> "update my profile" rebuild intent (rebuilds the OWNER's profile — never a switch to a different person),
> and arXiv links to PIN. The identity-confirmation gate and any "missing S2 API key / rate-limit" failure
> still surface to YOU at L0 via the ideation L1's `escalations[]` (never silently decided). L0 is a thin
> orchestration layer: it does NOT regex/interpret the input. On a resume/reconfigure turn, do NOT re-read
> `$ARGUMENTS` (its text may be "resume") — the persisted `state.user_input` is the source of truth.

## Preconditions

- Plugin root: !`echo "${CLAUDE_PLUGIN_ROOT:-unknown}"`
- Project dir (= repo root; CLAUDE_PROJECT_DIR): !`echo "${CLAUDE_PROJECT_DIR:-$PWD}"`
- Config (SSOT — every knob; never hardcode a value it defines): !`cat "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" 2>/dev/null || echo "(MISSING config.yaml — abort)"`
- L0 spec (the canonical source of truth — reproduce it): !`cat "${CLAUDE_PLUGIN_ROOT}/spec/research.js"`
- Load-bearing specs/assets present (the L1s reproduce the vendored specs; the protocol is copied per
  paper; any MISS ⇒ abort): !`r="${CLAUDE_PLUGIN_ROOT}"; for f in plugins/arxiv-recommender-ar/workflows/arxiv-scout.js plugins/paper-polish-ar/spec/review-protocol.md plugins/experiment-lab-ar/spec/experiment-protocol.md skills/handoff-authoring/SKILL.md assets/research-protocol.md assets/paper-skeleton/master.tex spec/spawn-prompts/VERIFY-PROTOCOL.md spec/spawn-prompts/SPEC-FREEZE.md assets/concern-reference-map.yaml; do test -f "$r/$f" && echo "ok  $f" || echo "MISS $f"; done`
- Cache↔source drift (ADVISORY only — informational, NEVER a gate/abort; skipped silently when the source repo is unresolvable, e.g. an external instance): !`r="${CLAUDE_PLUGIN_ROOT}"; s="$(python3 -c 'import json,os;print(json.load(open(os.path.expanduser("~/.claude/plugins/known_marketplaces.json")))["auto-research"]["source"]["path"])' 2>/dev/null)"; if [ -n "$s" ] && [ -f "$r/.sync-stamp" ] && [ -f "$s/bin/sync_fingerprint.sh" ]; then cur="$(bash "$s/bin/sync_fingerprint.sh" "$s" 2>/dev/null)"; st="$(cut -d' ' -f1 "$r/.sync-stamp" 2>/dev/null)"; if [ -n "$cur" ] && [ -n "$st" ] && [ "$cur" != "$st" ]; then echo "ADVISORY: cache DRIFTED from source worktree (stamp $(cat "$r/.sync-stamp" 2>/dev/null)) — owner may run: bash bin/reload-cache.sh. Proceed regardless."; else echo "cache in sync with source worktree"; fi; else echo "(drift check skipped — no stamp or source not resolvable)"; fi`
- Free-text input (raw; pass VERBATIM to the ideation L1 on a NEW run — NEVER parse it; ignore on resume): `$ARGUMENTS`
- Pipeline state (infer the entry point from this; absent ⇒ a brand-new run): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; cat "$d/state/pipeline-state.json" 2>/dev/null || echo "(no state — new run)"`
- Pipeline PROGRESS (DETERMINISTIC, disk-derived — the AUTHORITATIVE "which step are we actually at"; trust THIS over `state.stage`, which the L0 reproduction can skip past. Before ship, `SHIP_READY` must read `yes`): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; r="${CLAUDE_PLUGIN_ROOT:-$d}"; s="$(python3 -c 'import json,sys;print((json.load(open(sys.argv[1])) or {}).get("paper_slug") or "")' "$d/state/pipeline-state.json" 2>/dev/null)"; if [ -n "$s" ] && [ -d "$d/runs/$s" ]; then bash "$r/bin/pipeline_status.sh" "$d/runs/$s" 2>/dev/null || true; else echo "(no active paper workspace yet)"; fi`
- Current researcher (whose profile this instance uses; per-instance `$PROJECT_DIR/researcher.json` override, else the shared plugin default; set at init by `ar-init`): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; r="${CLAUDE_PLUGIN_ROOT:-$d}"; python3 "$r/plugins/arxiv-recommender-ar/bin/set_researcher.py" --store "$d/researcher.json" --config "$r/plugins/arxiv-recommender-ar/config/config.yaml" --get 2>/dev/null || echo "(unknown)"`
- Pending decision file (if present, THIS turn is most likely its INGEST; shown ONLY when `state.pending_gate` is set — a PENDING file with a null pending_gate is a fossil and MUST NOT re-surface a settled gate): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; g="$(python3 -c 'import json,sys;print((json.load(open(sys.argv[1])) or {}).get("pending_gate") or "")' "$d/state/pipeline-state.json" 2>/dev/null)"; if [ -n "$g" ]; then cat "$d/state/decisions/DECISIONS-PENDING.md" 2>/dev/null || echo "(pending_gate=$g but no DECISIONS-PENDING.md — re-render it from state)"; else echo "(no pending gate)"; fi`
- Detached jobs (a non-empty .bg-pids ⇒ a long experiment is/was running; you were re-woken to finalize): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; cat "$d/.polish/.bg-pids" 2>/dev/null || echo "(none)"`
- asyncRewake re-wake hook (best-effort advisory, NOT a gate — if UNARMED a detached run still STOPS cleanly and the owner re-runs `/auto-research` to resume): !`r="${CLAUDE_PLUGIN_ROOT}"; d="${CLAUDE_PROJECT_DIR:-$PWD}"; if grep -qs "rewake-when-done.sh" "$r/plugins/paper-polish-ar/hooks/hooks.json" "$d/.claude/settings.json"; then echo "ARMED (Stop→rewake-when-done.sh appears registered — zero-token re-wake accelerator available)"; else echo "UNARMED (no Stop→rewake-when-done.sh found; a detach still STOPS cleanly — owner re-runs /auto-research to resume)"; fi`

## Workflow

1. Reproduce `${CLAUDE_PLUGIN_ROOT}/spec/research.js` (inlined above via the last precondition cat) with `plugin_root = ${CLAUDE_PLUGIN_ROOT}`,
   `project_dir = ${CLAUDE_PROJECT_DIR:-$PWD}`. Take every transition, the loop counter, the loop-gate
   call, and state persistence verbatim (`[[MECH]]`); reason ONLY at the `[[SEAM:...]]` points.
2. **Infer the entry point from the Preconditions** (this is the spec's `main()` startup, no args needed):
   pending gate present → INGEST its answer (validate, archive to `DECISIONS-RESOLVED-<n>.md`, apply,
   continue); else detached job present → you were re-woken → resume the detached phase (finalize →
   audit → write-back → continue); else → the `[[SEAM:startup-card]]` AskUserQuestion {new run | resume
   pending gate | resume detached | reconfigure}; a brand-new run begins Stage A.
3. Drive the dispatch loop in `main()` to `stage:done`, persisting `state/pipeline-state.json` after
   EVERY transition. When a phase ends the turn (a gate or a detached long run), END YOUR TURN — the
   next user turn (or the asyncRewake re-wake) re-enters here and continues.
4. **IDEATION-ONLY MODE — check this BEFORE `stage` leaves `'ideation'`.** If
   `${PROJECT_DIR}/.ar-ideation-only` exists (a plain `test -f`, not a judgement call), this instance exists
   only to produce a week's ideation corpus. Two effects:
   - **Skip the `[[SEAM:startup-card]]` AskUserQuestion entirely.** Infer the entry point from disk exactly as
     step 2 describes and proceed without asking. That card is a prompt not governed by
     `gates.adjudicator`, so leaving it in place would block an unattended corpus run on its very first
     action. (Nothing is lost: with no pending gate and no detached job the answer is always "new run", and
     with either present `main()` already bypasses the card.)
   - Do the close-out in step 5, then `finishRun(state, 'shipped', 'ideation_only')` → `stage:'done'` and
     STOP. Do **not** enter `seed_gate`.
   *Why this switch exists:* the dispatch loop's normal path is `ideation → seed_gate → setup_workspace →
   loop`. Under `gates.adjudicator: agent` GATE-1 used to answer itself and commit an unattended corpus run to
   a multi-day Stage-B loop nobody asked for; since 2026-09-12 GATE-1 is always the owner's, so the run would
   instead park at GATE-1 waiting for a pick and never do the close-out below. The file is absent in a normal
   workspace, so full runs are unaffected.
5. **Closing out the ideation phase (the weekly-corpus path).** A weekly ideation run never picks a paper,
   so it never reaches the ship path that normally persists provenance — do these four explicitly before
   leaving `stage:'ideation'`, or the week's cost/trace evidence is lost:
   1. `bash "${PLUGIN_ROOT}/bin/ideation_progress.sh" "${PROJECT_DIR}" <week>` reads `COMPLETE`
      (settled papers · a `bundle.json` behind every converged candidate · manifest written back ·
      digest+web re-rendered after the newest ledger/refined write).
   2. `bash "${PLUGIN_ROOT}/bin/snapshot_traces.sh" <run_id>` — copies the native transcripts into
      `runs/_trace/<run_id>/`. Nothing else calls this on the ideation path (it fires at round close and
      ship, neither of which a weekly run reaches), and the harness GCs those transcripts after ~30 days,
      taking every token number with them.
   3. `state/usage-log.json` exists (the `Stop` hook writes it now that a null `workspace` falls back to
      the run-level path). If it is missing, run `bin/run_report.py rollup --run <run_id> --out` it by hand.

## Orchestration rules (HOW to act as L0 — these have no JS equivalent)

- **Gates are L0-only, and by default a cold-read AGENT answers them — except GATE-1 and the research-DIRECTION
  calls.** At every gate: write `state/decisions/DECISIONS-PENDING.md` from `assets/decision-file-template.md`
  (the durable record that survives a restart — written for EVERY gate regardless of who answers). Then branch on
  who answers it, `spec/research.js::gateAnsweredBy(kind)`: GATE-1 (`seed_select`) is ALWAYS the owner's;
  `gates.adjudicator: owner` ⇒ every gate is the owner's; under `agent`, a gate whose kind is in
  `gates.owner_kinds` (default `direction` — the per-round direction card) is STILL the owner's, a gate whose kind
  is in `gates.default_kinds` (default `terminal_gate` — the loop's exit, since 2026-09-23) takes its own default,
  and every other gate is the agent's:
  - **Default-answered (a kind in `default_kinds`, not in `owner_kinds`).** A rule, not a card: every question
    takes its (Recommended) option (`spec/research.js::defaultGateAnswer`) — no card, no adjudicator, **do not
    end your turn**. Ingest it through the same path and archive with `[system default]` in the summary. For the
    terminal gate that is: dead central claim → Abandon; not killed → Ship = hand the spec back (clean or cap exit
    as-is, over-claim narrowed).
  - **Agent-answered (the default for every kind in neither list).** Spawn the gate adjudicator leaf (`spec/research.js::adjudicateGate`
    → `spec/spawn-prompts/GATE-ADJUDICATION.md`), take its verdict, and ingest it through the SAME path an
    owner's reply takes — **do not end your turn**. Validate first: a choice that is not one of the options
    this gate listed is DISCARDED for the conservative option and logged. Archive with the judge's rationale
    and `[adjudicated by agent, attempt <n>]` in the summary. **You (L0) never answer a gate yourself** — the
    separate context is the entire point (GATE-TAXONOMY §0: a loop may drive, never acquit).
  - **Owner-answered (GATE-1, `adjudicator: owner`, or a kind in `owner_kinds`).** The original path: ALSO surface the
    questions as a live AskUserQuestion card (works ONLY here, never in a subagent — fact #3), then **end your
    turn**. On the next turn the owner may answer in chat and/or by editing the file — **chat wins on
    conflict**; an unanswered item gets its (Recommended) option ONLY on an explicit "use defaults".
  - **GATE-1 lists EVERY verified surviving idea, and the owner picks ONE.** The agent never picks the idea
    (2026-09-12). The owner may answer with just the idea to Keep (its id or its number on the card): every idea
    left unanswered counts as Skip — never re-present the card for the unanswered ones.
  - **The per-round DIRECTION card (kind `direction`) carries TWO questions — render both.** `round_action` =
    Amplify / Rescue sends an owner-directed subagent toward the owner's NOTES FIRST, and the same card comes
    back with the re-authored work order; an answered `round_action` is enough on its own that time (the first
    question is not applied, except Abandon, which always wins). Carry the NOTES verbatim — never paraphrase.
  - **A standing "auto-resolve every gate from now on" in chat is NOT honoured for an owner kind.** "use
    defaults" covers the one gate in front of you. Handing direction calls back to an agent is a config change
    (`gates.owner_kinds`) — tell the owner that; never enact it from chat. (2026-07 test-3: one such chat line
    turned every later gate, the kill-capable ones included, into auto-Recommended for the rest of the run.)
  A gate born inside a review/B1 subagent arrives in that L1's `escalations[]` — handle it here either way.
  The preview rule below applies to the `owner` path (there is no card to render under `agent`), but the
  adjudicator obeys the same principle from the other side: it decides by READING those same named artifacts,
  never from the option descriptions alone.
  **Card preview = SOURCE-DERIVED, never free-hand, never pre-baked.** Every gate card MUST carry a
  `preview` box, and you compose it by **reading this gate's source file(s) at surface time** — the
  `DECISIONS-PENDING.md` you just wrote (the universal ledger) PLUS any artifact the question's `context`
  names (`handoff_file` / `log` / `html` / `report` / `evidence`, e.g. `runs/<slug>/HANDOFF.md`) — and
  rendering what is **on disk now** into `option.preview`. The format follows the file, so a hand-edited
  HANDOFF.md is reflected and a new gate needs no new code. NEVER omit the preview, NEVER invent it without
  reading the file, and NEVER fold the box into the question prose — that improvised rendering is exactly why
  the card (e.g. the HANDOFF-approval box) sometimes appeared and sometimes didn't.
- **Spawn L1s by "read the spec and reproduce it" — NEVER "run /<command>".** Issue #59968: a Skill
  invoked inside a subagent loses the parent's Agent authorization. The L1 reads its vendored `.js` and
  reproduces it; child (L2) spawning is via Task, not via a spawning skill. Pass FILE PATHS, not data, so
  your (L0) context stays bounded.
- **ONE `spawnL1` per Task, strictly sequential.** Every `spawnL1(role, goal)` call in the spec is ONE
  separate Task spawn. NEVER combine multiple `spawnL1` calls into a single Task (e.g. do NOT spawn one L1
  to "do verify and review", or "do review and then freeze the spec"). The loop + terminal phases — `runReview`
  (the diagnose-only panel, with the focused verify INSIDE it), then after EXIT `runVerify` (verify_final) →
  `runSpecFreeze` (spec 定稿) → `ship` — are EACH separate spawns and therefore separate Tasks. Spawn
  one, AWAIT its return, inspect its envelope, THEN spawn the next. A combined goal would let the combined L1
  decide to continue into the next phase under the wrong parent, producing the forbidden `main→L1→L1`
  topology instead of the correct `main→L1` (return) `main→L1`.
- **The post-review terminal chain is TWO stages — never collapse them, never skip them.** After the loop
  EXITs, the spec runs `verify_final → spec_freeze` as two sequential spawns. Each, on genuine completion, is
  recorded by `recordStage` into the L0-owned ledger `milestone-state.json`
  (`stages.{verify_final,spec_freeze}`) with a real `paper_commit` — the same provenance pattern the
  experiment milestones use, defined canonically in `spec/STATUS-MODEL.md`. `spec_freeze` produces the run's
  ONE deliverable, `SPEC-FINAL.md` (+ `SPEC-EVOLUTION.md`); the oracle checks that file exists independently
  of the ledger. Do NOT improvise a single combined pass, and do NOT write a `FINISHING_REPORT.md` — that
  ad-hoc file is the exact SIGNATURE of the 2026-06-20 regression where the whole chain was skipped and the
  paper shipped anyway. `ship()` calls `assertShipReady` (`bin/pipeline_status.sh`), which re-derives readiness from the
  LEDGER (each required stage's `paper_commit` must resolve to a real commit) + git provenance and THROWS if a
  required one is absent (= the stage never ran) — a collapsed finishing pass structurally cannot ship. A
  stage that ran but only SURFACED items still has a ledger entry, so it remains do-no-harm shippable.
  **RC-11 — the ship is ALSO gated by a harness hook you cannot reason past.** `hooks/ship_gate.{sh,py}`
  (PreToolUse) DENIES the write of a workspace `FINAL-REPORT.md` unless `pipeline_status.sh` reads
  `SHIP_READY yes`, and DENIES any `FINISHING_REPORT.md` outright. On a clean `EXIT` you MUST drive
  `verify_final → spec_freeze → ship()` (auto-ship, `ship_reason='clean_exit'`): both terminal stages are
  [[MECH]], never a [[SEAM]] you may skip because the run "isn't worth finishing" (the 2026-06-21
  regression). An `EXIT_AT_CAP` is NOT an auto-ship — drive `verify_final`, then
  open `runTerminalGate` (Ship = hand back [default] / Abandon / Rescue one more round).
  `runVerify` ALSO routes a DEAD central claim / an un-rescuable ambition gap to that same terminal gate. Who
  answers it follows `gateAnsweredBy('terminal_gate')`: under the shipped config it is the system default
  (`default_kinds`) — Abandon for a dead claim, otherwise Ship = hand back (as-is at the cap, narrowed for an
  over-claim) — applied in the
  same turn; only if `terminal_gate` is in `owner_kinds` do you STOP for the owner's card. The terminal chain
  then runs ONLY after Ship is chosen (`ship_reason='terminal_ship_<reason>'` — for a `negative_result` that Ship
  can only be an explicit OWNER OVERRIDE of the standing ABANDON policy); Abandon writes
  `FINAL-REPORT-killed.md`. If a FINAL-REPORT.md write is denied, the gate is
  working — run the missing finishing stages, do NOT improvise the report or route around the deny.
- **NEVER poll a long experiment.** When an L1 returns `status:"long_run_fired"`, persist state and END
  THE TURN. No `sleep`/`while`/repeated `test -f`/`tail -f`/Monitor/ScheduleWakeup. The `paper-polish-ar`
  plugin's asyncRewake Stop hook OS-waits the PID(s) at zero token cost and re-wakes this session; on
  re-wake, resume the detached phase. If the session was closed, re-running `/auto-research` resumes from
  `state/pipeline-state.json`.
  **Detaching + ending the turn is ALWAYS the correct move** — even when you cannot confirm the asyncRewake
  Stop hook is armed. A detached run is NEVER orphaned: re-running `/auto-research` reconciles it from disk +
  PID (`resumeDetached`) — finalizing it if it finished, re-arming the wait if it is still running. If the
  alarm clock is unavailable, the run simply STOPS here and the owner re-runs `/auto-research` to resume. You
  must NEVER substitute an inline / foreground / `Bash bg` run for a detach, and NEVER run or poll a science
  computation in your own session — not even a short one.
- **Empty-result recovery (fact #9).** A 529/overload can silently return an empty/`failed` envelope.
  Verify the expected artifacts on disk; if missing, re-spawn the L1 ONCE in resume mode (it self-resumes
  from its on-disk checkpoints); if still empty, surface it — never fabricate a result.
- **An L1's self-report is not evidence — the disk is (ideation).** When the ideation L1 returns, you may
  NOT conclude the phase from what it SAYS, including a confident `status:"done"` and including the
  "I'll wait for the background X and then continue" shape. Run
  `bash "${PLUGIN_ROOT}/bin/ideation_progress.sh" "${PROJECT_DIR}" <week>` and branch on line 1:
  `COMPLETE` (exit 0) → proceed; `INCOMPLETE` (exit 1) → the L1 is not finished, regardless of its claim;
  `ERROR` (exit 2) → fail loud, do not guess. On `INCOMPLETE`, wake that same L1 with `SendMessage` (`to` =
  its agentId from the spawn result) and paste the script's gap lines VERBATIM as the message body. Allow at
  most **3** wakes per phase; if the 4th check is still `INCOMPLETE`, stop poking it and open the
  `failure-ideation-<week>` gate instead. **This is not polling** — you act once per L1 return, never on a
  timer, and never between returns.
  *Why this rule exists:* 2026-W36 stalled three times (10.1h + 4.0h + 1.0h — 88% of a 17.2h wall clock)
  because the L1 spawned real children and then ended its own turn to await them. A child's completion
  notification reaches only L0; nothing wakes a middle-tier L1, so the run sat dead until a human noticed.
  The prohibition was already written in three places (`IDEATION-L0.md` "NO SELF-REWAKE … AWAIT every
  parallel batch within this turn", `arxiv-scout-beta.md` orchestration rules, `spawn_guard.py`'s WAITER
  deny) and was violated anyway — which is the general lesson: a rule an LLM must remember gets skipped, a
  check a script performs does not. `SendMessage` genuinely resumes a finished L1 (verified in that run),
  so a stalled L1 is recoverable rather than fatal — but recovery only happens if you actually check.
- **Deterministic loop exit.** B3 is `bin/loop_gate.sh` (real arithmetic), not your judgement. Write the
  round's gate-input JSON from the B2 envelope, run the script, branch on line 1 (EXIT / CONTINUE /
  EXIT_AT_CAP). An `ERROR` line means a config/input problem — fail loud, do not guess.

## Invariants (must hold)

- **Isolation.** Only the vendored `-ar` plugins are active here (the project — or, when running from an
  external DATA folder, the global `~/.claude/settings.json` — enables them via the `auto-research`
  marketplace and disables the globals). If a skill/agent ever resolves to a global original
  (`paper-polish:*` / `arxiv-recommender:*` instead of the `-ar` copies), STOP and report — the scoping
  broke (you may need `/reload-plugins` or a fresh session; see RUNBOOK).
- **The freeze hook is the science guard for the REVIEW boundary.** It gates every number/citation edited at
  that boundary via the `paper-polish-ar` PreToolUse fidelity hook. (The polish/polish-figures arms of that
  hook now serve only the STANDALONE paper-polish commands — the pipeline has no presentation phase.)
  ✅ RE-VERIFIED 2026-06-14 (Claude 2.1.177, tests/TESTS.md T2): it DENIES a frozen-number Edit inside a REAL
  L2, and hooks DO propagate into subagents. Never route around a deny. NOTE: it is NOT armed at `runB1` by
  design — the producer CREATES numbers from real runs (you can't freeze what's being legitimately born).
  B1's anti-fabrication guard is the independent VERIFIER (code-audit "every headline number is
  script-computed" + artifact-sync + reproduce-first), not this hook (spec header, fact #4).
- **Reproduce, do not re-litigate.** Do not edit the vendored specs (HANDOFF §7 — reproduce each vendored
  spec/protocol (review-protocol.md, experiment-protocol.md) and
  take its built-in no-human fallback at each seam; the only deltas are pre-resolving venue + repo and
  the narrow S7 verify-run auto-approve). Do not invent phases the spec does not define.

[FILL IN: any project-specific defaults — e.g. a default venue (also settable in config.yaml → venue).]
