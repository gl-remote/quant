# value_area_reacceptance 主题当前研究进度

> 类型：Theme / 主题当前状态
> 状态：活跃 / R29 扩样未通过 / 进入 R30 多次 POC 回归 spec 阶段
> 最近更新：2026-07-03
> 主题入口：[README.md](README.md)
> 数学规格：[strategy-math-spec.md](strategy-math-spec.md)
> 研究计划：[experiment-plan.md](experiment-plan.md)
> 参数选择：[parameter-selection-spec.md](parameter-selection-spec.md)
> 工程实现细节：[implementation-notes.md](implementation-notes.md)
> 全局研究入口：[../../strategy-current.md](../../strategy-current.md)
> 当前归档：[R29 扩样与随机基准复验](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 前置归档：[R28 结构诊断](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md)

## 1. 主题一句话结论

```text
value_area_reacceptance 已经不作为单一固定策略推进，
拆成两条结构线继续验证：
1. VA 边界 → POC 的多次回归测试（主线，R30 spec 已成文）；
2. failed reacceptance / continuation 对照线（对照）。

旧 value_area_reacceptance 实现已降级为 value_area_reacceptance_baseline，
只用于复现 R27-R29 历史规则与随机基准对照。
```

边界：

```text
1. R28 DCE.p 四样本不能再视为已验证主线；
2. R29 失败不能直接否定 VA reacceptance 事件；
3. seq1/seq2/seq3 不再机械混成一套 reentry 逻辑；
4. R30 先按 strategy-math-spec.md 定义验证结构条件，不先调 stop/target。
```

## 2. 当前工件

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

## 3. 已完成阶段结论

### 3.1 R27 扩样后的降级

```text
旧 m/SR + 1m + A4_ratio_80 + actual RR=0.8 + min_reaccept_ticks=2/3 外推失败；
旧 m/SR 单笔 POC 回归线不再作为主候选。
```

### 3.2 R28 结构诊断

```text
DCE.p 四样本内：
- max_trades_per_day=1 时首笔 VA reacceptance 收益有限；
- max_trades_per_day=3 后主要收益来自第 2 笔；
- 第 1 笔更像 VA reversion；
- 第 2/3 笔可能更像 continuation / retry；
- reentry target 1.0R~1.35R 构成样本内平台，继续细调会过拟合。
```

### 3.3 R29 扩样与随机基准

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

## 4. R30 当前主规则（详见 strategy-math-spec.md）

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

## 5. R30 小矩阵（详见 experiment-plan.md）

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

## 6. 当前不建议继续的方向

| 方向 | 当前处理 | 原因 |
| --- | --- | --- |
| 继续调旧 value_area_reacceptance_baseline | 停止 | baseline 只保留历史口径，不再叠加新逻辑 |
| DCE.p 四样本内继续细调 1.3 / 1.35 / 1.4 | 停止 | R29 已证明不能直接外推 |
| 把 seq2 直接解释为 VA 回归 | 暂停 | 可能属于 continuation，需要拆分验证 |
| 直接用 strong_trend 过滤 | 暂缓 | 需要先看结构条件是否解释失败 |
| ATR / volatility normalization 入主规则 | 暂缓 | 可能有助于泛化，但不应先混入主效应 |
| range-profile 替换 close-profile | 暂缓 | 当前主问题不是 profile 定义替换 |

## 7. 下一阶段待验证

```text
1. 按 strategy-math-spec.md 实现 multi_attempt_poc_reversion 策略；
2. 单样本 smoke test：核对 entry/stop/target/exit/state reset/refresh；
3. 固定 R29 样本与首轮默认参数，跑 Ω_pattern × Ω_risk × Ω_direction × Ω_tp 小矩阵；
4. 分别输出 C1 / C2_only / C3_only / C23 及 overlap 的 POC touch rate、pnl、stop_loss 占比；
5. 用 value_area_random_baseline 做同 runner 随机对照；
6. 汇总首轮观察后回填到 parameter-selection-spec.md，进入参数选择阶段；
7. 若 VA 回归主线失败而 continuation 对照更好，continuation 独立成下一条策略线。
```

## 8. 关联文档

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
