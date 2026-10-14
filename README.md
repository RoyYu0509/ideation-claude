<div align="center">

# ideation-claude

**From "what should I work on?" to a verified, adversarially reviewed research specification — in one Claude Code session.**

Personalized arXiv recommendation · verified-kill ideation · execute-and-review loop · you only steer the direction

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-7c3aed.svg)](https://docs.claude.com/en/docs/claude-code)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](RUNBOOK.md)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)

[Quick start](#quick-start) · [How it works](#how-it-works) · [Results](#results) · [Commands](#commands) · [Layout](#repository-layout) · [Limitations](#limitations)

**English** | [简体中文](README.zh-CN.md)

</div>

<p align="center">
  <img src="docs/images/system-overview.png" alt="System overview: memory, orchestrators, stage workflows" width="100%">
</p>

`ideation-claude` is a set of [Claude Code](https://docs.claude.com/en/docs/claude-code) plugins (plugin id
`auto-research`, command `/auto-research`) that turn a
researcher's own publication history into a ranked weekly reading list, proposes research ideas from it,
**kills the ones that do not survive executed checks**, and then spends rounds *running* the survivor,
*reviewing* what came back, and *re-authoring* the research specification toward more ambition and more rigor.

You are asked for one thing: **which idea to pursue** (and, per round, a direction call when the system flags
one). Everything else runs unattended and is resumable.

The deliverable is a **research specification** — `SPEC-FINAL.md`, the way it evolved (`SPEC-EVOLUTION.md`),
the evidence under `EXPERIMENTS/`, and a `FINAL-REPORT.md` — not a paper draft.

## Highlights

- **Ideas die on executed evidence.** Candidates go through screen → verify (with *executed* probes) →
  recheck → refutation hunt. A killed idea is not rescued by a later rewrite.
- **The auditor is never the producer.** Work is split across three agent tiers; reviewers cold-read in
  independent contexts, and a `spawn_guard` hook forbids unbounded nesting.
- **Numbers cannot be quietly invented.** Reported values are frozen and traced back to an audited ledger;
  PreToolUse hooks (`ship_gate`, `lock_guard`, `decision_guard`, `central_narrow_guard`) enforce this
  mechanically instead of by prompt.
- **A deterministic exit gate.** The loop ends by arithmetic over reviewer verdicts (`bin/loop_gate.sh`), not by
  the model deciding it is done. A negative result that contradicts the idea's novelty claim is an *abandon*
  signal, not a deliverable.
- **Humans steer direction only.** One gate to pick the idea; per-round direction cards; routine gates are
  answered by a cold-read agent unless you opt to answer them yourself.
- **Resumable and long-run safe.** All state is on disk; long experiments detach and re-wake the session at
  zero token cost.
- **One config file per layer.** Every knob lives in `config/config.yaml` (see also `key-config.yaml`);
  code has no hidden defaults — a missing key crashes with its name.

## How it works

Four stages run in order, each owned by its own orchestrator and only the last one touching you again:

| Stage | What happens | Where it lives |
|---|---|---|
| **Recommendation** | Build a researcher profile (Google Scholar / arXiv), fetch the week's new papers, rank them deterministically — thread queries, BM25 and arXiv category merged by reciprocal rank fusion. | [`plugins/arxiv-recommender-ar`](plugins/arxiv-recommender-ar) |
| **Ideation** | Select high-quality papers per research thread (claim matches evidence · code is reproducible · problem is extensible), then propose candidate ideas. | `plugins/arxiv-recommender-ar` |
| **Desk Check** | Check the premises, the theory derivation and novelty against prior work. Each idea ends *retained* or *eliminated*, with the reasons recorded. | `plugins/arxiv-recommender-ar` |
| **Experiment Check** | You pick one retained idea. It becomes a work order, then a loop of *author experiment → run → log → review-panel vote → pass / fail / flag*; a *flag* routes back through human steering. | root plugin + [`paper-polish-ar`](plugins/paper-polish-ar) + [`experiment-lab-ar`](plugins/experiment-lab-ar) |

<p align="center">
  <img src="docs/images/stage-workflows.png" alt="The four stage workflows in detail" width="100%">
</p>

### What a verdict looks like

The review panel returns one of three verdicts per round. The three runs below are real, replayed under the
current rules: a **pass** hands back findings and next steps, a **fail** eliminates the idea and records why,
a **flag** pauses for human steering and then re-enters the loop.

<p align="center">
  <img src="docs/images/experiment-check-cases.png" alt="Experiment Check: a pass, a fail and a flag" width="85%">
</p>

### Three tiers of agents

| Tier | Agent | Role |
|---|---|---|
| L0 | the main session (`commands/auto-research.md`, spec in `spec/research.js`) | state machine, gates, you |
| L1 | [`orchestrator`](agents/orchestrator.md), [`producing-worker`](agents/producing-worker.md) | fan out to independent contexts, or own one heavy job |
| L2 | [`leaf-worker`](agents/leaf-worker.md) | one bounded sub-task; structurally cannot spawn further agents |

Details and the forbidden topologies are in [`docs/agents.md`](docs/agents.md).

## Results

These figures come from our own evaluation on a 12-week pool of arXiv papers labelled by a researcher. The
operating point was chosen after seeing the labels, so treat the curves as in-sample illustrations, not as
a held-out benchmark.

**Recommendation.** The deployed configuration sits above both single-signal baselines at every list length.

<p align="center">
  <img src="docs/images/recall.png" alt="Recall and group-averaged recall vs list length" width="85%">
</p>

**Which signals matter, and does re-ranking help?** Gains come from the thread and category channels; BM25 adds
a little; the other four signals add nothing. In this evaluation no re-ranking run — cross-encoder or LLM —
beat the deterministic order.

<table>
  <tr>
    <td width="50%"><img src="docs/images/channels.png" alt="Contribution of each signal"></td>
    <td width="50%"><img src="docs/images/rerank.png" alt="nDCG@100 after re-ranking"></td>
  </tr>
</table>

**Does the Desk Check discard the right ideas?** An external grader (a different model family from the one
that generated and verified the ideas) rated each idea without seeing the verdict. Eliminated ideas are far more
often rated *Fatal* or *Flawed* than retained ones.

<p align="center">
  <img src="docs/images/desk-check-quality.png" alt="External-grader ratings of eliminated vs retained ideas" width="85%">
</p>

**Retrieval vs. reading the whole week.** An agent that reads the whole week's papers with the researcher's
profile matches or beats the deployed retrieval for all three researchers at both depths; with only a
one-sentence description it falls behind in most cells.

<p align="center">
  <img src="docs/images/fullread.png" alt="Papers worth reading: retrieval vs whole-week agent" width="85%">
</p>

## Quick start

**Requirements:** [Claude Code](https://docs.claude.com/en/docs/claude-code), Python 3.11+ (tested on
3.13/3.14), `git`, and several GB of disk for the ideation environment (PyTorch + SPECTER2 are pulled once).
TeX Live (`pdflatex`, `bibtex`) is optional — only the review phase's PDF rendering uses it.

```bash
git clone https://github.com/RoyYu0509/ideation-claude.git ~/ideation-claude
cd ~/ideation-claude

# one-off: Python environment for ideation (idempotent)
bash plugins/arxiv-recommender-ar/bin/setup_venv.sh

# arXiv/OAI etiquette: put a contact address in the User-Agent
export AR_CONTACT_EMAIL="you@example.com"

# create your own data folder (profile, caches, runs, state) pinned to you — code stays read-only
bash bin/ar-init.sh ~/my-research \
     --scholar "https://scholar.google.com/citations?user=<YOUR_ID>" --aliases "Your Name"

# open Claude Code from the data folder with all four plugins loaded from the checkout
cd ~/my-research
R=~/ideation-claude
claude --plugin-dir $R --plugin-dir $R/plugins/arxiv-recommender-ar \
       --plugin-dir $R/plugins/paper-polish-ar --plugin-dir $R/plugins/experiment-lab-ar
```

Inside the session:

```
/auto-research
```

No arguments are needed; it reads `state/pipeline-state.json` to decide whether to start, resume a gate or
resume a detached run. On a fresh folder it confirms your identity, builds your research profile once, then
runs ideation and stops at the **idea-selection gate**. Pass free text to steer the scout, e.g.
`/auto-research a direction on conformal prediction for PDE surrogates`.

Prefer a marketplace install? `/plugin marketplace add RoyYu0509/ideation-claude`, then
`/plugin install auto-research@auto-research` plus the three phase plugins; the plugins are then available in
any folder. The ideation Python environment must still be bootstrapped inside the installed plugin directory.
[`RUNBOOK.md`](RUNBOOK.md) walks through setup, a first run, resuming, and permissions.

Check your checkout before a long run:

```bash
bash tests/run_all.sh      # shell test suites for the loop gate, hooks, gates, detach/re-wake, …
```

## Commands

| Command | Plugin | What it does |
|---|---|---|
| `/auto-research [free text]` | `auto-research` | The whole pipeline: ideation → pick one idea → execute / review / re-author loop → `SPEC-FINAL.md`. |
| `/arxiv-scout-beta` | `arxiv-recommender-ar` | Only the weekly recommendation + verified-kill ideation (stages 1–3). |
| `/review` | `paper-polish-ar` | Adversarial top-venue review of a manuscript: independent cold reads → one prioritized punch-list. |
| `/polish`, `/polish-figures` | `paper-polish-ar` | Rewrite prose or repaint figures while the data, claims and citations stay frozen. |
| `/learn` | `auto-research` | Post-run retrospective of the *machine*: maps every artifact to the component that made it. |
| `/auto-research-smoke` | `auto-research` | Wiring probe: checks every spawn point is reachable without doing any real work. |

## Configuration

| File | Governs |
|---|---|
| [`config/config.yaml`](config/config.yaml) | The glue: loop rounds, exit gate, role → model routing, milestones. |
| [`key-config.yaml`](key-config.yaml) | A single control panel, ordered by phase; apply with `bin/apply_key_config.sh`. |
| [`plugins/arxiv-recommender-ar/config/config.yaml`](plugins/arxiv-recommender-ar/config/config.yaml) | Ingest, prefetch, judges, kill loop. |
| [`plugins/paper-polish-ar/config/config.yaml`](plugins/paper-polish-ar/config/config.yaml) | Review panel size, rounds, role → model. |

Role-to-model routing is per role (e.g. cheaper models for per-item fan-out, stronger ones for judgment
calls); change it in the configs above rather than in code.

## Repository layout

```
.claude-plugin/        marketplace + root plugin manifest
commands/              /auto-research, /learn, /auto-research-smoke
spec/                  L0 state machine (research.js), status model, gate taxonomy, spawn prompts
agents/  hooks/        the three agent tiers; PreToolUse / Stop guards
skills/                handoff-authoring, research-amplify, research-rescue, experiment-engineering
bin/  config/  assets/ deterministic helpers, config SSOT, per-venue paper skeletons
plugins/
  arxiv-recommender-ar/  recommendation + verified-kill ideation (Python + workflows)
  paper-polish-ar/       adversarial review, /polish, /polish-figures, freeze hooks
  experiment-lab-ar/     experiment + drafting loop work spec
tests/                 shell test suites
docs/                  agent topology, figures
```

## Limitations

- **Claude Code only.** Orchestration relies on Claude Code subagents, hooks and `AskUserQuestion`.
- **It is expensive and slow.** A full run fans out many subagents and may run for hours; set model routing
  and `max_loop_rounds` deliberately before the first run.
- **The deliverable is a specification.** Experiments are executed to check and sharpen the spec; the system
  does not write the paper.
- **Evaluation is small.** The results above come from a few researchers' data; they motivate the design,
  they do not establish general performance.

## Contributing

Issues and PRs are welcome. Each phase is a self-contained plugin under `plugins/`; edit it in place. Please run
`bash tests/run_all.sh` before opening a PR, and keep prompts in the markdown/skill files rather than inlining
them into the orchestration JS (`spec/research.js` is a thin spec on purpose).

## Acknowledgements

`plugins/paper-polish-ar/skills/nature-reader` and `nature-academic-search` are vendored from
[Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills) (MIT). See
[`plugins/paper-polish-ar/NOTICE.md`](plugins/paper-polish-ar/NOTICE.md). The LaTeX skeletons under `assets/`
keep their publishers' original licenses.

## License

[MIT](LICENSE) © 2026 Yifan Yu
