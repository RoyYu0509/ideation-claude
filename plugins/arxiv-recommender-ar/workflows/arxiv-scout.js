// arxiv-scout (workflow A: RECOMMEND) — fetch this week's arXiv papers,
// rank against the researcher profile, gate them through the claim/repo judges,
// and render a papers-only digest/web report.
//
// IDEATION MOVED OUT (2026-07-08; 2026-07-11 verified-kill redesign): ideation
// lives in workflows/arxiv-ideation.js (workflow B — multi-round generate →
// screen → verify → recheck with executed probes and death-certificate
// regeneration), which reads THIS workflow's on-disk outputs
// (week-<W>-gated-pool.json + week-<W>-judge-cache.json) and can be run/re-run
// independently. The command enacts A then B consecutively. (The WeChat
// publishing phase was retired 2026-08-30 — the plugin lives in inactive/.)
//
// EXECUTION MODEL: this file is the LLM-READ SPEC for the /arxiv-scout-beta
// command, which embeds it verbatim and re-enacts it phase by phase (the
// former Workflow-VM registration is retired). Deterministic control flow,
// no dead branches — every line here is something the enactor must do.
//
// All pipeline knobs (spawn count, thresholds, rounds, etc.) are read from
// config/config.yaml → scout: block at startup. Edit that file to tune.
//
// Topology:
//   Phase 0 Profile Rebuild (optional) — triggered when user input contains
//                         profile-rebuild intent (e.g. "update my profile").
//                         0a: build_profile_papers.py (S2 fetch + dedup + supplement merge).
//                         0b: website cross-check agent (if researcher.personal_website set).
//                         0c: arxiv-profile skill agent (NL profile generation).
//   Phase 1 Fetch       — cache cleanup (>cache_stale_days entries) + ingest
//                         script chosen by io.ingest_method: oai → oai_ingest.py
//                         (VPS/OAI-PMH); api → build_shared_cache.py (Mac/API).
//   Phase 2 Score       — execSync prefetch.py --top-k prefetch_top_k
//                         (SPECTER2 + BM25 + citation, fused via RRF).
//   Phase 3 Final Rank  — 3a the delivered reading list (the fused order's first TOP_K) is
//                         PARTITIONED by owning thread: a paper belongs to the thread that ranks
//                         it highest (scripts/lib/thread_seed.py). Deterministic, no LLM call.
//   Phase 3.6 Judge Gate — the seed walk. Each thread takes the FIRST paper it owns that passes
//                         the gate: claim judge per paper (Stage 1 — integrity, claim strength and
//                         the extensibility tier, all from one full-text read), then repo judge for
//                         repo-active papers (Stage 2). FAIL-CLOSED: inconclusive drops at both
//                         judges; a mediocre claim_strength drops (strength floor); a tier below
//                         extensibility_gate drops. Rounds exist only because a seed is defined by
//                         a verdict: round r judges every seedless thread's r-th paper in ONE
//                         parallel barrier, then assigns. Ownership is a partition, so two threads
//                         can never nominate one paper. A thread whose papers are all rejected ends
//                         with no seed and the vacancy is logged, never filled. Verdicts are
//                         disk-cached per week (crash-resume never re-judges). Pinned papers are
//                         exempt. The seeds are persisted to week-<W>-gated-pool.json — the
//                         contract file workflow B (arxiv-ideation.js) reads.
//                         3c the arxiv-rerank skill then writes the seeds' rationales.
//   (render)            — papers-only manifest (top_papers = gate survivors,
//                         ideation_manifest: []) + digest + web report. Workflow B
//                         re-renders both with ideas after it runs.

export const meta = {
  name: 'arxiv-scout',
  description: 'Fetch this week\'s arXiv papers, rank against the researcher profile, judge-gate the pool, and render a papers-only digest. Ideation/refinement moved to the arxiv-ideation workflow (run after this one).',
  whenToUse: 'Weekly. Bundles the manual fetch + the existing /weekly-papers pipeline into one deterministic workflow. Add "update my profile" / "rebuild profile" to the invocation to trigger profile refresh before the scout run. Follow with workflows/arxiv-ideation.js for idea generation.',
  phases: [
    { title: 'Profile Rebuild', optional: true },
    { title: 'Fetch' },
    { title: 'Inject pinned papers', optional: true },
    { title: 'Score' },
    { title: 'Final Rank' },
    { title: 'Judge Gate', optional: true },
  ],
}

// Node built-ins for zero-token shell-outs + file I/O. HARD-REQUIRED — there
// is no degraded mode: if require is unavailable this spec fails at load,
// loudly. (The /arxiv-scout-beta enactor's own Bash/Read/Write tools play
// these roles when re-enacting; it never needs a fallback branch here.)
const { execSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

// --- Resolve plugin root from args or env --------------------------------
const pluginRoot = (args && args.plugin_root)
  || (typeof process !== 'undefined' && process.env && process.env.CLAUDE_PLUGIN_ROOT)
  || null
if (!pluginRoot) {
  throw new Error('plugin_root must be passed in args (the slash command expands ${CLAUDE_PLUGIN_ROOT})')
}
// --- Resolve the DATA root (per-instance mutable data: profile/cache/ideations/digests/web) ---
// SHARED plugin CODE stays under pluginRoot; generated DATA lives under the run's project dir, so the
// plugin can run from any external folder and two instances stay isolated. Defaults to the cwd
// (CLAUDE_PROJECT_DIR); == pluginRoot for the legacy in-monorepo run (cwd == plugin), so behavior is
// unchanged there. Every Python call below carries AR_DATA_ROOT=${dataRoot} so config.py routes its
// data dirs here too (the JS path strings and the Python helpers agree on one root).
const dataRoot = (args && (args.data_root || args.project_dir))
  || (typeof process !== 'undefined' && process.env && (process.env.AR_DATA_ROOT || process.env.CLAUDE_PROJECT_DIR))
  || (typeof process !== 'undefined' && process.cwd && process.cwd())   // like bin/run_py.sh — NEVER the plugin dir (a cached plugin dir can hold an old profile of the owner)
const week = (args && args.week) || isoWeek(new Date())

// ── Config: the single source of truth ────────────────────────────────────────
// ONE strict Python load: config.load_config() validates every key and applies
// io.*, so there are NO JS-side defaults. A missing/invalid key makes the Python
// loader throw → execSync throws → the whole workflow aborts loudly (never a
// silent fallback). req() enforces the same for JS-only keys.
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
const KNOBS = req(CFG, 'scout')              // scout.* funnel + ideation knobs
const RJ = req(CFG, 'repo_judge')             // Phase 3.6b repo judge
const CJ = req(CFG, 'claim_judge')            // Phase 3.6a claim judge
const RESEARCHER = req(CFG, 'researcher')   // Phase 0 profile build/rebuild target (always config's owner)
const PROFILE = req(CFG, 'profile')          // Phase 0 profile-build knobs
const PREFETCH = req(CFG, 'prefetch')        // Phase 1.8 citation-graph refresh (citation_mode graph)

// The cross-cutting funnel constraint (prefetch_top_k >= rerank_return_n) is
// validated inside Python load_config, so no re-check is needed here.

// Resolved scout knobs (read once; req throws on a missing key — zero defaults).
const N = req(KNOBS, 'top_n_papers')
const requireRepo = req(KNOBS, 'require_repo')   // Phase 3→4 gate: keep only papers with a live GitHub repo
const prefetchTopK = req(KNOBS, 'prefetch_top_k')
const rerankReturnN = req(KNOBS, 'rerank_return_n')   // = the Phase 3.6 gate candidate pool. DERIVED by config.py at load (min(prefetch_top_k, 2*top_n_papers); 2026-09-19 修订 #11: the G1 → TOP select hands the gate 2·top_n papers) and injected into the raw config — never a yaml key, never a panel knob. The full funnel invariant is enforced once, in config.py.validate().
const cacheStaleDays = req(KNOBS, 'cache_stale_days')
// Categorical tiers (owner preference: adjectival verdicts, no LLM numeric
// scores). Order is low→high; gates compare by tier INDEX, deterministically.
const EXT_TIERS = ['solved', 'incremental', 'needs_bridge', 'natural_followup', 'publishable']
// (Tier ladders retired 2026-07-11 — workflow B gates on verification artifacts, not tiers.)
const tierRank = (tiers, v) => tiers.indexOf(v)
const tierAtLeast = (tiers, v, floor) => tierRank(tiers, v) >= tierRank(tiers, floor)
const reqTier = (tiers, obj, ...p) => {
  const v = req(obj, ...p)
  if (!tiers.includes(v)) throw new Error(`config: ${p.join('.')} must be one of [${tiers.join(', ')}], got '${v}'`)
  return v
}
const extensibilityGate = reqTier(EXT_TIERS, KNOBS, 'extensibility_gate')
// (ideation_rounds_max / candidates_per_round / verify_fanout are ideation-B knobs — read there.)
const breadthPerThread = req(KNOBS, 'breadth_per_thread')
const breadthMinExt = reqTier(EXT_TIERS, KNOBS, 'breadth_min_extensibility')
// Per-phase model overrides: config holds an explicit value (null = no override).
const repoJudgeModel = req(RJ, 'phases', 'repo_judge', 'model') || undefined
const claimJudgeModel = req(CJ, 'phases', 'claim_judge', 'model') || undefined
const profileGenModel = req(PROFILE, 'phases', 'profile_gen', 'model') || undefined
const repoMode = req(RJ, 'mode')    // 'audit' (static code-claim review, no run) | 'execute' (clone + run experiments)
// Phase 3/4/5 core-reasoning routing. `effort` is a harness reasoning-budget
// keyword (e.g. "ultrathink") prepended to the delegation prompt; '' / ~ = none.
const rerankPass   = req(KNOBS, 'rerank_pass')   // 'none' (fused order → G1; production since 修订 #12) | 'a0' (one LLM rerank call)
const rerankModel  = req(KNOBS, 'phases', 'rerank', 'model') || undefined
const rerankEffort = req(KNOBS, 'phases', 'rerank', 'effort') || ''
// (generate/screen/verify/recheck/refute/plan model+effort are ideation-B knobs — read there.)
const withEffort = (prompt, effort) => effort ? `${effort}\n\n${prompt}` : prompt
const ingestMethod = req(CFG, 'io', 'ingest_method')  // 'oai' | 'api'
const ingestScript = ingestMethod === 'oai'
  ? `${pluginRoot}/scripts/oai_ingest.py`
  : `${pluginRoot}/scripts/build_shared_cache.py`

// ── Profile rebuild intent detection ─────────────────────────────────────────
// Triggered when user input mentions rebuilding/refreshing/updating the profile.
// Example: "/arxiv-scout-beta update my profile and run this week's scout"
const userInput = (args && args.input) || ''
let shouldRebuildProfile = /\b(rebuild|refresh|update).{0,20}profile\b/i.test(userInput)
  || /\bprofile\b.{0,20}\b(rebuild|refresh|update)\b/i.test(userInput)

// ── Pinned paper detection ────────────────────────────────────────────────────
// Triggered when user input contains arxiv.org URLs or arxiv: prefixed IDs.
// Example: "/arxiv-scout-beta 这篇也很有意思 https://arxiv.org/abs/2501.12345"
const _arxivLinkRe = /(?:arxiv\.org\/(?:abs|pdf)\/|arxiv:)(\d{4}\.\d{4,5})(?:v\d+)?/gi
const pinnedIds = []
let _linkMatch
while ((_linkMatch = _arxivLinkRe.exec(userInput)) !== null) {
  const id = _linkMatch[1]
  if (!pinnedIds.includes(id)) pinnedIds.push(id)
}
const hasPinnedPapers = pinnedIds.length > 0
if (hasPinnedPapers) log(`Detected ${pinnedIds.length} user-pinned paper(s): ${pinnedIds.join(', ')}`)

// ── Structured output schemas (Phase 0) ──────────────────────────────────────
const WEBSITE_PAPERS_SCHEMA = {
  type: 'object',
  required: ['papers'],
  properties: {
    papers: {
      type: 'array',
      items: {
        type: 'object',
        required: ['title'],
        properties: {
          title:     { type: 'string' },
          year:      { type: ['integer', 'null'] },
          venue:     { type: ['string', 'null'] },
          coauthors: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    scrape_failed: { type: 'boolean' },
  },
}

const PROFILE_SUMMARY_SCHEMA = {
  type: 'object',
  required: ['paper_count', 'supplement_count', 'thread_labels', 'arxiv_categories'],
  properties: {
    paper_count:      { type: 'integer' },
    supplement_count: { type: 'integer' },
    thread_labels:    { type: 'array', items: { type: 'string' } },
    arxiv_categories: { type: 'array', items: { type: 'string' } },
    categories_note:  { type: 'string' },
  },
}

function isoWeek(d) {
  // ISO 8601 year-week, matching `date -u +%G-W%V`
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))
  const day = t.getUTCDay() || 7
  t.setUTCDate(t.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1))
  const wk = Math.ceil(((t - yearStart) / 86400000 + 1) / 7)
  return `${t.getUTCFullYear()}-W${String(wk).padStart(2, '0')}`
}

const runPy = `AR_DATA_ROOT="${dataRoot}" bash ${pluginRoot}/bin/run_py.sh`
const cacheDir = `${dataRoot}/data/cache`
const candidatesPath = `${cacheDir}/week-${week}-candidates.json`
const prefetchedPath = `${cacheDir}/week-${week}-prefetched.json`
const scoutJsonPath = `${cacheDir}/week-${week}-scout.json`

// --- Phase 0: Profile Build / Rebuild (optional) ----------------------------
// Triggered when: (a) user input requests rebuild/refresh/update, OR
// (b) profile.json does not exist yet (first-time setup).
//
// When researcher.google_scholar_url is set (PREFERRED since 2026-09-12, REC-SYSTEM-V2 A1):
//   Phase 0a: build_profile_papers.py --scholar-url → data/profile/paper_candidates.json (+ .md)
//             (ONE robots-allowed Scholar request; arXiv / S2 fill in abstracts, dates, categories)
//   Phase 0b: [USER GATE — arxiv-scout-beta has the owner give every entry a decision
//              (self / peripheral / not) in paper_candidates.json before Phase 0c runs]
//   Phase 0c: build_profile_papers.py --from-list [--cutoff researcher.profile_cutoff] → papers.json
//   Phase 0e: arxiv-profile skill (threads = groups of the researcher's own papers) + profile_finalize.py
//
// Else, when researcher.personal_website is set (website-first identity verification, legacy):
//   Phase 0a: website scrape → data/profile/website_papers.json
//   Phase 0b: paper-level S2 matching → data/profile/identity_check.json
//   Phase 0c: [USER GATE — arxiv-scout-beta skill calls AskUserQuestion here,
//              writes data/profile/identity_decision.json before Phase 0d runs]
//   Phase 0d: build_profile_papers.py using verified identity from identity_decision.json
//   Phase 0e: NL profile generation via arxiv-profile skill
//
// When no personal_website:
//   Phase 0a: direct S2 author fetch via build_profile_papers.py
//   Phase 0b: NL profile generation via arxiv-profile skill
//
// The Phase 0c USER GATE is interactive — only arxiv-scout-beta (running as a
// main agent with AskUserQuestion access) can execute it. The JS workflow logs
// the gate requirement and expects identity_decision.json to exist before Phase 0d.
const papersJsonPath = `${dataRoot}/data/profile/papers.json`
const supplementPath = `${dataRoot}/data/profile/papers_supplement.json`
const profileMdPath  = `${dataRoot}/data/profile/profile.md`
const profileJsonPath = `${dataRoot}/data/profile/profile.json`
const websitePapersPath = `${dataRoot}/data/profile/website_papers.json`
const identityCheckPath = `${dataRoot}/data/profile/identity_check.json`
const identityDecisionPath = `${dataRoot}/data/profile/identity_decision.json`

const profileExists = fs.existsSync(profileJsonPath)

let profileRebuildSummary = null
let profileKept = false  // set when scrape fails + null s2_author_id but a cached profile.json exists → keep it, skip rebuild

if (shouldRebuildProfile || !profileExists) {
  phase('Profile Rebuild')
  const phase0Reason = shouldRebuildProfile
    ? 'profile rebuild requested by user'
    : 'profile.json not found, running initial build'
  log(`Phase 0 — ${phase0Reason}`)

  if (RESEARCHER.google_scholar_url) {
    // ── Scholar path (REC-SYSTEM-V2 A1) ─────────────────────────────────────
    const paperCandidatesPath = `${dataRoot}/data/profile/paper_candidates.json`
    fs.mkdirSync(path.join(dataRoot, 'data', 'profile'), { recursive: true })
    // A candidate list written for THIS build (newer than profile.json, or no profile yet) is waiting on — or
    // already carries — the owner's decisions: REUSE it. Re-entering Phase 0 after the 0b gate must neither read
    // Scholar again nor wipe the decisions (2026-09-13). A rebuild re-reads Scholar; build_profile_papers.py
    // carries the owner's earlier decisions over by key, so only rows NEW on the page need one.
    const pendingList = fs.existsSync(paperCandidatesPath)
      && (!profileExists || fs.statSync(paperCandidatesPath).mtimeMs > fs.statSync(profileJsonPath).mtimeMs)
    if (pendingList) {
      log(`Phase 0a — reusing ${paperCandidatesPath} (written for this build; no second Scholar read)`)
    } else {
      log(`Phase 0a — reading the Google Scholar profile ${RESEARCHER.google_scholar_url} (one robots-allowed request)`)
      try {
        execSync(`${runPy} ${pluginRoot}/scripts/build_profile_papers.py --scholar-url ${JSON.stringify(RESEARCHER.google_scholar_url)}`, { stdio: 'inherit' })
      } catch (e) {
        throw new Error('Phase 0a — build_profile_papers.py failed (see the message above). Exit 2 = Scholar did not serve the page: ask the owner to save it from their own browser and run --scholar-html <file>; never retry or work around a CAPTCHA. Exit 3 = arXiv/S2 lookups errored: wait, then run --refill data/profile/paper_candidates.json (keeps decisions, no Scholar request).')
      }
    }
    // ── Phase 0b: USER GATE — every candidate gets a decision (self / peripheral / not) ──
    // The JS cannot prompt: arxiv-scout-beta runs this gate in the main agent (under /auto-research the headless
    // ideation L1 returns it as a 'paper-list' escalation and L0 asks the owner) and the decisions land in
    // paper_candidates.json before Phase 0c (see its Orchestration rules). No gate when every row is decided.
    log('Phase 0b — paper-list confirmation gate (handled by the orchestrator; none if every row is decided)')
    // ── Phase 0c: confirmed list → papers.json ──────────────────────────────
    const cutoffArg = RESEARCHER.profile_cutoff ? ` --cutoff ${RESEARCHER.profile_cutoff}` : ''
    execSync(`${runPy} ${pluginRoot}/scripts/build_profile_papers.py --from-list ${paperCandidatesPath}${cutoffArg}`, { stdio: 'inherit' })
  } else if (RESEARCHER.personal_website) {
    // ── Website-first identity verification path (legacy) ───────────────────
    log(`Phase 0 — personal_website set: running website-first identity verification`)

    // ── Phase 0a: Website paper extraction ──────────────────────────────────
    log(`Phase 0a — scraping paper list from ${RESEARCHER.personal_website}`)
    const websiteScrape = await agent(
      [
        `You are the website-scrape step (Phase 0a) of the arxiv-profile workflow. Read`,
        `${pluginRoot}/workflows/spawn-prompts/WEBSITE-SCRAPE.md and do EXACTLY what it says — it carries the`,
        `extraction rubric and the return-JSON shape. Substitute as you read it:`,
        `  <WEBSITE_URL>=${RESEARCHER.personal_website}`,
      ].join('\n'),
      { label: 'website-scrape', phase: 'Profile Rebuild', schema: WEBSITE_PAPERS_SCHEMA }
    )
    const websitePapers = websiteScrape.papers || []
    fs.mkdirSync(path.join(dataRoot, 'data', 'profile'), { recursive: true })
    fs.writeFileSync(websitePapersPath, JSON.stringify(websitePapers, null, 2))
    log(`Phase 0a — extracted ${websitePapers.length} papers from website`)

    if (websitePapers.length === 0 || websiteScrape.scrape_failed) {
      // Scrape returned nothing (e.g. a Google-Sites nav shell). We must NOT
      // hand-fabricate a list. The only clean rebuild source now is a direct S2
      // author fetch, which needs researcher.s2_author_id. Guard it: with no
      // author id, build_profile_papers.py exits 1 and this execSync would turn
      // that non-zero exit into an uncaught throw, hard-crashing Phase 0.
      if (RESEARCHER.s2_author_id) {
        log('Phase 0a — scrape failed or 0 papers; falling back to direct S2 author fetch')
        execSync(`${runPy} ${pluginRoot}/scripts/build_profile_papers.py`, { stdio: 'inherit' })
      } else if (profileExists) {
        log('Phase 0a — WEBSITE SCRAPE FAILED and researcher.s2_author_id is null: no source to rebuild the profile from. KEEPING the existing data/profile/profile.json and skipping the rebuild. To force a rebuild, set researcher.s2_author_id in config or point personal_website at a scrapeable publications page.')
        profileKept = true
      } else {
        throw new Error('cannot build profile: website scrape failed and researcher.s2_author_id is null — set researcher.s2_author_id in config or provide a scrapeable publications page')
      }
    } else {
      // ── Phase 0b: Paper-level S2 matching → identity_check.json ────────────
      log('Phase 0b — matching website papers against S2 to identify researcher ...')
      execSync(`${runPy} ${pluginRoot}/scripts/verify_s2_identity.py`, { stdio: 'inherit' })
      const identityCheck = JSON.parse(fs.readFileSync(identityCheckPath, 'utf8'))
      log(`Phase 0b — candidate: ${identityCheck.candidate_author_name || '?'} (${identityCheck.candidate_author_id || 'none'}), S2 total=${identityCheck.s2_total_count ?? '?'}, website=${identityCheck.website_count ?? '?'}, needs_confirmation=${identityCheck.needs_confirmation}`)

      // ── Phase 0c: USER GATE ─────────────────────────────────────────────────
      // identity_check.json contains needs_confirmation. When true, the orchestrating
      // agent (arxiv-scout-beta) calls AskUserQuestion here and writes
      // identity_decision.json before Phase 0d can proceed.
      // This JS workflow cannot issue interactive prompts — the gate is in the skill.
      log('Phase 0c — identity verification gate (handled by arxiv-scout-beta orchestrator)')

      // ── Phase 0d: Build papers.json with verified identity ──────────────────
      log('Phase 0d — building papers.json ...')
      let buildArg = ''
      if (fs.existsSync(identityDecisionPath)) {
        const decision = JSON.parse(fs.readFileSync(identityDecisionPath, 'utf8'))
        buildArg = (decision.use_merged && decision.confirmed_author_id)
          ? `--verified-author-id ${decision.confirmed_author_id} --merged`
          : (decision.use_s2_full && decision.confirmed_author_id)
          ? `--verified-author-id ${decision.confirmed_author_id}`
          : '--website-only'
        log(`Phase 0d — using decision: ${buildArg}`)
      } else if (RESEARCHER.s2_author_id) {
        // Non-interactive context (e.g. Workflow VM): fall back to config s2_author_id
        buildArg = `--verified-author-id ${RESEARCHER.s2_author_id}`
        log('Phase 0d — no identity_decision.json; falling back to config s2_author_id')
      } else {
        buildArg = '--website-only'
        log('Phase 0d — no identity_decision.json and no s2_author_id; using website-only')
      }
      execSync(`${runPy} ${pluginRoot}/scripts/build_profile_papers.py ${buildArg}`, { stdio: 'inherit' })
    }

  } else {
    // ── No personal_website: direct S2 author fetch ─────────────────────────
    log('Phase 0a — no personal_website; fetching papers directly from S2 author ID')
    execSync(`${runPy} ${pluginRoot}/scripts/build_profile_papers.py`, { stdio: 'inherit' })
  }

  // ── Phase 0e: NL profile generation via arxiv-profile skill ───────────────
  // Skipped when we kept an existing profile above (scrape failed + null s2_author_id):
  // there is no fresh papers.json to regenerate from and the cached profile stands.
  if (profileKept) {
    log('Phase 0 — kept existing profile; skipping NL profile regeneration (Phase 0e).')
  } else {
    const papers1 = JSON.parse(fs.readFileSync(papersJsonPath, 'utf8')).papers
    const t1 = papers1.filter(p => p.abstract).length
    const t2 = papers1.length - t1
    const suppCount = papers1.filter(p => p.status === 'not_in_s2').length
    log(`Phase 0e — generating NL profile from ${papers1.length} papers (${t1} full, ${t2} stubs, ${suppCount} website-only)`)

    profileRebuildSummary = await agent(
      [
        `You are the profile-generation step of the arxiv-profile workflow. Invoke the arxiv-profile skill and`,
        `reproduce it EXACTLY — it owns the per-paper notes, the thread grouping, profile.md, starting`,
        `scripts/profile_tools.py and running scripts/profile_finalize.py until its coverage check passes (the`,
        `scripts, not you, compute every other field and write profile.json); do NOT re-derive any of that here.`,
        ``,
        `Injected inputs (paths the skill expects from the orchestrator):`,
        `  - ${papersJsonPath}  (${papers1.length} papers: ${t1} Tier-1 with abstract, ${t2} Tier-2 stubs)`,
        `  - ${pluginRoot}/config/config.yaml`,
        `The skill writes ${profileMdPath} and ${profileJsonPath}.`,
        ``,
        `Return the summary: paper_count, supplement_count, thread_labels, arxiv_categories.`,
      ].join('\n'),
      { label: 'profile-gen', phase: 'Profile Rebuild', schema: PROFILE_SUMMARY_SCHEMA,
        ...(profileGenModel ? { model: profileGenModel } : {}) }
    )

    log(`Phase 0 — complete. arxiv_categories: [${(profileRebuildSummary.arxiv_categories || []).join(', ')}]`)
    log(`Phase 0 — threads: [${(profileRebuildSummary.thread_labels || []).join(' | ')}]`)
  }
} else {
  log('Phase 0 — skipped (no profile rebuild intent detected in user input)')
}

// --- Phase 1 + 2: cache cleanup + fetch + prefetch -----------------------
// Phase 1: clean stale cache (>7d), then oai_ingest.py (stateless fixed-window OAI fetch).
// Phase 2: prefetch.py --top-k scout.prefetch_top_k (config prefetch.*; production 2026-09-18 修订 #10 =
//   equal-weight RRF over dense(paper notes) + per-thread SPECTER2 [split] + phrase BM25 + category).
//   SPECTER2 model load (~10s) amortizes over the full pool; prefetch_top_k (300) is what the A0 rerank call reads.
phase('Fetch')
log(`Phase 1 — cleaning stale cache entries, then ensuring shared arXiv cache for week ${week}`)

let candCount, prefetchedCount

{
  // Cleanup: delete week-* cache files and ideation folders older than 7 days.
  try {
    execSync(`find ${cacheDir} -maxdepth 1 -name "week-*" -mtime +${cacheStaleDays} -delete`, { stdio: 'ignore' })
    execSync(`find ${dataRoot}/data/ideations -maxdepth 1 -mindepth 1 -type d -mtime +${cacheStaleDays} -exec rm -rf {} +`, { stdio: 'ignore' })
    log('Phase 1 — stale cache cleanup done')
  } catch (_) {
    log('Phase 1 — cache cleanup skipped (non-fatal)')
  }

  const fetchStart = Date.now()
  // io.ingest_method selects the fetch script (config.yaml):
  //   oai → oai_ingest.py (OAI-PMH, VPS/datacenter IP)
  //   api → build_shared_cache.py (arXiv Python API, Mac/residential IP)
  // Freshness gate (ingest.cache_fresh_hours) skips re-harvest if cache is recent.
  execSync(`${runPy} ${ingestScript}`, { stdio: 'inherit' })
  if (!fs.existsSync(candidatesPath)) {
    throw new Error(`Phase 1 finished but ${candidatesPath} does not exist`)
  }
  candCount = JSON.parse(fs.readFileSync(candidatesPath, 'utf8')).candidates.length
  log(`Phase 1 done in ${Date.now() - fetchStart}ms — ${candCount} candidates in cache`)

  // ── Phase 1.5: inject user-pinned papers ───────────────────────────────────
  if (hasPinnedPapers) {
    phase('Inject pinned papers')
    log(`Phase 1.5 — fetching metadata for ${pinnedIds.length} pinned paper(s): ${pinnedIds.join(', ')}`)
    const pinnedRaw = execSync(
      `${runPy} ${pluginRoot}/scripts/fetch_pinned_papers.py --arxiv-ids ${pinnedIds.join(' ')}`,
      { encoding: 'utf8' }
    )
    const pinnedPapers = JSON.parse(pinnedRaw)
    const candData = JSON.parse(fs.readFileSync(candidatesPath, 'utf8'))
    const existingIds = new Set(candData.candidates.map(c => c.arxiv_id))
    const newPapers = pinnedPapers.filter(p => !existingIds.has(p.arxiv_id))
    if (newPapers.length > 0) {
      candData.candidates = [...candData.candidates, ...newPapers]
      fs.writeFileSync(candidatesPath, JSON.stringify(candData, null, 2))
      candCount = candData.candidates.length
      log(`Phase 1.5 — injected ${newPapers.length} new pinned paper(s); total candidates: ${candCount}`)
    } else {
      log('Phase 1.5 — all pinned papers already present in candidates; skipping injection')
    }
  }

  // ── Phase 1.6: dedup safety net — guarantee unique arxiv_ids before ranking,
  // independent of the fetch source / pinned injection (never touches fetch). ──
  execSync(`${runPy} ${pluginRoot}/scripts/dedup_candidates.py --candidates ${candidatesPath}`, { stdio: 'inherit' })
  candCount = JSON.parse(fs.readFileSync(candidatesPath, 'utf8')).candidates.length

  // ── Phase 1.8: citation graph (prefetch.citation_mode graph) — built from papers.json, rebuilt
  // only when missing or stale (its papers.json sha no longer matches, e.g. after a Phase 0
  // rebuild); an up-to-date graph costs one local sha check. prefetch.py refuses a stale graph,
  // so this step is what keeps the graph channel from hard-failing. ──
  if (req(PREFETCH, 'use_citation_signal') && req(PREFETCH, 'citation_mode') === 'graph') {
    log('Phase 1.8 — citation graph: build_citation_graph.py --if-stale')
    execSync(`${runPy} ${pluginRoot}/scripts/build_citation_graph.py --if-stale`, { stdio: 'inherit' })
  }

  phase('Score')
  log(`Phase 2 — running mechanical prefetch on ${candCount} candidates (top-k ${prefetchTopK})`)
  const scoreStart = Date.now()
  const _pinnedArg = hasPinnedPapers ? ` --pinned-ids ${pinnedIds.join(',')}` : ''
  execSync(`${runPy} ${pluginRoot}/scripts/prefetch.py --candidates ${candidatesPath} --top-k ${prefetchTopK}${_pinnedArg}`, { stdio: 'inherit' })
  prefetchedCount = JSON.parse(fs.readFileSync(prefetchedPath, 'utf8')).candidates.length
  log(`Phase 2 done in ${Date.now() - scoreStart}ms — top-${prefetchedCount} prefetched`)
}

// --- Phase 3: per-thread seed selection over the delivered reading list -------------------
// 2026-09-20: replaces the G1 → TOP select. The rule has NO free parameters and no LLM ranking call:
//
//     Every paper of the delivered reading list belongs to the thread that ranks it highest;
//     each thread's seed is the highest-ranked paper it owns that PASSES the gate.
//
// Ownership is a partition (scripts/lib/thread_seed.py), so a paper serves at most one thread by
// construction — nothing to arbitrate, no promotion target, no returned-set size, no padding rule.
// Because a seed is the first paper that PASSES, the walk interleaves with the gate and therefore
// lives below, next to acceptCandidate (Phase 3.6). Here we only compute the plan.
//
// What this removed, and why: G1 dealt the 100 into groups and asked one blinded call per group for
// the most relevant paper per thread, then TOP ranked the promoted papers and returned 2·top_n_papers
// of them, padding a short list from the fused order. Three of those steps had no principled setting
// (40, 2·N, the padding), and the selection asked for RELEVANCE while the step's actual question is
// which papers are worth building on — which is what the gate's extensibility tier answers.
// lib/rerank_llm.py keeps the A0/G1/TOP implementation intact: report-v2/ablation imports it to
// reproduce the evaluated reranking arms, and that fidelity check must keep passing.
const TOP_N_SCHEMA = {
  type: 'object',
  required: ['top_papers'],
  properties: {
    top_papers: {
      type: 'array',
      items: {
        type: 'object',
        required: ['arxiv_id', 'title', 'abstract', 'authors', 'categories', 'thread', 'why_it_matters', 'gap'],
        properties: {
          arxiv_id: { type: 'string' },
          title: { type: 'string' },
          abstract: { type: 'string' },              // copy from prefetched JSON; ideator needs this
          authors: { type: 'array', items: { type: 'string' } },
          categories: { type: 'array', items: { type: 'string' } },
          thread: { type: 'string' },                // exact label from profile.threads[i].label
          why_it_matters: { type: 'string' },        // 1-2 sentences, specific to this researcher
          gap: { type: 'string' },                   // 1-2 sentences: what this paper does NOT do
          // extensibility_verdict / _rationale are NOT written here: the gate's claim judge reads the
          // full text and issues them (Phase 3.6), and the seed walk needs them BEFORE this step runs.
        },
      },
    },
  },
}

phase('Final Rank')
// Phase 3a — the seed plan: the delivered reading list partitioned by owning thread, each thread's
// papers best first. Deterministic, zero LLM calls. The WALK (first paper that passes the gate)
// runs in Phase 3.6, where acceptCandidate is in scope.
const seedPlan = JSON.parse(execSync(
  `${runPy} ${pluginRoot}/scripts/lib/thread_seed.py order --week ${week}`,
  { encoding: 'utf8' }).trim().split('\n').pop()).threads
if (!seedPlan.length) throw new Error('Phase 3a — no profile thread owns any delivered paper; check the profile and the channels file')
log(`Phase 3a — seed plan: ${seedPlan.length} thread(s) own the delivered list ` +
    `(${seedPlan.map(t => `${t.key}:${t.candidates.length}`).join(' ')})`)

// Landscape.md (the shared field-view block) REMOVED — ideation is per-paper and governed
// ONLY by top_n_papers. Each ideate agent gets its assigned paper + the researcher profile;
// field/competitor breadth is the arxiv-generate skill's own per-paper scan, not a shared prefix.

// --- Phase 3→3.6 gate: extensibility threshold, then the judge fan-out -------
// (The Phase-4 ideation schema/knobs moved to workflows/arxiv-ideation.js.)

// Coverage selection (coverage_select.py, coverage_mode / mmr_lambda / rotation_enabled) was
// RETIRED 2026-09-20: the seed walk takes one paper per research thread by construction, which
// is what the coverage order existed to approximate. The knobs stay in config so nothing that
// names them fails to load; they are read nowhere.

// ── require_repo gate helpers (Phase 3→4) ───────────────────────────────────
// Deterministic JS, no agent reasoning. Defined here; only CALLED after
// prefetchMapForJudge is built (below), so the const reference resolves fine.
//
// paperHasRepo: hybrid repo check (Q1). Trust a prefetch-verified repo_active
// first; otherwise deep-scan the PDF body for github URLs and confirm one is a
// live repo. A discovered+validated repo is PROMOTED to repo_active in
// prefetchMapForJudge (mirrors the claim-judge promotion) so the repo judge
// downstream picks it up.
function paperHasRepo(p) {
  const pf = prefetchMapForJudge.get(p.arxiv_id) || {}
  if (pf.repo_status === 'repo_active' && pf.repo_url) return true   // already validated at prefetch time
  let urls = []
  try {
    urls = execSync(`AR_DATA_ROOT="${dataRoot}" bash ${pluginRoot}/bin/pdf_github_urls.sh ${p.arxiv_id}`, { encoding: 'utf8' })
      .trim().split('\n').filter(Boolean)
  } catch (e) {
    log(`Phase 3.6 — require_repo: PDF url-scan failed for ${p.arxiv_id}: ${e.message}`)
    return false
  }
  for (const url of urls) {
    try {
      execSync(`bash ${pluginRoot}/bin/validate_github_url.sh ${JSON.stringify(url)}`, { stdio: 'ignore' })
      const entry = prefetchMapForJudge.get(p.arxiv_id) || {}   // promote (mirror claim-judge 1119-1124)
      entry.repo_status = 'repo_active'
      entry.repo_url = url
      prefetchMapForJudge.set(p.arxiv_id, entry)
      log(`Phase 3.6 — require_repo: PDF repo discovered + validated for ${p.arxiv_id} → ${url}`)
      return true
    } catch { /* not a live repo — try the next url */ }
  }
  return false
}

const REPO_SCHEMA = {
  type: 'object',
  required: ['arxiv_id', 'verdict'],
  properties: {
    arxiv_id: { type: 'string' },
    verdict: { type: 'string', enum: ['pass', 'flag', 'fail', 'inconclusive'] },
    seed_tested: { type: 'integer', const: 0 },
    results: { type: 'object' },
    claimed_value: { type: ['number', 'string', 'null'] },
    direction_consistent: { type: ['boolean', 'null'] },
    report_path: { type: 'string' },
    findings: { type: 'array' },   // audit mode: [{check, finding, severity}] (mirrors claim consistency_issues)
    rationale: { type: 'string' },
  },
}

const CLAIM_JUDGE_SCHEMA = {
  type: 'object',
  // extensibility_verdict is REQUIRED: the seed walk drops any paper whose tier is below the
  // gate, so a judge that omitted it would silently reject every paper and starve every thread.
  required: ['arxiv_id', 'verdict', 'claim_strength', 'extensibility_verdict', 'claims'],
  properties: {
    arxiv_id: { type: 'string' },
    verdict: { type: 'string', enum: ['pass', 'flag', 'inconclusive'] },
    // Strength floor (categorical, no numbers): how ambitious/consequential the
    // paper's CENTRAL claim is. 'mediocre' is dropped by the gate regardless of
    // the integrity verdict — bland claims never earn a deep-dive slot.
    claim_strength: { type: 'string', enum: ['bold', 'solid', 'mediocre'] },
    // Follow-up headroom, from the same full-text read: does this paper leave a sub-problem worth
    // working on? This is the ONLY gate that asks whether a paper is worth BUILDING ON rather than
    // whether it is relevant or sound, so the seed walk needs it before it can seed a thread.
    extensibility_verdict: { type: 'string', enum: EXT_TIERS },
    extensibility_rationale: { type: 'string' },
    repo_url_in_pdf: { type: 'array', items: { type: 'string' } },
    claims: {
      type: 'array',
      items: {
        type: 'object',
        required: ['claim_id', 'description', 'baseline', 'metric', 'testable'],
        properties: {
          claim_id: { type: 'string' },
          description: { type: 'string' },
          baseline: { type: 'string' },
          metric: { type: 'string' },
          metric_primary: { type: ['string', 'null'] },
          metric_secondary: { type: ['string', 'null'] },
          claimed_rate: { type: ['string', 'null'] },
          testable: { type: 'boolean' },
          testability_note: { type: 'string' },
        },
      },
    },
    claim_spec: { type: 'object' },
    consistency_issues: { type: 'array' },
    rationale: { type: 'string' },
  },
}

function buildRepoPrompt(p, pf, claims) {
  const inputPayload = {
    arxiv_id: p.arxiv_id,
    title: p.title,
    abstract: p.abstract || '',
    repo_url: pf.repo_url,
    timeout_sec: req(RJ, 'timeout_per_paper_sec'),
    cache_dir: cacheDir,
  }
  if (claims && claims.length) {
    inputPayload.claims = claims
    inputPayload.claim_spec = {
      main_claim: claims[0].description,
      baseline: claims[0].baseline,
      metric: claims[0].metric,
      metric_primary: claims[0].metric_primary || claims[0].metric,
      metric_secondary: claims[0].metric_secondary || null,
      claimed_rate: claims[0].claimed_rate || null,
    }
  }
  inputPayload.mode = repoMode
  return [
    `You are a repo judge in the arxiv-scout workflow for week ${week}.`,
    `Invoke the arxiv-repo-judge skill on the paper below; it runs the Phase-2 section matching the`,
    `\`mode\` field in the input JSON. Return its raw verdict + evidence only — the workflow gates`,
    `(do NOT decide keep/drop).`,
    ``,
    `Per-paper input JSON (the skill's "Inputs" contract):`,
    `\`\`\`json`,
    JSON.stringify(inputPayload, null, 2),
    `\`\`\``,
  ].join('\n')
}

function buildClaimJudgePrompt(p, pf) {
  const inputPayload = {
    arxiv_id: p.arxiv_id,
    title: p.title,
    abstract: p.abstract || '',
    repo_status: (pf && pf.repo_status) || 'unknown',
    quality_tier: (pf && pf.quality_tier) || 'unknown',
    author_h_max: (pf && pf.author_h_max) || null,
    plugin_root: pluginRoot,
  }
  return [
    `You are a claim-integrity judge in the arxiv-scout workflow for week ${week}.`,
    `Invoke the arxiv-claim-judge skill on the paper below. Return its raw output only — the workflow`,
    `gates; do NOT decide keep/drop.`,
    ``,
    `Per-paper input JSON (the skill's "Inputs" contract):`,
    `\`\`\`json`,
    JSON.stringify(inputPayload, null, 2),
    `\`\`\``,
  ].join('\n')
}

// prefetchMapForJudge: prefetch features keyed by arxiv_id — read by paperHasRepo
// (repo check + promotion) and acceptCandidate (claim/repo). Built before the
// fill-to-N loop so the gates can read it.
const prefetchMapForJudge = fs.existsSync(prefetchedPath)
  ? new Map(JSON.parse(fs.readFileSync(prefetchedPath, 'utf8')).candidates.map(c => [c.arxiv_id, c]))
  : new Map()

let claimsMap = {}                 // arxiv_id → claims[] (claim Stage 1 → repo Stage 2)
let judgeConclusionsByPaper = {}   // arxiv_id → {claim_*, repo_*} — surfaced to ideation

// ── Phase 3→4: single-fan-out "pass-all-judges" survivor selection ──────────
// A paper counts toward the N deep-dive slots ONLY if it passes every applicable
// gate: require_repo (a live repo), claim judge (Stage 1: integrity FAIL-CLOSED
// + categorical strength floor), and — for repo-active papers — repo judge
// (Stage 2). The WHOLE eligible pool is judged in ONE parallel barrier (small by
// construction: rerank_return_n ≈ 2*top_n_papers+1), then JS walks the COVERAGE
// order taking the first N survivors. No rounds, no cursor — nothing stateful
// for the re-enactor to replay. No cost cap (the repo clone+run expense is
// accepted). pinned papers are force-included and exempt from every judge. JS
// owns all pass/fail; agents return raw verdicts only. Each survivor carries
// original_rank for the final report.

// Full coverage-PRIORITISED ordering of the eligible pool (rank-1, one best per
// new thread, then the rerank tail). mode=off ⇒ rerank order. This is the walk
// order the fill-to-N loop draws candidates from.
// ── Judge-verdict disk cache (crash-resume; mirrors tryResumeIdeation) ──────
// Keyed per week via the filename. A same-week re-run replays cached verdicts
// AND their side effects instead of re-spawning judges — repo clone/run is the
// most expensive step in the pipeline and must never be paid twice for one
// week. Delete the file to force re-judging (e.g. after retuning the gates).
const judgeCachePath = `${cacheDir}/week-${week}-judge-cache.json`
let judgeCache = {}
try { judgeCache = JSON.parse(fs.readFileSync(judgeCachePath, 'utf8')) } catch (_) { judgeCache = {} }
function persistJudgeEntry(id, entry) {
  judgeCache[id] = entry
  try { fs.writeFileSync(judgeCachePath, JSON.stringify(judgeCache, null, 2)) }
  catch (e) { log(`Phase 3.6 — judge-cache write failed (non-fatal): ${e.message}`) }
}

// Per-candidate acceptance test → {ok, why, penalize}. Consults the disk cache
// first; on a fresh judgment records claim/repo conclusions + the claims list
// (each candidate touches only its OWN map entries — per-candidate-local, no
// cross-candidate coupling) and persists its cache entry. pinned papers never
// reach here.
async function acceptCandidate(p) {
  const id = p.arxiv_id
  const cached = judgeCache[id]
  if (cached && cached.result) {
    if (cached.conclusions) judgeConclusionsByPaper[id] = cached.conclusions
    if (cached.claims) claimsMap[id] = cached.claims
    if (cached.promotion) {
      const entry = prefetchMapForJudge.get(id) || {}
      entry.repo_status = cached.promotion.repo_status
      entry.repo_url = cached.promotion.repo_url
      prefetchMapForJudge.set(id, entry)
    }
    log(`Phase 3.6 — ${id}: replaying cached verdict (${cached.result.why})`)
    return cached.result
  }
  let penalize = false
  const finish = (result) => {   // persist verdict + side effects, then return it
    const pf = prefetchMapForJudge.get(id)
    persistJudgeEntry(id, {
      result,
      conclusions: judgeConclusionsByPaper[id] || null,
      claims: claimsMap[id] || null,
      promotion: (pf && pf.repo_status === 'repo_active' && pf.repo_url)
        ? { repo_status: pf.repo_status, repo_url: pf.repo_url } : null,
    })
    return result
  }
  // (1) require_repo: must have (or PDF-discover) a live repo. paperHasRepo may
  //     promote no_repo→repo_active in prefetchMapForJudge (consumed by step 3).
  if (requireRepo && !paperHasRepo(p)) return finish({ ok: false, why: 'no repo' })
  // (2) Claim judge — Stage 1. FAIL-CLOSED + strength floor: 'inconclusive'
  //     drops (can't verify the claims ⇒ don't ideate on them); a 'mediocre'
  //     claim_strength drops (bland central claims never earn a deep-dive
  //     slot); 'flag' (overclaim/suspicious) follows claim_judge.flag_action.
  if (req(CJ, 'use_claim_judge')) {
    const pf = prefetchMapForJudge.get(id) || {}
    const r = await agent(buildClaimJudgePrompt(p, pf),
      { label: `claim:${id}`, phase: 'Judge Gate',
        schema: CLAIM_JUDGE_SCHEMA, ...(claimJudgeModel ? { model: claimJudgeModel } : {}) })
    if (!r) return finish({ ok: false, why: 'claim judge error' })
    judgeConclusionsByPaper[id] = {
      ...(judgeConclusionsByPaper[id] || {}),
      claim_verdict: r.verdict,
      claim_strength: r.claim_strength,
      claim_rationale: r.rationale || '',
      claim_issues: (r.consistency_issues || []).length,
    }
    if (r.claims && r.claims.length) claimsMap[id] = r.claims
    if (r.repo_url_in_pdf && r.repo_url_in_pdf.length) {
      const entry = prefetchMapForJudge.get(id)
      if (entry && entry.repo_status === 'no_repo') {
        entry.repo_status = 'repo_active'
        entry.repo_url = r.repo_url_in_pdf[0]
        log(`Phase 3.6 — claim judge: repo URL discovered in PDF for ${id}, promoting to repo_active`)
      }
    }
    if (r.extensibility_verdict) {
      judgeConclusionsByPaper[id].extensibility_verdict = r.extensibility_verdict
      judgeConclusionsByPaper[id].extensibility_rationale = r.extensibility_rationale || ''
    }
    if (r.verdict === 'inconclusive') return finish({ ok: false, why: 'claim inconclusive (fail-closed)' })
    if (!EXT_TIERS.includes(r.extensibility_verdict))
      throw new Error(`Phase 3.6 — claim judge returned no usable extensibility_verdict for ${id} ` +
                      `(got ${JSON.stringify(r.extensibility_verdict)}); the seed walk cannot proceed`)
    if (!tierAtLeast(EXT_TIERS, r.extensibility_verdict, extensibilityGate))
      return finish({ ok: false, why: `extensibility ${r.extensibility_verdict} below '${extensibilityGate}' (${r.extensibility_rationale || ''})` })
    if (r.claim_strength === 'mediocre') return finish({ ok: false, why: `claim mediocre — strength floor (${r.rationale || ''})` })
    if (r.verdict === 'flag') {
      if (req(CJ, 'flag_action') === 'filter') return finish({ ok: false, why: `claim flag→filter (${r.rationale || ''})` })
      penalize = true
      log(`Phase 3.6 — claim judge: flag ${id} → penalize (${r.rationale || ''})`)
    }
  }
  // (3) Repo judge — Stage 2 (repo-active only; no-repo papers survive on claim alone).
  if (req(RJ, 'use_repo_judge')) {
    const pf = prefetchMapForJudge.get(id) || {}
    if (pf.repo_status === 'repo_active' && pf.repo_url) {
      const r = await agent(buildRepoPrompt(p, pf, claimsMap[id]),
        { label: `repo:${id}`, phase: 'Judge Gate',
          schema: REPO_SCHEMA, ...(repoJudgeModel ? { model: repoJudgeModel } : {}) })
      if (!r) return finish({ ok: false, why: 'repo judge error' })
      judgeConclusionsByPaper[id] = {
        ...(judgeConclusionsByPaper[id] || {}),
        repo_verdict: r.verdict,
        repo_rationale: r.rationale || '',
        repo_report_path: r.report_path || `${cacheDir}/repo-${id}.md`,
      }
      const failOpen = !!req(RJ, 'fail_open')
      if (r.verdict === 'fail' || (!failOpen && r.verdict === 'inconclusive'))
        return finish({ ok: false, why: `repo ${r.verdict}` })
      if (r.verdict === 'flag') {   // audit mode: minor reproducibility gaps
        if (req(RJ, 'flag_action') === 'filter') return finish({ ok: false, why: 'repo flag→filter' })
        penalize = true
        log(`Phase 3.6 — repo audit: flag ${id} → penalize (${r.rationale || ''})`)
      }
    }
  }
  return finish({ ok: true, why: 'pass', penalize })
}

// ── Phase 3.6: the seed walk ───────────────────────────────────────────────
// Each thread takes the first paper it owns that passes the gate. A paper the gate rejects is
// rejected for good (its verdict is cached, so a later round never re-pays for it); a thread whose
// papers are exhausted ends with no seed, and the vacancy is reported rather than filled.
// Rounds exist only because a seed is defined by a verdict we do not have yet: round r nominates
// every seedless thread's r-th paper, judges the nominations in ONE parallel barrier, and assigns.
// Ownership is a partition, so two threads can never nominate the same paper and there is nothing
// to arbitrate. Typically 1-2 rounds; the walk is bounded by the delivered list itself.
const pinnedSet = new Set(pinnedIds || [])
const survivors = []
for (const id of (pinnedIds || [])) {
  const pf = prefetchMapForJudge.get(id)
  if (pf) survivors.push(pf)
}

const anyGate = requireRepo || req(CJ, 'use_claim_judge') || req(RJ, 'use_repo_judge')
if (anyGate) phase('Judge Gate')

// The WALK ITSELF is scripts/lib/thread_seed.py, not this file: it reads the judge CACHE from disk
// and owns every state transition (which thread is seeded, which paper is next, when to stop), so a
// hand-enacting orchestrator never has to hold cursors in its head. This loop only spawns judges.
// Same boundary compute_gated_pool.py draws for the survivor tally, and for the same reason.
const walkStatePath = `${cacheDir}/week-${week}-seed-walk.json`
const seedWalk = () => JSON.parse(execSync(
  `${runPy} ${pluginRoot}/scripts/lib/thread_seed.py walk --week ${week} --state ${walkStatePath}` +
  (pinnedIds && pinnedIds.length ? ` --exempt ${pinnedIds.join(',')}` : ''),
  { encoding: 'utf8' }).trim().split('\n').pop())

let st = seedWalk()
for (let round = 1; !st.done; round++) {
  log(`Phase 3.6 — seed walk round ${round}: ${st.nominations.length} nomination(s) ` +
      `(${st.nominations.map(n => `${n.key}→${n.arxiv_id}`).join(' ')})`)
  // ONE in-turn-awaited barrier. acceptCandidate PERSISTS each verdict to week-<W>-judge-cache.json;
  // the next seedWalk() reads THAT file. The in-memory result is discarded on purpose.
  await parallel(st.nominations.map(n => () =>
    acceptCandidate(prefetchMapForJudge.get(n.arxiv_id) || { arxiv_id: n.arxiv_id })))
  const next = seedWalk()
  if (next.seeds.length === st.seeds.length && next.rejected.length === st.rejected.length)
    throw new Error(`Phase 3.6 — seed walk round ${round} made no progress: the judges committed no ` +
                    `verdict for ${st.nominations.map(n => n.arxiv_id).join(', ')}`)
  for (const s2 of next.seeds.slice(st.seeds.length)) log(`Phase 3.6 — ${s2.key} seeded with ${s2.arxiv_id}`)
  st = next
}
const seeds = st.seeds
for (const key of st.unseeded) log(`Phase 3.6 — ${key} has NO seed: every paper it owns was rejected`)
if (!seeds.length) throw new Error('Phase 3.6 — no thread produced a seed; every delivered paper was rejected by the gate')
log(`Phase 3.6 — seed walk done: ${seeds.length}/${seedPlan.length} thread(s) seeded`)

// final.json, in the shape the arxiv-rerank skill already consumes (contract unchanged).
const seedsPath = `${cacheDir}/week-${week}-seeds.json`
fs.writeFileSync(seedsPath, JSON.stringify(seeds))
const finalPath = JSON.parse(execSync(
  `${runPy} ${pluginRoot}/scripts/lib/thread_seed.py final --week ${week} --seeds ${seedsPath}`,
  { encoding: 'utf8' }).trim().split('\n').pop()).final_path

// Phase 3c — rationales for the seeds. Pinned papers are force-included downstream (exempt from the gate);
// they must be in the rationale set even when no thread seeded them — appended AFTER the seeds.
const rationaleIds = seeds.map(t => t.arxiv_id)
for (const id of (hasPinnedPapers ? pinnedIds : [])) if (!rationaleIds.includes(id)) rationaleIds.push(id)

log(`Phase 3c — rationales for the ${rationaleIds.length} seed paper(s) (arxiv-rerank skill; the set and order are already fixed)`)
const ranked = await agent(
  withEffort([
    `You are the rationale step of the arxiv-scout workflow for week ${week}.`,
    ``,
    `Inputs on disk:`,
    `  - ${dataRoot}/data/profile/profile.md  (NL profile, first-person)`,
    `  - ${dataRoot}/data/profile/profile.json  (threads, extracted keywords, recent_direction)`,
    `  - ${prefetchedPath}  (top-${prefetchedCount} prefetched candidates)`,
    `  - ${finalPath}  (THE selection: "top" = the ${seeds.length} seed papers in served order, each with the`,
    `    thread that owns it — the partition is exact, so a thread is never null and must not be reassigned)`,
    ``,
    `Invoke the arxiv-rerank skill and reproduce it EXACTLY — it is the single source of truth for the`,
    `why_it_matters / thread / gap rubric and the no-seed / no-external-LLM-API`,
    `rules. The ORDER is already decided by final.json: do NOT re-rank, drop or add papers. It writes`,
    `${cacheDir}/week-${week}-rerank.json (the /weekly-papers pipeline also consumes it) and does NOT render the digest.`,
    ``,
    `Return contract (structured output the orchestrator branches on, BEYOND the rerank.json the skill writes):`,
    `  - Return EXACTLY these ${rationaleIds.length} papers, in this order, as top_papers — they ARE the seeds the`,
    `    gate already passed (do NOT drop, add or reorder): ${rationaleIds.join(', ')}`,
    `  - For every returned paper copy arxiv_id, title, authors, categories AND the full abstract VERBATIM from the`,
    `    prefetched JSON; thread = final.json's thread when non-null, else the exact profile thread name you assign.`,
    ...(hasPinnedPapers ? [
      ``,
      `User-pinned papers (researcher explicitly requested these — the ids after the selected ones above are pinned`,
      `and marked pinned:true in the prefetched JSON; write their rationales like any other):`,
      ...pinnedIds.map(id => `  - arXiv:${id}`),
    ] : []),
  ].join('\n'), rerankEffort),
  { label: 'final-rank', phase: 'Final Rank', schema: TOP_N_SCHEMA,
    ...(rerankModel ? { model: rerankModel } : {}) }
)

if (!ranked || !ranked.top_papers || ranked.top_papers.length === 0) {
  throw new Error('Phase 3c returned no top papers — check arxiv-rerank skill output')
}
// The rationale step must hand back the selected set in the selected order — checked deterministically against
// final.json, never trusted from the agent's own reading.
{
  const got = ranked.top_papers.map(p => p.arxiv_id)
  if (got.join(',') !== rationaleIds.join(',')) {
    throw new Error(`Phase 3c returned a different set/order than final.json: got [${got.join(',')}] want [${rationaleIds.join(',')}]`)
  }
}
log(`Phase 3 done — ${ranked.top_papers.length} seed paper(s) with rationales`)

// Stamp each paper's 1-based rerank rank so survivors can report their original
// position after the fill-to-N judging loop reorders/drops the pool (Phase 3.6).
ranked.top_papers.forEach((p, i) => { p.original_rank = i + 1 })


// The gate issued the extensibility tier (from the full text), not the rationale step — stamp it
// back onto the paper objects so the digest, the web report and workflow B read it where they
// always did. A pinned paper never passed a gate, so it carries no tier and, as before, does not
// compete for a breadth slot.
for (const p of ranked.top_papers) {
  const c = judgeConclusionsByPaper[p.arxiv_id]
  if (c && c.extensibility_verdict) {
    p.extensibility_verdict = c.extensibility_verdict
    p.extensibility_rationale = c.extensibility_rationale || ''
  }
}

const queue = ranked.top_papers.filter(p => !pinnedSet.has(p.arxiv_id))

// DETERMINISTIC survivor tally — the ANTI-FABRICATION boundary (2026-07-12). The tally used
// to be an in-memory queue.forEach over the judge returns; when /arxiv-scout-beta is ENACTED
// by hand, that is exactly where a run went wrong — the orchestrator lost track of which judge
// leaves had returned and FABRICATED ~10 verdicts to fill the gap. The survivor set is now
// computed by scripts/compute_gated_pool.py, which reads the judge CACHE and FAIL-CLOSES if any
// queued paper has no committed verdict (it cannot be invented from memory). Emits the gate
// OUTPUT week-<W>-gated-pool.json (<= top_n_papers; pinned seeded → count toward N; penalize →
// quality_tier:'flagged'; empty-pool fail-safe → ext_pool_ordered[:N] — same rules as before,
// now code-owned). See scripts/compute_gated_pool.py for the exact tally.
fs.writeFileSync(`${cacheDir}/week-${week}-gate-input.json`, JSON.stringify({
  queue,                                               // the seeds, in served order, pinned excluded
  pinned: survivors.slice(),                           // force-included, never judged; count toward N
  ext_pool_ordered: queue.slice(),                     // empty-pool fail-safe source (same order)
  n: N,
}))
execSync(`${runPy} ${pluginRoot}/scripts/compute_gated_pool.py --week ${week} ` +
  `--gate-input ${cacheDir}/week-${week}-gate-input.json`, { stdio: 'inherit' })
// PERSIST the gate OUTPUT (the <= top_n_papers survivors) under the honest name gated-pool.json — these
// ARE the Phase-4 ideation set AND the resume boundary. The coverage_select INPUT pool lives in a separate
// scratch file (week-<W>-coverage-input.json). A RESUME author (human or L1) reads THIS file to learn which
// papers survived the gate; before this write the survivor set lived only in memory, so resume mistook the
// larger candidate pool (rerank_return_n) for the survivors and ideated all of them — bypassing top_n_papers.
let gatedPapers = JSON.parse(fs.readFileSync(`${cacheDir}/week-${week}-gated-pool.json`, 'utf8'))
// ↑ week-<W>-gated-pool.json + week-<W>-judge-cache.json are the ON-DISK CONTRACT
// workflow B (workflows/arxiv-ideation.js) reads: the pool carries the FULL paper
// objects (abstract / why_it_matters / gap / extensibility / original_rank), the
// judge cache carries each survivor's claim/repo conclusions. B must run within
// scout.cache_stale_days of this write (Phase 1 cleanup deletes older caches).

// --- Build the digest breadth block (M1) ---------------------------------
// Every profile thread's best gate-passing paper this week, in canonical
// profile order. Decoupled from ideation depth: pure assembly over
// ranked.top_papers (already computed in Phase 3), zero extra agent cost.
// Generic over T = number of profile threads — no hardcoded thread count.
// in_deepdive = survived the judge gate (the set workflow B will ideate).
const gatedIdSet = new Set(gatedPapers.map(p => p.arxiv_id))
let breadth = null
if (req(KNOBS, 'breadth_section')) {
  try {
    const profileThreads = JSON.parse(
      fs.readFileSync(`${dataRoot}/data/profile/profile.json`, 'utf8')
    ).threads || []
    const labels = profileThreads.map(t => t.label).filter(Boolean)
    const perThread = breadthPerThread
    const minExt = breadthMinExt
    const byThread = new Map()
    for (const p of ranked.top_papers) {
      if (!tierAtLeast(EXT_TIERS, p.extensibility_verdict, minExt)) continue
      const arr = byThread.get(p.thread) || []
      if (arr.length < perThread) arr.push(p)  // rerank order = best-first
      byThread.set(p.thread, arr)
    }
    breadth = labels.map(label => ({
      thread: label,
      papers: (byThread.get(label) || []).map(p => ({
        arxiv_id: p.arxiv_id,
        title: p.title,
        why_it_matters: p.why_it_matters,
        extensibility_verdict: p.extensibility_verdict,
        in_deepdive: gatedIdSet.has(p.arxiv_id),
      })),
    }))
    const covered = breadth.filter(e => e.papers.length).length
    log(`Digest breadth: ${covered}/${labels.length} thread(s) have a paper this week`)
  } catch (e) {
    log(`Digest breadth skipped: ${e.message}`)
  }
}

// --- Write the scout-side index JSON + render digest ---------------------
// PAPERS-ONLY manifest: top_papers is PINNED to the gate survivors so the paper
// set stays STABLE across the A/B renders (workflow B re-renders with ideas but
// never changes which papers appear — a recommended paper can never vanish from
// the digest because B's quality filter dropped it). B rewrites this
// same file, filling ideation_manifest and leaving top_papers untouched.
const manifestPayload = {
  week,
  generated_at_utc: new Date().toISOString(),
  profile_rebuild: shouldRebuildProfile && profileRebuildSummary ? {
    triggered: true,
    paper_count: profileRebuildSummary.paper_count,
    supplement_count: profileRebuildSummary.supplement_count,
    thread_labels: profileRebuildSummary.thread_labels,
    arxiv_categories: profileRebuildSummary.arxiv_categories,
  } : { triggered: false },
  top_papers: gatedPapers,
  breadth,  // M1 digest breadth block (null when disabled) — see scout_digest._render_breadth
  ideation_manifest: [],   // filled by workflow B (arxiv-ideation.js)
}
const manifestJson = JSON.stringify(manifestPayload, null, 2)

fs.writeFileSync(scoutJsonPath, manifestJson)
log(`Wrote scout JSON (papers-only): ${scoutJsonPath}`)
execSync(`${runPy} ${pluginRoot}/scripts/lib/scout_digest.py --week ${week}`, { stdio: 'inherit' })
const digestPath = `${dataRoot}/data/digests/${week}-scout.md`

// (The ideation loop lives in workflows/arxiv-ideation.js — the verified-kill
// redesign: candidates die on executed evidence or converge on artifacts;
// no tier scoring exists anywhere in that loop.)

// --- Generate interactive HTML web report (pure mechanical shell-out; mirrors
// the digest render above — no agent, failures are loud via non-zero exit) ----
const webReportPath = `${dataRoot}/data/web/${week}-scout.html`
execSync(`${runPy} ${pluginRoot}/scripts/lib/scout_web.py --week ${week} --no-open`, { stdio: 'inherit' })
log(`Web report: data/web/${week}-scout.html`)

return {
  week,
  digest_path: `data/digests/${week}-scout.md`,
  web_report_path: `data/web/${week}-scout.html`,
  scout_json: `data/cache/week-${week}-scout.json`,
  gated_pool: `data/cache/week-${week}-gated-pool.json`,
  papers_gated: gatedPapers.length,
  next_step: `Recommendation done (papers-only digest at ${digestPath}). NOW RUN workflow B — ` +
    `workflows/arxiv-ideation.js — the verified-kill ideation loop over the gate survivors ` +
    `for the ${gatedPapers.length} gated paper(s); it re-renders the digest/web report with ideas.`,
}
