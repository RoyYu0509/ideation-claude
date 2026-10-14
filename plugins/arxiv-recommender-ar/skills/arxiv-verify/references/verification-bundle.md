# The Verification Bundle — on-disk contract (SSOT)

One bundle per candidate: `<data_root>/data/ideations/<week>/bundles/<arxiv_id>-<key>/`.
Shared by arxiv-screen (writes fragments), arxiv-verify (composes bundle.json),
scripts/verify_bundle.py (V0 mechanical recheck), arxiv-recheck (semantic recheck),
and the workflow's finalize (Verification Record). The machine validator is
`scripts/lib/bundle_io.py` — its rules are THE rules; this file explains them.

## Layout

```
bundles/<arxiv_id>-<key>/
  prior-art.json                 # screen stage — the bundle's prior_art object, verbatim
  assets.json                    # screen stage — the bundle's assets array, verbatim
  assets/<name>.listing.json     # asset_listing.sh outputs (real file listings)
  probes/<probe_id>/probe.py     # verify stage — one dir per probe (premise or theory check)
  probes/<probe_id>/stdout.txt   # committed run (probe_run.sh)
  probes/<probe_id>/meta.json    # hashes/runtime/utc (probe_run.sh writes; advisory tamper evidence)
  theory.md                      # verify stage — typed-step derivation (theoretical/both only)
  bundle.json                    # verify stage — machine SSOT, written ONLY via bundle_io.py
  bundle.prev.json               # workflow snapshot before a mechanical bounce rewrite
  recheck-r<N>.json              # V0 output (verify_bundle.py)
```

## bundle.json shape (validated write-time by bundle_io.py)

```json
{
  "schema": 1, "week": "2026-W28", "arxiv_id": "...", "candidate_key": "c0",
  "round_born": 1, "working_title": "...",
  "claim": "<the VERIFIED CLAIM — must equal the generator's ideas[i].claim VERBATIM;
            V0 fails claim_drift otherwise. The verifier may KILL, never re-aim.>",
  "claim_type": "theoretical | empirical | both",
  "prior_art": {
    "queries": [
      { "id": "Q1", "tool": "s2_novelty", "mode": "search", "query": "<verbatim, 3-6 words>",
        "limit": 8, "hits": [ { "title": "...", "arxiv_id": "2402.15419", "year": 2024 } ] },
      { "id": "Q3", "tool": "s2_novelty", "mode": "related", "arxiv_id": "<parent>", "limit": 8, "hits": [] },
      { "id": "Q4", "tool": "websearch", "query": "<verbatim>",
        "findings": [ { "url": "...", "takeaway": "...", "load_bearing": false } ] },
      { "id": "Q5", "tool": "arxiv_web_fallback", "query": "<verbatim>", "note": "<the S2 failure>",
        "hits": [ { "title": "...", "arxiv_id": "...", "year": 2024 } ] }
    ],
    "degraded": false,             // true ONLY when S2 was unreachable and Q* fell back to arXiv directly
    "degraded_reason": "<required when degraded>",
    "diff_table": [
      { "rival": "Title (arXiv:XXXX)", "found_by": "Q1", "same_mechanism": false, "same_task": true,
        "residual_delta": "<one line, quantitative where possible>",
        "source_anchor": "arXiv:XXXX §3.1 / Table 2 p.6" }
    ],
    "dispositions": [ { "hit": "arXiv:YYYY", "class": "rival|adjacent|irrelevant", "why": "<one line>" } ]
  },
  "premises": {
    "rows": [
      { "id": "P1", "premise": "<falsifiable sentence about the WORLD (target/benchmark/data)>",
        "probe_class": "required | deferrable",
        "status": "probed_pass | probed_fail | quote_verified | unverified | deferred",
        "quote": { "page": 4, "section": "4.4", "text": "<verbatim>" },
        "probe": { "id": "P1-spectrum", "dir": "probes/P1-spectrum",
                   "criterion": { "metric": "<what the probe measures, with units>",
                                  "direction": "<=", "threshold": 1.0,
                                  "threshold_src": "src: <anchor>" } },
        "deferred_justification": "<verifier-only, when status=deferred: the VERIFICATION
                                   OBLIGATION — what data/instrument/machine-time settles
                                   it and what a failure would mean. Never a number.>",
        "consequence_if_false": "<one line: what dies>" }
    ],
    "falsifier": {
      "statement": "<the kill criterion>",
      "thresholds": [ { "value": 10, "units": "x", "src": "src: arXiv:XXXX Table 1 p.5" } ],
      "routes_through": ["P1"],
      "limit_analysis": { "can_trigger": "...", "can_fail_to_trigger": "...", "non_circular": "..." }
    },
    "rescope_declarations": []
  },
  "theory": { "path": "theory.md",
              "checks": [ { "step": "T3", "probe_dir": "probes/T3-check" } ] },
  "assets": [
    { "url": "...", "kind": "repo|dataset|checkpoint|benchmark-code", "needed_for": "<one line>",
      "needed_paths": ["gen/*.py"], "listing": "assets/<name>.listing.json",
      "status": "live_verified | stub_or_empty | missing",
      "fallback": "<REQUIRED unless live_verified>" }
  ],
  "artifacts": { "prior_art": "pass|fail", "asset_check": "pass|fail",
                 "premise_probe": "pass|fail|deferred", "derivation_check": "pass|fail|not_applicable" }
}
```

## The probe contract (enforced by bin/probe_run.sh + bundle_io + V0)

- `probe.py`: ≤ ~200 lines, CPU-only, deterministic (`np.random.default_rng(0)`
  — any fixed seed), NO network / NO subprocess (mechanically grepped; a probe
  works from EXTRACTED formulas, it never fetches).
- **Pre-registered criterion**: `{metric, direction, threshold, threshold_src}`
  is committed in the premise row (from the GENERATOR's declaration) BEFORE the
  run — the verifier implements the measurement, it never moves the threshold.
- **Input non-degeneracy assertion** (Phase-0 DISCRIMINATIVE SANITY): the script
  must `assert` its input is not analytically trivial for the premise (e.g. the
  extracted u_exact actually has >1 nonzero mode). A probe that passes on a
  degenerate input is a correspondence FAIL at recheck.
- **Machine verdict**: the LAST stdout line is
  `PROBE_VERDICT: {"id":"<probe_id>","pass":<bool>,"value":<num>,"threshold":<num>,"direction":"<=|>=|<|>"}`
- Run ONLY via `bash bin/probe_run.sh <probe_dir>` (timeout scout.probe_timeout_sec,
  writes stdout.txt + meta.json). V0 replays with `--suffix .replay` and compares
  verdict fields (pass exact, value rtol 1e-6). A verdict that does not reproduce
  is an INTEGRITY kill, not a retry.
- Per-candidate total probe budget: scout.probe_total_budget_sec.

## src anchors (v1 grammar — simple, fetch-verified)

Every quantitative value (falsifier thresholds, residual-delta numbers, expected
deltas) carries a non-empty `src:` anchor. V0 checks PRESENCE only; the recheck
stage checks TRUTH by FETCHING the anchor and transcribing the actual value.
Anchor forms (keep them fetchable):
- `src: arXiv:XXXX vN Table K p.P` — paper table/page (recheck fetches the PDF page)
- `src: probe:<probe_id>` — an executed probe's PROBE_VERDICT value
- `src: derived theory.md T<k>` — a checked derivation step
- `src: <URL>` — a fetchable web source (recheck WebFetches it)
An unfetchable or mismatching anchor is a fabricated-number event → kill.

## theory.md (typed-step derivation; claim_type theoretical/both)

```
T1 [ASSUME]  A1: ... (must appear in the premises rows or the plan's assumptions)
T2 [CITE]    Lemma 3.5 of arXiv:XXXX (p.12) — SCOPE: <one line: what the lemma
             does and does NOT cover>          ← the anti-irrelevant-lemma line
T3 [ALG]     r = 2/(πν) ∈ [0.0064, 0.021] for ν∈[30,100]   → check: probes/T3-check
T4 [INEQ]    ... ≤ ... because ...                          → check: probes/T4-check
T5 [GAP]     <honest hole: what is asserted without proof + why plausible>
```
Every load-bearing [ALG]/[INEQ] step carries a sympy/numpy check probe (3–20
lines, same PROBE_VERDICT contract). Every [CITE] carries its SCOPE line — the
recheck stage checks the USAGE against the stated scope. [GAP] rows are allowed
(honest holes) but a load-bearing step that is really a GAP sold as [CITE]/[ALG]
is proof_broken.

`arxiv_web_fallback` exists for one case: S2 itself is down (the client already
retried with exponential backoff, so a RuntimeError is the service, not pacing).
Then the screener searches arXiv directly and the bundle MUST carry
`degraded: true` + `degraded_reason`. Those queries are not replayable by V0, so
the flag is the provenance: novelty resting on them is weaker evidence, and the
flag is how a gate or a reader ever learns that. Relabelling a fallback query as
`s2_novelty` is a fabrication, not a shortcut — bundle_io refuses an
`arxiv_web_fallback` query in a bundle that is not flagged.

## Kill conditions (who fires them)

| Condition | Stage | kill_reason |
|---|---|---|
| same-mechanism rival, no defensible residual delta | screen / refute | scooped |
| re-tread of a graveyard direction | screen | retread |
| pre-registered premise probe FAILS **on zero-simulation evidence** | verify | premise_failed |
| load-bearing derivation step unprovable-as-stated / circular falsifier | verify / recheck | proof_broken |
| significance below paper_worthy (no revision channel exists) | recheck | insignificant |
| verdict does not reproduce / concealed hit / threshold or claim drift / fabricated number | V0 / recheck | integrity_violation |

`premise_failed` requires evidence of one of exactly three kinds: arithmetic on
the paper's own published numbers, a symbolic/analytic contradiction, or a
refutation read off the paper's real released data. A number produced by a
simulator or synthetic distribution the verifier wrote CANNOT carry a kill —
it marks the premise `deferred` instead (arxiv-verify SKILL Step 2).

Two non-kill outcomes share the table:

| Condition | Stage | outcome |
|---|---|---|
| mechanism stands, but the given verification route does not exist | verify | `rescope` — no certificate, no regeneration_constraint |
| depended asset missing/stub | screen | recorded in `assets` + a fallback; flows to the spec as a constraint |

A kill mints a death certificate (workflow-owned): the direction is SEALED for
this week — regeneration must produce genuinely different directions. There is
NO successor/rescue channel at this layer (owner hard principle, 2026-07-11).
