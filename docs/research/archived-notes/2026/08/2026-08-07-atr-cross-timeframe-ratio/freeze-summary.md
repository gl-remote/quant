# ATR Cross-Timeframe Ratio · 主题归档

> **归档日期**：2026-08-07
> **家族 slug**：atr-cross-timeframe-ratio
> **研究周期**：2026-08-04 ~ 2026-08-07
> **数据**：52 个中国商品期货合约，2022-05 至 2026-04，33,996 个 1h 样本
> **结论标签**：❌ 独立 alpha 证伪 · ✅ 状态/制度因子成立 · 🧪 方法论 · 🔁 转 factor-library

---

## 一句话结论

**跨周期 ATR 比值（R_bar = ATR_1h / ATR_15m）是稳健的市场状态描述因子（四象限分类、牛熊差异、板块差异、转换路径），但不是方向 alpha 因子。** 7 类方向信号（H_only confirmed、短脉冲、R_1h_d 三分位等）在 2022–2023 熊市 out-of-sample 中全部失效或翻转。因子规格已蒸馏到 factor-library。

---

## 主题冻结原因

1. **因子定位明确**：全周期数据（52 合约、4 年、含牛熊）确认 R_bar 是状态/制度因子，不是 alpha。所有方向假设已系统证伪，无未验证的方向线索值得继续投入。
2. **规格已沉淀**：definition.md / evidence.md / boundary.md 三件套已进入 factor-library/atr-cross-timeframe-ratio/，后续引用直接走因子库，不需回 workbench。
3. **最有增量的描述性发现已记录**：L_only/L_path 作为短周期压力指标是唯一值得未来探索的线索，但需要更长历史或更细数据（5m/LME 时段）才有进展，当前数据已用尽。
4. **方法论遗产完整**：7 条信号去伪流程、随机基准对照、非重叠抽样、熊市 OOS 验证、多空双向检验已形成模板，可被后续主题复用。

---

## 研究阶段一览

| Stage | 主题 | 结论 |
|---|---|---|
| Stage 1 | R_bar 分布 EDA（15m/1h） | 中位 1.82 < 理论 2.0，波动聚集确认 |
| Stage 2 | 四象限分类与基础画像 | 双压缩占 57%，共振 H_norm 高 31% |
| Stage 3 | H_only confirmed 信号（重叠样本） | +0.47%，CI 不含 0（但事后偏差） |
| Stage 4 | confirmed 分层（trend/MADEV） | MADEV<0/超卖位置收益更高（beta 嫌疑） |
| Stage 5 | 前瞻指标预测力（量/OI/跳空） | AUC 0.53 < 0.6，vol_ratio 最强但也弱 |
| Stage 6 | 非重叠抽样验证 | episode_first +1.43%（首根入场更好） |
| Stage 7 | 持续长度拆分 | short(1–2 根) +1.76% 胜率 85%（事后偏差） |
| Stage 8 | 策略原型回测（短脉冲+第3根平仓） | +0.07%，跑输随机 → 事后偏差确认 |
| Stage 9 | 止损改进回测 | SL1% +0.21% 但随机+SL 更高 → beta |
| VRP 验证 | 随机+止损真相 | 做空 -1.01%，纯多头 beta |
| F 组 | 跨期限结构（5m/15m/1h/d） | R_1h_d 方向信号熊市翻转 |
| 熊市验证 | R_1h_d 在 2022–2023 | 全部信号翻转，确认非独立 alpha |
| 全周期画像 | 52 合约四象限 | 状态分类稳健，牛熊差异显著 |
| 路径分析 | 压缩→共振路径 | H_path 65% 主流，L_path 熊市翻倍 |

---

## 关键数字

### 四象限全周期画像

| 状态 | 占比 | H_norm(%) | fwd_\|r\|₂₀(%) | 持续中位(根) |
|---|---:|---:|---:|---:|
| 双压缩 | 51.6% | 0.52 | 1.50 | 5 |
| H_only | 8.1% | 0.62 | 1.61 | 2 |
| L_only | 6.7% | 0.60 | **1.74** | 2 |
| 共振扩张 | 33.6% | **0.68** | 1.73 | 4 |

### 牛熊对比

| 指标 | 熊市(2022) | 牛市(2024-26) |
|---|---:|---:|
| 双压缩占比 | 47.9% | 57.0% |
| L_only 占比 | **8.3%** | 4.7% |
| 共振占比 | 36.4% | 28.7% |
| 平均 H_norm | 0.62–0.76% | 0.42–0.56% |

### 方向信号证伪

| 信号 | 牛市收益 | 熊市收益 | 结论 |
|---|---:|---:|---|
| H_only confirmed | +0.47% | 不可执行 | 事后偏差 |
| 短脉冲（事后） | +1.76% | +0.07%（可执行） | 事后选择 |
| H_only + SL1% | +0.21% | 随机+SL +0.27% | beta |
| R_1h_d long_short | +0.61% | **-0.44%** | 非 neutral |

---

## 方法论遗产

1. **事后分组 ≠ 可交易**：任何"按某变量分组后收益显著"的发现，必须验证该变量 t 时刻是否已知；
2. **必须有随机基准**：策略收益必须跑赢"随机入场 + 同样规则"；
3. **必须做空头测试**：只做多信号在牛市天然占优，做空检验能暴露 beta；
4. **必须熊市 OOS**：2024–26 多头数据上任何方向信号都容易显著；
5. **多空组合 ≠ market neutral**：必须在熊市验证多空组合是否翻转；
6. **非重叠抽样是必须的**：重叠 bar 高估显著性，episode_first/daily_dedup 是最低要求；
7. **描述先行**：先做全周期画像和状态分类，不急着找 alpha。

---

## 蒸馏去向

| 产出 | 位置 | 说明 |
|---|---|---|
| 因子定义 | `theorems/factor-library/atr-cross-timeframe-ratio/definition.md` | R_bar、S_H/S_L、四象限、辅助因子 |
| 因子证据 | `theorems/factor-library/atr-cross-timeframe-ratio/evidence.md` | 10 节核心数字 |
| 适用边界 | `theorems/factor-library/atr-cross-timeframe-ratio/boundary.md` | 用什么/不用什么/未验证什么 |

---

## 文件清单

```
2026-08-07-atr-cross-timeframe-ratio/
├── freeze-summary.md                      ← 本文件
├── atr-cross-timeframe-ratio-report.md     ← 完整研究报告（7 节）
├── atr-timeframe-ratio.md                 ← 原始研究设计与 stage1-2
├── atr-timeframe-ratio-related-studies.md ← 相关研究索引
└── atr-timeframe-ratio/                   ← workbench 原始目录
    ├── README.md                           ← workbench 索引
    ├── quadrant-profile.md                 ← 全周期四象限画像
    ├── transition-paths.md                 ← 转换路径分析
    ├── wrap-up-and-next-direction.md      ← 阶段性总结
    ├── stage1-distribution.md             ← 早期 EDA
    ├── scripts/                            ← 17 个分析脚本
    ├── outputs/                            ← CSV + 图表
    └── archive/h_only_signal_research/     ← 11 篇证伪文档
        ├── README.md
        ├── stage3-results.md
        ├── stage4-results.md
        ├── stage5-results.md
        ├── stage7-results.md
        ├── stage8-results.md
        ├── stage9-results.md
        ├── stage3-todo.md
        ├── stage5-todo.md
        ├── mechanism-oversold-vs-trend.md
        ├── vrp-validation-report.md
        └── term-bear-validation-archive.md
```

---

## 后续指引

- **引用因子**：直接用 `theorems/factor-library/atr-cross-timeframe-ratio/`，不需回 workbench；
- **如果未来要重启**：L_only/L_path 作为短周期压力指标是唯一值得继续的线索，需要 5m 级数据或 LME 时段数据；
- **避免重复**：7 类方向信号已全部证伪，不要重新测试 H_only confirmed / 短脉冲 / R_1h_d 方向信号；
- **方法论复用**：本主题的信号去伪流程（随机基准 + 非重叠 + 熊市 OOS + 做空检验）已形成模板，后续新因子验证应直接套用。
