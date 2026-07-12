# 策略当前研究进度

> 类型：Research / 当前策略研究状态
> 状态：**va-asymmetry-composite v1.0 已归档 · v2.0 重启开发中（2026-07-10）** · poc-value-area-asymmetry 分类器 v4.0 冻结 · structural-shaping-alpha 阶段 1 完成（待冻结候选）· value-area 家族全部冻结
> 最近更新：2026-07-09
> 当前主题：[va-asymmetry-composite](./themes/va-asymmetry-composite/README.md)
> 前置 Alpha 源：[poc-value-area-asymmetry](./themes/poc-value-area-asymmetry/README.md)
> 前置塑形工具：[structural-shaping-alpha](./themes/structural-shaping-alpha/README.md)
> 家族归档：[themes-frozen/value-area/](./themes-frozen/value-area/README.md)
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)

## 1. 当前一句话结论

```text
value_area 家族两个主题于 2026-07-03 / 2026-07-05 先后冻结，
主题假设链完全崩塌（POC / rolling POC / reacceptance / 距离档均被证伪）。

2026-07-05 立题 structural-shaping-alpha：
检验"结构塑形本身是否具有独立 alpha"，阶段 1 gatekeeper 未通过
（7 combo 全部 realistic-cost 下 mean ≈ -2c 或 μ_implied≈0 伪影），
塑形降级为"alpha 变现的必要条件而非独立 alpha 源"。
工具资产（First-Passage Designer / ν_implied 归因 / 真实成本模型 / KF 方法论）
保留供后续主题引用。

2026-07-07 立题 poc-value-area-asymmetry：
检验"POC 两侧 value area 形状不对称是否携带方向 alpha"，
经过 4 阶段完整验证（143 合约 · 36625 events · 20 品种前缀 · FDR 校正 · 7 层严格性），
分类器 v4.0（6 类合并版）冻结，输出 A/A- 级 9 档可用 tier，
单笔 IR 0.28~0.46 · 品种保留 ≥ 60% · 分类器主动性研究暂停，留待下游策略层引用。
archive:2026/07/2026-07-09-poc-va-shaping 在同一分类器上完成塑形参数扫描
与风控口径验证（年化 15.45% / Sharpe 2.23 / MaxDD -7.51 / 胜率 60.3% / 盈亏比 1.41），
alpha 变现路径 POC 通过。

2026-07-09 立新主题 va-asymmetry-composite（**当前主线**）：
把 poc-value-area-asymmetry 分类器（alpha 源）+ structural-shaping-alpha 工具
（塑形/成本/归因）+ archive:2026/07/2026-07-09-poc-va-shaping 塑形参数，
经品种筛选 / 信号强度加权 / 多空权重优化三道组合关，压缩到 100% 名义
暴露约束下，目标构建夏普 ≥ 2.5、年化净收益 ≥ 18%、可实盘的完整交易策略。
阶段 1 Gatekeeper 三大方向 0/6 通过，B0=S1×W0×VW0 即最优（Sharpe 2.70 · 年化 15.10% · MaxDD −2.40%）。
当前待决策：路径 A（直接工程化）或路径 B（提名义上限至 120%）。
```

边界：

```text
1. value_area_reacceptance_baseline 只保留为历史 baseline，不再作为候选策略；
2. value_area_random_baseline 作为长期随机入场基准保留；
3. 前主题 C3 特征仍可作为 feature 供下游主题引用（Group_M concentration risk 高，需在目标品种上重验）；
4. 主题冻结不否定 VA reacceptance 事件的信息量，但否定
   "VA reacceptance / POC / rolling POC / 4+ ATR 距离档" 作为独立策略的可行性。
```

## 2. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| **va-asymmetry-composite** | **重启开发态（v1.0 已归档 · 2026-07-10）** | [themes/va-asymmetry-composite/](./themes/va-asymmetry-composite/README.md) · [v1.0 归档](../archive/strategy-research/2026/07/2026-07-10-va-asymmetry-composite/) |
| poc-value-area-asymmetry | 活跃 · 阶段 4 完成 · 分类器 v4.0 冻结 · 主动性研究暂停（供下游引用） | [themes/poc-value-area-asymmetry/](./themes/poc-value-area-asymmetry/README.md) |
| structural-shaping-alpha | 活跃 · 阶段 1 完成待冻结候选 · 工具资产保留供引用 | [themes/structural-shaping-alpha/](./themes/structural-shaping-alpha/README.md) |
| value_area_reacceptance | 冻结 / feature-only 降级 | [themes-frozen/value-area/value-area-reacceptance/](./themes-frozen/value-area/value-area-reacceptance/README.md) |
| value_area_rolling_reacceptance | **冻结（2026-07-05）** / 主题假设完全证伪 | [themes-frozen/value-area/value-area-rolling-reacceptance/](./themes-frozen/value-area/value-area-rolling-reacceptance/README.md) |

家族总结：[themes-frozen/value-area/README.md](./themes-frozen/value-area/README.md)

**活跃主题目录**：
- 当前主线：`docs/research/themes/va-asymmetry-composite/`（**v2.0 重启开发态**，旧 v1.0 已归档）
- 上游 Alpha 源：`docs/research/themes/poc-value-area-asymmetry/`（分类器组件）
- 上游工具资产：`docs/research/themes/structural-shaping-alpha/`（塑形 / 成本 / 归因工具）

## 3. 当前基础设施

当前保留的 active 策略代码：

```text
value_area_reacceptance_baseline
- 旧 value_area_reacceptance 实现的 baseline 版本；
- 用于历史复现（R27-R29 旧规则、结构诊断、随机基准对照）；
- 不再代表当前候选交易策略。

value_area_random_baseline
- 长期随机入场基准；
- 在 VA baseline 的事件、止损和退出口径上随机化入场；
- 用于判断结构入口是否优于随机。

poc_va_asymmetry_classifier_v4
- poc-value-area-asymmetry 主题冻结的分类器 v4.0 实现（组件级）；
- 包含 tier 判定（6 tier 合并）、14 条严格性约束、品种/月份前缀过滤、ATR 归一化；
- 不做塑形/风控，仅输出事件标签与信号强度（skew / d_mid / 3D product）；
- 位置：research/themes/poc-value-area-asymmetry/ 下组件脚本，待下游策略层包装。

structural_shaping_toolkit
- structural-shaping-alpha 主题保留的工具资产（非独立策略）；
- 包含 First-Passage Designer（SL/TP/TH 参数扫描）、ν_implied 归因、真实成本模型
  （滑点 0.15 ATR × (0.5+SlippageTier) + 手续费 0.03% 双边）、
  Cluster bootstrap、跨周期稳健性检验（KF-1 至 KF-7）；
- 位置：research/themes/structural-shaping-alpha/ 下组件脚本。

va_asymmetry_composite
- va-asymmetry-composite 主线策略（**目标输出**）：整合分类器 + 塑形 + 组合优化；
- Stages 0-3 为向量化模拟脚本（backtest_tools vectorized pipeline），
  Stage 4 为 vnpy 事件驱动策略；
- 当前占位：research/themes/va-asymmetry-composite/（文档 + Stage 0-1 完成，B0 锁定，待工程化）。
```

轻量比较 runner（已归档）：

```text
docs/archive/strategy-research/2026/06/2026-06-29-structural-alpha-random-baseline/raw-scripts/value_area_random_baseline_compare.py
```

注意：该 runner 输出使用 vnpy BacktestResult 口径，只做同一 runner 下相对比较，不替代 trade_clearings 清算口径。

## 4. 关键归档结论（历史备忘）

以下均为已完成阶段的结论，进入 archive；本节仅列关键要点便于快速定位。

| 阶段 | 结论 | 归档 |
| --- | --- | --- |
| R27 外推降级 | 旧 m/SR + 1m + A4_ratio_80 单笔 POC 回归候选外推失败 | [2026-07-02](../archive/strategy-research/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md) |
| R28 结构诊断 | DCE.p 四样本内收益主要来自第 2 笔，第 1 笔更像 VA reacceptance | [2026-07-02](../archive/strategy-research/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md) |
| R29 扩样 + 随机基准复验 | 固定规则不通过外推；但结构仍优于随机基准 → 触发 Stage B | [2026-07-02](../archive/strategy-research/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| Stage B v2 双 Q | Q_return 通过（C3 @ n=144 ret_mean +1.10）/ Q_generalize 未通过（Group_M 5/8 无 trade）→ feature-only 降级 | [2026-07-03](../archive/strategy-research/2026/07/2026-07-03-value-area-reacceptance-stage-b/stage-b-sweep-summary.md) |
| Rolling Stage 1 / 1.5 / 4 / 4b | 20 品种 × 70 合约 × 5m/15m 双周期证伪主题全部核心假设 → 主题冻结 | [2026-07-05](../archive/strategy-research/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |
| structural-shaping Stage 1 Gatekeeper | 7 combo 全部 realistic-cost 下 μ ≈ -2c / ν_implied≈0 → 塑形非独立 alpha 源，降级为必要条件 + 工具资产 | [2026-07-06](../archive/strategy-research/2026/07/2026-07-06-structural-shaping-alpha-stage1/) |
| poc-va-asymmetry Stage 3/4 | 分类器 v4.0 冻结 · 9 档 A/A- tier · 单笔 IR 0.28~0.46 · 品种保留 ≥ 60% · FDR ≤ 5% | [2026-07-08](../archive/strategy-research/2026/07/2026-07-08-poc-va-asymmetry/) |
| poc-va-shaping Stage 2/3 组合验证 | 在分类器 v4.0 + SL1.0/TP1.4/TH8h 下 · 净 15.45% / Sharpe 2.23 / MaxDD -7.51 / 胜率 60.3% · alpha 变现 POC | [2026-07-09](../archive/strategy-research/2026/07/2026-07-09-poc-va-shaping/) |

## 5. 下一步

**当前主题**：[va-asymmetry-composite](./themes/va-asymmetry-composite/README.md)（**v2.0 重启开发态** · 旧 v1.0 已归档至 [archive/2026/07/2026-07-10-va-asymmetry-composite](../archive/strategy-research/2026/07/2026-07-10-va-asymmetry-composite/)）

旧 v1.0 的 B0=S1×W0×VW0（Sharpe 2.70 · 年化 15.10% · MaxDD −2.40%）作为 **frozen control baseline**，
任何新底层逻辑须相对 B0 做同一批事件的配对增量（≥0.2 夏普）评估。
本次重启将修订**底层逻辑**与**探索计划**，具体待定义。

详见新主题 [strategy-math-spec.md](./themes/va-asymmetry-composite/strategy-math-spec.md)。

**立题时的方法论前置约束**（继承自 value-area 家族 + 前序主题教训，任何新主题必须遵守）：

```text
1. 距离/大小/时间统一 ATR 归一化；
2. 判据用期望净值（成本后），不用 reach_rate 单指标；
3. 结构 × 距离档二维联合优化，不能单结构定论；
4. 多锚点 + 多触发器 + no_trigger baseline 三层对照；
5. 配对差异检验（同一批事件配对），避免未配对样本假象；
6. Cluster bootstrap 检验事件非独立性；
7. 跨周期验证（至少 5m + 15m）作为稳健性硬门槛；
8. 立题前先说明为什么本次假设不落入 value-area 家族已证伪的四条中；
9. 塑形 + 组合层必须显式核算"事件净期望 × 频率 × 资本效率"三乘积，不单独看单笔均值；
10. 名义暴露压缩约束（100%/200%/400% 三档对比），避免无限杠杆美化夏普；
11. 组合关前所有组件参数冻结为 L1（分类器）+ L2（塑形），禁止回看式调参。
```

详见：
- [themes-frozen/value-area/README.md #共同教训](./themes-frozen/value-area/README.md)
- [poc-value-area-asymmetry stage4-findings.md](./themes/poc-value-area-asymmetry/workbench/stage4-findings.md)
- [archive:2026/07/2026-07-09-poc-va-shaping stage3-shaping-result.md](../archive/strategy-research/2026/07/2026-07-09-poc-va-shaping/workbench/stage3-shaping-result.md)

## 6. 文档地图

| 目的 | 文档 |
| --- | --- |
| 当前状态入口 | 本文件 |
| **va-asymmetry-composite（v2.0 重启开发态 · 原 v1.0 已归档）** | [themes/va-asymmetry-composite/](./themes/va-asymmetry-composite/README.md) · [v1.0 归档](../archive/strategy-research/2026/07/2026-07-10-va-asymmetry-composite/) |
| poc-value-area-asymmetry（分类器 v4.0 · 上游 Alpha） | [themes/poc-value-area-asymmetry/](./themes/poc-value-area-asymmetry/README.md) |
| structural-shaping-alpha（塑形工具资产 · 上游） | [themes/structural-shaping-alpha/](./themes/structural-shaping-alpha/README.md) |
| value_area 家族总结（冻结） | [themes-frozen/value-area/README.md](./themes-frozen/value-area/README.md) |
| value_area_reacceptance（冻结） | [themes-frozen/value-area/value-area-reacceptance/](./themes-frozen/value-area/value-area-reacceptance/README.md) |
| value_area_rolling_reacceptance（冻结） | [themes-frozen/value-area/value-area-rolling-reacceptance/](./themes-frozen/value-area/value-area-rolling-reacceptance/README.md) |
| Rolling 冻结摘要 | [freeze-summary.md](../archive/strategy-research/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |
| structural-shaping Stage 1（归档） | [2026/07/2026-07-06-structural-shaping-alpha-stage1](../archive/strategy-research/2026/07/2026-07-06-structural-shaping-alpha-stage1/) |
| poc-va-asymmetry 分类器验证（归档） | [2026/07/2026-07-08-poc-va-asymmetry](../archive/strategy-research/2026/07/2026-07-08-poc-va-asymmetry/) |
| **poc-va-shaping 组合验证（当前立题起点 · 归档）** | [2026/07/2026-07-09-poc-va-shaping](../archive/strategy-research/2026/07/2026-07-09-poc-va-shaping/) |
| Stage B 归档 | [stage-b-sweep-summary.md](../archive/strategy-research/2026/07/2026-07-03-value-area-reacceptance-stage-b/stage-b-sweep-summary.md) |
| R29 扩样 + 随机基准 | [r29-expanded-validation.md](../archive/strategy-research/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| POC / VA 质量诊断阶段归档 | [quality-summary.md](../archive/strategy-research/2026/07/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| 长期框架 | [strategy-research-framework.md](../roadmap/strategy-research-framework.md) |

## 7. 给 AI 的工作规则

后续 AI 接手时：

```text
1. 先读本文件确认当前活跃主题为 va-asymmetry-composite（**v2.0 重启开发态**，旧 v1.0 已归档）；新逻辑须相对归档 B0 做配对增量评估
   + poc-value-area-asymmetry（分类器引用）+ structural-shaping-alpha（工具引用）；
2. 读 themes/va-asymmetry-composite/README.md 与 experiment-plan.md 了解阶段进度与门槛；
3. 遵守 §5 的 11 条方法论前置约束，尤其是"多层对照""跨周期验证""三乘积核算""名义暴露压缩"；
4. 需要 value-area 家族历史细节时读 themes-frozen/value-area/ 与对应 archive；
5. 不要继续调旧 baseline 参数（value_area_reacceptance_baseline 只作历史复现工具）；
6. 不要在冻结主题目录（themes-frozen/*/）下增加新实验；
7. 前置组件参数（分类器 tier 表 / 塑形 SL/TP/TH / 成本模型）在新主题内视为冻结常量，
   除非发现数据错误或分类器 bug；所有参数变更必须在 workbench 记录并写进 parameter-selection-spec；
8. 新实验过程写入 docs/workbench/va-asymmetry-composite-stage<N>-<topic>.md；
   阶段稳定后再归档到 docs/archive；
9. 若发现数据周期、成交配对、成本口径、品种月份过滤、事件时间对齐问题，
   先写 docs/issues 并暂停受影响实验；
10. 所有结论需同时给出"不压缩名义 / 2× 压缩 / 4× 压缩"三档夏普/回撤/换手对照，
    避免用无约束杠杆美化结果。
```
