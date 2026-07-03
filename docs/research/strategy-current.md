# 策略当前研究进度

> 类型：Research / 当前策略研究状态
> 状态：活跃 / R29 扩样未通过 / 进入 R30 多次 VA 回归与 continuation 分支验证
> 最近更新：2026-07-02
> 当前归档：[R29 扩样与随机基准复验](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 前置归档：[R28 结构诊断](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md)
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)

## 1. 当前一句话结论

```text
旧 value_area_reacceptance 实盘候选规则已降级为 value_area_reacceptance_baseline。

R29 扩样显示：
1. 固定规则不能通过外推验证；
2. DCE.p 旧窗口、DCE.m、DCE.c/cs 均未形成稳健收益；
3. 但随机入场复验显示，VA reacceptance 结构入口仍优于 same-direction / random-direction 随机基准。

当前研究重心从“继续调旧策略参数”切换为：
R30 多次 VA 回归测试 / continuation 分支拆分。
```

边界：

```text
1. value_area_reacceptance_baseline 只保留为历史 baseline，不再作为当前候选交易策略继续叠加逻辑；
2. value_area_random_baseline 作为长期随机入场基准保留；
3. R29 失败不能直接否定 VA reacceptance 事件的信息量；
4. 后续必须把 VA 回归和 continuation 分开验证，不再混在 seq1/seq2/seq3 的机械 reentry 规则里优化。
```

## 2. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| value_area_reacceptance | 活跃 / R30 结构分支验证 | [themes/value-area-reacceptance/](./themes/value-area-reacceptance/README.md) |

## 3. 当前基础设施

当前保留的 active 策略代码：

```text
value_area_reacceptance_baseline
- 旧 value_area_reacceptance 实现的 baseline 版本；
- 用于复现 R27-R29 旧规则、结构诊断、随机基准对照；
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

## 4. 最近关键结论

### 4.1 R27 外推降级

```text
旧 m/SR + 1m + A4_ratio_80 单笔 POC 回归候选外推失败；
不能继续把旧 m/SR 线作为主候选硬调。
```

### 4.2 R28 结构诊断

```text
DCE.p 四样本内，放开每日最多 3 笔后，收益主要来自第 2 笔；
第 1 笔更像 VA reacceptance / 价值回归；
第 2/3 笔可能更接近 failed-probe continuation / retry。
```

### 4.3 R29 扩样与随机基准

```text
固定 R28 后的保守候选扩样未通过；
R28 DCE.p 四样本优势不能外推到更早 DCE.p 历史；
DCE.m 明显失败，DCE.c/cs 信号不足或弱负；
DCE.y 有 seq2 局部线索，但整体不过关。

随机入场复验显示：
旧 DCE.p 失败样本上，结构仍优于 same-direction/random-direction 随机基准；
因此问题更可能在市场环境、风险空间、交易序列或退出兑现层，不能简单判定 VA reacceptance 是无信息噪声。
```

## 5. R30 候选研究方向

R30 不继续无约束调参，先验证结构分支：

```text
A. VA 回归主线
   - 只做 VA 边界 → POC 更近方向；
   - 将多次交易统一解释为多次 VA → POC 回归测试；
   - 开仓候选条件：首次测试 POC / 当前突破 VA 距离弱于上次 / 上次 POC 未充分测试。

B. continuation 对照线
   - 做远离 POC 的方向；
   - 只作为 failed reacceptance / continuation 候选；
   - 不与 VA 回归线混在同一组收益结论里评估。
```

核心观测指标：

```text
POC touch rate
entry_to_poc_ticks
breakout_ticks
breakout_ticks_delta
by_condition pnl
B2/B3 overlap pnl
stop_loss 占比
by_environment：strong_trend / trend_bias / non_strong_trend
random baseline percentile
```

## 6. 当前不建议继续的方向

```text
1. 不继续在旧 value_area_reacceptance_baseline 上叠加新交易逻辑；
2. 不继续围绕 reentry_take_profit_r=1.3/1.35 做小样本精调；
3. 不把 R28 DCE.p 四样本视为已验证主线；
4. 不把 seq1/seq2/seq3 混成同一策略的钱；
5. 不把强趋势标签直接作为最终过滤条件，先做结构归因；
6. 不用随机 baseline 的绝对 pnl 替代清算口径，只做同 runner 相对比较。
```

## 7. 下一步优先级

```text
1. 新建 R30 workbench 文档；
2. 实现 VA 多次回归状态：同侧突破距离、POC 是否充分测试、attempt_count；
3. 分别验证 A1/A2 与 B1/B2/B3 条件组合；
4. 用 R29 固定样本先做小矩阵，不先调 stop/target；
5. 每组输出 POC touch rate、breakout_ticks_delta、stop_loss 占比和 by_condition pnl；
6. 用 value_area_random_baseline 复验结构是否仍优于随机。
```

## 8. 文档地图

| 目的 | 文档 |
| --- | --- |
| 当前状态入口 | 本文件 |
| value_area_reacceptance 主题状态 | [themes/value-area-reacceptance/](./themes/value-area-reacceptance/README.md) |
| R29 扩样与随机基准复验 | [value-area-reacceptance-r29-expanded-validation.md](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| R28 结构诊断 | [value-area-reacceptance-r28-structure-diagnosis.md](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md) |
| R27 扩样复验 | [value-area-reacceptance-r27-expanded-sample.md](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md) |
| POC / VA 质量诊断阶段归档 | [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| 长期框架 | [strategy-research-framework.md](../roadmap/strategy-research-framework.md) |

## 9. 给 AI 的工作规则

后续 AI 接手时：

```text
1. 先读本文件；
2. 再读 themes/value-area-reacceptance/README.md（会导向 current.md/spec.md/plan.md/parameter-selection-spec.md）；
3. 需要 R27-R29 细节时读 docs/archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/；
4. 不要继续调旧 baseline 参数；
5. 下一步围绕 R30 多次 VA 回归 / continuation 分支验证；
6. 新实验过程写入 docs/workbench；
7. 阶段稳定后再归档到 docs/archive；
8. 若发现数据周期、成交配对、成本口径问题，先写 docs/issues 并暂停受影响实验。
```
