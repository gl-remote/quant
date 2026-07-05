# 策略当前研究进度

> 类型：Research / 当前策略研究状态
> 状态：**无活跃主题**（value_area 家族全部冻结）
> 最近更新：2026-07-05
> 最近归档：[value_area_rolling_reacceptance Freeze](../archive/strategy-research/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md)
> 家族归档：[themes-frozen/value-area/](./themes-frozen/value-area/README.md)
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)

## 1. 当前一句话结论

```text
value_area 家族两个主题全部冻结：
- value_area_reacceptance（2026-07-03）：Stage B v2 双 Q 判据未同时达标 →
  feature-only 降级 / 主策略暂停。
- value_area_rolling_reacceptance（2026-07-05）：Stage 1 / 1.5 / 4 / 4b
  完整实验链证伪 POC 特殊性（fixed + rolling）、reacceptance 触发器特殊性、
  4+ ATR 距离档独立 edge → 主题假设完全崩塌。

当前无活跃策略主题。下一主题需另立立题。
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
| value_area_reacceptance | 冻结 / feature-only 降级 | [themes-frozen/value-area/value-area-reacceptance/](./themes-frozen/value-area/value-area-reacceptance/README.md) |
| value_area_rolling_reacceptance | **冻结（2026-07-05）** / 主题假设完全证伪 | [themes-frozen/value-area/value-area-rolling-reacceptance/](./themes-frozen/value-area/value-area-rolling-reacceptance/README.md) |

家族总结：[themes-frozen/value-area/README.md](./themes-frozen/value-area/README.md)

**活跃主题目录**：`docs/research/themes/` 当前为空。

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
```

轻量比较 runner：

```text
scripts/analysis/value_area_random_baseline_compare.py
```

注意：该 runner 输出使用 vnpy BacktestResult 口径，只做同一 runner 下相对比较，不替代 trade_clearings 清算口径。

## 4. 关键归档结论（历史备忘）

以下均为已完成阶段的结论，进入 archive；本节仅列关键要点便于快速定位。

| 阶段 | 结论 | 归档 |
| --- | --- | --- |
| R27 外推降级 | 旧 m/SR + 1m + A4_ratio_80 单笔 POC 回归候选外推失败 | [2026-07-02](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md) |
| R28 结构诊断 | DCE.p 四样本内收益主要来自第 2 笔，第 1 笔更像 VA reacceptance | [2026-07-02](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md) |
| R29 扩样 + 随机基准复验 | 固定规则不通过外推；但结构仍优于随机基准 → 触发 Stage B | [2026-07-02](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| Stage B v2 双 Q | Q_return 通过（C3 @ n=144 ret_mean +1.10）/ Q_generalize 未通过（Group_M 5/8 无 trade）→ feature-only 降级 | [2026-07-03](../archive/strategy-research/2026-07-03-value-area-reacceptance-stage-b/stage-b-sweep-summary.md) |
| Rolling Stage 1 / 1.5 / 4 / 4b | 20 品种 × 70 合约 × 5m/15m 双周期证伪主题全部核心假设 → 主题冻结 | [2026-07-05](../archive/strategy-research/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |

## 5. 下一步

**当前无活跃主题。** 下一主题需要用户/策略研究者主动立题。立题时的方法论前置约束（继承自 value-area 家族的教训）：

```text
1. 距离/大小/时间统一 ATR 归一化；
2. 判据用期望净值（成本后），不用 reach_rate 单指标；
3. 结构 × 距离档二维联合优化，不能单结构定论；
4. 多锚点 + 多触发器 + no_trigger baseline 三层对照；
5. 配对差异检验（同一批事件配对），避免未配对样本假象；
6. Cluster bootstrap 检验事件非独立性；
7. 跨周期验证（至少 5m + 15m）作为稳健性硬门槛；
8. 立题前先说明为什么本次假设不落入 value-area 家族已证伪的四条中。
```

详见 [themes-frozen/value-area/README.md #共同教训](./themes-frozen/value-area/README.md)。

## 6. 文档地图

| 目的 | 文档 |
| --- | --- |
| 当前状态入口 | 本文件 |
| value_area 家族总结 | [themes-frozen/value-area/README.md](./themes-frozen/value-area/README.md) |
| value_area_reacceptance 主题（冻结）| [themes-frozen/value-area/value-area-reacceptance/](./themes-frozen/value-area/value-area-reacceptance/README.md) |
| value_area_rolling_reacceptance 主题（冻结）| [themes-frozen/value-area/value-area-rolling-reacceptance/](./themes-frozen/value-area/value-area-rolling-reacceptance/README.md) |
| Rolling 冻结摘要 | [freeze-summary.md](../archive/strategy-research/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |
| Stage B 归档 | [stage-b-sweep-summary.md](../archive/strategy-research/2026-07-03-value-area-reacceptance-stage-b/stage-b-sweep-summary.md) |
| R29 扩样 + 随机基准 | [r29-expanded-validation.md](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| POC / VA 质量诊断阶段归档 | [quality-summary.md](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| 长期框架 | [strategy-research-framework.md](../roadmap/strategy-research-framework.md) |

## 7. 给 AI 的工作规则

后续 AI 接手时：

```text
1. 先读本文件确认没有活跃主题；
2. 若要立新主题，先阅读 themes-frozen/value-area/README.md 的共同教训与方法论约束；
3. 需要历史 R27-R29 / Stage B / Rolling Stage 1-4b 细节时读对应 archive 目录；
4. 不要继续调旧 baseline 参数（value_area_reacceptance_baseline 只作历史复现工具）；
5. 不要在冻结主题目录下增加新实验（应立新主题，写入 docs/workbench/）；
6. 新实验过程写入 docs/workbench；阶段稳定后再归档到 docs/archive；
7. 若发现数据周期、成交配对、成本口径问题，先写 docs/issues 并暂停受影响实验；
8. 立新主题时严格遵循 §5 的八条方法论前置约束，尤其是"多层对照"和"跨周期验证"。
```
