# paper-polish

A Claude Code plugin that takes a **correct** AI-generated paper draft and polishes it into
**publishable, human-sounding, fluent** prose — without touching the science.

This is a **scaffold**. The orchestration, the house-style rules, the per-section rubrics, and the
agent roles are written. The **examples** (blessed before/after pairs, model paragraphs,
your and your advisor's extra criteria) are intentionally left as marked slots for you to fill
in later. Every slot is tagged `[FILL IN: ...]`.

## The one rule that defines the system

**Freeze the science. Rewrite the prose.**
- Frozen (the reviser must never change): experimental data, numbers, claims, citations, the
  paper's topic/subject, what was done.
- Free (the reviser may change arbitrarily): wording, sentence structure, paragraph
  organization, section-internal ordering, an entire section's rewrite.
- Proportionality: if a passage is already good, change little. Edit in proportion to need,
  not to prove activity.

## Architecture

`/polish` reads `spec/polish.js` (the canonical spec) and reproduces it as the orchestrator,
using goal-spawned subagents that retrieve skills at runtime.

```
draft ─┐  Phase 0: detect format · write .polish/fidelity-manifest.json (arms the hook) · git base + polish branch
       ▼  per section (serial), a revise → evaluate → converge loop:
  ┌──────────────┐  goal-spawned; retrieves polish-prose + house-style + section-<name>; holds the
  │  reviser      │  WHOLE current paper; edits in place; commits the round.
  │ (one shell,   │  ┌─ PRE-EDIT HOOK blocks any edit that mutates a frozen token (numbers,
  │  read-write)  │ ◄┘  \cite/\ref/\label, math) or touches a data file — mechanical freeze, zero-token.
  └──────┬───────┘
         ▼  evaluate — read-only reviewer shells, goal-spawned, retrieve check-* skills:
  ┌───────────────────────────────────────────────────────────────────────────────┐
  │  fidelity gate (ALWAYS, isolated)  check-fidelity — semantic meaning-drift only │
  │  quality (dynamic count, but EVERY check-logic · check-results ·                │
  │  dimension covered each round)     check-readability · check-ai-tells           │
  └──────┬────────────────────────────────────────────────────────────────────────┘
         ▼  the workflow computes the severity-weighted open-flag count (pure arithmetic, never
         │  told to the agents) → converge (≤ max_rounds) → SHIP THE BEST ROUND, not the last
         ▼
  Phase 2.9 cross-section sweep (when target=all) · Phase 3 emit: git log/diff + close-call list
  + polish-diff.pdf (latexdiff inline-diff; LaTeX + TeX toolchain, else the git diff)
```

- **Orchestrator-driven, config-driven.** `spec/polish.js` is the executable spec; a Claude
  model reproduces it. Every knob (models, subagent type, `inject_thinking`, thresholds, order)
  lives in `config/config.yaml`. (Direct run by the Workflow tool is deferred.)
- **Goal-spawned subagents, runtime skill retrieval.** Two generic shells — a read-write `reviser`
  and a read-only `reviewer` — are spawned *by goal* and pull the capability + section skills the
  goal needs. Revision is single-agent and always holds the full paper.
- **Two-layer fidelity.** The mechanical freeze (numbers, `\cite`/`\ref`/`\label`, math, data
  files) is enforced deterministically by a **pre-edit hook** — a bad edit is blocked, not reviewed
  after. The **semantic** half (claim strength, dropped hedges, citation re-attachment, invented
  causality, scope) is the always-on `check-fidelity` reviewer; it flags meaning-drift only, never
  rewording. A semantic FAIL is restored (its own commit) before convergence is judged.
- **Coverage guaranteed, count dynamic.** Every round covers all four quality dimensions; only how
  they are packaged into reviewers varies (`evaluate.spawn_mode`).

## Components

| Path | What it is |
|---|---|
| `spec/polish.js` | the canonical executable spec (the loop) |
| `config/config.yaml` (+ `.example.yaml`) | all knobs: models, subagent type, `inject_thinking`, thresholds, section order |
| `hooks/` | the pre-edit fidelity hook (`check-fidelity.sh` + `check_fidelity.py`) — the mechanical freeze guard |
| `commands/polish.md` | `/polish` — reads `polish.js` and reproduces it |
| `commands/review.md` | `/review` — adversarial review (总修), diagnose-only; reads `spec/review-protocol.md` |
| `spec/review-protocol.md` (+ `spec/review/`) | the REVIEW OWNER's standing orders (cold panel → owner synthesis → punch-list → HANDOFF export; replaces the retired `spec/review.js`) |
| `scripts/render_diff_pdf.sh` | latexdiff → pdflatex inline-diff PDF (`polish-diff.pdf` / `review-diff.pdf`); the only diff renderer |
| `skills/polish-prose/` | the writer capability |
| `skills/check-*/` | the evaluation capabilities (fidelity / logic / results / readability / ai-tells) |
| `skills/house-style/` | banned-vocab + AI-tells + readability + house voice |
| `skills/section-*/` | per-section rubric + writing heuristics |
| `agents/{reviewer,reviser}.md` | the two generic goal-driven subagent shells |

## How to test it in Claude Code

```bash
# from the directory that contains the paper-polish/ folder
claude --plugin-dir .
# then inside Claude Code:
/polish path/to/draft.tex introduction
```

`--plugin-dir` loads the plugin locally without publishing to a marketplace, so you can iterate fast.

## The development loop (how you make it good)

The run is **fully autonomous** — no human gate at runtime; the system judges its own convergence and
ships. You improve it **offline**, by editing rules and watching what changes in the output:

1. Run `/polish` on a real draft. The system polishes on a `polish` git branch, one commit per round.
2. Read the **git history** (`git log` + `git diff base..HEAD`) and the **fidelity close-call list**.
   Each change's commit names the rule (and `[ex:]` example) behind it.
3. When a change is wrong, you can see **which rule caused it** → edit that rule (a rubric line, a
   banned word, a `readability.md` line, a threshold), not the prose.
4. When you bless a fix, drop the before/after pair into `examples/` and reference it from the rule
   with `[ex: <id>]`. Examples are **inline anchors that make the rules concrete** (and so make the
   agents' behavior more robust) — not a runtime gate and not the convergence judge.

The voice is anchored by worked examples under `skills/house-style/examples/venue-anchors/` (one file per
section, each a before→after pair); none ship in this release — copy `_TEMPLATE/` to add your own.

## A note on the readability dimension

Your original prompts cover **structure** thoroughly but said little about **fluency/flow**, which is
your stated core goal. So this axis now has its own checkable rulebook —
`skills/house-style/references/readability.md` — with a fail-signal per rule, plus your own
before→after passages as anchors. It is still the dimension to keep developing as
real runs reveal flow problems specific to your writing: add lines and `[ex:]` pairs, and tune the
fail-signal thresholds to taste.


  