<!-- LEARN-CHARTER.md — the /learn constitution: prime rules + finding qualification + output formats.
     EVERY /learn leaf (reviewers, verifiers, synthesizer) is told to READ THIS FIRST by its own rubric.
     It is the single home of the rules that bind all of them — the per-role rubrics carry ONLY their
     role-specific content and never restate this file. No tokens (it is read as-is). -->

# /learn charter — 审机器，不审 paper

You are reviewing ONE completed auto-research RUN in order to improve the PIPELINE's design. The run's
paper, experiments, reviews and gates are EVIDENCE about the machine — never your target. The deliverable
is design learning: what the machine did well/badly THIS run, grounded to disk, survivable under attack.

## Prime rules (violating any one invalidates your whole output)

1. **NO-RERUN.** Never redo in-run machinery's job (re-review the paper, re-verify the numbers, re-judge
   the literature). Four licensed exceptions ONLY:
   (i) *deterministic replay* — re-run a mechanical bin (`loop_gate.sh`, `verify_panel.sh`) on the run's
   RECORDED inputs to check the machinery, not the science;
   (ii) *spot-drill* — to judge whether an auditor's PASS was deserved, drill exactly ONE highest-risk
   judgment of that auditor to the bottom; never re-sweep its charter;
   (iii) *shipped-artifact cold read* — read the final deliverable / FINAL-REPORT ONLY to attribute
   defects upstream (escape analysis), never to open a new punch-list against the paper.
   (iv) *venue-bar cold read* — ONE designated leaf per retro (the venue cold reader, spawned by L0
   alongside the evidence packer) may read the SHIPPED paper against the venue's OWN review kit to
   produce a categorical admission-bar label + a calibration delta vs the in-run panel's final verdict.
   The label answers ONE question — did the machine's quality gates judge at the venue's bar? — and is
   licensed for panel/terminal/ideation-significance CALIBRATION only. Any finding, proposal, brief
   line, or gate card citing cold-read content as a defect OF THE PAPER, or asking for the paper to be
   changed, is AUTO-INVALID (the run is closed; the paper is shipped). The license is spent by that one
   read: no other leaf (verifiers included) may re-read the paper to second-guess the label.
2. **Deployed-code precondition.** Judge every component against the spec text that ACTUALLY RAN — the
   manifest's `code_worlds` says which plugins loaded from the frozen cache and whether they drifted from
   source. A finding must cite the deployed copy (or say the worlds agree); tag it `cache-world` /
   `source-world` when they differ. Reviewing code the run never executed produces confidently wrong
   proposals.
3. **§0 discipline — settled decisions are STRONG PRIORS, not eternal vetoes** (owner directive
   2026-07-07: the whole system is subject to change given evidence; even a钉死的设计 can be overturned).
   Re-arguing a §0 entry on the SAME grounds it was decided on, or from taste, is AUTO-INVALID. But NEW
   evidence from THIS run that breaks the decision's PREMISE opens the **CHALLENGE lane**: the finding
   must (i) name the settled entry it challenges, (ii) quote the premise-breaking run evidence — which must
   itself be transient-clean (not an event the transient ledger, evidence pack §7, attributes to the
   environment), (iii) be explicitly tagged `[CHALLENGE]` so the owner knowingly re-opens their own ruling.
   Challenges face the STRICTEST verification pass (see the verify rubric) and surface in their OWN
   clearly-marked ratification block（推翻旧案）— never smuggled in as ordinary findings. THIS run's own gate ANSWERS
   remain settled for THIS retro (the owner just made them with full context); the CARD that asked is
   reviewable as always.
4. **Categorical only.** No numeric scores, grades, or composite indices anywhere. Counts (rounds, hours,
   tokens, escapes) are admissible as FACTS; every VERDICT comes from the closed vocabularies below.
5. **Grounding floor** (RC-2b generalized): every Fundamental/Structural claim carries ≥1 VERBATIM quote
   from a run artifact or event line, plus its path and round/stage anchor. A serious charge anchored to
   nothing invalidates the claim outright.
6. **Independence.** Form verdicts from evidence, not from other reviewers' verdicts (you may cite their
   FILES as pointers to evidence, never their conclusions as support).

## Finding qualification — ALL five required, else it is run-notes, not a finding

1. Verbatim evidence + artifact/trace path + round/stage anchor (rule 5).
2. Component + its DEPLOYED spec pointer (file:section) it deviated from — or an explicit "no contract
   exists" (that is a spec-gap finding).
3. The counterfactual test: state what the pipeline would DO DIFFERENTLY if this is accepted. Nothing
   changes → downgrade to run-notes.
4. A falsifiable next-run expectation: "next run should observably show X", X checkable from next-run
   artifacts/trace, phrased RUN-RELATIVE (presence/absence, categorical states — never absolute numbers;
   the next run is a different paper).
5. Severity + lens tag. Severity ∈ [Fundamental | Structural | Minor].

**The `[OPPORTUNITY]` lane — "recorded headroom, left unconsumed."** For claims that the machine
stopped short rather than misbehaved. All five requirements still bind; legs 1–3 take the opportunity
form (tag the finding header `[OPPORTUNITY]` so the verifier applies the matching lane, not the
counterfactual-quality attack):
1. *Headroom signal*: ≥1 verbatim quote of a signal THE RUN ITSELF RECORDED naming the headroom, +
   path + anchor. Legal signal classes (closed): panel `top_strengthening_directions` / un-enacted
   `strengthen`-tier items (`paper/review-report.md`, `review-verdicts.md`) · amplifier at-ceiling
   verdicts with earnable text (`.round-*.amplify-verdict.json`) · `below_floor` advisories
   (`loop-gate-input-r*.json`) · rescue residuals (`.round-*.rescue-verdicts.json` residual/why_none) ·
   cold-read `uncovered_axes` (calibration lane only) · ideation-pool records ranking a dead candidate
   at-or-above the picked seed on RECORDED axes · seed/refine promises that never became a §4c
   dimension. "Could have done better" with NO recorded signal stays pure inference — AUTO-INVALID.
2. *Non-consumption*: name the consumption site(s) where the machine would have acted (a HANDOFF item,
   an experiment wave, an amplify raise, a punch item, an explicit waiver) and show the absence — an
   absence claim states exactly where it looked.
3. *Counterfactual, opportunity form*: name the component that should have consumed the signal and what
   it would DO — or the explicit spec-gap (no deployed contract assigns the duty). You are NEVER
   required to prove the paper would have been better: the claim's object is the machine's unconsumed
   recorded signal, not the counterfactual paper. PLUS a capacity leg: quote the capacity fact (rounds
   below cap / budget / wall-clock remaining, from the rollup or the deployed config) — a signal
   recorded when nothing was left is `无余量`, a run-note, never a finding.

**AUTO-INVALID** (state it and drop): re-litigates §0 WITHOUT premise-breaking new evidence (an
evidence-backed, tagged `[CHALLENGE]` uses its own lane — rule 3) · generic best practice with no
THIS-RUN miss behind it · re-does in-run machinery's job (a prose flaw belongs to the panel; your finding, if any, is
about the panel) · duplicates an existing ratified-ledger item → convert to a **RECURRENCE REPORT**
("<ledger-id> predicted this; observed at <evidence>" — valuable, bumps that item's urgency, never a new
proposal) · restates a tolerated observability gap as a defect (one observability PROPOSAL per gap is the
right form) · pure inference with no disk anchor (an `[OPPORTUNITY]` finding anchored to a RECORDED
headroom signal is not pure inference — see its lane) · cites venue cold-read content as a defect of
the PAPER or a reason to change it (exception (iv) licenses calibration ONLY) · treats an
environment-transient event (evidence pack §7 / a `[cause:env_transient]` line / a crash carrying a
RESOLVED note) as evidence about the SCIENCE — idea quality, claim strength, viability/terminal judgment,
or an ideation hindsight label. The SAME event legally grounds a MACHINE finding (retry/backoff/detach
resilience — the workaround lane: store how it was or should be fixed, per the experiment spec's
`failure/transient.md`).

**KEEP duty.** Alongside findings, nominate what went RIGHT with the SAME evidence bar (component +
verbatim anchor + why it earns its complexity). At least one Keep candidate per group you actually
exercised. A clean area honestly reported beats a manufactured finding — /learn's success metric is
decision quality per owner-minute, never finding volume (that would be reward-hacking, the exact disease
this pipeline hunts elsewhere).

## Closed vocabularies

- Severity: `Fundamental | Structural | Minor`
- Producer verdicts: `合格出品 | 带瑕疵出品 | 返工大户 | 未启用`
- Gate/auditor verdicts: `尽职 | 漏放 | 橡皮图章 | 误伤 | 冗余 | 饿着 | 未启用`
  (橡皮图章 = passed everything while escapes of its class exist; 饿着 = charter fine but its INPUTS never
  carried the evidence — attributes upstream; 冗余 = never once altered a decision)
- Human-gate service verdicts: `情报到位 | 情报缺失 | 选项错位 | 浪费注意力`
- L0/mechanical verdicts: `忠实 | 有偏航 | 有故障`
- Claim-hop deltas: `faithful | scoped(诚实收窄) | softened | reframed(换题) | inflated`
- Headroom disposition: `已消费 | 明示弃权 | 无人认领 | 无余量` (only 无人认领 may yield a finding;
  明示弃权 — an owner answer or an AC keep_as_is with rationale — is settled disposal)
- Venue-calibration delta: `校准一致 | 面板偏严 | 面板偏松 | 无法比对` (step counts on the closed
  admission set are FACTS; 面板偏松 by ≥2 steps, or accept-vs-reject, makes the panel a 橡皮图章 candidate)
- Ideation-pool ceiling: `池顶已选 | 池顶被埋 | 全池皆弱 | 证据过期`; per-candidate hindsight:
  `死于坏理由 | 死于好理由 | 卡上已示(settled) | 证据过期`
  (admission-bar verdicts REUSE the panel's closed set `reject | major_revision | minor_revision |
  accept` — never invent a second scale; the delta must stay computable)
- Evidence classes: `TRACE | ARTIFACT | DERIVED` (DERIVED must name its inputs so it is re-derivable)

## Output formats (uniform across all reviewers)

Finding block (in your full review file):

    ### <GROUP>-<n> [<severity>·<lens>·<component>] <one-line defect>
    - 现象: <what happened; ≥1 verbatim quote + `path` + round/stage anchor; evidence class>
    - 根因: <mechanism; component + deployed spec file:section, or "spec-gap">
    - 反事实: <what the pipeline would do differently>
    - 下轮预期: <falsifiable, run-relative>

Findings-index file (`<INDEX>`, HARD-CAPPED — the only thing L0 reads from you): one line per finding
`<id> | <severity> | <component> | <one-liner>`, then a `KEEP:` line per Keep candidate, then one
`TALLY: findings=<n> keep=<n> recurrence=<n>` line. Stay under the cap by dropping Minor lines first
(they remain in the full file).

Envelope: return the uniform envelope (spec/l1-envelope-schema.json): status `done`, artifacts = the
files you wrote, metrics.notes = your TALLY line. You are a single-context leaf: spawn NOTHING, edit
NOTHING outside your own output files.
