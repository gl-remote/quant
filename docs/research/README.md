# Research 文档入口

> 类型：Research / 当前研究入口\
> 状态：活跃\
> 用途：给人和 AI 快速了解当前研究状态、主题主线、成果和应避免重复的方向。

## 1. 目录定位

`docs/research` 用来保存当前仍在活跃维护的研究状态和主题索引。

它不同于：

| 目录 | 用途 |
|------|------|
| `docs/roadmap` | 阶段规划、未来计划、评价标准 |
| `docs/workbench` | 当前实验过程记录、参数对照、临时结论 |
| `docs/archive` | 已结题阶段归档、压缩复盘 |
| `docs/issues` | 回测、数据、框架、统计口径等问题 |
| `docs/research` | 当前研究状态、主题主线、已确认成果、下一步入口 |

## 2. 当前策略研究入口

先读：

- [strategy-current.md](./strategy-current.md)

该文件只维护总入口：

```text
当前一句话结论；
当前主题列表；
当前候选参数；
下一步优先级；
文档地图；
AI 接手规则。
```

## 3. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| ~~va-asymmetry-revisit~~ | **⚠️ 已彻底废弃归档（2026-07-14）** · 一日 4 轮因果版实验全线证伪 · pipeline 因果性完好但假设无 alpha · 原主题目录整包搬入 archive | [archive:2026-07-14-va-asymmetry-revisit-full-refutation](../research/archived-notes/2026/07/2026-07-14-va-asymmetry-revisit-full-refutation/README.md) |
| ~~va-asymmetry-composite~~ | **⚠️ 已证伪归档（2026-07-13）** · 假设由未来信息泄漏支撑 · 无独立 alpha | [archive:2026-07-13-va-asymmetry-leak-chain-consolidated](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/README.md) |
| ~~poc-value-area-asymmetry~~ | **⚠️ 已归档（2026-07-13）** · va-asymmetry 错误链条上游 · Stage 1-4 数字全部作废（daily 特征泄漏）· 仅分类器 v4.0 6 阵营坐标切分结构可作方法论继承 | [archive:...leak-chain-consolidated/theme-poc-value-area-asymmetry/](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/theme-poc-value-area-asymmetry/README.md) |
| structural-shaping-alpha | 活跃 / 阶段 1 完成待冻结候选 / 工具资产引用 | [themes/structural-shaping-alpha/](./themes/structural-shaping-alpha/README.md) |
| ~~strength-factor-screening~~ | **已冻结归档（2026-07-17）** / 核心假设证伪 · 8 候选全 L4 · 强度不比方向容易识别 | [archive:2026-07-17-strength-factor-screening-freeze](../research/archived-notes/2026/07/2026-07-17-strength-factor-screening-freeze/freeze-summary.md) |
| ~~value_area_reacceptance~~ | **已冻结归档（2026-07-03）** / feature-only 降级 | [archive:2026-07-17-value-area-family-consolidated](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md) |
| ~~value_area_rolling_reacceptance~~ | **已冻结归档（2026-07-05）** / 主题假设完全证伪 | [archive:2026-07-17-value-area-family-consolidated](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md) · [freeze-summary](../research/archived-notes/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |

家族目录：[archive:2026-07-17-value-area-family-consolidated](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md) · [themes-frozen/structural-shaping-alpha/](./themes-frozen/structural-shaping-alpha/README.md)

活跃主题目录：
- 上游 Alpha 源（**已归档**）：`archive:...leak-chain-consolidated/theme-poc-value-area-asymmetry/`（⚠️ 数字作废，分类器 v4.0 tier 坐标结构可继承）
- 上游工具：`docs/research/themes/structural-shaping-alpha/`（塑形 / 成本 / 归因）

## 4. 当前主线摘要

```text
2026-07-13 重大变化：
- va-asymmetry-composite 主题整目录已归档（archive:...leak-chain-consolidated/theme-va-asymmetry-composite）；
- 其假设（daily 特征 spec 系列 → tier → alpha）被 4 层证据链证伪（含截断法因果判据）；
- 07-08 ~ 07-13 共 7 个 va-asymmetry 系列批次全部合并入同一封装批次，
  性能类数字结论作废（B0 Sharpe 2.70、63.44% 年化、P0-P9 全部数字 等）；
- 分类器 v4.0 的 6 阵营坐标结构定义仍可作为方法论遗产继承，但归一化输入需重新设计。

后续研究入口:
- structural-shaping-alpha 仍是工具资产（First-Passage Designer 等）；
- 若要延续 va-asymmetry 假设：需先重建因果版 daily 特征管道，
  三条候选路径详见 archive:2026-07-13-va-asymmetry-leak-chain-consolidated#README §五；
- 若要立新主题：跳过 va-asymmetry 家族，从其他 alpha 源起。
```

## 5. 关键文档

- **[archive:2026-07-13-va-asymmetry-leak-chain-consolidated（va-asymmetry 错误路径链条归并封装 · 必读）](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/README.md)**
- [2026/07/2026-07-06-structural-shaping-alpha-stage1（塑形 Stage 1 归档）](../research/archived-notes/2026/07/2026-07-06-structural-shaping-alpha-stage1/README.md)
- [2026/07/2026-07-05-value-area-rolling-reacceptance-freeze（Rolling 冻结摘要）](../research/archived-notes/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md)
- [Stage B v2/v3 sweep（feature-only 降级决策）](../research/archived-notes/2026/07/2026-07-03-value-area-reacceptance-stage-b/README.md)
- [R29 扩样与随机基准复验](../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
- [R28 value_area_reacceptance 结构诊断](../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md)
- [R27 扩样复验](../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md)

更早归档：

- [value_area_reacceptance POC / VA 质量诊断阶段归档](../research/archived-notes/2026/07/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)
- [R1~R15 原始实验记录](../research/archived-notes/2026/07/2026-07-01-value-area-reacceptance-quality/raw-workbench/)
- [结构型 Alpha 随机对照阶段归档](../research/archived-notes/2026/06/2026-06-29-structural-alpha-random-baseline/README.md)

如果需要追溯上一阶段详细实验过程，再从归档目录进入：

- [raw-roadmap](../research/archived-notes/2026/06/2026-06-29-structural-alpha-random-baseline/raw-roadmap/README.md)
- [raw-workbench](../research/archived-notes/2026/06/2026-06-29-structural-alpha-random-baseline/raw-workbench/README.md)

## 6. 给 AI 的阅读顺序

后续 AI 接手策略研究时：

```text
1. 先读 docs/research/strategy-current.md；
2. va-asymmetry 家族已作为一整条错误路径归档：archive:2026-07-13-va-asymmetry-leak-chain-consolidated
   （必读顶层 README，了解哪些数字作废、哪些方法论可继承）；
3. 若继续在其他主题上研究，则读：
   - poc-value-area-asymmetry（**已归档** · 只读只做方法论参考）：archive:...leak-chain-consolidated/theme-poc-value-area-asymmetry/
   - structural-shaping-alpha README + stage1-summary（工具合同 & 真实成本模型）
4. 若涉及 daily 特征聚合的新主题：
   先跑一遍截断法泄漏检测（archive:...leak-chain-consolidated/
   2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py）
   确认自己的 pipeline 无泄漏；
5. 前置组件参数（分类器 tier 结构 / 塑形 SL/TP/TH / 成本模型）视为方法论继承，
   但数字不复用；
6. 新实验过程写入 docs/workbench/<theme-slug>-<topic>.md；
7. 阶段稳定后再归档到 docs/archive。
```
