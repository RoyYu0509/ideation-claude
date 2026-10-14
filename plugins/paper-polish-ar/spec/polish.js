// polish — turn a correct, AI-sounding paper draft into publishable, human-sounding
// prose without touching the science. Freeze the science; rewrite the prose.
//
// This file is the CANONICAL SPEC for the run. It is driven by an ORCHESTRATOR: a Claude
// model reads this file (via commands/polish.md) and reproduces the phase sequence using
// Task subagents + Bash. The JS format is intentional — it eliminates branching/loop
// ambiguity that prose cannot.
//
// MULTI-FILE: the input is the MASTER file (the root .tex that \input{}s the section files,
// e.g. main.tex), or a self-contained single-file paper. scripts/resolve_manuscript.py turns
// it into a FILE-UNIT model: each loop unit is one file tagged (section, rubric). A reviser
// reads the WHOLE paper for context but edits ONLY its one file; best-round/restore are per-file.
//
// Conventions used below (the orchestrator maps these to its own actions):
//   agent(goal, {role, schema, ...})  -> spawn ONE subagent of the configured shell
//                                        (roles.<role>.subagent_type) with this goal and
//                                        required output schema; returns the parsed schema.
//   parallel([() => agent(...), ...]) -> run several spawns concurrently.
//   bash(cmd, schema?)                -> run a shell command (git / fs) and return output.
//                                        The orchestrator runs these itself; the reviser
//                                        commits its own rounds (it has Bash).
//   askUser(questions)                -> the AskUserQuestion tool. The orchestrator runs in the main
//                                        loop, so ONLY it can ask the author; subagents never can.
//                                        `questions` is an array of {question, header, options[]};
//                                        returns the author's selection per question. Used at
//                                        [[SEAM:venue-resolve]] (the venue picker when none is named).
//   phase(name) / log(msg)            -> progress markers.
//
// All knobs come from config/config.yaml -> polish: block, read once at startup.
// Convergence and best-round selection are a DETERMINISTIC CATEGORICAL decision owned here (a state
// ladder, NOT a numeric score — D15) and never told to the agents. The agents return verdicts (a
// fidelity verdict + categorically-tagged quality flags); this file decides.
//
// ── Two-tier execution contract (显式决策点分层) ───────────────────────────────
// This spec is driven by an LLM ORCHESTRATOR. Every step below is exactly ONE of:
//   [[MECH]]         MUST-MECHANICAL. Deterministic; script-backed where feasible. Reproduce it
//                    verbatim — never improvise, reorder, paraphrase, or "improve" it. (git/branch
//                    scoping, convergence arithmetic, flag weights, schema shapes, max_rounds, and
//                    verdict serialization are all MECH.)
//   [[SEAM:<name>]]  ORCHESTRATOR-MAY-REASON. A named, bounded point where the orchestrator thinks.
//                    Each seam states its TRIGGER, the bounded DECISION space, the hard FLOOR the
//                    reasoning may never cross, and the FALLBACK when it cannot decide.
// The orchestrator seams: input-resolve, venue-resolve, empty-result-recovery, next-round-prompt,
// sweep-routing. (A further one, context-depth, lives SUBAGENT-side via the context-scope skill — the
// orchestrator only passes sibling paths + keynote effort.) venue-resolve is INTERACTIVE: when no venue
// is named it recommends + asks the author. (Two former seams are gone: the near-convergence stop was
// REMOVED — D15 makes convergence the strict empty-set model; reviewer-packaging was removed when
// reviewer spawning collapsed to single — 第三刀.)
// Reasoning happens ONLY at a seam; everywhere else follow the MECH bytes. The only guards that
// survive a misbehaving orchestrator are the pre-edit hook (frozen tokens / denylist) and the
// agents/*.md tool allowlists (e.g. fidelity has no Edit/Write).
//
// Topology:
//   Phase 0 Setup     — resolve the manuscript (master + \input files -> file units); write the
//                       fidelity manifest (.polish/, a `manuscripts` list) so the pre-edit hook is
//                       armed; SAFE git: branch polish-<ts> from the current HEAD, base commit only
//                       the manuscript files (never sweep unrelated repo changes).
//   Phase 1 Plan      — plannedSections = section_order ∩ present-in-draft ∩ target; plannedFiles.
//   Phase 1.5 Keynote — ONE read-only whole-paper read: per-section effort + global arc flags
//                       (seeds round 1); out-of-scope science gaps parked as advisory only.
//   Phase 2 Sections  — serial; per FILE a revise→evaluate→converge loop (runBodySection),
//                       except `abstract` (runAbstractSection, last).
//   Phase 2.9 Sweep   — when target=all and >1 file: a read-only consistency reviewer whose flags
//                       are ROUTED per file to a per-file fix reviser. Then runFinalFidelitySweep — ONE
//                       read-only ADVISORY meaning-drift read per file (base→HEAD), pushing close-calls
//                       (never reverting); the sole close-call source now the per-round gate is gone (D1).
//   Phase 3 Emit      — git log + git diff base..HEAD + the close-call list + verdict files
//                       + a latexdiff inline-diff PDF (whole compiled paper, changes marked in place;
//                       LaTeX papers with a TeX toolchain only — otherwise the git diff is the diff).
//
// ── PROGRESSIVE DISCLOSURE protocol (Doc A §3.2 — load only what is still open) ──────────────────
// PROGRESSIVE DISCLOSURE protocol (Doc A §3.2 — load only what is still open).
//
// This phase participates in the demand-driven loading engine. Your spawn goal names a FROZEN open-concern
// snapshot (the round-stamped .round-<N>.concerns.json for in-loop phases, or this phase per-unit TASK_STATUS
// for the post-freeze finishing phases) and the concern->reference map (assets/concern-reference-map.yaml).
// On entry:
//   1. READ the frozen snapshot the goal names — NEVER the live ledger (Doc A §3.3: a detach and its re-wake
//      must see a byte-identical disclosure set).
//   2. RUN every resident sensor for this phase (cheap; they may add or reopen items) — these run EVERY round
//      regardless of the open set.
//   3. COMPUTE the open-concern set = the concern of every item with status in {open, reopened}, deduped.
//   4. DISCLOSE references ONLY for those open concerns (look each up in the concern->reference map and load
//      those files); load NO reference for a closed/deferred concern.
//   5. ACT only on open/reopened items; update the live concern ledger (TASK_STATUS.concerns.json + the
//      markdown TASK_STATUS) — fixed->closed, regressed->reopened, cannot-act->deferred, each with evidence
//      (task-ledger schema).
//   6. When you spawn an L2 worker, its goal names ONLY the open concerns references — never the full set.
//
// Ledger ② role, keyed by SECTION unit (post-freeze, mode:polish — ALL science frozen, only prose/structure
// free). The per-SECTION open-items ledger TASK_STATUS.polish.concerns.json is WRITTEN DETERMINISTICALLY
// by recordSectionLedger/writePolishLedger (D-1) after each section — never hand-curated. The converge
// verdict (state, off the quality reviewers' open flags) feeds that ledger's open set. (D1: the per-round
// prose-meaning fidelity gate was removed; meaning-drift is checked ONCE, advisory, by the end-of-run
// runFinalFidelitySweep — never blocking.)
// ─────────────────────────────────────────────────────────────────────────────────────────────────

export const meta = {
  name: 'polish',
  description: 'Polish a correct paper draft into publishable, human-sounding, fluent prose without changing the science. Handles single- and multi-file (\\input) LaTeX. Freezes data/claims/citations/symbols; rewrites wording, structure, and flow. A single context-aware reviser writes per file; a dynamic set of read-only reviewers (always covering fidelity + logic/results/readability/ai-tells) judges; a one-shot keynote pass sets per-section effort + global arc flags; the workflow self-judges convergence and ships per-round git history.',
  whenToUse: 'When the user wants to polish / refine / de-AI / clean up a paper draft (or one section) toward top-journal quality. Describe in natural language which paper, which section (or all), and which venue; the venue is resolved at runtime from the request (or, if none is named, via a recommend-then-pick prompt) — it is never read from config.',
  phases: [
    { title: 'Setup' },
    { title: 'Plan' },
    { title: 'Keynote' },
    { title: 'Sections' },
    { title: 'Cross-section sweep', optional: true },
    { title: 'Emit' },
  ],
}

// ── Resolve inputs ────────────────────────────────────────────────────────────
const pluginRoot = (args && args.plugin_root)
  || (typeof process !== 'undefined' && process.env && process.env.CLAUDE_PLUGIN_ROOT)
  || null
if (!pluginRoot) throw new Error('plugin_root must be passed (the slash command expands ${CLAUDE_PLUGIN_ROOT})')
// The input is the MASTER file: the root .tex that \input{}s the section files (e.g. main.tex),
// or a self-contained single-file paper.
const masterPath = (args && args.master_path) || null
if (!masterPath) throw new Error('master_path (the master/root manuscript file to polish) must be passed')
const target = (args && args.target) || 'all'            // a section name or `all`
// The venue the orchestrator parsed from the NL request (a venue-anchors rel it fuzzy-matched against
// the prepared list, or a bare name), or null if the request named none. NEVER read from config.
const venueArg = (args && args.venue) || null
const paperDir = dirname(masterPath)                     // where the manuscript lives; git ops scoped here
const projectDir = (args && args.project_dir)
  || (typeof process !== 'undefined' && process.env && process.env.CLAUDE_PROJECT_DIR)
  || paperDir

// ── Config (fail-soft: a missing key falls back to the baked-in default) ───────
function loadKnobs(root) {
  try {
    const raw = bash(
      `python3 -c "import yaml,json;print(json.dumps(yaml.safe_load(open('${root}/config/config.yaml')).get('polish',{})))"`
    )
    return JSON.parse(raw)
  } catch { return {} }
}
const KNOBS = loadKnobs(pluginRoot)

const SECTION_ORDER = KNOBS.section_order || ['introduction', 'results', 'methods', 'discussion', 'si', 'abstract']
const SKIP = new Set(KNOBS.sections_to_skip || [])
const MAX_ROUNDS = Math.max(2, KNOBS.max_rounds ?? 3)  // [[MECH]] hard floor of 2 rounds (one exception: a keynote effort=light section caps at 1 — see roundCap)
const NO_IMPROVE = KNOBS.no_improvement_rounds ?? 2
// [[MECH]] D5 self-limit: max concurrent section-runners in the Phase-2 fan-out. No on/off switch
// (D6) — `=1` is the implicit safety valve (fully serial); single-file / one-body-file degrade
// naturally regardless. polish never knows the caller's remaining concurrency budget, so it caps itself.
const MAX_PARALLEL_SECTIONS = Math.max(1, KNOBS.max_parallel_sections ?? 4)
// [[MECH]] D15: numeric severity weighting was REMOVED. Convergence + best-round are a categorical
// LADDER (clean > cosmetic-only > has-core), decided by scripts/polish_converge.py (D1 removed the
// `unrecoverable` rung — the per-round semantic-fidelity gate is gone).
// The reviewer still tags each flag with a categorical `severity` (an adjective) + a `disposition`;
// there is no weight to sum (config `flag_weights` is gone). A round collapses to ONE state read off
// its worst OPEN flag; deferred flags leave the open set; convergence is the strict empty-set model.
const EVAL = KNOBS.evaluate || {}
const SPAWN_MODE = EVAL.spawn_mode || 'single'           // single (default) | parallel — 第三刀 removed the dynamic `auto` packaging
const DIMENSIONS = EVAL.quality_dimensions || ['logic', 'results', 'readability', 'ai-tells']
const ABSTRACT = KNOBS.abstract || { candidates: 3, do_no_harm_floor: true }
// [dossier-12 G3] numeric replace_margin retired with the 1-10 scores: selection is a CATEGORICAL
// head-to-head vs the original (clearly_better | marginally_better | not_better); do-no-harm = ship
// a candidate ONLY on clearly_better (owner doctrine: no LLM numeric scoring anywhere).
const KEYNOTE_CFG = KNOBS.keynote || {}
const KEYNOTE_ENABLED = KEYNOTE_CFG.enabled !== false    // on by default; only skipped if explicitly false
const ROLES = KNOBS.roles || {}
// The diff report is a latexdiff inline-diff PDF (LaTeX papers with a TeX toolchain); no knobs.

// inject_thinking is per-role; appended to a role's goal prompt when non-null.
function think(role) {
  const k = ROLES[role] && ROLES[role].inject_thinking
  return k ? `\n\n${k}` : ''
}
function roleOpts(role, schema) {
  const r = ROLES[role] || {}
  return { role, schema, ...(r.model ? { model: r.model } : {}), subagent_type: r.subagent_type || role }
}

// ── Venue resolution (RUNTIME — resolved in Phase 0; threaded into every reviser/reviewer/keynote goal) ──
// The venue (register + vocabulary exceptions + conventions + acceptance bar + before→after anchors
// under skills/house-style/examples/venue-anchors/) is resolved from the RUNTIME request, NOT config:
// the orchestrator parses a venue out of the /polish prompt (commands/polish.md) and passes it as
// args.venue. There is NO config.target_venue and NO silent `default` fallback. resolveVenue returns a
// discriminated result the Phase-0 driver acts on: {status:'ok'|'venue-only'} use it; {status:'missing'}
// ABORT (unsupported venue); {status:'needs-picker'} no venue named -> recommend + AskUserQuestion picker.
const VENUE_BASE = 'skills/house-style/examples/venue-anchors'
// ── Venue file-system resolution → scripts/venue_resolve.py (shared, identical machine, with the /review side — spec/review-protocol.md §0) ──
// The DETERMINISTIC parts live in the script: venuePack (incl. [[core+overlay]] detection — a `_core/` sibling
// profile means this venue is an OVERLAY that COMPOSES over a shared CORE), the profile readiness check,
// resolveVenue's discriminated result, and listPreparedVenues. The ONE intentional difference from /review is
// now EXPLICIT: /polish OMITS --require-review-kit (it needs only a profile.md, not the review/ kit). The
// JUDGMENT steps (recommendVenue / runVenuePicker / venuePreamble below) stay here — they call an agent /
// AskUserQuestion. The orchestrator runs these as Bash; <root> is pluginRoot (where the venue anchors live).
function venuePack(rel, label, status) {   // -> {label,dir,profile,reviewDir,status,coreDir,coreProfile}
  return JSON.parse(bash(`python3 "${pluginRoot}/scripts/venue_resolve.py" pack --root "${pluginRoot}" --rel ${shq(rel)} --label ${shq(label)} --status ${shq(status)}`))
}
function resolveVenue(venueArg, root) {
  // venueArg: null (none named) | a string venue | {venue, field}. [[SEAM:venue-resolve]] named + profile.md
  // -> {status:'ok'} (or {status:'venue-only'} when a field was requested but only the parent venue has a
  // profile); named + absent -> {status:'missing'} (ABORT, no fallback, NEVER auto-select `default`); null ->
  // {status:'needs-picker'}. Deterministic — scripts/venue_resolve.py resolve (no --require-review-kit).
  const t = (typeof venueArg === 'string') ? { venue: venueArg } : (venueArg || {})
  const flags = (t.venue ? `--venue ${shq(t.venue)}` : ``) + (t.field ? ` --field ${shq(t.field)}` : ``)
  return JSON.parse(bash(`python3 "${pluginRoot}/scripts/venue_resolve.py" resolve --root ${shq(root)} ${flags}`.trim()))
}
// listPreparedVenues — every <venue>[/<field>] under venue-anchors/ that has a profile.md, EXCLUDING
// default/_TEMPLATE/_core. The picker's universe + the set a named venue is validated against. Deterministic.
function listPreparedVenues(root) {
  return JSON.parse(bash(`python3 "${pluginRoot}/scripts/venue_resolve.py" list --root ${shq(root)}`)).prepared
}

// recommendVenue — ONE read-only reviewer-shell subagent reads the paper's title/abstract/opening and
// picks the best fit from the prepared list. It RETURNS only (a subagent can never ask). No
// venuePreamble (the venue is undecided). Returns a rel in `prepared`, or null if it cannot tell.
const RECOMMEND_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['recommended_venue', 'rationale', 'confidence'],
  properties: {
    recommended_venue: { type: ['string', 'null'], description: 'one rel from the prepared list verbatim, or null if unsure' },
    rationale: { type: 'string' },
    confidence: { enum: ['high', 'medium', 'low'] },
  },
}
function recommendVenue(prepared, ms, root) {
  if (!prepared.length) return null
  const ctx = [ms.master, ...ms.files.slice(0, 2).map(f => f.path)].filter(Boolean)
  const goal = [
    `Read ${pluginRoot}/spec/spawn-prompts/polish-recommend-venue.md and do EXACTLY what it says — it is`,
    `the best-fit-venue recommender rubric (pick one rel from the prepared list verbatim, or null).`,
    `Substitute as you read it:`,
    `  <CONTEXT>=${ctx.join(', ')}  <PREPARED_LIST>=${prepared.map(v => `"${v}"`).join(', ')}`,
    think('reviewer'),
  ].join('\n')
  let rec
  try { rec = agent(goal, roleOpts('reviewer', RECOMMEND_SCHEMA)) } catch { return null }
  const pick = rec && rec.recommended_venue
  return prepared.includes(pick) ? pick : null
}

// runVenuePicker — orchestrator-side (Phase 0). Recommend, then AskUserQuestion over the prepared
// venues (recommended first, "(Recommended)") + a Stop option. NO `default` option. Stop / askUser
// unavailable -> ABORT (never auto-pick). Returns a venuePack.
function runVenuePicker(prepared, ms, root) {
  if (!prepared.length) throw new Error(`No venues are prepared under ${VENUE_BASE}/. Add a <venue>/<field>/profile.md (with a review/ kit) and re-run, or name a prepared venue in the prompt.`)
  const rec = recommendVenue(prepared, ms, root)
  const ordered = rec ? [rec, ...prepared.filter(v => v !== rec)] : prepared
  const options = ordered.map(v => ({
    label: v === rec ? `${v} (Recommended)` : v,
    description: v === rec ? 'Best fit for this paper (from its title/abstract).' : 'A prepared venue profile + review kit.',
  }))
  options.push({ label: 'Stop', description: 'Cancel; I will name a venue in the prompt instead.' })
  let res
  try {
    res = askUser([{ header: 'Venue', question: 'No venue was named. Which venue should set the register and the bar?', multiSelect: false, options }])
  } catch (e) {
    throw new Error(`No venue named and AskUserQuestion is unavailable (${String(e && e.message || e).split('\n')[0]}). Re-run naming one of: ${prepared.join('; ')}.`)
  }
  const picked = Array.isArray(res) ? res[0] : res
  if (!picked || /^stop$/i.test(String(picked).trim())) throw new Error('Run stopped at venue selection (no venue chosen).')
  const rel = String(picked).replace(/\s*\(Recommended\)\s*$/, '').trim()
  if (!prepared.includes(rel)) throw new Error(`Venue selection "${picked}" did not match a prepared venue. Prepared: ${prepared.join('; ')}.`)
  return venuePack(`${VENUE_BASE}/${rel}`, rel, 'picked')
}
let VENUE = null   // resolved in Phase 0 (after the manuscript is known, so the recommender can read it)

// Appended to every reviser/reviewer/AC goal (NOT fidelity or the consistency sweep — those are
// venue-neutral). Tells the agent which venue profile + anchors to load and apply.
function venuePreamble() {
  const profileBlock = VENUE.coreProfile
    ? [ `This venue is a sub-brand OVERLAY over a shared CORE — load and COMPOSE both: the core contract`,
        `${pluginRoot}/${VENUE.coreProfile} (family-wide rules) + the overlay ${pluginRoot}/${VENUE.profile}`,
        `(sub-brand deltas, which OVERRIDE the core). Also load ${pluginRoot}/${VENUE.coreDir}/voice.md (target`,
        `voice + the negative space of what this venue does NOT do) and ${pluginRoot}/${VENUE.coreDir}/structure.md (macro skeleton).` ]
    : [ `Load the venue profile at ${pluginRoot}/${VENUE.profile} (register, venue-acceptable vocabulary`,
        `exceptions, and conventions — spelling / abstract shape / reference style / section norms / bar).` ]
  return [
    `\nTARGET VENUE: ${VENUE.label}.`,
    ...profileBlock,
    `Apply it. When you write/revise a SECTION, READ the matching before→after few-shot at`,
    `${pluginRoot}/${VENUE.dir}/<section>.md (if present) and write toward that anchor — it is the strongest`,
    `signal of this venue's writing. Where the profile is silent, fall back to house-style defaults. Never`,
    `import another venue's conventions.`,
  ].join('\n')
}

// [[SEAM:empty-result-recovery]] — after ANY agent() that should produce substantive output, the
// orchestrator inspects the returned schema for a DEGENERATE result and recovers before trusting it:
//   • quality reviewer: empty dimensions_covered → re-spawn that group once with the missing dims named.
//   • reviser: committed=false → re-spawn once; if still no commit, ship the prior best round.
// (D1: the per-round fidelity gate is gone, so there is no fidelity-PASS-verification recovery here; the
// one end-of-run advisory fidelity sweep is read-only and never blocks.)
// Bound: at most ONE retry per call.

// ── Run-wide state (this file's memory; agents never see the drop logic) ───────
let baseSha = null
let gitRoot = null        // git toplevel (may be a PARENT of paperDir); report paths are relative to it
let branch = null         // the polish branch (polish-<ts>), created from the user's current HEAD
let format = 'latex'
let MS = null             // the resolved manuscript model {format, master, files[], contextFilesList, presentSections}
let KEYNOTE = null        // the Phase 1.5 whole-paper read (per-section effort + arc flags)
const closeCalls = []     // accumulated across the whole run, never reset; emitted once
const sectionReport = []  // {section, file, shippedRound, shippedSha, state, stopReason}
const scienceAdvisory = []// keynote's out-of-scope science-completeness notes (advisory only, never edited)
const couldNotFix = []    // W1: gray-area science judgments the reviser escalated to the author (per section/round)
const deferredFlags = []  // W5: flags the reviewer deliberately left in (disposition=deferred + defer_reason), surfaced in the report
const polishLedgerItems = []   // D-1: section-keyed open-items (task-ledger id/concern/status), rebuilt+committed each section
const polishMasterAdvisory = []// D-1: the cross-section sweep's whole-paper bucket (terminology/symbol/citation drift homed to master)
let abstractDecision = null  // 第一刀: the abstract pick (original vs candidate) + disqualified candidates, for the W2 report

// ════════════════════════════════════════════════════════════════════════════
// Phase 0 — Setup
// ════════════════════════════════════════════════════════════════════════════
phase('Setup')

// Resolve the manuscript model: format from the MASTER, \input/\include -> the real section files,
// each mapped to a (section, rubric). A single-file paper resolves to one unit per section heading.
MS = resolveManuscript(masterPath)
format = MS.format
log(`Resolved manuscript — ${MS.files.length} file unit(s): ${MS.files.map(f => `${f.rel}→${f.section}`).join(', ') || '(single file)'}`)

// Write the fidelity manifest so the pre-edit hook is armed: every editable prose file (a
// `manuscripts` list) + format + the data-file denylist (citations / data / tables / figures the
// reviser must never edit). Without this file the hook is a silent no-op.
bash(`mkdir -p "${projectDir}/.polish"`)
buildFidelityManifest(MS, format, projectDir)

// [[SEAM:venue-resolve]] Resolve the venue from the RUNTIME request now that the manuscript is known
// (the recommender reads its title/abstract). named+found -> use; named+missing -> ABORT (unsupported);
// none named -> recommend + AskUserQuestion picker. Placed BEFORE the git branch
// so any abort (missing venue / Stop / no-ask / none prepared) leaves no side effects on the repo.
{
  const vres = resolveVenue(venueArg, pluginRoot)
  if (vres.status === 'missing') {
    const prep = listPreparedVenues(pluginRoot)
    throw new Error(`Target venue "${vres.requested}" is not supported — no prepared profile under ${VENUE_BASE}/. Prepared venues: ${prep.join('; ') || '(none)'}. Re-run naming one of these (or name nothing to pick interactively).`)
  } else if (vres.status === 'needs-picker') {
    VENUE = runVenuePicker(listPreparedVenues(pluginRoot), MS, pluginRoot)   // may ABORT (Stop / no-ask / none prepared)
  } else {
    VENUE = vres
  }
}
log(`Venue — ${VENUE.label} (profile ${VENUE.profile}; ${VENUE.status})`)

// Git (SAFE): the manuscript may live in a subtree of a live repo on a feature branch with
// uncommitted work. Branch from the CURRENT HEAD with a unique name (never clobber a branch). The
// base commit is DEFERRED to Phase 1 and scoped to ONLY the in-scope files (+ master) — unrelated
// repo changes (incl. WIP in non-target sections) are never swept in.
bash(`git -C "${paperDir}" rev-parse --git-dir >/dev/null 2>&1 || git -C "${paperDir}" init`)
gitRoot = bash(`git -C "${paperDir}" rev-parse --show-toplevel`).trim()
const startBranch = bash(`git -C "${paperDir}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "(unborn)"`).trim()
branch = `polish-${bash(`date +%s`).trim()}`
bash(`git -C "${paperDir}" checkout -b "${branch}"`)        // from current HEAD; the user's branch ref is untouched
log(`Setup done — format=${format}, gitRoot=${gitRoot}, from=${startBranch}, branch=${branch} (base committed after Plan)`)

// ════════════════════════════════════════════════════════════════════════════
// Phase 1 — Plan
// ════════════════════════════════════════════════════════════════════════════
phase('Plan')
const present = MS.presentSections                       // which canonical sections actually exist
const wanted = target === 'all' ? SECTION_ORDER : [target]
const plannedSections = SECTION_ORDER.filter(s => wanted.includes(s) && present.includes(s) && !SKIP.has(s))
// The loop unit is a FILE; a section like `discussion` may map to >1 file (discussion.tex + conclusion.tex).
const plannedFiles = MS.files.filter(f => plannedSections.includes(f.section))
log(`Plan — file units: ${plannedFiles.map(f => f.rel).join(' → ') || '(none found)'}`)

// [[MECH]] D6/I4: base-commit ONLY the in-scope files (+ master, which the abstract path edits) —
// NOT every context file. Non-target files are never committed on the polish branch, so base:f ==
// HEAD:f → empty diff in the report, and the user's unrelated WIP stays uncommitted in the worktree.
const baseScopePaths = [...new Set([MS.master, ...plannedFiles.map(f => f.path)])]
bash(`git -C "${paperDir}" add -- ${baseScopePaths.map(p => `"${p}"`).join(' ')}`)
bash(`git -C "${paperDir}" diff --cached --quiet || git -C "${paperDir}" commit -m "polish: base (untouched draft)"`)
baseSha = readHeadSha()
log(`Base committed — base=${baseSha.slice(0, 8)} over ${baseScopePaths.length} in-scope file(s)`)

// ════════════════════════════════════════════════════════════════════════════
// Phase 1.5 — Keynote (whole-paper read, ONCE up front; seeds each section's round 1)
// ════════════════════════════════════════════════════════════════════════════
// One read-only pass over the WHOLE paper that does what no per-section reviewer can:
// (1) sets a per-section EFFORT level (proportionality — heavy where weak, light where good),
// (2) flags global ARGUMENT-ARC misalignments (gap↔contribution↔abstract-claim↔results) routed to the
//     owning section, and (3) parks any out-of-scope SCIENCE-completeness gaps as advisory only (never
//     fed into the freeze-the-science loop). Only runs when there is >1 unit to coordinate.
phase('Keynote')
if (KEYNOTE_ENABLED && plannedFiles.length > 1) {
  KEYNOTE = agent(
    [
      `Read ${pluginRoot}/spec/spawn-prompts/polish-keynote.md and do EXACTLY what it says — it is the`,
      `keynote whole-paper reviewer rubric (per-section effort + global argument-arc flags + science advisory).`,
      `Substitute as you read it:`,
      `  <MASTER>=${MS.master}  <CONTEXT_FILES>=${MS.contextFilesList.join(', ')}  <PLANNED_SECTIONS>=${plannedSections.join(', ')}`,
      venuePreamble(),
      think('reviewer'),
    ].join('\n'),
    roleOpts('reviewer', KEYNOTE_SCHEMA)
  )
  for (const a of (KEYNOTE.science_advisory || [])) scienceAdvisory.push(a)
  log(`Keynote — effort: ${(KEYNOTE.per_section || []).map(p => `${p.section}:${p.effort}`).join(', ')}; ` +
    `${(KEYNOTE.per_section || []).reduce((n, p) => n + (p.arc_flags || []).length, 0)} arc flag(s); ` +
    `${scienceAdvisory.length} science advisory note(s)`)
} else {
  log('Keynote — skipped (single unit or disabled)')
}

// ════════════════════════════════════════════════════════════════════════════
// Phase 2 — Sections
// ════════════════════════════════════════════════════════════════════════════
// Body sections parallelize over DISTINCT files (Step C): each gets its own git worktree + a
// section-runner that drives its whole converge loop in isolation, then they are assembled SERIALLY back
// onto the main polish branch (Step D). Sections that share a file (single-file papers all edit main.tex)
// cannot assemble cleanly from separate worktrees, so they stay SERIAL on the main tree — identical to
// the pre-parallel behavior (D6); a lone body file or max_parallel_sections=1 (D5 valve) degrade the
// same way. The abstract + cross-section sweep NEVER join the body fan-out (D8): the abstract needs the
// whole finished paper and writes the master \title; the sweep is cross-section by definition.
phase('Sections')
const bodyFiles = plannedFiles.filter(f => f.section !== 'abstract')
const abstractFile = plannedFiles.find(f => f.section === 'abstract') || null
const distinctBodyPaths = [...new Set(bodyFiles.map(f => f.path))]

if (distinctBodyPaths.length > 1 && MAX_PARALLEL_SECTIONS > 1) {
  // PARALLEL (multi-file): per-file worktree + section-runner, bounded; assembled serially (Step C/D).
  // Then the sweep (serial), then the abstract LAST — it condenses the finished, swept paper.
  runBodySectionsParallel(bodyFiles)
  if (target === 'all' && bodyFiles.length > 1) runCrossSectionSweep()
  if (abstractFile) runAbstractSection(abstractFile)
  runFinalFidelitySweep()   // D1: ONE advisory meaning-drift read per file, whole-paper, no revert
} else {
  // SERIAL (single-file / one body file / cap=1): the pre-parallel behavior, byte-for-byte — every
  // planned file in section order (abstract last), then the cross-section sweep.
  for (const file of plannedFiles) {
    if (file.section === 'abstract') runAbstractSection(file)
    else runBodySection(file)
  }
  if (target === 'all' && plannedFiles.length > 1) runCrossSectionSweep()
  runFinalFidelitySweep()   // D1: ONE advisory meaning-drift read per file, whole-paper, no revert
}

// ════════════════════════════════════════════════════════════════════════════
// Phase 3 — Emit
// ════════════════════════════════════════════════════════════════════════════
phase('Emit')
const gitLog = bash(`git -C "${paperDir}" log --oneline ${baseSha}..HEAD`)
const diffStat = bash(`git -C "${paperDir}" diff --stat ${baseSha}..HEAD`)

// Render the visual before/after report: a PDF inline-diff built by latexdiff → pdflatex (the standard
// LaTeX review form — added text blue-underlined, deleted text red strike-through, in place), across
// the whole \input-flattened manuscript. Reads git only; the work tree is untouched. Deterministic.
// Only a LaTeX paper with a TeX toolchain (latexdiff/pdflatex/bibtex) gets the PDF; otherwise the
// deliverable is the git diff (git log/diff base..HEAD). There is no HTML report.
let reportPath = null, reportKind = null
const haveTeX = format === 'latex' && (() => {
  try { bash('command -v latexdiff pdflatex bibtex >/dev/null 2>&1'); return true } catch (e) { return false }
})()
if (haveTeX) {
  reportPath = `${paperDir}/polish-diff.pdf`
  try {
    bash(`bash "${pluginRoot}/scripts/render_diff_pdf.sh" --repo "${gitRoot}" ` +
      `--master "${relTo(gitRoot, MS.master)}" --base ${baseSha} --head HEAD --out "${reportPath}"`)
    reportKind = 'pdf'
  } catch (e) {
    log(`PDF diff build failed (${String(e && e.message || e).split('\n')[0]}); the git diff is the deliverable.`)
    reportPath = null
  }
} else {
  log(`No PDF diff (${format !== 'latex' ? 'not a LaTeX paper' : 'no latexdiff/pdflatex/bibtex toolchain'}); the git diff base..HEAD is the deliverable.`)
}

// W2: the human-facing run report (per-section outcomes + stop reasons, abstract decision, close-calls,
// could_not_fix gray-area items, deferred flags, science advisory). One file the author actually reads.
const reportMdPath = writeReport()
log(reportMdPath ? `Wrote run report ${reportMdPath}` : 'Run report not written.')

// [[MECH]] D5: disarm the fidelity hook now the run is done — remove the manifest so the PreToolUse
// hook no-ops and the user's later edits to numbers/citations are NOT blocked. Idempotent (a fresh
// Phase 0 re-arms). Remove ONLY the manifest, not the whole .polish/ dir (verdict files live there).
bash(`rm -f "${projectDir}/.polish/fidelity-manifest.json"`)
log('Disarmed fidelity hook (removed .polish/fidelity-manifest.json).')
log('Polish complete.')

return {
  branch,
  base: baseSha,
  format,
  venue: VENUE.label,
  files: MS.files.map(f => ({ rel: f.rel, section: f.section, rubric: f.rubric })),
  sections: sectionReport,
  close_calls: closeCalls,
  science_advisory: scienceAdvisory,
  git_log: gitLog,
  diff_stat: diffStat,
  report: reportPath,
  report_md: reportMdPath,
  task_status: `${paperDir}/TASK_STATUS.polish.concerns.json`,   // D-1: the per-SECTION open-items ledger
  could_not_fix: couldNotFix,
  deferred_flags: deferredFlags,
  abstract_decision: abstractDecision,
  next_step:
    `Start with the run report: \`${reportMdPath || `${paperDir}/polish-report.md`}\` — per-section ` +
    `outcomes + stop reasons, the abstract decision, the ${closeCalls.length} fidelity close-call(s), ` +
    `the ${couldNotFix.length} gray-area item(s) left to you (could_not_fix), the ${deferredFlags.length} ` +
    `deliberately-kept flag(s), and the ${scienceAdvisory.length} science-advisory note(s). ` +
    (reportKind === 'pdf'
      ? `Then open the PDF inline-diff: \`${reportPath}\` — the compiled paper with added text underlined ` +
        `(blue) and deletions struck through (red), in place; the marked-up LaTeX source is alongside ` +
        `as \`${reportPath.replace(/\.pdf$/, '.tex')}\`. `
      : `No PDF was produced (non-LaTeX paper or no TeX toolchain). `) +
    `Full history on the ${branch} branch: \`git -C ${paperDir} log ${baseSha.slice(0, 8)}..HEAD\` ` +
    `and \`git -C ${paperDir} diff ${baseSha.slice(0, 8)}..HEAD\`; every change names the rule (and example) ` +
    `that drove it. Your original branch is untouched.`,
}

// ════════════════════════════════════════════════════════════════════════════
// runBodySection — the per-FILE converge loop (the Phase-5 analogue), SERIAL path.
// [dossier-12 G1] POINTERIZED: spec/section-loop.md is the ONE encoding of the loop (the parallel
// section_runner has always executed it from the file; now the serial path READS it too instead of
// carrying a ~100-line inline copy that had to be hand-mirrored). The JS keeps ONLY the caller-side
// bindings + report bookkeeping (sectionReport / recordSectionLedger / collectCNF / deferredFlags /
// writeVerdictFile) — the loop structure itself has exactly one home. When the loop changes, edit
// spec/section-loop.md; there is no inline copy left to drift.
// ════════════════════════════════════════════════════════════════════════════
function runBodySection(file) {
  phase('Sections')
  const section = file.section
  const rubric = file.rubric
  log(`── ${file.rel} (${section}) ──`)
  const kn = keynoteFor(section)
  const siblingPaths = MS.contextFilesList.filter(p => p !== file.path)   // for [[SEAM:context-depth]]
  // [[MECH]] W0: per-section LOCAL baseline. At entry HEAD = every PRIOR section already shipped, but
  // THIS file's blob is still its original text (untouched until now). Every restore/fidelity for this
  // section uses sectionBaseSha so it touches ONLY this section's own edits — never clobbering an
  // earlier shipped section. Single-file: all sections share main.tex, so sectionBaseSha pins the
  // already-shipped prefix; multi-file: this file is untouched ⇒ sectionBaseSha:file == baseSha:file
  // (strict generalization). The global baseSha stays the Phase-3 report base (base..HEAD).
  const sectionBaseSha = readHeadSha()
  // [[MECH]] 第二刀改b: keynote effort='light' is a HARD round cap of 1 (not a soft prior). A section the
  // whole-paper read judged already-good gets exactly one minimal pass — no marginal rounds to chase
  // cosmetic flags. Everything else runs to MAX_ROUNDS (light overrides the global 2-round floor for
  // THIS section only; the floor still governs normal/heavy sections).
  const roundCap = (kn && kn.effort === 'light') ? 1 : MAX_ROUNDS

  // [[MECH]] CANONICAL LOOP EXECUTION (dossier-12 G1). FIRST read ${pluginRoot}/spec/section-loop.md and
  // drive that loop IN-CONTEXT — serial means YOU are the runner on the main tree: do NOT spawn a
  // section_runner; spawn only the loop's own per-step subagents (reviser, quality reviewer) exactly as
  // the file's step goals prescribe. Bindings:
  //   SECTION=section  RUBRIC=rubric  FILE=file.path  REL=file.rel  GIT_C=paperDir
  //   BASE_SHA=sectionBaseSha  SIBLINGS=siblingPaths  ROUND_CAP=roundCap
  //   NO_IMPROVE=NO_IMPROVE  DIMENSIONS=DIMENSIONS  KEYNOTE_EFFORT=(kn ? kn.effort : 'n/a')
  //   ARC_FLAGS=(kn ? kn.arc_flags : [])
  //   CONVERGE = python3 "${pluginRoot}/scripts/polish_converge.py"   (convergence + best-round ONLY via
  //   the script — the IDENTICAL decider the parallel path calls; never judge them yourself, invariant 6)
  // SERIAL-ONLY deltas (the same ones this path always added around the loop):
  //   • append venuePreamble() + think('reviser') / think('reviewer') to the loop's sub-goals;
  //   • EVALUATE (loop §2) runs via runEvaluators(file) — the wrapper that honors evaluate.spawn_mode
  //     (single = one reviewer covers all DIMENSIONS; parallel = one per dimension; same schema);
  //   • round>1 open flags are formatted for the reviser with fmtFlags(lastRoundFlags);
  //   • pass every reviser return through collectCNF(rev, `${file.rel} (${section})`, round)   // W1
  //   • after each round: writeVerdictFile(file, round, verdicts), and push
  //     {round, sha: readHeadSha(), state, open_count, coverage, verdicts} onto `rounds` (trust HEAD,
  //     never a sha the agent reports);
  //   • ship-best (loop §4) restores via restoreSectionToCommit(file, best.sha) + commits via
  //     commitPaths([file.path], `polish: ${file.rel} — ship best round <R> (state=<S>)`).
  // The executed loop yields: rounds[] (all rounds), best (the SHIPPED round's entry), stopReason.
  const { rounds, best, stopReason } = executeSectionLoop_per_canonical_md()

  log(`${file.rel}: shipped round ${best.round} (state=${best.state}); stop=${stopReason}`)
  sectionReport.push({ section, file: file.rel, shippedRound: best.round, shippedSha: best.sha, state: best.state, stopReason })
  // [[MECH]] D-1: feed the shipped round's open-items into the per-SECTION ledger TASK_STATUS.polish.concerns.json
  // (rebuilt + committed each section so it is crash-safe + readable by the L0 PD pointer). Deterministic.
  recordSectionLedger(section, file, best)
  // W5: surface the flags the reviewer deliberately left in (the shipped round's deferred set).
  for (const q of (best.verdicts && best.verdicts.quality || []))
    for (const f of (q.flags || []))
      if (f.disposition === 'deferred') deferredFlags.push({ section, file: file.rel, round: best.round, severity: f.severity, dimension: f.dimension, issue: f.issue, defer_reason: f.defer_reason || '(no reason given)' })
}

// ════════════════════════════════════════════════════════════════════════════
// Parallel body sections (Step C/D) — fan-out per file into isolated worktrees, funnel-in serially.
// Each body file is polished by ONE section-runner subagent that drives the SAME revise→evaluate→
// converge loop as runBodySection, but INSIDE its own git worktree (+ its own branch), spawning its own
// reviser + fidelity + quality reviewers and calling scripts/polish_converge.py for the deterministic
// decision. Run bounded-concurrent; then assemble onto the main polish branch with a single writer (D9).
// ════════════════════════════════════════════════════════════════════════════
function runBodySectionsParallel(bodyFiles) {
  phase('Sections')
  // One temp dir holds every worktree (cleaned up in assembleSections). G4: every path is explicit and
  // absolute — bash env vars do not persist across the orchestrator's separate Bash calls.
  const wtRoot = bash(`mktemp -d -t polish-wt 2>/dev/null || mktemp -d "${paperDir}/.polish-wt.XXXXXX"`).trim()
  const units = bodyFiles.map(f => {
    const name = slug(f.rel)
    const wtdir = `${wtRoot}/${name}`
    const wbranch = `${branch}-${name}`
    const rel = relTo(gitRoot, f.path)
    // [[MECH]] W0: the worktree is created at baseSha — this file's UNTOUCHED original (multi-file:
    // sectionBaseSha:file == baseSha:file). The worktree mirrors the whole repo from gitRoot; the file
    // lives at `${wtdir}/${rel}`. -b makes the section's own branch so the main polish branch is free
    // for assembly. No `|| true` — a worktree-add failure must surface (G10).
    bash(`git -C "${paperDir}" worktree add -b "${wbranch}" "${wtdir}" "${baseSha}"`)
    return { file: f, wtdir, branch: wbranch, rel, wfile: `${wtdir}/${rel}` }
  })
  // Bounded fan-out (D5): at most MAX_PARALLEL_SECTIONS section-runners at once. Results align to units.
  const results = boundedParallel(units.map(u => () => runSection(u)), MAX_PARALLEL_SECTIONS)
  assembleSections(units, results, wtRoot)
}

function boundedParallel(thunks, cap) {
  // [[MECH]] run `thunks` with at most `cap` concurrent (D5/G7). Reproduce as sequential batches of
  // `cap`: spawn a batch with parallel(), await it, then the next — so peak concurrency is bounded and
  // results stay in `thunks` order. cap>=1 (clamped at the knob).
  const out = []
  for (let i = 0; i < thunks.length; i += cap) out.push(...parallel(thunks.slice(i, i + cap)))
  return out
}

function runSection(unit) {
  // Spawn ONE section-runner for this file. It owns the whole loop inside `unit.wtdir` and returns the
  // structured result (SECTION_RESULT_SCHEMA). A null result (skipped/dead runner) is handled in
  // assembleSections (keeps the file's base) — the empty-result-recovery contract.
  const kn = keynoteFor(unit.file.section)
  const siblingReadPaths = MS.contextFilesList
    .filter(p => p !== unit.file.path)
    .map(p => `${unit.wtdir}/${relTo(gitRoot, p)}`)   // siblings live in THIS worktree (read-only, at base)
  return agent(sectionRunnerGoal(unit, kn, siblingReadPaths), roleOpts('section_runner', SECTION_RESULT_SCHEMA))
}

function sectionRunnerGoal(unit, kn, siblingReadPaths) {
  // The section-runner reproduces the CANONICAL loop one level down, pointed at the worktree. The loop
  // STRUCTURE (steps, freeze discipline, converge contract, sub-goal templates, return schema) is the single
  // source spec/section-loop.md — this goal supplies the BINDINGS + the dynamic keynote/arc lines and tells
  // the runner to read + execute that file (the same loop runBodySection runs serially). The "how" of writing
  // quality lives in the skills the sub-agents pull. Drift surface removed: the 95-line inline copy is gone.
  const { file, wtdir, branch: wbranch, rel, wfile } = unit
  const section = file.section, rubric = file.rubric
  const knArc = (kn && kn.arc_flags && kn.arc_flags.length) ? fmtSweep(kn.arc_flags) : null
  const roundCap = (kn && kn.effort === 'light') ? 1 : MAX_ROUNDS
  return [
    `You are the SECTION-RUNNER for the ${section} of the paper. You OWN this one file's entire polishing`,
    `loop, running INSIDE an isolated git worktree, and you RETURN SECTION_RESULT_SCHEMA — you never touch any`,
    `other file, any sibling section, or the main working tree. Drive the loop by SPAWNING subagents (you have`,
    `the Task tool); the reviser + quality reviewer are the default \`claude\` subagent (model sonnet).`,
    ``,
    `FIRST read the canonical loop: ${pluginRoot}/spec/section-loop.md — it is the SINGLE SOURCE for the`,
    `revise→evaluate→converge steps, the freeze discipline, the reviser + quality-reviewer sub-goal templates,`,
    `the deterministic-converge contract, and the SECTION_RESULT_SCHEMA return. Execute that loop EXACTLY,`,
    `substituting these bindings:`,
    `  • SECTION = ${section}   • RUBRIC = ${rubric}`,
    `  • FILE  (absolute, the one file you edit) = ${wfile}`,
    `  • REL   (repo-relative blob path)         = ${rel}`,
    `  • GIT_C (every git command is \`git -C "${wtdir}"\`; the worktree shares the repo object DB) = ${wtdir}`,
    `  • BASE_SHA (this file's untouched original, W0) = ${baseSha}    • BRANCH = ${wbranch}`,
    `  • SIBLINGS (READ-ONLY context) = ${siblingReadPaths.join(', ') || '(none)'}`,
    `  • CONVERGE = python3 "${pluginRoot}/scripts/polish_converge.py"   (decide convergence + best-round ONLY`,
    `    via this script — never judge them yourself, invariant 6)`,
    `  • ROUND_CAP = ${roundCap}   • NO_IMPROVE = ${NO_IMPROVE}   • DIMENSIONS = ${JSON.stringify(DIMENSIONS)}`,
    `  • KEYNOTE_EFFORT = ${kn ? kn.effort : 'n/a'}`,
    `  • ARC_FLAGS = ${knArc ? `(resolve from WITHIN this section, no new material)\n${knArc}` : '(none)'}`,
    venuePreamble(),
    think('section_runner'),
  ].filter(Boolean).join('\n')
}

function assembleSections(units, results, wtRoot) {
  // [[MECH]] Step D — the BARRIER write-back: bring each section branch's finished file onto the main
  // polish branch. The body files are disjoint (distinct paths), so checkout-per-file never conflicts;
  // ONE add + ONE commit keeps the main index single-writer (D9/G9). No `|| true` on the merge commit —
  // a real failure must surface (G10). Then buffer-write each runner's per-round verdict files + roll up
  // the run-wide report state, and remove the worktrees.
  phase('Sections')
  const got = []
  for (let i = 0; i < units.length; i++) {
    const u = units[i], r = results[i]
    if (!r) { log(`assemble: ${u.file.rel} — section-runner returned nothing; keeping its base text`); continue }
    // PATH RULE: working-tree checkout uses git -C paperDir + the absolute file path (like restoreSectionToCommit).
    bash(`git -C "${paperDir}" checkout "${r.branch || u.branch}" -- "${u.file.path}"`)
    got.push(u.file.path)
  }
  if (got.length) {
    bash(`git -C "${paperDir}" add -- ${got.map(p => `"${p}"`).join(' ')}`)
    bash(`git -C "${paperDir}" diff --cached --quiet || git -C "${paperDir}" commit -m "polish: assemble ${got.length} parallel section(s)"`)
    log(`assemble: merged ${got.length} parallel section(s) onto ${branch}`)
  }
  // Roll up results into run-wide state + write per-round verdict files (serial, main tree → no race).
  for (let i = 0; i < units.length; i++) {
    const u = units[i], r = results[i]
    if (!r) { sectionReport.push({ section: u.file.section, file: u.file.rel, shippedRound: 0, shippedSha: null, state: 'failed', stopReason: 'runner_failed' }); continue }
    for (const rd of (r.rounds || [])) writeVerdictFile(u.file, rd.round, rd.verdicts || {})
    // D1: the runner returns no close_calls — drift is surfaced once, advisory, by runFinalFidelitySweep.
    for (const c of (r.could_not_fix || [])) couldNotFix.push({ where: `${u.file.rel} (${u.file.section})`, ...c })
    for (const f of (r.deferred_flags || [])) deferredFlags.push({ section: u.file.section, file: u.file.rel, round: r.best_round, ...f })
    sectionReport.push({ section: u.file.section, file: u.file.rel, shippedRound: r.best_round, shippedSha: r.shipped_sha, state: r.state || '—', stopReason: r.stop_reason })
    // [[MECH]] D-1: record the parallel section-runner's SHIPPED round into the per-SECTION open-items ledger.
    const bestRd = (r.rounds || []).find(rd => rd.round === r.best_round)
    recordSectionLedger(u.file.section, u.file, { round: r.best_round, state: r.state, verdicts: (bestRd && bestRd.verdicts) || {} })
  }
  // Clean up worktrees + their branches (cleanup `|| true` is fine — it is not a commit path).
  for (const u of units) bash(`git -C "${paperDir}" worktree remove --force "${u.wtdir}" 2>&1 || true`)
  bash(`git -C "${paperDir}" worktree prune 2>&1 || true`)
  bash(`rm -rf "${wtRoot}" 2>&1 || true`)
  log(`assemble: cleaned ${units.length} worktree(s)`)
}

// ════════════════════════════════════════════════════════════════════════════
// runAbstractSection — revise-and-auto-select (forked body; runs last). 第一刀: candidates are
// MINIMAL revisions of the existing abstract (not from-scratch generations); both fidelity AND a hard
// ai-tells gate disqualify before scoring; the original is replaced only by a margin (do-no-harm).
// ════════════════════════════════════════════════════════════════════════════
function runAbstractSection(file) {
  phase('Sections')
  log(`── ${file.rel} (abstract — revise-and-auto-select) ──`)
  const n = ABSTRACT.candidates ?? 3
  const kn = keynoteFor('abstract')

  // 1. Reviser emits N title + N abstract candidates (minimal revisions; prose IS in the schema — bounded).
  const out = agent(
    [
      `Read ${pluginRoot}/spec/spawn-prompts/polish-abstract-candidates.md and do EXACTLY what it says — it`,
      `is the title+abstract revise-and-select candidate-generation rubric (minimal revision; original is a`,
      `first-class baseline candidate). Substitute as you read it:`,
      `  <FILE>=${file.path}  <MASTER>=${MS.master}  <CONTEXT_FILES>=${MS.contextFilesList.join(', ')}  <N>=${n}`,
      `  <ARC_NOTES>=${kn && kn.arc_flags && kn.arc_flags.length ? `\n${fmtSweep(kn.arc_flags)}` : '(none)'}`,
      venuePreamble(),
      think('reviser'),
    ].join('\n'),
    roleOpts('reviser', ABSTRACT_CANDIDATES_SCHEMA)
  )

  // 2. Judge every candidate HEAD-TO-HEAD against the original (categorical — dossier-12 G3; owner
  //    doctrine: no numeric scoring). The original is judged too, but only for its GATES (is it clean?);
  //    its vs_original is the fixed 'baseline'. Fidelity/ai-tells disqualify BEFORE any comparison is weighed.
  const pool = [...out.candidates, { id: 'original', title: out.original.title, abstract: out.original.abstract }]
  const scored = parallel(pool.map(c => () => agent(
    [
      `Read ${pluginRoot}/spec/spawn-prompts/polish-abstract-score.md and do EXACTLY what it says — it is the`,
      `abstract+title candidate judging rubric (two disqualifying gates fidelity + ai-tells, then ONE`,
      `categorical head-to-head verdict vs the ORIGINAL — no numeric scores).`,
      `Substitute as you read it:`,
      `  <CAND_ID>=${c.id}  <TITLE>=${c.title}  <ABSTRACT>=${c.abstract}`,
      `  <ORIG_TITLE>=${out.original.title}  <ORIG_ABSTRACT>=${out.original.abstract}`,
      venuePreamble(),
      think('reviewer'),
    ].join('\n'),
    roleOpts('reviewer', ABSTRACT_SCORE_SCHEMA)
  )))

  // 3. JS picks categorically; do-no-harm unless a CLEAN candidate is CLEARLY better than the original.
  // [[MECH]] A candidate is eligible only if BOTH gates pass — fidelity (meaning preserved) AND
  // ai_tells_clean (no em-dash / banned word / interchangeable template). Both disqualify BEFORE the
  // head-to-head is weighed: a dirty candidate never ships however it compares.
  const TIER = { clearly_better: 2, marginally_better: 1, not_better: 0, baseline: 0 }
  const eligible = scored.filter(s => s.fidelity_ok && s.ai_tells_clean && s.candidate_id !== 'original')
  const best = eligible.reduce((a, b) => ((TIER[b.vs_original] || 0) > (TIER[a.vs_original] || 0) ? b : a),
    { candidate_id: null, vs_original: 'not_better' })
  const orig = scored.find(s => s.candidate_id === 'original')
  const origClean = !!(orig && orig.fidelity_ok && orig.ai_tells_clean)
  // Replace a CLEAN original ONLY on a clearly_better clean candidate (marginally_better = churn, keep
  // the original). A dirty original (origClean=false) is never the do-no-harm fallback when a clean
  // candidate exists — then the BEST clean candidate ships whatever its tier; the original is only kept
  // when NO clean candidate was produced at all (degenerate — surfaced in the report).
  const clearlyBetter = best.candidate_id && best.vs_original === 'clearly_better'
  const keepOriginal = ABSTRACT.do_no_harm_floor !== false && (!best.candidate_id || (origClean && !clearlyBetter))

  if (keepOriginal) {
    log(`abstract: no clean candidate is CLEARLY better than the original — keeping the original (do-no-harm floor)`)
    abstractDecision = { shipped: 'original', reason: best.candidate_id ? 'no_clean_clear_win' : 'no_clean_candidate', best_vs_original: best.candidate_id ? best.vs_original : null, original_clean: origClean, disqualified: scored.filter(s => !(s.fidelity_ok && s.ai_tells_clean)).map(s => ({ id: s.candidate_id, fidelity_ok: s.fidelity_ok, ai_tells_clean: s.ai_tells_clean })) }
    sectionReport.push({ section: 'abstract', file: file.rel, shippedRound: 0, shippedSha: readHeadSha(), state: 'clean', stopReason: 'do_no_harm' })
    return
  }
  // 4. Reviser writes the winning candidate in place and commits (records the runners-up).
  const winner = pool.find(c => c.id === best.candidate_id)
  const rev = agent(
    [
      `You are the reviser. Replace the abstract in ${file.path} and the \\title{...} in the master`,
      `${MS.master} with the selected candidate below, using Edit/MultiEdit (the fidelity hook still`,
      `applies to both files). Commit ONLY those two files (\`git -C ${paperDir} add -- ${file.path} ${MS.master}\``,
      `then commit) with a message that records the candidates NOT chosen.`,
      `Return the schema.`,
      `\nSELECTED TITLE: ${winner.title}\n\nSELECTED ABSTRACT: ${winner.abstract}`,
      think('reviser'),
    ].join('\n'),
    roleOpts('reviser', REVISE_SCHEMA)
  )
  collectCNF(rev, `${file.rel} (abstract)`, 1)   // W1
  log(`abstract: shipped candidate ${best.candidate_id} (${best.vs_original} vs original${origClean ? '' : '; original was DIRTY'})`)
  abstractDecision = { shipped: best.candidate_id, reason: origClean ? 'clearly_better_than_original' : 'original_dirty_best_clean_candidate', best_vs_original: best.vs_original, original_clean: origClean, disqualified: scored.filter(s => !(s.fidelity_ok && s.ai_tells_clean)).map(s => ({ id: s.candidate_id, fidelity_ok: s.fidelity_ok, ai_tells_clean: s.ai_tells_clean })) }
  sectionReport.push({ section: 'abstract', file: file.rel, shippedRound: 1, shippedSha: readHeadSha(), state: 'clean', stopReason: 'selected' })
}

// ════════════════════════════════════════════════════════════════════════════
// runCrossSectionSweep — one consistency pass: read-only diagnose, routed per file to fix
// ════════════════════════════════════════════════════════════════════════════
function runCrossSectionSweep() {
  phase('Cross-section sweep')
  const sweep = agent(
    [
      `Read ${pluginRoot}/spec/spawn-prompts/polish-cross-section-sweep.md and do EXACTLY what it says — it`,
      `is the read-only cross-section consistency sweep rubric (venue-neutral). Substitute as you read it:`,
      `  <MASTER>=${MS.master}  <CONTEXT_FILES>=${MS.contextFilesList.join(', ')}  <PLANNED_SECTIONS>=${plannedSections.join(', ')}`,
      think('reviewer'),
    ].join('\n'),
    roleOpts('reviewer', SWEEP_SCHEMA)
  )
  if (!sweep.flags || sweep.flags.length === 0) { log('sweep: clean'); return }

  // Route each flag to the file that owns it; flags homed to the master (captions/back-matter, not a
  // loop unit) are advisory only. Then, per file with ≥1 flag, ONE reviser edits ONLY that file.
  const byFile = new Map()
  for (const fl of sweep.flags) {
    const owner = routeFlag(fl)
    if (!owner) { log(`sweep: master/unowned flag → advisory only: ${fl.detail || fl.type}`); scienceAdvisory.push({ issue: fl.detail || fl.type, where: 'master', why: 'cross-section flag homed to non-looped master prose' }); polishMasterAdvisory.push({ type: fl.type || 'drift', detail: fl.detail || fl.type || '', locations: fl.locations || [] }); continue }
    if (!byFile.has(owner.path)) byFile.set(owner.path, { file: owner, flags: [] })
    byFile.get(owner.path).flags.push(fl)
  }
  for (const { file, flags } of byFile.values()) {
    const preSweepSha = readHeadSha()   // W0: the sweep fidelity base — judge ONLY the sweep's own edit, not the section work already shipped into this file
    const rev = agent(
      [
        `You are the reviser. Fix these cross-section consistency issues in ONLY ${file.path} with`,
        `minimal edits (freeze the science; the hook still applies). Commit ONLY ${file.path}`,
        `(\`git -C ${paperDir} add -- ${file.path}\` then commit). Return the schema.`,
        fmtSweep(flags),
        think('reviser'),
      ].join('\n'),
      roleOpts('reviser', REVISE_SCHEMA)
    )
    collectCNF(rev, `sweep:${file.rel}`, 1)   // W1
    const fidelity = runFidelity(file, readHeadSha(), preSweepSha)
    if (fidelity.verdict === 'FAIL') {
      agent(
        [`You are the reviser. The sweep edits to ${file.path} drifted meaning; restore exactly (only ${file.path}):`, fmtDrift(fidelity.drift_items), `Commit. Return the schema.`].join('\n'),
        roleOpts('reviser', REVISE_SCHEMA)
      )
    }
    for (const cc of (fidelity.close_calls || [])) closeCalls.push({ section: `sweep:${file.section}`, file: file.rel, round: 1, ...cc })
  }
  // [[MECH]] D-1: the cross-section sweep is a WHOLE-PAPER sensor (Doc A §10-E) — record its findings as a
  // cross-cutting concern: each owned flag becomes a section-keyed CLOSED item (the sweep fixed it inline);
  // master/unowned drift lives in the master-advisory bucket (above). Then rebuild + commit the ledger.
  for (const { file, flags } of byFile.values())
    for (const fl of flags)
      polishLedgerItems.push({ id: `POL-${ledgerSlug(file.section)}-consistency-${ledgerSlug(fl.type || 'drift')}-${polishLedgerItems.length}`, concern: 'prose.consistency', unit: file.section, status: 'closed', opened_round: 1, closed_round: 1, last_touched_round: 1, evidence: `${file.rel} (cross-section sweep)`, source: 'sweep', issue: fl.detail || fl.type || 'cross-section consistency', defer_reason: null })
  if (byFile.size || polishMasterAdvisory.length) writePolishLedger()
  log(`sweep: routed ${sweep.flags.length} flag(s) across ${byFile.size} file(s)`)
}

// ════════════════════════════════════════════════════════════════════════════
// runFinalFidelitySweep — D1: the ONE semantic-fidelity read per file, run ADVISORY at the very end
// (replacing the deleted per-round, per-section gate — ~25×/paper → ~1×/file). It does NOT revert and
// NEVER blocks: it reuses the read-only `fidelity` agent to compare each polished file base→HEAD and
// surfaces any meaning-drift (dropped hedge, claim-strength shift, citation re-attached, invented causal
// link, scope inflation) + close-calls into the run-wide closeCalls list (tagged round:'final',
// advisory:true) so the report's close-calls section + next_step render them for the author to skim.
// The base_read_attestation self-item is excluded (it is bookkeeping, not drift). A,类 token/provenance
// is still enforced deterministically by the pre-edit hook on every edit; this is the C,类 advisory残留.
// ════════════════════════════════════════════════════════════════════════════
function runFinalFidelitySweep() {
  phase('Cross-section sweep')
  const head = readHeadSha()
  for (const file of plannedFiles) {
    const fidelity = runFidelity(file, head, baseSha)
    for (const d of (fidelity.drift_items || [])) {
      if (d && d.check === 'base_read_attestation') continue
      closeCalls.push({ section: file.section, file: file.rel, round: 'final', advisory: true, why: d.why || '', original: d.original || '', revised: d.revised || '' })
    }
    for (const cc of (fidelity.close_calls || [])) {
      if (cc && cc.check === 'base_read_attestation') continue
      closeCalls.push({ section: file.section, file: file.rel, round: 'final', advisory: true, ...cc })
    }
  }
  log(`final fidelity sweep: ${plannedFiles.length} file(s) checked (advisory; no revert)`)
}

// Route a sweep flag to the file unit that owns it (null = master / unowned → advisory).
function routeFlag(fl) {
  const candidates = MS.files.filter(f => f.section === fl.section)
  if (candidates.length === 0) return null            // [[MECH]] master/unowned → advisory
  if (candidates.length === 1) return candidates[0]   // [[MECH]] single owner
  // [[SEAM:sweep-routing]] >1 file for this section (e.g. discussion.tex + conclusion.tex). First the
  // mechanical grep on the flag's snippet; if it lands in EXACTLY one candidate, use it.
  const needle = (fl.detail || (fl.locations && fl.locations[0]) || '').trim().slice(0, 40)
  if (needle) {
    const hits = candidates.filter(c => {
      const n = bash(`grep -cF ${shq(needle)} "${c.path}" 2>/dev/null || echo 0`).trim()
      return n && n !== '0'
    })
    if (hits.length === 1) return hits[0]
  }
  // grep inconclusive (0 hits, or >1): the orchestrator reads the flag detail/locations + the
  // candidate files and picks the OWNING file by where the offending terminology actually lives.
  // FLOOR: choose only among `candidates`; if undecidable, fall back to candidates[0]; NEVER edit two
  // files for one flag.
  return candidates[0]
}

// ════════════════════════════════════════════════════════════════════════════
// Evaluation — quality reviewers (dynamic count, full coverage). D1: the per-round semantic-fidelity
// gate was removed — drift is checked ONCE per file by the篇末 advisory sweep (runFinalFidelitySweep),
// not every round. A,类的确定性 token/provenance hook (buildFidelityManifest → check_fidelity.py) is
// untouched and still arms every reviser edit.
// ════════════════════════════════════════════════════════════════════════════
function runEvaluators(file) {
  const kn = keynoteFor(file.section)
  const siblingPaths = MS.contextFilesList.filter(p => p !== file.path)   // for [[SEAM:context-depth]] (quality reviewers)

  // Quality reviewers: the default is a SINGLE reviewer covering every dimension, now under an explicit
  // DEPTH MANDATE — it first sweeps all dimensions so COVERAGE stays floor-guaranteed (the agent never
  // decides whether a dimension is checked, only which skills it pulls to cover one), then sinks the bulk
  // of its diagnostic into the single most lethal writing thread of the section. Breadth is the floor;
  // depth on the worst thread is the goal.
  // (spawn_mode: parallel remains as a one-reviewer-per-dimension option.)
  let groups = SPAWN_MODE === 'parallel'
    ? DIMENSIONS.map(d => [d])                              // one reviewer per dim
    : [DIMENSIONS]                                          // single (default): one reviewer covers all dims
  // [[MECH]] coverage floor: the union of groups MUST equal DIMENSIONS; else fall back to one reviewer.
  if (DIMENSIONS.some(d => !groups.flat().includes(d))) groups = [DIMENSIONS]
  const qualityThunks = groups.map(dims => () => agent(
    [
      `Review the ${dims.join(' and ')} dimension(s) of the ${file.section} of the paper at the`,
      `committed revision. The file under review is ${file.path}. Retrieve the matching capability`,
      `skill(s) (${dims.map(d => 'check-' + (d === 'ai-tells' ? 'ai-tells' : d)).join(', ')}) +`,
      `section-${file.rubric} + house-style + context-scope. [[SEAM:context-depth]] Read ${file.path}`,
      `first; per context-scope decide whether you also need the sibling sections (read-only):`,
      `${siblingPaths.join(', ') || '(none)'} — keynote effort = ${kn ? kn.effort : 'n/a'} (the prior).`,
      `DEPTH MANDATE: do NOT spread effort uniformly. First sweep ALL your assigned dimension(s) so coverage`,
      `is complete, then SINK the bulk of your diagnostic into the SINGLE most lethal writing thread of this`,
      `section and go deep on it — name that thread as highest_leverage_fix. Breadth is the floor; a thorough`,
      `kill of the worst thread beats four shallow uniform passes.`,
      `Apply each skill's thresholds. Mark a flag disposition='deferred' when (a) it concerns a structure`,
      `deliberately kept (leave it as-is), (b) it needs the author (out-of-scope here), OR (c) it is a`,
      `TRIVIAL cosmetic tell (minor_tell / recurring_readability) that has ALREADY had ≥1 fix attempt and`,
      `is not worth another round — a lone "However,", one parallel pair. A cosmetic flag you have NOT yet`,
      `tried is 'actionable' (it earns its one attempt before you may defer it); do NOT keep grinding a`,
      `trivial nit past one attempt. Every 'deferred' flag MUST carry a one-line defer_reason (it leaves`,
      `the open set but the author reviews it). Everything else you genuinely want changed is 'actionable'.`,
      `Return the schema with dimensions_covered = [${dims.map(d => `"${d}"`).join(', ')}] and each`,
      `flag tagged with severity + disposition (+ defer_reason when deferred).`,
      venuePreamble(),
      think('reviewer'),
    ].join('\n'),
    roleOpts('reviewer', EVAL_QUALITY_SCHEMA)
  ))

  let quality = parallel(qualityThunks)
  // [[SEAM:empty-result-recovery]] re-spawn a reviewer that covered nothing (the contract by roleOpts).
  quality = quality.map((q, i) => (q && (q.dimensions_covered || []).length) ? q : qualityThunks[i]())
  return { quality }
}

function runFidelity(file, sha, base = baseSha) {
  // [[MECH]] the gate itself. The `fidelity` role now routes to agents/fidelity.md (Read+Bash, NO
  // Edit/Write), so it can git-show the base and actually compare. `base` is the comparison baseline —
  // the section-local W0 baseline (this section's pre-edit text) for the section loop, or the pre-sweep
  // sha for the consistency sweep — so fidelity judges ONLY this section's / this edit's own meaning-drift
  // and never re-flags an already-shipped earlier section. `sha` is the committed round revision. Paths
  // follow the PATH RULE (gitRoot-relative + git -C gitRoot).
  const rel = relTo(gitRoot, file.path)
  return agent(
    [
      `You are the fidelity gate for the ${file.section}: judge ONLY semantic meaning-drift between the`,
      `BASE and the committed revision of ${file.path}. Retrieve check-fidelity and apply its protocol.`,
      `  BASE (original):       git -C "${gitRoot}" show ${base}:${rel}`,
      `  REVISED (this round):  git -C "${gitRoot}" show ${sha}:${rel}`,
      `Return EVAL_FIDELITY_SCHEMA.`,
      think('fidelity'),
    ].join('\n'),
    roleOpts('fidelity', EVAL_FIDELITY_SCHEMA)
  )
}

// ════════════════════════════════════════════════════════════════════════════
// Convergence + best-round — owned by scripts/polish_converge.py (Step B/D4), never told to agents.
// The orchestrator (serial path) and the section-runner (Phase 2 parallel) both shell out to the SAME
// script, so the decision is deterministic, identical across paths, and unit-tested
// (scripts/test_polish_converge.py). D15: it is NO LONGER a weighted sum — a round collapses to ONE
// categorical STATE (clean > cosmetic-only > has-core) read off its worst OPEN flag; convergence is the
// strict empty-set model (state==clean ∧ full coverage); best-round is the highest state on the ladder
// (ties: latest). D1: the per-round semantic-fidelity gate is gone — there is no `unrecoverable` state
// any more (the script keeps the RANK key only for backward-compat with old on-disk ledgers).
// ════════════════════════════════════════════════════════════════════════════
// (dossier-12 G1) convergeRound/pickBestRound/stopMessage remain as the SERIAL driver's exact call
// recipes for the canonical loop's CONVERGE steps (spec/section-loop.md §3/§4 name the same heredoc
// contract) — payload shape only, never judgment.
function convergeRound(input) {
  // [[MECH]] input: {round, roundCap, dimensions, noImprove, history:[{state}], current:{verdicts:{quality}}}.
  //   Returns {state, open_count, coverage, full_coverage, no_improvement_streak, stop, stop_reason}.
  //   `history` is the PRIOR rounds' state; the script reads this round's state off the verdicts. No
  //   weights — the reviewer's categorical severities decide.
  const payload = JSON.stringify({
    mode: 'round', round: input.round, round_cap: input.roundCap,
    dimensions: input.dimensions, no_improvement_rounds: input.noImprove,
    history: input.history, current: input.current,
  })
  return JSON.parse(bash(`python3 "${pluginRoot}/scripts/polish_converge.py" <<'PCONV'\n${payload}\nPCONV`))
}

function pickBestRound(rounds) {
  // [[MECH]] rounds: [{round, state}]. Returns {best_round, best_state, do_no_harm}. Highest state on the
  // ladder clean>cosmetic-only>has-core wins (ties: latest). D1: no round is ever `unrecoverable`, so
  // do_no_harm is always false — the caller ALWAYS ships the best round.
  const payload = JSON.stringify({ mode: 'best', rounds })
  return JSON.parse(bash(`python3 "${pluginRoot}/scripts/polish_converge.py" <<'PCONV'\n${payload}\nPCONV`))
}

function stopMessage(reason, round, roundCap) {
  // Human-facing log line for a converge stop_reason (the decision itself is the script's).
  switch (reason) {
    case 'clean': return `converged (open set empty — every concern closed or deferred) at round ${round}`
    case 'no_improvement': return `stopped — no net improvement for ${NO_IMPROVE} rounds`
    case 'light_single_pass': return `stopped — light single pass (keynote effort=light)`
    case 'max_rounds': return `stopped — max ${roundCap} rounds`
    default: return `stopped — ${reason}`
  }
}

function keynoteFor(section) {
  if (!KEYNOTE || !KEYNOTE.per_section) return null
  return KEYNOTE.per_section.find(p => p.section === section) || null
}

function collectCNF(rev, where, round) {
  // W1: pull a reviser's could_not_fix items into the run-wide ledger for the W2 report. Tagged with
  // where it arose; harmless when the field is absent (the common case — most rounds escalate nothing).
  for (const c of (rev && rev.could_not_fix || [])) couldNotFix.push({ where, round, ...c })
}

// ── Git / fs / manuscript helpers — the orchestrator runs these via Bash ───────
// [[MECH]] PATH RULE: for any `<rev>:<path>` (git show/diff of a blob), the path is ALWAYS
// gitRoot-relative via relTo(gitRoot, abs) and the command runs with `git -C "${gitRoot}"`.
// Working-tree pathspec ops (add/checkout/commit `-- <path>`) use `git -C "${paperDir}"` with the
// absolute/file.path form (pathspecs resolve against cwd, not rev:path). `.polish/` fs paths use
// projectDir. Do not mix the three. (restoreSectionToCommit below is the pathspec form — leave it.)
function readHeadSha() {
  return bash(`git -C "${paperDir}" rev-parse HEAD`).trim()
}
function restoreSectionToCommit(file, sha) {
  // Per-file restore: only this file is reset to `sha` (other files untouched). Serial sections make
  // this trivially safe; staged for the caller to commit with commitPaths.
  bash(`git -C "${paperDir}" checkout ${sha} -- "${file.path}"`)
}
function commitPaths(paths, msg) {
  // Commit ONLY the given paths — never sweep unrelated repo changes. Empty -> a marker commit so the
  // round's SHA is real.
  const ps = paths.map(p => `"${p}"`).join(' ')
  const r = bash(`git -C "${paperDir}" commit -m ${shq(msg)} -- ${ps} 2>&1 || true`)
  if (/nothing to commit|no changes added|did not match|pathspec/i.test(r)) {
    bash(`git -C "${paperDir}" commit --allow-empty -m ${shq(msg)}`)
  }
}
function resolveManuscript(master) {
  // `master` now arrives from the orchestrator's natural-language parse of the /polish request (a file
  // path or a directory) — see commands/polish.md. The resolution logic below is unchanged.
  // [[MECH]] strict resolve via the script — it auto-selects the \documentclass master when given a
  // DIRECTORY, and emits {error, candidates} + nonzero on failure.
  const raw = bash(`python3 "${pluginRoot}/scripts/resolve_manuscript.py" --master "${master}" --section-order "${SECTION_ORDER.join(',')}" 2>/dev/null || true`)
  let res
  try { res = JSON.parse(raw) } catch { res = { error: 'resolver produced no JSON', candidates: [] } }
  // [[SEAM:input-resolve]] TRIGGER: res.error (bad path / wrong filename / dir with no obvious master).
  // DECISION: read-only Bash (grep) over res.candidates to find the real master — the existing file
  // with \documentclass (prefer one that also \input{}s sections) — then re-call the resolver ONCE.
  // FLOOR: only SELECT an existing \documentclass file; never fabricate a path, never edit; if none
  // qualifies, STOP and report res.candidates to the user.
  if (res && res.error) {
    const pick = pickMasterFromCandidates(res.candidates || [])
    if (!pick) throw new Error(`Could not resolve a master manuscript (${res.error}). Candidates: ${(res.candidates || []).join(', ') || '(none)'}`)
    log(`input-resolve: '${master}' failed (${res.error}); reasoned to master ${pick}`)
    res = JSON.parse(bash(`python3 "${pluginRoot}/scripts/resolve_manuscript.py" --master "${pick}" --section-order "${SECTION_ORDER.join(',')}"`))
  }
  return res
}
function pickMasterFromCandidates(candidates) {
  // [[SEAM:input-resolve]] the existing .tex that is a real master: has \documentclass, prefer one that
  // \input{}s sections, then names main/master/paper (first max wins on a tie). Deterministic, in
  // scripts/resolve_manuscript.py (--pick-master-from). Returns a path or null.
  return JSON.parse(bash(`python3 "${pluginRoot}/scripts/resolve_manuscript.py" --pick-master-from ${shq(JSON.stringify(candidates))}`)).master
}
function relTo(root, abs) {
  return bash(`python3 -c "import os,sys;print(os.path.relpath(sys.argv[1],sys.argv[2]))" "${abs}" "${root}"`).trim()
}
function detectFormat(path) {
  const head = bash(`head -c 4000 "${path}"`)
  if (/\\documentclass|\\begin\{document\}|\\cite\{/.test(head)) return 'latex'
  if (/^---\n|^#\s|\]\(http/.test(head)) return 'markdown'
  return 'markdown'
}
function buildFidelityManifest(ms, fmt, proj) {
  // Write .polish/fidelity-manifest.json: the `manuscripts` list (every editable prose file + the
  // master) + format + the data-file denylist (citations / data / tables / figures). The reviser never
  // edits denylisted files; the hook denies any attempt and recognizes any listed manuscript file.
  //
  // Step A (worktree freeze): also record the git toplevel + the repo-RELATIVE path of every manuscript
  // and denylist entry. A reviser running inside a linked git WORKTREE (parallel sections, Phase 2) edits
  // a file whose ABSOLUTE path differs from the main tree's (so the legacy abspath match misses), but
  // whose REPO-RELATIVE path is identical. The hook recognizes the manuscript by that relative path, so
  // the freeze holds at any worktree depth. realpath both sides so macOS /var↔/private/var never causes
  // a miss (G2). gitroot is resolved from the manuscript dir's own repo; when no repo exists yet (Phase 0
  // runs before the `git init` at Setup), it falls back to the realpath'd dir — which `git init` then
  // makes the toplevel, so the recorded relatives stay correct. Legacy absolute fields are kept (back-
  // compat + fallback): an old manifest without the *_rel fields still works via the abspath match.
  // The deterministic builder is scripts/build_manifest.py --mode polish. Pipe it {mode, root, master,
  // manuscripts, format, proj} on stdin (root = dirname(master), manuscripts = contextFilesList). It resolves
  // the gitroot itself (git rev-parse --show-toplevel, realpath'd; falls back to the realpath'd dir before the
  // Setup `git init`) and records manuscripts_rel + denylist_rel so the freeze holds at any worktree depth. It
  // writes <proj>/.polish/fidelity-manifest.json. (Explicit mode:"polish" — GAP-1 — so the polish-phase mode
  // assertion holds rather than relying on the check_fidelity.py default.)
  const input = JSON.stringify({ mode: 'polish', root: dirname(ms.master), master: ms.master, manuscripts: ms.contextFilesList, format: fmt, proj })
  bash(`printf '%s' ${shq(input)} | python3 "${pluginRoot}/scripts/build_manifest.py" >/dev/null`)
}
function writeVerdictFile(file, round, verdicts) {
  // [[MECH]] B5/D7 verdict PASS-THROUGH: the file is written from the EXACT structured object each
  // agent() returned (serialized verbatim by renderVerdicts). The orchestrator MUST NOT re-type,
  // summarize, reorder, or reconstruct verdict JSON — a hand-rebuilt copy once mislabeled a flag's
  // dimension. Keep the printf+shq mechanism (never swap in a hand-typed heredoc). Record the verdicts
  // in polish-round-<file-slug>-<section>-<N>.md and commit it on its own (the hook allows it — not a
  // manuscript, not a data file). W0: the <section> segment disambiguates a single-file paper where
  // every section shares one file.rel (main.tex) — without it all sections collide on one filename and
  // overwrite each other's verdicts.
  const name = `polish-round-${slug(file.rel)}-${slug(file.section)}-${round}.md`
  const abs = `${paperDir}/${name}`
  bash(`printf '%s' ${shq(renderVerdicts(file.section, round, verdicts))} > "${abs}"`)
  bash(`git -C "${paperDir}" add "${abs}" && (git -C "${paperDir}" commit -m "polish: verdict ${file.rel} round ${round}" -- "${abs}" 2>/dev/null || true)`)
}
// ════════════════════════════════════════════════════════════════════════════
// D-1 — the per-SECTION open-items ledger TASK_STATUS.polish.concerns.json (Doc A §2.3 / §10-E).
// DETERMINISTIC + dimension-agnostic (task-ledger schema: id / concern / status). polish and
// polish-figures share this SCHEMA. Written + committed after each section so the L0 PD pointer and a
// crash-resume read the same per-unit open set. No LLM hand-curation — the convergence verdict (the
// shipped round's quality flags) IS the ledger source.
// ════════════════════════════════════════════════════════════════════════════
function ledgerSlug(s) { return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) }

// [[MECH]] map a quality flag to its concern (domain.aspect) — the key the concern->reference map
// (assets/concern-reference-map.yaml) + the PD engine read. Prose concerns only (science is frozen).
function concernFor(flag) {
  const dim = (flag && flag.dimension) || '', sev = (flag && flag.severity) || ''
  if (/ai.?tell/i.test(dim) || sev === 'ai_tells_systematic' || sev === 'minor_tell') return 'prose.ai-tells'
  if (/read/i.test(dim) || sev === 'recurring_readability') return 'prose.readability'
  if (/logic|result/i.test(dim) || sev === 'logic_core' || sev === 'results_core') return 'prose.logic'
  return 'prose.readability'
}

// [[MECH]] record the SHIPPED round's quality flags as section-keyed ledger items: an actionable flag
// that survived to ship is `open` (could not fix); a deferred flag is `deferred` (intentionally kept /
// needs-author / trivial cosmetic). A section with neither is `clean` (its open set is empty).
// Idempotent per unit (a re-record replaces this unit's items). Then rebuild + commit the JSON ledger.
// D1: do-no-harm is gone (every section always ships its best round), so there is no do-no-harm item.
function recordSectionLedger(section, file, best) {
  const unit = section, round = (best && best.round) || 0
  const quality = (best && best.verdicts && best.verdicts.quality) || []
  for (let i = polishLedgerItems.length - 1; i >= 0; i--) if (polishLedgerItems[i].unit === unit) polishLedgerItems.splice(i, 1)
  let n = 0
  for (const q of quality) for (const f of (q.flags || [])) {
    const deferred = f.disposition === 'deferred'
    polishLedgerItems.push({
      id: `POL-${ledgerSlug(unit)}-${ledgerSlug(f.severity)}-${++n}`,
      concern: concernFor(f), unit, status: deferred ? 'deferred' : 'open',
      opened_round: round, closed_round: null, last_touched_round: round,
      evidence: `${file.rel} @ shipped round ${round}`, source: 'reviewer',
      severity: f.severity || null, dimension: f.dimension || null, issue: f.issue || '',
      defer_reason: deferred ? (f.defer_reason || '(no reason given)') : null,
    })
  }
  if (n === 0) polishLedgerItems.push({ id: `POL-${ledgerSlug(unit)}-clean`, concern: null, unit, status: 'closed',
    opened_round: round, closed_round: round, last_touched_round: round,
    evidence: `${file.rel} @ shipped round ${round}`, source: 'reviewer', issue: 'section converged with an empty open set', defer_reason: null })
  writePolishLedger()
}

// [[MECH]] rebuild TASK_STATUS.polish.concerns.json from polishLedgerItems (+ the sweep's master-advisory
// bucket) and commit it (a verdict-class file → the fidelity hook allows it). `open_concerns` is the
// deduped concern of every {open,reopened} item — the exact set the L0 PD pointer discloses references for.
function writePolishLedger() {
  const open = polishLedgerItems.filter(it => it.status === 'open' || it.status === 'reopened')
  const ledger = {
    phase: 'polish', schema: 'task-ledger (Doc A §2.1 — dimension-agnostic id/concern/status)',
    keyed_by: 'section unit', round_key: 'inline (no frozen snapshot — /polish does not detach)',
    open_concerns: [...new Set(open.map(it => it.concern).filter(Boolean))],
    items: polishLedgerItems, master_advisory: polishMasterAdvisory,
  }
  const p = `${paperDir}/TASK_STATUS.polish.concerns.json`
  try {
    bash(`printf '%s' ${shq(JSON.stringify(ledger, null, 2))} > "${p}"`)
    bash(`git -C "${paperDir}" add "${p}" && (git -C "${paperDir}" commit -m "polish: TASK_STATUS ledger (${polishLedgerItems.length} item(s), ${open.length} open)" -- "${p}" 2>/dev/null || true)`)
  } catch (e) { log(`polish ledger write failed (${String(e && e.message || e).split('\n')[0]})`) }
}

function writeReport() {
  // W2: the human-facing run summary, surfaced once at the end so the author actually sees what the
  // run decided rather than burying it in a next_step sentence. Pulls only run-wide state already
  // accumulated (no re-derivation). Written via printf+shq + committed like a verdict file (not a
  // manuscript / data file → the hook allows it). Returns the path, or null if writing failed.
  const abs = `${paperDir}/polish-report.md`
  try {
    bash(`printf '%s' ${shq(renderReport())} > "${abs}"`)
    bash(`git -C "${paperDir}" add "${abs}" && (git -C "${paperDir}" commit -m "polish: run report" -- "${abs}" 2>/dev/null || true)`)
    return abs
  } catch (e) { log(`report write failed (${String(e && e.message || e).split('\n')[0]})`); return null }
}
function renderReport() {
  const L = []
  L.push(`# Polish report`, ``)
  L.push(`- Branch: \`${branch}\` (from \`${baseSha.slice(0, 8)}\`)`)
  L.push(`- Venue: ${VENUE.label}`)
  L.push(`- Files: ${MS.files.map(f => `${f.rel}→${f.section}`).join(', ') || '(single file)'}`, ``)

  // [[standard]] editor-level ship-readiness summary (computed). The prose-scope pre-submission checklist
  // itself lives in the `task-ledger` skill (single source — not duplicated here); science is frozen in
  // /polish, so experiments/theory/figures are out of scope (run /review + /polish-figures for those).
  // D1: do-no-harm is gone — body sections always ship their best round. The only shippedRound===0 cases
  // left are a failed parallel runner (state 'failed', kept its base) or the abstract that kept its
  // original (the abstract do-no-harm floor, owner-decision-2). Count those as "not improved".
  const notImproved = sectionReport.filter(s => s.state === 'failed' || s.shippedRound === 0).length
  const openForAuthor = couldNotFix.length + deferredFlags.length
  L.push(`## Ship-readiness (润色视角)`, ``)
  L.push(`- ${sectionReport.length} section(s) polished; ${notImproved} kept their original (failed runner / abstract do-no-harm); ` +
    `${couldNotFix.length} could_not_fix + ${deferredFlags.length} deferred flag(s) for your review.`)
  L.push(`- Prose-level readiness: ${openForAuthor === 0 && notImproved === 0 ? '**clean** — every section reached a faithful improved version with no escalations'
    : openForAuthor === 0 ? '**near-clean** — no open escalations, but some sections kept their original'
    : '**needs your review** — see could_not_fix / deferred below before submitting'}.`)
  L.push(`- Before submitting, verify the prose-scope pre-submission checklist in the \`task-ledger\` skill.`)
  L.push(`- Science (experiments / theory / claims) is frozen here — for those run \`/review\`; for figures run \`/polish-figures\`.`, ``)

  L.push(`## Per-section outcomes`, ``)
  L.push(`| section | file | shipped round | state | stop reason |`)
  L.push(`|---|---|---|---|---|`)
  for (const s of sectionReport) L.push(`| ${s.section} | ${s.file} | ${s.shippedRound} | ${s.state || '—'} | ${s.stopReason} |`)
  L.push(``)

  L.push(`## Abstract decision (第一刀)`, ``)
  if (!abstractDecision) {
    L.push(`_Abstract not in scope this run._`, ``)
  } else {
    L.push(`- Shipped: **${abstractDecision.shipped}** (${abstractDecision.reason}); head-to-head: ${abstractDecision.best_vs_original || 'n/a'} vs original (original clean: ${abstractDecision.original_clean}).`)
    const dq = abstractDecision.disqualified || []
    if (dq.length) {
      L.push(`- Disqualified candidates (failed a hard gate before scoring):`)
      for (const d of dq) L.push(`  - \`${d.id}\` — fidelity_ok=${d.fidelity_ok}, ai_tells_clean=${d.ai_tells_clean}`)
    } else L.push(`- No candidate was disqualified by the fidelity / ai-tells gates.`)
    L.push(``)
  }

  L.push(`## Gray-area science left to the author (\`could_not_fix\`)`, ``)
  if (!couldNotFix.length) L.push(`_None — no scientific judgment calls were escalated._`, ``)
  else { for (const c of couldNotFix) L.push(`- **${c.where}** r${c.round} [${c.kind || 'other'}]: ${c.item} — ${c.why}`); L.push(``) }

  L.push(`## Fidelity close-calls (skim these)`, ``)
  if (!closeCalls.length) L.push(`_None._`, ``)
  else { for (const c of closeCalls) L.push(`- **${c.section}** (${c.file}, r${c.round}): ${c.why || ''}${c.original ? `\n  - base: ${c.original}\n  - revised: ${c.revised}` : ''}`); L.push(``) }

  L.push(`## Deliberately-kept flags (\`deferred\`, W5)`, ``)
  if (!deferredFlags.length) L.push(`_None._`, ``)
  else { for (const f of deferredFlags) L.push(`- **${f.section}** (${f.file}) [${f.severity}/${f.dimension}]: ${f.issue} — kept because: ${f.defer_reason}`); L.push(``) }

  L.push(`## Science-completeness advisory (out of scope — your call)`, ``)
  if (!scienceAdvisory.length) L.push(`_None._`, ``)
  else { for (const a of scienceAdvisory) L.push(`- ${a.where ? `(${a.where}) ` : ''}${a.issue}${a.why ? ` — ${a.why}` : ''}`); L.push(``) }

  return L.join('\n')
}

// ── tiny string helpers (formatting goals; not load-bearing) ──────────────────
function dirname(p) { return p.replace(/\/[^/]*$/, '') || '.' }
function slug(s) { return String(s).replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '') }
function fmtFlags(v) { return JSON.stringify((v.quality || []).flatMap(q => q.flags || []), null, 2) }
function fmtDrift(items) { return JSON.stringify(items || [], null, 2) }
function fmtSweep(flags) { return JSON.stringify(flags || [], null, 2) }
function renderVerdicts(section, round, v) { return JSON.stringify({ section, round, ...v }, null, 2) }  // [[MECH]] verbatim serialize; never hand-rebuild
function shq(s) { return `'` + String(s).replace(/'/g, `'\\''`) + `'` }

// ── Output schemas (the fixed contracts; prose lives on disk except abstract) ──
const REVISE_SCHEMA = {
  type: 'object', required: ['committed', 'hunks'],
  properties: {
    committed: { type: 'boolean' },
    hunks: { type: 'array', items: { type: 'object', required: ['rule_tag', 'rationale'],
      properties: { rule_tag: { type: 'string' }, rationale: { type: 'string' }, example_anchor: { type: 'string' } } } },
    answered_flags: { type: 'array', items: { type: 'string' } },
    // W1: gray-area scientific judgments the reviser left to the AUTHOR (kept the original verbatim
    // rather than silently deciding). kind ∈ re-describe-mechanism | relative-positioning |
    // caption-attribution | qual-to-quant | needs-citation | original-may-be-wrong | other.
    could_not_fix: { type: 'array', items: { type: 'object', required: ['item', 'why'],
      properties: { item: { type: 'string' }, why: { type: 'string' }, kind: { type: 'string' } } } },
  },
}
const EVAL_FIDELITY_SCHEMA = {
  type: 'object', required: ['verdict'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    drift_items: { type: 'array', items: { type: 'object',
      properties: { check: { type: 'string' }, original: { type: 'string' }, revised: { type: 'string' }, why: { type: 'string' } } } },
    close_calls: { type: 'array', items: { type: 'object',
      properties: { original: { type: 'string' }, revised: { type: 'string' }, why: { type: 'string' } } } },
  },
}
const EVAL_QUALITY_SCHEMA = {
  type: 'object', required: ['dimensions_covered', 'flags'],
  properties: {
    dimensions_covered: { type: 'array', items: { type: 'string' } },   // e.g. ["logic","results"]
    flags: { type: 'array', items: { type: 'object', required: ['severity', 'dimension', 'issue'],
      properties: {
        severity: { type: 'string', enum: ['logic_core', 'results_core', 'ai_tells_systematic', 'recurring_readability', 'minor_tell'] },
        disposition: { type: 'string', enum: ['actionable', 'deferred'] },   // absent ⇒ actionable; deferred = intentionally-kept / needs-author / a trivial cosmetic tell already given one attempt — excluded from the open set (D15)
        defer_reason: { type: 'string' },   // W5: MANDATORY when disposition='deferred' — why this flag is left in (accountability; surfaced in polish-report)
        dimension: { type: 'string' }, quote: { type: 'string' }, issue: { type: 'string' }, direction: { type: 'string' } } } },
    reads_like: { type: 'string', enum: ['human-expert', 'competent-but-flat', 'machine-assembled'] },
    recurring_problem: { type: 'boolean' },
    highest_leverage_fix: { type: 'string' },
  },
}
const KEYNOTE_SCHEMA = {
  type: 'object', required: ['per_section'],
  properties: {
    per_section: { type: 'array', items: { type: 'object', required: ['section', 'effort'],
      properties: {
        section: { type: 'string' },
        effort: { type: 'string', enum: ['light', 'normal', 'heavy'] },
        arc_flags: { type: 'array', items: { type: 'object', required: ['issue'],
          properties: { section: { type: 'string' }, issue: { type: 'string' }, detail: { type: 'string' } } } },
      } } },
    science_advisory: { type: 'array', items: { type: 'object',
      properties: { issue: { type: 'string' }, where: { type: 'string' }, why: { type: 'string' } } } },
  },
}
const ABSTRACT_CANDIDATES_SCHEMA = {
  type: 'object', required: ['candidates', 'original'],
  properties: {
    candidates: { type: 'array', items: { type: 'object', required: ['id', 'title', 'abstract'],
      properties: { id: { type: 'string' }, title: { type: 'string' }, abstract: { type: 'string' }, hunk_tags: { type: 'array', items: { type: 'string' } } } } },
    original: { type: 'object', required: ['title', 'abstract'], properties: { title: { type: 'string' }, abstract: { type: 'string' } } },
  },
}
const ABSTRACT_SCORE_SCHEMA = {
  // [dossier-12 G3] categorical head-to-head — the last numeric-scoring island removed (no 1-10, no aggregate).
  type: 'object', required: ['candidate_id', 'fidelity_ok', 'ai_tells_clean', 'vs_original'],
  properties: {
    candidate_id: { type: 'string' }, fidelity_ok: { type: 'boolean' },
    ai_tells_clean: { type: 'boolean' },   // the check-ai-tells zero-tolerance gate: false ⇒ disqualified BEFORE the head-to-head (em-dash / banned word / interchangeable template)
    vs_original: { type: 'string', enum: ['clearly_better', 'marginally_better', 'not_better', 'baseline'] },   // 'baseline' ONLY for the original judging itself
    why: { type: 'string' },               // one sentence grounding the verdict (which axis carried it)
  },
}
const SWEEP_SCHEMA = {
  type: 'object', required: ['flags'],
  properties: { flags: { type: 'array', items: { type: 'object',
    properties: { type: { type: 'string', enum: ['terminology', 'symbol', 'abbreviation', 'citation'] }, section: { type: 'string' }, locations: { type: 'array', items: { type: 'string' } }, detail: { type: 'string' } } } } },
}
// Step C: what a section-runner returns to the orchestrator. `rounds` carries each round's verdicts so
// assembleSections writes the per-round verdict files on the main tree (no per-round commit raced inside
// the worktree). `state` is the shipped (best) round's categorical state (D15 — no numeric weight).
// D1: the per-round fidelity gate is gone — each round's verdicts is now {quality} only, the runner
// always ships its best round (no do-no-harm), and it returns no close_calls (the篇末 advisory sweep
// is the sole close-call source, run serially on the main tree).
const SECTION_RESULT_SCHEMA = {
  type: 'object', required: ['section', 'rel', 'branch', 'shipped_sha', 'stop_reason', 'rounds'],
  properties: {
    section: { type: 'string' },
    rel: { type: 'string' },                         // repo-relative path (assembly checks the file out)
    branch: { type: 'string' },                      // the section branch holding the shipped file
    shipped_sha: { type: ['string', 'null'] },       // worktree HEAD after ship-best
    best_round: { type: ['integer', 'null'] },
    state: { type: ['string', 'null'] },             // shipped round's state: clean|cosmetic-only|has-core
    stop_reason: { type: 'string' },
    rounds: { type: 'array', items: { type: 'object', required: ['round'],
      properties: { round: { type: 'integer' }, state: { type: ['string', 'null'] }, verdicts: { type: 'object' } } } },   // verdicts: { quality }
    could_not_fix: { type: 'array', items: { type: 'object' } },
    deferred_flags: { type: 'array', items: { type: 'object' } },
  },
}
