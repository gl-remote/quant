# 2026-07-13 · va-asymmetry-composite · 未来信息泄漏铁证

## 一句话结论

`va-asymmetry-composite` v1.0 归档 metrics（年化 +63.44%、夏普 3.47、613 笔）是**未来信息泄漏**产物；分类器的 `A3_skew_spec` / `daily_atr_spec` / `trend_ret_M_spec` / `close_session` 四个 daily 特征在事件触发时使用了当日 event_time 之后的 5m bars。因果修复（`shift(1)`）后年化 -38.25%、夏普 -1.60、笔数 1018。**原策略假设无独立 alpha**。

结论标签：❌ 证伪 · 🧪 方法论（未来信息泄漏检测的双证据链范式）

## 阅读顺序

1. [future-info-leak-verification.md](future-info-leak-verification.md) —— **主报告**，含 4 层独立证据链、修复效果、代码定位、后续方向
2. `raw-workbench/engineering-gap-investigation-report.md` —— 工程侧对齐研究侧的历次尝试全流水（发现泄漏之前的过程）
3. `raw-workbench/research-vs-engineering-gap-breakdown.md` —— 研究/工程 R/E 逐层差异拆解

## 4 层独立证据链概览

| # | 证据 | 关键脚本 |
|---|---|---|
| 1 | 单事件 68 根未来 bar 泄漏（SHFE.rb2501 2024-10-14 09:00 事件当日仅 1 根 bar 已发生，另 68 根都在事件之后） | `raw-scripts/verify_leak_evidence_chain.py` |
| 2 | 4 个字段泄漏版 vs 因果版数值完全不同 + 与 `build_events` 中合法 `A3_skew` 边界精确一致 | 同上 |
| 3 | 夜盘边界分析：shift(1) 是保守修法（周五 21:00 事件 shift 会误扔 45 根白天已知 bars） | 同上 |
| 4 | **截断法因果判据**：15/15 事件 r_s 归一化值不同、3/15 direction 反转 | `raw-scripts/verify_leak_by_truncation.py` |

## 目录结构

```text
2026-07-13-va-asymmetry-future-info-leak/
├── README.md                                # 本文
├── future-info-leak-verification.md         # 压缩版主报告（4 层证据链）
├── raw-workbench/
│   ├── engineering-gap-investigation-report.md    # 工程侧对齐研究侧尝试全流水
│   └── research-vs-engineering-gap-breakdown.md   # R/E 逐层差异拆解
├── raw-scripts/                              # 24 个验证/对比/复现脚本
│   ├── verify_leak_evidence_chain.py         # 证据 1-3 主证据脚本
│   ├── verify_leak_by_truncation.py          # 证据 4 截断法脚本
│   ├── reproduce_research_side.py            # 研究侧全量回测（含 shift(1) 修复）
│   ├── compare_research_vs_engineering*.py   # R/E 一致性对比
│   ├── compare_R_E_7contracts_*.py           # 7 合约级 R/E 对比（v1/v2/v3）
│   ├── debug_matched_three_layer.py          # 三层归一化对齐调试
│   ├── debug_E_classifier_4d_inputs.py       # 工程侧分类器 4D 输入调试
│   ├── debug_R_E_single_contract_inputs.py   # 单合约 R/E 输入对比
│   ├── debug_pathB_single_contract.py        # PathB 单合约 debug
│   ├── diagnose_intraday_dup.py              # 日内去重诊断
│   ├── diagnose_strategy_sm_SHFE_rb2501.py   # rb2501 状态机诊断
│   ├── diagnose_tier_internal_7contracts.py  # 7 合约 tier 内部诊断
│   ├── analyze_entry_timing.py               # 入场时机分析
│   ├── verify_classifier_baseline_*.py       # 分类器基线复现（full / repro）
│   ├── verify_fixed_roll_t_pit.py            # roll_t_pit 修复验证
│   ├── verify_r_extreme_on_300days.py        # r_s 极端度 300 日验证
│   ├── verify_roll_t_pit_mad_bug.py          # roll_t_pit MAD bug 定位
│   ├── show_db_schema.py                     # 回测 DB schema 探查
│   └── query_run18.py                        # run_id=18 回测查询
└── raw-outputs/                              # 全量回测产出
    ├── reproduce-research-side/              # 因果修复版全量回测：142 合约 / 1018 笔
    │   ├── events.parquet                    # 152KB
    │   ├── trades.parquet                    # 196KB
    │   └── metrics.json
    ├── compare-r-e/                          # 研究/工程 R/E 对比产出
    │   ├── research_events.parquet           # 148KB
    │   ├── research_trades.parquet           # 160KB
    │   ├── engine_backtests.parquet          # 20KB
    │   ├── engine_paired_trades.parquet      # 52KB
    │   ├── matched_pair_detail{,_v2}.parquet # 各 224/252KB
    │   ├── per_contract_compare.parquet
    │   ├── same_contract_day_three_layer_diff.parquet
    │   └── summary{,_v2}.json
    ├── reproduce-research-side.log
    ├── engineering-side-5m-batch.log         # 36KB
    └── engineering-side-full.log             # 36KB
```

## 关键关联

- **前置批次**：archive:2026-07-13-va-asymmetry-engineering-fix —— MAD-fix 分类器修复 + 工程侧初步对齐（本批次的直接前身；发现泄漏之前的最后一次「归因到分类器/输入端」的尝试）
- **主题冻结基线**：archive:2026-07-10-va-asymmetry-composite —— v1.0 B0 泄漏版归档
- **数学 spec**：archive:2026-07-12-va-asymmetry-composite-mathspec

## 修复动作（已落地代码）

| 位置 | 动作 |
|---|---|
| `raw-scripts/reproduce_research_side.py#L375-L386` | merge 前对 4 个 daily 值列 `shift(1)` |
| `workspace/strategies/va_asymmetry_composite_strategy.py::_precompute_va_daily_lookup` | 同步 shift(1)，保证 lookup[今日] 返回昨日收盘后的值 |
| `workspace/strategies/classifiers/poc_va.py` | 无因果问题，仅 `git restore` 回 HEAD |

## 方法论遗产（对后续主题的价值）

**双证据链未来信息泄漏检测范式**：

1. **值级证据**（证据 1-3）：直接对比「事件触发时可见的 5m bars 数量」与「daily 特征计算实际用到的 bars」，用信息边界的定量差异证明泄漏；
2. **因果证据**（证据 4）：**截断法** —— 同一份泄漏版代码，喂两份不同数据（完整 vs 截断到 event_time），若结果不同则泄漏铁证。

第 2 类是**充分且不可辩驳**的因果性判据：因为唯一控制变量就是「event_time 之后的 bars 是否可见」。任何后续主题若怀疑存在时间对齐问题，都可以直接套用此范式。

## 剩余方向（本次未纳入）

- 方向 A：`daily_atr_spec` / `trend_ret_M_spec` / `close_session` 改为事件级精确截断（bars.datetime < event_time），重建 daily 特征管道
- 方向 B：放弃 daily `_spec` 聚合，改用 `build_events` 里已经因果合法的 intraday 特征重新设计分类器
- 方向 C：接受 shift(1) 保守口径，先做 R/E 收敛，再重寻优参数
