# va-asymmetry-revisit · 二轮回收报告：Causal Tier 分类器

> 类型：Workbench 实验流水
> 状态：**发现制度依赖 alpha 候选**（2026-07-14）· L_seg2_low_flat 通过多重稳健性

## 一句话结论

在 H-1（一维 signed A3_skew IC）判死后，回到 archive va-asymmetry-composite 原策略核心——**(skew × ATR × trend) 三维联合 tier + 6-12h 长持仓**——用严格 causal 的 intraday 特征（全部截止到 event_idx-1）重建 6 个 tier，发现 **L_seg2_low_flat（高 skew · 低 ATR · 平趋势 · 做多）在 15 品种 40 合约 16,406 events 数据上：Full 期 realistic-cost 后年化 36.7% / Sharpe 1.48 / DD -21.6%；2025-11 之后 late 段年化 62.3% / Sharpe 2.83 / DD -3.0%**；跨 8 组阈值 sensitivity + rank_win 240/360 复验均同向；LGO 5 sector 中 3 通过；但 3-fold 时间稳定性显示**信号集中在数据末段**，早段 fold 0 (2024-09→2025-04) test 反向 → **制度依赖 alpha，而非全期稳定**。

## 实验链路

- **入口**：h1 已产的 16,406 events 长表（15 品种 40 合约 hourly）
- **N-0 因果性**：三个特征均严格 causal
  - `A3_skew`：W3 rolling 12h volume-profile 三阶偏度（`bars.iloc[lo:event_idx]`，`event_idx` 自身排除）
  - `atr_intra`：前 96 根 5m 绝对 log-ret 均值，`.shift(1)`
  - `trend_intra`：前 96 根 5m 累积 log-ret，`.shift(1)`
  - 100% 通过 h1 的 N-0 截断法（全 sector `max_abs_diff=0.00e+00`）
- **rank 口径**：per-contract rolling 240 events (≈20 交易日) 百分位
- **tier 判定**：按 spec §1.3 的 6 阵营区间（转成 data-rank 语义，data rank 高 = long）
- **判据**：signed pnl mean + cluster bootstrap CI (cluster = (contract, event_date)) + realistic roundtrip cost

## ① Tier × horizon 全景（[c1_tier_horizon.csv](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c1/c1_tier_horizon.csv)）

| tier | dir | horizon | n | gross mean | **net mean** | ci_lo | ci_hi | p_two |
|---|:-:|---|---:|---:|---:|---:|---:|---:|
| **L_seg2_low_flat** | +1 | ret_8h | 299 | 0.00254 | **0.00194** | 0.00031 | 0.00343 | 0.012 |
| **L_seg2_low_flat** | +1 | ret_10h | 299 | 0.00257 | **0.00196** | 0.00014 | 0.00364 | 0.028 |
| L_seg2_low_flat | +1 | ret_12h | 296 | 0.00242 | 0.00181 | -0.00030 | 0.00380 | 0.078 |
| L_seg3_lowmid_up | +1 | ret_10h | 441 | 0.00143 | 0.00085 | -0.00074 | 0.00239 | 0.270 |
| L_seg12_high_up | +1 | 全 | — | ≈0 | 负 | — | — | — |
| S_seg12_high_dn | -1 | ret_10h | 282 | +0.00238 | +0.00292 | 0.00085 | 0.00528 | 0.002 (**反向**!) |
| S_seg34_high_dn | -1 | 全 | — | 负 | 负 | — | — | — |
| S_seg2_mid_dn | -1 | 全 | — | 负 | 负 | — | — | — |

**关键发现 1**：`L_seg2_low_flat` 是 6 tier 中唯一 net CI 排 0 的多头信号；`S_seg12_high_dn` **反向通过**（spec 判空但数据实际是慢多），与原 archive va-asymmetry `L_seg2 争议 tier` 及 `spec §1.3.4.2 W mismatch` 相符。这直接印证 hypothesis-inventory **H-17 (L_seg2 争议 tier 可能是均值回归 S)** 的**否定**——同时否认原多头逻辑与"应反转"假设，实际是"低波动 + 平趋势 + 高 skew 的 6-10h 慢多头 drift"。

## ② 稳健性检验矩阵

### [c2](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c2/) · 8:2 walk-forward

| split | horizon | n | net mean | CI | p |
|---|---|---:|---:|---|---:|
| train (2024-09 → 2025-11-17) | ret_10h | 239 | 0.00149 | [-0.00062, 0.00363] | 0.147 |
| **test (2025-11-17 → 2026-05)** | ret_10h | 60 | **0.00385** | [0.00057, 0.00695] | **0.020** |
| **test** | ret_12h | 59 | **0.00466** | [0.00083, 0.00829] | **0.017** |

### [c3](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c3/) · 品种保留率 + LGO + 随机对照

- 品种保留率：ret_8h **25/39 = 64.1%**，ret_10h 24/39 = 61.5%（H-1 只有 37%，此候选高得多，但仍未达 methodology 80% 硬门）
- Sector LGO 10h：去除任一 sector，**3/5** 剩余组 CI 排 0（agri/metals 去除后 CI 塌）；说明信号靠 black/chem/energy 撑
- 随机对照：从 tier=none 事件随机抽 302 个，10 折 walk-forward 中 2/10 也"通过 test CI 排 0" → **20% 假阳性率**警报
- **hour=11 单点分析**：hour 11 (n=38) 8h p=0.002 / 10h p=0.008，是所有 hour 中信号最强的一点；但 **drop hour=11 后 test 仍通过（10h p=0.041 / 12h p=0.037）** → 非"完全靠 hour=11 单点"

### [c4](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c4/) · 参数敏感度

8 组 tier 阈值变体 × 3 split × 4 horizon = 96 格：

| variant | test 10h net | test 10h p |
|---|---:|---:|
| baseline_spec | 0.00379 | **0.025** |
| skew_wider (0.75-0.95) | 0.00370 | **0.003** |
| skew_narrow (0.85-0.90) | 0.00473 | **0.007** |
| atr_looser (≤0.50) | 0.00375 | **0.014** |
| atr_tighter (≤0.20) | 0.00328 | **0.024** |
| trend_wider (0.10-0.85) | 0.00290 | 0.071 |
| trend_narrow (0.35-0.65) | 0.00542 | **0.007** |
| skew_low_atr (0.70+) | 0.00318 | **0.016** |

**7/8 变体 test p<0.05**，方向全同 → **信号跨阈值稳健**，不是过拟合到某一格。

### [c4] · 3-fold walk-forward

| fold | period | train 10h p | test 10h p |
|---:|---|---:|---:|
| 0 | train 0-50%, test 50-70% | 0.050 | 0.398 (**反向**) |
| 1 | train 0-70%, test 70-85% | 0.214 | 0.379 |
| 2 | train 0-85%, test 85-100% | 0.127 | **0.043** |

**制度依赖判决**：fold 0 test 反向说明 2025-04→2025-08 段这个信号是负的（早段负 pnl 已在 [c5_B_monthly.csv](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c5/c5_B_monthly.csv) 显示：2025-02 -7%、2025-05 -18%、2025-08 -19%）；fold 2 test 强通过说明近半年市场对这个结构给出更强 edge。

### [c4] · rank_win = 360 复验

L_seg2 events 从 302 变到 328（阈值扩展）：test 10h **p=0.021**，12h **p=0.011** → 与 240 完全一致，非 rank window 敏感。

## ③ 实用性能估算（[c5](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c5/)）

**逐笔 net log-return → 按 event_date 聚合日收益 → 补齐 bdate → 年化/夏普/回撤**（简化版，不含 Cap / dedup / 保证金等 B 层塑形）：

| 候选 | 期段 | n_trades | 年化 | Sharpe | Max DD | Hit | mean_bps/笔 |
|---|---|---:|---:|---:|---:|---:|---:|
| A: L_seg2 单信号 · 10h | full (2024-09 → 2026-05) | 299 | 36.7% | **1.48** | -21.6% | 53.2% | 19.6 |
| A · late (2025-11+) | 6 个月 | 87 | **62.3%** | **2.83** | -3.0% | 60.9% | 33.8 |
| A · early | 12 个月 | 212 | 26.2% | 1.02 | -21.6% | 50.0% | 13.8 |
| B: L_seg2 + L_seg3 · 10h | full | 740 | 56.8% | 1.39 | **-46%⚠** | 52.6% | 13.0 |
| B · late | | 236 | 94.4% | 2.37 | -11.8% | 55.9% | 21.4 |
| B · early | | 504 | 39.4% | 0.95 | -46.0% | 51.0% | 9.0 |
| C: 全 6 tier · 10h（含空头 tier 反向拖累）| full | 1671 | **-73.3%** | -0.86 | -178% | 49.2% | -8.2 |
| D: B + hour∈{9,10,11,14} filter | full | 436 | 30.1% | 0.98 | -30.7% | 52.3% | 11.7 |

**关键读数**：
- **候选 A（L_seg2 单信号）**：Sharpe 1.48 / 年化 36.7% 的全期表现在方法论门槛之上（>0.2 Δ Sharpe vs 零），且近半年 Sharpe 2.83 → **可作实验候选、非可交付策略**
- **候选 B（L_seg2 + L_seg3 池）**：full 期 DD -46% 太大，交易信号密度换来了尾部风险；不推荐 —— 除非引入 Cap 限制并发暴露
- **候选 C（全 6 tier）**：空头 tier 全部反向拖累（跟 c1 观察一致，signed short 平均为负）→ **原 archive 的 6-tier 组合结构在 causal 修复下崩塌**，只剩多头两个 tier 有信号
- **候选 D（+ hour filter）**：全期 Sharpe 降到 0.98 → hour filter 抑制了非主时段的正贡献，负优化 → **hour=11 是必要但非充分**

## ④ 与 archive 的对比

| 维度 | archive B0（原 va-composite） | 本次 causal 修复 |
|---|---|---|
| 特征 | daily A3_skew（前日 5m）+ daily ATR + daily trend，event_date merge **未 shift(1)** | 全部 intraday，严格 event_idx-1 截断 |
| Tier 命中率 | 未报 | 10.4% (1709/16406 events)，其中多头 4.7% 空头 3.9% |
| L_seg2_low_flat 判定 | 争议 tier，B0 内活跃但 workbench 曾标"IR 负漏判" | **确认多头信号有 edge，late 段 Sharpe 2.83** |
| S_seg12_high_dn | 核心空头 tier，Cap=4 下年化 35% | **反向**（应做多而非做空），net p=0.002 |
| S_seg34 / S_seg2_mid | 主力/辅助空头 tier | 全部反向或无信号 |
| 6-tier "组合等权" 假设 | 原 KF-11 已证伪 tier 独立性 | **进一步证伪**：causal 修复后仅 2 个多头 tier 有正 edge，空头全反向 → hypothesis-inventory H-10 组合层结构在 causal 版下需重新设计 |

## ⑤ 判决与去向

**这是一条候选、不是稳定策略**：
- ✅ 通过 methodology 主要门槛：多阈值方向一致 + 品种保留率 61% + rank window 无关 + drop-hour-11 test 仍过
- ❌ 未通过：3-fold 中早段 fold 0 反向 + 品种保留率未达 80% + 随机对照 20% 假阳性
- 📊 实用规模：Full Sharpe 1.48、Late Sharpe 2.83、Full DD -21.6% —— **对制度友好期而言性能好**，对制度不友好期（2025-05/08）会亏 15-20%

**下一步（建议）**：

1. **扩样时间维度**：目前数据只有 21 个月（2024-09 → 2026-05），fold 0 早段负是"另一个制度"还是"信号根本不稳"，需要 2023-09 → 2024-09 的历史合约数据来判定
2. **扩样品种维度**：加入 CFFEX（IF/IC/IH/IM）、股指、更多小品种，看 sector LGO 通过率是否升到 4/5
3. **正式回测**：把候选 A 用 workspace 的 vnpy backtest 引擎跑一次，含 Cap 限制、真实成交配对、走 8:2 walk-forward
4. **Alternative：转向 H-11 τ_signed（timing 特征）** 而非坚持 tier 路线——如果 tier 3 维联合仅剩多头 2 个 tier 稳，H-11 可能是更纯净的 alpha 源

**为什么没直接写成策略代码**：候选 A 的 fold 0 反向 + 20% 假阳性率不足以让我直接把它包装成 `workspace/strategies/` 里的长期策略；工程化投入按方法论 §8「样本外双维度通过 → 才可开始实现」的门槛，本轮只满足单折 walk-forward 且时间维度不稳。写策略代码是下一次数据扩样后的动作。

## 文件清单

- 脚本
  - [c1_causal_tier_scan.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/c1_causal_tier_scan.py) · causal 三特征 + 6 tier + horizon 全景
  - [c2_l2_robustness.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/c2_l2_robustness.py) · L_seg2 walk-forward + 品种 IR + S_seg12 反向验证 + hour-of-day
  - [c3_l2_lgo_retention.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/c3_l2_lgo_retention.py) · 品种保留率 + LGO by sector + 随机对照
  - [c4_sensitivity.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/c4_sensitivity.py) · 阈值敏感度 + 3-fold + 组合池 + rank_win 复验
  - [c5_performance_estimate.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/c5_performance_estimate.py) · 4 个候选的实用性能表
- 数据：`docs/workbench/va-asymmetry-revisit/outputs/{c1,c2,c3,c4,c5}/`
