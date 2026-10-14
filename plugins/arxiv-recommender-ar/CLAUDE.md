# arxiv-recommender — onboarding for Claude sessions

A Claude Code plugin that fetches each week's arXiv papers, ranks them against
the researcher's profile, gates them through a claim/repo judge, and runs the
VERIFIED-KILL ideation loop over the survivors: multi-round generate → screen →
verify (EXECUTED probes) → recheck, where candidates die on executed evidence
(death-certificate regeneration) and one verification-hardened
`/research` plan ships per surviving idea. Outputs (a Markdown digest, an interactive web
report, and refined plans) land under the session's runtime
folder (`AR_DATA_ROOT` → `CLAUDE_PROJECT_DIR` → cwd), never inside the plugin.

The pipeline is **mechanical PREFETCH (RRF over SPECTER2 + BM25 + citation) →
Claude RERANK → deterministic JUDGE GATE (claim/repo, fail-closed) → the
VERIFIED-KILL loop (generate → screen → verify → recheck, ≤ ideation_rounds_max
rounds)**. Claude is the reranker and generator — natively; no external LLM API
is involved. Convergence gates on VERIFICATION ARTIFACTS (executed probes /
replayable prior-art / derivation checks / real listings) — never on tier scores
(owner rule: no LLM numeric scores; tiers retired 2026-07-11).

## Where to look

| You want to… | Read this |
|---|---|
| Use the plugin (setup, weekly cadence) | `README.md` |
| Architecture invariants + JSON data contracts | `ARCHITECTURE.md` |
| The one workflow command | `commands/arxiv-scout-beta.md` |
| What each Claude-reasoning step does | `skills/*/SKILL.md` |
| Python implementation | `scripts/*.py` + `scripts/lib/*.py` |
| **Tune any knob** (parallelism, thresholds, rounds) | `config/config.yaml → scout:` block |
| Tests | `skills/tests/test_*.py` (run via `make test` after `bash bin/setup_venv.sh`) |
| Workflow logic | `workflows/arxiv-scout.js` (A: recommend) + `workflows/arxiv-ideation.js` (B: verified-kill loop) — the LLM-read specs `/arxiv-scout-beta` enacts; both read config/config.yaml at startup |

## Key invariants — 3 highlighted here, 12 total in ARCHITECTURE.md §Architecture invariants

1. **Claude is the reranker.** No external LLM API call for ranking.
2. **Bi-encoders (SPECTER2 / SciNCL) live in prefetch ONLY** — never as the final ranker.
3. **No bio / personal-website scraping.** Publication content only. (Validated: bio context hurts.)

Why each matters + the other 9 invariants are in `ARCHITECTURE.md` §Architecture
invariants.

## Quickstart

```bash
bash bin/setup_venv.sh           # idempotent
make test                        # pytest over skills/tests (12 modules)
```

One workflow command:
- `/arxiv-scout-beta` — weekly: Fetch → Score → Final Rank → Judge Gate → verified-kill ideation (generate/screen/verify/recheck).
  Embeds and enacts `workflows/arxiv-scout.js` (the sole entry point). All knobs (spawn count,
  thresholds, round limits) are in `config/config.yaml → scout:` — edit there to tune the pipeline.
  Produces (under the runtime folder, not the plugin): `data/digests/<week>-scout.md`,
  `data/ideations/<week>/` + `.../refined/`, `data/web/<week>-scout.html`.

To rebuild the research profile (quarterly; v2 since 2026-09-12 — Google Scholar source):
```bash
bash bin/run_py.sh scripts/build_profile_papers.py --scholar-url "<researcher.google_scholar_url>"
# owner sets every entry's decision (self / peripheral / not) in data/profile/paper_candidates.json
bash bin/run_py.sh scripts/build_profile_papers.py --from-list data/profile/paper_candidates.json [--cutoff YYYY-MM-DD]
# then invoke the arxiv-profile skill: it starts scripts/profile_tools.py in the background, writes its parts,
# and runs scripts/profile_finalize.py until the coverage check passes (profile.json is written only then)
bash bin/run_py.sh scripts/profile_finalize.py --check-only [DIR]   # read-only channel × variant table
```

## Notes for the next session

- `.gitignore` excludes `.venv/` and `data/` (runtime artifacts). `config/config.yaml`
  IS tracked — it is the durable, portable single source of truth.
- When in doubt about a JSON shape between Python and a skill, the contracts are in `ARCHITECTURE.md` §Pipeline data contracts.
