---
name: context-scope
description: Decides how much cross-section context to load before polishing or reviewing one section (target only vs pull in siblings). Loaded by name by polish.js and the section-loop spec.
user-invocable: false
---

# context-scope — how much of the paper to read

You are polishing or reviewing ONE section file. Reading the whole 6–8-file paper every time is
expensive and usually unnecessary: most prose edits are local. This skill tells you how much sibling
context to load. **Default to local; pull in siblings only when the edit genuinely needs them.**

## The decision

1. **Always read your target section file first** (the goal names it). Form your edit or judgment from
   it before deciding you need anything else.
2. **Use the keynote effort as the prior** (the goal passes it for this section):
   - `light`, or **no keynote (a single-section run)** — expect trivial, local edits → **stay local.**
     Do NOT bulk-read siblings; at most pull a single, specific sibling on demand per step 3.
   - `normal` / `heavy` — expect substantial work → you MAY load the sibling sections up front.
3. **Targeted, on-demand escalation (light / no-keynote):** open a sibling **only when a CONCRETE
   cross-section question actually arises while editing**, and then open **only the one file that
   answers it** — never the whole set:
   - "Does Methods call this `X` or `Y`?" → open Methods, that file only.
   - resolving a specific keynote argument-arc flag → open the one section it names.
   - a structural move that physically spans two sections → open that one other section.
   A *vague sense* that an edit "might touch cross-section wording" is NOT a reason to read anything:
   make the local edit; if no concrete question forms, you never needed the sibling.
4. **Anti-pattern — the thing this skill exists to prevent:** on a `light` / no-keynote section, do
   NOT read all the sibling files up front "to be safe" or "to align terminology." That throws away
   the entire saving. One targeted read beats six speculative ones; usually you need zero.
5. **Never load siblings for purely local work:** word choice, sentence rhythm, removing an AI tell,
   tightening a clause, fixing local clarity. These are self-contained in your own file.
6. **Carve-out — contribution / identity edits are inherently whole-paper-scope (never local).** If an
   edit touches the **main method's name or definition**, any **primary-contribution / `sacred_identity`
   token**, or a **key term** (the paper model flags these), it is *not* a local edit no matter how small
   it looks. Before changing such a token you MUST read, together, the **Methods** (the definition), the
   **relevant theorem/definition**, and the **Introduction's contribution statement**, so a rename or a
   claim-scope stays coherent across every site (the referent rules for HOW to edit such a token — and why
   a single-file find-replace of a method/estimand name is forbidden — are in `polish-prose`). Renaming the
   same token in five places is one cross-section change, not five local ones.

## How to load

The goal gives you the sibling section paths. Load them with `Read` (read-only — you still edit or
judge only your own file). You do not need the master's figure captions / back-matter unless a flag
points there.

## Why local-by-default is safe

The whole-paper safety nets still hold when you stay local: the **keynote** already read the entire
paper and seeded the global argument-arc flags; the **cross-section sweep** runs at the end to catch
terminology / symbol / citation drift; and **house-style** carries the target voice independent of
reading other sections. So local-by-default loses nothing on trivial edits, and you escalate exactly
when meaning could depend on another section. In particular, you do NOT need to pre-read siblings just
to keep terminology consistent — the cross-section sweep is the dedicated catch for that; reach for a
sibling only when a concrete question blocks the edit in front of you.
