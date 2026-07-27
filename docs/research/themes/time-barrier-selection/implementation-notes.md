# time-barrier-selection · Implementation Notes（占位）

> 状态：**占位** · Stage 1 实验开工后按需补充

## 待记录

- 5m 数据加载与 ATR 计算的实现路径（复用 `workspace/data/*` 与 `workspace/backtest/*` 的组件）
- 首达停时的向量化实现（沿用 `archive:2026-07-24-structural-shaping-alpha-freeze/raw-scripts/first_passage_designer.py` 的向量化思路）
- cluster bootstrap 的独立实现（cluster 单位 = `(contract, date)`）
- 真实成本模型接入（`workspace/common/contract_specs.py`）
