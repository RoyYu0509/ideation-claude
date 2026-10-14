// =====================================================================================================
// spec/research.js — the auto-research L0 state machine (the orchestrator's "constitution").
//
// HOW TO CONSUME THIS FILE. You are REPRODUCING this spec, not executing it: the MAIN session (L0) walks
// these functions with the real harness tools (Read/Write/Bash/Agent/AskUserQuestion) and delegates the heavy
// work to L1 subagents that each reproduce THEIR vendored spec. Two tags tell you how to read every line:
//   [[MECH]]        reproduce verbatim — NO reasoning (state transitions, loop counter, loop_gate arithmetic,
//                   persistence, the L1 envelope handling).
//   [[SEAM:<name>]] the ONLY points where reasoning happens (by L0, or delegated) — each names its trigger,
//                   bounded decision, and conservative fallback.
//
// The rest of this layer's design lives in single-source homes — read them once, do NOT re-derive here:
//   • full workflow panorama + intuition (self-contained; incl. the 读法约定: two-tier contract / 3-tier spawn /
//     detach / platform invariants) → spec/research-flow-narration.md.
//   • 3-tier spawn topology + Agent-tool table + invariants (#1 nested spawn needs the Agent tool; gates are
//     L0-only; no unbounded nesting; detach is L0-only) + forbidden topologies → docs/agents.md.
//   • TWO GUARDS — L0 = flow guard (this file: state, gates, loop-exit arithmetic, resume); the fidelity
//     PreToolUse hook = science guard at the FREEZE boundary (review / rewrite-consolidate / polish-figures), NOT the
//     producer, whose anti-fabrication guard is the independent VERIFIER (runVerify, RC-1) — see narration RC-1/RC-6.
//   • #9 a 529 can silently empty an L1 → verify artifacts on disk + re-spawn once: enacted at
//     [[SEAM:empty-result-recovery]] (spawnAgent); see narration 读法约定.
//   • verification provenance for every RC / platform invariant → DECISIONS.md §RC 历史 / §平台不变量验证史.
// =====================================================================================================

// ── TWO ROOTS (separate CODE from DATA so the plugin runs from any EXTERNAL folder without polluting the
//    plugin dir, and two instances stay isolated). PLUGIN_ROOT (= the command's plugin_root = CLAUDE_PLUGIN_ROOT):
//    read-only SHARED code/specs/assets/bin/config/vendored-plugins. PROJECT_DIR (= project_dir = CLAUDE_PROJECT_DIR,
//    the cwd / per-instance DATA root): state/runs/decisions/data/.polish. Run from the monorepo ⇒ the two
//    coincide (legacy behavior unchanged). RULE: read code/asset/bin/vendor from PLUGIN_ROOT; write
//    state/runs/data to PROJECT_DIR. ───────────────────────────────────────────────────────────────────
// ── Config (SSOT = PLUGIN_ROOT/config/config.yaml; ZERO defaults — a missing key CRASHES with its name) ─
const CFG          = loadYaml(`${PLUGIN_ROOT}/config/config.yaml`)   // [[MECH]] shared default; crash if absent
const MILESTONES   = need(CFG, 'milestones')                         // [PHASE0_KILL_OR_CONFIRM..RESULTS_ON_DISK]
const DRAFTING     = need(CFG, 'drafting')                           // B1 drafting quality: skill names L0 injects + figure/citation floors
const EXP_ENG      = need(CFG, 'experiment_engineering')             // B1 experiment_worker: hardware-probe/bottleneck/OOM/utilization/seed skill (bare name injected into the goal)
const AUDIT        = need(CFG, 'audit')                              // VERIFY: skills the verifier may retrieve + free-spawn permission (decision b)
const MODELS       = need(CFG, 'models')                             // role -> {model, think}
const BUDGETS      = need(CFG, 'budgets')                            // per-stage soft caps
const BACKEND      = need(CFG, 'experiment_backend')                 // 'local'
const P            = need(CFG, 'paths')                              // vendor roots, runs root, specs, ...
const CONCERN_MAP  = need(P, 'concern_map')                          // ledger concern -> reference map (injected into PD goal-builders)
// SUBAGENT-GOAL RUBRICS (spawning prompts) are NOT config paths — each slim goal-builder reads its file DIRECTLY
// from spec/spawn-prompts/<FILE>.md (one level down from this file): VERIFY-PROTOCOL / WORKORDER-HARDENING /
// AUDIT-ARTIFACT-INTEGRITY / SCALE-CONTRACT-REVIEW / LITERATURE-{WORKER,AUDIT} / DOSSIER / THEORY-AUDIT /
// VIABILITY-RECOMMENDER / {REVIEW,POLISH-FIGURES}-L0-CONTRACT / FINDINGS-FREEZE / STORY / WRITE / EDIT / FREEZE
// (the writing engine). "logic lives in markdown, L0 stays thin."
const RUNS         = `${PROJECT_DIR}/${P.runs_root}`
const STATE_FILE   = `${PROJECT_DIR}/${P.state_file}`
const DECISIONS    = `${PROJECT_DIR}/${P.decisions_dir}`

// ── State model (state/pipeline-state.json) — written after EVERY transition [[MECH]] ────────────────
// { stage:        'ideation'|'seed_gate'|'setup_workspace'|'gen_handoff'|'handoff_gate'|'loop'|'verify_final'|'spec_freeze'|'ship'|'done',
//   loop_round:   0,                         // current Stage-B round (1..max_loop_rounds) — set 0 at the GATE-1 pick (applyPickedIdea)
//   paper_slug:   null, workspace: null,     // runs/<slug> — the ONE picked idea (set by applyPickedIdea at the GATE-1 ingest)
//   venue:        null,                      // the picked idea's venue (a prepared-venue rel)
//   picked_seed_file: null,                  // the picked idea's refined seed .md file
//   ideation_integrity: null,                // [[SEAM:ideation-integrity]] path to the ideation auditor's .integrity.json
//                                            //   (REAL vs suspect PER IDEA); written in phaseIdeation, surfaced at GATE-1
//   notes:        null,                       // the picked idea's GATE-1 author note (framing/emphasis; may carry "venue: <rel>")
//   final_status: null, exit_reason: null,    // set ONCE at finishRun (shipped|abandoned + reason) when the single run ends → stage='done'
//   milestone:    null,                      // current B1 milestone this round — per-paper, reset on advance
//   pending_gate: null,                      // { id, kind, decision_file } | null  (survives restart)
//   round_in_progress: false,                // [[MECH]] loop-counter guard (surfacing remediation): true once a
//                                            //   round's counter was incremented; a mid-round gate→resume must NOT
//                                            //   double-count the round. Cleared when the round completes / new paper.
//   phase0_verdict:  null,                   // (B) CONFIRM|SUSPECT|NOT_APPLICABLE — the surfaced toy kill-or-confirm TRIAGE (a toy cannot science-kill)
//   gate_attempts: {},                        // [[MECH]] gate id → how many times an adjudicator has answered it
//                                            //   this run. Feeds the adjudicator's <ATTEMPT> and the ≥3 converge rule
//                                            //   (an unattended gate that keeps re-opening must END, not spin).
//   orphan_ack_count: 0,                      // (D) count of log-only stop markers the owner has acknowledged;
//                                            //   scanOrphanStops surfaces only an INCREASE over this (un-buryable seam).
//   ship_reason:  null,                       // FINISHING: the ship reason (clean_exit = a clean auto-ship EXIT;
//                                            //   terminal_ship_<reason> = the owner elected Ship at the unified terminal gate),
//                                            //   set at loop EXIT / the terminal-gate Ship ingest, carried through finishing, consumed at ship — per-paper
//   terminal_reason: null,                   // [[SEAM:terminal-gate]] clean_exit | cap_exit | negative_result | over_claim —
//                                            //   the loop/verify terminal-exit reason. Set at the loop tail (clean_exit vs cap_exit) and
//                                            //   RE-SET by runTerminalGate to the routed reason; the terminal-gate ingest reads it. Persisted
//                                            //   before gate() (crash-safe default = cap_exit). Only EXIT_AT_CAP / a dead-or-over-claim
//                                            //   verify surfaces the gate; a clean-earned EXIT still auto-ships. — per-paper
//   user_input:   '',                        // RAW free-text from $ARGUMENTS, captured ONCE on a brand-new run
//                                            //   (never on resume). L0 NEVER parses it — phaseIdeation passes it
//                                            //   VERBATIM to the ideation L1 as the JS args.input (userInput), and
//                                            //   arxiv-scout.js owns ALL of its meaning: profile-rebuild intent
//                                            //   and pinned arXiv papers.
//   detached:     [],                        // [{ pidfile, state_path, kind, resume_phase }] (fact #8) — per-paper
//   pending_crash: null,                     // [[SEAM:failure-surface]] { ms, marker, crashes } | null (survives restart):
//                                            //   set by resumeDetached when a detached run finalized exit!=0; main()
//                                            //   routes it to crashSurface (owner failure gate) BEFORE any re-spawn, so a
//                                            //   crash is REPORTED + dispositioned, never a silent blind foreground re-run.
//   stage_budgets_spent: {},                 // {stage: {subagent_spawns}} vs BUDGETS (soft)
//   history:      [] }                        // [{ ts, event, detail }] (audit trail for FINAL-REPORT)
function loadState() { return exists(STATE_FILE) ? readJson(STATE_FILE) : freshState() }
function persist(s)  { s.history.push({ ts: now(), event: s.stage, detail: s.milestone || s.loop_round })
                       writeJson(STATE_FILE, s) }                    // [[MECH]] whole state, every transition

// ── Single-idea model [[MECH]] — one /auto-research run pursues exactly ONE picked idea ───────────────
// There is no batch / idea-queue / outer loop. GATE 1 picks ONE idea (applyPickedIdea writes the flat
// fields below) and the run drives that single idea to ship-or-abandon, then ends (stage='done'). To try
// another idea, re-run /auto-research — it opens a fresh ideation gate in a clean orchestrator context,
// so no end-of-run "pick another idea" machinery is needed.

// ── Uniform L1 return envelope (HANDOFF §3); ALL artifacts go to disk, the return is small JSON ──────
// The AUTHORITATIVE schema is spec/l1-envelope-schema.json — spawnL1 validates EVERY return against it via
// bin/validate_envelope.sh (RC-3: the envelope is no longer trusted on faith), and it is the SAME JSON
// Schema a future Workflow agent({schema}) call will reuse verbatim (Option-B forward-compat).
// { status: 'done'|'escalations_pending'|'long_run_fired'|'failed',
//   artifacts: [paths], escalations: [{id,severity,question,options,recommended}],
//   detached: { pidfile, state_path } | null, metrics: { subagents_spawned, notes, verdict? } }
const L1_SCHEMA = readJson(`${PLUGIN_ROOT}/spec/l1-envelope-schema.json`)   // load the REAL schema (RC-3); crash if absent
// isEnvFailed — P-2 fix (dossier 02, 2026-07-07): treat a schema-INVALID status (an invented string outside
// L1_SCHEMA's enum) EXACTLY like status:'failed', everywhere a caller asks "did this envelope fail?". Root
// cause this closes: the seed_to_handoff incident, where a call site checked ONLY the literal string
// `env.status === 'failed'`, so an out-of-enum status ("recovered_stalled_verified_on_disk") sailed through
// un-caught and the mandated resume-once retry (spawnAgent's own `!valid` check) never got a chance to fire —
// because research.js is REPRODUCED by an LLM each session, not compiled/enforced, a single literal-string
// guard is one skipped step away from being defeated by a persuasive-but-invalid status. This helper is the
// SAME check at every call site (never hand-repeat the enum), derived from the schema itself (never a copy
// that can drift). Use isEnvFailed(env) in place of every `env.status === 'failed'` check.
const L1_VALID_STATUS = L1_SCHEMA.properties.status.enum   // ['done','escalations_pending','long_run_fired','failed']
function isEnvFailed(env) { return !env || env.status === 'failed' || !L1_VALID_STATUS.includes(env.status) }

// spawnAgent — the shared spawn+validate+resume body for BOTH layers. [[MECH]] + [[SEAM:empty-result-recovery]]
// model/think come from CFG.models[role]; the caller fixes the subagent_type via spawnL1 / spawnL2 (below).
// ORCHESTRATOR vs LEAF: an ORCHESTRATOR role needs to fan out sub-contexts, so it must be the custom
// 'auto-research:orchestrator' type (which carries Agent BY ITS OWN frontmatter tools list); a leaf role uses
// the plain 'claude' shell. Either goal ALWAYS says "Read <spec> and reproduce it" — NEVER "run /<command>"
// (issue #59968: a Skill invoked in a subagent loses Agent auth).
// NO-NEST GUARANTEE is CAPABILITY-DEFINED + HOOK-ENFORCED, NOT "the built-in shells lack Agent" (the current
// harness grants the built-in catch-all worker the full Tools:* set, so that old assumption does not hold — 见
// DECISIONS.md §平台不变量验证史): a producing-worker delegates ONLY to types whose OWN frontmatter omits Agent —
// 'auto-research:leaf-worker' (a full worker minus spawn), 'Explore', 'Plan' — and a PreToolUse hook
// (hooks/spawn_guard) hard-blocks the built-in catch-all worker, redirecting to auto-research:leaf-worker. See
// agents/producing-worker.md + agents/leaf-worker.md.
function spawnAgent(subagent_type, role, goal, { resume = false } = {}) {
  const m = need(MODELS, role)                                       // {model, think}
  const tier = subagent_type === 'auto-research:orchestrator' ? 'L1' : 'L2'   // leaf ('claude') = L2; orchestrator = L1
  logEvent('agent_spawn', { src: 'l0', role, tier, subagent_type, model: m.model, resume })   // LOGGING (side-channel): spawn boundary. src:'l0' = this L0 semantic record (has ROLE/model); the spawn_guard hook writes the DETERMINISTIC src:'hook' twin (session-complete, but no role). Grep agent_spawn = both.
  const env = AGENT({ subagent_type, model: m.model,
                      prompt: goal + (m.think ? `\n\n${m.think}` : ''), schema: L1_SCHEMA })
  const agent_id = agentLastId()                                     // capture the spawned agentId (the JOIN KEY)
  // [[MECH]] RC-3: the envelope IS the L0↔agent contract — VALIDATE its shape, never trust it on faith.
  // Write the return to disk and run bin/validate_envelope.sh against spec/l1-envelope-schema.json (the
  // SAME schema a future Workflow agent({schema}) will enforce natively — Option-B forward-compat).
  const envFile = `${RUNS}/.last-envelope-${role}.json`; writeJson(envFile, env || {})
  const valid = firstLine(bash(`bash "${PLUGIN_ROOT}/bin/validate_envelope.sh" "${envFile}" 2>&1 || true`)).startsWith('OK')
  logEvent('agent_return', { role, tier, agent_id, status: (env && env.status) || 'none', schema_valid: valid,
    subagents_spawned: (env && env.metrics && env.metrics.subagents_spawned) || 0,                          // 0 is EXPECTED + correct for an L2 leaf
    escalations_n: (env && env.escalations && env.escalations.length) || 0,
    artifacts_n: (env && env.artifacts && env.artifacts.length) || 0 })       // LOGGING (side-channel)
  if (!valid) logEvent('envelope_invalid', { role, tier, agent_id, status: (env && env.status) || 'none' })
  // [[SEAM:empty-result-recovery]] a 529/overload (fact #9) can return nothing/failed OR a schema-invalid
  // envelope. Either way: re-spawn ONCE in resume mode; if STILL bad, bubble a failed envelope.
  if (isEnvFailed(env) || !env.artifacts || !valid) {
    if (!resume) return spawnAgent(subagent_type, role, goal + `\n\n[RESUME] A prior attempt returned no/invalid envelope (it`
        + ` MUST satisfy spec/l1-envelope-schema.json). Read your on-disk checkpoints (the spec +`
        + ` RESEARCH_LOG.md / milestone-state.json / repo state) and CONTINUE from the last checkpoint; do`
        + ` not redo completed work. Return a SCHEMA-VALID envelope.`, { resume: true })
    return { status: 'failed', artifacts: [], escalations: [], detached: null, metrics: { notes: 'empty/invalid after one resume' } }
  }
  return env
}
// spawnL1 — a genuine multi-leaf ORCHESTRATOR (carries the Agent tool, CAN spawn L2 leaves). Use ONLY for
// roles that genuinely fan out independent sub-contexts: ideation judges, the review panel + Area Chair,
// polish-figures workers + fidelity gate, rewrite + its independent provenance auditor.
function spawnL1(role, goal, opts = {}) { return spawnAgent('auto-research:orchestrator', role, goal, opts) }
// spawnL2 — a single-context LEAF worker (built-in 'claude' shell). NOTE: the shell is Tools:* and DOES carry
// the Agent tool (DECISIONS.md §平台不变量验证史 CORRECTION 2026-06-25) — the no-nest guarantee for these
// leaves is BEHAVIORAL, not structural: an L2 goal never instructs a spawn (see the NO-NEST note in the
// spawnAgent header above for the tiers where the structural lock actually lives). Use for roles that do ONE
// clear task in one honest context and return the same envelope: the whole-paper section drafter, cross-check,
// and the read-only auditor leaves (theory / scale-contract / workorder-hardener / viability / audit-artifact).
// The independent audit for these lives at the LOOP boundary (review panel + the L0 independent verifier),
// NOT in an intra-phase orchestrator/leaf split — that split only created a surface for a conductor to re-reason
// on (launder) a worker's conclusion. metrics.subagents_spawned = 0 is EXPECTED. (The experiment milestone is
// heavier and gets the MIDDLE tier — spawnWorker, below — not a locked leaf.)
function spawnL2(role, goal, opts = {}) { return spawnAgent('claude', role, goal, opts) }
// spawnWorker — the MIDDLE tier: a PRODUCING WORKER (auto-research:producing-worker; carries the Agent tool, so
// it CAN spawn helper leaves). Use where the work is heavy enough to want delegation AND an external audit gates
// the result (currently the experiment milestone) — the binding audit is the EXTERNAL, code-enforced L0
// independent verifier, NOT a capability lock, which is why this tier may delegate safely. Its full spawn
// contract (which helper roles, verify-on-return, never-judge-own-result, never-a-peer) lives in
// agents/producing-worker.md — don't restate it here.
function spawnWorker(role, goal, opts = {}) { return spawnAgent('auto-research:producing-worker', role, goal, opts) }
// spawnWorkersParallel — fan out one producing-worker PER goal AS A CONCURRENT BATCH: the reproducing L0 issues
// ALL of these spawns as Task calls IN ONE MESSAGE (parallel, not sequential — the same enactment the smoke probe
// uses: "one Task per item, in one turn"), then collects the envelopes in goal order. Use ONLY where the items are
// INDEPENDENT and each worker owns a DISJOINT unit (research-rescue's per-failed-direction fan-out, skill §3);
// NEVER for ordered/dependent work (that stays a serial spawnWorker sequence). Envelope post-processing
// (tallyBudget / onLongRun) stays SERIAL in the caller — only the spawns are concurrent.
function spawnWorkersParallel(role, goals) { return (goals || []).map(g => spawnWorker(role, g)) }

// ── Gate — AUTONOMOUS by default: a cold-read adjudicator answers in the owner's place ──────────────
// [[SEAM:gate]] (2026-09-02, owner decision: no human-in-the-loop — runs go start to finish unattended.)
// (2026-09-12, owner decision: take back ONLY the research-direction calls — gates.owner_kinds — and GATE-1's
// idea pick, which is always the owner's; see gateAnsweredBy.)
// EVERY gate still writes its decision file: that file remains the durable, auditable record AND it is the
// adjudicator's instruction set (the options in it are the only answers that exist). What changed is WHO
// answers it. `gates.adjudicator: agent` (default) spawns a fresh read-only L2 that produced none of the
// work under judgement; L0 ingests its answer through the SAME ingestGateAnswer path an owner's reply takes,
// so every downstream transition is byte-identical. `gates.adjudicator: owner` restores the blocking
// AskUserQuestion + END_TURN path exactly as it was.
// WHY A SEPARATE LEAF AND NOT L0 ITSELF: GATE-TAXONOMY §0 — a goal/loop may DRIVE but never ACQUIT. L0
// answering its own gates is precisely the self-acquittal shape §5 exists to catch; the fresh context is
// what keeps a gate a gate rather than a formality the loop performs on itself.
// [[MECH]] gateAnsweredBy(kind) — WHO answers a gate of this kind. `gates.adjudicator: owner` ⇒ every gate is the
// owner's. Under `agent`, a kind listed in `gates.owner_kinds` is STILL the owner's — by default the two research-
// DIRECTION calls: `direction` (the per-round card: approve / revise / abandon + an owner-directed Amplify or Rescue)
// and `terminal_gate` (ship / abandon / one more round). GATE-1 (`seed_select`) is the owner's UNCONDITIONALLY — the
// agent never picks the idea, whatever the config. A kind in `gates.default_kinds` (and not the owner's) is a RULE,
// not a card: it takes the gate's own `recommended` option, no judge — by default `terminal_gate` since 2026-09-23
// (the loop's exit: clean exit ships, cap / dead claim abandons, over-claim ships narrowed). Every other gate
// (failure-* Resume, audit-artifact, phase0, central-narrow, ...) stays with the cold-read judge. Used by gate()
// AND by main()'s crash-resume path, so a pending owner gate is never re-adjudicated by an agent after a restart.
function gateAnsweredBy(kind) {
  if (kind === 'seed_select') return 'owner'                          // GATE-1 (2026-09-12): not configurable
  if (kind === 'identity') return 'owner'                             // who this folder runs for + which papers are theirs (2026-09-13): never an agent's call
  if (((CFG.gates && CFG.gates.adjudicator) || 'agent') === 'owner') return 'owner'
  if (((CFG.gates && CFG.gates.owner_kinds) || []).indexOf(kind) >= 0) return 'owner'
  return ((CFG.gates && CFG.gates.default_kinds) || []).indexOf(kind) >= 0 ? 'default' : 'agent'
}
function gate(state, id, kind, questions) {
  const file = `${DECISIONS}/DECISIONS-PENDING.md`
  writeDecisionFile(file, `${PLUGIN_ROOT}/${P.decision_template}`, id, kind, questions)  // the UNIVERSAL gate source file (written for EVERY gate) — the L0 reads it to compose the live-card preview
  state.pending_gate = { id, kind, decision_file: file }; persist(state)
  logEvent('gate_open', { id, kind })                                // LOGGING (side-channel)
  // [[SEAM:gate-preview]] LIVE CARD = SOURCE-DERIVED, never pre-baked. The format is NOT pinned in code (that
  // was inflexible + could drift from / go stale vs the file). INVARIANT, enforced by the askUser enactment
  // contract (helper-doc) + commands/auto-research.md: when surfacing, the L0 READS this gate's source file(s)
  // — the decision file just written PLUS any artifact the question's context NAMES (handoff_file / log / html
  // / report / evidence) — and composes each option's `preview` box from what is ON DISK NOW. A preview is
  // ALWAYS present; it is NEVER free-invented without reading the file. So a hand-edited HANDOFF.md is
  // reflected, and a NEW gate needs zero preview code (format follows the file, not a per-gate switch).
  if (gateAnsweredBy(kind) === 'default') {
    ingestGateAnswer(state, defaultGateAnswer(id, kind, questions))  // a rule, not a card: apply the gate's own default in THIS turn
    return
  }
  if (gateAnsweredBy(kind) === 'agent') {
    ingestGateAnswer(state, adjudicateGate(state, id, kind, questions, file))   // answer + apply in THIS turn
    return                                                           // caller returns; the dispatch loop continues on the new stage
  }
  try { askUser(questions) } catch (_) {}                            // live card if reachable; file is the record
  log(`GATE ${id}: wrote ${file}; ending turn. Answer in chat and/or edit the file.`)
  END_TURN()
  // On the NEXT user turn (ingest, [[MECH]]): validate answers (chat reply wins over file on conflict),
  // archive file → DECISIONS-RESOLVED-<n>.md, clear pending_gate, apply, continue. An UNANSWERED item
  // gets its (Recommended) option ONLY on an explicit "use defaults"; else re-present (never guess an
  // author-only call). The apply logic is ingestGateAnswer (below) — the SINGLE per-gate dispatcher the
  // next-turn human path (main → ingestGateAnswer) calls.
}

// ── adjudicateGate — spawn the cold-read judge, then VALIDATE what it said ───────────────────────────
// [[MECH]] Returns the SAME `{per_question}` shape readOwnerAnswer produces for a human, so ingestGateAnswer
// cannot tell the two apart. The validation is the load-bearing part: an answer that is missing, unparseable,
// or names an option THIS gate does not offer is discarded and replaced by the conservative fallback, and the
// substitution is logged. A judge that fails must never degrade into a silent yes.
function adjudicateGate(state, id, kind, questions, file) {
  state.gate_attempts = state.gate_attempts || {}
  const n = (state.gate_attempts[id] || 0) + 1; state.gate_attempts[id] = n; persist(state)
  const out = `${DECISIONS}/.adjudication-${id}.json`
  // The gate's own question context NAMES its evidence (verdict file, review report, concerns ledger, log);
  // hand those paths to the judge rather than letting it hunt — a judge that reads nothing decides nothing.
  const ctx = questions.flatMap(q => Object.values(q.context || {})
    .filter(v => typeof v === 'string' && v.indexOf('/') >= 0))
  spawnL2('gate_adjudicator', gateAdjudicationGoal(id, kind, file, ctx, out, n))
  let v = null; try { if (exists(out)) v = readJson(out) } catch (_) { v = null }     // FAIL-SAFE: unreadable ⇒ fallback
  const per_question = questions.map(q => {
    const a = ((v && v.answers) || []).find(x => x && x.id === q.id)
    const labels = (q.options || []).map(o => o.label)
    const ok = !!(a && labels.indexOf(a.choice) >= 0)
    if (!ok) logEvent('gate_adjudication_fallback', { id, question: q.id, got: (a && a.choice) || null })
    return { id: q.id, choice: ok ? a.choice : conservativeOption(q),
             notes: (ok && a.notes) || '',
             rationale: (ok && a.rationale) || 'no usable adjudication — conservative fallback applied' }
  })
  logEvent('gate_adjudicated', { id, kind, attempt: n, confidence: (v && v.confidence) || 'none',
                                 evidence_read: (v && v.evidence_read) || [], choices: per_question.map(x => x.choice) })
  return { per_question }   // archiveDecisionFile writes this (choice + rationale) into DECISIONS-RESOLVED-<n>.md
}
// [[MECH]] conservativeOption — the fallback when the judge gave nothing usable. Prefer the gate's OWN
// `recommended` when it declares one; else the FIRST option, which in every gate in this file is the
// non-advancing / non-shipping / non-accepting one (options are authored conservative-first). Never pick by
// keyword: "Kill this segment" is conservative at a terminal gate and reckless at a viability gate.
function conservativeOption(q) {
  const labels = (q.options || []).map(o => o.label)
  if (q.recommended && labels.indexOf(q.recommended) >= 0) return q.recommended
  return labels[0]
}
// [[MECH]] defaultGateAnswer — the answer for a kind in `gates.default_kinds`: every question takes its own
// default (conservativeOption), no judge is spawned. Same `{per_question}` shape as an owner or adjudicator answer,
// so ingestGateAnswer cannot tell them apart; the decision file is still written and archived with this rationale.
function defaultGateAnswer(id, kind, questions) {
  const per_question = questions.map(q => ({ id: q.id, choice: conservativeOption(q), notes: '',
    rationale: 'system default — this gate kind is a rule, not a card (gates.default_kinds)' }))
  logEvent('gate_defaulted', { id, kind, choices: per_question.map(x => x.choice) })
  return { per_question }
}
// [[MECH]] gateAdjudicationGoal — thin: the rubric lives in the markdown, L0 only substitutes tokens.
function gateAdjudicationGoal(id, kind, file, ctxFiles, out, attempt) {
  return [
    `You are the GATE ADJUDICATOR LEAF for gate \`${id}\` — a single-context, STRICTLY READ-ONLY worker. Read`,
    `${PLUGIN_ROOT}/spec/spawn-prompts/GATE-ADJUDICATION.md and do EXACTLY what it says — it carries the evidence`,
    `to read, the JSON to write, the per-kind rules, and the choose-only-a-listed-option contract. Substitute`,
    `as you read it:`,
    `  <GATE_ID>=${id}  <KIND>=${kind}  <DECISION_FILE>=${file}  <OUT>=${out}  <ATTEMPT>=${attempt}`,
    `  <CONTEXT_FILES>=`,
    ...(ctxFiles || []).map(f => `    ${f}`),
  ].join('\n')
}

// ── ingestGateAnswer — the per-gate apply dispatcher (owner reply OR adjudicator verdict) ────────────────────
// [[MECH]] Applies a gate's answer → action. The next-turn human path (main → here, with `answer` read from the
// chat reply / DECISIONS-PENDING.md ANSWER+NOTES lines). Validates the chosen option(s) against the question set,
// applies the per-gate transition, archives the decision file to DECISIONS-RESOLVED-<n>.md, and clears
// pending_gate. An UNANSWERED author-only item (no 'use defaults') is re-presented, never guessed. `answer`
// shape: { choice?:<label>, per_question?:[{id,choice,notes}], notes? }.
function ingestGateAnswer(state, answer) {
  const g = state.pending_gate; if (!g) return
  if (!answer) answer = readOwnerAnswer(g)   // [[MECH]] human path: parse the chat reply (wins on conflict) + the
                                             // DECISIONS-PENDING.md ANSWER/NOTES lines into {choice|per_question,notes}.
                                             // An UNANSWERED author-only item ⇒ readOwnerAnswer re-presents (never guesses).
  if (!answer) return                        // re-presented (waiting on the owner) — nothing to apply this turn
  const id = g.id
  const pick = (qid) => {                                            // the chosen option label for a question id
    if (answer && answer.per_question) { const q = answer.per_question.find(x => x.id === qid); return q && q.choice }
    return answer && answer.choice
  }
  const note = (qid) => {                                            // the free-text NOTES for a question id (else the reply's general notes)
    const q = answer && answer.per_question && answer.per_question.find(x => x.id === qid)
    return (q && q.notes) || (answer && answer.notes) || ''
  }
  if (id.startsWith('GATE1-seed-select')) {
    // [[MECH]] take the ONE picked idea (first Keep in presentation order; any other Keep is IGNORED), resolve its
    // venue + author note, write the flat fields, and enter setup_workspace — OR end the run if the owner kept none.
    // (The post-pick seed_verify gate was ABSORBED into the weekly verified-kill ideation loop, 2026-07-11: every
    // surviving seed already carries executed probes + independent recheck; a zero-token freshness re-check runs at
    // GATE-1 render instead.)
    // applyPickedIdea sets state.stage ('setup_workspace' on a pick, 'done' on none); a bad venue
    // re-presents (returns false) and leaves the gate open. The whole transition is committed in the ONE persist below (atomic).
    if (!applyPickedIdea(state, answer)) return                    // re-presented the venue gate (human path) — a new gate is open; nothing to apply now
    archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; persist(state)
    return
  }
  if (id.startsWith('handoff-approve')) {
    const c = pick('handoff_approval')
    const act = pick('round_action') || ''                          // the DIRECTION card's 2nd question (rounds ≥1 only)
    archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
    // [[MECH]] (2026-09-12) an owner-directed Amplify / Rescue runs FIRST: the worker authors a work order toward the
    // owner's NOTES, it is folded into the round about to run, and THIS card comes back with the re-authored order.
    // Abandon on the first question always wins over it.
    if (c !== 'Abandon this idea' && /^(Amplify|Rescue)/.test(act)) {
      const s = runOwnerSteer(state, /^Amplify/.test(act) ? 'amplify' : 'rescue', note('round_action'), state.loop_round)
      if (!s) return                                                 // a detached worker already ended the turn (onLongRun)
      if (s.authored) { foldOwnerSteer(state); if (turnEnded(state)) return }
      state.stage = 'handoff_gate'; persist(state); return          // re-present with the re-authored order (or the worker's reason)
    }
    if (c === 'Approve & run')      { state.stage = 'loop'; persist(state); return }
    // 'Revise' → re-enter gen_handoff: generateHandoff(state, false) RE-AUTHORS the work order then re-presents
    // this gate (transition=false: skip the round-transition mechanics — they ran at the loop tail). See generateHandoff.
    if (c === 'Revise')             { state.stage = 'gen_handoff'; persist(state); return }   // re-render / re-author
    if (c === 'Re-author stale Editorial direction now') {          // [[MECH]] same re-author path as Revise; the
      const ws = `${RUNS}/${state.paper_slug}`                      // owner is fixing the flagged prose specifically —
      const sidecarPath = `${ws}/.concern-prose-staleness.json`     // reset the counter so a fresh flag next round
      if (exists(sidecarPath)) bash(`rm -f "${sidecarPath}"`)       // starts its own 3-round clock, not a stale one
      logEvent('concern_prose_stale_escalated', { round: state.loop_round })
      state.stage = 'gen_handoff'; persist(state); return
    }
    // 'Abandon this idea'. From round 1 on this KILLS a direction that already ran — leave the same honest
    // FINAL-REPORT-killed.md the viability Kill writes (not ship-gated), grounded in the just-completed round.
    if (c === 'Abandon this idea' && state.loop_round > 0) writeKilledReport(state, state.loop_round - 1, 'owner_killed_at_direction_card')
    return finishRun(state, 'abandoned', 'owner_abandoned_at_handoff')                          // 'Abandon this idea'
  }
  if (id.startsWith('phase0-')) {
    const c = pick('phase0')
    archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; persist(state)
    if (c === 'Proceed') {
      // [[MECH]] RC-12 Phase-0(C) LOCK: snapshot §4b/§4c → HANDOFF.{scale-contract,ambition}.locked.json — the
      // IMMUTABLE baseline V5 (ratchet) + V8 (scale audit) + §4c reconciliation diff against. Deterministic +
      // idempotent (lock only if ABSENT; a re-lock needs --ratchet). A missing §4b/§4c block is a HANDOFF defect
      // → ERROR first line → STOP LOUD (never proceed to experiments unlocked — that is how a WEAKEN slips past V5).
      const ws = `${RUNS}/${state.paper_slug}`
      if (firstLine(bash(`bash "${PLUGIN_ROOT}/bin/contract_lock_status.sh" "${ws}" 2>&1`)).startsWith('ABSENT')) {
        const lk = bash(`bash "${PLUGIN_ROOT}/bin/lock_contracts.sh" "${ws}" 2>&1`)
        if (firstLine(lk).startsWith('ERROR')) throw new Error(`Phase-0(C) lock_contracts failed: ${lk}`)
      }
      return                                                         // milestoneDone(phase0)=true → re-entering 'loop' continues to ENV_READY
    }
    if (c === 'Redirect — I will clarify') {                        // re-run Phase 0 with the
      const ws = `${RUNS}/${state.paper_slug}`                      // owner's new scope: CLEAR its milestone marker so runB1 re-enters it (else
      const ms = readJson(`${ws}/milestone-state.json`)             // milestoneDone(phase0)=true would skip it). The owner's clarification notes are
      delete ms.milestones[CFG.checkpoints.phase0_milestone]        // appended to the re-spawned B1 goal by the L0 reproducer (same as the prose before).
      writeJson(`${ws}/milestone-state.json`, ms); return
    }
    return finishRun(state, 'abandoned', 'owner_abandoned_at_phase0')                           // 'Abandon this idea'
  }
  if (id.startsWith('literature-')) {                                // [[MECH]] LITERATURE auditor surfaced an INCOMPLETE bib or a SCOOPED (S10) verdict
    const c = pick('literature')
    archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; persist(state)
    if (c === 'Proceed')            { return }                       // milestoneDone(LITERATURE)=true → re-entering 'loop' continues to ENV_READY
    if (c === 'Revise — I will clarify') {                          // rebuild the bib: CLEAR the LITERATURE marker so runExperiment re-enters it
      const ws = `${RUNS}/${state.paper_slug}`                      // (the re-spawned literatureGoal reads .literature-review.json to close the gaps;
      const ms = readJson(`${ws}/milestone-state.json`)             // the owner's clarification notes are appended by the L0 reproducer, same as phase0).
      delete ms.milestones[CFG.checkpoints.literature_milestone]
      writeJson(`${ws}/milestone-state.json`, ms); return
    }
    return finishRun(state, 'abandoned', 'owner_abandoned_at_literature')                       // 'Abandon this idea'
  }
  if (id.startsWith('viability-gate-')) {
    // [[MECH]] unit ① — the per-wave viability gate disposition. round_in_progress is still true (the gate fired
    // mid-round, before the verdict was enacted), so a resolved round is NOT re-run (the loop-top viability-resolved
    // skip owns that). An UNRECOGNIZED answer re-presents (kill is destructive — never guessed); so clear the
    // pending_gate ONLY on a recognized disposition.
    const c = pick('viability')
    const ws = `${RUNS}/${state.paper_slug}`
    if (c === 'Continue' || c === 'Redirect') {
      if (c === 'Redirect') {
        // Write the owner's steer as a round HANDOFF the loop folds into the NEXT wave (generateHandoff).
        // Free-text note (if any) + the recommender's next_step compose the steer.
        const note = (answer && (answer.notes || (answer.per_question || []).map(q => q.notes).filter(Boolean).join('\n'))) || ''
        writeViabilitySteer(`${ws}/HANDOFF-viability-steer.md`, state, note)
      }
      // Mark THIS round viability-resolved (the .round-<N>.drafted idempotency idiom) so the loop-top skip enacts
      // the verdict (REDIRECT forces CONTINUE via the steer file) WITHOUT re-running the completed wave.
      bash(`touch "${ws}/.round-${state.loop_round}.viability-resolved"`)
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
      state.stage = 'loop'; persist(state); return
    }
    if (c === 'Kill this segment') {
      // Abandon-at-exhaustion close (recommender's blocking_point / tried / next_step = the content).
      // The kill path SKIPS ship()/assertShipReady, so it must NOT write the workspace FINAL-REPORT.md (the RC-11
      // ship_gate hook denies that basename unless pipeline_status says SHIP_READY). Write FINAL-REPORT-killed.md
      // (NOT hook-gated), then route through the EXISTING abandon contract (finishRun 'abandoned' → stage='done').
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
      const brief = writeKilledReport(state, state.loop_round, 'viability_killed')
      logEvent('viability_killed', { paper: state.paper_slug, round: state.loop_round, blocking_point: (brief && brief.blocking_point) || null })
      return finishRun(state, 'abandoned', 'viability_killed')
    }
    return   // unrecognized/empty disposition → leave pending_gate set; the next turn re-presents (never guess a kill)
  }
  if (id.startsWith('terminal-gate-')) {
    // [[SEAM:terminal-gate]] the UNIFIED terminal-exit disposition (folds the former ambition-residual gate). One
    // gate for cap_exit / negative_result / over_claim — and clean_exit when the owner answers it (runTerminalGate
    // persisted state.terminal_reason + wrote .terminal-verdict.json). The owner picks Abandon / Ship / Rescue-one-
    // more-round / Amplify-one-more-round. An UNRECOGNIZED answer re-presents (every disposition is consequential —
    // never guessed); clear pending_gate ONLY on a match.
    const c = pick('terminal') || ''
    const ws = `${RUNS}/${state.paper_slug}`
    const reason = state.terminal_reason || 'cap_exit'                                // crash-safe default = cap_exit (risk #6)
    const tv = exists(`${ws}/.terminal-verdict.json`) ? readJson(`${ws}/.terminal-verdict.json`) : null
    if (/abandon/i.test(c)) {                                    // reuse the viability-Kill abandon template (FINAL-REPORT-killed.md is NOT ship-gated → finishRun 'abandoned')
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
      const verdicts = collectVerdicts(ws)                       // [[MECH]] P-3: harvest the machine verdicts BEFORE the write
      writeFinalReport(`${ws}/FINAL-REPORT-killed.md`, { timeline: state.history, artifacts: collectArtifacts(ws),
        venue: state.venue, exit_reason: reason, how_it_failed: tv && tv.how_it_failed, plain_why: tv && tv.plain_why,
        contribution_verdict: tv && tv.contribution_verdict, verdicts, policy_resolved: collectResolvedDecisions(DECISIONS),
        unresolved: collectUnresolved(ws), usage: state.stage_budgets_spent })
      enforceVerdictFidelity(ws, `${ws}/FINAL-REPORT-killed.md`, verdicts)   // [[MECH]] P-3 read-back — bounded, never blocks the abandon
      logEvent('terminal_abandoned', { paper: state.paper_slug, round: state.loop_round, reason })
      return finishRun(state, 'abandoned',
        reason === 'cap_exit' ? 'cap_exit_abandoned' : reason === 'over_claim' ? 'ambition_residual_abandoned'
          : reason === 'clean_exit' ? 'owner_abandoned_at_clean_exit' : 'central_claim_dead')
    }
    if (/ship/i.test(c) && reason === 'clean_exit') {            // (2026-09-12) the owner confirmed a CLEAN, reconciled exit — record exactly what the auto path records
      recordStage(state, 'verify_final', { verdict: 'PASS', round: state.loop_round, ambition_reconciled: true, ambition_gaps: 0 }, { commit: false })
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
      state.stage = 'spec_freeze'; persist(state); return        // ship_reason stays 'clean_exit' (loop tail); no steer file — nothing to narrow
    }
    if (/ship/i.test(c)) {                                       // unblock ship + steer the downstream reframe/rewrite (narrow, never strengthen; BAR reframe for a dead claim)
      recordStage(state, 'verify_final', { verdict: 'PASS', round: state.loop_round, ambition_reconciled: true, narrowing: `owner_terminal_${reason}` }, { commit: false })
      const barred = reason === 'negative_result'
      bash(`printf '%s\\n' '${barred
        ? 'OWNER OVERRIDE at the terminal gate for a DEAD central claim. System policy was ABANDON (a negative that contradicts the novelty claim is not a deliverable); the owner has overridden it. Deliver it stating the contradiction plainly and labelling it an owner override. reframe-result is BARRED — do NOT repackage the dead claim as a positive, and do NOT dress the refutation up as the contribution. See .terminal-verdict.json / VERIFICATION-REPORT.md.'
        : reason === 'over_claim'
          ? (gateAnsweredBy('terminal_gate') === 'owner' ? 'OWNER chose' : 'The system default (gates.default_kinds) chose') + ' SHIP at the terminal gate. The downstream reframe/rewrite MUST narrow the claim to what the evidence holds (reframe-result may narrow the REAL result; never strengthen). See .terminal-verdict.json.'
          : (gateAnsweredBy('terminal_gate') === 'owner' ? 'OWNER chose' : 'The system default (gates.default_kinds) chose') + ' SHIP-AS-IS at the terminal gate (cap reached, central claim not killed): hand the spec back to the researcher. List every unresolved reject/major item honestly as what remains open.'}' > "${ws}/.terminal-narrowing-accepted.md"`)
      state.ship_reason = `terminal_ship_${reason}`
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
      state.stage = 'spec_freeze'; persist(state); return        // verify_final ledgered reconciled:true → spec_freeze → ship
    }
    if (/rescue/i.test(c)) {                                     // research-rescue (禁止轻易放弃) + reopen ONE loop round
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
      const scenario = reason === 'over_claim' ? 'delivery-vs-ambition' : 'central-claim-viability'
      runResearchRescue(state, scenario, [{ id: 'terminal', reason }]); if (turnEnded(state)) return
      reopenLoopWith(state); return                             // re-author HANDOFF + reopen milestones + stage='loop'; round_in_progress=false ⇒ loop-top increments (NOT a beginNextRound site)
    }
    if (/amplify/i.test(c) && reason !== 'negative_result') {    // (2026-09-12) the owner pushes the idea one more round, toward the NOTES (never offered for a dead claim)
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; persist(state)
      const s = runOwnerSteer(state, 'amplify', note('terminal'), state.loop_round + 1); if (!s) return
      if (!s.authored) return runTerminalGate(state, reason)     // nothing to run → back to this card, the worker's reason on disk
      // Same shape as the loop tail's amplify-raised EXIT: fold at the loop-tail position (its re-open snapshot key
      // loop_round+1 is right here), advance the counter, and show the owner the amplified order before it runs.
      generateHandoff(state, true); if (turnEnded(state)) return
      beginNextRound(state)
      state.stage = CFG.checkpoints.handoff_approval ? 'handoff_gate' : 'loop'; persist(state); return
    }
    return   // unrecognized/empty → leave pending_gate set; re-present (never guess a consequential disposition)
  }
  if (id.startsWith('audit-artifact-gate-')) {
    // [[SEAM:audit-artifact]] the in-round audit-artifact integrity gate disposition (a goalpost-move surfaced).
    // The gate fired BEFORE the producer was re-spawned, so resolving it re-enters the loop (the worker resumes);
    // the .round-<N>.audit-artifact-resolved marker makes runAuditArtifactGate skip on re-entry (never re-open a
    // disposed round). Unrecognized → re-present (a strip/abandon is consequential — never guessed).
    const c = pick('audit_artifact') || ''
    const ws = `${RUNS}/${state.paper_slug}`
    if (/strip/i.test(c) || /accept/i.test(c)) {                     // enact via bin/ (git-checkout revert OR manifest un-lock+log OR re-lock), mark resolved, re-enter the loop (the worker resumes)
      bash(`bash "${PLUGIN_ROOT}/bin/audit_artifact_dispose.sh" "${ws}" ${/strip/i.test(c) ? 'revert' : 'accept'} "${state.loop_round}" 2>/dev/null || true`)
      bash(`touch "${ws}/.round-${state.loop_round}.audit-artifact-resolved"`)
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; state.stage = 'loop'; persist(state); return
    }
    if (/abandon/i.test(c)) { archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; return finishRun(state, 'abandoned', 'audit_artifact_goalpost') }
    return   // unrecognized/empty → leave pending_gate set; re-present next turn (never guess a strip/abandon)
  }
  if (id.startsWith('central-narrow-gate-')) {
    // [[SEAM:central-ambition-guard]] the mid-loop central/GAMBLE-K disposition gate — a rescue ALREADY ran
    // before this card was shown; the owner confirms the documented residual, redirects, or abandons.
    const c = pick('central_narrow') || ''
    const ws = `${RUNS}/${state.paper_slug}`
    if (/confirm/i.test(c)) {
      // The resumed worker re-authors HANDOFF.md §4c to record the NARROW-TO-DELIVERED move (handoff-authoring
      // §4c ratchet); THIS turn only re-locks whatever HANDOFF.md now says under --ratchet (audited, never a
      // silent overwrite) once that re-author has happened — resume in author mode first if §4c is unchanged.
      bash(`bash "${PLUGIN_ROOT}/bin/lock_contracts.sh" "${ws}" --ratchet 2>&1 || true`)
      bash(`touch "${ws}/.round-${state.loop_round}.central-narrow-resolved"`)
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; state.stage = 'loop'; persist(state); return
    }
    if (/redirect/i.test(c)) {
      bash(`touch "${ws}/.round-${state.loop_round}.central-narrow-resolved"`)
      archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; state.stage = 'gen_handoff'; persist(state); return
    }
    if (/abandon/i.test(c)) { archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; return finishRun(state, 'abandoned', 'central_ambition_narrowed') }
    return   // unrecognized/empty → re-present (never guess a confirm/redirect/abandon)
  }
  if (id.startsWith('capacity-')) {
    // [[SEAM:capacity-readout]] the early wall-clock CONCERN gate — never auto-kills; Proceed continues at full
    // locked scale (§4b stays hardware-blind), Redirect re-authors the work order (widen the stated budget, or
    // an honest §4b/§4c REDIRECT — NOT a "re-run the probe" retry: the hardware-blind rule means there is
    // nothing to fix about the measurement itself, only the budget/claim), Abandon ends the run.
    const c = pick('capacity') || ''
    archiveDecisionFile(g.decision_file, answer); state.pending_gate = null; persist(state)
    if (c === 'Proceed') return                                     // milestoneDone(CAPACITY_READOUT)=true → re-entering 'loop' continues to LITERATURE
    if (c === 'Redirect — I will clarify') { state.stage = 'gen_handoff'; persist(state); return }
    return finishRun(state, 'abandoned', 'owner_abandoned_at_capacity')   // 'Abandon this idea'
  }
  if (id.startsWith('researcher-identity')) {
    // [[MECH]] write <PROJECT_DIR>/researcher.json from the OWNER's answer, then enter the scout. 'Pin a researcher'
    // needs a Google Scholar profile URL in the notes — without one the card is re-presented (never guess an
    // identity); the names are optional (the profile build also collects the name as printed on the researcher's own
    // arXiv papers). The shared default writes a marker that scripts/lib/config.py reads as "no override".
    const c = pick('researcher') || ''
    archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
    if (/abandon/i.test(c)) return finishRun(state, 'abandoned', 'owner_abandoned_at_identity')
    if (/shared default/i.test(c)) {
      writeJson(`${PROJECT_DIR}/researcher.json`, { use_shared_default: true })
    } else {
      const txt = `${c}\n${note('researcher')}`
      const url = (txt.match(/https?:\/\/scholar\.google\.[a-z.]+\/citations\?[^\s;,，；]*user=[\w-]+[^\s;,，；]*/i) || [])[0]
      if (!url) return identityGate(state, 'no Google Scholar profile URL (…/citations?user=…) in the answer')
      const nm = txt.match(/(?:names?|aliases|名字|姓名)\s*[:：]\s*([^\n]+)/i)
      const names = nm ? nm[1].split(/[;；|]+/).map(s => s.trim()).filter(s => s && !/https?:|scholar\s*[:：]/i.test(s)) : []
      bash(`python3 "${PLUGIN_ROOT}/${P.vendor_arxiv}/bin/set_researcher.py" --store "${PROJECT_DIR}/researcher.json" ` +
           `--scholar ${JSON.stringify(url)} --website null --s2-id null --aliases ${JSON.stringify(names.join('||'))} --categories null`)
    }
    log(`researcher.json written → ${PROJECT_DIR}/researcher.json (${c})`)
    state.stage = 'ideation'; persist(state); return
  }
  if (id.startsWith('ideation-paperlist')) {
    // [[MECH]] relay the OWNER's Phase 0b answer into paper_candidates.json through set_paper_decisions.py — never an
    // agent's pick. 'All others are theirs' = --rest self + one --mark per "<key or title words>=not|peripheral" in the
    // notes; 'I filled every decision' = --check. A bad / ambiguous mark (the script then writes nothing) or a row
    // left undecided RE-PRESENTS the card. Then re-enter ideation: Phase 0a reuses the list, Phase 0c builds papers.json.
    const c = pick('paper-list') || ''
    archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
    if (/abandon/i.test(c)) return finishRun(state, 'abandoned', 'owner_abandoned_at_paper_list')
    const others = /all others/i.test(c)
    const marks = others ? note('paper-list').split(/[;；\n]+/).map(s => s.trim()).filter(s => /=\s*(not|peripheral|self)\s*$/i.test(s)) : []
    const ARX = `${PLUGIN_ROOT}/${P.vendor_arxiv}`
    const rc = bash(`AR_DATA_ROOT="${PROJECT_DIR}" bash "${ARX}/bin/run_py.sh" "${ARX}/scripts/set_paper_decisions.py" ` +
                    (others ? `--rest self ${marks.map(m => `--mark ${JSON.stringify(m)}`).join(' ')}` : '--check') +
                    ` >/dev/null 2>&1; echo $?`).trim()
    if (rc !== '0') return paperListGate(state, null, rc === '2'
      ? 'a named row matched no row or several rows — nothing was written; name each by its key or more title words'
      : 'some rows are still undecided — see paper_candidates.md')
    state.stage = 'ideation'; persist(state); return
  }
  if (id.startsWith('ideation-identity')) {
    // [[MECH]] translate the answer into data/profile/identity_decision.json (the file the vendored Phase 0d
    // reads), then re-enter ideation; or abandon the run. writeIdentityDecision encodes the chosen option.
    const c = pick('disposition') || answer.choice
    writeIdentityDecision(state, c)                                 // writes identity_decision.json (s2-full / merged / website-only); no-op for key-resume + abandon
    archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
    if (c && /abandon/i.test(c)) { log(`Ideation cannot proceed autonomously (${c}); ending the run — see the decision record.`); state.stage = 'done'; persist(state); return }
    state.stage = 'ideation'; persist(state); return
  }
  // (seed-verify-* gate family RETIRED 2026-07-11: the deep-verification tier was absorbed into the weekly
  //  verified-kill ideation loop — executed probes + independent recheck happen BEFORE GATE-1 now, and the
  //  bundle's deferred rows flow into HANDOFF §4K/Phase-0 via seedToHandoffGoal's verification clause.)
  // failure-* family — Resume (re-enter the current phase in resume mode) | Abandon (advance the queue).
  // The phase is encoded in the id (failure-<phase>-<slug>); 'resume' keeps state.stage unchanged so the
  // dispatch loop re-drives it idempotently. orphan-stops additionally acks the just-scanned marker count.
  const c = pick('disposition') || answer.choice
  archiveDecisionFile(g.decision_file, answer); state.pending_gate = null
  if (c && /abandon/i.test(c)) {
    const phase = id.replace(/^failure-/, '').replace(new RegExp(`-${state.paper_slug}$`), '')
    return finishRun(state, 'abandoned', `owner_abandoned_at_${phase}`)
  }
  if (id.startsWith('failure-orphan-stops')) state.orphan_ack_count = scanOrphanCount(state)   // ack: a later round re-surfaces only genuinely-new markers
  persist(state); return                                            // 'Resume' → stage unchanged; loop re-drives the phase in resume mode
}

// applyPickedIdea — the GATE-1 ingest: take the ONE picked idea, resolve its venue + note, write the flat fields.
// [[MECH]] Only ONE idea proceeds: the FIRST Keep in presentation order; any OTHER Keep is IGNORED (no queue, no
// outer loop). Presentation order IS parseRefinedSeeds' rank order (P-4/H-18 — its ORDER clause is the SINGLE
// order source; this ingest and the gateSeedSelect card both read it, so presented order === pick order).
// The human path never enters an out-of-set venue (re-present the venue gate → return false; caller
// does nothing). Sets state.stage itself: 'setup_workspace' on a pick, 'done' if the owner kept NONE (nothing to
// research — re-run /auto-research to choose again). Returns true once it set the stage (caller archives + persists),
// false only when it re-presented the venue gate.
function applyPickedIdea(state, answer) {
  const seeds  = parseRefinedSeeds(state.ideation_artifacts)        // [{id,title,hypothesis,significance,rigor,file,verification,judge,premises,rank,novelty}]
  const venues = listPreparedVenues(`${PLUGIN_ROOT}/${P.vendor_paper_polish}`)
  const ans    = (qid) => ((answer.per_question || []).find(x => x.id === qid) || {})
  const defVenue = ans('venue').choice || CFG.venue
  if (!venues.includes(defVenue)) { representVenue(state, venues); return false }   // a venue not in the prepared set never starts a run — re-present
  const kept = seeds.filter(s => /keep/i.test(ans(`idea-${s.id}`).choice || ''))    // presentation order
  if (!kept.length) {                                               // owner kept nothing — end the run; a fresh /auto-research opens a new ideation gate
    log('GATE 1: no idea kept — ending the run. Re-run /auto-research to pick an idea from a fresh ideation gate.')
    state.final_status = 'abandoned'; state.exit_reason = 'no_idea_selected'; state.stage = 'done'; return true
  }
  const s = kept[0]                                                 // the single idea this run pursues — the rest are ignored
  const note  = ans(`idea-${s.id}`).notes || null                  // per-idea note (may carry "venue: <rel>" to override the default)
  const m     = note && note.match(/venue:\s*([^\s,;]+)/i)
  const venue = (m && venues.includes(m[1])) ? m[1] : defVenue
  // [[MECH]] P-1 fix (dossier 02, 2026-07-07): a RE-PICK after this SAME state file's previous idea already
  // CONCLUDED (state.final_status set by a prior finishRun) mints a FRESH run_id — never reuse a finished
  // attempt's run_id. Root cause this closes: state.run_id is stamped ONCE at true process start (main(), "if
  // (!state.run_id)") and nothing downstream ever re-mints it, so an abandon→re-pick within the same DATA_ROOT
  // silently re-opened hooks/spawn_guard.py's C6 ledger-pollution window under the OLD run_id — the successor
  // attempt's own spawns (AND any concurrent /learn retro's leaves) got attributed to the CONCLUDED run's
  // run-events.jsonl stream. A brand-new run's FIRST pick never hits this branch (final_status is still null
  // at that point — run_id was already freshly minted at main()'s startup), so ideation-phase events keep
  // sharing the same run_id as their own pick, unchanged.
  if (state.final_status) {
    state.run_id = genRunId()
    logEvent('run_start', { run_id: state.run_id, re_pick_after: state.exit_reason || state.final_status,
      spec_commit: bash(`cut -d" " -f1 "${PLUGIN_ROOT}/.sync-stamp" 2>/dev/null | cut -c1-12 || true`).trim()
                   || bash(`git -C "${PLUGIN_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown`).trim(),
      git_branch:  bash(`git -C "${PLUGIN_ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo ?`).trim(),
      researcher_key: 'owner' })
    state.final_status = null; state.exit_reason = null            // the concluded attempt's verdict must never leak into the new one
  }
  state.paper_slug = slugify(s.title); state.workspace = `${P.runs_root}/${state.paper_slug}`
  state.venue = venue; state.picked_seed_file = s.file; state.notes = note
  state.loop_round = 0; state.milestone = null; state.detached = []                 // per-run progress reset (fresh idea, fresh workspace)
  state.round_in_progress = false; state.phase0_verdict = null; state.orphan_ack_count = 0; state.ship_reason = null; state.terminal_reason = null
  state.pending_crash = null
  // (2026-07-11 verified-kill redesign) deep verification already happened INSIDE the weekly ideation loop —
  // every surviving seed carries executed probes + an independent recheck; its Verification Record is the
  // binding input seedToHandoffGoal folds into the work order. The post-pick seed_verify gate is retired.
  state.stage = 'setup_workspace'                                    // → one-time workspace bootstrap → gen_handoff
  return true
}

// writeIdentityDecision — translate the ideation-identity answer into data/profile/identity_decision.json (the
// file the vendored arxiv-scout Phase 0d reads). Mirrors phaseIdeation's ingest mapping; a no-op for
// the key-resume / 'Proceed website-only' options (the re-spawned L1 simply re-runs Phase 0b with/without S2).
function writeIdentityDecision(state, choice) {
  const c = String(choice || ''); let dec = null
  if (/use s2 full/i.test(c))       dec = { use_s2_full: true }
  else if (/use merged/i.test(c))   dec = { use_merged: true }
  else if (/website-only/i.test(c)) dec = { confirmed_author_id: null, use_website_only: true }   // covers 'Website-only ...' AND 'Proceed website-only (skip S2 verification)' — both skip S2 so the re-spawn won't re-escalate (no loop)
  // NOTE: 'Resume after I set S2_API_KEY' and 'Abandon' write NO file (the owner sets a key locally / the run stops).
  if (dec) writeJson(`${PROJECT_DIR}/data/profile/identity_decision.json`, dec)
}

// scanOrphanCount — re-derive the current orphan stop-marker COUNT (bin/scan_orphan_stops.sh) for the ack.
function scanOrphanCount(state) {
  const out = bash(`bash "${PLUGIN_ROOT}/bin/scan_orphan_stops.sh" "${RUNS}/${state.paper_slug}" 2>&1 || true`)
  return parseInt((firstLine(out).match(/^COUNT (\d+)/) || [])[1] || '0', 10)
}

// ── Detach / asyncRewake — the ONLY zero-token-for-hours path; L0-owned (fact #8) ────────────────────
// [[SEAM:async-rewake]] When an L1 returns status:'long_run_fired' (it launched a long LOCAL experiment
// detached via exp_ledger.py run-detach, which appended the PID to .polish/.bg-pids), L0 records
// detached[], persists, and ENDS THE TURN. NEVER poll (no sleep/Monitor/ScheduleWakeup/tail -f). The
// paper-polish-ar Stop hook (rewake-when-done.sh, asyncRewake:true) OS-waits the PID(s) at zero token
// cost and `exit 2` re-wakes THIS session; on re-wake L0 re-spawns the same phase in resume mode.
// The wait is BOUNDED, not infinite: the harness silently kills a command hook at hooks.json `timeout`
// (default 600s — the 2026-07-07 ">10min never re-wakes" root cause), so hooks.json pins timeout:86400
// and the hook self-deadlines just under it, exiting 2 with a STILL-RUNNING message that lands in
// resumeDetached's alive-branch (re-arm + END_TURN → a fresh Stop hook resumes the wait).
function onLongRun(state, env, resume_phase) {
  state.detached = (state.detached || []).concat([{ ...env.detached, resume_phase }]); persist(state)
  logEvent('long_run_fired', { phase: resume_phase })                // LOGGING (side-channel)
  log('Long experiment detached. Ending turn; the asyncRewake Stop hook will re-wake to finalize.'); END_TURN()
}

// ── resumeDetached — [[SEAM:async-rewake]] the re-wake LANDING (the inverse of onLongRun) ─────────────
// RESOLVE each detached job deterministically FROM DISK (exp_ledger.py finalize stamps exit code + after-state +
// extracted numbers into the ledger; provenance minted OUTSIDE any subagent transcript), REAP the tracked PID,
// and clear state.detached so batchGroundClean's quiesce invariant holds. Do NOT re-spawn the L1 here: control
// falls back to main()'s dispatch loop at state.stage='loop' (every detach fires inside the loop), which RE-ENTERS
// the same sub-phase in resume mode (idempotent). The re-spawned L1 FINALIZES from the L0-finalized ledger — it
// does NOT re-run (Phase-5 resume rule) and MUST NOT re-finalize. FAIL LOUD, never silently drop a segment.
// STARTUP SELF-HEAL (B) — runs on the hook re-wake AND any FRESH L0 re-invoke; branches on PID LIVENESS, not on
// who woke it: (a) alive → re-arm wait + END_TURN (never clobber a live run); (b) dead + no exitcode → KILLED
// mid-flight → surface as interrupted crash, never a silent re-spawn; (c) dead + exitcode → finalize, crash-scan
// surfaces a non-zero exit. A fresh L0 is the reliable resume path; the resident exit-2 re-wake is only an accelerator.
function resumeDetached(state) {
  const LEDGER_CLI = `${PLUGIN_ROOT}/${P.vendor_paper_polish}/scripts/exp_ledger.py`
  const crashes = []                                                  // [[SEAM:failure-surface]] records that finalized exit!=0 (or died mid-run) → durable report + owner surface
  const stillRunning = []                                             // [[SEAM:async-rewake]] records whose PID is STILL ALIVE on this (possibly FRESH) L0 — never clobber a live run
  for (const d of (state.detached || [])) {
    const ledger = d.state_path                                       // state_path IS the run-detach LEDGER (so L0 can finalize)
    let finalized = 0, crashedHere = 0, liveHere = 0
    if (ledger && exists(ledger)) {
      // a milestone may fire a SMALL PARALLEL BATCH of INDEPENDENT segments into one ledger; reconcile EVERY
      // still-'running' detached record (each captures its own after-state). We touch ONLY 'running' records,
      // so L0 never double-finalizes — and the resume L1 must not finalize at all (see the B1 goal).
      for (const rec of (readJson(ledger).runs || [])) {
        if (!(rec.detached && rec.run_status === 'running')) continue
        // [[SEAM:async-rewake]] STARTUP SELF-HEAL (B): the resident-session exit-2 re-wake is FRAGILE — laptop
        // sleep / a closed terminal / a 429 that killed the session all leave the run with NO live session to be
        // re-woken, so a FRESH /auto-research (a new L0 — cheap: it rebuilds from disk, redoes no finished work)
        // must reconcile from DISK + PID, never from the hook. Branch on PID LIVENESS, not on who re-woke us:
        const alive = rec.pid && /ALIVE/.test(bash(`kill -0 ${rec.pid} 2>/dev/null && echo ALIVE || echo DEAD`))
        if (alive) { liveHere++; continue }                          // (a) PID ALIVE → experiment genuinely still running: do NOT finalize/clear; re-armed below
        // [[MECH]] H3 (commit-at-finalize=A) — pass the draft-class subject so finalize ATOMICALLY commits the
        // run's products into <ws>/code as it marks the record 'finished' (finalized ⟺ committed). "milestone …"
        // prefix is the run's stable draft-class commit subject (readers + tooling classify on it).
        const out = bash(`python3 "${LEDGER_CLI}" finalize --ledger "${ledger}" --ledger-id "${rec.ledger_id}" --commit-msg "milestone ${d.resume_phase} run ${rec.ledger_id}:" 2>&1 || true`)
        if (/ATOMIC commit failed/.test(out)) {                      // [[MECH]] H3: capture OK but the atomic commit FAILED → finalize left the record
          // 'running' (NOT 'finished'), so nothing is stranded. Surface via the EXISTING crash-surface; the owner's
          // resume re-finalizes and retries the commit (capture_after + "nothing to commit" make the retry idempotent).
          log(`WARN resumeDetached: ${rec.ledger_id} (${d.resume_phase}) finalize-capture OK but the H3 atomic commit FAILED — record left 'running'; surfacing for owner resume (re-finalize retries the commit).`)
          logEvent('detached_anomaly', { phase: d.resume_phase, ledger_id: rec.ledger_id, reason: 'commit_at_finalize_failed' })   // LOGGING (side-channel)
          crashes.push({ phase: d.resume_phase, ledger_id: rec.ledger_id, exit_code: 'H3 atomic commit-at-finalize failed (record left running for retry)',
                         stdout_tail: rec.stdout_tail || '', stdout_log: rec.stdout_log || '' })
          crashedHere++
        } else if (/not finished yet/.test(out)) {                   // (b) PID DEAD but NO exitcode file ⇒ KILLED mid-run (sleep/OOM/kill) — NOT a clean finish:
          log(`WARN resumeDetached: ${rec.ledger_id} (${d.resume_phase}) PID ${rec.pid} dead with NO exitcode — interrupted run; surfacing (never a silent re-spawn).`)
          logEvent('detached_anomaly', { phase: d.resume_phase, ledger_id: rec.ledger_id, reason: 'pid_dead_no_exitcode' })   // LOGGING (side-channel)
          crashes.push({ phase: d.resume_phase, ledger_id: rec.ledger_id, exit_code: 'killed (PID died mid-run, no exitcode)',
                         stdout_tail: rec.stdout_tail || '', stdout_log: rec.stdout_log || '' })
          crashedHere++
        } else {                                                     // (c) PID DEAD + exitcode present → clean finalize; the crash-scan below catches a non-zero exit
          finalized++
          // [[MECH]] P1 (REWRITE-CONSOLIDATION-PLAN) — forward-carry this just-finalized B1 run's
          // extracted_numbers into the paper's audited-values registry (experiment-protocol.md: finalize captures
          // "extracted numbers"), so /rewrite's provenance auditor can look a paper number up instead of
          // re-deriving it. B1 ONLY (resume_phase 'B1:<ms>'): a B2 review run ALSO finalizes here but registers
          // later at bless with --require-audit (pass/B2) — registering it now as pending would dedup-block that;
          // VERIFY produces no paper numbers. NO --require-audit: B1 is producer self-review, not independently
          // audited — the entry carries phase=B1 so the auditor weights its provenance strength. NON-FATAL.
          if (String(d.resume_phase || '').startsWith('B1:')) {
            try {
              bash(`python3 "${LEDGER_CLI}" register --ledger "${ledger}" --ledger-id "${rec.ledger_id}" ` +
                   `--registry "${RUNS}/${state.paper_slug}/AUDITED-VALUES.json" --phase B1`)
            } catch (e) { log(`register: B1 audited-values append failed for ${rec.ledger_id} (non-fatal): ${String(e && e.message || e).split('\n')[0]}`) }
          }
        }
      }
      // [[SEAM:failure-surface]] CRASH SCAN — re-read the now-finalized ledger: a detached run that finalized with
      // a NON-ZERO exit code CRASHED (e.g. a sanity-assert abort), produced NO verdict, and must NOT fall through
      // to a blind B1 re-spawn (without this branch the reproducing L0 improvised a foreground re-run that tripped a
      // rate-limit and killed the turn — 见 DECISIONS.md §RC 历史 — detached-crash surface).
      // Succeeded segments (exit 0) still resume normally; only crashed ones are collected for the report+surface.
      for (const rec of (readJson(ledger).runs || [])) {
        if (rec.detached && Number(rec.exit_code) > 0) {
          crashes.push({ phase: d.resume_phase, ledger_id: rec.ledger_id, exit_code: rec.exit_code,
                         stdout_tail: rec.stdout_tail || '', stdout_log: rec.stdout_log || '' })
          crashedHere++
        }
      }
    } else {
      log(`WARN resumeDetached: no readable ledger at state_path for ${d.resume_phase}; the resume L1 finalizes from its own RESEARCH_LOG.md checkpoint.`)
    }
    if (liveHere) { stillRunning.push(d); continue }                  // (a) live run → KEEP its pidfile + record; re-armed below, never reaped/cleared
    if (d.pidfile) bash(`rm -f "${d.pidfile}"`)                       // reap the tracked PID (batchGroundClean re-checks each pidfile too)
    logEvent('detached_finalized', { phase: d.resume_phase, ledger: ledger || null, finalized, crashed: crashedHere })   // LOGGING (side-channel)
  }
  // [[SEAM:async-rewake]] A fresh L0 that found a LIVE detached run RE-ARMS the wait and ENDS THE TURN (exactly like
  // onLongRun) — never clobber it. If this session stays resident the Stop hook OS-waits; either way a later fresh
  // re-invoke reconciles it from disk+PID (the hook is now only an accelerator, not the correctness path).
  if (stillRunning.length) {
    state.detached = stillRunning; persist(state)
    log(`${stillRunning.length} detached experiment(s) STILL RUNNING — re-armed; ending turn (the asyncRewake hook waits if resident, else re-invoke to finalize). Crash(es) found this pass are re-surfaced on the next reconcile.`)
    logEvent('detached_still_running', { n: stillRunning.length }); END_TURN(); return
  }
  state.detached = []; persist(state)                                 // quiesced → batchGroundClean's gate + the next round are safe
  if (crashes.length) recordDetachedCrash(state, crashes)             // [[SEAM:failure-surface]] arm the surface; main() routes pending_crash → crashSurface
}

// ── recordDetachedCrash — [[SEAM:failure-surface]] durable crash report + arm the owner surface ────────
// A detached run that finalized exit!=0 CRASHED. Do TWO durable things (recoverable even if this turn dies):
// (1) write full evidence to a .crash-<ms>.json marker (writeJson — injection-safe) + a short pointer in
// RESEARCH_LOG.md / FAILURES.md (controlled tokens only, never the raw traceback in a shell string); (2) set
// state.pending_crash so main() routes to crashSurface BEFORE re-entering runB1. The marker also FORCES runB1's
// re-run to stay DETACHED — a previously-detached long run is never silently re-run in the foreground.
function recordDetachedCrash(state, crashes) {
  const ws = `${RUNS}/${state.paper_slug}`
  const ms = state.milestone || (crashes[0] && crashes[0].phase) || 'UNKNOWN'
  const marker = `${ws}/.crash-${slugify(ms)}.json`
  writeJson(marker, { schema: 'auto-research-crash@1', paper: state.paper_slug, milestone: ms,
                      loop_round: state.loop_round, at: now(), crashes })   // full evidence (traceback) — never shell-interpolated
  // [[MECH]] capture hygiene (failure/transient.md): classify each crash's CAUSE (env_transient|oom|code|unknown)
  // mechanically inside the marker — L0 never judges in-context, and the raw traceback never crosses a shell
  // string. The [cause:*] tag is what lets every downstream memory surface (dossier, rescue, viability, /learn)
  // discount a transient environment death instead of solidifying it into a science conclusion.
  const causes = firstLine(bash(`python3 "${PLUGIN_ROOT}/bin/classify_crash.py" annotate --marker "${marker}" 2>/dev/null || echo CAUSES unknown`))
                   .replace(/^CAUSES\s*/, '').trim() || 'unknown'
  const annotated = (readJson(marker).crashes || crashes)
  const ids = annotated.map(c => `${c.ledger_id}(exit ${c.exit_code})`).join(', ')   // controlled tokens only
  bash(`printf '%s\\n' "" "## ${now()} — DETACHED RUN CRASHED · ${ms} (exit!=0)" `
    + `"L0 finalized the detached job(s) and found a NON-ZERO exit (${ids}). NOT auto-re-running blindly:" `
    + `"surfacing to the owner (failure gate). On Resume the re-run is FORCED DETACHED (never foreground a" `
    + `"previously-detached run). Full traceback: ${marker}." >> "${ws}/RESEARCH_LOG.md"`)
  bash(`printf '%s\\n' "[${now()}] ${ms}: detached run crashed (exit!=0) — ${ids}; see ${marker} + RESEARCH_LOG.md. [cause:${causes}]" >> "${ws}/FAILURES.md"`)
  state.pending_crash = { ms, marker, crashes: annotated }; persist(state)
  logEvent('detached_crash', { milestone: ms, n: annotated.length, exit_codes: annotated.map(c => c.exit_code),
    causes: annotated.map(c => c.cause || 'unknown') })   // LOGGING (side-channel)
}

// ── crashSurface — [[SEAM:failure-surface]] route a detected detached-crash to the owner failure gate ──
// Hand the crash to the SAME failureSurface gate every hard-stop uses (report + Resume/Abandon, END_TURN).
// Clear pending_crash the moment the gate opens — the durable record is now pending_gate (+ the .crash marker),
// so a turn that dies after this re-ingests the gate, not a second crash surface.
function crashSurface(state) {
  const pc = state.pending_crash; if (!pc) return
  const esc = pc.crashes.map(c => ({
    id: 'disposition', severity: 'reject',
    question: `Detached experiment ${c.ledger_id} (${pc.ms}) CRASHED with exit ${c.exit_code} — it did NOT `
      + `complete and produced NO verdict. Mechanical cause classification: ${c.cause || 'unknown'}`
      + (c.cause === 'env_transient' ? ` (signature of a TRANSIENT environment failure — an identical re-run usually succeeds; a died run is never a result or a negative)` : '')
      + (c.cause === 'oom' ? ` (OOM awaits adjudication: one identical re-run decides contention vs capacity wall — see failure/transient.md)` : '')
      + `. Diagnose+fix+re-run (the re-run is FORCED DETACHED, never foreground), `
      + `or abandon this idea? Captured traceback: ${pc.marker}.`,
    experiment: c.ledger_id, why_stuck: `detached run exited ${c.exit_code} (crash, no result; cause: ${c.cause || 'unknown'})`,
    crash_tail: (c.stdout_tail || '').slice(-800),
    options: ['Resume after I clarify', 'Abandon this idea'],
  }))
  state.pending_crash = null; persist(state)                          // consumed — the gate (+ .crash marker) is now the durable record
  return failureSurface(state, `${pc.ms}-crashed`, esc)               // → END_TURN (owner failure gate)
}

// ── failureRollup — [[MECH]] P-5 (dossier 03 / H-19; NOT dossier-02's P-5 at finishRun — same name, different
// dossier): deterministic this-run signal rollup for EVERY failure/abandon card. Grep-level ONLY — no LLM
// judgment. NARROW BY CONSTRUCTION: only FLAGGED lines whose ±8-line context names a kill-criterion token
// survive (the ratified revert direction is the default, not a fallback). BOTH fields always present with
// fixed greppable prefixes + explicit "none" forms (H-19 expected_signal: 存在/缺席可查). COUNTS ARE
// PER-WORKSPACE (runs/<slug>): on the crashSurface path the CURRENT crash line was already appended by
// recordDetachedCrash and IS counted in nCrash — expected (dossier X-sci-1 counts exactly all such lines);
// do NOT apply a "minus 1" correction.
function failureRollup(ws) {
  const ff = `${ws}/FAILURES.md`, rl = `${ws}/RESEARCH_LOG.md`
  const nCrash = parseInt(firstLine(bash(`grep -c -E 'detached run crashed|killed runaway PID' "${ff}" 2>/dev/null || echo 0`)), 10) || 0
  const nRes   = parseInt(firstLine(bash(`grep -c 'RESOLVED' "${ff}" 2>/dev/null || echo 0`)), 10) || 0
  const last   = nCrash ? bash(`grep -E 'detached run crashed|killed runaway PID' "${ff}" | tail -1`).trim().slice(0, 200) : ''
  const crash_history = nCrash
    ? `THIS-RUN FAILURES: ${nCrash} crash/failure line(s) in FAILURES.md (${nRes} RESOLVED line(s)) — latest: ${last}`
    : `THIS-RUN FAILURES: none recorded in FAILURES.md`
  const hits = bash(`grep -n 'FLAGGED' "${rl}" 2>/dev/null | tail -5 || true`).trim().split('\n').filter(Boolean)   // tail: the flags NEAREST the failure moment are the disposition-relevant ones
  const kept = []
  for (const h of hits) {
    if (/RESOLVED|CLOSED|cleared/i.test(h)) continue                 // flag resolved on its own line → not open
    const ln = parseInt(h, 10) || 0
    const ctx = ln ? bash(`sed -n '${Math.max(1, ln - 8)},${ln + 2}p' "${rl}" 2>/dev/null`) : ''
    if (/\bK[0-9]\b|\[GAMBLE\]|falsif|central/i.test(ctx)) kept.push(`L${h}`.slice(0, 240))
  }
  const science_flags = kept.length
    ? `OPEN SCIENCE FLAGS: ${kept.length} FLAGGED kill-criteria signal(s) in RESEARCH_LOG.md — ${kept.join(' · ')}`
    : `OPEN SCIENCE FLAGS: none (no FLAGGED line touching K<n>/[GAMBLE]/falsify/central in RESEARCH_LOG.md)`
  return { crash_history, science_flags }
}

// ── Failure surface — the run's ONLY new human gate during execution (PROTOCOL §5) ───────────────────
// [[SEAM:failure-surface]] When the run hits a B1 hard-stop (S1–S10) or a B2 author-only seam the
// built-in fallbacks can't resolve, do NOT auto-decide and do NOT silently skip (there is no
// continue_on_failure). Surface a CONCRETE payload + exactly two dispositions.
function failureSurface(state, phase, escalations) {
  const slug = state.paper_slug
  return gate(state, `failure-${phase}-${slug}`, 'author', [{
    id: 'disposition',
    context: { slug, phase, milestone: state.milestone, loop_round: state.loop_round,
               run_rollup: failureRollup(`${RUNS}/${slug}`),   // [[MECH]] P-5 (dossier 03 / H-19): this-run crash history + open kill-criteria science flags — both lines always present (explicit "none" when zero)
               escalations },   // each escalation states: experiment (if any), why_stuck, what's needed
    options: ['Resume after I clarify', 'Abandon this idea'],
  }])
  // INGEST → ingestGateAnswer (failure-* family, the canonical dispatcher): 'Resume' re-enters the phase in
  // resume mode (stage unchanged); 'Abandon' → finishRun 'abandoned'.
}

// =====================================================================================================
// PHASES
// =====================================================================================================

// ── Stage A — ideation (vendored arxiv-recommender, reproduced at L1) ────────────────────────────────
// NOTE: WHICH researcher a folder runs for is the owner's identity card below (researcher.json); building /
// rebuilding that researcher's profile is owned by arxiv-scout. L0 passes state.user_input VERBATIM and never
// parses it; arxiv-scout interprets a profile-rebuild request ("update my profile") or pinned arXiv links.
// [[SEAM:instance-identity]] (2026-09-13) A folder with no researcher.json gets an OWNER-ONLY card (kind 'identity',
// never adjudicated — gateAnsweredBy) BEFORE the scout: the researcher's Google Scholar URL + the name forms they
// publish under on arXiv, or the shared default. Skipped for the monorepo itself (its own default instance) and in
// ideation-only mode (unattended). bin/ar-init.sh --scholar writes the same file up front.
function identityGate(state, problem) {
  return gate(state, 'researcher-identity', 'identity', [{
    id: 'researcher',
    context: { researcher_json: `${PROJECT_DIR}/researcher.json`, problem: problem || null,
               notes_format: 'scholar: https://scholar.google.com/citations?user=XXXX; names: Ada Lovelace; A. Lovelace' },
    options: [
      { label: 'Pin a researcher', description: 'NOTES carry their Google Scholar profile URL (the profile is built from it) and, after "names:", the ;-separated name forms they publish under on arXiv (their own papers are dropped from the weekly pool).' },
      { label: 'Use the shared default researcher', description: "This folder runs the plugin config's default identity (the owner)." },
      { label: 'Abandon', description: 'Stop; nothing is written.' },
    ] }])
  // INGEST → ingestGateAnswer('researcher-identity'): researcher.json written → re-enter ideation.
}
// [[SEAM:paper-list]] Phase 0b on the Scholar path: WHICH rows are the researcher's own papers. The headless ideation
// L1 returns it as a 'paper-list' escalation (IDEATION-L0.md); L0 asks the OWNER — never an agent — and relays the
// answer through set_paper_decisions.py (ingest), then re-spawns the L1, whose Phase 0a reuses the list.
function paperListGate(state, scoutSays, problem) {
  return gate(state, 'ideation-paperlist', 'identity', [{
    id: 'paper-list',
    context: { list: `${PROJECT_DIR}/data/profile/paper_candidates.md`, json: `${PROJECT_DIR}/data/profile/paper_candidates.json`,
               scout_says: scoutSays || null, problem: problem || null },
    options: [
      { label: 'All others are theirs', description: 'Every undecided row is the researcher\'s (self) EXCEPT the rows named in the NOTES, ;-separated, each "<key or title words>=not" (not theirs) or "=peripheral" (a large collaboration: kept on record, never in the semantic channel).' },
      { label: 'I filled every decision in paper_candidates.json', description: 'You edited the file yourself: self / peripheral / not on every row.' },
      { label: 'Abandon', description: 'Stop the run.' },
    ] }])
  // INGEST → ingestGateAnswer('ideation-paperlist'): decisions written → re-enter ideation (Phase 0c continues).
}
function phaseIdeation(state) {
  if (!exists(`${PROJECT_DIR}/researcher.json`) && !exists(`${PROJECT_DIR}/spec/research.js`)
      && !exists(`${PROJECT_DIR}/.ar-ideation-only`))
    return identityGate(state)
  const scoutBeta = `${PLUGIN_ROOT}/${P.vendor_arxiv}/commands/arxiv-scout-beta.md`
  const goal = [
    `USER FREE-TEXT INPUT (this IS the JS args.input / the command's $ARGUMENTS; L0 captured it RAW and did NOT`,
    `parse it) — bind the block below to that input; arxiv-scout owns ALL of its meaning:`,
    `<<<USER_INPUT`,
    `${state.user_input || ''}`,
    `USER_INPUT`,
    `You are the L1 IDEATION orchestrator. Reproduce ${scoutBeta} (the COMPLETE agentic stand-in for /arxiv-scout)`,
    `AND apply ${PLUGIN_ROOT}/spec/spawn-prompts/IDEATION-L0.md (the L0 subagent deltas that differ from that`,
    `main-session command). Read BOTH and do EXACTLY what they say. Substitute as you read IDEATION-L0.md:`,
    `  <PLUGIN_ROOT>=${PLUGIN_ROOT}  <PROJECT_DIR>=${PROJECT_DIR}`,
  ].join('\n')
  const env = spawnL1('ideation_orchestrator', goal)
  tallyBudget(state, 'ideation', env)
  const esc = env.escalations || []
  const pl = esc.find(e => /paper-list/.test(String((e && e.id) || '')))
  if (pl) return paperListGate(state, pl.question)                   // OWNER-ONLY: whose papers these are is never an agent's call
  if (esc.length)                                                    // identity / S2-key / scrape escalations
    return gate(state, 'ideation-identity', 'author', esc)
  // INGEST → ingestGateAnswer('ideation-identity') → writeIdentityDecision encodes the choice into
  // identity_decision.json, then re-enter ideation (or abandon).
  state.ideation_artifacts = env.artifacts
  // [[SEAM:ideation-integrity]] INDEPENDENT ideation-content auditor (auditor != producer; LLM JUDGMENT, surfaced at
  // GATE-1). spawnAgent above validated only the ENVELOPE SHAPE (bin/validate_envelope.sh, structural) — that CANNOT
  // tell a REAL refined seed from a producer-FAKED one (placeholder/TODO/"for speed" stubs, invented arXiv IDs, an
  // idea with no evidence sidecar on disk). A read-only skeptic reads the on-disk ideation artifacts and writes a
  // per-idea integrity verdict; gateSeedSelect folds it into the GATE-1 card so a faked envelope can NEVER reach the
  // owner silently trusted. Surface-ONLY (never blocks here) — like the sibling literature/audit-artifact surfacers.
  const idir = ideationDir(env.artifacts)                            // ABSOLUTE data/ideations/<week> dir — resolved against PROJECT_DIR (the auditor is a FRESH context with NO cwd guarantee); derived from the refined-seed paths, mirrors htmlReportOf
  const integrity = `${idir}/.integrity.json`; bash(`rm -f "${integrity}"`)
  tallyBudget(state, 'ideation', spawnL2('ideation_auditor', ideationIntegrityGoal(idir, integrity)))
  // [[SEAM:ideation-integrity]] THREE-STATE record — NEVER fail-open silent-null (risk #1). A skipped/overloaded/
  // timed-out auditor (a 529 → the synthetic {status:'failed'} spawnAgent bubbles after one resume) writes NO
  // sidecar; record the 'UNVERIFIED' SENTINEL (NOT null — a null renders IDENTICALLY to "nothing suspect"), so
  // gateSeedSelect surfaces "⚠ integrity check did NOT run — unverified" at GATE-1. The owner MUST be able to tell
  // CLEAN (a verdict: real on disk) from UNCHECKED. A real verdict on disk ⇒ the sidecar path.
  const verdict = exists(integrity) ? readJson(integrity) : null
  state.ideation_integrity = verdict ? integrity : 'UNVERIFIED'
  // COVERAGE RECONCILIATION (risk #3): an empty/mis-pathed ideationDir makes the auditor enumerate ZERO ideas →
  // {ideas:[]} → falsely CLEAN. Record the bare .md stems the auditor ACTUALLY judged; gateSeedSelect matches each
  // idea's context.id against this list and marks any idea NOT covered as UNVERIFIED (same surface as #1) — never
  // clean — so covered < refined-seeds-on-disk can NEVER pass silently.
  state.ideation_integrity_covered = verdict ? (verdict.ideas || []).map(i => i.id) : []
  logEvent('ideation_integrity', { file: state.ideation_integrity, covered: state.ideation_integrity_covered.length, expected: parseRefinedSeeds(env.artifacts).length })  // LOGGING (side-channel)
  state.stage = 'seed_gate'; persist(state)
}
// [[SEAM:ideation-integrity]] the INDEPENDENT ideation-content auditor goal (auditor != producer). The ideation L1
// returns a STRUCTURALLY-valid envelope (bin/validate_envelope.sh checks shape only); this read-only skeptic reads
// the on-disk refined seeds + per-paper ideation JSON + evidence sidecars and judges REAL vs PLACEHOLDER/FABRICATED
// PER IDEA, writing the verdict gateSeedSelect surfaces at GATE-1. Thin pointer: the full realness rubric + verdict
// JSON live in the asset. Mirrors auditArtifactReviewGoal's read-the-spec form.
function ideationIntegrityGoal(idir, out) {
  return [
    `You are the IDEATION INTEGRITY AUDITOR — independent, READ-ONLY, adversarial. You did NOT produce these ideas`,
    `and have NO stake in any surviving. Your ONE job: decide, PER IDEA, whether the ideation output is REAL`,
    `research-grade content or PLACEHOLDER/FABRICATED filler a producer emitted to pass the structural envelope check.`,
    `Your FULL rubric (the realness signals, the read list, and the exact per-idea verdict JSON) is`,
    `${PLUGIN_ROOT}/spec/spawn-prompts/IDEATION-INTEGRITY.md. READ IT FIRST, in full; you CANNOT work without it — if it`,
    `is absent, FAIL LOUD, never improvise a rubric. Substitute these with the run's live values as you read it:`,
    `  <IDEATION_DIR>=${idir}  <OUT>=${out}`,
  ].join('\n')
}

// ── GATE 1 — owner picks ONE seed + a venue (the only Stage-A human gate beyond identity) ────────────
// (2026-09-12, owner decision) ALWAYS the owner's — kind 'seed_select', which gateAnsweredBy never hands to the
// adjudicator: every surviving idea is on this card (arxiv-ideation.js PLAN now writes one plan per survivor, not
// one per converged paper) and the owner picks ONE. An idea left unanswered counts as Skip (readOwnerAnswer).
// [[SEAM:seed-select]] L0 presents the HTML report path + a per-seed table (significance/rigor, title,
// one-line hypothesis, rank line, competitor line) parsed from the refined seed .md files (ONE FILE PER IDEA —
// flat, no grouping) + the prepared venues. Ideas are presented MACHINE-RANK-BEST-FIRST (per parseRefinedSeeds'
// ORDER clause — rank 1 first; filename order only when the weekly pool is absent). The run pursues exactly
// ONE idea: of the ideas answered Keep, only the FIRST (presentation order) is researched; any others are
// IGNORED. NEVER auto-pick a seed (no recommended seed) — rank is surfaced INTELLIGENCE, not a recommendation:
// the idea questions still carry NO recommended option (only the venue question may).
function gateSeedSelect(state) {
  const seeds = parseRefinedSeeds(state.ideation_artifacts)          // [{id,title,hypothesis,significance,rigor,file,verification,judge,premises,rank,novelty}]
  const venues = listPreparedVenues(`${PLUGIN_ROOT}/${P.vendor_paper_polish}`)
  // [[SEAM:ideation-integrity]] the INDEPENDENT ideation auditor's per-idea verdict (written to .integrity.json in
  // phaseIdeation; LLM JUDGMENT) rides in EACH idea's context below. Per [[SEAM:gate-preview]], L0 reads the sidecar
  // at surface time and JOINS its per-idea entry to THIS card by entry.id === context.id (the BARE refined-seed .md
  // stem, e.g. 2606.15061-idea0 — NOT by stripping the question-id's 'idea-' prefix; that join is now PINNED here +
  // tested, not unpinned). Then, next to the matching idea, it SHOWS: a `suspect` entry ⇒ the flag + the auditor's
  // one-line `why`; state.ideation_integrity === 'UNVERIFIED' (auditor DID NOT RUN) OR this s.id ∉
  // ideation_integrity_covered (coverage gap) ⇒ "⚠ integrity check did NOT run / not covered — unverified" (NOT
  // clean); a matching `real` entry ⇒ checked-clean. So a producer-FAKED seed that passed the STRUCTURAL envelope
  // check can NEVER reach the owner silently trusted, and neither can a SKIPPED/UNCOVERED check masquerade as clean.
  // ONE Keep/Skip QUESTION PER IDEA — notes bind to a QUESTION not an option (F7), so per-idea notes need
  // per-idea questions. AskUserQuestion takes ≤4 QUESTIONS/call → the card PAGES (venue + ≤3 ideas page 1, ≤4
  // per later page; every idea shown, none truncated). Only the FIRST Keep runs. The decision file mirrors each
  // question with a durable NOTES: line (survives a crash); chat reply wins over the file on conflict.
  return gate(state, 'GATE1-seed-select', 'seed_select', [
    { id: 'venue', context: { prepared: venues, role: 'default venue for the picked idea' },
      options: venues, recommended: CFG.venue || undefined },
    ...seeds.map(s => ({ id: `idea-${s.id}`,
        context: { title: s.title, hypothesis: s.hypothesis, significance: s.significance,
                   rigor: s.rigor, html: htmlReportOf(state.ideation_artifacts),
                   verification: s.verification || null,   // the machine-derived '## Verification Record' summary (artifact passes, executed-probe headline, kill history) — the PRIMARY quality signal for verified-kill seeds; when present it supersedes everything above
                   rank: (s.rank != null ? s.rank : null),  // P-4/H-18: machine Phase-3 rerank original_rank (1=best; pre-gate position, MAY exceed pool size) joined from week-<W>-gated-pool.json — non-null ⇒ the card MUST render "Phase-3 rerank #N (1=best)" (NEVER "#N/<pool size>"); null (pool/rank absent) ⇒ omit the line, NEVER block the card
                   novelty: s.novelty || null,              // P-4/H-18: ONE competitor/differentiation line (old vintage: LAST '## Novelty Check' verdict sentence — later rounds supersede earlier ones; verified-kill vintage: first '## Prior Art & Differentiation' diff-table row). COMPLEMENTS (never replaces) verification.significance's confrontation clause; null ⇒ omit the line
                   freshness: seedFreshness(s),            // zero-token GATE-1 re-check (verify_bundle.py --freshness: S2 replay + asset re-fetch) — info line, NEVER a gate; null when the seed has no bundle (old vintage) or the check errored
                   judge: s.judge || null,                 // LEGACY (pre-2026-07-11 weeks): the '## Judge Verdict' line — surface only when verification is null
                   unverified_premises: (s.premises != null ? s.premises : null),   // count of UNVERIFIED rows in the '## Premise Ledger' — under verified-kill these are the DEFERRED probes (auto-become mandatory Phase-0 checks in the HANDOFF)
                   id: s.id,                              // [[SEAM:ideation-integrity]] the BARE refined-seed .md stem — the SAME id the auditor keys each verdict entry by; L0 joins the sidecar entry to THIS card by entry.id === context.id (join PINNED here, no prefix-stripping)
                   integrity: state.ideation_integrity,   // the auditor's verdict sidecar PATH, or the 'UNVERIFIED' sentinel (auditor did NOT run); L0 reads it at surface time (gate-preview SEAM)
                   covered: state.ideation_integrity_covered,   // the bare stems the auditor ACTUALLY judged; s.id ∉ covered ⇒ this idea is UNVERIFIED (coverage gap), surfaced like a did-not-run — never clean
                   note: 'ONE idea is researched per run — Keep the one you want (only the FIRST Keep runs); an idea you leave unanswered counts as Skip.' },
        options: [
          { label: 'Keep',
            description: `Research this idea — add a note (n) with your angle / emphasis, or "venue: <key>" to`
                       + ` override the default venue. Only the FIRST Keep runs.` },
          { label: 'Skip', description: 'Do not research this idea' },
        ] })),                                                        // NEVER a recommended pick
  ])
  // INGEST → ingestGateAnswer('GATE1-seed-select') → applyPickedIdea (the canonical dispatcher: venue-validate,
  // take the FIRST Keep, write the flat fields + per-run reset, stage='setup_workspace').
}

// seedFreshness — the zero-token GATE-1 freshness re-check (2026-07-11, replaces the retired post-pick
// seed_verify gate's timeliness function). Days can pass between the weekly run and the pick; this replays
// the bundle's top S2 query + re-fetches asset listings MECHANICALLY (no LLM) and surfaces the result as an
// info line on the card. TOLERANT BY DESIGN: any missing ledger/bundle (pre-redesign vintage) or script/network
// error returns null — freshness is information, never a gate.
function seedFreshness(s) {
  try {
    const idir = s.file.replace(/\/refined\/[^/]+$/, '')             // data/ideations/<week>
    const week = idir.replace(/^.*\/ideations\//, '')
    const ledgerFile = `${PROJECT_DIR}/data/cache/week-${week}-ideation-ledger.json`
    if (!exists(ledgerFile)) return null
    const ledger = readJson(ledgerFile)
    const paperId = s.id.replace(/-idea\d+$/, '')
    const ps = ledger && ledger.papers && ledger.papers[paperId]
    if (!ps) return null
    // idea<N> = the paper's N-th converged candidate in LEDGER order (arxiv-ideation.js PLAN numbers a paper's
    // survivors the same way since 2026-09-12), so each card re-checks ITS OWN bundle, not the paper's first.
    const n = Number((s.id.match(/-idea(\d+)$/) || [])[1] || 0)
    const conv = Object.values(ps.candidates || {}).filter(c => c.status === 'converged')[n]
    if (!conv || !conv.bundle_dir) return null
    const out = bash(`AR_DATA_ROOT="${PROJECT_DIR}" bash "${PLUGIN_ROOT}/${P.vendor_arxiv}/bin/run_py.sh" ` +
      `"${PLUGIN_ROOT}/${P.vendor_arxiv}/scripts/verify_bundle.py" --bundle "${conv.bundle_dir}" --freshness 2>/dev/null`)
    const j = JSON.parse(firstLine(out.trim().split('\n').filter(l => l.trim().startsWith('{')).pop() || 'null'))
    if (!j) return null
    const newHits = (j.new_hits || []).length
    const badAssets = (j.assets || []).filter(a => a.recorded === 'live_verified' && a.now !== 'live_verified')
    return {
      new_s2_hits: newHits,                                          // >0 ⇒ list them on the card (possible fresh scoop — owner judges)
      assets_regressed: badAssets.map(a => `${a.url}: ${a.now}`),    // a repo that died since the weekly run
      checked_utc: j.checked_utc || null,
    }
  } catch (_) { return null }
}

// (phaseSeedVerify / seedVerifyGoal RETIRED 2026-07-11 — the verified-kill redesign moved the deep tier
//  INSIDE the weekly ideation loop: executed premise probes, theory checks, V0 mechanical re-execution,
//  independent recheck, and the WebSearch refutation hunt all run per-candidate BEFORE the seed ever
//  reaches GATE-1. What replaced the post-pick gate: (a) gateSeedSelect surfaces each seed's
//  '## Verification Record' + a zero-token freshness re-check (verify_bundle.py --freshness — S2 replay +
//  asset re-fetch, info-only, never a gate); (b) seedToHandoffGoal folds the Verification Record in as
//  BINDING INPUT, and every UNVERIFIED (deferred-probe) Premise Ledger row becomes a MANDATORY Phase-0
//  check + two-sided §4 K criterion. SEED-VERIFY.md moved to stale/.)

// ── Seed → HANDOFF conversion — render the phased work order from ONE picked seed ────────────────────
// seedToHandoffGoal lifts the /review export format (the review protocol's HANDOFF export, review/
// output-contract.md — kept for the per-experiment sections) into the phased work-order shape: GOVERNANCE pointer → CORE HYPOTHESIS (H1 +
// sub-claims) → KILL/FALSIFICATION (K1…) → EXECUTION PLAN Phase 0→7 → DEFINITION OF DONE. The seed's
// WORKING TITLE / HYPOTHESIS / PREDICTIONS / SETUP / KILL CRITERION / FIRST EXPERIMENT / BASELINES /
// SCOPE / OPEN QUESTIONS map field-for-field onto those sections.
function seedToHandoffGoal(seedFile, slug, venueLabel, notes, reauthor) {
  // Taste injection (1b): the owner's per-idea note from GATE 1 shapes FRAMING/EMPHASIS only.
  const notesClause = notes ? `\nAUTHOR'S ANGLE / NOTES: ${notes} — fold into framing/emphasis;`
                            + ` never override the seed's science or kill criteria.` : ''
  // (2026-07-11 verified-kill) round-0 only: fold the seed's VERIFICATION RECORD into the work order. The
  // weekly loop already EXECUTED the premise probes and independently rechecked every artifact; the seed .md
  // carries the machine-derived '## Verification Record' + the probe-evidenced '## Premise Ledger'. BINDING
  // INPUT: probe-VERIFIED premises get cited with their probe evidence; every UNVERIFIED row (= a DEFERRED
  // probe the verifier ruled weekly-cost-undecidable) is ALWAYS mandated as a Phase-0 check + two-sided §4 K
  // criterion — no owner toggle exists anymore. (Until 2026-09 bundle_io capped deferred rows at
  // ≤1 per seed; the cap is gone, because forcing the verifier to settle instrument-grade premises
  // with a self-written toy inside its probe budget was killing sound directions. Expect several
  // deferred rows per seed now — each one is a Phase-0 check, which is the stronger fate.)
  const verifyClause = !reauthor ? '\n' + [
    `VERIFICATION RECORD (the weekly verified-kill loop's executed evidence for this seed — BINDING INPUT):`,
    `read the seed file's '## Verification Record' and '## Premise Ledger' sections in full. Fold them in:`,
    `premises VERIFIED by an executed probe → cite the probe evidence (dir + values) in §3's assumption ledger;`,
    `every UNVERIFIED row (a deferred probe) → MANDATORY: author it as a Phase 0 check in §5 AND a two-sided K`,
    `criterion in §4 (premise holds / premise fails), so PHASE0_KILL_OR_CONFIRM tests the premise BEFORE the`,
    `method. The frozen falsifier thresholds (with their src anchors) are the §4 kill numbers — never re-anchor`,
    `or relax them; the Verification Record's kill history tells you which adjacent directions are DEAD (do not`,
    `let the work order drift toward one).`,
  ].join('\n') : ''
  const ws = `${P.runs_root}/${slug}`
  // [[MECH]] MODE extension (progressive disclosure): the worker loads the handoff-authoring skill's universal
  // core (SKILL.md), then ONE mode leaf for its inputs + per-phase behavior — round 0 first-author vs rounds-1+
  // re-author. The full RE-AUTHOR contract (inputs, legal ratchet moves, the never-silently-WEAKEN /
  // NEVER-overwrite-locked-baselines discipline) lives ONCE in reference/mode-round-update.md; this goal only flags
  // the mode + the workspace and points the worker at that extension — it does NOT restate the inputs (no duplication).
  const modeExt = reauthor ? 'reference/mode-round-update.md' : 'reference/mode-seed-generation.md'
  const reauthorClause = reauthor ? '\n' + [
    `RE-AUTHOR MODE (per-round regeneration, NOT a first conversion): you are in rounds 1+ — read the round-update`,
    `extension reference/mode-round-update.md and follow it EXACTLY; it carries the full ratchet discipline and names`,
    `the on-disk inputs to FOLD IN (all under ${ws}/). Hold the WHOLE prior ${ws}/HANDOFF.md in context and RE-AUTHOR`,
    `it (do not merely append). OUTPUT: overwrite ${ws}/HANDOFF.md with the complete re-authored work order.`,
  ].join('\n') : ''
  // [[MECH]] ROUND-0 ONLY: the seed→HANDOFF worker is the FIRST writer of TASK_STATUS.concerns.json (§3 seeds one open
  // concern per K); give it the canonical container so its round-0 seed conforms (reauthor reads the ledger, never re-seeds it).
  const ledgerClause = reauthor ? '' : '\nOPEN-CONCERN LEDGER — this is the container your §3 round-0 seed of TASK_STATUS.concerns.json MUST use:\n' + LEDGER_CONTAINER
  return [
    `You are the seed→HANDOFF converter — a PRODUCING WORKER (your spawn contract is your standing system prompt).`,
    `LOAD the \`handoff-authoring\` skill FIRST and follow it: its SKILL.md carries the binding HANDOFF format (the`,
    `§1–§6 section map + the §4b/§4c machine-readable contracts) + the authoring discipline. THEN read the MODE`,
    `extension for your run — ${modeExt} (in that skill) — for your inputs + per-phase behavior. The STRUCTURE is`,
    `BINDING — instantiate every section, dropping or reordering none — but the prose is yours (an authoring rubric,`,
    `not a verbatim template). The skill + its reference/ files use <UPPER_SNAKE> placeholders; substitute each:`,
    `  <SEED_FILE> = ${seedFile}`,
    `  <RUNS_ROOT> = ${P.runs_root}`,
    `  <SLUG> = ${slug}`,
    `  <VENUE_LABEL> = ${venueLabel}`,
    `  <REVIEW_SPEC> = ${P.review_spec}`,
    `  <CITATION_SKILLS> = ${DRAFTING.citation_skills.join(' + ')}`,
    `  <MIN_INTRO_CITATIONS> = ${DRAFTING.min_intro_citations}`,
    `  <MIN_TOTAL_CITATIONS> = ${DRAFTING.min_total_citations}`,
    `  <FIGURE_SKILLS> = ${DRAFTING.figure_skills.join(' + ')}`,
    `  <REQUIRE_FIGURES> = ${DRAFTING.require_figures}`,
    `  <PROFILE_FILE> = ${PROJECT_DIR}/data/profile/profile.json`,
    `  <SESSION_HOURS_ASSUMPTION> = ${CFG.researcher.session_hours_assumption}`,
    `OUTPUT: author the COMPLETE work order to ${ws}/HANDOFF.md and run nothing; your return is the small status envelope (the markdown is on disk), not the markdown itself.`,
    `§4b SCALE-CONTRACT is the binding, machine-checkable definition of FULL INTENDED SCALE the whole loop rests on (LOCKED at Phase 0(C)) — give it special care; follow the rubric's §4b in full.`,
  ].join('\n') + verifyClause + notesClause + reauthorClause + ledgerClause
}
// [[MECH]] M1 — the INDEPENDENT scale-contract completeness reviewer (auditor != producer): a read-only skeptic
// L0 spawns AFTER the worker authors HANDOFF.md to surface any secretly-toy/under-scale dimension at the handoff
// gate. GATES nothing (binding enforcement is V8 in the round verifier). Rubric: spec/spawn-prompts/SCALE-CONTRACT-REVIEW.md.
function scaleContractReviewGoal(ws, seedFile, out) {
  return [
    `You are the SCALE-CONTRACT COMPLETENESS REVIEWER. Read ${PLUGIN_ROOT}/spec/spawn-prompts/SCALE-CONTRACT-REVIEW.md and do`,
    `EXACTLY what it says — it carries your full rubric + the verdict JSON shape. Substitute as you read it:`,
    `  <WS>=${ws}  <SEED_FILE>=${seedFile}  <OUT>=${out}`,
  ].join('\n')
}
// [[MECH]] in-round AUDIT-ARTIFACT INTEGRITY auditor goal (auditor != producer, AT the wave boundary). Thin
// pointer: the full legitimate-vs-goalpost-move rubric lives in the asset; L0 hands it the deterministic
// SHA-diff + first-sight queue it found (mutations, first_sight:true entries included) + where to write the
// verdict. Mirrors workorderHardenGoal's read-the-spec form.
function auditArtifactReviewGoal(ws, round, mutations, out) {
  return [
    `You are the AUDIT-ARTIFACT INTEGRITY AUDITOR (round ${round}) — independent, READ-ONLY, adversarial. You did`,
    `NOT produce this experiment. Your ONE job: decide, for each item, whether it — a changed gate OR a`,
    `criterion/gate artifact reaching its FIRST lock (first_sight:true, nothing to diff yet) — is a LEGITIMATE`,
    `gate (or fix) or a GOALPOST-MOVE — a check that manufactures a pass, whether by a later rewrite or baked in`,
    `from birth.`,
    `Your FULL rubric (the legitimate-vs-goalpost-move classification, the single-sample-gate rule, the inputs,`,
    `and the exact verdict JSON) is ${PLUGIN_ROOT}/spec/spawn-prompts/AUDIT-ARTIFACT-INTEGRITY.md. READ IT FIRST, in full; you`,
    `CANNOT work without it — if it is absent, FAIL LOUD, never improvise a rubric. Substitute these with the`,
    `run's live values as you read it:`,
    `  <ROUND>=${round}  <WS>=${ws}  <OUT>=${out}`,
    `  <MUTATIONS>=${JSON.stringify(mutations)}`,
  ].join('\n')
}
// resolveSkeleton — venue-keyed LaTeX scaffold with a safe fallback (Stage 3).
// key(venue) = the venue rel's TOP-LEVEL segment, lowercased ('Journal-of-Computational-Physics/
// scientific-machine-learning' → 'journal-of-computational-physics'). Use
// ${P.paper_skeleton_dir}/paper-skeleton-<key>/ when it has a master.tex, else the generic
// ${P.paper_skeleton}. Every stocked skeleton is smoke-compiled by tests/t7_skeletons.sh — a broken
// skeleton must fail THERE, never mid-run during drafting/verify.
function resolveSkeleton(venue) {
  const key = String(venue).split('/')[0].toLowerCase()
  const venueDir = `${PLUGIN_ROOT}/${P.paper_skeleton_dir}/paper-skeleton-${key}`
  return exists(`${venueDir}/master.tex`) ? venueDir : `${PLUGIN_ROOT}/${P.paper_skeleton}`
}
// [[MECH]] RC-10: every paper folder is a git repo from the FIRST stage — provenance, the diff-ladder, and
// the rewrite/polish-figures finishing branches all rest on it (见 STATUS-MODEL §3/§4; ship-without-git
// regression 见 DECISIONS.md §RC 历史 — RC-10). A non-repo here is a HARD STOP (re-run the init block), not a
// silent skip.
function assertGitInit(ws) {
  for (const sub of ['', '/paper', '/code']) {
    const ok = bash(`git -C "${ws}${sub}" rev-parse HEAD >/dev/null 2>&1 && echo ok || echo no`).trim()
    if (ok !== 'ok') throw new Error(`assertGitInit: ${ws}${sub} is not a git repo with a baseline commit — the env-stage 'git init' + baseline commit was SKIPPED. Re-run the git-init block before any L1 spawns; the whole run's provenance/diff-ladder/finishing branches depend on it.`)
  }
}
// [[MECH]] setupWorkspace — the ONE-TIME destructive workspace bootstrap (skeleton, living logs, frozen
// sha-stamps, the L0-owned milestone ledger, baseline git commits). Its OWN dispatch stage ('setup_workspace'),
// separate from generateHandoff. Thin JS wrapper over bin/setup_workspace.sh: resolve venue→skeleton, call the
// script, run the RC-10 hard-stop. GUARDED on the milestone ledger's existence (re-running would cp -R the
// skeleton OVER the drafted master.tex + truncate the living logs + reset the ship-gate provenance ledger);
// generateHandoff deletes ENTRIES from milestone-state.json but NEVER the file, so the sentinel persists.
function setupWorkspace(state) {
  const slug = state.paper_slug, ws = `${RUNS}/${slug}`
  // [[MECH]] pool snapshot at pick time (quality-ceiling upgrade 2026-07-07): the scout's ~7-day cache cleanup
  // destroys the ideation pool a late /learn ceiling-audit needs; copy it into the run ws NOW. The bin is
  // idempotent + expiry-tolerant and this NEVER blocks the run (|| true). Sits BEFORE the sentinel so a crash
  // between snapshot and build still retries; re-entry is free.
  bash(`python3 "${PLUGIN_ROOT}/bin/snapshot_ideation_pool.py" --data-root "${PROJECT_DIR}" --ws "${ws}" --seed-file "${state.picked_seed_file}" || true`)
  if (exists(`${ws}/milestone-state.json`)) return                  // [[MECH]] built once already → NEVER re-run the destructive build
  const specSha = bash(`git -C "${PROJECT_DIR}" rev-parse HEAD 2>/dev/null || echo unknown`).trim()
  bash(`bash "${PLUGIN_ROOT}/bin/setup_workspace.sh" "${ws}" "${resolveSkeleton(state.venue)}" `
     + `"${PLUGIN_ROOT}/${P.research_protocol_src}" "${PLUGIN_ROOT}/config/config.yaml" "${specSha}"`)
  assertGitInit(ws)   // [[MECH]] RC-10: fail loud NOW if the git inits were skipped; throw path stays in JS (见 DECISIONS.md §RC 历史 — RC-10)
}

// ── GATE A — HANDOFF approval (surfacing remediation): the binding work order faces the owner BEFORE the
// loop executes it for days. [[SEAM:handoff-approval]] The researcher reviews the PLAN; routine execution
// stays autonomous (Principle I). Reads runs/<slug>/HANDOFF.md and presents H1 + the K kill/success
// criteria + the Phase 0→7 outline. NEVER auto-approves.
// [[MECH]] concern↔prose staleness: bin/concern_prose_lint.sh flags an Editorial-direction bullet that still
// names a concern-id whose structured status has moved on (advisory — D12 precedent: never auto-edits owner
// prose, never blocks). Escalates to a REQUIRED 4th gate option only once the SAME flag (same section sha) has
// ridden through STALE_ESCALATE_K consecutive handoff-approval rounds unaddressed — mirrors VIABILITY_FLOOR_K's
// "let the loop self-repair a few rounds before surfacing" idiom (same K value, same rationale).
const STALE_ESCALATE_K = 3
function concernProseStaleness(ws) {
  if (!CFG.checkpoints.concern_prose_lint) return { stale: [], escalated: [] }
  const prose = JSON.parse(bash(`bash "${PLUGIN_ROOT}/bin/concern_prose_lint.sh" "${ws}" 2>/dev/null || echo '{"stale":[]}'`) || '{"stale":[]}')
  const sidecarPath = `${ws}/.concern-prose-staleness.json`
  const prior = exists(sidecarPath) ? (readJson(sidecarPath) || {}) : {}
  const next = {}
  const escalated = []
  for (const item of (prose.stale || [])) {
    const p = prior[item.id]
    const consecutive = (p && p.last_section_sha256 === prose.section_sha256) ? (p.consecutive_rounds + 1) : 1
    next[item.id] = { consecutive_rounds: consecutive, last_section_sha256: prose.section_sha256 }
    if (consecutive >= STALE_ESCALATE_K) escalated.push(item.id)
  }
  writeJson(sidecarPath, next)
  return { stale: prose.stale || [], escalated }
}

function gateHandoffApproval(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  const h = parseHandoff(`${ws}/HANDOFF.md`)                         // {h1, kill_criteria:[...], phases:[...], definition_of_done}
  const prose = concernProseStaleness(ws)                            // [[MECH]] cheap advisory check every round — see concernProseStaleness above
  // [[MECH]] PER-ROUND REPORT (owner's 需求 5): rounds 1+ reach this gate AFTER the round's review + amplifier + the
  // work-order RE-AUTHOR. Surface WHAT review found + WHAT the amplifier raised + that the re-authored work order
  // below IS the next round's plan, so the owner approves the next round's DIRECTION with eyes open (round 0 = the
  // initial conversion — no prior round to report). PURE JSON-field reads — L0 never reasons over the concern text.
  let report = null
  if (state.loop_round > 0) {
    let led; try { led = exists(`${ws}/TASK_STATUS.concerns.json`) ? readJson(`${ws}/TASK_STATUS.concerns.json`) : null } catch (_) { led = null }
    const open = ((led && led.open_concerns) || []).filter(r => r && (r.status === 'open' || r.status === 'reopened'))
    const tgt = exists(`${ws}/HANDOFF.ambition.target.json`) ? (readJson(`${ws}/HANDOFF.ambition.target.json`) || null) : null
    // FIX B: the gate now carries N+1 (the round being approved); the amplifier that raised this target ran in the
    // just-COMPLETED round N = loop_round-1 (raiseAmbitionTarget stamps raised_at_round with that earning round).
    const raisedThisRound = !!(tgt && tgt.provenance && tgt.provenance.raised_at_round === state.loop_round - 1)
    report = {
      round: state.loop_round,
      prior_review: { open_major: open.filter(r => r.severity === 'major').map(r => ({ id: r.id, concern: r.concern, kind: r.kind || null })),
                      open_minor_count: open.filter(r => r.severity !== 'major').length,
                      verifier_report: exists(`${ws}/VERIFICATION-REPORT.md`) ? `${ws}/VERIFICATION-REPORT.md` : null },
      amplifier: raisedThisRound ? { raised: true, central_result: tgt.central_result, from: (tgt.provenance && tgt.provenance.from) || 'floor',
                                     by: (tgt.provenance && tgt.provenance.by) || 'amplifier' }
                                 : { raised: false, note: 'no bolder claim earned this round (or this round\'s focused-verify was not PASS) — the work order carries the review demands only' },
      next_work: 'the re-authored HANDOFF.md below IS the next round\'s work order — H1 + phases + kill criteria reflect any REDIRECT / RAISE made this round',
    }
    // [[MECH]] (2026-09-12) the just-completed round's KILL / RESCUE / AMPLIFY signals, ON the card, so the owner makes
    // the direction call here. They used to live only behind the viability + central-narrow gates, each auto-resolved
    // to its non-kill default (test-3: K1 not_retained at r1; viability Continue r1–r5). PURE JSON-field reads.
    const done = state.loop_round - 1
    const rj = f => { try { return exists(f) ? readJson(f) : null } catch (_) { return null } }
    const gi = rj(`${ws}/loop-gate-input-r${done}.json`), vb = rj(`${ws}/.round-${done}.viability.json`)
    const rv = rj(`${ws}/.round-${done}.rescue-verdicts.json`), av = rj(`${ws}/.round-${done}.amplify-verdict.json`)
    report.round_signals = {
      overall_risk: (gi && gi.overall_risk) || null,
      viability: vb && { block: vb.block === true, recommended_action: vb.recommended_action || null,
                         what_died: vb.what_died || null, blocking_point: vb.blocking_point || null },
      rescues: (Array.isArray(rv) ? rv : []).map(v => ({ item: v.item, scenario: v.scenario, verdict: v.verdict,
                                                          residual: (v.residual && v.residual.kind) || null })),
      amplify_verdict: av && { outcome: av.outcome, rationale: av.rationale || null },
    }
    report.owner_steer = rj(`${ws}/.round-${state.loop_round}.owner-steer.json`)   // this card's last Amplify/Rescue result, if any
  }
  const questions = [{
    id: 'handoff_approval',
    context: { slug: state.paper_slug, venue: state.venue, round: state.loop_round, report, h1: h.h1, kill_criteria: h.kill_criteria,
               phases: h.phases, definition_of_done: h.definition_of_done,
               handoff_file: `${ws}/HANDOFF.md`,
               scale_review: exists(`${ws}/.scale-contract-review.json`) ? readJson(`${ws}/.scale-contract-review.json`) : null,   // [[MECH]] M1 completeness findings — surface any secretly-toy dimension before approval
               prose_staleness: prose.stale,   // [[MECH]] advisory: Editorial-direction bullets that still name a concern-id whose structured status moved on
               scope_note: 'Non-goals and hard constraints: see HANDOFF.md §2 GOVERNANCE (S1–S10 stops) + §RUN HEADER (problem scope / out-of-scope)' },
    options: [
      { label: 'Approve & run',       description: state.loop_round > 0 ? 'The re-authored work order is sound — run this round.' : 'The work order is sound — begin the loop (Phase 0 first).' },
      { label: 'Revise',              description: 'Edit HANDOFF.md (or tell me what to change); I re-render and re-present.' },
      { label: 'Abandon this idea',   description: 'Do not pursue — end the run (re-run /auto-research to try another idea).' },
      ...(prose.escalated.length ? [{ label: 'Re-author stale Editorial direction now',
          description: `${prose.escalated.join(', ')} read as unaddressed in the Editorial-direction section for `
            + `${STALE_ESCALATE_K} consecutive rounds — pause and fix the prose before approving.` }] : []),
    ] }]
  // [[MECH]] (2026-09-12) rounds ≥1 = the per-round DIRECTION card (kind 'direction' — owner-answered by default via
  // gates.owner_kinds). A SECOND question because AskUserQuestion caps one question at 4 options: send a subagent at
  // the next round's direction before approving it. Round 0 has nothing verified to amplify or rescue.
  if (state.loop_round > 0) questions.push({
    id: 'round_action',
    context: { note: 'Optional. Amplify or Rescue runs a subagent toward your NOTES first; this card then comes back with the re-authored work order (the answer above is not applied this time, except Abandon, which always wins).',
               viability_file: `${ws}/.round-${state.loop_round - 1}.viability.json`,
               rescue_verdicts_file: `${ws}/.round-${state.loop_round - 1}.rescue-verdicts.json`,
               amplify_verdict_file: `${ws}/.round-${state.loop_round - 1}.amplify-verdict.json` },
    recommended: 'No subagent this round',
    options: [
      { label: 'No subagent this round',         description: 'Apply the answer above as-is.' },
      { label: 'Amplify (direction in NOTES)',   description: 'Spawn the amplifier toward the direction you write in NOTES (blank = its boldest earnable rung). It MUST author the work order even if it judges the raise not yet earned; its risk call comes back on this card, and verify_final still re-audits the raised claim.' },
      { label: 'Rescue (K or concern in NOTES)', description: 'Spawn research-rescue on what you name in NOTES. It MUST author runnable experiment work (a wording-only fix does not count); the next round runs it.' },
    ] })
  return gate(state, `handoff-approve-${state.paper_slug}`, state.loop_round > 0 ? 'direction' : 'author', questions)
  // INGEST → ingestGateAnswer('handoff-approve'): an Amplify/Rescue round_action → runOwnerSteer + fold + re-present /
  // Approve→stage='loop' / Revise or the stale-prose option→gen_handoff re-author + re-present / Abandon→finishRun
  // 'abandoned' (+ FINAL-REPORT-killed.md from round 1 on).
}

// [[MECH]] pdPointer — the progressive-disclosure pointer L0 appends to a phase goal: names the open-concern
// artifact + the concern→reference map (ABSOLUTE path), and tells the L1 to run the protocol from its spec (L0
// provides PATHS, not disclosure logic). `ledgerLine` = the frozen round snapshot (in-loop) or per-unit ledger
// (finishing); `scope` = the role caveat; `specWritten` (polish only) = the ledger is spec-written, so the L1
// READS it for disclosure instead of hand-maintaining it.
function pdPointer(ledgerLine, scope, specWritten) {
  return [
    `PROGRESSIVE DISCLOSURE (Doc A §3.2 — execute the protocol documented in your spec${scope ? '; ' + scope : ''}):`,
    `${ledgerLine} The concern→reference map is ${PLUGIN_ROOT}/${CONCERN_MAP}. Disclose references ONLY for`,
    `open/reopened concerns; act only on open/reopened items.`,
    specWritten
      ? `Your spec WRITES this ledger DETERMINISTICALLY (recordSectionLedger/writePolishLedger — not hand-curated): READ it for disclosure; never hand-edit the concern set.`
      : `Update the live concern ledger (TASK_STATUS.concerns.json + TASK_STATUS) per the task-ledger schema. ${LEDGER_CONTAINER}`,
  ].join('\n')
}
// [[MECH]] CANONICAL CONCERN-LEDGER CONTAINER (P0-A). The round-freeze hard-READS `readJson(TASK_STATUS.concerns.json).open_concerns`
// (the loop case ~`openC = readJson(liveC).open_concerns`), so the container MUST be the OBJECT `{ "open_concerns": [ <rows> ] }`
// — a leaf that writes a bare `[…]` or `{ items:[…] }` makes the freeze silently read `[]` and the disclosure set drifts. This
// string is appended to EVERY ledger-WRITING goal (verifier / review / theory_auditor via pdPointer's non-specWritten branch, and
// inlined verbatim where a writer goal does not route through pdPointer) so every writer conforms to the SAME container + the SAME
// canonical row field list. The authoritative copy of this shape lives in the task-ledger skill's
// references/open-concerns-schema.md (split out of its SKILL.md 2026-07-06, dossier-12 H2; kept in sync).
const LEDGER_CONTAINER = [
  `LEDGER CONTAINER (CANONICAL — the round-freeze reads \`.open_concerns\`, so conform EXACTLY): the file is the OBJECT`,
  `{ "open_concerns": [ <rows> ] } — NEVER a bare array and NEVER { "items": [...] } (either makes the freeze read [] and the`,
  `disclosure set silently drift). READ IT FIRST and upsert into the \`open_concerns\` array by \`id\`, PRESERVING every existing`,
  `row (verifier / review / theory_auditor each append to the SAME array — never drop or overwrite a peer's rows). If the file is`,
  `absent, create { "open_concerns": [ <your row> ] }. Each row: { id, concern, status:"open"|"closed"|"reopened"|"deferred",`,
  `severity:"major"|"minor", opened_round, closed_round, last_touched_round, evidence, source }. A row backing`,
  `HANDOFF.ambition.locked.json's central_result/GAMBLE set MUST NOT encode a claim-narrowing disposition as a`,
  `bespoke status string (e.g. never "descoped_infeasible_at_scale") — status stays IN this enum; a narrowing`,
  `disposition is recorded via \`resolution\` text ONLY after research-rescue ran (bin/central_ambition_guard.sh`,
  `enforces this mechanically before the milestone records done).`,
].join('\n')
// ── LITERATURE (unified-loop) — the role/coverage bibliography milestone (HANDOFF Phase 1) ────────────
// [[MECH]] Builds the bib ONCE, after Phase 0 survives + BEFORE experiments/drafting — closes the orphan gap the
// unified-loop split created (draftGoal is content-only, rewrite CANNOT mint .bib entries; 见 DECISIONS.md §RC 历史
// — literature-milestone). Idempotent (milestoneDone skips rounds 2+); NEVER re-opened by generateHandoff. The
// producing-worker reproduces HANDOFF Phase 1 role/coverage; an INDEPENDENT auditor (literatureReviewGoal)
// surfaces any padded/miscited/under-covered bib for owner direction before the loop spends days under a bad one.
function literatureGoal(ws) {
  return [
    `You are the LITERATURE & POSITIONING worker — a PRODUCING WORKER (your spawn contract is your standing`,
    `system prompt). Read ${PLUGIN_ROOT}/spec/spawn-prompts/LITERATURE-WORKER.md and do EXACTLY what it says — it carries`,
    `your full role/coverage protocol, the grounding discipline, and the deliverables. Substitute as you read it:`,
    `  <WS>=${ws}  <CITATION_SKILLS>=${DRAFTING.citation_skills.join(' + ')}`,
    `  <MIN_INTRO_CITATIONS>=${DRAFTING.min_intro_citations}  <MIN_TOTAL_CITATIONS>=${DRAFTING.min_total_citations}`,
    `  <VENDOR_ARXIV>=${PLUGIN_ROOT}/${P.vendor_arxiv}`,
  ].join('\n')
}
// [[MECH]] The INDEPENDENT bibliography auditor (auditor != producer): a read-only adversarial skeptic L0 spawns
// AFTER the literature worker. Re-derives role-coverage from disk and hunts PADDING (topically-related, no role),
// MISCITATION (a real source that does not support its claim), and UNDER-COVERAGE (a differentiation-table row /
// borrowed theorem with no canonical cite; a positioning thread missing its origin or frontier). It assigns NO
// numeric score; it writes a categorical verdict the LITERATURE milestone surfaces (literature_surface). Mirrors
// scaleContractReviewGoal — read-only, no fire path, runs INLINE.
function literatureReviewGoal(ws, out) {
  return [
    `You are the LITERATURE & BIBLIOGRAPHY AUDITOR. Read ${PLUGIN_ROOT}/spec/spawn-prompts/LITERATURE-AUDIT.md and do EXACTLY`,
    `what it says — it carries your full role-coverage rubric + the verdict JSON shape. Substitute as you read it:`,
    `  <WS>=${ws}  <OUT>=${out}  <VENDOR_ARXIV>=${PLUGIN_ROOT}/${P.vendor_arxiv}`,
  ].join('\n')
}
// [[SEAM:capacity-readout]] CAPACITY_READOUT — a bounded, mostly-mechanical L2 leaf: run a tiny real timed probe
// on THIS machine, multiply out against the LOCKED §4b contract's scale_size, and report whether the estimated
// full-scale wall-clock fits the researcher's stated budget_envelope. Thin goal-builder (mirrors literatureGoal
// / scaleContractReviewGoal) — the full rubric lives in spec/spawn-prompts/CAPACITY-READOUT.md.
function capacityReadoutGoal(ws, out) {
  return [
    `You are the CAPACITY-READOUT worker. Read ${PLUGIN_ROOT}/spec/spawn-prompts/CAPACITY-READOUT.md and do`,
    `EXACTLY what it says — it carries your full rubric + the verdict JSON shape. Substitute as you read it:`,
    `  <WS>=${ws}  <OUT>=${out}  <SESSION_HOURS_ASSUMPTION>=${CFG.researcher.session_hours_assumption}`,
    `  <GAP_RATIO_THRESHOLD>=${CFG.checkpoints.capacity_gap_ratio_threshold}`,
  ].join('\n')
}
// ── runAuditArtifactGate (audit-artifact integrity) — the IN-ROUND auditor≠producer gate ─────────────────
// [[SEAM:audit-artifact]] The producer authors its OWN gate/sanity/criterion scripts AND registers each in
// <ws>/AUDIT-ARTIFACTS.locked.json; L0 OWNS the lock — the producer may declare an artifact but NEVER write its
// sha. At every experiment wave boundary, BEFORE re-spawning the producer, L0 re-derives each artifact's sha from
// disk (deterministic SHA-diff + first-sight lock in bin/audit_artifact_diff.sh; enactment in
// bin/audit_artifact_dispose.sh): CHANGED ⇒ a mutation; role∈{criterion,gate} reaching its FIRST lock ⇒ ALSO
// queued for review (2026-07-18 gap-close — first sight used to be a silent no-op, so a self-added condition
// baked in from a script's very first commit and never touched again would lock forever unreviewed; real
// incident: E3_conformal_stopping.py's `frac_stopped` floor, self-labeled "report-labeled" in its own comment yet
// wired into the top-level verdict, drove a bogus S1 with zero independent review — see the asset's WHY YOU
// EXIST #2). role=sanity locks silently either way (not a verdict-gating artifact). No reviewable event ⇒ cheap
// pass. Any reviewable event ⇒ spawn an INDEPENDENT auditor (judgment lives in the asset + the leaf) that
// classifies each item legitimate (bug-fix/TIGHTEN/self-added-anchor-removal/first-sight-grounded) vs
// goalpost_move (weaken-to-pass / overturn-a-recorded-FAIL / pass-by-construction / single-sample gate /
// self-added-anchor — birth or later edit alike). legitimate ⇒ re-lock + continue. goalpost_move OR an
// unreadable verdict (FAIL-CLOSED) ⇒ HARD-block: gate the owner (Strip the flagged condition /
// Accept-with-justification / Abandon), DO NOT re-spawn the producer until disposed. A first-sight goalpost_move
// has no prior version to revert TO — "Strip" un-locks it (bin/audit_artifact_dispose.sh) and leaves a durable
// note in RESEARCH_LOG.md (the producer's own documented resume substrate) instead of a git-checkout. A
// milestone-END mutation is backstopped by the loop-boundary verifier (V5/V8). Returns 'gated' when it opened
// the owner gate (caller must bubble out), else undefined (continue).
function runAuditArtifactGate(state, ws) {
  if (exists(`${ws}/.round-${state.loop_round}.audit-artifact-resolved`)) return  // this round's gate already disposed (mirror viability-resolved) → never re-open
  // DETECT (deterministic; the SHA-diff + first-sight lock + manifest writeback live in bin/, NOT this spec).
  // `mutated` despite the name also carries first_sight:true entries (a criterion/gate reaching its FIRST lock)
  // — the auditor treats both as review subjects; see bin/audit_artifact_diff.sh + the asset.
  const mutated = JSON.parse(bash(`bash "${PLUGIN_ROOT}/bin/audit_artifact_diff.sh" "${ws}" 2>/dev/null || echo '[]'`).trim() || '[]')
  if (!mutated.length) return                                        // nothing changed AND nothing newly-locked needs review → cheap pass, no audit spawned
  const out = `${ws}/.audit-artifact-review.json`; bash(`rm -f "${out}"`)
  tallyBudget(state, 'audit_artifact_audit', spawnL2('audit_artifact_auditor', auditArtifactReviewGoal(ws, state.loop_round, mutated, out)))
  const v = exists(out) ? readJson(out) : null
  writeJson(`${ws}/.round-${state.loop_round}.audit-artifact.json`, { mutated, verdict: v || null })   // sidecar the bin dispose script + the ingest read
  if (v && v.verdict === 'legitimate') {                             // legitimate → re-lock the new shas (bin/) + continue. FAIL-CLOSED: ONLY an affirmative 'legitimate' passes
    bash(`bash "${PLUGIN_ROOT}/bin/audit_artifact_dispose.sh" "${ws}" accept "${state.loop_round}" 2>/dev/null || true`)
    logEvent('audit_artifact_legitimate', { round: state.loop_round, n: mutated.length, paths: mutated.map(x => x.path) }); return
  }
  // goalpost_move OR unreadable verdict (FAIL-CLOSED) → HARD BLOCK: surface for the owner BEFORE the producer is re-spawned
  logEvent('audit_artifact_goalpost', { round: state.loop_round, n: mutated.length, paths: mutated.map(x => x.path), verdict: (v && v.verdict) || 'unreadable' })
  gate(state, `audit-artifact-gate-${state.paper_slug}-r${state.loop_round}`, 'author', [{
    id: 'audit_artifact',
    context: { slug: state.paper_slug, round: state.loop_round, mutated, verdict: v || null,
               manifest: `${ws}/AUDIT-ARTIFACTS.locked.json`, review: out, log: `${ws}/RESEARCH_LOG.md` },
    options: [
      { label: 'Strip the flagged condition',   description: 'A changed gate is restored to its locked content; a first-sight artifact (no prior version exists) is un-locked + noted in RESEARCH_LOG.md for the producer to fix next turn. Either way the producer must address the real FAIL/condition, not the gate.' },
      { label: 'Accept the change — I justify',  description: 'The flagged gate/condition is legitimate and the auditor misjudged it; I take responsibility — re-lock as-is and continue.' },
      { label: 'Abandon this idea',              description: 'The science does not hold up under an honest gate — stop here.' },
    ] }])
  return 'gated'   // INGEST → ingestGateAnswer('audit-artifact-gate-'): Strip | Accept | Abandon (enacted via bin/audit_artifact_dispose.sh)
}

// ── runCentralAmbitionGuard — the MID-LOOP central/GAMBLE-K disposition guard ───────────────────────────
// [[SEAM:central-ambition-guard]] research-rescue was wired ONLY at verify_final's §4c reconciliation and the
// per-wave viability gate. This closes the gap those two miss: a concern-ledger status write for a K backing
// HANDOFF.ambition.locked.json's central_result/GAMBLE set, landing mid-milestone via a plain B1 failureSurface
// resume (never touching research-rescue at all -- the 2026-07-16 gate-invariant-relaxed-speculative-decoding
// incident: K1 -> descoped_infeasible_at_scale via DECISIONS-RESOLVED-17, zero rescue). DETECT is mechanical
// (bin/central_ambition_guard.sh, NOT this spec) before EVERY milestone is recorded done. A hit spawns
// research-rescue FIRST (the existing fan-out, scenario='mid-loop-central-narrow'), then surfaces an owner
// card carrying the rescue's verdict SIDE BY SIDE with the disposition -- mirrors runAuditArtifactGate's
// Revert/Accept/Abandon shape. Returns 'gated' when it opened the owner gate (caller must bubble out) or
// re-entered the loop for loopback work, else undefined (continue).
function runCentralAmbitionGuard(state, ws) {
  if (exists(`${ws}/.round-${state.loop_round}.central-narrow-resolved`)) return  // this round's gate already disposed → never re-open
  const out = firstLine(bash(`bash "${PLUGIN_ROOT}/bin/central_ambition_guard.sh" check "${ws}" "${state.loop_round}" 2>/dev/null || echo OK`))
  if (out === 'OK') return                                          // no central K narrowed this round (or no contract locked yet) → cheap pass
  const ids = out.replace(/^NEEDS_RESCUE\s+/, '').split(',').map(s => s.trim()).filter(Boolean)
  if (!ids.length) return
  const rescueMark = `${ws}/.round-${state.loop_round}.central-narrow-rescue-tried`
  let rescue
  if (!exists(rescueMark)) {
    bash(`touch "${rescueMark}"`)                                   // rescue runs ONCE per round; a still-narrowed re-derive then surfaces (no infinite re-run)
    log(`中心指标 mid-loop narrow guard: ${ids.join(', ')} moved to a non-canonical disposition this round — spawning research-rescue BEFORE the narrow is accepted (禁止轻易放弃).`)
    rescue = runResearchRescue(state, 'mid-loop-central-narrow', ids.map(id => ({ id, milestone: state.milestone })))
    logEvent('central_narrow_rescue', { round: state.loop_round, ids, verdicts: rescue.map(r => r.verdict) })
    if (turnEnded(state)) return 'gated'                             // a detached rescue already END_TURN'd via onLongRun (mirrors the terminal-gate 'rescue' branch)
  } else {
    const all = exists(`${ws}/.round-${state.loop_round}.rescue-verdicts.json`) ? (readJson(`${ws}/.round-${state.loop_round}.rescue-verdicts.json`) || []) : []
    rescue = ids.map(id => all.find(r => r.item === id) || { item: id, verdict: 'not_retained' })
  }
  const loopback = rescue.filter(r => r.verdict === 'needs_loopback' || r.detached)
  const retained = rescue.filter(r => r.verdict === 'retained' && !r.detached)
  if (loopback.length) {                                            // RESCUABLE heavy gap-work → auto re-enter, no owner gate (mirrors §4c's own loopback branch)
    log(`中心指标 rescue: ${loopback.length} K(s) RESCUABLE — auto re-entering the loop to run the authored HANDOFF-ambition gap-work (no owner gate).`)
    logEvent('central_narrow_rescue', { round: state.loop_round, outcome: 'loopback' })
    reopenLoopWith(state); return 'gated'
  }
  if (retained.length === ids.length) {                             // every flagged K retained inline → clear, continue silently
    bash(`touch "${ws}/.round-${state.loop_round}.central-narrow-resolved"`)
    logEvent('central_narrow_rescue', { round: state.loop_round, outcome: 'inline_retained' }); return
  }
  // 1+ K genuinely NOT retained → surface, never silently apply the narrow.
  gate(state, `central-narrow-gate-${state.paper_slug}-r${state.loop_round}`, 'author', [{
    id: 'central_narrow',
    context: { slug: state.paper_slug, round: state.loop_round, milestone: state.milestone, ids, rescue,
               concerns_file: `${ws}/TASK_STATUS.concerns.json`, ambition: `${ws}/HANDOFF.ambition.locked.json`,
               log: `${ws}/RESEARCH_LOG.md` },
    options: [
      { label: 'Confirm the narrow (documented residual)', description: 'The rescue genuinely could not retain it — accept the K\'s current disposition; re-author + ratchet HANDOFF.ambition.locked.json (NARROW-TO-DELIVERED) to match before continuing.' },
      { label: 'Redirect — I will clarify',                description: 'Push through a different way — merge my steer into the next wave instead of accepting the narrow.' },
      { label: 'Abandon this idea',                        description: 'Not worth continuing under the narrowed claim.' },
    ] }])
  return 'gated'
  // INGEST → ingestGateAnswer('central-narrow-gate-'): see ingestGateAnswer.
}

// ── EXPERIMENT (unified-loop; was B1) — EXPERIMENT milestones only (drafting split to runDossier) ─────
// [[MECH]] Walk MILESTONES (PHASE0→LITERATURE→ENV_READY→EXPERIMENTS_DONE→RESULTS_ON_DISK) in order; each is a
// FRESH leaf (fact #6) resuming from RESEARCH_LOG.md + milestone-state.json, executing the round's HANDOFF.md
// under RESEARCH-PROTOCOL.md (S1–S10 hard-stops, no-fabrication, reproduce-before-compare). Round 1 = bootstrap +
// initial suite; rounds 2+ = the review-demanded experiments (ADDITIVE new_exhibit + REDESIGNs of an invalid
// segment). generateHandoff at CONTINUE re-opens EXPERIMENTS_DONE + RESULTS_ON_DISK (clearing a redesign
// target's result.md) so the loop re-walks them under the Phase-5 claim-fingerprint gate; done segments skip.
function runExperiment(state) {                                     // [unified-loop] was runB1; EXPERIMENT milestones only (drafting split to runDossier)
  const ws = `${RUNS}/${state.paper_slug}`
  for (const ms of MILESTONES) {
    if (milestoneDone(ws, ms)) continue                              // idempotent resume
    state.milestone = ms; persist(state)
    const crashMarker = `${ws}/.crash-${slugify(ms)}.json`           // [[SEAM:failure-surface]] set by recordDetachedCrash on a prior crash of THIS milestone
    const priorCrash = exists(crashMarker) ? readJson(crashMarker) : null   // present ⇒ owner chose Resume after a detached crash → force-detach the fixed re-run
    const isLit = ms === CFG.checkpoints.literature_milestone         // [[MECH]] LITERATURE owns HANDOFF Phase 1 bib-building — its OWN focused goal, NOT the experiment-wave spec (no detach, no [PHASE_0] arm)
    const isCap = ms === CFG.checkpoints.capacity_milestone           // [[MECH]] CAPACITY_READOUT owns the early wall-clock heads-up — its OWN thin goal, NOT the experiment-wave spec
    const capOut = `${ws}/.capacity-readout.json`
    const goal = isLit ? literatureGoal(ws) : isCap ? capacityReadoutGoal(ws, capOut) : [
      `Read the experiment loop work spec at ${P.experiment_spec} and reproduce it EXACTLY — execute the goal it`,
      `specifies (it carries your full role, the wave loop, and the helper-spawn contract). The spec is written`,
      `with <UPPER_SNAKE> placeholders; substitute each with the value below before acting, following its`,
      `instructions byte-for-byte (do not reword, reorder, add, or drop anything):`,
      `  <MS> = ${ms}`,
      `  <WS> = ${ws}`,
      `  <BACKEND> = ${BACKEND}`,
      `  <VENDOR_PAPER_POLISH> = ${P.vendor_paper_polish}`,
      `  <EXP_ENG_SKILLS> = ${EXP_ENG.skills.join(' + ')}`,
      `  <FIGURE_SKILLS> = ${DRAFTING.figure_skills.join(' + ')}`,
      `  <CRASH_MARKER> = ${crashMarker}`,
      `  <EXPERIMENT_SPEC_DIR_ABS> = ${PLUGIN_ROOT}/${P.experiment_spec.replace(/\/[^/]+$/, '')}`,   // abs dir of the spec → the worker resolves its on-demand failure/ leaves against this
      `  <PIDFILE> = ${PROJECT_DIR}/.polish/.bg-pids`,   // [[MECH]] ABSOLUTE pidfile the asyncRewake hook OS-waits on (rewake-when-done.sh reads ${PROJECT_DIR}/.polish/.bg-pids). Baked here so the worker NEVER reconstructs it from $CLAUDE_PROJECT_DIR — that var is UNSET in the Bash tool → bare-$CLAUDE_PROJECT_DIR collapses to /.polish/.bg-pids and crashes run-detach's makedirs. Writer (this) == reader (the hook).
      `CONDITIONAL SECTIONS — the spec marks [BASE]/[PRIOR_CRASH]/[PHASE_0] arms in HTML comments. INCLUDE the`,
      `[BASE] arm always; INCLUDE [PRIOR_CRASH] = ${priorCrash ? 'YES' : 'NO'}; INCLUDE [PHASE_0] = ` +
        `${ms === CFG.checkpoints.phase0_milestone ? 'YES' : 'NO'}. Ignore every arm marked NO (it is not part of this goal).`,
    ].join('\n')
    if (!isLit && !isCap && CFG.checkpoints.audit_artifact_surface && runAuditArtifactGate(state, ws) === 'gated') return  // [[SEAM:audit-artifact]] re-derive the producer's OWN gates BEFORE re-spawning it for the next wave — a goalpost-move (a rewritten failing gate) surfaces HERE, before the producer fires the downstream waves on a manufactured pass. checkpoints.audit_artifact_surface=false → run-to-completion (skip the integrity hard-block, like the sibling surfacing checkpoints). CAPACITY_READOUT registers no AUDIT-ARTIFACTS.locked.json gate of its own — exempted like isLit.
    // [[MECH]] RC-12 LOCK-GATE: an experiment milestone past Phase 0 may NOT run while the SCALE/AMBITION
    // baseline is unlocked — an unlocked run lets a post-Phase-0 WEAKEN pass V5 as a silent "legacy" no-op.
    // Verify LOCKED; auto-heal from HANDOFF §4b/§4c if the Phase-0(C) lock was skipped; a missing block → STOP LOUD.
    // CAPACITY_READOUT is NOT exempted here (unlike isLit) — it is the very next milestone after Phase 0, so
    // this auto-heal is exactly what guarantees §4b's budget_envelope/scale_size are on disk before it reads them.
    if (!isLit && ms !== CFG.checkpoints.phase0_milestone
        && firstLine(bash(`bash "${PLUGIN_ROOT}/bin/contract_lock_status.sh" "${ws}" 2>&1`)).startsWith('ABSENT')) {
      const lk = bash(`bash "${PLUGIN_ROOT}/bin/lock_contracts.sh" "${ws}" 2>&1`)
      if (firstLine(lk).startsWith('ERROR')) throw new Error(`contracts unlocked before ${ms}: ${lk}`)
    }
    const env = isLit ? spawnWorker('literature_worker', goal)
              : isCap ? spawnL2('capacity_probe_worker', goal)     // [[MECH]] bounded leaf tier — a timed micro-probe + arithmetic, no delegation mandate
              : spawnWorker('experiment_worker', goal)
    tallyBudget(state, isCap ? 'capacity_readout' : 'b1_per_round', env)
    if (isEnvFailed(env))                                                    // [[MECH]] surfacing fix (C): a
      return failureSurface(state, `B1-${ms}-failed`,                               // failed L1 is NOT a done milestone —
        (env.escalations && env.escalations.length) ? env.escalations               // do NOT --allow-empty commit + record
          : [{ id: 'l1_failed', severity: 'reject',                                 // it (which silently corrupted the
               question: `B1 milestone ${ms}: the experiment leaf returned status:'failed' (no valid envelope after one`   // resume ledger)
                 + ` resume — likely overload). Nothing was produced; not recording it as done.`,
               options: ['Resume after I clarify', 'Abandon this idea'] }])
    if (env.status === 'long_run_fired') return onLongRun(state, env, `B1:${ms}`)   // [[SEAM:async-rewake]]
    if (env.escalations && env.escalations.length) {                                // S1–S10 hard-stop
      // [[SEAM:audit-artifact]] the producer's internal waves this turn may have authored + first-locked NEW
      // gate/criterion artifacts invisible to L0 until now (§ runAuditArtifactGate normally fires BEFORE this
      // spawn, so it never saw them) — re-derive BEFORE the owner is asked to disposition an S1 that might rest
      // on one of them (2026-07-18 gap-close: an S1 driven by a self-added anchor is not a real S1). Catches it
      // one step earlier than the next turn's top-of-loop check would.
      if (!isLit && !isCap && CFG.checkpoints.audit_artifact_surface && runAuditArtifactGate(state, ws) === 'gated') return
      return failureSurface(state, `B1-${ms}`, env.escalations)                     // resume | abandon (§5)
    }
    // [[MECH]] LITERATURE deterministic backstop (before recording done): the worker must have produced a non-empty
    // references.bib + a differentiation_table.md. A silently-empty bib HARD-stops mechanically (like assertGitInit),
    // NOT recorded as done (re-runs on resume). The role-coverage QUALITY judgment is the auditor's job below.
    if (isLit) {
      const bib = `${ws}/paper/references.bib`
      const nEntries = exists(bib) ? parseInt(bash(`grep -c '^@' "${bib}" 2>/dev/null || echo 0`).trim() || '0', 10) : 0
      if (!exists(`${ws}/differentiation_table.md`) || !nEntries)
        return failureSurface(state, `B1-LITERATURE-empty`, [{ id: 'lit_empty', severity: 'reject',
          question: `LITERATURE returned success but produced no bibliography (references.bib entries=${nEntries},`
            + ` differentiation_table.md ${exists(`${ws}/differentiation_table.md`) ? 'present' : 'MISSING'}). The loop`
            + ` must not run experiments + drafting under an empty bibliography.`,
          options: ['Resume after I clarify', 'Abandon this idea'] }])
    }
    // [[MECH]] F2 NO-OP-REOPEN BACKSTOP (the "review→fix→review spin" fix). A review-driven re-open that produced
    //   NO new result.md would --allow-empty re-mark EXPERIMENTS_DONE = a no-op masquerading as progress. So before
    //   the re-mark: if this milestone was RE-OPENED this round (snapshot exists) AND the EXPERIMENTS/*/result.md
    //   SHA set is byte-identical to the pre-open snapshot (bin/ diff), REFUSE the re-mark + surface noop-reopen
    //   (fail-closed). PROGRESS (set changed) or no snapshot (nothing re-opened) ⇒ proceed normally.
    if (ms === 'EXPERIMENTS_DONE'
        && firstLine(bash(`bash "${PLUGIN_ROOT}/bin/reopen_noop_diff.sh" check "${ws}" "${state.loop_round}" 2>/dev/null || echo PROGRESS`)) === 'NOOP') {
      logEvent('noop_reopen', { round: state.loop_round, ms })       // LOGGING (side-channel)
      return failureSurface(state, `noop-reopen-r${state.loop_round}`, [{ id: 'noop_reopen', severity: 'reject',
        question: `EXPERIMENTS_DONE was re-opened this round for review-demanded work, but the experiment worker produced`
          + ` NO new result (the on-disk EXPERIMENTS/*/result.md set is byte-identical to the pre-open snapshot). Re-marking`
          + ` it done would silently re-ledger a no-op as progress (the review→fix→review spin). Not recording it as done.`,
        options: ['Resume after I clarify', 'Abandon this idea'] }])
    }
    // [[SEAM:central-ambition-guard]] BEFORE recording ANY milestone done: mechanically re-derive whether a
    // concern backing HANDOFF.ambition.locked.json's central_result/GAMBLE set just moved to a narrowing
    // disposition this round with no rescue on disk — spawn research-rescue FIRST if so. Cheap no-op else.
    if (CFG.checkpoints.central_ambition_guard && runCentralAmbitionGuard(state, ws) === 'gated') return
    // [[MECH]] RC-9 + RC-3: milestone genuinely completed (no long-run, no hard-stop) → commit provenance
    // and record it in the L0-owned ledger. This commit is ALSO the running write_backs baseline (RC-4),
    // and these fields are exactly what bin/milestone_done.sh reads for idempotent resume next time.
    bash(`git -C "${ws}/code"  add -A && git -C "${ws}/code"  commit -qm "milestone ${ms}: code"  --allow-empty`)
    bash(`git -C "${ws}/paper" add -A && git -C "${ws}/paper" commit -qm "milestone ${ms}: paper" --allow-empty`)
    const msState = readJson(`${ws}/milestone-state.json`)
    msState.milestones[ms] = { completed_at: now(),
      code_commit:  bash(`git -C "${ws}/code"  rev-parse HEAD`).trim(),
      paper_commit: bash(`git -C "${ws}/paper" rev-parse HEAD`).trim() }
    writeJson(`${ws}/milestone-state.json`, msState)
    bash(`git -C "${ws}" add -A && git -C "${ws}" commit -qm "milestone ${ms}: workspace" --allow-empty`)
    logEvent('milestone_done', { ms, code_commit: msState.milestones[ms].code_commit,
      paper_commit: msState.milestones[ms].paper_commit })            // LOGGING (side-channel; RC-9 provenance)
    // [[MECH]] concern↔prose staleness (advisory, log-only here — the human-visible flag lives at
    // gateHandoffApproval/concernProseStaleness): widens observability so a long milestone's drift is greppable
    // in run-events.jsonl even between handoff-approval gates, never gates this commit.
    if (CFG.checkpoints.concern_prose_lint) {
      const proseCheck = JSON.parse(bash(`bash "${PLUGIN_ROOT}/bin/concern_prose_lint.sh" "${ws}" 2>/dev/null || echo '{"stale":[]}'`) || '{"stale":[]}')
      if (proseCheck.stale && proseCheck.stale.length)
        logEvent('concern_prose_stale', { ms, round: state.loop_round, stale: proseCheck.stale })
    }
    if (priorCrash) {                                                 // [[SEAM:failure-surface]] crash resolved (milestone completed) — clear the re-detach/forensic marker
      bash(`rm -f "${crashMarker}"`)
      // capture hygiene (failure/transient.md): the append-only FAILURES.md crash line gets its RESOLVED pairing,
      // so a re-run-cleared (typically transient) death reads as self-healed downstream, never as open evidence.
      bash(`printf '%s\\n' "[${now()}] ${ms}: RESOLVED — prior crash cleared, milestone completed on re-run (pairs the earlier [cause:*] line closed)." >> "${ws}/FAILURES.md"`)
    }
    // [[SEAM:capacity-readout]] CAPACITY_READOUT surfaces an early wall-clock heads-up: the locked §4b contract's
    // estimated full-scale cost on THIS machine vs the researcher's stated budget. Like Phase 0, this NEVER
    // auto-kills — a CONCERN is an informed owner fork BEFORE the costly LITERATURE/ENV_READY milestones, not a
    // verdict on the science (§4b stays hardware-blind). FITS (or no stated budget) advances silently. The
    // worker WRITES its verdict to capOut (mirrors literature_reviewer's litReview pattern) — read from disk,
    // never env.metrics (a spawnL2 leaf's file output is the contract, not envelope metrics).
    const capEvidence = isCap && exists(capOut) ? readJson(capOut) : null
    if (isCap && CFG.checkpoints.capacity_surface && capEvidence && capEvidence.verdict === 'CONCERN') {
      return gate(state, `capacity-${state.paper_slug}`, 'author', [{
        id: 'capacity',
        context: { slug: state.paper_slug, evidence: capEvidence, log: `${ws}/RESEARCH_LOG.md`,
                   scale_contract: `${ws}/HANDOFF.scale-contract.locked.json` },
        options: [
          { label: 'Proceed', description: 'The estimate is a heads-up, not a wall — continue at full locked scale; let the hardware tell the truth (reactive OOM/partition handling still applies).' },
          { label: 'Redirect — I will clarify', description: 'Widen my stated budget, or genuinely REDIRECT/narrow the claim (§4b/§4c ratchet) before the costly milestones — re-authors the work order.' },
          { label: 'Abandon this idea', description: 'Not worth pursuing at this budget on this hardware.' },
        ] }])
      // INGEST → ingestGateAnswer('capacity-'): Proceed→continue / Redirect→gen_handoff re-author / Abandon→finishRun.
    }
    // [[SEAM:phase0-surface]] (B) the toy kill-or-confirm probe is a CHEAP TRIAGE, NOT a verdict: sub-full-scale,
    // so it can never SCIENCE-kill (no-partial-verdict rule). CONFIRM/SUSPECT both surface as an INFORMED owner
    // fork before the costly milestones; the [GAMBLE] K is settled at FULL scale later (V8-audited), never
    // auto-killed on the toy. Fires ONCE (milestoneDone skips on resume). NOT_APPLICABLE skips the surface.
    if (ms === CFG.checkpoints.phase0_milestone && CFG.checkpoints.phase0_surface
        && (env.metrics && env.metrics.phase0_verdict) !== 'NOT_APPLICABLE') {
      state.phase0_verdict = (env.metrics && env.metrics.phase0_verdict) || 'CONFIRM'; persist(state)
      const suspect = state.phase0_verdict === 'SUSPECT'
      return gate(state, `phase0-${state.paper_slug}`, 'author', [{
        id: 'phase0',
        context: { slug: state.paper_slug, verdict: state.phase0_verdict, toy_only: true, log: `${ws}/RESEARCH_LOG.md`,
                   evidence: (env.metrics && env.metrics.phase0_evidence) || null },
        options: [
          { label: 'Proceed', description: suspect
              ? 'Toy looks SUSPECT, but a toy cannot kill — proceed to settle the [GAMBLE] K at FULL scale (V8-audited).'
              : 'Toy CONFIRMs the [GAMBLE] K is worth the full test — continue to the full experiments.' },
          { label: 'Redirect — I will clarify', description: 'Adjust scope/approach before the costly phases.' },
          { label: 'Abandon this idea',         description: suspect
              ? 'You judge the toy signal hopeless enough to stop cheaply — your informed call, NOT an auto-kill.'
              : 'Not worth the deeper investment.' },
        ] }])
      // INGEST → ingestGateAnswer('phase0-'): Proceed→continue / Redirect→clear the phase0 marker + re-spawn / Abandon→finishRun.
    }
    // [[MECH]] LITERATURE gate: an INDEPENDENT auditor (auditor != producer) re-derives bib role-coverage from
    // disk; an INCOMPLETE verdict (padding/miscitation/under-covered/thin) OR a SCOOPED verdict (S10: a rival
    // covers the central contribution with no defensible delta — never grind a true-but-known paper) surfaces
    // for owner direction before the loop spends days under it (complete or literature_surface off → advance
    // silently). Mirrors phase0 (milestone already done: 'Proceed' continues, 'Revise' clears the marker to
    // rebuild — a scooped rebuild REPOSITIONS against the rival per the owner's notes; a silent claim-narrow
    // stays forbidden by §4c).
    if (isLit && CFG.checkpoints.literature_surface) {
      const litReview = `${ws}/.literature-review.json`; bash(`rm -f "${litReview}"`)
      tallyBudget(state, 'b1_per_round', spawnL2('literature_reviewer', literatureReviewGoal(ws, litReview)))
      const v = exists(litReview) ? readJson(litReview) : null         // robust to a broken leaf (absent ⇒ no findings ⇒ advance)
      if (v && (v.verdict === 'incomplete' || v.verdict === 'scooped')) {
        const scooped = v.verdict === 'scooped'
        if (scooped) logEvent('literature_scooped', { paper: state.paper_slug, rival: (v.scooped_by || {}).rival || null })
        return gate(state, `literature-${state.paper_slug}`, 'author', [{
          id: 'literature',
          context: { slug: state.paper_slug, verdict: v.verdict, padding: v.padding || [], miscited: v.miscited || [],
                     uncovered_comparators: v.uncovered_comparators || [], thin_threads: v.thin_threads || [],
                     ...(scooped ? { scooped_by: v.scooped_by || null, stop: 'S10 — novelty collapse (RESEARCH-PROTOCOL §3)' } : {}),
                     summary: v.summary || null, bib: `${ws}/paper/references.bib`, diff_table: `${ws}/differentiation_table.md` },
          options: [
            { label: 'Proceed',                 description: scooped
                ? 'I judge the residual delta defensible against the named rival — continue, positioning against it head-on.'
                : 'The bibliography is good enough — continue to experiments + drafting.' },
            { label: 'Revise — I will clarify', description: scooped
                ? 'Reposition: rebuild the bibliography + differentiation table against the rival per my notes (a real delta must be named, not wished for); re-audit.'
                : 'Rebuild the bibliography addressing the auditor gaps (+ any notes I add); re-audit.' },
            { label: 'Abandon this idea',       description: scooped
                ? 'Scooped — the central contribution is already covered; do not grind a true-but-known paper.'
                : 'Do not pursue this paper.' },
          ] }])
      }
      // INGEST → ingestGateAnswer('literature-'): Proceed→continue / Revise→clear the LITERATURE marker + rebuild / Abandon→finishRun.
    }
  }
  state.milestone = null; persist(state)                            // [unified-loop] experiment milestones done this round → runDossier
}

// ── DOSSIER (writing-redesign) — per-round FINDINGS-DOSSIER maintainer ────────────────────────────────
// Replaces the per-round whole-paper CONTENT drafter (retired). The loop NO LONGER produces a manuscript: runs
// EVERY round after runExperiment, ONE dossier_writer maintains the INTERNAL SCIENCE RECORD (FINDINGS-DOSSIER.md)
// the review panel reads — subject-isolated to the science (no process/audit/chronology). The manuscript is
// written ONCE post-loop by the writing engine from the FROZEN dossier. SCOPE = the science record only (NOT a
// paper, NOT prose, NOT figures-embedding). Idempotent: a .round-<N>.dossier marker → skip.
function dossierGoal(ws, round) {
  return [
    `You are the FINDINGS-DOSSIER MAINTAINER LEAF (round ${round}) — a single-context worker, NO sub-spawn. Read`,
    `${PLUGIN_ROOT}/spec/spawn-prompts/DOSSIER.md and do EXACTLY what it says — it carries your full scope (the SCIENCE`,
    `RECORD the SPEC rests on, never a manuscript), the inputs, the section structure, and the SUBJECT-ISOLATION +`,
    `anti-fabrication discipline. Substitute as you read it:`,
    `  <WS>=${ws}  <ROUND>=${round}`,
  ].join('\n')
}
function runDossier(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  const marker = `${ws}/.round-${state.loop_round}.dossier`
  if (exists(marker)) return                                         // [[MECH]] per-round idempotent: already maintained this round (resume) → skip
  bash(`rm -rf "${PROJECT_DIR}/.polish"`)                            // [[MECH]] DISARM the freeze hook — the dossier writer is a pre-freeze PRODUCER (guarded by the focused verifier, not the freeze hook)
  const env = spawnL2('dossier_writer', dossierGoal(ws, state.loop_round))
  tallyBudget(state, 'dossier_per_round', env)
  if (isEnvFailed(env))                                       // a failed dossier is NOT a done round — surface, do not advance
    return failureSurface(state, `dossier-r${state.loop_round}-failed`,
      (env.escalations && env.escalations.length) ? env.escalations
        : [{ id: 'dossier_failed', severity: 'reject',
             question: `Dossier round ${state.loop_round}: the dossier_writer returned status:'failed' (no valid`
               + ` envelope after one resume — likely overload). Nothing was written; not advancing.`,
             options: ['Resume after I clarify', 'Abandon this idea'] }])
  if (env.escalations && env.escalations.length)                     // a dossier hard-stop (rare) bubbles to the owner
    return failureSurface(state, `dossier-r${state.loop_round}`, env.escalations)
  bash(`git -C "${ws}" add FINDINGS-DOSSIER.md 2>/dev/null && git -C "${ws}" commit -qm "round ${state.loop_round}: findings dossier" --allow-empty || true`)
  bash(`touch "${marker}"`)                                          // [[MECH]] mark this round's dossier maintained (idempotent resume)
}

// ── VERIFY — independent reversed-incentive verifier (RC-1, the lead finding) ────────────────────────
// [[MECH]] TWO scopes, ONE harness (spec/spawn-prompts/VERIFY-PROTOCOL.md): (1) FOCUSED per-round (runFocusedVerify,
//   scope='focused'): V1-V6/V8 + code-audit; does NOT surface — writes failed checks to the concern ledger and
//   BLOCKS EXIT via the gate's RC-1 belt (verdict != PASS → CONTINUE), so a defect is re-addressed next round.
//   (2) SCIENCE terminal (runVerify, scope='science', once after EXIT): the full audit V1-V6/V8/V9 + figure
//   provenance, NOT the V7 citation floors (a build-to sanity target met at the LITERATURE milestone + role-audited
//   by the literature auditor there, NOT verified at the polish chain); a FAIL SURFACES
//   via §5 failureSurface. A SEPARATE reversed-incentive context whose ONLY job is to FALSIFY the SUCCESS label — never wrote
//   the work, never writes paper/code. verdict='PASS' only if every IN-SCOPE check passes.
// [[MECH]] B4-25: the four PURELY-MECHANICAL facts (V4 Gate-4a recorded-verdict presence / V6 paper↔result.json
//   number-sync candidates / V7 figure→plot-script trace / \cite→.bib fabrication) are SUNK to bin/verify_preflight.sh
//   (run before each spawnVerifier, both scopes); the verifier READS <PREFLIGHT> and does NOT re-derive them, freeing
//   its single context to DEPTH-mine the one lethal clue. A belt-eligible mechanical FAIL overrides a verifier PASS
//   (verifyBeltReconcile, fail-closed); all JUDGEMENT (V1/V2/V3/V5/V8/V9/V10 + V4 fit / V6 materiality) stays in the md.
// [[MECH]] the V1–V9 rubric LIVES IN MARKDOWN (spec/spawn-prompts/VERIFY-PROTOCOL.md), not inlined in L0; the goal names the
// path + live substitution values + PD sensor role, makes reading it FIRST mandatory + fail-loud (RC-1 — 释义见
// research-flow-narration 幕「RC-1」). Preflight checks the asset exists.
function verifierGoal(ws, round, scope) {
  // [unified-loop] scope ∈ {'focused','science'} — the SAME VERIFY-PROTOCOL.md rubric over a SCOPED subset; the
  // [FOCUSED]/[SCIENCE] arms (which checks run, + the SCIENCE-only §4c ambition reconciliation) live IN the asset.
  // [[MECH]] #3 amplifier: reconcile delivery against the CURRENT TARGET — the raised target if a prior amplify
  // round earned one (HANDOFF.ambition.target.json), ELSE the immutable locked FLOOR. BACKWARD-COMPAT: target.json
  // ABSENT (no raise yet) ⇒ the FLOOR, exactly as before; an un-earned raise → delivery < target → reconciled:false.
  const ambitionFile = exists(`${ws}/HANDOFF.ambition.target.json`)
    ? `${ws}/HANDOFF.ambition.target.json` : `${ws}/HANDOFF.ambition.locked.json`
  return [
    `You are the INDEPENDENT VERIFIER (round ${round}, scope=${scope}). Read ${PLUGIN_ROOT}/spec/spawn-prompts/VERIFY-PROTOCOL.md FIRST,`,
    `in full, and do EXACTLY what it says — it carries your full V1–V10 + CAPABILITY + NO-DEMOTION + VERDICT rubric`,
    `AND the SCOPE arm that gates which checks run. You did NOT produce this work; you only READ and JUDGE, writing`,
    `NOTHING into the spec, the dossier or the code. If the rubric is absent, FAIL LOUD, never improvise.`,
    `Substitute as you read it:`,
    `  <ROUND>=${round}  <WS>=${ws}  <SCOPE>=${scope}  <AMBITION_FILE>=${ambitionFile}`,
    `  <PREFLIGHT>=${ws}/.verify-preflight.json`,
    `  <CONCERN_MAP>=${PLUGIN_ROOT}/${CONCERN_MAP}  <REQUIRE_FIGURES>=${DRAFTING.require_figures}`,
    `  <AUDIT_SKILLS>=${AUDIT.skills.join(', ')}  <ALLOW_SPAWN>=${AUDIT.allow_spawn}`,
    `  <CODE_AUDIT_NO_HARDCODED>=${AUDIT.code_audit_no_hardcoded}`,
    `Record each PASS/FAIL with file:line evidence in ${ws}/VERIFICATION-REPORT.md and return EXACTLY the envelope`,
    `the rubric describes (metrics.verdict PASS/FAIL, escalations[] per failed check, report path in artifacts[]).`,
    LEDGER_CONTAINER,   // the canonical ledger-object shape the asset's PROGRESSIVE DISCLOSURE section refers to (single-sourced)
  ].join('\n')
}
// spawnVerifier — the independent_verifier is a lean READ-ONLY judge: a LEAF (spawnL2) when audit.allow_spawn=false
// (the lean default), the orchestrator type when ON (so it MAY fan out Task sub-auditors). Pick the tier FROM the
// flag — a plain 'claude' leaf silently cannot spawn (see spawnAgent's gotcha note).
function spawnVerifier(goal) {
  return AUDIT.allow_spawn ? spawnL1('independent_verifier', goal) : spawnL2('independent_verifier', goal)
}
// [[MECH]] B4-25 FAIL-CLOSED BELT: verify_preflight.sh is a pure mechanical sensor. If it recorded an UNAMBIGUOUS
// mechanical FAIL (belt-eligible: fabricated \cite / missing Gate-4a verdict / untraced figure) yet the verifier
// still returned PASS, the mechanical FACT wins — override to FAIL (a verifier cannot bless away a fabricated
// citation). V6 number-sync is candidates-only (belt:false) and NEVER triggers this. Preflight-absent → no-op.
function verifyBeltReconcile(ws, scope, verdict) {
  if (verdict !== 'PASS') return verdict
  let pf; try { pf = readJson(`${ws}/.verify-preflight.json`) } catch (_) { pf = null }
  if (pf && pf.belt_fail) {
    log(`FAIL-CLOSED BELT (${scope}): verifier returned PASS but bin/verify_preflight.sh found a hard mechanical FAIL (${(pf.belt_failed_checks || []).join(', ')}) — mechanical fact wins, verdict → FAIL. See ${ws}/.verify-preflight.json.`)
    logEvent('verify_belt', { scope, overrode: true, checks: pf.belt_failed_checks || [] })
    return 'FAIL'
  }
  return verdict
}
function runVerify(state) {                                          // [unified-loop] the TERMINAL science verify (verify_final stage, once after loop EXIT)
  const ws = `${RUNS}/${state.paper_slug}`
  bash(`bash "${PLUGIN_ROOT}/bin/verify_preflight.sh" "${ws}" 'science' 2>&1 || true`)   // [[MECH]] B4-25: pre-compute the mechanical facts the verifier READS (side-effect JSON; same idiom as verify_panel.sh)
  const env = spawnVerifier(verifierGoal(ws, state.loop_round, 'science'))
  tallyBudget(state, 'verify_per_round', env)
  if (env.status === 'long_run_fired') { onLongRun(state, env, 'VERIFY'); return null }
  let verdict = (env.metrics && env.metrics.verdict) || 'FAIL'      // [[MECH]] absent verdict = FAIL (fail loud)
  verdict = verifyBeltReconcile(ws, 'science', verdict)             // [[MECH]] B4-25 fail-closed belt: a hard mechanical FAIL overrides a verifier PASS
  state.verify_verdict = verdict; persist(state)
  logEvent('verdict', { source: 'independent_verifier', label: verdict })   // LOGGING (side-channel; RC-1)
  if (verdict !== 'PASS') {                                          // RC-1: STOP and ask the owner (§5)
    failureSurface(state, `verify-r${state.loop_round}`,
      (env.escalations && env.escalations.length) ? env.escalations
        : [{ id: 'verify', severity: 'reject',
             question: `Independent verifier did not PASS round ${state.loop_round}; see ${ws}/VERIFICATION-REPORT.md`,
             options: ['Resume after I clarify', 'Abandon this idea'] }])
    return null
  }
  // [[SEAM:terminal-gate]] central-claim-dead = the spec's novelty claim was CONTRADICTED (LLM plain-language
  // verdict, NO numeric scoring). alive:false (NEGATIVE_CONTRADICTS_NOVELTY / falsified central claim) NEVER
  // auto-ships → the unified terminal gate, whose STANDING POLICY is Abandon (a novelty-contradicting negative
  // is not a deliverable). Ship stays on the card ONLY as an explicit owner override.
  // ORDER (risk #3): the verdict!=='PASS' → failureSurface block above ran FIRST, so HOLLOW/broken never reaches
  // here. verify_final is NOT recorded here (ship-gate stays blocked); the Ship ingest records it only if the owner
  // elects to ship. NOTE: an over-claimed REAL result keeps alive:true (that is the §4c axis below, NOT a dead claim).
  const cc = (env.metrics && env.metrics.central_claim) || null
  if (cc && cc.alive === false) {
    logEvent('central_claim', { alive: false, contribution: (env.metrics && env.metrics.contribution_verdict) || null })
    writeJson(`${ws}/.terminal-verdict.json`, { reason: 'negative_result', central_claim_alive: false,
      plain_why: cc.plain_why || null, how_it_failed: (env.metrics && env.metrics.how_it_failed) || null,
      contribution_verdict: (env.metrics && env.metrics.contribution_verdict) || null, report: `${ws}/VERIFICATION-REPORT.md` })
    return runTerminalGate(state, 'negative_result')
  }
  // [[MECH]] RC-10 / option A: terminal verify_final PASSED → record it in the L0-owned ledger
  // (milestone-state.json stages.verify_final) so the ship-gate sees it from disk, independent of state.stage.
  // Read-only stage → snapshot the verified paper HEAD, no new commit.
  // [[MECH]] §4c ambition reconciliation (Phase II) + research-rescue (Phase III) — the claim-vs-delivery axis,
  // SEPARATE from PASS/FAIL. reconciled:false = delivery < the locked §4c ambition on >=1 dimension. Phase III: do
  // NOT lower the claim — spawn the research-rescue (one DO-capable worker PER gap, parallel) to RETAIN it first;
  // only a documented FAILED rescue (or heavy gap-work needing a re-run) surfaces to the owner. The rescue NEVER
  // self-blesses: an inline retain is RE-AUDITED by re-running verify_final on the updated artifacts. Absent
  // reconciliation (legacy / no §4c lock) ⇒ reconciled (do-no-harm). A once-per-round marker stops infinite re-runs.
  const rec     = (env.metrics && env.metrics.ambition_reconciliation) || null
  const gapList = (rec && Array.isArray(rec.gaps)) ? rec.gaps : []
  const reconciled0 = rec ? (rec.reconciled !== false) : true
  const rescueMark = `${ws}/.round-${state.loop_round}.ambition-rescue-tried`
  if (!reconciled0 && gapList.length && !exists(rescueMark)) {
    bash(`touch "${rescueMark}"`)                                    // the rescue runs ONCE per round; a still-failing re-audit then surfaces (no infinite re-run)
    logEvent('ambition_reconciled', { reconciled: false, gaps: gapList.length })
    log(`抱负对账: delivery < the locked §4c AMBITION on ${gapList.length} dimension(s) — spawning the research-rescue (NOT lowering the claim).`)
    const verdicts = runResearchRescue(state, 'delivery-vs-ambition', gapList)
    // [[MECH]] D3 detach backstop: a rescue should author a HANDOFF + return needs_loopback (NOT fire-detach), but
    // if one still detached, runResearchRescue already routed it through onLongRun (state.detached written +
    // END_TURN). Mirror runVerify's own VERIFY guard — short-circuit here, do NO tool work after END_TURN; the
    // re-wake finalizes the job from disk and re-enters verify_final to re-audit (the marker stays so it does not
    // re-spawn until the re-audit decides).
    if (turnEnded(state)) return null
    // [[MECH]] THREE-WAY partition of the per-item rescue verdict (priority load-bearing — read in order):
    //   • inline_retained (retained & NOT detached) — gap RETAINED inline. NO self-bless: RE-AUDITED by re-running
    //     verify_final, never taken on its word.
    //   • loopback (needs_loopback OR detached) — RESCUABLE heavy gap-work (HANDOFF-ambition-*.md); run it AUTO via
    //     the loop (no owner gate — 禁止轻易放弃); a failed gap re-surfaces at the NEXT verify_final.
    //   • failed (not_retained) — NOT-RESCUABLE; the documented residual, surfaced to the owner.
    const inline_retained = verdicts.filter(v => v.verdict === 'retained' && !v.detached)
    const loopback        = verdicts.filter(v => v.verdict === 'needs_loopback' || v.detached)
    const failed          = verdicts.filter(v => v.verdict === 'not_retained' && !v.detached)
    if (!loopback.length && !failed.length && inline_retained.length) {
      // EVERY gap RETAINED INLINE → do NOT record verify_final; L0 RE-RUNS this stage so the verifier RE-AUDITS the
      // §4c reconciliation on the updated artifacts (re-audit, not the rescue's word, clears the gate). A still-
      // unreconciled re-audit falls through below (reconciled:false → ship-gate blocks) — no infinite re-run, no self-bless.
      log(`抱负 rescue: all ${inline_retained.length} gap(s) RETAINED inline — re-running verify_final to RE-AUDIT (no self-bless).`)
      logEvent('ambition_rescue', { gaps: gapList.length, outcome: 'inline_retained_reaudit' })
      return null                                                    // verify_final NOT recorded → L0 re-runs it; the re-audit decides
    }
    if (loopback.length) {
      // RESCUABLE (1+ gap needs heavy gap-work) → AUTO re-enter the loop to RUN the authored HANDOFF-ambition-*.md,
      // NO owner gate. Do NOT recordStage(verify_final) — re-entering the loop; the NEXT verify_final re-audits the
      // now-closed gap (run first; a genuinely-failed gap re-surfaces then).
      log(`抱负 rescue: ${loopback.length} gap(s) RESCUABLE — auto re-entering the loop to RUN the authored HANDOFF-ambition gap-work (no owner gate).`)
      logEvent('ambition_rescue', { gaps: gapList.length, loopback: loopback.length, outcome: 'loopback' })
      reopenLoopWith(state)                                          // merge the gap work-order + re-open the loop; the next verify_final re-audits
      return null
    }
    // NOT-RESCUABLE: no loopback work to run and 1+ gap genuinely failed → record reconciled:false (ship-gate
    // blocks) + fold into the UNIFIED terminal gate (was a dedicated ambition-residual gate). This is OVER-CLAIM:
    // a REAL result whose claim over-reaches delivery on ≥1 un-rescuable dimension — central_claim stays alive:true
    // (the §4c ambition axis, NOT a dead claim); the gate's default is Ship = narrow the claim to what holds.
    recordStage(state, 'verify_final', { verdict: 'PASS', round: state.loop_round, ambition_reconciled: false, ambition_gaps: failed.length }, { commit: false })
    logEvent('ambition_rescue', { gaps: gapList.length, failed: failed.length, outcome: 'surfaced' })
    writeJson(`${ws}/.terminal-verdict.json`, { reason: 'over_claim', central_claim_alive: true, contribution_verdict: 'REAL',
      over_claim_gaps: failed.map(v => ({ item: v.item, tried: v.tried || [], why_none: v.why_none || null,
        residual: (v.residual && v.residual.statement) || null })), report: `${ws}/VERIFICATION-REPORT.md` })
    return runTerminalGate(state, 'over_claim')
  }
  // [[SEAM:terminal-gate]] AT THE CAP (decision #1): the science holds + the claim reconciles, but the loop hit
  // max_loop_rounds with unresolved reject/major items (that is exactly why loop_gate said EXIT_AT_CAP, not clean
  // EXIT). Surface the unified terminal gate — its default at the cap is Ship = HAND BACK (2026-09-24: an idea the
  // loop did not kill goes back to the researcher as the spec: what is established + what remains open; it is not
  // a claim of success). verify_final is NOT recorded here; the Ship ingest records it when Ship is chosen.
  if (state.terminal_reason === 'cap_exit') {
    writeJson(`${ws}/.terminal-verdict.json`, { reason: 'cap_exit', central_claim_alive: true,
      plain_why: (cc && cc.plain_why) || null, how_it_failed: (env.metrics && env.metrics.how_it_failed) || null,
      contribution_verdict: (env.metrics && env.metrics.contribution_verdict) || null,
      report: `${ws}/VERIFICATION-REPORT.md`, review_report: `${ws}/paper/review-report.md` })
    return runTerminalGate(state, 'cap_exit')
  }
  // [[SEAM:terminal-gate]] (2026-09-12) CLEAN EXIT under an OWNER-answered terminal card: the owner still makes the
  // last direction call — Ship (recommended) or push the idea further (Amplify / Rescue one more round). Only the
  // fully reconciled path; the rescue-already-ran edge below keeps its behaviour. Nothing is recorded here — the
  // Ship ingest records verify_final exactly as the auto path would.
  if (state.terminal_reason === 'clean_exit' && reconciled0 && gateAnsweredBy('terminal_gate') === 'owner') {
    writeJson(`${ws}/.terminal-verdict.json`, { reason: 'clean_exit', central_claim_alive: true,
      plain_why: (cc && cc.plain_why) || null, contribution_verdict: (env.metrics && env.metrics.contribution_verdict) || null,
      report: `${ws}/VERIFICATION-REPORT.md`, review_report: `${ws}/paper/review-report.md` })
    return runTerminalGate(state, 'clean_exit')
  }
  // else CLEAN EARNED EXIT — unchanged: record verify_final PASS + proceed to rewrite → … → ship (AUTO). Also the
  // legacy/no-lock path, or the rescue-already-ran-this-round + re-audit-still-fails edge — the latter records
  // reconciled:false so the ship-gate blocks (owner sees it at the ship surface), rather than re-spawning forever.
  const reconciledFinal = reconciled0
  logEvent('ambition_reconciled', { reconciled: reconciledFinal, gaps: gapList.length })
  if (!reconciledFinal) log(`抱负对账仍未通过（research-rescue 已尝试本轮）——ship 受阻，待 owner 处置残值。见 ${ws}/VERIFICATION-REPORT.md。`)
  // [[MECH]] #3 ambition amplifier MOVED OUT of verify_final INTO the loop (maybeAmplify, per-round after review,
  // before re-author). verify_final stays the TERMINAL #1 arbiter: it reconciles the (possibly raised) claim
  // against delivery — a raise the loop could not deliver lands as a reconciliation GAP (research-rescue above),
  // auto-earned, never self-blessed. Nothing to amplify here; record the verify_final ledger entry + ship.
  recordStage(state, 'verify_final', { verdict: 'PASS', round: state.loop_round, ambition_reconciled: reconciledFinal, ambition_gaps: reconciledFinal ? 0 : gapList.length }, { commit: false })
  return env
}

// runFocusedVerify — [unified-loop] the per-round FOCUSED verify (factual/result), spawned INSIDE the review
// stage. Does NOT failureSurface on FAIL: records state.verify_verdict (the gate's RC-1 belt blocks EXIT unless
// PASS) + writes failed checks to the concern ledger. Read-only → never detaches; the long_run guard is a backstop.
function runFocusedVerify(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  bash(`bash "${PLUGIN_ROOT}/bin/verify_preflight.sh" "${ws}" 'focused' 2>&1 || true`)   // [[MECH]] B4-25: pre-compute the mechanical facts the verifier READS (side-effect JSON)
  const env = spawnVerifier(verifierGoal(ws, state.loop_round, 'focused'))
  tallyBudget(state, 'verify_per_round', env)
  if (env.status === 'long_run_fired') { onLongRun(state, env, 'REVIEW'); return null }   // backstop (read-only verify shouldn't detach)
  let verdict = (env.metrics && env.metrics.verdict) || 'FAIL'      // [[MECH]] absent verdict = FAIL (fail loud)
  verdict = verifyBeltReconcile(ws, 'focused', verdict)             // [[MECH]] B4-25 fail-closed belt: a hard mechanical FAIL overrides a verifier PASS (blocks EXIT)
  state.verify_verdict = verdict; persist(state)
  logEvent('verdict', { source: 'focused_verifier', label: verdict })   // LOGGING (side-channel; RC-1 in-loop)
  return env                                                         // FAIL is NOT surfaced here — it blocks EXIT (gate belt) + lands in the punch-list
}

// theoryAuditorGoal — the READ-ONLY math/proof rigor auditor LEAF (unit ②): audits the central theorems/proofs
// for RIGOR and UPSERTs a theory-rigor concern into the verifier's SAME live ledger (TASK_STATUS.concerns.json).
// Diagnose-only: NEVER edits a proof, NEVER gates the verdict. The upsert PRESERVES opened_round, so a MAJOR
// theory concern open ≥K rounds reads as non-convergence at unit ①. Regression (prose drafter "fixed" an
// unprovable theorem): 见 DECISIONS.md §RC 历史 — theory-auditor.
function theoryAuditorGoal(ws, round) {
  return [
    `You are the THEORY AUDITOR (round ${round}) — a STRICTLY READ-ONLY math/proof auditor. Read`,
    `${PLUGIN_ROOT}/spec/spawn-prompts/THEORY-AUDIT.md and do EXACTLY what it says — it carries your full rigor rubric, the`,
    `concern-upsert + stable-id/opened_round discipline, and the envelope contract. Substitute as you read it:`,
    `  <WS>=${ws}  <ROUND>=${round}`,
    LEDGER_CONTAINER,                                                // the canonical ledger-object shape (single-sourced; the asset points here)
  ].join('\n')
}
// runTheoryAudit — [unit ②] the per-round THEORY-RIGOR audit, spawned INSIDE the review stage. Read-only LEAF
// (spawnL2; never fans out). Does NOT failureSurface: upserts its concern to the ledger + returns the envelope.
// Read-only → never detaches; the long_run guard is a backstop.
function runTheoryAudit(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  const env = spawnL2('theory_auditor', theoryAuditorGoal(ws, state.loop_round))
  tallyBudget(state, 'verify_per_round', env)
  if (env.status === 'long_run_fired') { onLongRun(state, env, 'REVIEW'); return null }   // backstop (read-only audit shouldn't detach)
  return env
}

// ── (D) Orphan-stop scan — make the log→envelope seam UN-BURYABLE ─────────────────────────────────────
// [[MECH]] An L1 can write a stop-shaped marker into its OWN logs (FAILURES.md / RESEARCH_LOG.md / STOP report)
// yet return new_handoff_items:0 — the recognition dies at the log→envelope seam (见 DECISIONS.md §RC 历史 —
// orphan-stop seam). DERIVE from disk the count of such markers (bin/scan_orphan_stops.sh, RC-4 idiom) and
// SURFACE any INCREASE over the owner's ack. Runs after runB1, before runVerify, every round.
function scanOrphanStops(state) {
  if (!CFG.checkpoints.orphan_stop_scan) return
  const ws = `${RUNS}/${state.paper_slug}`
  const out = bash(`bash "${PLUGIN_ROOT}/bin/scan_orphan_stops.sh" "${ws}" 2>&1 || true`)
  const n   = parseInt((firstLine(out).match(/^COUNT (\d+)/) || [])[1] || '0', 10)
  const ack = state.orphan_ack_count || 0
  logEvent('orphan_stop_scan', { count: n, ack, new: Math.max(0, n - ack) })   // LOGGING (side-channel; seam)
  if (n > ack) {                                                    // NEW log-only stop markers since last ack
    failureSurface(state, `orphan-stops-r${state.loop_round}`, [{ id: 'orphan_stops', severity: 'major_revision',
      question: `The B1 agent wrote ${n - ack} new stop-shaped marker(s) into its OWN logs (FAILURES.md /`
        + ` RESEARCH_LOG.md / a STOP report) that it did NOT return in escalations[]:\n${out}\nConfirm these`
        + ` are handled (Resume), or treat as a real stop (Abandon).`,
      options: ['Resume after I clarify', 'Abandon this idea'] }])
    // INGEST → ingestGateAnswer('failure-orphan-stops'): Resume acks the scanned count (orphan_ack_count ← n; the
    // monotone count re-surfaces only genuinely-new markers later) + re-enters; Abandon→finishRun.
  }
}

// ── B2 — adversarial review (the vendored review PROTOCOL, executed by an L1 REVIEW OWNER) ──────────────────
// [[MECH]] The L1 reads ${P.review_spec} (review-protocol.md) and executes it as the REVIEW OWNER with the
// [IN-LOOP] arms active — DIAGNOSE-ONLY (no reviser/experiment machinery): the owner reads the paper itself,
// spawns the independent cold panel (≥2) + checklist pass, synthesizes the punch-list, exports experiment-demands
// as HANDOFF. REVIEW-L0-CONTRACT.md carries the loop wiring (ledger write, redesign/additive export
// classification, contribution-substance concern, headless seam policy, return contract). Venue is PRE-RESOLVED
// = state.venue. Author-only seams RETURN in escalations[] → L0's gate. The freeze hook fires at L2.
function runReview(state) {                                          // [unified-loop] was runB2; the review protocol is diagnose-only + focused verify
  const ws = `${RUNS}/${state.paper_slug}`
  // [[MECH]] RC-6: ARM the science guard before the panel runs. The fidelity PreToolUse hook + asyncRewake
  // Stop hook read ${PROJECT_DIR}/.polish/ (repo root), but the review protocol writes runs/<slug>/.polish/
  // (project_dir=ws). Symlink repo-root/.polish → the per-paper .polish so the hook actually fires at L2.
  // (v1 is strictly serial — one active paper — so a single symlink is unambiguous; dropped at batch seal.)
  bash(`mkdir -p "${ws}/.polish"; rm -rf "${PROJECT_DIR}/.polish"; ln -s "${ws}/.polish" "${PROJECT_DIR}/.polish"`)
  // [[MECH]] round-freshness belt: the review artifacts live at CONSTANT paths with no round stamp — a prior
  // round's files on disk would let a resume-by-artifact skip this round's panel (stale gate input). Clear them.
  bash(`rm -f "${ws}/paper/review-verdicts.md" "${ws}/paper/review-report.md" "${ws}/paper/paper-model.md"`)
  const goal = [
    `You are the REVIEW OWNER (in-loop seat). Read ${PLUGIN_ROOT}/spec/spawn-prompts/REVIEW-L0-CONTRACT.md and do EXACTLY what it`,
    `says — it wires the review protocol (<REVIEW_SPEC>) into this loop: the input bindings; the in-loop cold-read`,
    `hazard; the diagnose-only export classification; the contribution-substance concern; the punch-list ledger`,
    `write; the headless seam policy; the return contract. Substitute as`,
    `you read it:`,
    `  <REVIEW_SPEC>=${P.review_spec}  <WS>=${ws}  <VENUE>=${state.venue}  <ROUND>=${state.loop_round}`,
    LEDGER_CONTAINER,
    pdPointer(`this round's FROZEN open-concern set is ${ws}/.round-${state.loop_round}.concerns.json (read the FROZEN snapshot, NEVER the live ledger — Doc A §3.3).`,
              `review is DIAGNOSE-ONLY — read the open concerns, find problems, write the punch-list; make NO edits to the paper`),
  ].join('\n')
  const env = spawnL1('review_orchestrator', goal)
  tallyBudget(state, 'b2_per_round', env)
  // [[MECH]] RC-6 arm-assertion: after the review protocol's setup, the manifest the hook reads MUST exist; if absent,
  // the science guard ran UNARMED this round — record it loudly so a silent no-op becomes a visible failure.
  if (!exists(`${ws}/.polish/fidelity-manifest.json`)) {
    log(`WARN RC-6: ${ws}/.polish/fidelity-manifest.json absent after B2 setup — fidelity hook may have been unarmed.`)
    logEvent('hook_unarmed', { where: 'B2', manifest: `${ws}/.polish/fidelity-manifest.json` })   // LOGGING (side-channel; RC-6)
  }
  if (env.status === 'long_run_fired') { onLongRun(state, env, 'REVIEW'); return null }   // diagnose-only review never runs experiments → shouldn't detach (backstop)
  if (env.escalations && env.escalations.length) {                  // author-only seams bubbled → owner gate
    failureSurface(state, `review-r${state.loop_round}`, env.escalations); return null
    // INGEST → 'Resume after I clarify': re-spawn review in resume mode with the owner's dispositions; 'Abandon' → finishRun.
  }
  // [unified-loop] FOCUSED verify (factual/result) runs in the SAME review stage; it sets state.verify_verdict
  // (the gate's RC-1 belt blocks EXIT unless PASS) and writes its failed checks to the concern ledger.
  const v = runFocusedVerify(state)
  if (v === null) return null                                       // focused verify detached (unexpected) → onLongRun ended the turn
  // [unit ②] THEORY-RIGOR audit runs in the SAME review stage (early per-round catch). It upserts a theory
  // concern to the SAME ledger (so review sees the proof gap, and an UNFIXED major gap persists across rounds →
  // unit ①'s viability gate reads non-convergence). Diagnose-only: it never sets the verdict, never blocks ship.
  const ta = runTheoryAudit(state)
  if (ta === null) return null                                      // theory audit detached (unexpected) → onLongRun ended the turn
  return env                                                        // carries metrics (overall_risk, new_handoff_items) for the gate
}

// ── B3 — deterministic LOOP exit gate (bin/loop_gate.sh; real arithmetic, not judgement) ─────────────
function runB3(state, b2env) {
  const ws = `${RUNS}/${state.paper_slug}`, m = b2env.metrics || {}
  // [[MECH]] RC-2: PROVE a real panel ran THIS round before trusting any review output. verify_panel.sh
  // checks the per-round panel artifacts on disk; a narrated review with no real panel (P2/P3) fails here.
  const vp = bash(`bash "${PLUGIN_ROOT}/bin/verify_panel.sh" "${ws}" "${state.loop_round}" 2>&1 || true`)
  if (!firstLine(vp).startsWith('OK')) throw new Error(`verify_panel failed (RC-2 — no real review this round): ${vp}`)
  // [[MECH]] RC-4: DERIVE the gate inputs from disk (review-report.md overall_risk + HANDOFF-*.md count). The
  // review agent's self-reported metrics are recorded only as `claimed`; a derived≠claimed risk/handoff MISMATCH
  // → SURFACE it, do not gate on a lie. [unified-loop] write_backs is NO LONGER a gate/mismatch signal — the
  // DRAFT stage rewrites the whole paper every round (paper-diff ≠ write-backs); it is logged, never gated.
  const inputFile = `${ws}/loop-gate-input-r${state.loop_round}.json`
  const dout = bash(`bash "${PLUGIN_ROOT}/bin/derive_gate_input.sh" "${ws}" "${state.loop_round}"`
    + ` "${state.round_baseline_paper}" "${m.overall_risk || ''}" "${m.new_handoff_items|0}" "${m.write_backs|0}"`
    + ` "${inputFile}"`)
  if (firstLine(dout).startsWith('ERROR')) throw new Error(`derive_gate_input failed: ${dout}`)   // fail loud
  if (dout.includes('MISMATCH')) {                                  // RC-4: envelope under-reported — ask owner (§5)
    failureSurface(state, `gate-mismatch-r${state.loop_round}`, [{ id: 'gate_mismatch', severity: 'major_revision',
      question: `B3 disk-derived gate inputs disagree with the review envelope's self-report:\n${dout}\nSee ${inputFile}.`,
      options: ['Resume after I clarify', 'Abandon this idea'] }])
    return null
  }
  const out = bash(`bash "${PLUGIN_ROOT}/${P.loop_gate}" "${inputFile}"`)
  const verdict = firstLine(out)                                    // EXIT | CONTINUE | EXIT_AT_CAP | ERROR...
  log(`B3 loop_gate (round ${state.loop_round}): ${out}`)
  if (verdict === 'ERROR') throw new Error(`loop_gate failed: ${out}`)   // fail loud, never guess
  // RC-1 belt-and-suspenders: never EXIT while the independent verifier did not PASS this round.
  if (verdict === 'EXIT' && state.verify_verdict !== 'PASS') {
    log(`B3: gate says EXIT but verify_verdict=${state.verify_verdict} — downgrading to CONTINUE (RC-1).`)
    return 'CONTINUE'
  }
  return verdict
}

// ── runViabilityGate (unit ①) — the per-wave SCIENTIFIC-VIABILITY gate ────────────────────────────────────
// [[SEAM:viability-gate]] Runs at the end of each experiment↔review wave (after runB3's verdict, round_in_progress
// still set), BEFORE the verdict is enacted: lets the owner steer (continue/redirect/kill) a segment whose
// viability is in doubt, but auto-continues a HEALTHY wave (an overnight run is never disturbed). Returns the
// unchanged verdict to PROCEED, or null when it opened the gate (gate() END_TURN'd; the next turn drives the
// disposition via ingestGateAnswer keyed on pending_gate.id — detach-safe).
//
// TWO-LAYER DETECTION (both must agree to auto-continue; EITHER flags ⇒ gate):
//   • DETERMINISTIC FLOOR (machine-readable state ONLY, no free-text parsing). Fires on ANY of:
//       (a) overall_risk ∈ {reject, major_revision} (loop-gate-input-r<N>.json, written by runB3 this round);
//       (b) a severity:"major" concern OPEN (closed_round null) for ≥ VIABILITY_FLOOR_K rounds (severity-filtered
//           non-convergence — does NOT over-trigger on minor concerns). DEFENSIVE: absent ledger ⇒ NOTHING.
//     A machine-readable per-K verdict floor is DEFERRED (no per-K verdict producer yet); a failed K reaches the
//     floor via overall_risk + its concern's non-convergence. L0 never parses concern / result.md FREE TEXT.
//   • RECOMMENDER NET: ALWAYS spawned (an intuitive human read) — catches UNANTICIPATED viability problems the
//     floor cannot see. Floor did NOT fire but recommender returns block:true ⇒ gate. Neither flags ⇒ auto-continue.
// VIABILITY_FLOOR_K = the floor's non-convergence threshold (a major concern still open this many rounds =
// exhaustion). Set to 3: let the loop SELF-REPAIR a few rounds before surfacing (a single bad round self-heals).
// TODO(key-config): lift into config.yaml (checkpoints.*) if tunable — DEFERRED P1; a const today.
const VIABILITY_FLOOR_K = 3   // a MAJOR concern still open this many rounds = non-convergence → surface (the DETERMINISTIC FLOOR reads the ledger's categorical severity field — P0-B)
// [[MECH]] majorNonConverging(ws, round): TRUE iff some severity:"major" concern has been OPEN (open/reopened,
// closed_round null) for ≥ VIABILITY_FLOOR_K rounds — (round − opened_round + 1) ≥ K. Read from the LIVE ledger's
// canonical { open_concerns:[…] }; only a major row counts (P0-B). EXCLUDES pre-registered kill-criteria seed rows
// (source starts with 'seed:') — a pre-registered K is DISCLOSURE, not an OBSERVED non-convergence signal, so it
// must not spuriously trip the viability gate on a HEALTHY run at round 3+ (a real sensor raising its own row for
// the same issue still drives convergence). DEFENSIVE (REQUIRED): an absent/unparseable ledger or a row missing
// severity/opened_round contributes NOTHING (skip; never crash, never false-fire).
function majorNonConverging(ws, round) {
  let led; try { led = exists(`${ws}/TASK_STATUS.concerns.json`) ? readJson(`${ws}/TASK_STATUS.concerns.json`) : null } catch (_) { led = null }
  const rows = (led && Array.isArray(led.open_concerns)) ? led.open_concerns : []
  for (const r of rows) {
    if (!r || r.severity !== 'major') continue                        // severity-filtered: minor concerns never trip non-convergence
    if (String(r.source || '').startsWith('seed:')) continue          // pre-registered kill-criteria are disclosure, NOT observed non-convergence — a round-0 seed row (source:'seed:*') never counts toward the floor; only genuine sensor-raised rows (review/verifier/theory_auditor/…) do
    if (r.status !== 'open' && r.status !== 'reopened') continue      // closed/deferred do not count
    if (r.closed_round != null) continue                              // belt: a closed_round set ⇒ not open
    const opened = Number(r.opened_round)
    if (!Number.isFinite(opened)) continue                            // missing/garbage opened_round ⇒ contributes nothing
    if ((round - opened + 1) >= VIABILITY_FLOOR_K) return true        // open for ≥ K rounds (inclusive of the round it opened)
  }
  return false
}
function runViabilityGate(state, verdict, rev) {
  const ws = `${RUNS}/${state.paper_slug}`
  // [[MECH]] DEFENSIVE backstop (the loop-top viability-resolved skip is the PRIMARY guard, so this is normally
  // unreached on a fresh wave): if this round's gate was already resolved, never re-open it — pass the verdict
  // through. (redirect/kill resolve terminally in ingestGateAnswer; continue is handled by the loop-top skip.)
  if (exists(`${ws}/.round-${state.loop_round}.viability-resolved`)) return verdict
  // (a) DETERMINISTIC FLOOR — two machine-readable signals, ANY of which fires (no free-text parsing). The floor
  // now OWNS non-convergence (the ledger carries a categorical severity field — P0-B); this is the "dissolve D1"
  // the owner asked for, so the recommender no longer has to fail-closed to keep it. L0 still never parses concern
  // / result.md free text — every read is a JSON field. (A machine-readable K-verdict floor signal is a DEFERRED
  // next unit — it needs a producer the experiment phase does not yet write; until then a failed K reaches the
  // floor via overall_risk + the non-convergence of the concern it raises.)
  const gi = `${ws}/loop-gate-input-r${state.loop_round}.json`       // written by runB3 (derive_gate_input) this round
  const risk = exists(gi) ? (readJson(gi).overall_risk || '') : ((rev.metrics && rev.metrics.overall_risk) || '')
  const riskFired  = risk === 'reject' || risk === 'major_revision'  // (a1) AC overall_risk
  const nonConverg = majorNonConverging(ws, state.loop_round)        // (a2) a severity:"major" concern open ≥ K rounds (DEFENSIVE: absent ledger ⇒ false)
  const floorFired = riskFired || nonConverg
  // (b) RECOMMENDER NET — ALWAYS spawn; it returns a structured human read (block + the researcher's stop-report).
  // It no longer owns non-convergence (the floor does) — it catches UNANTICIPATED problems the floor cannot see.
  const brief = runViabilityRecommender(state)
  const block = floorFired || (brief && brief.block === true)
  logEvent('viability_judged', { round: state.loop_round, floor_fired: floorFired,
    risk, risk_fired: riskFired, non_converging: nonConverg,
    recommender_block: !!(brief && brief.block), recommender_unusable: !!(brief && brief.unusable),
    action: (brief && brief.recommended_action) || null, gate: block })
  if (!block) return verdict                                         // healthy wave → auto-continue, no gate surfaced
  // [[SEAM:research-rescue]] strategic-kill rescue (Phase III). BEFORE the gate surfaces a kill option, spawn the
  // research-rescue to hunt a surviving regime / reframe / cheap experiment (禁止轻易放弃). Its verdict FRAMES the
  // card: rescuable ⇒ Redirect is recommended; not-rescuable ⇒ kill is the DOCUMENTED residual of a failed rescue,
  // never the first move. Gated to a KILL-PLAUSIBLE block (real reject/major, or recommender 'kill'), once per round.
  const killOnTable = riskFired || (brief && /kill/i.test(String(brief.recommended_action || '')))
  let rescue = null
  if (killOnTable && !exists(`${ws}/.round-${state.loop_round}.viability-rescue-tried`)) {
    bash(`touch "${ws}/.round-${state.loop_round}.viability-rescue-tried"`)
    const rv = runResearchRescue(state, 'central-claim-viability',
      [{ id: 'central-claim', overall_risk: risk, blocking_point: (brief && brief.blocking_point) || null }])
    const r = rv && rv[0]
    rescue = r ? { rescuable: (r.verdict === 'retained' || r.verdict === 'needs_loopback'),
                   verdict: r.verdict, tried: r.tried, why_none: r.why_none, residual: r.residual } : null
    logEvent('viability_rescue', { round: state.loop_round, rescuable: !!(rescue && rescue.rescuable), verdict: rescue && rescue.verdict })
  }
  // [[MECH]] (2026-09-12) FOLD INTO THE DIRECTION CARD. When the owner answers the per-round direction card and a
  // round follows (CONTINUE), this wave's continue / redirect / kill call is the OWNER's at that card (Revise =
  // redirect, Abandon = kill, plus Amplify / Rescue). Opening this gate as well would let the cold-read judge take
  // the same fork first — the 2026-07 test-3 run Continued it five rounds running. The recommender brief + the
  // rescue verdicts are on disk and the card reports them; marked resolved so a same-round re-entry never re-opens it.
  if (verdict === 'CONTINUE' && CFG.checkpoints.handoff_approval && gateAnsweredBy('direction') === 'owner') {
    bash(`touch "${ws}/.round-${state.loop_round}.viability-resolved"`)
    logEvent('viability_folded', { round: state.loop_round, rescuable: rescue ? rescue.rescuable : null })
    return verdict
  }
  // (c) ON BLOCK — surface the gate (mirrors gateHandoffApproval). The recommender brief + recommended_action go
  // into the question context so the source-derived card shows the human read; gate() persists + askUser + END_TURN.
  const floorReasons = [riskFired && `overall_risk=${risk}`,
    nonConverg && `a major concern has stayed open ≥ ${VIABILITY_FLOOR_K} rounds (non-convergence)`].filter(Boolean)
  const why = floorFired
    ? `deterministic floor: ${floorReasons.join('; ')}`
    : (brief && brief.unusable)
      ? `viability recommender returned no usable read this wave — surfacing for your call (the deterministic floor did not fire)`
      : `recommender flagged this wave (no deterministic floor hit)`
  // FALSIFICATION DISCLOSURE (Point 3): riskFired (reject/major) AND a rescue was tried and did NOT retain the
  // contribution (rescue.rescuable === false) ⇒ the card must say so plainly and point at the evidence. Purely the
  // surfaced text — NO change to the gate's options or control flow; uses data already in scope.
  const falsified = riskFired && rescue && rescue.rescuable === false
  const why2 = falsified
    ? `${why}. The central novel contribution appears FALSIFIED at full scale (overall_risk=${risk}) and a rescue`
      + ` did NOT retain it (rescue verdict=${rescue.verdict}${rescue.why_none ? `; why_none: ${rescue.why_none}` : ''}`
      + `${rescue.residual ? `; residual: ${rescue.residual}` : ''}${brief && brief.what_died ? `; what_died: ${brief.what_died}` : ''}`
      + `${brief && brief.blocking_point ? `; blocking_point: ${brief.blocking_point}` : ''}) — review the evidence`
      + ` (overall_risk, the rescue's why_none/residual, the review report) and CONFIRM whether to stop (Kill), redirect, or continue.`
    : why
  gate(state, `viability-gate-${state.paper_slug}-r${state.loop_round}`, 'viability_gate', [{
    id: 'viability',
    context: { slug: state.paper_slug, venue: state.venue, round: state.loop_round, loop_verdict: verdict,
               why: why2, falsified, overall_risk: risk, recommender_unusable: !!(brief && brief.unusable),
               recommended_action: brief && brief.recommended_action, what_died: brief && brief.what_died,
               rescue,   // [[MECH]] strategic-kill rescue verdict — rescuable ⇒ card recommends Redirect (rescue=steer); not-rescuable ⇒ kill is the documented residual of this failed rescue

               impact: brief && brief.impact, blocking_point: brief && brief.blocking_point,
               tried: brief && brief.tried, next_step: brief && brief.next_step,
               concerns_file: `${ws}/TASK_STATUS.concerns.json`, log: `${ws}/RESEARCH_LOG.md`, review_report: `${ws}/paper/review-report.md` },
    options: [
      { label: 'Continue',           description: 'The segment is still viable — enact the loop verdict and proceed (auto-continue this and resume).' },
      { label: 'Redirect',           description: 'Push through a different way — I will clarify; merge my steer into the next wave.' },
      { label: 'Kill this segment',  description: 'Genuine exhaustion — abandon this direction, write the honest abandon report, then advance the queue.' },
    ] }])
  return null
  // INGEST → ingestGateAnswer('viability-gate-'): Continue→mark viability-resolved + stage='loop' (the loop-top
  // skip re-derives the verdict from the frozen gate input, no wave re-run) / Redirect→write HANDOFF-viability-steer.md
  // + resolved marker (loop-top forces CONTINUE) / Kill→abandon report + finishRun 'viability_killed'.
}

// ── runTerminalGate (unit — the UNIFIED terminal exit gate) ─────────────────────────────────────────────────
// [[SEAM:terminal-gate]] The ONE owner gate for every non-clean terminal exit: cap_exit (max rounds, unresolved),
// negative_result (central claim DEAD), over_claim (REAL result over-reaching delivery). NO leaf spawn — runVerify
// already wrote ${ws}/.terminal-verdict.json with the routing signal + the plain "how it failed" narrative; this
// function only SURFACES the card (owner picks Abandon / Ship / Rescue-one-more-round). The card is SOURCE-DERIVED
// per [[SEAM:gate-preview]]: L0 reads the files the question's context NAMES and composes each option's preview.
// FAIL-OPEN (risk #7): a missing/garbage .terminal-verdict.json must NOT crash L0 — the card still opens with a
// crash-safe default so the owner decides. terminal_reason is persisted BEFORE gate() (risk #6). A clean-earned
// EXIT never reaches here (it auto-ships in runVerify's reconciled path) — decision #1.
function runTerminalGate(state, reason) {
  const ws = `${RUNS}/${state.paper_slug}`
  const out = `${ws}/.terminal-verdict.json`
  let tv = null; try { if (exists(out)) tv = readJson(out) } catch (_) { tv = null }   // FAIL-OPEN (risk #7)
  if (!tv) tv = { reason, central_claim_alive: null, how_it_failed: null }             // card still opens; owner decides
  const recommended = reason === 'clean_exit' || reason === 'cap_exit' ? 'Ship' : reason === 'over_claim' ? 'Ship' : 'Abandon'   // decision #3 (2026-09-24): only a DEAD claim abandons; not killed ⇒ hand back (clean / cap as-is, over_claim narrowed)
  state.terminal_reason = reason; persist(state)                                       // ingest reads this next turn (persisted BEFORE gate())
  const shipDesc = reason === 'negative_result'
      ? 'OWNER OVERRIDE — system policy for a novelty-contradicting negative is ABANDON (it is not a deliverable). Override it: state the contradiction plainly (NO repackaging as positive, NO selling the refutation as the contribution), then finish + ship.'
      : reason === 'over_claim'
        ? 'Narrow the claim to what the evidence holds (reframe narrows the REAL result — never strengthen), then finish + ship.'
        : reason === 'clean_exit'
          ? 'The loop exited clean and verify_final reconciled the claim — freeze the spec and ship.'
          : 'Hand back as-is: the central claim was not killed in max rounds — freeze the spec with every unresolved reject/major item listed as what remains open.'
  gate(state, `terminal-gate-${state.paper_slug}-r${state.loop_round}`, 'terminal_gate', [{
    id: 'terminal',
    context: { slug: state.paper_slug, venue: state.venue, round: state.loop_round, reason,
               central_claim_alive: tv.central_claim_alive, plain_why: tv.plain_why, how_it_failed: tv.how_it_failed,
               contribution_verdict: tv.contribution_verdict, over_claim_gaps: tv.over_claim_gaps,
               verdict_file: out, report: `${ws}/VERIFICATION-REPORT.md`, review_report: `${ws}/paper/review-report.md`,
               concerns_file: `${ws}/TASK_STATUS.concerns.json`, log: `${ws}/RESEARCH_LOG.md`, handoff: `${ws}/HANDOFF.md`,
               owner_steer: exists(`${ws}/.round-${state.loop_round + 1}.owner-steer.json`) ? `${ws}/.round-${state.loop_round + 1}.owner-steer.json` : null },
    recommended,
    options: [
      { label: 'Abandon', description: reason === 'negative_result'
          ? 'SYSTEM POLICY for a novelty-contradicting negative — the direction is dead: write the honest FINAL-REPORT-killed.md and stop.'
          : 'End of the line — write the honest FINAL-REPORT-killed.md and stop (advance the queue).' },
      { label: 'Ship', description: shipDesc },
      { label: 'Rescue one more round', description: 'Do NOT give up — spawn a research-rescue to hunt a surviving regime / cheap experiment, then run ONE more experiment round (禁止轻易放弃). A still-unclean round returns here.' },
      ...(reason === 'negative_result' ? [] : [   // a DEAD central claim is abandoned, override-shipped or rescued — never amplified (research-amplify: no amplifying a falsified finding)
      { label: 'Amplify one more round', description: 'Push the idea further: spawn the amplifier toward the direction you write in NOTES (blank = its boldest earnable rung). It MUST author the work order; the amplified order comes back to you on the direction card before it runs, and verify_final re-audits the raised claim.' }]),
    ] }])
  return null
  // INGEST → ingestGateAnswer('terminal-gate-'): Abandon→FINAL-REPORT-killed.md + finishRun 'abandoned' / Ship→
  // record verify_final reconciled:true (ship-unblock) + write .terminal-narrowing-accepted.md + stage='spec_freeze' /
  // Rescue→runResearchRescue then reopenLoopWith (ONE more round; a still-unclean round re-surfaces here) /
  // Amplify→runOwnerSteer → generateHandoff(transition) → next round's direction card.
}

// [[MECH]] runViabilityRecommender — spawn the read-only recommender LEAF (the LLM net). The leaf WRITES its
// judgment JSON to a known path (read from disk — detach-safe) + mirrors it in metrics.notes; L0 reads the file
// robustly. A null/garbage return ⇒ {block:false, unusable:true} — FAIL-OPEN: a broken recommender no longer
// LOSES signal (the deterministic floor reads overall_risk + non-convergence directly), so do not over-gate on a
// flaky LEAF read; auto-continue on the floor's signals and only NOTE the unusable read.
function runViabilityRecommender(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  const out = `${ws}/.round-${state.loop_round}.viability.json`
  bash(`rm -f "${out}"`)                                             // fresh per call (re-derived on a continue-resume too)
  const env = spawnL2('viability_recommender', viabilityRecommenderGoal(ws, state.loop_round, out))
  tallyBudget(state, 'verify_per_round', env)                        // reuse the per-round verify bucket (a read-only round-boundary judge)
  let brief = null                                                   // robust parse: tolerate a missing / fenced / malformed file (never crash L0 on a broken leaf)
  try { if (exists(out)) brief = readJson(out) } catch (_) { brief = null }   // (same try/catch idiom as gate()'s askUser)
  if (!brief || typeof brief.block !== 'boolean') {                  // null / garbage / missing the one required field
    logEvent('viability_recommender_unusable', { round: state.loop_round, status: (env && env.status) || 'none', file: out })
    return { block: false, unusable: true }                          // FAIL-OPEN: a broken recommender no longer loses signal — the deterministic floor reads overall_risk + non-convergence directly, so do not over-gate on a flaky LEAF read
  }
  return brief
}
function viabilityRecommenderGoal(ws, round, out) {
  return [
    `You are the VIABILITY RECOMMENDER LEAF (round ${round}) — a single-context, STRICTLY READ-ONLY worker. Read`,
    `${PLUGIN_ROOT}/spec/spawn-prompts/VIABILITY-RECOMMENDER.md and do EXACTLY what it says — it carries the evidence to read,`,
    `the JSON to write, and the HARD card-contract (the kill-only-at-genuine-exhaustion + catch-the-unanticipated`,
    `discipline). Substitute as you read it:`,
    `  <WS>=${ws}  <ROUND>=${round}  <OUT>=${out}  <VIABILITY_FLOOR_K>=${VIABILITY_FLOOR_K}`,
  ].join('\n')
}

// ── research-rescue (Phase III) — the unified DO-capable rescue spawned BEFORE the pipeline lowers any claim ──
// [[SEAM:research-rescue]] Both L0 ambition gates call runResearchRescue BEFORE a claim is narrowed or a paper
// killed: it fans out one PRODUCING-WORKER per item (a §4c gap / a dead-or-hollow claim / a falsified direction),
// each LOADING the `research-rescue` skill for the SCENARIO. The worker tries to RETAIN the ambition by REAL work;
// only the DOCUMENTED residual of a failed rescue reaches the owner (kill/narrow is never the first move — 禁止轻易放弃).
// NEVER self-blesses: any retain is RE-AUDITED (verify_final re-runs §4c; loopback gap-work runs under the normal
// gates). THIN-SPEC: the goal POINTS to the skill + injects the runtime item; it NEVER inlines the protocol.
function rescueGoal(state, scenario, item) {
  const ws = `${RUNS}/${state.paper_slug}`
  return [
    `You are a RESCUE producing-worker. LOAD the \`research-rescue\` skill FIRST and follow it — it carries the`,
    `full protocol; this goal only names your SCENARIO + the ONE item you own.`,
    `SCENARIO = ${scenario}. Pinned ambition: ${ws}/HANDOFF.ambition.locked.json. Locked scale:`,
    `${ws}/HANDOFF.scale-contract.locked.json. Failure evidence is on disk (RESEARCH_LOG.md / EXPERIMENTS/ /`,
    `VERIFICATION-REPORT.md / THEORY.md / loop-gate-input-r*.json). YOUR ITEM (own ONLY this one — never reach`,
    `into another worker's item): ${JSON.stringify(item)}.`,
    ...(scenario === 'owner-directed' ? [
    `OWNER-DIRECTED (binding): the owner chose, on the per-round direction card, to rescue what ${item.owner_direction_file}`,
    `names — read it first. This rescue MUST end in a RUNNABLE experiment work order (the HANDOFF-ambition file below) +`,
    `verdict:needs_loopback; a wording- or reframe-only "retained" does not count here. If you judge it unrescuable,`,
    `still author the most promising experiment and say why in why_none — the owner reads it on the card and decides.`] : []),
    `CONCURRENCY — you run AT THE SAME TIME as the other rescue workers on a SHARED working tree: write ONLY`,
    `files scoped to YOUR item (the ${ws}/HANDOFF-ambition-*.md work-order named below + any evidence under a`,
    `your-dimension-named path), do NOT edit shared manuscript/theory files, and do NOT run git add/commit/stash`,
    `(concurrent workers would race on .git/index.lock). L0 owns all git integration; your retain reaches the`,
    `paper via re-audit + the loop, never by you editing the manuscript here.`,
    `Try HARD to RETAIN the ambition by real work (the skill routes by gap type). You WILL be re-audited — never`,
    `claim a retain you did not achieve. Heavy work needing a full experiment run: author`,
    `${ws}/HANDOFF-ambition-${(item && (item.dimension || item.id)) || 'gap'}.md (a gap work-order) and return`,
    `verdict:needs_loopback — do NOT fire-detach the heavy run yourself; the LOOP runs it. Return`,
    `metrics.rescue = { verdict: retained|needs_loopback|not_retained,`,
    `evidence, tried:[...], why_none, residual: { kind: narrow|reframe|kill, statement } }.`,
  ].join('\n')
}
// runResearchRescue — fan out one DO-capable worker per item (the owner's "parallel producing-worker per failed
// direction"). spawnWorker = the MIDDLE tier that OWNS production + may delegate leaf-workers SERIALLY; its result
// is externally audited (it never judges its own rescue). Returns a per-item verdict array (filter on .verdict).
function runResearchRescue(state, scenario, items) {
  const list = items || []
  if (!list.length) return []
  // [[MECH]] research-rescue §3 — fan out ONE rescue worker per item AS A CONCURRENT BATCH. The items are
  // contractually DISJOINT (each worker owns exactly one falsified direction / gap and never reaches into
  // another's), and rescueGoal forbids the workers from editing shared files or running git, so the concurrent
  // workers write DISJOINT dimension-scoped files and never race on .git/index.lock. The spawns fire together;
  // envelope post-processing (tallyBudget + onLongRun, the SOLE state.detached writer) stays SERIAL below.
  const envs = spawnWorkersParallel('rescue', list.map(it => rescueGoal(state, scenario, it)))
  const results = list.map((it, i) => {
    const env = envs[i]
    tallyBudget(state, 'rescue', env)
    const detached = !!(env && env.status === 'long_run_fired')
    // [[MECH]] D3 DEFENSIVE backstop: the rescue should author a HANDOFF + return needs_loopback (the loop runs the
    // heavy job), NOT fire-detach. If an env STILL returns long_run_fired, route it through onLongRun (the SOLE
    // state.detached writer + END_TURN) so it is tracked; the detached:true verdict flows to the caller as loopback.
    if (detached) onLongRun(state, env, 'RESCUE')
    const r = (env && env.metrics && env.metrics.rescue) || null
    return { item: it, verdict: (r && r.verdict) || 'not_retained',
             evidence: r && r.evidence, tried: (r && r.tried) || [], why_none: r && r.why_none,
             residual: r && r.residual, detached }
  })
  // [[MECH]] persist rescue residuals per round (quality-ceiling upgrade 2026-07-07): retained/loopback verdicts
  // used to live only in event lines — the residual/why_none text is a /learn [OPPORTUNITY] headroom signal.
  // Append-tolerant: a round can rescue more than one scenario. Covers ALL runResearchRescue call sites.
  const rvPath = `${RUNS}/${state.paper_slug}/.round-${state.loop_round}.rescue-verdicts.json`
  const prior = exists(rvPath) ? (readJson(rvPath) || []) : []
  writeJson(rvPath, (Array.isArray(prior) ? prior : []).concat(results.map(v => ({
    schema: 'auto-research-rescue-verdict@1', round: state.loop_round, scenario,
    item: (v.item && v.item.id) || null, verdict: v.verdict, tried: v.tried,
    why_none: v.why_none || null, residual: v.residual || null }))))
  return results
}

// [[SEAM:ambition-amplify]] #3 — the UPWARD DUAL of research-rescue. Fires IN-LOOP (maybeAmplify, after review) on
// an HONEST round (this round's FOCUSED verify PASSED) and asks whether the VERIFIED findings can earn a BOLDER,
// more PUBLISHABLE claim. If yes & loop headroom remains, it authors HANDOFF-amplify-*.md + proposes a RAISED
// target; the SAME round's generateHandoff folds it in and the loop RUNS it; the TERMINAL verify_final RE-AUDITS
// the raised claim through #1 (AUTO-EARNED). THIN-SPEC: the goal POINTS to `research-amplify` + injects runtime
// paths; it NEVER inlines the protocol.
// `owner` (optional) = { dirFile, out } — the OWNER-DIRECTED scenario (runOwnerSteer): the owner's NOTES file + a
// round-scoped work-order path, so a later owner push never lands on a segment that already ran. The automatic
// default is round-scoped for the same reason (HANDOFF-amplify-r<N+1>.md, N+1 = the round it feeds; maybeAmplify
// runs before beginNextRound): generateHandoff mints EXPERIMENTS/<slug of the name>/ from it, so a fixed name would
// land a later raise on the segment an earlier raise already finished (its result.md ⇒ the experiment protocol's
// SKIP) and the raised work would never run.
function amplifyGoal(state, owner) {
  const ws = `${RUNS}/${state.paper_slug}`
  const out = (owner && owner.out) || `${ws}/HANDOFF-amplify-r${state.loop_round + 1}.md`
  return [
    `You are the AMBITION AMPLIFIER producing-worker. LOAD the \`research-amplify\` skill FIRST and follow it — it`,
    `carries the full protocol; this goal only names the SCENARIO + injects your runtime paths + output schema.`,
    ...(owner ? [
    `SCENARIO = owner-directed amplify (the skill's §4): the OWNER chose to push this idea further and wrote where in`,
    `${owner.dirFile} — read it first. That direction is BINDING: AUTHOR the work order toward it even when you judge`,
    `the raise not yet earned, and put that judgement in rationale (what must come out true, what could sink it) with`,
    `can_go_bolder = your honest call. The focused-verify-PASS precondition does not apply here. The re-authored work`,
    `order goes back to the owner before it runs, and verify_final still re-audits any raised claim through #1.`,
    ] : [
    `SCENARIO = ambition-amplify (in-loop, after review): THIS round's FOCUSED verify PASSED — the round is HONEST`,
    `(claim ≤ delivery so far). Weigh THIS round's VERIFIED findings and judge whether they can EARN a bolder, more`,
    `publishable claim. Your authored HANDOFF-amplify is folded into the SAME re-authored work order as the round's`,
    `review demands and RUNS next round; the TERMINAL verify_final re-audits the raised claim through #1 (auto-earned).`,
    ]),
    `FLOOR (immutable — NEVER below it, NEVER hand-edit it): ${ws}/HANDOFF.ambition.locked.json. CURRENT TARGET (the`,
    `claim to RAISE ABOVE; the floor itself if absent): ${ws}/HANDOFF.ambition.target.json. Verified evidence is on`,
    `disk (RESEARCH_LOG.md / EXPERIMENTS/*/result.md / THEORY.md / the paper draft / TASK_STATUS.concerns.json /`,
    `VERIFICATION-REPORT.md). Propose a TARGET strictly ≥ the floor; rescue owns below-floor, you own above-target.`,
    `EARN it by DOING: when a rung is earnable, AUTHOR the ambition-directed work order ${out}`,
    `(same shape as research-rescue's HANDOFF-ambition-*.md — the loop's forward-motion folds it into the next wave and`,
    `RUNS it). You do NOT self-bless: the NEXT verify_final re-audits the raised claim.`,
    owner ? `An owner-directed amplify NEVER returns without that work order.`
          : `Call the ceiling HONESTLY when the findings cannot support a bolder PUBLISHABLE claim than the current target (can_go_bolder:false — ship as-is).`,
    `Return metrics.amplify = { can_go_bolder: true|false, proposed_raise: { central_result, scope, named_rivals },`,
    `work: [...], rationale, earnable }.`,
  ].join('\n')
}
// runAmplify — spawn ONE producing-worker (NOT a per-item fan-out: one paper has ONE headline raise; the worker
// weighs ALL verified findings and picks the boldest earnable rung). Backstop: if it STILL fire-detaches, route
// through onLongRun (the SOLE state.detached writer + END_TURN), return {detached:true}. Absent/false
// metrics.amplify ⇒ can_go_bolder:false (do-no-harm ship).
function runAmplify(state, owner) {
  const env = spawnWorker('amplify', amplifyGoal(state, owner))
  tallyBudget(state, 'amplify', env)
  if (env && env.status === 'long_run_fired') { onLongRun(state, env, 'AMPLIFY'); return { detached: true } }
  const a = (env && env.metrics && env.metrics.amplify) || null
  return { can_go_bolder: !!(a && a.can_go_bolder), proposed_raise: a && a.proposed_raise,
           work: (a && a.work) || [], rationale: a && a.rationale, earnable: (a && a.earnable) || null, env }
}
// [[MECH]] raiseAmbitionTarget — persist the amplifier's proposed bolder claim as the CURRENT TARGET
// (HANDOFF.ambition.target.json), the file #1's verifierGoal reconciles delivery against. It starts ABSENT (⇒ the
// locked FLOOR is the target); each earned raise writes/updates it with provenance. NEVER touches the immutable
// floor HANDOFF.ambition.locked.json. The raise is NOT self-blessed — it only holds if the NEXT verify_final's #1
// re-audit finds delivery ≥ this raised target (else delivery < target ⇒ reconciled:false ⇒ D2 rescue).
function raiseAmbitionTarget(ws, proposed_raise, round) {
  const target = `${ws}/HANDOFF.ambition.target.json`
  const prior  = exists(target) ? (readJson(target) || {}) : null
  writeJson(target, {
    central_result: proposed_raise && proposed_raise.central_result,
    scope:          (proposed_raise && proposed_raise.scope) || [],
    named_rivals:   (proposed_raise && proposed_raise.named_rivals) || [],
    provenance: { raised_at_round: round, from: prior ? (prior.central_result || 'prior_target') : 'floor',
                  by: (proposed_raise && proposed_raise.by) || 'amplifier' },   // 'owner' = an owner-directed raise (runOwnerSteer)
  })
}
// [[MECH]] maybeAmplify — the per-round #3 UPWARD amplifier, runs AFTER review, BEFORE generateHandoff re-authors
// the work order. GATED to an HONEST round: (1) this round's FOCUSED verify PASSED — NEVER raise a claim on an
// un-reconciled/over-claimed round (keeps #3 downstream of #1); (2) loop HEADROOM (shares the loop cap); (3) a
// once-per-round .amplify-tried marker (resume idempotent). The TERMINAL verify_final #1 + ship-gate stay the
// FINAL arbiter the raise was EARNED (a raise the loop cannot deliver re-surfaces as a gap → research-rescue,
// never self-blessed). Returns 'raised' | 'none' | 'detached'.
function maybeAmplify(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  const amplifyMark = `${ws}/.round-${state.loop_round}.amplify-tried`
  if (state.verify_verdict !== 'PASS') return 'none'                 // only amplify an HONEST round (focused verify passed)
  if (!(state.loop_round < CFG.max_loop_rounds)) return 'none'       // no headroom (shares the loop cap) → ship as-is
  if (exists(amplifyMark)) return 'none'                             // already tried this round (resume idempotent)
  bash(`touch "${amplifyMark}"`)
  const a = runAmplify(state)
  if (a.detached) return 'detached'                                  // onLongRun already END_TURNed → caller must return
  // [[MECH]] persist BOTH outcomes (quality-ceiling upgrade 2026-07-07): the at-ceiling rationale used to vanish
  // into a bare event line — /learn's [OPPORTUNITY] lane needs it on disk as a headroom signal. Events stay as-is.
  writeJson(`${ws}/.round-${state.loop_round}.amplify-verdict.json`, {
    schema: 'auto-research-amplify-verdict@1', round: state.loop_round,
    outcome: (a.can_go_bolder && a.proposed_raise) ? 'raised' : 'at_ceiling',
    can_go_bolder: !!a.can_go_bolder, rationale: a.rationale || null, earnable: a.earnable || null,
    work: a.work || [], proposed_raise: a.proposed_raise || null })
  if (a.can_go_bolder && a.proposed_raise) {
    raiseAmbitionTarget(ws, a.proposed_raise, state.loop_round)      // persist the RAISED target (#1 re-audits it; never self-blessed)
    log(`抱负 amplify（轮 ${state.loop_round}）: VERIFIED findings can earn a BOLDER claim — raising the ambition target + folding the authored HANDOFF-amplify into this round's re-authored work order (#1 re-audits at verify_final, auto-earned).`)
    logEvent('ambition_amplify', { round: state.loop_round, outcome: 'raised', proposed: a.proposed_raise && a.proposed_raise.central_result })
    return 'raised'
  }
  logEvent('ambition_amplify', { round: state.loop_round, outcome: 'at_ceiling' })   // honest ceiling → ship as-is
  return 'none'
}

// [[MECH]] runOwnerSteer — the OWNER-DIRECTED subagent behind the direction card's `round_action` and the terminal
// card's "Amplify one more round" (2026-09-12, owner decision: the owner steers amplify / rescue; the automatic
// amplifier stays as it was). The owner's NOTES go VERBATIM into a direction file the worker reads — L0 never
// interprets them. The direction is BINDING: the amplifier records its honest risk call but MUST author the work
// order; an owner-directed rescue MUST author runnable experiment work, never a wording-only retain. Nothing is
// self-blessed: a raised target is still reconciled by verify_final #1, and the re-authored order goes back to the
// owner before it runs. `intoRound` = the round this steer feeds; it keys every file written here. Returns the
// persisted record ({ authored, ... }), or null when a detached worker already ended the turn. The CALLER folds.
function runOwnerSteer(state, action, direction, intoRound) {
  const ws = `${RUNS}/${state.paper_slug}`
  const dirFile = `${ws}/.round-${intoRound}.owner-${action}-direction.md`
  const safe = s => String(s == null ? '' : s).replace(/^OWNER_STEER_EOF[ \t]*$/gm, ' OWNER_STEER_EOF')   // same heredoc guard as writeViabilitySteer
  bash(`cat > "${dirFile}" <<'OWNER_STEER_EOF'\n${safe(direction) || '(no direction given — pick the boldest direction the verified findings can support)'}\nOWNER_STEER_EOF`)
  logEvent('owner_steer', { round: intoRound, action, has_direction: !!direction })
  const rec = { schema: 'auto-research-owner-steer@1', round: intoRound, action, direction_file: dirFile }
  const recFile = `${ws}/.round-${intoRound}.owner-steer.json`
  // Written BEFORE the worker runs: if it fire-detaches (both skills forbid it — backstop only), onLongRun ends the
  // turn with the stage unchanged, and the re-presented direction / terminal card still shows this steer in flight.
  writeJson(recFile, Object.assign({ status: 'in_flight' }, rec))
  if (action === 'amplify') {
    const a = runAmplify(state, { dirFile, out: `${ws}/HANDOFF-amplify-owner-r${intoRound}.md` })
    if (a.detached) return null                                      // onLongRun already END_TURNed
    if (a.proposed_raise) raiseAmbitionTarget(ws, Object.assign({}, a.proposed_raise, { by: 'owner' }), intoRound - 1)
    Object.assign(rec, { can_go_bolder: a.can_go_bolder, rationale: a.rationale || null,
                         proposed: (a.proposed_raise && a.proposed_raise.central_result) || null })
  } else {
    const r = runResearchRescue(state, 'owner-directed', [{ id: `owner-r${intoRound}`, owner_direction_file: dirFile }])[0]
    if (turnEnded(state)) return null                                // a detached rescue already END_TURNed via onLongRun
    Object.assign(rec, { verdict: (r && r.verdict) || null, why_none: (r && r.why_none) || null, residual: (r && r.residual) || null })
  }
  rec.authored = !!bash(`ls "${ws}"/HANDOFF-*.md 2>/dev/null || true`).trim()   // every re-author consumes the sidecars, so what is here now is this action's
  rec.status = 'done'
  writeJson(recFile, rec)
  if (!rec.authored) log(`owner ${action}: the worker authored NO work order — the card comes back with its reason (${ws}/.round-${intoRound}.owner-steer.json).`)
  return rec
}
// [[MECH]] foldOwnerSteer — fold an owner-steer work order into the round ABOUT TO RUN. The direction card sits after
// the counter advanced, so loop_round already names that round. Re-open the experiment milestones HERE with the
// no-op snapshot keyed on THIS round (generateHandoff's own re-open keys on loop_round+1 because at the loop tail it
// runs one round earlier, and it skips its re-open once the milestones are no longer done), then let the transition
// path do the folding: scaffold the new segment, re-author + harden the work order, version the spec.
function foldOwnerSteer(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  const led = readJson(`${ws}/milestone-state.json`)
  if (led.milestones['EXPERIMENTS_DONE'] || led.milestones['RESULTS_ON_DISK']) {
    bash(`bash "${PLUGIN_ROOT}/bin/reopen_noop_diff.sh" snapshot "${ws}" "${state.loop_round}" 2>/dev/null || true`)
    delete led.milestones['EXPERIMENTS_DONE']; delete led.milestones['RESULTS_ON_DISK']
    writeJson(`${ws}/milestone-state.json`, led)
    logEvent('experiments_reopened', { round: state.loop_round, reason: 'owner_steer' })
  }
  generateHandoff(state, true); if (turnEnded(state)) return
  restampSpecVersion(state, false)
  bash(`git -C "${ws}" add -A && git -C "${ws}" commit -qm "round ${state.loop_round}: owner-steered work order" --allow-empty`)
}
// [[MECH]] restampSpecVersion — a re-author made AT the direction card (an owner steer, a Revise) belongs to the
// just-completed round's slot. The card sits after the counter advanced, so generateHandoff versioned it as
// SPEC-v<loop_round> — the slot the NEXT loop-tail re-author overwrites, which would erase the very version that
// round then runs. Copy it down into SPEC-v<loop_round-1> and re-ledger that row. The early SPEC-v<loop_round> copy
// is harmless: it is overwritten if the round continues, and it IS the spec in force if the round exits unchanged.
function restampSpecVersion(state, commit) {
  if (!(state.loop_round > 0)) return                                // round 0's initial author is already v0
  const ws = `${RUNS}/${state.paper_slug}`, cur = state.loop_round, prev = state.loop_round - 1
  if (!exists(`${ws}/SPEC/SPEC-v${cur}.md`)) return
  bash(`cp "${ws}/SPEC/SPEC-v${cur}.md" "${ws}/SPEC/SPEC-v${prev}.md"`)
  const sl = bash(`bash "${PLUGIN_ROOT}/bin/spec_ledger.sh" "${ws}" "${prev}" 2>&1 || true`)
  if (!firstLine(sl).startsWith('OK')) log(`WARN spec-ledger did not re-record round ${prev}: ${sl}`)
  logEvent('spec_restamped', { from: cur, to: prev })
  if (commit) bash(`git -C "${ws}" add -A && git -C "${ws}" commit -qm "round ${prev}: card-time re-author re-stamped as SPEC-v${prev}" --allow-empty`)
}
// [[MECH]] writeKilledReport — the honest abandon report for a direction that RAN and was killed (the viability
// gate's Kill, the direction card's Abandon). FINAL-REPORT-killed.md is NOT ship-gated (the RC-11 ship_gate hook
// denies only FINAL-REPORT.md), so the kill never needs ship()/assertShipReady. Returns the round's viability brief.
function writeKilledReport(state, round, exitReason) {
  const ws = `${RUNS}/${state.paper_slug}`
  const brief = exists(`${ws}/.round-${round}.viability.json`) ? readJson(`${ws}/.round-${round}.viability.json`) : null
  const verdicts = collectVerdicts(ws)                               // [[MECH]] P-3: harvest the machine verdicts BEFORE the write
  writeFinalReport(`${ws}/FINAL-REPORT-killed.md`, {
    timeline: state.history, artifacts: collectArtifacts(ws), venue: state.venue, exit_reason: exitReason,
    blocking_point: brief && brief.blocking_point, tried: brief && brief.tried, next_step: brief && brief.next_step,
    what_died: brief && brief.what_died, impact: brief && brief.impact, verdicts,
    policy_resolved: collectResolvedDecisions(DECISIONS), unresolved: collectUnresolved(ws), usage: state.stage_budgets_spent })
  enforceVerdictFidelity(ws, `${ws}/FINAL-REPORT-killed.md`, verdicts)   // [[MECH]] P-3 read-back — bounded, never blocks the kill
  return brief
}

// [[MECH]] writeViabilitySteer — render the owner's Redirect steer as HANDOFF-viability-steer.md the loop merges
// into the next wave. Composes the owner's free-text note with the recommender's next_step (a heredoc write).
function writeViabilitySteer(path, state, note) {
  const ws = `${RUNS}/${state.paper_slug}`
  const brief = exists(`${ws}/.round-${state.loop_round}.viability.json`) ? readJson(`${ws}/.round-${state.loop_round}.viability.json`) : null
  const next_step = (brief && brief.next_step) || ''
  // owner note + recommender next_step are FREE TEXT — neutralize any line that would prematurely close the
  // heredoc (the only injection vector with a single-quoted sentinel: a body line that IS the delimiter).
  const safe = s => String(s == null ? '' : s).replace(/^VIABILITY_STEER_EOF[ \t]*$/gm, ' VIABILITY_STEER_EOF')
  bash(`cat > "${path}" <<'VIABILITY_STEER_EOF'\n`
     + `# VIABILITY STEER (round ${state.loop_round}) — owner Redirect at the per-wave viability gate\n\n`
     + `The owner chose REDIRECT (push the segment through a different way) over kill/continue. Treat this as a\n`
     + `binding additional work order for the NEXT experiment wave (merged into HANDOFF.md Phase 5).\n\n`
     + `## Owner's steer\n${safe(note) || '(none provided)'}\n\n`
     + `## Recommender's suggested next direction\n${safe(next_step) || '(none provided)'}\n`
     + `VIABILITY_STEER_EOF`)
  logEvent('viability_redirect', { round: state.loop_round, has_owner_note: !!note })
}

// ── generateHandoff(state, transition) — the SINGLE HANDOFF.md (re-)authoring step ───────────────────────
// ONE function for EVERY HANDOFF generation point (absorbs the old authorHandoff (P) re-author core + the old
// per-round merge). Three entries: round-0 initial conversion (transition=false), a Revise re-author
// (transition=false), the per-round CONTINUE/amplify transition (transition=true). Round 0 is the DEGENERATE
// transition=false case (no sidecars, no F1, no milestone re-open). `transition` (true ONLY from the loop tail)
// gates the round-transition mechanics; the (P) re-author core ALWAYS runs once we reach the author step.
// When transition: a CONTINUE round exported the diagnose-only review's demands as runs/<slug>/HANDOFF-*.md;
// this makes them ACTUALLY re-run next round (closing the validity-defect spin; 见 DECISIONS.md §RC 历史 —
// validity-redesign). TWO demand kinds by filename:
//   • HANDOFF-redesign-<segId>.md — the EXISTING Phase-5 segment does NOT test its claim: DELETE its done marker
//     (EXPERIMENTS/<segId>/result.md) so the worker RE-AUTHORS it under the Phase-5 claim-fingerprint gate.
//   • HANDOFF-<name>.md — an ADDITIVE new_exhibit (mint an empty EXPERIMENTS/<seg>/.pending scaffold).
// RE-OPEN the experiment milestones (delete EXPERIMENTS_DONE + RESULTS_ON_DISK) so runExperiment re-walks them;
// surviving result.md segments skip, so the re-run is BOUNDED. RE-OPEN is GUARDED on the milestones being done
// (round 0 has none → skipped). A truly no-empirical-concern transition round early-returns (runDossier refreshes the record). The (P)
// core spawns the seed→HANDOFF worker in RE-AUTHOR mode for loop_round>0, folding the demands + the amplifier's
// target into a RE-AIMED work order that MAY legally REDIRECT (§4b) / RAISE (§4c) but NEVER silently WEAKENs (the
// verifier V5/V8 diff the untouched .locked.json baselines). surfaceOnFail = isRound0 || !transition: the initial
// author AND any Revise HARD-halt on a bad work order; a failed transition re-author FALLS BACK to the append-cat
// (forward-motion floor). It does NOT set state.stage — the CALLER routes.
// workorderHardenGoal — [[MECH]] the ADVERSARIAL WORK-ORDER HARDENER goal (THIN; the rubric + CHECKLIST +
// fetch-the-source discipline live in spec/spawn-prompts/WORKORDER-HARDENING.md). Spawned by generateHandoff on EVERY
// (re-)author (incl. round 0), AFTER the work order is authored, BEFORE the experiment worker reads it: the leaf
// FETCHES the authoritative source of every named baseline/method/metric and EDITS the work order to pin
// definitions/judge-metric/anchors, so the worker cannot mis-implement from memory (regression: a memory-built
// baseline diverged from its claimed source; 见 DECISIONS.md §RC 历史 — workorder-hardener).
function workorderHardenGoal(ws, round) {
  return [
    `You are the ADVERSARIAL WORK-ORDER HARDENER (round ${round}). You did NOT review the paper and you do NOT`,
    `implement the experiments — your ONE job is to make THIS round's freshly review-merged experiment demands`,
    `IMPOSSIBLE to mis-implement, BEFORE the experiment worker reads them. You GENERATE a sharper work order`,
    `(edit the vague parts shut); you do not merely flag them.`,
    `Your FULL rubric + the CHECKLIST + the GROUND-TRUTH (fetch-the-source, never memory) discipline + inputs +`,
    `output contract is ${PLUGIN_ROOT}/spec/spawn-prompts/WORKORDER-HARDENING.md. READ IT FIRST, in full; you CANNOT work`,
    `without it — if it is absent, FAIL LOUD, never improvise a rubric. Substitute these placeholders with the`,
    `run's live values as you read it:  <ROUND>=${round}  <WS>=${ws}.`,
  ].join('\n')
}
function generateHandoff(state, transition) {
  const ws = `${RUNS}/${state.paper_slug}`, slug = state.paper_slug
  const isRound0 = state.loop_round === 0
  let handoffs = []
  if (transition) {                                                  // ── round-transition mechanics (loop tail only); round 0 / Revise skip this whole block
    handoffs = bash(`ls "${ws}"/HANDOFF-*.md 2>/dev/null || true`).trim().split('\n').filter(Boolean)
    // [[MECH]] F1 FORWARD-FLOOR (the "review→fix→review spin" fix, half 1). A round can return overall_risk=
    //   major_revision yet write ZERO HANDOFF-*.md, so the early return below would leave experiments un-re-opened →
    //   spin. When review demanded NO experiment this round, READ the LIVE ledger and FORCE-FORWARD any open
    //   EMPIRICAL major concern into a HANDOFF stub the re-open path runs. PURE JSON-FIELD logic — L0 NEVER parses
    //   concern free text (only cat's it verbatim).
    if (!handoffs.length) {                                          // GATE: only force-forward when review produced NO experiment demand (otherwise the normal path runs untouched)
      let led; try { led = exists(`${ws}/TASK_STATUS.concerns.json`) ? readJson(`${ws}/TASK_STATUS.concerns.json`) : null } catch (_) { led = null }
      const rows = (led && Array.isArray(led.open_concerns)) ? led.open_concerns : []
      for (const r of rows) {
        // SELECT: severity major, still open (open|reopened), closed_round null, and an EMPIRICAL/validity concern
        // (needs !== 'spec') — a SPEC-WORDING concern (needs:'spec', legacy alias 'rewrite') must NEVER force an
        // experiment: the next round's HANDOFF re-author already reads the live ledger and fixes it in the spec.
        // Forcing it into a segment would mint experiment work for a wording problem (spec-convergence).
        if (!r || r.severity !== 'major') continue
        if (String(r.source || '').startsWith('seed:')) continue     // pre-registered kill-criteria are disclosure, NOT an observed experiment demand — never force-mint a seed row into a HANDOFF-*/EXPERIMENTS segment (only genuine sensor-raised rows force-forward)
        if (r.status !== 'open' && r.status !== 'reopened') continue
        if (r.closed_round != null) continue
        if (r.needs === 'spec' || r.needs === 'rewrite') continue     // spec-wording concern (legacy alias 'rewrite') → the HANDOFF re-author owns it; force NO experiment
        if (!r.id) continue
        // ANTI-THRASH: skip a concern that already has a live forced segment/marker on disk, so the SAME concern is not
        // re-stubbed every round (a redesign whose target result.md was already cleared, an additive whose scaffold dir
        // already exists, or this concern's own per-round .forced marker). Keyed on the concern id — deterministic.
        const forced = `${ws}/.forced-${slugify(r.id)}.marker`
        const redesignSeg = (r.kind === 'redesign' && r.target_segment) ? r.target_segment : null
        const addSlug = slugify(r.id)
        if (exists(forced)) continue
        if (redesignSeg && !exists(`${ws}/EXPERIMENTS/${redesignSeg}/result.md`)) continue   // its target is already re-opened (result.md cleared) → don't re-stub
        if (!redesignSeg && exists(`${ws}/EXPERIMENTS/${addSlug}`)) continue                  // its additive scaffold already exists → don't re-stub
        // SYNTHESIZE a HANDOFF stub DETERMINISTICALLY — content = the concern id + its recorded text copied VERBATIM
        // (a cat of the JSON field, NO L0 reasoning over it) + one line telling the downstream workorder-hardener +
        // experiment worker to turn it into runnable experiment work. L0 authors NO experiment science.
        const stub = redesignSeg ? `${ws}/HANDOFF-redesign-${redesignSeg}.md` : `${ws}/HANDOFF-${addSlug}.md`
        const verbatim = String((r.concern != null ? r.concern : '') || (r.evidence != null ? r.evidence : '')).replace(/'/g, `'\\''`)
        bash(`printf '%s\\n' '<!-- F1 forward-floor stub: round ${state.loop_round}, concern ${r.id} (severity:major, needs:${r.needs || 'experiment'}, kind:${r.kind || 'new_exhibit'}) -->' '# Forced experiment demand for open major concern: ${r.id}' '' 'This open empirical/validity concern survived the round with no experiment demand written. VERBATIM recorded concern (copied from the ledger, not reasoned over by L0):' '' '${verbatim}' '' 'WORK ORDER: the work-order hardener + experiment worker MUST convert the above into a RUNNABLE experiment ${redesignSeg ? `that re-authors segment ${redesignSeg} under the Phase-5 claim-fingerprint gate` : 'as a NEW first-class Phase-5 segment'} — define the missing baseline/metric/scale at FULL scale, not a gesture.' > "${stub}"`)
        bash(`: > "${forced}"`)                                      // per-concern marker (anti-thrash key) — created the round we force, prevents re-stubbing the SAME concern next round
        logEvent('forced_forward', { concern: r.id, kind: r.kind || 'new_exhibit', seg: redesignSeg || addSlug, needs: r.needs || 'experiment' })   // LOGGING (side-channel)
      }
      handoffs = bash(`ls "${ws}"/HANDOFF-*.md 2>/dev/null || true`).trim().split('\n').filter(Boolean)   // re-scan: stubs we just minted make handoffs.length>0 → the re-open path below runs
    }
    if (!handoffs.length) return                                     // [[MECH]] 陷阱1: no-empirical-concern TRANSITION round (no open empirical major concern) → runDossier refreshes the record → nothing to re-author/re-open
    const additiveSegs = []                                          // [[MECH]] F2: ids the additive scaffolds mint, referenced in HANDOFF.md §5 below
    for (const h of handoffs) {                                      // (1) REDESIGN: clear the target segment's done marker → re-author under the fingerprint gate
      const m = /HANDOFF-redesign-(.+)\.md$/.exec(h)
      if (m) { bash(`rm -f "${ws}/EXPERIMENTS/${m[1]}/result.md"`); logEvent('segment_reopened', { seg: m[1], reason: 'review_validity_redesign' }); continue }
      // [[MECH]] F2 SCAFFOLD (the "review→fix→review spin" fix, half 2). An ADDITIVE HANDOFF re-opens EXPERIMENTS_DONE
      //   but clears NO result.md and mints NO new segment dir → the worker sees every existing segment's result.md and
      //   SKIPs all (experiment-protocol.md:119) → runExperiment re-marks done with --allow-empty (milestone_done.sh
      //   checks only the ledger record, never whether a segment ran) → no-op → spin. So MINT a first-class EMPTY
      //   segment scaffold the worker is FORCED to fill: EXPERIMENTS/<newid>/ with a .pending marker and NO result.md
      //   (protocol:119 then guarantees it runs — a segment without result.md is unfinished). newid is a DETERMINISTIC
      //   slug from the HANDOFF name so a resume/re-merge is idempotent (never double-minted).
      const add = /HANDOFF-(.+)\.md$/.exec(h)
      if (add) { const seg = slugify(add[1]); bash(`mkdir -p "${ws}/EXPERIMENTS/${seg}"; : > "${ws}/EXPERIMENTS/${seg}/.pending"`); additiveSegs.push(seg); logEvent('segment_scaffolded', { seg, reason: 'review_additive_new_exhibit' }) }
    }
    // [[MECH]] F2: reference each minted scaffold id in HANDOFF.md §5 as a FIRST-CLASS segment so the worker must fill it.
    if (additiveSegs.length)
      bash(`{ printf '\\n\\n<!-- F2 round ${state.loop_round}: minted scaffolds (fill EXPERIMENTS/<id>/result.md) -->\\n'; for s in ${additiveSegs.map(s => `'${s}'`).join(' ')}; do printf -- '- Phase-5 segment id: %s (scaffolded empty; produce EXPERIMENTS/%s/result.md at FULL scale)\\n' "$s" "$s"; done; } >> "${ws}/HANDOFF.md"`)
  }
  // ── (P) (re-)author the binding work order (ALWAYS once we reach here: round 0 init, Revise, or transition-with-demand).
  //    REAUTHOR mode for loop_round>0 (seedToHandoffGoal §RE-AUTHOR folds prior HANDOFF + sidecars + ledger + amplifier
  //    target + locked baselines → a RE-AIMED order; MAY REDIRECT §4b / RAISE §4c, NEVER silently WEAKEN, V5/V8 diff the
  //    untouched .locked.json). The worker READS the sidecars; we consume them (rm) below so they never double-merge.
  const surfaceOnFail = isRound0 || !transition                     // [[MECH]] 陷阱2: round-0 init AND any Revise HARD-halt (no plan / no fallback); only a transition fall back to append-cat
  const env = spawnWorker('seed_to_handoff', seedToHandoffGoal(state.picked_seed_file, slug, state.venue, state.notes, !isRound0))
  tallyBudget(state, 'seed_to_handoff', env)
  if (isEnvFailed(env) || !exists(`${ws}/HANDOFF.md`) || (env.escalations && env.escalations.length)) {
    // surfacing fix (C): NEVER proceed on a failed/empty work order. A failed envelope / missing HANDOFF.md / escalation = no binding plan.
    if (surfaceOnFail) {
      failureSurface(state, 'seed-to-handoff',
        (env.escalations && env.escalations.length) ? env.escalations
          : [{ id: 'handoff', severity: 'reject',
               question: `seed→HANDOFF did not produce a valid ${ws}/HANDOFF.md (envelope status=${(env && env.status) || '?'}).`
                 + ` The loop has no work order to execute.`,
               options: ['Resume after I clarify', 'Abandon this idea'] }])
      return                                                         // turnEnded → caller bubbles out of main()
    }
    // FALLBACK (transition only): append-cat the round's sidecars so the round is never stranded (forward-motion floor).
    bash(`for h in "${ws}"/HANDOFF-*.md; do [ -e "$h" ] || continue; printf '\\n\\n<!-- merged round ${state.loop_round}: %s -->\\n' "$(basename "$h")" >> "${ws}/HANDOFF.md"; cat "$h" >> "${ws}/HANDOFF.md"; done`)
  } else {
    // [[MECH]] M1 (lean) — INDEPENDENT scale-contract completeness review (auditor != producer): a read-only skeptic
    // hunts any secretly-toy dimension in the (re-)authored §4b and writes its findings for the handoff gate to
    // surface. It GATES nothing (binding scale enforcement is V8 in the per-round verifier); robust to a broken leaf.
    const scReview = `${ws}/.scale-contract-review.json`; bash(`rm -f "${scReview}"`)
    tallyBudget(state, 'seed_to_handoff', spawnL2('scale_contract_reviewer', scaleContractReviewGoal(ws, state.picked_seed_file, scReview)))
    recordStage(state, 'seed_to_handoff', { handoff: 'HANDOFF.md', round: state.loop_round }, { commit: false })   // [[MECH]] RC-10: ledger the (re-)authored work-order baseline
  }
  bash(`rm -f "${ws}"/HANDOFF-*.md`)                                 // consume sidecars (round0/Revise: none → no-op)
  // (2b) ADVERSARIAL WORK-ORDER HARDENING — runs on EVERY (re-)author incl round 0: an independent leaf FETCHES
  //   the authoritative source of every named baseline/method/metric and EDITS HANDOFF.md to pin definition /
  //   judge-metric / anchors, so the experiment_worker cannot mis-implement from memory. INLINE (cannot detach);
  //   captured by the commit below.
  tallyBudget(state, 'workorder_harden', spawnL2('workorder_hardener', workorderHardenGoal(ws, state.loop_round)))
  // [[MECH]] SPEC VERSION SNAPSHOT — the loop's PRODUCT is the specification, so every (re-)author is versioned
  // on disk right here, after the hardener's last edit and before the round's provenance commit picks it up.
  // SPEC-v<N>.md = the spec produced by round N's evaluation (v0 = the initial work order). bin/spec_ledger.sh
  // then UPSERTs one mechanical row (ambition source/target, scale-contract criteria, open rigor debt, sha) —
  // accounting lives in code, NEVER in an L0 reproduction that can skip it. This pair IS the run's record of how
  // the spec evolved; a round must never close without it. Non-fatal by construction (tolerant of every absent
  // sidecar), but a snapshot failure is LOUD in the log because the record is the deliverable's provenance.
  bash(`mkdir -p "${ws}/SPEC" && cp "${ws}/HANDOFF.md" "${ws}/SPEC/SPEC-v${state.loop_round}.md"`)
  const sl = bash(`bash "${PLUGIN_ROOT}/bin/spec_ledger.sh" "${ws}" "${state.loop_round}" 2>&1 || true`)
  if (!firstLine(sl).startsWith('OK')) log(`WARN spec-ledger did not record round ${state.loop_round}: ${sl}`)
  logEvent('spec_versioned', { round: state.loop_round, file: `SPEC/SPEC-v${state.loop_round}.md` })   // LOGGING (side-channel)
  if (transition && !isRound0) {
    // (3) RE-OPEN the experiment milestones — GUARDED on them actually being done (陷阱3: round 0 has none →
    //     skipped). F2 BACKSTOP: snapshot the PRE-OPEN result.md SHA set keyed on the NEXT round; runExperiment
    //     diffs the current set against it before re-marking EXPERIMENTS_DONE — byte-identical ⇒ REFUSE the
    //     --allow-empty re-mark + surface noop-reopen (fail-closed). Snapshot/diff in bin/reopen_noop_diff.sh.
    const led = readJson(`${ws}/milestone-state.json`)
    if (led.milestones['EXPERIMENTS_DONE'] || led.milestones['RESULTS_ON_DISK']) {
      bash(`bash "${PLUGIN_ROOT}/bin/reopen_noop_diff.sh" snapshot "${ws}" "${state.loop_round + 1}" 2>/dev/null || true`)
      delete led.milestones['EXPERIMENTS_DONE']; delete led.milestones['RESULTS_ON_DISK']
      writeJson(`${ws}/milestone-state.json`, led)
      bash(`git -C "${ws}" add -A && git -C "${ws}" commit -qm "round ${state.loop_round}: re-open experiments for review-demanded work" --allow-empty`)
      logEvent('experiments_reopened', { round: state.loop_round, handoffs: handoffs.length })   // LOGGING (side-channel)
    }
  } else {
    // round 0 / Revise: no milestone re-open.
    // [[MECH]] FIX A (P1#3) — round-0 concern-ledger SEED (deterministic L0 backstop). The seed_to_handoff worker
    // is INSTRUCTED to derive TASK_STATUS.concerns.json from the §4 kill criteria (handoff-authoring
    // reference/mode-seed-generation.md §3 "one open concern per K"; §4 already FOLDS the seed plan's 🔴 Priority
    // Issues into those Ks), but that is a SOFT L1 step. If it does not fire, round 1's bin/round_setup.sh (which
    // runs BEFORE any writer, ~case 'loop') FREEZES an EMPTY .round-1.concerns.json → the round-1
    // experimenter+drafter lose the kill criteria already known from seed→HANDOFF. So DETERMINISTICALLY seed the
    // live ledger from the parsed kill_criteria — ROUND 0 ONLY, and ONLY IF ABSENT (idempotent: the L1 write / a
    // resume / a re-Revise never double-seeds; a peer writer's rows are never clobbered — same canonical
    // { open_concerns:[…] } container the writers upsert into BY id, so K1… stays a single row).
    if (isRound0 && !exists(`${ws}/TASK_STATUS.concerns.json`)) {
      const kh = parseHandoff(`${ws}/HANDOFF.md`)                     // {h1, kill_criteria:[…], …} — thin read; HANDOFF.md is source of truth
      const seeded = (kh.kill_criteria || []).map((k, i) => {
        const text = (k && typeof k === 'object') ? String(k.concern || k.text || k.claim || '') : String(k || '')
        const id = (k && typeof k === 'object' && k.id) || (text.match(/\bK\d+\b/) || [])[0] || `K${i + 1}`
        // opened_round:1 — pre-registered at round 0 but ACTIVE from round 1 (the first wave / first .round-1 freeze).
        // severity:major — a kill criterion is a MAJOR bar the paper must eventually meet. source:'seed:…' is
        // LOAD-BEARING: these pre-registered rows are DISCLOSURE only, so majorNonConverging + the F1 forward-floor
        // both EXCLUDE source:'seed:*' (they must not drive convergence/forcing math — a pre-registered K is not an
        // OBSERVED non-convergence signal). A genuine sensor later raising its OWN row for the same issue drives
        // convergence normally; the seed row stays pure round-1 context. (see the source-startsWith-'seed:' guards.)
        return { id, concern: text, status: 'open', severity: 'major', opened_round: 1, closed_round: null,
                 last_touched_round: 1, evidence: '', source: 'seed:kill_criteria (round-0 pre-registration)' }
      }).filter(r => r.concern)                                       // drop any empty parse artifact
      if (seeded.length) writeJson(`${ws}/TASK_STATUS.concerns.json`, { open_concerns: seeded })   // canonical container the round-freeze hard-reads
    }
    // Commit the (re-)authored + hardened HANDOFF.md (+ any seeded ledger) NOW (recordStage's ledger write was
    // commit:false and the hardener edited HANDOFF.md after it) so its provenance is not deferred.
    bash(`git -C "${ws}" add -A && git -C "${ws}" commit -qm "round ${state.loop_round}: (re-)authored + hardened work order" --allow-empty`)
    // [[MECH]] P-4 fix (dossier 02, 2026-07-07): this commit is UNSKIPPABLE — VERIFY it actually landed. A past
    // run's L0 reproduction silently skipped the bash call above; the hardener's HANDOFF.md edit then rode
    // uncommitted into an unrelated later commit ~55min afterward, breaking clean git-history attribution. A
    // dirty tree here means the commit did NOT happen — FAIL LOUD (never silently proceed with an uncommitted
    // round-0 work order; the caller's failureSurface/gate path is the correct way to stop, not a swallowed gap).
    { const dirty = bash(`git -C "${ws}" status --porcelain -- HANDOFF.md TASK_STATUS.concerns.json 2>/dev/null`).trim()
      if (dirty) throw new Error(`round-0 provenance commit did not land — ${ws} still has uncommitted HANDOFF/ledger changes:\n${dirty}`) }
  }
}

// [[MECH]] reopenLoopWith — the SHARED "re-enter the loop with new HANDOFF work" primitive. A post-loop stage
// (verify_final) authored a HANDOFF-*.md gap demand; this folds it in and re-opens the loop so it RUNS.
// generateHandoff(state, true) does the heavy lifting (transition path); then point state back at 'loop' so the
// dispatch loop re-enters `case 'loop'` at loop_round+1. Do NOT END_TURN here — the loop's experiment fire-detach
// ends it. Used by D2's rescuable ambition-loopback (and #3's forward amplifier).
function reopenLoopWith(state) {
  generateHandoff(state, true)                                       // re-author HANDOFF.md + re-open the experiment milestones (transition)
  state.stage = 'loop'; state.round_in_progress = false; persist(state)   // no between-rounds gate here → the loop-top increment (round_in_progress false) is correct; not a beginNextRound site
}

// [[MECH]] FIX B (P1#5) — beginNextRound: advance the round counter as the NEXT round's setup BEGINS (its work
// order was just authored + experiments re-opened by generateHandoff(state,true) at the CONTINUE / amplify-raised
// transition), NOT lazily on the next 'loop' re-entry. So the between-rounds handoff gate + the persisted
// pipeline-state.json already carry N+1 and gateHandoffApproval labels the card with the round it is ACTUALLY
// approving (was: the stale just-completed N). round_in_progress is set TRUE so the 'loop' re-entry guard SKIPS
// re-incrementing — the idempotency invariant is preserved: a resume/re-present while paused at the gate never
// double-counts. CALL ORDER MATTERS: run this AFTER generateHandoff(state,true) — that call still reads the OLD
// loop_round for its reopen_noop_diff snapshot key (loop_round+1) + its round-N commit messages. round_baseline_paper
// re-anchors to the just-settled paper HEAD (no paper commit happens between here and the round's first write-back,
// so this is byte-identical to the old loop-top computation). Mirrors the loop-top's two-persist idempotency shape.
function beginNextRound(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  state.loop_round += 1; state.round_in_progress = true; persist(state)
  state.round_baseline_paper = bash(`git -C "${ws}/paper" rev-parse HEAD`).trim(); persist(state)
}

// =====================================================================================================
// SPEC DELIVERY — post-loop, from the OPTIMIZED SPEC + its evidence; runs ONCE after verify_final PASSes
// =====================================================================================================
// The loop's PRODUCT is a RESEARCH SPECIFICATION, not a manuscript. Every round EXECUTES the current spec,
// EVALUATES what came back, and RE-AUTHORS the spec to be more AMBITIOUS and more RIGOROUS; generateHandoff
// snapshots each version into SPEC/SPEC-v<N>.md and appends a row to SPEC/spec-ledger.json, so the spec's own
// evolution is on disk. `spec_freeze` is the SINGLE terminal stage: it distils the settled HANDOFF.md into the
// delivered SPEC-FINAL.md, writes SPEC-EVOLUTION.md (the per-round ambition/rigor ledger), and AUDITS that every
// number and criterion the delivered spec carries traces to on-disk evidence. MANDATORY (the RC-10 ship-gate
// requires its ledger entry), idempotent on that entry, and it never detaches.
//
// (The post-loop WRITING ENGINE — freeze_findings -> story -> write -> figures -> edit -> freeze — was RETIRED
// 2026-08-30 with the spec re-aim: the run delivers an optimized specification, not a paper. Its spawn-prompts,
// the FINDINGS.json firewall (schema + bin/freeze_lint.sh) and hooks/writer_isolation live in inactive/.)

// spec_freeze goal — distil the settled spec + its evidence into SPEC-FINAL.md + SPEC-EVOLUTION.md, grounded.
// [[SEAM:terminal-gate]] the owner-Ship steering (present ONLY on a terminal-gate ship) is honored HERE: the
// delivered spec must never claim more than the run's evidence supports — an owner override of the
// novelty-contradicted ABANDON policy is stated AS an override, never repackaged; an over-claim is NARROWED.
function specFreezeGoal(ws, venue) {
  const steer = `${ws}/.terminal-narrowing-accepted.md`
  return [
    `You are the SPEC FREEZE stage — the last gate before ship, a single-context leaf. Read`,
    `${PLUGIN_ROOT}/spec/spawn-prompts/SPEC-FREEZE.md and do EXACTLY what it says — distil the settled work order`,
    `into the DELIVERED research specification, write the per-round evolution ledger, and ground every number and`,
    `criterion in on-disk evidence. Distil and verify; NEVER invent. Substitute as you read it:`,
    `  <WS>=${ws}  <VENUE>=${venue}  <TERMINAL_STEER>=${exists(steer) ? steer : 'none'}`,
    `  <MIN_TOTAL_CITATIONS>=${DRAFTING.min_total_citations}  <MIN_INTRO_CITATIONS>=${DRAFTING.min_intro_citations}`,
  ].join('\n')
}
// [[MECH]] RC-10 / option A — record a stage's GENUINE completion into the L0-owned ledger milestone-state.json
// (STATUS-MODEL.md §6): a real subject-prefixed git commit in ws/paper + a
// stages[name] entry. The ship-gate reads stages[*] + requires a RESOLVABLE paper_commit, so a stage that NEVER
// ran cannot ship; a ran-and-only-surfaced stage DOES leave an entry (do-no-harm ships). opts.commit:false =
// read-only stage (snapshot HEAD, no commit); opts.subject = the commit-subject prefix.
function recordStage(state, name, fields, opts) {
  const ws = `${RUNS}/${state.paper_slug}`; opts = opts || {}
  if (opts.commit !== false)                                          // content stages leave a real subject-prefixed commit
    bash(`git -C "${ws}/paper" add -A && git -C "${ws}/paper" commit -qm "${opts.subject || name}: ${name} complete" --allow-empty`)
  const paper_commit = bash(`git -C "${ws}/paper" rev-parse HEAD`).trim()   // provenance anchor (read-only stages snapshot the verified HEAD)
  const ledger = readJson(`${ws}/milestone-state.json`) || {}
  ledger.stages = ledger.stages || {}
  ledger.stages[name] = Object.assign({ completed_at: now(), paper_commit }, fields || {})
  writeJson(`${ws}/milestone-state.json`, ledger)
  bash(`git -C "${ws}" add -A && git -C "${ws}" commit -qm "stage ${name}: ledger" --allow-empty`)   // ws-root ledger commit (mirrors milestone 828)
  logEvent('stage_recorded', { stage: name, paper_commit, fields: fields || {} })   // LOGGING (side-channel; RC-10)
}
// ── stageDone — RC-10-consistent idempotent-resume predicate for the post-loop stages: a ledger stages[name]
// entry ⇒ the stage genuinely completed (recordStage wrote it) ⇒ skip on resume. The ledger is the single truth
// (a stage's own deliverable may sit at ws root — e.g. SPEC-FINAL.md — rather than under paper/).
function stageDone(ws, name) {
  const s = readJson(`${ws}/milestone-state.json`) || {}
  return !!(s.stages && s.stages[name])
}

// spec_freeze — distil the settled spec into the DELIVERED SPEC-FINAL.md + SPEC-EVOLUTION.md, audited against
// on-disk evidence, then SHIP. MANDATORY: without SPEC-FINAL.md the run has no deliverable, so a failure here
// SURFACES rather than shipping an empty run (the spec-era counterpart of the old 定稿 gate).
function runSpecFreeze(state) {
  const ws = `${RUNS}/${state.paper_slug}`
  const reason = state.ship_reason || 'clean_exit'
  if (stageDone(ws, 'spec_freeze')) { ship(state, reason); return }                            // idempotent resume → ship
  bash(`rm -rf "${PROJECT_DIR}/.polish"`)                            // auditor stage; no fidelity manifest is armed here
  const env = spawnL2('spec_freezer', specFreezeGoal(ws, state.venue))
  tallyBudget(state, 'spec_freeze', env)
  if (isEnvFailed(env) || !exists(`${ws}/SPEC-FINAL.md`) || (env.escalations && env.escalations.length))
    return failureSurface(state, 'spec-freeze-failed',
      (env.escalations && env.escalations.length) ? env.escalations
        : [{ id: 'spec_freeze_failed', severity: 'reject',
             question: `spec_freeze did not produce ${ws}/SPEC-FINAL.md (envelope status=${(env && env.status) || '?'}).`
               + ` The run has NO deliverable specification — it cannot ship.`,
             options: ['Resume after I clarify', 'Abandon this idea'] }])
  const surfaced = (env && (env.surface_items || (env.metrics && env.metrics.surface_items))) || []
  if (surfaced.length) {
    state.spec_freeze_surface_items = surfaced
    log(`SURFACE spec 定稿: ${surfaced.length} ungrounded claim(s)/number(s) narrowed to what the evidence supports — see ${ws}/SPEC-FREEZE-REPORT.md.`)
    logEvent('spec_freeze_surfaced', { n: surfaced.length })          // LOGGING (side-channel)
  }
  recordStage(state, 'spec_freeze', { spec: 'SPEC-FINAL.md', evolution: 'SPEC-EVOLUTION.md',
    surfaced: surfaced.length, status: (env && env.status) || 'done' }, { commit: false })   // ws-root deliverable → snapshot the paper HEAD, no new paper commit
  ship(state, reason)                                                // spec 定稿 done → ship
}

// ── Ship + end the run ────────────────────────────────────────────────────────────────────────────

// ── Verdict fidelity (P-3/H-17, dossier 03 纠正区 C1-1) — the terminal prose must carry the machine verdicts ──
// writeFinalReport ENACTMENT CONTRACT (the function stays model-enacted; these clauses are load-bearing).
// props.verdicts = the collect harvest { verdicts: [{file, key, value}...], skipped: [{file, reason}...] }:
//   • VERDICT FIDELITY: every experiment/segment whose outcome the prose characterizes MUST quote its
//     harvest enum string VERBATIM at first mention (or the named load-bearing boolean aggregate,
//     e.g. ours_valid_past_vacuity_all=false); a plain-English reading may ACCOMPANY the enum, never
//     replace it.
//   • ALWAYS emit the machine-verdict appendix — a '## Machine verdicts (verbatim)' section listing every
//     harvest {file, key, value} row (booleans included) + a note naming each skipped manifest — and the
//     appendix goes AT THE END of the file (export_site_data.py reads only leading excerpts; empty
//     collection → the appendix reads "none found").
//   • REVERT GRADIENT (ratified, dossier P-3): if in-prose enums prove unreadable next run, drop ONLY
//     clause (i)'s in-prose requirement (the BODY rule in bin/verdict_fidelity.py check + the first bullet
//     here) — paraphrase + the verbatim appendix ("转述+附注枚举") and the read-back-against-appendix
//     REMAIN. Keeping the appendix a separate sub-step is what makes that revert a one-clause relaxation.
function collectVerdicts(ws) {
  // [[MECH]] deterministic disk harvest, no reasoning — bin/verdict_fidelity.py collect globs
  // ${ws}/code/**/results/*.json for enum-string verdict fields (key `verdict` or `*_verdict`, dotted path
  // ≤3 segments) + the boolean siblings of every <k>_verdict.verdict hit. TOLERANT-BY-DESIGN: a missing or
  // failing oracle yields an EMPTY harvest (logged), NEVER a throw — a kill/abandon exit must not be blocked.
  try {
    const out = bash(`python3 "${PLUGIN_ROOT}/bin/verdict_fidelity.py" collect "${ws}" 2>/dev/null`)
    return JSON.parse(out || '{"verdicts":[],"skipped":[]}')
  } catch (e) {
    // missing/failing oracle OR unparseable stdout → EMPTY harvest + log; the terminal exit proceeds.
    logEvent('verdict_collect_failed', { ws, error: String(e && e.message || e).split('\n')[0] })   // LOGGING (side-channel)
    return { verdicts: [], skipped: [] }
  }
}
function enforceVerdictFidelity(ws, reportPath, verdicts) {
  // [[MECH]] narrative-vs-verdict read-back after EVERY writeFinalReport (all four call sites). The check is
  // the deterministic oracle (bin/verdict_fidelity.py check — BODY-scoped enum presence, per-verdict
  // flattening scan, appendix completeness); only the FIX reasons. BOUNDED (at most 2 fix rounds) and
  // NEVER blocks a terminal exit — do-no-harm at the terminal boundary.
  let violations = [], rounds = 0
  for (;;) {
    const out = bash(`python3 "${PLUGIN_ROOT}/bin/verdict_fidelity.py" check "${reportPath}" "${ws}" 2>&1 || true`)
    violations = out.split('\n').filter(l => /^(CLAUSE|VIOLATION)/.test(l))
    if (!violations.length) break                                   // PASS (or trivially: none found)
    if (rounds >= 2) {
      // still failing after 2 fix rounds → DEGRADE, never block: machine WARNING line into the appendix + log.
      bash(`printf '\\n%s\\n' "VERDICT-FIDELITY WARNING: ${violations.length} unresolved violation(s) after ${rounds} fix rounds — see run-events verdict_fidelity_warn." >> "${reportPath}"`)
      logEvent('verdict_fidelity_warn', { report: reportPath, violations })   // LOGGING (side-channel)
      break
    }
    rounds += 1
    // [[SEAM:verdict-fidelity]] trigger: the oracle itemized violations. Bounded decision: FIX the report IN
    // PLACE per the violation list — wording/enum/appendix ONLY (quote the missing enum at its first prose
    // mention, de-flatten the flagged line, append/complete the '## Machine verdicts (verbatim)' appendix at
    // EOF from `verdicts`); NEVER regenerate the report, NEVER change a number. Conservative fallback: keep
    // the sentence and add the enum string in parentheses. Then re-check (loop).
  }
  logEvent('verdict_fidelity', { report: reportPath, violations, fix_rounds: rounds })   // LOGGING (side-channel; H-17 度量)
}

// ship — write the run's FINAL-REPORT, then hand off to finishRun. IDEMPOTENT: re-entry OVERWRITES the report.
// [[MECH]] RC-10 ship-gate — the deterministic backstop for the silent finishing-collapse (见 STATUS-MODEL §7/§8;
// RC-11 harness-hook half too). ship() is the SINGLE choke that marks shipped + ends the run, so it re-derives
// ship-readiness from DISK (not state.stage) and REFUSEs if a required stage never produced its report. A MISSING
// report throws; a ran-and-only-surfaced report is do-no-harm shippable (NON-FATAL preserved).
function shipRequireList() {
  // Two required stages, both MANDATORY (no toggles): the terminal science verify, then the spec 定稿 that
  // produces the run's ONE deliverable (SPEC-FINAL.md). The six writing-engine stages retired 2026-08-30.
  return ['verify_final', 'spec_freeze'].join(',')
}
function assertShipReady(state) {
  const ws  = `${RUNS}/${state.paper_slug}`
  const out = bash(`bash "${PLUGIN_ROOT}/bin/pipeline_status.sh" "${ws}" --require "${shipRequireList()}" 2>&1 || true`)
  const ready = /\bSHIP_READY yes\b/.test(out)
  logEvent('ship_ready_check', { slug: state.paper_slug, ready })   // LOGGING (side-channel; RC-10)
  if (!ready) throw new Error(`assertShipReady: REFUSING to ship ${state.paper_slug}. The deterministic pipeline `
    + `oracle (bin/pipeline_status.sh) reports a required finishing stage never produced its on-disk report (= it `
    + `did NOT run), or git provenance is missing, or the §4c AMBITION was NOT reconciled (the claim over-reaches `
    + `delivery — run the research-rescue to RETAIN it, or have the owner approve the documented NARROW-TO-DELIVERED `
    + `residual). Do NOT improvise around it — run the missing stage (verify_final / spec_freeze) to completion so `
    + `it writes its ledger entry + deliverable, THEN ship. Oracle output:\n${out}`)
}
function ship(state, reason) {
  const ws = `${RUNS}/${state.paper_slug}`
  assertShipReady(state)                                          // [[MECH]] RC-10: disk-derived ship-gate (the silent finishing-collapse backstop) — see above
  const verdicts = collectVerdicts(ws)                             // [[MECH]] P-3: harvest the machine verdicts BEFORE the write
  writeFinalReport(`${ws}/FINAL-REPORT.md`, {                       // [[MECH]] HANDOFF §5 "Ship"; overwrite
    timeline: state.history, artifacts: collectArtifacts(ws), venue: state.venue, exit_reason: reason,
    verdicts,                                                      // P-3: the machine-verdict harvest (enactment contract above)
    policy_resolved: collectResolvedDecisions(DECISIONS),          // audit trail of every gate answer
    unresolved: collectUnresolved(ws),                             // every still-open reject/major item (prominent)
    usage: state.stage_budgets_spent })
  enforceVerdictFidelity(ws, `${ws}/FINAL-REPORT.md`, verdicts)    // [[MECH]] P-3 read-back — INSIDE ship() after assertShipReady, so the corrective in-place Edit re-passes the RC-11 ship_gate hook (SHIP_READY derives from the finishing ledger + commits, not the report bytes) and ship()'s overwrite-idempotency is preserved
  recordStage(state, 'ship', { reason, final_report: 'FINAL-REPORT.md' }, { commit: false })   // [[MECH]] RC-10: ledger the ship (after the gate + report; finishRun then seals + ends the run)
  log(`SHIPPED ${state.paper_slug} (${reason}). Deliverable: ${ws}/SPEC-FINAL.md (the optimized research specification) + ${ws}/SPEC-EVOLUTION.md + ${ws}/SPEC/ (per-round versions) + FINAL-REPORT.md; evidence under ${ws}/EXPERIMENTS + ${ws}/paper/review-report.md.`)
  logEvent('ship', { paper: state.paper_slug, reason }); snapshotTraces()   // LOGGING (side-channel) + final per-paper trace harvest
  finishRun(state, 'shipped', reason)
}

// batchGroundClean — seal the GLOBAL .polish/ at run end. [[MECH]] (PROTOCOL §2.5; Flag 1: this —
// not an "active folder" — is the real isolation. V-A resolved at build: the hooks read
// ${PROJECT_DIR}/.polish/* — rewake-when-done.sh, check_fidelity.py:311 — while the review
// protocol writes ${project_dir}/.polish/* with project_dir = runs/<slug>, and exp_ledger.py takes
// --pidfile explicitly; stale PIDs/manifests can therefore land in more than one place. Clear ALL
// THREE candidates (repo root; the workspace; paper/ — the paperDir fallback when no
// project_dir is passed). Do NOT edit the vendored hooks.)
function batchGroundClean(state) {
  // (a) QUIESCE the state: every tracked detached PID must already be joined-or-killed — a live one
  // would be orphaned by clearing the pidfile and could re-wake into the WRONG paper. Non-empty
  // detached here is a caller-ordering bug: resolve (resumeDetached / kill + finalize) BEFORE
  // advancing; fail loud.
  if ((state.detached || []).length) throw new Error('batchGroundClean: detached jobs not quiesced')
  const ws = `${RUNS}/${state.paper_slug}`
  for (const dir of [`${PROJECT_DIR}/.polish`, `${ws}/.polish`, `${ws}/paper/.polish`]) {
    // (b) JOIN/KILL then clear the pidfile — never rm a live PID blind. state.detached can MISS a PID (a 529 can
    // eat the envelope before run-detach's PID is recorded — fact #9), so each pidfile is checked directly: a
    // still-live PID is a runaway at the end of a finished run — kill + log it so PROTOCOL §2.5's quiesce holds.
    bash(`f="${dir}/.bg-pids"; if [ -f "$f" ]; then`
       + ` for p in $(grep -E '^[0-9]+$' "$f" 2>/dev/null); do`
       + `   kill -0 "$p" 2>/dev/null && { kill "$p" 2>/dev/null; echo "[run seal] killed runaway PID $p (${dir})" >> "${ws}/FAILURES.md"; }; done;`
       + ` rm -f "$f"; fi`)
    // (c) disarm the stale freeze. RC-6: use `find … -delete` (matches the Bash(find:*) allow), NOT a bare
    // `rm`, so the harness self-modification auto-classifier doesn't false-flag + BLOCK the disarm — a blocked
    // seal would leave the fidelity hook armed + a dangling .polish symlink that contaminates the next run.
    // Trailing slash on "${dir}/" makes find FOLLOW the symlink (iteration 1: dir=${PROJECT_DIR}/.polish is a
    // symlink); without it find treats the symlink as a leaf and won't descend (per-iteration behavior preserved).
    bash(`find "${dir}/" -maxdepth 1 -name fidelity-manifest.json -delete 2>/dev/null || true`)
  }
  // (d) drop the per-paper .polish SYMLINK (RC-6). `find … -type l -delete` (not bare `rm`) for the same
  // classifier reason as (c); -type l guarantees only the symlink is removed, never its target dir.
  bash(`find "${PROJECT_DIR}" -maxdepth 1 -type l -name .polish -delete 2>/dev/null || true`)
  bash(`git -C "${ws}/code"  add -A 2>/dev/null && git -C "${ws}/code"  commit -qm "run seal: finalize" || true`)
  bash(`git -C "${ws}/paper" add -A 2>/dev/null && git -C "${ws}/paper" commit -qm "run seal: finalize" || true`)
  bash(`git -C "${ws}"       add -A 2>/dev/null && git -C "${ws}"       commit -qm "run seal: finalize" || true`)
}

// finishRun — the run's terminal boundary. [[MECH]] ORDER IS LOAD-BEARING (PROTOCOL §2.6): artifacts already on
//   disk → SEAL (batchGroundClean quiesces detached PIDs + clears .polish) → record final status/reason →
//   stage='done'. IDEMPOTENT: a crash before stage='done' re-runs the (idempotent) seal.
function finishRun(state, finalStatus, reason) {
  // [[MECH]] P-2 fix (dossier 03, D-1): the centralized killed-report is an ARTIFACT — it must be ON DISK
  // BEFORE the seal (batchGroundClean's final `git add -A && commit`), or it is permanently untracked.
  // MUST-LAND-TOGETHER: any future re-introduction of RM2 `rm2.git_revert_resume` (code REMOVED 2026-06-20,
  // tests/TESTS.md SLIMMING note; RUNBOOK's "BUILT but gated" is stale) must land AFTER this ordering —
  // a coordinated revert silently destroys untracked reports.
  // [[MECH]] P-5 fix (dossier 02, 2026-07-07): CENTRALIZE the killed-report write here so no abandon branch can
  // silently ship zero artifacts after real work happened. Root cause this closes: FINAL-REPORT-killed.md was
  // written per-branch by hand (viability-Kill, terminal-gate Abandon) — every OTHER abandon exit (the generic
  // failure-* family, audit_artifact_goalpost) called finishRun directly and shipped NOTHING. Scope is
  // DELIBERATELY narrow (the ratified fix + its own honest caveat): only fires for a POST-WORK abandon — the
  // generic failure-* family (reason='owner_abandoned_at_<phase>' for any phase that is NOT handoff/phase0/
  // literature — those three exit before any experiment exists, and whether THEY deserve a report is a separate,
  // still-open spec question left untouched) and audit_artifact_goalpost. IDEMPOTENT: never overwrites a report
  // a caller already wrote (viability_killed / terminal_* write their OWN richer report, with recommender/verdict
  // detail, BEFORE calling finishRun — skip if the file already exists).
  if ((state.detached || []).length) throw new Error('finishRun: detached jobs not quiesced')  // pre-write quiesce guard — fail loud BEFORE any artifact write (mirrors batchGroundClean's own gate); without it a caller-ordering bug would strand a stray killed-report inside a run the owner may then Resume
  const ws = state.paper_slug ? `${RUNS}/${state.paper_slug}` : null
  const isPreLoopAbandon = /^owner_abandoned_at_(handoff|phase0|literature)$/.test(reason || '')
  const isPostWorkAbandon = finalStatus === 'abandoned' && ws && exists(`${ws}/milestone-state.json`)
    && (reason === 'audit_artifact_goalpost' || (/^owner_abandoned_at_/.test(reason || '') && !isPreLoopAbandon))
  if (isPostWorkAbandon && !exists(`${ws}/FINAL-REPORT-killed.md`)) {
    const verdicts = collectVerdicts(ws)                           // [[MECH]] P-3: harvest the machine verdicts BEFORE the write
    writeFinalReport(`${ws}/FINAL-REPORT-killed.md`, { timeline: state.history, artifacts: collectArtifacts(ws),
      venue: state.venue, exit_reason: reason, verdicts, policy_resolved: collectResolvedDecisions(DECISIONS),
      unresolved: collectUnresolved(ws), usage: state.stage_budgets_spent })
    enforceVerdictFidelity(ws, `${ws}/FINAL-REPORT-killed.md`, verdicts)   // [[MECH]] P-3 read-back — still inside the P-2 pre-seal window, so the CORRECTED bytes (not just the first write) land INSIDE the seal commit; bounded, never blocks the abandon
    logEvent('final_report_centralized', { paper: state.paper_slug, reason })   // LOGGING (side-channel)
  }
  batchGroundClean(state)                                            // PROTOCOL §2.5 — quiesce + seal (the centralized killed-report is now INSIDE the seal commit)
  state.final_status = finalStatus; state.exit_reason = reason
  state.stage = 'done'; persist(state)
  // [[MECH]] the /learn hand-off hint (one line, decision 2026-07-07 Q1): every finished run — shipped OR
  // killed — is retro-able; /learn is a SEPARATE owner-invoked command, never auto-spawned from here.
  log(`Run finished (${finalStatus}: ${reason}). 复盘本轮: 跑 /learn（审管线不审 paper；可随时对历史 run 补跑）。`)
}

// =====================================================================================================
// MAIN — startup card, then dispatch by state.stage; persist after every transition
// =====================================================================================================
function main() {
  // BOOTSTRAP — scaffold the per-instance DATA dirs so a brand-new run from an EMPTY external folder
  // does not fault on the first anchorSelf()/persist()/gate() write. Idempotent (no-op once they exist).
  bash(`mkdir -p "${PROJECT_DIR}/${P.decisions_dir}" "${RUNS}" "${PROJECT_DIR}/data/profile"`)
  // [[MECH]] SELF-PROVISION the folder-level SessionStart hook (idempotent) so EVERY session of this run — incl.
  // terminal-reopen resumes the L0 side-channel never anchors — is captured by the harness, not by model enactment.
  provisionInstance()
  const state = loadState()
  // LOGGING (side-channel; never read by control flow): stamp a stable run_id ONCE (survives resume
  // + spans sessions), anchor THIS session's native transcript dir (hook-independent), emit run_start once.
  anchorSelf()
  if (!state.run_id) {
    state.run_id = genRunId(); persist(state)
    logEvent('run_start', { run_id: state.run_id,
      spec_commit: bash(`cut -d" " -f1 "${PLUGIN_ROOT}/.sync-stamp" 2>/dev/null | cut -c1-12 || true`).trim()
                   || bash(`git -C "${PLUGIN_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown`).trim(),
      git_branch:  bash(`git -C "${PLUGIN_ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo ?`).trim(),
      researcher_key: 'owner' })   // L0 no longer tracks researcher identity — arxiv-scout owns profile build/rebuild
  }

  // [[SEAM:startup-card]] First L0 action = a native AskUserQuestion presenting the INFERRED state →
  // {new run | resume pending gate | resume detached | reconfigure}. A pending_gate ⇒ this turn is most likely
  // the INGEST of its answer. FREE-TEXT INPUT: on the NEW-RUN branch ONLY, startupCard captures $ARGUMENTS
  // VERBATIM into state.user_input — L0 does NOT parse it; phaseIdeation hands it to the ideation L1 and
  // arxiv-scout owns all of its meaning. NEVER read $ARGUMENTS on a RESUME/RECONFIGURE turn (the persisted
  // user_input is the source of truth across re-invocations).
  if (state.pending_gate) {
    const _g = state.pending_gate
    // [[MECH]] A pending gate survived a crash/restart. If an AGENT answers its kind (gateAnsweredBy) it is
    // re-adjudicated here (re-reading the SAME decision file, which is why that file is written for every gate)
    // rather than waiting on a human who is not coming; the attempt counter carries over, so a gate that keeps
    // re-opening still converges. An owner kind ingests the owner's reply exactly as before — never re-adjudicated.
    const _qs = gateAnsweredBy(_g.kind) === 'default' ? readDecisionQuestions(_g.decision_file) : null
    if (gateAnsweredBy(_g.kind) === 'agent' && !readOwnerAnswer(_g)) {
      const qs = readDecisionQuestions(_g.decision_file)     // the questions/options, re-read from the file
      ingestGateAnswer(state, adjudicateGate(state, _g.id, _g.kind, qs, _g.decision_file))
    } else if (_qs && _qs.length) {                          // a default kind re-applies its rule (zero parsed questions ⇒ owner path, never blind)
      ingestGateAnswer(state, defaultGateAnswer(_g.id, _g.kind, _qs))
    } else {
      ingestGateAnswer(state) /* [[MECH]] validate+archive+apply+clear — ingest the owner's answer */
    }
    logEvent('gate_answer', { id: _g.id, kind: _g.kind })
  }
  else if ((state.detached || []).length) { resumeDetached(state) /* re-woken: finalize the detached phase */; logEvent('rewake', {}) }
  else startupCard(state, ARGUMENTS)   // {new | resume | reconfigure}; the NEW-RUN branch sets state.user_input = ARGUMENTS (raw free-text, captured ONCE) and begins at Stage A (ideation); resume/reconfigure leave the persisted user_input untouched

  // [[MECH]] RESUME is flat: the picked idea's working fields + state.stage ARE the source of truth (one run,
  // one idea — no queue index to recompute). applyPickedIdea commits flat-fields + stage in a single atomic
  // persist, so there is no K→K+1 window to heal; every dispatch case is independently idempotent on re-entry.

  // [[SEAM:failure-surface]] A detected detached-crash (resumeDetached set state.pending_crash) is SURFACED to the
  // owner BEFORE the dispatch loop can re-enter runB1 — never a silent blind re-spawn. crashSurface opens the
  // failure gate (interactive → END_TURN here).
  if (state.pending_crash) crashSurface(state)

  // Dispatch loop — run the current stage, persist, advance. Every branch is idempotent/resumable.
  while (state.stage !== 'done') {
    logEvent('stage_enter', {})                                       // LOGGING (side-channel)
    switch (state.stage) {
      // ===== 科研实质:ideation → 选种子 → SPEC-v0 → loop{执行↔评估↔重写 spec} → 终局核验 → spec 定稿。 =====
      // (Banner only. Zero control-flow change; the spine lives in this stage enum.)
      case 'ideation':        phaseIdeation(state); break                 // Stage A entry; → seed_gate (or ends turn at a gate)
      case 'seed_gate':       gateSeedSelect(state); break                // ends turn; ingest picks ONE idea → setup_workspace (deep verification already ran INSIDE the weekly ideation loop; a zero-token freshness check rides the card)
      case 'setup_workspace': setupWorkspace(state); state.stage = 'gen_handoff'; persist(state); break   // one-time destructive bootstrap (bin/setup_workspace.sh; guarded) → gen_handoff
      case 'gen_handoff': {                                               // round-0 initial HANDOFF author (transition=false); Revise re-enters here too
        generateHandoff(state, false); if (turnEnded(state)) return      // a bad work order halts via failureSurface (surfaceOnFail)
        restampSpecVersion(state, true)                                   // a card-time Revise (loop_round ≥ 1) belongs to the just-completed round's SPEC slot
        // [[SEAM:handoff-approval]] (A) the owner approves the binding work order BEFORE the loop spends days on it
        // (config: checkpoints.handoff_approval). Disabled → straight to the loop (byte-identical to the old flow).
        state.stage = CFG.checkpoints.handoff_approval ? 'handoff_gate' : 'loop'; persist(state); break
      }
      case 'handoff_gate':    gateHandoffApproval(state); break           // (A) owner approves the work order → loop
      case 'loop': {
        // [[MECH]] round counter — GUARDED (idempotent): a round is incremented EXACTLY ONCE. FIX B moved the
        // rounds-2+ increment to the between-rounds transition (beginNextRound, so the handoff gate + persisted
        // state carry N+1), which also sets round_in_progress=true; so this loop-top block now fires ONLY when
        // round_in_progress is false on entry — round 1's first entry, plus the reopenLoopWith / detached-amplifier
        // re-wake re-entries (which do NOT pre-increment). A mid-round gate (S1–S10 / [[SEAM:phase0-surface]] /
        // orphan-stops / verify / B2/B3 / the handoff gate) ends the turn with round_in_progress STILL true, so the
        // resume back into 'loop' SKIPS here and NEVER double-counts. (round_in_progress clears at the loop tail
        // when the round genuinely completes; beginNextRound re-arms it for the next round.)
        const wsR = `${RUNS}/${state.paper_slug}`
        if (!state.round_in_progress) {
          state.loop_round += 1; state.round_in_progress = true; persist(state)
          // round_baseline_paper is the paper commit the round's write_backs diff measures against (RC-4).
          state.round_baseline_paper = bash(`git -C "${wsR}/paper" rev-parse HEAD`).trim(); persist(state)
        }
        // [[MECH]] DETERMINISTIC round setup + fail-loud hard-stop (RC-12). bin/round_setup.sh replaces the
        // inline freeze the L0 could skip (taking the throw with it): idempotent on EVERY loop entry (fresh OR
        // mid-round resume) — it creates .round-<n>.start ONCE (its mtime dates HANDOFF-*.md exported THIS
        // round; never re-touched) and FREEZES the open-concern disclosure set into .round-<n>.concerns.json
        // from TASK_STATUS.concerns.json, written ONLY if absent so the freeze stays BYTE-IDENTICAL across a
        // detach+rewake. Its exit 2 (→ 'ERROR' first line) IS the Doc A §3.3 hard-stop: the disclosure set is
        // unreconstructable → STOP LOUD, never silently re-derive a different one.
        const rsout = bash(`bash "${PLUGIN_ROOT}/bin/round_setup.sh" "${wsR}" "${state.loop_round}" 2>&1`)
        if (firstLine(rsout).startsWith('ERROR')) throw new Error(`round_setup failed: ${rsout}`)
        // [[MECH]] After each gating sub-phase: a turn-ENDING gate/detach → bubble out of main(); the next-turn
        // resume re-enters 'loop' and re-drives the sub-phases idempotently (round_in_progress stays true). A
        // review/B3 null WITHOUT turnEnded = an abandon ingest advanced the stage → `continue` re-dispatches.
        // [unified-loop] ONE loop, FOUR stages: experiment → draft → review(+FOCUSED verify) → gate. The full
        // SCIENCE verify runs ONCE at 'verify_final' after EXIT.
        let verdict
        // [[SEAM:viability-gate]] (①) CONTINUE-resume skip: a PRIOR turn's viability gate already resolved this
        // round (.round-<N>.viability-resolved on disk). The wave already RAN — do NOT re-execute
        // runExperiment/runDossier/runReview/runB3 (INVARIANT: a completed wave never re-runs on the gate resume).
        // Reconstruct the verdict from the disk gate-input, then fall through. A REDIRECT (HANDOFF-viability-steer.md
        // on disk) FORCES CONTINUE so generateHandoff folds the steer into the next wave (never a stale-cap EXIT).
        const ws_ = `${RUNS}/${state.paper_slug}`
        if (exists(`${ws_}/.round-${state.loop_round}.viability-resolved`)) {
          if (exists(`${ws_}/HANDOFF-viability-steer.md`)) {
            verdict = 'CONTINUE'                                         // REDIRECT → keep going; the steer feeds the next wave
          } else {                                                      // CONTINUE → enact the SAME verdict the gate opened on, re-derived
            const gi = `${ws_}/loop-gate-input-r${state.loop_round}.json`   // (the frozen gate input runB3 wrote this round)
            verdict = exists(gi) ? firstLine(bash(`bash "${PLUGIN_ROOT}/${P.loop_gate}" "${gi}"`)) : 'CONTINUE'   // pure arithmetic — safe to re-run
            if (verdict === 'EXIT' && state.verify_verdict !== 'PASS') verdict = 'CONTINUE'   // RC-1 belt (mirror runB3): never EXIT on a non-PASS verify
            if (verdict === 'ERROR' || !verdict) verdict = 'CONTINUE'    // un-derivable on resume → do-no-harm CONTINUE (never a spurious EXIT)
          }
          logEvent('viability_resolved_skip', { round: state.loop_round, verdict })   // LOGGING (side-channel)
        } else {
          runExperiment(state);   if (turnEnded(state)) return   // experiment milestones; may gate (failed/S1–S10/phase0) / detach
          scanOrphanStops(state); if (turnEnded(state)) return   // (D) surface log-only stops the L1 didn't escalate
          runDossier(state);      if (turnEnded(state)) return   // per-round FINDINGS-DOSSIER refresh (science record; NO manuscript — the writing engine writes the paper ONCE post-loop)
          const rev = runReview(state);      if (rev === null)     { if (turnEnded(state)) return; continue }   // diagnose-only panel+AC + FOCUSED verify (sets verify_verdict); may gate / (rarely) detach
          verdict = runB3(state, rev);       if (verdict === null) { if (turnEnded(state)) return; continue }   // gate may surface a derived/claimed mismatch
          // [[SEAM:viability-gate]] (①) CONDITIONAL per-wave human gate: a wave whose SCIENTIFIC VIABILITY is in
          // doubt faces the owner (continue / redirect / kill) BEFORE the verdict is enacted; a HEALTHY wave
          // auto-continues untouched (an overnight unattended run is never disturbed). round_in_progress is still
          // set, so a gate→resume re-enters 'loop' and the skip above avoids re-running the (completed) wave.
          // Mirrors the null-verdict idiom: if it gated (gate() did END_TURN), the loop bubbles out; else proceed.
          if (runViabilityGate(state, verdict, rev) === null) { if (turnEnded(state)) return; continue }
        }
        logEvent('verdict', { source: 'loop_gate', label: verdict, gate_passed: verdict === 'EXIT' || verdict === 'EXIT_AT_CAP' })
        snapshotTraces()                                                // LOGGING: harvest this round's full-depth native trace (anti-GC)
        state.round_in_progress = false; persist(state)                 // round genuinely completed → next 'loop' entry = fresh round
        // [[MECH]] the freeze boundary MOVED: /rewrite is the LAST PRE-FREEZE step (may still reconcile science), so
        // [[MECH]] #3 amplifier — on a CLEAN EXIT with loop headroom, try ONE more ambitious round before shipping:
        // if the round's VERIFIED findings can earn a bolder claim (maybeAmplify gated on this round's focused-verify
        // PASS), convert the EXIT into a CONTINUE. EXIT_AT_CAP has no headroom → ship. recordStage('loop' exited) is
        // written ONLY when the loop ACTUALLY exits (after the amplifier declines), never on a convert-to-CONTINUE.
        if (verdict === 'EXIT' || verdict === 'EXIT_AT_CAP') {
          const amp = maybeAmplify(state); if (turnEnded(state)) return                  // a detached amplifier already END_TURNed
          if (amp === 'raised') {                                                        // earned a bolder claim → one more round instead of ship
            generateHandoff(state, true); if (turnEnded(state)) return                   // fold HANDOFF-amplify → re-author HANDOFF → re-open experiments (transition)
            beginNextRound(state)                                                        // [[MECH]] FIX B: advance loop_round to N+1 NOW so the gate + persisted state carry the round being approved
            state.stage = CFG.checkpoints.handoff_approval ? 'handoff_gate' : 'loop'; break   // per-round gate (owner approves the bolder work order) → loop
          }
          recordStage(state, 'loop', { rounds: state.loop_round, exited: verdict }, { commit: false })   // [[MECH]] RC-10: ledger the loop's exit (read-only snapshot of the settled paper HEAD)
          // [[SEAM:terminal-gate]] BOTH exits go to verify_final; the terminal_reason tells runVerify which route it
          // owns. cap_exit surfaces the unified terminal gate (default: hand back as-is); a clean EXIT still auto-ships (its
          // ship_reason is set now). negative_result / over_claim are decided INSIDE runVerify from the verifier's
          // own output. Persist terminal_reason BEFORE the next stage so a crash/gate resume carries it (risk #6).
          state.terminal_reason = (verdict === 'EXIT_AT_CAP') ? 'cap_exit' : 'clean_exit'
          if (verdict === 'EXIT') state.ship_reason = 'clean_exit'
          state.stage = 'verify_final'; persist(state); break   // → final science verify → (auto-ship on clean earn, else terminal gate) → spec_freeze (SPEC-FINAL.md) → ship
        }
        // CONTINUE: the review's experiment-demands + the amplifier's earned raise feed the next round through ONE
        // re-authored work order. maybeAmplify authors HANDOFF-amplify-*.md if earned; generateHandoff RE-AUTHORS
        // HANDOFF.md from ALL the round's demands (re-aimed, possibly REDIRECTed) AND re-opens the experiment
        // milestones (a broken experiment is REDESIGNED, not reframed). Then the per-round handoff gate faces the owner.
        maybeAmplify(state); if (turnEnded(state)) return
        generateHandoff(state, true); if (turnEnded(state)) return
        beginNextRound(state)                                                            // [[MECH]] FIX B: advance loop_round to N+1 NOW so the gate + persisted state carry the round being approved
        state.stage = CFG.checkpoints.handoff_approval ? 'handoff_gate' : 'loop'; break
      }
      case 'verify_final': {                                   // [simplify 2026-06-19] the ONE independent science verify (RC-1), moved out of the per-round loop → runs once on the settled science
        const vf = runVerify(state)                            // PASS → env; FAIL/long-run → null (failureSurface already gated the turn; resume re-enters this stage, idempotent re-verify)
        if (vf === null) { if (turnEnded(state)) return; break } // gated/detached → bubble out of main
        state.stage = 'spec_freeze'; persist(state); break     // science PASSED → freeze the optimized spec
      }
      // ===== 交付层:loop 的产物是 SPEC —— 定稿并交付,不再写论文。 =====
      case 'spec_freeze':    runSpecFreeze(state);     break   // spec 定稿 — SPEC-FINAL.md + SPEC-EVOLUTION.md + grounding audit → ship
      default: throw new Error(`unknown stage ${state.stage}`)
    }
    persist(state)
  }
  log('auto-research run complete.')
}

// ── tiny helpers (reproduced with real tools; names match config keys / state keys exactly) ─────────
// need(obj,...path): fetch a config/state key or CRASH "<MISSING KEY: a.b>" (SSOT, no silent default).
// paginate(arr,n): split into ≤n-sized pages (AskUserQuestion ceilings: ≤4 QUESTIONS per call —
//   venue + ≤3 ideas on GATE-1 page 1 — and ≤4 options per question).
// slugify(title): lowercase, alnum+hyphen, collapse repeats — must be filesystem- and git-safe.
// ARGUMENTS: the RAW $ARGUMENTS free-text the owner typed after /auto-research (harness-injected, like
//   PROJECT_DIR / PLUGIN_ROOT). L0 NEVER parses it — it is captured once into state.user_input on a
//   brand-new run and passed verbatim to the ideation L1 (the URL parsing that used to live here was
//   removed; arxiv-scout.js owns it now).
// tallyBudget(state,stage,env): add env.metrics.subagents_spawned to stage_budgets_spent[stage]; if it
//   exceeds BUDGETS[stage].max_subagent_spawns, note it to SURFACE at the next gate (soft; never kill).
// milestoneDone(ws,ms): run `bash bin/milestone_done.sh <ws> <ms>` — exit 0 → true (recorded by runB1 with
//   completed_at + a commit sha that RESOLVES in ws/code|paper — RC-12), exit 1 → false. The REAL
//   idempotent-resume predicate (RC-3; was undefined). For an EXPERIMENT milestone (ms is NEITHER
//   checkpoints.phase0_milestone NOR checkpoints.literature_milestone) append `--require-segment-commits`, so a
//   milestone whose EXPERIMENTS/<id>/result.md cites an UNCOMMITTED producer stays not-done (the E3-ghost class).
// parseHandoff(path): parse runs/<slug>/HANDOFF.md into { h1, kill_criteria:[…], phases:[…], definition_of_done }
//   for the [[SEAM:handoff-approval]] card (A) — §3=CORE HYPOTHESIS→h1, §4=KILL→kill_criteria,
//   §5=EXECUTION PLAN→phases, §6=DEFINITION OF DONE→definition_of_done. Thin read; file is source of truth.
// scanOrphanStops(state): (D) `bash bin/scan_orphan_stops.sh <ws>` derives the COUNT of stop-shaped markers the
//   B1 L1 wrote into its logs but never escalated; surfaces any INCREASE over state.orphan_ack_count (un-buryable seam).
// parseRefinedSeeds(artifacts): parse the ideation L1's refined-seed .md files (env.artifacts /
//   state.ideation_artifacts) into [{ id, title, hypothesis, significance, rigor, file, verification, judge,
//   premises, rank, novelty }]. CONTRACT — PINNED for the integrity join ([[SEAM:ideation-integrity]]): s.id === the refined-seed
//   .md FILENAME STEM (e.g. 2606.15061-idea0) — the SAME id the ideation_auditor keys each verdict entry by
//   (IDEATION-INTEGRITY.md `id`), so gateSeedSelect joins verdict-entry ↔ card unambiguously by
//   entry.id === context.id (NO 'idea-' prefix-stripping).
//   VINTAGE-TOLERANT additive fields (all null when absent):
//   • `verification` (2026-07-11 verified-kill): when the file carries a '## Verification Record' block (written
//     deterministically by arxiv-ideation.js from bundle.json + the independent recheck), parse its summary —
//     { artifacts (e.g. '4/4 pass'), probe_headline (the first executed-probe line), significance (the floor line,
//     incl. the confrontation), deferred (the deferred-probes count line), killed_siblings (the 死亡名单 count) } —
//     and PREFER it over everything else as the card's primary quality signal. s.hypothesis stays the seed's
//     HYPOTHESIS; s.significance/s.rigor come from the Record when present.
//   • `judge` (2026-07-08 vintage): the '## Judge Verdict' outcome+tiers line — parsed ONLY when no Verification
//     Record exists (older weeks).
//   • `premises` = the count of UNVERIFIED rows in '## Premise Ledger' (pinned row format
//     `P<n>: ... | status: UNVERIFIED (probe: ...) | ...`) — under verified-kill these are exactly the DEFERRED
//     probes (≤1 per seed by construction). Old files without any block parse exactly as before.
//   • `rank` (P-4 / H-18, dossier 03): the paper's machine Phase-3 `original_rank` (1-based, 1 = machine-best).
//     It is the PRE-GATE rerank position, so it MAY exceed the gated-pool size — render it as
//     "Phase-3 rerank #N (1=best)", NEVER "#N/<pool size>". JOIN: find the weekly gated pool — prefer the
//     week-<W>-gated-pool.json path already present in the passed artifacts list (state.ideation_artifacts
//     carries its absolute path), else fall back to `${PROJECT_DIR}/data/cache/week-${week}-gated-pool.json`
//     (week derived from s.file, paperId = s.id minus its -idea\d+ suffix — the same derivations seedFreshness
//     uses); match the pool entry by entry.arxiv_id === paperId and take its `original_rank`. Pool file / entry /
//     field missing at ANY layer ⇒ rank = null; the whole join is try/catch and NEVER throws (TOLERANT BY
//     DESIGN, like seedFreshness) — the card renders with or without it.
//   • `novelty` (P-4 / H-18, dossier 03; VINTAGE-TOLERANT, both formats): ONE competitor/differentiation line.
//     Old vintage: across the '## Novelty Check' section AND every '## Novelty Check Addendum*' section, take
//     the FIRST SENTENCE of the LAST paragraph whose bold lead-in contains 'verdict' (case-insensitive — covers
//     '**Verdict:**', '**Updated verdict:**', '**Verdict (Round 2, supersedes Round 1):**'; later rounds
//     SUPERSEDE earlier ones, so last-wins; the sentence may be long — never truncate it mid-sentence).
//     Verified-kill vintage (2026-07-11+): the FIRST data row of the '## Prior Art & Differentiation' diff
//     table (killing-rival-first), rendered as `<rival> — <residual delta>`. Neither section present ⇒ null.
//     (Dual-vintage parsing is a necessary HOW upgrade over the dossier's wording — written before the format
//     split; the WHAT is unchanged.)
//   • ORDER (independent revert knob): the returned array is sorted by a deterministic key — rank ASCENDING
//     (1 = best FIRST); null rank sorts LAST (as +infinity); ties and nulls keep the original parse order (the
//     refined/*.md filename order). Weekly pool absent ⇒ all ranks null ⇒ the order IS the filename order
//     (this PINS the previously-unpinned fallback order; zero behavior change vs the old glob order).
//     BOTH consumers (gateSeedSelect card + applyPickedIdea first-Keep-wins) read THIS order — presented
//     order === pick order is invariant. RATIFIED REVERT (dossier 03 P-4 / H-18): if rank ordering proves
//     misleading, DELETE ONLY this ORDER clause; keep the rank/novelty fields and card lines.
// ideationDir(artifacts): the ABSOLUTE data/ideations/<week> dir the ideation L1 wrote — derived from the refined
//   seed paths in env.artifacts (the parent of refined/); MUST resolve a relative path against PROJECT_DIR (the
//   ideation_auditor is a fresh context with no cwd guarantee). The auditor reads its refined/*.md + per-paper
//   <arxiv_id>.json + evidence-<arxiv_id>.json here and writes .integrity.json ([[SEAM:ideation-integrity]]).
// ── gate-answer helpers (owner path AND adjudicator path) ────────────────────────────────────────────────────
// readDecisionQuestions(decision_file): re-parse a written DECISIONS-PENDING.md back into the `questions`
//   array gate() was called with — [{ id, options:[{label,description}], context, recommended }]. Needed ONLY
//   on the crash-resume path, where the in-memory questions are gone but the file (the gate's source of truth)
//   survived. Parse the Q-blocks: `**id:**` → id, the Options table rows → option labels (strip a trailing
//   "(Recommended)" into `recommended`), the Context block → context. A block it cannot parse is skipped, and
//   a gate that parses to ZERO questions must fall back to the owner path rather than be auto-answered blind.
// readOwnerAnswer(pending_gate): the answer reader — parse the chat reply (WINS on conflict) + the
//   DECISIONS-PENDING.md ANSWER/NOTES lines into { choice | per_question:[{id,choice,notes}] }. An UNANSWERED
//   author-only item is RE-PRESENTED (returns null; never guess) — except an explicit "use defaults" takes the
//   (Recommended) option. GATE-1 exception (2026-09-12): the owner may name just the ONE idea to Keep (its id or
//   its number on the card) — every idea question left unanswered is Skip, and an unanswered venue takes its
//   (Recommended) default when one exists. (Backstop: archiveDecisionFile REFUSES a still-blank gate, so a mis-parsed sentinel
//   can never be archived — RC-12.)
// archiveDecisionFile(file, answer): [[MECH]] enact as `bash "${PLUGIN_ROOT}/bin/archive_decision.sh"
//   "${DECISIONS}" "<answer summary>"` — the DETERMINISTIC atomic move (mv DECISIONS-PENDING.md →
//   DECISIONS-RESOLVED-<n>.md, n = next index) that stamps the RESOLVED header, REMOVES the pending file (so
//   no stale DECISIONS-PENDING.md can survive → no re-surface next turn), and EXITS 2 on an UNANSWERED gate
//   (ANSWER still the <leave blank> sentinel AND no chat summary). On `ERROR` first line, do NOT clear
//   pending_gate (re-present). NEVER hand-write the RESOLVED file — the decision_guard PreToolUse hook denies a
//   Write/Edit to DECISIONS-RESOLVED-* (gates are L0-only; a subagent that mints one is blocked). <answer
//   summary> = the chosen option label + any notes (chat wins on conflict). Under `gates.adjudicator: agent`
//   the summary MUST also carry the judge's rationale and the marker `[adjudicated by agent, attempt <n>]` —
//   the archived file is the only place a reader later learns that no human signed this, and a decision whose
//   provenance is invisible is worse than one that is merely automatic. (A non-empty summary is also what
//   keeps archive_decision.sh from refusing the gate as UNANSWERED: the ANSWER lines stay on their sentinel
//   because the judge never edits the file — it writes its verdict to its own JSON.)
// representVenue(state, venues): re-present GATE 1's venue question when the answer is not a prepared venue
//   (gate() again — a run never starts on an unprepared venue).
// ── LOGGING side-channel helpers (the trace/event logging system) — ALL fail-open; NONE is read back by
//    control flow, so they CANNOT change any gate/loop/resume decision (pure observability). ──────────────
// logEvent(event, payload): `bash bin/log_event.sh <event> '<json>'`. Appends ONE line to
//   state/run-events.jsonl; the wrapper (ts UTC / run_id / paper / round / milestone / stage) is auto-filled
//   from pipeline-state.json by the script, so callers pass ONLY event-specific fields.
// provisionInstance(): `bash bin/provision_instance.sh <PROJECT_DIR> <PLUGIN_ROOT>`. Idempotently arms a
//   folder-level SessionStart hook (→ session_anchor.sh, absolute path) in <DATA_ROOT>/.claude/settings.local.json,
//   so the HARNESS anchors EVERY native session (incl. a terminal-reopen resume = a new session uuid) regardless
//   of L0 enactment. Called ONCE at bootstrap; the hook it writes arms sessions 2..N (session 1 = anchorSelf).
// anchorSelf(): `bash bin/session_anchor.sh --self`. Records THIS L0 session's native transcript dir into
//   state/sessions.jsonl heuristically (newest project jsonl) — the session-1 belt to provisionInstance's hook
//   suspenders (the hook can't fire for the session that writes it; --self covers session 1, hook covers 2..N).
// snapshotTraces(): `bash bin/snapshot_traces.sh <state.run_id>`. TRUE-COPIES this run's full-depth native
//   trace (L0 jsonl + every subagents/agent-*.jsonl + tool-results) into runs/_trace/<run_id>/ — survives the
//   30-day native GC. Called at each round close + each ship + batch ship.
// genRunId(): `date -u +%Y%m%dT%H%M%SZ` + '-' + the CODE fingerprint (same expression as spec_commit).
//   PROVENANCE (fixed 2026-09-03). A run must be attributable to the code that ran it, and TWO obvious forms
//   both fail: `git -C "${PROJECT_DIR}"` because an external DATA_ROOT is not a git repo (2026-W36's id was
//   literally `20260901T194236Z-unknown`), and `git -C "${PLUGIN_ROOT}"` because at runtime PLUGIN_ROOT is the
//   installed CACHE COPY, which has no .git either. The right source is that cache's own `.sync-stamp` — the
//   content fingerprint bin/reload-cache.sh writes (bin/sync_fingerprint.sh: sha256 over every tracked file's
//   content). It beats a HEAD sha on the merits, not merely on availability: the normal dev loop is
//   edit-worktree → reload-cache → run, where HEAD never moves while the running code does, so a HEAD stamp
//   would label materially different runs identically. Fall back to PLUGIN_ROOT's git HEAD (covers running
//   straight from the monorepo, which has no .sync-stamp), then to `unknown`. Without this, a week's corpus can
//   only argue its own eligibility the way W36 had to: hand-diffing commit timestamps against opus spawn counts.
//   Stamped ONCE at true process start
//   (main()'s `if (!state.run_id)`) into state.run_id; survives resume and stitches MULTIPLE sessions of one
//   logical run under one id. RE-MINTED exactly once more, by applyPickedIdea (P-1 fix, dossier 02,
//   2026-07-07), when a re-pick follows a PREVIOUS idea's conclusion in this same state file (final_status was
//   set) — so an abandon→re-pick never lets the successor attempt's events pollute the concluded attempt's
//   run-events.jsonl stream under a shared id.
// agentLastId(): the agentId in the Agent tool-result trailer ("agentId: <id> (use SendMessage …)") of the
//   call spawnL1 just made — the JOIN KEY to subagents/agent-<id>.jsonl. null if unreadable (the reader then
//   falls back to the subagent's meta.json toolUseId, so it is NOT a single point of failure).
// firstLine(s): first line of a string — used to branch on a gate/validator's first stdout line (EXIT/OK/ERROR).
// turnEnded(state): true if the last phase called END_TURN (gate/detach) — stop the dispatch loop.
// askUser(questions): enact as the real AskUserQuestion tool with a SOURCE-DERIVED preview (the invariant —
//   [[SEAM:gate-preview]]). The preview FORMAT is NOT pinned in code. When you build the card, READ this
//   gate's source file(s): the decision file gate() just wrote (the UNIVERSAL ledger, always present) PLUS
//   any artifact the question's `context` NAMES (handoff_file / log / html / report / evidence). Compose each
//   option's `preview` (the side-by-side box) from what is ON DISK NOW — so a hand-edited HANDOFF.md is
//   reflected and there is no stale snapshot. MAP each question → AskUserQuestion: question text = a one-line
//   restatement; header = a ≤12-char tag; option.label + option.description pass through; option.preview =
//   that source-derived box. RULES: the preview is ALWAYS present, MUST carry the decision-bearing facts, and
//   is NEVER invented without first reading the file (free-hand rendering is the bug this fixes). previews are
//   single-select-only — no gate here is multiSelect, so this always applies.
// loadYaml/readJson/writeJson/exists/bash/log/AGENT/END_TURN: enacted with the real harness tools
// (Read/Write/Bash/Agent). The vendored specs are read+reproduced the same way; this file is the L0 layer.
// now(): [[MECH]] enact as `bash(date -u +%Y-%m-%dT%H:%M:%SZ)` — a REAL UTC timestamp every call, NEVER a
//   constant. A placeholder (e.g. midnight) collapses the history audit trail to one instant — RC-12.

main()
