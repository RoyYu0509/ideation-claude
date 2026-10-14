// =====================================================================================================
// spec/learn.js — the /learn L0 state machine: the POST-RUN LEARNING/RETRO pass (半递归自我改进的复盘半环).
//
// WHAT THIS IS. After one /auto-research run completes, /learn maps every artifact back to the component
// that produced it, reviews each component's OUTPUT + PROCESS (five lenses: 科学/工程/经济/产品/流程),
// adversarially verifies every serious claim, synthesizes ONE dossier + ONE self-contained owner brief,
// ratifies proposals with the owner theme-by-theme, and records accepted proposals as HYPOTHESES the NEXT
// run's retro must check. /learn reviews the MACHINE, not the paper — the paper is evidence about the
// machine. It PROPOSES only; fixes are built in a separate session from the ratified dossier (the "半" in
// semi-recursive: the human gate).
//
// HOW TO CONSUME THIS FILE. You are REPRODUCING this spec exactly like spec/research.js: the MAIN session
// (L0) walks these functions with real harness tools. Same two tags:
//   [[MECH]]        reproduce verbatim — no reasoning (state transitions, bin calls, envelope handling).
//   [[SEAM:<name>]] the ONLY reasoning points — each names its trigger, bounded decision, fallback.
//
// HARD BOUNDARIES (invariants, enforced by every phase below):
//   • READ-ONLY toward the run + the pipeline: /learn writes ONLY under DATA_ROOT/state/learning/<run_id>/
//     and (the dossier + hypothesis tracker) under SOURCE_REPO/dev/learning/. It NEVER touches
//     pipeline-state.json, the workspace, or any run artifact.
//   • Categorical verdicts only — no numeric scores anywhere (owner law).
//   • Findings that re-litigate the evidence pack's §0 SETTLED DECISIONS are AUTO-INVALID.
//   • Proposals always name SOURCE-repo paths (the cache is a frozen copy that drifts).
//   • Zero nesting: every spawn below is a SINGLE-CONTEXT leaf ('auto-research:leaf-worker' — no Agent
//     tool by frontmatter). No L1 tier exists in /learn v1.
// =====================================================================================================

// ── Roots + config (SSOT = PLUGIN_ROOT/config/config.yaml `learning:` block; missing key CRASHES) ─────
const CFG        = loadYaml(`${PLUGIN_ROOT}/config/config.yaml`)
const L          = need(CFG, 'learning')                    // knobs: reviewer caps, brief cap, models, trace depth
const LMODELS    = need(L, 'models')                        // role -> {model, think}: evidence_packer | venue_cold_reader | component_reviewer | crosscut_reviewer | adversarial_verifier | synthesizer
const DATA_ROOT  = PROJECT_DIR                              // /learn runs in the instance DATA_ROOT (same cwd as /auto-research)
const SP         = `${PLUGIN_ROOT}/spec/spawn-prompts`      // rubric home — goal-builders point, never inline

// ── learn-state (state/learning/<run_id>/learn-state.json) — persisted after EVERY transition [[MECH]] ─
// { run_id, phase: 'resolve'|'manifest'|'evidence'|'review_wave'|'verify'|'synthesis'|'ratify'|'record'|'done',
//   resolved: {<KEY lines from bin/learn_resolve.sh>},     // WS/SOURCE_REPO/TRACE_DIR/DEGRADED/...
//   reviewers: [{group, out, index}],                      // the review wave's planned leaves (resume map)
//   coldread: null,                                        // D1 venue cold read: {status:'planned'|'done'|'skipped',
//                                                          //   reason?, venue?, pack?} — set in P-evidence; a skip
//                                                          //   DEGRADES calibration to 无法比对, never blocks
//   themes: [],                                            // [[SEAM:theme-cluster]] output (verify wave plan)
//   dossier: null, brief: null, ratify_queue: null,        // synthesis outputs (paths)
//   brief_delivered: false,                                // the six-section brief is printed ONCE
//   gates_done: [], decisions: [],                         // ratified themes + their raw answers
//   pending_gate: null,                                    // { id, kind, decision_file } | null — /learn's OWN
//                                                          //   gate (its decisions dir is ISOLATED from the
//                                                          //   pipeline's: state/learning/<run_id>/decisions/)
//   history: [] }                                          // [{ts, event, detail}] — /learn does NOT write the
//                                                          //   pipeline's run-events.jsonl (its trace stays local)
function statePath(runId) { return `${DATA_ROOT}/state/learning/${runId}/learn-state.json` }
function loadLS(runId)    { return exists(statePath(runId)) ? readJson(statePath(runId)) : null }
function persistLS(ls)    { ls.history.push({ ts: now(), event: ls.phase })
                            writeJson(statePath(ls.run_id), ls) }     // [[MECH]] whole state, every transition

// ── Leaf spawn — ONE tier only. [[MECH]] + [[SEAM:empty-result-recovery]] (same idiom as research.js) ──
// Every /learn subagent is a single-context 'auto-research:leaf-worker' (frontmatter has NO Agent tool —
// structural no-nesting; spawn_guard allows it). Envelope contract + validation are REUSED verbatim from
// the pipeline: the leaf returns the uniform envelope, validated by bin/validate_envelope.sh against
// spec/l1-envelope-schema.json; empty/failed/invalid → ONE resume re-spawn, then a failed envelope bubbles.
function spawnLearnLeaf(role, goal, { resume = false } = {}) {
  const m = need(LMODELS, role)                                        // {model, think}
  const env = AGENT({ subagent_type: 'auto-research:leaf-worker', model: m.model,
                      prompt: goal + (m.think ? `\n\n${m.think}` : '') })
  const envFile = `${DATA_ROOT}/state/learning/.last-envelope-${role}.json`; writeJson(envFile, env || {})
  const valid = firstLine(bash(`bash "${PLUGIN_ROOT}/bin/validate_envelope.sh" "${envFile}" 2>&1 || true`)).startsWith('OK')
  if (!env || env.status === 'failed' || !valid) {
    if (!resume) return spawnLearnLeaf(role, goal + `\n\n[RESUME] A prior attempt returned no/invalid envelope`
        + ` (it MUST satisfy spec/l1-envelope-schema.json). Check which of your output files already exist on`
        + ` disk, CONTINUE from there (do not redo finished reading/writing), and return a SCHEMA-VALID envelope.`,
        { resume: true })
    return { status: 'failed', artifacts: [], escalations: [], detached: null, metrics: { notes: 'empty/invalid after one resume' } }
  }
  return env
}
// spawnLearnLeavesParallel — the review/verify waves fan out AS ONE CONCURRENT BATCH: the reproducing L0
// issues ALL Task calls IN ONE MESSAGE (the spawnWorkersParallel enactment from research.js), then collects
// envelopes in plan order. Items are independent by construction (disjoint groups / disjoint themes).
function spawnLearnLeavesParallel(plans) { return plans.map(p => spawnLearnLeaf(p.role, p.goal)) }

// ── /learn's OWN human gate — the pipeline gate() idiom against an ISOLATED decisions dir ─────────────
// [[SEAM:gate]] Same hybrid mechanism as research.js gate(): durable decision file + live AskUserQuestion
// card + END_TURN; ingest on the next turn (chat wins over file; unanswered items re-presented, never
// guessed). ISOLATION: the file lives under state/learning/<run_id>/decisions/ so a /learn gate can NEVER
// collide with (or be swallowed by) a pipeline gate in state/decisions/. Archival reuses
// bin/archive_decision.sh verbatim (it takes the dir as an argument).
function learnGate(ls, id, questions) {
  const ddir = `${DATA_ROOT}/state/learning/${ls.run_id}/decisions`
  bash(`mkdir -p "${ddir}"`)
  const file = `${ddir}/DECISIONS-PENDING.md`
  writeDecisionFile(file, `${PLUGIN_ROOT}/${CFG.paths.decision_template}`, id, 'author', questions)
  ls.pending_gate = { id, kind: 'author', decision_file: file }; persistLS(ls)
  // [[SEAM:gate-preview]] SOURCE-DERIVED, never pre-baked (the research.js invariant, reused): compose every
  // option's preview by READING this gate's source files AT SURFACE TIME — the decision file just written
  // PLUS the dossier section / ratify-queue entry the question's context names. Never invent, never omit.
  try { askUser(questions) } catch (_) {}
  log(`LEARN GATE ${id}: wrote ${file}; ending turn. Answer in chat and/or edit the file.`)
  END_TURN()
}
function archiveLearnGate(ls, answerSummary) {                         // [[MECH]] atomic archive; refuses blanks
  const ddir = `${DATA_ROOT}/state/learning/${ls.run_id}/decisions`
  bash(`bash "${PLUGIN_ROOT}/bin/archive_decision.sh" "${ddir}" ${answerSummary ? quote(answerSummary) : ''}`)
  ls.pending_gate = null; persistLS(ls)
}

// =====================================================================================================
// P-resolve — mechanical run/path resolution. [[MECH]] bin/learn_resolve.sh; branch on its KEY lines.
// =====================================================================================================
function phaseResolve(ls, target) {
  const out = bash(`bash "${PLUGIN_ROOT}/bin/learn_resolve.sh" "${DATA_ROOT}" ${target ? quote(target) : ''}`)
  if (firstLine(out).startsWith('ERROR')) throw new Error(out)         // fail loud — never guess a run
  const R = parseKeyLines(out)   // {DATA_ROOT,RUN_ID,SLUG,WS,SOURCE_REPO,CACHE_ROOT,TRACE_DIR,SESSIONS_N,EVENTS_N,DEGRADED,PIPELINE_BUSY,LEARN_DIR,LEARN_STATE,DOSSIER_HOME,RESOLVED_BY}
  // [[MECH]] busy discipline: a pending PIPELINE gate always refuses (two live gates would fight for the
  // owner's next answer). A mid-stage run refuses ONLY the no-arg form — an EXPLICIT target is consent to
  // retro a live/other run (its still-moving artifacts are reviewed as-of-now; the manifest timestamps that).
  if (R.PIPELINE_BUSY.startsWith('gate:'))
    throw new Error(`refusing to start /learn: the pipeline has a PENDING gate (${R.PIPELINE_BUSY}) — answer it first`)
  if (R.PIPELINE_BUSY.startsWith('stage:') && !target)
    throw new Error(`the pipeline is mid-run (${R.PIPELINE_BUSY}); pass an explicit run/workspace target to retro a past run, or wait for stage:done`)
  ls.run_id = R.RUN_ID; ls.resolved = R; ls.phase = 'manifest'
  bash(`mkdir -p "${R.LEARN_DIR}"`); persistLS(ls)
}

// =====================================================================================================
// P-manifest — the mechanical run manifest + economics rollup. [[MECH]] zero LLM.
// =====================================================================================================
function phaseManifest(ls) {
  const R = ls.resolved
  const out = bash(`python3 "${PLUGIN_ROOT}/bin/learn_manifest.py" --data-root "${R.DATA_ROOT}" --ws "${R.WS}"`
    + ` --run-id "${R.RUN_ID}" --slug "${R.SLUG}" --source-repo "${R.SOURCE_REPO === 'none' ? '' : R.SOURCE_REPO}"`
    + ` --out-dir "${R.LEARN_DIR}"`)
  if (!firstLine(out).startsWith('OK')) throw new Error(`learn_manifest failed: ${out}`)
  // economics input — derived, never persisted by the pipeline; tolerate absence of transcripts/events.
  bash(`cd "${R.DATA_ROOT}" && CLAUDE_PROJECT_DIR="${R.DATA_ROOT}" python3 "${PLUGIN_ROOT}/bin/run_report.py"`
    + ` rollup --run "${R.RUN_ID}" --out "${R.LEARN_DIR}/rollup.json" >/dev/null 2>&1 || true`)
  // [[MECH]] capture hygiene — the transient-event ledger (failure/transient.md): mechanical cause tags the
  // evidence packer copies into §7 so no reviewer reads a transient death as science. Degrade honest (|| true).
  bash(`python3 "${PLUGIN_ROOT}/bin/classify_crash.py" scan --ws "${R.WS}"`
    + ` --events "${R.DATA_ROOT}/state/run-events.jsonl" --out "${R.LEARN_DIR}/transient-events.json" || true`)
  // [[MECH]] the ONLY manifest artifact L0 reads is the <=60-line summary (context discipline).
  log(readFile(`${R.LEARN_DIR}/manifest-summary.md`))
  ls.phase = 'evidence'; persistLS(ls)
}

// =====================================================================================================
// P-evidence — a TWO-leaf pre-wave batch: the evidence packer (load-bearing) + the CONDITIONAL venue
// cold reader (D1, charter exception iv). Independent by construction — the packer never reads the
// paper, the cold reader reads NOTHING else — so both go out in ONE message. The cold read DEGRADES
// (calibration 无法比对), it never blocks the retro.
// =====================================================================================================
function evidenceGoal(R) {
  return `Read ${SP}/LEARN-EVIDENCE-PACK.md and do EXACTLY what it says, substituting:
<LEARN_DIR>      = ${R.LEARN_DIR}
<MANIFEST>       = ${R.LEARN_DIR}/manifest.json
<SOURCE_REPO>    = ${R.SOURCE_REPO}                (if 'none': skip repo corpora, say so in the pack)
<RUN_DECISIONS>  = ${R.DATA_ROOT}/state/decisions  (this run's resolved human gates)
<HYPOTHESES>     = ${R.DOSSIER_HOME}/hypotheses.json  (may not exist yet — then say 'no prior hypotheses')
<QUALITY_LEDGER> = ${qualityLedgerToken(R)}        (§6; 'absent' ⇒ say 'N/A pre-upgrade / 首轮')
<OUT>            = ${R.LEARN_DIR}/evidence-pack.md
Return the uniform envelope (spec/l1-envelope-schema.json) with artifacts=[<OUT>].`
}
// [[MECH]] token helpers — 'absent — <reason>' keeps every downstream rubric's degrade path deterministic.
function coldreadTokens(R, coldread) {
  const done = coldread && coldread.status === 'done'
  const abs = `absent — ${(coldread && coldread.reason) || 'cold read not run'}`
  return { md: done ? `${R.LEARN_DIR}/venue-cold-read.md` : abs,
           json: done ? `${R.LEARN_DIR}/venue-cold-read.json` : abs }
}
function qualityLedgerToken(R) {
  return exists(`${R.DOSSIER_HOME}/quality-ledger.json`) ? `${R.DOSSIER_HOME}/quality-ledger.json` : 'absent'
}
// [[MECH]] planColdRead — D1 eligibility, deterministic (the group-E precedent: artifact-driven, no knob).
// Eligible iff the run SHIPPED a paper (manifest d-master-tex count > 0), has a venue, and the venue
// resolves WITH a review kit. A shipped run at a kit-less venue SKIPS (a nearest-kit proxy would poison
// the label). Returns { eligible:true, venue, pack } or { eligible:false, reason }.
function planColdRead(R) {
  const man = readJson(`${R.LEARN_DIR}/manifest.json`)
  const tex = (((man.groups || {}).D || {}).artifacts || []).find(a => a.family === 'd-master-tex')
  if (!tex || !tex.count) return { eligible: false, reason: 'no shipped paper (d-master-tex count 0)' }
  const venue = (man.pipeline || {}).venue
  if (!venue) return { eligible: false, reason: 'run has no venue' }
  const vroot = `${PLUGIN_ROOT}/${CFG.paths.vendor_paper_polish}`
  let pack; try {
    pack = JSON.parse(bash(`python3 "${vroot}/scripts/venue_resolve.py" resolve --root "${vroot}" --venue ${quote(venue)} --require-review-kit 2>/dev/null || echo '{}'`))
  } catch (_) { pack = {} }
  if (!pack || pack.status !== 'ok') return { eligible: false, reason: `venue '${venue}' has no review kit` }
  return { eligible: true, venue, pack: { ...pack, root: vroot } }     // pack paths are RELATIVE to root
}
function coldreadGoal(R, venue, pack) {
  return `Read ${SP}/LEARN-VENUE-COLDREAD.md and do EXACTLY what it says, substituting:
<VENUE>             = ${venue}
<VENUE_PACK_JSON>   = ${JSON.stringify(pack)}   (its dir/profile/reviewDir/core* paths are RELATIVE to its 'root')
<PAPER_DIR>         = ${R.WS}/paper
<PANEL_VERDICTS>    = ${R.WS}/paper/review-verdicts.md   (may be absent — Part 2 says so)
<TERMINAL_JSON>     = ${R.WS}/.terminal-verdict.json     (may be absent — Part 2 says so)
<OUT>               = ${R.LEARN_DIR}/venue-cold-read.md
<OUT_JSON>          = ${R.LEARN_DIR}/venue-cold-read.json
Return the uniform envelope with artifacts=[<OUT>, <OUT_JSON>].`
}
function phaseEvidence(ls) {
  const R = ls.resolved
  if (!ls.coldread) {                                                  // [[MECH]] eligibility decided ONCE, persisted
    const c = planColdRead(R)
    ls.coldread = c.eligible ? { status: 'planned', venue: c.venue, pack: c.pack }
                             : { status: 'skipped', reason: c.reason }
    persistLS(ls)
  }
  const plans = []                                                     // idempotent resume: output exists ⇒ skip
  if (!exists(`${R.LEARN_DIR}/evidence-pack.md`))
    plans.push({ role: 'evidence_packer', goal: evidenceGoal(R) })
  if (ls.coldread.status !== 'skipped' && !exists(`${R.LEARN_DIR}/venue-cold-read.json`))
    plans.push({ role: 'venue_cold_reader', goal: coldreadGoal(R, ls.coldread.venue, ls.coldread.pack) })
  if (plans.length) spawnLearnLeavesParallel(plans)                    // ONE message, both leaves
  if (!exists(`${R.LEARN_DIR}/evidence-pack.md`))
    throw new Error('evidence pack failed after one resume — cannot proceed without §0')
  if (ls.coldread.status !== 'skipped')                                // [[MECH]] degrade, never block
    ls.coldread = exists(`${R.LEARN_DIR}/venue-cold-read.json`)
      ? { ...ls.coldread, status: 'done' }
      : { status: 'skipped', reason: 'cold-read leaf failed after one resume' }
  ls.phase = 'review_wave'; persistLS(ls)
}

// =====================================================================================================
// P-review_wave — the parallel fan-out: 5-6 component-group reviewers + 4 cross-cutting lines.
// =====================================================================================================
// [[MECH]] wave planning is deterministic from the manifest + knobs (no judgment):
//   groups = A B C1 C2 D (group E — 公众号 publishing — retired 2026-08-30 with the plugin).
//   L.max_component_reviewers < needed ⇒ merge in fixed order: first C1+C2 -> C, then B into A.
//   Cross-cutting lines are ALWAYS spawned: X1 science-chain, X2 economics, X3 enactment-fidelity,
//   X4 quality-ceiling (opportunity stance; its cold-read/ledger inputs degrade to 'absent' honestly).
function planReviewWave(ls) {
  const R = ls.resolved
  let groups = ['A', 'B', 'C1', 'C2', 'D']
  let cap = L.max_component_reviewers
  if (groups.length > cap) groups = groups.filter(g => g !== 'C2').map(g => g === 'C1' ? 'C1+C2' : g)
  if (groups.length > cap) groups = groups.filter(g => g !== 'B').map(g => g === 'A' ? 'A+B' : g)
  const cr = coldreadTokens(R, ls.coldread)
  const plans = groups.map(g => ({
    role: 'component_reviewer', group: g,
    out: `${R.LEARN_DIR}/reviews/${g.replace('+', '_')}.md`,
    index: `${R.LEARN_DIR}/reviews/${g.replace('+', '_')}.index.md`,
    goal: componentReviewGoal(R, g, cr),
  }))
  for (const x of ['science', 'economics', 'enactment', 'quality']) plans.push({
    role: 'crosscut_reviewer', group: `X-${x}`,
    out: `${R.LEARN_DIR}/reviews/X-${x}.md`, index: `${R.LEARN_DIR}/reviews/X-${x}.index.md`,
    goal: crosscutGoal(R, x, cr),
  })
  return plans
}
function componentReviewGoal(R, group, cr) {
  return `Read ${SP}/LEARN-COMPONENT-REVIEW.md and do EXACTLY what it says, substituting:
<GROUP>          = ${group}
<LEARN_DIR>      = ${R.LEARN_DIR}
<MANIFEST>       = ${R.LEARN_DIR}/manifest.json        (your group's artifact families + event slice live here)
<EVIDENCE_PACK>  = ${R.LEARN_DIR}/evidence-pack.md     (READ FIRST — §0 SETTLED DECISIONS binds you)
<WS>             = ${R.WS}
<DATA_ROOT>      = ${R.DATA_ROOT}
<SOURCE_REPO>    = ${R.SOURCE_REPO}
<TRACE_DEPTH>    = ${L.trace_depth}                    (events = event slices + artifacts only; full = may also open trace transcripts via bin/run_report.py)
<VENUE_COLDREAD> = ${cr.md}                            (calibration label ONLY — charter exception iv)
<OUT>            = ${R.LEARN_DIR}/reviews/${group.replace('+', '_')}.md
<INDEX>          = ${R.LEARN_DIR}/reviews/${group.replace('+', '_')}.index.md   (hard cap ${L.findings_index_max_lines} lines)
Return the uniform envelope with artifacts=[<OUT>, <INDEX>].`
}
function crosscutGoal(R, line, cr) {
  const RUBRIC = { science: 'LEARN-CROSSCUT-SCIENCE.md', economics: 'LEARN-CROSSCUT-ECONOMICS.md',
                   enactment: 'LEARN-CROSSCUT-ENACTMENT.md', quality: 'LEARN-CROSSCUT-QUALITY.md' }[line]
  return `Read ${SP}/${RUBRIC} and do EXACTLY what it says, substituting:
<LEARN_DIR>      = ${R.LEARN_DIR}
<MANIFEST>       = ${R.LEARN_DIR}/manifest.json
<EVIDENCE_PACK>  = ${R.LEARN_DIR}/evidence-pack.md     (READ FIRST — §0 binds you)
<WS>             = ${R.WS}
<DATA_ROOT>      = ${R.DATA_ROOT}
<SOURCE_REPO>    = ${R.SOURCE_REPO}
<ROLLUP>         = ${R.LEARN_DIR}/rollup.json          (may be absent on a degraded run — then say 'unmeasurable')
<TRACE_DIR>      = ${R.TRACE_DIR}                      ('none' on a degraded run)
<RUN_REPORT>     = cd "${R.DATA_ROOT}" && CLAUDE_PROJECT_DIR="${R.DATA_ROOT}" python3 "${PLUGIN_ROOT}/bin/run_report.py"
<VENUE_COLDREAD> = ${cr.md}                            (calibration label ONLY — charter exception iv)
<VENUE_COLDREAD_JSON> = ${cr.json}
<QUALITY_LEDGER> = ${qualityLedgerToken(R)}
<OUT>            = ${R.LEARN_DIR}/reviews/X-${line}.md
<INDEX>          = ${R.LEARN_DIR}/reviews/X-${line}.index.md   (hard cap ${L.findings_index_max_lines} lines)
Return the uniform envelope with artifacts=[<OUT>, <INDEX>].`
}
function phaseReviewWave(ls) {
  const R = ls.resolved
  bash(`mkdir -p "${R.LEARN_DIR}/reviews"`)
  const plans = planReviewWave(ls)
  ls.reviewers = plans.map(p => ({ group: p.group, out: p.out, index: p.index })); persistLS(ls)
  // [[MECH]] idempotent resume: spawn ONLY the leaves whose OUT file is missing; all in ONE message.
  const todo = plans.filter(p => !exists(p.out))
  if (todo.length) spawnLearnLeavesParallel(todo)
  const missing = plans.filter(p => !exists(p.out)).map(p => p.group)
  if (missing.length) throw new Error(`review wave incomplete after resume: ${missing.join(', ')} — inspect and re-run /learn`)
  ls.phase = 'verify'; persistLS(ls)
}

// =====================================================================================================
// P-verify — adversarial verification BY THEME (refute stance; the 25-31% correction layer).
// =====================================================================================================
function phaseVerify(ls) {
  const R = ls.resolved
  if (!ls.themes || !ls.themes.length) {
    // [[SEAM:theme-cluster]] the FIRST of /learn's two judgment seams. Trigger: all findings-indexes on
    // disk. Decision: read ONLY the .index.md files (bounded), cluster every Fundamental/Structural claim
    // into <= L.verify_themes_max themes (cluster by shared root cause, NOT by reviewer — the
    // deep-review-harness split-by-theme rule); Minor claims are spot-checked by the theme they ride with.
    // Output: ls.themes = [{ name, claims: [claim-ids], index_files: [paths] }] + write themes.json.
    // Fallback: clustering unclear ⇒ ONE theme per index file, capped at the knob (never skip verification).
    ls.themes = clusterThemes(ls.reviewers.map(r => r.index), L.verify_themes_max)
    writeJson(`${R.LEARN_DIR}/themes.json`, ls.themes); persistLS(ls)
  }
  bash(`mkdir -p "${R.LEARN_DIR}/verify"`)
  const cr = coldreadTokens(R, ls.coldread)
  const plans = ls.themes.map((t, i) => ({
    role: 'adversarial_verifier', group: `theme-${i}`,
    out: `${R.LEARN_DIR}/verify/theme-${i}.md`,
    goal: `Read ${SP}/LEARN-ADVERSARIAL-VERIFY.md and do EXACTLY what it says, substituting:
<THEME>          = ${t.name}
<CLAIMS>         = ${t.claims.join('; ')}
<REVIEW_FILES>   = ${ls.reviewers.map(r => r.out).join(', ')}
<EVIDENCE_PACK>  = ${R.LEARN_DIR}/evidence-pack.md
<MANIFEST>       = ${R.LEARN_DIR}/manifest.json
<WS>             = ${R.WS}
<DATA_ROOT>      = ${R.DATA_ROOT}
<VENUE_COLDREAD> = ${cr.md}
<VENUE_COLDREAD_JSON> = ${cr.json}
<OUT>            = ${R.LEARN_DIR}/verify/theme-${i}.md
Return the uniform envelope with artifacts=[<OUT>].`,
  }))
  const todo = plans.filter(p => !exists(p.out))                       // idempotent resume
  if (todo.length) spawnLearnLeavesParallel(todo)
  const missing = plans.filter(p => !exists(p.out)).map(p => p.group)
  if (missing.length) throw new Error(`verify wave incomplete: ${missing.join(', ')}`)
  ls.phase = 'synthesis'; persistLS(ls)
}

// =====================================================================================================
// P-synthesis — ONE leaf writes the dossier (repo), the owner brief, and the machine ratify-queue.
// =====================================================================================================
function synthesisGoal(ls) {
  const R = ls.resolved
  const cr = coldreadTokens(R, ls.coldread)
  return `Read ${SP}/LEARN-SYNTHESIS.md and do EXACTLY what it says, substituting:
<LEARN_DIR>      = ${R.LEARN_DIR}
<RUN_ID>         = ${R.RUN_ID}
<SLUG>           = ${R.SLUG}
<MANIFEST>       = ${R.LEARN_DIR}/manifest.json
<ROLLUP>         = ${R.LEARN_DIR}/rollup.json          (may be absent)
<EVIDENCE_PACK>  = ${R.LEARN_DIR}/evidence-pack.md
<REVIEWS>        = ${R.LEARN_DIR}/reviews/             (all *.md + *.index.md)
<VERIFY>         = ${R.LEARN_DIR}/verify/              (per-theme CONFIRMED/ADJUSTED/REFUTED verdicts)
<HYPOTHESES>     = ${R.DOSSIER_HOME}/hypotheses.json   (prior hypotheses to clear; may not exist)
<VENUE_COLDREAD_JSON> = ${cr.json}
<QUALITY_LEDGER> = ${qualityLedgerToken(R)}
<QUALITY_RECORD> = ${R.LEARN_DIR}/quality-record.json  (§3b — this run's ledger record you draft)
<TEMPLATE>       = ${PLUGIN_ROOT}/assets/learn-dossier-template.md
<DOSSIER_HOME>   = ${R.DOSSIER_HOME}                   (create the dir if missing; gap-safe max+1 numbering)
<BRIEF>          = ${R.LEARN_DIR}/dossier-brief.md     (HARD CAP ${L.dossier_brief_max_lines} lines)
<RATIFY_QUEUE>   = ${R.LEARN_DIR}/ratify-queue.json
<HYP_VERDICTS>   = ${R.LEARN_DIR}/hyp-verdicts.json
<PROPOSALS_MAX>  = ${L.proposals_max}
Return the uniform envelope with artifacts=[<dossier path>, <BRIEF>, <RATIFY_QUEUE>, <HYP_VERDICTS>, <QUALITY_RECORD>].`
}
function phaseSynthesis(ls) {
  const R = ls.resolved
  if (!exists(`${R.LEARN_DIR}/ratify-queue.json`)) {                   // idempotent resume
    const env = spawnLearnLeaf('synthesizer', synthesisGoal(ls))
    if (env.status === 'failed') throw new Error('synthesis failed after one resume')
    ls.dossier = (env.artifacts || [])[0] || null
  }
  ls.brief = `${R.LEARN_DIR}/dossier-brief.md`
  ls.ratify_queue = `${R.LEARN_DIR}/ratify-queue.json`
  if (!ls.dossier) ls.dossier = latestDossierIn(R.DOSSIER_HOME)        // resume path: newest NN-run-retro-*.md
  ls.phase = 'ratify'; persistLS(ls)
}

// =====================================================================================================
// P-ratify — deliver the brief ONCE, then one theme-gate per turn (<=4 questions each), then hypotheses.
// =====================================================================================================
// ratify-queue.json (written by the synthesizer; the machine plan L0 gates from):
// { themes: [{ name, dossier_anchor, proposals: [{ id, title, type, severity, urgency, cost,
//              one_liner, expected_signal, how_to_check, options: [labels...] }] }] }
// Every proposal card carries the closed option set: adopt / adopt-modified / defer-someday /
// reject-with-reason / convert — plus the honest option spectrum in the preview (never pre-trim the bold end).
function phaseRatify(ls) {
  const R = ls.resolved
  const Q = readJson(ls.ratify_queue)
  if (!ls.brief_delivered) {
    // [[MECH]] the owner-facing moment this whole command exists for: print the brief VERBATIM (it is
    // written self-contained per the six-section skeleton; capped at L.dossier_brief_max_lines). Do NOT
    // paraphrase it, do NOT re-summarize it — the synthesis leaf owns its quality; L0 only delivers.
    log(readFile(ls.brief))
    ls.brief_delivered = true; persistLS(ls)
  }
  const next = (Q.themes || []).find(t => !ls.gates_done.includes(t.name))
  if (next) {
    // [[MECH]] one theme per gate; <=4 questions per card (AskUserQuestion ceiling). >4 proposals in a
    // theme ⇒ the synthesizer already split it; a malformed queue fails loud here, never silently trims.
    if ((next.proposals || []).length === 0 || next.proposals.length > 4)
      throw new Error(`ratify-queue theme '${next.name}' has ${(next.proposals || []).length} proposals (must be 1-4)`)
    learnGate(ls, `learn-${slugify(next.name)}`, next.proposals.map(p => ({
      id: p.id, question: `${p.title} — ${p.one_liner}`,
      options: p.options,                                              // closed set incl. the bold end
      context: { dossier: ls.dossier, anchor: next.dossier_anchor, expected_signal: p.expected_signal },
    })))                                                               // ends the turn
    return
  }
  if (!ls.gates_done.includes('__hypotheses__') && exists(`${R.LEARN_DIR}/hyp-verdicts.json`)
      && (readJson(`${R.LEARN_DIR}/hyp-verdicts.json`).checks || []).length) {
    // the FINAL card: confirm last cycle's hypothesis verdicts (helped/no-effect/hurt/unmeasurable per
    // open hypothesis, drafted by the synthesizer from run evidence; the owner may overrule any verdict).
    const HV = readJson(`${R.LEARN_DIR}/hyp-verdicts.json`)
    learnGate(ls, 'learn-hypothesis-verdicts', HV.checks.map(c => ({
      id: c.id, question: `${c.id}: ${c.statement} — verdict ${c.verdict}?`,
      options: ['confirm', 'overrule: helped', 'overrule: no-effect', 'overrule: hurt', 'overrule: unmeasurable'],
      context: { evidence: c.evidence },
    })))
    return
  }
  ls.phase = 'record'; persistLS(ls)
}
// ingest — the next-turn dispatcher for /learn's own gates. [[MECH]] mirrors ingestGateAnswer.
function ingestLearnGate(ls, answer) {
  const g = ls.pending_gate; if (!g) return
  if (!answer) answer = readOwnerAnswer(g)                             // chat wins over file; unanswered ⇒ re-present
  if (!answer) return
  if (g.id === 'learn-hypothesis-verdicts') {
    ls.decisions.push({ gate: g.id, answer }); ls.gates_done.push('__hypotheses__')
  } else {
    ls.decisions.push({ gate: g.id, answer })
    const Q = readJson(ls.ratify_queue)
    const t = (Q.themes || []).find(t => `learn-${slugify(t.name)}` === g.id)
    if (t) ls.gates_done.push(t.name)
  }
  archiveLearnGate(ls, summarize(answer))
}

// =====================================================================================================
// P-record — [[MECH]] write the ratified ledger into the dossier + update the hypothesis tracker.
// =====================================================================================================
function phaseRecord(ls) {
  const R = ls.resolved
  const Q = readJson(ls.ratify_queue)
  // 1) append the DECISION LEDGER section to the dossier (the dossier is the FIX SPEC — dossier-12 idiom):
  //    one line per proposal: `**<id> = <owner disposition>**` + verbatim owner notes. [[MECH]] append-only.
  appendDecisionLedger(ls.dossier, Q, ls.decisions)
  // 2) hypothesis tracker: one `add` per ADOPTED proposal (id/expected_signal/how_to_check come from the
  //    ratify-queue entry, owner edits win); one `check` per confirmed prior-hypothesis verdict; all in ONE
  //    atomic patch via bin/learn_hypotheses.py (validated writer — a malformed record can't poison the flywheel).
  const patch = buildHypothesesPatch(Q, ls.decisions, `${R.LEARN_DIR}/hyp-verdicts.json`)
  if (!exists(`${R.DOSSIER_HOME}/hypotheses.json`))
    bash(`python3 "${PLUGIN_ROOT}/bin/learn_hypotheses.py" "${R.DOSSIER_HOME}/hypotheses.json" init`)
  if (patch.ops.length) {
    writeJson(`${R.LEARN_DIR}/hyp-patch.json`, patch)
    const out = bash(`python3 "${PLUGIN_ROOT}/bin/learn_hypotheses.py" "${R.DOSSIER_HOME}/hypotheses.json" apply "${R.LEARN_DIR}/hyp-patch.json"`)
    if (!out.includes('OK')) throw new Error(`hypothesis tracker apply failed: ${out}`)
  }
  // 3) quality ledger: append THIS run's record (the cross-run quality memory). Same validated-writer
  //    discipline as (2); idempotent re-record via if_exists:'amend'. [[MECH]]
  const qpatch = buildQualityPatch(R, ls)
  if (!exists(`${R.DOSSIER_HOME}/quality-ledger.json`))
    bash(`python3 "${PLUGIN_ROOT}/bin/learn_quality_ledger.py" "${R.DOSSIER_HOME}/quality-ledger.json" init`)
  writeJson(`${R.LEARN_DIR}/quality-patch.json`, qpatch)
  const qout = bash(`python3 "${PLUGIN_ROOT}/bin/learn_quality_ledger.py" "${R.DOSSIER_HOME}/quality-ledger.json" apply "${R.LEARN_DIR}/quality-patch.json"`)
  if (!qout.includes('OK')) throw new Error(`quality ledger apply failed: ${qout}`)
  // 4) COMMIT POLICY: /learn never commits (shared-worktree law). Print the exact suggestion and stop.
  log(`DONE. Ratified dossier: ${ls.dossier}\nTracker: ${R.DOSSIER_HOME}/hypotheses.json\nQuality ledger: ${R.DOSSIER_HOME}/quality-ledger.json\n`
    + `Suggested commit (run it yourself):\n  git -C "${R.SOURCE_REPO}" add "${ls.dossier}" "${R.DOSSIER_HOME}/hypotheses.json" "${R.DOSSIER_HOME}/quality-ledger.json" "${R.DOSSIER_HOME}/README.md" && `
    + `git -C "${R.SOURCE_REPO}" commit -m "docs(learning): run-retro ${R.SLUG} — ratified ledger + hypotheses + quality record"`)
  ls.phase = 'done'; persistLS(ls)
}
// [[MECH]] buildQualityPatch — wrap the synthesizer's quality-record.json as ONE idempotent ledger op.
// A degraded/pre-upgrade retro (no record drafted) falls back to a FACTS-ONLY record from the manifest's
// pipeline block: every verdict 'unassessed' + reason (the grounding rule still holds — no judgment here).
function buildQualityPatch(R, ls) {
  const recPath = `${R.LEARN_DIR}/quality-record.json`
  let rec
  if (exists(recPath)) rec = readJson(recPath)
  else {
    const p = (readJson(`${R.LEARN_DIR}/manifest.json`).pipeline) || {}
    const why = 'facts-only record: no quality-record.json drafted (degraded or pre-upgrade retro)'
    rec = { run_facts: { final_status: p.final_status || 'unknown', exit_reason: p.exit_reason || null,
                         loop_rounds: (typeof p.loop_round === 'number') ? p.loop_round : null, venue: p.venue || null },
            claim_arc:     { end_to_end_verdict: 'unassessed', unassessed_reason: why },
            ambition:      { seed_to_contract: 'unassessed', amplifier_arc: 'unassessed', unassessed_reason: why },
            terminal:      { route: 'unknown', outcome: p.final_status || 'unknown' },
            venue_bar:     { cold_verdict: 'unassessed', delta: 'unassessed', unassessed_reason: why },
            ideation_pool: { snapshot: 'absent-pre-upgrade', ceiling_verdict: 'unassessed', unassessed_reason: why } }
  }
  return { ops: [{ op: 'record', if_exists: 'amend',
    run: { ...rec, run_id: R.RUN_ID, slug: R.SLUG || null, recorded_at: now(),
           recorded_by: 'learn-record', retro_ref: ls.dossier ? ls.dossier.split('/').pop() : null } }] }
}

// =====================================================================================================
// MAIN — resume from learn-state; dispatch by phase; persist after every transition.
// =====================================================================================================
function main(target /* optional $ARGUMENTS: run_id prefix | slug | workspace path */) {
  // [[MECH]] startup: resolve FIRST (cheap, read-only) — it pins run_id, which locates learn-state.
  // A pre-existing learn-state for this run resumes it; phases skip forward on their on-disk outputs.
  const probe = bash(`bash "${PLUGIN_ROOT}/bin/learn_resolve.sh" "${DATA_ROOT}" ${target ? quote(target) : ''}`)
  if (firstLine(probe).startsWith('ERROR')) throw new Error(probe)
  const R0 = parseKeyLines(probe)
  let ls = loadLS(R0.RUN_ID)
  if (!ls) ls = { run_id: R0.RUN_ID, phase: 'resolve', resolved: null, reviewers: [], coldread: null,
                  themes: [], dossier: null, brief: null, ratify_queue: null, brief_delivered: false,
                  gates_done: [], decisions: [], pending_gate: null, history: [] }
  if (ls.pending_gate) { ingestLearnGate(ls) }                         // this turn is most likely the INGEST
  while (ls.phase !== 'done') {
    switch (ls.phase) {
      case 'resolve':     phaseResolve(ls, target); break
      case 'manifest':    phaseManifest(ls); break
      case 'evidence':    phaseEvidence(ls); break
      case 'review_wave': phaseReviewWave(ls); break
      case 'verify':      phaseVerify(ls); break
      case 'synthesis':   phaseSynthesis(ls); break
      case 'ratify':      phaseRatify(ls); if (ls.pending_gate) return; break   // gate ended the turn
      case 'record':      phaseRecord(ls); break
    }
  }
  log('LEARN done — 复盘闭环写入完毕。Fixes are built in a SEPARATE session from the ratified dossier; '
    + 'the next /learn checks the hypotheses.')
}
