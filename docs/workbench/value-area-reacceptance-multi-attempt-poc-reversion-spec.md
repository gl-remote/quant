# value_area_reacceptance 多次 POC 回归策略数学规格

> 类型：Workbench / 策略数学规格
> 状态：草案 / 待实现与验证
> 最近更新：2026-07-02
> 前置结论：[R29 扩样与随机基准复验](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 研究计划：[value-area-reacceptance-multi-attempt-poc-reversion-plan.md](value-area-reacceptance-multi-attempt-poc-reversion-plan.md)

## 1. 目标

固定下一阶段 POC 策略的数学定义与候选分支：VA reacceptance event 仍有信息量；旧 reentry 规则不再作为候选策略；下一策略将多次 reacceptance 建模为多次 VA -> POC 共识测试。

本文只定义策略候选集合，不记录实验结果。

## 2. 基础对象

交易日与索引：

```text
d       := current trading session
d-1     := previous trading session used to build profile
I_d     := bar index set of session d
I_{d-1} := bar index set of session d-1
```

执行 bar：

```text
x_t := (O_t, H_t, L_t, C_t, V_t), t ∈ I_{d-1} ∪ I_d
O_t := open price of bar t
H_t := high price of bar t
L_t := low price of bar t
C_t := close price of bar t
V_t := volume of bar t
τ   := price_tick
```

上一交易日 session 级别变量：

```text
O_{d-1} := open price of session d-1
H_{d-1} := high price of session d-1
L_{d-1} := low price of session d-1
C_{d-1} := close price of session d-1
```

上一交易日 profile：

```text
Π_{d-1}: price -> volume
```

结构锚：

```text
P := previous-session POC, defined by §3.1
D := previous-session VAL, defined by §3.2
U := previous-session VAH, defined by §3.2
D <= P <= U
```

距离 tick 化：

```text
T(x) := x / τ
```

通用记号：

```text
round_τ(x) := nearest tradable price bucket to x under tick size τ
1[A]       := 1 if condition A is true, else 0
G_{d-1}    := all tradable price buckets touched by session d-1 profile
```

策略参数总表：

```text
poc_mode, va_mode, ρ
b, r, δ, m
Ω, direction_mode
α, β, λ
stop_atr_bars, stop_atr_multiplier, rr_min
N_max, cooldown, trade_start_time, last_entry_time, force_flat_time
max_hold_bars, strict_close_exit
Capital, risk_per_trade, contract_size, max_position_ratio, margin_rate
```

派生参数：

```text
β := failure_buffer_ticks
λ := max(stop_widen_multiplier, 1)
```

## 3. Profile 定义候选

### 3.1 POC

候选：

```text
poc_mode ∈ {close, range}
```

close-profile：

```text
Π_close(p) := Σ_{t∈I_{d-1}} V_t · 1[round_τ(C_t) = p]
M_close    := {p ∈ G_{d-1} | Π_close(p) = max_{u∈G_{d-1}} Π_close(u)}
POC_close  := argmin_{p∈M_close} |p - C_{d-1}|
```

range-profile：

```text
B_t        := {p ∈ G_{d-1} | round_τ(L_t) <= p <= round_τ(H_t)}
Π_range(p) := Σ_{t∈I_{d-1}} (V_t / |B_t|) · 1[p ∈ B_t]
M_range    := {p ∈ G_{d-1} | Π_range(p) = max_{u∈G_{d-1}} Π_range(u)}
POC_range  := argmin_{p∈M_range} |p - C_{d-1}|
```

POC tie-break：

```text
If multiple price buckets have max profile volume,
choose the one nearest to previous session close C_{d-1}.
```

默认：`poc_mode = close`。

### 3.2 VA

候选：

```text
va_mode ∈ {greedy_from_poc}
ρ       := value_area_ratio
```

定义：

```text
Adj(S_k) := nearest unselected lower/upper price bucket adjacent to [min(S_k), max(S_k)]
S_0      := {POC}
S_{k+1}  := S_k ∪ {argmax_{p∈Adj(S_k)} (Π(p), side_priority(p))}
stop(k)  := Σ_{p∈S_k} Π(p) >= ρ · Σ_p Π(p)
VAL      := min(S_k)
VAH      := max(S_k)
```

VA expansion tie-break：

```text
side_priority(p) := +1 if p > max(S_k), else 0
```

即相邻上下桶成交量相等时，先扩上边界。

profile 对照：

```text
if poc_mode = close:
    Π_{d-1} := Π_close
    P       := POC_close

if poc_mode = range:
    Π_{d-1} := Π_range
    P       := POC_range
```

## 4. 事件定义

参数：

```text
b := min_breakout_ticks
r := min_reaccept_ticks
δ := poc_test_band_ticks
```

边界突破：

```text
Break_L(t) := L_t <= D - bτ
Break_U(t) := H_t >= U + bτ
```

同侧突破极值：

```text
X_L(t) := min{L_i | i <= t, Break_L(i) since last reset}
X_U(t) := max{H_i | i <= t, Break_U(i) since last reset}
```

突破距离：

```text
B_L(t) := T(D - X_L(t))
B_U(t) := T(X_U(t) - U)
```

重新接受：

```text
R_L(t) := X_L(t) exists ∧ C_t >= D + rτ
R_U(t) := X_U(t) exists ∧ C_t <= U - rτ
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
T_s^-      := previous same-side exit time
T_last_exit := previous exit time across all sides in session d
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
TouchPOC_long(t0,t1)  := max_{t0<=u<=t1} H_u >= P - δτ
TouchPOC_short(t0,t1) := min_{t0<=u<=t1} L_u <= P + δτ
TouchPOC_q(t0,t1)    := TouchPOC_long(t0,t1),  if q = +1
TouchPOC_q(t0,t1)    := TouchPOC_short(t0,t1), if q = -1
```

## 6. 开仓条件候选

候选集合：

```text
Ω ⊆ {C1, C2, C3}
```

三类条件：

```text
C1_s(t) := A_s = 0
C2_s(t) := B_s^- exists ∧ B_s(t) < B_s^-
C3_s(t) := Z_s^- = False
```

组合条件：

```text
C_Ω(s,t) := ∨_{C∈Ω} C_s(t)
```

overlap 诊断：

```text
C2_only := C2 ∧ ¬C3
C3_only := C3 ∧ ¬C2
C23     := C2 ∧ C3
```

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
E_t := C_t
```

方向有效性：

```text
DirOK(s,t,to_poc)         := q_to_poc(s) · (P - E_t) > 0
DirOK(s,t,away_from_poc)  := q_away(s) · (P - E_t) < 0
```

目标空间：

```text
m          := min_target_ticks
SpaceOK(t) := |P - E_t| >= mτ
```

全局执行约束：

```text
Flat(t)              := no open position before evaluating bar t
PrevLevelsAvailable := P,D,U from session d-1 exist
InEntryTimeWindow(t) := trade_start_time <= time(t) <= last_entry_time
ForceFlatTime(t)     := time(t) >= force_flat_time
TradeCount_d         := number of entries already opened in session d
CooldownOK(t)        := no previous exit, or time(t) - T_last_exit >= cooldown
```

```text
ExecOK(t) := Flat(t)
          ∧ PrevLevelsAvailable
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
              ∧ C_Ω(s,t)
```

策略参数：

```text
θ_profile := (poc_mode, va_mode, ρ)
θ_signal  := (direction_mode, Ω, b, r, δ, m, N_max, cooldown)
θ_exec    := (α, β, λ, stop_atr_bars, stop_atr_multiplier, rr_min, max_hold_bars, strict_close_exit)
θ_size    := (Capital, risk_per_trade, contract_size, max_position_ratio, margin_rate)
θ         := (θ_profile, θ_signal, θ_exec, θ_size)
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

默认：`d_atr = 0`。

止损价：

```text
Stop_t := E_t - q · d_stop
```

目标价：

```text
Target_t := E_t + q · α · |P - E_t|
0 < α <= 1
```

交易冻结变量：

```text
t_entry := entry time
Entry   := E_t at t_entry
Stop    := Stop_t at t_entry
Target  := Target_t at t_entry
F       := F_t at t_entry
q       := q at t_entry
```

风险收益过滤：

```text
RiskOK(s,t) := d_stop > 0
            ∧ q · (Target_t - E_t) > 0
            ∧ |Target_t - E_t| >= mτ
            ∧ |Target_t - E_t| / d_stop >= rr_min
```

仓位：

```text
Capital            := account equity used for sizing
risk_per_trade     := max capital fraction risked per trade
contract_size      := contract multiplier
max_position_ratio := max capital fraction used as margin notional
margin_rate        := exchange margin rate
```

```text
volume_risk   := floor(Capital · risk_per_trade / (d_stop · contract_size))
volume_margin := floor(Capital · max_position_ratio / (E_t · contract_size · margin_rate))
volume        := max(0, min(volume_risk, volume_margin))
```

若 `volume = 0`，则不开仓。

## 9. 退出函数

持仓期间不评估新入场：

```text
Position_t ≠ 0 => evaluate Exit only
```

退出参数：

```text
strict_close_exit := whether close beyond F triggers exit
holding_bars      := number of bars since t_entry
max_hold_bars     := max holding bars before time exit
```

long 退出：

```text
Exit_long(t) := first_true(
  L_t <= Stop,
  strict_close_exit ∧ C_t <= F,
  H_t >= Target,
  ForceFlatTime(t),
  holding_bars >= max_hold_bars
)
```

short 退出：

```text
Exit_short(t) := first_true(
  H_t >= Stop,
  strict_close_exit ∧ C_t >= F,
  L_t <= Target,
  ForceFlatTime(t),
  holding_bars >= max_hold_bars
)
```

退出优先级：

```text
stop_loss > strict_failure_close > take_profit > force_flat > time_exit
```

退出价：

```text
stop_loss / take_profit: use engine fill model
strict_failure_close / force_flat / time_exit: strategy-level C_t
```

交易关闭后：

```text
A_s         := A_s + 1
B_s^-       := B_s(t_entry)
Z_s^-       := TouchPOC_q(t_entry, t_exit)
T_s^-       := t_exit
T_last_exit := t_exit
```

## 10. 状态重置

session reset：

```text
A_L = A_U = 0
B_L^- = B_U^- = None
Z_L^- = Z_U^- = None
T_L^- = T_U^- = None
T_last_exit = None
TradeCount_d = 0
breakout_tracking = None
trade_info = None
```

breakout reset：

```text
reset(s)   <= Enter(s,t;θ)
reset(L,U) <= new session
```

默认不因反向突破清空另一侧状态。

## 11. 首轮默认候选

```text
poc_mode = close
va_mode = greedy_from_poc
direction_mode = to_poc
Ω ∈ {{C1}, {C2}, {C3}, {C2,C3}, {C1,C2,C3}}
α = 0.8
δ ∈ {0, 1}
N_max = 3
cooldown ∈ {K1, optionally K0}
β = 1
λ = 1.0
rr_min = 0.8
max_hold_bars = 60
strict_close_exit = true
```
