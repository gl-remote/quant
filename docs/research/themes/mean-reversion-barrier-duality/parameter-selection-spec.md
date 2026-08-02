# 参数选择规格 · mean-reversion-barrier-duality

> 类型：Theme / parameter-selection-spec
> 状态：占位（阶段 1 广度扫描完成后回填）

---

## 待回填

阶段 1 实验完成后在此定义：

- 入场偏离 $d=K_T$ 的分层（按品种波动率 / $\kappa$）；
- 均衡锚点选择（VWAP / 滚动均值 / POC / 开盘价）及判据；
- $R=K_T/K_S$ 与 $T$ 按回归强度 $\kappa$ 的分层规则；
- OU / Hurst 估计窗口与最小样本；
- 参数回填格式与稳健性邻域。

参数选择必须引用 [strategy-math-spec.md](strategy-math-spec.md) 的定义，不重复策略公式。
