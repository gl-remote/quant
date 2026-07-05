# Archive · Strategy Research 顶层索引

> 类型：Archive Index
> 目的：立题扫描时的**首要入口**——按日期倒序列出全部归档批次，避免逐个打开 summary。
> 维护规则：每次归档新批次时按"归档原子步骤 7"追加一行（见 `.trae/skills/quant-research-layout/SKILL.md`）。

## 批次总览

| 日期 | 家族 slug | Topic 一句话 | 结论标签 |
|------|----------|-------------|---------|
| 2026-07-05 | value-area | value-area-rolling-reacceptance 主题冻结：POC 特殊性 / rolling 独立价值 / reacceptance 触发器 / 距离档 edge 全部证伪 | ❌ 证伪 · 🧪 方法论 |
| 2026-07-03 | value-area | value-area-reacceptance stage-b sweep，主题降级 feature-only | ❌ 证伪 |
| 2026-07-02 | value-area | value-area-reacceptance 扩样与结构诊断（R27-R29） | ❌ 证伪 |
| 2026-07-01 | value-area | value-area reacceptance quality 分层与形状 bucket 分析（R1-R26） | ❌ 证伪 |
| 2026-06-29 | structural-alpha | 结构入口 vs 随机 baseline 双对照；VA reacceptance 确立为下一阶段主线；IB / 流动性 / 低波入口降级 | 🧪 方法论 · ⚠️ 分流 · 🔁 转主线 |
| 2026-06-27 | low-validation-cost | 低验证成本区间判据体系建立；具体候选（布林带 / 前 N 高低点 / 趋势回踩）成本后未通过 | ❌ 证伪 · 🧪 方法论 |
| 2026-06-26 | indicator-baseline | MA 正期望值 + ATR 调参基线 | 🧪 方法论 |

## 结论标签约定

- ✅ 通过：假设被证实、后续可作为策略候选或核心组件；
- ❌ 证伪：核心假设失败或主题降级，作为反例记录；
- 🧪 方法论：无论结论如何，产出的判据 / 采样 / 统计工具对后续主题有长期价值；
- ⚠️ 分流：部分方向通过 + 部分方向降级/暂停（混合结论，不宜单打 ✅ 或 ❌）；
- 🔁 转主线：本批次结论直接指向下一阶段的新主线（含"某某深化"或"改由 X 主线继续"）。

标签**可组合使用**（如 `🧪 方法论 · ⚠️ 分流 · 🔁 转主线`）；顺序无硬性要求，
但建议按"结论强度 → 遗产 → 元信息"排列。

## 使用方式

**立题者**：
1. 先按新主题所属家族 slug 过滤本表；
2. 家族外批次只关注**近 2 周**的行；
3. 需要深读时再打开 `<batch>/freeze-summary.md` 或 `<batch>/README.md`；
4. 决定是否登记到主题的 `archive-references.md`（"引用触发登记"原则）。

**归档者**：新归档批次时追加一行，按日期倒序排列。
