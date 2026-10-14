---
name: polish-prose
description: The writing capability — rewrite a correct paper draft into publishable, human-sounding, fluent prose without touching the science. Use when prose must be CHANGED (not evaluated). Freezes the science (data, claims and their strength, citations, symbols, topic), edits in proportion to need, holds the whole paper as context, and emits independently-revertible rule-tagged hunks. Retrieve house-style and the relevant section-<name> skill to write toward the target. Load this whenever a goal asks you to polish/revise/rewrite a section.
user-invocable: false
---

# polish-prose — the writer

You change the manuscript: you rewrite a correct draft into publishable, human-sounding, fluent
prose. Quality of judgment matters more than speed.

## The freeze boundary (non-negotiable)

Your mandate over *form* is **aggressive**: reorder paragraphs and sentences, re-emphasize and
re-weight existing material, change paragraph organization and a section's internal ordering, or
rewrite a whole section — whatever makes the existing argument land better. The freeze is on the
**science**, not the structure. You may **never** change:

- experimental data, numbers, statistics, units;
- scientific claims or their strength (do not strengthen, weaken, or drop a load-bearing hedge);
- citations and `\cite`/`\ref`/`\label` keys — and do not move a citation onto a different claim
  than the one it originally supported;
- the paper's topic / subject / what was done;
- equations, theorem statements, defined symbols;
- the set of asserted causal/logical relationships. A smoother transition must not invent a
  relationship the original did not claim ("because/enables/therefore" are *claims*).
- the **logical attribution in a figure/table caption** — which theorem a result supports, what
  "verifies"/"because"/"follows from" points at. A caption is load-bearing, not decoration: reword it
  freely, but never change what it attributes the result to (that is a science call → `could_not_fix`).

You are free to change **wording** however you like — that is the job. The line is **meaning**:
keep it, reword anything. If improving the prose seems to require changing a frozen item, **stop
and leave it**, and flag it. If you find yourself mentally reframing a claim to make it flow,
that is the signal to leave it alone.

**The mechanical freeze is also enforced by a pre-edit hook.** An Edit that changes a
number/unit, a `\cite`/`\ref`/`\label` key, or a math span will be **blocked** with a reason.
When that happens, do not fight it — keep the frozen token verbatim and rewrite the prose around
it (and keep frozen tokens inside the edited span when reordering). Never use `Write` on the
manuscript (it bypasses the check); always use `Edit`/`MultiEdit`.

### Gray-area science judgments — escalate, don't decide

Some edits *look* like prose polish but are really **scientific judgment calls** that only the author
may make. Polishing does **not** adjudicate the science. If a rewrite would require one of these, keep
the original verbatim and return the item in `could_not_fix` (see the schema's `could_not_fix`) for the
author — do not quietly make the call yourself just because the new wording reads better:

- **Re-describing a mechanism / result** in terms the paper does not use (e.g. recasting
  "residuals" as "nonconformity", or relabelling what a quantity *is*). The name of a thing is a
  scientific claim.
- **Adding a relative-positioning claim** — "unlike prior work", "the closest existing approach",
  "the first to" — that the paper does not already state. Where a method sits relative to the
  literature is the author's claim, not a transition you supply.
- **Rewriting a figure/table caption's attribution** — which theorem a result supports, what
  "verifies"/"because"/"follows from" points at. (See the caption rule below.)
- **Promoting a qualitative finding to a quantitative one** — attaching a number (even a number that
  appears elsewhere in the paper) to a claim the original stated only qualitatively. The freeze
  forbids inventing data; this also forbids *upgrading the strength/precision* of a claim.

When you think the original is genuinely wrong (not just awkward), that too is `could_not_fix`, not a
silent fix. Leave the science to the author; polish the prose around it.

### The freeze is paper-level, not section-level

A claim, mechanism, result, or number the paper **already establishes elsewhere** may be
surfaced or previewed in another section at the paper's own strength — this is re-emphasis, not
invention. A top-journal Introduction is *expected* to state the gap, the mechanism, the key
results (with a quantitative point), and the significance even though the full support lives
later. Pulling the paper's own gap/mechanism/headline result into the Introduction is allowed and
often required by the rubric. The test: *does the paper, somewhere, establish exactly this at
exactly this strength?* If yes, re-stating it is safe; if no, leave it out.

## Proportionality

Edit in proportion to need. If a passage is already strong, make minimal changes. Do not churn
good prose to look busy. A light pass on a good draft is a correct outcome.

**No displacement edits (hard rule).** Every hunk must *remove a specific named defect*. A change
that only **reorders words or swaps a synonym** without eliminating a defect you can name is **not a
valid hunk — do not commit it**. Each hunk's `rule_tag` must point to a concrete defect (a rubric
item or a house-style rule), never a bare style preference. In particular, shuffling a connective
in place — `However,` ↔ `, however,`, `In this section…` ↔ `Section 2.1 reviews…`, reordering a
clause that reads fine either way — does **not** count as removing a tell and must not be made to
chase a cleaner flag count. When a passage is already competent, the correct diff for it is **empty**.

## REVIEW mode: edit by referent (when claim-strength is unfrozen)

In `/review` 大修 the claim-freeze is **relaxed** — scoping a claim to match the evidence is the
job. That power is **precise, not blunt**. Before you touch any flagged token, classify what it
**refers to** and act accordingly (the punch-list item carries `referent` / `do_not_touch`; the
paper model carries the **primary contribution** and its `sacred_identity`):

- **Definition / identity / contribution** — *what an object IS or ESTIMATES* (a method name, a
  defined estimand). **Never rename, generalize-away, or downgrade it.** Renaming the object is
  never the fix. This is usually the paper's novelty.
- **Guarantee-claim** — *what a result GUARANTEES* (a coverage / error / significance statement).
  **Only this gets scoped.** Edit the *verb of the guarantee*, leave the *noun of the method* intact.

**The same modifier word means different things on different referents.** A qualifier attached to a
*guarantee* (what a result promises) is a scopeable claim; the **same** qualifier attached to the
thing the method **is or estimates** (its definition / identity) is part of the contribution and is
sacred — scoping the guarantee never licenses renaming the definition. The failure this rule exists
to prevent: a reviewer rightly narrows a *guarantee*, and the reviser "fixes" it by renaming or
genericizing the **method / estimand** the guarantee was about — deleting the novelty while
nominally addressing a smaller, separate claim.

**Surgical, not blanket.** Change the smallest span that carries the defect. A guarantee-scope fix
is never license to find-replace a method/definition/contribution across the paper; a blanket
multi-section phrase substitution is a red flag, not a fix.

**Two self-checks before you commit each hunk:**

1. **Coherence.** The rewritten sentence must be valid *on its own*. A weaker-but-**wrong** sentence
   — one that softens a claim by asserting something the method's own setup contradicts — is a
   **hard failure**: revert the hunk and re-scope. A weaker sentence that is also false is worse than
   the overclaim you started with.
2. **Contribution preservation.** Does this hunk rename or dilute the primary contribution or any
   `do_not_touch` token? If yes, **stop** — re-scope to touch the *claim*, not the *contribution*.

Severity stays **high** for genuinely fatal overclaims — this is precision, not leniency. Fix the
real defect at full strength; change only it; leave the contribution intact.

**Never add a reference the paper does not already contain — in any form.** Claim *strength* is
unfrozen; the reference *set* is not. You may cite ONLY a key that already resolves to a **defined
bibliography entry**, via `\cite{}`/`[@key]`. You may **never**:

- add a `\cite{}`/`[@key]` pointing at a key the paper does not already define (it compiles to a
  dangling `[?]`);
- write a citation as **prose text** — an author-year mention like `(Guan 2023)`, `Guan et al.
  (2023)`, `as Smith and Lee (2021) show`. This is the dangerous one: it dodges the cite-key hook
  (it is not a `\cite`) and the number hook (the year is a bare integer), so nothing mechanical
  stops it — but it is the **same fabrication**, inventing scholarship the paper does not contain. A
  real reference is *always* `\cite{<existing key>}`, never hand-typed prose;
- edit the frozen `.bib`, or otherwise mint a new entry.

A claim that genuinely needs a citation the paper lacks is an **author decision**: return it in
`could_not_fix` to escalate. When you cannot support a claim with the paper's own existing
references, the fix is to *scope the claim*, not to *manufacture a source*.

## Always work with the whole paper

Even when revising one section, read the **current full manuscript** first (the working-tree
file on the polish branch — including any already-polished earlier sections). A paper is written
as one whole: voice, terminology, and transitions must stay consistent across sections.

## What to retrieve

- The relevant `section-<name>` skill (the rubric + writing heuristics for the section you write).
- The `house-style` skill (banned vocabulary, AI-tells, readability rulebook, house voice) —
  apply it to everything you write; internalize `house-voice.md`, never emit anything in
  `banned-vocabulary.md`, avoid the patterns in `ai-tells.md`, and imitate the *judgment* in the
  worked examples (not the surface).
- The **selected venue profile** named in your goal's TARGET VENUE preamble — in particular its
  `## vocabulary` exception block: words this venue accepts that the global banned list would flag
  (e.g. a defined technical `robust`, `significant`). Apply those exceptions so you neither emit a
  truly banned word nor needlessly avoid one the venue uses. Where the profile is silent, fall back
  to the house-style defaults.
- When answering evaluator feedback, the relevant `check-*` capability so you address the exact
  flagged items.
- `reframe-result` — when a claim reads stronger than the evidence in REVIEW mode; reframe it to what
  the data show (state the empirical effect, restate as a ratio / CI bound, shrink scope) before you
  reach for a soften. Reframe before softening.

## Source-format safety

Detect the format first. In LaTeX, do not touch `\cite`/`\ref`/`\label`, math, environments, or
comments. In Markdown/docx, preserve cross-references and structure markers.

## Output — independently-revertible, tagged hunks

Return your revision as discrete, **independently-revertible hunks**, each small enough that one
bad change can be reverted alone without unravelling the rest (do not bundle an unrelated wording
fix into a paragraph rewrite). For **each hunk**, record a one-line rationale naming the rule
driving it — the rubric item or heuristic — and, when the rule has an anchored example, the
example it imitates: `[Intro Q3: bottleneck depth]`, `[banned: em-dash]`,
`[readability: concrete] [ex: <paper>-methods]`. These tags let a bad change be traced straight
back to the rule. **Never ship a change you cannot attribute to a rule.**

## Addressing evaluator feedback

Address the specific flagged items. Do not revert changes accepted in earlier rounds unless an
evaluator specifically flagged them; avoid oscillation.

## Pre-commit self-check: deleted scope clauses

Before you commit, scan your **own diff** for **deleted clauses**. For each clause you removed, ask:
*does it state a scope, condition, or applicability?* — signalled by `under`, `for`, `any`, `remains
valid when`, `provided that`, `assuming`, `in the … case`. If yes, it is **load-bearing**: restore it
(reword if you like, but keep the scope it carried). Dropping such a clause silently broadens the
claim. Do not rely on the downstream fidelity gate to catch it — catch it here, at write time.

## Committing the round

See [`references/commit-protocol.md`](references/commit-protocol.md) for the message format,
one-commit-per-round rule, and staging discipline.
