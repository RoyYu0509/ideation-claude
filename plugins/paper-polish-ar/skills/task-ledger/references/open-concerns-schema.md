<!-- open-concerns-schema.md — the AUTHORITATIVE open-items ledger schema (dossier-12 H2: split out of
     task-ledger SKILL.md so the root loop's hard-read contract has its own leaf; the SKILL.md keeps only
     the five review task files + checklists). Consumed by: every phase-spec's PROGRESSIVE DISCLOSURE
     protocol + spec/research.js (round freeze reads open_concerns; its LEDGER_CONTAINER inline string is
     the freeze-critical container fallback, kept in sync with the Container paragraph below). -->

## Open-items ledger — schema (the PROGRESSIVE-DISCLOSURE engine's input)

This is the **authoritative definition** of the open-items table that `TASK_STATUS.md` maintains and that
every phase-spec's PROGRESSIVE DISCLOSURE protocol reads (Doc A §2.1 / §6.1). It is **dimension-agnostic** —
the same shape serves Ledger ① (科研实质, keyed by concern) and Ledger ② (呈现精修, keyed by unit) — so do
not bake prose-only or figure-only fields into it.

**Container (authoritative).** The file is the JSON **object** `{ "open_concerns": [ <rows> ] }` — **never** a bare
array and **never** `{ "items": [...] }`. The in-loop round-freeze (`spec/research.js`) hard-reads
`readJson(TASK_STATUS.concerns.json).open_concerns`, so a writer that picks any other container makes the freeze
silently read `[]` and the disclosure set drifts. Every writer (verifier / review-AC / theory-auditor) READS the file
first and **upserts into the same `open_concerns` array by `id`, preserving every existing row** (each sensor appends;
none overwrites a peer's rows). The same container serves both Ledger ① and Ledger ② (the figure pass uses the same
object in its own file). Absent file ⇒ create `{ "open_concerns": [ <your row> ] }`.

One row per item:

| field | meaning |
|---|---|
| `id` | stable slug, e.g. `RV-baseline-missing`, `FIG3-legend-overlap` |
| `concern` | the `domain.aspect` it rolls up to (= which reference; see `assets/concern-reference-map.yaml`). For Ledger ② keyed-by-unit, also carry the unit (section name / figure id). |
| `status` | `open` / `closed` / `reopened` / `deferred` (deferred = needs-author or out-of-scope) |
| `severity` | categorical `major` / `minor` (NO numeric score). Each sensor tags it: a verifier hard-check FAIL ⇒ `major`; review maps the item's disposition tier (reject/major ⇒ `major`, minor ⇒ `minor`); theory-auditor flags only load-bearing gaps ⇒ always `major`. The viability floor reads this to detect severity-filtered non-convergence (a `major` item open across rounds) without over-triggering on `minor` ones. |
| `opened_round` / `closed_round` / `last_touched_round` | round trace |
| `evidence` | path proving open or closed (result.md / diff / log) |
| `source` | which sensor/agent raised it (verifier / panel / AC / fidelity / figure-fidelity / visual-QA) |

**Status state machine (demand-driven, NON-monotonic):** `open → closed` when a fix is proven (record
evidence); `closed → reopened` when a resident sensor detects a regression (never silently stays closed);
`open → deferred` when it cannot be acted on here (needs-author / out-of-scope). A `reopened` item behaves
exactly like `open` for disclosure. **The set never just shrinks** — a cheap resident sensor runs every round
and can reopen or add items.

**Central-K discipline.** A row whose `id` backs `HANDOFF.ambition.locked.json`'s `central_result`/GAMBLE set
NEVER encodes a claim-narrowing disposition as a bespoke `status` string (status stays in the 4-value enum
above); the narrowing is recorded via `resolution` free text ONLY after `research-rescue` has run for it this
round (`bin/central_ambition_guard.sh` enforces this mechanically before a milestone can be recorded done —
`spec/research.js`'s `runCentralAmbitionGuard`).

**The PD engine's only per-round action:** take items with `status ∈ {open, reopened}` → dedupe their
`concern` → that union is the **reference set to disclose this round** (look each concern up in
`concern-reference-map.yaml`); every other reference stays unloaded. Closed/deferred concerns are NOT read.

**Round key** = `state.loop_round` (reset at the GATE-1 pick by `applyPickedIdea`), never turn/session. Goal-builders
and all in-session resumes read the **frozen round snapshot** `runs/<slug>/.round-<N>.concerns.json`
(Doc B §6), never the live ledger — so a detach and its re-wake see a byte-identical disclosure set.

### Ledger ① 科研实质 — one living `TASK_STATUS.md`, three cadences (Doc A §2.2 / §10-A)

It is **one file with three update cadences**, not "five phases each updating every round":

- **(i) setup-once** (`round=0`, seed→handoff): seed the initial open-items from the HANDOFF K-criteria.
- **(ii) per-round triad** (`round=state.loop_round`, B1 / verify / B2): **only these three** update the table
  and drive per-round shrink. `generateHandoff(state, transition=true)` (research.js) is the reopen mechanism (a B2
  new_exhibit becomes a next-round B1 open item).
- **(iii) append-once** (`round=final` sentinel, after loop EXIT, rewrite): NON-FATAL, appends/closes once,
  **must not trigger a "next round."**

**Closing predicate:** an item may close only on **verify PASS ∧ B3 EXIT** (RC-1 belt); otherwise it
carries forward / reopens into the next round. ⚠️ **experiment-wave exception (Doc A §5.3 / §10-B):** the B1
`experiment_worker` does NOT run concern-ledger PD — it runs a *completeness* ledger (result.md / DAG,
monotone). Concern-driven disclosure applies to `section_drafter` (drafting) only.

### Ledger ② 呈现精修 — reuse this schema, keyed by unit (Doc A §2.3 / §10-E)

`polish` keeps one section-keyed `TASK_STATUS.md`, `polish-figures` keeps one figure-keyed one (two passes,
same schema). Resident sensors are the fidelity-gate (prose meaning unchanged) and figure-fidelity-gate
(figure science unchanged) — they reopen units. Convergence = open set empty ∧ sensors clean. Round floors
differ by dimension (prose vs figures), and the `abstract` path is select-not-iterate (a categorical
head-to-head gate — clearly/marginally/not better vs the original, no numeric scores — not a converge
loop) — the schema must tolerate both without per-dimension fields.
