# value-area-rolling-reacceptance · 主题草案

> 类型：Theme / 草案（尚未启动实施）
> 状态：仅设想已成文 · 主题目录未完全初始化 · 触发条件见 §6
> 前提：等 `value-area-reacceptance` 主题的 R30 空间完全挖掘、
> feature-only 结论稳定归档后，再评估是否启动本主题
> 关联主题：[../value-area-reacceptance/README.md](../value-area-reacceptance/README.md)
> 创建时间：2026-07-03

## 1. 动机

当前 `strategy-math-spec.md` 里 POC / VA 只在 InitEvent / TickEvent /
ExitEvent 三种时刻刷新，其余时段用"上一次采纳"的锚。这种「离散刷新 + 跨
bar 累积 attempt state」的设计有三个后果：

1. 引入了 §11.3.5 Replay 的反事实计算（用新锚在过去 n_step 根 bar 上重扫
   attempt），需要专门解释「Replay 是 §5.7 的例外」；
2. 策略核心持有一大堆跨 bar 状态：`SideState`、`BreakoutTrack`、
   `T_prev_event`、`va_r30_anchors` 等；
3. C2 语义的"最近一次 vs 上一次"跟"当前锚 vs 上一次锚"两个坐标系纠缠，
   spec 需要显式声明反事实计算规则。

如果参照布林带 / KDJ 一类 rolling indicator 的设计思路，把 POC / VA 做成
**每 bar rolling recompute** 的 indicator，上述三个问题都消失：

- POC / VAH / VAL 每 bar 都是"最近 n_profile 根 bar 的 volume profile"
- 每根历史 bar `i` 有它自己那一刻的 `(P_i, U_i, D_i)`（rolling 锚）
- C1/C2/C3 是"最近 n_step 根 bar 上按 rolling 锚重扫 attempt"的滚动统计
- 策略核心零跨 bar 状态

## 2. 语义定义（草稿）

### 2.1 每 bar rolling 锚（indicator 层）

```text
Window(t) := 最近 n_profile 根已收盘 bar
Profile_t := volume_profile(Window(t))          # rolling
P_t       := select_poc(Profile_t, C_t)
(D_t, U_t):= greedy_value_area(Profile_t, P_t, ratio)
```

### 2.2 每 bar rolling 事件（indicator 层）

```text
Break_L(i)  := 1[L_i <= D_i - b_tau]            # 用 bar i 自己的 D_i
Break_U(i)  := 1[H_i >= U_i + b_tau]
R_L(i)      := 1[Break_L(i-k..i) 存在 ∧ C_i >= D_i + r_tau]
R_U(i)      := 1[Break_U(i-k..i) 存在 ∧ C_i <= U_i - r_tau]
```

即每根 bar 上 breakout / reacceptance 都用 **bar 自己那一刻的 rolling 锚**
判定，跟布林带突破逻辑完全同构。

### 2.3 t 时刻的滚动统计（strategy 层，纯查表）

```text
Events_s(t) := { i ∈ [t-n_step+1, t] : R_s(i) = 1 }        # 最近 n_step 内的 attempt
A_s(t)      := |Events_s(t)|
i_last(t)   := max(Events_s(t))                            # 最近一次 attempt
i_prev(t)   := 第二大 idx in Events_s(t)
B_s^-(t)    := B_s(i_prev(t))                              # 上一次 attempt 的 B_s
B_s(t)      := 当前 bar 的 B_s（用 t 时刻的 U_t / D_t 和最近突破 bar 的 extreme）
Z_s^-(t)    := TouchPOC_q(i_prev(t)+1, i_last(t)-1)        # 相邻两次 attempt 间是否触 POC
```

C1/C2/C3 判定：

```text
C1_s(t) := A_s(t) = 0     # 最近 n_step 内还没有 attempt
C2_s(t) := A_s(t) >= 1 ∧ B_s(t) < B_s^-(t)
C3_s(t) := A_s(t) >= 1 ∧ Z_s^-(t) = False
```

### 2.4 TouchPOC 判定的锚选择

两种可选：

- **B-per-bar**：每根中间 bar `i` 用它自己那一刻的 `P_i` 判定
  `L_i <= P_i - δ_tau <= H_i`（**推荐**，与布林带 rolling 语义完全一致）
- **B-current**：整段 window 都用当前 `P_t` 判定（简单，但混合坐标系）

## 3. 优点

1. **完全无状态**：策略核心只读 indicator，不维护跨 bar 变量
   - `SideState` / `BreakoutTrack` / `T_prev_event` / `va_r30_anchors`
     全部删除
2. **spec 大幅简化**：§5.3 `Reset_s / i_start / τ_s`、§6.2 attempt 更新
   规则、§11.3 三类刷新事件、§11.3.5 Replay 全部删除，spec 长度约减半
3. **多策略复用**：POC / VA 提炼为 `VolumeProfileIndicator`，别的策略
   （比如未来 continuation 对照线）能直接读同一 indicator
4. **反事实计算问题消失**：每 bar 都是 rolling 计算，历史 bar 用历史锚，
   spec §5.7「TouchPOC 逐 bar 用自身锚」是唯一规则，没有例外
5. **C2 语义天然成立**：`B_s(t)` 用 t 时刻的 U_t 和最近 breakout 的 extreme，
   `B_s^-` 是 i_prev 时刻的 U_{i_prev} 和当时的 breakout extreme，两者可
   自然比较

## 4. 代价

### 4.1 计算量

1m 数据 190k bar 单品种：

| 操作 | 每 bar 开销 | 全回测总量 | 估计 wall-clock |
|---|---|---|---|
| Rolling profile 重算（增量 add/remove）| O(K̄) | O(N · K̄) | <100ms |
| Profile → POC / VA 计算 | O(B log B) | O(N · B log B) | 1-3s |
| Break / R 判定（当前 bar）| O(1) | O(N) | <10ms |
| C1/C2/C3 滚动统计（查表）| O(n_step) | O(N · n_step) | ~1s |
| **合计** | ~5k op | | **~5-10s 单品种 1m** |

对比当前 Stage B 5m 数据单跑 0.4-0.8s，1m 数据每 bar 刷新版本约 20-30x，
仍在可接受范围。Stage B 225 runs 1m 数据估计 30-60min。

### 4.2 增量维护 rolling profile 的工程复杂度

- `range` 模式：bar 进入时 volume 摊到 K̄ 个桶（add），bar 离开时同样 K̄ 个
  桶反向 subtract，需要保留每根 bar 的 volume 分布（deque[dict]）
- `close` 模式：每 bar 一个桶 add/remove，简单
- POC / VA 计算：每 bar 从 rolling_profile 全量重算（O(B log B)）；也可以
  加缓存但收益有限

### 4.3 语义变化

- C1 定义从"本次刷新以来还没触发过 attempt"变成"最近 n_step 内还没触发过
  attempt"——n_step 大时含义变化不大；n_step 小时差别显著
- Adopt 时机消失：不再有"刷新采纳新锚"这个概念，也没有"Adopt 后不能立即
  开仓"的约束。策略随时可用最新 POC / VA
- 「持仓期间锚不变」的行为消失：不需要区分是否持仓，锚永远是 rolling 的
- session reset 从"清空 attempt state"变成"清空 rolling window 里跨 session
  的 bar"——需要在 indicator 层处理

## 5. 未决问题

- **n_step 保留还是删除？** 保留作为 attempt 追溯长度（推荐）；或者直接
  用 n_profile 判 attempt（简化）
- **Session 边界处理**：rolling window 是否允许跨夜盘 → 日盘 → 夜盘？
  当前 spec 规定 session_start 时 Reset。rolling 版本需要在
  VolumeProfileIndicator 里明确 session boundary 规则
- **参数命名**：`n_profile` / `n_step` 语义都保留，但含义从"离散刷新周期"
  变成"滚动窗口长度"，需要 spec 与代码同步更名或加注释
- **诊断字段**：`va_r30_last_refresh_bar_idx` 等成为无意义字段，需要
  三层诊断（Alpha / Risk / Execution）里的相关字段一并清理

## 6. 触发条件

**暂不实施**。等下列条件之一满足再启动重构：

1. 当前 spec §7-§10 定义的 R30 空间（Ω_pattern × Ω_risk × Ω_direction
   × Ω_tp）跑完首轮候选参数、feature-only 结论稳定归档；
2. 有第二个策略需要复用 POC / VA 概念，`VolumeProfileIndicator` 抽取
   有明确复用价值；
3. Stage C 需要在 1m 数据上验证结构信号，当前 5m spec 不足以覆盖。

## 7. 参考

- 布林带 rolling 突破再接受：mid / upper / lower 每 bar rolling，
  breakout / reaccept 每 bar 用当时锚判定，无跨 bar 状态。是本提案的
  参考模型。
- 当前 spec 的 Replay 机制（§11.3.5）是"想吃 rolling 的直觉，但被离散
  刷新 + 跨 bar 状态设计束缚"的折中产物；rolling 版本让这个 workaround
  自然消失。
