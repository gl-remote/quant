# value\_area\_reacceptance 多次 POC 回归策略数学规格

> 类型：Theme / 策略数学规格
> 状态：草案 / 待实现与验证
> 最近更新：2026-07-03
> 前置结论：[R29 扩样与随机基准复验](../../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 研究计划：[experiment-plan.md](experiment-plan.md)
> 参数选择：[parameter-selection-spec.md](parameter-selection-spec.md)
> 工程实现细节：[implementation-notes.md](implementation-notes.md)
> 主题入口：[README.md](README.md)

## 1. 目标与范围

固定下一阶段 POC 策略的数学定义与候选分支：VA reacceptance event 仍有信息量；旧 reentry 规则不再作为候选策略；下一策略将多次 reacceptance 建模为「多次同侧 VA → POC 共识测试」的形态。

本文只定义策略候选集合与数学规格，不记录实验结果。

## 2. 基础对象与量纲

### 2.1 交易日与索引

```text
d          := current trading session
I_d        := bar index set of session d
I_all      := bar index set across all historically available sessions up to session d
idx(t)     := ordinal position of bar t in I_all (1-based, monotonic across sessions)
time(t)    := wall-clock timestamp of bar t (bar close time)
```

跨 session 拼接：只要在 `I_all` 中相邻（上一 session 收盘紧邻下一 session 开盘的下一根 bar），就视作连续的 bar 序列；夜盘停牌、周末等真实时间跳跃不产生"空 bar"，不计入窗口累计。

### 2.2 执行 bar

```text
x_t := (O_t, H_t, L_t, C_t, V_t), t ∈ I_d
O_t := open  price of bar t
H_t := high  price of bar t
L_t := low   price of bar t
C_t := close price of bar t
V_t := volume        of bar t
```

### 2.3 时序与窗口

```text
Δbar       := bar period (nominal cadence, e.g. 5m)
n_profile  := profile lookback in bars,  integer >= 1
n_step     := shared refresh interval and signal lookback in bars, integer, 1 <= n_step <= n_profile

W_profile  := n_profile · Δbar          (nominal profile window length)
W_step     := n_step    · Δbar          (nominal refresh / signal window length)
```

`n_step` 同时承担三个含义：

1. 定期刷新的节拍（`TickEvent`，见 §11.3）
2. 事件层的信号回溯长度（`X_s / J_s` 的起点回溯 `n_step` 根 bar，见 §5.3）
3. Adopt 时 Replay 的回溯窗口（见 §11.3.5）

窗口以「bar 条数」为度量单位，不以钟表时间计算。

Profile 窗口（对任意刷新时刻 `u` 定义，用于构造 POC/VA）：

```text
I_W(u) := {i ∈ I_all | idx(u) - n_profile < idx(i) <= idx(u)}
C_W(u) := C_u
|I_W(u)| <= n_profile (exactly n_profile when at least n_profile bars precede u)
```

信号窗口（对当前评估 bar `t` 定义，用于 `X_s / J_s` 的起点）：

```text
i_sig(t) := max(1, idx(t) - n_step + 1)         (first bar index of the signal window)
```

### 2.4 Tick 舍入

```text
τ := price_tick
T(x)       := x / τ                             (tick-scale distance)
k_τ(x)     := x / τ
floor_τ(x) := floor(k_τ(x)) · τ
ceil_τ(x)  := ceil(k_τ(x))  · τ
round_τ(x) := floor_τ(x), if x/τ - floor(x/τ) <  0.5
round_τ(x) := ceil_τ(x),  if x/τ - floor(x/τ) >= 0.5
1[A]       := 1 if condition A is true, else 0
```

价格桶与买卖分派：

```text
G_τ               := {n · τ | n ∈ ℤ}
bucket_profile(x) := round_τ(x)
bucket_buy(x)     := ceil_τ(x)
bucket_sell(x)    := floor_τ(x)

∀ p ∈ dom(Π_t) ∪ {P_t, D_t, U_t}:       p ∈ G_τ ∧ p = bucket_profile(p)
∀ p ∈ {E_t, Stop_t, Target_t, F_t}:      p ∈ G_τ

p_submit(p_raw, buy)  := bucket_buy(p_raw)
p_submit(p_raw, sell) := bucket_sell(p_raw)
```

`E_t / Stop_t / Target_t / F_t` 的方向映射见 §9。

### 2.5 量纲约定

```text
bar-count  量纲(idx(·)):  n_profile, n_step, cooldown, max_hold_bars, T_last_exit, holding_bars, n_fast, n_fast_hold
wall-clock 量纲(time(·)): trade_start_time, last_entry_time, force_flat_time
tick       量纲(τ):        b, r, δ, m, β, all price-derived distances
```

其它常量（`α, λ, ρ, rr_min, rr_raw_min, stop_atr_multiplier, risk_per_trade, max_position_ratio, margin_rate, η_arm, η_retrace, η_fast`）为无量纲比值。

## 3. 策略参数

### 3.1 参数分组

```text
θ_profile := (poc_mode, va_mode, ρ, n_profile, n_step)
θ_signal  := (direction_mode, Ω_pattern, Ω_risk, Ω_direction, rr_raw_min,
              b, r, δ, m, N_max, cooldown,
              trade_start_time, last_entry_time, force_flat_time)
θ_exec    := (α, β, λ, stop_atr_bars, stop_atr_multiplier, rr_min,
              max_hold_bars, strict_close_exit,
              Ω_tp, η_arm, η_retrace, n_fast, η_fast, n_fast_hold)
θ_size    := (Capital, risk_per_trade, contract_size, max_position_ratio, margin_rate)
θ         := (θ_profile, θ_signal, θ_exec, θ_size)
```

### 3.2 各参数含义

```text
θ_profile:
poc_mode      := POC construction mode ∈ {close, range}
va_mode       := VA construction mode ∈ {greedy_from_poc}
ρ             := target value-area volume ratio, 0 < ρ <= 1
n_profile     := profile lookback in bars, integer >= 1
n_step        := shared refresh interval and signal lookback in bars, integer, 1 <= n_step <= n_profile

θ_signal:
b                := minimum breakout       distance in ticks, integer b >= 0
r                := minimum reacceptance   distance in ticks, integer r >= 0
δ                := POC touch tolerance    in ticks, integer δ >= 0
m                := minimum target         distance in ticks, integer m >= 0
Ω_pattern        := pattern-class   entry condition set, Ω_pattern   ⊆ {C1, C2, C3}
Ω_risk           := risk-class      entry condition set, Ω_risk      ⊆ {R0, R1}
Ω_direction      := direction-class entry condition set, Ω_direction ⊆ {D_near, D_far}
rr_raw_min       := minimum pre-entry raw target/stop ratio for R1, rr_raw_min >= 0
direction_mode   := trade direction mode ∈ {to_poc, away_from_poc}
N_max            := max entries per session, integer >= 1
cooldown         := minimum bar-count spacing between previous exit and next entry, integer >= 0
trade_start_time := earliest entry time in session d
last_entry_time  := latest   entry time in session d
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
η_arm               := arm threshold as fraction of Anchor, 0 < η_arm <= α         (TP_armed_retrace)
η_retrace           := retrace fraction from peak_profit  as fraction of Anchor, 0 < η_retrace < 1 (TP_armed_retrace)
n_fast              := fast-profit window in bars, integer >= 1                   (TP_fast_time)
η_fast              := fast-profit threshold as fraction of Anchor, 0 < η_fast <= α (TP_fast_time)
n_fast_hold         := hold bars after fast-hit before forced exit, integer >= 0  (TP_fast_time)

θ_size:
Capital            := account equity used for sizing
risk_per_trade     := max capital fraction risked per trade
contract_size      := contract multiplier
max_position_ratio := max capital fraction used as margin notional
margin_rate        := exchange margin rate
```

## 4. Profile 构造

本节定义在任意刷新时刻 `u` 上，由 `I_W(u)` 计算得到的窗口 profile `Π̂_u` 与 `(P̂_u, D̂_u, Û_u)`。是否将其采用为结构锚 `(P_t, D_t, U_t)` 见 §11.3。

以下定义在任意 `u` 上使用简写 `I := I_W(u)`，`G := G_{I_W(u)}`，`C̄ := C_W(u)`，其中 `G_{I_W(u)}` 为 `I_W(u)` 中所有 bar 触达的可交易价格桶集合。

### 4.1 POC

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

POC tie-break：多个桶取得最大值时，先按距离 `C̄` 最近选，再按价格更高选（lexicographic order on `(|p - C̄|, -p)`）。

### 4.2 VA

候选：

```text
va_mode ∈ {greedy_from_poc}
```

以 `P := POC_·` 为种子，`Π := Π_·` 为窗口 profile，贪心扩展：

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

VA 扩展 tie-break：相邻上下桶成交量相等时，先扩上边界（lexicographic order on `(Π(p), side_priority(p))`）。

### 4.3 单刷新输出

```text
if poc_mode = close:  Π := Π_close,  P := POC_close
if poc_mode = range:  Π := Π_range,  P := POC_range
D := VAL
U := VAH

(P̂_u, D̂_u, Û_u) := (P, D, U)
```

`(P̂_u, D̂_u, Û_u)` 是刷新时刻 `u` 上的候选锚；实际结构锚 `(P_t, D_t, U_t)` 见 §11.3。

## 5. 事件层

本节定义与结构锚 `(P_t, D_t, U_t)` 交互的原语事件：`Break_s`、`R_s`、`AttemptEvent_s`。结构锚为分段常量的时变量，其值来自 §11.3 的采纳流程；本节对任意 bar `t` 只使用「当前锚」`(P_t, D_t, U_t)`。

### 5.1 方向记号

```text
s ∈ {L, U}
q_to_poc(L) := +1     q_to_poc(U) := -1
q_away(L)   := -1     q_away(U)   := +1
```

### 5.2 边界突破

**当前 bar** 是否突破，用当前锚判定：

```text
Break_L(t) := L_t <= D_t - bτ
Break_U(t) := H_t >= U_t + bτ
```

**历史 bar** **`i`** **被追溯为「同侧突破」时同样用当前锚** **`U_t / D_t`** **复核**（避免 anchor drift 后旧突破仍留在 `J_s(t)` 中导致 `B_s(t) < 0`）：

```text
Break_L^*(i | t) := L_i <= D_t - bτ
Break_U^*(i | t) := H_i >= U_t + bτ
```

### 5.3 同侧突破极值 X\_s(t)

Reset 与信号窗口起点：

```text
Reset_s(t)  := 1 if a Reset event for side s fires at bar t, else 0        (see §11.2)
τ_s(t)      := max{i ∈ I_all | idx(i) <= idx(t) ∧ Reset_s(i) = 1}
                     (undefined if no Reset_s has fired on or before t)
i_reset(t)  := idx(τ_s(t)) + 1,       if τ_s(t) is defined
             := idx of the first bar in I_all, if τ_s(t) is undefined
i_start(t)  := max(i_reset(t), i_sig(t))
```

极值集：

```text
J_s(t)      := {i ∈ I_all | i_start(t) <= idx(i) <= idx(t), Break_s^*(i | t)}
Exists_s(t) := 1[J_s(t) ≠ ∅]

i*_s(t) := max{ idx(i) : i ∈ J_s(t) },   if Exists_s(t) = 1     # 最近一次同侧 breakout bar 的索引
X_L(t)  := L_{i*_L(t)},                  if Exists_L(t) = 1
X_U(t)  := H_{i*_U(t)},                  if Exists_U(t) = 1
X_s(t)  := undefined,                    if Exists_s(t) = 0
```

即 `X_s(t)` 记录**信号窗口内最近一次同侧突破 bar 的极值**（不是窗口累积极值）。取"最近一次"而非"最强一次"是为了让 C2（§7.1）能反映"最近一次突破弱于上一次" 的直觉——若用累积极值，一旦窗口内出现过强突破，后续弱突破无法降低 `X_s`，`B_s` 恒等于历史最强，C2 恒为假。

历史窗口以 bar 条数为度量，起点取「上次 `Reset_s` 之后一根 bar」与「bar `t` 之前 `n_step` 条 bar 起点」两者较近者，终点为 `t`。

**Reset 触发时窗口起点**：当 `Reset_s(u) = 1`（§11.2）时，`τ_s(t) = u` for all `t >= u`，从而 `i_reset(t) = idx(u) + 1`。特别地，在 `t = u` 那根 bar 上 `i_reset(u) = idx(u) + 1 > idx(u)`，导致 `J_s(u) = ∅`、`X_s(u)` = undefined。在 `u < t < u + n_step` 期间，`i_reset(t) > i_sig(t)`，信号窗口由 `i_reset` 主导；`t >= u + n_step` 之后，`i_sig` 才重新主导。

**anchor drift 的处理**：`Break_s^*(i | t)` 使用**当前**锚 `U_t / D_t` 重新判定历史 bar 是否仍构成同侧突破。当刷新（§11.3）导致 `U_t` 上移或 `D_t` 下移时，只有 `H_i ≥ U_t + bτ` 或 `L_i ≤ D_t - bτ` 的历史 bar 才保留在 `J_s(t)` 里。由此保证：

- `B_L(t) = T(D_t - X_L(t)) ≥ 0`，`B_U(t) = T(X_U(t) - U_t) ≥ 0` 恒成立
- 计算复杂度：每次访问 `X_s(t)` 时对 `[i_start, t]` 内 `O(n_step)` 根 bar 重新扫描一遍

### 5.4 突破距离 B\_s

```text
B_L(t) := T(D_t - X_L(t))
B_U(t) := T(X_U(t) - U_t)
```

### 5.5 再接受 R\_s

```text
R_L(t) := Exists_L(t) = 1 ∧ C_t >= D_t + rτ
R_U(t) := Exists_U(t) = 1 ∧ C_t <= U_t - rτ
```

即"曾经同侧突破 + 当前 bar 收盘回到 VA 之内"。

### 5.6 AttemptEvent\_s

`AttemptEvent_s(t)` 是形态判定的最小事件单元，**与是否实际下单无关**：

```text
AttemptEvent_s(t) := R_s(t)
```

（`R_s(t)` 自身已蕴含 `Exists_s(t) = 1`。）

`AttemptEvent` 触发时对状态变量 `(A_s, B_s^-, Z_s^-, T_prev_event)` 的更新规则见 §6.2。

### 5.7 POC 测试 TouchPOC

给定区间 `[t0, t1]` 与方向 `q ∈ {+1, -1}`：

```text
TouchPOC_long(t0,t1)  := max_{t0<=u<=t1} (H_u - (P_u - δτ)) >= 0
TouchPOC_short(t0,t1) := min_{t0<=u<=t1} (L_u - (P_u + δτ)) <= 0
TouchPOC_q(t0,t1)    := TouchPOC_long(t0,t1),  if q = +1
TouchPOC_q(t0,t1)    := TouchPOC_short(t0,t1), if q = -1
```

`TouchPOC` 在 `[t0, t1]` 内逐 bar 使用 bar 自身的锚 `P_u`；历史上刷新过的 POC 仍能被正确记账。

## 6. 状态变量

### 6.1 每侧状态

每个 session、每一侧 `s ∈ {L, U}` 维护以下**事件驱动**状态：

```text
A_s          := same-side attempt-event count             (event-driven, decoupled from actual trades)
B_s^-        := previous same-side breakout ticks         (last AttemptEvent's B_s)
Z_s^-        := previous same-side POC-tested flag        (TouchPOC between last two events)
T_prev_event := bar index of the previous same-side attempt event (None if none yet)
```

以及**交易调度**状态（跨侧共享）：

```text
T_last_exit  := bar index of the most recent exit in session d (None if none yet)
TradeCount_d := number of entries already opened in session d
```

### 6.2 AttemptEvent 触发时的状态更新

当 `AttemptEvent_s(t) = 1` 时，在 **bar t 结束之后**（即 bar t+1 开始之前）执行：

```text
Z_s^-        := TouchPOC_q(T_prev_event, t)                if T_prev_event exists
             := TouchPOC_q(t_ref(t), t)                    if T_prev_event is None
                (with q = q_to_poc(s); t_ref(t) is the most recent Adopt time, see §11.3.3)
B_s^-        := B_s(t)
A_s          := A_s + 1
T_prev_event := idx(t)
```

`TouchPOC_q` 的起点选 `t_ref(t)`（当前 Adopt 时刻）而非 `session_start`：Adopt 前旧锚下的历史 `P_i` 与新锚 `P_t` 语义不同，混入 Adopt 之前的 bar 会污染 Z_s^- 判定。若 session 开始至今尚未发生任何 Adopt，`t_ref(t) = u_open = session_start`，两者等价。

对同一 bar `t` 上的 `Enter` 判定（§8），使用**更新前**的 `(A_s, B_s^-, Z_s^-)`。含义：

- 首次事件那根 bar，更新前 `A_s = 0`，触发 C1；bar 结束后 `A_s → 1`，`B_s^-` 记录当次 `B_s(t)`
- 次次事件那根 bar，更新前 `A_s = 1`，C1 不触发；此时 `B_s^-` 已定义，可判定 C2；`Z_s^-` 已定义，可判定 C3

**与交易的解耦**：实际是否开仓不影响 `(A_s, B_s^-, Z_s^-, T_prev_event)` 的更新；§10.3 的 `T_last_exit` 只用于交易冷却。

### 6.3 当前侧简写

```text
B_s(t) := B_L(t), if s = L        R_s(t) := R_L(t), if s = L
B_s(t) := B_U(t), if s = U        R_s(t) := R_U(t), if s = U
```

## 7. 开仓条件候选

开仓条件分三组：形态类 `Ω_pattern`、风控类 `Ω_risk`、方向类 `Ω_direction`。三组以 AND 合成 `Enter`：每组内部候选取析取（∨），组间取合取（∧）。

止盈类 `Ω_tp`（§10.1）与前三组正交，只影响退出。

### 7.1 形态类 Ω\_pattern

候选集合：

```text
Ω_pattern ⊆ {C1, C2, C3}
```

三类条件（使用 §6.2 更新前的状态）：

```text
C1_s(t) := A_s = 0                                (first attempt in current attempt-history)
C2_s(t) := B_s^- exists ∧ B_s(t) < B_s^-          (weaker breakout than the previous attempt)
C3_s(t) := Z_s^- exists ∧ Z_s^- = False           (previous inter-attempt window did NOT touch POC)
```

组合：

```text
C_Ω_pattern(s,t) := ∨_{C ∈ Ω_pattern} C_s(t)
```

overlap 诊断：

```text
C2_only := C2 ∧ ¬C3
C3_only := C3 ∧ ¬C2
C23     := C2 ∧ C3
```

C1/C2/C3 的语义完全依赖 §6.2 的事件驱动更新，与"是否实际开过仓"无关。

### 7.2 风控类 Ω\_risk

候选集合：

```text
Ω_risk ⊆ {R0, R1}
```

默认原始盈亏比（基于开仓时的入场价 `E_t`、当时目标锚 `P_t`、上次同侧突破极值 `X_s(t)`）：

```text
G_raw_default(s,t)  := |P_t - E_t|
L_raw_default(s,t)  := |E_t - X_s(t)|
rr_raw_default(s,t) := G_raw_default(s,t) / L_raw_default(s,t),  if L_raw_default(s,t) > 0
                    := +∞,                                        otherwise
```

候选定义：

```text
R0_s(t) := True                                                   (no raw rr filter)
R1_s(t) := L_raw_default(s,t) > 0 ∧ rr_raw_default(s,t) >= rr_raw_min
```

`R1` 的 `L_raw_default(s,t) = |E_t - X_s(t)|` 依赖 `X_s(t)` 存在。由于 `Enter` 一并要求 `R_s(t)`（§8.5），而 `R_s(t)` 蕴含 `Exists_s(t) = 1`（§5.5），进而蕴含 `X_s(t)` 存在，因此 R1 判定时 `L_raw_default` 一定有定义。

组合：

```text
C_Ω_risk(s,t) := ∨_{R ∈ Ω_risk} R_s(t)
```

（此处的 rr 过滤只是入场前的原始盈亏比门槛；实际下单的止损/止盈见 §9/§10。）

### 7.3 方向类 Ω\_direction

候选集合：

```text
Ω_direction ⊆ {D_near, D_far}
```

POC 到 VA 上下界的 tick 化距离：

```text
d_L(t) := T(P_t - D_t)     d_U(t) := T(U_t - P_t)
```

近侧 / 远侧：

```text
Near(s,t) := (s = L ∧ d_L(t) <  d_U(t)) ∨ (s = U ∧ d_U(t) <  d_L(t))
Far(s,t)  := (s = L ∧ d_L(t) >  d_U(t)) ∨ (s = U ∧ d_U(t) >  d_L(t))
Tie(t)    := d_L(t) = d_U(t)
```

`Tie(t)` 时同时视作近侧与远侧（把等距 profile 视为方向中性）。

候选定义：

```text
D_near_s(t) := Near(s,t) ∨ Tie(t)
D_far_s(t)  := Far(s,t)  ∨ Tie(t)
```

组合：

```text
C_Ω_direction(s,t) := ∨_{D ∈ Ω_direction} D_s(t)
```

`Ω_direction = {D_near, D_far}` 时 `C_Ω_direction ≡ True`，等价于不启用方向过滤。

### 7.4 候选配对

入场候选按三维配对枚举，与止盈类 `Ω_tp`（§10.1）正交组合，总配对矩阵为四维：

```text
(Ω_pattern, Ω_risk, Ω_direction, Ω_tp) ∈ P × R × D × TP
```

其中 `P, R, D, TP` 分别为四组的取值集合，见 §12。每对配置独立评估。

## 8. 入场函数

### 8.1 方向映射

```text
q(s, to_poc)         := q_to_poc(s)
q(s, away_from_poc)  := q_away(s)
```

### 8.2 入场价

```text
E_t_raw := C_t
E_t     := ceil_τ(E_t_raw),  if q(s, direction_mode) = +1
E_t     := floor_τ(E_t_raw), if q(s, direction_mode) = -1
```

若 `C_t` 已是可交易价格桶，`E_t = C_t`。

### 8.3 方向有效性与目标空间

```text
DirOK(s,t,to_poc)        := q_to_poc(s) · (P_t - E_t) > 0
DirOK(s,t,away_from_poc) := q_away(s)   · (P_t - E_t) < 0
SpaceOK(t)               := E_t ≠ P_t ∧ |P_t - E_t| >= mτ
```

`E_t = P_t` 由 `DirOK` 与 `SpaceOK` 严格不等式蕴含均为 `False`，此时 `Enter = False`。

### 8.4 全局执行约束

```text
Flat(t)              := no open position before evaluating bar t
LevelsAvailable(t)   := t_ref(t) exists ∧ P_t, D_t, U_t are defined
InEntryTimeWindow(t) := trade_start_time <= time(t) <= last_entry_time
ForceFlatTime(t)     := time(t) >= force_flat_time
CooldownOK(t)        := T_last_exit = None ∨ idx(t) - T_last_exit >= cooldown

ExecOK(t) := Flat(t)
          ∧ LevelsAvailable(t)
          ∧ InEntryTimeWindow(t)
          ∧ ¬ForceFlatTime(t)
          ∧ TradeCount_d < N_max
          ∧ CooldownOK(t)
```

### 8.5 入场判定

```text
Enter(s,t;θ) := ExecOK(t)
              ∧ R_s(t)
              ∧ DirOK(s,t,direction_mode)
              ∧ SpaceOK(t)
              ∧ RiskOK(s,t)                       (see §9.3)
              ∧ C_Ω_pattern(s,t)
              ∧ C_Ω_risk(s,t)
              ∧ C_Ω_direction(s,t)
```

## 9. 执行函数

### 9.1 方向

```text
q := q(s, direction_mode)
```

### 9.2 严格失败价与止损价

```text
F_t      := X_s(t) - q · βτ
d_strict := |E_t - F_t|

ATR(n,t) := average true range over the last n bars up to and including t
d_atr    := ATR(stop_atr_bars, t) · stop_atr_multiplier

d_stop     := max(d_strict · λ, d_atr)
Stop_raw_t := E_t - q · d_stop
Stop_t     := floor_τ(Stop_raw_t), if q = +1
Stop_t     := ceil_τ(Stop_raw_t),  if q = -1
d_stop_eff := |E_t - Stop_t|
```

约定 `stop_atr_multiplier = 0` 时 `d_atr = 0`；此时 `d_stop = d_strict · λ`。

### 9.3 目标价与 RiskOK

```text
Target_raw_t := E_t + q · α · |P_t - E_t|
Target_t     := floor_τ(Target_raw_t), if q = +1
Target_t     := ceil_τ(Target_raw_t),  if q = -1

RiskOK(s,t) := d_stop_eff > 0
            ∧ q · (Target_t - E_t) > 0
            ∧ |Target_t - E_t| >= mτ
            ∧ |Target_t - E_t| / d_stop_eff >= rr_min
```

`Target_t` 恒定义为 `α · |P_t - E_t|` 的名义目标价，供 `RiskOK` 与 `TP_fixed`（§10.1.1）使用。其他止盈候选（`TP_armed_retrace, TP_fast_time`）不使用 `Target_t`，但 `RiskOK` 对所有 `Ω_tp` 生效，保证任何配置下最坏盈亏比不劣于 `rr_min`。

### 9.4 交易冻结变量

`Enter(s, t; θ) = 1` 时冻结交易上下文：

```text
t_entry := entry bar (bar reference at which Enter fires)
Entry   := E_t at t_entry
Stop    := Stop_t at t_entry
Target  := Target_t at t_entry
F       := F_t at t_entry
q       := q at t_entry
```

`t_exit` 记为对应的退出 bar 引用。

### 9.5 仓位

```text
volume_risk   := floor(Capital · risk_per_trade     / (d_stop_eff · contract_size))
volume_margin := floor(Capital · max_position_ratio / (E_t · contract_size · margin_rate))
volume        := max(0, min(volume_risk, volume_margin))
```

`volume = 0` 时不开仓。

## 10. 退出函数

持仓期间不评估新入场：

```text
Position_t ≠ 0 => evaluate Exit only
```

持仓 bar 数：

```text
holding_bars(t) := idx(t) - idx(t_entry)
```

### 10.1 止盈候选 Ω\_tp

止盈类候选与形态/风控/方向组同层，构造 `Ω_tp` 决定持仓期间使用哪几种止盈规则；任一候选触发即触发止盈。所有候选共享同一"盈利参考"标尺：

```text
Anchor        := |P_{t_entry} - E_{t_entry}|          (frozen at entry, same as |P - E_t| in §9)
signed_pnl(t) := q · (C_t - Entry)                    (running unrealized P&L per unit)
peak_pnl(t)   := max_{t_entry <= u <= t} signed_pnl(u)
```

候选集合：

```text
Ω_tp ⊆ {TP_fixed, TP_armed_retrace, TP_fast_time}, |Ω_tp| >= 1
```

#### 10.1.1 TP\_fixed（固定比例，等价旧 Target 挂单）

```text
TP_fixed(t) := (q = +1 ∧ H_t >= Target)
             ∨ (q = -1 ∧ L_t <= Target)
```

#### 10.1.2 TP\_armed\_retrace（到达比例后按峰值回撤止盈）

```text
arm_level     := η_arm     · Anchor
retrace       := η_retrace · Anchor
Armed(t)      := 1[peak_pnl(t) >= arm_level]

TP_armed_retrace(t) := Armed(t) = 1 ∧ (peak_pnl(t) - signed_pnl(t)) >= retrace
```

`peak_pnl` 首次达到 `arm_level` 后 `Armed` 恒为 1；此后任何 bar `signed_pnl` 从峰值回撤 `retrace` 以上即触发。

#### 10.1.3 TP\_fast\_time（快速获利 → 时间锁定）

```text
fast_window(t) := {u ∈ I_all | idx(t_entry) <= idx(u) <= min(idx(t), idx(t_entry) + n_fast)}
fast_hit(t)    := 1[∃ u ∈ fast_window(t) : signed_pnl(u) >= η_fast · Anchor]
u_fast(t)      := min{u ∈ fast_window(t) | signed_pnl(u) >= η_fast · Anchor}
                  (undefined if fast_hit(t) = 0)

TP_fast_time(t) := fast_hit(t) = 1 ∧ idx(t) - idx(u_fast(t)) >= n_fast_hold
```

`n_fast_hold = 0` 表示 fast-hit 当根 bar 立即止盈；若持仓超过 `idx(t_entry) + n_fast` 仍未达标，`fast_hit(t)` 保持为 0，此候选此后不再触发。

### 10.2 出场判定

拆分止盈事件（区分成交模型）：

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

退出成交价：

```text
stop_loss:                                          engine fill model at Stop
TP_fixed:                                           engine fill model at Target
TP_soft (TP_armed_retrace, TP_fast_time, ...):      strategy-level C_t
strict_failure_close / force_flat / time_exit:      strategy-level C_t
```

同一 bar 上 `TP_fixed` 与 `TP_soft` 同时触发，按优先级取 `TP_fixed`。

### 10.3 交易关闭后

```text
T_last_exit := idx(t_exit)
```

`(A_s, B_s^-, Z_s^-, T_prev_event)` 不在此处更新（它们由 §6.2 的 `AttemptEvent` 驱动，与交易解耦）。

## 11. 状态重置与刷新调度

### 11.1 Session reset

在 session `d` 的首根 bar 上执行：

```text
A_L = A_U = 0
B_L^- = B_U^- = None
Z_L^- = Z_U^- = None
T_prev_event_L = T_prev_event_U = None
T_last_exit  = None
TradeCount_d = 0
T_refresh    = ∅
T_adopt      = ∅
```

历史突破跟踪 `X_s, J_s` 由 §5.3 的 `i_start(t)` 自动被 `Reset_s = 1`（§11.2）截断到本 session，不需额外清空。

### 11.2 Reset\_s 触发规则

`Reset_s(t) = 1` 当且仅当下列条件之一成立：

```text
(a) Enter(s, t; θ) = 1                                (opening the same side clears its own tracker)
(b) t is the first bar of a new session               (via §11.1)
(c) RefreshEvent(t) = 1 ∧ Adopt(t) = 1                (see §11.3.4: adopted refresh clears both sides)
```

反向突破、未成交的 `R_s`、非采纳刷新均**不**触发 `Reset_s`。

### 11.3 Profile 刷新调度

刷新按三个正交维度定义：事件生成 `T_refresh`、每次刷新的 profile 计算 `Π̂_u`、锚是否采用 `Adopt(u)`。

#### 11.3.1 刷新事件生成

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

即：`T_init = {u_open}`，`T_tick = {t | TickEvent(t)}`，`T_exit = {t | ExitEvent(t)}`。三者按到达 bar 的时间顺序独立判定，同一 bar 上多类事件同时触发时视作单次刷新。

#### 11.3.2 每次刷新的 profile 计算

`Π̂_u` 与 `(P̂_u, D̂_u, Û_u)` 已在 §4 中给出，本节不再重复。仅强调该计算仅依赖 `I_W(u)` 与 `C_W(u)`，与持仓状态、`X_s` 无关。

#### 11.3.3 锚采用规则

刷新时刻 `u` 是否更新结构锚由 `Adopt(u)` 决定：

```text
Flat_at(u)  := 1[Flat(u)]      (position status just before u)
Adopt(u)    := 1[u ∈ T_init ∪ T_exit] ∨ (1[u ∈ T_tick] ∧ Flat_at(u))
```

即首次刷新与平仓刷新总是采用，定时刷新仅在空仓时采用；持仓期间的定时刷新只计算 `Π̂_u`（用于监控），不改锚。

结构锚定义：

```text
T_adopt := {u ∈ T_refresh | Adopt(u) = 1}
t_ref(t) := max{u ∈ T_adopt | u <= t}
(P_t, D_t, U_t) := (P̂_{t_ref(t)}, D̂_{t_ref(t)}, Û_{t_ref(t)})
```

#### 11.3.4 Adopt 的副作用

对任意 `u ∈ T_refresh`：

```text
Adopt(u) = 0  =>  (P_t, D_t, U_t) unchanged for all t >= u
                  (A_s, B_s^-, Z_s^-, T_prev_event, X_s, J_s) unchanged
                  (T_last_exit, TradeCount_d) unchanged

Adopt(u) = 1  =>  (P_t, D_t, U_t) become (P̂_u, D̂_u, Û_u) for all t >= u
                  Reset_s(u) := 1 for each side s ∈ {L, U}
                  Replay(u; s) prefills (A_s, B_s^-, Z_s^-, T_prev_event) for each side
                  (T_last_exit, TradeCount_d) unchanged
```

`Reset_s(u) := 1` 通过 §5.3 的 `i_start = i_reset` 把新锚下的信号窗口起点设到 `idx(u) + 1`：`J_s(u) = ∅`，`X_s(u) = undefined`，从 `t = u+1` 开始重新累积。`Replay(u; s)` 只回填 attempt 侧标量状态 `(A_s, B_s^-, Z_s^-, T_prev_event)`，**不填 `J_s / X_s`**——这两者一定从空开始，靠 `t >= u+1` 后新的 `Break_s^*(i | t)` 重新装入。

**Adopt 之后的开仓时机**：由于 `Enter(s, t; θ)` 要求 `R_s(t)`，而 `R_s(t)` 要求 `Exists_s(t) = 1`，故 `t = u` 那根 bar 上不可能开仓；只有当 `t >= u+1` 上出现新的 `Break_s^*(i | t)` 与新的 close 回到 VA 内时，C1（或若 Replay 已回填 `B_s^- / Z_s^-` 则 C2/C3）才可能触发。

`T_last_exit` 与 `TradeCount_d` 属于交易调度维度，不随 profile 采纳清零；`CooldownOK` 与 `TradeCount_d < N_max` 保持跨刷新连续。

#### 11.3.5 Replay procedure

`Replay(u; s)` 采纳新锚 `(P_u, D_u, U_u)` 后，对每一侧 `s ∈ {L, U}` 独立执行，在 `[max(idx(u) - n_step, idx(session_start)), idx(u) - 1]` 上重放 `AttemptEvent`：

```text
Replay(u; s):
    A_s          := 0
    B_s^-        := undefined
    Z_s^-        := undefined
    T_prev_event := None

    replay_start         := max(idx(u) - n_step, idx(session_start))
    breakout_seen        := False
    breakout_extreme     := undefined         # H_i (side U) or L_i (side L) of the most recent breakout bar since last event
    touch_start_bar      := idx(replay_start) - 1
                                              # TouchPOC 起点：初始为 replay 窗口起点前一根
                                              # （首个事件的 TouchPOC 覆盖整个 replay 前缀）

    for i in ascending order of idx from replay_start to idx(u) - 1:
        # (1) Break_s^*(i | u) 用新锚复核（同一根 bar 既是首次 breakout 又满足 R_s 的情况在 (2) 里会被正确处理）
        if Break_s^*(i | u) holds:
            breakout_seen    := True
            breakout_extreme := H_i if s = U else L_i         # spec §5.2: 最近一次 breakout bar 的极值，覆盖前值

        # (2) 判定 R_s(i; u)：breakout_seen 承担了 §5.5 中 Exists_s(i | u) = 1 的角色
        R_i_new := breakout_seen ∧ (
                       (s = L ∧ C_i >= D_u + rτ) ∨
                       (s = U ∧ C_i <= U_u - rτ)
                   )
        if R_i_new:
            Z_s^-        := TouchPOC_q(touch_start_bar, i)  # q = q_to_poc(s), using P_u for every bar
            B_s^-        := T(breakout_extreme - U_u) if s = U else T(D_u - breakout_extreme)
            A_s          := A_s + 1
            T_prev_event := idx(i)
            # reset tracker for the next event, TouchPOC 起点前移到本事件之后
            breakout_seen    := False
            breakout_extreme := undefined
            touch_start_bar  := idx(i)
```

Replay 保证：

- 若 `[u - n_step, u - 1]` 内新锚下发生过一次 breakout + reacceptance，`A_s ≥ 1`，`B_s^-` 记录当次事件
- 发生两次以上时，`A_s ≥ 2`，`B_s^-` 停留在最近一次；两次之间的 `Z_s^-` 依据 `TouchPOC` 结果
- 若窗口内新锚下未发生任何 `AttemptEvent`，四个变量维持初始值（0 / undefined / undefined / None）
- 同一根 bar 既构成 Break_s 又满足 close 回到 VA 内时，`breakout_seen` 在 (1) 里先置 True，(2) 里立即触发 event，与 §5.5 语义一致（该 bar 上同时 `Exists_s = 1` 与 `R_s = 1`）

Replay 中 `TouchPOC_q` 使用新锚 `P_u`（对回溯窗口内所有历史 bar 都用 `P_u` 记账），与 §5.7 逐 bar 用 bar 自身锚的定义**有意不同**。原因如下：

- Replay 是「假设新锚在过去 n_step 根 bar 上一直生效，回填 attempt 状态」的追溯记账，本质是**反事实计算**，不是复现历史真实事件
- 既然 Replay 中 `Break_s^*(i | u)` / `R_s(i; u)` 都用新锚 `U_u / D_u` 判定，`Z_s^-` 也必须用**同一坐标系**下的新锚 `P_u` 才自洽；用旧锚 `P_i` 会让 `Break / R / TouchPOC` 分处两套坐标系，`C3` 的"两次 attempt 之间是否触碰 POC"语义漂移
- 回溯窗口内的历史 bar 也不存在"过去时刻的新锚"这种量——`P_u` 是刚刚在 `t = u` 时计算出来的

因此 §5.7 的"逐 bar 自身锚"规则**只适用于在线序列**（`t` 沿实际时间前进时对已经发生过的 refresh 结果记账）；Replay 是唯一一个「用当前锚统一评估过去 bar」的例外。TouchPOC 的起点在 Replay 首次事件时为 `replay_start` 之前一根（覆盖整个 replay 前缀），之后的事件为上一次 event 的 `idx(i)`；不使用 `session_start`，避免混入 replay 窗口之前的旧锚下 bar。

### 11.4 首轮参数取值约束

```text
n_step := 4h / Δbar
n_step <= n_profile
```

`n_step = 4h/Δbar` 与 5m bar 匹配：

- 过短（如 2h/5m = 24 bar）会让 `X_s / J_s` 只覆盖 2 小时的极端点，噪声敏感
- 4h 与最短 `n_profile` 候选（4h）持平，保证信号窗口至少等于 profile 窗口的一半，避免"信号追溯反而比 profile 更短"的语义反常

## 12. 首轮默认候选

```text
poc_mode = close
va_mode = greedy_from_poc
ρ = 0.7
n_profile ∈ {4h, 8h, 12h} / Δbar     (e.g. {48, 96, 144} when Δbar = 5m)
n_step    = 4h  / Δbar               (e.g. 48  when Δbar = 5m)
direction_mode = to_poc
b = 1
r = 1
δ ∈ {0, 1}
m = 1
Ω_pattern ∈ {{C1}, {C2}, {C3}, {C2, C3}, {C1, C2, C3}}
Ω_risk ∈ {{R0}, {R1}}
Ω_direction ∈ {{D_near}, {D_far}, {D_near, D_far}}
rr_raw_min ∈ {1.0, 1.5, 2.0}
α = 0.8
N_max = 3
cooldown ∈ {1, optionally 0}         (unit: bars)
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

配对矩阵按 `Ω_pattern × Ω_risk × Ω_direction × Ω_tp` 全枚举；`n_profile ∈ {4h, 8h, 12h} / Δbar` 作为正交扫描维度，与四维候选矩阵独立组合，用于评估 profile 窗口长度对结构锚稳定性的影响。归并规则：

- `R0` 组合下 `rr_raw_min` 取值不影响结果，归并为单点
- `Ω_direction = {D_near, D_far}` 时方向类过滤为常真，可用于对照
- `Ω_tp` 中未涉及的候选参数（`η_arm / η_retrace / n_fast / η_fast / n_fast_hold`）在对应候选不出现时归并为单点

