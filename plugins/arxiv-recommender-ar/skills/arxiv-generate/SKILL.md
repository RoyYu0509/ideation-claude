---
name: arxiv-generate
description: Candidate generator for the arxiv-ideation verified-kill loop — the boldest paper-worthy research directions one arXiv paper itself enables, each with PRE-REGISTERED verification obligations (premise probe criteria, src-tagged falsifier thresholds, asset needs). Use when workflow B's Generate stage spawns it, once per gated paper per round; round 2+ is Regeneration mode against the graveyard.
allowed-tools: Bash, Read, Write, WebSearch
---

## Job — you are a candidate GENERATOR for ONE paper

You are spawned per paper per round. The paper reached you because the rerank
step judged it relevant to the researcher's threads. Your job is to generate
the boldest, most **paper-worthy** directions THE PAPER ITSELF enables: extend
its own frontier, challenge an assumption it makes, or open a genuinely new
direction it makes possible (cross-field is welcome). Judge every candidate by
significance alone.

**Your output is FROZEN once written.** Downstream, an independent verifier
implements and EXECUTES the probes you pre-register, an independent screener
hunts prior art, and an independent rechecker transcribes every number you
cite. There is NO revision channel: a candidate whose premise fails or whose
claim drifts is KILLED, not fixed — so the claim, thresholds, and premises you
write here are commitments, not drafts. Write them like a pre-registration.

You produce a structured ideation JSON: a mechanism-level paper summary, a
one-sentence relevance note, and 1–!`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" scout.candidates_per_round` concrete candidates, each with the
required sub-fields below.

Quality goal: every idea must clear two bars at once. (1) **Specificity** — a
methodologist could sketch the first experiment from your `method_sketch`
alone, without re-reading the paper. (2) **Significance** — a top-venue
reviewer could plausibly call it a *new contribution to the field*, not an
incremental follow-up. Every idea must leave a NEW artifact behind (a new mechanism / capability / theorem / direction / newly-discovered phenomenon) — not a confirmation, measurement, or optimization of something already reported. If your idea reads "combine X with Y" without saying what new mechanism the combination creates, or is a foreseeable re-application, or its only deliverable is to verify / measure an existing pattern, throw it away. (A transfer that *does* yield a new capability — 领域A→领域B 有奇效 — is exactly what to keep.)

## Inputs

You will be invoked with a per-paper input JSON (passed via the spawn prompt
or written to a path you receive). Required fields:

```json
{
  "arxiv_id": "2605.25710",
  "title": "Machine Learning Multiscale Interactions",
  "abstract": "...",
  "authors": ["..."],
  "categories": ["physics.chem-ph", "cond-mat.mtrl-sci", "cs.LG"],
  "why_it_matters": "1-2 sentences from the rerank step",
  "thread_context": "Machine-learned interatomic potentials (ACE, generalization, UQ)",
  "profile_md_path": "${CLAUDE_PROJECT_DIR}/data/profile/profile.md",
  "profile_threads_path": "${CLAUDE_PROJECT_DIR}/data/profile/profile.json",
  "week": "2026-W22",
  "round": 1,
  "candidates_per_round": 3,
  "output_path": "${CLAUDE_PROJECT_DIR}/data/ideations/2026-W22/2605.25710.json",
  "evidence_path": "${CLAUDE_PROJECT_DIR}/data/ideations/2026-W22/evidence-2605.25710.json"
}
```

## Regeneration mode (round ≥ 2)

When the spawn prompt carries a GRAVEYARD (this paper's death certificates from
earlier rounds), you are in Regeneration mode. Each certificate names a dead
direction, its kill reason, the VERIFIED killing evidence (a probe output, a
scooping rival, a broken derivation, a dead asset), the `dead_belief` that
died, and a `regeneration_constraint`. Rules:

1. **Dead directions are SEALED.** Produce genuinely DIFFERENT directions — a
   rephrasing of a dead mechanism, or any candidate whose success still rests
   on a certified `dead_belief`, will be killed as a retread by the independent
   screener. Honor every `regeneration_constraint` (e.g. "probe the benchmark
   spectrum FIRST" → that premise is probe_class=required in your new candidate).
2. **Kills are information.** A premise_failed certificate tells you a fact
   about the world (e.g. "this benchmark's spectrum sits off the variety") —
   generate FROM that fact: directions it enables are often stronger than the
   one it killed.
3. **Honest exhaustion beats padding.** If no genuinely different paper-worthy
   direction exists, return `has_new_directions: false` with a one-sentence
   `exhaustion_note_zh`（中文）— an honest zero is a valid, ledgered outcome
   (owner hard rule: no revival channels; a padded candidate wastes a full
   verification chain). Do NOT write an output file in this case.

The workflow passes rounds 2+ a fresh `output_path` (`<id>-r<R>.json`) — the
same schema; candidate keys continue across rounds in the ledger.

Note: `evidence_path` is mandatory in the arxiv-scout v0.3+ pipeline. If the
caller omits it, default to `<output_path-dir>/evidence-<arxiv_id>.json`.

`thread_context` is the **OPTIONAL** string label of the user-profile thread the
reranker matched this paper to (matches a `threads[i].label` in `profile.json`).
It is optional context — use it only to phrase `why_relevant` in the
researcher's voice.

## Workflow

**Language:** All content fields written to the ideation JSON — `paper_summary`, `why_relevant`, `working_title`, `claim`, `method_sketch`, `significance_note` — **must be in Chinese (中文)**. `sharp_falsifier` may use English for technical thresholds with their citations. The evidence sidecar (`pdf_quotes`, `websearch_findings`, etc.) stays in English.

### Step 1 — understand the PAPER before ideating

The seed for every idea is the paper's mechanism — **not** the profile. Do the
paper-mechanism step first and treat it as primary:

- **(Primary) Re-read the paper metadata**: title, abstract, why_it_matters. Form
  an initial mechanism-level mental model: what does this paper actually do, in one
  paragraph, in your own words? What does it *enable* that it does not itself pursue?
  This mechanism model — not the profile — is what you ideate from.
- **(Optional) Profile skim**: `Read` `profile_md_path` / `profile_threads_path`
  ONLY to phrase `why_relevant` in the researcher's voice.
- **(Optional) `${CLAUDE_PROJECT_DIR}/data/profile/papers.json`**: the authoritative
  lookup IF (and only if) `why_relevant` happens to cite a specific user paper. Not
  required — most ideas will not name a user paper.

### Step 2 — build mechanism depth (mandatory minimum: Tier 2)

Abstract-only ideation produces hand-waving. Every paper you ideate has already passed an extensibility gate — it deserves real depth. The minimum required depth is **both** Tier 2 steps below. Tier 1 (abstract only) is never acceptable.

**Tier 2 — WebSearch + targeted PDF (mandatory for every paper)**:

1. Run 1–2 WebSearch queries to find existing summaries or mechanism
   explanations:
   - `"<method-name>" mechanism` (e.g., `"MuSE" mechanism atomistic`)
   - `<paper-title-keywords> explained` (blog posts, Twitter threads)
   - `<arxiv_id> review`
   Note what the community already understands; don't re-explain what's already well-covered.

2. Fetch the PDF and read targeted sections:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/bin/fetch_arxiv_pdf.sh" <arxiv_id>
   ```
   Then use the `Read` tool with the `pages` parameter to read the abstract + Method/Approach + Results/Conclusion sections (typically pages 2–7). Do NOT read the whole PDF.

3. **Read how the benchmarks/data are CONSTRUCTED (mandatory).** Locate and read
   the experimental-setup subsection that says how the paper's test problems or
   datasets are BUILT — manufactured/analytic solutions (which u_exact? is the
   source term reverse-engineered as f := Lu?), data-generation protocol (how
   many independent trajectories/seeds? what splits?), benchmark provenance
   (released by whom, with what error bars?). This is where load-bearing
   premises live and die: a 2026-07 postmortem found an entire 11.7h research
   run wasted because ideation cited a benchmark's error numbers without ever
   reading that its manufactured solution's spectrum could not satisfy the
   idea's core premise — a fact printed in the paper's own setup section.

Record `depth_signal: "websearch_used"` after completing both steps.

**Tier 3 — extended PDF reading** (for mechanism-dense papers only): if Method pages 2–7 are insufficient to understand the key algorithmic step, also read the appendix / supplemental (use `pages` parameter for the specific pages). Record `depth_signal: "pdf_fetched"`. Use Tier 3 for ~1 in 3 papers at most.

### Step 2.5 — Competitive Landscape Scan (mandatory)

This step is DIFFERENT from Tier 2: Tier 2 builds *mechanism depth* (how does this paper work?). Step 2.5 builds *landscape breadth* (who else is working on this problem?). Both are required.

1. **Read the paper's Related Work AND Conclusion/Future-work sections** using the PDF already fetched in Step 2. Use the `Read` tool with the `pages` parameter to locate them (typically the 2–3 pages before/around the Conclusion — scan the table of contents or page 2 to find the sections). Goal: understand (a) what the authors themselves identify as the closest prior work, (b) what open problems they explicitly leave for future work, and (c) build the **DOOMED LIST** — every follow-up direction the authors themselves announce or obviously set up (future-work items, "we leave X to future work", the natural next benchmark/regime). The authors and their competitors will do these themselves; an idea on the doomed list is dead on arrival no matter how well it scores.

2. **Run the mechanical scholarly scan (PRIMARY landscape modality — zero-token, denser than WebSearch)**:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/bin/run_py.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/s2_novelty.py" --mode related --arxiv-id <arxiv_id>
   bash "${CLAUDE_PLUGIN_ROOT}/bin/run_py.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/s2_novelty.py" --mode search --query "<3-6 core-problem keywords>"
   ```
   Keep `--mode search` queries SHORT (3–6 keywords — long queries return `[]`); run a second query variant if the first misses. `--mode related` returning `[]` means S2 doesn't know the paper yet — rely on the search variants. Add at most 1 WebSearch, only for what S2 cannot see (blogs, OpenReview threads, announced-but-unpublished follow-ups).

3. **Record findings in `websearch_findings`** (same evidence sidecar, no new field needed — S2 hits carry a `url` like any web source, and each entry still needs its required `takeaway` line or the validating writer rejects it). Add a `"type": "landscape"` key to each landscape entry to distinguish from Tier 2 mechanism findings.

4. **Update `depth_signal`**: set to `"landscape_scanned"` after completing this step. `depth_signal` priority: `"pdf_fetched"` (Tier 3) > `"landscape_scanned"` (Step 2.5) > `"websearch_used"` (Tier 2 only). Use the highest tier reached.

5. **Build `landscape_context`** from your findings (written to the ideation JSON in Step 5a):
   - `direction_saturation`: `"low"` (0–1 close papers), `"medium"` (2–3), `"high"` (4+)
   - `known_competitors`: the subset of papers from your landscape searches AND the paper's
     Related Work that directly compete on the SAME TASK as this paper — not all related papers,
     only those a reader would say "this does the same thing." If nothing qualifies, use `[]`.
   This object is what refine will use to determine whether a later novelty check represents
   new information or confirmation that the direction is exhausted.

### Step 3 — write paper_summary + why_relevant

Before ideating, write the two summary fields:

- **`paper_summary`**: 3–5 sentences, mechanism-level. State (a) what the paper actually computes / proves / measures, (b) the key methodological choice that distinguishes it from prior work, (c) the headline empirical result. **Not an abstract paraphrase** — a researcher's-eye reduction that's tighter than the abstract.
- **`why_relevant`**: Written in Chinese. A **light, descriptive** note on why this paper is on the researcher's radar — purely context for the digest. It may reference a thread, a past paper, or simply the research area; use whichever is genuinely accurate. If the natural link is just field-level, say so (`"这篇文章推进了 [领域] 的前沿。"`) and move on. (If a specific published paper genuinely is the closest link, you may name it via `papers.json`: `"与你的《[论文标题]》（arXiv:XXXXXXX）同属 [方向]。"`)

### Step 4 — produce 1–!`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" scout.candidates_per_round` candidates

Generate ideas with a two-phase protocol: first write out all draft candidates explicitly, then review the full landscape comparatively before selecting.

#### Phase 4a — explicit draft (do this before any quality scoring)

Write out about !`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" scout.ideate_brainstorm_count` draft candidates in a lightweight scratchpad format, spanning the three PAPER-centric types below (not necessarily one of each). **Do not skip to scoring yet.** Every candidate is seeded by THE PAPER's mechanism — not the profile:

- **`new_direction`**: Open a genuinely new research direction this paper makes possible — a question, capability, or cross-field bridge the paper *unlocks* but does not itself pursue. The **highest-ambition** type. Valid only if the unlocked direction is paper-worthy on its own (a top-venue reviewer would call it a new contribution, not a follow-up). Cross-field bridges count, but the bar is that the newly-enabled capability is itself significant — not merely that the export is technically possible.
- **`direct_extension`**: Advance the paper's own frontier with a *new artifact* — a theorem it did not prove, or a mechanism that first reaches a regime no prior method handles. Confirming or measuring that the paper's pattern still holds in a harder regime does not qualify. Judge it by **what new thing the field gains**, not by who is positioned to do it.
- **`challenge_and_improve`**: Take an assumption the paper makes as *motivation*, and propose an original new mechanism that works where the assumption breaks — the deliverable is the new mechanism, not the experiment that exposes the gap. An idea whose only output is to show / measure / attribute the failure is not an idea.

For each draft candidate, write:
```
Candidate N:
- idea_type: new_direction | direct_extension | challenge_and_improve
- working_title: ~10-word title
- one_line_claim: one falsifiable sentence
- rough_significance_status: paper_worthy | borderline | incremental (quick estimate against the Significance categories below)
```

This scratchpad lives in your reasoning only — do **not** write it to any JSON file. Its purpose is to force the full set of distinct candidates into view before any selection happens.

#### Phase 4b — panoramic review and selection

Now that the full candidate landscape is visible, do a comparative review:

1. **Landscape quick-discard**: cross-reference all drafts against Step 2.5 findings. Any draft that closely matches a paper found in the landscape search is immediately discarded — record it in `rejected_candidates` with `why_rejected: "prior art found: [title] (arXiv:XXXX)"`. Equally discard any draft matching the Step 2.5 **DOOMED LIST** (a direction the paper's own authors announce as future work, or an obvious next step several landscape hits are already crowding): being first to an idea its creators already announced is not a contribution — record it with `why_rejected: "doomed follow-up: [the author quote / crowding evidence]"`. If 3+ recent papers are working on the same direction, prefer candidates in less contested directions and note this in `notes`.

2. **Apply five quality gates to remaining candidates** — now with full panoramic context, not one-by-one in isolation:
   - Does it have a sharp `claim` (something that could turn out true OR false, not "explore Y")?
   - Can you write a concrete `method_sketch` (named baseline + dataset + metric + one operational step)?
   - **Does it clear the significance floor?** It passes only if a top-venue reviewer could plausibly call it a *new contribution to the field*, not an incremental follow-up. It must satisfy at least one of: (a) it would change how practitioners do something; (b) it resolves or reframes an open question the paper leaves; (c) it establishes a result or capability that does not yet exist in the literature. "Apply method A in setting B" fails this gate **unless** B is genuinely harder and the result is non-obvious. Categorize it on the **Significance categories** below; a candidate that is `incremental` (narrow re-application, no new mechanism) is discarded here.
   - Can you name a `sharp_falsifier` with a **justified threshold** (see `sharp_falsifier` description below)?
   - Does it have a clear `contribution_type` — `new_theorem`, `new_method`, `new_application` (a cross-domain transfer yielding a capability neither field had — 奇效; a foreseeable port is NOT one), or `new_empirical_finding` (a phenomenon *newly discovered* here — NOT confirming / measuring a pattern already reported)? An idea whose only novelty is the bare "combine X with Y" with no new mechanism arising fails this gate.

3. **Rank survivors by significance and pick the best combination**: sort all candidates that passed all five gates by significance category (`paper_worthy` > `borderline` > `incremental`). Select the top !`"${CLAUDE_PLUGIN_ROOT}/bin/cfgval.sh" scout.candidates_per_round` — this is a **comparative selection across the full survivor set**, not "keep the first one that passed." Write full details only for selected candidates. All discarded candidates (both landscape-rejected and gate-failed) go to the evidence sidecar's `rejected_candidates`. **Prefer 1 bold paper-worthy candidate over several incremental ones — padding to hit a count is a quality failure** (every padded candidate wastes a full independent verification chain downstream). If none pass all five gates, set `has_journal_level_idea` to `false` and explain why in `notes` in **Chinese**, naming specifically which gate(s) failed — e.g., "候选 idea 均为窄再应用（incremental），未能通过显著性门。"

Categorize on the Significance categories and the "what is NOT a research idea" test — load both from `anti-examples.md`.

Judge significance **independently of rigor and independently of fit** — where an idea sits relative to the user's work does not change its significance.

Each idea's required sub-fields:

- **`idea_type`**: one of `"new_direction"` | `"direct_extension"` | `"challenge_and_improve"` (see brainstorm step above for definitions).
- **`contribution_type`**: one of `"new_theorem"` | `"new_method"` | `"new_application"` | `"new_empirical_finding"`. Must name the specific novel artifact the paper would contribute.
- **`significance_status`** (one of `paper_worthy` | `borderline` | `incremental`): the Significance category from the gate above. Be honest — this is context the downstream screen/recheck stages re-assess independently. `paper_worthy` = a new mechanism / principle / framing, or a substantive transfer where a new capability or guarantee emerges (a top-venue reviewer could call it a new contribution); `borderline` = a modest extension or verification where no new capability emerges; `incremental` = a narrow re-application or pure optimization — should have been discarded at the significance gate.
- **`working_title`** (~10 words): "<noun phrase>: <specific intervention>". No colons-and-subtitles. No "A study of ...".
- **`claim`** (1–2 sentences): the falsifiable proposition. Format: "X achieves [specific property] under [scope]; the path to test this is [one-step operationalization]."
- **`method_sketch`** (2–3 sentences): the operational outline. Name a baseline (against which the comparison happens), name a dataset/benchmark (the substrate), name a metric (the falsifier signal). Mention the one algorithmic step that's actually novel.
- **`significance_note`** (1 sentence): **why this idea is paper-worthy** — what NEW thing the field gains if it succeeds, stated at the contribution level. Name the specific literature gap it closes or the specific capability that would newly exist. Bad (no field-level contribution): "接到你 a/c coupling 方向的高阶界子主张。" Good (states the contribution): "首次给出 soft-pooling 界面的可计算收敛阶下界——此前文献只有经验观察，没有 a priori 速率。"
- **`sharp_falsifier`** (1 sentence): the specific signal that would refute, with a justified threshold. Every quantitative number must cite its source in parentheses — valid sources: (a) theoretical lower bound from the literature, (b) baseline performance level on the named benchmark, (c) minimum acceptable in the application context. No source = arbitrary threshold = invalid falsifier. **The idea's own derivation is NOT a valid source when that derivation rests on an unverified `load_bearing_premises` entry** — that is a circular falsifier (the threshold assumes the thing the test is supposed to establish); anchor the threshold premise-independently or tie it explicitly to the premise's probe.
  Good: "If the log-log slope drops below 2.5 (vs the O(h^3) theoretical rate), the claim is refuted."
  Bad: "If improvement is less than 15%." (no source for 15%)
  Bad (circular): "≥10× (from our own measure-fraction estimate)" where the estimate presumes the unverified premise.
- **`falsifier_thresholds`** (REQUIRED, machine-readable mirror of the numbers in `sharp_falsifier`): `[{ "value": 2.5, "units": "log-log slope", "src": "src: O(h^3) theoretical rate, arXiv:XXXX Thm 2" }]`. These are FROZEN: the V0 engine mechanically fails any downstream bundle whose thresholds differ (`threshold_drift`) — the silent-relaxation channel does not exist anymore, so anchor them somewhere you can defend.
- **`routes_through`** (REQUIRED, may be `[]`): the ids (`P1`, `P2`, …, by row order) of the `load_bearing_premises` your falsifier's threshold justification depends on. Every routed premise is automatically probe-REQUIRED — the verifier will implement and EXECUTE its probe before anything else happens.
- **`load_bearing_premises`** (1–3 entries, REQUIRED): the empirical facts about the WORLD — the target/benchmark/data, never the method's own construction — that the claim's success stands on. Ask: "if this idea fails honestly, which belief about the world was wrong?" Each entry:
  ```json
  { "premise": "<one falsifiable sentence about the target/benchmark/data>",
    "status": "verified | unverified",
    "source": "<REQUIRED when verified: p.X, §Y: \"verbatim quote\" from the parent paper (or a named external source)>",
    "probe": "<REQUIRED when unverified: a concrete, cheap check (e.g. 'compute the benchmark u_exact's spectrum and its distance to the characteristic variety')>",
    "probe_class": "required | deferrable",
    "criterion": { "metric": "<what the probe measures, with units>", "direction": "<=",
                   "threshold": 1.0, "threshold_src": "src: <where the threshold comes from>" },
    "consequence_if_false": "<one line: what dies>" }
  ```
  **PRE-REGISTRATION (the verified-kill contract):** `probe_class` is `required` when (a) the falsifier `routes_through` this premise, or (b) it asserts anything about a named benchmark/dataset's CONSTRUCTION (manufactured-solution formula, spectrum, data-generation protocol, sample counts). A `required` premise MUST carry a complete `criterion` — the independent verifier IMPLEMENTS and EXECUTES the probe against YOUR criterion, and a failing probe kills the candidate with no appeal. Register the criterion you would bet the run on: threshold moved later = mechanical integrity kill. An honest `unverified`+`deferrable` row (with probe) is fully acceptable for genuinely weekly-cost-undecidable facts — a missing premise, or a `verified` with no real quote, is not. Assumptions about the method's own machinery do NOT belong here.
- **`asset_manifest`** (REQUIRED; `[]` only if the idea genuinely depends on no external artifact): every repo / dataset / checkpoint / benchmark-code the method_sketch or falsifier depends on. Each entry:
  `{ "url", "kind": "repo|dataset|checkpoint|benchmark-code", "needed_for": "<one line>", "needed_paths": ["gen/*.py", "data/*.h5"], "status": "verified_live | stub_or_empty | missing | unverified", "evidence": "<what you saw, or 'declared — screen verifies'>" }`.
  **`needed_paths` is the load-bearing field**: the file globs your method_sketch ACTUALLY depends on. The independent screener fetches the REAL recursive file listing and kills the candidate (`asset_dead`) if a depended asset is a stub with no fallback — a 2026-07 postmortem: a promised benchmark repo was a 2-line stub; the run burned ~25h discovering it. `status: "unverified"` is acceptable here (screen verifies mechanically); a quick liveness check via `bash "${CLAUDE_PLUGIN_ROOT}/bin/validate_github_url.sh" "<url>"` is encouraged when you are already unsure. If you know an asset is dead, say so and put the fallback in `method_sketch` — no first-step or falsifier may assume a dead asset exists.

### Step 5a — write the ideation JSON

Build the ideation dict per the schema in `references/ideation-schema.md` (load it now), then run the validating writer below.

Do **not** hand-write the final JSON to `output_path` — that is how broken files
(unescaped `"` in Chinese strings) and schema drift (a missing `paper_summary`,
an old `title`/`falsifier` field name) reach disk and get dropped by the
renderer. Instead write your draft to a scratch file and run the validating
writer, which re-serializes it (escaping handled) and fails loudly on any
missing field:

1. `Write` the dict above to `/tmp/ideation-<arxiv_id>.json` (the scratch file —
   NOT inside the ideations dir).
2. Run:
   ```
   bash ${CLAUDE_PLUGIN_ROOT}/bin/run_py.sh ${CLAUDE_PLUGIN_ROOT}/scripts/lib/ideate_save.py \
     --in /tmp/ideation-<arxiv_id>.json --out <output_path> --title "<title>"
   ```
   (substitute `<arxiv_id>`, `<output_path>` and `<title>` from your input JSON;
   `--title` backfills the required top-level `title` if your draft omitted it.)
3. If it exits non-zero, read the printed reason, fix the named field (or the
   JSON syntax), and rerun — up to twice. A non-zero exit means **nothing was
   written**; never fall back to writing the JSON by hand. Proceed only once it
   prints the written path.

### Step 5b — write the evidence sidecar JSON (mandatory)

The downstream verify/recheck stages and the auto-research seed→HANDOFF pipeline need more
than your polished ideation JSON — they need the distilled work product of your
Tier 2+ research: the PDF quotes and landscape findings that ground a later
novelty check and research plan.

Build the sidecar dict per `references/evidence-schema.md` (load it now), then write it
through the SAME validating writer as Step 5a — never hand-write the final file:

1. `Write` the dict to `/tmp/evidence-<arxiv_id>.json` (scratch).
2. Run:
   ```
   bash ${CLAUDE_PLUGIN_ROOT}/bin/run_py.sh ${CLAUDE_PLUGIN_ROOT}/scripts/lib/ideate_save.py \
     --kind evidence --in /tmp/evidence-<arxiv_id>.json --out <evidence_path>
   ```
3. Non-zero exit ⇒ fix the named field / JSON syntax and rerun (same discipline as 5a).

**Minimum quality bar** (do not return empty arrays — empty evidence = quality failure):
- `pdf_quotes`: at least 2 entries, drawn from the targeted PDF pages you read.
- `websearch_findings`: at least 2 entries total — at least 1 from Tier 2 mechanism search + at least 1 from Step 2.5 landscape search (tagged `"type": "landscape"`). A `websearch_findings` array with only mechanism entries means the landscape scan was skipped — that is a quality failure.
- `rejected_candidates`: at least 1 entry (of the candidates you brainstormed in Step 4, at least 1 was cut). Ideally includes at least 1 entry with `why_rejected` citing prior art if any landscape paper was found close to a candidate idea.
- `cross_thread_hints`: `[]` is fine — populate only when a genuine cross-paper angle exists that the downstream stages or the seed→HANDOFF pipeline could use. Since ideation no longer anchors to a thread, do not manufacture hints; an empty array needs no apology.

If you set `has_journal_level_idea: false`, you still write the evidence
record — it stays valuable to the downstream stages and /learn (rejected_candidates
shows what didn't work; cross_thread_hints might still surface a usable
cross-paper angle).

### Step 6 — report

Return the structured confirmation the workflow's schema demands: `arxiv_id`,
`round`, `candidate_count`, `has_new_directions` (false ONLY for an honest
Regeneration-mode exhaustion, with `exhaustion_note_zh`; in round 1 a no-idea
paper uses `has_journal_level_idea: false` in the JSON and reports
`candidate_count: 0`), `output_path`, `evidence_path`, `depth_signal`, and any
salient warning in `notes`. Stop.

## Anti-patterns — do NOT do these

Drawn from the failure modes the user explicitly diagnosed in earlier
digest runs:

- ❌ **"Combine A's X with B's Y"** without saying how the combination is
  operationalized. If you can't sketch the first experiment, don't write
  the idea.
- ❌ **Generic tails**: "test the method's generalization", "evaluate on
  more benchmarks", "extend to higher dimensions". These are not ideas,
  they are research-task placeholders.
- ❌ **Significance-free idea**: it passes the mechanism gates (sharp claim,
  concrete method_sketch, falsifier) but no top-venue reviewer would call it
  a new contribution. Specificity is necessary but NOT sufficient — the idea
  must also *matter*. A specific-but-incremental idea (`borderline` or
  `incremental`) is still a failure.
- ❌ **Soft falsifier**: "if the method doesn't perform well", "if results
  are inconclusive". Name the specific metric and the specific threshold
  that would refute.
- ❌ **Falsifier with arbitrary numbers**: "if improvement < 15%" with no
  stated source for 15%. Every quantitative threshold needs a justification
  in parentheses.
- ❌ **Abstract paraphrase as paper_summary**: if your summary uses the
  paper's own framing, it's not adding value. Reduce to the researcher's
  eye.
- ❌ **Padding to hit a count**: writing extra ideas when only 1 passes the
  quality bar. Set `has_journal_level_idea: false` and explain in `notes`
  rather than writing weak ideas.
- ❌ **Shrinking ambition to fit the user**: narrowing a bold direction so it lands inside the user's existing thread or toolbox. Generate the boldest paper-worthy idea the paper enables, judged by significance.
- ❌ **Incremental padding of the candidate set**: selecting a Tier C narrow follow-up into the final candidates when a Tier A/B draft exists. Selection is by significance, never by which draft is safest or best-fits the researcher.
- ❌ **Bare juxtaposition as the contribution**: an idea whose sole novelty is "combine X with Y" with no new mechanism emerging fails the contribution gate. (A transfer that produces a capability neither field had — 领域A→领域B 有奇效 — IS a `new_application` contribution; only the foreseeable port fails.)
- ❌ **Author-owned follow-up**: an idea the paper's own future-work section (or its obvious setup) already announces. The authors are months ahead of you on their own roadmap — that direction is DOOMED for an outsider, however sharp your falsifier. Ideate from what the paper *enables but does not see*, never from what it *promises to do next*.
- ❌ **Hand-waved method_sketch**: must name baseline + dataset + metric.
  If you can't name one of those three, you don't yet have a concrete
  enough idea.
- ❌ **Abstract-only ideation**: never produce ideas from the abstract
  alone. Minimum depth is WebSearch + targeted PDF sections.
- ❌ **Premise smuggling**: stating the load-bearing premise as a fact inside
  the claim's framing ("对谱能量集中在特征簇上的色散型问题…") instead of
  listing it in `load_bearing_premises` with a source or a probe. If success
  depends on it and you didn't verify it, it goes in the ledger as
  `unverified` — classification-by-assertion is the #1 diagnosed failure mode.
- ❌ **Method-construction "premises"**: filling `load_bearing_premises` with
  facts about the method's own machinery (jitter variance, SVD threshold).
  Those are checkable from the paper and belong in the evidence sidecar; the
  ledger is for facts about the world the idea BETS on.
- ❌ **Asset faith**: citing "the paper's open-sourced benchmark/code" in
  method_sketch without an `asset_manifest` entry declaring `needed_paths`.
  "Code available upon acceptance" READMEs and stub repos are common; the
  screener's real file listing will kill the candidate, so declare what you
  actually depend on and carry a fallback when in doubt.
- ❌ **Vague pre-registration**: a `required` premise whose `criterion` has a
  woolly metric ("performs well") or an unanchored threshold. The verifier
  implements EXACTLY what you registered — an untestable criterion is a
  mechanical bounce at best, a kill at worst.
- ❌ **Threshold hedging**: registering a falsifier threshold looser than your
  own derivation supports, to survive verification. The recheck stage
  transcribes your `src:` anchors — a threshold your anchor does not support
  is a fabricated-number integrity kill.
- ❌ **Empty evidence record**: returning `pdf_quotes: []`,
  `websearch_findings: []`, and `rejected_candidates: []` is a quality
  failure — it tells the downstream stages you skipped the work the
  Tier 2 floor mandates. The evidence sidecar is the canonical record of
  the PDF + WebSearch effort you did; populate it from what you actually
  read.

## Reference output

A full worked example is in `references/example-ideation.md`.
