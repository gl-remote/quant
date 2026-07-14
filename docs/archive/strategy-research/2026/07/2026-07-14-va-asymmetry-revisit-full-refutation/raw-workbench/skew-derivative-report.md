# va-asymmetry-revisit · Skew 派生假设广度扫描

> 类型：Workbench 实验流水
> 状态：**Skew 派生 7 大类假设全线证伪**（2026-07-14）· 成交量偏度确实"含信息"但不构成可交易 alpha

## 一句话结论

针对用户直觉"成交量峰度不可能不含任何信息"，本轮在 **145 合约 · 55,877 events · 33 个月**扩样数据上广度扫描 **7 大类 skew 派生假设**（|skew| → 波动率 / drawdown / range，短窗 skew 4h/8h/24h → 方向，Δskew → 方向，cross-sectional rank → 方向，skew×trend 交互，persistence 过滤）。**所有 |IC| 最强的候选也只到 0.022**（abs_skew_4h → future_range），**通过门槛 (|IC|>0.03 AND per-symbol 一致性≥65%) 的候选：0**；最强候选做 Tercile mean 分档 + walk-forward 时序切分后 **top_30 vs bottom_30 差异 <0.005%、方向在 train/test 间翻转、per-contract 保留率 50%**——skew 里确实有微弱统计信息（否则不会有 IC=-0.022），但**该信息量在期货交易成本尺度（0.06%-0.30%）下完全不可用**。

## 实验设计

在 s2/s3 中共扫描了 **8 个 signed 特征 × 5 horizon + 5 个 |skew| 特征 × 6 target = 70 组 (feature, target) pair**，涵盖：

- **Category A：|skew| → 未来 |ret| 波动率预测**（假设"高|skew|意味成交极端不平衡 → 未来更高/更低波动"）
- **Category B：短窗 skew 4h/8h/24h → signed ret**（假设"12h 默认窗口太长，短窗更敏感"）
- **Category C：Δskew (1h/4h) → signed ret**（假设"skew 变化率捕获资金流转向"）
- **Category D：Cross-sectional skew rank → signed ret**（假设"跨品种相对 skew 强度"）
- **Category E：skew × sign(trend) 共振/背离**（假设"同向趋势 + 高 skew = 强化"）
- **Category F：Persistence-filtered signed skew**（假设"连续同号 skew 才是稳定信号"）
- **Category G：|skew| → future_min_ret / future_range**（假设"|skew| 预示回撤"）

判据：
- 快速版 `s2_broad_ic_scan.py` · Spearman IC pooled + 145 品种 sign consistency
- 深挖版 `s3_abs_skew_deep.py` · 对 top-3 候选做 Tercile 分档 mean、per-contract 保留率、8:2 walk-forward

## 结果矩阵

### TOP 10 |IC| 候选（所有 scan 合并）

| Rank | scan | feature | target | n | IC | per-symbol consistency |
|---:|---|---|---|---:|---:|---:|
| 1 | magnitude | `abs_skew_4h` | `future_range` | 55,587 | **-0.022** | 55.6% |
| 2 | magnitude | `abs_skew_4h` | `abs_ret_4h` | 55,288 | -0.014 | 56.9% |
| 3 | magnitude | `abs_skew_8h` | `future_range` | 55,587 | -0.014 | 56.9% |
| 4 | magnitude | `abs_skew_4h` | `abs_ret_8h` | 54,707 | -0.013 | 52.1% |
| 5 | magnitude | `abs_skew_4h` | `abs_ret_6h` | 54,997 | -0.012 | 54.2% |
| 6 | drawdown | `abs_skew_24h` | `future_min_ret` | 53,832 | +0.012 | 51.4% |
| 7 | magnitude | `abs_skew_24h` | `future_range` | 53,832 | -0.011 | 58.3% |
| 8 | magnitude | `abs_skew_8h` | `abs_ret_6h` | 54,997 | -0.011 | 56.3% |
| 9 | magnitude | `abs_skew` (12h) | `abs_ret_2h` | 55,587 | -0.010 | **61.8%** |
| 10 | signed | `skew_delta_1h` | `ret_8h` | 54,562 | +0.010 | 59.0% |

**观察**：
- 所有 top 均为 |skew| → 波动率/range 方向，**非** signed → 方向
- IC 符号一致：**负相关**——即"高 |skew| → 未来波动/range **减小**"（反直觉但符合"volume 挤在一侧 → 供需暂时锁定 → 单边稳定行走"）
- 但 IC 绝对值 <0.023，consistency 徘徊在 50-62% → 弱信息 + 广度不足
- **门槛（|IC|>0.03 AND consistency≥65%）通过：0**

### #1 候选 abs_skew_4h → future_range 深挖（s3）

Tercile mean(future_range) 分档：

| bucket (per-contract) | future_range mean | vs bottom |
|---|---:|---:|
| bottom_30 (|skew|_4h 最低 30%) | 0.01350 | — |
| middle_40 | 0.01353 | +0.2% |
| **top_30 (|skew|_4h 最高 30%)** | **0.01347** | **-0.2%** |

**差异 <0.005%**，与成本尺度 0.06-0.30% 相差 15-60 倍。

Per-contract 保留率：144 个合约中 **72 个**（50.0%）呈 "top<bot" → **完全等概率**。

Walk-forward 8:2 稳健性：

| split | top_mean | bot_mean | diff |
|---|---:|---:|---:|
| train | 0.01384 | 0.01396 | **-0.00012** |
| test | 0.01202 | 0.01171 | **+0.00030** (符号翻转) |

**结论**：Rank IC=-0.022 是**大样本量放大统计噪声的伪影**（55k+ 样本下微小系统性差异也能被 Spearman 检出），但**没有一致的均值差异、无品种保留率、无时序稳健性**——不构成可交易或可作过滤器的信号。

## 结论回答用户问题

### "skew 有没有继续挖掘的空间？"

**没有**（在本主题的验证框架下）。理由：

1. **广度已足够**：145 合约 × 33 个月 × 55,877 events 覆盖了合理的期货实盘环境；假设扩样到 200+ 合约或加入股指，也只是量级问题不改变结构
2. **正交假设已穷尽 7 大类**：signed 方向、|skew| 波动率、短窗、Δskew、cross-sectional、交互、persistence——**都没有 |IC|>0.03**
3. **信号极限已被诚实测出**：|skew|_4h → future_range 的 IC=-0.022 是**该家族的最强上限**（大样本下更小 IC 都能"显著"，但均值差在成本尺度以下）
4. **微弱信号 ≠ 可交易 alpha**：期货 hourly-event 尺度上 realistic roundtrip cost 0.06-0.30%，任何均值差 <0.05% 的信号都被成本完全吞噬

### "成交量峰度不可能不含任何信息" —— 这个直觉是**部分正确**的

**证据支持"有信息"**：
- abs_skew_4h → future_range 的 pooled IC=-0.022（p 值远小于 0.001 by 大样本量）
- Consistency 55.6%（略高于 50% 基准）
- 方向符号一致（-）

但**"含信息"与"可交易 alpha"是两个门槛**：
- 前者只需 IC 显著异于零
- 后者需 |IC| > 0.03 + consistency > 65% + 均值差可穿透成本
- 本次实验证明 skew 派生特征在期货 hourly 尺度上**卡在前一个门槛之内**

### 若真要继续，只剩这些方向（都超出本主题验证范围）

- **换到 tick / 秒级数据**：hourly bar 已经把 skew 大部分信息平滑掉了；order book imbalance / trade imbalance 在 tick 级可能有 |IC|>0.05
- **换到股票 / crypto**：期货 hourly 事件流本身噪声高，股票日内数据、crypto 5m 数据的 skew 派生可能有更强信号
- **组合成多因子 xgboost**：本次是**单变量 IC**，但如果 skew 只是 5 个因子中占 1/5 权重的输入，可能作为组合的一员有增量贡献——但那属于 ML 主题，不属于本主题的"因果 event-driven 单信号"框架

## 文件清单

- 脚本
  - [s1_skew_multi_angle.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/s1_skew_multi_angle.py) · 计算多窗 skew（4h/8h/24h）+ cluster bootstrap（未跑完，特征缓存已保存）
  - [s2_broad_ic_scan.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/s2_broad_ic_scan.py) · 70 组 (feature, target) 广度 Spearman IC + sign consistency
  - [s3_abs_skew_deep.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/s3_abs_skew_deep.py) · TOP-1 候选 tercile / per-contract / walk-forward 深挖
- 数据
  - `outputs/skew_wide/events_with_multi_skew.csv` · 55,877 events × (A3_skew, skew_4h, skew_8h, skew_24h, atr_intra, trend_intra, ret_2h..12h, cost_rt, ...)
  - `outputs/skew_wide/s2_top30.csv` · TOP-30 |IC| 结果表
  - `outputs/skew_wide/s2_passing_candidates.csv` · 通过门槛的候选（空）
