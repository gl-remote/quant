# value_area_reacceptance 多次 POC 回归研究计划

> 类型：Theme / 下阶段研究计划
> 状态：草案 / 首轮实验待执行
> 最近更新：2026-07-03
> 前置结论：[R29 扩样与随机基准复验](../../../../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 数学规格：[strategy-math-spec.md](strategy-math-spec.md)
> 参数选择：[parameter-selection-spec.md](parameter-selection-spec.md)
> 工程实现细节：[implementation-notes.md](implementation-notes.md)
> 主题入口：[README.md](README.md)
> 当前研究入口：[../../../strategy-current.md](../../../strategy-current.md)

## 1. 研究目标

R29 结论：旧 `value_area_reacceptance_baseline` 未通过扩样验证，但 VA reacceptance event 相对随机基准仍有结构信息。R30 已将策略行为按 spec 重构：四维正交入场候选（`Ω_pattern × Ω_risk × Ω_direction × Ω_tp`）+ 滚动 profile 刷新 + 三类退出优先级。

首轮实验不打算一次性开完 108+ 组合矩阵，先验证结构主效应，逐 stage 引入维度。

核心问题：

```text
Q1: profile 窗口长度 (n_profile ∈ {4h, 8h, 12h}/Δbar) 对 POC 稳定性的影响？
Q2: 形态类 Ω_pattern 中，C2 / C3 / C23 相对 C1 是否给出额外结构收益？
Q3: 方向类 Ω_direction 的近侧 / 远侧划分是否稳定放大主效应？
Q4: 止盈类 Ω_tp 中 TP_armed_retrace / TP_fast_time 相对 TP_fixed 是否兑现更多结构收益？
Q5: 风控类 Ω_risk 的 R1（rr_raw_min 预算）是否只是过滤器，本身不产生收益？
Q6: R30 相对 R29 样本上的 same-direction random baseline 是否稳定占优？
```

## 2. 文档边界

本计划只记录研究路径、候选矩阵、验证顺序和判定标准。

策略定义以数学规格为准：

```text
spec := docs/research/themes-frozen/value-area/value-area-reacceptance/strategy-math-spec.md
```

若实现或实验发现规格缺失，先更新规格，再继续实现或回测。

参数选择规格另外记录：

```text
parameter-selection-spec := docs/research/themes-frozen/value-area/value-area-reacceptance/parameter-selection-spec.md
```

## 3. 首轮实验参数底座

按 spec §11 默认候选，本轮固定"非扫描维度"为下列单点，只让明确列入 sweep 的维度变化：

```text
poc_mode         := close
va_mode          := greedy_from_poc
ρ                := 0.7
direction_mode   := to_poc                (对照分支 D 会切 away_from_poc)
n_step           := 2h / Δbar             (= 24 when Δbar = 5m)

b                := 1
r                := 1
δ                := 0
m                := 1
N_max            := 3
cooldown         := 1 bar
trade_start_time / last_entry_time / force_flat_time := per-instrument schedule

α                := 0.8
β                := 1
λ                := 1.2
stop_atr_bars    := 0
stop_atr_multiplier := 0
rr_min           := 0.8
max_hold_bars    := 60
strict_close_exit:= true
rr_raw_min       := 1.0                   (仅 R1 组合下参与判定)

η_arm            := 0.5
η_retrace        := 0.5
n_fast           := 6
η_fast           := 0.5
n_fast_hold      := 0

Δbar             := 5m                    (首轮固定，其它周期留待后续)
```

不在首轮继续调 execution 参数；先看结构分支是否有效。

## 4. 样本计划

优先复用 R29 已经暴露外推问题的样本：

```text
Group_P (主验证组，R29 暴露外推问题):
  DCE.p2405, DCE.p2409, DCE.p2501, DCE.p2505, DCE.p2509, DCE.p2601, DCE.p2605

Group_M (泛化对照组):
  DCE.m2505, DCE.m2509, DCE.m2601, DCE.m2603, DCE.m2605
```

样本原则：

```text
先同品种跨月份验证结构信号，再看跨品种泛化；
每个 stage 保留同 runner 内 same-direction / random-direction 随机基准对照；
两组独立评估，不合并样本量。
```

## 5. 候选矩阵（首轮）

| 维度 | 首轮候选取值 | 单点固定值（未 sweep 时） |
| --- | --- | --- |
| `n_profile` | `{4h, 8h, 12h}/Δbar` = {48, 96, 144} @ Δbar=5m | 12h 桶（最长） |
| `Ω_pattern` | `{ {C1}, {C2}, {C3}, {C2,C3}, {C1,C2,C3} }` | `{C1,C2,C3}` |
| `Ω_risk` | `{ {R0}, {R1} }` | `{R0}` |
| `Ω_direction` | `{ {D_near}, {D_far}, {D_near,D_far} }` | `{D_near,D_far}`（等价关掉方向过滤） |
| `Ω_tp` | `{ {TP_fixed}, {TP_armed_retrace}, {TP_fast_time}, {TP_fixed,TP_armed_retrace}, {TP_fixed,TP_fast_time} }` | `{TP_fixed}` |
| `direction_mode` | `{ to_poc, away_from_poc }` | `to_poc` |

维度笛卡尔积 108 组过大，按 stage 拆分验证。

## 6. 验证顺序

### Stage A：实现校核与单样本 smoke

目标：确认策略按 spec 运行；诊断字段可用；bar 索引与 profile 刷新按 §10 正确触发。

```text
A1: 挑一个 DCE.p 样本，跑最小配置 (Ω_pattern = {C1,C2,C3}, Ω_risk = {R0},
    Ω_direction = {D_near,D_far}, Ω_tp = {TP_fixed}, n_profile = 12h/Δbar)
A2: 抽 5 笔交易明细核对：entry / stop / target / F / holding_bars / exit_reason
A3: 抽 profile 刷新事件核对：InitEvent 首根 bar；TickEvent 每 24 bars；ExitEvent 平仓后
A4: 检查 alpha / risk / execution 三层诊断字段是否非 placeholder
A5: 与 value_area_reacceptance_baseline 保持隔离，无路径冲突
```

出场条件：A2–A5 全部人工核对通过；否则回补 spec 或修实现，再重跑 A1。

### Stage B：profile 窗口 × 形态类主效应扫描

目标：验证 Q1 + Q2。

**前置条件（2026-07-03 更新）**：spec 已把 `AttemptEvent_s(t)` 从交易依赖里剥离
（§5.6 / §6.2）——`A_s / B_s^- / Z_s^-` 由事件触发更新而非交易关闭时更新，
`Adopt(u) = 1` 时用新锚 Replay 最近 `n_step` 根 bar 回填状态（§11.3.5）。
这一语义变更使得 C2 / C3 在无实际交易时也能累积，直接影响 Stage B 的
`Ω_pattern` 触发分布，Stage B 需在**新语义**下重跑，早期用 v1 语义（原
`_close_trade` 更新 attempt）跑出的 "C2/C3 = 0 trades" 结论作废。

```text
维度扫描:
  n_profile   ∈ {48, 96, 144}  (Δbar = 5m)
  Ω_pattern   ∈ { {C1}, {C2}, {C3}, {C2,C3}, {C1,C2,C3} }

固定:
  Ω_risk = {R0}
  Ω_direction = {D_near, D_far}   (等价关闭方向过滤)
  Ω_tp = {TP_fixed}
  direction_mode = to_poc
```

矩阵大小：`3 × 5 = 15 组 / 样本`；`Group_P (7 样本) + Group_M (5 样本)` → 180 runs。

核心观测：

```text
n
poc_touch_rate
avg_pnl / PF / maxDD
stop_loss_ratio / take_profit_ratio / strict_failure_ratio / time_exit_ratio
by_pattern (C1 / C2_only / C3_only / C23)
by_side (L / U)
by_attempt (A_s)
random_baseline_percentile (same-direction / random-direction)
```

判定：

```text
Q1 pass  <= 某个 n_profile 桶稳定占优（跨样本 percentile 一致优于其它两个）
Q2 pass  <= {C2}, {C3}, {C2,C3} 中至少一个在 poc_touch_rate 与 stop_loss_ratio 上显著优于 {C1}
Both fail => 主效应太弱，进 Feature-only 分支，不再往后打
```

### Stage C：方向类对照

目标：验证 Q3。前提是 Stage B 至少通过 Q1 或 Q2。

```text
维度扫描:
  Ω_direction ∈ { {D_near}, {D_far}, {D_near, D_far} }

固定 (取 Stage B 的赢家):
  n_profile   = <B 阶段选定的最佳桶>
  Ω_pattern   = <B 阶段选定的最佳组合>
  Ω_risk = {R0}
  Ω_tp = {TP_fixed}
  direction_mode = to_poc
```

矩阵大小：`3 × 12 = 36 runs`。

核心观测：

```text
by_direction (D_near / D_far / Tie)
poc_touch_rate 差异
same-side 突破深度 (break_ticks) 分布
avg_pnl 差异
```

判定：

```text
D_near dominates    => 主线固定 Ω_direction = {D_near}
D_far dominates     => 主线固定 Ω_direction = {D_far}
Both similar        => 关闭方向过滤，保留 Ω_direction = {D_near, D_far}
```

### Stage D：止盈类对照

目标：验证 Q4。前提是 Stage B 通过。

```text
维度扫描:
  Ω_tp ∈ { {TP_fixed}, {TP_armed_retrace}, {TP_fast_time},
            {TP_fixed, TP_armed_retrace}, {TP_fixed, TP_fast_time} }

固定 (取 Stage B/C 的赢家):
  n_profile   = <B 阶段选定的最佳桶>
  Ω_pattern   = <B 阶段选定的最佳组合>
  Ω_direction = <C 阶段选定的最佳组合>
  Ω_risk = {R0}
  direction_mode = to_poc
```

矩阵大小：`5 × 12 = 60 runs`。

核心观测：

```text
by_exit_reason:
  take_profit_fixed / take_profit_armed_retrace / take_profit_fast_time
  stop_loss / strict_failure_close / force_flat / time_exit
mfe_r / mae_r 分布（按 exit_reason 分层）
realized_pnl_per_unit
avg_pnl / PF 相对 {TP_fixed} 单点的增益
```

判定：

```text
{TP_fixed, TP_armed_retrace} 或 {TP_fixed, TP_fast_time} 提升 PF 且不显著抬升 stop_loss_ratio => 采纳
所有软 TP 组合都不提升 PF               => 保留 {TP_fixed}
软 TP 单独占优（{TP_armed_retrace} 或 {TP_fast_time}）而组合不提升 => 重新审视 TP_fixed
```

### Stage E：风控 / 冷却 / 方向消融

目标：验证 Q5、Q6，并核对 continuation 对照。

```text
E1 (Ω_risk 消融):
  Ω_risk ∈ { {R0}, {R1} }，rr_raw_min ∈ {1.0, 1.5, 2.0}
  其它维度取 Stage B/C/D 赢家

E2 (cooldown 消融):
  cooldown ∈ {0, 1, 4}  (bars)
  其它维度取赢家

E3 (continuation 对照):
  direction_mode = away_from_poc
  其它维度取 Stage B 主线赢家
  → 与主线独立评估，不合并样本
```

判定：

```text
R1 有效       <= 相同赢家参数下 R1 提高 PF 或降低 maxDD 而不显著降 n
cooldown 有效 <= 改变交易序列 且 结构指标同步改善；否则保持 cooldown = 1
away_from_poc <= 单独作为 continuation 候选线上台；不混入 VA 回归主线评估
```

## 7. 每次实验记录要求

每个 stage 每个样本 group 独立记录：

```text
sample_group          := Group_P / Group_M
stage_id              := B / C / D / E1 / E2 / E3
run_ids               := 从 quant CLI 输出获取
fixed_params          := 上锁的维度快照
sweep_params          := 变化维度快照
trade_count           := 每 run 交易数
net_pnl / PF / maxDD  := 每 run 汇总
poc_touch_rate        := 主要结构指标
exit_reason_dist      := 6 类退出占比
condition_mask_pnl    := by_pattern / by_direction 分层
random_baseline_delta := 相对 same-direction / random-direction 的 percentile
unexpected_obs        := 触发下一 stage 决策的观察
next_decision         := 是否进入下一 stage / 是否需要回补 spec
```

单轮实验结果不回填本计划，另存 workbench，Stage 全部收敛后归档到 archive。

## 8. 判定标准

通过条件（承接 R29 教训）：

```text
1. 不允许单样本盈利驱动结论；至少 Group_P + Group_M 都朝同一方向；
2. 结构指标（poc_touch_rate / break_ticks / condition mask）改善先于收益改善；
3. 相对 same-direction / random-direction random baseline 有稳定 percentile 优势；
4. 净盈利不来自单笔异常大单（观察 top-3 trade 占比）；
5. 不通过新增参数搜索救回结果；不在首轮引入 ATR / volatility filter。
```

失败降级路径：

```text
Stage B 双 Q 都失败       => reacceptance event 转为 feature-only，本主题冻结
Stage C/D 无一致方向      => 保持默认单点，本轮不再迭代结构维度
Stage E continuation 占优 => 派生 continuation 独立主题，本主题维持"结构信号不足"结论
```

## 9. 关联文档

| 目的 | 文档 |
| --- | --- |
| 主题入口 | [README.md](README.md) |
| 主题当前状态 | [research-status.md](research-status.md) |
| 数学规格 | [strategy-math-spec.md](strategy-math-spec.md) |
| 参数选择规格 | [parameter-selection-spec.md](parameter-selection-spec.md) |
| 工程实现细节 | [implementation-notes.md](implementation-notes.md) |
| R29 扩样与随机基准复验 | [../../../../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md](../../../../research/archived-notes/2026/07/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
