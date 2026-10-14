<!--
auto-research DECISION FILE template (HANDOFF §6 — the durable backbone of every human gate).

L0 copies this to state/decisions/DECISIONS-PENDING.md at a gate, fills the questions, prints a
short summary in chat, ALSO surfaces the same questions as a native AskUserQuestion card (when the
session is live), and ENDS ITS TURN. The file is the source of truth so a gate survives a
crash/restart: a fresh `/auto-research` reads state/pipeline-state.json, sees pending_gate, and
re-presents this file.

INGEST CONTRACT (next user turn):
- The owner answers by editing the `ANSWER:` line(s) below AND/OR replying in chat. Both are
  accepted; on conflict the CHAT reply wins.
- L0 validates each answer against that question's options (or accepts free text), archives this
  file to state/decisions/DECISIONS-RESOLVED-<n>.md, updates pipeline-state.json, and continues.
- An UNANSWERED question gets its (Recommended) option ONLY if the owner explicitly replies
  "use defaults"; otherwise L0 re-presents it (never silently guesses an author-only call).
-->

# DECISION REQUIRED — <gate id, e.g. GATE1-seed-select / failure-<phase>-<slug> / startup>

Run: <paper_slug or "(pre-seed)">  ·  Stage: <stage>  ·  Loop round: <n>  ·  Written: <ISO ts>

---

## Q1 — <one-line question>

**id:** `<question-id>`

**Context** (≤5 lines): 
<what the owner needs to decide this, e.g. the HTML report path, the per-seed score table, or the
investigator's findings for an escalated reviewer demand>

**Options:**

| # | Option | Notes |
|---|--------|-------|
| A | <option label> (Recommended) | <why / trade-off> |
| B | <option label> | <…> |
| C | <option label> | <…> |
| — | Other (free text) | <when a custom answer makes sense> |

**ANSWER:** <leave blank; owner fills with an option letter/label or free text>

**NOTES:** <optional free text bound to THIS question — durable twin of the live card's 'n' note.
For a GATE-1 idea question: your refining angle for the idea, and/or "venue: <prepared-venue>" to
override the batch default venue for it. Survives a crash; chat wins on conflict.>

---

<!-- Repeat the Q-block per pending question. GATE 1 carries one venue question (the batch default)
plus ONE Keep/Skip question per idea (notes are per-question, so per-idea notes need per-idea
questions). A failure surface (B1 hard-stop / B2 author-only seam) carries one disposition question:
Resume after I clarify / Abandon this idea, with {slug, phase, milestone, why-stuck, needed} in
Context. Context also carries run_rollup — two deterministic lines (THIS-RUN FAILURES: FAILURES.md
crash/failure count; OPEN SCIENCE FLAGS: kill-criteria-touching FLAGGED signals from
RESEARCH_LOG.md), each present-or-explicitly-'none'; render both verbatim on the card. These two
rollup lines are IN ADDITION to the "Context (≤5 lines)" guidance above — the fixed prefixes
THIS-RUN FAILURES / OPEN SCIENCE FLAGS must be rendered verbatim, never compressed away.
Escalations bubbled from a review L1 (escalations[] → author-only seams S3/S10/S4/S5) ride
in that Context, each with the investigator's findings and the item's real executor options. -->
