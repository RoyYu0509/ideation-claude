---
name: arxiv-profile
description: Profile builder (v3 superset) — from the owner-confirmed papers.json, writes one note per paper (field, core method, grounded keywords), the research threads and the recent direction as separate part files plus profile.md, while the deterministic tools run in the background; then runs profile_finalize.py, which checks that every recall channel and every ablation variant can be derived and only then merges profile.json. Publication content only; no bio.
allowed-tools: Bash, Read, Write
---

## Job

You build, **once**, the profile every downstream step reads. It must support every recall channel and
every ablation variant of it, so nobody ever has to run this skill again just to test another
configuration — a build costs 200–300k tokens.

- **You write (judgement):** a note for every paper, the research threads, the recent direction, and
  profile.md — each to its own file.
- **Scripts write (never you):** the extracted retrieval phrases, the arXiv categories, the reference
  abstracts, the citation graph (`scripts/profile_tools.py`), and profile.json itself
  (`scripts/profile_finalize.py`, which merges everything only after its coverage check passes).

## Inputs

- `${CLAUDE_PROJECT_DIR}/data/profile/papers.json` — each paper has a `key`, `title`, `abstract`
  (null = title-only record), `first_date` / `year`, `venue`, `categories` and `peripheral` (owner-marked:
  stays on record but is not the researcher's direction). Top-level `cutoff` (may be null).

## Outputs (all under `${CLAUDE_PROJECT_DIR}/data/profile/`)

| File | Content |
|---|---|
| `parts/paper_notes.json` | `[{"key", "field", "method", "keywords"}]` — one per non-peripheral paper |
| `parts/threads.json` | `[{"name", "summary", "papers"}]` |
| `parts/recent_direction.json` | `{"recent_direction": "<one paragraph>"}` |
| `profile.md` | the prose the reranker reads |

Never write any other file under `parts/`, and never write profile.json.

## Hard guardrails — DO NOT VIOLATE

1. **Publication content only.** Titles, abstracts, venues, dates. No name, affiliation, position, awards,
   homepage blurbs; ignore any bio the user volunteers.
2. **No external LLM API calls.** Do all the reading and writing yourself.
3. **A thread is a group of the researcher's own papers.** Never a topic without member papers.
4. **Every non-peripheral paper first submitted within the last !`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" profile.active_window_months` months**
   (before papers.json `cutoff`, else today) belongs to exactly one thread. Older papers may join a thread
   or stay out. Peripheral papers join no thread and get no note; marking a paper peripheral is the
   owner's call, not yours.

## Who reads what

| Field | Read by |
|---|---|
| `paper_notes[].field`, `.method` | the dense channel's grounded query (dN); re-grouping ablations |
| `paper_notes[].keywords` | phrase BM25 when config `prefetch.bm25_query: agent`; the b1/b2/b3 ablations |
| `threads[].papers` | one semantic channel per thread: a candidate's highest similarity to the member papers that have an abstract |
| `threads[].name`, `summary`, `recent_direction`, profile.md | the reranker and the idea generator; the d0 dense query |
| computed by scripts | extracted phrases (BM25 by default), categories (weekly fetch + category channel), reference abstracts (refs ablations), citation graph |

## Step 0 — Start the deterministic tools in the background

They need only papers.json. Start them now with the Bash tool's `run_in_background` option and carry on:

```
bash "${CLAUDE_PLUGIN_ROOT}/bin/run_py.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/profile_tools.py"
```

## Step 1 — A note for every paper

`Read` papers.json in full. For every non-peripheral paper write one entry of `parts/paper_notes.json`:

- **`key`** — from papers.json.
- **`field`** — the field, or the class of problems or systems, the paper works on (at most 8 words).
- **`method`** — the core method the paper **develops or analyses**; not a standard tool it merely uses.
- **`keywords`** — 1–5 phrases naming that field and that core method, each **printed in this paper's own
  title or abstract** in that form. A phrase counts only as a whole — all its words consecutive and in
  order (hyphens and a plural s are normalized). Prefer the standard names the field also prints over
  coinages of this one paper. No generic words ("model", "framework", "data", "analysis", "neural
  network", "deep learning", "novel"). A title-only record takes its phrases from its title.

## Step 2 — Threads and the recent direction

Group the papers into !`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" profile.min_threads`–!`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" profile.max_threads` threads, reading them off your notes: a thread gathers the papers that
develop **the same kind of core method for the same kind of problem**. A thread with a single recent paper
is legitimate (an emerging direction); do not fold it into an unrelated thread. Title-only records join
threads by their titles. For each thread write to `parts/threads.json`:

- **`name`** — `<core method> for <field or object>`, at most 10 words and precise: the specific technique
  family and the specific object, never a bare field or a generic word ("machine learning", "simulation",
  "AI", "modeling"). The reranker tags every pick with it verbatim.
- **`summary`** — one concrete sentence: the methods developed and what they are applied to.
- **`papers`** — the member papers' `key`s.

Then write `parts/recent_direction.json`: one paragraph on the last two years, from the dates — first the
directions that continued (the threads with the most recent papers), then what is new; a thread with a
single paper gets at most one clause.

## Step 3 — profile.md

First person, research content only, **at most !`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" profile.md_max_chars` characters**, in exactly this shape (every
researcher's profile has the same shape, so profile length is never a confound):

- one opening paragraph on the overall research program. Cover the threads in decreasing order of member
  count, giving each words roughly in proportion to its member count and never more than about twice its
  share; early on, name the disciplines of the two arXiv categories that carry the most of the
  researcher's papers (count them in papers.json `categories`); then name the methods that recur across
  several threads in your notes;
- one section per thread: `### <name>`, two sentences, then a bullet list of its member paper titles
  (newest first, at most three);
- a closing `### Recent direction` paragraph with the content of your recent direction.

## Step 4 — Finalize and fix

When the background tools have finished (`parts/_tools.json` lists all four steps), run:

```
bash "${CLAUDE_PLUGIN_ROOT}/bin/run_py.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/profile_finalize.py"
```

It checks your parts, the tools' parts, and a coverage table — every recall channel × variant must be
derivable — and writes profile.json only when nothing is missing.

- **Exit 1** → read the errors in `data/profile/profile_check.json`.
  - Your parts (a recent paper in no thread or in two, an unknown key, a thread without a summary, a paper
    without a note, a note with no field / method, a keyword count outside 1–5, **a keyword its paper does
    not print** — named with the paper and the phrase, profile.md too long): fix the part and re-run.
  - A tool's part (missing, failed, or built from another papers.json): re-run the tools, e.g.
    `profile_tools.py --only ref_abstracts`. If a tool keeps failing — no weekly candidate pool, Semantic
    Scholar unreachable — **stop and report it**. Never write a tool's file yourself and never work around
    a missing one.
- Repeat until it exits 0.

## Step 5 — Report

One short paragraph: how many papers you noted (with / without abstract, peripheral skipped), each
thread's name with the status the script computed (active / legacy / emerging), the categories and the
number of extracted phrases the tools produced, and that the coverage table passed. Then stop.
