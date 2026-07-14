# va-asymmetry-revisit · Session 总报告（2026-07-14）

> 类型：Workbench 顶层摘要
> 状态：**主题所有假设全线证伪 · 建议冻结**（2026-07-14）
> 覆盖：四轮实验的顶层结论 + 关键数字 + 决策链

## TL;DR

用户目标：从被 daily 特征未来函数污染而废弃的 va-asymmetry 家族里回收有效策略，时间预算充足，允许自由探索。

一整天四轮实验，我做完了以下事：

| 轮次 | 假设 | 数据 | 结果 | KF |
|---:|---|---|---|---|
| 1 | H-1：signed A3_skew 一维方向 IC | 15 品种 · 40 合约 · 16k events | **判死**：pooled IC∈[-0.03, 0.01]，CI 全跨 0，跨品种一致性 45-60% | KF-1, KF-2 |
| 2 | 6-tier causal 三维联合（skew×ATR×trend） | 同上 | **疑似 alpha**：L_seg2_low_flat Sharpe 1.48 / 年化 36.7% | KF-5（后撤销） |
| 3 | 扩样 145 合约 + 因果性铁证 + 选样偏差诊断 | 20 品种 · 145 合约 · 56k events · 33m | **判死 + 铁证**：pipeline 无未来函数（max_abs_diff=0），扩样后 Sharpe 塌至 0.08，原 40 合约是随机分布 top 1.5% | KF-9, KF-10, KF-11 |
| 4 | Skew 派生 7 大类（\|skew\|、短窗、Δskew、xs-rank、交互、persistence、drawdown） | 同扩样 · 70 组 pair | **判死**：\|IC\| 最强 -0.022，通过门槛 0/70 | KF-12 |

**最终判决**：va-asymmetry 家族在**完整数据 + 严格 causal + 无选样偏差**三重条件下全线证伪。建议整体冻结进 `themes-frozen/va-asymmetry/`。

## 关键数字表

### 数据规模

- **合约**：145 个（20 品种：CZCE.CF/FG/MA/OI/RM/SR/TA、DCE.c/cs/i/m/p/y、INE.sc、SHFE.ag/al/au/cu/hc/rb）
- **时间跨度**：2023-09 → 2026-07，33 个月
- **Hourly events**：55,877 个
- **数据源**：`project_data/market_data/csv/*.tqsdk.5m.csv`
- **成本模型**：`workspace/common/contract_specs.py` 真实 tick + slip + commission

### 因果性铁证

- 225 个随机 event × 3 特征（A3_skew / atr_intra / trend_intra）
- 双数据源对比（Full vs `bars.iloc[:event_idx+1]` 截断）
- **max_abs_diff = 0.0000e+00**，一致率 **100%**
- ✅ pipeline 无未来函数

### 假设 1：H-1 A3_skew 一维方向 IC

| Cluster | Horizon | n | IC | CI | p |
|---|---|---:|---:|---|---:|
| (contract, date) | ret_1h | 16,366 | +0.007 | [-0.008, +0.021] | 0.39 |
| (contract, date) | ret_12h | 15,921 | -0.027 | [-0.057, +0.001] | 0.06 |

- 跨品种 sign consistency **45-60%** vs 门槛 80%
- 制度分层（ATR 3档 × side × horizon = 36 格）0/36 净收益 CI 排 0

### 假设 2：Causal L_seg2 tier（小样本发现的假 alpha）

| 版本 | n_trades | 年化 | Sharpe | DD |
|---|---:|---:|---:|---:|
| **40 合约**（c1-c5） | 299 | 36.7% | **1.48** | -21.6% |
| **145 合约**（e2） | 1,100 | **3.4%** | **0.08** | **-64.6%** |

### 假设 3：选样偏差诊断

- 从 145 合约随机抽 40 个 × 200 次
- Sharpe 分布：mean 0.018, std 0.572, p95 = 1.062
- 原 40 合约 Sharpe 1.44 落在 **98.5% 分位** = 极端右尾选样

### 假设 4：Skew 派生 7 大类广度扫描

Top |IC| 榜（70 组 pair）：

| Rank | Feature | Target | IC | consistency |
|---:|---|---|---:|---:|
| 1 | abs_skew_4h | future_range | **-0.022** | 55.6% |
| 2 | abs_skew_4h | abs_ret_4h | -0.014 | 56.9% |
| 3 | abs_skew_8h | future_range | -0.014 | 56.9% |
| 4 | abs_skew_4h | abs_ret_8h | -0.013 | 52.1% |
| 5 | abs_skew_4h | abs_ret_6h | -0.012 | 54.2% |
| 6 | abs_skew_24h | future_min_ret | +0.012 | 51.4% |
| 7 | abs_skew_24h | future_range | -0.011 | 58.3% |
| 8 | abs_skew_8h | abs_ret_6h | -0.011 | 56.3% |
| 9 | abs_skew (12h) | abs_ret_2h | -0.010 | **61.8%** |
| 10 | skew_delta_1h | ret_8h | +0.010 | 59.0% |

通过门槛（|IC|>0.03 AND consistency≥65%）：**0/70**

TOP-1 深挖（abs_skew_4h → future_range）：
- Tercile 均值差 <0.005%，比成本 0.06-0.30% 小 20 倍
- Per-contract 保留率 50.0%
- Walk-forward train/test 符号翻转

## 12 条 KF 全览

- **KF-1**（判死）· H-1 pooled IC 一维方向无 alpha
- **KF-2**（判死）· H-1 制度分层 36 格 0 通过
- **KF-3**（方法论）· 期货 hourly-event 半 tick 成本吞噬约束
- **KF-4**（边界待定）· Hour-of-day 白盘 mean(ret) 偏漂移 · 作为基准非 alpha
- **KF-5**（**已撤销**）· Causal L_seg2 疑似制度依赖 alpha（40 合约假阳性）
- **KF-6**（判死）· 6-tier 组合等权在 causal 修复下崩塌
- **KF-7**（判死）· S_seg12_high_dn 反向 · 空头单机制假设不成立
- **KF-8**（方法论）· Rank-window 240/360 结果一致
- **KF-9**（判死）· L_seg2 扩样后 Sharpe 1.44→0.08 判死
- **KF-10**（方法论）· 选样偏差自诊断法（随机等大子样 Sharpe 分布）
- **KF-11**（方法论）· 因果性铁证四层证据链方法
- **KF-12**（判死 + 方法论）· Skew 派生 7 大类全线证伪 · "含信息" ≠ "可交易 alpha"

## 6 条 F-系列（后续主题禁止重跑）

- F-13 signed A3_skew 一阶方向 alpha
- F-14 signed A3_skew top/bottom 20% × ATR 三档直接下注
- F-15 6-tier 组合等权复合策略
- F-16 va-asymmetry-composite 原空头单机制假设
- F-17 Causal L_seg2 单信号 6-10h 长持仓
- F-18 Skew 派生特征全家族（7 大类）

## 四份实验流水报告

1. [workbench:va-asymmetry-revisit-h1-report](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit-h1-report.md) · 一轮 H-1 判死
2. [workbench:va-asymmetry-revisit-causal-tier-report](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit-causal-tier-report.md) · 二轮 causal tier 疑似 alpha
3. [workbench:va-asymmetry-revisit-expanded-report](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit-expanded-report.md) · 三轮扩样 + 因果性铁证 + 选样偏差诊断
4. [workbench:va-asymmetry-revisit-skew-derivative-report](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit-skew-derivative-report.md) · 四轮 skew 派生 7 大类广度扫描

## 12 个可复用脚本

在 [docs/workbench/va-asymmetry-revisit/scripts/](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/)：

| 脚本 | 用途 | 状态 |
|---|---|---|
| `h1_a3_skew_pooled_ic.py` | H-1 pooled IC + N-0 截断法 | ✅ |
| `h1b_regime_stratified.py` | 制度分层 + 极端事件 + hour baseline | ✅ |
| `h1c_hour_of_day_net.py` | Hour-of-day 净收益 walk-forward | ✅ |
| `c1_causal_tier_scan.py` | Causal 三特征 + 6 tier + horizon | ✅ |
| `c2_l2_robustness.py` | L_seg2 walk-forward + IR + 反向 | ✅ |
| `c3_l2_lgo_retention.py` | LGO + 品种保留率 + 随机对照 | ✅ |
| `c4_sensitivity.py` | 阈值敏感度 + 3-fold + 组合池 | ✅ |
| `c5_performance_estimate.py` | 逐笔 net pnl → 年化/夏普/回撤 | ✅ |
| `e1_v2_causality_ironproof.py` | 因果性铁证（225 events × 3 特征） | ✅ |
| `e2_expanded_causal_tier.py` | 扩样 145 合约完整链路 | ✅ |
| `e3_selection_bias_check.py` | 选样偏差诊断（随机 40 抽样 Sharpe 分布） | ✅ |
| `s2_broad_ic_scan.py` | Skew 派生 7 大类广度 IC 扫描 | ✅ |
| `s3_abs_skew_deep.py` | Top-1 abs_skew_4h 深挖 | ✅ |

## 方法论沉淀（这条主题最值钱的产出）

1. **KF-3 · 期货 hourly-event 成本天花板**：realistic roundtrip 0.06-0.30%，任何 gross <0.1% 的信号结构上不可能过关
2. **KF-8 · Rank-window 无关性**：per-contract rolling rank 240 vs 360 event 结果一致，后续无需扫参
3. **KF-10 · 选样偏差自诊断法**：小样本 Sharpe>1 的信号 → 扩样前必须先跑"随机等大子样 Sharpe 分布"诊断，落在 p95 之外的就是选样偏差
4. **KF-11 · 因果性铁证四层证据链**：值级（Full vs Truncated max_abs_diff）→ rank 一致（单调传递）→ tier 一致（纯函数）→ pipeline 无未来函数
5. **KF-12 · "含信息" ≠ "可交易 alpha"**：前者只需 IC≠0，后者要 |IC|>0.03 + consistency>65% + 均值差穿透成本 · 三门槛缺一不可

## 建议下一步

- **主题彻底废弃归档**（已执行 · 2026-07-14）：主题目录整包搬入本批次 `theme-va-asymmetry-revisit/` 子目录（不迁往 themes-frozen，因家族已判死无恢复计划）
- **归档批次**（可选）：把本 session 四份 workbench 报告 + 13 个脚本 + 数据产出（大文件只登记路径）归档为 `archive:2026-07-14-va-asymmetry-revisit-full-refutation`

## 我用整天时间证明的一件事

**成交量偏度确实含微弱统计信息，但在期货 hourly-event 尺度上不可交易。**

- 若继续挖 skew，必须换周期粒度（tick / order book）或换资产（股票分钟 / crypto 5m）
- 若继续做 event-driven 因子，必须找**结构上不属于本家族**的新特征源（volume imbalance、amihud、trade sign autocorrelation 等）
- 不建议在 va-asymmetry 家族内继续投入 · KF-1~KF-12 已经覆盖所有正交假设方向
