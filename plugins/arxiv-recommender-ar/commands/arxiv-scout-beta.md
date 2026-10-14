---
description: THE arxiv-scout weekly pipeline entry point. Reads workflows/arxiv-scout.js (workflow A, recommend) THEN workflows/arxiv-ideation.js (workflow B, the verified-kill ideation loop) and enacts both phase sequences with subagents.
allowed-tools: Bash, Read, Write, Task
---

End-to-end weekly recommender + ideation pipeline, enacted as TWO
consecutive workflows: **A** (`workflows/arxiv-scout.js` — fetch → rank → judge
gate → papers-only digest/web) then **B**
(`workflows/arxiv-ideation.js` — the verified-kill loop: multi-round generate →
screen → verify (EXECUTED probes) → recheck, death-certificate regeneration,
artifact-gated convergence → digest/web re-render). The phase sequences, every gate condition, and every knob
value live in those two JS files + `config/config.yaml` (all three embedded
under Preconditions below) — that trio is the **single source of truth**. This
file deliberately does NOT restate phase logic, thresholds, or pass/fail rules
(a hand-maintained copy drifts and was already out of sync); it only tells you
HOW to enact each JS construct as a main-agent + subagent stand-in.

**B is independently re-runnable:** it reads only A's on-disk outputs
(`week-<W>-gated-pool.json` + `week-<W>-judge-cache.json` + the papers-only
manifest). To re-run ideation for a week whose pool is still on disk (within
`scout.cache_stale_days` of A), enact workflow B alone; A's own phases are all
resume-cached, so re-enacting A first is also cheap and always safe.

## Preconditions

- Plugin root: !`echo "${CLAUDE_PLUGIN_ROOT:-unknown}"`
- Config present: !`test -f "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" && echo yes || echo no`
- Profile present: !`test -f "${CLAUDE_PROJECT_DIR:-$PWD}/data/profile/profile.json" && echo yes || echo no`
- Active config: !`cat "${CLAUDE_PLUGIN_ROOT}/config/config.yaml"`
- Workflow A definition (recommend): !`cat "${CLAUDE_PLUGIN_ROOT}/workflows/arxiv-scout.js"`
- Workflow B definition (verified-kill ideation loop): !`cat "${CLAUDE_PLUGIN_ROOT}/workflows/arxiv-ideation.js"`
- User input (the raw text after the command; THIS is the JS `args.input` / userInput): `$ARGUMENTS`
- Current ISO week: !`date -u +%G-W%V`

## Workflow

1. If "Config present" is `no`, tell the user: create `config/config.yaml` and set `researcher.google_scholar_url` (or `researcher.s2_author_id`). Stop.

2. If "Profile present" is `no`, the JS workflow runs Phase 0 (profile build)
   automatically — its sub-phase sequence and the Scholar (or legacy website-first) flow live in
   the embedded JS. Run the NL profile-generation step as a **Task subagent** (do NOT
   invoke the `arxiv-profile` skill directly here); the skill's trailing "Then stop."
   ends only that subagent. Phase 0 is the FIRST phase, not the whole task — the moment
   `profile.md` / `profile.json` exist, continue into Phase 1 **in the same turn** (see
   "Continuous execution"). The Phase 0 confirmation gate (0b paper list on the Scholar
   path, 0c identity on the website path) runs in the main agent (see Orchestration rules).

3. Reproduce `${CLAUDE_PLUGIN_ROOT}/workflows/arxiv-scout.js` (workflow A) **and then**
   `${CLAUDE_PLUGIN_ROOT}/workflows/arxiv-ideation.js` (workflow B) — the canonical
   sources of truth for the phase sequences, inlined above via the precondition cats.
   **Bind `$ARGUMENTS` to the JS `args.input` (userInput)** — its meaning (profile-rebuild
   intent, pinned arXiv papers) is parsed entirely by workflow A; do not interpret it here.
   Walk each file's top-level `phase()` calls and gates **in order** and reproduce each one
   continuously, without ending your turn between them (B starts the moment A's return
   value is assembled). Take every gate condition and
   every knob value from the embedded config/JS — never from a restatement in this
   document, and never a hardcoded default. The **Phase → action map** below tells you
   which skill/script each phase maps to; everything the map does not cover (thresholds,
   pass/fail logic, which papers are dropped, coverage/extensibility gating, refine↔judge
   convergence) you read directly from the embedded JS.

4. When all phases finish, surface both outputs:
   - `data/web/<week>-scout.html` — interactive HTML report (primary reading surface;
     each surviving idea shows its plan + the machine-derived Verification Record;
     each paper shows its 死亡名单 with kill evidence)
   - `data/digests/<week>-scout.md` — markdown digest with survivors' seeds ready to
     paste into `/research <seed>` and the per-paper verified-kill history

## Orchestration rules (HOW to act as a stand-in — these have no JS equivalent)

- **Continuous execution (no mid-pipeline stop).** Run the entire pipeline in ONE
  continuous turn. The ONLY legitimate interactive pause is the Phase 0 confirmation
  gate (`AskUserQuestion`): the **Phase 0b paper-list gate** on the Scholar path, or the
  **Phase 0c identity gate** on the website path. Completing Phase 0 (profile.md / profile.json written)
  is **NOT** a stopping point — immediately proceed to Phase 1. Do not emit a
  wrap-up / recap, and do not end your turn, until the step-4 outputs
  (`data/web/<week>-scout.html` + `data/digests/<week>-scout.md`) exist on disk.
  - **Yielding to a harness-tracked background task is NOT a mid-pipeline stop.**
    When you fire a long mechanical command with `run_in_background: true` (e.g.
    Phase 2 `prefetch.py`), handing control back so the process can run while the
    harness re-invokes you on exit is the *sanctioned* way to wait — it is not
    "ending the turn." When fired, do not emit a recap; just resume the pipeline
    the moment you are re-invoked with the completed shell result.
- **Phase 0b paper-list gate** (when `google_scholar_url` is set and `data/profile/paper_candidates.json` has
  any entry without a decision — Phase 0a may have REUSED a list written for this build):
  Read `data/profile/paper_candidates.md` (and the JSON beside it). In one `AskUserQuestion`,
  show the owner: the Scholar profile name, the row count, how many rows were resolved to
  arXiv (with abstracts) vs title-only, the table's path, and — by title — every row you
  suspect is NOT the researcher's or is a large collaboration (a `peripheral` candidate).
  Options must include:
  - "我已在 paper_candidates.json 里填好每一条的 decision"
  - "除了你列出的几条,其余全部标为 self(是本人)" — only when you listed rows; the owner
    says which listed rows are `not` / `peripheral` via "Other"
  - "停下,我自己改完再继续"
  Write exactly the decisions the owner gave into `paper_candidates.json` (never invent a
  `not` or `peripheral`), then continue with Phase 0c (`build_profile_papers.py --from-list`).
  **This gate MUST run in the main agent, never in a subagent.**
- **Phase 0c identity gate** (website path: when `personal_website` is set, no
  `google_scholar_url`, and Phase 0b just ran):
  After `verify_s2_identity.py` writes `data/profile/identity_check.json`, YOU (the
  main agent) must read it. If `needs_confirmation: true`, call `AskUserQuestion`
  presenting: the candidate researcher name/ID, their S2 paper count vs website count,
  and the list of papers on S2 but not on the website. Options must include:
  - "是,这些都是我的论文(使用完整 S2 主页,共 N 篇)"
  - "是,合并使用(S2 完整档案 N 篇 + 网站独有 M 篇)"  ← 推荐:当 website_only_papers 非空时最优选择
  - "不是,请只使用我网站上的论文(M 篇)"
  When presenting the options, replace N with `s2_total_count` and M with the count of
  `website_only_papers`. Only show the merge option when `website_only_papers` is non-empty
  (which is always true when `needs_confirmation: true` unless only `s2_only_papers` differ).
  Based on the answer, write `data/profile/identity_decision.json`:
  - S2 only → `{"confirmed_author_id": "<id>", "use_s2_full": true}`
  - Merged   → `{"confirmed_author_id": "<id>", "use_merged": true}`
  - Website  → `{"confirmed_author_id": null, "use_website_only": true}`
  Then continue with Phase 0d (`build_profile_papers.py`).
  If `needs_confirmation: false` (cached decision or perfect match), skip the gate.
  **This gate MUST run in the main agent, never in a subagent.**
- **agent() → Task; parallel() → one message, many Task calls.** Each JS `agent()`
  call becomes one `Task` subagent. A JS `parallel([...])` becomes a single message
  with multiple `Task` calls. Where the JS shares one prompt prefix across a parallel
  batch (e.g. a shared instruction header across a fan-out), make that prefix
  byte-identical across the subagents so the prefix cache hits.
- **Skill loading inside leaves.** A leaf that carries the `Skill` tool must INVOKE
  the skill instead of Reading its SKILL.md — same-plugin names
  (`arxiv-recommender-ar:<name>`) are the PROVEN path; a cross-plugin name is invoked
  the same way but each such prompt must also carry an explicit Read-the-SKILL.md
  fallback in case the cross-plugin resolve fails (fall back, don't improvise) —
  Skill-tool loading evaluates the `` !`cfgval` `` injection spans into live config
  values (verified 2026-07-05: evaluation runs inside subagents too, and a broken
  span fails the load LOUDLY instead of showing stale text). Only a leaf WITHOUT the
  Skill tool falls back to Reading the SKILL.md — and must then execute each
  `` !`…` `` span's command itself (they are plain `bin/cfgval.sh` calls) to obtain
  the values before acting. Caveat: Skill-tool content is snapshotted at plugin
  load — after editing a SKILL.md, reload the plugin (or start a fresh session)
  before relying on the invoked copy.
- **Background prefetch (Phase 2).** `prefetch.py` is long-running mechanical work
  (local CPU SPECTER2 over the full pool can exceed the 10-minute foreground `Bash`
  timeout). Fire it with `run_in_background: true`; do NOT poll it with `sleep` /
  `Monitor` — the detached process runs across turns and the harness re-invokes you
  when it exits; that wake-up IS your signal to continue. (Phase 1 `oai_ingest.py` is
  network-bounded and normally fits the foreground timeout; background it only if a
  run is observed to exceed it.) When re-invoked: confirm the shell exited 0 (if it
  failed, surface the error and stop — do not proceed on a failed score), confirm
  `data/cache/week-<W>-prefetched.json` exists, then continue into Phase 3.
- **Web report step.** Run `bash ${CLAUDE_PLUGIN_ROOT}/bin/run_py.sh ${CLAUDE_PLUGIN_ROOT}/scripts/lib/scout_web.py --week <W> --no-open` directly via `Bash` in the main agent — do NOT spawn a subagent (it is purely mechanical: reads JSON → renders HTML; subagent overhead is wasted latency).
- **Completion.** Do not end your turn until all JS-declared outputs of BOTH workflows exist
  on disk (the per-week cache JSONs incl. `week-<W>-gated-pool.json` + `week-<W>-ideation-ledger.json`,
  the verification bundles under `data/ideations/<W>/bundles/`, each converged paper's refined
  markdown with its `## Verified Claim` + `## Verification Record` blocks, the digest, and the web
  report) — the authoritative list is each JS's `return` + its `writeFileSync` calls, not a copy here.
- **V0 runs INSIDE `ideation_ledger.py apply-verify`, never as an agent and never hand-branched.**
  V0 (`verify_bundle.py`) is a mechanical zero-token re-execution; the driver runs it per candidate
  and returns the verified / one-time-mechanical-bounce / kill decision (+ any `bounce_items`). Never
  spawn a subagent to "do" V0, never hand-run or hand-branch it, and never skip it — call `apply-verify`
  and act on its output.
- **The ideation candidate state machine is CODE, not memory.** In workflow B you NEVER track which
  candidate is generated/screened/verifying/converged/killed, never tally promote/kill/bounce/converge
  yourself, and never hand-write the ledger. Ask `ideation_ledger.py worklist` what to spawn, AWAIT the
  batch in-turn (one message, many Task calls — NO detached/background/placeholder "waiter" spawns; you
  are a headless L1 with no self-rewake), and pipe the awaited returns straight to `apply-*`. The driver
  is the SINGLE writer of `week-<W>-ideation-ledger.json`.

## Phase → action map

Each row maps a JS `phase()` / gate to the tool calls that enact it. Gate
conditions and caps shown here are live config injections; everything else
(thresholds, verdict→action rules) is read from the embedded JS.

| JS phase (in `arxiv-scout.js` order) | Enact as |
|---|---|
| Phase 0 profile (when missing/requested) | Fires when the owner's profile is missing or `args.input` requests a rebuild ("update my profile"): `arxiv-profile` skill via a Task subagent (Phase 0e); the Phase 0c identity gate runs in the main agent (see Orchestration rules) |
| Phase 1 Fetch | `oai_ingest.py` via `Bash` in the main agent; confirm `candidates.json` exists |
| Phase 1.5 pinned-paper injection | handled entirely in the JS workflow (`fetch_pinned_papers.py` + `--pinned-ids` to `prefetch.py`); no extra action here |
| Phase 2 Score | `prefetch.py` with `--top-k` !`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" scout.prefetch_top_k`, fired `run_in_background` (see Orchestration rules); confirm `prefetched.json` exists |
| Phase 3 Final Rank | **3a (the selection, no Task):** Bash `scripts/lib/thread_seed.py order --week <W>` — it partitions the delivered reading list (the fused order's first `TOP_K`) by OWNING thread: a paper belongs to the thread that ranks it highest. Deterministic; there is no ranking call and nothing to enact by judgement. The seeds themselves are chosen in Phase 3.6, because a seed is the first paper that PASSES the gate. **3c (the rationales):** `arxiv-rerank` skill (Task) over exactly final.json's `top` in that order (+ pinned appended); writes `week-<W>-rerank.json` (consumed by the gate + the /weekly-papers pipeline). Then verify, deterministically, that the returned `top_papers` ids equal final.json's `top` ids (+ pinned) in order — the JS throws otherwise. No shared field-view/landscape block is built — ideation is per-paper. |
| Phase 3.6 Judge Gate | **The seed walk.** Each thread takes the first paper it owns that passes the gate. Round `r`: every seedless thread nominates its `r`-th owned paper (ownership is a partition, so two threads can never nominate the same paper); fan out the gate skills via Task in ONE in-turn-awaited `parallel()` barrier over THOSE nominations only, then assign — a pass seeds the thread, a rejection advances it to its next paper. Stop when no thread can nominate. A thread whose papers are all rejected ends with NO seed: log the vacancy, never fill it. The gate skills: `arxiv-claim-judge` (Stage 1) and, for `repo_active` papers, `arxiv-repo-judge` (Stage 2, fed the claim list). Each paper's verdict MUST be persisted to `week-<W>-judge-cache.json` exactly as `acceptCandidate`/`persistJudgeEntry` does (replay a cached verdict instead of re-judging; side effects included). **Then compute the survivors DETERMINISTICALLY — do NOT tally the judge returns in your head. That in-memory tally is the exact fabrication vector this step exists to kill (a hand-enacting orchestrator once lost track of the returns and invented ~10 verdicts).** Reproduce the JS: write `week-<W>-seeds.json` (`[{arxiv_id, thread}]` in served order), run Bash `scripts/lib/thread_seed.py final --week <W> --seeds <path>` to emit `final.json`, then write the `gate-input` JSON (`{queue, pinned, ext_pool_ordered, n}` — `queue` = the seeds) and run via **Bash** `compute_gated_pool.py --week <W> --gate-input <cacheDir>/week-<W>-gate-input.json` — it reads the judge CACHE, applies every keep/drop/penalize/empty-pool-fail-safe rule, **FAIL-CLOSES (exit 3) if any queued paper has no committed verdict** (surface it and actually run that judge; never paper over it), and writes `week-<W>-gated-pool.json`. Pinned papers are force-included and never judged; the JS+config own all thresholds; never empty the digest. (See **Phase 4 paper hard cap** in Invariants below.) |
| Generate — **workflow B** (the candidate STATE MACHINE is owned by `scripts/ideation_ledger.py`, NOT by you) | ONCE before round 1: Bash `ideation_ledger.py init --week <W> --gated-pool <cacheDir>/week-<W>-gated-pool.json`. Then per round ask the driver what to spawn — Bash `ideation_ledger.py worklist --round R --stage generate` → for each returned item spawn `arxiv-generate` (round 1: all; rounds 2+: the item carries the paper's `graveyard` for regeneration; `buildGeneratePrompt` owns the payload), **AWAIT the whole batch in-turn**, write the returns to a file, then Bash `ideation_ledger.py apply-generate --round R --result <file>` (it registers candidates from each idea file and self-DROPs honest-exhaustion papers). NEVER track candidate state or ledger it yourself. |
| Screen — **workflow B** | Bash `worklist --round R --stage screen` → ONE `arxiv-screen` leaf per listed paper (similar-merge, replayable-S2 prior-art, `asset_listing.sh`, retread-vs-graveyard — the item carries the graveyard), AWAIT in-turn, then Bash `apply-screen --round R --result <file>`. The DRIVER mints death certificates and owns every kill/merge/rank transition. |
| Verify + V0 — **workflow B** | Bash `worklist --round R --stage verify` PROMOTES inside the driver (top `verify_fanout` → verify, the rest → dormant) and returns the candidates to verify → one adversarial `arxiv-verify` leaf each (implements + EXECUTES probes via `probe_run.sh`, composes bundle.json via `bundle_io.py`), AWAIT in-turn, then Bash `apply-verify --round R --result <file>`. **V0 (`verify_bundle.py`) runs INSIDE apply-verify** — the driver decides verified / one-time-mechanical-bounce / kill; do NOT run or branch V0 yourself. If apply-verify returns `bounce_items`, re-spawn `arxiv-verify` for exactly those (content frozen, with the item's `bounce_note`) and Bash `apply-verify … --bounce`. |
| Recheck + Refute — **workflow B** | Bash `worklist --round R --stage recheck` → per verified candidate TWO parallel leaves: `arxiv-recheck` (model from !`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" scout.phases.recheck.model`; theoretical/both candidates use !`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" scout.phases.recheck_theory.model`) and `arxiv-refute` (the ONLY WebSearch leaf). AWAIT the whole flat batch in-turn, pair the two returns per candidate `{arxiv_id,key,recheck,refute}`, then Bash `apply-recheck --round R --result <file>`, then Bash `settle --round R`. The DRIVER owns the scooped / significance-floor (paper_worthy REQUIRES a non-null confrontation) / artifact-recheck kill rules and the converge+settle decision — never your own reading. |
| Plan + Finalize — **workflow B** | After the round loop: Bash `ideation_ledger.py finalize --week <W>` (round cap → exhausted_budget + the ideation manifest). One `arxiv-plan` leaf per SURVIVOR — every converged candidate, whatever its paper settled as → `data/ideations/<W>/refined/<arxiv_id>-idea<N>.md` (N = its place among the paper's converged candidates, ledger order). Then the JS (you, deterministically — no agent) runs the `## Verified Claim` equality check and inserts the machine-derived `## Verification Record` before `## /research Seed`, reading the **driver-written** `week-<W>-ideation-ledger.json` (the driver persists it after EVERY subcommand — the crash-resume boundary; never hand-write it). Owner pruning (`week-<W>-quality-gate-decision.json`) is honored by the driver's promote step. |

## Invariants (must hold)

- **This command is a PURE ORCHESTRATOR.** It NEVER uses the `Skill` tool directly.
- Do NOT rank or select inline: the seeds come only from `thread_seed.py`'s partition plus the gate's verdicts; `arxiv-rerank` writes rationales for that fixed set and must not be skipped or replaced. (`rerank_llm.py`'s A0/G1/TOP units are retired from production and kept only because `report-v2/ablation` reproduces the evaluated reranking arms through them.)
- Do NOT generate research-idea seeds in Phase 3 — ideation is Phase 4 only.
- Do NOT call any external LLM API as the reranker.
- **Phase 4 paper hard cap.** Phase 4 receives at most the JS's `top_n_papers` survivors (the judge
  gate enforces it) — never ideate all reranked papers; that skips the gate entirely. The count is owned
  by the JS; do not re-derive it here. **On RESUME,** the survivor set is persisted to
  `data/cache/week-<W>-gated-pool.json` (the gate OUTPUT, ≤ `top_n_papers`) — read THAT to learn which
  papers to ideate. Never source the survivor list from `week-<W>-seeds.json` (the scratch handoff written
  before the rationales); mistaking a scratch file for the gate output ideates the whole
  pool and bypasses the cap.
