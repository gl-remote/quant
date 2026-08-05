# Volume Spike · Trend Exhaustion

> **状态：已归档（2026-08-05）**。核心机制已确认并蒸馏到因子库：[factor-library/volume-spike/](../../../../theorems/factor-library/volume-spike/)。
>
> **结论定位**：该因子不是独立交易策略，也不是趋势反转开仓信号；它适合作为已有趋势策略的减仓/止盈过滤器。裸空已证伪，震荡市无效，2026 年放量端衰减，单品种样本不足，OI/订单流未验证。重启条件见 [freeze-summary.md](freeze-summary.md)。
>
> **主题定位**：研究成交量异常如何与前期趋势交互，以及成交量水平如何调节因子预测方向。

---

## 核心结论

在高市场强度上涨趋势中（s_pre≥0.10），价格偏离长期均线（MADEV120）是核心驱动变量：

- **放量（z≥1.5）+ 高 MADEV** → 均值回归：mean −2.33%，P(r<−3%)=35%，IC=−0.4；
- **缩量（z<−0.5）+ 高 MADEV** → 趋势延续：mean +1.84%，P(r>+3%)=22%，IC=+0.2；
- 放量本身不增加不确定性（控制 MADEV 后 β_z 对 |r| 不显著），但在高偏离条件下伴随方差放大（+0.76%）；
- 一阶矩（均值漂移 −4.16%）主导，是二阶矩（标准差变化 +0.76%）的 5.5 倍；
- 机制：价格偏离均线后的均值回归，不是"趋势强度 exhaustion"（s_pre 控制 MADEV 后残差 IC 翻正）。

---

## 文档地图

| 文档 | 角色 |
|------|------|
| **[volume-spike-trend-exhaustion-1h-daily-findings.md](volume-spike-trend-exhaustion-1h-daily-findings.md)** | **主文档**：放量事件发现、s=ν/σ 机制、参数高原、均值回归路径 |
| **[volume-as-factor-conditioner.md](volume-as-factor-conditioner.md)** | **一般化文档**：成交量调节因子方向、30 因子→1 维度（MADEV）、一阶/二阶矩分解、含 3 张图 |
| [research-status.md](research-status.md) | 当前结论、KF-1–KF-31 清单 |
| [freeze-summary.md](freeze-summary.md) | 归档摘要、证伪项、重启条件 |
| [implementation-notes.md](implementation-notes.md) | 工程实现笔记 |
| [archive-references.md](archive-references.md) | 相关归档引用 |
| [figures/](figures/) | 3 张核心图（均值漂移 vs 方差、回归路径、尾部概率） |

---

## Workbench 目录

所有中间报告、脚本、r2 分析在本批次的 [`raw-workbench/`](raw-workbench/)：

```
volume-spike-regime-shift/
├── r1-stages/          # Stage 0–8 + A 共 11 份阶段报告
├── r1-specs/           # 原 strategy-math-spec、parameter-selection-spec、experiment-plan
├── r2/                 # r2 结果、深度分析、实验计划（3 份）
├── daily/              # 日线放量反转报告
├── 1h-recalibration/   # 日线 OOS、1h 参数敏感性、OOS、N×H 矩阵
├── factor-interaction/ # 动量/反转/波动率/流动性因子 × 放量交互
├── scripts/            # 30+ 可复现脚本（含 r2_*.py）
└── outputs/            # 中间 parquet/csv
```

---

## 命名引用

```markdown
archive:2026-08-05-volume-spike-regime-shift
archive:2026-08-05-volume-spike-regime-shift#freeze-summary
archive:2026-08-05-volume-spike-regime-shift#volume-as-factor-conditioner
```
