// polish-figures — turn a paper's figures into publication-quality figures without touching the
// science. Freeze the data + the prose; repaint the figures. The MIRROR of polish (which freezes the
// figures + data and rewrites the prose): here the plotting SCRIPTS and the figure files they
// regenerate are free, while the cached analysis data and the manuscript text are frozen.
//
// This file is the CANONICAL SPEC for the run. It is driven by an ORCHESTRATOR: a Claude model reads
// this file (via commands/polish-figures.md) and reproduces the phase sequence using Task subagents +
// Bash. The JS format is intentional — it eliminates branching/loop ambiguity that prose cannot.
//
// Conventions used below (the orchestrator maps these to its own actions):
//   agent(goal, {role, schema, ...})  -> spawn ONE subagent of the configured shell
//                                        (roles.<role>.subagent_type) with this goal and required
//                                        output schema; returns the parsed schema.
//   parallel([() => agent(...), ...]) -> run several spawns concurrently.
//   bash(cmd, schema?)                -> run a shell command (git / fs / re-run a plotting script) and
//                                        return output. The reviser commits its own rounds (it has Bash).
//   phase(name) / log(msg)            -> progress markers.
//
// All knobs come from config/config.yaml -> figures: block, read once at startup. Convergence and
// best-version selection are PURE ARITHMETIC owned here and never told to the agents (mirrors polish.js):
// the agents return verdicts; this file decides.
//
// ── Two-tier execution contract ────────────────────────────────────────────────
//   [[MECH]]         MUST-MECHANICAL. Deterministic; reproduce verbatim — never improvise, reorder, or
//                    "improve" it. (git scoping, the converge/ship arithmetic, schema shapes, max_rounds.)
//   [[SEAM:<name>]]  ORCHESTRATOR-MAY-REASON. A named, bounded point where the orchestrator thinks.
// The only guards that survive a misbehaving orchestrator are the pre-edit hook (figure mode: data +
// prose frozen) and the agents/*.md tool allowlists (fidelity has no Edit/Write).
//
// Topology:
//   Phase 0 Setup    — SAFE git (branch polish-fig-<ts> from current HEAD); write the figure-mode
//                      fidelity manifest (.polish/, mode:"figure") so the pre-edit hook freezes the data
//                      + prose and frees the plotting scripts + figure outputs.
//   Phase 1 Survey   — mechanical collect (\includegraphics targets + plotting scripts) + ONE read-only
//                      survey+DESIGN agent (role `designer`) that maps each figure -> {plot_script,
//                      paper_location, data_sources, output_files, regen_cmd, regenerable, effort} PLUS a
//                      per-figure DESIGN BRIEF (figure-design skill: reader_takeaway, verdict
//                      keep|restyle|redesign, archetype, axis/panel plan, regen_expectations, proposed
//                      caption) AND a cross-figure taste BASELINE + inconsistencies. Briefs persist to
//                      <paperDir>/figure-design-briefs.json (+ .md) and are base-committed with the scripts.
//   Phase 2 Figures  — serial; per FIGURE a revise→regenerate(HARD GATE: script must run)→visual-QA→
//                      fidelity→converge loop (runFigure). A verdict=redesign figure's round 1 IMPLEMENTS
//                      its brief (chart type / axis windows / panel composition may change — same data,
//                      same statistics, same series meaning); later rounds polish the new design. The
//                      fidelity gate is THREE-WAY: PASS (restyle, or a structural change MATCHING the
//                      brief — reported in design_changes) / HOLD (a deliberate numeric/scale RESCALE, or
//                      an OFF-brief structural change — reverted + surfaced for author approval, never
//                      shipped unapproved) / FAIL (suspected drift — reverted). Converge stops on
//                      clean+faithful, on a 2-round no-improvement stall, or at the round cap.
//   Phase 3 Emit     — apply the approved caption/tex-structure changes of shipped redesigns under the
//                      polish-mode token-freeze manifest (compile-fail ⇒ deterministic revert + patches
//                      file) + git log + diff base..HEAD + a recompiled paper PDF (figures seen in place) +
//                      the run report (per-figure outcomes, skips, fidelity close-calls); disarm the hook.
//
//   STAGE arg (args.stage, default 'all'): 'design' = Setup+Survey+briefs ONLY, then return (the pipeline
//   may gate the briefs for owner approval); 'repaint' = reload the persisted briefs (same branch, no new
//   survey) and run Figures+Emit; 'all' = both inline, briefs auto-approved (unattended default).
//
// ── PROGRESSIVE DISCLOSURE protocol (Doc A §3.2 — load only what is still open) ──
// (A COMMENT the reproducing L1 reads on entry; it changes no executable JavaScript below.)
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
// Ledger ② role, keyed by FIGURE unit (post-freeze, mode:figure — data + prose frozen, only plot scripts/
// figures free). Resident sensor = the figure-fidelity-gate (figure science unchanged). REOPEN semantics
// (owner 2026-06-18 = data-touch retry): when figure-fidelity reopens a figure, the next round RETRIES that
// figure with a data-touch flag (it already iterates to cap) — there is no targeted-restore. Do NOT change
// the per-figure phase sequence.
// ────────────────────────────────────────────────────────────────────────────

export const meta = {
  name: 'polish-figures',
  description: 'Polish a paper\'s figures toward publication quality without changing the science — up to and including a full per-figure REDESIGN (chart type, axis windows, panel composition) when the design cannot deliver the reader takeaway. Freezes the cached data; repaints/replots the figures by editing their plotting scripts and regenerating them from the same data. A one-shot survey+design pass (figure-design skill) writes a per-figure DESIGN BRIEF (verdict keep|restyle|redesign) that licenses and bounds the redesign; a single context-aware reviser implements it per figure (retrieving research-figure-plotting for rendering); a read-only check-figure-fidelity gate confirms the science never moved (structural changes judged against the brief); a visual-QA reviewer judges design/layout/legibility/consistency; approved caption/tex changes of shipped redesigns are applied at Emit under a token-freeze manifest; the workflow self-judges convergence and ships per-figure git history.',
  whenToUse: 'When the user wants to polish / restyle / de-AI / regenerate a paper\'s figures (or one figure) toward publication quality — make them match a taste and read like a researcher (not an AI) wrote the plotting code. Describe which paper and which figure (or all). The OPPOSITE of /polish (which freezes figures and rewrites prose).',
  phases: [
    { title: 'Setup' },
    { title: 'Survey' },
    { title: 'Figures' },
    { title: 'Emit' },
  ],
}

// ── Resolve inputs ────────────────────────────────────────────────────────────
const pluginRoot = (args && args.plugin_root)
  || (typeof process !== 'undefined' && process.env && process.env.CLAUDE_PLUGIN_ROOT)
  || null
if (!pluginRoot) throw new Error('plugin_root must be passed (the slash command expands ${CLAUDE_PLUGIN_ROOT})')
// The input is the MASTER manuscript file (the root .tex that \includegraphics{}es the figures, or a
// directory) — used to locate the paper's figures and recompile the PDF at the end.
const masterPath = (args && args.master_path) || null
if (!masterPath) throw new Error('master_path (the master/root manuscript file) must be passed')
const target = (args && args.target) || 'all'            // a figure id/substring, or `all`
// [[MECH]] stage ∈ design|repaint|all — see the STAGE arg note in the topology comment. 'design' stops
// after persisting the briefs (gateable); 'repaint' resumes from them; 'all' runs both inline (default).
const stage = (args && args.stage) || 'all'
if (!['design', 'repaint', 'all'].includes(stage)) throw new Error(`stage must be design|repaint|all, got "${stage}"`)
const paperDir = dirname(masterPath)                     // where the manuscript lives
const projectDir = (args && args.project_dir)
  || (typeof process !== 'undefined' && process.env && process.env.CLAUDE_PROJECT_DIR)
  || paperDir

// ── Config (fail-soft: a missing key falls back to the baked-in default) ───────
function loadKnobs(root) {
  try {
    const raw = bash(
      `python3 -c "import yaml,json;print(json.dumps(yaml.safe_load(open('${root}/config/config.yaml')).get('figures',{})))"`
    )
    return JSON.parse(raw)
  } catch { return {} }
}
const KNOBS = loadKnobs(pluginRoot)
const MAX_ROUNDS = Math.max(1, KNOBS.max_rounds ?? 3)   // [[MECH]] rounds from config (figures.max_rounds, default 3 per the standard); floor 1, like /review. effort=light caps at 1; early convergence (clean + faithful) stops sooner.
// [[MECH]] round cap for a LICENSED redesign figure (design_brief.verdict='redesign'): round 1 implements
// the brief, later rounds polish the new design — needs more headroom than a restyle.
const REDESIGN_MAX_ROUNDS = Math.max(1, KNOBS.redesign_max_rounds ?? 3)
// The target-venue figure stance (computational science / JCP-CMAME-SISC, never Nature, PDF+PNG, matplotlib)
// is NOT duplicated here — it lives in the research-figure-plotting skill, which every figure agent retrieves.
// [[MECH]] D5 concurrency cap for the per-figure fan-out. Figures with PAIRWISE-DISJOINT (script ∪ outputs)
// paths are polished IN PARALLEL, each in its own git worktree, then assembled SERIALLY back onto the main
// branch (the exact worktree+funnel pattern /polish uses for sections); figures that SHARE a script/output
// stay SERIAL (they cannot be isolated in separate worktrees without racing on the shared file). This knob is
// the PEAK-CONCURRENCY cap: 0/unset = NEED-BASED (one worker per figure, no artificial ceiling — the owner's
// "3 figures → 3 workers, don't cap this kind"); a positive value throttles peak concurrency if cost/rate bites.
const MAX_PARALLEL_FIGURES = Math.max(0, KNOBS.max_parallel_figures ?? 0)
const DIMENSIONS = KNOBS.quality_dimensions || ['design', 'layout', 'legibility', 'consistency', 'code-naming']
const ROLES = KNOBS.roles || {}

// [[venue figure style]] OPTIONAL per-venue figure-style guide. The pipeline (or /polish-figures) may pass
// args.venue (a venue-anchors rel, e.g. "SIAM/SISC"); if that venue ships a figures.md, every figure agent
// loads it as the venue's figure stance, SPECIALIZING research-figure-plotting. Absent → generic stance (unchanged).
const VENUE_BASE = 'skills/house-style/examples/venue-anchors'
const venueArg = (args && args.venue) || null
const venueFiguresRel = (() => {
  if (!venueArg) return null
  const rel = `${VENUE_BASE}/${String(venueArg).replace(/^.*venue-anchors\//, '')}/figures.md`
  try { return bash(`test -f "${pluginRoot}/${rel}" && echo y || echo n`).trim() === 'y' ? rel : null } catch { return null }
})()
function venueFiguresGuide() {
  if (!venueFiguresRel) return ''
  return `TARGET-VENUE FIGURE STYLE: ALSO load ${pluginRoot}/${venueFiguresRel} and apply it as THIS venue's `
    + `figure stance — it SPECIALIZES research-figure-plotting for this venue (figure types, palette, panel/`
    + `subfigure labeling, colorbar sharing, convergence-plot conventions, caption detail, table style). Where it `
    + `is silent, fall back to research-figure-plotting defaults; on a presentation conflict the venue guide wins `
    + `(NEVER for the de-AI default-off removal rules — those always hold).`
}

function think(role) {
  const k = ROLES[role] && ROLES[role].inject_thinking
  return k ? `\n\n${k}` : ''
}
// Default subagent type per role so the spec is self-sufficient even if config/config.yaml lags (config always
// overrides). figure_runner drives ONE figure's whole loop inside its worktree and SPAWNS its own reviser +
// fidelity + visual-QA, so it MUST carry the Task tool → the 'claude' shell (same choice as /polish's section_runner).
// designer is the ONE survey+design call per run (reads figures + prose, authors the design briefs) — a plain
// read-only reviewer shell; its model is the figures.roles.designer knob (the single step worth a stronger model).
const DEFAULT_SUBAGENT = { figure_runner: 'claude', designer: 'claude' }
function roleOpts(role, schema) {
  const r = ROLES[role] || {}
  return { role, schema, ...(r.model ? { model: r.model } : {}), subagent_type: r.subagent_type || DEFAULT_SUBAGENT[role] || role }
}

// ── Run-wide state (this file's memory; agents never see the drop logic) ───────
let baseSha = null
let gitRoot = null
let branch = null
let REPO_BASES = {}            // {repoRoot: baseSha} — every repo the in-scope figures span (multi-repo layouts)
let SURVEY = null              // Phase 1 whole-set read {figures[], baseline, inconsistencies}
const figureReport = []        // {id, script, shippedVersion, shippedSha, actionable, stopReason}
const skipped = []             // {id, reason} — figures that are not regenerable
const closeCalls = []          // fidelity close-calls across the run
const fidelityReverts = []     // {id, round, why} — rounds reverted because the data was touched (FAIL: suspected drift)
const needsApproval = []       // {id, round, why, base, revised, rationale} — rounds HELD (not shipped): a deliberate
                               // numeric/scale RESCALE (unit conversion, fraction→%, colorbar vmin/vmax, an annotated
                               // value that follows the rescale) the author must approve. The MIRROR of /review's
                               // needs_author + /rewrite's audited-values: a number change is never shipped unapproved.
const deferredFlags = []       // visual flags the reviewer deliberately left in
const baselineCorrections = [] // QA-confirmed shared default-off decorations to REMOVE from EVERY figure —
                               // overrides SURVEY.baseline; the mid-run backstop for a defect the survey missed
const blockers = []            // {id, why} — figures the reviser could not proceed on (unclear/missing data,
                               // script, or paper location): standard F8 = stop + explain, never guess
const taskStatusBlocks = []    // rendered TASK_STATUS.md block per finished figure (rewritten + committed each figure)
const designChanges = []       // {id, round, what, why_science_preserved} — brief-matching structural changes the
                               // fidelity gate PASSed under a redesign license (FYI trail for the author)
const texApply = { applied: [], denied: [], reverted: false }   // Emit-phase caption/structure application record
const BRIEFS_PATH_REL = 'figure-design-briefs.json'             // persisted survey+briefs (paperDir-relative)
let APPROVAL = null            // briefs approval stamp: 'owner' | 'auto' | 'restyle_only' (null until stamped)

// ════════════════════════════════════════════════════════════════════════════
// Phase 0 — Setup
// ════════════════════════════════════════════════════════════════════════════
phase('Setup')

// Git (SAFE): branch from the CURRENT HEAD with a unique name (never clobber a branch). The base commit
// is DEFERRED to Phase 1 and scoped to ONLY the in-scope plotting scripts + figure outputs.
// [[MECH]] stage='repaint' does NOT create a new branch — it resumes the branch + baseSha + SURVEY the
// design stage persisted in figure-design-briefs.json (same run, post-gate continuation).
bash(`git -C "${paperDir}" rev-parse --git-dir >/dev/null 2>&1 || git -C "${paperDir}" init`)
gitRoot = bash(`git -C "${paperDir}" rev-parse --show-toplevel`).trim()
if (stage === 'repaint') {
  // [[MECH]] PRECONDITION (dossier-12 G5): repaint RESUMES a persisted design stage — no briefs file means
  // design never ran. Hard-stop with the remediation instead of a bare JSON.parse crash.
  if (!bash(`test -f "${paperDir}/${BRIEFS_PATH_REL}" && echo yes || echo no`).trim().startsWith('yes')) {
    throw new Error(`stage='repaint' but ${BRIEFS_PATH_REL} is missing — the design stage never ran here. `
      + `Run stage='design' first (it persists the briefs + branch/base coordinates), approve/edit the `
      + `briefs, then relaunch stage='repaint'.`)
  }
  const saved = JSON.parse(bash(`cat "${paperDir}/${BRIEFS_PATH_REL}"`))
  branch = saved.branch
  baseSha = saved.base_sha
  SURVEY = saved.survey
  // [[MECH]] (dossier-12 G5) an UNSTAMPED briefs file on a bare manual repaint defaults to the
  // LEAST-privilege stamp: 'restyle_only' (an approval gate whose stamp is absent must not hand out the
  // full-redesign license). The unattended full license stays where it is deliberate — stage='all'
  // stamps approved:'auto' at design time (:below), and the pipeline's gate stamps 'owner'/'restyle_only'.
  APPROVAL = saved.approved || 'restyle_only'
  if (!saved.approved) log(`Repaint — briefs file is UNSTAMPED (approved:null): defaulting to approved='restyle_only' (redesign licenses withheld); stamp 'owner'/'auto' in ${BRIEFS_PATH_REL} to enable redesigns.`)
  REPO_BASES = saved.repo_bases || {}
  bash(`git -C "${paperDir}" checkout "${branch}"`)
  for (const r of Object.keys(REPO_BASES)) if (r !== gitRoot) bash(`git -C "${r}" checkout "${branch}"`)   // multi-repo: resume the sibling repos' branch too
} else {
  const startBranch = bash(`git -C "${paperDir}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "(unborn)"`).trim()
  branch = `polish-fig-${bash(`date +%s`).trim()}`
  bash(`git -C "${paperDir}" checkout -b "${branch}"`)
  log(`Setup — from=${startBranch}`)
}

// Write the figure-mode fidelity manifest so the pre-edit hook is armed: it FREEZES the cached data +
// the manuscript prose (denylist) and FREES the plotting scripts + the figure files they regenerate.
bash(`mkdir -p "${projectDir}/.polish"`)
buildFigureManifest(gitRoot, projectDir)
log(`Setup done — gitRoot=${gitRoot}, branch=${branch}, stage=${stage}${APPROVAL ? `, briefs approved=${APPROVAL}` : ''}; figure-mode freeze armed (data + prose frozen)`)

// ════════════════════════════════════════════════════════════════════════════
// Phase 1 — Survey (whole-set read, ONCE up front)
// ════════════════════════════════════════════════════════════════════════════
phase('Survey')

// Mechanical collect: the figure files the paper \includegraphics{}es, and the candidate plotting
// scripts. These RAW lists seed the survey agent (which maps them + reads the scripts/data itself).
// [[MECH]] stage='repaint' skips the survey agent entirely — SURVEY (incl. the design briefs) was
// reloaded from disk in Phase 0; re-running it would fork the contract the gate approved.
if (stage !== 'repaint') {
  const includeRaw = bash(
    `grep -rhoE '\\\\includegraphics(\\[[^]]*\\])?\\{[^}]*\\}' "${paperDir}" --include=*.tex 2>/dev/null ` +
    `| sed -E 's/.*\\{([^}]*)\\}/\\1/' | sort -u || true`
  ).split('\n').map(s => s.trim()).filter(Boolean)
  const scriptRaw = bash(
    `grep -rlE 'matplotlib|pyplot|savefig|\\bplt\\.' "${gitRoot}" --include=*.py 2>/dev/null ` +
    `| grep -vE '/(\\.git|node_modules|vendor)/' | sort -u || true`
  ).split('\n').map(s => s.trim()).filter(Boolean)
  log(`Survey inputs — ${includeRaw.length} \\includegraphics target(s), ${scriptRaw.length} candidate plotting script(s)`)

  // Survey+design rubric (figure map + PER-FIGURE DESIGN BRIEF + cross-figure taste baseline + shared
  // default-off defects + the anti-laundering rule) → spec/spawn-prompts/figures-survey.md. The goal injects
  // the paths + raw lists and appends the optional venue figure-style guide + any thinking directive.
  SURVEY = agent(
    [
      `Read ${pluginRoot}/spec/spawn-prompts/figures-survey.md and do EXACTLY what it says — ONE read-only pass; return FIGURE_SURVEY_SCHEMA.`,
      `<MASTER_PATH>: ${masterPath}`,
      `<PAPER_DIR>: ${paperDir}`,
      `<GIT_ROOT>: ${gitRoot}`,
      `<INCLUDE_RAW>: ${includeRaw.join(', ') || '(none found — search yourself)'}`,
      `<SCRIPT_RAW>: ${scriptRaw.join(', ') || '(none found — search ' + gitRoot + ' yourself)'}`,
      venueFiguresGuide(),
      think('designer'),
    ].join('\n'),
    roleOpts('designer', FIGURE_SURVEY_SCHEMA)
  )
} else {
  log(`Survey — reloaded from ${BRIEFS_PATH_REL}: ${(SURVEY.figures || []).length} figure(s), briefs approved=${APPROVAL}`)
}

// [[SEAM:figure-select]] TRIGGER: target !== 'all'. DECISION: keep figures whose id/output/script matches
// the requested figure (substring, case-insensitive). FLOOR: never invent a figure not in the survey; an
// empty match after a named target is a hard stop. FALLBACK: target='all' keeps every regenerable figure.
const allFigures = (SURVEY.figures || [])
for (const f of allFigures) if (!f.regenerable) skipped.push({ id: f.id, reason: f.skip_reason || 'not regenerable (no source script / missing data)' })
let figures = allFigures.filter(f => f.regenerable)
if (target !== 'all') {
  const t = String(target).toLowerCase()
  const match = figures.filter(f =>
    String(f.id).toLowerCase().includes(t) ||
    (f.output_files || []).some(o => o.toLowerCase().includes(t)) ||
    (f.plot_script || '').toLowerCase().includes(t))
  if (!match.length) throw new Error(`No regenerable figure matched target "${target}". Regenerable: ${figures.map(f => f.id).join(', ') || '(none)'}. Skipped: ${skipped.map(s => s.id).join(', ') || '(none)'}.`)
  figures = match
}
log(`Survey — ${allFigures.length} figure(s): ${figures.length} regenerable in scope, ${skipped.length} skipped; ${(SURVEY.inconsistencies || []).length} cross-figure inconsistency(ies), ${(SURVEY.shared_defects || []).length} shared default-off defect(s) to strip`)
if (!figures.length) { log('No regenerable figures in scope — nothing to polish.'); }

// [[MECH]] base-commit ONLY the in-scope plotting scripts + their figure outputs, so base..HEAD shows
// exactly this run's figure work and a restore can fall back to the untouched original. git is not
// gated by the hook (the hook only intercepts Edit/Write tools), so this commit is always allowed.
// stage='repaint' skips this — the design stage already base-committed; baseSha came from the briefs file.
if (stage !== 'repaint') {
  const baseScope = [...new Set(figures.flatMap(f => [f.plot_script, ...(f.output_files || [])]).filter(Boolean).map(p => abs(p)))]
  // [[MECH]] multi-repo: base-commit PER OWNING REPO; a sibling repo (e.g. a separate code/ repo holding the
  // plotting scripts) gets the SAME branch name first (W28 hardening — no more improvised dual-branch protocol).
  const byRepo = groupByRepo(baseScope)
  for (const r of Object.keys(byRepo)) {
    if (r !== gitRoot) bash(`git -C "${r}" checkout -b "${branch}" 2>/dev/null || git -C "${r}" checkout "${branch}"`)
    bash(`git -C "${r}" add -- ${byRepo[r].map(p => `"${p}"`).join(' ')} 2>&1 || true`)
    bash(`git -C "${r}" diff --cached --quiet || git -C "${r}" commit -m "polish-figures: base (untouched scripts + figures)"`)
  }
  baseSha = readHeadSha()
  REPO_BASES = baseScope.length ? headShas(baseScope) : { [gitRoot]: baseSha }
  log(`Base committed — base=${baseSha.slice(0, 8)} over ${baseScope.length} in-scope file(s) across ${Object.keys(REPO_BASES).length} repo(s)`)

  // [[MECH]] persist the DESIGN BRIEFS (the whole SURVEY + run coordinates) so the design stage is
  // gateable + resumable: 'all' stamps approved:'auto' (unattended default); 'design' leaves the stamp
  // null (the pipeline's gate sets 'owner' / 'restyle_only' — or the owner edits the briefs — then
  // relaunches with stage='repaint').
  if (stage === 'all') APPROVAL = 'auto'
  writeBriefs()
  if (stage === 'design') {
    log(`Design stage complete — ${figures.length} brief(s) persisted to ${BRIEFS_PATH_REL}; run stage='repaint' after approval.`)
    return {
      stage: 'design',
      branch,
      base: baseSha,
      briefs: `${paperDir}/${BRIEFS_PATH_REL}`,
      briefs_md: `${paperDir}/figure-design-briefs.md`,
      figures_in_scope: figures.map(f => f.id),
      verdicts: figures.map(f => ({ id: f.id, verdict: (f.design_brief && f.design_brief.verdict) || 'restyle', takeaway: (f.design_brief && f.design_brief.reader_takeaway) || '' })),
      skipped,
      next_step: `Review ${paperDir}/figure-design-briefs.md (per-figure verdict + takeaway + plan + proposed caption). ` +
        `Approve (stamp approved:'owner' in ${BRIEFS_PATH_REL}, or let the pipeline gate do it), optionally edit any brief, ` +
        `then rerun with stage='repaint' on the same workspace to implement them.`,
    }
  }
}

// ════════════════════════════════════════════════════════════════════════════
// Phase 2 — Figures (per-figure converge loop; PARALLEL over disjoint figures, else SERIAL)
// ════════════════════════════════════════════════════════════════════════════
phase('Figures')
// NEED-BASED cap: default = one worker per figure (no artificial ceiling); a positive knob throttles it.
const figCap = MAX_PARALLEL_FIGURES > 0 ? MAX_PARALLEL_FIGURES : figures.length
// [[MECH]] the PARALLEL worktree path is SINGLE-REPO only (a worktree isolates the paper repo; scripts living
// in a sibling code/ repo would be edited in place → races). A multi-repo layout always runs SERIAL.
if (figures.length > 1 && figCap > 1 && allDisjoint(figures) && singleRepo(figures)) {
  log(`Figures — PARALLEL: ${figures.length} figure(s), each in its own git worktree, up to ${figCap} concurrent`)
  runFiguresParallel(figures, figCap)
} else {
  if (figures.length > 1) log(`Figures — SERIAL (${figCap <= 1 ? 'cap≤1' : (!singleRepo(figures) ? 'figures span MULTIPLE git repos — worktree isolation is single-repo only' : 'figures share a script/output — cannot isolate in separate worktrees')})`)
  for (const fig of figures) runFigure(fig)
}

// ════════════════════════════════════════════════════════════════════════════
// Phase 3 — Emit
// ════════════════════════════════════════════════════════════════════════════
phase('Emit')
// [[MECH]] apply the approved caption / tex-structure changes of SHIPPED redesigns under the polish-mode
// token-freeze manifest (numbers / \cite / \ref / \label must survive verbatim). Deterministic do-no-harm:
// a failed recompile reverts the tex commit and the changes fall back to figure-tex-patches.md.
applyTexChanges()
// multi-repo aware: the run log/diff covers EVERY repo the in-scope figures span (labeled when >1).
const repoList = Object.keys(REPO_BASES).length ? REPO_BASES : { [gitRoot]: baseSha }
const multi = Object.keys(repoList).length > 1
const gitLog = Object.entries(repoList).map(([r, b]) => (multi ? `[${r}]\n` : '') + bash(`git -C "${r}" log --oneline ${b}..HEAD`)).join('\n')
const diffStat = Object.entries(repoList).map(([r, b]) => (multi ? `[${r}]\n` : '') + bash(`git -C "${r}" diff --stat ${b}..HEAD`)).join('\n')

// Recompile the paper PDF so the figures are seen IN PLACE (LaTeX + TeX toolchain only; otherwise the
// git diff of the scripts + the regenerated figure files is the deliverable). Reads git only.
let reportPath = null, pdfPath = null
const haveTeX = (() => { try { bash('command -v pdflatex >/dev/null 2>&1'); return true } catch { return false } })()
if (haveTeX && /\.tex$/.test(masterPath)) {
  pdfPath = `${paperDir}/polish-figures-preview.pdf`
  try {
    bash(`bash "${pluginRoot}/scripts/render_pdf.sh" --repo "${gitRoot}" --master "${relTo(gitRoot, masterPath)}" --rev HEAD --out "${pdfPath}" 2>&1 || ` +
      `(cd "${paperDir}" && pdflatex -interaction=nonstopmode "${masterPath}" >/dev/null 2>&1 && mv "${masterPath.replace(/\.tex$/, '.pdf')}" "${pdfPath}")`)
  } catch (e) { log(`PDF preview build failed (${String(e && e.message || e).split('\n')[0]}); the git diff is the deliverable.`); pdfPath = null }
}

reportPath = writeReport()
log(reportPath ? `Wrote run report ${reportPath}` : 'Run report not written.')

// [[MECH]] disarm the figure-mode hook now the run is done — remove the manifest so later edits to data
// / prose are not blocked. Idempotent (a fresh Phase 0 re-arms). Remove ONLY the manifest.
bash(`rm -f "${projectDir}/.polish/fidelity-manifest.json"`)
log('Disarmed figure-mode hook (removed .polish/fidelity-manifest.json).')
log('polish-figures complete.')

return {
  branch,
  base: baseSha,
  briefs: `${paperDir}/${BRIEFS_PATH_REL}`,
  briefs_approved: APPROVAL,
  figures_in_scope: figures.map(f => f.id),
  skipped,
  blockers,
  per_figure: figureReport,
  design_changes: designChanges,
  tex_apply: texApply,
  fidelity_reverts: fidelityReverts,
  needs_approval: needsApproval,
  close_calls: closeCalls,
  deferred_flags: deferredFlags,
  git_log: gitLog,
  diff_stat: diffStat,
  pdf_preview: pdfPath,
  report_md: reportPath,
  task_status: `${paperDir}/TASK_STATUS.md`,
  next_step:
    `Start with the run report: \`${reportPath || `${paperDir}/polish-figures-report.md`}\` — per-figure ` +
    `outcomes + main improvements, the ${blockers.length} blocked figure(s) needing author input, the ` +
    `${needsApproval.length} numeric/scale rescale(s) HELD for your approval (reverted, not shipped), the ` +
    `${skipped.length} skipped figure(s) (no source / not regenerable), the ` +
    `${fidelityReverts.length} round(s) reverted for touching the data, and the ${closeCalls.length} ` +
    `fidelity close-call(s). The living per-figure status is \`${paperDir}/TASK_STATUS.md\`. ` +
    (pdfPath ? `Then open the recompiled paper: \`${pdfPath}\` — the polished figures seen in place. ` : `No PDF preview (non-LaTeX or no toolchain). `) +
    `Full history on the ${branch} branch: \`git -C ${gitRoot} log ${baseSha.slice(0, 8)}..HEAD\` and ` +
    `\`git -C ${gitRoot} diff ${baseSha.slice(0, 8)}..HEAD\`. Your original branch is untouched.`,
}

// ════════════════════════════════════════════════════════════════════════════
// runFigure — the per-FIGURE converge loop, SERIAL path.
// [dossier-12 G1] POINTERIZED: spec/figure-loop.md is the ONE encoding of the loop (the parallel
// figure_runner has always executed it from the file; now the serial path READS it too instead of a
// ~300-line inline copy). Convergence + best-round are decided by scripts/figure_converge.py on BOTH
// paths now — the serial inline arithmetic is RETIRED (it was line-verified ≡ the script before this
// switch; the asymmetry was the drift risk). The JS keeps ONLY caller-side bindings + accumulators.
// ════════════════════════════════════════════════════════════════════════════
function runFigure(fig) {
  phase('Figures')
  const lic = redesignLicensed(fig)
  log(`── ${fig.id} (${fig.plot_script})${lic ? ' [REDESIGN per brief]' : ''} ──`)
  // [[MECH]] per-figure LOCAL baseline: this figure's untouched script + outputs. Restores/fidelity use
  // figBaseSha so a revert touches ONLY this figure, never an already-shipped earlier figure. A {repo: sha}
  // MAP (multi-repo aware; single-repo collapses to {gitRoot: sha}).
  const figAbs = figurePaths(fig)
  const figBaseSha = figAbs.length ? headShas(figAbs) : { [gitRoot]: readHeadSha() }
  // Read-only SEMANTICS pre-pass (figure-loop.md pre-loop step): the visual freeze manifest. `let` — a
  // licensed redesign RE-DERIVES it after its first faithful round (figure-loop.md §4b).
  let semantics = runFigureSemantics(fig, figBaseSha)
  log(`${fig.id}: semantics — ${(semantics && semantics.visual_encodings || []).length} encoding(s), ${(semantics && semantics.annotations || []).length} annotation(s)`)
  // [[MECH]] round cap: REDESIGN_MAX_ROUNDS for a licensed redesign; else effort=light caps at 1, else
  // MAX_ROUNDS. The ternary order makes it impossible for a light rating to starve a licensed redesign.
  const roundCap = lic ? REDESIGN_MAX_ROUNDS : (fig.effort === 'light' ? 1 : MAX_ROUNDS)

  // [[MECH]] CANONICAL LOOP EXECUTION (dossier-12 G1). FIRST read ${pluginRoot}/spec/figure-loop.md and
  // drive that loop IN-CONTEXT — serial means YOU are the runner on the main tree: do NOT spawn a
  // figure_runner; spawn only the loop's own per-step subagents (reviser; fidelity + visual-QA in
  // parallel) exactly as the file's steps prescribe. Bindings:
  //   FIG_ID=fig.id  PLOT_SCRIPT=fig.plot_script  OUTPUT_FILES=fig.output_files  REGEN_CMD=fig.regen_cmd
  //   GIT_C=the main tree, PER-REPO (multi-repo figures commit each file in ITS OWN repo — use
  //     groupByRepo(figAbs) exactly as before; roundSha anchors on the SCRIPT repo's sha)
  //   FIG_BASE_SHA=figBaseSha ({repo:sha} map)  SEMANTICS=semantics  SURVEY=SURVEY (+ append the run's
  //     accumulated baselineCorrections as QA-confirmed shared defects, exactly as before)
  //   DESIGN_BRIEF=fig.design_brief  REDESIGN_LICENSED=lic  ROUND_CAP=roundCap
  //   DIMENSIONS/NO_IMPROVE = the figures config knobs
  //   CONVERGE = python3 "${pluginRoot}/scripts/figure_converge.py"   (convergence + best-round ONLY via
  //     the script, figure-loop.md §6/§7 — the SAME decider the parallel path calls; the old inline
  //     streak/actionable arithmetic is retired; never judge convergence yourself)
  // SERIAL-ONLY deltas (unchanged semantics from before the pointerization):
  //   • the reviser goal also gets: the figure's core_message line, venueFiguresGuide(), think('reviser');
  //   • fidelity = runFigureFidelity(fig, roundShas, figBaseSha, semantics); visual-QA =
  //     runVisualQA(fig, roundSha, semantics) — the same evaluator wrappers the md's step 2 names;
  //   • the §3 annotation crop-check backstop runs HERE via countInPlotAnnotations(fig.plot_script) and
  //     injects the blocking flag verbatim (do not leave it to agent honesty);
  //   • semantics re-derive (§4b) via runFigureSemantics(fig, readHeadSha()) once, after the first
  //     faithful PASS of a licensed redesign;
  //   • per-round accumulators (the caller-side ledger, exactly as before): blockers (committed=false or
  //     regen_ok=false — both STOP this figure per the md), needsApproval (+held_sha = the reverted
  //     round's SCRIPT-repo sha), fidelityReverts, closeCalls, designChanges (PASS under license),
  //     baselineCorrections (set-wide propagation, keyed by issue text), and push each round
  //     {round, sha: headShas(figAbs), revise, fidelity, quality, actionable} onto `rounds`.
  // The executed loop yields: rounds[] + the §7 best verdict {best_round, do_no_harm}.
  const { rounds, best_round, do_no_harm } = executeFigureLoop_per_canonical_md()
  const stopReason = (rounds.length && rounds[rounds.length - 1].stop_reason) || 'max_rounds'

  // SHIP BEST (figure-loop.md §7 — the script's verdict; the JS keeps the restore + report bookkeeping).
  const best = do_no_harm ? null : rounds.find(r => r.round === best_round)
  if (!best) {
    restoreFigure(fig, figBaseSha)
    commitFigure(fig, `polish-figures: ${fig.id} — ship original (do-no-harm: no faithful improving round)`)
    figureReport.push({ id: fig.id, script: fig.plot_script, shippedVersion: 0, shippedSha: readHeadSha(), actionable: null, stopReason: blockers.find(b => b.id === fig.id) ? 'blocked' : 'do_no_harm', improvements: [] })
    log(`${fig.id}: shipped the ORIGINAL (no round both preserved the data and improved the figure)`)
  } else {
    if (!sameShas(best.sha, figAbs.length ? headShas(figAbs) : { [gitRoot]: readHeadSha() })) {
      restoreFigure(fig, best.sha)
      commitFigure(fig, `polish-figures: ${fig.id} — ship round ${best.round} (actionable=${best.actionable})`)
    }
    figureReport.push({ id: fig.id, script: fig.plot_script, shippedVersion: best.round, shippedSha: shaOf(best.sha, repoOf(abs(fig.plot_script))), actionable: best.actionable, stopReason, improvements: ((best.revise && best.revise.hunks) || []).map(h => h.rule_tag + (h.rationale ? `: ${h.rationale}` : '')) })
    log(`${fig.id}: shipped round ${best.round} (actionable=${best.actionable}); stop=${stopReason}`)
    for (const f of (best.quality.flags || [])) if (f.disposition === 'deferred') deferredFlags.push({ id: fig.id, round: best.round, severity: f.severity, dimension: f.dimension, issue: f.issue, defer_reason: f.defer_reason || '(no reason given)' })
  }
  // [[MECH]] standard F12 — update the living TASK_STATUS.md (one section per figure: location, script,
  // output, per-round record, resolved/unresolved, needs-author) and git-commit it as each figure finishes.
  writeTaskStatus(fig, rounds)
}

// ════════════════════════════════════════════════════════════════════════════
// PARALLEL FIGURES — worktree per figure + figure_runner + serial assemble (mirrors /polish sections).
// Only figures with PAIRWISE-DISJOINT (script ∪ outputs) reach here (allDisjoint), so each git worktree and
// each assemble checkout touches a DISJOINT path set and never conflicts. spec/figure-loop.md + scripts/
// figure_converge.py are the SINGLE SOURCE for the loop + convergence arithmetic on BOTH paths ([dossier-12
// G1] the serial runFigure now reads the same file — there is no inline reference copy left to mirror). The
// deterministic annotation crop-check is RE-VERIFIED by the
// orchestrator at assemble (assembleFigures), so it is never left to the runner's honesty.
// ════════════════════════════════════════════════════════════════════════════
function figurePaths(f) { return [f.plot_script, ...(f.output_files || [])].filter(Boolean).map(p => abs(p)) }
// ── multi-repo support (real-run topology: paper/ and code/ can be SEPARATE git repos) ──────────────────
// [[MECH]] Every figure-scoped git action groups its paths by OWNING repo (repoOf) and runs per repo; sha
// bookkeeping is a {repoRoot: sha} MAP. In the common single-repo layout all of this collapses to exactly
// the old behavior ({gitRoot: sha}); in a split layout the scripts repo gets the same branch + base commit
// and every restore/commit lands in the right repo (W28: the vendored spec assumed one gitRoot and the
// orchestrator had to improvise a dual-branch protocol by hand).
const repoCache = {}
function repoOf(p) {
  const d = dirname(String(p))
  if (!repoCache[d]) {
    try { repoCache[d] = bash(`git -C "${d}" rev-parse --show-toplevel 2>/dev/null`).trim() || gitRoot } catch { repoCache[d] = gitRoot }
  }
  return repoCache[d]
}
function groupByRepo(paths) {
  const g = {}
  for (const p of paths) { const r = repoOf(p); (g[r] = g[r] || []).push(p) }
  return g
}
function headShas(paths) {
  const out = {}
  for (const r of Object.keys(groupByRepo(paths))) out[r] = bash(`git -C "${r}" rev-parse HEAD`).trim()
  return out
}
function shaOf(s, repo) { return typeof s === 'string' ? s : ((s && (s[repo] || Object.values(s)[0])) || '') }
function sameShas(a, b) { return Object.keys(b).every(r => shaOf(a, r) === b[r]) }
function singleRepo(figs) { return Object.keys(groupByRepo([...figs.flatMap(figurePaths), `${gitRoot}/x`])).length === 1 }
function allDisjoint(figs) {
  // true iff no two figures share ANY path (plot_script or output file) — the precondition for isolating each
  // in its own worktree + assembling back conflict-free (mirrors polish.js's distinct-file gate for sections).
  const seen = new Set()
  for (const f of figs) for (const p of figurePaths(f)) { if (seen.has(p)) return false; seen.add(p) }
  return true
}
function boundedParallel(thunks, cap) {
  // [[MECH]] run `thunks` with at most `cap` concurrent (mirrors polish.js boundedParallel): sequential batches
  // of `cap`, parallel() within a batch, results kept in `thunks` order. cap>=1.
  const out = []
  const c = Math.max(1, cap)
  for (let i = 0; i < thunks.length; i += c) out.push(...parallel(thunks.slice(i, i + c)))
  return out
}
function runFiguresParallel(figs, cap) {
  const wtRoot = bash(`mktemp -d -t polish-fig-wt 2>/dev/null || mktemp -d "${paperDir}/.polish-fig-wt.XXXXXX"`).trim()
  const units = figs.map(f => {
    const name = slug(f.id)
    const wtdir = `${wtRoot}/${name}`
    const wbranch = `${branch}-fig-${name}`
    // [[MECH]] worktree at baseSha — this figure's UNTOUCHED original. Each worktree has its OWN index, so
    // concurrent commits in different worktrees never contend on a single .git/index.lock. No `|| true` — a
    // worktree-add failure must surface (it would silently drop the figure otherwise).
    bash(`git -C "${paperDir}" worktree add -b "${wbranch}" "${wtdir}" "${baseSha}"`)
    return { fig: f, wtdir, branch: wbranch }
  })
  const results = boundedParallel(units.map(u => () => runFigureUnit(u)), cap)
  assembleFigures(units, results, wtRoot)
}
function runFigureUnit(u) {
  // Spawn ONE figure_runner for this figure; it owns the whole loop inside u.wtdir and returns FIGURE_RESULT_SCHEMA.
  // A null result (dead/overloaded runner) is handled in assembleFigures (keeps the figure's base).
  return agent(figureRunnerGoal(u), roleOpts('figure_runner', FIGURE_RESULT_SCHEMA))
}
function figureRunnerGoal(u) {
  const { fig, wtdir, branch: wbranch } = u
  const wScript = `${wtdir}/${relTo(gitRoot, abs(fig.plot_script))}`
  const wOutputs = (fig.output_files || []).map(o => `${wtdir}/${relTo(gitRoot, abs(o))}`)
  const lic = redesignLicensed(fig)
  const roundCap = lic ? REDESIGN_MAX_ROUNDS : (fig.effort === 'light' ? 1 : MAX_ROUNDS)
  return [
    `You are the FIGURE-RUNNER for figure "${fig.id}" of the paper. You OWN this one figure's entire`,
    `revise→regenerate→evaluate→converge loop, running INSIDE an isolated git worktree, and you RETURN`,
    `FIGURE_RESULT_SCHEMA — you never touch any other figure or the main working tree. Drive the loop by`,
    `SPAWNING subagents (you have the Task tool): the reviser + visual-QA reviewer are the default 'claude'`,
    `subagent (model sonnet); the fidelity gate is subagent_type 'fidelity' (read-only, no Edit/Write). Run the`,
    `fidelity gate and the visual-QA reviewer IN PARALLEL each round.`,
    ``,
    `FIRST read the canonical loop: ${pluginRoot}/spec/figure-loop.md — it is the SINGLE SOURCE for the`,
    `revise→regenerate(HARD GATE)→evaluate→3-way-fidelity→converge steps, the annotation crop-check backstop,`,
    `the freeze discipline, and the FIGURE_RESULT_SCHEMA return. The semantics + visual-QA sub-goals live in`,
    `${pluginRoot}/spec/spawn-prompts/figures-semantics.md and figures-visual-qa.md; the reviser follows the`,
    `paper-polish-ar:research-figure-plotting skill (the namespaced form — never the bare name); the fidelity gate follows the check-figure-fidelity skill. Read them.`,
    `Execute the loop EXACTLY, substituting these bindings:`,
    `  • FIG_ID = ${fig.id}   • CORE_MESSAGE = ${fig.core_message || '(infer from the figure + the prose that cites it)'}`,
    `  • PLOT_SCRIPT (the ONE file you edit, in the worktree) = ${wScript}`,
    `  • OUTPUT_FILES = ${wOutputs.join(', ') || '(none)'}   • REGEN_CMD = ${fig.regen_cmd}`,
    `  • GIT_C (every git command is \`git -C "${wtdir}"\`; the worktree shares the repo object DB) = ${wtdir}`,
    `  • FIG_BASE_SHA (this figure's untouched original, W0) = ${baseSha}   • BRANCH = ${wbranch}`,
    `  • CONVERGE = python3 "${pluginRoot}/scripts/figure_converge.py"  (decide convergence + best-round ONLY`,
    `    via this script — never judge them yourself)`,
    `  • ROUND_CAP = ${roundCap}   • EFFORT = ${fig.effort}   • NO_IMPROVE = 2   • DIMENSIONS = ${JSON.stringify(DIMENSIONS)}`,
    `  • REDESIGN_LICENSED = ${lic}   • DESIGN_BRIEF = ${lic || (fig.design_brief && fig.design_brief.verdict) ? fmt(fig.design_brief || null) : '(none)'}`,
    ...(lic ? [
      `    (verdict=redesign, approved: round 1 IMPLEMENTS the brief — chart type / axis windows / panel`,
      `    composition may change per the brief, same cached data + statistics + series meanings; the reviser`,
      `    retrieves figure-design; the fidelity gate judges structural changes AGAINST the brief (matching =`,
      `    PASS + design_changes, off-brief = HOLD); AFTER the first fidelity-PASS round RE-RUN the semantics`,
      `    pre-pass on the NEW figure and use that manifest for later rounds. NEVER edit any .tex — the`,
      `    brief's caption/tex changes are applied by the orchestrator at Emit.)`,
    ] : []),
    `  • SEMANTICS: run the read-only semantics pre-pass (figures-semantics.md) yourself, in the worktree, before round 1.`,
    `  • SURVEY relational baseline (stay consistent — never reproduce a removable decoration for consistency):`,
    `    ${fmt(SURVEY.baseline)}`,
    (SURVEY.shared_defects || []).length ? `  • SHARED DEFECTS to strip set-wide (override the baseline): ${fmt(SURVEY.shared_defects)}` : ``,
    (SURVEY.inconsistencies || []).filter(i => sameFig(i.figure_id, fig.id)).length ? `  • Inconsistencies flagged for THIS figure: ${fmt((SURVEY.inconsistencies || []).filter(i => sameFig(i.figure_id, fig.id)))}` : ``,
    venueFiguresGuide(),
    think('reviser'),
  ].filter(Boolean).join('\n')
}
function assembleFigures(units, results, wtRoot) {
  // [[MECH]] BARRIER write-back: bring each figure's shipped script + outputs from its worktree branch onto the
  // main polish-fig branch. Figures are pairwise-disjoint (allDisjoint), so checkout-per-figure never conflicts;
  // ONE add + ONE commit per figure keeps the main index single-writer. Then roll up run-wide state, and the
  // orchestrator RE-VERIFIES the mandated annotation crop-check on each shipped figure (never trust the runner).
  phase('Figures')
  for (let i = 0; i < units.length; i++) {
    const u = units[i], r = results[i], fig = u.fig
    if (!r) {
      log(`assemble: ${fig.id} — figure-runner returned nothing; keeping its base + flagging for author.`)
      blockers.push({ id: fig.id, why: 'figure-runner returned no result (dead/overloaded); shipped original' })
      figureReport.push({ id: fig.id, script: fig.plot_script, shippedVersion: 0, shippedSha: baseSha, actionable: null, stopReason: 'runner_failed', improvements: [] })
      writeTaskStatus(fig, [])
      continue
    }
    const figFiles = figurePaths(fig)
    if (figFiles.length && (r.branch || u.branch)) {
      const q = figFiles.map(p => `"${p}"`).join(' ')
      bash(`git -C "${gitRoot}" checkout "${r.branch || u.branch}" -- ${q} 2>&1 || true`)
      bash(`git -C "${gitRoot}" add -- ${q} 2>&1 || true`)
      bash(`git -C "${gitRoot}" diff --cached --quiet || git -C "${gitRoot}" commit -m ${shq(`polish-figures: assemble ${fig.id} (v${r.shipped_version ?? 0}, ${r.stop_reason || '—'})`)} 2>&1 || true`)
    }
    // [[MECH]] orchestrator re-check of the mandated annotation crop-check on the SHIPPED figure — the SAME
    // deterministic grep the serial runFigure runs; it does NOT trust the runner's self-report. If the shipped
    // script still has in-plot annotations but the shipped round reported checking none, surface it for the author.
    const inPlot = countInPlotAnnotations(abs(fig.plot_script))
    const shippedRound = (r.rounds || []).find(rd => rd.round === r.shipped_version)
    const checkedN = shippedRound ? (shippedRound.annotations_checked_n || 0) : 0
    if (inPlot > 0 && checkedN === 0 && r.shipped_version) {
      deferredFlags.push({ id: fig.id, round: r.shipped_version, severity: 'blocking', dimension: 'legibility',
        issue: `orchestrator re-check: ${inPlot} in-plot annotation(s) present but the runner reported 0 crop-checked — overlap with a data element not certified`,
        defer_reason: 'surfaced for author (parallel-path backstop, not left to runner honesty)' })
      log(`${fig.id}: assemble backstop — ${inPlot} in-plot annotation(s), 0 crop-checked; flagged for author.`)
    }
    // roll up run-wide state from the runner's envelope (same run-wide arrays the serial path fills)
    figureReport.push({ id: fig.id, script: fig.plot_script, shippedVersion: r.shipped_version ?? 0, shippedSha: r.shipped_sha || readHeadSha(),
      actionable: (r.actionable ?? null), stopReason: r.stop_reason || 'max_rounds',
      improvements: ((shippedRound && shippedRound.hunks) || []).map(h => (h.rule_tag || '') + (h.rationale ? `: ${h.rationale}` : '')) })
    for (const b of (r.blockers || [])) blockers.push({ id: fig.id, why: (typeof b === 'string' ? b : (b && b.why)) || 'reviser could not proceed' })
    for (const dc of (r.design_changes || [])) designChanges.push({ id: fig.id, ...(typeof dc === 'object' ? dc : { what: String(dc) }) })
    for (const n of (r.needs_approval || [])) needsApproval.push({ id: fig.id, ...(typeof n === 'object' ? n : { why: String(n) }) })
    for (const fr of (r.fidelity_reverts || [])) fidelityReverts.push({ id: fig.id, ...(typeof fr === 'object' ? fr : { why: String(fr) }) })
    for (const cc of (r.close_calls || [])) closeCalls.push({ id: fig.id, ...(typeof cc === 'object' ? cc : { why: String(cc) }) })
    for (const df of (r.deferred_flags || [])) deferredFlags.push({ id: fig.id, ...(typeof df === 'object' ? df : { issue: String(df) }) })
    for (const bc of (r.baseline_conflicts || [])) { const issue = typeof bc === 'string' ? bc : (bc && bc.issue); if (issue && !baselineCorrections.includes(issue)) baselineCorrections.push(issue) }
    // per-figure TASK_STATUS (synthesize a rounds array shaped exactly like the serial path's)
    writeTaskStatus(fig, (r.rounds || []).map(rd => ({ round: rd.round, fidelity: { verdict: rd.fidelity_verdict }, actionable: (rd.actionable == null ? Infinity : rd.actionable), revise: { hunks: rd.hunks || [] } })))
  }
  // Clean up worktrees + their branches (cleanup `|| true` is fine — not a commit path).
  for (const u of units) bash(`git -C "${paperDir}" worktree remove --force "${u.wtdir}" 2>&1 || true`)
  bash(`git -C "${paperDir}" worktree prune 2>&1 || true`)
  bash(`rm -rf "${wtRoot}" 2>&1 || true`)
  log(`assemble: merged ${units.length} parallel figure(s) onto ${branch}; cleaned worktrees`)
}

// ── Evaluators ────────────────────────────────────────────────────────────────
function runFigureSemantics(fig, baseSha) {
  // Read-only pre-revise pass: render the ORIGINAL figure, read its LaTeX caption + the prose that
  // cites it, and return a structured map of what each visual encoding MEANS. This is the visual freeze
  // manifest — it tells the reviser what cannot be collapsed or relocated, and it extends the fidelity
  // gate beyond data/transform to cover encoding conventions (e.g., 3-color cross-panel L indexing).
  const pngOut = (fig.output_files || []).find(f => /\.png$/i.test(f)) || (fig.output_files || [])[0] || ''
  const captionCtx = (() => {
    try {
      return bash(
        `grep -r -n -B2 -A8 '\\\\caption' "${paperDir}" --include='*.tex' 2>/dev/null | head -80 || echo "(no captions found)"`
      )
    } catch { return '(caption grep failed)' }
  })()
  // Extraction rubric (STEP 1-3 + the encoding / annotation / structural-choice schema-fill) →
  // spec/spawn-prompts/figures-semantics.md. The goal injects the figure id + PNG + regen cmd + paperDir +
  // pre-grepped caption context.
  return agent(
    [
      `Read ${pluginRoot}/spec/spawn-prompts/figures-semantics.md and do EXACTLY what it says — ONE read-only pass; return FIGURE_SEMANTICS_SCHEMA.`,
      `<FIG_ID>: ${fig.id}`,
      `<PNG_OUT>: ${pngOut}`,
      `<REGEN_CMD>: ${fig.regen_cmd}`,
      `<PAPER_DIR>: ${paperDir}`,
      `<CAPTION_CTX>:\n${captionCtx}`,
    ].join('\n'),
    roleOpts('reviewer', FIGURE_SEMANTICS_SCHEMA)
  )
}

function runFigureFidelity(fig, sha, base, semantics) {
  // [[MECH]] read-only gate: did the restyling move the SCIENCE the figure conveys? Compares the script
  // base→revised with READ-ONLY git; never edits. `base` is this figure's local pre-edit sha.
  // `semantics` (optional) extends the gate: encoding collapses (3 colors → 1 where each encoded a
  // different condition) are caught here as FAIL, not treated as style PASS.
  // multi-repo aware: the script and the PNG each git-show from their OWNING repo at that repo's sha
  // (sha/base may be {repo: sha} maps; shaOf resolves either shape).
  const srepo = repoOf(abs(fig.plot_script))
  const rel = relTo(srepo, abs(fig.plot_script))
  const pngOut = (fig.output_files || []).find(f => /\.png$/i.test(f)) || (fig.output_files || [])[0] || ''
  const pngAbs = pngOut ? abs(pngOut) : ''
  const prepo = pngOut ? repoOf(pngAbs) : srepo
  const pngRel = pngOut ? relTo(prepo, pngAbs) : ''
  return agent(
    [
      `You are the figure-fidelity gate for figure "${fig.id}". Compare the committed revision of its`,
      `plotting script against the original and judge ONLY whether the SCIENCE the figure conveys moved`,
      `(not its style). You have Bash for READ-ONLY git. Fetch BOTH versions before judging:`,
      `  BASE:    git -C "${srepo}" show ${shaOf(base, srepo)}:${rel}`,
      `  REVISED: git -C "${srepo}" show ${shaOf(sha, srepo)}:${rel}`,
      ...(pngRel ? [
        `PRIMARY EVIDENCE — LOOK at the two RENDERS (first-class basis; the code diff corroborates):`,
        `  REVISED render (on disk): Read ${pngAbs}`,
        `  BASE render: git -C "${prepo}" show ${shaOf(base, prepo)}:${pngRel} > "$TMPDIR/fidelity-base-${fig.id}.png" 2>/dev/null; if that file is non-empty, Read it.`,
        `Compare what the READER sees — point positions, curve shapes, bar heights, the distinct colors/linestyles used, and every annotated number. The renders tell you WHETHER the science moved; the code diff (above) tells you WHICH frozen item moved.`,
        `GRACEFUL DEGRADATION: if the base PNG is not in the repo (extract yields an empty file) or a render is otherwise unavailable, judge from the code diff alone — a missing/failed render is NEVER by itself a FAIL.`,
      ] : []),
      `Retrieve check-figure-fidelity and apply its THREE-WAY verdict (PASS / HOLD / FAIL) in full; keep its HOLD/approval logic intact.`,
      ...(redesignLicensed(fig)
        ? [
            `APPROVED DESIGN BRIEF (the presentation contract this figure was REDESIGNED under — apply the`,
            `skill's "judging against an approved design brief" section):`,
            fmt(fig.design_brief),
            `Structural changes (chart type / panel composition / axis plan) MATCHING this brief are licensed`,
            `presentation → PASS, each reported in design_changes[{what, why_science_preserved}]. An OFF-brief`,
            `structural change is HOLD (deliberate but uncontracted → needs_approval), not FAIL. The brief NEVER`,
            `licenses a frozen-item move — data source / transform / statistics / annotated values / series`,
            `meaning are FAIL regardless. Encoding-collapse still FAILs when the number of DISTINGUISHABLE`,
            `conditions drops; a brief-matching channel swap that keeps every condition distinguishable is PASS.`,
          ]
        : []),
      `Return PASS/HOLD/FAIL + drift_items (FAIL) + needs_approval (HOLD) + close_calls${redesignLicensed(fig) ? ' + design_changes (brief-matching structural changes you PASSed)' : ''}.`,
      `In your first returned item (a drift_items or close_calls entry), state whether you viewed both renders or fell back to code-diff, and why.`,
      `VISUAL ENCODING CONSISTENCY (additional check beyond data/transform):`,
      ...(semantics && (semantics.visual_encodings || []).some(e => e.do_not_collapse)
        ? [
            `For each encoding with do_not_collapse=true in the manifest below, count the DISTINCT values`,
            `used for that channel in BASE vs REVISED. Confirm by LOOKING at the two renders — count the distinct`,
            `colors/linestyles actually visible; the code count corroborates. Fewer distinct values in REVISED = an encoding`,
            `dimension was collapsed = FAIL. Record as a drift_item with why="encoding collapsed: N distinct`,
            `values → M (M<N) — reader can no longer distinguish conditions that were previously separated".`,
            `This is NOT a style change; it destroys the same information as removing a data column would.`,
            `Semantics encoding map: ${fmt(semantics)}`,
          ]
        : [`(no do_not_collapse encodings in semantics — data/transform check only)`]),
      ...(semantics && (semantics.annotations || []).some(a => a.move_inside_requires_clear_space)
        ? [
            `Annotation placement: for each annotation with move_inside_requires_clear_space=true, if the`,
            `BASE script had it outside the plot area (ax.set_title / suptitle) and the REVISED script moved`,
            `it inside (ax.text with transAxes/transData), Read the rendered PNG and confirm the text's`,
            `bounding box does not touch any data element. Unverified inside placement = FAIL; add to`,
            `drift_items with why="annotation moved inside plot — data overlap not verified at render time".`,
          ]
        : []),
      think('fidelity'),
    ].join('\n'),
    roleOpts('fidelity', FIGURE_FIDELITY_SCHEMA)
  )
}

// Deterministic floor for the visual-QA crop-check. The crop-and-Read of every in-plot annotation is a
// MANDATORY protocol, but it is agent-executed prose the reviewer can skip and still return actionable=0
// (exactly how an annotation anchored over the data once shipped). Count the axes-anchored text/annotate
// calls (transAxes/transData) in the plotting script — the elements the reviewer MUST crop-and-Read;
// margin text (set_title / xlabel / ylabel / suptitle) cannot overlap the data area and is excluded.
function countInPlotAnnotations(scriptPath) {
  try {
    return parseInt(bash(`grep -oE 'transform=[A-Za-z_.]*\\.(transAxes|transData)' "${scriptPath}" 2>/dev/null | wc -l`).trim(), 10) || 0
  } catch { return 0 }
}

function runVisualQA(fig, sha, semantics) {
  // The visual-QA reviewer: render the regenerated figure and actually LOOK; judge the skill's ABSOLUTE
  // standard FIRST (de-AI default-off rules win over the baseline — a defect shared by all figures is still
  // a defect), THEN cross-figure consistency. Read-only (reuses the reviewer shell; renders + Reads PNGs).
  const pngOut = (fig.output_files || []).find(f => /\.png$/i.test(f)) || (fig.output_files || [])[0] || ''
  // QA rubric (mandatory render + crop-and-Read protocol, two-tier absolute-then-relational judging,
  // baseline_conflict / annotations_checked contract) → spec/spawn-prompts/figures-visual-qa.md. The goal
  // injects the figure handles + the dimensions and APPENDS the runtime context blocks (encoding freeze,
  // relational baseline, confirmed-removable defects). The convergence-blocking crop-check backstop +
  // actionable-count arithmetic stay in the JS (runFigure), so this prose can never weaken the gate.
  return agent(
    [
      `You are the visual-QA reviewer for figure "${fig.id}" at the committed revision; judge the ${DIMENSIONS.join(', ')} dimensions.`,
      `Read ${pluginRoot}/spec/spawn-prompts/figures-visual-qa.md and do EXACTLY what it says; return FIGURE_QUALITY_SCHEMA with dimensions_covered = ${JSON.stringify(DIMENSIONS)}.`,
      `<FIG_ID>: ${fig.id}`,
      `<DIMENSIONS>: ${DIMENSIONS.join(', ')}`,
      `<REGEN_CMD>: ${fig.regen_cmd}`,
      `<PNG_OUT>: ${pngOut}`,
      `<PLOT_SCRIPT>: ${fig.plot_script}`,
      // conditional injection: the do_not_collapse channels the QA must flag a collapse of (rule prose in the file)
      ...(semantics && (semantics.visual_encodings || []).some(e => e.do_not_collapse)
        ? [
            `VISUAL ENCODING FREEZE — do_not_collapse channels:`,
            `${fmt((semantics.visual_encodings || []).filter(e => e.do_not_collapse))}`,
          ]
        : []),
      // the 'design' dimension's contract: with a brief, judge takeaway legibility + every regen_expectation;
      // without one, judge against figure-design's axioms (rule prose in figures-visual-qa.md).
      fig.design_brief
        ? `DESIGN BRIEF (the 'design' dimension judges this FIRST — reader_takeaway legible at a glance + EVERY regen_expectation holds; verdict=${fig.design_brief.verdict}${redesignLicensed(fig) ? ', redesign licensed' : ', NO redesign license — an archetype-level defect is deferred with defer_reason="needs design-brief redesign", never actionable churn'}):\n${fmt(fig.design_brief)}`
        : ``,
      `RELATIONAL BASELINE (tier-2 FREE choices + any sibling_alignment note):\n${fmt(SURVEY.baseline)}`,
      baselineCorrections.length
        ? `CONFIRMED-REMOVABLE DEFECTS (already confirmed removable this run):\n${fmt(baselineCorrections)}`
        : ``,
      venueFiguresGuide(),
      think('reviewer'),
    ].filter(Boolean).join('\n'),
    roleOpts('reviewer', FIGURE_QUALITY_SCHEMA)
  )
}

// ── git / fs helpers ────────────────────────────────────────────────────────
function restoreFigure(fig, sha) {
  // Restore ONLY this figure's script + outputs to `sha` (other figures untouched); staged for commit.
  // Multi-repo aware: paths grouped by owning repo, `sha` may be a {repo: sha} map (shaOf resolves either).
  const byRepo = groupByRepo(figurePaths(fig))
  for (const r of Object.keys(byRepo)) {
    bash(`git -C "${r}" checkout ${shaOf(sha, r)} -- ${byRepo[r].map(p => `"${p}"`).join(' ')} 2>&1 || true`)
  }
}
function commitFigure(fig, msg) {
  const byRepo = groupByRepo(figurePaths(fig))
  for (const r of Object.keys(byRepo)) {
    const q = byRepo[r].map(p => `"${p}"`).join(' ')
    const res = bash(`git -C "${r}" add -- ${q} 2>&1; git -C "${r}" commit -m ${shq(msg)} -- ${q} 2>&1 || true`)
    // keep the paper repo's linear run chain even on a no-op (the other repos skip empty commits)
    if (r === gitRoot && /nothing to commit|no changes added|did not match|pathspec/i.test(res)) bash(`git -C "${r}" commit --allow-empty -m ${shq(msg)}`)
  }
}
function readHeadSha() { return bash(`git -C "${gitRoot}" rev-parse HEAD`).trim() }

function buildFigureManifest(root, proj) {
  // [[MECH]] figure mode = MIRROR of polish. FREEZE the cached analysis data + the manuscript prose; FREE the
  // plotting scripts + the figure files they regenerate. Extension globs (*.csv/*.tex/…) freeze those file
  // types under ANY path via the hook's basename fnmatch; data DIRECTORIES (data/datasets/raw/cache/… ) are
  // glob-expanded under the repo root into the abspath denylist so extension-less data files are frozen too;
  // denylist_rel makes the freeze worktree-safe. Figures (.svg/.pdf/.png) and scripts (.py) are deliberately
  // NOT denylisted — that is the whole point of figure mode. The deterministic builder is
  // scripts/build_manifest.py --mode figure; pipe it {mode:"figure", root:<gitRoot>, proj} on stdin (it forces
  // format "latex" and ignores master/manuscripts). It writes <proj>/.polish/fidelity-manifest.json.
  const input = JSON.stringify({ mode: 'figure', root, proj })
  bash(`printf '%s' ${shq(input)} | python3 "${pluginRoot}/scripts/build_manifest.py" >/dev/null`)
}

// ── design briefs + Emit tex-apply helpers ─────────────────────────────────────
// [[MECH]] the redesign LICENSE: brief verdict 'redesign' AND the briefs not stamped 'restyle_only'.
// Everything structural hangs off this ONE predicate (roundCap, reviser plan, fidelity judging, tex apply).
function redesignLicensed(f) {
  return APPROVAL !== 'restyle_only' && !!(f && f.design_brief && f.design_brief.verdict === 'redesign')
}

function writeBriefs() {
  // Persist the whole SURVEY (incl. per-figure design briefs) + run coordinates: the design stage's
  // durable artifact — gateable (approved: null → 'owner'/'auto'/'restyle_only') and the repaint stage's
  // resume source. Written via bash (bypasses the Edit/Write hook by design, like writeReport).
  const p = `${paperDir}/${BRIEFS_PATH_REL}`
  const payload = { branch, base_sha: baseSha, repo_bases: REPO_BASES, approved: APPROVAL, survey: SURVEY }
  bash(`printf '%s' ${shq(JSON.stringify(payload, null, 2))} > "${p}"`)
  const md = `${paperDir}/figure-design-briefs.md`
  bash(`printf '%s' ${shq(renderBriefsMd())} > "${md}"`)
  bash(`git -C "${gitRoot}" add "${p}" "${md}" 2>&1 && (git -C "${gitRoot}" commit -m ${shq(`polish-figures: design briefs (${figures.length} figure(s))`)} -- "${p}" "${md}" 2>&1 || true)`)
}

function renderBriefsMd() {
  const L = [`# figure design briefs`, ``, `- Branch: \`${branch}\` (base \`${(baseSha || '').slice(0, 8)}\`)`, `- Approved: ${APPROVAL || 'PENDING — stamp "approved" in ${BRIEFS_PATH_REL} (owner | auto | restyle_only)'}`, ``]
  for (const f of figures) {
    const b = f.design_brief || {}
    L.push(`## ${f.id} — ${b.verdict || 'restyle'}`, ``)
    L.push(`- Current render: ${(f.output_files || []).find(o => /\.png$/i.test(o)) || (f.output_files || [])[0] || '—'}`)
    L.push(`- Reader takeaway: ${b.reader_takeaway || '—'}`)
    L.push(`- Archetype: ${b.archetype || '—'}`)
    if ((b.axis_plan || []).length) { L.push(`- Axis plan:`); for (const a of b.axis_plan) L.push(`  - ${a.axis}: ${a.window || ''} ${a.scale || ''} — ${a.rationale || ''}`) }
    if ((b.panel_plan || []).length) { L.push(`- Panel plan:`); for (const pp of b.panel_plan) L.push(`  - ${pp.panel}: **${pp.action}** — ${pp.content || ''}`) }
    if ((b.regen_expectations || []).length) { L.push(`- Acceptance checks:`); for (const e of b.regen_expectations) L.push(`  - ${e}`) }
    if (b.caption_implication) L.push(`- Caption implication: ${b.caption_implication}`)
    if (b.proposed_caption) L.push(`- Proposed caption: ${b.proposed_caption}`)
    if (b.tex_structure_patch) L.push(`- Tex structure change: ${b.tex_structure_patch}`)
    L.push(``)
  }
  return L.join('\n')
}

function applyTexChanges() {
  // [[MECH]] Emit-phase application of the APPROVED caption / tex-structure changes of SHIPPED redesigns.
  // Guards, in order: (1) only figures whose redesign actually shipped (shippedVersion > 0); (2) only when
  // the briefs are stamped 'owner' or 'auto' (restyle_only / unstamped → patches file only); (3) the edit
  // runs under the POLISH-mode token-freeze manifest (numbers / \cite / \ref / \label survive verbatim —
  // hook-enforced); (4) a failed recompile deterministically REVERTS the tex commit → patches file.
  const items = figures
    .filter(f => redesignLicensed(f) && f.design_brief && (f.design_brief.proposed_caption || f.design_brief.tex_structure_patch))
    .filter(f => { const s = figureReport.find(r => r.id === f.id); return s && s.shippedVersion > 0 })
  if (!items.length) return
  if (APPROVAL !== 'owner' && APPROVAL !== 'auto') { writeTexPatches(items, `briefs approval is '${APPROVAL}' — tex changes not applied`); return }
  const preSha = readHeadSha()
  // Swap freezes: figure mode (ALL .tex frozen) → polish mode (manuscripts editable under token preservation).
  const texFiles = bash(`find "${paperDir}" -name '*.tex' -not -path '*/.git/*' 2>/dev/null | sort`).split('\n').map(s => s.trim()).filter(Boolean)
  bash(`rm -f "${projectDir}/.polish/fidelity-manifest.json"`)
  const pin = JSON.stringify({ mode: 'polish', root: gitRoot, master: masterPath, manuscripts: texFiles, format: 'latex', proj: projectDir })
  bash(`printf '%s' ${shq(pin)} | python3 "${pluginRoot}/scripts/build_manifest.py" >/dev/null`)
  const res = agent(
    [
      `You are the caption/tex-structure APPLIER for polish-figures' Emit phase. ${items.length} redesigned`,
      `figure(s) shipped with gate-approved caption / structure changes; apply them to the manuscript .tex.`,
      `Use Edit (never Write) on the .tex files under ${paperDir}. For each item: locate the figure's`,
      `environment (by its \\label / \\includegraphics target from paper_location), then`,
      `  • proposed_caption: replace ONLY the \\caption{...} content with the proposed text, verbatim;`,
      `  • tex_structure_patch: apply it exactly as written (e.g. insert a booktabs table float, drop a`,
      `    panel's \\includegraphics, move a figure environment to the SI) — nothing beyond it.`,
      `TOKEN FREEZE (hook-enforced): every number, \\cite, \\ref and \\label key in the text you replace must`,
      `survive verbatim in your replacement. If the hook DENIES an edit, do NOT fight or work around it —`,
      `record that item as denied (with the hook's reason) and continue with the rest. Never touch the .bib,`,
      `never change a number or claim. Do NOT git-commit (the orchestrator commits).`,
      `Items:`,
      fmt(items.map(f => ({ id: f.id, paper_location: f.paper_location, proposed_caption: f.design_brief.proposed_caption || null, tex_structure_patch: f.design_brief.tex_structure_patch || null }))),
      `Return TEX_APPLY_SCHEMA (applied / denied per item).`,
      think('reviser'),
    ].join('\n'),
    roleOpts('reviser', TEX_APPLY_SCHEMA)
  )
  texApply.applied = (res && res.applied) || []
  texApply.denied = (res && res.denied) || []
  const changed = bash(`git -C "${gitRoot}" diff --name-only -- '*.tex' 2>/dev/null || true`).split('\n').map(s => s.trim()).filter(Boolean)
  if (!changed.length) { if (texApply.denied.length) writeTexPatches(items, 'every tex edit was denied by the token-freeze hook'); return }
  bash(`git -C "${gitRoot}" add -- ${changed.map(c => `"${gitRoot}/${c}"`).join(' ')} 2>&1`)
  bash(`git -C "${gitRoot}" commit -m ${shq(`polish-figures: apply gate-approved captions/tex-structure (${texApply.applied.length} item(s))`)} 2>&1 || true`)
  // Compile check (deterministic do-no-harm): a tex apply that breaks the build is reverted, not shipped.
  const canTeX = (() => { try { bash('command -v pdflatex >/dev/null 2>&1'); return true } catch { return false } })()
  if (canTeX && /\.tex$/.test(masterPath)) {
    try {
      bash(`bash "${pluginRoot}/scripts/render_pdf.sh" --repo "${gitRoot}" --master "${relTo(gitRoot, masterPath)}" --rev HEAD --out "${paperDir}/.polish-figures-texcheck.pdf" && rm -f "${paperDir}/.polish-figures-texcheck.pdf"`)
    } catch (e) {
      bash(`git -C "${gitRoot}" checkout ${preSha} -- ${changed.map(c => `"${gitRoot}/${c}"`).join(' ')} 2>&1`)
      bash(`git -C "${gitRoot}" commit -m "polish-figures: REVERT tex apply (recompile failed)" 2>&1 || true`)
      texApply.reverted = true
      writeTexPatches(items, `recompile FAILED after the tex apply — reverted to ${preSha.slice(0, 8)}; apply manually`)
      log(`Emit tex-apply: recompile failed — reverted; changes fell back to figure-tex-patches.md`)
      return
    }
  } else {
    log(`Emit tex-apply: no TeX toolchain — applied without a compile check (cross-check lints figure<->prose next)`)
  }
  log(`Emit tex-apply: ${texApply.applied.length} applied, ${texApply.denied.length} denied (token-freeze)`)
  if (texApply.denied.length) writeTexPatches(items.filter(f => texApply.denied.some(d => d.id === f.id)), 'denied by the token-freeze hook — apply manually')
}

function writeTexPatches(items, why) {
  const p = `${paperDir}/figure-tex-patches.md`
  const L = [`# figure tex patches — NOT applied (${why})`, ``]
  for (const f of items) {
    const b = f.design_brief || {}
    L.push(`## ${f.id} (${f.paper_location || '—'})`, ``)
    if (b.proposed_caption) L.push(`Proposed \\caption:`, '```tex', b.proposed_caption, '```', ``)
    if (b.tex_structure_patch) L.push(`Structure change:`, '```', b.tex_structure_patch, '```', ``)
  }
  bash(`printf '%s' ${shq(L.join('\n'))} > "${p}"`)
  bash(`git -C "${gitRoot}" add "${p}" 2>&1 && (git -C "${gitRoot}" commit -m "polish-figures: tex patches (manual apply)" -- "${p}" 2>&1 || true)`)
}

function writeReport() {
  const abs2 = `${paperDir}/polish-figures-report.md`
  try {
    bash(`printf '%s' ${shq(renderReport())} > "${abs2}"`)
    bash(`git -C "${gitRoot}" add "${abs2}" 2>&1 && (git -C "${gitRoot}" commit -m "polish-figures: run report" -- "${abs2}" 2>&1 || true)`)
    return abs2
  } catch (e) { log(`report write failed (${String(e && e.message || e).split('\n')[0]})`); return null }
}

function renderReport() {
  const L = []
  L.push(`# polish-figures report`, ``)
  L.push(`- Branch: \`${branch}\` (from \`${baseSha.slice(0, 8)}\`)`)
  L.push(`- Figures in scope: ${figures.map(f => f.id).join(', ') || '(none)'}`)
  L.push(`- Design briefs: \`${BRIEFS_PATH_REL}\` (approved=${APPROVAL || 'PENDING'})`, ``)
  L.push(`## Per-figure outcomes`, ``)
  L.push(`| figure | script | design verdict | shipped version | actionable flags | stop reason |`)
  L.push(`|---|---|---|---|---|---|`)
  for (const s of figureReport) {
    const f = figures.find(x => x.id === s.id)
    const v = (f && f.design_brief && f.design_brief.verdict) || '—'
    L.push(`| ${s.id} | ${s.script || '—'} | ${v} | ${s.shippedVersion} | ${s.actionable === null ? '∞ (do-no-harm)' : s.actionable} | ${s.stopReason} |`)
  }
  L.push(``)
  L.push(`## Redesigns — brief-matching structural changes (fidelity-PASSed, FYI)`, ``)
  if (!designChanges.length) L.push(`_None — no figure shipped a licensed structural redesign change._`, ``)
  else { for (const d of designChanges) L.push(`- **${d.id}**${d.round ? ` (r${d.round})` : ''}: ${d.what || ''} — ${d.why_science_preserved || ''}`); L.push(``) }
  L.push(`## Caption / tex-structure application (Emit)`, ``)
  if (!texApply.applied.length && !texApply.denied.length && !texApply.reverted) L.push(`_None needed (no shipped redesign carried a caption/structure change)._`, ``)
  else {
    if (texApply.reverted) L.push(`**REVERTED — recompile failed after the apply; see \`figure-tex-patches.md\` for manual application.**`, ``)
    for (const a of texApply.applied) L.push(`- applied: **${a.id}** (${a.kind || 'caption'}${a.file ? `, ${a.file}` : ''})`)
    for (const d of texApply.denied) L.push(`- DENIED (token-freeze): **${d.id}** — ${d.why || ''} (in \`figure-tex-patches.md\`)`)
    L.push(``)
  }
  L.push(`## Main improvements per figure`, ``)
  const withImp = figureReport.filter(s => (s.improvements || []).length)
  if (!withImp.length) L.push(`_No restyling changes recorded._`, ``)
  else { for (const s of withImp) { L.push(`- **${s.id}**:`); for (const i of s.improvements) L.push(`  - ${i}`) } L.push(``) }
  L.push(`## Figures blocked — need author (unclear / missing data, script, or location)`, ``)
  if (!blockers.length) L.push(`_None._`, ``)
  else { for (const b of blockers) L.push(`- **${b.id}**: ${b.why}`); L.push(``) }
  L.push(`## Numeric / scale rescales — NEED YOUR APPROVAL (held, NOT shipped)`, ``)
  if (!needsApproval.length) L.push(`_None — no figure needed a numeric/scale rescale._`, ``)
  else {
    L.push(`Each was reverted (do-no-harm) and is waiting for you to approve before it goes into the figure:`, ``)
    for (const n of needsApproval) {
      L.push(`- **${n.id}** (r${n.round}): ${n.why || n.rationale || 'numeric/scale rescale'}`)
      if (n.base || n.revised) L.push(`  - base \`${String(n.base || '').slice(0, 140)}\` → revised \`${String(n.revised || '').slice(0, 140)}\``)
      if (n.held_sha) L.push(`  - apply if approved: \`git -C ${gitRoot} checkout ${String(n.held_sha).slice(0, 12)} -- <script> <outputs>\` (held round's script + regenerated outputs)`)
    }
    L.push(``)
  }
  L.push(`## Skipped figures (not regenerable)`, ``)
  if (!skipped.length) L.push(`_None — every figure had a runnable source script._`, ``)
  else { for (const s of skipped) L.push(`- **${s.id}**: ${s.reason}`); L.push(``) }
  L.push(`## Rounds reverted for touching the data (figure-fidelity FAIL)`, ``)
  if (!fidelityReverts.length) L.push(`_None — no restyle moved the science._`, ``)
  else { for (const r of fidelityReverts) L.push(`- **${r.id}** r${r.round}: ${r.why}`); L.push(``) }
  L.push(`## Fidelity close-calls (skim these)`, ``)
  if (!closeCalls.length) L.push(`_None._`, ``)
  else { for (const c of closeCalls) L.push(`- **${c.id}** (r${c.round}): ${c.why || ''}`); L.push(``) }
  L.push(`## Deliberately-kept visual flags (deferred)`, ``)
  if (!deferredFlags.length) L.push(`_None._`, ``)
  else { for (const f of deferredFlags) L.push(`- **${f.id}** [${f.severity}/${f.dimension}]: ${f.issue} — kept because: ${f.defer_reason}`); L.push(``) }
  L.push(`## De-AI default-off decorations stripped set-wide`, ``)
  const allDefects = [
    ...(((SURVEY && SURVEY.shared_defects) || []).map(d => `${d.trait} — ${d.rule}${d.scope ? ` (${d.scope})` : ''}`)),
    ...baselineCorrections.map(c => `${c} (QA-confirmed mid-run)`),
  ]
  if (!allDefects.length) L.push(`_None — the figure set carried no shared default-off decoration._`, ``)
  else { for (const d of allDefects) L.push(`- ${d}`); L.push(``) }
  return L.join('\n')
}

// [[MECH]] TASK_STATUS.md — the living per-figure status the standard (F12) requires. Rebuilt from
// taskStatusBlocks (append-only) each figure so it stays git-committed and crash-safe.
function writeTaskStatus(fig, rounds) {
  const shipped = figureReport.find(r => r.id === fig.id)
  const blk = []
  blk.push(`## ${fig.id}`, ``)
  blk.push(`- 论文位置 / Paper location: ${fig.paper_location || '—'}`)
  blk.push(`- Script: \`${fig.plot_script || '—'}\``)
  blk.push(`- Output(s): ${(fig.output_files || []).map(o => `\`${o}\``).join(', ') || '—'}`)
  blk.push(`- Core message: ${fig.core_message || '—'}`)
  blk.push(`- Shipped: ${shipped ? (shipped.shippedVersion === 0 ? 'original (do-no-harm)' : `round ${shipped.shippedVersion}`) + ` (stop=${shipped.stopReason})` : '—'}`)
  blk.push(``, `### Round-by-round`, ``)
  if (!rounds.length) blk.push(`_No round committed (blocked or nothing to do)._`)
  else {
    blk.push(`| round | fidelity | actionable flags | changes |`)
    blk.push(`|---|---|---|---|`)
    for (const r of rounds) {
      const changes = ((r.revise && r.revise.hunks) || []).map(h => h.rule_tag).filter(Boolean).join(', ')
      blk.push(`| ${r.round} | ${r.fidelity ? r.fidelity.verdict : '—'} | ${r.actionable === Infinity ? '∞ (reverted)' : r.actionable} | ${changes || '—'} |`)
    }
  }
  // [[MECH]] C — 已解决问题 (researcher's status record wants resolved AND unresolved, split). The shipped
  // round's hunks ARE the landed fixes; the original (do-no-harm) ships nothing, so resolved is empty.
  const resolved = (shipped && shipped.shippedVersion !== 0) ? (shipped.improvements || []) : []
  blk.push(``, `### 已解决 (Resolved — landed in the shipped figure)`, ``)
  if (!resolved.length) blk.push(`_None (shipped the original, or nothing landed)._`)
  else for (const r of resolved) blk.push(`- ${r}`)

  const unresolved = deferredFlags.filter(f => f.id === fig.id)
  const blocker = blockers.find(b => b.id === fig.id)
  const cc = closeCalls.filter(c => c.id === fig.id)
  const na = needsApproval.filter(n => n.id === fig.id)
  blk.push(``, `### 未解决 / 需作者确认 (Unresolved / needs author)`, ``)
  if (!unresolved.length && !blocker && !cc.length && !na.length) blk.push(`_None._`)
  else {
    if (blocker) blk.push(`- **BLOCKED (author)**: ${blocker.why}`)
    for (const n of na) blk.push(`- **需批准 (rescale)** r${n.round}: ${n.why || n.rationale || 'numeric/scale rescale held for approval'}`)
    for (const f of unresolved) blk.push(`- deferred [${f.severity}/${f.dimension}]: ${f.issue} — ${f.defer_reason}`)
    for (const c of cc) blk.push(`- fidelity close-call (r${c.round}): ${c.why || ''}`)
  }
  blk.push(``)
  taskStatusBlocks.push(blk.join('\n'))

  const head = [
    `# TASK_STATUS — figure polishing`, ``,
    `- Branch: \`${branch}\` (from \`${(baseSha || '').slice(0, 8)}\`)`,
    `- Figures in scope: ${figures.map(f => f.id).join(', ') || '(none)'}`, ``,
  ].join('\n')
  const body = head + taskStatusBlocks.join('\n')
  const p = `${paperDir}/TASK_STATUS.md`
  try {
    bash(`printf '%s' ${shq(body)} > "${p}"`)
    bash(`git -C "${gitRoot}" add "${p}" 2>&1 && (git -C "${gitRoot}" commit -m ${shq(`polish-figures: TASK_STATUS after ${fig.id}`)} -- "${p}" 2>&1 || true)`)
  } catch (e) { log(`TASK_STATUS write failed (${String(e && e.message || e).split('\n')[0]})`) }
}

// ── tiny helpers ──────────────────────────────────────────────────────────────
function dirname(p) { return p.replace(/\/[^/]*$/, '') || '.' }
function abs(p) { return p && p.startsWith('/') ? p : `${gitRoot}/${p}` }
function slug(s) { return String(s).replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-|-$/g, '') || 'fig' }
function sameFig(a, b) { return String(a || '').toLowerCase().includes(String(b || '').toLowerCase()) || String(b || '').toLowerCase().includes(String(a || '').toLowerCase()) }
function fmt(o) { return JSON.stringify(o || {}, null, 2) }
function relTo(root, a) { return bash(`python3 -c "import os,sys;print(os.path.relpath(sys.argv[1],sys.argv[2]))" "${a}" "${root}"`).trim() }
function shq(s) { return `'` + String(s).replace(/'/g, `'\\''`) + `'` }

// ── Output schemas (the fixed contracts) ──────────────────────────────────────
const FIGURE_SEMANTICS_SCHEMA = {
  type: 'object', required: ['visual_encodings', 'annotations'],
  properties: {
    visual_encodings: {
      type: 'array',
      items: {
        type: 'object', required: ['channel', 'element', 'encodes', 'scientific_role'],
        properties: {
          channel: { type: 'string' },         // "color", "linestyle", "marker_shape", "position"
          element: { type: 'string' },          // "solid line + filled marker", "dashed line", etc.
          encodes: { type: 'string' },          // what scientific / experimental dimension
          scientific_role: { type: 'string' },  // why this encoding matters for the reader
          distinct_values: { type: 'array', items: { type: 'string' } }, // each value → what it encodes
          do_not_collapse: { type: 'boolean' }, // true = each value encodes a different condition; collapsing = FAIL
        },
      },
    },
    annotations: {
      type: 'array',
      items: {
        type: 'object', required: ['content_pattern', 'placement_type', 'encodes'],
        properties: {
          content_pattern: { type: 'string' },   // e.g. "L=1, Δ=2.34 [CI] (tier)"
          placement_type: { type: 'string', enum: ['above_axes', 'figure_title', 'inside_plot_area', 'axis_label'] },
          encodes: { type: 'string' },            // what information this text conveys
          move_inside_requires_clear_space: { type: 'boolean' }, // true if currently outside — moving inside needs render verification
        },
      },
    },
    structural_choices: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          choice: { type: 'string' },
          scientific_reason: { type: 'string' },
          do_not_change: { type: 'boolean' },
        },
      },
    },
    caption_summary: { type: 'string' },
    prose_context: { type: 'string' },
  },
}

const FIGURE_SURVEY_SCHEMA = {
  type: 'object', required: ['figures', 'baseline'],
  properties: {
    figures: { type: 'array', items: { type: 'object', required: ['id', 'regenerable', 'effort'],
      properties: {
        id: { type: 'string' },
        plot_script: { type: ['string', 'null'] },
        core_message: { type: 'string' },
        paper_location: { type: 'string' },   // .tex file + section / \label the figure sits at (researcher's "论文位置")
        data_sources: { type: 'array', items: { type: 'string' } },
        output_files: { type: 'array', items: { type: 'string' } },
        regen_cmd: { type: ['string', 'null'] },
        regenerable: { type: 'boolean' },
        skip_reason: { type: 'string' },
        effort: { type: 'string', enum: ['light', 'normal', 'heavy'] },
        // the per-figure DESIGN BRIEF (figure-design skill) — the contract a redesign is licensed and judged
        // against. Categorical verdict only (owner rule: no numeric scores). verdict=redesign FORCES effort
        // at least 'normal' (survey rule; the roundCap ternary also makes light unreachable for redesigns).
        design_brief: { type: 'object', required: ['reader_takeaway', 'verdict'],
          properties: {
            reader_takeaway: { type: 'string' },       // the ONE sentence the reader must come away with
            verdict: { type: 'string', enum: ['keep', 'restyle', 'redesign'] },
            archetype: { type: 'string' },              // named entry from figure-design references/archetypes.md
            axis_plan: { type: 'array', items: { type: 'object',
              properties: { axis: { type: 'string' }, window: { type: 'string' }, scale: { type: 'string' }, rationale: { type: 'string' } } } },
            panel_plan: { type: 'array', items: { type: 'object', required: ['panel', 'action'],
              properties: { panel: { type: 'string' }, action: { type: 'string', enum: ['keep', 'merge', 'drop', 'to_si', 'to_table'] }, content: { type: 'string' } } } },
            regen_expectations: { type: 'array', items: { type: 'string' } },  // measurable acceptance checks visual-QA verifies
            caption_implication: { type: ['string', 'null'] },
            proposed_caption: { type: ['string', 'null'] },   // full replacement \caption text (applied at Emit, post-approval)
            tex_structure_patch: { type: ['string', 'null'] }, // to_table / to_si structural .tex change, spelled out
          } },
      } } },
    baseline: { type: 'object',
      properties: { method_colors: { type: 'string' }, font_sizes: { type: 'string' }, conventions: { type: 'string' }, sibling_alignment: { type: 'string' } } },
    inconsistencies: { type: 'array', items: { type: 'object',
      properties: { figure_id: { type: 'string' }, issue: { type: 'string' } } } },
    // traits shared across figures that a research-figure-plotting default-OFF rule says to REMOVE — the
    // anti-laundering channel (a uniformly-shared defect goes HERE, never into baseline.conventions).
    shared_defects: { type: 'array', items: { type: 'object', required: ['trait', 'rule'],
      properties: {
        trait: { type: 'string' },
        rule: { type: 'string' },
        affected_figures: { type: 'array', items: { type: 'string' } },
        scope: { type: 'string', enum: ['all', 'most', 'some'] },
        fix: { type: 'string' },
      } } },
  },
}
const FIGURE_REVISE_SCHEMA = {
  type: 'object', required: ['committed'],
  properties: {
    committed: { type: 'boolean' },
    problem_list: { type: 'array', items: { type: 'string' } },  // round 1: what's wrong now (or the blocker if committed=false)
    fix_plan: { type: 'array', items: { type: 'string' } },      // round 1: what will change, before editing
    changed_script: { type: 'string' },
    regenerated: { type: 'array', items: { type: 'string' } },
    regen_ok: { type: 'boolean' },           // B: true ONLY if regen_cmd ran clean + wrote every output (no broken-script commit)
    hunks: { type: 'array', items: { type: 'object', required: ['rule_tag', 'rationale'],
      properties: { rule_tag: { type: 'string' }, rationale: { type: 'string' } } } },  // rule_tag="rescale" marks a held numeric/scale change
    visual_self_check: { type: 'string' },   // what the reviser saw after rendering
  },
}
const FIGURE_FIDELITY_SCHEMA = {
  type: 'object', required: ['verdict'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'HOLD', 'FAIL'] },   // HOLD = deliberate numeric/scale rescale, needs author approval
    drift_items: { type: 'array', items: { type: 'object',
      properties: { frozen_item: { type: 'string' }, base: { type: 'string' }, revised: { type: 'string' }, why: { type: 'string' } } } },
    // HOLD verdict: each numeric/scale rescale (or off-brief structural change) the author must approve
    needs_approval: { type: 'array', items: { type: 'object',
      properties: { kind: { type: 'string' }, base: { type: 'string' }, revised: { type: 'string' }, why: { type: 'string' }, rationale: { type: 'string' } } } },
    // PASS under a redesign license: each brief-MATCHING structural change (chart type / panel / axis plan),
    // reported so the author sees exactly what the redesign did to the presentation (FYI, non-blocking).
    design_changes: { type: 'array', items: { type: 'object', required: ['what'],
      properties: { what: { type: 'string' }, why_science_preserved: { type: 'string' } } } },
    close_calls: { type: 'array', items: { type: 'object',
      properties: { base: { type: 'string' }, revised: { type: 'string' }, why: { type: 'string' } } } },
  },
}
const FIGURE_QUALITY_SCHEMA = {
  type: 'object', required: ['dimensions_covered', 'flags'],
  properties: {
    dimensions_covered: { type: 'array', items: { type: 'string' } },
    flags: { type: 'array', items: { type: 'object', required: ['severity', 'dimension', 'issue'],
      properties: {
        severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
        disposition: { type: 'string', enum: ['actionable', 'deferred'] },
        defer_reason: { type: 'string' },
        // a default-off decoration the baseline wrongly preserves: un-deferrable + propagated set-wide.
        baseline_conflict: { type: 'boolean' },
        dimension: { type: 'string' }, issue: { type: 'string' }, fix: { type: 'string' } } } },
    annotations_checked: { type: 'array', description: 'EVERY in-plot (transAxes/transData) text/annotation you cropped-and-Read, each with its overlap verdict. Empty ONLY when the script has no in-plot annotation; an empty array while the script does have one is read as "the mandated crop-check was skipped" and blocks convergence.',
      items: { type: 'object', required: ['position', 'overlaps_data'],
        properties: { position: { type: 'string' }, overlaps_data: { type: 'boolean' }, note: { type: 'string' } } } },
    reads_like: { type: 'string', enum: ['publication-ready', 'acceptable', 'rough'] },
  },
}
// The parallel figure_runner's return (spec/figure-loop.md ## Parallel return). assembleFigures rolls these
// into the SAME run-wide arrays the serial runFigure fills; shipped_version 0 = shipped the original (do-no-harm).
const FIGURE_RESULT_SCHEMA = {
  type: 'object', required: ['id', 'shipped_version', 'stop_reason', 'rounds'],
  properties: {
    id: { type: 'string' },
    plot_script: { type: 'string' },
    branch: { type: 'string' },
    shipped_sha: { type: ['string', 'null'] },
    shipped_version: { type: ['integer', 'null'] },   // 0 = shipped the ORIGINAL (do-no-harm); else the best round
    actionable: { type: ['integer', 'null'] },          // the shipped round's actionable visual-flag count (null if original)
    stop_reason: { type: 'string' },                    // clean / light_single_pass / no_improvement / max_rounds / blocked / do_no_harm
    rounds: { type: 'array', items: { type: 'object', required: ['round', 'fidelity_verdict'],
      properties: {
        round: { type: 'integer' },
        sha: { type: 'string' },                          // the round's commit (a HOLD round's sha doubles as its held_sha)
        fidelity_verdict: { type: 'string', enum: ['PASS', 'HOLD', 'FAIL'] },
        actionable: { type: ['integer', 'null'] },        // null == ∞ (reverted / un-shippable round)
        annotations_checked_n: { type: 'integer' },       // count the visual-QA cropped-and-Read (the assemble backstop reads this)
        hunks: { type: 'array', items: { type: 'object',
          properties: { rule_tag: { type: 'string' }, rationale: { type: 'string' } } } },
      } } },
    blockers: { type: 'array', items: { type: ['string', 'object'] } },
    design_changes: { type: 'array', items: { type: 'object' } },       // brief-matching structural changes fidelity PASSed (redesign license)
    needs_approval: { type: 'array', items: { type: 'object' } },       // HOLD rescales the author must approve (each with held_sha)
    fidelity_reverts: { type: 'array', items: { type: 'object' } },     // FAIL rounds reverted for touching the data
    close_calls: { type: 'array', items: { type: 'object' } },
    deferred_flags: { type: 'array', items: { type: 'object' } },       // the shipped round's deliberately-kept flags
    baseline_conflicts: { type: 'array', items: { type: ['string', 'object'] } },
    semantics: { type: 'object' },
  },
}
// The Emit-phase caption/tex-structure applier's return (applyTexChanges). `denied` = edits the token-freeze
// hook refused (they fall back to figure-tex-patches.md); the applier never commits (the orchestrator does).
const TEX_APPLY_SCHEMA = {
  type: 'object', required: ['applied', 'denied'],
  properties: {
    applied: { type: 'array', items: { type: 'object', required: ['id', 'kind'],
      properties: { id: { type: 'string' }, kind: { type: 'string', enum: ['caption', 'structure'] }, file: { type: 'string' } } } },
    denied: { type: 'array', items: { type: 'object', required: ['id', 'why'],
      properties: { id: { type: 'string' }, kind: { type: 'string' }, why: { type: 'string' } } } },
  },
}
