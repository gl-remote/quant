# va-asymmetry-composite · 阶段 0 基线 B0 回测

> 生成脚本: `scripts/ai_tmp/va_composite_stage0_baseline.py`
> 数据: `project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet` + `project_data/market_data/csv/*.tqsdk.5m.csv`
> 输出: `project_data/ai_tmp/va_composite_stage0_baseline.trades.parquet`（§10 字段）

## 1. 配置摘要（B0）

| 层 | 参数 | 值 | 来源 |
|:---|:---|:---|:---|
| L0 | 成本口径 | realistic-cost | parameter-selection-spec L0.3 / §6 |
| L0 | 单笔止损 | 2% 权益 | L0.4 / §7.1 |
| L0 | 总名义上限 | 100% 权益 | L0.5 / §7.2 |
| L0 | 合约内去重 | 8h | L0.6 / §8.1 |
| L1 | 多头 SL × 持仓 | 1.0 × 8h | L1.1/L1.2 |
| L1 | 空头 SL × 持仓 | 2.5 × 10h | L1.3/L1.4 |
| L1 | Trailing / TP | 关闭 / 关闭 | L1.5/L1.6 |
| L2 | 品种筛选 | S1 全品种5档 | L2.1 / §4.2 |
| L2 | 强度加权 | W0 等权 | L2.3 / §5.1 |
| L2 | 多空权重 | VW0 等权 | L2.5 / §5.2 |

## 2. 文档/数据差异登记（实现已采纳数据实际）

| # | 差异 | 处理 |
|:---|:---|:---|
| 1 | §2 写 entry_atr_bps=rolling20d，timeline 实测仅 `daily_atr_10_bps`（10日） | 采用 `daily_atr_10_bps` |
| 2 | §5.3 仓位公式 `0.02/K_SL` 漏 ATR，与 §3.2/§7.1「单笔亏2%」矛盾 | 采用含 ATR 版 `0.02/(K_SL·entry_atr_bps/10000)`，与 archive 一致 |
| 3 | experiment-plan §0.1「阶段0不需市场数据」与 §3.3/§10 矛盾 | 以 math-spec 为准，读 5m 做退出 |

## 3. 主指标 vs archive

| 指标 | B0 本主题 | archive 参考 | 阈值(§0.3) |
|:---|---:|---:|---:|
| 年化净收益 | 15.10% | 15.45% | ≥12% |
| 净夏普 | 2.70 | 2.23 | ≥1.8 |
| MaxDD | -2.40% | -7.51% | ≤10% |
| 月度胜率 | 86.7% | 83% | ≥70% |
| 单笔 IR | 0.370 | 0.30 | ≥0.25 |
| ν_implied | 50.283 | - | >0 |
| p(ν>0) bootstrap | 1.000 | - | ≥0.95(目标) |

## 4. 多空 / 逐 tier

- 多头: 年化 5.40% · Sharpe 1.46 · MaxDD -5.23% · n=78
- 空头: 年化 10.65% · Sharpe 2.39 · MaxDD -2.06% · n=220

| tier | n | 年化 | Sharpe | MaxDD |
|:---|---:|---:|---:|---:|
| L_seg12_high_up | 24 | 1.35% | 0.64 | -3.85% |
| L_seg3_lowmid_up | 54 | 4.29% | 1.37 | -2.66% |
| S_seg12_high_dn | 98 | 5.94% | 1.86 | -1.94% |
| S_seg2_mid_dn | 72 | 2.06% | 1.03 | -1.19% |
| S_seg34_high_dn | 50 | 2.92% | 1.39 | -1.17% |

## 5. 风控诊断

- 交易数: 298 | 合约数: 115
- 日均名义暴露(压仓前): 124.2%
- 触发压仓的天数: 86

## 6. Gatekeeper（§0.3）

| 判据 | 结果 | 参考 |
|:---|:---:|:---|
| 年化净收益 ≥ 12% | PASS | archive 15.45% |
| 净夏普 ≥ 1.8 | PASS | archive 2.23 |
| MaxDD ≤ 10% | PASS | archive -7.51% |
| 月度胜率 ≥ 70% | PASS | archive 83% |
| 单笔 IR ≥ 0.25 | PASS | archive 0.30 |
| ν_implied > 0 | PASS | 唯一定义源 §9 |

**结论: ALL PASS ✅**
