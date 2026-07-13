# va-asymmetry · 未来信息泄漏铁证报告

> 主题：`va-asymmetry-composite`
> 日期：2026-07-13
> 结论：**原研究侧 63% 年化 / 夏普 3.47 的表现，来自 daily 特征在事件触发时使用了当日 event_time 之后的 5m bars 数据。策略假设无独立 alpha。**

## 一、问题背景

`va-asymmetry-composite` 归档 metrics 显示：K_L=1.0 / K_S=2.5 / ATR=SMA(10) / Cap=4.0
参数组 5m 粒度全量回测，年化 +63.44%、夏普 3.47、613 笔交易。工程侧 5m 实盘化实现
（`workspace/strategies/va_asymmetry_composite_strategy.py`）无论如何对齐输入、分类器、
FIFO 配对与仓位链路，性能始终无法接近这一基线。差距 ≥15×，落地路径尝试穷尽后仍无解。

## 二、假设与验证方法

**假设**：分类器四输入之一 `A3_skew_spec` / `daily_atr_spec` / `trend_ret_M_spec` /
`close_session` 是**按自然日 merge 当日 daily 值**（在
[reproduce_research_side.py#L385](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/reproduce_research_side.py#L385)
的 `ev.merge(daily, left_on="event_date", right_on="date")`），
但 daily 值是当日 22:55 收盘后才能计算出的量。当事件在盘中触发（如 09:00 / 10:00 / 11:00）
时，daily 值需要**用到事件之后的当日 5m bars** —— 这是标准未来信息泄漏。

**四层独立证据链**：

### 证据 1：单事件级 68 根未来 bar 泄漏（脚本 [verify_leak_evidence_chain.py](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_evidence_chain.py)）

事件：SHFE.rb2501, event_time = 2024-10-14 09:00:00（早盘开盘第一小时）
当日自然日 bars 总数：69 根

| bars.datetime 与 event_time 的关系 | bar 数 |
|---|---|
| < event_time（事件前已知） | 0 |
| == event_time（事件同 bar） | 1 |
| **> event_time（未来，事件时未发生）** | **68** ← 泄漏源 |

泄漏 bar 覆盖当日 22:35 / 22:40 / 22:45 / 22:50 / 22:55 等夜盘收盘阶段的 close/volume，
参与了当日 `A3_skew_spec` (VW-skew) 与 `daily_atr_spec` (SMA10 ATR 的最新一根 TR) 的计算。

### 证据 2：4 个分类器字段值在泄漏版 vs 因果版数值完全不同（同事件）

| 字段 | 泄漏版（merge 当日值） | 因果版（shift-1，即用前一交易日值） |
|---|---|---|
| A3_skew_spec | 0.161675 | 0.927829 ← 符号级差异 |
| daily_atr_spec | 131.10 | 128.60 |
| trend_ret_M_spec | 0.117424 | 0.124160 |
| close_session | 3484（22:55） | 3520（前日收） |

**信息边界交叉验证**：`build_events` 里作者显式用 `prev_day_bars` 计算的合法 `A3_skew`
（不带 `_spec` 后缀）在这个事件的值也是 **0.927829**，与 shift(1) 因果版的
`A3_skew_spec` 精确到小数点后 6 位完全相等 —— 证明 shift(1) 修复的信息边界就是研究侧
已经写合法的边界。

### 证据 3：夜盘边界（shift(1) 是否过头）

周五夜盘事件 2024-10-11 21:00 检验：
- 当日 bars 共 69 根，事件之前已知 46 根（含白天 09:00~15:00 全 45 根），未来 23 根（21:05~23:00）；
- 「merge 当日」→ 仍泄漏 23 根 bar；
- shift(1) 用前一交易日全日 → 扔掉了白天已知的 45 根合法 bars，属**保守修法**（零泄漏）。

若追求最小信息损失，应改为**事件级精确截断**（仅取 `bars.datetime < event_time` 的 bars 参与 daily 聚合），但该口径会让 daily 特征变成事件级非稳定值，需重构管道。

### 证据 4：截断法 —— 因果性判据最直接的验证（脚本 [verify_leak_by_truncation.py](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py)）

**方法**：同一份**泄漏版**代码，喂两份数据，比较单事件分类结果。
- 全量数据：完整 CSV → daily 聚合到 event_date；
- 截断数据：CSV 仅保留 `datetime <= event_time` → daily 聚合。

**结果**（15 个抽样事件，来自 trades.parquet 的 top5 盈利 / bottom5 亏损 / 中位 5）：

| 差异维度 | 差异事件数 | 占比 |
|---|---|---|
| A3_skew_spec 值不同 | 7/15 | 47% |
| **r_s 归一化值不同** | **15/15** | **100%** |
| tier 分类不同 | 3/15 | 20% |
| **direction 交易方向不同** | **3/15** | **20%** |

**方向反转案例**：

| 事件 | 全量泄漏版 direction | 截断诚实版 direction |
|---|---|---|
| DCE.cs2405 @ 2024-03-01 11:00 | 无信号（tier=None） | long |
| DCE.c2505 @ 2025-02-13 09:00 | long | 无信号 |
| CZCE.TA509 @ 2025-07-18 21:00 | 无信号 | long |

单事件示例（DCE.cs2405 @ 2024-03-01 11:00）：
- 全量版 A3_skew_spec=0.236（用了 11:00 之后的 bars 后算出）→ r_s=0.410（不够极端）→ 未进阵营
- 截断版 A3_skew_spec=0.643（只用 09:00~11:00 的 bars）→ r_s=0.193（更极端）→ `L_seg3_lowmid_up` → long

**分类结果对「事件之后 bars 是否可见」敏感 → 用了未来信息**（因果性判据的定义）。

## 三、修复效果（对照）

在 [reproduce_research_side.py#L375-L386](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/reproduce_research_side.py#L375-L386)
merge 前对四个值列执行 `shift(1)`：

| 指标 | 泄漏版（原报告） | 因果修复版 |
|---|---|---|
| 交易笔数 | 613 | 1018 |
| 合约数 | ~140 | 142 |
| 年化收益 | **+63.44%** | **-38.25%** |
| 夏普 | **+3.47** | **-1.60** |

胜率、月度胜率、单笔 IR 全线转负 —— 原策略性能 100% 由泄漏贡献。

## 四、r_s 极端度是「怎么变成钱的」

泄漏让 `roll_t_pit(A3_skew_spec, window=10)` 归一化的 r_s 更容易压到极端：

| 指标（SHFE.rb2501 前 120 交易日） | 泄漏版 | 因果版 |
|---|---|---|
| `|r_s - 0.5|` 平均偏离度 | 0.2379 | 0.2308 |
| 极端占比（r_s<0.2 或 >0.8） | **32.0%** | 30.0% |

分类器阵营硬 cutoff（`L_seg3_lowmid_up`: r_s≥0.6, r_t≤0.2 等）
命中率随极端度上升，回测因而虚高。

## 五、代码定位

**研究侧**：[reproduce_research_side.py](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/reproduce_research_side.py)
第 385 行 `merge(daily, left_on="event_date", right_on="date")` 是泄漏源。
当前该文件已加入 shift(1) 修复（[#L375-L386](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/reproduce_research_side.py#L375-L386)）。

**工程侧**：[va_asymmetry_composite_strategy.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py)
`_precompute_va_daily_lookup` 函数（[#L415-L447](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L415-L447)）
同步 shift(1)，保证 lookup[今日] 返回昨日收盘后的值。

**分类器**：[poc_va.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/classifiers/poc_va.py)
本身无因果问题，已用 `git restore` 恢复到 HEAD 版本，研究/工程共用。

## 六、结论

1. **原策略假设无独立 alpha**：所有超额收益都能被因果修复清零；
2. **shift(1) 是保守修法**：将 daily 特征的信息边界拉齐到 `build_events` 中已合法的 `A3_skew` 字段（不带 _spec）的口径。未来若要挽回一部分信号质量，需重写为事件级精确截断（bars.datetime < event_time）；
3. **本报告的 4 层证据链完全独立于 [reproduce_research_side.py](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/reproduce_research_side.py) 输出**：验证脚本直接从原始 5m CSV 出发手工复现 daily 计算，避免了「用被测品检测被测品」的循环论证。

## 七、后续方向（不属于本报告的结论范围）

- 方向 A：把 `daily_atr_spec` / `trend_ret_M_spec` / `close_session` 也改为事件级精确截断，重跑因果基线；
- 方向 B：放弃 daily `_spec` 聚合，改用 `build_events` 里已经因果合法的 intraday 特征（`A3_skew` / `close_t` / `ret_8h` / `ret_4h`）重新设计分类器；
- 方向 C：接受 shift(1) 保守口径，先做 R/E 一致性收敛，再做参数重寻优。

## 附：验证脚本

- 4 层证据链（不依赖 reproduce 脚本输出）：[verify_leak_evidence_chain.py](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_evidence_chain.py)
- 截断法因果性判据：[verify_leak_by_truncation.py](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py)
- 研究侧全量回测（含 shift(1) 修复）：[reproduce_research_side.py](file:///Users/gaolei/Documents/src/quant/docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/reproduce_research_side.py)
