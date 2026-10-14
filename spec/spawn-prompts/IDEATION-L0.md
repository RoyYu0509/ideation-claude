<!-- IDEATION-L0.md — the L0 DELTAS for reproducing arxiv-scout-beta.md as an L1 subagent.
     The FULL ideation behavior lives in the vendored command commands/arxiv-scout-beta.md (the agentic stand-in
     for /arxiv-scout) — reproduce THAT. This file carries ONLY what differs because the reproducer is an L1
     SUBAGENT, not the main session that command assumes. The slim phaseIdeation goal injects the raw USER_INPUT
     block + substitutes the <TOKENS> below; it adds no behavior of its own.
     TOKENS the goal-builder substitutes (every one MUST be replaced before the goal ships):
       <PLUGIN_ROOT>  the read-only SHARED code root
       <PROJECT_DIR>  the per-instance DATA root (cwd)
-->

Reproduce commands/arxiv-scout-beta.md EXACTLY (phase sequence, Phase→action map, every gate/knob, the
$ARGUMENTS↔userInput binding, and the completion rule — all there + in the arxiv-scout.js it embeds). Do NOT
re-derive any of that here. Apply these L0 deltas — you are an L1 SUBAGENT, not the main session that command assumes:
  • HEADLESS (fact #3): you CANNOT AskUserQuestion. Where the command runs the Phase 0c identity gate in the
    main agent, instead RETURN it — plus the S2-key/rate-limit and scrape-failed Phase-0 seams — in escalations[]
    (do NOT auto-decide, do NOT crash) for L0 to surface; L0 writes data/profile/identity_decision.json from the
    answer and re-spawns you to finish Phase 0d/0e. (identity_decision.json persists ⇒ a re-run skips the gate.)
  • PAPER-LIST GATE (Scholar path, Phase 0b): where the command has the main agent get a decision for every row of
    data/profile/paper_candidates.json, RETURN it instead as ONE escalation with id 'paper-list' — its question names
    <PROJECT_DIR>/data/profile/paper_candidates.md, the row count, how many rows resolved to arXiv vs title-only, and
    by title every row you suspect is NOT the researcher's or is a large collaboration (a peripheral candidate). NEVER
    write a decision yourself. L0 asks the OWNER (never an agent), writes the answer into paper_candidates.json with
    set_paper_decisions.py and re-spawns you; Phase 0a then REUSES that file (no second Scholar read) → Phase 0c.
  • NO SELF-REWAKE (fact #8): a subagent that ends its turn is DONE — there is no harness re-invoke. So do NOT
    fire prefetch.py run_in_background-and-return; run it BLOCKING in-turn, OR (only if it would exceed the
    foreground limit) launch it DETACHED and RETURN status:'long_run_fired' with detached{pidfile,state_path} so
    L0 (which CAN rewake) owns the wait. (This inline-or-detach choice is for THIS mechanical prefetch step
    ONLY — an embedding computation, not a science run. It is NOT a general rule: any SCIENCE/experiment run
    ALWAYS fires detached via exp_ledger.py run-detach, no short/long judgment — see experiment-protocol.md §4.
    Never generalize this prefetch allowance to a science run. The verified-kill loop's PROBES are also NOT
    science runs — they execute in-turn via bin/probe_run.sh, seconds each.) AWAIT every parallel
    judge/generate/screen/verify/recheck/refute Task batch within this turn.
    ★ THIS IS THE MOST-VIOLATED RULE IN THE PIPELINE — 2026-W36 broke it three times in one run (10.1h +
    4.0h + 1.0h of dead clock, 88% of the run), each time by spawning REAL children (legal) and then ending
    the turn to await them (not legal). Concretely: when you fan out a batch, issue every Task/Agent call in
    ONE message and collect all returns BEFORE you produce your final answer. Ending your turn with
    "I'll continue once X finishes" does not schedule anything — a child's completion notification is
    delivered to L0, never to you, so nothing re-enters your context on its own.
    CORRECTION to fact #8 (2026-09-03): "a subagent that ends its turn is DONE" is no longer strictly true —
    L0 can now resume you via SendMessage, and it will, because it verifies your work against the disk with
    bin/ideation_progress.sh instead of trusting your envelope. Treat that as a SAFETY NET, not a plan: each
    wake costs hours of wall clock, is capped at 3, and a 4th failure opens a failure gate on your phase.
  • ROOTS (multi-instance isolation): reproduce with plugin_root=<PLUGIN_ROOT> (read-only SHARED code) and
    project_dir=<PROJECT_DIR> (per-instance DATA root) — write profile/cache/ideations/digests/web under
    <PROJECT_DIR>/data, NEVER under plugin_root, and carry AR_DATA_ROOT=<PROJECT_DIR> on every Python call.
  • SUBAGENT TYPE (no-nesting — every scout-phase Task): where scout-beta maps a JS `agent()` to a `Task`, ALWAYS
    set `subagent_type: 'auto-research:leaf-worker'` (pass that phase's `model` explicitly, per the ARX config's
    scout.phases block — generate/screen/verify/recheck/refute/plan each carry their own tier). NEVER leave
    `subagent_type` blank and NEVER use `'claude'` here: a blank type
    resolves to the harness's built-in catch-all worker, and `claude` is itself the full-toolset catch-all — BOTH
    are `Tools:*` and carry the `Agent` (spawn) tool, so a scout leaf could itself spawn a nested subagent (e.g. a
    Phase-0e profile leaf spawning an "extract fields" helper) → an unbounded, token-burning tree that the
    top-level spawn_guard hook does NOT catch once it is nested. `auto-research:leaf-worker` has the SAME tools
    MINUS `Agent`, so each scout phase does its work in ONE bounded context and structurally cannot nest; a phase
    that wanted a helper does that step inline.
Return the L1 envelope with the scout's declared outputs (data/ideations/<week>/refined/*.md + the
<week>-scout.html) in artifacts[].
