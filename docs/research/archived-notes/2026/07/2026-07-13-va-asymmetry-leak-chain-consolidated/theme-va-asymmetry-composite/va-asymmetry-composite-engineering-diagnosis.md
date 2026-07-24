# VA Asymmetry Composite 工程化问题诊断报告

**日期：** 2025-07-13  
**分支：** `fix/va-asymmetry-atr-source`  
**版本：** v1.0

---

## 1. 概述

| 问题 | 状态 |
|------|------|
| 工程侧无法运行 | **已解决** ← 当前分支 |
| 工程侧 vs 研究侧收益差距 15× | **待解决** ← 本报告主题 |

当前分支 `fix/va-asymmetry-atr-source` 解决了策略无法通过 CLI backtest 运行的问题（A 层分类从外部 parquet 依赖改为策略内部自算）。但工程侧回测结果（年化 ~4-12%）与研究侧全量回测结果（年化 63.44%，夏普 3.47）存在约 **15 倍** 差距。本报告详述两条路径的差异根因、复现脚本与数据流。

---

## 2. 分支改动清单（已解决问题）

本分支共改动 6 个文件，核心目标：**让策略不依赖外部 timeline parquet，直接通过 CLI backtest 运行。**

### 2.1 `va_asymmetry_composite_strategy.py`（388 行变更）

| 改动 | 说明 |
|------|------|
| 移除 `_load_a_table` / `_ensure_a_table` / `_resolve_atr_bps` / `_resolve_sigma_day` | 删除外部 parquet 查表逻辑 |
| 移除 `_DEFAULT_TIMELINE` 常量 | 删除硬编码 parquet 路径依赖 |
| 新增 `on_bar` 日线状态机 | 策略内部维护 `deque` 日线缓冲区，每根 1d bar 触发一次 t-PIT → tier 分类 |
| 入场逻辑迁移到 1m `on_bar` | 从 `event_time` 预知入场改为实时 `on_bar` 驱动，使用 `open_grace_min=5` 延迟入场 |
| 止损 ATR 来源修正（spec §7.1） | 从 1h RMA(10) Wilder's ATR 改为 A 层日线 SMA(10) ATR（`daily_atr_bps`） |

### 2.2 `strategy_aspects/indicators.py`

新增 `DAILY_ATR_BPS` 指标规范：`ATR(10)/close × 10000`，在 1d 周期上计算，供策略自算 A 层波动率基准。

### 2.3 `core/indicators.py`

新增 `daily_atr_bps_func`：封装 `talib.ATR` + `close` 归一化，产出 bps 量纲。

### 2.4 `runtime/period.py`

修复跨周期指标持久化：高周期（1d）结果索引与 base（1m）索引不对齐时，只把最新值写回 `current_time` 行，避免 IndexError。

### 2.5 `classifiers/poc_va.py`（3 处修复）

| 改动 | 说明 |
|------|------|
| MAD min_periods 稳健化 | `min_periods` 从 `window` 改为 `max(3, window//4)`，避免小数据集 MAD 全部 NaN |
| pandas 3.0 兼容 | `groupby.apply` 丢弃 group key 列后回填 `contract_col` |
| 默认窗口 20→10 | `ClassifierConfig` 的 `skew_rank_win` / `atr_rank_win` / `trend_win` 对齐 W=10 |

### 2.6 `.gitignore`

新增忽略项。

---

## 3. 工程侧复现路径

### 3.1 脚本

```bash
cd /Users/gaolei/Documents/src/quant
uv run python main.py backtest --mode single --strategy va_asymmetry_composite --symbol <品种>
```

### 3.2 数据流

```
1m bar (datafeed)
  │
  ├─ DataFeed 聚合 → 1d bar（日线 OHLC）
  ├─ 策略 on_bar(1d)：维护 deque 日线缓冲区
  │   ├─ volume_weighted_skew（1m → 5m 实时聚合）
  │   ├─ talib.ATR(10) / close × 10000  ← Wilder's 平滑（指数衰减权）
  │   └─ trend log_return(close, 10)
  ├─ t-PIT 归一化（W=10）→ r_s, r_a, r_t
  ├─ compute_transition_series → transition gate
  ├─ classify_tier → 六阵营
  │
  ├─ 策略 on_bar(1m)：每根 1m K 线决策
  │   ├─ 入场：open_grace_min=5 分钟后 bar.close 成交
  │   ├─ 止损 K_L=1.0 / K_S=1.75，1m 粒度逐 bar 检查
  │   ├─ 时间退出 H_L=8 / H_S=10，波动累积触发
  │   └─ Sizing：Risk × Equity / (K_SL × atr_bps/10000)
  │
  └─ 无日名义暴露 Cap（策略注释"组合级 Cap 属桥接层职责"）
```

### 3.3 关键参数

| 参数 | 值 |
|------|-----|
| K_L_SL | 1.0 |
| K_S_SL | **1.75** |
| H_L | 8 |
| H_S | 10 |
| ATR 公式 | **talib.ATR (Wilder's)** |
| 止损粒度 | **1m bar** |
| 日名义 Cap | **无** |
| 5m bar 来源 | 1m → 5m 实时聚合 |
| open_grace_min | 5 min |

---

## 4. 研究侧复现路径

### 4.1 脚本

```bash
cd /Users/gaolei/Documents/src/quant
uv run python docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/scripts/va_mad_fix_full_backtest.py
```

### 4.2 数据流

```
5m CSV (project_data/market_data/csv/*.tqsdk.5m.csv)
  │
  ├─ build_daily_features → 日线特征
  │   ├─ volume_weighted_skew（昨日 5m session 数据）
  │   ├─ daily_atr_sma（SMA(10)，等权移动平均）  ← SMA 非 Wilder's
  │   └─ trend_log_return(close, 10)
  ├─ build_events → 逐小时事件快照（event_time + close_t + A3_skew）
  ├─ build_coordinates → t-PIT 归一化
  ├─ evaluate_dataset → classify_tier → 六阵营事件
  │
  ├─ simulate_contract → 逐合约 5m 精确模拟
  │   ├─ 入场：事件时间点 bar.close 成交
  │   ├─ 止损 K_L=1.0 / K_S=2.5，5m 粒度检查
  │   ├─ 时间退出 H_L=8h / H_S=10h
  │   └─ Sizing：同上公式
  │
  └─ compress → max_notional=4.0（日名义暴露封顶）
```

### 4.3 关键参数

| 参数 | 值 |
|------|-----|
| K_L_SL | 1.0 |
| K_S_SL | **2.5** |
| H_L | 8 |
| H_S | 10 |
| ATR 公式 | **SMA(10)（等权）** |
| 止损粒度 | **5m bar** |
| 日名义 Cap | **max_notional=4.0** |
| 5m bar 来源 | 预制的交易所标准 5m CSV |
| EQUITY_INIT | 1,000,000 |
| RISK_PER_TRADE | 2% |

### 4.4 已有运行结果

结果存档于 `docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/`：

| 指标 | 研究侧（新版） |
|------|---------------|
| 年化收益 | **63.44%** |
| 夏普 | **3.47** |
| MaxDD | -12.30% |
| 胜率 | 62.8% |
| 月度胜率 | 81.2% |
| 单笔 IR | 0.271 |
| 交易笔数 | 613 |
| 覆盖合约 | 139 / 143 |
| 活跃交易日 | 590 |

---

## 5. 两条路径的 5 个关键差异

按预估影响权重排序：

### 差异 1：ATR 公式（影响权重 ★★★★★）

| | 研究侧 | 工程侧 |
|---|---|---|
| 实现 | `daily_atr_sma`: `TR.rolling(10).mean()` | `daily_atr_bps_func`: `talib.ATR(high,low,close,10)` |
| 平滑方式 | 等权移动平均 | Wilder's 指数衰减（α=1/10） |
| 对新信息的反应 | 逐日等权，滞后大 | 指数衰减，对近期更敏感 |

同一个品种同一天，SMA(10) ATR 和 Wilder's ATR(10) 可差 **10-20%**。这个差传导到 r_a 值 → tier 分类 → 直接影响开仓阵营甚至是否开仓。一个本应落入 L_seg2 的信号可能因此被分到 L_seg3 或 no_tier。

### 差异 2：空头止损乘数 K_S_SL（影响权重 ★★★★）

| | 研究侧 | 工程侧 |
|---|---|---|
| K_S_SL | 2.5 | 1.75 |

研究侧空头止损距离宽 43%（2.5 vs 1.75 ATR）。V 转行情中，研究路径的空单能扛住回调，生产路径却被扫出。这是空头侧盈亏差距的直接来源。

### 差异 3：日名义暴露封顶 Cap（影响权重 ★★★）

| | 研究侧 | 工程侧 |
|---|---|---|
| Cap | max_notional=4.0 | 无 |

研究侧 `max_notional=4.0` 意即单日名义暴露不超过 4×EQUITY_INIT（400 万）。当日多笔信号并发时，研究侧会等比缩量，避免集中度风险。生产侧无此控制，同日多信号全量入场，暴露出过量风险。

### 差异 4：止损检查粒度（影响权重 ★★）

| | 研究侧 | 工程侧 |
|---|---|---|
| 粒度 | 5m bar | 1m bar |

1m K 线对日内噪声更敏感，同一段行情中 1m 粒度可能触发假突破止损，而 5m 粒度不会。尤其对 S_seg 空头（K_S=1.75 已经偏窄），1m 粒度的误杀率更高。

### 差异 5：5m bar 来源（影响权重 ★）

| | 研究侧 | 工程侧 |
|---|---|---|
| 来源 | 预制的交易所标准 5m CSV | 1m bar 实时聚合 |
| 边界 | TQSdk 标准切片 | session 内拼接 |

bar 边界可能差 1-2 秒，影响 OHLC 极值，进而影响 volume_weighted_skew 的计算结果。但这个差异的量级远小于前 4 个。

---

## 6. 修复验证方案

要验证 5 个差异中哪些是根因，推荐分步对照实验：

### Step 1：统一 ATR 公式（预期影响最大）

在工程侧策略中，将 `daily_atr_bps_func` 的 `talib.ATR` 替换为 `SMA(TR, 10)`：

```python
# core/indicators.py 或策略内临时覆盖
def daily_atr_bps_sma(df, period=10):
    prev_close = df["close"].shift(1)
    tr = np.maximum.reduce([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ])
    atr = tr.rolling(period).mean()
    return atr / df["close"] * 10000
```

跑同一品种的回测对比，观察 tier 分类分布和盈亏变化。

### Step 2：统一 K_S_SL

将工程侧 `K_S_SL` 从 1.75 调至 2.5，与研究侧对齐。

### Step 3：加入日名义 Cap

在工程侧策略的 `on_bar(1m)` 入场逻辑中加入同日名义暴露累计 → 等比缩量逻辑。

### Step 4（可选）：止损粒度

如果前三步已大幅弥合差距，5m vs 1m 粒度差异可接受为工程化代价（1m 更保守）。

---

## 7. 附录：研究侧中间数据位置

| 文件 | 路径 |
|------|------|
| 分类事件（新版） | `docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/events_new.parquet` |
| 分类事件（旧版） | `docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/events_old.parquet` |
| 交易记录（新版） | `docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/trades_new.parquet` |
| 交易记录（旧版） | `docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/trades_old.parquet` |
| 指标 JSON（新版） | `docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/metrics_new.json` |
| 指标 JSON（旧版） | `docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/metrics_old.json` |
| 对比总结 | `docs/research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/summary.md` |
| 5m 行情数据 | `project_data/market_data/csv/*.tqsdk.5m.csv` |
