# poc-value-area-asymmetry · 参数选择规格

> 类型：Theme / 参数选择与性能报告（配置值唯一源）
> 状态：**v4.0（2026-07-08）· 阶段 4 v9.1 收尾 · 6 类合并版冻结**
> 主题 README：[README.md](README.md)
> 数学契约：[classifier-math-spec.md](classifier-math-spec.md)
> 研究状态：[research-status.md](research-status.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)

## 1. 契约边界

**本文件承载**：
- ✅ 分类器所有具体参数值（rolling 窗口 · skew/atr/trend 分位边界）
- ✅ Tier 集合的具体定义（多头/空头 · skew×ATR×trend 组合）
- ✅ 白名单分级（A / A-）+ 性能指标（mean · IR · 品保 · 时稳）
- ✅ 版本变更记录

**不承载**：
- ❌ 数学定义（→ [classifier-math-spec.md](classifier-math-spec.md)）
- ❌ 完整策略层面（入场 · 出场 · 仓位 · 成本）

## 2. 参数值（v4.0 冻结）

### 2.1 Rolling 窗口

| 参数 | 值 | 说明 |
|:---:|:---:|:---|
| `n_rolling_events` | 100 | signed_skew_rank rolling 窗口 |
| `n_rolling_days` | 20 | ATR / trend rolling 窗口 |
| `n_atr_lookback` | 10 | ATR 计算窗口 |
| `n_trend_lookback` | 10 | trend_ret 计算窗口 |
| `n_warmup_days` | 20 | Warmup 门槛 |
| `n_transition_window_days` | 3 | Regime transition 判定窗口 |

### 2.2 制度分档阈值

| 维度 | 分档 | 阈值 |
|:---:|:---|:---|
| **ATR regime** | 低 / 中 / 高 | rank ≤ 0.33 / (0.33, 0.67) / ≥ 0.67 |
| **Trend regime** | 跌 / 平 / 涨 | rank ≤ 0.20 / (0.20, 0.75) / ≥ 0.75 |

## 3. Tier 集合

### 3.1 v3.0（10 互斥 tier · 过渡版 · 保留作诊断证据）

见 archive:2026-07-08-poc-va-asymmetry#stage4-classifier-v4 §2.4（v3.0 白名单表）。**不建议下游策略引用 v3.0** · 已被 v4.0 取代。

### 3.2 v4.0（6 类合并版 · 阶段 4 v9.1 收尾冻结）⭐

**多头 3 类**（trend ≥ 0.75）：

| Tier ID | skew range | ATR range | trend range | 覆盖 144 tier 通过格 |
|:---:|:---:|:---:|:---:|:---|
| **L_seg3_lowmid_up** | (0.09, 0.30] | ≤ 0.67 | ≥ 0.75 | L2_Amid + L3_Alow + L3_Amid |
| **L_seg12_high_up**  | [0, 0.19]   | > 0.67 | ≥ 0.75 | L1_Ahigh + L2_Ahigh |
| **L_seg2_low_flat**  | (0.09, 0.19] | ≤ 0.33 | (0.20, 0.75) | L2_Alow_Tflat |

**空头 3 类**（trend ≤ 0.20 除 L_seg2_low_flat 外）：

| Tier ID | skew range | ATR range | trend range | 覆盖 144 tier 通过格 |
|:---:|:---:|:---:|:---:|:---|
| **S_seg12_high_dn**  | [0.81, 1]   | > 0.67 | ≤ 0.20 | S1_Ahigh + S2_Ahigh |
| **S_seg34_high_dn**  | (0.60, 0.81] | > 0.67 | ≤ 0.20 | S3_Ahigh + S4_Ahigh |
| **S_seg2_mid_dn**    | (0.81, 0.91] | (0.33, 0.67) | ≤ 0.20 | S2_Amid_Tdn |

**互斥性**：6 类之间在 (skew × ATR × trend) 三维空间内**完全互斥**，同一事件最多命中 1 类。

## 4. 白名单（v4.0 · 3 period 严格验证）

### 4.1 A 级（L1-L4 全过 ∧ 时稳 ≤ 0.50）· 9 个

| Tier·Period | 方向 | n | mean bps | CI 95% | p_boot | 品保 | IR | 时稳 |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| L_seg3_lowmid_up · stable | 多 | 647 | +31.2 | [+11.8, +50.7] | 0.00040 | 63% | +0.26 | 0.26 |
| L_seg12_high_up · trans   | 多 | 395 | +57.7 | [+36.1, +80.4] | 0.00000 | 76% | +0.47 | 0.02 |
| L_seg2_low_flat · full    | 多 | 851 | +18.3 | [+4.9, +31.8]  | 0.00760 | 65% | +0.17 | 0.01 |
| **S_seg12_high_dn · full**   | 空 | 1053 | +31.4 | [+22.5, +40.4] | 0.00000 | 73% | +0.35 | 0.29 |
| **S_seg12_high_dn · stable** | 空 | 574  | +26.8 | [+16.2, +38.4] | 0.00000 | 71% | +0.34 | 0.27 |
| **S_seg12_high_dn · trans**  | 空 | 479  | +37.1 | [+22.0, +52.1] | 0.00000 | 67% | +0.37 | 0.44 |
| S_seg34_high_dn · full    | 空 | 776 | +37.1 | [+22.5, +52.5] | 0.00000 | 73% | +0.32 | 0.43 |
| S_seg2_mid_dn · full      | 空 | 367 | +23.2 | [+9.2, +39.0]  | 0.00080 | 74% | +0.29 | 0.13 |
| S_seg2_mid_dn · trans     | 空 | 242 | +24.5 | [+7.2, +44.0]  | 0.00440 | 74% | +0.32 | 0.50 |

**⭐ S_seg12_high_dn 三 period 全 A** —— 阶段 4 v4.0 最铁的复合信号。

### 4.2 A- 级（L1-L4 全过 · 时稳超标）· 6 个

| Tier·Period | 方向 | n | mean bps | 时稳 | 备注 |
|:---|:---:|:---:|:---:|:---:|:---|
| L_seg3_lowmid_up · full   | 多 | 1336 | +30.5 | 0.97 | 大样本 · 时稳边缘 |
| L_seg3_lowmid_up · trans  | 多 | 689  | +29.9 | 1.98 | 时稳强警示 |
| L_seg12_high_up · full    | 多 | 710  | +45.5 | 0.91 | 边缘时稳 |
| L_seg2_low_flat · trans   | 多 | 280  | +37.3 | 0.66 | 平稳期渗透 |
| S_seg34_high_dn · stable  | 空 | 417  | +25.3 | 0.55 | 边缘时稳 |
| S_seg34_high_dn · trans   | 空 | 359  | +50.8 | 0.74 | 转换期强空头 |

### 4.3 Fail（3 个）

| Tier·Period | 方向 | mean bps | 主要原因 |
|:---|:---:|:---:|:---|
| L_seg12_high_up · stable | 多 | +30.3 | CI 越 0 · p=0.16 |
| L_seg2_low_flat · stable | 多 | +8.9  | CI 越 0 · mean 太低 |
| S_seg2_mid_dn · stable   | 空 | +20.7 | CI 越 0 · p=0.08 · 样本 125 |

## 5. 多重比较校正

**主判据**：Bonferroni family=6 · α = 0.05/6 ≈ **0.00833**
- v4.0 · 15/18 通过（9 A + 6 A- · 3 fail）
- 相比 v3.0（family=15）· v4.0 更严格但**通过率更高**（合并降级效应 · KF-29）

**Sanity check**：FDR (BH) α=0.05 · BH 阈值 p ≤ 0.00960
- 15 个通过 · 与 Bonferroni family=6 结果一致（差 1 · L_seg2_low_flat·trans）

**独立采样单位**（KF-22）：`(contract, date)` cluster · rank 单位 per-contract

## 6. 数据源

- **Step 3 严格验证数据**：`project_data/logs/poc_va_asymmetry_stage4/stage4_6class_merged_verification.csv`
- **144 tier 诊断证据**：`project_data/logs/poc_va_asymmetry_stage4/stage4_step3_144tier_verification.csv`
- **描述性扫描**：`project_data/logs/poc_va_asymmetry_stage4/stage4_step2_144tier_descriptive.csv`
- **扩容数据集**：`project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet`
  - 143 合约 · 36625 events · 20 品种前缀 · 2023-09 → 2026-06

## 7. 变更记录

| 版本 | 日期 | 变更 |
|:---:|:---:|:---|
| v3.0 | 2026-07-08 | 阶段 4 首版 · 10 互斥 tier · family=15 · A 6 + A- 3（过渡版） |
| **v4.0** | 2026-07-08 | 阶段 4 v9.1 收尾 · **6 类合并版** · family=6 · A 9 + A- 6 · KF-29 定型 |

## 8. 下游使用指南

**推荐引用顺序**：
1. **首选**：S_seg12_high_dn（三 period 全 A · 最铁）
2. **次选**：L_seg3_lowmid_up · S_seg34_high_dn · S_seg2_mid_dn（多个 period 通过）
3. **有条件用**：L_seg12_high_up（trans 强 · stable 弱）· L_seg2_low_flat（平稳期唯一）

**时稳警示**：A- 级 tier 需要下游策略层做时段过滤或分周期建模 · 避免时点漂移。

**品种筛选**：分类器承诺"整体信号存在" · 不承担品种选择 · 详见 KF-24（品种异质性）。
