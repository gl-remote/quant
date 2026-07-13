# 2026-07-13 · va-asymmetry 未来信息泄漏错误路径链条 · 归并封装

> ⚠️ **警示归档（Warning Archive）**：本批次收纳 va-asymmetry 系列（poc-value-area-asymmetry / va-asymmetry-composite）从 2026-07-08 到 2026-07-13 共 7 个连续批次。它们共享同一条被证明存在**未来信息泄漏**的输入管道，所有性能类结论数字均不可信。**引用其中任何子批次前必读本 README**。
>
> 结论标签：❌ 证伪 · 🧪 方法论遗产 · 🔒 数字结论作废

## 一、错误链条概览

| 子批次 | 日期 | 主要产出 | 是否受泄漏影响 |
|---|---|---|---|
| [2026-07-08-poc-va-asymmetry](./2026-07-08-poc-va-asymmetry/) | 07-08 | Stage 1~4 全流程：测量→护栏→稳健性→分类器 v4.0 | ❌ 结论数字全部污染 |
| [2026-07-09-poc-va-asymmetry-reaccept-symmetric-regime](./2026-07-09-poc-va-asymmetry-reaccept-symmetric-regime/) | 07-09 | 对称制度 reaccept 支线证伪 | ❌ 甜点参数扫描基于泄漏 |
| [2026-07-09-poc-va-shaping](./2026-07-09-poc-va-shaping/) | 07-09 | 塑形参数扫描：SL1.0/TP1.4/TH8h → 净 15.45%/Sharpe 2.23 | ❌ 塑形基线数字污染 |
| [2026-07-10-va-asymmetry-composite](./2026-07-10-va-asymmetry-composite/) | 07-10 | **v1.0 冻结版**：B0=S1×W0×VW0 · Sharpe 2.70 · 年化 15.10% · 组合层 0/6 增量 | ❌ B0 基线数字污染 |
| [2026-07-12-va-asymmetry-composite-mathspec](./2026-07-12-va-asymmetry-composite-mathspec/) | 07-12 | P0-P9 实验框架 + math-spec 冻结 | ❌ P0-P9 全部对照数字污染 |
| [2026-07-13-va-asymmetry-engineering-fix](./2026-07-13-va-asymmetry-engineering-fix/) | 07-13 | MAD-fix + 工程侧对齐尝试；研究侧 63.44% 年化 / 夏普 3.47 全量回测 | ❌ 15× 差距根因误判 |
| **[2026-07-13-va-asymmetry-future-info-leak](./2026-07-13-va-asymmetry-future-info-leak/)** | **07-13** | **4 层证据链证明泄漏；因果修复后 -38.25%/-1.60/1018 笔** | ✅ **结论正确（链条终结批次）** |
| **[theme-va-asymmetry-composite](./theme-va-asymmetry-composite/)** | **07-13** | **原活跃主题目录整体归档**：README + research-status + strategy-math-spec + experimental-plan + archive-references + engineering-diagnosis | ❌ 假设证伪归档 |

## 二、根因（一句话）

**7 个批次共享同一条 daily 特征管道**：
`bars.groupby("date").agg(...)` → 得到当日 daily → `daily["A3_skew_spec" / "daily_atr_spec" / "trend_ret_M_spec"]` → `events.merge(daily, left_on="event_date", right_on="date")`。

当事件在盘中触发（如 09:00 / 10:00 / 11:00），此 merge 把「当日 22:55 收盘后才能算出」的 daily 值贴到了事件时刻——事件在 09:00 时用了当日 68 根尚未发生的 5m bars 的信息（SHFE.rb2501 2024-10-14 09:00 实证）。

详细证据链见 [2026-07-13-va-asymmetry-future-info-leak/future-info-leak-verification.md](./2026-07-13-va-asymmetry-future-info-leak/future-info-leak-verification.md)。

## 三、什么能保留 · 什么必须作废

### ✅ 可保留的方法论遗产（可继承给后续主题）

- **Stage 1~4 判据框架**（07-08）：cluster bootstrap · Bonferroni · 多层对照 · 7 层严格判据 · OOS 分离
- **分类器 v4.0 坐标切分结构**（07-08 stage4）：6 阵营 tier 定义本身无问题（`L_seg3_lowmid_up` 等），只是喂给它的 r_s/r_a/r_t 输入被污染
- **P0-P9 实验设计框架**（07-12）：P8 transition / P9 governance / paired 对照的组织方式
- **First-Passage Designer 工具遗产**（继承自 07-06 structural-shaping-alpha）
- **未来信息泄漏检测双证据链范式**（07-13-future-info-leak）：值级 + 因果级（截断法）
- **工程侧 5m 实盘化 pipeline**（07-13-engineering-fix）：backtest_trades / FIFO 配对 / 合约级并行 / MAD min_periods 等基础设施

### ❌ 必须作废的数字结论

- 任何形如「Sharpe X · 年化 Y%」的批次基线数字，包括但不限于：
  - B0=Sharpe 2.70 / 年化 15.10% / MaxDD −2.40%
  - Stage 3 shaping：SL1.0/TP1.4/TH8h → 净 15.45% / Sharpe 2.23 / 胜率 60.3%
  - 组合层 0/6 增量结论、S2 反向 ΔSh −0.27
  - 研究侧全量回测：63.44% 年化 / 3.47 夏普 / 613 笔
  - P0-P9 所有对照数字
  - Stage 3/4 各 tier 单笔 IR / 品种保留率 / FDR
- **任何相对 B0 的配对增量评估**均为伪比较（因为 B0 本身受污染）

## 四、引用规则

1. **禁止**引用本封装内子批次中的性能类数字结论；
2. **允许**引用方法论遗产条目（第三节 ✅ 列表），但引用时必须显式说明「数字结论作废、仅继承方法论」；
3. **推荐**：新主题若涉及 daily 特征聚合，先阅读 [2026-07-13-va-asymmetry-future-info-leak/future-info-leak-verification.md](./2026-07-13-va-asymmetry-future-info-leak/future-info-leak-verification.md) 与 [2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py](./2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py)，套用截断法验证自己的管道；
4. **命名引用协议**：本批次的命名引用为 `archive:2026-07-13-va-asymmetry-leak-chain-consolidated`；子批次用 `archive:2026-07-13-va-asymmetry-leak-chain-consolidated/<sub-batch>` 或 `#<sub-batch>` 形式。

## 五、后续方向（不属于本封装的结论范围）

- 方向 A：daily `_spec` 系列改为**事件级精确截断**（`bars.datetime < event_time`），重建 daily 特征管道；
- 方向 B：放弃 daily `_spec` 聚合，改用 `build_events` 里已经因果合法的 intraday 特征（`A3_skew` / `close_t` / `ret_8h` / `ret_4h`）重新设计分类器；
- 方向 C：接受 shift(1) 保守口径，先做 R/E 一致性收敛，再重寻优参数。

## 六、封装动作说明

- **归档动作日期**：2026-07-13
- **动作类型**：归并压缩（不拆散子批次、不删除内容，仅整目录搬入本目录 + 加顶层 README 警示）
- **搬入前**：7 个子批次分散在 `docs/archive/strategy-research/2026/07/2026-07-XX-*/`
- **搬入后**：全部位于 `docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/<sub-batch>/`
- **原命名引用**（如 `archive:2026-07-08-poc-va-asymmetry`）**已失效**，全库引用同步更新为 `archive:2026-07-13-va-asymmetry-leak-chain-consolidated`（或子批次锚点）；
- **归档规则依据**：`.trae/skills/quant-research-layout/SKILL.md § Archive 写法 § 归档动作的原子步骤`——本次属于「跨批次归并压缩」的一次特殊执行，压缩单元是 7 个已有批次而非 workbench 增量。
