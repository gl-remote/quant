# value_area_reacceptance 工程实现细节

> 类型：Theme / 工程实现细节
> 状态：占位 / 待实现开始后填充
> 最近更新：2026-07-03
> 数学规格：[strategy-math-spec.md](strategy-math-spec.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)
> 参数选择：[parameter-selection-spec.md](parameter-selection-spec.md)
> 主题入口：[README.md](README.md)

## 0. 文档定位

本文件记录 R30 策略从 [strategy-math-spec.md](strategy-math-spec.md) 落到代码时的**工程选择与优化细节**，只涉及"怎么实现"，不改变"是什么"：

- **不定义任何策略行为**——策略行为由 strategy-math-spec.md 唯一确定；
- **不记录实验流水**——实验结果写在 `docs/workbench/` 或归档；
- **不覆盖参数选择流程**——参数选择规则见 parameter-selection-spec.md；
- **只回答**：给定 spec，代码层应如何组织数据结构、事件调度、缓存策略、成交模型桥接、精度处理、性能优化，才能既正确又高效。

若某项工程决定影响策略语义（例如"平仓刷新与再入场的时序"），说明 spec 定义不完整，必须先回补 strategy-math-spec.md，再更新本文件。

## 1. 状态说明

本文件处于占位状态，实际实现开始后按下列小节填充。填充时保持"每条决定都有理由 + 反例说明为什么不选别的方案"的格式。

## 2. 待补写内容清单

### 2.1 数据结构与状态维护

```text
- session 级 vs bar 级状态的存储层次；
- 每侧 s ∈ {L, U} 的状态槽如何组织；
- 冻结变量 (Entry, Stop, Target, F, q, Anchor) 的生命周期与内存模型；
- 状态在 backtest 与实盘之间的兼容层。
```

### 2.2 Profile 滚动窗口的增量维护

```text
- 每次刷新 u 的 profile 是否全量重算 vs 增量维护；
- close-profile 与 range-profile 的桶数据结构选择（dict / SortedDict / numpy array）；
- VA 贪心扩展的边界维护；
- 采用型 vs 监控型刷新的开销分离（Adopt(u) = 0 时可跳过下游代价大的量）。
```

### 2.3 事件调度与 bar 循环

```text
- T_refresh / T_adopt 的构造顺序（先枚举 InitEvent → TickEvent → ExitEvent）；
- 同一 bar 上多事件同时触发时的合并处理；
- Enter 与 Refresh 在同一 bar 上的优先级：Enter 前评估 => Refresh 后处理；
- 平仓刷新与下一 bar Enter 的时序（保证 CooldownOK 正确度量）。
```

#### 2.3.1 on_bar 内的评估顺序（对齐 spec §6.2 "更新前状态"，2026-07-03）

`ValueAreaMultiAttemptPocReversionStrategyCore.on_bar` 单根 bar 的评估顺序**必须**按下列固定顺序执行：

```text
1. _ensure_session(state, ctx)           # spec §11.1 session reset（若跨 session）
2. _append_bar_history(state, ctx.bar)   # bar 存入 history，同步 bar_idx
3. _maybe_init_refresh(state, config)    # spec §11.3.1 InitEvent（首次 Adopt）
4. _maybe_tick_refresh(state, config)    # spec §11.3.1 TickEvent + §11.3.3 Adopt
5. _track_breakout(state, ctx, config)   # 把 bar t 的 Break_s(t) 装入 J_s
6. _entry_signal / _exit_signal(...)     # §7-§10 判定，使用 §6.2 "更新前"的 (A_s, B_s^-, Z_s^-)
7. _track_attempt_event(state, ctx, config)  # §5.6 AttemptEvent_s(t) := R_s(t) 若成立 → §6.2 更新
8. _advance_bar_index(state)             # bar_idx += 1
```

关键约束：**Step 7 必须在 Step 6 之后**。这是 spec §6.2「对同一 bar `t` 上的 Enter 判定，使用**更新前**的 `(A_s, B_s^-, Z_s^-)`」的字面落地：
- 首次 attempt 触发的 bar：Step 6 读到 `A_s = 0` 触发 C1；Step 7 再把 `A_s → 1`
- 次次 attempt 触发的 bar：Step 6 读到 `A_s = 1` 且 `B_s^-` 已定义，可判定 C2；Step 7 更新为 `A_s = 2`

反例：若 Step 7 放在 Step 6 之前，首次事件会更新 `A_s → 1`，导致同 bar 的 Enter 判定读到 `A_s = 1`，C1 永远不触发。

#### 2.3.2 Refresh 事件的 Adopt 分支（对齐 spec §11.3.3 + §11.3.4，2026-07-03）

三种 Refresh 事件（Init / Tick / Exit）在 `Adopt(u) = 1` 时都要执行相同的三步：

```text
Adopt=1 branch (共享):
  a) 更新 (P_t, D_t, U_t) := (P̂_u, D̂_u, Û_u)
  b) Reset_s(u) := 1 for s ∈ {L, U}      # _reset_side_track 清空 J_s / X_s
  c) Replay(u; s)                        # _replay_attempt_events 回填 attempt 侧状态
```

三个 refresh 方法 (`_maybe_init_refresh` / `_maybe_tick_refresh` / `_exit_refresh`) 都要**统一**执行这三步；`Adopt(u) = 0` 分支（持仓期 tick）只计算 `Π̂_u` 用于监控，什么都不改。

反例：早期实现只在 `_maybe_init_refresh` 里做 Reset，Tick / Exit 分支忘记 Replay，会导致 `A_s / B_s^-` 在 Adopt 后仍是旧锚下的累积值，`C2/C3` 判定漂移。

### 2.4 突破跟踪 X_s 的实现

```text
- J_s(t) 是否物化整段列表 vs 只维护 min/max 极值；
- i_start(t) 前移时如何逐 bar 剔除过期突破 bar；
- Reset_s = 1 事件如何触发 J_s 与 X_s 清空；
- 反向突破与未成交 R_s 不清空 X_s 的正确性验证。
```

#### 2.4.1 anchor drift 与 Break_s^*(i | t) 的实现（对齐 spec §5.2 + §5.3，2026-07-03）

历史 bar 的突破判定 `Break_s^*(i | t)` 用**当前**锚 `U_t / D_t` 复核，而不是 bar i 上的历史锚 `U_i / D_i`。实现：

```text
BreakoutTrack = {bar_indices: deque, extremes: deque}   # 只存 (idx, extreme)
_track_add(bar_idx, extreme)          # bar t 上 Break_s(t) 成立时追加
_track_evict(min_idx)                 # i_start 前移时按 bar_indices[0] < min_idx 弹出
_track_x(track, side, anchor, b_tau)  # 每次访问时用 anchor 过滤 extremes，取 max/min
```

`_track_x` 每次访问 O(n_step) 复扫，不缓存中间结果：因为每次刷新后 `anchor` 可能变化，缓存需要伴随 anchor 版本失效，反而复杂。n_step ≤ 200 的量级下线性扫描完全够用（Stage B 单跑 0.8s）。

反例：如果 `_track_add` 时先用 bar-i 的锚过滤，虽然存量小，但 anchor drift 上移后老 breakout 会被永久锁定为 "有效"，B_s 可能出现负值（对应 Stage A 09-02 10:55 的 C2 假触发）。

### 2.5 AttemptEvent 与 Replay（对齐 spec §5.6 + §6.2 + §11.3.5）

#### 2.5.1 `_track_attempt_event` 与交易解耦（2026-07-03）

`AttemptEvent_s(t) := R_s(t)` 是纯**事件层**信号：无论是否实际下单，只要 bar t 上 `R_s(t)` 成立就更新 `(A_s, B_s^-, Z_s^-, T_prev_event)`。这跟 R29 的 spec v1 语义（在 `_close_trade` 里更新 `A_s`）根本不同——**新 spec 把 attempt 从交易依赖里剥离**，才能让 C2/C3 有实际触发机会。

调用点（见 §2.3.1）：`_entry_signal / _exit_signal` 之后、`_advance_bar_index` 之前。

同一 bar 上双侧都可能触发（L 侧 R_L=1 且 U 侧 R_U=1，虽然罕见），两侧各自独立更新。

`_close_trade` 现在只维护 `T_last_exit`，**不再动 attempt 侧状态**。反例：spec v1 在 `_close_trade` 里 `A_s += 1` 导致次次 attempt 永远只在平仓后才能被记录，`C2/C3` 需要至少一次实际交易才能成立，这是 R29 → Stage B `C2/C3 = 0 trades` 的直接根因。

#### 2.5.2 `_touch_poc_since` 的 fallback 优先级（2026-07-03）

当 `T_prev_event` 为 None 时（session 内还没发生过任何 AttemptEvent），起点按下列优先级选取：

```text
1. T_prev_event（若存在）→ since_bar_idx + 1
2. t_ref（当前 Adopt 时刻，实现为 state.extra["va_r30_last_refresh_bar_idx"]）
3. 0（session 开始，仅在 Adopt 从未发生时兜底）
```

对齐 spec §6.2：Adopt 前旧锚下的历史 `P_i` 与新锚 `P_t` 语义不同，混入 Adopt 之前的 bar 会污染 `Z_s^-`；所以 fallback 用 `t_ref(t)` 而不是 `session_start`。若 session 尚未 Adopt，`last_refresh_bar_idx` 为 None，回落到 0。

#### 2.5.3 `_replay_attempt_events` procedure（2026-07-03）

`Adopt(u) = 1` 后用新锚在 `[max(cur_idx - n_step, session_start), cur_idx - 1]` 内**顺序扫描** bar history，用新锚 `(P_u, D_u, U_u)` 复算 `AttemptEvent`，预填四个状态变量。伪代码严格按 spec §11.3.5 落地。

关键实现细节：

```text
- replay_bars = list(history)[-(replay_len+1):-1]  # 跳过当前 bar，按时间升序
- touch_start_idx 初始 = replay_start - 1          # 首事件 TouchPOC 覆盖整个前缀
- 每次触发 event 后：touch_start_idx = idx(i)       # 后续事件起点前移
- TouchPOC 用新锚 P_u（对所有 replay bar 统一），
  这是 spec §5.7 的例外，见 §11.3.5 的解释（反事实计算需坐标系一致）
- L 与 U 侧独立执行，各自维护 breakout_seen / breakout_extreme
```

Replay 后 `J_s / X_s` **仍为空**（Reset_s = 1 通过 §5.3 的 `i_start = idx(u)+1` 生效），要等 `t >= u+1` 上新的 `Break_s^*` 才能重新累积。这决定了 Adopt 当根 bar 上 `Enter` 必然为 False（`R_s(u)` 要求 `Exists_s(u) = 1`，而此时 `J_s(u) = ∅`）。

反例：如果 Replay 顺便回填 `J_s / X_s`（即等价于把新锚 breakout 也物化），会让 `Enter(s, u; θ)` 在 Adopt 当根就可能触发，违反"新锚初始化后至少等一根 bar"的 spec §11.3.4 规定。

### 2.6 止盈候选状态位

```text
- Anchor / signed_pnl / peak_pnl 在持仓期间的增量维护；
- Armed(t) := 1[peak_pnl(t) >= arm_level] 利用 peak_pnl 单调性 O(1) 更新；
- fast_window(t) / u_fast(t) 的滚动实现；
- TP_fixed_active(t) 与 TP_soft_active(t) 分派到不同成交模型的代码路径。
```

### 2.7 精度与舍入

```text
- price_tick 全局配置 vs 品种级配置；
- bucket_profile / bucket_buy / bucket_sell 的统一实现入口；
- 浮点数比较容差；
- G_τ 越界处理（session 内新极值超出上一次 profile 桶范围）。
```

### 2.8 与回测引擎的桥接

```text
- vnpy BacktestingEngine 的下单接口与 Stop / Target 挂单模型；
- TP_soft（策略级 C_t 平仓）的成交撮合口径；
- 手续费 / 滑点 / 保证金在 R30 策略下的口径与 baseline 保持一致；
- trade_clearings 清算口径 vs vnpy BacktestResult 口径的选择与切换。
```

#### 2.8.1 vnpy fill-on-next-bar 惯例（Stage A 校核发现，2026-07-03）

vnpy BacktestingEngine 采用"bar 收盘信号 → 下一根 bar 开盘成交"模型：

```text
strategy.on_bar(bar_t)       fires Signal at time(bar_t)
engine fills at              time(bar_{t+1})   (next bar's open time)
backtest_trades.datetime     = time(bar_{t+1})
signal 时间 (bar 收盘)         = time(bar_t)
```

结论：

```text
1. backtest_trades.datetime 与 backtest_trades.decision_payload.execution.exit_reason
   触发时点相差一根 bar；跨会话（日盘 14:55 → 夜盘 21:00）时时间跳跃可达数小时。
2. 归因分析按"信号时间"分层的口径必须用 payload.execution.entry_bar_idx
   或 payload.execution.holding_bars 派生，而不是 backtest_trades.datetime。
3. 策略层 holding_bars = idx(t_exit_signal) - idx(t_entry_signal)（信号 bar 索引之差）
   与引擎侧 fill 时间无关，是正确的持仓时长度量。
4. 报告里出现 force_flat 交易 datetime = 夜盘时间点属于正常现象，不是策略 bug。
```

处置：本项目 R30 及后续 vnpy 引擎回测统一遵循此惯例；跨引擎（tqsdk）验证时若成交模型不同，需另开一节记录差异。

### 2.9 参数与配置

```text
- θ_profile / θ_signal / θ_exec / θ_size 的配置 schema；
- Ω_pattern / Ω_risk / Ω_direction / Ω_tp 的枚举与序列化格式；
- 每轮实验配置的 config 目录布局；
- CLI / runner 与策略 data_requirements 的一致性校验。
```

### 2.10 性能优化

```text
- 全部 bar 一次性构造 idx / time 数组；
- 滚动窗口的 O(1) 更新技巧（deque / segment tree / SortedList）；
- profile 计算按需重算的短路；
- 大样本回测下的内存 footprint 控制（不保留全部 Π̂_u 历史，只保留 T_adopt 上的采用值）。
```

### 2.11 测试与验证

```text
- 单元测试：POC / VAL / VAH 构造、tie-break、round_τ、reset 触发；
- 集成测试：single-bar smoke test 覆盖 Enter / Exit 全路径；
- 属性测试：随机 bar 序列下 §10.3.4 正交性断言；
- 回归测试：value_area_reacceptance_baseline 与 R30 隔离运行，互不影响。
```

## 3. 与其他文档的边界

- 本文件不定义**任何**策略行为；如需改变行为，先改 [strategy-math-spec.md](strategy-math-spec.md)。
- 本文件不记录**任何**实验结果；实验流水写到 `docs/workbench/`。
- 本文件不给出**任何**参数选择判据；判据见 [parameter-selection-spec.md](parameter-selection-spec.md)。
- 本文件不重述 [experiment-plan.md](experiment-plan.md) 的候选矩阵。

## 4. 更新触发条件

- 开始实现某个模块前，先在对应小节写"计划的实现选择"；
- 实现完成后回填"实际采用的实现 + 反例 + 性能数据"；
- 若某项决定后来被证明影响语义，先回改 [strategy-math-spec.md](strategy-math-spec.md)，再更新本文件；
- 每次 spec 有跨小节的结构性变更，同步检查本文件相关小节是否需要补写。
