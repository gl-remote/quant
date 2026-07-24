# 策略当前研究进度

> 类型：Research / 当前策略研究状态
> 状态：**无活跃策略主题（2026-07-14）** · va-asymmetry-revisit 已因假设全线证伪彻底废弃归档 · va-asymmetry / value-area 两大家族全部证伪 · structural-shaping-alpha 保留为工具资产
> 最近更新：2026-07-13
> 归档批次：[archive:2026-07-13-va-asymmetry-leak-chain-consolidated](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/README.md)（**必读**）
> 家族归档：[archive:2026-07-17-value-area-family-consolidated](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md)
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)

## 1. 当前一句话结论

```text
2026-07-13 · va-asymmetry 系列（07-08 ~ 07-13 共 7 个批次 + 主题目录）
整条错误路径归档：所有性能类数字结论作废，原因是 daily 特征 pipeline
在事件触发时使用了当日 event_time 之后的 5m bars（未来信息泄漏）。
4 层证据链（含截断法因果判据）见:
archive:2026-07-13-va-asymmetry-leak-chain-consolidated#README

可继承的方法论遗产（详细清单见封装 README）:
- Stage 1-4 判据框架 · cluster bootstrap · Bonferroni · 7 层严格判据
- 分类器 v4.0 的 6 阵营坐标切分结构（tier 定义本身无问题）
- P0-P9 实验设计模板
- 截断法泄漏检测范式
- 工程侧 5m 实盘化 pipeline 基础设施

被作废的数字（禁止引用）:
- B0=S1×W0×VW0 · Sharpe 2.70 · 年化 15.10%
- 塑形基线 · SL1.0/TP1.4/TH8h · 年化 15.45% · Sharpe 2.23
- 研究侧全量回测 · 年化 63.44% · 夏普 3.47 · 613 笔
- P0-P9 所有对照数字
- Stage 3/4 各 tier 的单笔 IR / 品种保留率 / FDR
- 任何相对 B0 的配对增量评估结论

previously 冻结:
- value_area 家族两个主题于 2026-07-03 / 2026-07-05 冻结，
  主题假设链完全崩塌（POC / rolling POC / reacceptance / 距离档均被证伪）；
- structural-shaping-alpha 阶段 1 gatekeeper 未通过，
  降级为"alpha 变现的必要条件而非独立 alpha 源"。
```

边界：

```text
1. value_area 家族（reacceptance_baseline / random_baseline / multi_attempt_poc_reversion）
   已于 2026-07-15 从 workspace/strategies 归档到
   archive:2026-07-05-value-area-rolling-reacceptance-freeze/raw-strategies/，
   不再作为工程侧可运行策略；若需复现旧规则应从归档目录重新引入最小实现，
   而不是复制回 active 目录；
2. structural-alpha R2-R6 五个原始结构策略（prevday_reacceptance / prevday_volume_filter /
   volume_shock_boundary / hourly_liquidity_sweep / low_volatility_restart）
   已于 2026-07-15 归档到
   archive:2026-06-29-structural-alpha-random-baseline/raw-strategies/，
   随机对照阶段已完成，不再维护；
3. va-asymmetry-composite 主题目录已整体归档到 archive:2026-07-13-va-asymmetry-leak-chain-consolidated/theme-va-asymmetry-composite/；
   工程侧 va_asymmetry_composite_strategy.py 于 2026-07-15 一并归档到该批次的
   2026-07-10-va-asymmetry-composite/raw-strategies/；
4. poc-value-area-asymmetry 主题目录已整体归档到 archive:2026-07-13-va-asymmetry-leak-chain-consolidated/theme-poc-value-area-asymmetry/，Stage 1-4 数字全部作废，仅方法论/分类器结构可作参考；
5. 若要延续 va-asymmetry 假设，必须先重建因果版 daily 特征管道（三条候选路径见封装 README §五）。
```

## 2. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| ~~va-asymmetry-revisit~~ | **⚠️ 已彻底废弃归档（2026-07-14）** · 一日 4 轮因果版实验全线证伪 · pipeline 因果性完好但假设无 alpha · 原主题目录整包搬入 archive | [archive:2026-07-14-va-asymmetry-revisit-full-refutation](../research/archived-notes/2026/07/2026-07-14-va-asymmetry-revisit-full-refutation/README.md) |
| ~~va-asymmetry-composite~~ | **⚠️ 假设证伪归档（2026-07-13）** · 无独立 alpha · 主题目录已整体搬入归档批次 | [archive:...leak-chain-consolidated/theme-va-asymmetry-composite/](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/theme-va-asymmetry-composite/) |
| ~~poc-value-area-asymmetry~~ | **⚠️ 已归档（2026-07-13）** · va-asymmetry 错误链条上游 · Stage 1-4 数字全部作废（daily 特征泄漏）· 仅分类器 v4.0 6 阵营坐标切分结构可作方法论继承 | [archive:...leak-chain-consolidated/theme-poc-value-area-asymmetry/](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/theme-poc-value-area-asymmetry/README.md) |
| structural-shaping-alpha | 活跃 · 阶段 1 完成待冻结候选 · 工具资产保留供引用 | [themes/structural-shaping-alpha/](./themes/structural-shaping-alpha/README.md) |
| ~~strength-factor-screening~~ | **冻结归档（2026-07-17）** / 核心假设证伪 · 8 候选全 L4 · 强度不比方向容易识别 | [archive:2026-07-17-strength-factor-screening-freeze](../research/archived-notes/2026/07/2026-07-17-strength-factor-screening-freeze/freeze-summary.md) |
| ~~value_area_reacceptance~~ | **冻结归档（2026-07-03）** / feature-only 降级 | [archive:2026-07-17-value-area-family-consolidated](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md) |
| ~~value_area_rolling_reacceptance~~ | **冻结归档（2026-07-05）** / 主题假设完全证伪 | [archive:2026-07-17-value-area-family-consolidated](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md) |

家族总结：[archive:2026-07-17-value-area-family-consolidated](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md) · [themes-frozen/structural-shaping-alpha/README.md](./themes-frozen/structural-shaping-alpha/README.md)

**当前活跃策略主题**：无（va-asymmetry-revisit 已于 2026-07-14 彻底废弃归档）。工具/方法论主题保留：

- 分类器结构参考（数字作废，仅结构可继承，**已归档**）：archive:...leak-chain-consolidated/theme-poc-value-area-asymmetry/
- 塑形工具资产：`docs/research/themes/structural-shaping-alpha/`

## 3. 当前基础设施

保留代码：

```text
structural_shaping_toolkit
- structural-shaping-alpha 主题保留的工具资产（非独立策略）；
- 包含 First-Passage Designer（SL/TP/TH 参数扫描）、ν_implied 归因、真实成本模型
  （滑点 0.15 ATR × (0.5+SlippageTier) + 手续费 0.03% 双边）、
  Cluster bootstrap、跨周期稳健性检验（KF-1 至 KF-7）；
- 位置：research/themes/structural-shaping-alpha/ 下组件脚本。

poc_va_asymmetry_classifier_v4
- poc-value-area-asymmetry 主题（**已归档**）的分类器 v4.0 实现（组件级）；
- 包含 tier 判定（6 tier 合并）、14 条严格性约束、品种/月份前缀过滤、ATR 归一化；
- ⚠️ 分类器结构本身无问题，但归一化输入的原研究基线数字（tier 单笔 IR 等）
  已作废（依赖泄漏的 A3_skew_spec / daily_atr_spec / trend_ret_M_spec）；
- 位置：workspace/strategies/classifiers/poc_va.py（长期代码）。
```

已归档策略代码（不再位于 `workspace/strategies/`，仅可从 archive 目录参考）：

```text
va_asymmetry_composite_strategy      → archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-10-va-asymmetry-composite/raw-strategies/
value_area_reacceptance_baseline     → archive:2026-07-05-value-area-rolling-reacceptance-freeze/raw-strategies/
value_area_random_baseline           → archive:2026-07-05-value-area-rolling-reacceptance-freeze/raw-strategies/
value_area_multi_attempt_poc_reversion → archive:2026-07-05-value-area-rolling-reacceptance-freeze/raw-strategies/
prevday_reacceptance                 → archive:2026-06-29-structural-alpha-random-baseline/raw-strategies/
prevday_volume_filter                → archive:2026-06-29-structural-alpha-random-baseline/raw-strategies/
volume_shock_boundary                → archive:2026-06-29-structural-alpha-random-baseline/raw-strategies/
hourly_liquidity_sweep               → archive:2026-06-29-structural-alpha-random-baseline/raw-strategies/
low_volatility_restart               → archive:2026-06-29-structural-alpha-random-baseline/raw-strategies/
```

工程侧当前仍在 `workspace/strategies/` 长期维护的策略：`ma_strategy`、`atr_strategy`
（骨架/示例策略，供切面 DSL 与运行时框架回归使用），以及 `classifiers/poc_va` 组件。

## 4. 关键归档结论（历史备忘）

| 阶段 | 结论 | 归档 |
| --- | --- | --- |
| R27 外推降级 | 旧 m/SR + 1m + A4_ratio_80 单笔 POC 回归候选外推失败 | [2026-07-02](../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md) |
| R28 结构诊断 | DCE.p 四样本内收益主要来自第 2 笔，第 1 笔更像 VA reacceptance | [2026-07-02](../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md) |
| R29 扩样 + 随机基准复验 | 固定规则不通过外推；但结构仍优于随机基准 → 触发 Stage B | [2026-07-02](../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| Stage B v2 双 Q | Q_return 通过（C3 @ n=144 ret_mean +1.10）/ Q_generalize 未通过 → feature-only 降级 | [2026-07-03](../research/archived-notes/2026/07/2026-07-03-value-area-reacceptance-stage-b/stage-b-sweep-summary.md) |
| Rolling Stage 1 / 1.5 / 4 / 4b | 20 品种 × 70 合约 × 5m/15m 双周期证伪主题全部核心假设 → 主题冻结 | [2026-07-05](../research/archived-notes/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |
| structural-shaping Stage 1 Gatekeeper | 7 combo 全部 realistic-cost 下 μ ≈ -2c / ν_implied≈0 → 塑形非独立 alpha 源，降级为必要条件 + 工具资产 | [2026-07-06](../research/archived-notes/2026/07/2026-07-06-structural-shaping-alpha-stage1/) |
| **va-asymmetry 错误路径链条归并** | **07-08 ~ 07-13 共 7 批次 + va-asymmetry-composite 主题目录整体归档** · 假设由未来信息泄漏支撑 · 无独立 alpha · 方法论遗产保留 | [archive:...leak-chain-consolidated](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/README.md) |

## 5. 下一步

**当前状态**：无活跃策略主题（va-asymmetry-revisit 已于 2026-07-14 彻底废弃归档）。近期路径：

1. **等待新研究方向**：direction-strength-combo 主题已删除，等待新方向立题
2. **同步维护**塑形工具资产（structural-shaping-alpha）

**任何新主题必须遵守的方法论前置约束**（继承自 value-area 家族 + va-asymmetry 家族证伪 + 前序主题教训）：

```text
1. 距离/大小/时间统一 ATR 归一化；
2. 判据用期望净值（成本后），不用 reach_rate 单指标；
3. 结构 × 距离档二维联合优化，不能单结构定论；
4. 多锚点 + 多触发器 + no_trigger baseline 三层对照；
5. 配对差异检验（同一批事件配对），避免未配对样本假象；
6. Cluster bootstrap 检验事件非独立性；
7. 跨周期验证（至少 5m + 15m）作为稳健性硬门槛；
8. 立题前先说明为什么本次假设不落入 value-area / va-asymmetry 家族已证伪的假设中；
9. 塑形 + 组合层必须显式核算"事件净期望 × 频率 × 资本效率"三乘积；
10. 名义暴露压缩约束（100%/200%/400% 三档对比），避免无限杠杆美化夏普；
11. 组合关前所有组件参数冻结为 L1（分类器）+ L2（塑形），禁止回看式调参；
12. **【新增】若涉及 daily 特征聚合**：立题第一步必须跑截断法验证
    （archive:...leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak/
    raw-scripts/verify_leak_by_truncation.py），
    禁止用未通过截断法验证的 daily 特征做交易决策。
```

详见：
- [archive:2026-07-17-value-area-family-consolidated#共同教训](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md)
- [archive:2026-07-13-va-asymmetry-leak-chain-consolidated#README](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/README.md)

## 6. 文档地图

| 目的 | 文档 |
| --- | --- |
| 当前状态入口 | 本文件 |
| **va-asymmetry 错误路径归并封装（必读）** | [archive:...leak-chain-consolidated](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/README.md) |
| poc-value-area-asymmetry（**已归档** · 只读只做方法论参考） | [archive:...leak-chain-consolidated/theme-poc-value-area-asymmetry/](../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/theme-poc-value-area-asymmetry/README.md) |
| structural-shaping-alpha（塑形工具资产 · 上游） | [themes/structural-shaping-alpha/](./themes/structural-shaping-alpha/README.md) |
| value_area 家族总结（**已归档**） | [archive:2026-07-17-value-area-family-consolidated](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/README.md) |
| value_area_reacceptance（**已归档**） | [archive:2026-07-17-value-area-family-consolidated/value-area-reacceptance/](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/value-area-reacceptance/README.md) |
| value_area_rolling_reacceptance（**已归档**） | [archive:2026-07-17-value-area-family-consolidated/value-area-rolling-reacceptance/](../research/archived-notes/2026/07/2026-07-17-value-area-family-consolidated/value-area-rolling-reacceptance/README.md) |
| Rolling 冻结摘要 | [freeze-summary.md](../research/archived-notes/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |
| structural-shaping Stage 1（归档） | [2026/07/2026-07-06-structural-shaping-alpha-stage1](../research/archived-notes/2026/07/2026-07-06-structural-shaping-alpha-stage1/) |
| Stage B 归档 | [stage-b-sweep-summary.md](../research/archived-notes/2026/07/2026-07-03-value-area-reacceptance-stage-b/stage-b-sweep-summary.md) |
| R29 扩样 + 随机基准 | [r29-expanded-validation.md](../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| POC / VA 质量诊断阶段归档 | [quality-summary.md](../research/archived-notes/2026/07/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| 长期框架 | [strategy-research-framework.md](../roadmap/strategy-research-framework.md) |

## 7. 给 AI 的工作规则

```text
1. 先读本文件确认**当前活跃策略主题**：无（direction-strength-combo 已删除）；
2. 必读 archive:2026-07-14-va-asymmetry-revisit-full-refutation#va-asymmetry-family-retrospective
   了解 va-asymmetry 家族 8+ 天全周期复盘 · 5 条系统性错误 · 6 条 skill 补丁建议；
3. 必读 archive:2026-07-13-va-asymmetry-leak-chain-consolidated#README
   了解 va-asymmetry 家族错误路径链条与方法论遗产；
4. 遵守 §5 的 12 条方法论前置约束（第 12 条：涉及 daily 特征聚合的必须先过截断法）；
5. 需要 value-area 家族历史细节时读 archive:2026-07-17-value-area-family-consolidated/ 与对应 archive；
6. 不要在冻结/归档主题目录下增加新实验（含
   archive:...leak-chain-consolidated/theme-va-asymmetry-composite/）；
7. 若发现数据周期、成交配对、成本口径、事件时间对齐问题，
   先写 docs/issues 并暂停受影响实验；
8. 所有结论需同时给出"不压缩名义 / 2× 压缩 / 4× 压缩"三档夏普/回撤/换手对照，
   避免用无约束杠杆美化结果。
```
