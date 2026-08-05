# Archive References · volume-spike-regime-shift

> 本文件登记本主题实际引用过的归档批次。采用 pull 模式：引用触发登记，不引用不登记。
> 立题时按 quant-research-layout 的截断策略（家族内必读 + 跨家族近 2 周 + 顶层索引先读）做了首轮扫描。

---

## 归档清单

### archive:2026-07-06-structural-shaping-alpha-stage1

- **关系类型**：方法论遗产 + 代码模板
- **说明**：本主题的 barrier hit 模拟、cluster bootstrap、全局分位切桶、真实成本换算范式直接继承该批次的 `structural_shaping_gatekeeper.py` / `regime_split_er.py`。区别在于本主题把切分因子从 ER 换成 1h 成交量 z-score，且研究目的从"塑形 combo 判决"改为"因子切制度的效力测量"。
- **复用要点**：
  - `simulate_combo` 式逐 bar barrier 判定（复制后简化为三组固定容器）；
  - `cluster_bootstrap_paired_diff` / `bootstrap_p_gt_0` 思路，正式实现走 `workspace/research/bootstrap.py:cluster_bootstrap`；
  - `realistic_cost_atr_per_side` 成本换算范式，正式实现走 `workspace/common/contract_specs.py`；
  - 全局分位切桶（不每 combo 独立切）以保持 paired 语义。
- **相关文件**：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report

### archive:2026-07-24-structural-shaping-alpha-freeze

- **关系类型**：理论母定理来源
- **说明**：该主题冻结后提炼的 `theorem:structural-shaping-alpha#factor-filtering-and-dgp-boundary` 给出"因子筛选后条件漂移 $b_A$ 为常数 iff GBM 闭式仍成立"的理论判据；本主题是其实证配套，测量成交量 spike 触发后 $b_A$、$\sigma_A$、$H_A$ 的实际形态，决定套用哪套 barrier 结论。
- **相关文件**：archive:2026-07-24-structural-shaping-alpha-freeze#freeze-summary

### archive:2026-07-13-va-asymmetry-leak-chain-consolidated

- **关系类型**：方法论遗产（数据边界）
- **说明**：该批次（特别是 poc-value-area-asymmetry 阶段 3）确立了两条本主题必须遵守的硬约束：
  1. **KF-22**：分类器 rank 单位必须 per-contract，禁止跨合约池化——本主题 $Z_t$ 的 rolling mean/std 严格 per-contract；
  2. **KF-23**：判决"过拟合"前必须先拆制度维度（ATR / trend / 时段）——本主题 math-spec §5.3 的 ATR 二维拆分 + ATR 匹配对照直接继承此判据。
- **相关文件**：archive:2026-07-13-va-asymmetry-leak-chain-consolidated

---

## 本批次自登记

### archive:2026-08-05-volume-spike-regime-shift

- **关系类型**：主题冻结归档
- **说明**：volume-spike-regime-shift 主题整包归档；核心机制确认（MADEV 主导、极端放量触发均线回归），但独立 alpha 被证伪。稳定定义与边界已蒸馏到 `theorems/factor-library/volume-spike/`。
- **相关文件**：archive:2026-08-05-volume-spike-regime-shift#freeze-summary

---

## 未来登记规则

- 本主题产生新的归档批次时，按 quant-research-layout 的归档原子步骤在本文件追加自登记条目（O(1)）；
- 实际引用其他归档批次时，在同一次 commit 中 pull 登记到本文件；
- 不做预防性登记。
