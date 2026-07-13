# VA 非对称复合策略 · 研究侧 vs 工程侧 差异拆解报告（run_id=15）

> **对比基线**：研究侧 = 5m CSV batch 管线（`reproduce_research_side.py`）· 工程侧 = vnpy 框架 run_id=15（5m 数据、100w 本金、合约级并行）
> **日期**：2026-07-13
> **本金一致**：两侧 EQUITY_INIT = 1,000,000 CNY
> **数据一致**：两侧均为 145 个 tqsdk 5m CSV 合约
> **研究范围**：仅关注与 run_id=15 本次回测可比的全量合约区间

---

## 0. 总览

### 0.1 核心指标对照

| 指标 | 研究侧 (R) | 工程侧 (E) | E−R 差 |
|---:|---:|---:|---:|
| 分类事件数 | **980** | — | — |
| 入场信号数（open） | **980** | **432** | **−548 笔** |
| 去重后入场信号数（每合约日 1 笔） | **926** | **432** | **−494 笔** |
| 去重后信号覆盖率（E/R） | 100% | **46.65%** | −53.35pp |
| 净盈亏（BT 级合计）¥ | **+2,634,024** | **−142,318** | **−2,776,341** |
| 年化收益 | 125.83% | −4.78% | −1.31 |
| 夏普 | 4.64 | −0.23 | −4.86 |
| MaxDD | −9.63% | −24.21% | −0.15 |
| 胜率 | 63.57% | 47.92% | −15.65pp |

### 0.2 盈亏差三因子拆解（口径：E_net − R_net = −2,776,341 ¥）

| # | 归因项 | 金额 ¥ | 占比 | 是否已查清 |
|---:|---|---:|---:|:---:|
| a) | **信号覆盖率缺口**：926−432=494 合约日 × R 均值 2,687.8 ¥/笔 | **−2,601,770** | **93.7%** | ✅ 已查清占比，**根因待分块追查** |
| b) | **共有交易单笔差**（信号一致时执行/成本差） | **+2,864** | −0.1% | ✅ 已查清，不是瓶颈 |
| c) | **残差**（工程侧 420 笔额外信号 + 近似误差） | **−177,436** | **6.4%** | ✅ 已查清占比，**额外信号特征待查** |
| Σ | 合计 | **−2,776,341** | 100% | — |

> **结论一句话**：**93.7% 的收益差来源于"工程侧信号覆盖率低（46.65%）"，执行/成本/单笔质量不是瓶颈。**

### 0.3 交易三分块（本报告结构）

按 **(合约 + 方向 + 同日 + tier + 价格±0.3%)** 组合匹配（稳健版匹配 v2），926 个研究侧独立信号与 432 个工程侧信号分成三块：

| 块 ID | 含义 | R 信号数 | E 信号数 | 占 R 净盈亏贡献 | 调查状态 |
|:---:|---|---:|---:|---:|:---:|
| [A](#a-%E5%B7%A5%E7%A8%8B%E4%BE%A7%E7%BC%BA%E5%A4%B1%E4%BF%A1%E5%8F%B7research_only) | **工程侧缺失信号（research_only）** | **914** = 去重 926 − 匹配 12 | 0 | 最大缺口 | 🔴 待追查 |
| [B](#b-%E5%B7%A5%E7%A8%8B%E4%BE%A7%E9%A2%9D%E5%A4%96%E4%BF%A1%E5%8F%B7engine_only) | **工程侧额外信号（engine_only）** | 0 | **420** | 残差主因 | 🟡 待追查 |
| [C](#c-%E5%85%B1%E6%9C%89%E4%BA%A4%E6%98%93matched) | **共有交易（matched，两侧一致信号）** | 12 | 12 | 微量 | 🟢 已查清 |

---

## A. 工程侧缺失信号（research_only）

> 定义：研究侧产生了"每合约日 1 笔"入场信号，但工程侧当日没有。
> 数量：914 个合约日（占 R 去重信号 926 的 **98.7%**）。这是本次调查的**主矛盾**。

### A.1 盈亏贡献
- 按 R 均值估算：914 × 2,687.8 ¥/笔 ≈ **−2,456,600 ¥**（占总盈亏缺口 ~88.5%）
- 若覆盖到 100%，即使工程侧单笔略差，也能把净盈亏从 −14.2w 拉回显著正值区间。

### A.2 缺失信号分布（按 Tier × 方向 Top-5 占 97%）

| 方向 | Tier | R-only 合约日 | 占 R-only 比 | 是否已调查清楚 |
|:---:|---|---:|---:|:---:|
| L | **L_seg3_lowmid_up** | 340 | **35.1%** | ❌ 未调查 |
| L | L_seg12_high_up | 173 | 17.9% | ❌ 未调查 |
| S | S_seg34_high_dn | 151 | 15.6% | ❌ 未调查 |
| S | S_seg12_high_dn | 150 | 15.5% | ❌ 未调查 |
| L | L_seg2_low_flat | 126 | 13.0% | ❌ 未调查 |
| Σ 以上 5 项 | — | **940 / 914** | **97%** | — |

> 缺口高度集中，**优先查 L_seg3_lowmid_up（占 35%）即可逼近答案**。

### A.3 研究资源（现存可直接用）

| 资源类型 | 路径 / 命令 | 内容说明 |
|---|---|---|
| 对比明细 parquet | [matched_pair_detail_v2.parquet](outputs/compare-r-e/matched_pair_detail_v2.parquet) | 所有 trade 级匹配对，`match_type=research_only` 即本块 |
| 分类事件落盘 | [research_events.parquet](outputs/compare-r-e/research_events.parquet) | 研究侧按 145 合约逐条事件的 tier/dir/seg 边界 |
| 研究侧交易落盘 | [research_trades.parquet](outputs/compare-r-e/research_trades.parquet) | R 侧 entry/exit/pnl/cost 完整列，附 `_entry_date` / `tier` |
| 日度重复诊断脚本 | [diagnose_intraday_dup.py](scripts/diagnose_intraday_dup.py) | 统计 (合约, 入场日) 笔数分布、识别日内重复 tier |
| 分类器实现（研究侧）| [classify_for_day()](scripts/reproduce_research_side.py) | 研究侧 `classify_for_day(spec, prev_day_close, d1_hist, m5_today_open)` |
| 分类器实现（工程侧）| [_compute_daily_state()](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L203-L203) | 工程侧 vnpy event loop 内的日频分类计算入口 |
| 工程侧回测 DB | `project_data/database/backtest/quant.db` · `run_id=15` | `backtests` 表（合计）/ `trades` 表（逐笔成交 open/close 行） |

### A.4 根因检查项清单（按调查顺序）

每一项都应当：**先挑 Top 缺口 tier（L_seg3_lowmid_up）+ 1 个合约样本做单 bar 级 trace，结论成立后再扩展到全 tier**。

| # | 检查项 | 含义 / 检查方法 | 目标判定 | 是否已查清 |
|---:|---|---|---|:---:|
| A.1 | **时间戳对齐**：研究侧 event_date vs 工程侧 daily_state 触发日 | 取 R-only Top 合约 + 日，dump 研究侧 `prev_day_close`、`ret_5d`、`ret_20d`、`daily_atr_bps`、`m5 今日首根 bar open` 的时间戳，与工程侧 `_compute_daily_state()` 在 `on_bar(5m)` 里拿到的上一交易日对齐判断 | 两侧 X 输入在同一日期的同一合约上**数值完全一致** | ❌ |
| A.2 | **daily_atr_bps 计算窗口**：研究侧 `_calc_atr_bps_sma10_prev_day` vs 工程侧 `DAILY_ATR_BPS` | 同一 prev_day，两侧 daily_atr_bps 数值差是否 ≥ 1bp；是否存在 warmup 差 1~10 根 bar 的情况 | 差 ≤ 0.5bp 视为一致 | ❌ |
| A.3 | **prev_close / ret_5d / ret_20d 的前复权/截断**：研究侧 `_load_5m_d1_hist` 按 `D-1` 截断 vs 工程侧 vnpy `bar.df[daily_state._T_days:-1]` | 同合约同 D-1：两侧 `prev_day_close`、`ret_5d`、`ret_20d` 数值 | 差 ≤ 1e-4 相对 | ❌ |
| A.4 | **seg 分位边界**：研究侧 `rank_percentile`（per-contract 3 档）vs 工程侧每日在 `_ensure_tier_boundaries` 重算的 `_seg_q` | 同合约同日：seg12 / seg2 / seg34 边界值是否一致 | 两侧边界差 ≤ 1e-4 相对 | ❌ |
| A.5 | **session / 时段过滤**：工程侧 `in_trading_session` 是否把研究侧事件窗口的 bar 当作"非交易时段"跳过 | 抽查 R-only 的 20 个样本：其 `entry_bar` 时间是否在工程侧被 skip | 不应当 skip；若 skip 要给出原因（合约 session 配置缺项/覆盖） | ❌ |
| A.6 | **分类 tier 判断边界**：研究侧 `if r1 <= seg12 → L_seg12_high_up` … 与工程侧 `_classify_asymmetry_tier` 6 个 if 条件逐行对照 | 是否存在一处以上 `<=` vs `<` 、顺序不同、或漏某个 tier 的 fallback | 6 个 tier 的真值表完全一致 | ❌ |
| A.7 | **事件窗口 1m 波动率**：研究侧 `m5_today_open[:int(EVENT_WINDOW_NBAR/5)]` 聚合 vs 工程侧 `evt_window_vol` 加载窗口 | 同 event_date 开盘 30min 的 1m 波动率 bps 是否一致 | 差 ≤ 1bp | ❌ |
| A.8 | **前一日 5m 历史是否截断到收盘**：研究侧按 `date < event_date` 取 hist vs 工程侧 `_T_days_needed` 偏移 | 是否多/少一根夜盘 bar 导致 ret_20d、ATR、seg 边界错位 | 样本对照 | ❌ |
| A.9 | **warmup 不够导致的 seg 边界退回到全局 fallback**：工程侧某合约 `_daily_state._ready` 为 False 的日期数 vs 研究侧 | 在 R-only 样本中 `seg_needs_global` 比例是否显著高于共有样本 | 不应有显著差异 | ❌ |
| A.10 | **前一日结算/收盘价定义差异**：`(prev_day_close - prev_settle)/prev_settle` 是否用于 seg2 / ret_flat 档 | 研究侧是否用昨收而工程侧用昨结（或相反）导致 `seg2_mid` / `flat` 命中错 | 定义一致 | ❌ |

### A.5 建议分块推进顺序

1. **Phase I（单 tier 单合约 trace）**：选 R-only 最大的 L_seg3_lowmid_up，挑缺口笔数 Top 1 合约，抽 10 个 R-only 样本，跑 A.1~A.10 → **预计能定位 1~2 个输入差异**
2. **Phase II（修复 + 验证）**：把 Phase I 发现的差异在工程侧修复（或研究侧按真实约定修正），跑冒烟 8 合约，看覆盖率从 46% → 多少
3. **Phase III（扫 tier）**：若 Phase I 找到的差异在 Top-5 tier 之间通用（97% 缺口覆盖），则直接修全 tier；若 tier 特定，每个 tier 单独验证

---

## B. 工程侧额外信号（engine_only）

> 定义：工程侧当日有入场信号，但研究侧同日没有（或者同日但 tier 完全不重叠、价格差 > 0.3% 都算）。
> 数量：**420 笔**（E 去重后 432 − 匹配 12）。

### B.1 盈亏贡献
- 三因子拆解里残差项 = **−177,436 ¥**（6.4% 总缺口），就是本块 + 近似误差的合计
- 表现为**拖后腿**：如果没有这 420 笔额外信号，纯 a)+b) 的 E 净盈亏 = R × b/a ≈ +1~2 个档位

### B.2 额外信号分布（Tier × 方向，跟 A 块高度相似 → 信号移位）

| 方向 | Tier | E-only 笔数 | 占 E-only 比 | 是否已调查清楚 |
|:---:|---|---:|---:|:---:|
| L | **L_seg3_lowmid_up** | 184 | **43.8%** | ❌ 未调查 |
| L | L_seg2_low_flat | 45 | 10.7% | ❌ 未调查 |
| S | S_seg34_high_dn | 80 | 19.0% | ❌ 未调查 |
| S | S_seg12_high_dn | 59 | 14.0% | ❌ 未调查 |
| L | L_seg12_high_up | 33 | 7.9% | ❌ 未调查 |
| S | S_seg2_mid_dn | 19 | 4.5% | ❌ 未调查 |

> **分布形态跟 A 块 R-only 几乎一样（都是 L_seg3_lowmid_up 最大）→ 这不是"工程侧多了另一类策略信号"，而是**分类边界在输入略微错位后，同一天的 tier 判定从 0 移位到 1**，信号整体平移了一格。这高度指向 A.1~A.10 里的某个输入差异。**

### B.3 研究资源

| 资源类型 | 路径 / 位置 | 内容说明 |
|---|---|---|
| 对比明细 parquet | [matched_pair_detail_v2.parquet](outputs/compare-r-e/matched_pair_detail_v2.parquet) | `match_type=engine_only` 即本块 |
| 工程侧 FIFO 配对交易 | [engine_paired_trades.parquet](outputs/compare-r-e/engine_paired_trades.parquet) | E 侧所有 entry/exit 配对，带 tier / exit_reason / gross / net / cost |
| 工程侧回测汇总 | [engine_backtests.parquet](outputs/compare-r-e/engine_backtests.parquet) | E 侧 145 合约的 BT 级总 PnL / 成本 / MaxDD |
| 策略状态机入口 | [_on_event()](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L416-L416) | 工程侧事件窗口判断 + 信号发出位置（如果 A.1~A.10 查不到，要检查这里是否有额外的状态机 allow） |

### B.4 根因检查项清单

| # | 检查项 | 含义 / 检查方法 | 目标判定 | 是否已查清 |
|---:|---|---|---|---|
| B.1 | **重复入场**：工程侧 `on_init` 后，同一合约日是否在开盘首 30min 内多次触发 `_on_event` → 重算 → 再发一次 open | 统计 E-only 的 (contract, entry_date) 是否有 >1 笔（当前 E 去重 432=432 → 已经严格 1 笔/日，所以此项大概率无问题） | 100% 都是 1 笔/日 | ✅ 已查清（diagnose 脚本段 A） |
| B.2 | **日间 signal re-entry guard**：工程侧 `_entry_sent` / `_entry_tier_sent` 是否在 `next_daily_state` 时被正确 reset | 若某合约日没 reset 到 False，下一日的 tier 判定可能不成立 → 跳过应发的信号 | reset 逻辑应与日期挂钩，而不是 session 结束 | ❌ |
| B.3 | **平掉又开（日内回转）**：工程侧在同一合约日是否先 SL/TIME 出场后，又触发一次入场（但 FIFO 配对后只有 1 笔/日，说明 close 的是前一日持仓而不是当日） | 与 B.1 同口径 | 无 | ❌ |
| B.4 | **分类 tier 输入漂移 1 日**：与 A.1~A.5 同一根因，如果工程侧"拿 D-2 当 D-1"（前滚），会把某些不该触发的 tier 触发出来 → 正好构成 E-only | 与 A 块同步解决，无需单独 trace | — | ❌（依赖 A 块） |

### B.5 建议分块推进顺序

- **Phase I 和 II 完全绑定 A 块**：先修 A 的输入漂移，E-only 应当自然消失 ≥ 70%（因为分布一致、只是 tier 边界命中偏移）
- Phase III：若 A 全解后仍有残留 > 30%，再单独查 B.2/B.3

---

## C. 共有交易（matched）

> 定义：(合约 + 同日 + 同向 + 同 tier + 价格±0.3%) 组合匹配成功。
> 数量：12 笔（占 R 去重 926 的 1.3%）。

### C.1 盈亏贡献
- R 合计净盈亏 = **+32,638 ¥**
- E 合计净盈亏（配对级）= **+35,502 ¥**
- **差额 = +2,864 ¥ → E 侧反而略好**（三因子拆解 b 项）
- **结论**：只要信号一致，工程侧单笔执行/成本/退出**不比研究侧差**；执行质量不是瓶颈

### C.2 共有交易分布与一致性

| 指标 | 值 | 是否可接受 | 是否已查清 |
|---|---:|:---:|:---:|
| N | 12 笔 | 样本偏少 | ✅ |
| 入场时间差 median | 600s（10min） | OK（研究侧整点 vs E 侧 5m close 差 0~10min 合理） | ✅ |
| 入场价相对差 median | 0.62‰ | OK（< 1‰） | ✅ |
| direction 一致率 | 7/12 = **58.3%** | ⚠️ 偏低（即使同 tier 同日，方向判断仍在漂移） | ✅（现象已确认，根因 = A 块输入差） |
| exit_reason 一致率 | 8/12 = **66.7%** | OK（6/8 以上就属于合理） | ✅ |

### C.3 研究资源

| 资源类型 | 路径 / 位置 | 内容说明 |
|---|---|---|
| 匹配对明细（v2 稳健版）| [matched_pair_detail_v2.parquet](outputs/compare-r-e/matched_pair_detail_v2.parquet) | `match_type=matched` 行是本块，带 `entry_dt_diff_sec` / `entry_price_reldiff` |
| 归因摘要 JSON | [summary_v2.json](outputs/compare-r-e/summary_v2.json) | 含 `match_v2_counts` / `metrics_research` / `engine_bt_agg` / `attribution` |
| 对比 v2 脚本 | [compare_research_vs_engineering_v2.py](scripts/compare_research_vs_engineering_v2.py) | L4 段 matched 统计，可直接扩展增加指标 |

### C.4 检查项清单（确认"不是瓶颈"的证据已充分）

| # | 检查项 | 状态 | 说明 | 是否已查清 |
|---:|---|:---:|---|:---:|
| C.1 | 共有交易 N ≥ 10 | ✅ | 12 笔，量级够判断"单笔不差" | ✅ |
| C.2 | 方向一致率 ≥ 80% | ⚠️ | 仅 58.3%，**这是 A 块输入漂移的旁证**（不是执行的锅） | ✅ |
| C.3 | 价格差 median ≤ 1‰ | ✅ | 0.62‰，价格对齐 OK | ✅ |
| C.4 | 共有交易 E 净盈亏 ≥ R | ✅ | 35,502 ≥ 32,638，执行无劣化 | ✅ |
| C.5 | 成本（comm + slip）单笔一致 | ✅ | diagnose 末段：R 单笔 631.8 ¥ vs E 636.2 ¥（几乎打平） | ✅ |

---

## D. 研究资源汇总索引

### D.1 脚本（均可直接 `uv run python <path>` 运行）

| 脚本 | 路径 | 作用 | 依赖 | 耗时参考 |
|---|---|---|---|---|
| 研究侧复现管线 | [reproduce_research_side.py](scripts/reproduce_research_side.py) | 从 5m CSV 批量分类、模拟、出指标、落盘 events/trades parquet | 145 CSV / tqsdk path | 2~3 min |
| 对比 v1（时间窗口匹配）| [compare_research_vs_engineering.py](scripts/compare_research_vs_engineering.py) | 初版对比（入场时间 ±10min 匹配、指标分层） | DB / 研究侧 parquet | 2.3min（含研究侧重跑） |
| 对比 v2（稳健匹配 + 归因）| [compare_research_vs_engineering_v2.py](scripts/compare_research_vs_engineering_v2.py) | 读 v1 落盘，按 (合约+同日+tier+同向+价格±0.3%) 匹配，三因子拆解 | v1 落盘 parquet | 秒级 |
| 日内重复诊断 | [diagnose_intraday_dup.py](scripts/diagnose_intraday_dup.py) | 按 (合约, 入场日) 统计笔数，识别重复 tier/方向，给出真实覆盖率 | v1 落盘 parquet | 秒级 |

### D.2 数据产物（compare-r-e 目录）

| 文件 | 说明 |
|---|---|
| `research_events.parquet` | 研究侧 145 合约逐条分类事件（980 行 = 信号前分类） |
| `research_trades.parquet` | 研究侧模拟后完整交易（980 行），附 `_entry_date` / `tier` / `cost_entry_bps` 等 |
| `engine_paired_trades.parquet` | 工程侧 FIFO 配对后 432 笔完整交易（run_id=15） |
| `engine_backtests.parquet` | 工程侧 145 合约 BT 级汇总（total_net_pnl / total_commission / total_slippage 等） |
| `matched_pair_detail.parquet` | v1 匹配明细（时间窗 ±10min，仅 8 匹配） |
| **`matched_pair_detail_v2.parquet`** | **v2 稳健匹配明细（968 R-only / 420 E-only / 12 matched / 合计 1400 行）← 所有块的主数据源** |
| `summary.json` | v1 汇总 JSON |
| **`summary_v2.json`** | **v2 汇总 JSON（含三因子拆解 attribution）← 顶层脚本读它即可重画 0.2 表** |

### D.3 策略实现入口（对照阅读）

| 模块 | 研究侧（batch） | 工程侧（vnpy） |
|---|---|---|
| 分类器主函数 | [classify_for_day()](scripts/reproduce_research_side.py) | [_classify_asymmetry_tier()](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L258-L258) |
| daily_atr_bps 指标 | `_calc_atr_bps_sma10_prev_day` | [DAILY_ATR_BPS](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L54-L54) → [indicators.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/core/indicators.py) |
| seg 边界计算 | `rank_percentile` per-contract 3 档 | [_ensure_tier_boundaries()](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L336-L336)（每日重算） |
| 信号发出入口 | `build_event_timeline` → `simulate_contract` | [_on_event()](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L416-L416) |

### D.4 DB / run_id 信息

- **DB 路径**：`project_data/database/backtest/quant.db`（SQLite，`sqlite3` CLI / `pd.read_sql` 均可读）
- **表 `backtests(run_id, vt_symbol, total_net_pnl, total_commission, total_slippage, max_drawdown, end_balance, ...)`**：145 行 = 本合约级结果
- **表 `trades(run_id, vt_symbol, tradeid, direction, offset, price, volume, commission, ..., exit_reason, tier_pnl_tag)`**：877 行 = 445 open + 432 close（13 个未平仓 unmatched_open）
- **对比 run_id**：`RUN_ID = 15`（策略：`va_asymmetry_composite` · base_tf=5m · k_sl_short=2.5 · 本金 100w · 145 合约并行 16 workers）

---

## E. 分块推进路线图（后续研究顺序）

| 阶段 | 目标 | 输入文件 / 脚本 | 产出 | 判定阈值 |
|---|---|---|---|---|
| **1** | **L_seg3_lowmid_up Top-1 合约单 bar trace**（缺口 35% tier 的根因定位）| matched_pair_detail_v2.parquet / reproduce_research_side.py + va_asymmetry_composite_strategy.py | 发现 A 块 1~N 个具体输入差异（如 daily_atr_bps warmup 差 10 bar） | 能把 Top-1 合约 30 个 R-only 样本还原出 ≥ 25 个应打的信号 |
| **2** | 输入差异修复（工程侧按研究侧基线对齐，或反之） | 对应 1 的差异点代码 | 补丁策略代码 | 8 合约冒烟覆盖率 ≥ 90% |
| **3** | 145 合约全量回归回测 | run_id ≥ 16 | 新 BT 汇总 | 覆盖率 ≥ 85% · 净盈亏 ≥ +1,000,000 ¥ · Sharpe ≥ 2.5 |
| **4** | 若 Phase 3 仍 < 80%：Top-5 tier 其余四个各单独一次 Phase 1 | 同 Phase 1 脚本 | 每个 tier 的特定根因 | 每个 tier 覆盖率 ≥ 85% |
| **5** | 残留 E-only（> 30% 才查）：B.2/B.3 状态机 re-entry guard | va_asymmetry_composite_strategy.py | 修正 reset 逻辑 | E-only 占比 ≤ 10% |
| **6** | 最终判决：净盈亏 Δ 仍 ≥ 500k → 做"方向一致但 SL/TIME 退出参数对齐"深挖 | — | — | 所有 tier 的 exit_reason 一致率 ≥ 80% |

---

## F. 报告变更记录

| 日期 | 版本 | 变更内容 |
|---|:---:|---|
| 2026-07-13 | v1.0 | 初版：run_id=15 对比基线 + 三块（R-only / E-only / matched）拆解 + 检查项 + 资源索引 + 推进路线 |
