---
description: Adversarial top-venue review (诊断). The main session becomes the REVIEW OWNER — it reads the whole paper itself, spawns ≥2 independent venue-persona cold reads + a mechanical checklist pass, synthesizes the harshest honest rejection reasons into ONE prioritized punch-list, and escalates reject/major needs-author items to the author. Review is DIAGNOSE-ONLY — it performs no revision; every fix (claim reframing, content moves, logic-gap closures, supplementary experiments) is HANDED OFF, not applied here. Exported experiment-demands become a portable HANDOFF that the auto-research loop's experiment/draft stage (or /polish & /rewrite) acts on. Run BEFORE /polish. Reads spec/review-protocol.md.
argument-hint: natural language — e.g. "review paper/main.tex for Nature Computational Science, introduction only"
allowed-tools: Bash, Read, Write, Task, Skill, AskUserQuestion
---

You are starting a paper REVIEW run (诊断) — and **you are the REVIEW OWNER** in its STANDALONE seat.
Your standing orders are `spec/review-protocol.md` (inlined below in the Preconditions); its mechanical
shapes live in `spec/review/output-contract.md`, its depth catalogue in `spec/review/attack-classes.md`,
and the checklist-pass brief in `spec/review/checklist-pass.md` — Read each leaf when the protocol says
to. Review is **diagnose-only**: you never edit the manuscript; every actual fix happens downstream (the
auto-research loop's experiment/draft stage, or `/polish` & `/rewrite`). This file does NOT restate the
protocol's phases, invariants, schemas, or escalation buckets (a hand-maintained copy drifts — and had
already gone stale once); it only tells you how to ENTER it.

The user's request (free-form, any language): `$ARGUMENTS`

**Parse all inputs from that request by meaning, not by position:**
- **MASTER file** — the root `.tex` that `\input{}`s the sections (e.g. `main.tex`), or a single-file
  paper, or its directory. Match it against the candidate `.tex` list below; if unstated/ambiguous, the
  protocol's manuscript-resolution step reasons it out.
- **TARGET section(s)** — one of `introduction|results|methods|discussion|si`, or `all` (default).
- **VENUE** — a journal/conference name if the request names one (map it case/space/hyphen-insensitively
  to one of the prepared venues below); if it names a venue you cannot confidently map, still pass that
  name (the protocol §0 aborts it as unsupported) — do NOT pass `null`. Pass `null` ONLY when no venue
  was named at all (the protocol then recommends + asks you to pick). NEVER read the venue from config.

## Preconditions

- Plugin root: !`echo "${CLAUDE_PLUGIN_ROOT:-unknown}"`
- Project dir: !`echo "${CLAUDE_PROJECT_DIR:-$PWD}"`
- Prepared venues (the ONLY venues you may use; each needs a `review/` kit; map a named venue to one of these, else it is unsupported): !`base="${CLAUDE_PLUGIN_ROOT}/skills/house-style/examples/venue-anchors"; for p in "$base"/*/profile.md "$base"/*/*/profile.md; do [ -f "$p" ] || continue; d=$(dirname "$p"); rel="${d#$base/}"; case "$rel" in default|_TEMPLATE) ;; *) [ -f "$d/review/rubric.md" ] && kit=yes || kit=no; echo "$rel (review-kit:$kit)";; esac; done 2>/dev/null || echo "(none prepared)"`
- Config present: !`test -f "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" && echo yes || echo "no (defaults will be used)"`
- Active config (roles/models + escalate knob + section_order — NOT the venue, which is runtime): !`cat "${CLAUDE_PLUGIN_ROOT}/config/config.yaml" 2>/dev/null || echo "(none — baked-in defaults apply)"`
- Standing orders (the protocol you now execute): !`cat "${CLAUDE_PLUGIN_ROOT}/spec/review-protocol.md"`
- Request (parse master / section / venue from this): !`echo "$ARGUMENTS"`
- Candidate `.tex` under project (match the master against these): !`find "${CLAUDE_PROJECT_DIR:-$PWD}" -name '*.tex' -not -path '*/.git/*' 2>/dev/null | head -40`
- Git safety preview (project dir): !`d="${CLAUDE_PROJECT_DIR:-$PWD}"; echo "repo=$(git -C "$d" rev-parse --show-toplevel 2>/dev/null || echo none) branch=$(git -C "$d" rev-parse --abbrev-ref HEAD 2>/dev/null || echo none)"; git -C "$d" status --short 2>/dev/null | head -5`

## Entering the protocol

1. Parse `master_path`, `target` (default `all`), and `venue` from the request as above. If the request
   is `--continue` (resume an interrupted run), the protocol's resume rule applies: the on-disk artifacts
   are the state (§6) — but a fresh context ALWAYS re-reads the paper itself before synthesizing.
2. Execute the protocol as the STANDALONE seat, with `plugin_root = ${CLAUDE_PLUGIN_ROOT}` and
   `project_dir = ${CLAUDE_PROJECT_DIR:-$PWD}`. The [STANDALONE] arms apply to you: you resolve the venue
   (§0, asking via the picker when none was named) and you ask the author every escalated item (§4).
   All non-venue knobs live in `config/config.yaml → review:` (`section_order` is shared from the
   `polish:` block).
3. Review runs to completion in-session (no detached job, no asyncRewake yield). When the protocol's Emit
   finishes, surface the deliverable — a **diagnosis package, not a revised paper**: the git-tracked task
   files, `review-report.md`, and — for every demand the author elected to export — the `HANDOFF` +
   `REVIEW-EXPERIMENT-PROTOCOL`. Report the count of escalated / still-open / exported items. Recommend handing
   the HANDOFF to the loop (or running it standalone), then `/polish`. The user's original branch is
   untouched.

## Seat rules (standalone specifics the protocol leaves to the entry)

- **The non-negotiables are not yours to adapt.** Protocol §2 and the output contract are executed
  exactly; your freedom lives in §3 (panel width ≥2, personas, investigation depth, ordering).
- **Only you can ask; investigate before asking.** Subagents never call AskUserQuestion — they mark items
  and return. You ask **every** reject/major needs-author item (multi-round, ≤4 questions per call, never
  truncated), after the per-item investigator has run (unless `review.escalate.investigate: false`).
- **Pass the `questions` array as the EXACT named `questions` parameter** — do not hand-roll or reshape
  the AskUserQuestion call inline (that caused the observed `required parameter 'questions' is missing`
  error).
- **Never fabricate to resolve; never silently drop a reject/major item.** A fix that needs data the
  paper lacks is a `needs_author` item that escalates and exports — never an invention.

[FILL IN: any project-specific review defaults — e.g. always-skipped sections
(also settable in config.yaml → review:).]
