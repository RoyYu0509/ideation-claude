# RUNBOOK — running your first auto-research pipeline

`auto-research` carries ONE idea from ideation to a rigorous, reviewer-hardened paper draft,
end to end, inside one interactive Claude Code session — you pick ONE seed at one gate (its venue + your
refining notes) and it runs to ship-or-abandon. To try another idea, re-run `/auto-research`. The pipeline
has completed real end-to-end runs (first: cp4pinn, 2026-06); the tests in `tests/` guard the scaffolding.
This is how you start.

> Architecture in one line: a thin L0 state machine (`spec/research.js`, reproduced by
> `/auto-research`) spawns L1 subagent-orchestrators that reproduce the vendored arxiv-recommender
> (ideation) and paper-polishing (review) specs; B1 (experiment+drafting) is generic goal-driven
> orchestration under the auto-research-owned `RESEARCH-PROTOCOL.md` (`assets/`, copied per paper).

## 0. One-time setup

1. **Bootstrap the vendored ideation venv** (deferred from the build — it pulls multi-GB ML deps). From the repo root:
   ```bash
   bash plugins/arxiv-recommender-ar/bin/setup_venv.sh      # idempotent; installs torch/SPECTER2 etc.
   ```
   The research profile lives under the run folder's `data/profile/` (per-instance data root
   `AR_DATA_ROOT`/`CLAUDE_PROJECT_DIR`/cwd; the plugin's legacy vendored `data/` was archived
   2026-07-05). A fresh folder first gets the owner-only identity card (whose Google Scholar profile, which
   name forms — see §9); Stage A then builds the profile once, via an owner-only paper-list card. Once
   `profile.json` exists, later runs skip both. To rebuild it later, re-run with "update my profile" (the
   trigger is English-only; see that repo's CLAUDE.md).
2. **LaTeX toolchain** (for the review Comprehend phase + final compile): you need `pdflatex` + `bibtex`
   (TeX Live). Verified present on this machine during the build. Without it, `render_pdf.sh` falls back
   to reading `.tex` (degraded, non-fatal).
3. **Open a session IN the repo so the vendored plugins load.** Plugin enablement is read at session
   start, so:
   ```bash
   cd ~/auto-research    # (or a per-instance runtime dir whose settings point at this marketplace)
   claude                 # a FRESH session here; or in an existing session run /reload-plugins
   ```
   Then confirm the plugins loaded (this is the LIVE half of smoke test T5): the skill registry should
   show `paper-polish-ar:*` and `arxiv-recommender-ar:*`. If they are missing, run `/reload-plugins` or
   restart; if it persists, check the three enablement layers (user/project/local `enabledPlugins`) —
   (the most-specific layer wins
   per key).
4. **auto-research ships its OWN skill** — `skills/experiment-engineering/` (hardware-probe +
   bottleneck-first GPU black-magic + OOM discipline for the B1 experiment_worker; deep detail in its
   `reference/`). It is auto-discovered from the `skills/` dir (same as `commands/`), and — like the phase
   plugins under `plugins/` — its source IS this repo, so editing it here takes effect directly. After adding/editing
   it you MUST reload for the running session to see it: `/reload-plugins` (or restart). Confirm
   `experiment-engineering` shows in the skill registry; the B1 experiment_worker retrieves it by BARE NAME
   (see `config.yaml → experiment_engineering.skills`), so if the registry doesn't list it, the worker
   silently won't load it (verify once with a real B1 run that the worker probes the machine before scaling).

## 1. Re-confirm the platform premises (recommended after any Claude Code upgrade)

```bash
bash tests/test_loop_gate.sh && bash tests/t2_hook_logic.sh && \
bash tests/t3_detach_rewake.sh && bash tests/t4_decision_roundtrip.sh && bash tests/t5_vendored_load.sh
```
All should be GREEN. Then re-run the LIVE checks per `tests/TESTS.md`: T1 (nested spawn), T2 (freeze
hook denies a frozen-number edit at depth L2 — the go/no-go; if it does NOT, STOP, see HANDOFF §13),
and T3's full end-turn→re-wake roundtrip once before your first long experiment.

## 2. Start a run

```
/auto-research
```
No arguments — it infers what to do from `state/pipeline-state.json`:

1. **Startup card** (AskUserQuestion): new run / resume pending gate / resume detached run / reconfigure.
2. **Stage A — ideation** runs the vendored scout pipeline. Heavy prefetch runs in the background; do
   not be surprised by a pause.
3. **GATE 1** (decision file + live card): you get the HTML report path + a per-seed table
   (significance/rigor, title, hypothesis) and the prepared venues. **Pick ONE idea — keep or skip each,
   optionally attaching a refining note and a `venue: <rel>` override** (else the default venue applies).
   The run pursues exactly ONE idea: if you Keep several, only the FIRST (in order) runs and the rest are
   ignored; the card tells you so. Answer in chat and/or by editing `state/decisions/DECISIONS-PENDING.md`
   (chat wins on conflict). To try a different idea, re-run `/auto-research` (a fresh ideation gate).
4. **For the picked idea**: **Seed → HANDOFF**: the seed (+ your note) becomes `runs/<slug>/HANDOFF.md` and
   the workspace is created (`runs/<slug>/{code,paper,RESEARCH-PROTOCOL.md,RESEARCH_LOG.md,...}`).
5. **LOOP (≤ `max_loop_rounds`, default 2)**: B1 experiment+drafting (milestones ENV_READY → … →
   drafting) → B2 adversarial review → B3 deterministic exit gate. Items needing NEW content become
   handoff items that feed the next round's B1. `min_loop_rounds` (default 1) is an ADVISORY soft floor,
   NOT a hard minimum: a clean EXIT below the floor is still allowed (the loop is never forced to continue),
   but `bin/loop_gate.sh` FLAGS it so the FINAL-REPORT records "converged early at round N (< soft floor)".
   An UNCONVERGED loop CONTINUEs to the cap. A clean **EXIT** auto-ships: the run routes into the terminal
   chain, the global `.polish/` is sealed, and the run ends. An **EXIT_AT_CAP** opens the unified terminal gate
   (Ship = hand the spec back [default] / Abandon / Rescue one more round), listing every unresolved
   reject/major item as what remains open.

   **What the loop is optimizing.** Each round re-authors `HANDOFF.md` — the research SPECIFICATION — toward
   more scientific AMBITION (the §4c contract + the amplifier) and more RIGOR (the work-order hardener + the
   verifier + the scale contract), and snapshots the result to `SPEC/SPEC-v<N>.md` with a mechanical row in
   `SPEC/spec-ledger.json` (`bin/spec_ledger.sh`). That version chain is the run's own record of whether the
   loop improved the spec or merely narrowed it.
6. **Terminal chain → Ship**: the loop EXIT/EXIT_AT_CAP routes to **verify_final** (the one independent
   science verify) and then **spec_freeze (spec 定稿)** — both MANDATORY, no toggles. spec_freeze distils the
   settled work order into `SPEC-FINAL.md` (the delivered research specification), writes `SPEC-EVOLUTION.md`
   (the per-round ambition/rigor ledger, including an honest closing verdict on whether the spec improved),
   and audits every number/criterion back to `AUDITED-VALUES.json` / `EXPERIMENTS/*/result.md`
   (`SPEC-FREEZE-REPORT.md`). The ship artifacts are `runs/<slug>/SPEC-FINAL.md` + `SPEC-EVOLUTION.md` +
   `SPEC/` (the version chain), the evidence under `EXPERIMENTS/`, `paper/review-report.md`, and
   `FINAL-REPORT.md` (timeline, artifacts, every policy-resolved decision, unresolved items, usage —
   including any "converged early at round N (< soft floor)" note). A viability-kill or a terminal Abandon
   writes `FINAL-REPORT-killed.md` instead.

   > The post-loop WRITING ENGINE (freeze_findings → story → write → figures → edit → freeze) and the
   > standalone `/rewrite` were retired on 2026-08-30 with the spec re-aim; both live in `inactive/`.
   > `/polish` and `/polish-figures` remain available as STANDALONE paper-polish commands.

## 3. During a run — what you'll be asked, and what runs unattended

- **You are asked** at the startup card, at **GATE 1** (always: every verified surviving idea is listed — one
  plan per survivor — and you pick ONE; name just the one you want, the rest count as Skip), and at the
  research-DIRECTION call — with the shipped default config, nowhere else. `gates.owner_kinds: [direction]`
  (config.yaml, 2026-09-12; `terminal_gate` moved out 2026-09-23) keeps one gate with you even though
  `gates.adjudicator: agent`: the per-round **direction card** after every loop round (approve / revise /
  abandon, plus sending the amplifier or research-rescue at a direction you write in NOTES; that round's
  viability call is folded into it). **The loop's exit is a rule, not a card** (`gates.default_kinds:
  [terminal_gate]`): only a dead central claim abandons; an idea the loop did not kill is handed back to you as
  the spec (clean or cap exit as-is, an over-claim
  narrowed) — put `terminal_gate` back in `owner_kinds` to decide the exit yourself. Every other gate — phase-0, literature, audit-artifact, failure Resume, and the author-only
  review escalations — is answered
  in-turn by a fresh cold-read adjudicator leaf that produced none of the work it judges. Each still writes
  its decision file and archives it to `DECISIONS-RESOLVED-<n>.md` with the judge's rationale and an
  `[adjudicated by agent, attempt <n>]` marker, so the audit trail is intact. Set `gates.adjudicator: owner`
  to answer every gate yourself; set `gates.owner_kinds: []` to be asked nothing after GATE 1.
- **Runs unattended**: the whole review panel → Area Chair → revision → experiment verify-runs (the spec
  decides these itself); `updates_existing` experiments are auto-run and provenance-audited;
  `new_exhibit` experiments are exported to a handoff and fed back into B1 (the loop's main path).
- **Long experiments** (hours+) auto-detach and the session ends its turn; the asyncRewake Stop hook
  re-wakes it for free when the job finishes. **Do not poll** and do not close the terminal if you want
  auto-resume; if you do close it, just re-run `/auto-research` to resume from disk.

## 4. Unattended runs & permissions

`.claude/settings.json` pre-authorizes git / python / latex / pytest / the known repo+vendored scripts /
common read-only commands (HANDOFF fact #7). It deliberately does NOT blanket-allow `bash *`, `rm`, or
`mv` — experiment code that needs those will prompt. For a truly hands-off multi-hour run, either:
- broaden the allowlist in `.claude/settings.json` to the commands your experiments actually use, or
- launch the session in a permission mode you are comfortable with (your global `skipAutoPermissionPrompt`
  already reduces prompts).
Tune to your risk tolerance — the pipeline runs code it writes, by design.

## 5. Resume, crash recovery, reconfigure

- **Resume after closing/crashing**: re-run `/auto-research` in the repo — it reads
  `state/pipeline-state.json` and continues (re-presents a pending gate, resumes a detached run, or
  continues the loop). State is written after every transition.
- **Two distinct resume layers** (do not conflate them): (1) **in-session asyncRewake** — a LIVE detached PID
  the Stop hook OS-waits at zero token cost and re-arms; this is the long-experiment zero-token wait. It is an
  ACCELERATOR, not the guarantee — it requires the registered asyncRewake Stop hook (`rewake-when-done.sh`) to be
  armed at session start. The ALWAYS-AVAILABLE correctness path is the disk+PID reconcile on a fresh
  `/auto-research` (`resumeDetached`): if the hook is unarmed, a detached run simply STOPS cleanly and resumes
  when the owner re-runs `/auto-research`. (2) **cross-session git-checkpoint resume (RM2)** — for a COLD restart (a fresh session, every
  detached PID dead): coordinated-revert the in-flight paper's three repos to the last durable git checkpoint
  and rerun the lost unit DETACHED through the crash-surface gate, never blind foreground. RM2 is BUILT but
  gated behind `rm2.git_revert_resume` (default **off**) — until it passes live crash-recovery + asyncRewake-
  regression testing the proven disk+PID self-heal (a fresh `/auto-research` reconciling detached records from
  disk) is the cross-session path. With the switch off, resume behaves exactly as before.
- **A pending gate** is the source of truth in `state/decisions/DECISIONS-PENDING.md`; answer it and the
  run continues.
- **Reconfigure — the easy way (`key-config.yaml`)**: the high-leverage runtime knobs (loop rounds,
  per-round reviewer count, citation floors, finishing toggles, scout gates, and every role's model +
  ultrathink) are scattered across THREE configs in three inline-map dialects. `key-config.yaml` (repo root)
  is ONE phase-ordered control panel for all of them. Edit it, then run `bash bin/apply_key_config.sh`
  (`--check` previews) — it patches the values back into the three runtime configs IN PLACE, preserving every
  comment, fail-loud on a missing path. The runtime configs stay the SSOT (so standalone `/review` `/polish`
  `/arxiv-scout-beta` are unaffected); it is NOT auto-run by `/auto-research`, so apply after each edit.
- **Reconfigure — directly**: anything `key-config.yaml` does not surface (io timeouts, embedding/RRF weights,
  S2 rate limits) lives in `config/config.yaml` and the two plugin configs. `config/config.yaml` is the SSOT —
  a missing key crashes with its name; never hardcode a value it defines.

## 6. Hook registration (advanced)

The freeze (anti-fabrication) PreToolUse hook + the asyncRewake Stop hook come from the enabled
`paper-polish-ar` plugin's own `hooks/hooks.json` — its commands resolve through `${CLAUDE_PLUGIN_ROOT}`,
so they are fully self-contained (the path proven at depth L2 by T2 / re-wake by T3). If
you prefer a project-settings registration, add a `hooks` block to `.claude/settings.json` pointing at
`plugins/paper-polish-ar/hooks/{check-fidelity.sh, rewake-when-done.sh}` AND empty the plugin's
`plugins/paper-polish-ar/hooks/hooks.json` to `{"hooks":{}}` so the asyncRewake Stop hook does not
double-fire. Either way, a fresh session is required for hook changes (hooks snapshot at session start).

## 7. Self-contained guarantee

This is a **standalone git repo with no external dependency**. Everything a run needs lives under it; the
phase plugins under `plugins/` ARE the source of truth and are yours to modify in place. There is no
external `~/arxiv-recommender` / `~/paper-polishing` to sync from, and nothing outside the repo is read or
touched at run time.

## 8. Attributing / debugging a run (trace + event log)

Every run records a full, GC-proof trace and a semantic event stream so a post-mortem is one command, not
an archaeology dig across native jsonl + git + mtimes. Three pieces, all pure side-channels (none is read
back by control flow, so they cannot change a gate/loop/resume decision):

- `state/run-events.jsonl` — append-only L0 event stream (`run_start` / `agent_spawn` / `agent_return` /
  `envelope_invalid` / `verdict` / `gate_open`|`gate_answer` / `gate_input_derived` / `auto_decision` /
  `orphan_stop_scan` / `milestone_done` / `hook_unarmed` / `long_run_fired` / `detached_*` / `rewake` /
  `enter_post_freeze` / `concern_snapshot_written` / `finishing_mode_mismatch` / `finishing_incomplete` /
  `ship` / `edit`; plus the forward-contract `checkpoint_committed` /
  `ledger_item_opened`|`ledger_item_closed`|`ledger_item_reopened`). Each line carries `run_id` +
  `paper`/`round` + (for agents) `agent_id` — the JOIN KEY to the native transcript.
- `runs/_trace/<run_id>/<session>/` — a TRUE COPY of the full-depth native trace (the L0 `<session>.jsonl`
  + every `subagents/agent-<id>.jsonl` for L1/L2/… + `tool-results/`), snapshotted at each round close and
  each ship. Survives the 30-day native GC (`cleanupPeriodDays`). `runs/` is gitignored — never committed.
- `state/sessions.jsonl` — which native sessions this run touched (a run may span several across resumes).

Read it with `bin/run_report.py` (read-only, python3 stdlib only):

```bash
python3 bin/run_report.py timeline             # the run's semantic events, real UTC
python3 bin/run_report.py tree                 # the rebuilt L0→L1→L2 agent tree + per-node stats + role tags
python3 bin/run_report.py agent <id>           # ONE agent's full per-tool action trace ("what did that L2 do?")
python3 bin/run_report.py attribute "R=0.98"   # which agent/transcript emitted a number/string/regex
python3 bin/run_report.py health               # auto red/green flags: RC-1/2/3/4/6/9 + the log→envelope seam
# forensics on a PAST run/session that predates this stream (reads native jsonl directly):
python3 bin/run_report.py tree       --session <session-uuid>
python3 bin/run_report.py agent <id> --session <session-uuid>
```

`health` is the first thing to run after a finish: it turns the manual reconstructions of the first-run
diagnosis into assertions — e.g. a round with a verdict but a `review_orchestrator` that spawned 0
panelists → RC-2; a milestone marked done with no provenance commit → RC-9; a disk-derived gate mismatch
→ RC-4; an `envelope_invalid` or `hook_unarmed` event → RC-3 / RC-6.

**Precise session anchoring is now AUTO-provisioned (2026-07-05).** A run spans many native sessions; a
terminal-reopen resume is a NEW session uuid with no native link back, and the L0-enacted
`bin/session_anchor.sh --self` (heuristic, newest project jsonl) only reliably anchors session 1 — so the old
setup left sessions 2..N (their whole subagent trees) out of `state/sessions.jsonl` → out of `runs/_trace/`.
The airtight fix is now wired for you: at bootstrap, `main()` calls `provisionInstance()` = `bin/provision_instance.sh`,
which idempotently writes a `SessionStart` hook → `bin/session_anchor.sh` into `<DATA_ROOT>/.claude/settings.local.json`
(the per-instance data folder, merged so it never clobbers owner keys). The HARNESS then fires that hook once per
session start — including every reopen — anchoring it regardless of L0 enactment; `--self` still covers session 1
(the hook cannot fire for the session that writes it). A fresh session is required for the hook to take effect
(hooks snapshot at session start), so it arms the resumes, not the session that provisions it. The deterministic
top-level `agent_spawn` stream (`src:"hook"`) is likewise written by the `spawn_guard` PreToolUse hook, so the
ledger no longer depends on L0 re-enacting `logEvent` on a resume fast-path.

## 9. Running multiple INDEPENDENT instances (separate folders, separate researchers)

The plugin separates **CODE from DATA**. The CODE is this monorepo (`CLAUDE_PLUGIN_ROOT`): shared,
read-only, loaded for any session via the global `~/.claude/settings.json` marketplace entry. The DATA of
one run — researcher profile, ranking cache, ideations, `state/`, `runs/`, decisions, paper drafts — lives
under the **folder you launch from** (`CLAUDE_PROJECT_DIR`, the cwd). So **one external folder = one
independent instance**: run as many side by side as you like, each with its own researcher, all off the one
shared plugin. Each instance researches ONE idea per `/auto-research` run (re-run to do another).

```bash
# one folder = one researcher; run several side by side, each in its own terminal
mkdir -p ~/research/alice && cd ~/research/alice && claude      # then type: /auto-research
mkdir -p ~/research/bob   && cd ~/research/bob   && claude      # then type: /auto-research
```

- **`/auto-research` asks who the folder runs for.** On the first new run in a folder with no
  `researcher.json`, an owner-only identity card asks for the researcher's Google Scholar profile URL (the
  profile is built from it) and the name forms they publish under on arXiv (their own papers are dropped from
  the pool) — or "use the shared default researcher". Stage A then reads Scholar ONCE and an owner-only
  paper-list card asks which rows are the researcher's ("all others are mine" + name the exceptions) before
  the profile is built. The gate adjudicator never answers either card.
- Scripted alternative (skips the identity card): `bin/ar-init.sh <folder> --scholar <url> --aliases "A; B"`.
- Each instance writes `researcher.json` + `data/profile/` + `data/cache/` + `state/` + `runs/` under its
  OWN folder; the two never collide and the plugin dir is never written to. Confirm with
  `git -C <monorepo> status` staying clean.
- `researcher.json` only sets the **identity** (Scholar URL / website / s2-id / aliases); all other knobs come
  from the shared `config/config.yaml`, and an instance that has one inherits NO identity from it. No
  `researcher.json` (e.g. the monorepo itself) ⇒ the shared (owner) default identity.
- Running `/auto-research` **from the monorepo itself** still works exactly as before — there `cwd ==
  plugin`, so the data lands in the monorepo (legacy/dev behavior, fully backward-compatible).
- Each instance gets its own `state/pipeline-state.json`, so resume / crash-recovery / the asyncRewake
  long-experiment Stop hook all operate per-instance with no cross-talk. `ar-init.sh` is idempotent — safe
  to re-run on an existing folder (it only ensures the dirs and, if flags are given, rewrites the identity).


## 10. /learn — retro a finished run (the learning half-loop)

After a run reaches `stage:done` (or for any PAST run), in the SAME instance folder:

```
/learn                      # retro the run in state/pipeline-state.json
/learn <run-id-prefix>      # or a paper slug under runs/, or a workspace path — retro a past run
```

What happens: a mechanical manifest maps every artifact to its component (+ which code version ACTUALLY
ran, cache vs source), read-only reviewers fan out (6 component groups + science/economics/enactment
lines), every serious claim is adversarially re-verified, then you get ONE self-contained brief in the
session and ratify proposals theme-by-theme (each card also written to
`state/learning/<run_id>/decisions/DECISIONS-PENDING.md` — isolated from pipeline gates). Accepted
proposals land in the dossier (`<repo>/dev/learning/NN-run-retro-*.md`, the fix spec for a separate
session) and the hypothesis tracker (`dev/learning/hypotheses.json`) — the NEXT `/learn` opens by
checking whether they actually helped. /learn never edits the pipeline, never commits, and refuses to
start while a pipeline gate is pending. Knobs: `key-config.yaml` 阶段⑥ / `config/config.yaml
learning:`. Interrupted? Just re-run `/learn` — `state/learning/<run_id>/learn-state.json` resumes it.
