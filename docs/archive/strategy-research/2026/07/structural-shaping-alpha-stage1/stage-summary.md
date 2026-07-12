# structural-shaping-alpha 阶段 1 · Stage Summary

> 类型：Archive Stage Summary
> 主题：`theme:structural-shaping-alpha`
> 批次：`archive:2026-07-06-structural-shaping-alpha-stage1`
> 判决：❌ 主假设证伪 · 🧪 9 条 KF + 工具遗产
> 完成日期：2026-07-06

## 1. 阶段 1 判决

**核心问题**："结构塑形技巧本身是否具有独立 alpha？"

**判据**：experiment-plan §0.6 · 至少 1 个 combo mean 净值显著 > 0（成本后）且显著优于 E 基准，或 Sharpe/Sortino 显著优于 E 或 MDD 显著降低。

**结果**：

- **5m × SCALE=1 + realistic-cost**：7 个行业共识 combo (A-F/D2) 全部 mean ≈ -2c，未通过 mean 显著正判据
- **5m × SCALE=5 + realistic-cost**：L/M/N 三个探索性 combo mean 严格 > 0（+0.312 / +0.306 / +0.472）且 paired CI 排除 0，**但 median 严重负（-7.6 ATR）+ stop=7.5 ATR 对应账户风险 13-15%（超出 framework §5 预算 3%）**，即"数学正 edge ≠ 工业可用 alpha"
- **15m × SCALE=1 跨周期复核**：
  - M mean=-0.181，vs E p=0.970（**显著劣**于 E）→ 5m×SCALE=5 是伪影
  - N mean=-0.144，方向负但不显著 → 5m×SCALE=5 是伪影
  - L mean=+0.041，vs E p=0.060（接近显著） → **唯一保留**
- **$\nu_{\text{implied}}$ 反算**：L / M / N / A 所有场景 $|\nu/\sigma| \le 0.04$ → **martingale 恒等式在实测精确成立**，所有正 mean 都是 Itô 凸性 + 时间尺度放大 + 采样噪声，无真实市场漂移

**综合判决**：主假设"结构塑形独立 alpha"**证伪**，L combo 保留为"跨周期 tail 探索候选"（阶段 2b 拉起时可再验证）。

## 2. 关键发现清单（KF-1 ~ KF-9）

完整定义在 `kf:structural-shaping-alpha#KF-N`。此处只列一句话摘要 + 证据入口。

| KF | 一句话结论 | 类型 | 证据 |
|----|-----------|------|------|
| KF-1 | 结构塑形在 no-signal 下无独立 alpha（$E[\text{gross}] \equiv 0$）| 策略行为 · 假设证伪 | §2-3 · §8.7 |
| KF-2 | Trailing 分两类：急性负 edge · 延迟中性偏正 | 策略行为 | §8.9-8.10 |
| KF-3 | Trailing 组合机械诊断准则（armed/缓冲/止盈三元组）| 方法论 | §4 |
| KF-4 | "少输"型 paired 显著性 ≠ 独立 alpha | 方法论 | §8.6 |
| KF-5 | 扁平 ATR 成本模型跨品种低估 4.5 倍 | 方法论 | §8.7 |
| KF-6 | 近距首达定理支配 · 远距可捕获 tail 但样本极偏 | 策略行为 · 方法论 | §8.10 |
| KF-7 | 5m×SCALE=5 tail alpha 是重采样伪影（15m 复核）| 方法论 | §8.11 |
| KF-8 | "数学正 edge" ≠ 工业可用 alpha（四道账户闸门）| 方法论 | §8.10 |
| KF-9 | 归因必须用 $\nu = \mu - \sigma^2/2$，不能用 $\mu$ | 方法论 | `first-passage-lookup-tables.md` 表 5 |

§引用指向本批次的 `stage1-gatekeeper-report.md` 相应章节。

## 3. 工具遗产

**First-Passage Designer**：GBM 首达定理的解析计算工具。

- 数学 spec：`theme:structural-shaping-alpha#first-passage-designer-math-spec`
- 代码 v1（本批次副本）：`raw-scripts/first_passage_designer.py`（470 行 · 6 条自检通过）
- 对照表（本批次副本）：`first-passage-lookup-tables.md`（5 张表）

**能力**：给定 $(K_S, K_T, T, \mu, \sigma, c)$，秒级输出 $P_{\text{win}}, E[\text{gross}], E[\text{net}], E[\tau], T^*, \mu^*, [K_T^{\min}, K_T^{\max}], f_{\text{Kelly}}, \mu_{\text{implied}}$。

**主要用途**：未来任何 combo 参数在实测前用工具做数学预筛（μ=0 下 $E[\text{net}]$ 若显著负则直接淘汰，无需实测）。

## 4. 阶段 2 前置条件

experiment-plan v2.2 已重构阶段 2 为"塑形受益条件扫描"：

- **2a · 方向 alpha × 塑形**：需要外部方向 alpha 主题产出 baseline（**未就绪**）
- **2b · 跨周期 tail × 塑形**：需要 1h+ 数据 fetch（**部分就绪**，15m 已跑）
- **2c · 波动率制度 × 塑形**：数据现成，**立即可跑**

主题保留在 `themes/`，等外部触发条件满足后可拉起对应子分支。

## 5. 与关联批次的关系

- **archive:2026-06-29-structural-alpha-random-baseline**：继承 DirRandom 采样定义，是本批次的方法论上游
- **archive:2026-07-05-value-area-rolling-reacceptance-freeze**：value-area 家族证伪批次，本批次与之正交（结构塑形独立 alpha vs 触发器均值回归）；继承四大方法论约束（ATR / 期望净值 / cluster bootstrap / 多层对照）

## 6. 复现指引

- 数据采样脚本：`raw-scripts/structural_shaping_gatekeeper.py`（5m）· `raw-scripts/structural_shaping_gatekeeper_15m.py`（15m）
- 数据文件（未含入 archive，位置）：`project_data/research/structural_shaping_gatekeeper/`
- 首达定理对照表脚本：`raw-scripts/first_passage_designer.py`
- 若需重跑：`python raw-scripts/structural_shaping_gatekeeper.py --scale 1|3|5 [--flat-cost-debug]`
