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
| **va-asymmetry-composite** | **重启开发态（v1.0 已归档 · 2026-07-10）** | [themes/va-asymmetry-composite/](./themes/va-asymmetry-composite/README.md) · [v1.0 归档](../archive/strategy-research/2026-07-10-va-asymmetry-composite/) |
| poc-value-area-asymmetry | 活跃 / 阶段 4 完成 / 分类器 v4.0 冻结 / 下游引用 | [themes/poc-value-area-asymmetry/](./themes/poc-value-area-asymmetry/README.md) |
| structural-shaping-alpha | 活跃 / 阶段 1 完成待冻结候选 / 工具资产引用 | [themes/structural-shaping-alpha/](./themes/structural-shaping-alpha/README.md) |
| value_area_reacceptance | 已冻结 / feature-only 降级 | [themes-frozen/value-area/value-area-reacceptance/](./themes-frozen/value-area/value-area-reacceptance/README.md) |
| value_area_rolling_reacceptance | **已冻结（2026-07-05）** / 主题假设完全证伪 | [themes-frozen/value-area/value-area-rolling-reacceptance/](./themes-frozen/value-area/value-area-rolling-reacceptance/README.md) · [freeze-summary](../archive/strategy-research/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |

家族目录：[themes-frozen/value-area/](./themes-frozen/value-area/README.md)

活跃主题目录：
- 主线：`docs/research/themes/va-asymmetry-composite/`（**v2.0 重启开发态**，旧 v1.0 已归档）
- 上游 Alpha 源：`docs/research/themes/poc-value-area-asymmetry/`（分类器）
- 上游工具：`docs/research/themes/structural-shaping-alpha/`（塑形 / 成本 / 归因）

## 4. 当前主线摘要

```text
value_area 家族两个主题已冻结，假设链完全崩塌；
structural-shaping-alpha 阶段 1 证伪"塑形作为独立 alpha 源"，保留为工具资产；
poc-value-area-asymmetry 阶段 4 冻结分类器 v4.0：9 档 A/A- tier，
单笔 IR 0.28~0.46，品种保留 ≥ 60%，FDR ≤ 5%。
archive:2026-07-09-poc-va-shaping 在分类器 v4.0 上完成塑形验证
（年化净 15.45% / Sharpe 2.23 / MaxDD -7.51 / 胜率 60.3% / 盈亏比 1.41），
alpha 变现路径 POC 通过。

当前主线为 va-asymmetry-composite：经"品种筛选 × 信号强度加权 × 多空权重优化"
三道组合关，在 100% 名义暴露约束下把单品种结果提升到
Sharpe ≥ 2.5 / 年化净 ≥ 18% / MaxDD ≤ 8% 的实盘可上线标准。

阶段 0（立题复现）待启动：精确复现 archive:2026-07-09-poc-va-shaping 基准
（分类器 v4.0 + SL1.0/TP1.4/TH8h + c_realistic），Sharpe/MDD 偏差 ≤ 5% 即通过。
```

> **2026-07-10 重置提示**：va-asymmetry-composite 已从 v1.0（B0 冻结版）整体重置为 v2.0 开发态，旧版整目录归档至 [2026-07-10-va-asymmetry-composite](../archive/strategy-research/2026-07-10-va-asymmetry-composite/)。B0 作为 frozen control baseline，新底层逻辑待定义。

## 5. 关键文档

最新归档（当前立题起点）：

- **[2026-07-09-poc-va-shaping（组合验证 · 当前立题 POC）](../archive/strategy-research/2026-07-09-poc-va-shaping/README.md)**
- [2026-07-08-poc-va-asymmetry（分类器 v4.0 验证归档）](../archive/strategy-research/2026-07-08-poc-va-asymmetry/README.md)
- [2026-07-06-structural-shaping-alpha-s1（塑形 Stage 1 归档）](../archive/strategy-research/2026-07-06-structural-shaping-alpha-s1/README.md)
- [2026-07-05-value-area-rolling-reacceptance-freeze（Rolling 冻结摘要）](../archive/strategy-research/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md)
- [Stage B v2/v3 sweep（feature-only 降级决策）](../archive/strategy-research/2026-07-03-value-area-reacceptance-stage-b/README.md)
- [R29 扩样与随机基准复验](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
- [R28 value_area_reacceptance 结构诊断](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md)
- [R27 扩样复验](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md)

更早归档：

- [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)
- [R1~R15 原始实验记录](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/)
- [结构型 Alpha 随机对照阶段归档](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)

如果需要追溯上一阶段详细实验过程，再从归档目录进入：

- [raw-roadmap](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-roadmap/README.md)
- [raw-workbench](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/README.md)

## 6. 给 AI 的阅读顺序

后续 AI 接手策略研究时：

```text
1. 先读 docs/research/strategy-current.md；
2. 再读当前主线主题 docs/research/themes/va-asymmetry-composite/README.md
   （会导向 strategy-math-spec.md / experiment-plan.md / parameter-selection-spec.md）；
3. 为确认上游组件冻结状态，再读：
   - poc-value-area-asymmetry README + stage4-findings（分类器合同）
   - structural-shaping-alpha README + stage1-summary（工具合同 & 真实成本模型）
4. 为了 Stage 0 立题复现，先精读 archive:2026-07-09-poc-va-shaping 的
   stage3-shaping-result.md 与对应脚本，拿到基准 Sharpe/MDD/事件列表；
5. 不要继续在旧 baseline 上调 reentry_take_profit_r 或 value_area 家族任何参数；
6. 前置组件参数（分类器 tier / 塑形 SL/TP/TH / 成本模型）在新主题内视为冻结常量；
7. 新实验过程写入 docs/workbench/va-asymmetry-composite-stage<N>-<topic>.md；
8. 阶段稳定后再归档到 docs/archive。
```
