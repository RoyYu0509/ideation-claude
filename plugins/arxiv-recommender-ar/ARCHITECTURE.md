# arxiv-recommender — architecture reference

Deep reference. For orientation / quickstart see `CLAUDE.md` (one hop up).

## Architecture invariants — DO NOT VIOLATE

These came out of a validated offline study (incl. SciNUP). Don't relitigate without
running the dev-only `/arxiv-eval` (see `.claude/commands/`; usable only with cwd
inside the plugin) and showing lift.

1. **Two-stage pipeline.** Mechanical PREFETCH (cheap, high recall) → Claude RERANK
   (precision). Never collapse into one stage.
2. **Bi-encoder is prefetch-only.** SPECTER2/SciNCL go into RRF, never as the final
   ranker. They were the weakest method when used as a final ranker.
   **Pooling must be explicit and must match the model's training objective.**
   `prefetch.embedding_pooling` (config.yaml) is threaded into `embeddings.encode`
   and is part of the cache key. Never call `SentenceTransformer(model_name)` bare:
   a hub repo with no sentence-transformers config (allenai/specter2_base is one)
   makes the library silently invent MEAN pooling, while SPECTER2's citation-triplet
   loss is on `[CLS]`. Measured on W31 (1434 papers) the two settings share only
   5/10 of the dense top-10 (Spearman 0.744) — they are not interchangeable.
3. **No external LLM API for ranking.** Claude itself reranks natively. Do not add a
   call to OpenAI / Anthropic API / etc. for the rerank step.
4. **Fused prefetch.** Semantic (SPECTER2) + BM25 + citation + category channels. Since **2026-09-18**
   (owner, EVAL-PLAN amendment #9 — the researcher's labels, 5 formal profiles, 3,239 configurations)
   the default is equal-weight RRF (`prefetch.pool_rule: rrf`) over **the dense channel over the paper
   notes (`dense_query: paper_notes` — each note's "field. method", vectors averaged) + one max-cosine
   channel per thread over its member papers and their shared references, the thread family splitting one
   vote (`thread_fusion: split`) + whole-phrase BM25 over the agent's keywords ∪ the extracted phrases
   (`bm25_query: agent+extracted`) + category** — **no prf** (`use_prf: false`; dense carries the same
   kind of signal) and **no citation channel** (`use_citation_signal: false`: adding it left every recall
   number inseparable while doubling the 0-graded papers in the top 300). This subset has the highest
   GeometricRecall@300 (0.719) AND the highest recall@300 (0.774) of all 2,880 thread-bearing
   configurations. GeometricRecall is the selection metric because plain recall cannot separate
   configurations at K = 300: among arms with the same recall@300 it spans 0.05, since a configuration
   can trade a small category group away for more of the researcher's home field. Since 2026-09-16 the
   **category** channel joins it (`prefetch.use_category_channel`): a candidate scores the summed
   weight of its arXiv categories, where a category weighs how many core own papers carry it, and
   ties take the mean rank. It is the only change that improved every one of 15 profile builds on
   the researcher's 12-week labelled pool (out-of-thread recall +0.047; REPORT §8.4). The dense
   prose query stays out: it lost on 15/15 builds and at 10 threads it silently exceeds SPECTER2's
   512-token limit. The reranker reads the
   whole pool, so pool MEMBERSHIP reaches the product and fusion order does not; under RRF
   every thread channel is one list, so the number of threads sets the SPECTER2 vote share.
   `pool_rule: quota` (2026-09-12, REC-SYSTEM-V2 B3: seats per channel via
   `scripts/lib/pool_select.py`, then an RRF fill) stays as an ablation arm. Don't drop
   channels to "simplify".
5. **Recency weighting.** A thread is `active` iff a member paper was first submitted within
   `profile.active_window_months` (computed by `scripts/profile_finalize.py`, never by the
   agent). Under `pool_rule: quota` only active threads get seats, split by their recent
   output; under the default `rrf` every thread channel votes equally and recency reaches
   the pool only through the PRF centroid (`prefetch.prf_min_year`) — the reranker still
   prefers active threads.
6. **Publication content only.** No bio / personal-website scraping. An ablation in
   the validating study showed bio context HURTS by diluting signal. Reading a publication
   LIST (a Google Scholar profile, a website's paper list) is fine — it yields titles only.
7. **Broad-profile mitigation.** The final select (Phase 3b–3c, `lib/rerank_llm.py`, 2026-09-19
   修订 #11) deals A0's top 100 into groups and asks each group for ONE paper per profile thread,
   then ranks the promoted papers — a thread quota by construction, so a broad researcher's small
   directions cannot be crowded out. (It replaced the per-thread rank-then-merge inside the old
   reranker skill; `scout.multi_thread_threshold` is retired.)
8. **Cap candidates fed to the selection (`scout.prefetch_top_k`, 300 since 2026-09-19).** The prefetch is
   the recall bottleneck; the value lives in `config.yaml`, not in code. Only the first `TOP_K`
   (`scripts/lib/rerank_llm.py`) of the fused order are DELIVERED and eligible to seed a thread — the rest
   of the 300 exist because the evaluated reranking arms read that depth.
9. **Quality signal is staged, never in RRF.** `quality_signal.py` is a separate
   annotation layer that runs after RRF fusion; it surfaces to Claude as a tiebreaker
   only. Do not merge quality scores into the RRF formula to "simplify".
10. **One seed per research thread, by ownership, not by quota arithmetic (2026-09-20).** Every
    delivered paper belongs to the thread that ranks it highest (`scripts/lib/thread_seed.py`), and a
    thread's seed is the first paper it owns that passes the gate. The partition is why no two threads
    can claim one paper. Do not reintroduce a promotion target, a returned-set size or a padding rule:
    the rule has no free parameters and that is the point.
11. **The seed walk is deterministic Python + gate verdicts, not agent reasoning.** The ordering lives in
    `scripts/lib/thread_seed.py`; the accept/reject comes from the judge cache. Do not migrate
    thread-selection logic into agent prompts — empirically unstable. (`coverage_select.py` and the
    `coverage_mode` / `mmr_lambda` / `rotation_enabled` knobs are retired and read nowhere: taking one
    paper per thread is what they approximated.)
12. **`config/config.yaml` is the single source of truth — code holds ZERO defaults.**
    Every tunable value lives in `config.yaml` (tracked in git) with an explicit value.
    `scripts/lib/config.py` reads each key with `_req` (no `.get(k, default)`); the JS
    workflow reads via one strict Python load + `req()` (no `?? default`). A missing or
    invalid key crashes the loader and names the key — never a silent fallback. `io.*`
    operational constants are injected into the low-level clients by `lib/runtime.py`
    (auto-called by `load_config`). Secrets stay in env vars only. Do not reintroduce an
    inline default anywhere — add the key to `config.yaml` instead. The embedding backend
    is `prefetch.embedding_backend` (`local`|`hf_api`), not an env var.

## Pipeline data contracts

These JSON shapes are stable interfaces between the Python scripts and the skills.
Changes here must be reflected in all consumers.

### `data/profile/papers.json`

```json
{
  "s2_author_id": "string",
  "author_name": "string or null (null for a website-only profile)",
  "fetched_at_utc": "ISO-8601 string",
  "papers": [
    {
      "paper_id": "S2 paper ID",
      "arxiv_id": "string or null",
      "title": "string",
      "abstract": "string or null",
      "year": 2024,
      "venue": "string or null",
      "categories": ["cs.LG", ...],
      "reference_ids": ["S2 paper IDs", ...]
    }
  ]
}
```

Since 2026-09-12 the Scholar path (`build_profile_papers.py --scholar-url` → owner-confirmed
`paper_candidates.json` → `--from-list [--cutoff]`) writes the same file with, on top:
`source: "scholar"`, `scholar`, `name_forms` (the researcher's full name as written in arXiv
author lists), `cutoff`, `coverage`; and per paper `key` (what profile threads reference),
`first_date` (arXiv first-version date), `primary_category`, `peripheral` (owner-marked: on
record, never a thread member, adds no category) and `date_uncertain`. On this path
`categories` are real arXiv categories (the legacy S2 path stores S2's coarse labels).

### `data/profile/` — the profile directory  *(schema_version 3 since 2026-09-16)*

A profile is built **once** and must support every recall channel and every ablation variant of it
(building one costs the agent 200–300k tokens). What each channel × variant needs, and how it selects its
inputs, is defined in exactly one place — **`scripts/lib/channel_spec.py`** — which the coverage check
(`profile_finalize.py`), the production channels (`prefetch.py`) and the ablation runtime
(`report-v2/ablation/profile_view.py`) all read; `scripts/lib/profile_io.py` is the one reader of a profile
directory.

| File | Written by | Merged into profile.json |
|---|---|---|
| `papers.json` | `build_profile_papers.py` (owner-confirmed list) | no — input |
| `parts/paper_notes.json` | arxiv-profile agent — `{key, field, method, keywords}` per core paper, each keyword printed in that paper's title or abstract | yes |
| `parts/threads.json` | agent — `{name, summary, papers}` | yes (plus computed stats) |
| `parts/recent_direction.json` | agent | yes |
| `parts/keywords_extracted.json` | `profile_tools.py` — `lib/keyphrases` against the newest weekly pool | yes (`keywords`) |
| `parts/categories.json` | `profile_tools.py` | yes (`arxiv_categories`) |
| `ref_abstracts.json` | `profile_tools.py` — S2 abstracts of references cited by ≥ 2 core papers | no — companion |
| `citation-graph.json` | `profile_tools.py` → `build_citation_graph.py --if-stale` | no — companion |
| `profile.md` | agent — the prose the reranker reads | no — companion |
| `profile_check.json` | `profile_finalize.py` — errors, warnings and the coverage table | no |
| `profile.json` | `profile_finalize.py` — **only when nothing blocks** | — |

Every tool output and companion carries the sha256 of the papers.json it was built from; a stale one is
refused.

```json
{
  "schema_version": 3,
  "finalized_by": "profile_finalize.py/<date>-v3",
  "finalized_at": "ISO-8601",
  "as_of": "2026-06-15",
  "papers_sha256": "…",
  "paper_notes": [{"key": "…", "field": "≤ 8 words", "method": "the core method it develops",
                   "keywords": ["1–5 phrases printed in its title or abstract"]}],
  "threads": [
    { "name": "<core method> for <field or object>", "summary": "1 sentence", "keywords": [],
      "papers": ["<papers.json key>", "..."],
      "status": "active", "n_members": 3, "n_recent": 2, "last_date": "2026-01-10",
      "emerging": false, "n_title_only": 0 }
  ],
  "recent_direction": "1 paragraph (prose only; ranking uses `status`)",
  "keywords": ["phrases EXTRACTED from the own papers"],
  "keywords_source": "extracted",
  "keywords_note": "how they were extracted",
  "keywords_pool": {"file": "week-….json", "sha256": "…", "size": 1768},
  "arxiv_categories": ["math.NA", "..."],
  "arxiv_categories_note": "how the categories were chosen"
}
```

**The coverage check.** `profile_finalize.py` builds the would-be profile.json and runs
`channel_spec.coverage`: one row per channel × variant (dense d0/dN · prf recency · thread members /
members_refs · bm25 b1–b4 · category · refs · citation), each **ok**, **EMPTY** (the raw materials are
complete but this researcher's data gives the rule nothing to select) or **MISSING**. Every MISSING row
blocks, and so does an EMPTY row on a variant production runs under the current config; nothing falls back
to another variant. `profile_finalize.py --check-only [DIR]` prints the same table for any existing profile
directory, writes nothing, and exits 1 if a row blocks.

**Which variant production runs** is config: `prefetch.bm25_query` (`extracted` → b4, `agent` → b1; every
v3 profile stores both) and one pinned PRF design — every core paper, weighted
`0.5 ** (months since first version / prefetch.prf_half_life_months)`. The v2 channel set requires
`schema_version` 2 or 3 **and** `finalized_by`; a production channel whose input the profile cannot supply
stops the run. A 2026-09-12 profile (no `finalized_by`) must be rebuilt; a pre-v2 profile still runs with
`--channel-set legacy`. Only member papers with an abstract feed a thread's semantic channel.

**How the thread lists enter the fusion** is config too: `prefetch.thread_fusion` (`lib/thread_fusion.py`,
2026-09-16). Each thread is its own RRF list, so a K-thread profile casts K SPECTER2 votes against one for
every other channel. `per_thread` (default, the behaviour before the key) · `split` (each 1/K) · `sqrt`
(each ∝ √member papers, mean 1) · `best` (the K lists collapse into one `thread_best` list by each paper's
sorted per-thread ranks). Anything but `per_thread` needs channel_set v2 and pool_rule rrf; prefetch and the
ablation runtime both call `thread_fusion.apply`, and `rrf.fuse` takes the resulting per-list `weights`.

The thread key is **`name`** (what the profile writer emits). `prefetch.py` also
accepts the legacy `label` and warns if neither is present — it must never fall back
to a constant, because identical names collapse the per-thread rank-lookup entries.

### `data/cache/week-<YYYY-Www>-candidates.json`

```json
{
  "week": "2026-W22",
  "window_days": 7,
  "fetched_at_utc": "ISO-8601",
  "categories": ["cs.LG", ...],
  "self_exclusion": { "names": ["lowercased name", ...], "dropped": ["arxiv_id", ...] },
  "candidates": [
    { "arxiv_id": "...", "title": "...", "abstract": "...",
      "authors": ["..."], "submitted": "ISO-8601", "categories": ["..."] }
  ]
}
```

`self_exclusion` records the self-author filter: the names matched (papers.json `author_name`
∪ `researcher.author_aliases`) and the IDs dropped. `names: []` means no name was known and
nothing was excluded. Pools written before 2026-09-11 lack the key and were never checked.

Produced by `oai_ingest.py` (v0.9+; was `rss_ingest.py` in v0.8, `build_shared_cache.py`
before). A pool holds only papers whose FIRST version was submitted in the half-open window
[end − `window_days`, end) (UTC dates; end = the run date, or `--end-utc` for a backfill).
`submitted` is that first-version (v1) timestamp, taken from an arXivRaw pass. OAI-derived
candidates also carry the `arXiv` format's raw `created`/`updated` — `<created>` there is the
LATEST version's date, so never filter on it. `comment`/`doi` are populated when present. Extra
fields are ignored by consumers that read by key. The OAI ingest is STATELESS — no
accumulator file.

### `data/cache/week-<YYYY-Www>-prefetched.json`

```json
{
  "week": "2026-W22",
  "prefetch_top_k": 50,
  "rrf_k": 60,
  "candidates": [
    { "arxiv_id": "...", "title": "...", "abstract": "...", "authors": ["..."],
      "submitted": "...", "categories": ["..."], "rrf_score": 0.123,
      "dense_rank": 4, "bm25_rank": 11, "citation_rank": null }
  ]
}
```

Ordered by `rrf_score` descending. Per-list ranks may be null when a candidate isn't
in that list's top-K. Since 2026-09-12 every candidate also carries `channel_ranks`
({channel: rank}) and `seated_by` (the channel that seated it, or `fill` / `rrf` /
`pinned`); the top level carries `channel_set`, `pool_rule`, `seats`, `thread_fusion` and `citation_mode`
(the mode the citation channel ran in, `coupling` | `graph`; null when the channel was
disabled by `use_citation_signal: false` or `--no-citation` — a channel that ran but got zero
hits keeps its mode and sets `used_citation_signal: false`).

### `data/cache/week-<YYYY-Www>-channels.json`  *(2026-09-12)*

Written by every prefetch run: each channel's full ranking (`channels: {name: [arxiv_id, ...]}`; every
`thread_i` list is kept, plus `thread_best` when `thread_fusion: best` collapsed them),
`thread_labels` ({`thread_i`: thread name}), `seats`, `channel_set`, `pool_rule`, `thread_fusion`, `citation_mode`.
Offline ablations and the bench read this file; they never re-derive the channels.

### `data/profile/citation-graph.json`  *(2026-09-12, citation_mode graph)*

Written ONCE per profile by `scripts/build_citation_graph.py` (after `papers.json`); read by
`prefetch.py` only when `prefetch.citation_mode: graph`.

```json
{ "schema_version": 3, "seed_rule": "core", "papers_sha256": "<sha256 of the papers.json it was built from>",
  "built_utc": "...", "alpha": 0.85, "discount": "inv_log1p_citation_count",
  "versions": { "networkx": "3.6.1", "scipy": "1.18.0" },
  "n_seeds": 38, "n_nodes": 13643, "n_edges": 18724, "n_seeds_without_refs": 4,
  "seeds": ["<s2 id>", ...],
  "out_edges": { "<source s2 id>": ["<reference s2 id>", ...] },
  "nodes": { "<s2 id>": { "ppr": 1.2e-4, "citation_count": 170000, "weight": 1.0e-5 } } }
```

`weight = ppr * 1/log(1 + max(citation_count, 1))` is what a candidate collects per reference
(`lib/citation_graph.py`). `out_edges` (sources only: seeds + layer 2; layer 3 never has
out-edges) lets an audit re-derive the walk from the file. Seeds are the CORE papers with an S2 id
(`channel_spec.graph_seed_papers`; peripheral papers never seed the walk — schema 3, 2026-09-17). Seed edges come from papers.json
only — a seed with empty `reference_ids` stays a dangling seed (counted in
`n_seeds_without_refs`, warned at build), never back-filled from S2. `papers_sha256` is a
lock: prefetch REFUSES a graph whose sha does not match the current papers.json, whose
schema/seed rule/discount differ, or whose node table / seeds / out_edges are inconsistent (hard error,
never a silently dropped channel; only the S2 fetch itself may degrade the channel).

### `data/cache/week-<YYYY-Www>-landscape.md`  *([REMOVED in v0.6+])*

The shared field-view prefix block was removed. Ideation is now per-paper and
self-contained: each generation agent receives only its assigned paper + the
researcher profile, and field/competitor breadth is the `arxiv-generate` skill's own
per-paper scan — there is no shared prefix and no landscape file is written.
Selection is governed only by `scout.top_n_papers`. See the Phase 3 note in
`workflows/arxiv-scout.js` ("Landscape.md ... REMOVED").

### `data/cache/week-<YYYY-Www>-judge-cache.json`  *(v0.6+)*

Per-candidate judge-verdict cache for the Phase 3.6 gate, keyed by `arxiv_id`.
Written incrementally as each candidate is judged so a crash-resume within the
same week replays cached verdicts (and their side effects) instead of re-spawning
the judges — the repo clone/run is the most expensive step and must never be paid
twice for one week. Delete the file to force re-judging (e.g. after retuning gates).

```json
{
  "2501.12345": {
    "result": { "ok": true, "why": "pass", "penalize": false },
    "conclusions": { "claim_verdict": "pass", "claim_strength": "solid",
                     "claim_rationale": "...", "repo_verdict": "pass" },
    "claims": [ { "claim_id": "...", "description": "...", "metric": "..." } ],
    "promotion": { "repo_status": "repo_active", "repo_url": "..." }
  }
}
```

`conclusions`/`claims`/`promotion` are null when the candidate produced none.

### `data/cache/week-<YYYY-Www>-gated-pool.json`  *(v0.6+)*

The Phase 3.6 gate OUTPUT — the ≤`scout.top_n_papers` survivors that passed every
applicable judge (this is NOT the larger candidate pool). It is both the Phase-4
ideation set and the resume boundary: a resume author reads this file to learn
which papers survived the gate. (The seeds the walk selected, before rationales, are in the
scratch file `week-<W>-seeds.json`; the per-thread candidate orders come from
`scripts/lib/thread_seed.py order`.)

```json
[
  { "arxiv_id": "...", "title": "...", "abstract": "...", "authors": ["..."],
    "categories": ["..."], "thread": "...", "why_it_matters": "...", "gap": "...",
    "extensibility_verdict": "natural_followup", "extensibility_rationale": "...",
    "original_rank": 7 }
]
```

### `data/ideations/<YYYY-Www>/evidence-<arxiv_id>.json`  *(v0.3+)*

Per-paper sidecar to the ideation JSON, written by the `arxiv-generate` skill
alongside the ideation JSON (rounds 2+ write `evidence-<id>-r<R>.json`). Captures
the distilled Tier-2+ work product for the downstream verify/recheck stages.

```json
{
  "arxiv_id": "...",
  "week": "...",
  "pdf_quotes": [
    {"page": 4, "section": "Method 3.2", "quote": "...", "why_useful": "..."}
  ],
  "websearch_findings": [
    {"url": "...", "takeaway": "..."}
  ],
  "rejected_candidates": [
    {"working_title": "...", "why_rejected": "..."}
  ],
  "cross_thread_hints": [
    {"thread": "<other-thread-label>", "connection": "..."}
  ]
}
```

Empty arrays = quality failure (the skill enforces minimums per field).

### `data/cache/week-<YYYY-Www>-scout.json`  *(v0.4+)*

Phase 4 manifest written after all ideation subagents complete. Maps each
ideated paper to its output paths so the digest renderer and Phase 5 can
locate files without scanning the filesystem. Each paper carries
`original_rank` — its 1-based position among the seeds, in the order the threads
were served (surfaced in the digest + web report).

```json
{
  "week": "2026-W22",
  "ideations": [
    {
      "arxiv_id": "...",
      "title": "...",
      "extensibility_verdict": "natural_followup",
      "original_rank": 7,
      "ideation_path": "data/ideations/2026-W22/2501.12345.json",
      "evidence_path": "data/ideations/2026-W22/evidence-2501.12345.json"
    }
  ]
}
```

### `data/cache/week-<YYYY-Www>-quality-gate.json`  *(v0.4+)*

The optional human-prune handshake before deep verification (verified-kill loop,
2026-07-11). Written after round 1's screen — it lists every candidate so the user
can prune which ones may be PROMOTED to the (expensive) verify stage.

```json
{
  "week": "2026-W22",
  "generated_at_utc": "ISO-8601",
  "usage": "copy to week-<W>-quality-gate-decision.json, trim selected_ideas, re-run",
  "selected_ideas": [
    { "arxiv_id": "2501.12345", "key": "c0", "claim_preview": "..." }
  ]
}
```

### `data/cache/week-<YYYY-Www>-quality-gate-decision.json`  *(v0.4+, HUMAN-written)*

To prune which candidates may be promoted to verification, copy the request file
above to this name, trim `selected_ideas`, then re-run. Only `arxiv_id` + `key`
(the ledger candidate key) are read; `claim_preview` is ignored. Absent = all
candidates eligible; unparseable = logged, all proceed.

```json
{ "selected_ideas": [ { "arxiv_id": "2501.12345", "key": "c0" } ] }
```

### `data/cache/week-<YYYY-Www>-ideation-ledger.json`  *(v0.9, verified-kill)*

THE ideation SSOT of the 2026-07-11 verified-kill loop (replaces
`week-<W>-refine-ledger.json`): per-paper status
(`active | converged | exhausted_honest | exhausted_budget`), per-candidate
trajectory (`generated → screened → dormant/verifying → verified → converged`,
or `killed / shelved / merged / error`), and the GRAVEYARD of death
certificates (`kill_reason ∈ scooped | premise_failed | proof_broken |
asset_dead | insignificant | retread | integrity_violation`, each with the
killing evidence + replay pointer). Persisted after EVERY stage — the
crash-resume boundary and /learn's false-kill audit material. Exact shape:
the ledger section of `workflows/arxiv-ideation.js` (SSOT).

### `data/ideations/<YYYY-Www>/bundles/<arxiv_id>-<key>/`  *(v0.9, verified-kill)*

One VERIFICATION BUNDLE per candidate: `prior-art.json` + `assets.json`
(screen stage), `probes/<id>/{probe.py,stdout.txt,meta.json}` (EXECUTED
premise/theory probes, run only via `bin/probe_run.sh`), `theory.md`,
`bundle.json` (machine SSOT, written only via the validating writer
`scripts/lib/bundle_io.py`), and `recheck-r<N>.json` (the zero-token V0
engine's report, `scripts/verify_bundle.py`). Full contract:
`skills/arxiv-verify/references/verification-bundle.md` (SSOT).

### `data/profile/identity_check.json`  *(v0.4+)*

Written by `scripts/verify_s2_identity.py` (Phase 0b). Used by the Phase 0c
gate to show the user which S2 author was matched.

```json
{
  "candidate_author_name": "Jane Doe",
  "candidate_author_id": "102316879",
  "s2_total_count": 42,
  "website_count": 18,
  "match_count": 15,
  "needs_confirmation": true
}
```

`needs_confirmation` is false if there is exactly one candidate with
match_count / website_count ≥ 0.7 (high-confidence auto-confirm).

### `data/profile/identity_decision.json`  *(v0.4+)*

Written after the Phase 0c `AskUserQuestion` gate. Consumed by Phase 0d
(`build_profile_papers.py`) to set the confirmed S2 author ID.

```json
{
  "confirmed_s2_author_id": "102316879",
  "confirmed_by": "user",
  "decided_at_utc": "2026-05-29T10:00:00Z"
}
```

## When you change something

- Touching prefetch math (RRF, dense, BM25, citation, category)? Run the dev-only `/arxiv-eval`
  (cwd inside the plugin) on a known-good cutoff and confirm nDCG@10 didn't regress.
- Touching the rerank skill prompt? Same.
- Adding a new candidate signal? Wire it as another input list to RRF; don't
  hand-merge.
