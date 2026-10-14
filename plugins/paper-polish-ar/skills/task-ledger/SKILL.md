---
name: task-ledger
description: Format + completion criteria for the standard review task files (TASK_SPEC / TASK_PLAN / TASK_RUNBOOK / TASK_STATUS / PAPER_REVISION_PLAN) that /review writes, and the pre-submission completion checklist shared by /review and /polish. ALSO the home of the authoritative open-items ledger schema (TASK_STATUS.concerns.json — references/open-concerns-schema.md) that the auto-research loop hard-reads for progressive disclosure. Retrieved by the orchestrator when it writes or refreshes those files. Not a slash command.
user-invocable: false
---

# Task ledger — the review task files + completion checklist

The standard opens by establishing five named, git-tracked task files during the review's
single diagnose pass (the manuscript body is never touched in `/review`). This skill is
the single source of truth for **what each file contains** and **the completion checklist**
— so the spec stays thin and nothing is hardcoded.

Hard rule: **review is a single diagnose pass — there is no inner convergence loop and no round
count to read.** Do not reference `max_review_rounds` / `max_macro_rounds` / `no_progress` (those
knobs are retired). The venue (resolved at runtime), the sections in scope, and the base sha are
filled from the run, never invented.

Write Markdown. Keep each file tight; these are working artifacts, not prose essays.

## The five files (write all five in Plan; finalize TASK_STATUS at Emit)

**TASK_SPEC.md** — 投稿目标；非目标（不只语言润色，不改科学结论；**review 只诊断不改稿**）；硬性约束 /
不可虚构边界（不虚构实验、不伪造引用、不改结论；无法验证项标"需作者确认/补充"；任何数字必须来自真实运行
或可追踪日志——但写回在下游 loop / `/polish` & `/rewrite` 阶段进行，不在 review）；工作边界（本地只读论文
与代码做诊断；运行/训练/写回交下游）；完成标准（见下）；关键路径（Manuscript、review-report.md、
paper-model、HANDOFF）。

**TASK_PLAN.md** — 审稿诊断流程：**一次诊断 pass** = panel（多个对抗式 reviewer 的多轴）→ Area Chair 汇总
一份按拒稿风险排序的 punch-list → escalate（需作者项）→ 把所有需要的实验/理论/claim 改写打包成可移植
HANDOFF；**没有内层 panel↔大修 收敛循环，没有 macro 重审循环**（这些旋钮已退役）。覆盖标准的"全文 →
section → paragraph → 实验 → 理论 → 图表"六层只用于**诊断分类**（全文/section/paragraph 由 reviewer 多轴 +
AC 覆盖；实验/理论/claim 改写一律导出到 HANDOFF，由下游 loop 执行；图件视觉打磨交 /polish-figures）。

**TASK_RUNBOOK.md** — 诊断产物（review 不改稿、不开 review-<ts> 分支：只产出 task 文件、review-report.md、
HANDOFF-<paper>.md / REVIEW-EXPERIMENT-PROTOCOL.md）；下游执行指针（实验运行 / 写回 / provenance 复核都在下游 loop
的 experiment+draft 阶段，HANDOFF 即工单，每条对抗式 concern 带 kill 标准）。

**PAPER_REVISION_PLAN.md** — 范围（被诊断的章节）；优先原则（先标拒稿核心问题：实验不足/理论缺口/
claim 过强/结果不支撑，再标增强项；reject > major > minor，同级按对主旨中心程度）；编辑级判断与
强化方向（可送审/大修后送审/暂不建议投稿、3-5 强化方向、每条 punch-item 标必须改/建议增强/可不变，运行时
由 Area Chair 产出并写入 TASK_STATUS）；交接（仍未达完成标准的差距 + 需作者补充的实验/理论/引用 全部进
HANDOFF，交下游执行）。

**TASK_STATUS.md** — 头部（base + 范围章节）；编辑级判断（acFinal.overall_risk + 3-5 最需强化方向，写在一个
标题**字面锁定**为 `## Editorial direction (top strengthening needs)` 的小节下——不要改写或翻译这个标题，
`bin/concern_prose_lint.sh` 靠这个字面字符串定位该小节，标题漂移会让陈旧性检查静默失效）；
punch-list（按拒稿风险排序，每条 = 主要批评与发现问题）；需作者确认/补充（escalations + 文献缺失类别及
检索关键词）；导出 HANDOFF 的实验/理论/claim 改写需求清单；完成标准对照（下面的 checklist，逐项 `- [ ]`）；
硬阻塞与交接指针。**编辑级判断小节里但凡提到某个 `TASK_STATUS.concerns.json` 里的 concern id，措辞必须和该
id 当前的 `status` 一致**（例如已经 `descoped`/`closed` 的 K 不能仍被写成"是全文核心"）——写这一节时先读一遍
`TASK_STATUS.concerns.json` 的当前状态。

## Completion checklist (TASK_STATUS 的"投稿前 checklist"——作者逐项核对)

- 整体逻辑清晰；创新性表达适度
- 方法、理论、实验、结论互相支撑
- 主要 claims 有实验 / 理论 / 引用支撑
- 理论缺口、实验缺口、引用风险已修复或明确标记
- 图表叙事与正文一致
- 符号、公式、术语、引用、编号基本一致
- 数值实验达到发表级
- 论文各部分达到投稿 Manuscript 级
- 需作者确认 / 补充项已全部列出

## Prose-scope checklist (for /polish's ship-readiness — science is frozen there)

- 整体逻辑清晰、叙事连贯（一个核心故事贯穿）
- 创新性表达适度，无空泛宣传式措辞 / AI 腔
- 段落主题句、逻辑衔接、句子节奏达投稿级
- 术语、符号、引用、编号跨章节一致
- 摘要与标题达投稿 Manuscript 级
- 本地已生成最终 Manuscript（本分支 HEAD）

## Open-items ledger — schema (moved)

The **authoritative open-items ledger schema** (the PROGRESSIVE-DISCLOSURE engine's input — container
contract, row fields, status state machine, per-round PD action, Ledger ①/② cadences) lives in
[`references/open-concerns-schema.md`](references/open-concerns-schema.md). Load it whenever you write
or read `TASK_STATUS.concerns.json`; the container rule (`{ "open_concerns": [...] }`, upsert-by-id,
never overwrite a peer's rows) is FREEZE-CRITICAL — spec/research.js hard-reads that exact shape.
