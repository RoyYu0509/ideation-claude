---
name: formal-discipline
description: Production discipline for any formal/mathematical artifact (proof, derivation) — grounding, symbol consistency, weakness ledger. Loaded by name by the rewrite formal gate and research-rescue.
user-invocable: false
---

# formal-discipline — produce a SCAFFOLD, not a verified result

You are about to draft a formal/mathematical artifact (a proof, a derivation, or a formal definition) for a paper-polishing /review item. The result must be marked UNVERIFIED and is for the author to sign off on. The four steps below are MANDATORY — apply all of them BEFORE returning, even when the construction appears complete.

The orchestrator does not re-litigate these steps after you return; the soundness audit downstream is your peer reviewer, not your safety net. A skipped step here surfaces as a failure there.

## Step 1 — Literature grounding

Before drafting the artifact, run at least one `WebSearch` (and a `WebFetch` if a specific source surfaces) to locate the standard form / canonical statement of the result you are establishing, or the closest published analogue. The purpose is to:

- anchor the argument's STRUCTURE against an established pattern,
- surface known edge cases / common pitfalls / failure modes specific to results of this shape.

The search is for ORIENTATION only. You may **not** introduce new citations the paper does not already include — the orchestrator's pre-edit hook blocks new citation keys outright. Use what you learn to inform what you write, not what you cite.

## Step 2 — Internal cross-reference self-check

For every named object the artifact invokes — assumption, definition, lemma, theorem, equation, symbol, set, constant, index — verify the target actually exists in the paper before returning.

- If a `\ref{}` / `\eqref{}` / named reference would resolve to nothing, EITHER introduce the missing object explicitly within the artifact OR surface the gap in the weakness ledger (Step 4). Never silently invent the target.
- If the paper introduces the object under a different name in a different section, use the paper's name; do not coin a new one.

## Step 3 — Symbol / notation / definition consistency

Where the artifact uses a quantity also defined elsewhere in the paper, the formulation here must match the paper's existing formulation. If you find a divergence (the same symbol denotes a different object across sections; the same object has two formulations; the definition you need disagrees with the one the paper states), DO NOT silently pick one convention — surface the divergence in the weakness ledger.

Readers compare formulations across sections. A silent unification reads as an error.

## Step 4 — Weakness ledger

Always return a short list of open points. Produce this list EVEN WHEN the construction appears complete — its purpose is to scope the author's verification, not to signal failure. Each entry names:

- a step relying on a property the paper has not explicitly stated, OR
- an edge case not handled (degenerate inputs, equality cases, empty sets, limiting cases), OR
- a formulation that differs from another statement of the same object elsewhere in the paper, OR
- a place where the construction depends on an implicit assumption.

Template (substitute the bracketed placeholders with concrete material from the paper):

- Step [N] uses property [X] of object [Y]; the paper does not state [X] explicitly. OPEN.
- The argument assumes [assumption A]; the case where [A is not in force] is not addressed. OPEN.
- Symbol [Z] is used here as [usage A]; in Section [S] the paper defines [Z] as [usage B]. RECONCILE.

## Stance and output framing

Your output is a SCAFFOLD for the author to sign off on, not a verified result. Default toward listing MORE open points rather than fewer; defer judgment calls to the author.

Mark the artifact UNVERIFIED at the location your spawn prompt's safety contract specifies (a visible "(draft — pending author verification)" note and the LaTeX comment the prompt names). Return the weakness ledger as part of your free-form return text alongside `committed` / `touched_files` — no schema change is needed.

If after applying Steps 1–4 you CANNOT produce a sound scaffold (the gap between what the paper states and what the artifact needs is too wide), do not hand-wave. Return `could_not_fix` with the unresolved gaps; the orchestrator records them for the author. A blocking ledger is a useful result; a forced completion that fails Step 2 or 3 is not.
