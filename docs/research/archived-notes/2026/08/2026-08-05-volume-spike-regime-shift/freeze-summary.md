# 2026-08-05 · volume-spike-regime-shift 归档摘要

> 批次：`archive:2026-08-05-volume-spike-regime-shift`
> 家族：`volume-spike`
> 结论标签：❌ 独立 alpha 证伪 / ✅ 条件因子成立 / 🧪 方法论遗产 / 🔁 转 factor-library

---

## 1. 归档对象

本批次归档 2026-08-05 完成的成交量放量主题研究：

- 主题长期文档（原 `docs/research/themes/volume-spike-regime-shift/`）：README、research-status、findings、conditioner、skew spec、implementation notes、archive references、figures；
- workbench 实验流水（原 `docs/workbench/volume-spike-regime-shift/`）：r1 stages、daily、1h recalibration、factor interaction、r2、r1 specs、scripts、outputs。

稳定蒸馏保留在：[factor-library/volume-spike/](../../../../theorems/factor-library/volume-spike/definition.md)。

---

## 2. 最终结论

成交量放量不是独立 alpha，也不是趋势反转开仓信号；它是一个**条件过滤器**：

> 当价格远离长期均线（MADEV）且处于强趋势（$|s_{\text{pre}}|\ge0.10$）时，极端放量（同时段 z-score $Z\ge2.5$）触发价格向均线回归。

高 s_pre 上涨趋势中：

- $Z\ge2.5$ 且 MADEV120 位于该层 67% 分位以上：未来 100 根 1h bar mean ≈ −2.66%，约 69% 下跌，IC≈−0.77；
- 但这是相对 baseline 跑输，不保证绝对下跌；裸空日线信号扣成本后亏损。

低 s_pre 下跌趋势中存在镜像：

- $Z\ge2.5$ 且 MADEV120 位于该层 33% 分位以下：mean ≈ +4.17%，约 96% 上涨，但 n=24，证据较弱。

MADEV 是主导变量：高 s_pre 样本消融 R² 中，MADEV only=0.118，Z only=0.054，Skew only≈0.001；Z+MADEV=0.143，加入 Skew 仅到 0.153。

---

## 3. 已证伪/撤回

| 命题 | 结论 |
|---|---|
| 放量本身导致未来波动/不确定性放大 | 控制 MADEV 后 $Z$ 对 $|r_{100}|$ 不显著；高偏离下方差伴随放大但非主效应 |
| 全时段 z-score 可直接使用 | 75% spike 集中在开盘 bar，必须使用同时段 z-score |
| 左尾风险 ES5 信号 | N=20 短窗 artefact；N≥60 后消失 |
| 裸空 volume spike 可盈利 | 日线毛收益约 +0.16%，扣成本净 −103bps |
| 熊市放量反弹（旧结论） | baseline 选择偏差；只按 s_pre 看不显著，按 MADEV 分层后才出现镜像回归 |
| PATEFF 高=平滑下跌续跌 | 同 regime baseline 后方向相反：高 PATEFF + 放量反弹更强 |
| 30 个因子各自被成交量调节 | 30 个翻转本质是 MADEV 一个维度的投影，PCA PC1 占 41% |

---

## 4. 保留的实践知识

- 同时段 hour-of-day z-score 是商品期货成交量异常的必要口径；
- 事件研究必须使用同 regime baseline，否则会得到假的熊市反弹；
- LOPO 品种留一是必过门槛；
- MADEV 是比 raw return / s_pre 更干净的价格位置变量；
- 一阶矩 mean shift 主导二阶矩 variance expansion；
- Volume Profile Skew 只能作为弱置信度过滤器，不能作为独立信号。

---

## 5. 重启条件

满足任一条件可重启，不需要重复 r1/r2 已证伪方向：

1. ~~获得 OI（持仓量）数据，可区分放量增仓 vs 放量减仓~~ → 已在后续批次 `archive:2026-08-06-volume-spike-oi` 检验，结论为当前数据范围内 OI 过滤器证伪；
2. 获得更长历史（建议覆盖 2020–2023）或更多品种，解决样本量和年度衰减；
3. 将该过滤器叠加在基础趋势策略上，完成 walk-forward 组合 P&L 回测；
4. 获得 tick/订单流数据，可区分主动买卖方向。

---

## 6. 文件索引

- 核心发现：`volume-spike-trend-exhaustion-1h-daily-findings.md`
- 一般化机制：`volume-as-factor-conditioner.md`
- Skew 数学规格：`volume-spike-skew-spec.md`
- 关键发现清单：`research-status.md`（KF-1 至 KF-31）
- r1/r2 原始报告和脚本：`raw-workbench/`
- 项目数据产出：`raw-outputs/`，共 38 个文件、约 11MB；文件清单和 MD5 见 [`raw-outputs-manifest.json`](raw-outputs-manifest.json)
  - 包含 stage0–stageA、1h calibration、daily OOS、r2 主数据集、skew events、路径数据等 JSON/CSV/Parquet/NPZ 产物；
  - 原路径 `project_data/research/volume-spike-regime-shift/` 已清空并移除；
  - 复现注意：归档脚本仍保留原始输出路径，若重跑会重新创建 `project_data/research/volume-spike-regime-shift/`，需要手动将新产物与本批次 `raw-outputs/` 对齐。
- 因子库蒸馏：`theorems/factor-library/volume-spike/`
