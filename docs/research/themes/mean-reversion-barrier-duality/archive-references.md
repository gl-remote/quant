# 归档引用 · mean-reversion-barrier-duality

> 类型：Theme / archive-references
> 状态：初稿（2026-08-02）
> 采用 pull 模式：引用触发登记，不引用不登记。

---

## 相关归档批次

### archive:2026-08-02-mean-reversion-barrier-duality-stage0

- 关系类型：**阶段归档（自登记）**
- 说明：本主题阶段 0（合成数据）的归档批次。含 OU 首达闭式、小 κ 展开、$R^\ast(\kappa)$ 单调性、Péclet 数判据、成本/regime/均衡误差三类压力测试的完整原始脚本（9 个），以及 KF-1..6 的证据源。阶段 1 真实数据启动后引用此批次作为方法论与数学基础。
- 相关文件：archive:2026-08-02-mean-reversion-barrier-duality-stage0#stage0-summary

### archive:2026-07-24-structural-shaping-alpha-freeze

- 关系类型：**对偶 + 方法论遗产**
- 说明：本主题是该冻结主题的镜像补全。其通道 B（未知符号趋势漂移）给出 $E\sim K_S^3R(R-1)$，结论偏向 $R>1$；本主题研究均值回归下 $R<1$ 何时最优。复用其 Doob OST、首达记号、成本簿记、KF-22 cluster bootstrap、KF-27 分布输入参数优化器方法论，但假设正交（回归 vs 趋势），不复用其结论数字。
- 稳定数学内核：`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`、`theorem:structural-shaping-alpha#winrate-payoff-tradeoff-under-frictions`。
- 相关文件：archive:2026-07-24-structural-shaping-alpha-freeze#freeze-summary

### theorem:structural-shaping-alpha#piecewise-static-kelly-vs-fixed-risk

- 关系类型：**下游仓位管理接口**
- 说明：一旦本主题确认 $R<1$ alpha 存在，其仓位管理（动态 / 加性 / 分段静态凯利、最优 rebalance 窗口）直接复用该定理；本主题只解决"alpha 是否存在、$R$ 朝向"，不重复仓位管理推导。

### theorem:structural-shaping-alpha#hurst-evolution-and-trend-alpha-decay

- 关系类型：**制度对照**
- 说明：该定理给出趋势 alpha 随 Hurst 衰减、现代残留通道（冷门 / 长周期 / 事件驱动）。本主题的均值回归是趋势的对偶制度；$H<1/2$（反持续）段与 OU 回归段的关系需在阶段 2 实证厘清（KF-4：纯反持续不等于均值回归漂移）。

---

## 立题扫描说明

按 `quant-research-layout` 截断策略，立题时重点读取同家族（`structural-*`）归档与近两周跨家族批次；其余远期批次走 pull 模式，实际引用时再登记。本主题尚无自有归档批次。
