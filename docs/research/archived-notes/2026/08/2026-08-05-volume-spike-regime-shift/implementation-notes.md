# Implementation Notes · volume-spike-regime-shift

> r1 阶段本文件只占位。工程实现细节在脚本落地后回填。
> 研究脚本保留在本批次的 `raw-workbench/scripts/`，属于归档研究资产，不进入 `workspace/` 长期目录。

---

## 1. 数据访问

- 研究脚本采用轻量风格：`pd.read_csv(market_csv_dir() / f"{symbol}.tqsdk.1h.csv")`；
- 不走 `DataManager`（避免研究脚本启动开销），但口径必须与生产层一致；
- CSV 字段：`datetime, open, high, low, close, volume, ...`；`datetime` 用 `pd.to_datetime` 解析。

## 2. 复用的正式模块

| 用途 | 模块 |
|------|------|
| Cluster bootstrap | `workspace/research/bootstrap.py:cluster_bootstrap` |
| Hurst 估计 | `workspace/research/hurst.py:hurst_rs` |
| 合约规格 / 成本 | `workspace/common/contract_specs.py:CONTRACT_SPECS` |
| 路径 | `workspace/data/output_paths.py:market_csv_dir` |
| 品种前缀 | `workspace/common/symbol_utils.py:extract_contract_prefix` |

## 3. 研究脚本内联实现（不进 workspace/）

- 成交量 z-score（rolling N trailing，不含当根）
- ATR(14, SMA-TR 口径)
- session_date（按交易日分组，夜盘算次日）
- barrier hit 模拟（从 structural_shaping_gatekeeper.py 的 `simulate_combo` 简化）
- 事件长表 / 聚合表输出

## 4. 产物路径

- 事件长表 / 聚合表（parquet）：`project_data/research/volume-spike-regime-shift/`
- 图（png）：同目录 `figures/`
- >10MB 文件不进 git，只在阶段日志登记路径与 hash / 行数。

## 5. 回填触发条件

- Stage 0 脚本落地后：回填数据加载、session_date 切分、ATR 口径的具体实现细节；
- Stage 2 脚本落地后：回填 barrier 模拟、bootstrap 调用、BH-FDR 实现；
- 若 Stage 5 触发：回填真实成本换算细节与合约规格异常处理。
