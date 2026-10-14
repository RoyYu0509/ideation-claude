---
name: arxiv-rerank
description: Rationale writer for the seed papers the per-thread seed walk selected. Use when arxiv-scout's Phase 3c spawns it; the set and order are fixed by week-<W>-rerank-llm/final.json — it writes why_it_matters / thread / gap per seed and week-<W>-rerank.json. Never re-ranks, never re-judges, never generates idea seeds.
allowed-tools: Bash, Read, Write
---

## Job — you write the rationales; the ranking is already decided

Since 2026-09-20 the selection that runs before you has no ranking call at all. The fused
mechanical order's first papers are the delivered reading list (its length is `TOP_K` in
`scripts/lib/rerank_llm.py`, the one definition); every one of them belongs to the
research thread that ranks it highest, and each thread's **seed** is the first paper it owns that
passed the claim / repo / extensibility gate. So the set handed to you is already final, already
judged, and already carries the thread it was seeded for. Your job is
to write, for EXACTLY the papers in its `top` list and in that order, the rationale the ideator
needs, and to write `week-<W>-rerank.json`.

You do NOT call any external LLM API — you reason natively. You do NOT re-rank.

## Inputs

- `${CLAUDE_PROJECT_DIR}/data/profile/profile.md` — first-person NL profile.
- `${CLAUDE_PROJECT_DIR}/data/profile/profile.json` — `threads` (each: `name`, `summary`,
  `keywords`, member `papers`, and the script-computed `status` active / legacy, `n_recent`,
  `emerging`), `keywords`, `recent_direction`, `arxiv_categories`. profile.md lists each
  thread's member paper titles — compare a candidate against those real papers, not only
  against the summaries.
- `${CLAUDE_PROJECT_DIR}/data/cache/week-<YYYY-Www>-prefetched.json` — the prefetched
  candidates with `arxiv_id`, `title`, `abstract`, `authors`, `submitted`, `categories`
  (plus mechanical scores and quality hints you do NOT use for ordering — the order is fixed).
- `${CLAUDE_PROJECT_DIR}/data/cache/week-<YYYY-Www>-rerank-llm/final.json` — **the selection**:
  `top` = `[{arxiv_id, thread, source}]` in served order. `thread` is the thread that owns the
  paper; ownership is a partition, so it is never null and must not be reassigned.

## Workflow

### Step 1 — read everything

`Read` profile.md, profile.json, the prefetched JSON and final.json. Don't skim — the
rationales depend on you holding the profile and each candidate in mind together.

### Step 2 — take the selection as given

`top_papers` = final.json `top`, in that order. Do not re-rank, drop, add or cap it.
If the orchestrator's spawn prompt lists user-pinned papers after the selected ones, append
those (in the listed order) — they are force-included downstream and exempt from the judges.

### Step 3 — write the rationale for EVERY seed

These papers are the seeds ideation will work from; they have already passed the gate, so every
one of them will be used. For each, write:

- **`why_it_matters`** (1–2 sentences) — concrete, specific to *this* researcher's
  threads. Bad: "This paper is about LLM reasoning, which is relevant to your
  work." Good: "Its retrieval-step uncertainty mechanism could be transferred into your tool-augmented reasoning line to enable a capability it currently lacks — calibrated step-level abstention."
  A candidate whose prefetched record says `repo_status: repo_claimed_but_dead` (the paper
  advertises a GitHub repo that is 404 / empty / private) gets that fact noted here; no other
  quality hint is used for anything.
- **`thread`** — the **exact `name` string** of the user-profile thread this pick anchors to
  (one of `profile.threads[i].name`). When final.json gives a non-null `thread`, use it
  verbatim (it is the thread the selection picked the paper for); when it is `null`, assign
  the primary thread yourself. This label drives **coverage**: stratified selection, the
  digest's per-thread grouping and the manifest all key off it. It is ALSO passed to the
  downstream `arxiv-generate` skill as optional flavor context (`thread_context`) — ideation
  is DECOUPLED from threads and only uses it to phrase relevance.
- **`gap`** (1–2 sentences) — a concrete thing this paper does NOT do that a follow-up could attack.
> The `extensibility_verdict` / `extensibility_rationale` that used to be written here moved to
> the `arxiv-claim-judge` skill on 2026-09-20: the seed walk needs the tier to decide whether a
> paper may seed its thread, which is BEFORE you run, and the judge already has the full text open.

**Do NOT** generate `novel_idea_seed` or `seed` fields here. Seed/idea
generation is the job of the `arxiv-generate` skill, run as a separate step
on this output. If you find yourself wanting to write a seed, write
a sharper `why_it_matters` instead — naming the specific sub-claim is more
useful to the downstream ideator than a half-formed seed.

### Step 4 — write the rerank JSON

`Write` the structured result to
`${CLAUDE_PROJECT_DIR}/data/cache/week-<YYYY-Www>-rerank.json` with shape:

```json
{
  "week": "2026-W22",
  "top": [
    {
      "arxiv_id": "...",
      "title": "...",
      "authors": ["..."],
      "categories": ["..."],
      "thread": "thread name (matches profile.threads[i].name)",
      "why_it_matters": "...",
      "gap": "..."
    }
  ],
  "rest": [
    { "arxiv_id": "...", "title": "..." }
  ]
}
```

`top` is final.json's `top` in final order (plus any pinned papers appended), each carrying the
full rationale + extensibility block from Step 3, because `top` IS the Phase 3.6 gate pool.
`rest` is final.json's `rest` in its order with titles copied from the prefetched JSON
(no rationales — they only feed the digest's adjacent-field browsing block, never gate candidates).

### Step 5 — report and stop

Tell the caller (the arxiv-scout orchestrator): the path of the rerank JSON
you wrote, the top titles, and a one-line summary of which threads were
represented. **Do NOT render the digest yourself** — the pipeline runs the
`arxiv-generate` step next (per-paper parallel generation), and the digest is
rendered after that step so it includes the ideation blocks.

## Anti-patterns — do NOT do these

- Do not call any external LLM API. The rationale writer is YOU.
- Do not re-rank, reorder, drop or add papers — final.json is the ranking. The only additions
  are the pinned papers the spawn prompt lists, appended after the selected ones.
- Do not use `rrf_score`, per-list ranks, `quality_tier`, `author_h_max` or `repo_status`
  to change anything about the order; `repo_claimed_but_dead` is only noted in `why_it_matters`.
- Do not write rationales that just paraphrase the abstract.
- Do not generate `novel_idea_seed` or `seed` fields — that's the
  `arxiv-generate` skill's job, run as the next pipeline step.
- Do not render the digest. Ideation runs between rerank and rendering.
