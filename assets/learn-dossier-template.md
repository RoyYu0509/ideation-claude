<!--
auto-research LEARNING DOSSIER — scaffold (assets/learn-dossier-template.md)
Filled by the /learn synthesis leaf per spec/spawn-prompts/LEARN-SYNTHESIS.md. Structure mirrors
dev/review-findings/12-* (the ratified-dossier idiom): the in-file DECISION LEDGER (appended at the
/learn `record` phase) is the SOLE remediation spec for the follow-up fix session.
-->
# <NN>-run-retro-<run_id-short> — <slug>（<date>）

- **对象**：run `<run_id>`（paper `<slug>`，DATA_ROOT `<data_root>`）
- **方法**：/learn v1 — manifest 对账 → evidence pack(§0) + venue 冷读(条件) → <N> 组件组 reviewer + 4 横切线 → 按主题对抗复核（驳倒立场）→ 综合
- **代码世界**：run_spec_commit `<sha>` · source HEAD `<sha>` · 漂移插件：<list|none>（finding 均标注 cache-world / source-world）
- **规模**：<n> leaves · findings <n>（复核后）· 提案 <n> 进拍板 / <n> parked · 复发报告 <n>

## ⚠️ 复核纠正区 — 不要据此行动
<!-- one line per REFUTED/ADJUSTED claim: what the reviewer asserted, why the verifier killed/adjusted it.
     The anti-wrong-fix device: nobody later "fixes" a non-problem. -->

## 上轮假设清算
<!-- one block per open hypothesis: H-n · ratified expected_signal (verbatim) · verdict
     helped/no-effect/hurt/unmeasurable · evidence anchor · consequence filed (Keep entry / revert
     proposal / observability bump). First retro: "无历史假设。" -->

## 主题 <A/B/...> — <theme name>（worst-first）
<!-- per confirmed finding:
### <id> [<Fundamental|Structural|Minor>·<CONFIRMED|ADJUSTED>] <one-line defect>
    (an opportunity-lane finding additionally carries the [OPPORTUNITY] tag — charter lane)
**现象** what happened, with >=1 verbatim quote + artifact/trace path + round anchor
**根因** the mechanism; names the component + its DEPLOYED spec file:section (or declares spec-gap)
**修复提案** -> P-<n> below (or "run-notes only — fails the counterfactual test")
-->

## Keep / 别动清单
<!-- >=1 per exercised group, same evidence bar as findings: what went RIGHT and earns its complexity.
     helped-hypothesis graduates auto-enter here. -->

## 复发报告（已拍板未生效项的再现实证）
<!-- "dossier-12 <id> predicted this; observed at <evidence>" — bumps that item's urgency; never a new
     proposal, never occupies a ratification slot. -->

## 提案（进拍板席 3–7 条；其余 parked 在附录）
<!-- per proposal:
### P-<n> [<type: bug-fix|spec-hardening|simplification|new-capability|redesign|knob-tuning|observability>·<severity>·<urgency: this-week|before-next-run|someday>·<cost: S|M|L>] <title>
- **finding refs**: <ids> (evidence lives there; never re-argue here)
- **改法**: one paragraph; **blast radius**: the SOURCE files/specs touched; MUST-LAND-TOGETHER batch if coupled
- **expected observable（=假设）**: next run should observably show X (run-relative, categorical — owner may edit at ratification)
- **how to check**: where the next /learn looks
- **ledger interaction**: independent | extends <id> | blocked-by <id> | duplicate→复发报告
- **overturns** ([CHALLENGE] only): the §0 entry + its recorded premise + the premise-breaking evidence ref — rendered in its own 推翻旧案 ratification block, original decision shown verbatim
- **revert plan** (M/L only): what next-run evidence means "undo this"
-->

## DECISION LEDGER（owner 拍板 — 修复的唯一规格）
<!-- appended by /learn `record`: one line per proposal `**P-<n> = <disposition>**` + verbatim owner notes;
     hypothesis-verdict confirmations recorded here too. EMPTY until ratification. -->

## 附录：parked 候选 + 统计
<!-- parked proposals (one line each) · defect-ledger tallies · gate verdict table sources · rollup pointer
     · 质量水位存档 (the D2 harvest): headroom-ledger tally · venue-calibration record (冷读 verdict /
       panel verdict / delta) · pool-ceiling verdict — mirrors quality-record.json for human readers -->
