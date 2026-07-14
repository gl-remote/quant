# 因子研发流程（从 va-asymmetry 路径复盘提炼）

> **本文档定位**：把 `archive:2026-07-13-va-asymmetry-leak-chain-consolidated` 这条 6 天走完的错误研究路径**拆解为可复用流程**。虽然最终结论作废，但路径上**每一次关键决策**都通过多品种/多归一化/多窗口的对照拿到过收敛证据；这些**流程节点的收敛结论与踩过的坑**独立于最终 alpha 是否成立，是本主题唯一可以直接复用到下一个因子的产出。
>
> **使用方式**：任何一个新的 event-driven 因子研发主题，可以直接把本文的 N-0 ~ N-10 作为**默认起点**——只在需要偏离默认时写理由，不重扫已收敛的架构参数。

---

## N-0 · 因果性验证（Causality Gate）

- **问题**：任何 daily 派生特征在 event_time 触发时是否可见？如果不可见，用了它就是未来信息泄漏。
- **历史选择**：va-asymmetry 系列 6 天内**没有**这一节点，直接把 `daily.groupby("date").agg` 结果 merge 到 events 上；连续 7 个批次都在这条泄漏管道上出结论。
- **结论**：`daily["<feature>_spec"]` 与 `events` 在 `event_date` 上 merge 时，若未 shift(1)，事件时刻直接读到当日 22:55 收盘后才能算出的值——盘中 09:00 事件用到当日 68 根未来 bars。4 层证据链（值级 + 因果级）铁证。
- **复用建议**（**硬约束**）：
  - 每个 daily 派生特征进 pipeline 前先跑一次截断法（`archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py`）：同一份代码 × 两份数据（完整 vs 截断到 event_time），若结果不同即泄漏铁证；
  - Intraday 派生特征也走截断法，只是截断点是 event_time 而不是 event_date；
  - 默认给每个 daily 特征列上 shift(1)（保守口径），除非因果证明当日值在 event_time 之前已可见。

---

## N-1 · 时间粒度与样本去重（Density Gate）

- **问题**：一个交易日多次触发 event，是"多条独立信号"还是"同一信号被多次采样"？
- **历史选择**：默认 30m N=6，同 (contract, event_date) 内多条 event 共享相同 daily 值。
- **结论**：泄漏版基线在 `(contract, event_date)` Gate 1 去重后，样本量骤降到 10.8%，Sharpe 崩塌；在 hourly N=1 抽样下 alpha 几乎消失。同一天多个 30m event 因共享 daily 值制造了**重复行偏置**，把 IC/Sharpe 系统性放大。
- **复用建议**：
  - 第 0 天起就做 `(contract, event_date)` Gate 1 去重（每合约每日至多 1 条 event）；
  - 默认时间粒度先在 hourly N=1 上验证，30m N=6 只作 robustness 对照；
  - 不允许"高密度触发 = 高信号数"的假象作为立项依据。

---

## N-2 · 归一化方式（Normalization）

- **问题**：跨合约、跨时间尺度的特征需要归一化——用哪一种？
- **历史选择**：P3 阶段扫了 4 种归一化：
  - A（per-contract rank）
  - B（t-PIT / z-score in-training window）
  - C（percentile within cluster）
  - D（绝对阈值 / 全局分位）
- **结论**：**B 采纳**（OOS 单侧门通过率最高、跨合约稳定）；A 与 B 差异小但 B 计算侧更清晰；C 与 A 无显著差异且实现更复杂；D 因跨合约漂移严重被淘汰。
- **复用建议**：
  - 默认 B（t-PIT 稳健 z）+ 学生 t CDF 映射（`ν=12`）——这是 va-asymmetry-composite 生产链路已采纳的口径；
  - 不再扫归一化族，除非新因子有明确理由（如离散型特征）；
  - 归一化窗口 N 单独校准，与归一化方式无关。

---

## N-3 · 成本模型（Cost Model）

- **问题**：回测的成本用扁平 ATR 还是 realistic（滑点 + 手续费 + funding）？
- **历史选择**：Stage 3 robustness 与 P8 分别用两种；扁平 ATR 是早期默认，realistic 是 structural-shaping-alpha 遗产。
- **结论**：h ≤ 12h 时两种成本对结论排序影响 <5%，但 **h > 12h 会出现方向翻转**——扁平 ATR 高估长持仓 alpha。
- **复用建议**：
  - 第 0 天起用 realistic：**滑点 `0.15 × ATR × (0.5 + SlippageTier)` + 手续费 0.03% 双边 + funding**；
  - 扁平 ATR 只作 sanity check，不作决策依据；
  - 任何 h>12h 的结论必须同时报两种成本。

---

## N-4 · Baseline 固化契约（Base Line Freeze）

- **问题**：多轴优化如何避免"每个 Phase 微调 → 累积过拟合"？
- **历史选择**：P0 冻结前六阶段各自独立调优；P0 冻结后 P1~P9 每 Phase 只允许改一个轴。
- **结论**：P0 冻结前的结论无法拆解归因（无法说清收益来自哪个改动）；P0 冻结契约让 P1~P9 每一步都可归因。
- **复用建议**：
  - P0 一旦冻结（含所有参数/成本/gate），后续任一 Phase 只允许改一个轴；
  - 冻结点必须落硬盘（YAML/spec），实验代码引用而非复制；
  - 违反契约即视为该 Phase 无效结论，回退。

---

## N-5 · 判据 & 多重检验（Statistical Decision Rule）

- **问题**：单笔毛收益 μ > 0、Sharpe > 阈值就够了吗？
- **历史选择**：初期直接看 μ；Stage 3 引入 Bonferroni；Stage 4 起改用 FDR + 期望净值。
- **结论**：
  - 单指标（μ 或 reach_rate）会因样本非独立而假阳性——必须用**期望净值** $\mu_{true}=\mu_g-\tfrac12\sigma_g^2$ 判定 edge；
  - Bonferroni 在 6-12 tier 场景下过严，检出功率过低；FDR (Benjamini-Hochberg) 更合适；
  - Cluster bootstrap（按 (contract, date) 聚类）是必须的（否则 CI 系统性偏窄）。
- **复用建议**：
  - **判据固定为**：$\mu_{true}>0 \wedge P(\mu_{true}>0)\ge 0.95$（cluster bootstrap CI）；
  - 多重检验用 FDR 决策 + Bonferroni 报作最保守下限；
  - 不允许用 Sharpe/reach_rate 单独下结论。

---

## N-6 · Exit 塑形（First-Passage Design）

- **问题**：SL/TP/持仓时间怎么选？
- **历史选择**：初期扫参 SL∈{0.5,1.0,1.5,2.0}σ × TP∈{1.0,1.4,2.0}σ × TH∈{4h,6h,8h,12h}；shaping 批次锁定 First-Passage Designer 框架。
- **结论**：
  - 把 exit 视为 First-Passage Time 问题，参数化为 (K_sl σ, K_tp σ, H hours) 后可复用给不同因子；
  - **风控 v2 全关**（trailing / TP / circuit breaker 全关）反而更优——策略以时间退出为主，SL 极少触发；
  - $H_{vol}(τ)$ 波动率归一化持仓在 6/6 tier 未过门，**放弃**。
- **复用建议**：
  - 默认 exit 骨架 = **First-Passage Designer + 风控 v2 全关**；
  - SL 用日线 SMA(10) ATR 而非 1h RMA（P0-P9 全链路已在 SMA 口径下跑通）；
  - 持仓时间统一用 $H_{cal}$（日历时长），不按 tier 分化。

---

## N-7 · 组合层（Combination Layer）

- **问题**：多个信号如何合并？强度加权还是等权？
- **历史选择**：扫过 W0/W1/W2/W3（强度加权）× VW0/VW1/VW2（多空加权）矩阵；泄漏修复后又扫 equal / IC-weighted / inverse-vol。
- **结论**：
  - 泄漏修复后不同加权方案差异 < 0.2 Sharpe——**加权不是 alpha 源**；
  - 6 tier 组合被证伪"6 独立信号等权"假设：tier 间事件重叠率 40-60%、方向共振 > 期望——tier 不独立；
  - Cap（总名义暴露上限）作为组合层默认参数有效，年化改善且 MDD 未恶化。
- **复用建议**：
  - 默认 **equal-weight** 起步，加权扫描降到低优先级；
  - 合并信号前先做**事件级重叠率 + 方向共振率 + 收益相关矩阵**三张表；
  - Cap 作为默认约束，具体值在因果版基线上重定。

---

## N-8 · OOS 与稳健性（Out-of-Sample & Robustness）

- **问题**：如何避免 in-sample 过拟合？
- **历史选择**：Stage 3 robustness 扫过 leave-one-out / walk-forward / 跨周期 / 跨品种；P6 采纳 walk-forward + LGO 双维。
- **结论**：
  - 品种维度：**leave-group-out**（按品种类型能源/有色/农产品/金融分组）比 leave-one-out 更能稳定 tier 内 alpha；
  - 时间维度：滚动 train/test（TS）5 折，要求至少 4 折方向为正才通过（OOS 单侧门 80%）；
  - 跨周期至少 5m + 15m 双周期验证（继承自 value-area 家族证伪教训）。
- **复用建议**：
  - **OOS 默认双维**：品种 LGO + 时间 walk-forward；
  - **单侧门 80%** 作为参数升级阈值；
  - 至少两个周期（5m + 15m 或 30m + hourly）作为稳健性硬门槛。

---

## N-9 · 失败回溯协议（Failure Retrospective）

- **问题**：某层实验 0/N 通过时，是接受"基线最优"还是怀疑轴选错？
- **历史选择**：va-asymmetry-composite experimental-plan §3 明确写：**先怀疑轴，再放弃**——切归一化、切单位、切 gate 各试一遍。
- **结论**：这一协议在 P0-P9 中至少两次挽救了误判：
  - P2 entry_mode 0/7 通过 → 换归一化后仍 0/7 → 判定 entry_mode 无 alpha；
  - P6 H_vol(tier) 0/6 tier 通过 → 换 gate 后仍 0/6 → 判定波动归一持仓无 alpha。
- **复用建议**：
  - 任何 Phase 0/N 通过时，**默认先怀疑轴本身选错**，按顺序试：切归一化 → 切单位（bps vs abs）→ 切 gate → 再判死；
  - 判死条件：三重变体全部 0/N；
  - 判死后写入本文档的"已证伪档案"章节（下方 F-系列），后续主题不再重跑。

---

## N-10 · 双管线互验（Research vs Engineering Cross-Check）

- **问题**：研究侧脚本与工程侧生产回测的数字一定要对得上——差异从哪定位？
- **历史选择**：va-asymmetry-composite-mathspec 阶段发现 R/E 15× 差距，绕了 3 天才定位到根因；最终发现两侧差异**完全**由 4 个 daily 特征 (`daily_atr_spec / trend_ret_M_spec / close_session / A3_skew_spec`) 在 event_date merge 时是否 shift(1) 解释。
- **结论**：R/E 数字差在 event-driven 因子中的第一嫌疑**永远**是 daily 特征 shift(1) 是否一致；不存在其他隐性 gap 时才怀疑成交配对/成本口径/时区。
- **复用建议**：
  - 每个新因子上线前必须跑一次 R/E 互验（`archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/compare_research_vs_engineering.py` 是可复用骨架）；
  - Diff 检查清单顺序：daily merge shift(1) → intraday feature 时间对齐 → 成交配对 FIFO → 成本口径 → 时区；
  - 差异 > 阈值 0.1 Sharpe 视为 bug，必须定位到具体列/具体日期。

---

## 附 · F-系列（走过的死路，不重跑）

以下条目由 va-asymmetry 系列已证伪，本主题及后续主题**不再验证**（除非有强新证据）：

- **F-1** entry_mode 7 模式（P2 全灭）——日内择时对 event-driven 无 alpha
- **F-2** $H_{vol}(τ)$ 波动率归一化持仓（P6，6/6 tier 未过门）
- **F-3** Profile 窗口除 W=2h 外的变体（Stage 3）
- **F-4** VW1/VW2 组合层加权（0/6 过门）
- **F-5** S2 品种筛选（负偏品种全排除；反而丢失 ν_implied 归因证据）
- **F-6** reaccept "对称三维协同" 整体框架（除 B 区顺势 S 分支外全灭）
- **F-7** 风控 v1（trailing / TP / circuit breaker 全灭）
- **F-8** 归一化 D（绝对阈值）
- **F-9** 归一化 C（percentile within cluster）
- **F-10** T1 治理裁剪（P8/P9 空间接近 0）
- **F-11** "6-tier = 6 独立信号等权" 假设（tier 间事件重叠率过高）
- **F-12** ATR 扁平成本模型（h>12h 会翻转，被 realistic 取代）
- **F-13** signed A3_skew 一阶方向 alpha（H-1 主假设，pooled IC 全 horizon ∈ [-0.03, 0.01]，CI 全跨 0，跨品种一致性 45–60%；kf:va-asymmetry-revisit#KF-1）
- **F-14** signed A3_skew top/bottom 20% × ATR 三档直接下注策略（3×2×6=36 格 0 通过；kf:va-asymmetry-revisit#KF-2）
- **F-15** 6-tier "组合等权" 复合策略（causal 修复下年化 -73% / Sharpe -0.86 / DD -178%，空头 tier 全反向拖累；kf:va-asymmetry-revisit#KF-6）
- **F-16** va-asymmetry-composite 原空头单机制假设（S_seg12_high_dn 在 causal 版下反向：net 10h +0.29% p=0.002，"崩盘前奏"叙事不成立；kf:va-asymmetry-revisit#KF-7）
- **F-17** Causal L_seg2 单信号 6-10h 长持仓策略（40 合约 Sharpe 1.44 但扩样至 145 合约后 Sharpe 0.08 / 年化 3.4% / DD -64.6%，被随机 40 抽样诊断证实为选样偏差极右尾；kf:va-asymmetry-revisit#KF-9）
- **F-18** Skew 派生特征全家族（7 大类：|skew|→波动率/range/drawdown、短窗 4h/8h/24h、Δskew、cross-sectional rank、skew×trend、persistence 过滤；145 合约 55k events 上 70 组 pair 广度扫描，|IC| 最强 -0.022，通过门槛 0；kf:va-asymmetry-revisit#KF-12）

出处：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated` 各子批次。

---

## 附 · 工具脚本索引

以下脚本可以直接从 archive 复制使用：

| 工具 | 位置（`archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/` 下） |
|---|---|
| 截断法泄漏检测（N-0） | `verify_leak_by_truncation.py` |
| 4 层证据链检测（N-0） | `verify_leak_evidence_chain.py` |
| 研究侧复现（N-10 骨架） | `reproduce_research_side.py` |
| R/E 一致性对比（N-10） | `compare_research_vs_engineering.py` |
| 分类器 baseline 复现 | `verify_classifier_baseline_full.py` |

---

## 与本主题的关系

- 本文档是**流程侧资产**，不预设任何具体 alpha 假设；
- 具体假设见 [hypothesis-inventory.md](hypothesis-inventory.md)；
- 本主题下若开始验证任一 H-系列猜想，**流程侧默认沿用本文档的 N-0 ~ N-10 与 F-系列排除**，只在 experiment-plan.md 中列出偏离项。
