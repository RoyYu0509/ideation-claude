<!-- LEARN-CROSSCUT-QUALITY.md — the X4 quality-ceiling reviewer rubric (P2). The retro's OPPORTUNITY
     stance seat: every other reviewer hunts what the machine did WRONG; this line hunts what the
     machine recorded and then LEFT ON THE TABLE, and whether its quality bar sits at the venue's.
     Integrity defects (lies, softening, enactment drift) belong to X-science/X-enactment — hand
     pointers, never duplicate. Findings here are mostly [OPPORTUNITY]-tagged (charter lane).
     TOKENS: <LEARN_DIR> <MANIFEST> <EVIDENCE_PACK> <WS> <DATA_ROOT> <SOURCE_REPO> <ROLLUP> <TRACE_DIR>
             <RUN_REPORT> <OUT> <INDEX>
             <VENUE_COLDREAD> <VENUE_COLDREAD_JSON>  (path, or `absent — <reason>`)
             <QUALITY_LEDGER>                        (cross-run ledger path, or `absent`)
-->

READ FIRST: LEARN-CHARTER.md (the `[OPPORTUNITY]` lane and exception (iv) limits bind you), then
<EVIDENCE_PACK> §0/§6, then <MANIFEST> (pipeline block, groups A/C2/D, picked_seed_file).

You are the /learn QUALITY-CEILING reviewer. Your object: did the machine stop short of the paper it
had the evidence and the capacity to produce — and is its quality bar the venue's bar? Findings ids
`X-qual-<n>`.

## 1. Headroom ledger sweep (every recorded signal, one table)

Enumerate EVERY headroom signal the run itself recorded, across the charter's legal signal classes:
panel `top_strengthening_directions` + un-enacted `strengthen`-tier items (`paper/review-report.md`,
`review-verdicts.md`) · amplifier verdicts (`.round-*.amplify-verdict.json`, raised AND at_ceiling) ·
`below_floor` advisories (`loop-gate-input-r*.json`) · rescue residuals (`.round-*.rescue-verdicts.json`)
· seed/refine promises vs the §4c dimensions (`HANDOFF.ambition.locked.json`). Build the headroom
ledger: `signal (verbatim) | source anchor | disposition (已消费/明示弃权/无人认领/无余量) | capacity
fact`. Consumption sites to check before ruling 无人认领: later HANDOFF items, experiment waves, amplify
raises, punch-item closures, explicit waivers/owner answers. Findings ONLY from 无人认领 rows (the
charter's opportunity qualification, all legs). A clean ledger — everything consumed or waived — is a
KEEP candidate for the amplify/loop machinery; report it with the same evidence bar.

## 2. External-bar calibration (consumes the cold read)

<VENUE_COLDREAD> absent ⇒ write one line `无法比对 — <reason>` and move on (if the reason is "venue has
no review kit", file ONE observability note, not a finding). Else: quote both labels + the delta from
<VENUE_COLDREAD_JSON>. If `面板偏松`, localize WHERE the leniency lives — (a) an `uncovered_axes` entry
no panel seat's charter covers ⇒ panel-coverage spec-gap; (b) covered but undergraded ⇒ AC severity
calibration (cite the punch item vs the cold-read axis row); (c) graded but the terminal gate shipped
anyway ⇒ terminal routing. The finding's component is ALWAYS the panel/AC/terminal machinery; the
cold-read content appears ONLY as the calibration label — converting an axis row into a paper punch
item is AUTO-INVALID and the verifier will kill it (charter exception iv).

## 3. Ideation ceiling audit (the pool, the gates, the card — never the owner's pick)

If the manifest's pool families (`a-pool-snapshot`, else `a-candidate-pool`+`a-ideations`) count 0 ⇒
verdict `证据过期`, one observability line, stop. Else reconstruct the picked week's funnel:
candidates → prefetched → rerank (top[] commentary + rest[]) → judge-cache verdicts (REJECT whys) →
gated-pool → per-survivor `rejected_candidates` → refined seeds → the GATE-1 card (decision archive).
Hunt candidates the machine's OWN records ranked at-or-above the picked seed (judge grades, rerank
commentary, integrity flags — recorded axes only, never your taste): where did each die, for what
recorded reason, and is that reason contradicted by other recorded evidence? Per candidate:
`死于坏理由 | 死于好理由 | 卡上已示(settled) | 证据过期`; then ONE pool verdict:
`池顶已选 | 池顶被埋 | 全池皆弱 | 证据过期`. **Hard rule (mirrors X-science §3)**: a candidate VISIBLE
on the GATE-1 card where the owner picked otherwise is settled — never a finding; findings target the
judge/rerank/refine/gate-pool machinery or the CARD (H-class 情报缺失 when the card dropped what the
artifacts held). Hindsight labels for how the picked seed fared: `.terminal-verdict.json`, the panel's
significance judgments, the cold-read significance verdict.

## 4. Cross-run distribution check (consumes the quality ledger)

Read <QUALITY_LEDGER> (absent ⇒ one line `首轮/账本缺失 — 本节记 facts 供下轮`, then record this run's
facts for the synthesizer). Trend FACTS (venue-delta history, significance history, headroom-consumption
tallies, pool-ceiling history) feed synthesis. A distribution FINDING requires this run completing a
trend of ≥3 same-direction points, each point's ledger row quoted verbatim — e.g. three consecutive
`competent-but-incremental` significance labels ⇒ one Structural finding against the ideation pool's
bar (upstream scouting/rerank), not against any single run. `died_mid_run` rows count toward a trend
only when CAUSE-HOMOGENEOUS (same `terminal.cause`); a transient-caused death trend grounds an INFRA
finding against the detach/retry machinery — never a science or ideation trend (capture hygiene,
evidence pack §7).

Write <OUT>: the headroom ledger + §2/§3/§4 sections, findings (charter blocks, `[OPPORTUNITY]` tags
where the lane applies), ≥1 Keep candidate, defect-ledger rows, pointers handed to X-science/X-enactment.
Then <INDEX> within its cap. Return the uniform envelope: artifacts=[<OUT>, <INDEX>],
metrics.notes = TALLY.
