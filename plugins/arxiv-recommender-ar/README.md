# arxiv-recommender

A Claude Code plugin that recommends the top-N newest arXiv papers most relevant to your
own research each week (N configured via `scout.top_n_papers`), then runs the
verified-kill ideation loop over the survivors — candidates die on EXECUTED
evidence, one verification-hardened `/research` plan per surviving idea — delivered as a
Markdown digest and an interactive web report.

## How it works

Mechanical PREFETCH → Claude RERANK, the field-standard high-recall + high-precision
two-stage retrieval pipeline.

1. **Profile** is built once (refreshable) from your Semantic Scholar publication
   history. Claude condenses it into a natural-language research profile, structured
   research threads, and recent-direction emphasis. Publication content only — no bio,
   no website scraping.
2. **Weekly ingest** pulls new arXiv submissions in your categories over the last 7
   days.
3. **Prefetch** fuses three cheap signals — SPECTER2 dense cosine, BM25 sparse, and
   citation overlap with your recent work — via Reciprocal Rank Fusion into the top-
   `prefetch_top_k` candidate set (a mechanical funnel cut).
4. **Rerank** is Claude itself: native reasoning over the profile + the prefetched
   candidates, producing a best-first ordering with a per-paper categorical
   extensibility verdict and a "why this matters to you" rationale.
5. **Judge → verified-kill ideation → publish.** Survivors of a claim/repo judge gate
   enter the kill loop (generate → screen → verify with executed probes → recheck);
   the survivors, plus each paper's 死亡名单, ship as research-
   ready `/research` plans. Outputs: a dated Markdown digest, an interactive web
   report, and the refined plans — all written under
   the session's runtime folder (see Data layout), never inside the plugin.

The bi-encoder lives in prefetch only — never as the final ranker. No external LLM API
is used for ranking; Claude reasons natively.

## Setup

```bash
# 1. Install the plugin (from a Claude Code session)
# Add this directory as a local plugin per your Claude Code plugin docs.

# 2. Bootstrap the Python venv (idempotent; safe to rerun)
bash bin/setup_venv.sh

# 3. Configure
# edit config/config.yaml: set researcher.s2_author_id to your numeric S2 author ID

# 4. Build your research profile (one-shot, ~1-3 minutes for prolific authors)
bash bin/run_py.sh scripts/build_profile_papers.py
# then invoke the arxiv-profile skill in a Claude Code session: it writes the profile parts + profile.md,
# runs scripts/profile_tools.py and scripts/profile_finalize.py (profile.json appears once every check passes)

# 5. (Optional) Pre-fetch this week's candidates into the cache.
#    /arxiv-scout-beta fetches on demand in Phase 1, so this is only to warm the
#    cache. The DEFAULT fetch is oai_ingest.py (OAI-PMH; VPS/datacenter IPs).
#    On a Mac/residential IP set io.ingest_method: api to use build_shared_cache.py.
bash bin/run_py.sh scripts/oai_ingest.py

# 6. Get this week's recommendations + research plans
/arxiv-scout-beta
```

For an unattended weekly cadence, see "Scheduling the centralized fetch" below.

## Commands

- `/arxiv-scout-beta` — the weekly workflow, and the single entry point. Embeds and
  enacts `workflows/arxiv-scout.js` phase by phase (Fetch → Score → Final Rank →
  Judge Gate → the verified-kill ideation loop) via main-agent +
  subagents. Produces (all under the runtime folder, see Data layout):
  - `data/digests/<week>-scout.md` — ranked digest with ideas
  - `data/ideations/<week>/` — per-paper ideation JSON + evidence sidecars
  - `data/ideations/<week>/refined/` — verified survivors' plans (Verification Record + `/research` seeds); `bundles/` holds the executed-probe evidence
  - `data/web/<week>-scout.html` — interactive web report

**Tuning:** all pipeline knobs (parallelism, thresholds, round limits) live in
`config/config.yaml → scout:`. Edit that file — no code changes needed.

## Scripts (non-Claude)

- `scripts/oai_ingest.py` — the DEFAULT weekly arXiv fetch (OAI-PMH; works from
  VPS/datacenter IPs). Optionally run from cron / launchd / `/schedule` to warm the
  shared cache (see "Scheduling the centralized fetch" below).
- `scripts/build_shared_cache.py` — the api-mode ALTERNATIVE (arXiv Python API; for
  Mac/residential IPs). Selected by `io.ingest_method: api`.

## Scheduling the centralized fetch

`/arxiv-scout-beta` fetches on demand in Phase 1 (a freshness gate skips re-harvest
when the cache is recent), so scheduling is **optional** — it just warms a shared
cache so N users cost one arXiv batch per week. The fetch script is chosen by
`io.ingest_method`: the default `oai_ingest.py` (OAI-PMH), or the api-mode
alternative `build_shared_cache.py`. Either one:

- Walks every registered profile (`data/users/*/profile/profile.json` if present,
  else `data/profile/profile.json`).
- Computes the union of their `arxiv_categories`.
- Fetches one batch from arXiv per week and writes
  `data/cache/week-<YYYY-Www>-candidates.json` under the runtime folder.
- Is idempotent (skips if the current week's cache is fresh, unless `--force`); the
  api-mode fetcher is additionally 429-safe (60s → 180s → 600s outer backoff).

To schedule, pick one option below. Replace `<PLUGIN_ROOT>` with the plugin's
absolute path (in this monorepo: `.../plugins/arxiv-recommender-ar`) and use the
fetch script that matches your `io.ingest_method` (`scripts/oai_ingest.py` by
default; `scripts/build_shared_cache.py` for `api`):

### Option A — macOS launchd (recommended for local)

Drop this into `~/Library/LaunchAgents/com.example.arxiv-fetch.plist` (adjust
paths, label, and weekday/hour as needed):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.example.arxiv-fetch</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string><PLUGIN_ROOT>/bin/run_py.sh</string>
    <string><PLUGIN_ROOT>/scripts/oai_ingest.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string><PLUGIN_ROOT></string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>1</integer>  <!-- 1 = Monday -->
    <key>Hour</key><integer>7</integer>
    <key>Minute</key><integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/tmp/arxiv-fetch.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/arxiv-fetch.log</string>
</dict>
</plist>
```

Then:

```bash
launchctl load ~/Library/LaunchAgents/com.example.arxiv-fetch.plist
launchctl start com.example.arxiv-fetch   # fire once now to smoke-test
tail -f /tmp/arxiv-fetch.log
```

### Option B — crontab

```cron
# Every Monday at 07:00 local
0 7 * * 1 cd <PLUGIN_ROOT> && bash bin/run_py.sh scripts/oai_ingest.py >> /tmp/arxiv-fetch.log 2>&1
```

### Option C — Claude Code `/schedule`

Schedule a recurring routine from Claude Code that invokes the script:

```
/schedule weekly 'cd <PLUGIN_ROOT> && bash bin/run_py.sh scripts/oai_ingest.py'
```

### Monitoring

- Success: the script writes `data/cache/week-<YYYY-Www>-candidates.json` and exits 0.
- Failure (e.g., arXiv 429 persisted through all backoffs): the script writes
  `data/cache/week-<YYYY-Www>-FETCH-FAILED.json` (with timestamp + error +
  traceback) and exits 1. Cron / launchd can alert on the non-zero exit.

### Weekly recommendation cadence (downstream of the fetch)

Once the shared cache is in place, run the weekly workflow:

- `/arxiv-scout-beta` inside Claude Code, or
- A second cron entry that invokes Claude Code headlessly with `/arxiv-scout-beta`.

## Configuration knobs

`config/config.yaml` is the **single source of truth** for every tunable value —
it is tracked in git and holds an explicit value for every key. There are **no
defaults in code**: a missing or invalid key makes the loader crash and name the
key, rather than silently substituting a hidden default. Secrets stay in env vars
(`HF_TOKEN`, `SEMANTIC_SCHOLAR_API_KEY`/`S2_API_KEY`, `GITHUB_TOKEN`/`GH_TOKEN`).

Key sections:
- `scout:` — the primary tuning surface: funnel sizes (`prefetch_top_k`, `top_n_papers`; the gate pool `rerank_return_n` is DERIVED at load, not a key), categorical gate tiers, round limits, cache age.
- `prefetch.embedding_backend` — `local` (sentence-transformers) or `hf_api` (HuggingFace Inference API); `prefetch.embedding_model` picks the model.
- `io:` — operational constants (S2/arXiv/GitHub timeouts, retries, rate limits).

## Data layout

All runtime artifacts go under `<runtime-folder>/data/`. The runtime folder is the
session's `AR_DATA_ROOT` (else `CLAUDE_PROJECT_DIR`, else the cwd) — **NOT** the plugin
directory, which is read-only at runtime (only `.venv/` is written there). This keeps
two parallel instances isolated and lets the plugin run from any external folder.

```
data/
├── profile/           # papers.json, profile.md, profile.json
├── cache/             # embeddings, PDFs, weekly candidate/prefetched/judge-cache/gated-pool/scout JSONs
├── ideations/         # per-week ideation JSONs, evidence sidecars, refined plans
├── digests/           # YYYY-Www-scout.md weekly digests
└── web/               # YYYY-Www-scout.html interactive reports
```

## Why this exact design

The architecture comes from a validated offline study including the SciNUP benchmark.
Key load-bearing decisions:

- One-shot retrieval has inherently low recall — a fused prefetch is mandatory.
- The reranker is candidate-set-limited; spend the recall budget on prefetch fusion.
- Bi-encoders (SPECTER2, SciNCL) underperform as final rankers — they belong in
  prefetch only.
- Claude as a native reranker (extended thinking over profile + candidates) beat BM25,
  RM3, a BGE cross-encoder, and PRP-style LLM rerankers; tied an RRF ensemble on
  nDCG@10.
- Recommending only NEW papers (post-training-cutoff) sidesteps citation-memorization
  confounds.

See `CLAUDE.md` for internal conventions and the v2 backlog.
