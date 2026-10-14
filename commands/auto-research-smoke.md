---
description: Pure wiring/connectivity probe for the auto-research pipeline — confirms every spawn point (the roles spec/research.js spawns directly, plus the per-orchestrator nested roles inside ideation/review) is reachable with the EXACT production subagent_type and that its skill/spec artifact still loads, WITHOUT doing any of the real work (no real ideation/WebSearch, no real profile creation, no real review panel deliberation, no real experiment execution, no real spec freeze). Derives its role checklist from config/config.yaml + the actual spawnL1/spawnL2/spawnWorker call sites in spec/research.js at run time (never trusts stale comments/docs), runs in an isolated data root, and writes a coverage ledger + markdown report in minutes. Re-run after any spec/research.js or vendored-spec change as a fast wiring regression check — this is NOT a functional/content regression test (no toy paper is produced; see git history before this command's redesign if that heavier design is ever needed again).
argument-hint: optional run-slug to name/parallelize smoke workspaces (default "default") — resolves to ~/.auto-research-smoke/<slug>
allowed-tools: Bash, Read, Write, Task
---

You are running a WIRING-ONLY connectivity sweep of the auto-research pipeline — NOT `/auto-research`,
NOT a real run. Your entire job: for every role the pipeline can spawn, spawn ONE minimal probe using
that role's exact production `subagent_type`, have it confirm its own skill/spec artifact still exists
and loads, record the result, and move on. No pipeline state machine, no gates, no loop rounds, no
finishing chain, no paper — none of that is reproduced here because there is no real work to gate.

Run-slug (raw text after `/auto-research-smoke`, default `default`): `$ARGUMENTS`

## What this command must NOT do

- Must NOT create or rebuild a researcher profile (no Semantic Scholar fetch, no `arxiv-profile` real
  run) — the ideation-nested `arxiv-profile` probe below only confirms its own skill file loads.
- Must NOT really fetch/rerank/judge arXiv papers, and must NOT fan out one ideation agent per paper —
  exactly ONE `arxiv-generate`-shaped probe (and one each of its sibling nested roles) is enough.
- Must NOT spawn a real 2-4-reviewer panel doing a full cold read — exactly ONE `reviewer`-shaped probe
  is enough to prove the review fan-out edge works.
- Must NOT run any real experiment code, draft any real prose, edit any real figures, or write a real
  paper. Every probe returns a placeholder the instant its artifact is confirmed loadable.
- Must NOT edit `config/config.yaml`, any vendored `plugins/*/config/config.yaml`, or any spec file —
  the model override is prompt-injected only, exactly like the design this command replaces used.

## Preconditions

- Plugin root: !`echo "${CLAUDE_PLUGIN_ROOT:-unknown}"`
- Smoke root (derive from $ARGUMENTS, default slug "default"; NEVER the monorepo): !`slug="$ARGUMENTS"; [ -z "$slug" ] && slug="default"; echo "$HOME/.auto-research-smoke/$slug"`
- Live role list — `models:` keys, the ground truth for every role `spec/research.js` spawns directly: !`awk '/^models:/{f=1;next} f&&/^[a-z_]+:$/{exit} f' "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" | grep -oE '^  [a-z_]+:' | tr -d ' :'`
- Vendored review-spec role keys (nested under `review_orchestrator`): !`grep -A5 "DIAGNOSE-ONLY review shells" "${CLAUDE_PLUGIN_ROOT}/plugins/paper-polish-ar/config/config.yaml"`
- Monorepo cleanliness guardrail (must be empty at start AND end): !`git -C "${CLAUDE_PLUGIN_ROOT}" status --short 2>/dev/null || echo "(not a git repo / cannot check)"`

## Role checklist (starting table — self-heal against the live `models:` keys above)

Use this table as the starting checklist. **Before dispatching, diff it against the live `models:`
keys precondition above** — if a key appears there that isn't in this table, or vice versa, that IS a
real finding (the checklist itself has drifted from the code): add/drop the row, note it in the final
report as `checklist_drift`, and proceed with the corrected list. Never trust a comment over an actual
`spawnL1(role,...)`/`spawnL2(role,...)`/`spawnWorker(role,...)` call site in `spec/research.js` — a role whose
name sounds like an orchestrator can still be a plain leaf at its real call site; the table below reflects
call-site ground truth, not naming.

| role | subagent_type | artifact to confirm-load |
|---|---|---|
| `ideation_orchestrator` | `auto-research:orchestrator` | `spec/spawn-prompts/IDEATION-L0.md` (+ `plugins/arxiv-recommender-ar/workflows/arxiv-scout.js`) |
| `ideation_auditor` | `claude` | `spec/spawn-prompts/IDEATION-INTEGRITY.md` |
| `review_orchestrator` | `auto-research:orchestrator` | `spec/spawn-prompts/REVIEW-L0-CONTRACT.md` (+ `plugins/paper-polish-ar/spec/review-protocol.md`) |
| `spec_freezer` | `claude` | `spec/spawn-prompts/SPEC-FREEZE.md` |
| `viability_recommender` | `claude` | `spec/spawn-prompts/VIABILITY-RECOMMENDER.md` |
| `seed_to_handoff` | `auto-research:producing-worker` | `skills/handoff-authoring/SKILL.md` |
| `rescue` | `auto-research:producing-worker` | `skills/research-rescue/SKILL.md` |
| `amplify` | `auto-research:producing-worker` | `skills/research-amplify/SKILL.md` |
| `scale_contract_reviewer` | `claude` | `spec/spawn-prompts/SCALE-CONTRACT-REVIEW.md` |
| `audit_artifact_auditor` | `claude` | `spec/spawn-prompts/AUDIT-ARTIFACT-INTEGRITY.md` |
| `independent_verifier` | `claude` | `spec/spawn-prompts/VERIFY-PROTOCOL.md` |
| `experiment_worker` | `auto-research:producing-worker` | `plugins/experiment-lab-ar/spec/experiment-protocol.md` |
| `literature_worker` | `auto-research:producing-worker` | `spec/spawn-prompts/LITERATURE-WORKER.md` |
| `literature_reviewer` | `claude` | `spec/spawn-prompts/LITERATURE-AUDIT.md` |
| `dossier_writer` | `claude` | `spec/spawn-prompts/DOSSIER.md` |
| `theory_auditor` | `claude` | `spec/spawn-prompts/THEORY-AUDIT.md` |
| `workorder_hardener` | `claude` | `spec/spawn-prompts/WORKORDER-HARDENING.md` |

### Nested roles (one extra probe-level, only for the true `auto-research:orchestrator` rows above)

For each of `ideation_orchestrator` / `review_orchestrator`, that spawned orchestrator ALSO probes the distinct nested roles it owns
(one probe per distinct role — never one per paper/reviewer/section). Starting sub-tables (self-heal
the same way against each vendored `config.yaml`'s own `roles:` block if it's read and differs):

- **ideation_orchestrator** nests: `arxiv-rerank`, `arxiv-claim-judge`, `arxiv-repo-judge`,
  `arxiv-generate`, `arxiv-verify`, `arxiv-profile` — all `claude`, artifact =
  `plugins/arxiv-recommender-ar/skills/<role>/SKILL.md`.
- **review_orchestrator** nests: `reviewer` (just ONE, not the 2-4 panel), `comprehender`,
  `experimenter` (`subagent_type: experimenter`), `investigator` (`subagent_type: investigator`) — all
  artifact = `plugins/paper-polish-ar/skills/review-panel/SKILL.md` for reviewer/comprehender, the
  agent's own instructions for experimenter/investigator.

## Uniform probe-goal template

Every probe (top-level and nested) gets this exact shape, substituting `<ROLE>`, `<SUBAGENT_TYPE>`,
`<ARTIFACT_PATH>` per its row above:

> You are a WIRING-ONLY connectivity probe for role `<ROLE>` (this is `/auto-research-smoke`, never a
> real run — no real research/review/writing work exists for you to do). Do NOT attempt this role's
> real task: no WebSearch, no experiment code, no paper edits, no real analysis. Your only job:
> 1. Use the Read tool to open `<ARTIFACT_PATH>`. Confirm it exists and is a real skill/spec doc —
>    report its first heading line and an approximate word count as evidence you actually read it.
> 2. Return immediately: `{"role":"<ROLE>","subagent_type":"<SUBAGENT_TYPE>","artifact_path":"<ARTIFACT_PATH>","reached":true,"note":"<first heading + word count>"}`.
> If the artifact is missing/unreadable, return `"reached":false` with a `note` explaining why — that
> IS a real wiring finding; report it faithfully, do not paper over it.
>
> If you are one of the four orchestrator-tier roles: after your own artifact check above, ALSO spawn
> your nested-role probes (listed for you above) in ONE parallel batch, each with this SAME template
> applied to that nested role, then return your own result PLUS a `"nested": [...]` array of their
> results.

Force `model:"haiku"` on every probe spawn (top-level and nested), prompt-injected exactly as before —
never edit `config/config.yaml` or any vendored config to achieve this.

## Workflow

1. Read the preconditions above; build the corrected role checklist (self-heal step).
2. Spawn every top-level role's probe in ONE message with one `Task` call per role (parallel, not
   sequential) — using that role's real `subagent_type` from the table.
3. Collect all results (the four orchestrator-tier ones arrive with their own `nested` array already
   filled in from step-2's spawn).
4. Write `$HOME/.auto-research-smoke/<slug>/coverage.json`: a flat map of every role (top-level +
   nested) to `{subagent_type, artifact_path, reached, at: <iso8601 you fill in>, note}`.
5. Write `$HOME/.auto-research-smoke/<slug>/SMOKE-REPORT.md`: one table (role | subagent_type |
   artifact | reached ✅/❌ | note), plus a `checklist_drift` line if step 1 found any.
6. Re-run the monorepo-cleanliness guardrail; if `git -C "${CLAUDE_PLUGIN_ROOT}" status --short` is
   non-empty, STOP and report which probe wrote outside its own spawn (a probe should never write
   anywhere but its own report) — this is a real finding, not a soft warning.
7. Summarize the coverage table directly in your response (counts of reached/unreached, any drift, any
   real breakage found) — no `AskUserQuestion`, no gate card; this command never blocks on a decision.

## Invariants

- **Never do the real work.** Every probe returns the instant its artifact is confirmed loadable — no
  role is asked to actually ideate, review, experiment, draft, or write.
- **Never a proxy `subagent_type`.** A probe spawned as plain `general-purpose`/`claude` when
  production spawns `auto-research:orchestrator` (or vice versa) proves nothing — always use the exact
  production type from the table, resolved from `spec/research.js`'s real call sites, never a comment.
- **Never mutate config or spec files.** The Haiku override is prompt-injected only.
- **Never write outside the isolated smoke root** (`$HOME/.auto-research-smoke/<slug>`) — the
  monorepo (`${CLAUDE_PLUGIN_ROOT}`) must be untouched at the end, checked by the guardrail above.
