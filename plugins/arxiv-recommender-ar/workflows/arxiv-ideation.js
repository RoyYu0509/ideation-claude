// arxiv-ideation (workflow B: the VERIFIED-KILL loop) — multi-round idea
// generation for this week's gate survivors, where convergence is earned by
// VERIFICATION ARTIFACTS (executed probes / replayable prior-art / derivation
// checks / real asset listings), never by tier scores. The 2026-07-11 redesign
// that replaced the refine↔judge revision loop: the W27 postmortem showed
// revise-until-tiers-pass is itself the reward-hacked channel (tier upgrades on
// irrelevant lemmas, criticals "resolved" by pinning onto the fatal premise,
// silently relaxed thresholds, fabricated baselines). Here a broken candidate
// cannot be patched into passing — it DIES with evidence (a death certificate),
// and the paper gets a genuinely different candidate or an honest exhaustion.
//
// HARD PRINCIPLE (owner, 2026-07-11): content-level failure = kill, direction
// sealed. NO successor/rescue/revival channel exists at this layer — agents
// exploit any revival channel to keep scientifically meaningless formulas
// alive. The only retry is ONE mechanical bounce per candidate per stage
// (missing file / malformed artifact / probe infra), never a content fix.
//
// EXECUTION MODEL: this file is the LLM-READ SPEC for the /arxiv-scout-beta
// command, which embeds it verbatim and re-enacts it phase by phase AFTER
// workflows/arxiv-scout.js (workflow A). Deterministic control flow, no dead
// branches. INDEPENDENTLY RE-RUNNABLE: reads only workflow A's on-disk outputs.
//
// ON-DISK CONTRACT (inputs, all written by workflow A):
//   data/cache/week-<W>-gated-pool.json   — gate survivors, FULL paper objects.
//                                           FAIL-LOUD if absent.
//   data/cache/week-<W>-judge-cache.json  — claim/repo judge conclusions (tolerant).
//   data/cache/week-<W>-scout.json        — workflow A's manifest; B fills
//                                           ideation_manifest, re-renders digest+web.
//
// OUTPUTS (all under the runtime data root):
//   data/ideations/<W>/<id>.json, <id>-r<R>.json    — per-round generation files
//   data/ideations/<W>/evidence-<id>*.json          — evidence sidecars
//   data/ideations/<W>/bundles/<id>-<cK>/           — verification bundles
//       prior-art.json assets.json probes/*/ theory.md bundle.json recheck-r*.json recheck.json
//   data/ideations/<W>/refined/<id>-idea<N>.md      — one plan per SURVIVOR (N = its place among the paper's converged candidates, ledger order)
//   data/cache/week-<W>-ideation-ledger.json        — THE ledger (candidates, graveyard, resume, /learn)
//
// Round topology (per round; stages lockstep across papers, early-exit per paper):
//   A GENERATE — parallel over papers needing fresh candidates (R1: all active).
//                Honest exhaustion → paper exhausted_honest (self-DROP; unfakeable-for-gain).
//   B SCREEN   — parallel, one agent per paper with fresh candidates: similar-MERGE,
//                prior-art table (replayable S2), asset listings, retread-vs-graveyard.
//                Kills: scooped / retread (an unavailable asset is recorded with a fallback).
//   C PROMOTE  — deterministic: top verify_fanout screen-survivors → verify; rest dormant
//                (dormants are promoted BEFORE any regeneration spend).
//   D VERIFY   — parallel: verifier IMPLEMENTS+EXECUTES probes from the generator's
//                pre-registered criteria, writes theory.md + checks, composes bundle.json
//                (validating writer). Kills: premise_failed / proof_broken / circular — on
//                zero-simulation evidence only; instrument-grade premises are deferred to Phase-0.
//   V0         — zero-token mechanical recheck (scripts/verify_bundle.py via Bash):
//                probe re-execution, S2 replay (set-intersection), asset re-fetch,
//                claim/threshold consistency vs the generator file, drift gates.
//                Mechanical codes bounce ONCE; integrity codes KILL.
//   E RECHECK  — parallel recheck agent + refutation hunter (WebSearch leaf).
//                Kills: insignificant / scooped / any artifact re-check failure.
//                Converged ⇒ paper settles; else promote ≤1 dormant this round.
//   PLAN       — parallel over EVERY survivor (each converged candidate, whatever its paper settled as) → refined .md.
//   FINALIZE   — deterministic: Verification Record + Verified Claim equality check,
//                manifest, digest+web render, rotation history.

export const meta = {
  name: 'arxiv-ideation',
  description: 'Multi-round verified-kill ideation for this week\'s gate survivors: generate → screen → verify (executed probes) → recheck, death-certificate regeneration, artifact-gated convergence. Runs after arxiv-scout (workflow A); independently re-runnable.',
  whenToUse: 'Weekly, after arxiv-scout. Or standalone to (re-)run ideation for a week whose gated pool is still on disk.',
  phases: [
    { title: 'Generate' },
    { title: 'Screen' },
    { title: 'Verify' },
    { title: 'Recheck' },
    { title: 'Plan' },
  ],
}

const { execSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

// --- Resolve plugin root / data root / week (same convention as workflow A) ---
const pluginRoot = (args && args.plugin_root)
  || (typeof process !== 'undefined' && process.env && process.env.CLAUDE_PLUGIN_ROOT)
  || null
if (!pluginRoot) {
  throw new Error('plugin_root must be passed in args (the slash command expands ${CLAUDE_PLUGIN_ROOT})')
}
const dataRoot = (args && (args.data_root || args.project_dir))
  || (typeof process !== 'undefined' && process.env && (process.env.AR_DATA_ROOT || process.env.CLAUDE_PROJECT_DIR))
  || (typeof process !== 'undefined' && process.cwd && process.cwd())   // like bin/run_py.sh — NEVER the plugin dir (a cached plugin dir can hold an old profile of the owner)

function isoWeek(d) {
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))
  const day = t.getUTCDay() || 7
  t.setUTCDate(t.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1))
  const wk = Math.ceil(((t - yearStart) / 86400000 + 1) / 7)
  return `${t.getUTCFullYear()}-W${String(wk).padStart(2, '0')}`
}
const week = (args && args.week) || isoWeek(new Date())

// ── Config: the single strict Python load (no JS-side defaults) ───────────────
function loadConfig(root) {
  const out = execSync(
    `AR_DATA_ROOT="${dataRoot}" python3 -c "import sys,json; sys.path.insert(0,'${root}/scripts'); ` +
    `from lib import config; print(json.dumps(config.load_config('${root}/config/config.yaml').raw))"`,
    { encoding: 'utf8' }
  ).trim()
  return JSON.parse(out)
}
function req(obj, ...path) {
  let n = obj
  for (const k of path) {
    if (n == null || typeof n !== 'object' || !(k in n)) {
      throw new Error(`config/config.yaml missing required key '${path.join('.')}'`)
    }
    n = n[k]
  }
  return n
}
const CFG = loadConfig(pluginRoot)
const KNOBS = req(CFG, 'scout')

const roundsMax = req(KNOBS, 'ideation_rounds_max')
const candidatesPerRound = req(KNOBS, 'candidates_per_round')
const verifyFanout = req(KNOBS, 'verify_fanout')
const survivorTarget = req(KNOBS, 'survivor_target')
const rotationEnabled = !!req(KNOBS, 'rotation_enabled')
const phaseOpts = (name) => {
  const model = req(KNOBS, 'phases', name, 'model') || undefined
  const effort = req(KNOBS, 'phases', name, 'effort') || ''
  return { model, effort }
}
const P = {
  generate: phaseOpts('generate'), regenerate: phaseOpts('regenerate'),
  screen: phaseOpts('screen'), verify: phaseOpts('verify'),
  recheck: phaseOpts('recheck'), recheckTheory: phaseOpts('recheck_theory'),
  refute: phaseOpts('refute'), plan: phaseOpts('plan'),
}
const withEffort = (prompt, effort) => effort ? `${effort}\n\n${prompt}` : prompt
const agentOpts = (p, label, phase, schema) => ({
  label, phase, schema, ...(p.model ? { model: p.model } : {}),
})

const runPy = `AR_DATA_ROOT="${dataRoot}" bash ${pluginRoot}/bin/run_py.sh`
const cacheDir = `${dataRoot}/data/cache`
const scoutJsonPath = `${cacheDir}/week-${week}-scout.json`
const ideationDir = `${dataRoot}/data/ideations/${week}`
const bundlesDir = `${ideationDir}/bundles`
const refinedDir = `${ideationDir}/refined`
const ledgerPath = `${cacheDir}/week-${week}-ideation-ledger.json`

// ── Inputs: workflow A's on-disk contract — FAIL-LOUD on a missing pool ───────
const gatedPoolPath = `${cacheDir}/week-${week}-gated-pool.json`
if (!fs.existsSync(gatedPoolPath)) {
  throw new Error(`arxiv-ideation: ${gatedPoolPath} not found. Workflow A (arxiv-scout.js) must run first ` +
    `for week ${week}, and B must run within scout.cache_stale_days of it. Re-run the scout.`)
}
const gatedPapers = JSON.parse(fs.readFileSync(gatedPoolPath, 'utf8'))
if (!Array.isArray(gatedPapers) || gatedPapers.length === 0) {
  throw new Error(`arxiv-ideation: ${gatedPoolPath} is empty — nothing to ideate.`)
}
const paperById = {}
for (const p of gatedPapers) paperById[p.arxiv_id] = p

// Claim/repo judge conclusions from workflow A (tolerant if absent).
let judgeConclusionsByPaper = {}
try {
  const jc = JSON.parse(fs.readFileSync(`${cacheDir}/week-${week}-judge-cache.json`, 'utf8'))
  for (const [id, entry] of Object.entries(jc)) {
    if (entry && entry.conclusions) judgeConclusionsByPaper[id] = entry.conclusions
  }
} catch (_) { judgeConclusionsByPaper = {} }

// ── Ledger: OWNED BY scripts/ideation_ledger.py (2026-07-12) ───────────────────
// The candidate/paper STATE MACHINE (promote / kill / bounce / converge), the death
// certificates, and the week-<W>-ideation-ledger.json writes are OWNED BY the
// deterministic driver scripts/ideation_ledger.py — NOT by this file and NOT by the
// enactor's memory. (Before: the enactor hand-tracked all state and silently dropped
// persistLedger(), so there was no resume / /learn ledger and the state machine
// self-spun on lost returns.) This file keeps the AGENT-facing spec (schemas +
// spawn-prompt builders below) and the FINALIZE render; every transition goes through a
// driver subcommand (init / begin-round / worklist / apply-* / settle / finalize). The
// on-disk schema is UNCHANGED (schema:2), so scout_digest.py / scout_web.py still render it:
//   { week, schema:2, papers: { <arxiv_id>: { status:'active'|'converged'|
//     'exhausted_honest'|'exhausted_budget', rounds_done, next_candidate_index,
//     exhaustion_note_zh, candidates:{ '<key>':{ round_born, file, idea_index,
//       working_title, claim, direction, direction_zh, status:'generated'|'screened'|
//       'dormant'|'verifying'|'verified'|'converged'|'killed'|'shelved'|'merged'|'error',
//       rank, bundle_dir, bounces, merged_into, artifacts, deferred_premises, recheck,
//       refute, error_note, death? } }, graveyard:[ <death certificate> ] } } }
const ledgerCli = `${runPy} ${pluginRoot}/scripts/ideation_ledger.py`
// READ-ONLY accessors over the driver-written ledger (the driver is the ONLY writer).
// loadLedger() re-reads it from disk; the round loop drives the CLI, then FINALIZE reloads.
function loadLedger() {
  try {
    const l = JSON.parse(fs.readFileSync(ledgerPath, 'utf8'))
    if (l && l.week === week && l.schema === 2 && l.papers) return l
  } catch (_) { /* absent/corrupt → empty view; the driver's `init` (re)builds it */ }
  return { week, schema: 2, papers: {} }
}
let ledger = loadLedger()
const paperState = (id) => ledger.papers[id] || { status: 'active', rounds_done: 0,
  next_candidate_index: 0, exhaustion_note_zh: null, candidates: {}, graveyard: [] }
const cands = (ps, ...statuses) =>
  Object.entries(ps.candidates).filter(([, c]) => statuses.includes(c.status))
const convergedCount = (ps) => cands(ps, 'converged').length

// ── Structured-output schemas ─────────────────────────────────────────────────
const GENERATE_SCHEMA = {
  type: 'object',
  required: ['arxiv_id', 'round', 'candidate_count', 'has_new_directions', 'output_path', 'evidence_path'],
  properties: {
    arxiv_id: { type: 'string' },
    round: { type: 'integer' },
    candidate_count: { type: 'integer', minimum: 0, maximum: candidatesPerRound },
    has_new_directions: { type: 'boolean' },   // false = honest exhaustion (self-DROP; ledgered for /learn)
    exhaustion_note_zh: { type: ['string', 'null'] },
    output_path: { type: 'string' },
    evidence_path: { type: 'string' },
    depth_signal: { type: 'string' },
    notes: { type: 'string' },
  },
}
const SCREEN_SCHEMA = {
  type: 'object',
  required: ['arxiv_id', 'round', 'results'],
  properties: {
    arxiv_id: { type: 'string' },
    round: { type: 'integer' },
    results: {
      type: 'array',
      items: {
        type: 'object',
        required: ['key', 'verdict', 'direction', 'direction_zh'],
        properties: {
          key: { type: 'string' },
          verdict: { type: 'string', enum: ['pass', 'kill', 'merged'] },
          direction: { type: 'string' },       // one-line English mechanism summary
          direction_zh: { type: 'string' },    // 中文一句话(进 digest 死亡名单/卡片)
          rank: { type: 'integer' },           // pass only: 1 = most promising
          kill_reason: { type: 'string', enum: ['scooped', 'retread'] },   // an unavailable asset is recorded with a fallback, never killed
          kill_evidence: { type: 'string' },   // the killing fact, verbatim-quotable
          evidence_path: { type: 'string' },
          retread_of: { type: ['string', 'null'] },
          merged_into: { type: 'string' },     // merged only: surviving candidate key
          dead_belief: { type: ['string', 'null'] },
          regeneration_constraint: { type: ['string', 'null'] },
        },
      },
    },
  },
}
const VERIFY_SCHEMA = {
  type: 'object',
  required: ['arxiv_id', 'key', 'verdict', 'bundle_dir', 'claim', 'claim_type'],
  properties: {
    arxiv_id: { type: 'string' },
    key: { type: 'string' },
    verdict: { type: 'string', enum: ['pass', 'kill', 'rescope', 'error'] },   // rescope = mechanism stands, the given verification route does not exist
    bundle_dir: { type: 'string' },
    claim: { type: 'string' },                 // MUST equal the generator's claim verbatim (V0 enforces)
    claim_type: { type: 'string', enum: ['theoretical', 'empirical', 'both'] },
    deferred_premises: { type: 'integer' },    // uncapped; each becomes a mandatory Phase-0 check downstream
    kill_reason: { type: 'string', enum: ['premise_failed', 'proof_broken'] },
    kill_evidence: { type: 'string' },         // e.g. the PROBE_VERDICT line / broken step
    rescope_note: { type: 'string' },          // verdict=rescope only: the blocked route + what a workable one needs
    evidence_path: { type: 'string' },
    dead_belief: { type: ['string', 'null'] },
    regeneration_constraint: { type: ['string', 'null'] },
    error_note: { type: 'string' },            // verdict=error only: infra reason
  },
}
const RECHECK_SCHEMA = {
  type: 'object',
  required: ['arxiv_id', 'key', 'verdict', 'all_artifacts_reconfirmed', 'artifact_pass', 'significance'],
  properties: {
    arxiv_id: { type: 'string' },
    key: { type: 'string' },
    verdict: { type: 'string', enum: ['pass', 'kill'] },
    all_artifacts_reconfirmed: { type: 'boolean' },
    artifact_pass: {
      type: 'object',
      required: ['prior_art', 'premise_probe', 'derivation_check', 'asset_check'],
      properties: {
        prior_art: { type: 'boolean' }, premise_probe: { type: 'boolean' },
        derivation_check: { type: 'boolean' }, asset_check: { type: 'boolean' },
      },
    },
    significance: { type: 'string', enum: ['paper_worthy', 'borderline', 'incremental'] },
    // REQUIRED (non-null) whenever significance == paper_worthy — the floor can
    // never be awarded without confronting the strongest rival's residual delta.
    significance_confrontation: {
      type: ['object', 'null'],
      properties: {
        strongest_rival_row: { type: 'string' },
        residual_delta_quoted: { type: 'string' },
        why_clears_or_fails: { type: 'string' },
      },
    },
    kill_reason: { type: 'string', enum: ['insignificant', 'premise_failed', 'proof_broken', 'integrity_violation'] },
    kill_evidence: { type: 'string' },
    dead_belief: { type: ['string', 'null'] },
    regeneration_constraint: { type: ['string', 'null'] },
    rationale: { type: 'string' },
  },
}
const REFUTE_SCHEMA = {
  type: 'object',
  required: ['arxiv_id', 'key', 'verdict', 'queries'],
  properties: {
    arxiv_id: { type: 'string' },
    key: { type: 'string' },
    verdict: { type: 'string', enum: ['clear', 'scooped'] },
    queries: { type: 'array', items: { type: 'object', properties: {
      query: { type: 'string' }, hit: { type: ['string', 'null'] } } } },
    killing_hit: { type: ['object', 'null'], properties: {
      title: { type: 'string' }, url: { type: 'string' }, why: { type: 'string' } } },
  },
}
const PLAN_SCHEMA = {
  type: 'object',
  required: ['arxiv_id', 'key', 'output_path', 'seed_preview'],
  properties: {
    arxiv_id: { type: 'string' }, key: { type: 'string' },
    output_path: { type: 'string' }, seed_preview: { type: 'string' },
  },
}

// ── Spawn-prompt builders — thin payloads + skill pointers (skills own the protocol) ──
function ideaFileFor(ps, round) {
  return round === 1 ? `${ideationDir}/%ID%.json` : `${ideationDir}/%ID%-r${round}.json`
}
function buildGeneratePrompt(p, round, ps) {
  const outputPath = ideaFileFor(ps, round).replace('%ID%', p.arxiv_id)
  const evidencePath = round === 1
    ? `${ideationDir}/evidence-${p.arxiv_id}.json`
    : `${ideationDir}/evidence-${p.arxiv_id}-r${round}.json`
  const inputPayload = {
    arxiv_id: p.arxiv_id, title: p.title, abstract: p.abstract || '',
    authors: p.authors || [], categories: p.categories || [],
    why_it_matters: p.why_it_matters, thread_context: p.thread,
    profile_md_path: `${dataRoot}/data/profile/profile.md`,
    profile_threads_path: `${dataRoot}/data/profile/profile.json`,
    week, round, candidates_per_round: candidatesPerRound,
    output_path: outputPath, evidence_path: evidencePath,
  }
  // Judge-cache fields vary by vintage (rationale is often absent) — never render 'undefined' (shakedown F2).
  const jc = judgeConclusionsByPaper[p.arxiv_id] || {}
  const vl = []
  if (jc.claim_verdict) vl.push(`  claim-judge: ${jc.claim_verdict}` +
    (jc.claim_strength ? ` (strength: ${jc.claim_strength})` : '') +
    (jc.claim_rationale ? ` — ${jc.claim_rationale}` : ''))
  if (jc.repo_verdict) vl.push(`  repo-judge: ${jc.repo_verdict}` +
    (jc.repo_rationale ? ` — ${jc.repo_rationale}` : ''))
  const graveyard = ps.graveyard
  return [
    `You are a candidate GENERATOR in the arxiv-ideation verified-kill workflow, week ${week}, round ${round}.`,
    `Invoke the arxiv-generate skill on the paper below — it is the single source of truth for the`,
    `depth floor, the new-artifact bar, the pre-registration obligations (premises with probe_class`,
    `+ criteria, src-tagged falsifier thresholds, asset list), the two output files, and the JSON contract.`,
    round > 1 ? `` : null,
    round > 1 ? `REGENERATION MODE (round ${round}): the graveyard below lists this paper's DEAD directions` : null,
    round > 1 ? `with verified kill evidence. Follow the skill's Regeneration section: produce genuinely` : null,
    round > 1 ? `DIFFERENT directions (a re-tread of a dead direction will be killed by the independent` : null,
    round > 1 ? `screener), or honestly declare exhaustion (has_new_directions=false + exhaustion_note_zh).` : null,
    round > 1 ? `Graveyard (death certificates):` : null,
    round > 1 ? '```json' : null,
    round > 1 ? JSON.stringify(graveyard, null, 1) : null,
    round > 1 ? '```' : null,
    ``,
    `Per-paper input JSON (the skill's "Inputs" contract):`,
    '```json', JSON.stringify(inputPayload, null, 2), '```',
    vl.length ? `Pre-ideation verification signals (context only, not the last word):\n${vl.join('\n')}` : null,
    `Generative-potential signals from the final-rank step (raw material to BUILD from, not holes to patch):`,
    `  Headroom: ${p.extensibility_verdict} — ${p.extensibility_rationale}`,
    `  Adjacent space the paper opens: ${p.gap}`,
    ``,
    `After the skill writes both files, return the structured confirmation. If no genuinely new`,
    `paper-worthy direction exists, return has_new_directions=false with exhaustion_note_zh — an`,
    `honest zero beats a padded candidate.`,
  ].filter(l => l !== null).join('\n')
}

function buildScreenPrompt(p, round, freshList, ps) {
  const payload = {
    arxiv_id: p.arxiv_id, title: p.title, week, round,
    plugin_root: pluginRoot, data_root: dataRoot,
    bundles_dir: bundlesDir,
    candidates: freshList.map(([key, c]) => ({
      key, ideas_file: c.file, idea_index: c.idea_index,
    })),
    graveyard: ps.graveyard,
  }
  return [
    `You are the independent SCREENER for paper ${p.arxiv_id} in the arxiv-ideation verified-kill`,
    `workflow, week ${week}, round ${round}. You did NOT generate these candidates and have no stake`,
    `in any surviving. Invoke the arxiv-screen skill and reproduce it exactly — it owns the`,
    `similar-merge rule, the prior-art artifact contract (replayable S2 queries + diff table +`,
    `dispositions, written to <bundles_dir>/<arxiv_id>-<key>/prior-art.json), the asset-listing`,
    `contract (bin/asset_listing.sh, real file listings), the retread check against the graveyard,`,
    `and the kill conditions (scooped / retread; an unavailable asset is recorded with a fallback, never killed).`,
    ``,
    `Input JSON (the skill's "Inputs" contract):`,
    '```json', JSON.stringify(payload, null, 2), '```',
    ``,
    `Return the structured results array — one entry per candidate (pass with rank / kill with the`,
    `killing evidence / merged with merged_into). Rank pass-survivors by promise (1 = best).`,
  ].join('\n')
}

function buildVerifyPrompt(p, key, c, bounceNote) {
  const bundleDir = `${bundlesDir}/${p.arxiv_id}-${key}`
  const payload = {
    arxiv_id: p.arxiv_id, key, week,
    ideas_file: c.file, idea_index: c.idea_index,
    evidence_file: c.file.includes('-r')
      ? c.file.replace(/\/(\d{4}\.\d{4,5})-r(\d+)\.json$/, '/evidence-$1-r$2.json')
      : c.file.replace(/\/(\d{4}\.\d{4,5})\.json$/, '/evidence-$1.json'),
    bundle_dir: bundleDir, plugin_root: pluginRoot, data_root: dataRoot,
  }
  return [
    `You are the adversarial VERIFIER for candidate ${p.arxiv_id}:${key} in the arxiv-ideation`,
    `verified-kill workflow, week ${week}. You did NOT generate this candidate; your job is to try`,
    `to KILL it with executed evidence. Invoke the arxiv-verify skill and reproduce it exactly — it`,
    `owns the probe-implementation contract (YOU implement and EXECUTE the probes from the`,
    `generator's pre-registered criteria via bin/probe_run.sh — the producer never runs its own`,
    `probe), the probe-REQUIRED rules, the theory.md typed-step derivation + sympy/numpy checks,`,
    `the falsifier limit analysis, the deferred-premise rule (uncapped; defer anything needing an`,
    `instrument you do not have — never settle it with a self-written simulator), and the`,
    `bundle.json composition through the validating writer.`,
    bounceNote ? `` : null,
    bounceNote ? `MECHANICAL BOUNCE (one-time): the previous attempt failed mechanical recheck. Fix ONLY` : null,
    bounceNote ? `these mechanical defects — the candidate's content (claim, thresholds, premises) must` : null,
    bounceNote ? `not change:\n${bounceNote}` : null,
    ``,
    `Input JSON (the skill's "Inputs" contract):`,
    '```json', JSON.stringify(payload, null, 2), '```',
    ``,
    `Return the structured verdict. A probe that REFUTES a required premise is a successful`,
    `verification with verdict=kill (kill_reason=premise_failed, kill_evidence=the PROBE_VERDICT`,
    `line, dead_belief=the world-belief that died, regeneration_constraint=what any new idea on`,
    `this paper must avoid or probe first). verdict=error is ONLY for infrastructure failures.`,
  ].filter(l => l !== null).join('\n')
}

function buildRecheckPrompt(p, key, c, v0Path) {
  const payload = {
    arxiv_id: p.arxiv_id, key, week,
    bundle_dir: c.bundle_dir, ideas_file: c.file, idea_index: c.idea_index,
    v0_recheck_path: v0Path, plugin_root: pluginRoot, data_root: dataRoot,
    webfetch_max: req(KNOBS, 'recheck_webfetch_max'),
  }
  return [
    `You are the independent RECHECKER for candidate ${p.arxiv_id}:${key} in the arxiv-ideation`,
    `verified-kill workflow, week ${week}. You did NOT write this bundle and have NO stake in it`,
    `converging. The zero-token mechanical recheck (V0) already re-executed probes and replayed`,
    `searches — its report is at v0_recheck_path. Invoke the arxiv-recheck skill and reproduce it`,
    `exactly — it owns the semantic re-checks that need READING bound to fetchable ground truth:`,
    `quote-vs-PDF, probe↔premise correspondence (claim-correspondence + input non-degeneracy),`,
    `the fabricated-number sweep (every quantitative claim's src fetched and TRANSCRIBED), the`,
    `theory-step re-derivation, and the significance floor (categorical; paper_worthy REQUIRES a`,
    `non-null significance_confrontation against the diff table's strongest rival).`,
    ``,
    `Input JSON (the skill's "Inputs" contract):`,
    '```json', JSON.stringify(payload, null, 2), '```',
    ``,
    `Return the structured verdict JSON only — the workflow owns all convergence decisions.`,
  ].join('\n')
}

function buildRefutePrompt(p, key, c) {
  const payload = {
    arxiv_id: p.arxiv_id, key, week,
    bundle_dir: c.bundle_dir, claim: c.claim || '',
    plugin_root: pluginRoot, data_root: dataRoot,
  }
  return [
    `You are the REFUTATION HUNTER for candidate ${p.arxiv_id}:${key} in the arxiv-ideation`,
    `verified-kill workflow, week ${week}. Invoke the arxiv-refute skill and reproduce it exactly —`,
    `2–4 WebSearch queries hunting what KILLS this mechanism (known negative results, fundamental`,
    `obstructions, concurrent work S2 cannot see, already-closed gaps). WebSearch is open at THIS`,
    `leaf only. A decisive hit ⇒ verdict=scooped with killing_hit.`,
    ``,
    `Input JSON (the skill's "Inputs" contract):`,
    '```json', JSON.stringify(payload, null, 2), '```',
  ].join('\n')
}

function buildPlanPrompt(p, key, c, n) {
  const outputPath = `${refinedDir}/${p.arxiv_id}-idea${n || 0}.md`   // idea<N> = the paper's N-th survivor (see PLAN)
  const payload = {
    arxiv_id: p.arxiv_id, key, week, title: p.title,
    ideas_file: c.file, idea_index: c.idea_index,
    bundle_dir: c.bundle_dir,
    profile_md_path: `${dataRoot}/data/profile/profile.md`,
    profile_threads_path: `${dataRoot}/data/profile/profile.json`,
    output_path: outputPath, plugin_root: pluginRoot, data_root: dataRoot,
  }
  return [
    `You are the PLAN AUTHOR for the verified survivor ${p.arxiv_id}:${key} in the arxiv-ideation`,
    `workflow, week ${week}. This candidate's verification bundle passed every artifact + the`,
    `independent recheck. Invoke the arxiv-plan skill and reproduce it exactly — it owns the plan`,
    `structure (Novelty/Prior-Art from the bundle's diff table, Premise Ledger with probe evidence,`,
    `Sections 0–4 content WITHOUT tier lines, the '## Verified Claim' block that must copy the`,
    `bundle claim VERBATIM, and the /research Seed template). You write the plan around the`,
    `verified evidence — you may not re-open, weaken, or extend the claim.`,
    ``,
    `Input JSON (the skill's "Inputs" contract):`,
    '```json', JSON.stringify(payload, null, 2), '```',
  ].join('\n')
}

// ── Driver wiring — scripts/ideation_ledger.py owns the state machine + the ledger ──
// V0 (verify_bundle.py) runs INSIDE the driver's apply-verify, so the verified/bounce/
// kill branch is code, not an enactor's guess. The owner quality-gate pruning
// (week-<W>-quality-gate-decision.json) is honored by the driver's promote step. Every
// call re-reads/re-writes the on-disk ledger — the SINGLE source of truth (never memory).
const drive = (sub, extra = '') => {
  const out = execSync(`${ledgerCli} ${sub} --week ${week} ${extra}`, { encoding: 'utf8' })
  // The driver prints exactly one JSON status line LAST; parse that line so any
  // run_py.sh / first-call venv-bootstrap noise on earlier lines can't break the parse.
  const lines = out.trim().split('\n').filter(l => l.trim())
  return JSON.parse(lines[lines.length - 1])
}
const driveWithResult = (sub, round, results, extraFlags = '') => {
  const f = `${cacheDir}/week-${week}-ideation-${sub}-r${round}.result.json`
  fs.writeFileSync(f, JSON.stringify(results))
  return drive(sub, `--round ${round} --result ${f} ${extraFlags}`)
}
// A worklist item already carries the driver-resolved file/idea_index/claim/bundle_dir;
// the prompt builders take a `c`-shaped object, so adapt an item in place.
const cOf = (it) => ({ file: it.ideas_file, idea_index: it.idea_index,
  claim: it.claim, bundle_dir: it.bundle_dir, claim_type: it.claim_type })

// ── THE ROUND LOOP — driven by scripts/ideation_ledger.py (2026-07-12) ─────────
// The candidate/paper state machine, the ledger writes, the V0 branch, and every
// promote/kill/bounce/converge transition are OWNED BY THE DRIVER. This loop only:
// (1) asks the driver for the next batch (worklist), (2) spawns it with the prompt
// builders above — AWAITED IN-TURN (one message, many Task calls; NO detached/waiter
// spawns — the L1 orchestrator is headless with no self-rewake), (3) pipes the awaited
// returns back (apply-*). It never tracks candidate state and never writes the ledger.
drive('init', `--gated-pool ${gatedPoolPath}`)

for (let round = 1; round <= roundsMax; round++) {
  // begin-round requeues last round's infra-error candidates (an infra error is not a
  // verdict) and returns the active-paper set; empty ⇒ every paper has settled.
  const begun = drive('begin-round', `--round ${round}`)
  if (begun.active_papers.length === 0) break
  log(`── Round ${round}/${roundsMax} — ${begun.active_papers.length} active paper(s)`)

  // A. GENERATE — the driver names the papers needing fresh candidates (round 1: all
  //    active; rounds 2+: regeneration with each paper's graveyard injected). Honest
  //    exhaustion (has_new_directions:false) self-DROPs the paper inside apply-generate.
  phase('Generate')
  const genWl = drive('worklist', `--round ${round} --stage generate`)
  if (genWl.count > 0) {
    log(`Round ${round} A-GENERATE — ${genWl.count} paper(s)`)
    const opts = round === 1 ? P.generate : P.regenerate
    const genOut = await parallel(genWl.items.map(it => () => agent(
      withEffort(buildGeneratePrompt(paperById[it.arxiv_id], round, { graveyard: it.graveyard || [] }), opts.effort),
      agentOpts(opts, `generate:${it.arxiv_id}:r${round}`, 'Generate', GENERATE_SCHEMA)
    )))
    // apply-generate reads each idea file, registers candidates c<next++>, and settles
    // exhausted_honest papers — all deterministic, all persisted by the driver.
    driveWithResult('apply-generate', round, genOut.filter(Boolean))
  }

  // B. SCREEN — one leaf per paper with fresh 'generated' candidates (the driver lists
  //    them + the paper's graveyard for the retread check). apply-screen owns the
  //    kill/merge/rank verdicts + death certificates; unmentioned candidates re-screen.
  phase('Screen')
  const scrWl = drive('worklist', `--round ${round} --stage screen`)
  if (scrWl.count > 0) {
    log(`Round ${round} B-SCREEN — ${scrWl.count} paper(s)`)
    const screenOut = await parallel(scrWl.items.map(it => () => agent(
      withEffort(buildScreenPrompt(paperById[it.arxiv_id], round,
        it.candidates.map(c => [c.key, { file: c.ideas_file, idea_index: c.idea_index }]),
        { graveyard: it.graveyard || [] }), P.screen.effort),
      agentOpts(P.screen, `screen:${it.arxiv_id}:r${round}`, 'Screen', SCREEN_SCHEMA)
    )))
    driveWithResult('apply-screen', round, screenOut.filter(Boolean))
  }

  // R1 only: write the owner quality-gate request from the driver-written ledger (prune
  // BEFORE deep verification: copy to …-decision.json, trim selected_ideas, re-run). Once.
  if (round === 1) {
    const l = loadLedger(), allKeys = []
    for (const [aid, ps] of Object.entries(l.papers)) {
      for (const [key, c] of Object.entries(ps.candidates)) {
        if (['screened', 'dormant', 'verifying', 'verified', 'converged'].includes(c.status)) {
          allKeys.push({ arxiv_id: aid, key, claim_preview: (c.claim || '').slice(0, 120) })
        }
      }
    }
    const qgPath = `${cacheDir}/week-${week}-quality-gate.json`
    if (allKeys.length > 0 && !fs.existsSync(qgPath)) {
      fs.writeFileSync(qgPath, JSON.stringify({
        week, generated_at_utc: new Date().toISOString(),
        usage: `To prune: copy to week-${week}-quality-gate-decision.json, trim selected_ideas (keys are ledger candidate keys), re-run.`,
        selected_ideas: allKeys,
      }, null, 2))
      log(`Quality-gate request written (${allKeys.length} candidate(s))`)
    }
  }

  // C→E. Verification chain — 2 passes max per round (pass 2 promotes ≤1 dormant per
  // paper). `worklist --stage verify` PROMOTES inside the driver (top verify_fanout →
  // verifying, the rest → dormant) then names the candidates to (re)verify; apply-verify
  // runs V0 (verify_bundle.py) and returns any one-time mechanical bounce; apply-recheck
  // converges/kills (significance floor) and settles the paper. Every decision is code-owned.
  for (let pass = 1; pass <= 2; pass++) {
    phase('Verify')
    const verWl = drive('worklist', `--round ${round} --stage verify`)
    if (verWl.count === 0) break
    log(`Round ${round}.${pass} D-VERIFY — ${verWl.count} candidate(s)`)
    const verifyOut = await parallel(verWl.items.map(it => () => agent(
      withEffort(buildVerifyPrompt(paperById[it.arxiv_id], it.key, cOf(it), null), P.verify.effort),
      agentOpts(P.verify, `verify:${it.arxiv_id}:${it.key}`, 'Verify', VERIFY_SCHEMA)
    )))
    const av = driveWithResult('apply-verify', round, verifyOut.filter(Boolean))
    // One mechanical bounce per candidate (content frozen); integrity/repeat V0 failures KILL — driver-decided.
    if (av.bounce_items && av.bounce_items.length > 0) {
      log(`Round ${round}.${pass} — ${av.bounce_items.length} V0 mechanical bounce(s) (one-time)`)
      const bounceOut = await parallel(av.bounce_items.map(it => () => agent(
        withEffort(buildVerifyPrompt(paperById[it.arxiv_id], it.key, cOf(it), it.bounce_note), P.verify.effort),
        agentOpts(P.verify, `verify:${it.arxiv_id}:${it.key}:bounce`, 'Verify', VERIFY_SCHEMA)
      )))
      driveWithResult('apply-verify', round, bounceOut.filter(Boolean), '--bounce')
    }

    // E. RECHECK ∥ REFUTE — 2 leaves per verified candidate, one flat in-turn-awaited batch.
    phase('Recheck')
    const recWl = drive('worklist', `--round ${round} --stage recheck`)
    if (recWl.count > 0) {
      log(`Round ${round}.${pass} E-RECHECK — ${recWl.count} candidate(s)`)
      const pairOut = await parallel(recWl.items.flatMap(it => {
        const recheckOpts = (it.claim_type === 'theoretical' || it.claim_type === 'both')
          ? P.recheckTheory : P.recheck
        const v0Path = `${it.bundle_dir}/recheck-r${round}.json`
        return [
          () => agent(withEffort(buildRecheckPrompt(paperById[it.arxiv_id], it.key, cOf(it), v0Path), recheckOpts.effort),
                      agentOpts(recheckOpts, `recheck:${it.arxiv_id}:${it.key}`, 'Recheck', RECHECK_SCHEMA)),
          () => agent(withEffort(buildRefutePrompt(paperById[it.arxiv_id], it.key, cOf(it)), P.refute.effort),
                      agentOpts(P.refute, `refute:${it.arxiv_id}:${it.key}`, 'Recheck', REFUTE_SCHEMA)),
        ]
      }))
      // Pair the two returns per candidate and hand them to the driver, which owns the
      // scooped / significance-floor / artifact-recheck kill rules and the converge decision.
      const recResults = recWl.items.map((it, i) => ({
        arxiv_id: it.arxiv_id, key: it.key,
        recheck: pairOut[2 * i] || null, refute: pairOut[2 * i + 1] || null,
      }))
      driveWithResult('apply-recheck', round, recResults)
    }
    drive('settle', `--round ${round}`)
  }
}

// Round cap + manifest: the driver settles still-active papers as exhausted_budget and
// shelves their unspent candidates. Reload its FINAL ledger for the PLAN + FINALIZE render
// below — the driver is the ONLY writer; every transition above already persisted per stage.
drive('finalize', '')
ledger = loadLedger()

// ── PLAN — one plan author per SURVIVOR ───────────────────────────────────────
// (2026-09-12, owner decision: every surviving idea is kept, and the owner picks ONE at /auto-research's GATE-1.)
// This used to be one plan per CONVERGED paper, for its first survivor only. A paper reaches status 'converged'
// only at survivor_target survivors, which a short week rarely does — W33/W35 shipped 0 plans for 11/8 survivors —
// and a paper's other survivors were dropped before anyone saw them. Now every converged candidate gets a plan,
// whatever its paper settled as. A paper's survivors are numbered in LEDGER order: idea0 = its first converged
// candidate (the old single plan, so existing files keep their meaning), then idea1, idea2, … — research.js
// seedFreshness and scripts/lib/scout_web.py index the same way.
phase('Plan')
const convergedPapers = gatedPapers.filter(p => paperState(p.arxiv_id).status === 'converged')   // rotation history below
const survivors = gatedPapers.flatMap(p =>
  cands(paperState(p.arxiv_id), 'converged').map(([key, c], n) => ({ p, key, c, n })))
const planPath = (s) => `${refinedDir}/${s.p.arxiv_id}-idea${s.n}.md`
log(`PLAN — ${survivors.length} survivor(s) across ${new Set(survivors.map(s => s.p.arxiv_id)).size} paper(s)`)
const planJobs = survivors.filter(s => !fs.existsSync(planPath(s)))   // resume: an existing refined plan skips re-authoring
const planOut = planJobs.length > 0
  ? await parallel(planJobs.map(j => () => agent(
      withEffort(buildPlanPrompt(j.p, j.key, j.c, j.n), P.plan.effort),
      agentOpts(P.plan, `plan:${j.p.arxiv_id}:${j.key}`, 'Plan', PLAN_SCHEMA)
    )))
  : []
planJobs.forEach((j, i) => {
  if (!planOut[i]) log(`PLAN — ${j.p.arxiv_id}:${j.key}: plan author returned nothing (re-run workflow B to retry)`)
})

// ── FINALIZE (all JS-deterministic; no agent prose reaches these blocks) ──────
// 1) '## Verified Claim' equality check — the plan author must copy the bundle
//    claim verbatim; drift is overwritten with the canonical claim and flagged
//    (fail-visible, ledgered for /learn).
// 2) '## Verification Record' — derived from bundle.json + recheck + refute +
//    graveyard, inserted BEFORE '## /research Seed' (seed stays byte-compatible).
const SEED_MARKER = '## /research Seed'
const VC_MARKER = '## Verified Claim'
const VR_MARKER = '## Verification Record'
function verificationRecordBlock(p, ps, key, c) {
  const rc = c.recheck || {}
  const ap = rc.artifact_pass || {}
  const passCount = ['prior_art', 'premise_probe', 'derivation_check', 'asset_check']
    .filter(k => ap[k]).length
  let bundle = null
  try { bundle = JSON.parse(fs.readFileSync(`${c.bundle_dir}/bundle.json`, 'utf8')) } catch (_) {}
  const probeLines = []
  for (const r of ((bundle && bundle.premises && bundle.premises.rows) || [])) {
    if (r.status === 'probed_pass' || r.status === 'probed_fail') {
      probeLines.push(`  - ${r.id} \`${r.probe.criterion.metric}\` → **${r.status}** (probe: \`${r.probe.dir}\`)`)
    } else if (r.status === 'deferred') {
      probeLines.push(`  - ${r.id} **DEFERRED** (weekly-cost-undecidable; auto-becomes a Phase-0 kill check downstream): ${r.deferred_justification}`)
    }
  }
  const queries = ((bundle && bundle.prior_art && bundle.prior_art.queries) || [])
    .filter(q => q.tool === 's2_novelty').map(q => `\`${q.query || ('related:' + q.arxiv_id)}\``)
  const killed = ps.graveyard.map(g => `  - ${g.direction_zh || g.direction} — ${g.kill_reason}(${g.stage})`)
  const conf = rc.significance_confrontation || {}
  return [
    VR_MARKER, '',
    `> Machine-derived from bundle.json + independent recheck — no producer prose. SUPERSEDES any self-assessment.`,
    '',
    `- **Artifacts:** ${passCount}/4 pass (prior-art / premise-probe / derivation / assets), V0 re-execution + independent recheck reconfirmed`,
    ...(probeLines.length ? [`- **Executed probes:**`, ...probeLines] : []),
    `- **Prior-art queries (replayable):** ${queries.join(', ') || 'n/a'}`,
    `- **Refutation hunt:** ${(c.refute && c.refute.verdict) === 'clear' ? 'clear (no killing hit)' : 'see ledger'}`,
    `- **Significance floor:** ${rc.significance}${conf.strongest_rival_row ? ` — confronted vs ${conf.strongest_rival_row}: ${conf.why_clears_or_fails || conf.residual_delta_quoted || ''}` : ''}`,
    `- **Deferred probes:** ${c.deferred_premises || 0}`,
    ...(killed.length ? [`- **本文被验证否决的其他方向 (${killed.length}):**`, ...killed] : []),
    '',
  ].join('\n')
}
for (const s of survivors) {
  const { p, key, c } = s
  const ps = paperState(p.arxiv_id)
  const mdPath = planPath(s)
  if (!fs.existsSync(mdPath)) continue
  try {
    let md = fs.readFileSync(mdPath, 'utf8')
    let bundle = null
    try { bundle = JSON.parse(fs.readFileSync(`${c.bundle_dir}/bundle.json`, 'utf8')) } catch (_) {}
    const canonicalClaim = (bundle && bundle.claim || c.claim || '').trim()
    // (1) Verified Claim equality check
    const vcIdx = md.indexOf(VC_MARKER)
    let written = null
    if (vcIdx !== -1) {
      const rest = md.slice(vcIdx + VC_MARKER.length)
      const end = rest.search(/\n## /)
      written = (end === -1 ? rest : rest.slice(0, end)).trim()
    }
    if (written !== canonicalClaim) {
      c.verified_claim_drift = written !== null
      if (written !== null) log(`⚠ ${p.arxiv_id}: '## Verified Claim' drifted from the bundle claim — overwriting with canonical (flagged for /learn)`)
      // strip any existing block, then insert canonical before the seed
      if (vcIdx !== -1) {
        const rest = md.slice(vcIdx + VC_MARKER.length)
        const end = rest.search(/\n## /)
        md = md.slice(0, vcIdx) + (end === -1 ? '' : rest.slice(end + 1))
      }
      const sIdx0 = md.indexOf(SEED_MARKER)
      const vcBlock = `${VC_MARKER}\n\n${canonicalClaim}\n\n`
      md = sIdx0 !== -1
        ? md.slice(0, sIdx0).replace(/\s*$/, '\n\n') + vcBlock + md.slice(sIdx0)
        : md.replace(/\s*$/, '\n\n') + vcBlock
    }
    // (2) Verification Record (idempotent re-render)
    const vrIdx = md.indexOf(VR_MARKER)
    if (vrIdx !== -1) {
      const afterVr = md.indexOf(SEED_MARKER, vrIdx)
      md = afterVr !== -1 ? md.slice(0, vrIdx) + md.slice(afterVr) : md.slice(0, vrIdx)
    }
    const block = verificationRecordBlock(p, ps, key, c)
    const sIdx = md.indexOf(SEED_MARKER)
    md = sIdx !== -1
      ? md.slice(0, sIdx).replace(/\s*$/, '\n\n') + block + '\n' + md.slice(sIdx)
      : md.replace(/\s*$/, '\n\n') + block
    fs.writeFileSync(mdPath, md)
  } catch (e) { log(`Finalize blocks failed for ${p.arxiv_id} (non-fatal): ${e.message}`) }
}

// ── Manifest update + digest/web re-render ────────────────────────────────────
if (!fs.existsSync(scoutJsonPath)) {
  throw new Error(`arxiv-ideation: ${scoutJsonPath} not found — workflow A's manifest is required for the re-render.`)
}
const manifest = JSON.parse(fs.readFileSync(scoutJsonPath, 'utf8'))
manifest.ideation_manifest = gatedPapers.map(p => {
  const ps = paperState(p.arxiv_id)
  const conv = cands(ps, 'converged')
  return {
    arxiv_id: p.arxiv_id,
    status: ps.status,
    idea_count: conv.length,
    has_journal_level_idea: conv.length > 0,
    output_path: conv.length ? conv[0][1].file : null,
    evidence_path: null,
    killed_directions: ps.graveyard.length,
    exhaustion_note_zh: ps.exhaustion_note_zh,
  }
})
manifest.ideation_completed_at_utc = new Date().toISOString()
manifest.ideation_ledger = `data/cache/week-${week}-ideation-ledger.json`
fs.writeFileSync(scoutJsonPath, JSON.stringify(manifest, null, 2))
log(`Updated scout JSON with ideation manifest: ${scoutJsonPath}`)

execSync(`${runPy} ${pluginRoot}/scripts/lib/scout_digest.py --week ${week}`, { stdio: 'inherit' })
execSync(`${runPy} ${pluginRoot}/scripts/lib/scout_web.py --week ${week} --no-open`, { stdio: 'inherit' })
log(`Re-rendered digest + web report: data/web/${week}-scout.html`)

// Cross-week rotation: record which threads got a deep dive (idempotent per week).
if (rotationEnabled) {
  try {
    const m = String(week).match(/(\d{4})-W(\d{1,2})/)
    const idx = m ? (parseInt(m[1], 10) * 53 + parseInt(m[2], 10)) : 0
    const historyPath = `${cacheDir}/thread-coverage-history.json`
    let h = { version: 1, last_deep_dive: {}, history: [] }
    try { h = JSON.parse(fs.readFileSync(historyPath, 'utf8')) } catch (_) {}
    const convergedIds = new Set(convergedPapers.map(p => p.arxiv_id))
    const threadsThisWeek = [...new Set(gatedPapers.filter(p => convergedIds.has(p.arxiv_id)).map(p => p.thread).filter(Boolean))]
    for (const t of threadsThisWeek) h.last_deep_dive[t] = idx
    h.history = [{ week, week_idx: idx, deep_dive_threads: threadsThisWeek },
                 ...(h.history || []).filter(e => e.week !== week)].slice(0, 12)
    fs.writeFileSync(historyPath, JSON.stringify(h, null, 2))
    log(`Rotation history updated: ${threadsThisWeek.length} thread(s)`)
  } catch (e) { log(`Rotation history write skipped: ${e.message}`) }
}

// ── Return ────────────────────────────────────────────────────────────────────
const statusCounts = {}
for (const p of gatedPapers) {
  const st = paperState(p.arxiv_id).status
  statusCounts[st] = (statusCounts[st] || 0) + 1
}
const totalKilled = gatedPapers.reduce((s, p) => s + paperState(p.arxiv_id).graveyard.length, 0)
log(`Done — papers: ${JSON.stringify(statusCounts)}; directions killed with evidence: ${totalKilled}`)

return {
  week,
  digest_path: `data/digests/${week}-scout.md`,
  web_report_path: `data/web/${week}-scout.html`,
  scout_json: `data/cache/week-${week}-scout.json`,
  ideations_dir: `data/ideations/${week}`,
  ideation_ledger: `data/cache/week-${week}-ideation-ledger.json`,
  papers: gatedPapers.map(p => {
    const ps = paperState(p.arxiv_id)
    const convs = cands(ps, 'converged').map(([key, c], n) => ({
      key, claim: c.claim,
      refined_path: `data/ideations/${week}/refined/${p.arxiv_id}-idea${n}.md`,
      deferred_premises: c.deferred_premises || 0,
    }))
    return {
      arxiv_id: p.arxiv_id, status: ps.status,
      survivor: convs[0] || null,      // the first survivor (back-compat); `survivors` lists every one
      survivors: convs,
      killed_directions: ps.graveyard.length,
      exhaustion_note_zh: ps.exhaustion_note_zh,
    }
  }),
  next_step: `Open data/web/${week}-scout.html — each survivor shows its plan + the machine-derived ` +
    `Verification Record (executed probes, replayable queries, kill history). Copy any /research seed ` +
    `from data/ideations/${week}/refined/ and run /research <paste> — or run /auto-research, whose ` +
    `GATE-1 surfaces the Verification Records (a freshness re-check runs at the gate; the deep ` +
    `verification already happened HERE, so picked seeds go straight to HANDOFF).`,
}
