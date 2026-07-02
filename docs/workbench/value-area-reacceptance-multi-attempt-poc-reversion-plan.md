# value_area_reacceptance 多次 POC 回归研究计划

> 类型：Workbench / 下阶段研究计划
> 状态：草案 / 待实现与验证
> 最近更新：2026-07-02
> 前置结论：[R29 扩样与随机基准复验](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 数学规格：[value-area-reacceptance-multi-attempt-poc-reversion-spec.md](value-area-reacceptance-multi-attempt-poc-reversion-spec.md)
> 当前研究入口：[strategy-current.md](../research/strategy-current.md)

## 1. 研究目标

R29 结论：旧 `value_area_reacceptance_baseline` 未通过扩样验证，但 VA reacceptance event 相对随机基准仍有结构信息。

下一阶段不继续修补旧 reentry 规则，改为验证：

```text
多次 VA reacceptance = 多次 VA -> POC 共识测试
```

核心问题：

```text
Q1: 只做 VA -> POC 方向，是否能稳定提高 POC touch 与盈亏表现？
Q2: 多次尝试条件 C2/C3 是否比首次条件 C1 更有效？
Q3: away_from_poc 是否只是 continuation 对照，还是独立候选方向？
Q4: close-profile 与 range-profile 的 POC 定义是否影响泛化？
```

## 2. 文档边界

本计划只记录研究路径、候选矩阵、验证顺序和判定标准。

策略定义以数学规格为准：

```text
spec := value-area-reacceptance-multi-attempt-poc-reversion-spec.md
```

若实现或实验发现规格缺失，先更新规格，再继续实现或回测。

## 3. 候选分支

主分支：

```text
D1 := to_poc
```

对照分支：

```text
D2 := away_from_poc
```

开仓条件分支：

```text
C1 := first same-side attempt
C2 := current breakout weaker than previous same-side breakout
C3 := previous same-side attempt did not test POC
```

Profile 分支：

```text
P1 := close-profile POC
P2 := range-profile POC
```

执行分支：

```text
K0 := no cooldown
K1 := 15m cooldown
```

## 4. 首轮候选矩阵

| id | POC | VA | direction | Ω | α | cooldown | purpose |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| M0 | close | greedy | to_poc | {C1} | 0.8 | K1 | 首次 POC 回归基线 |
| M1 | close | greedy | to_poc | {C2} | 0.8 | K1 | 突破衰减 |
| M2 | close | greedy | to_poc | {C3} | 0.8 | K1 | 上次未测试 POC |
| M3 | close | greedy | to_poc | {C2,C3} | 0.8 | K1 | 多次回归核心规则 |
| M4 | close | greedy | to_poc | {C1,C2,C3} | 0.8 | K1 | 完整 VA 回归候选 |
| M5 | range | greedy | to_poc | {C1,C2,C3} | 0.8 | K1 | profile 对照 |
| M6 | close | greedy | away_from_poc | separate | n/a | K1 | continuation 对照 |
| M7 | close | greedy | to_poc | {C1,C2,C3} | 0.8 | K0 | cooldown 对照 |

## 5. 默认参数

以规格文档中的默认候选为准，首轮固定：

```text
poc_mode = close
va_mode = greedy_from_poc
direction_mode = to_poc
Ω ∈ {{C1}, {C2}, {C3}, {C2,C3}, {C1,C2,C3}}
α = 0.8
δ ∈ {0, 1}
N_max = 3
cooldown = K1
β = 1
λ = 1.0
rr_min = 0.8
max_hold_bars = 60
strict_close_exit = true
```

不在首轮继续调参；先看结构分支是否有效。

## 6. 验证顺序

### Stage A：实现与单样本回归

目标：确认策略按规格运行，且旧 baseline 行为不受影响。

```text
A1: 实现 multi_attempt_poc_reversion 策略
A2: 单样本 smoke test
A3: 单样本交易明细核对：entry/stop/target/exit/state reset
A4: 与 value_area_reacceptance_baseline 保持隔离
```

### Stage B：结构分支验证

目标：比较 C1/C2/C3 的结构贡献。

```text
B1: M0 vs M1 vs M2
B2: M3 vs M4
B3: condition overlap: C2_only, C3_only, C23
```

核心观察：

```text
poc_touch_rate
stop_loss_ratio
take_profit_ratio
avg_pnl
PF
random_baseline_percentile
```

### Stage C：Profile 对照

目标：确认 POC 构造是否影响泛化。

```text
C1: M4 close-profile
C2: M5 range-profile
```

只比较 profile 定义，不同时改执行参数。

### Stage D：方向对照

目标：分离 VA -> POC 回归与 continuation。

```text
D1: M4 to_poc
D2: M6 away_from_poc
```

判定：

```text
to_poc wins      => 继续主线 VA -> POC 回归
away_from_poc wins => continuation 作为独立策略线，不混入 VA 回归
both fail        => reacceptance event 仅作为 feature，不直接交易
```

### Stage E：冷却对照

目标：确认多次尝试是否依赖冷却规则。

```text
E1: M4 cooldown=K1
E2: M7 cooldown=K0
```

若 K0 改变交易序列但不提高结构指标，不继续调 cooldown。

## 7. 样本计划

首轮优先使用已经暴露外推问题的样本：

```text
DCE.p2405
DCE.p2409
DCE.p2501
DCE.p2505
DCE.p2509
DCE.p2601
DCE.p2605
```

对照样本：

```text
DCE.m 系列
表现较弱的 m/SR 样本
```

样本原则：

```text
先验证结构，不扩大参数搜索；
先同品种跨月份，再跨品种；
每轮保留随机基准对照。
```

## 8. 诊断指标

交易指标：

```text
n, net_pnl, avg_pnl, win_pct, PF, maxDD
stop_loss_ratio, take_profit_ratio, time_exit_ratio
```

结构指标：

```text
poc_touch_rate
entry_to_poc_ticks
breakout_ticks
breakout_ticks_delta
condition_mask pnl: C1, C2_only, C3_only, C23
by_side: L / U
by_attempt: A_s
by_environment
random_baseline_percentile
```

## 9. 判定标准

```text
D1 valid if M3/M4 improves poc_touch_rate, stop_loss_ratio, and random_baseline_percentile vs M0.
D2 candidate if M6 dominates in strong_trend/trend_bias while D1 fails.
Feature-only if all Ω variants fail random baseline and poc_touch_rate does not improve.
```

通过条件：

```text
1. 不是单样本盈利；
2. 结构指标改善先于收益改善；
3. 优于随机基准；
4. 盈利不依赖单笔异常大单；
5. 不靠新增参数搜索救回结果。
```

## 10. 实验记录要求

每轮实验记录：

```text
sample set
candidate ids
fixed params
trade count
net pnl / PF / maxDD
poc_touch_rate
exit reason distribution
condition mask attribution
random baseline comparison
unexpected observations
next decision
```

实验记录另写，不回填到本计划，除非研究路线发生变化。
