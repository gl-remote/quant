# poc-value-area-asymmetry · 分类器数学规格

> 类型：Theme / 分类器数学规格（数学契约唯一源）
> 状态：**v4.0（2026-07-08）· 阶段 4 v9.1 收尾 · 6 类合并版冻结 · KF-29 定型**
> 主题 README：[README.md](README.md)
> 参数选择与性能报告：`parameter-selection-spec.md`（阶段 4 完成后重建）
> 研究状态：[research-status.md](research-status.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)

## 1. 目标与契约边界

### 1.1 分类器契约

**本文件是"POC value area 不对称背景分类器"的数学定义唯一源**。任何策略
若使用本分类器输出的标签，其**计算方式**由本文件规格决定，**具体参数值**由
`parameter-selection-spec.md` 决定。

### 1.2 本文件承载

- ✅ Bar 结构 · 事件时钟 · profile 构建 · A3_skew 度量的**数学定义**
- ✅ rank 计算方式（`signed_skew_rank` · `atr_rank` · `trend_rank`）
- ✅ 中间标签的**结构定义**（用符号化阈值）
- ✅ Tier 集合的**结构定义**（tier ID · 互斥性约束）
- ✅ Warmup 边界 · Leakage 约束 · 输出 API
- ✅ 静态一致性检查

### 1.3 本文件不承载

- ❌ **具体阈值数值**（skew / atr / trend 分位边界）· 全部在 `parameter-selection-spec.md`
- ❌ Tier 的性能指标（mean / IR / hit / 品种保留率）
- ❌ 白名单分级（A / A- / 未过）
- ❌ 机制假说 / 经济解读 / 使用建议
- ❌ 入场规则 · 出场规则 · 仓位管理 · 账户闸门 · 交易成本

以上属于完整策略层面，若阶段 4 通过则写入 `strategy-math-spec.md` 并显式
引用本分类器规格。

### 1.4 分类器输出承诺

对每个事件时刻 `t`（每小时整点）· 每个合约 `s` · 分类器输出：

```text
Classifier(s, t) := (
  skew_label,           -- 偏度分类
  atr_regime,           -- 波动率制度
  trend_regime,         -- 趋势制度
  transition_flag,      -- regime 转换标记
  tier: str | None,     -- 单值互斥 tier (完整列表见 §7.3)
  meta,                 -- 完整原始数值 (见 §9)
)
```

**互斥性**：每个 event 属于且仅属于一个 tier · 或未分类（`tier = None`）。

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
E := { t ∈ I_all | Δbar_trade divides time(t) }
```

即所有 wall-clock 分钟位为 `:00:00` 的 bar 索引集合（1h 事件时钟）。

阶段 2 洞察 O 已验证跨周期一致（15m/30m/1h/2h 全过）· 本规格锁定 1h 为主
分类器时钟。若阶段 4 或后续需要 4h 时钟 · 另行分档。

### 2.4 量纲约定

```text
bar-count 量纲(idx(·)):     n_rolling_events, n_rolling_days, n_warmup_days
wall-clock 量纲(time(·)):   event_time
rank 量纲 (无量纲 [0, 1]):   signed_skew_rank, atr_rank, trend_rank
bps 量纲 (1e4 · log return): mean, CI, hit-weighted return
```

## 3. Profile 构建（W1 · 前一交易日）

### 3.1 Profile 窗口

阶段 1 洞察 D 已锁定 W1 = 前一交易日整体 profile · W2/W3/前 N 天窗口一律
排除。

```text
W1(t) := { i ∈ I_all | i ∈ I_{d-1(t)}, Δbar(i) = Δbar_profile }
```

即：**t 时刻所在 session 的前一个 session 的所有 5m bar**。

### 3.2 Volume Profile 构造

采用 close-based bucketing（阶段 1 洞察 A 已锁定）：

```text
τ          := price_tick (合约特定 · 由 workspace/common/contract_specs.py 提供)
G_τ        := { n · τ | n ∈ ℤ }                    -- tick 网格
bucket(p)  := round_τ(p)                            -- 就近舍入到 tick

Π_W1(p; t) := Σ_{i ∈ W1(t)} V_i · 1[ bucket(C_i) = p ],  p ∈ G_τ
```

### 3.3 POC 与 Value Area（辅助 · 不用于分类器主输入）

```text
POC_W1(t) := argmin_{p ∈ M_W1(t)} |p - C_{last(W1(t))}|
    where M_W1(t) := { p ∈ G_τ | Π_W1(p; t) = max_{u ∈ G_τ} Π_W1(u; t) }
```

**注**：POC/VA 定义仅供参考。本分类器实际使用的度量是 A3_skew（§4）·
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
在 t 时刻取值时完全无当日信息。

## 5. Rolling Rank 分位定义

### 5.1 Signed Skew Rank

对每个合约 `s` 独立维护 `A3_skew` 事件序列 · rolling K 事件分位（`K` 由
`parameter-selection-spec.md` 配置）：

```text
E_s(t)         := { u ∈ E | s(u) = s, idx(u) < idx(t) }
E_s^prev(t, K) := { u ∈ E_s(t) | idx(u) 属于前 K 个事件 }

signed_skew_rank(s, t) :=
    (1 / |E_s^prev(t, K)|) · Σ_{u ∈ E_s^prev(t, K)} 1[ A3_skew(u) < A3_skew(t) ]
```

**范围**：`signed_skew_rank ∈ [0, 1]`（严格小于计数 · tie-break 见下）。

**语义**：
- rank ≈ 0 → A3_skew 是过去 K 事件里的最低值（极端左偏 / 底厚）
- rank ≈ 1 → A3_skew 是过去 K 事件里的最高值（极端右偏 / 顶厚）

**Tie-break**：使用严格小于计数 · 见公式定义（等值不加分）。

### 5.1a 独立采样单位与冻结约束（KF-22）

**表面 vs 实际**：
- **表面**：rolling K events 每合约的观察数为 K
- **实际**：`A3_skew` 是**日级变量**（同一交易日所有 event 共享 W1 · 因此
  A3_skew 相同）· 独立采样单位是 (合约, 日期) · K events ≈ K / (每日事件数)
  独立日

**冻结约束**（stage 3 workbench §12.12 论证）：
- **rank 单位固定为 per-contract**：禁止跨合约池化（品种前缀 / 交易所 / 全池）
- **禁止贝叶斯 shrinkage**：即使把其他合约作为先验也会破坏尾部信号
- **Bootstrap 单位**：必须按 (contract, date) cluster · 而非 (contract)
- **表述规范**：报告样本量时应同时给出 event 数和独立日数

**核心原则**："数据边界不可造假 · 承认样本量 · 用正确 bootstrap 揭露真实
不确定性 · 不用池化 / shrinkage 制造虚假显著性"（KF-poc-va-22 · 跨主题方法论）。

### 5.2 ATR Rank

Rolling `N` 交易日的日线 ATR_L 分位（`N` 与 `L` 由 `parameter-selection-spec.md`
配置）：

```text
D_s(t)         := { d' ∈ Trading_Sessions | s available on d', d' < d(t) }
D_s^prev(t, N) := { d' ∈ D_s(t) | d' 属于前 N 个 session }

TR_s(d) := max(H_s(d) - L_s(d),
                |H_s(d) - C_s(d-1)|,
                |L_s(d) - C_s(d-1)|)                 -- 要求 d ≥ d_start(s) + 1

daily_atr_L_bps(s, d) := (1e4 / C_s(d)) · (1/L) · Σ_{i=d-L+1}^{d} TR_s(i)
                                                     -- 要求 d ≥ d_start(s) + L

atr_rank(s, t) :=
    |{ d' ∈ D_s^prev(t, N) | daily_atr_L_bps(s, d') < daily_atr_L_bps(s, d(t)-1) }|
    / |D_s^prev(t, N)|
```

**范围**：`atr_rank ∈ [0, 1]`。

**注**：`daily_atr_L_bps(s, d(t)-1)` 使用前一交易日的 ATR 值 · 无未来函数。

### 5.3 Trend Rank

Rolling `N` 交易日的近 `M` 日累计 log return 分位（`N` 与 `M` 由
`parameter-selection-spec.md` 配置）：

```text
trend_ret_M(s, d) := log(C_s(d) / C_s(d - M + 1))

trend_rank(s, t) :=
    |{ d' ∈ D_s^prev(t, N) | trend_ret_M(s, d') < trend_ret_M(s, d(t)-1) }|
    / |D_s^prev(t, N)|
```

**范围**：`trend_rank ∈ [0, 1]`。

**语义**：
- rank ≈ 0 → 近 M 日累计跌幅是过去 N 日最深（跌段）
- rank ≈ 1 → 近 M 日累计涨幅是过去 N 日最强（涨段）

### 5.4 Warmup 约束

Warmup 天数 `n_warmup_days`（由 `parameter-selection-spec.md` 配置）·
事件 `t` 有效 iff（`warmup_ok(s, t) = True`）：

```text
|E_s^prev(t, K)| ≥ K                      -- 至少 K 个历史事件
∧ |D_s^prev(t, N)| ≥ N                    -- 至少 N 个历史 session
∧ d(t) ≥ d_start(s) + n_warmup_days        -- warmup 期过后
∧ ∀ d' ∈ D_s^prev(t, N):
      TR_s(d') 与 daily_atr_L_bps(s, d') 均可定义
```

否则 `Classifier(s, t)` 输出 `warmup_ok = False` · `tier = None` ·
`transition_flag = None`。

## 6. 分类器中间标签（结构化定义）

**说明**：本节定义中间标签的**分档结构** · 具体阈值（`θ_*`）由
`parameter-selection-spec.md` 配置。

### 6.1 Skew Label

Signed skew rank 分档为 K_skew 个互斥类别：

```text
skew_label(s, t) := 由 signed_skew_rank(s, t) 通过阈值配置 Θ_skew 分档得到
                    分档结构必须满足：
                    - 若配置为二侧对称 · 返回 {DN_*, ..., NEUTRAL, UP_*, ...}
                    - 所有类别两两互斥 · 并集覆盖 [0, 1]
```

**语义方向约定**：
- `DN_*` 类别对应 `signed_skew_rank` 靠近 0（底厚 · A3_skew < 0）
- `UP_*` 类别对应 `signed_skew_rank` 靠近 1（顶厚 · A3_skew > 0）
- `NEUTRAL` 类别对应中间区间（不进入分类器输出）

**具体分档配置**：见 `parameter-selection-spec.md §2`。

### 6.2 ATR Regime

`atr_rank` 分档为 K_atr 个互斥类别（默认 3-way · 阶段 3 洞察 P 定义）：

```text
atr_regime(s, t) := 由 atr_rank(s, t) 通过阈值配置 Θ_atr 分档得到
                    互斥性同 §6.1
```

**语义方向约定**：类别命名如 `"low"` / `"mid"` / `"high"` · 对应
`atr_rank` 从小到大。

**具体分档配置**：见 `parameter-selection-spec.md §2`。

### 6.3 Trend Regime

`trend_rank` 分档为 K_trend 个互斥类别（默认 3-way · 阶段 4 加入平稳期
探索）：

```text
trend_regime(s, t) := 由 trend_rank(s, t) 通过阈值配置 Θ_trend 分档得到
                     互斥性同 §6.1
```

**语义方向约定**：类别命名如 `"down"` / `"flat"` / `"up"` · 对应
`trend_rank` 从小到大。

**具体分档配置**：见 `parameter-selection-spec.md §2`。

### 6.4 Transition Flag

Regime transition 定义（阶段 3 洞察 R）· `atr_bucket_session` 用于日级
ATR 制度识别：

```text
-- Session 级 ATR 分档（区别于 event 级 atr_regime · 用 daily bar 计算）
atr_bucket_session(s, d) := 由 atr_rank_session(s, d) 通过阈值 Θ_atr_session 分档
                            (通常与 §6.2 相同 · 但可独立配置)

-- 前一同合约 session
prev_session(s, d) := max { d' ∈ D_s(·) | d' < d }

-- 制度切换判定
is_crossover(s, d) :=
    prev_session(s, d) exists
    ∧ atr_bucket_session(s, d) ≠ atr_bucket_session(s, prev_session(s, d))

-- Transition flag · 转换窗口天数 n_transition_window_days 由 parameter-selection 配置
transition_flag(s, t) :=
    1[ ∃ d' ∈ Trading_Sessions_of_s :
         d' ≤ d(t) ∧ d(t) - d' < n_transition_window_days
         ∧ is_crossover(s, d') = True ]
```

**语义**：
- `transition_flag = 1` → t 时刻处于 regime 转换期（前若干交易日 atr 制度切换）
- `transition_flag = 0` → t 时刻处于 regime 稳定期

**注**：`d(t) - d'` 用 session 计数（不含周末停牌）· 沿用 §2.1 语义。

## 7. 触发条件与 Tier 集合（结构定义）

### 7.1 Tier 结构

每个 tier 由**中间标签的组合值**唯一定义：

```text
Tier ≡ (skew_label 取值, atr_regime 取值, trend_regime 取值, transition_flag 取值)
```

或省略某些维度（表示"对该维度不设约束"）。

**分类器契约要求**：
- **完全互斥**：`∀ Tier_i ≠ Tier_j : Tier_i ∩ Tier_j = ∅`
- **可分类事件全集**：`⋃ Tiers = { (s, t) : warmup_ok ∧ 命中某个 tier }`
- **未分类事件**：不命中任何 tier · 分类器返回 `tier = None`

**具体 tier 集合与命名**：见 `parameter-selection-spec.md §3`（每个版本可能
不同 · v3.0 定义了 10 个 tier · v4.0 计划扩展为分位×制度×趋势的更细粒度）。

### 7.2 Tier ID 命名规范

Tier ID 采用**结构化命名**：

```text
<direction>_<detail>_<regime>[_stable|_trans|_full]

例：
  LP_only_stable    -- 多头首选 · 稳定期
  SP_only_trans     -- 空头首选 · 转换期
  LL_only_full      -- 多头宽档 · 全期别（stable ∪ trans 的报告口径）
```

`_full` 表示不区分 stable/trans（是 stable ∪ trans 的并集报告口径 · **不是
独立 tier** · 只在性能报告中使用）。

### 7.3 Tier 集合的当前版本引用

- **v3.0 tier 集合**（10 互斥 tier · 阶段 4 v3 过渡版）：见 `parameter-selection-spec.md §3.1`（保留作诊断证据）
- **v4.0 tier 集合**（6 类合并版 · 阶段 4 v9.1 收尾冻结）：见 `parameter-selection-spec.md §3.2`
  - 决策依据：144 tier 精细化通过率仅 20% · 稀疏率 91% · 合并 6 类后通过率 83%（KF-29）
  - 6 类：L_seg3_lowmid_up / L_seg12_high_up / L_seg2_low_flat / S_seg12_high_dn / S_seg34_high_dn / S_seg2_mid_dn

### 7.4 白名单

**评级判据**（Bonferroni + 反事实 + CI + 时稳）· 分级为 A / A- / 未过 ·
详见 `parameter-selection-spec.md §4-5`。

## 8. 严格无未来函数约束（Leakage Boundary）

### 8.1 数据边界

对每个 `Classifier(s, t)` 输出 · 所有输入数据严格来自 t 之前：

```text
Data_inputs(s, t) := {
    W1(t),                     -- 前一交易日 5m bar (完全在 t 之前)
    E_s^prev(t, K),            -- 前 K 个事件的 A3_skew 值
    D_s^prev(t, N),            -- 前 N 个 session 的 daily 特征
}
```

### 8.2 时序保证

```text
∀ (s, t) with tier(s, t) ≠ None:
    max { time(u) : u ∈ Data_inputs(s, t) } < time(t)
```

即：分类器输出在 `time(t)` 时刻可用 · 不需要 t 之后的信息。

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
    daily_atr_L_bps: float ≥ 0 | NaN
    atr_rank: float ∈ [0, 1] | NaN
    trend_ret_M: float | NaN
    trend_rank: float ∈ [0, 1] | NaN

    -- 中间标签
    skew_label: str | None         -- §6.1 · None if warmup 未过
    atr_regime: str | None         -- §6.2
    trend_regime: str | None       -- §6.3

    -- Regime transition
    atr_bucket_current: str | None
    atr_bucket_prev: str | None
    is_crossover_today: bool | None
    transition_flag: bool | None    -- None if warmup 不足

    -- 分类结果（v3.0 及以后 · 单值 tier · 互斥）
    tier: str | None                -- tier ID (见 §7.2 命名) 或 None (未分类)

    -- Warmup 状态
    warmup_ok: bool
}
```

### 9.2 输出不变量

```text
∀ output:
    warmup_ok = False  =>  tier = None ∧ transition_flag = None
    warmup_ok = True   =>  transition_flag ∈ {True, False}

    tier ≠ None       =>  (skew_label, atr_regime, trend_regime, transition_flag)
                          唯一决定该 tier ID

    tier = None       =>  或未命中任何 tier · 或 warmup 未过
```

**互斥性**：一个 event 属于且仅属于一个 tier（或 None）。

### 9.3 批量输出

对每个合约 `s`：

```text
Timeline_s := [ClassifierOutput(s, t) : t ∈ E_s, warmup_ok(s, t) = True]
```

保证按 `event_time` 升序 · 每个事件唯一。

## 10. 静态一致性检查

### 10.1 符号一致性

- `signed_skew_rank`（§5.1）与 `A3_skew`（§4.1）语义方向一致：rank 靠近 0
  ⇔ A3_skew 靠近其分布最低值
- `atr_rank / trend_rank`（§5.2/5.3）分别独立算 · 只在 `t-1` 时点评估 ·
  无同日互相依赖
- `transition_flag`（§6.4）只用 `atr_bucket_session` · 与 `trend` / `skew`
  无关

### 10.2 时序单调性

- `E_s^prev(t, K)` 只包含 `idx(u) < idx(t)` · 严格历史
- `D_s^prev(t, N)` 只包含 `d' < d(t)` · 严格历史
- `daily_atr_L_bps(s, d(t)-1)` 使用前一 session（无 leakage）

### 10.3 触发条件完全互斥性

- **所有 tier 两两不相交**：`∀ T_i, T_j ∈ Tiers, i ≠ j : T_i ∩ T_j = ∅`
- **并集是「可分类事件全集」**：`⋃ Tiers = { (s, t) : warmup_ok ∧ tier ≠ None }`
- 互斥性由 §6 中间标签的**互斥分档**+ §7.1 的**组合值分类**共同保证：
  - `skew_label` / `atr_regime` / `trend_regime` 各自内部互斥（§6）
  - tier 定义为中间标签组合值 · 天然互斥（§7.1）

### 10.4 Warmup 不变量

- warmup 未满足 → `tier = None` ∧ `transition_flag = None`
- warmup 满足 → `transition_flag ∈ {True, False}` · `tier ∈ Tiers ∪ {None}`

### 10.5 参数占位符汇总

**说明**：本 spec 只承载计算方式 · 所有可调参数的**具体数值**由
`parameter-selection-spec.md` 配置。以下是参数占位符清单：

| 参数占位符 | 语义 | 配置位置 |
|-----------|------|---------|
| `Δbar_profile` | Profile 构建 bar 周期 | `parameter-selection-spec.md §1` |
| `Δbar_trade` | 事件时钟 bar 周期 | 同上 |
| `Δbar_daily` | 日线特征 bar 周期 | 同上 |
| `K = n_rolling_events` | Rolling 事件窗口大小 | 同上 |
| `N = n_rolling_days` | Rolling 日窗口大小 | 同上 |
| `L = n_atr_lookback` | ATR 平均窗口 | 同上 |
| `M = n_trend_lookback` | Trend 累计窗口 | 同上 |
| `n_warmup_days` | Warmup 天数 | 同上 |
| `n_transition_window_days` | Transition 窗口 | 同上 |
| `Θ_skew` | Skew 分档阈值 | `parameter-selection-spec.md §2.1` |
| `Θ_atr` | ATR 分档阈值 | `parameter-selection-spec.md §2.2` |
| `Θ_trend` | Trend 分档阈值 | `parameter-selection-spec.md §2.3` |
| `Θ_atr_session` | Session 级 ATR 分档阈值 | `parameter-selection-spec.md §2.4` |
| Tier 集合 | 具体 tier 定义与命名 | `parameter-selection-spec.md §3` |
| Tier 白名单 | A/A- 级分级 | `parameter-selection-spec.md §4` |

### 10.6 已知边界（数学层面）

- **单值输出 · 完全互斥**：`tier ∈ Tiers ∪ {None}` · Tiers 内两两不相交（§10.3）
- **warmup 硬边界**：`warmup_ok = False` ⇒ `tier = None` ∧ `transition_flag = None`
- **transition_flag 滞后**：依赖 `atr_bucket_session` 的日级切换 · 同日 atr
  rank 计算延迟不引入 leakage（因用 `d(t) - 1` 的 daily 值）

**参数选择、性能指标、机制假说、使用限制**等非契约内容详见
`parameter-selection-spec.md`。

## 11. 版本控制与阶段引用

### 11.1 版本管理

**Spec 本身的版本**（本文件）：
- v3.1 · 结构化重构 · 数学定义与参数分离
- 数学计算方式如需修订（例如 A3_skew 定义、rank 公式）· spec 需升版

**参数配置的版本**（`parameter-selection-spec.md`）：
- v3.0 · 10 互斥 tier · skew 3 档 × atr 3 档 × trend 2 档
- v4.0 计划 · 分位×制度×趋势细化 · trend 加入 flat 档
- 参数配置更新 · 不影响本 spec

### 11.2 下游引用方式

下游策略（`strategy-math-spec.md`）通过 `import` 语义引用：

```text
Classifier := as defined in classifier-math-spec.md v3.x
              with parameter config from parameter-selection-spec.md v3.x

Strategy(s, t) :=
    tier := Classifier(s, t).tier            -- 单值 · str | None
    if tier == "LL_only_stable":
        entry := EntryFunc_LL_only_stable(s, t, ...)
        exit  := ExitFunc_LL_only_stable(s, t, ...)
    elif tier == "SP_only_trans":
        ...
    elif tier is None:
        skip                                  -- 未分类 · 不进场
    ...
```

## 附录 A · 与阶段 workbench 的对应关系

| 本文件章节 | Workbench 位置 |
|---------|------------|
| §3 W1 profile | 阶段 1 workbench §3 · KF-02 |
| §4 A3_skew | 阶段 1 workbench §4 · KF-01/03 |
| §5.1 signed_skew_rank | 阶段 1 workbench §10 · KF-07（洞察 K）|
| §5.1a 冻结约束 KF-22 | 阶段 3 workbench §12.12 |
| §5.2/5.3 rank | 阶段 2 workbench §2 · KF-14 |
| §6.2 ATR regime | 阶段 3 workbench §2 · KF-16（洞察 P）|
| §6.4 transition_flag | 阶段 3 workbench §6 · KF-18（洞察 R）|
| §7 tier 结构 | 阶段 4 workbench（待建） |
| §10.3 互斥性 | 阶段 4 workbench（待建） |

## 附录 B · 数据源要求

分类器计算的必需数据源（阶段 4 代码实现时对齐）：

- **5m bar**：`project_data/bars_5m/{contract}.parquet` · 至少覆盖
  `n_warmup_days + K + 目标区间`
- **日线 bar**：从 5m bar 聚合 · 或用 `project_data/bars_1d/{contract}.parquet`
- **合约规格**：`workspace/common/contract_specs.py` · 提供 `price_tick` ·
  `session_close_time`

## 附录 C · 阶段 4 建议实现结构

```
workspace/strategies/classifiers/poc_va.py
├── class POCVAClassifier
│   ├── __init__(config: ClassifierConfig)
│   ├── build_profile(contract, session) -> ProfileData
│   ├── compute_a3_skew(profile) -> float
│   ├── compute_ranks(...) -> RankValues
│   ├── evaluate_event(contract, event_time) -> ClassifierOutput
│   └── generate_timeline(contract, start, end) -> List[ClassifierOutput]
└── class ClassifierConfig
    -- 从 parameter-selection-spec.md 加载所有 Θ_* 阈值与 K/N/L/M 参数
    ├── skew_thresholds, atr_thresholds, trend_thresholds
    ├── n_rolling_events, n_rolling_days, n_warmup_days
    ├── n_atr_lookback, n_trend_lookback
    └── n_transition_window_days
```

**config 默认值**：来源于 `parameter-selection-spec.md` 当前版本冻结值。
