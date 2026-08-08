# 冻结总结：跨周期波动率比蕴含市场强度

> 归档日期：2026-08-08
> 研究周期：2026-08-07 ~ 2026-08-08
> 来源：从 ATR 跨周期比值研究衍生（[2026-08-07-atr-cross-timeframe-ratio](../2026-08-07-atr-cross-timeframe-ratio/)）
> 结论标签：**✅ 理论框架成立 · ⚠️ 无条件验证失败 · 🔄 条件性应用待后续验证**

---

## 1. 研究起源

从 ATR 跨周期比值（R_bar）研究衍生的新方向。原始研究确认 R_bar 是描述性状态因子，但用户提出假设："高跨期波动率比值说明长周期波动率远大于短周期，至少存在一个特定周期市场强度是高的"。

由此展开纯数学推导，试图建立"R 高 → 存在可盈利塑形周期 c"的理论框架。

---

## 2. 核心结论

### 2.1 理论侧

| 成果 | 内容 |
|------|------|
| 主定理 | $R > R_{\text{GBM}} \Rightarrow \exists\, c: H(c) > 1/2$（积分中值定理，纯数学） |
| 子区间非平凡版本 | 定理 4.7-4.8：充要条件 + Lipschitz 闭合 |
| 存在性到可盈利的鸿沟 | §11：标量 r 无法约束函数 H(τ)，需形状假设 |
| 假设谱系 | P0 恒定 / P1 Lipschitz / P2 单调 / P3 多区间 / P4 贝叶斯 |

### 2.2 实证侧

| 尺度 | R > GBM 占比 | P1 覆盖率 | H 曲线形状 |
|------|-------------|-----------|-----------|
| 5m/15m/1h | 19.3% | 0% | 前平后翘 |
| 1h/1d | **75.3%** | **27.8%** | **U 型** |

**P0/P1/P2 在两个尺度下均被拒绝**（无形状假设普遍成立），但 1h/1d 的 P1 跨品种比 5.09（< 10）、覆盖率 27.8%（> 5%），有条件性应用价值。

### 2.3 可盈利条件

**当 R(1h,1d) > 4.90 且 H(1h,2h) > 0.6 时，4h 周期塑形有 27.8% 基率可盈利。**

- R(1h,1d) > 4.90：保证存在 c 使 H(c) > 0.5（主定理）
- H(1h,2h) > 0.6：筛选 U 型左臂高，预测右臂也高
- c = 4h：几何中点附近，H(4h,1d) 均值 0.52

### 2.4 条件性应用框架

不要求形状假设普遍成立，用筛选因子 z 识别"假设成立区" Z：

$$r > r^\ast \;\wedge\; \mathbf{z} \in \mathcal{Z} \;\Rightarrow\; H(c) > H^\ast(c) \quad \text{在子集内成立}$$

验证准则：提升比 λ > 2。待验证假设清单 H1-H5（见 application.md §4.5）。

---

## 3. 方法论要点

1. **纯数学先行**——主定理用积分中值定理，不依赖 fBm 单一 H 假设
2. **平凡性诊断**——发现单区间下主定理是定义自洽（H(15m,1h) = ln(R_bar)/ln(4)）
3. **多尺度实证**——5m/15m/1h 和 1h/1d 两个尺度范围对比
4. **假设谱系**——从强（P0 恒定）到弱（P4 贝叶斯）的完整假设梯度
5. **思路转变**——从"无条件验证"到"条件性应用"，把函数估计问题降为分类问题

---

## 4. 文件清单

### 4.1 核心文档

| 文件 | 内容 |
|------|------|
| [cross-timeframe-vol-ratio-implies-market-strength.md](cross-timeframe-vol-ratio-implies-market-strength.md) | 理论主文档（v0.3）：主定理、子区间版本、鸿沟分析 |
| [hurst-shape-assumptions-testability.md](hurst-shape-assumptions-testability.md) | 假设检验蓝图：P0-P4 假设谱系、可证伪预言、检验设计 |
| [hurst-shape-experiment-design.md](hurst-shape-experiment-design.md) | 实验设计：数据筛选、样本独立性、多尺度估计、6 步执行 |
| [hurst-vs-rbar-briefing.md](hurst-vs-rbar-briefing.md) | 实证简报（v0.4）：散点分析、分叉点量化、跨尺度对比、条件性应用框架 |

### 4.2 脚本

| 文件 | 位置 | 内容 |
|------|------|------|
| rbar_event_count.py | raw-workbench/scripts/ | 样本量统计 |
| hurst_vs_rbar_scatter.py | raw-workbench/scripts/ | Hurst 与 R_bar 散点图 |
| h_curve_overlay.py | raw-workbench/scripts/ | H 曲线叠加对比图 |
| step3_6_assumption_test.py | raw-workbench/scripts/ | 5m/15m/1h 尺度 P0/P1/P2 检验 |
| h1_d1_assumption_test.py | raw-workbench/scripts/ | 1h/1d 尺度 P0/P1/P2 检验 |

### 4.3 输出

| 目录 | 内容 |
|------|------|
| raw-workbench/outputs/rbar_event_count/ | 样本量统计结果 |
| raw-workbench/outputs/hurst_vs_rbar/ | 散点图（3 张） |
| raw-workbench/outputs/h_curve_overlay/ | H 曲线叠加图（4 张） |
| raw-workbench/outputs/p1_assumption_test/ | 5m/15m/1h 检验结果（JSON + 报告 + 5 张图） |
| raw-workbench/outputs/h1_d1_assumption_test/ | 1h/1d 检验结果（3 张图） |

---

## 5. 因子库更新

本研究的成果已蒸馏到因子库：

- **[application.md](../../theorems/factor-library/atr-cross-timeframe-ratio/application.md)**：新增，记录因子的应用条件与可盈利门槛
- 因子库 README 更新：三件套扩展为四件套（application 可选）
- 因子索引表更新：atr-cross-timeframe-ratio 状态标记为"已归档 + 应用条件"

---

## 6. 后续工作（独立项目）

| 方向 | 内容 | 触发条件 |
|------|------|---------|
| 筛选因子验证 | 按 H1-H5 假设清单执行 | 本研究冻结后 |
| 4h 塑形策略原型 | 若找到 λ > 2 的 Z | 筛选验证成功后 |
| 成本参数校准 | 实际交易成本下的 H* 重新计算 | 策略原型前 |

---

## 7. 与已有研究的关系

| 研究 | 关系 |
|------|------|
| [2026-08-07-atr-cross-timeframe-ratio](../2026-08-07-atr-cross-timeframe-ratio/) | 上游：R_bar 作为描述性因子的证据基础 |
| [structural-shaping-alpha](../../theorems/structural-shaping-alpha/) | 理论根基：市场强度 s、Hurst 演化、barrier 塑形 |
| [volume-spike](../../theorems/factor-library/volume-spike/) | 方法论借鉴：筛选因子思路（s_pre + MADEV） |
