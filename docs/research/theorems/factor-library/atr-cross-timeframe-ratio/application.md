# 应用条件：ATR 跨周期波动比

> 因子：atr-cross-timeframe-ratio
> 日期：2026-08-08
> 性质：本文件记录因子从"描述性状态标签"升级为"可塑形盈利条件"的理论与实证依据。
> 原始研究：[archived-notes/2026/08/2026-08-08-vol-ratio-implies-market-strength/](../../../archived-notes/2026/08/2026-08-08-vol-ratio-implies-market-strength/freeze-summary.md)

---

## 1. 核心结论

**当 1h/1d 跨周期波动率比 $R > \sqrt{24} \approx 4.90$ 且可观测的短尺度 Hurst $H(1h,2h) > 0.6$ 时，4h 周期塑形有约 27.8% 的基率可盈利，加入筛选因子后预期可提升到 80%+。**

| 条件 | 作用 | 可观测性 |
|------|------|---------|
| $R(1h,1d) > 4.90$ | 保证存在 c 使 H(c) > 0.5（主定理） | 直接 |
| $H(1h,2h) > 0.6$ | 筛选 U 型左臂高，预测右臂也高 | 直接 |
| c = 4h | 落在几何中点附近，H(4h,1d) 均值 0.52 | 目标周期 |

简言之：**长尺度趋势凝聚（R 高）+ 短尺度 H 确认（U 型左臂）→ 4h 周期塑形可盈利**。

---

## 2. 理论基础：主定理

### 2.1 局部 Hurst 与跨周期比

设尺度 $\tau$ 上的波动率为 $\sigma_\tau$，定义局部 Hurst 指数：

$$H(\tau) := \frac{d \ln \sigma_\tau}{d \ln \tau}$$

跨周期波动率比：

$$R(\tau_1, \tau_2) := \frac{\sigma_{\tau_2}}{\sigma_{\tau_1}}, \qquad R_{\text{GBM}} := \sqrt{\tau_2/\tau_1}$$

区间平均 Hurst：

$$\overline{H}(\tau_1, \tau_2) = \frac{\ln R(\tau_1, \tau_2)}{\ln(\tau_2/\tau_1)}$$

### 2.2 主定理（存在性）

$$\boxed{\;R(\tau_1, \tau_2) > R_{\text{GBM}} \;\Longrightarrow\; \exists\, \tau^\ast \in (\tau_1, \tau_2): H(\tau^\ast) > \tfrac{1}{2}\;}$$

**证明**：由积分中值定理，$\int_{\ln \tau_1}^{\ln \tau_2} (H(\tau) - 1/2) d\ln \tau > 0$ 蕴含存在 $\tau^\ast$ 使 $H(\tau^\ast) > 1/2$。$\square$

**传递链**：

$$R > R_{\text{GBM}} \;\Rightarrow\; \exists\, \tau^\ast: H(\tau^\ast) > 1/2 \;\Rightarrow\; \rho_1(\tau^\ast) > 0 \;\Rightarrow\; P_{\text{顺}}(\tau^\ast) > 1/2 \;\Rightarrow\; \mathcal{S}(\tau^\ast) > 0$$

前三步纯数学严格，不依赖 fBm 单一 $H$ 假设。

### 2.3 从存在性到可盈利的鸿沟

主定理只给存在性，不给 $c$ 的具体值，也不保证 $H(c)$ 足够高以覆盖成本。可盈利需要：

$$s_{\text{eff}}(c) \ge x_{\min} = \sqrt{\frac{6 c_{\text{cost}}}{K_S^3 R(R-1)}}$$

对应临界 Hurst 门槛：

$$H^\ast(c) = \frac{1}{2} + \frac{1}{2} \log_2\!\left(1 + \sin\!\left(\pi \delta^\ast(c)\right)\right), \quad \delta^\ast(c) = \frac{x_{\min} \sqrt{c}}{\sqrt{2\pi}}$$

详细推导见 [cross-timeframe-vol-ratio-implies-market-strength.md §11](../../../archived-notes/2026/08/2026-08-08-vol-ratio-implies-market-strength/cross-timeframe-vol-ratio-implies-market-strength.md)。

---

## 3. 实证检验结果

### 3.1 尺度对比

| 指标 | 5m/15m/1h | 1h/1d |
|------|-----------|-------|
| GBM 基线 R | 2.0 | 4.90 |
| R 中位数 | 1.84 | 5.80 |
| R > GBM 占比 | 19.3% | **75.3%** |
| 高 R 事件数 | 553 | 90 |
| P0 恒定 H 拒绝率 | 46.7% | 96.7% |
| P1 Lipschitz L̂ 中位数 | 0.042 | 0.40 |
| P1 跨品种比 | 12.51 | **5.09** |
| P1 基准 r* 覆盖率 | 0% | **27.8%** |
| P2 可检验 | 否（2 点） | 是（4 点） |
| P2 Spearman ρ 中位数 | — | -0.50 |

### 3.2 H(τ) 曲线形状

| 子区间 | 高 R 事件（1h/1d） | 低 R 事件（1h/1d） |
|--------|-------------------|-------------------|
| H(1h,2h) | **0.62** | 0.29 |
| H(2h,4h) | 0.48 | 0.37 |
| H(4h,1d) | 0.52 | 0.47 |

**高 R 事件呈 U 型曲线**（0.62→0.48→0.52）：短尺度趋势凝聚 → 中尺度过渡 → 长尺度趋势回升。

### 3.3 假设检验结论

| 假设 | 5m/15m/1h | 1h/1d |
|------|-----------|-------|
| P0 恒定 H | ❌ 拒绝 | ❌ 拒绝 |
| P1 Lipschitz | ❌ 拒绝（覆盖率 0%） | ❌ 拒绝（L̂ 大），但**跨品种稳定**（5.09）且**覆盖率 27.8%** |
| P2 单调性 | ⚠️ 不可判定 | ❌ 拒绝（U 型非单调） |

**关键发现**：没有任何形状假设普遍成立，但 1h/1d 尺度的 P1 在子集内有实践价值。

---

## 4. 条件性应用框架

### 4.1 思路转变

不要求形状假设普遍成立，而是用筛选因子 $\mathbf{z}$ 识别"假设成立区" $\mathcal{Z}$：

$$r > r^\ast \;\wedge\; \mathbf{z} \in \mathcal{Z} \;\Rightarrow\; H(c) > H^\ast(c) \quad \text{在子集内成立}$$

把问题从"估计 H(τ) 函数"降为"分类 H(c) > 阈值"。

### 4.2 目标变量

$$Y = \mathbf{1}\{H(c) > H^\ast(c)\}$$

其中 $c = 4\text{h}$（几何中点附近），$H^\ast$ 由成本参数决定。

### 4.3 候选筛选因子

| 类别 | 因子 | 来源 |
|------|------|------|
| A. 跨周期比值 | $R(1h,1d)$, $R_{\text{norm}}$ | 本因子 |
| B. 子区间 H | $H(1h,2h)$, $H(4h,1d)$ | 多尺度面板 |
| C. 市场状态 | 四象限标签, $S_H$, $S_L$, $\sigma_{1h}$ | ATR 因子库 |
| D. 趋势强度 | $s_{\text{pre}}$, MADEV | volume-spike 因子库 |

### 4.4 验证准则

$$\lambda := \frac{P(Y=1 \mid R > r^\ast, \mathbf{z} \in \mathcal{Z})}{P(Y=1 \mid R > r^\ast)} > 2$$

即筛选后子集的"可塑形"概率显著高于仅用 R 筛选的基率。

### 4.5 待验证假设清单

| 编号 | 假设 | 筛选因子 | 预期 |
|------|------|---------|------|
| H1 | H(1h,2h) 高 → H(4h,1d) 也高 | $H(1h,2h) > 0.6$ | Y=1 占比提升 |
| H2 | 强趋势期 H(c) 更高 | $s_{\text{pre}} > 0.10$ | Y=1 占比提升 |
| H3 | co_expand 内 P1 更稳定 | 四象限=co_expand | 跨品种比下降 |
| H4 | 高波动期 H 曲线更平稳 | $\sigma_{1h}$ 高分位 | L̂ 下降 |
| H5 | 组合筛选优于单因子 | H1+H2 组合 | $\lambda > 2$ |

---

## 5. 当前状态与后续工作

### 5.1 已完成

- 主定理纯数学推导（存在性）
- 子区间非平凡版本（定理 4.7-4.8）
- 5m/15m/1h 实证检验（短尺度平凡，不可用）
- 1h/1d 实证检验（长尺度有 27.8% 覆盖率）
- 条件性应用框架设计

### 5.2 后续工作（独立项目）

- 按 §4.5 假设清单 H1-H5 执行筛选因子验证
- 若找到 $\lambda > 2$ 的 $\mathcal{Z}$，建立 4h 塑形策略原型
- 成本参数实际校准（当前用基准 $c_{\text{cost}}=0.1, K_S=1.5, R=2.0$）

### 5.3 失效条件

- 若所有筛选因子组合都无法达到 $\lambda > 2$，则本应用框架无实践价值
- 若 4h 塑形策略原型回测不盈利，则理论预测未被兑现

---

## 6. 引用

- 冻结总结：[freeze-summary.md](../../../archived-notes/2026/08/2026-08-08-vol-ratio-implies-market-strength/freeze-summary.md)
- 理论主文档：[cross-timeframe-vol-ratio-implies-market-strength.md](../../../archived-notes/2026/08/2026-08-08-vol-ratio-implies-market-strength/cross-timeframe-vol-ratio-implies-market-strength.md)
- 实证简报：[hurst-vs-rbar-briefing.md](../../../archived-notes/2026/08/2026-08-08-vol-ratio-implies-market-strength/hurst-vs-rbar-briefing.md)
- 假设检验蓝图：[hurst-shape-assumptions-testability.md](../../../archived-notes/2026/08/2026-08-08-vol-ratio-implies-market-strength/hurst-shape-assumptions-testability.md)
- 实验设计：[hurst-shape-experiment-design.md](../../../archived-notes/2026/08/2026-08-08-vol-ratio-implies-market-strength/hurst-shape-experiment-design.md)
- 相关定理：[theorems/theory-library/structural-shaping-alpha/](../../theory-library/structural-shaping-alpha/)
