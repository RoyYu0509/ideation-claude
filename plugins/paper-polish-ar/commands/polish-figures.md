---
description: Polish a paper's figures toward publication quality — freezes the cached data + the manuscript prose, repaints the figures via their plotting scripts (visual style + code naming) and regenerates them. The MIRROR of /polish. Reads spec/polish-figures.js and reproduces its phase sequence with subagents.
argument-hint: natural language — e.g. "polish all figures in paper/main.tex" or "restyle figure 3 in main.tex to match my taste"
allowed-tools: Bash, Read, Write, Task, Skill
---

You are starting a figure-polishing run. The phase sequence, the fidelity gate, and the ship/best-round
logic are defined in `spec/polish-figures.js`; **reproduce it** (it is inlined below in the Preconditions)
as the orchestrator, using Task subagents + Bash. This file does NOT restate the phase sequence or its
rules (a hand-maintained copy drifts) — `spec/polish-figures.js` + `config/config.yaml` are the single
source of truth; it only tells you HOW to enact them. Do not start editing before reading the spec.

The user's request (free-form, any language): `$ARGUMENTS`

**Parse all inputs from that request by meaning, not by position:**
- **MASTER file** — the root `.tex` (e.g. `main.tex`) the paper compiles from, or the directory it
  lives in. Match it against the candidate `.tex` list below; if unstated/ambiguous, reason it out
  (the existing file with `\documentclass`).
- **TARGET figure(s)** — a figure id / number / filename substring if the request names one (e.g.
  "figure 3", "the coverage plot"), or `all` (the default when none is named).
- **VENUE (optional)** — if the request names a target venue, map it (case/space/hyphen-insensitive) to
  one of the Prepared venues below and pass it as `venue`; if none is named, omit it (the figure stance
  then falls back to the generic research-figure-plotting defaults).

## Preconditions

- Plugin root: !`echo "${CLAUDE_PLUGIN_ROOT:-unknown}"`
- Project dir: !`echo "${CLAUDE_PROJECT_DIR:-$PWD}"`
- Prepared venues (map a NAMED venue to one of these to load its figures.md; omit if none named): !`base="${CLAUDE_PLUGIN_ROOT}/skills/house-style/examples/venue-anchors"; for p in "$base"/*/profile.md "$base"/*/*/profile.md; do [ -f "$p" ] || continue; d=$(dirname "$p"); rel="${d#$base/}"; case "$rel" in default|_TEMPLATE|*/_core) ;; *) [ -f "$d/figures.md" ] && echo "$rel";; esac; done 2>/dev/null | sort -u | head -40`
- Config present: !`test -f "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" && echo yes || echo "no (defaults will be used)"`
- Active config (figures block — max_rounds / quality_dimensions / roles): !`python3 -c "import yaml,json;print(json.dumps(yaml.safe_load(open('${CLAUDE_PLUGIN_ROOT}/config/config.yaml')).get('figures',{}),indent=2))" 2>/dev/null || echo "(none — baked-in defaults apply)"`
- Workflow definition: !`cat "${CLAUDE_PLUGIN_ROOT}/spec/polish-figures.js"`
- Request (parse master / target figure from this): !`echo "$ARGUMENTS"`
- Candidate `.tex` under project (match the master against these): !`find "${CLAUDE_PROJECT_DIR:-$PWD}" -name '*.tex' -not -path '*/.git/*' 2>/dev/null | head -40`
- Figures the paper includes (`\includegraphics` targets — the universe to polish): !`grep -rhoE '\\includegraphics(\[[^]]*\])?\{[^}]*\}' "${CLAUDE_PROJECT_DIR:-$PWD}" --include=*.tex 2>/dev/null | sed -E 's/.*\{([^}]*)\}/\1/' | sort -u | head -40`
- Candidate plotting scripts (where the figures are built): !`grep -rlE 'matplotlib|pyplot|savefig|\bplt\.' "${CLAUDE_PROJECT_DIR:-$PWD}" --include=*.py 2>/dev/null | grep -vE '/(\.git|node_modules|vendor)/' | sort -u | head -40`
- Git safety preview (project dir): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; echo "repo=$(git -C "$d" rev-parse --show-toplevel 2>/dev/null || echo none) branch=$(git -C "$d" rev-parse --abbrev-ref HEAD 2>/dev/null || echo none)"; git -C "$d" status --short 2>/dev/null | head -5`

## Workflow

1. First parse `master_path` and `target` (a figure id/substring, default `all`) from `$ARGUMENTS`
   — by meaning, not position. For the master: match the parsed description to the candidate `.tex`
   list (the existing file with `\documentclass`); if it cannot be matched, report the candidates.
2. Reproduce `${CLAUDE_PLUGIN_ROOT}/spec/polish-figures.js` — the **canonical source of truth** for the
   phase sequence, inlined above via the last precondition cat — exactly, with these args:
   `plugin_root = ${CLAUDE_PLUGIN_ROOT}`, `project_dir = ${CLAUDE_PROJECT_DIR:-$PWD}`, the parsed
   `master_path` and `target` (default `all`), and `venue` (a prepared-venue rel if one was named, else
   omit). All knobs live in `config/config.yaml → figures:`, read by the spec.
3. When all phases finish, surface the deliverable the spec's `return` composes (the `polish-fig-<ts>`
   branch history + diff, the recompiled preview PDF, the per-figure report, and the living
   `TASK_STATUS.md`) to the user. The user's original branch is untouched.

## Orchestration rules (HOW to act — these have no JS equivalent)

- **Reproduce, don't re-litigate.** Follow every `[[MECH]]` step verbatim and reason only at the seams.
  The figure survey, the three-way figure-fidelity gate (PASS/HOLD/FAIL), the regen gate, the serial
  one-figure-at-a-time valve, mandatory visual QA, and the ship-best decision are all owned by the spec —
  do not re-summarize them here.
- **The freeze hook is the science guard.** Phase 0 arms the figure-mode PreToolUse fidelity hook; it
  freezes the cached data + manuscript prose (captions belong to `/polish`) and DENIES edits that would
  change the science a figure conveys. Never route around a deny. The venue figure stance lives in the
  `paper-polish-ar:research-figure-plotting` skill (namespaced — the bare name can resolve to an opposite-stance global skill) (and the optional venue `figures.md`) that each figure agent retrieves
  — it is not restated here.
