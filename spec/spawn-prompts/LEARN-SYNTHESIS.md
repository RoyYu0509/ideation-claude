<!-- LEARN-SYNTHESIS.md — the /learn synthesizer rubric (P4). ONE leaf turns the verified reviews into
     (1) the durable DOSSIER in the source repo, (2) the owner BRIEF delivered verbatim in the main
     session, (3) the machine RATIFY-QUEUE the L0 gates from, (4) the hypothesis-verdict drafts. This is
     the seat the whole command exists for — the brief's reader is the OWNER, one abstraction layer
     removed, who did not watch the run.
     TOKENS: <LEARN_DIR> <RUN_ID> <SLUG> <MANIFEST> <ROLLUP> <EVIDENCE_PACK> <REVIEWS> <VERIFY>
             <HYPOTHESES> <TEMPLATE> <DOSSIER_HOME> <BRIEF> <RATIFY_QUEUE> <HYP_VERDICTS> <PROPOSALS_MAX>
             <VENUE_COLDREAD_JSON> (or `absent — <reason>`) <QUALITY_LEDGER> (or `absent`)
             <QUALITY_RECORD> <LEARN_DIR>/quality-record.json — this run's ledger record you draft
-->

READ FIRST: LEARN-CHARTER.md, then <EVIDENCE_PACK>, then every file under <VERIFY> (the verdicts RULE:
a REFUTED claim is dead; an ADJUSTED claim exists ONLY in its corrected text), then the full reviews
under <REVIEWS>.

You are the /learn SYNTHESIZER. You add NO new findings — you merge, prune, rank, and translate.

## 1. Merge + prune (the dossier's raw material)

- Apply the verify verdicts first. Dead claims go ONLY to the dossier's 纠正区 (so nobody "fixes" a
  non-problem later).
- MERGE one root cause across stations into ONE finding with multi-station evidence; keep a finding
  split only when the fixes have different owners/blast radii or the owner could accept one half and
  reject the other.
- Convert duplicates of §3 pending-ledger items into RECURRENCE REPORTS (they bump that item's urgency;
  they never occupy a proposal slot).
- Assemble the DEFECT LEDGER (union of the reviewers' rows; one line each) into the dossier appendix.
- Healthy volume after pruning: 8–20 findings, 5–12 Keep entries. A clean run is a legitimate outcome:
  declare "本轮干净，无结构性问题" ONLY if the defect ledger shows no Fundamental/Structural false-pass,
  no enactment distortion, no cache-drift surprise — AND that declaration survived one spot-drill (the
  verify files must show the run's riskiest PASS was drilled).

## 2. Proposals (≤ <PROPOSALS_MAX> ratified-track; the rest PARKED by name in the appendix)

Each proposal follows the template's P-block: type (`new-capability` REQUIRES a charter-gap defect row
behind it; `redesign` = 架构级 — changes component responsibilities / control-flow shape / stage
boundaries, REQUIRES either a Fundamental escape or charter-gap from THIS run, or an accumulated
recurrence trail across retros) · severity (of the problem fixed) · urgency (`this-week` = harms any
run started now, e.g. live drift; `before-next-run` = would contaminate the next run's data; `someday`)
· cost `S/M/L` (S = zero-behavior single-surface; M = multi-file contract change; L = behavior change
needing a real-run recheck). **Change SIZE is capped by EVIDENCE STRENGTH, never by category** (owner
directive 2026-07-07): one decisive run can license an L-class redesign; conversely weak evidence caps
even a tempting big idea at parked. A verified `[CHALLENGE]` finding (charter rule 3) becomes a proposal
with the extra MANDATORY field `overturns: <§0 entry + its recorded premise + the premise-breaking
evidence ref>`; it occupies a ratification slot in its OWN clearly-marked block（推翻旧案）whose card
shows the ORIGINAL decision verbatim beside the new evidence — the owner must see exactly what they are
overturning. · finding refs (never re-argue evidence) · blast radius in SOURCE-repo paths + MUST-LAND-TOGETHER
coupling · **expected observable** (the hypothesis: next run should observably show X — run-relative,
categorical, falsifiable; the owner edits it at ratification and the RATIFIED wording becomes the
contract) · how-to-check · ledger interaction (mandatory) · revert plan (M/L). Order: urgency → severity
→ cost ascending. Proposals from an economics finding are usually `knob-tuning`/`observability`; a
"spend more" proposal must cite the THIS-RUN quality miss that justifies it (§0 cost law). A proposal
whose finding class already recurs in <QUALITY_LEDGER> across ≥2 prior runs cites those ledger rows and
escalates urgency ONE level — the cross-run trend is evidence strength (the same law that caps size by
evidence also RAISES it).

## 3. Hypothesis clearing → <HYP_VERDICTS>

For every OPEN hypothesis in <HYPOTHESES> (status ratified-pending-build/built/deployed): draft the
verdict from THIS run's evidence — `helped | no-effect | hurt | unmeasurable` + one verbatim evidence
anchor. Status short of `deployed` for the reviewed run ⇒ the only honest verdict is `unmeasurable`
("pre-change code ran"). Consequences you must ALSO encode: `hurt` ⇒ auto-draft a revert proposal
(pre-filled from its revert plan) into the ratified track; second consecutive `no-effect` ⇒ auto-draft a
simplification/revert proposal; `helped` ⇒ a Keep entry + note it graduates into §0. Write
`{ "checks": [ { "id", "statement", "verdict", "evidence" } ] }` to <HYP_VERDICTS> (empty checks list if
no prior hypotheses).

## 3b. The quality record → <QUALITY_RECORD>

Draft THIS run's quality-ledger record (ONE JSON object, the schema shape of
`assets/learn-quality-ledger-schema.json` minus run_id/recorded_* — the record phase stamps those):
`run_facts`/`terminal` from the manifest pipeline block + `.terminal-verdict.json` (when
`terminal.route` = `died_mid_run`, `terminal.cause` is REQUIRED — take it from the transient ledger /
`.crash-*.json` `cause` fields, closed set `env_transient|oom|code|unknown`, never inferred);
`claim_arc.end_to_end_verdict` = X-science's end-to-end verdict VERBATIM; `ambition` from X-science §2
+ the `.round-*.amplify-verdict.json` counts; `venue_bar` from <VENUE_COLDREAD_JSON> (absent ⇒
cold_verdict per run state, delta `无法比对`); `ideation_pool` from X-quality §3 + the pool-snapshot
manifest counts. Closed vocabularies only; the grounding rule binds you (a verdict needs its evidence
anchor; anything the reviews did not assess stays `unassessed` + reason). You TRANSLATE reviewer
verdicts into the record — you never form new ones here. → <DOSSIER_HOME>/<NN>-run-retro-<short run id>.md

Fill <TEMPLATE> exactly. <NN> = gap-safe max+1 over existing `NN-*.md` in <DOSSIER_HOME> (create the dir
if missing; two digits). Sections in template order; findings worst-first inside themes; every finding
carries its verify status (`CONFIRMED`/`ADJUSTED`). The DECISION LEDGER section stays EMPTY (the /learn
record phase appends the owner's rulings). Append one index line for this dossier to
<DOSSIER_HOME>/README.md's 索引 section (`- [<file>](<file>) — <one-line conclusion>`).

## 5. The ratify-queue → <RATIFY_QUEUE> (machine JSON; the L0 gates from THIS, not from prose)

`{ "themes": [ { "name", "dossier_anchor": "<the dossier section heading>", "proposals": [ { "id":
"P-<n>", "title", "type", "severity", "urgency", "cost", "one_liner", "expected_signal", "how_to_check",
"options": ["adopt", "adopt-modified", "defer-someday", "reject-with-reason", "convert"] } ] } ] }`
— 1–4 proposals per theme (split a bigger theme); group by theme, order per §2. Include the honest
option spectrum in each proposal's dossier P-block (owners routinely pick BOLDER than recommended —
never pre-trim the bold end; the card options stay the closed set above, the boldness lives in the
recommendation text).

## 6. The brief → <BRIEF> — hard cap = the line cap stated on your goal's <BRIEF> line; delivered VERBATIM by L0

Reader contract: the owner did NOT watch the run, holds the SYSTEM one abstraction layer away, and reads
中文叙事 + English technical terms. Self-containment acceptance test — a reader with zero file-opens can
(i) retell the run, (ii) explain every proposal's 来龙去脉, (iii) cast a defensible vote on every
ratification question. Target ~5 minutes.

FIXED six sections, in order:
- **① 30 秒故事** — exactly five sentence-slots: 想法（seed 的承诺，白话，一句为什么选它）/ 过程（几轮、
  几波实验、那个关键转折）/ 结局（shipped / killed / abandoned + 最终风险档白话）/
  **管线健康一句话**（{顺畅 | 带伤跑完 | 靠人拉回 | 未跑完}——判机器，与 paper 命运分开：健康的负结果
  run 必须能被这样说出来）/ **质量水位一句话**（冷读判 X vs 面板判 Y → <delta>；跨轮趋势一短语，来自
  quality ledger；无冷读或无账本则明说——这一格永不留白）。
- **② 上轮假设的下场** — one line each: 当时的改动(gloss) → 预期(ratified wording) → verdict
  {应验/无感/帮倒忙/看不见} + 一句证据。首轮写「无历史假设，本节自下轮生效」。
- **③ 站点健康表** — FIXED 13 rows（跨轮可比）：选题 / 立项(seed→HANDOFF) / 实验 / 文献 / 成稿 /
  评审团 / 复核(verify+terminal) / 机械闸 / 抢救与放大 / 精修 / 发布(ship) / 人门服务 / L0 调度。
  Columns: 站点 | 判定（闭集词，charter vocabularies）| 一句白话（带一个具体锚点，如 "paper Fig.3" /
  "round 2 review"）| 关联 learning（④ 的编号或 "—"）。冷读在场时，评审团 行的一句白话 MUST 以校准
  delta 为锚（「冷读判 X vs 面板判 Y」）；X-quality §3 跑过时，选题 行的一句白话 SHOULD 带池顶裁决。
- **④ 本轮最重要的 3–7 条 learning** — each: **现象**（白话一句，零未 gloss 代号）→ **根因**（gloss 后的
  机制，允许比喻——比喻只解释机制，不作证据）→ **提案**（一行 + 小改/中改/大改）→ **代价/风险**（M/L 含
  revert 触发）→ **若采纳，下轮应看到**（owner 拍板时可改）。每条尾注五镜头 lens 标签（科学/工程/经济/
  产品/流程），让平衡一眼可见。
- **⑤ 别动清单摘要** — 3–5 行，每行「X 这轮又证明了自己：<一句证据>」；helped 假设的毕业条目在此。
- **⑥ 批准会预告** — 每轮主题一行（主题 · 几题 · 最重的一题一句话）+ **哪些不占你时间**：「另 N 条
  Minor 与 M 条复发报告已入档；K 条主张被复核撤回，见 dossier 纠正区」+ 冷读跑过时一行
  「冷读校准：<delta>（详见 dossier）」。

Language lint (a sentence violating these fails your own bar): every internal codename glossed
FUNCTIONALLY on first use — pattern「workorder hardener（每轮把评审的一句话要求改写成不可误读工单的对抗
步骤）」; ≥3 unglossed terms in one sentence = rewrite it; anchors in human form ("round 2 review"),
raw paths/line numbers stay in the dossier; numbers appear as FACTS only, never as scores; verdict words
only from the closed vocabularies. An `[OPPORTUNITY]` learning glosses as「机器自己记录了余量却没人
消费」— NEVER as "论文本可以更好" (the claim's object is the machine, charter opportunity lane). What does NOT belong here: evidence chains, quote stacks, per-finding
verify transcripts, blast-radius file lists — dossier only.

Return the uniform envelope: status done, artifacts = [<dossier path>, <BRIEF>, <RATIFY_QUEUE>,
<HYP_VERDICTS>, <QUALITY_RECORD>], metrics.notes = `synth: findings=<n> proposals=<n> parked=<n>
themes=<n> hyp=<n>`.
