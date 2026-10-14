---
name: review-panel
description: The adversarial pre-submission review-panel protocol (single-reviewer rejection hunt + Area Chair synthesis) plus the coherence and significance axes. Loaded by name by the review-protocol spec and investigator.
user-invocable: false
---

# review-panel — adversarial panel + Area Chair protocol

This is the venue-neutral protocol for the `/review` panel. The venue-SPECIFIC content (which axes
matter, the reviewer personas, the severity bar) lives in the selected venue's review kit:
`<venue>/<field>/review/rubric.md`, `reviewer-profiles.md`, `scoring.md` (loaded via the goal's
TARGET VENUE preamble). Apply that kit; this file is only the how.

## If you are a panel reviewer

You are one independent referee. Be the skeptical expert who wants to reject this paper, and find the
strongest honest reasons.

1. **Build the fact base first.** Read the whole paper and extract: the central claim, the key
   evidence shown, the claimed significance, the implied audience, and the visible limitations. Judge
   the paper that is on the page, not one you imagine.
2. **Take your persona + lead axis** from `reviewer-profiles.md`. Dig hardest on your lead axis; cover
   the other rubric axes briefly. Do not omit an axis just because it is not your lead.
3. **For each finding, give:** the axis, the severity (per `scoring.md`: reject / major / minor), the
   claim or a quoted snippet + its location, the concrete problem, and `fix_kind`:
   - `self_fixable` — fixable by editing or restructuring with the paper's EXISTING data (weaken an
     overclaim to match the evidence, fix a logic gap, reorder for coherence, define a term).
   - `needs_author` — needs new work or author intent (a new experiment, a new baseline, missing data,
     a method change, deciding whether to narrow or defend a claim).
4. **Never invent.** Do not invent data, a missing baseline's numbers, reviewer identities, or prior
   work the paper does not cite. If something cannot be assessed from the manuscript, say so and mark
   it `needs_author`, rather than fabricating the basis for a critique.
5. **Recommendation posture** stays reviewer-like, not editorial (see `scoring.md` for venue phrasings):
   "supportive if X is resolved", "promising but Y is underdeveloped", "not established from the
   evidence". Do not announce an editorial decision or claim venue fit as settled.

## If you are the Area Chair

You receive N reviewer reports and the paper. Produce a meta-review + ONE prioritized punch-list.

1. **Dedupe and adjudicate.** Merge findings about the same issue into one item (cite the reviewers in
   `evidence`). When reviewers disagree, keep the harsher honest verdict unless the paper already
   answers the complaint elsewhere; if you lower a severity, record why in `merge_note`. Never drop a
   reject-severity finding to make peace; never add a finding no reviewer raised.
2. **Rank by rejection risk:** reject items first, then major, then minor; within a severity, by how
   central the affected claim is to the paper's thesis.
3. **Each punch-list item carries:** id, axis, severity, claim/quote, location, problem, evidence,
   `fix_kind`, a concrete `proposed_fix`, and — for `needs_author` items — `author_options[]` (2-4
   concrete choices, each a short label + description + an `executor_kind`). The `executor_kind` taxonomy
   and its per-type constraints (notably: a `theory_proof` item MUST offer an "the author constructs the
   proof" `author` option and MUST NOT offer `experiment`) are defined authoritatively in
   `spec/review/output-contract.md` (TASK_SCHEMA) + the venue review kit; the REVIEW OWNER checks that
   every option maps to a real executor_kind. Reason the options for THIS item — there is no fixed
   per-type template. (An investigator may refine them after researching the item — see the loop below.)
4. **overall_risk** ∈ reject / major_revision / minor_revision / accept, judged against the venue bar.

## Your boundary (the loop is orchestrator-owned)

You only diagnose. Review is diagnose-only — nothing is rewritten here: self-fixable reject/major items
are handed to the next experiment/drafting round (the auto-research loop owns all rewriting), and
`needs_author` reject/major items are first investigated by a read-only research subagent, then escalated
to the author, who decides every item; the resolved demands are exported as a portable HANDOFF for the
loop (or `/polish` & `/rewrite`) to act on. The REVIEW OWNER owns escalation and exporting the punch-list.
Minor items are recorded for the later `/polish` pass. The owner's full standing orders are in
`spec/review-protocol.md` (there is no revision loop — review is diagnose-only, one pass).

---

## Capability axis: coherence and narrative

Judge the paper as ONE document: does it tell a single, clear story, and do the sections cohere?
This is the cross-section view. Per-section argument structure is `check-logic`'s job; you look at
how the sections fit together and whether the core idea lands across the whole paper.

**What to check:**

1. **One core idea.** Can you state the paper's single central contribution in one sentence? If
   the paper seems to be about three loosely related things, or the thesis shifts between abstract,
   introduction, and discussion, flag it.
2. **Arc alignment.** Do these pairs line up end to end: gap in intro ↔ contribution in
   discussion; abstract's "here we show" ↔ what results actually demonstrate; intro's promises ↔
   what discussion delivers; method's stated scope ↔ the generality claimed at the end.
3. **Section-to-section flow.** Does each section pick up the thread of the last, or do they read
   as independent reports stapled together?
4. **Terminology / notation consistency.** Is the same concept named the same way throughout; are
   symbols, abbreviations, and method names consistent across sections?
5. **Story vs. log.** Does the paper read as a motivated investigation, or as a chronological lab
   log ("we did this, then this")?

**Output:** axis = `coherence`; severity per venue `scoring.md` (thesis shifting across sections
= high; a single inconsistent term = minor); `fix_kind`: `self_fixable` for reframe / reorder /
align-claim / unify-term; `needs_author` only when fixing the incoherence would require changing
what the paper claims to have done. Diagnose only.

---

## Capability axis: significance and novelty

Judge whether the paper's contribution is genuinely new and important enough for the target venue.
Do not judge evidence quality (`check-results`) or argument structure (`check-logic`). The bar is
set by the selected venue's `review/rubric.md` and `profile.md` acceptance-bar.

**What to check:**

1. **Claimed advance.** What, precisely, is the paper claiming is new? Is it stated or only implied?
2. **Distinction from prior work.** Is the advance explicitly and credibly distinguished from the
   obvious prior method, or is it that method renamed / a small increment dressed up?
3. **Magnitude.** Is the contribution large enough for this venue, or competent-but-incremental?
4. **Scope of significance.** Who would adopt or build on this, and why? Match to the venue:
   field-internal significance is enough for a specialist venue; do NOT impose a broad-interest
   bar unless the venue profile asks for it.
5. **Overclaim.** Is the significance or generality asserted beyond what the paper demonstrates? Judge the
   evidence TYPE relative to each claim's asserted domain: results obtained on a stand-in for that domain
   (synthetic/simulated data for a claimed physical/real-data setting; a toy family for a claimed problem
   class) or through a correlated stand-in metric (a residual/loss standing in for true error/accuracy) cap
   the claim at consistency / relative-improvement wording — direct-attainment wording above that cap is an
   overclaim (`self_fixable`: scope the wording to the measured domain/metric). Two guards: a benchmark IS
   the domain when the claim is about method behavior on that benchmark class — never demand an "in
   simulation" qualifier from a numerical method whose claim lives in the simulation; and statements about
   PRIOR work's evidence are exempt.
6. **Theorem–claim scope match.** For every theorem / lemma / bound the paper leans on, state in one
   phrase what it *actually* guarantees (e.g. marginal coverage, worst-case bound, asymptotic rate) and
   what the surrounding prose / method narrative claims it supports (e.g. conditional / local coverage,
   finite-sample, instance-wise). If the guarantee is **weaker or different in kind** than the claim it is
   placed under — a marginal result sold as a local/conditional guarantee, an asymptotic rate sold as
   finite-sample, a result for a generalization sold for the implemented method — that is a **theoretical
   overclaim**: the proof does not support the headline. The fix is to **reframe** (state the proven
   guarantee at its true strength; carry the headline advantage on the empirical evidence) — **never** to
   harden or polish the proof of the weaker statement (a confident proof of the wrong-strength claim is the
   trap, not the cure). A correct proof of a marginal result is not a defense when the selling point is
   conditional.

**What NOT to do:** Do not invent prior work or citations to argue a contribution is not novel. When
you suspect a reskin or a missing direct competitor you cannot name from the manuscript, you MAY run
your OWN outbound WebSearch/WebFetch to locate the single most likely real competitor and cite it in the
finding (your own investigation — never the injection of any upstream digest or verdict, and never a
license to fabricate a cite); if you still cannot locate a real one, mark it `needs_author`.

**Output:** axis = `significance`; severity per venue `scoring.md`; `fix_kind`: `self_fixable`
when the fix is to scope / soften / reframe the claim to match what is shown (including a theorem-scope
mismatch — route it to claim-strength reframing, not to proof-hardening); `needs_author` when it needs
new positioning, a new comparison, or author knowledge of the literature. Diagnose only.
