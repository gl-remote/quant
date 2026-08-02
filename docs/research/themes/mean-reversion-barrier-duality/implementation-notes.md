# 工程实现备注 · mean-reversion-barrier-duality

> 类型：Theme / implementation-notes
> 状态：占位（阶段 1 启动后回填）

---

## 计划内容

- OU 参数估计器（AR(1) MLE，滚动窗口）；
- fBm Hurst 估计（R/S、增量自相关）；
- 双 barrier 首达求解器（三对角 ODE：胜率 $p(x)$ 与平均时间 $m(x)$）；
- 回测桥接（事件生成、$T$ 时间止损、真实成本模型 `workspace/common/contract_specs.py`）；
- cluster bootstrap（按 contract×date）。

若工程决定影响策略语义，先回改 [strategy-math-spec.md](strategy-math-spec.md) 再更新本文。
