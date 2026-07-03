# value_area_reacceptance 主题当前研究进度

> 类型：Theme / 主题当前状态
> 状态：Stage B v2 已完成 / feature-only 降级 / 主策略暂停
> 最近更新：2026-07-03
> 主题入口：[README.md](README.md)
> 数学规格：[strategy-math-spec.md](strategy-math-spec.md)
> 研究计划：[experiment-plan.md](experiment-plan.md)
> 参数选择：[parameter-selection-spec.md](parameter-selection-spec.md)
> 工程实现细节：[implementation-notes.md](implementation-notes.md)
> 全局研究入口：[../../strategy-current.md](../../strategy-current.md)
> Stage B 结果：[../../../workbench/stage-b-sweep-summary.md](../../../workbench/stage-b-sweep-summary.md)
> 当前归档：[R29 扩样与随机基准复验](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 前置归档：[R28 结构诊断](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md)

## 1. 主题一句话结论

```text
value_area_reacceptance 主策略在 Stage B v2（事件驱动 AttemptEvent）下
双 Q 判据仍未同时达标：
- Q_return（Group_P 均值提升）：C3 @ n_profile=144 达标（ret_mean +1.10）；
- Q_generalize（Group_M 泛化）：未达标（Group_M 只 2/8 profitable，5/8 无 trade）。

结论：走 feature-only 降级路径。
- C3（次次尝试且未触碰 POC，n_profile=12h）作为独立 feature 保留；
- 主策略暂停作为独立开仓策略，降级为 baseline-only；
- C2 因 spec §5.2 X_s 极值化的语义必然，恒不触发（不是 bug，是形式条件）。
```

边界：

```text
1. C3 在 n_profile=4h/8h 上不稳定，只在 12h 档有实质经济意义；
2. Group_M 上 C3 表现由 m2501 单样本主导（+10.50 独占 87% 贡献），concentration risk 高；
3. C2 若要有意义需要修 spec §5.2（把 X_s 从极值降级为最近一次 breakout bar high），
   属于策略语义变更，暂不推进；
4. R29 主要失败样本中 p2505 / p2601 在 C3 @ n=144 上大幅翻身，
   但 p2501 / p2605 仍负——不能视为整组翻身。
```

## 2. 未决问题

| 问题 | 现状 | 后续处理 |
| --- | --- | --- |
| C2 恒不触发（spec §5.2 X_s 极值化）| 已定性，非 bug | 如果 feature-only 层需要 C2，独立开 issue 讨论"X_s 是否降级为 last breakout high" |
| Group_M m2501 concentration risk | 数据观察 | feature-only 使用者需自行控制单样本权重 |
| n_profile=4h/8h C3 不稳定 | 观察 | feature-only 层默认 12h |
| B_s 负值 anchor drift | 已通过 `Break_s^*(i | t)` 当前锚复核修复 | 保留 spec §5.3 定义 |
| 每 bar rolling POC/VA + 无状态策略 | 已成文提案 | 详见 [../../../workbench/value-area-reacceptance-rolling-refactor-proposal.md](../../../workbench/value-area-reacceptance-rolling-refactor-proposal.md)，触发条件见提案 §6 |

## 3. 当前工件

| 目的 | 文档 |
| --- | --- |
| 数学规格（策略契约） | [strategy-math-spec.md](strategy-math-spec.md) |
| 实验计划 | [experiment-plan.md](experiment-plan.md) |
| 参数选择规格（占位） | [parameter-selection-spec.md](parameter-selection-spec.md) |
| 工程实现细节（占位） | [implementation-notes.md](implementation-notes.md) |
| 主题入口 | [README.md](README.md) |

保留代码：

```text
value_area_reacceptance_baseline
- 旧候选策略的 baseline 版本；
- 保留 R27-R29 回测口径、诊断字段、退出逻辑；
- 不再代表当前候选交易策略。

value_area_random_baseline
- 长期随机入场基准；
- 复用 VA baseline 的事件、止损和退出口径；
- 用 same-direction / random-direction 随机入场判断结构入口是否优于随机。
```

轻量随机基准 runner：

```text
scripts/analysis/value_area_random_baseline_compare.py
```

注意：runner 的 `total_net_pnl` 使用 vnpy BacktestResult 口径，只能做同一 runner 内相对比较，不和 trade_clearings 清算口径混算。

## 4. 已完成阶段结论

### 4.1 R27 扩样后的降级

```text
旧 m/SR + 1m + A4_ratio_80 + actual RR=0.8 + min_reaccept_ticks=2/3 外推失败；
旧 m/SR 单笔 POC 回归线不再作为主候选。
```

### 4.2 R28 结构诊断

```text
DCE.p 四样本内：
- max_trades_per_day=1 时首笔 VA reacceptance 收益有限；
- max_trades_per_day=3 后主要收益来自第 2 笔；
- 第 1 笔更像 VA reversion；
- 第 2/3 笔可能更像 continuation / retry；
- reentry target 1.0R~1.35R 构成样本内平台，继续细调会过拟合。
```

### 4.3 R29 扩样与随机基准

```text
固定 R28 后的保守候选未通过扩样：
- DCE.m 明显失败；
- DCE.y 接近但未通过；
- DCE.c / DCE.cs 信号不足或弱负；
- DCE.p 更早历史窗口失败，seq1 强负，seq2 接近打平。

随机入场复验显示：
- 结构规则虽亏损，但仍优于 same-direction random；
- 旧 DCE.p 失败样本上，结构没有退化成随机噪声；
- 问题更可能在环境过滤、风险空间、交易序列或退出兑现层。
```

## 5. R30 当前主规则（详见 strategy-math-spec.md）

R30 将旧的“上一笔 stop_loss / 亏损后才 reentry”改成结构状态判断，并将开仓与出场拆成正交候选组：

```text
入场候选（AND 组合，每组内部 ∨）：
- Ω_pattern ⊆ {C1, C2, C3}      形态类：首次 / 突破衰减 / 上次未测 POC
- Ω_risk    ⊆ {R0, R1}          风控类：无约束 / 原始盈亏比预算
- Ω_direction ⊆ {D_near, D_far} 方向类：按 POC 到 VA 上下界距离划分

出场候选（∨ 合成 TP_exit，与入场正交）：
- Ω_tp ⊆ {TP_fixed, TP_armed_retrace, TP_fast_time}

结构锚：
- POC / VA 每 2 小时（bar 条数）滚动刷新一次；
- 空仓状态下的定期刷新采用；
- 平仓事件驱动一次采用型刷新；
- 持仓期间只监控不改锚。
```

对照线：

```text
continuation：direction_mode = away_from_poc
只作为 failed reacceptance / continuation 候选，
必须单独统计，不与 VA 回归主线合并评估。
```

## 6. R30 小矩阵（详见 experiment-plan.md）

| 组合 | 方向分支 | 开仓条件 | 目的 |
| --- | --- | --- | --- |
| R30-A | 更接近 POC | 首次测试 POC | 验证最纯 VA 回归是否仍有边际 |
| R30-B | 更接近 POC | 突破距离弱于上次 | 验证外部接受衰减是否提高胜率 |
| R30-C | 更接近 POC | 上次 POC 未充分测试 | 验证多次回归是否有结构价值 |
| R30-D | 更接近 POC | B2 或 B3 | 验证完整多次 VA 回归规则 |
| R30-E | 更远离 POC | 单独记录 | continuation 候选对照 |

核心观测指标：

```text
POC touch rate
entry_to_poc_ticks
breakout_ticks
breakout_ticks_delta
by_condition pnl
overlap pnl
stop_loss 占比
by_environment
random baseline percentile
```

## 7. 当前不建议继续的方向

| 方向 | 当前处理 | 原因 |
| --- | --- | --- |
| 继续调旧 value_area_reacceptance_baseline | 停止 | baseline 只保留历史口径，不再叠加新逻辑 |
| DCE.p 四样本内继续细调 1.3 / 1.35 / 1.4 | 停止 | R29 已证明不能直接外推 |
| 把 seq2 直接解释为 VA 回归 | 暂停 | 可能属于 continuation，需要拆分验证 |
| 直接用 strong_trend 过滤 | 暂缓 | 需要先看结构条件是否解释失败 |
| ATR / volatility normalization 入主规则 | 暂缓 | 可能有助于泛化，但不应先混入主效应 |
| range-profile 替换 close-profile | 暂缓 | 当前主问题不是 profile 定义替换 |

## 8. 下一阶段待验证

```text
1. Stage B v2 结论归档：workbench 稳定结论压缩后归档到
   docs/archive/strategy-research/<date>-value-area-reacceptance-stage-b/；
2. C3 作为独立 feature 提取：暴露 C3 事件时点、B_s 序列、Z_s^- 序列
   给下游 feature 消费者（feature-only 层），不再作为独立开仓策略；
3. C2 恒不触发的 spec 语义决策：如果未来 feature-only 层需要 C2，
   独立开 issue 讨论"X_s 是否降级为 last breakout high"；
4. Group_M concentration risk：m2501 独占 87% 贡献，
   feature-only 使用者需自行做样本权重管理，主题层不再兜底；
5. continuation 对照线（direction_mode=away_from_poc）作为独立后续，
   不与本主题主线合并评估。
```

## 9. 关联文档

| 目的 | 文档 |
| --- | --- |
| 主题入口 | [README.md](README.md) |
| 全局研究入口 | [../../strategy-current.md](../../strategy-current.md) |
| 数学规格 | [strategy-math-spec.md](strategy-math-spec.md) |
| 实验计划 | [experiment-plan.md](experiment-plan.md) |
| 参数选择规格 | [parameter-selection-spec.md](parameter-selection-spec.md) |
| 工程实现细节 | [implementation-notes.md](implementation-notes.md) |
| R29 扩样与随机基准复验 | [../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| R28 结构诊断 | [../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md) |
| R27 扩样复验 | [../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md) |
| POC / VA 质量诊断阶段归档 | [../../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md](../../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| R16-R24 actual RR 重整 | [../../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md](../../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md) |
| R25 1m vs 5m | [../../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md](../../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md) |
| R26 稳定性检查 | [../../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r26-1m-stability-check.md](../../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r26-1m-stability-check.md) |
