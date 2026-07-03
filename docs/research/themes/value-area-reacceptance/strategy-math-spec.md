# value_area_reacceptance 多次 POC 回归策略数学规格

> 类型：Theme / 策略数学规格
> 状态：草案 / 待实现与验证
> 最近更新：2026-07-03
> 前置结论：[R29 扩样与随机基准复验](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 研究计划：[experiment-plan.md](experiment-plan.md)
> 参数选择：[parameter-selection-spec.md](parameter-selection-spec.md)
> 工程实现细节：[implementation-notes.md](implementation-notes.md)
> 主题入口：[README.md](README.md)

## 1. 目标

固定下一阶段 POC 策略的数学定义与候选分支：VA reacceptance event 仍有信息量；旧 reentry 规则不再作为候选策略；下一策略将多次 reacceptance 建模为多次 VA -> POC 共识测试。

本文只定义策略候选集合，不记录实验结果。

## 2. 基础对象

交易日与索引：

```text
d             := current trading session
I_d           := bar index set of session d
I_all         := bar index set across all historically available sessions up to session d
```

执行 bar：

```text
x_t := (O_t, H_t, L_t, C_t, V_t), t ∈ I_d
O_t := open price of bar t
H_t := high price of bar t
L_t := low price of bar t
C_t := close price of bar t
V_t := volume of bar t
τ   := price_tick
idx(t)  := ordinal position of bar t in I_all (1-based)
time(t) := wall-clock timestamp of bar t (typically bar close)
```

Profile 刷新调度（详见 §10）：

```text
Δbar            := bar period (nominal cadence, e.g. 5m)
n_profile       := profile lookback in bars, integer >= 1
n_step          := shared parameter for periodic refresh interval AND signal lookback, in bars,
                   integer, 1 <= n_step <= n_profile
W_profile       := n_profile · Δbar                 (nominal profile window length)
W_step          := n_step    · Δbar                 (nominal refresh / signal window length)
T_refresh       := ordered set of refresh timestamps in session d, defined by §10
T_adopt         := subset of T_refresh whose refresh updates the structural anchors, defined by §10
t_ref(t)        := max{u ∈ T_adopt | u <= t}
```

窗口以"bar 条数"为度量单位，不以钟表时间计算。跨 session 拼接时，只要在 `I_all` 中相邻（即上一 session 收盘紧邻下一 session 开盘的下一根 bar），就视作连续的 bar 序列；夜盘停牌、周末等真实时间跳跃不产生"空 bar"，不计入窗口累计。

`n_step` 同时承担两个含义：定期刷新的节拍（每累计 `n_step` 根 bar 触发一次 `TickEvent`）与信号窗口回溯长度（`Break_s / R_s / X_s` 的历史起点回溯 `n_step` 根 bar）。因此每次周期刷新点与信号窗口起点自然对齐，两窗口始终同步。

profile 窗口与窗口末样本（对任意刷新时刻 `u ∈ T_refresh` 定义，仅用于构造 POC/VA；窗口按 bar 条数取，可跨 session）：

```text
I_W(u) := {i ∈ I_all | idx(u) - n_profile < idx(i) <= idx(u)}
C_W(u) := C_u
|I_W(u)| <= n_profile (exactly n_profile when at least n_profile bars precede u)
```

信号窗口（对当前评估 bar `t` 定义，仅用于突破跟踪 `X_s`、事件 `Break_s / R_s` 的历史起点，见 §4；窗口按 bar 条数取，可跨 session）：

```text
i_sig(t) := max(1, idx(t) - n_step + 1)         (first bar index of the signal window)
```

窗口 profile（对任意刷新时刻 `u ∈ T_refresh` 定义）：

```text
Π̂_u: price -> volume, computed on I_W(u)
```

对采用型刷新 `u ∈ T_adopt`，同时定义采纳到锚上的量：

```text
Π_t := Π̂_{t_ref(t)}
G_t := all tradable price buckets touched by Π_t
```

结构锚（时变，分段常量，仅在 `t ∈ T_adopt` 时跳变）：

```text
P_t := window POC  at t_ref(t), defined by §3.1
D_t := window VAL  at t_ref(t), defined by §3.2
U_t := window VAH  at t_ref(t), defined by §3.2
D_t <= P_t <= U_t
```

后文 §4–§9 中出现的 `P, D, U` 均为 `P_t, D_t, U_t` 的简写，历史 bar `i` 上的判定使用 `P_i, D_i, U_i`（即 bar `i` 所属的采用刷新窗口取值）。

距离 tick 化：

```text
T(x) := x / τ
```

通用记号：

```text
k_τ(x)     := x / τ
floor_τ(x) := floor(k_τ(x)) · τ
ceil_τ(x)  := ceil(k_τ(x)) · τ
round_τ(x) := floor_τ(x), if x/τ - floor(x/τ) < 0.5
round_τ(x) := ceil_τ(x),  if x/τ - floor(x/τ) >= 0.5
1[A]       := 1 if condition A is true, else 0
```

Tick 舍入规则：

```text
G_τ               := {n · τ | n ∈ ℤ}
bucket_profile(x) := round_τ(x)
bucket_buy(x)     := ceil_τ(x)
bucket_sell(x)    := floor_τ(x)

∀ p ∈ dom(Π_t) ∪ {P_t, D_t, U_t}:       p ∈ G_τ ∧ p = bucket_profile(p)
∀ p ∈ {E_t, Stop_t, Target_t, F_t}:      p ∈ G_τ

side(p) ∈ {buy, sell} for any order-related price p, per §7–§8
p_submit(p_raw, buy)  := bucket_buy(p_raw)
p_submit(p_raw, sell) := bucket_sell(p_raw)
```

`round_τ` 已在 §2 中定义为半格向上舍入；`bucket_buy / bucket_sell` 保证买单不低于原始价、卖单不高于原始价。`E_t, Stop_t, Target_t` 的方向映射详见 §7、§8。

策略参数定义：

```text
θ_profile:
poc_mode      := POC construction mode ∈ {close, range}
va_mode       := VA construction mode ∈ {greedy_from_poc}
ρ             := target value-area volume ratio, 0 < ρ <= 1
n_profile     := profile lookback in bars, integer >= 1
n_step        := shared refresh interval / signal lookback in bars, integer, 1 <= n_step <= n_profile

θ_signal:
b              := minimum breakout distance in ticks, integer b >= 0
r              := minimum reacceptance distance in ticks, integer r >= 0
δ              := POC touch tolerance in ticks, integer δ >= 0
m              := minimum target distance in ticks, integer m >= 0
Ω_pattern      := pattern-class entry condition set, Ω_pattern ⊆ {C1, C2, C3}
Ω_risk         := risk-class entry condition set, Ω_risk ⊆ {R0, R1}
Ω_direction    := direction-class entry condition set, Ω_direction ⊆ {D_near, D_far}
rr_raw_min     := minimum pre-entry raw target/stop ratio for R1, rr_raw_min >= 0
direction_mode := trade direction mode ∈ {to_poc, away_from_poc}
N_max          := max entries per session, integer >= 1
cooldown       := minimum bar-count spacing between previous exit and next entry, integer >= 0
trade_start_time := earliest entry time in session d
last_entry_time  := latest entry time in session d
force_flat_time  := forced flat time in session d

θ_exec:
α                   := target fraction of |P_t - E_t|, 0 < α <= 1
β                   := failure buffer in ticks, integer β >= 0
λ                   := stop widening multiplier, λ >= 1
stop_atr_bars       := ATR lookback bars, integer >= 0
stop_atr_multiplier := ATR stop multiplier, stop_atr_multiplier >= 0
rr_min              := minimum target-distance / stop-distance ratio, rr_min >= 0
max_hold_bars       := maximum holding bars, integer >= 1
strict_close_exit   := whether close beyond F exits position
Ω_tp                := take-profit candidate set, Ω_tp ⊆ {TP_fixed, TP_armed_retrace, TP_fast_time}, |Ω_tp| >= 1
η_arm               := arm threshold as fraction of Anchor, 0 < η_arm <= α           (used by TP_armed_retrace)
η_retrace           := retrace fraction from peak_profit as fraction of Anchor, 0 < η_retrace < 1   (used by TP_armed_retrace)
n_fast              := fast-profit window in bars, integer >= 1                       (used by TP_fast_time)
η_fast              := fast-profit threshold as fraction of Anchor, 0 < η_fast <= α   (used by TP_fast_time)
n_fast_hold         := hold bars after fast-hit before forced exit, integer >= 0      (used by TP_fast_time)

θ_size:
Capital            := account equity used for sizing
risk_per_trade     := max capital fraction risked per trade
contract_size      := contract multiplier
max_position_ratio := max capital fraction used as margin notional
margin_rate        := exchange margin rate

θ_profile := (poc_mode, va_mode, ρ, n_profile, n_step)
θ_signal  := (direction_mode, Ω_pattern, Ω_risk, Ω_direction, rr_raw_min, b, r, δ, m, N_max, cooldown,
              trade_start_time, last_entry_time, force_flat_time)
θ_exec    := (α, β, λ, stop_atr_bars, stop_atr_multiplier, rr_min,
              max_hold_bars, strict_close_exit,
              Ω_tp, η_arm, η_retrace, n_fast, η_fast, n_fast_hold)
θ_size    := (Capital, risk_per_trade, contract_size, max_position_ratio, margin_rate)
θ         := (θ_profile, θ_signal, θ_exec, θ_size)
```

量纲约定：

```text
bar-count 量纲(idx(·)): n_profile, n_step, cooldown, max_hold_bars, T_last_exit, holding_bars
wall-clock 量纲(time(·)): trade_start_time, last_entry_time, force_flat_time
tick 量纲(τ):    b, r, δ, m, β, all price-derived distances
```

其它常量（`α, λ, ρ, rr_min, rr_raw_min, stop_atr_multiplier, risk_per_trade, max_position_ratio, margin_rate`）为无量纲比值。

## 3. Profile 定义候选

本节定义单个刷新时刻 `u ∈ T_refresh` 上的窗口 profile 与 `(POC, VAL, VAH)` 构造。刷新事件生成与是否采纳到结构锚的规则见 §10.3。以下定义在任意 `u` 上使用简写 `I := I_W(u)`, `G := G_{I_W(u)}`, `C̄ := C_W(u)`，其中 `G_{I_W(u)}` 为 `I_W(u)` 中所有 bar 触达的可交易价格桶集合。

### 3.1 POC

候选：

```text
poc_mode ∈ {close, range}
```

close-profile：

```text
Π_close(p) := Σ_{i∈I} V_i · 1[round_τ(C_i) = p]
M_close    := {p ∈ G | Π_close(p) = max_{v∈G} Π_close(v)}
POC_close  := argmin_{p∈M_close} (|p - C̄|, -p)
```

range-profile：

```text
Bkt_i      := {p ∈ G | round_τ(L_i) <= p <= round_τ(H_i)}
Π_range(p) := Σ_{i∈I} (V_i / |Bkt_i|) · 1[p ∈ Bkt_i]
M_range    := {p ∈ G | Π_range(p) = max_{v∈G} Π_range(v)}
POC_range  := argmin_{p∈M_range} (|p - C̄|, -p)
```

POC tie-break：

```text
If multiple price buckets have max profile volume,
choose the bucket minimizing (|p - C̄|, -p) in lexicographic order.
```

即先选距离窗口末收盘 `C̄` 最近的桶；若上下两个桶距离仍相等，选价格更高的桶。

默认：`poc_mode = close`。

### 3.2 VA

候选：

```text
va_mode ∈ {greedy_from_poc}
```

定义（以 `P := POC_·` 为种子，`Π := Π_·` 为窗口 profile）：

```text
S_0 := {P}

Adj(S_k) := {
  max{p∈G\S_k | p < min(S_k)},
  min{p∈G\S_k | p > max(S_k)}
} excluding missing sides

side_priority(p) := +1 if p > max(S_k), else 0
next(S_k) := argmax_{p∈Adj(S_k)} (Π(p), side_priority(p))

S_{k+1} := S_k ∪ {next(S_k)}
VAComplete(k) := Σ_{p∈S_k} Π(p) >= ρ · Σ_{p∈G} Π(p)
K := min{k >= 0 | VAComplete(k)}

VAL := min(S_K)
VAH := max(S_K)
```

VA expansion tie-break：

```text
argmax_{p∈Adj(S_k)} (Π(p), side_priority(p)) uses lexicographic order.
```

即相邻上下桶成交量相等时，先扩上边界。

profile 对照：

```text
if poc_mode = close:
    Π := Π_close
    P := POC_close

if poc_mode = range:
    Π := Π_range
    P := POC_range

D := VAL
U := VAH
```

在刷新时刻 `u` 上得到 `(P̂_u, D̂_u, Û_u) := (P, D, U)`；是否将其采用为结构锚 `(P_t, D_t, U_t)` 由 §10.3 决定。

## 4. 事件定义

结构锚为分段常量的时变量，`P, D, U` 在 bar `t` 上等价于 `P_t, D_t, U_t`；对历史 bar `i` 上的判定（如 `Break_s(i)`）使用 bar `i` 当时的锚 `D_i, U_i`。profile 刷新（§10）不主动清空同侧突破跟踪 `X_s(t)`。

边界突破：

```text
Break_L(t) := L_t <= D_t - bτ
Break_U(t) := H_t >= U_t + bτ
```

同侧突破极值：

```text
Reset_s(t)  := 1 if a Reset event for side s fires at bar t, else 0        (see §10.2)
τ_s(t)      := max{i ∈ I_all | idx(i) <= idx(t) ∧ Reset_s(i) = 1}
                     (undefined if no Reset_s has fired on or before t)
i_reset(t)  := idx(τ_s(t)) + 1,       if τ_s(t) is defined
             := idx of the first bar in I_all, if τ_s(t) is undefined
i_start(t)  := max(i_reset(t), i_sig(t))
J_s(t)      := {i ∈ I_all | i_start(t) <= idx(i) <= idx(t), Break_s(i)}
Exists_s(t) := 1[J_s(t) ≠ ∅]

X_L(t) := min{L_i | i ∈ J_L(t)}, if Exists_L(t) = 1
X_U(t) := max{H_i | i ∈ J_U(t)}, if Exists_U(t) = 1
X_s(t) := undefined,             if Exists_s(t) = 0
```

即 `X_s(t)` 的历史窗口以 bar 条数为度量，取「上次 `Reset_s` 之后一根 bar」与「bar `t` 之前 `n_step` 条 bar 起点」两者中较近的起点到 `t` 为止。由 §10.2 保证每个 session 的首根 bar 上 `Reset_s = 1`，故 `X_s` 天然被 session 切割，无需额外引入 `session_start` 特判。刷新（§10）不触发 `Reset_s`，仅 `i_sig(t)` 会随 `t` 前移；未成交的 `R_s(t)` 与反向突破均不清空 `X_s(t)`。

突破距离：

```text
B_L(t) := T(D_t - X_L(t))
B_U(t) := T(X_U(t) - U_t)
```

重新接受：

```text
R_L(t) := X_L(t) exists ∧ C_t >= D_t + rτ
R_U(t) := X_U(t) exists ∧ C_t <= U_t - rτ
```

方向集合：

```text
s ∈ {L, U}
q_to_poc(L) = +1
q_to_poc(U) = -1
q_away(L)   = -1
q_away(U)   = +1
```

## 5. 状态变量

每个 session、每一侧 `s ∈ {L, U}` 维护：

```text
A_s   := same-side attempt count
B_s^- := previous same-side breakout ticks
Z_s^- := previous same-side POC-tested flag
T_last_exit := bar index of previous exit across all sides in session d (None if no exit yet)
```

当前侧：

```text
B_s(t) := B_L(t), if s = L
B_s(t) := B_U(t), if s = U
R_s(t) := R_L(t), if s = L
R_s(t) := R_U(t), if s = U
```

POC 测试：

```text
TouchPOC_long(t0,t1)  := max_{t0<=u<=t1} (H_u - (P_u - δτ)) >= 0
TouchPOC_short(t0,t1) := min_{t0<=u<=t1} (L_u - (P_u + δτ)) <= 0
TouchPOC_q(t0,t1)    := TouchPOC_long(t0,t1),  if q = +1
TouchPOC_q(t0,t1)    := TouchPOC_short(t0,t1), if q = -1
```

`TouchPOC` 在 `[t0, t1]` 内逐 bar 使用 bar 自身的锚 `P_u`，因此持仓期间即使 `P_u` 保持恒定，历史上刷新过的 POC 仍能被正确记账。

## 6. 开仓条件候选

开仓条件分成三组：形态类 `Ω_pattern` 描述再接受形态，风控类 `Ω_risk` 描述开仓前的风控约束，方向类 `Ω_direction` 按 POC 到 VA 上下界的距离划分同侧突破方向 `s`。三组以 AND 方式合成 Enter：每组内部候选之间取析取（∨），组间取合取（∧）。

### 6.1 形态类候选

候选集合：

```text
Ω_pattern ⊆ {C1, C2, C3}
```

三类条件：

```text
C1_s(t) := A_s = 0
C2_s(t) := B_s^- exists ∧ B_s(t) < B_s^-
C3_s(t) := Z_s^- = False
```

组合条件：

```text
C_Ω_pattern(s,t) := ∨_{C∈Ω_pattern} C_s(t)
```

overlap 诊断：

```text
C2_only := C2 ∧ ¬C3
C3_only := C3 ∧ ¬C2
C23     := C2 ∧ C3
```

### 6.2 风控类候选

候选集合：

```text
Ω_risk ⊆ {R0, R1}
```

风控类候选依赖开仓时的入场价 `E_t`、当时的目标锚 `P_t` 和上次同侧突破极值 `X_s(t)`。每个候选定义自己的"原始盈亏比"计算方式，用于开仓前的预算过滤；此处不涉及实际下单的止盈止损，实际止盈止损由 §7 的 `RiskOK` 与 §8 的 `Stop_t / Target_t` 决定。

默认原始盈亏比：

```text
G_raw_default(s,t) := |P_t - E_t|
L_raw_default(s,t) := |E_t - X_s(t)|
rr_raw_default(s,t) := G_raw_default(s,t) / L_raw_default(s,t)
                      if L_raw_default(s,t) > 0, else +∞
```

即盈利部分取入场价到 POC 的距离，亏损部分取入场价到上次同侧突破极值的距离。

候选定义：

```text
R0_s(t) := True
R1_s(t) := L_raw_default(s,t) > 0 ∧ rr_raw_default(s,t) >= rr_raw_min
```

`R0` 不施加任何原始盈亏比约束，用作对照；`R1` 使用默认原始盈亏比。

组合条件：

```text
C_Ω_risk(s,t) := ∨_{R∈Ω_risk} R_s(t)
```

### 6.3 方向类候选

候选集合：

```text
Ω_direction ⊆ {D_near, D_far}
```

方向类候选按当前锚 `(P_t, D_t, U_t)` 下 POC 到 VA 上下界的距离，将同侧突破方向 `s ∈ {L, U}` 划分为"近侧"与"远侧"两组：

```text
d_L(t) := T(P_t - D_t)      = ticks from VAL to POC
d_U(t) := T(U_t - P_t)      = ticks from POC to VAH
```

近侧 / 远侧定义（以 tick 化距离为准）：

```text
Near(s,t)  := (s = L ∧ d_L(t) <  d_U(t)) ∨ (s = U ∧ d_U(t) <  d_L(t))
Far(s,t)   := (s = L ∧ d_L(t) >  d_U(t)) ∨ (s = U ∧ d_U(t) >  d_L(t))
Tie(t)     := d_L(t) = d_U(t)
```

`Tie(t)` 时约定同时视作近侧与远侧，避免在等距 profile 下全部候选被排除；等价于将该刷新窗口视为方向类中性，不施加过滤。

候选定义：

```text
D_near_s(t) := Near(s,t) ∨ Tie(t)
D_far_s(t)  := Far(s,t)  ∨ Tie(t)
```

组合条件：

```text
C_Ω_direction(s,t) := ∨_{D∈Ω_direction} D_s(t)
```

`Ω_direction = {D_near, D_far}` 时 `C_Ω_direction ≡ True`，等价于不启用方向类过滤。

### 6.4 候选配对

入场候选按三维配对枚举，与止盈类 `Ω_tp`（§9.1，出场维度）正交组合，总配对矩阵为四维：

```text
(Ω_pattern, Ω_risk, Ω_direction, Ω_tp) ∈ P × R × D × TP
```

其中 `P, R, D, TP` 分别为四组的候选取值集合，见 §11。每对配置独立评估。`Ω_tp` 只影响退出，与前三组的入场判定正交。

## 7. 入场函数

候选方向：

```text
direction_mode ∈ {to_poc, away_from_poc}
```

方向映射：

```text
q(s, to_poc)         := q_to_poc(s)
q(s, away_from_poc)  := q_away(s)
```

入场价：

```text
E_t_raw := C_t
E_t     := ceil_τ(E_t_raw),  if q(s,direction_mode) = +1
E_t     := floor_τ(E_t_raw), if q(s,direction_mode) = -1
```

若 `C_t` 已是可交易价格桶，则 `E_t = C_t`。

方向有效性：

```text
DirOK(s,t,to_poc)         := q_to_poc(s) · (P_t - E_t) > 0
DirOK(s,t,away_from_poc)  := q_away(s) · (P_t - E_t) < 0
```

入场价等于 POC 的自动排除：由 `DirOK` 中严格不等式 `> 0 / < 0` 与 `SpaceOK` 中 `E_t ≠ P_t` 蕴含，`E_t = P_t` 时 `DirOK` 与 `SpaceOK` 均为 False，从而 `Enter(s,t;θ) = False`。此处不再单列。

目标空间：

```text
SpaceOK(t) := E_t ≠ P_t ∧ |P_t - E_t| >= mτ
```

全局执行约束：

```text
Flat(t)              := no open position before evaluating bar t
LevelsAvailable(t)   := t_ref(t) exists ∧ P_t, D_t, U_t are defined
InEntryTimeWindow(t) := trade_start_time <= time(t) <= last_entry_time
ForceFlatTime(t)     := time(t) >= force_flat_time
TradeCount_d         := number of entries already opened in session d
CooldownOK(t)        := T_last_exit = None ∨ idx(t) - T_last_exit >= cooldown
```

```text
ExecOK(t) := Flat(t)
          ∧ LevelsAvailable(t)
          ∧ InEntryTimeWindow(t)
          ∧ ¬ForceFlatTime(t)
          ∧ TradeCount_d < N_max
          ∧ CooldownOK(t)
```

入场判定：

```text
Enter(s,t;θ) := ExecOK(t)
              ∧ R_s(t)
              ∧ DirOK(s,t,direction_mode)
              ∧ SpaceOK(t)
              ∧ RiskOK(s,t)
              ∧ C_Ω_pattern(s,t)
              ∧ C_Ω_risk(s,t)
              ∧ C_Ω_direction(s,t)
```

## 8. 执行函数

方向：

```text
q := q(s, direction_mode)
```

严格失败价：

```text
F_t := X_s(t) - q · βτ
```

严格失败距离：

```text
d_strict := |E_t - F_t|
```

止损距离：

```text
ATR(n,t) := average true range over last n bars before or at t
d_atr    := ATR(stop_atr_bars,t) · stop_atr_multiplier
d_stop   := max(d_strict · λ, d_atr)
```

约定 `stop_atr_multiplier = 0` 时 `d_atr = 0`，此时 `d_stop = d_strict · λ`。

止损价：

```text
Stop_raw_t := E_t - q · d_stop
Stop_t     := floor_τ(Stop_raw_t), if q = +1
Stop_t     := ceil_τ(Stop_raw_t),  if q = -1
d_stop_eff := |E_t - Stop_t|
```

目标价：

```text
Target_raw_t := E_t + q · α · |P_t - E_t|
Target_t     := floor_τ(Target_raw_t), if q = +1
Target_t     := ceil_τ(Target_raw_t),  if q = -1
```

交易冻结变量：

```text
t_entry := entry bar (bar reference at which Enter fires)
Entry   := E_t at t_entry
Stop    := Stop_t at t_entry
Target  := Target_t at t_entry
F       := F_t at t_entry
q       := q at t_entry
```

对应 bar 索引 `idx(t_entry)`；`t_exit` 记为对应的退出 bar 引用，`idx(t_exit)` 为其索引。

风险收益过滤：

```text
RiskOK(s,t) := d_stop_eff > 0
            ∧ q · (Target_t - E_t) > 0
            ∧ |Target_t - E_t| >= mτ
            ∧ |Target_t - E_t| / d_stop_eff >= rr_min
```

`Target_t` 恒定义为 `α · |P_t - E_t|` 的名义目标价，用于 `RiskOK` 与 `TP_fixed`（§9.1.1）。其他止盈候选（`TP_armed_retrace, TP_fast_time`）不使用 `Target_t`，但 `RiskOK` 仍对所有 `Ω_tp` 生效——保证任何配置下最坏盈亏比都不劣于 `rr_min`。

仓位：

```text
volume_risk   := floor(Capital · risk_per_trade / (d_stop_eff · contract_size))
volume_margin := floor(Capital · max_position_ratio / (E_t · contract_size · margin_rate))
volume        := max(0, min(volume_risk, volume_margin))
```

若 `volume = 0`，则不开仓。

## 9. 退出函数

持仓期间不评估新入场：

```text
Position_t ≠ 0 => evaluate Exit only
```

持仓 bar 数：

```text
holding_bars(t) := idx(t) - idx(t_entry)
```

### 9.1 止盈类候选

止盈类候选与形态/风控/方向组同层，构造 `Ω_tp` 决定持仓期间使用哪几种止盈规则；只要任一候选触发即触发止盈。所有候选共享同一"盈利参考"标尺：

```text
Anchor         := |P_{t_entry} - E_{t_entry}|   (frozen at entry, same as |P - E_t| in §8)
signed_pnl(t)  := q · (C_t - Entry)             (running unrealized P&L per unit)
peak_pnl(t)    := max_{t_entry <= u <= t} signed_pnl(u)
```

`Anchor` 与 §8 的 `Target_raw` 计算共用 `|P - E_t|`，与止损 `Stop_t / F` 无关。

候选集合：

```text
Ω_tp ⊆ {TP_fixed, TP_armed_retrace, TP_fast_time}, |Ω_tp| >= 1
```

#### 9.1.1 TP_fixed（固定比例，与旧 Target 等价）

```text
TP_fixed(t) := (q = +1 ∧ H_t >= Target)
             ∨ (q = -1 ∧ L_t <= Target)
```

即 §8 原有的 `Target_t = E_t + q · α · |P_t - E_t|` 达标即止盈。

#### 9.1.2 TP_armed_retrace（拿到 POC 距离固定比例后按回撤止盈）

```text
arm_level     := η_arm · Anchor
retrace       := η_retrace · Anchor
Armed(t)      := 1[peak_pnl(t) >= arm_level]

TP_armed_retrace(t) := Armed(t) = 1 ∧ (peak_pnl(t) - signed_pnl(t)) >= retrace
```

即 `peak_pnl` 首次达到 `arm_level` 后 `Armed` 恒为 1；随后任何 bar 上 `signed_pnl` 从峰值回撤 `retrace` 以上即触发止盈。回撤幅度以入场时刻的 `Anchor` 为分母。

#### 9.1.3 TP_fast_time（快速获利 → 时间窗口内锁定）

```text
fast_window(t) := {u ∈ I_all | idx(t_entry) <= idx(u) <= min(idx(t), idx(t_entry) + n_fast)}
fast_hit(t)    := 1[∃ u ∈ fast_window(t) : signed_pnl(u) >= η_fast · Anchor]
u_fast(t)      := min{u ∈ fast_window(t) | signed_pnl(u) >= η_fast · Anchor}
                  (undefined if fast_hit(t) = 0)

TP_fast_time(t) := fast_hit(t) = 1 ∧ idx(t) - idx(u_fast(t)) >= n_fast_hold
```

即"进场后 `n_fast` 根 bar 内曾达到 `η_fast · Anchor` 收益"即触发 fast-hit，`u_fast(t)` 为达标的首根 bar；再等 `n_fast_hold` 根 bar 强制止盈。`n_fast_hold = 0` 表示 fast-hit 当根 bar 立即止盈。若持仓超过 `idx(t_entry) + n_fast` 仍未达标，`fast_hit(t)` 保持为 0，该候选此后不再触发。

#### 9.1.4 组合止盈信号（诊断用）

```text
TP_exit(t) := ∨_{TP ∈ Ω_tp} TP(t)
```

`TP_exit(t)` 仅作为"是否有任一止盈候选触发"的合计诊断。真正参与出场判定与成交价分派的是 §9.2 拆分后的 `TP_fixed_active(t) / TP_soft_active(t)`。`Ω_tp = {TP_fixed}` 时 `TP_exit ≡ TP_fixed_active`，`TP_soft_active ≡ False`，退化为 §8 的原始固定 Target 行为。

### 9.2 出场判定

拆分止盈事件以便区分成交模型：

```text
TP_fixed_active(t)  := (TP_fixed ∈ Ω_tp) ∧ TP_fixed(t)
TP_soft_active(t)   := ∨_{TP ∈ Ω_tp \ {TP_fixed}} TP(t)
```

long 退出：

```text
Exit_long(t) := first_true(
  L_t <= Stop,
  strict_close_exit ∧ C_t <= F,
  TP_fixed_active(t),
  TP_soft_active(t),
  ForceFlatTime(t),
  holding_bars(t) >= max_hold_bars
)
```

short 退出：

```text
Exit_short(t) := first_true(
  H_t >= Stop,
  strict_close_exit ∧ C_t >= F,
  TP_fixed_active(t),
  TP_soft_active(t),
  ForceFlatTime(t),
  holding_bars(t) >= max_hold_bars
)
```

退出优先级：

```text
stop_loss > strict_failure_close > TP_fixed > TP_soft > force_flat > time_exit
```

退出价：

```text
stop_loss:                                          engine fill model at Stop
TP_fixed:                                           engine fill model at Target
TP_soft (TP_armed_retrace, TP_fast_time, ...):      strategy-level C_t
strict_failure_close / force_flat / time_exit:      strategy-level C_t
```

即 `TP_fixed` 保留原有 `Target` 挂单成交模型；其它止盈候选（`TP_armed_retrace, TP_fast_time`）是事件驱动的策略级平仓，用 bar 收盘价。同一 bar 上若 `TP_fixed` 与 `TP_soft` 同时触发，按优先级取 `TP_fixed`。

### 9.3 交易关闭后

```text
A_s         := A_s + 1
B_s^-       := B_s(t_entry)
Z_s^-       := TouchPOC_q(t_entry, t_exit)
T_last_exit := idx(t_exit)
```

## 10. 状态重置

### 10.1 Session reset

在 session `d` 的首根 bar 上，对以下状态执行初始化：

```text
A_L = A_U = 0
B_L^- = B_U^- = None
Z_L^- = Z_U^- = None
T_last_exit = None
TradeCount_d = 0
T_refresh = ∅
T_adopt = ∅
```

历史突破跟踪 `X_s, J_s` 由 §4 的 `i_start(t)` 自动被 `Reset_s = 1`（§10.2）截断到本 session，不需额外清空。

### 10.2 Breakout reset

```text
Reset_s(t) = 1  <=  Enter(s, t; θ) = 1
Reset_s(t) = 1  <=  t is the first bar of a new session (via §10.1)
```

默认不因反向突破清空另一侧状态；profile 刷新（§10.3）不触发 `Reset_s`。

### 10.3 Profile 刷新调度

刷新按三个正交维度定义：事件生成 `T_refresh`、每次刷新的 profile 计算 `Π̂_u`、锚是否采用 `Adopt(u)`。

#### 10.3.1 刷新事件生成

`T_refresh` 按时间顺序自会话开始逐 bar 增量构造，`u_prev(t)` 指截至 `t` 之前已经进入 `T_refresh` 的最后一个刷新时刻：

```text
u_open   := earliest bar t ∈ I_d with |I_W(t)| >= 1
                     (i.e. window has at least one bar of history; with cross-session data this is
                      typically the first bar of session d)
u_prev(t)         := max{u ∈ T_refresh already constructed | u < t}
                     (undefined before u_open)
InitEvent(t)      := 1[t = u_open]
TickEvent(t)      := 1[t > u_open ∧ idx(t) - idx(u_prev(t)) >= n_step]
ExitEvent(t)      := 1[trade closes at t]

RefreshEvent(t)   := InitEvent(t) ∨ TickEvent(t) ∨ ExitEvent(t)
T_refresh         := {t ∈ I_d | RefreshEvent(t) = 1}
```

即：`T_init = {u_open}`，`T_tick = {t | TickEvent(t)}`，`T_exit = {t | ExitEvent(t)}`。三者均按到达 bar 的时间顺序独立判定，同一 bar 上多类事件同时触发时视作单次刷新。`T_tick` 只依赖时钟节拍与已有 `T_refresh` 前缀，与持仓状态无关；`T_exit` 只由平仓事件触发。

#### 10.3.2 每次刷新的 profile 计算

`Π̂_u` 与 `(P̂_u, D̂_u, Û_u)` 已在 §3 中给出（对任意 `u ∈ T_refresh` 独立计算），本节不再重复。仅强调该计算仅依赖 `I_W(u)` 与 `C_W(u)`，与持仓状态、`X_s` 无关。

#### 10.3.3 锚采用规则

刷新时刻 `u` 是否更新结构锚由 `Adopt(u)` 决定：

```text
Flat_at(u)  := 1[Flat(u)]      (position status just before u)
Adopt(u) := 1[u ∈ T_init ∪ T_exit] ∨ (1[u ∈ T_tick] ∧ Flat_at(u))
```

即首次刷新与平仓刷新总是采用，定时刷新仅在空仓时采用；持仓期间的定时刷新只计算 `Π̂_u`（用于监控），不改锚。

结构锚定义：

```text
T_adopt := {u ∈ T_refresh | Adopt(u) = 1}
t_ref(t) := max{u ∈ T_adopt | u <= t}
(P_t, D_t, U_t) := (P̂_{t_ref(t)}, D̂_{t_ref(t)}, Û_{t_ref(t)})
```

#### 10.3.4 刷新与其他状态的正交性

对任意 `u ∈ T_refresh`：

```text
RefreshEvent(u) = 1                    => {A_s, B_s^-, Z_s^-, T_last_exit,
                                            TradeCount_d, X_s, Reset_s} are unchanged
RefreshEvent(u) = 1, Adopt(u) = 0      => (P_t, D_t, U_t) unchanged for all t
```

刷新与执行冷却（`CooldownOK`）、突破跟踪（`X_s`）、交易计数彼此独立；平仓后能否立即再入场仍由 §7 的 `CooldownOK` 决定，与刷新调度无关。

首轮参数取 `n_profile ∈ {4h, 8h, 12h} / Δbar, n_step = 2h/Δbar`；对每个 `n_profile` 候选独立评估。

## 11. 首轮默认候选

```text
poc_mode = close
va_mode = greedy_from_poc
ρ = 0.7
n_profile ∈ {4h, 8h, 12h} / Δbar     (e.g. {48, 96, 144} when Δbar = 5m)
n_step    = 2h  / Δbar     (e.g. 24  when Δbar = 5m)
direction_mode = to_poc
b = 1
r = 1
δ ∈ {0, 1}
m = 1
Ω_pattern ∈ {{C1}, {C2}, {C3}, {C2,C3}, {C1,C2,C3}}
Ω_risk ∈ {{R0}, {R1}}
Ω_direction ∈ {{D_near}, {D_far}, {D_near, D_far}}
rr_raw_min ∈ {1.0, 1.5, 2.0}
α = 0.8
N_max = 3
cooldown ∈ {1, optionally 0}   (unit: bars)
trade_start_time / last_entry_time / force_flat_time := per-instrument session schedule
β = 1
λ = 1.2
stop_atr_bars = 0
stop_atr_multiplier = 0
rr_min = 0.8
max_hold_bars = 60
strict_close_exit = true
Ω_tp ∈ {{TP_fixed}, {TP_armed_retrace}, {TP_fast_time}, {TP_fixed, TP_armed_retrace}, {TP_fixed, TP_fast_time}}
η_arm ∈ {0.3, 0.5}          (fraction of Anchor)
η_retrace ∈ {0.3, 0.5}      (fraction of Anchor)
n_fast ∈ {3, 6}             (bars)
η_fast ∈ {0.3, 0.5}         (fraction of Anchor)
n_fast_hold ∈ {0, 1}        (bars)
```

配对矩阵按 `Ω_pattern × Ω_risk × Ω_direction × Ω_tp` 全枚举；`n_profile ∈ {4h, 8h, 12h} / Δbar` 作为正交扫描维度，与四维候选矩阵独立组合，用于评估 profile 窗口长度对结构锚稳定性的影响；`R0` 组合下 `rr_raw_min` 取值不影响结果，可归并为单点；`Ω_direction = {D_near, D_far}` 组合下方向类过滤为常真，可用于对照；`Ω_tp` 中未涉及的候选参数（`η_arm/η_retrace/n_fast/η_fast/n_fast_hold`）在对应候选不出现时归并为单点。
