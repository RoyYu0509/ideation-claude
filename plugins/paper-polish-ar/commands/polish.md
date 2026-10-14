---
description: Polish a paper draft toward publishable quality (freezes the science, rewrites prose/structure/flow). Handles single- and multi-file (\input) LaTeX. Reads spec/polish.js and reproduces its phase sequence with subagents.
argument-hint: natural language — e.g. "polish paper/main.tex, introduction only, for Nature Computational Science"
allowed-tools: Bash, Read, Write, Task, Skill, AskUserQuestion
---

You are starting a paper-polishing run. The phase sequence, the gates, and the ship/best-round logic are
defined in `spec/polish.js`; **reproduce it** (it is inlined below in the Preconditions) as the
orchestrator, using Task subagents + Bash. This file does NOT restate the phase sequence or its rules (a
hand-maintained copy drifts) — `spec/polish.js` + `config/config.yaml` are the single source of truth; it
only tells you HOW to enact them. Do not start editing before reading the spec.

The user's request (free-form, any language): `$ARGUMENTS`

**Parse all inputs from that request by meaning, not by position:**
- **MASTER file** — the root `.tex` that `\input{}`s the section files (e.g. `main.tex`), or a
  self-contained single-file paper, or the directory it lives in. Match it against the candidate
  `.tex` list below; if unstated/ambiguous, the `[[SEAM:input-resolve]]` step reasons it out.
- **TARGET section(s)** — one of `introduction|results|methods|discussion|si|abstract`, or `all`
  (the default when none is named).
- **VENUE** — a journal/conference name if the request names one (map it case/space/hyphen-insensitively
  to one of the prepared venues below), else `null`. NEVER read the venue from config.

## Preconditions

- Plugin root: !`echo "${CLAUDE_PLUGIN_ROOT:-unknown}"`
- Project dir: !`echo "${CLAUDE_PROJECT_DIR:-$PWD}"`
- Prepared venues (the ONLY venues you may use; map a named venue to one of these, else it is unsupported): !`base="${CLAUDE_PLUGIN_ROOT}/skills/house-style/examples/venue-anchors"; for p in "$base"/*/profile.md "$base"/*/*/profile.md; do [ -f "$p" ] || continue; d=$(dirname "$p"); rel="${d#$base/}"; case "$rel" in default|_TEMPLATE) ;; *) echo "$rel" ;; esac; done 2>/dev/null || echo "(none prepared)"`
- Config present: !`test -f "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" && echo yes || echo "no (defaults will be used)"`
- Active config (knobs: section_order / roles / weights — NOT the venue, which is runtime): !`cat "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" 2>/dev/null || echo "(none — baked-in defaults apply)"`
- Workflow definition: !`cat "${CLAUDE_PLUGIN_ROOT}/spec/polish.js"`
- Request (parse master / section / venue from this): !`echo "$ARGUMENTS"`
- Candidate `.tex` under project (match the master against these): !`find "${CLAUDE_PROJECT_DIR:-$PWD}" -name '*.tex' -not -path '*/.git/*' 2>/dev/null | head -40`
- Git safety preview (project dir): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; echo "repo=$(git -C "$d" rev-parse --show-toplevel 2>/dev/null || echo none) branch=$(git -C "$d" rev-parse --abbrev-ref HEAD 2>/dev/null || echo none)"; git -C "$d" status --short 2>/dev/null | head -5`

## Workflow

1. **[[SEAM:input-resolve]]** First parse `master_path`, `target` (section, default `all`), and
   `venue` from `$ARGUMENTS` (and the surrounding message) — by meaning, not position. For the master:
   match the parsed description to the candidate `.tex` list. The resolver auto-selects the
   `\documentclass` master when given a DIRECTORY, and on failure emits `{error, candidates}` (nonzero
   exit); if it fails, **don't just stop** — thin-reason over the candidate `.tex` to find the real
   master (the existing file with `\documentclass`, preferring one that also `\input{}`s sections), then
   proceed. Only give up and report the candidates if none qualifies. For the **venue**: if the request
   names one, map it (case/space/hyphen-insensitive) to exactly one **Prepared venue**; if it maps to
   one, pass that rel as `venue`; if it names a venue you cannot confidently map, **still pass that
   name** (so the workflow's `[[SEAM:venue-resolve]]` aborts as unsupported) — do NOT pass `null`. Pass
   `null` ONLY when the request named no venue at all (the workflow then recommends + asks).
2. Reproduce `${CLAUDE_PLUGIN_ROOT}/spec/polish.js` — the **canonical source of truth** for the
   phase sequence, inlined above via the last precondition cat — exactly, with these args:
   `plugin_root = ${CLAUDE_PLUGIN_ROOT}`, `project_dir = ${CLAUDE_PROJECT_DIR:-$PWD}`, and the parsed
   `master_path`, `target` (default `all`), and `venue` (a prepared-venue rel, a named-but-unmapped
   venue, or `null`). The **venue is NOT read from config** — it comes from your NL parse (step 1); all
   OTHER knobs live in `config/config.yaml → polish:`, read by the spec.
3. When all phases finish, surface the deliverable the spec's `return` composes (the `polish-<ts>` branch
   history + diff, the inline-diff PDF, the fidelity close-call list, the keynote `science_advisory`
   notes, and the per-round verdict files) to the user. The user's original branch is untouched.

## Orchestration rules (HOW to act — these have no JS equivalent)

- **Reproduce, don't re-litigate.** Follow every `[[MECH]]` step verbatim and reason only at
  `[[SEAM:...]]` points. The freeze boundary, the venue three-outcome resolution, the hook lifecycle, and
  the ship/best-round decision (a categorical ladder pick — there is no numeric weighting) are all owned
  by the spec (+ `polish_converge.py`) — do not re-decide or re-summarize them here.
- **The freeze hook is the science guard.** Phase 0 arms the PreToolUse fidelity hook; it DENIES any edit
  to a frozen number/citation/symbol inside a reviser subagent. Never route around a deny.
