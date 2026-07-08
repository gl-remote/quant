# poc-value-area-asymmetry · 分类器数学规格

> 类型：Theme / 分类器数学规格（数学契约唯一源）
> 状态：**v3.0（2026-07-08）· 互斥单值分类器 · 10 mutex tier · 阶段 4 冻结**
> 主题 README：[README.md](README.md)
> 研究状态：[research-status.md](research-status.md)
> 参数选择与性能报告：[parameter-selection-spec.md](parameter-selection-spec.md)（一眼可读版）
> 实验计划：[experiment-plan.md](experiment-plan.md)
> 阶段 3 详细流水：workbench:poc-value-area-asymmetry-stage3-robustness

## 1. 目标与契约边界

### 1.1 分类器契约

**本文件是"POC value area 不对称背景分类器"的唯一契约**。任何策略若使用
本分类器输出的标签，其行为完全由本文件规格决定。

### 1.2 明确不包含的内容

- ❌ **入场规则**（触发时刻的具体订单类型、限价/市价、进场时机）
- ❌ **出场规则**（时间止盈、追踪止损、条件出场）
- ❌ **仓位管理**（Kelly、定额、波动率归一化）
- ❌ **账户闸门**（单次风险、MDD、频率限制）
- ❌ **交易成本**（佣金、滑点、冲击）

以上属于完整策略层面，若阶段 4 通过则写入 `strategy-math-spec.md`
并显式引用本分类器规格。

### 1.3 分类器输出承诺

对每个事件时刻 `t`（每小时整点）· 每个合约 `s` · 分类器输出：

```text
Classifier(s, t) := (
  skew_label,           -- 偏度分类（中间态）
  atr_regime,           -- 波动率制度（中间态）
  trend_regime,         -- 趋势制度（中间态）
  transition_flag,      -- regime 转换标记
  tier: str | None,     -- 单值互斥 tier · 见 §7.3（10 类之一 或 None）
  meta                  -- 完整原始数值
)
```

**每个 event 属于且仅属于一个 tier**（或 `tier = None` · 未分类）·
不再是 `List[str]` · 输出严格单值 · 互斥定义见 §7。

## 2. 基础对象与量纲

### 2.1 时间与索引

```text
d          := current trading session
d-1        := previous trading session (used to build profile)
I_all      := bar index set across all historically available sessions
I_d        := bar index set of session d
idx(t)     := ordinal position of bar t in I_all (1-based, monotonic)
time(t)    := wall-clock timestamp of bar t (bar close time)
```

跨 session 拼接：`I_all` 中相邻即视作连续 bar 序列（沿用 KF-04 dedup 语义）。

### 2.2 Bar 结构

```text
x_t := (O_t, H_t, L_t, C_t, V_t), t ∈ I_all
Δbar_profile := 5m       (profile 构建原始 bar)
Δbar_trade   := 1h       (事件时钟 · 触发时刻)
Δbar_daily   := 1d       (日线特征 bar)
```

### 2.3 事件时钟

```text
E := { t ∈ I_all | Δbar_trade divides time(t)  }
```

即：所有 wall-clock 分钟位为 `:00:00` 的 bar 索引集合（1h 事件时钟）。

**注**：阶段 2 洞察 O 验证过跨周期一致（15m/30m/1h/2h 全过）· 本规格
锁定 1h 为主分类器时钟。若阶段 4 需要 4h 时钟，另行分档。

### 2.4 量纲约定

```text
bar-count 量纲(idx(·)):     n_rolling_events, n_rolling_days, n_warmup_days
wall-clock 量纲(time(·)):    event_time
rank 量纲 (无量纲 [0, 1]):    signed_skew_rank, atr_rank, trend_rank
bps 量纲 (1e4 · log return): mean, CI, hit-weighted return
```

## 3. Profile 构建（W1 · 前一交易日）

### 3.1 Profile 窗口

阶段 1 洞察 D 已锁定 W1 = 前一交易日整体 profile · **W2/W3/前 N 天窗口
一律排除**。

```text
W1(t) := { i ∈ I_all | i ∈ I_{d-1(t)}, Δbar(i) = Δbar_profile }
```

即：**t 时刻所在 session 的前一个 session 的所有 5m bar**。

### 3.2 Volume Profile 构造

采用 **close-based bucketing**（阶段 1 洞察 A 已锁定）：

```text
τ          := price_tick (合约特定 · 由 workspace/common/contract_specs.py 提供)
G_τ        := { n · τ | n ∈ ℤ }                    -- tick 网格
bucket(p)  := round_τ(p) = floor_τ(p) if p/τ - floor(p/τ) < 0.5 else ceil_τ(p)

Π_W1(p; t) := Σ_{i ∈ W1(t)} V_i · 1[ bucket(C_i) = p ],  p ∈ G_τ
```

### 3.3 POC 与 Value Area（辅助 · 不用于分类器主输入）

```text
POC_W1(t) := argmin_{p ∈ M_W1(t)} |p - C_{last(W1(t))}|
    where M_W1(t) := { p ∈ G_τ | Π_W1(p; t) = max_{u ∈ G_τ} Π_W1(u; t) }
```

**注**：POC/VA 定义仅供参考。**本分类器实际使用的度量是 A3_skew（§4）**，
POC/VA 不进入触发条件。

## 4. A3_skew 度量

### 4.1 定义

阶段 1 洞察 A 已确认 A3_skew 唯一有效（A1/A2/A4 均未过 Bonferroni）。

```text
V_total(t) := Σ_{p ∈ G_τ} Π_W1(p; t)

μ_W1(t)    := (1 / V_total(t)) · Σ_{p ∈ G_τ} p · Π_W1(p; t)

σ_W1(t)    := sqrt(
                (1 / V_total(t)) · Σ_{p ∈ G_τ} (p - μ_W1(t))² · Π_W1(p; t)
              )

A3_skew(t) := (1 / V_total(t)) · Σ_{p ∈ G_τ} ((p - μ_W1(t)) / σ_W1(t))³ · Π_W1(p; t)
```

**范围**：`A3_skew(t) ∈ ℝ` · 典型值 `|A3_skew| < 3`。

**符号语义**：
- `A3_skew < 0` = 左偏（底厚）= profile 下方 volume 更集中 = **DN 事件**候选
- `A3_skew > 0` = 右偏（顶厚）= profile 上方 volume 更集中 = **UP 事件**候选

### 4.2 A3_skew 的严格无未来函数属性

`A3_skew(t)` 只依赖于 `W1(t)` 内的 5m bar · 即 **t-1 交易日的完整数据**。
在 t 时刻取值时 · **完全无当日信息**。

## 5. Rolling Rank 分位定义

### 5.1 Signed Skew Rank

对每个合约 `s` 独立维护 `A3_skew` 事件序列 · rolling 100 事件分位：

```text
n_rolling_events := 100                        -- rolling 事件窗口

E_s(t) := { u ∈ E | s(u) = s, idx(u) < idx(t) }        -- 合约 s 在 t 之前的事件集
E_s^prev(t, K) := { u ∈ E_s(t) | idx(u) 属于前 K 个事件 }   -- 前 K 事件子集

signed_skew_rank(s, t) :=
    (1 / |E_s^prev(t, K)|) · Σ_{u ∈ E_s^prev(t, K)} 1[ A3_skew(u) ≤ A3_skew(t) ]

    where K = n_rolling_events
```

**范围**：`signed_skew_rank ∈ [0, 1]`。

**语义**：
- rank ≈ 0 → A3_skew 是**过去 100 事件里的最低值**（极端左偏 / 底厚）
- rank ≈ 1 → A3_skew 是**过去 100 事件里的最高值**（极端右偏 / 顶厚）

**Tie-break**：当多个历史值等于当前值时 · 使用严格小于计数 · 即：

```text
signed_skew_rank(s, t) :=
    |{ u ∈ E_s^prev(t, K) | A3_skew(u) < A3_skew(t) }| / |E_s^prev(t, K)|
```

### 5.1a 独立采样单位与冻结约束（KF-22）

**表面 vs 实际**：
- **表面**：rolling 100 events 每个合约 · rank 有 100 个观察
- **实际**：`A3_skew` 是**日级变量**（同一交易日所有 event 共享 W1 · 因此 A3_skew 相同）·
  独立采样单位是**"合约-日期"**（约每合约 60 独立日）· 100 events ≈ **约 10 独立日**

**这意味着**：
- 同一交易日内所有 event 的 `signed_skew_rank` 完全相同
- 触发条件在**日级触发** · event 级只是"入场时机采样"
- 有效独立观察数远小于 event 总数

**冻结约束**（阶段 3 workbench §12.12 论证）：

- **rank 单位固定为 per-contract**：**禁止** cross-contract 池化 · **禁止**
  用 (品种前缀 / 交易所 / 全池) 计算 rank
- **禁止贝叶斯 shrinkage**：即使把其他合约作为先验也会破坏尾部信号
- **依据**：prefix 池化实验中 · 空头 4/5 档 Bonferroni 从 ✅ 降级到 ❌ ·
  因跨合约尾部 (p05, p95) 极差 0.5-0.7 · 池化会稀释极端触发的品种特异性
- **Bootstrap 单位**：必须按 **(contract, date)** cluster · 而非 (contract)
- **表述规范**：文档中报告样本量时 · 应同时给出 event 数和独立日数（例如
  "n_events=142 · n_indep_days≈14"）

**核心原则**："数据边界不可造假 · 承认样本量 · 用正确 bootstrap 揭露真实
不确定性 · 不用池化 / shrinkage 制造虚假显著性"（KF-poc-va-22 · 跨主题方法论）。

### 5.2 ATR Rank

Rolling 20 交易日的日线 ATR_10 分位：

```text
n_rolling_days := 20                           -- rolling 日窗口
n_atr_lookback := 10                           -- ATR 平均窗口

D_s(t) := { d' ∈ Trading_Sessions | s available on d', d' < d(t) }
D_s^prev(t, N) := { d' ∈ D_s(t) | d' 属于前 N 个 session }

TR_s(d) := max(H_s(d) - L_s(d),
                |H_s(d) - C_s(d-1)|,
                |L_s(d) - C_s(d-1)|)          -- 要求 d ≥ d_start(s) + 1

daily_atr_10_bps(s, d) := (1e4 / C_s(d)) · (1/n_atr_lookback) · Σ_{i=d-n_atr_lookback+1}^{d} TR_s(i)
                                              -- 要求 d ≥ d_start(s) + n_atr_lookback

atr_rank(s, t) :=
    |{ d' ∈ D_s^prev(t, N) | daily_atr_10_bps(s, d') < daily_atr_10_bps(s, d(t)-1) }|
    / |D_s^prev(t, N)|

    where N = n_rolling_days
```

**范围**：`atr_rank ∈ [0, 1]`。

**注**：`daily_atr_10_bps(s, d(t)-1)` 使用 **前一交易日** 的 ATR 值 · 无未来函数。

### 5.3 Trend Rank

Rolling 20 交易日的近 10 日累计 log return 分位：

```text
trend_ret_10d(s, d) := log(C_s(d) / C_s(d-9))

trend_rank(s, t) :=
    |{ d' ∈ D_s^prev(t, N) | trend_ret_10d(s, d') < trend_ret_10d(s, d(t)-1) }|
    / |D_s^prev(t, N)|

    where N = n_rolling_days
```

**范围**：`trend_rank ∈ [0, 1]`。

**语义**：
- rank ≈ 0 → 近 10 日累计跌幅是过去 20 日**最深**（跌段）
- rank ≈ 1 → 近 10 日累计涨幅是过去 20 日**最强**（涨段）

### 5.4 Warmup 约束

```text
n_warmup_days := max(n_rolling_days, n_atr_lookback + 10) = 20
                (设计为 20 · 因 n_atr_lookback=10 + 10 缓冲 = 20)
```

事件 `t` 有效 iff（`warmup_ok(s, t) = True`）：

```text
|E_s^prev(t, n_rolling_events)| ≥ n_rolling_events   -- 至少 100 个历史事件
∧ |D_s^prev(t, n_rolling_days)| ≥ n_rolling_days      -- 至少 20 个历史 session
∧ d(t) ≥ d_start(s) + n_warmup_days                   -- warmup 期过后
∧ TR_s / ATR_s 在 D_s^prev(t, n_rolling_days) 上全可定义
```

否则 `Classifier(s, t) := ClassifierOutput(warmup_ok=False, tier=None, transition_flag=None, ...)` （不触发）。

## 6. 分类器中间标签

### 6.1 Skew Label

```text
skew_label(s, t) :=
    "DN_strict"     if signed_skew_rank(s, t) ≤ 0.10
    "DN_loose"      if 0.10 < signed_skew_rank(s, t) ≤ 0.30
    "NEUTRAL"       if 0.30 < signed_skew_rank(s, t) < 0.70
    "UP"            if signed_skew_rank(s, t) ≥ 0.70
    "UP_extreme"    未使用（预留）
```

### 6.2 ATR Regime

3-way 分档（阶段 3 洞察 P 定义）：

```text
atr_regime(s, t) :=
    "low"     if atr_rank(s, t) ≤ 0.33
    "mid"     if 0.33 < atr_rank(s, t) < 0.67
    "high"    if atr_rank(s, t) ≥ 0.67
```

**辅助阈值**（用于宽松档位）：

```text
atr_extra(s, t) :=
    "≤0.50"   if atr_rank(s, t) ≤ 0.50
    "≤0.70"   if atr_rank(s, t) ≤ 0.70
    ">0.50"   if atr_rank(s, t) > 0.50
    ">0.67"   if atr_rank(s, t) > 0.67
    ">0.80"   if atr_rank(s, t) > 0.80
    (多个可同时命中)
```

### 6.3 Trend Regime

3-way 分档：

```text
trend_regime(s, t) :=
    "down"    if trend_rank(s, t) ≤ 0.33
    "flat"    if 0.33 < trend_rank(s, t) < 0.67
    "up"      if trend_rank(s, t) ≥ 0.67
```

**辅助阈值**（用于严格档位）：

```text
trend_extra(s, t) :=
    "≤0.20"   if trend_rank(s, t) ≤ 0.20
    "≥0.75"   if trend_rank(s, t) ≥ 0.75
    (多个可同时命中)
```

### 6.4 Transition Flag

Regime transition 定义（阶段 3 洞察 R）：

```text
n_transition_window_days := 3

-- Session 级 ATR 分档（区别于 event 级 atr_regime）
atr_bucket_session(s, d) :=
    "low"     if atr_rank_session(s, d) ≤ 0.33
    "mid"     if 0.33 < atr_rank_session(s, d) < 0.67
    "high"    if atr_rank_session(s, d) ≥ 0.67

    where atr_rank_session(s, d) := atr_rank on session d evaluated same way as §5.2
                                     using daily_atr_10_bps(s, d) and D_s^prev(d, N)

-- 前一同合约 session
prev_session(s, d) := max { d' ∈ D_s(·) | d' < d }

is_crossover(s, d) :=
    prev_session(s, d) exists
    ∧ atr_bucket_session(s, d) ≠ atr_bucket_session(s, prev_session(s, d))

transition_flag(s, t) :=
    1[ ∃ d' ∈ Trading_Sessions_of_s :
         d' ≤ d(t) ∧ d(t) - d' < n_transition_window_days
         ∧ is_crossover(s, d') = True ]
```

**语义**：
- `transition_flag = 1` → t 时刻处于 regime 转换期（前 3 交易日 atr 制度切换）
- `transition_flag = 0` → t 时刻处于 regime 稳定期

**注**：`d(t) - d'` 用 session 计数（不含周末停牌 · 只算实际交易日 · 沿用 §2.1 语义）。

## 7. 触发条件集合（10 互斥 tier）

### 7.1 互斥类别定义

**多头方向**（`skew_label ∈ {DN_strict, DN_loose} ∧ atr_rank ≤ 0.70 ∧ trend_rank ≥ 0.75`）：

```text
LP_only := { (s, t) : skew_label(s, t) = "DN_strict"
                    ∧ atr_rank(s, t) ≤ 0.70
                    ∧ trend_rank(s, t) ≥ 0.75 }
                                              -- 即 signed_skew_rank ≤ 0.10

LL_only := { (s, t) : skew_label(s, t) = "DN_loose"
                    ∧ atr_rank(s, t) ≤ 0.70
                    ∧ trend_rank(s, t) ≥ 0.75 }
                                              -- 即 signed_skew_rank ∈ (0.10, 0.30]
```

**空头方向**（`skew_label = UP ∧ trend_rank ≤ 0.20`）：

```text
SP_only := { (s, t) : skew_label(s, t) = "UP"
                    ∧ atr_rank(s, t) > 0.80
                    ∧ trend_rank(s, t) ≤ 0.20 }
                                              -- 极高波动率

SC_only := { (s, t) : skew_label(s, t) = "UP"
                    ∧ 0.67 < atr_rank(s, t) ≤ 0.80
                    ∧ trend_rank(s, t) ≤ 0.20 }
                                              -- 高波动率

SL_only := { (s, t) : skew_label(s, t) = "UP"
                    ∧ 0.50 < atr_rank(s, t) ≤ 0.67
                    ∧ trend_rank(s, t) ≤ 0.20 }
                                              -- 中偏高波动率
```

**互斥性证明**：

```text
LP_only ∩ LL_only = ∅
    (skew_label 二分 · DN_strict vs DN_loose 互斥)

SP_only ∩ SC_only ∩ SL_only = ∅
    (atr_rank 区间不重叠 · (0.80, ∞) / (0.67, 0.80] / (0.50, 0.67] 严格分割)

(LP_only ∪ LL_only) ∩ (SP_only ∪ SC_only ∪ SL_only) = ∅
    (skew 方向严格互斥 · DN_* vs UP 无交集)
```

### 7.2 稳定/转换拆分

对每个基础类 `M ∈ {LP_only, LL_only, SP_only, SC_only, SL_only}`：

```text
M_stable := { (s, t) ∈ M : transition_flag(s, t) = 0 }
M_trans  := { (s, t) ∈ M : transition_flag(s, t) = 1 }
```

由 `transition_flag ∈ {0, 1}` 二分 · 每个基础类拆分为互斥的 stable / trans ·
共 5 × 2 = **10 互斥 tier**。

### 7.3 Tier ID 列表

```text
Tiers := {
    LP_only_stable, LP_only_trans,
    LL_only_stable, LL_only_trans,
    SP_only_stable, SP_only_trans,
    SC_only_stable, SC_only_trans,
    SL_only_stable, SL_only_trans
}
```

`|Tiers| = 10` · 两两不相交 · 并集 = 「可分类事件全集」（warmup_ok ∧ 命中任一基础类）。

### 7.4 白名单（v3.0 · 阶段 4 冻结）

- **A 级 6 个**：`LP_only_full` · `LL_only_stable` · `SP_only_stable` · `SP_only_trans` · `SC_only_full` · `SC_only_trans`
- **A- 级 3 个**（时稳警示）：`LL_only_full` · `LL_only_trans` · `SP_only_full`
- **未过 6 个**：`LP_only_stable` / `LP_only_trans` / `SC_only_stable` / `SL_only_full` / `SL_only_stable` / `SL_only_trans`

注：`_full` 表示不区分 stable/trans（例如 `LP_only_full = LP_only_stable ∪ LP_only_trans`）·
`_full` 不是独立 tier · 是 stable/trans 的并集报告口径。

具体判据与性能指标见 [parameter-selection-spec.md](parameter-selection-spec.md)。

## 8. 严格无未来函数约束（Leakage Boundary）

### 8.1 数据边界

对每个 `Classifier(s, t)` 输出 · **所有输入数据严格来自 t 之前**：

```text
Data_inputs(s, t) := {
    W1(t),                         -- 前一交易日 5m bar (完全在 t 之前)
    E_s^prev(t, 100),              -- 前 100 个事件的 A3_skew 值
    D_s^prev(t, 20),               -- 前 20 个 session 的 daily 特征
}
```

### 8.2 时序保证

```text
∀ (s, t) with tier(s, t) ≠ None:
    max { time(u) : u ∈ Data_inputs(s, t) } < time(t)
```

即：**分类器输出在 time(t) 时刻可用 · 不需要 t 之后的信息**。

### 8.3 Session 边界约束

`d(t) - 1` 必须是**已完全收盘的 session**（不含跨夜 bar 未完成情况）·
夜盘品种沿用 KF-04 的 session 划分（`workspace/common/contract_specs.py`
给出每合约的 session_close_time）。

## 9. 输出 API

### 9.1 单事件输出结构

```text
ClassifierOutput := {
    -- 元数据
    contract: str                  -- 合约代码 (e.g. "rb2601")
    event_time: datetime           -- 事件 wall-clock 时间
    event_hour: int ∈ {0..23}      -- 事件小时（用于时段分析）

    -- 原始数值
    A3_skew: float | NaN
    signed_skew_rank: float ∈ [0, 1] | NaN
    daily_atr_10_bps: float ≥ 0 | NaN
    atr_rank: float ∈ [0, 1] | NaN
    trend_ret_10d: float | NaN
    trend_rank: float ∈ [0, 1] | NaN

    -- 中间标签
    skew_label: str ∈ {"DN_strict", "DN_loose", "NEUTRAL", "UP", None}
    atr_regime: str ∈ {"low", "mid", "high", None}
    trend_regime: str ∈ {"down", "flat", "up", None}

    -- Regime transition
    atr_bucket_current: str
    atr_bucket_prev: str | None
    is_crossover_today: bool
    transition_flag: bool | None    -- None if warmup 不足

    -- Tier 命中（单值 · 互斥 · 见 §7）
    tier: str | None
    -- ∈ {LP_only_stable, LP_only_trans,
    --    LL_only_stable, LL_only_trans,
    --    SP_only_stable, SP_only_trans,
    --    SC_only_stable, SC_only_trans,
    --    SL_only_stable, SL_only_trans}
    -- 或 None（未命中任何基础类 / warmup 未满足）

    -- Warmup 状态
    warmup_ok: bool
}
```

### 9.2 输出不变量

```text
∀ output:
    warmup_ok = False  =>  tier = None ∧ transition_flag = None
    warmup_ok = True   =>  transition_flag ∈ {True, False}

    -- 互斥性（单值不变量）
    |{ hit tier }| ≤ 1
    tier ∈ Tiers ∪ {None}                    -- 10 mutex tier 之一 或 None

    -- Tier 与中间标签的等价关系（tier ≠ None 时）
    tier = "LP_only_stable"
        <=>  skew_label = "DN_strict"
             ∧ atr_rank ≤ 0.70
             ∧ trend_rank ≥ 0.75
             ∧ transition_flag = False
    tier = "LP_only_trans"
        <=>  (LP_only conditions) ∧ transition_flag = True
    (LL_only / SP_only / SC_only / SL_only × stable/trans 类似 · 见 §7.1)

    -- 已删除嵌套关系不变量（v3.0 互斥类别不再有嵌套）
```

### 9.3 批量输出

对每个合约 `s`：

```text
Timeline_s := [ClassifierOutput(s, t) : t ∈ E_s, warmup_ok(s, t) = True]
```

保证按 `event_time` 升序 · 每个事件唯一。

## 10. 静态一致性检查

### 10.1 符号一致性

- `signed_skew_rank`（§5.1）与 `A3_skew`（§4.1）语义方向一致：rank ≤ 0.10 ⇔ A3_skew 底 10%
- `atr_rank / trend_rank`（§5.2/5.3）分别独立算 · **只在 t-1 时点评估** · 无同日互相依赖
- `transition_flag`（§6.4）只用 `atr_bucket_session` · 与 `trend` / `skew` 无关

### 10.2 时序单调性

- `E_s^prev(t, K)` 只包含 `idx(u) < idx(t)` · 严格历史
- `D_s^prev(t, N)` 只包含 `d' < d(t)` · 严格历史
- `daily_atr_10_bps(s, d(t)-1)` 使用前一 session（阶段 3 洞察 R 明确 t 时刻已知）

### 10.3 触发条件完全互斥性

- **所有 10 tier 两两不相交**：
  `∀ T_i, T_j ∈ Tiers, i ≠ j : T_i ∩ T_j = ∅`
- **并集是「可分类事件全集」**：
  `⋃ Tiers = { (s, t) : warmup_ok(s, t) ∧ tier(s, t) ≠ None }`
- 互斥来源：
  - skew 方向严格互斥（DN_strict / DN_loose vs UP · §6.1）
  - 空头 3 类 atr_rank 区间不重叠（(0.50, 0.67] / (0.67, 0.80] / (0.80, ∞) · §7.1）
  - stable / trans 由 `transition_flag ∈ {0, 1}` 二分（§7.2）

### 10.4 Warmup 不变量

- warmup 未满足 → 所有 tier 为空 · transition_flag None（§9.2）
- warmup 满足 → transition_flag 一定有明确布尔值

### 10.5 参数固定值汇总

| 参数 | 值 | 来源 |
|------|-----|-----|
| `Δbar_profile` | 5m | KF-02 · 阶段 1 |
| `Δbar_trade` | 1h | KF-09 · 阶段 2 |
| `n_rolling_events` | 100 | KF-07 · 洞察 K |
| `n_rolling_days` | 20 | KF-06 · 洞察 I |
| `n_warmup_days` | 20 | 阶段 2 严格无未来函数版本 |
| `n_transition_window_days` | 3 | 洞察 R · 阶段 3 §6 |
| `skew_thresholds` | {0.10, 0.30, 0.70} | KF-12 · 洞察 N |
| `atr_thresholds` | {0.33, 0.50, 0.67, 0.70, 0.80} | 洞察 N/P/Q |
| `trend_thresholds` | {0.20, 0.33, 0.67, 0.75} | 洞察 N |

### 10.6 已知边界（数学层面）

- **单值输出 · 完全互斥**：`tier ∈ Tiers ∪ {None}` · `|Tiers| = 10` · 两两不相交（§10.3）
- **stable/trans 拆分**：`M_stable ∩ M_trans = ∅` · `M_stable ∪ M_trans = M`（对任意基础类 M）
- **warmup 硬边界**：`warmup_ok = False` ⇒ `tier = None` ∧ `transition_flag = None`
- **transition_flag 滞后**：依赖 `atr_bucket_session` 的日级切换 · 同日 atr rank
  计算延迟不引入 leakage（因用 `d(t) - 1` 的 daily 值）

**参数选择相关的使用限制、扩样本建议、机制假说**等非契约内容
详见 [parameter-selection-spec.md §5](parameter-selection-spec.md)。

## 11. 版本控制与阶段 4 引用

### 11.1 冻结承诺

**本文件 v1 冻结后**：
- 所有阈值参数（skew/atr/trend/rolling）不再改动
- 若阶段 4 或后续实验发现需要调整 · 必须先修订本文件 · 再更新代码
- 修订需要 workbench 附录说明变更理由

### 11.2 阶段 4 引用方式

阶段 4 的 `strategy-math-spec.md` 通过 `import` 语义引用 · v3.0 输出单值 tier ·
分支采用相等判断：

```text
Classifier := as defined in classifier-math-spec.md v3.0

Strategy(s, t) :=
    tier := Classifier(s, t).tier            -- 单值 · str | None
    if tier == "LL_only_stable":
        entry := EntryFunc_LL_only_stable(s, t, ...)
        exit  := ExitFunc_LL_only_stable(s, t, ...)
    elif tier == "SP_only_trans":
        ...
    elif tier is None:
        skip                                  -- 未分类 · 不进场
    ... (其他互斥 tier)
```

分类器规格不重复写入 strategy-math-spec.md · 保证 single source of truth。

### 11.3 参数选择与阶段 4 使用建议（外部引用）

**分类器契约（本文件）不承载**：
- 参数选择的评级判据
- 单个 tier 的性能指标（mean / IR / Sharpe / hit / 品种保留率）
- 机制假说与经济解读
- 阶段 4 落地的组合建议
- 分位×制度未来细化候选（KF-23 · 12 格地图）

以上内容全部见 [parameter-selection-spec.md](parameter-selection-spec.md)：

- §1 · 一眼可读总览（A/B/C 白名单 + 12 格候选）
- §2 · 10 档评级卡（每 tier 单独一节 · 含机制假说）
- §3 · 12 格分位×制度地图（KF-23）
- §4 · 阶段 4 使用建议（起点组合 / 出场策略 / 仓位管理）
- §5 · 已知边界与阶段 4 必做验证

## 附录 A · 与阶段 3 workbench 的对应关系

| 本文件章节 | Workbench 位置 |
|---------|------------|
| §3 W1 profile | 阶段 1 workbench §3 · KF-02 |
| §4 A3_skew | 阶段 1 workbench §4 · KF-01/03 |
| §5.1 signed_skew_rank | 阶段 1 workbench §10 · KF-07（洞察 K）|
| §5.2/5.3 rank | 阶段 2 workbench §2 · KF-14 |
| §6.2 3-way ATR | 阶段 3 workbench §2 · KF-16（洞察 P）|
| §6.4 transition_flag | 阶段 3 workbench §6 · KF-18（洞察 R）|
| §7 触发条件 | 阶段 2 workbench §7.10 + 阶段 3 workbench §12.9 |
| §7.3 评级 | 阶段 3 workbench §12.9 |

## 附录 B · 数据源要求

分类器计算的必需数据源（阶段 4 代码实现时对齐）：

- **5m bar**：`project_data/bars_5m/{contract}.parquet` · 至少覆盖 `n_warmup_days + n_rolling_events + 目标区间`
- **日线 bar**：从 5m bar 聚合 · 或用 `project_data/bars_1d/{contract}.parquet`
- **合约规格**：`workspace/common/contract_specs.py` · 提供 `price_tick` · `session_close_time`

## 附录 C · 阶段 4 建议实现结构

```
workspace/common/poc_va_classifier.py
├── class POCVAClassifier
│   ├── __init__(config: ClassifierConfig)
│   ├── build_profile(contract, session) -> ProfileData
│   ├── compute_a3_skew(profile) -> float
│   ├── evaluate_event(contract, event_time) -> ClassifierOutput
│   │       # ClassifierOutput.tier: Literal[
│   │       #   "LP_only_stable", "LP_only_trans",
│   │       #   "LL_only_stable", "LL_only_trans",
│   │       #   "SP_only_stable", "SP_only_trans",
│   │       #   "SC_only_stable", "SC_only_trans",
│   │       #   "SL_only_stable", "SL_only_trans"
│   │       # ] | None
│   │       # 单值互斥输出 · 见 §9
│   └── generate_timeline(contract, start, end) -> List[ClassifierOutput]
└── class ClassifierConfig
    ├── skew_thresholds, atr_thresholds, trend_thresholds
    ├── n_rolling_events, n_rolling_days, n_warmup_days
    └── n_transition_window_days
```

**默认 config** = §10.5 参数汇总表的 v1 冻结值。
