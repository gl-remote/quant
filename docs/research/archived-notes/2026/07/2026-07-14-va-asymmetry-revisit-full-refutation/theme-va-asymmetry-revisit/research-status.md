# va-asymmetry-revisit · Research Status

> 类型：Research Status
> 状态：**三轮验证：L_seg2 candidate 判死（2026-07-14）** · Causal pipeline 无未来函数但 alpha 由选样偏差假造，主题进入冻结候选

## 一句话结论

va-asymmetry 系列所有性能类数字结论已作废（daily 特征未来信息泄漏），但**部分假设的因果叙事不依赖 daily 泄漏值**，且这条错误路径本身沉淀了一套**决策链条明确的因子研发流程**——本主题的任务是**分离出可复用流程 + 未验证猜想集**两份资产。**首轮 H-1 判死 → 二轮 causal tier 疑似发现 L_seg2 制度依赖 alpha (Sharpe 1.48) → 三轮扩样至 145 合约后 Sharpe 塌至 0.08 + 因果性铁证 225 event × 3 特征 max_abs_diff=0 + 选样偏差诊断证明原 40 合约是随机抽样的 top 1.5%**：strategy alpha 判死，pipeline 因果性完好，本主题的策略假设全线证伪。详见 archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/h1-report → archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/causal-tier-report → archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/expanded-report 与 KF-1~KF-10。

## 边界

- 本主题**只做资产分离**：把"流程约束"（默认参数/硬约束/方法论）与"待验证猜想"（core alpha 假设）拆开；不承担为原策略翻案。
- **不复用旧数字**：任何形如"Sharpe X / 年化 Y%"的历史数字均不写入本主题；每个猜想若开始验证，都从零重跑因果版基线。
- **不复用被证伪的组合层结构**：原 B0=S1×W0×VW0 视为已证伪，仅在流程节点中作为反例登记。
- **不复用任何 daily 泄漏输入**：所有 daily 派生特征进入实验前必须先过截断法（见 KF-0）。

## 下一步

- [x] **首批猜想验证优先级** 已选定并执行：H-1 A3_skew 独立方向 alpha
- [x] **二轮回收**：causal 三维 tier 分类器 → 疑似 L_seg2_low_flat 制度依赖 alpha 候选（KF-5）
- [x] **三轮扩样验证**：40→145 合约 → L_seg2 Sharpe 1.44→0.08 → **KF-5 撤销、增补 KF-9/KF-10**（详见下方）
- [x] **因果性铁证**：225 event × 3 特征 max_abs_diff = 0.00e+00 → pipeline 无未来函数（KF-11）
- [ ] **主题冻结候选**：va-asymmetry 系列全部策略假设在完整数据 + 严格 causal + 无选样偏差下均无 alpha。建议整体冻结进 `themes-frozen/va-asymmetry/`
- [ ] **仅剩独立探索路径**：hypothesis-inventory H-11 τ_signed / H-12 transition_flag（intraday 版）与 signed skew 输入正交，理论上可能仍有独立 edge；若也证伪则本主题彻底冻结
- [ ] **流程侧默认沿用** [factor-research-workflow.md](factor-research-workflow.md)，本轮新增：KF-3（半 tick 成本吞噬）+ KF-8（rank 窗口无关性）+ KF-11（因果性铁证四层证据链方法）+ KF-10（选样偏差自诊断法）

## 文档地图

| 文档 | 承载 |
|---|---|
| [README.md](README.md) | 目录索引 |
| [research-status.md](research-status.md) | 本文件：状态 / 边界 / 下一步 / KF 清单 |
| [factor-research-workflow.md](factor-research-workflow.md) | **可复用因子研发流程**（从 va-asymmetry 路径复盘提炼；11 个关键决策节点，每节点 = 问题 + 历史选择 + 结论 + 复用建议） |
| [hypothesis-inventory.md](hypothesis-inventory.md) | **未验证猜想集**（H-系列，核心 alpha 假设；每条 = 假设 + 出处 + 泄漏关系 + 重测方式） |
| [archive-references.md](archive-references.md) | 与本主题相关的 archive 批次索引与关系 |

## 关键发现清单

### KF-0 · 立题基线：va-asymmetry 家族的分类器输入侧必须先过截断法
- 类型：方法论
- 状态：已证实
- 证据：archive:2026-07-13-va-asymmetry-leak-chain-consolidated#README
- 影响：本主题（及沿用本主题流程的任何后续主题）所有实验的第一步都必须用截断法（`archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py`）验证特征输入无泄漏，才能进入后续节点。作为流程**第 0 号硬约束**登记。
- 日期：2026-07-13

### KF-1 · H-1 因果版 pooled IC 判死（signed A3_skew 无一阶方向 alpha）
- 类型：策略行为 · 假设证伪
- 状态：已证伪
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/h1-report
- 影响：hypothesis-inventory 中 H-1（signed A3_skew 独立方向 alpha）在 15 品种 40 合约 16,406 hourly events 上 pooled Spearman IC 全 horizon ∈ [-0.03, 0.01]、cluster-bootstrap CI 全跨 0、跨品种 sign 一致性 45–60%（远低于 80% 门槛）——**F 系列新增 F-13 · signed A3_skew 一阶方向 alpha**。H-3 / H-4 共享同一输入，先验大幅下降，暂缓验证。
- 日期：2026-07-14

### KF-2 · H-1 制度分层 + 极端事件净收益判死（36 格 0 通过）
- 类型：策略行为 · 假设证伪
- 状态：已证伪
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/h1-report
- 影响：按 methodology KF-23（"过拟合 vs 制度依赖"）预防性拆分 intraday session-ATR × side × horizon 制度维度（3×2×6=36 格），realistic 成本下 0/36 格通过（CI_lo>0 且 p<0.05），跨品种保留率最好格也仅 25%；从制度依赖角度确认 H-1 是**真无 alpha**而非过拟合。**F 系列新增 F-14 · signed A3_skew top/bottom 20% 直接下注策略（含 3 档 ATR 分层）**。
- 日期：2026-07-14

### KF-3 · 期货 hourly event 因子的"半 tick 成本吞噬"约束
- 类型：方法论
- 状态：已证实
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/h1-report
- 影响：40 合约 hourly event 上，per-contract realistic roundtrip cost ≈ 0.06%–0.30%（tick 相对 close 越大越贵）；因此任何"日内小方向 alpha"要 gross ≥0.1%/次才可能穿透成本。作为 factor-research-workflow N-3（Cost Model）的量化补充硬约束：**未来 event-driven 因子的 experiment-plan 必须在广度扫描前先估算 per-symbol gross 幅度 vs cost 幅度的可穿透性，避免结构上不可能过门的方向浪费预算**。
- 日期：2026-07-14

### KF-4 · Hour-of-day 白盘 mean(ret) 偏漂移（不作为独立 alpha，作为对照基准）
- 类型：方法论 · 边界待定
- 状态：边界待定
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/h1-report
- 影响：hour∈{9,10,11,14} 全多 mean_ret_4h ~5bps gross 显著（p<0.05, cluster CI 排 0），但扣 realistic cost 后 8:2 walk-forward：train p=0.42 未过、test p=0.04 单折过、品种保留率 13/35=37%——**不构成稳健 alpha**。作为后续任何 event-driven 因子净收益检验的**必备对照基准**（避免把"命中日盘时段"当作因子 alpha）。
- 日期：2026-07-14

### KF-5 · Causal Tier 分类器发现 L_seg2_low_flat 制度依赖 alpha 候选 [**已于 2026-07-14 撤销**]
- 类型：策略行为 · 假设证伪
- 状态：**已撤销**（详见 KF-9 / KF-10）
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/causal-tier-report → archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/expanded-report
- 影响：40 合约上观测到的 L_seg2_low_flat Sharpe 1.48 被三轮扩样证伪：145 合约下 Sharpe 塌至 0.08、年化 3.4%、DD -64.6%；随机 40 合约 Sharpe 分布诊断证明原 40 合约是随机抽样能到达的 top 1.5% 极右尾。**保留本条为历史记录，实际决策以 KF-9 为准**。
- 日期：2026-07-14

### KF-6 · 6-tier "组合等权" 假设在 causal 修复下进一步崩塌（H-10 修订）
- 类型：策略行为 · 假设证伪
- 状态：已证伪
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/causal-tier-report
- 影响：hypothesis-inventory H-10（6-tier 存在结构关系但非"6 独立信号等权"）在 causal 版下，全 6 tier 一起做（signed pnl）**年化 -73% / Sharpe -0.86 / DD -178%**，因空头 3 个 tier（S_seg12/S_seg34/S_seg2_mid）全部反向或无信号拖累。修复后**仅剩 2 个多头 tier（L_seg2 / L_seg3）有正 edge**，其中 L_seg2 是唯一 CI 排 0 的候选。这**扩展 F-系列 F-15**：6-tier 复合策略在 causal 修复后完全崩塌，B0 结构不可复用。
- 日期：2026-07-14

### KF-7 · S_seg12_high_dn 反向：spec 判空实际做多（H-4 修订）
- 类型：策略行为 · 假设证伪
- 状态：已证伪
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/causal-tier-report
- 影响：hypothesis-inventory H-4（空头单机制假设：崩盘前奏 = 高 ATR 顶厚 + 下跌趋势）在 causal 版下**反向**：S_seg12_high_dn (r_s≤0.19, r_a>0.67, r_t≤0.20) 在 10h net **+0.29% (p=0.002)** —— 极端负 skew + 高波动 + 弱趋势后市场**反弹**而非崩盘。**F 系列新增 F-16 · va-asymmetry-composite 原空头单机制假设**（本主题及后续主题不再验证除非有强新证据）。
- 日期：2026-07-14

### KF-8 · Rank-window 240 与 360 结果一致（rank 窗口无关性方法论确认）
- 类型：方法论
- 状态：已证实
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/causal-tier-report
- 影响：per-contract rolling rank 的窗口 240 event ≈ 20 交易日 与 360 event ≈ 30 交易日下 L_seg2 test 通过口径完全一致（p=0.021 vs 0.025，方向同）→ tier 边界坐标 `I_τ ⊂ [0,1]` 与窗口 N 无关的 spec §1.3 论断在 causal 版上重新验证；后续任何 event-driven 因子研究可默认 rank_win ≥ 240 events，无需扫参。
- 日期：2026-07-14

### KF-9 · L_seg2 candidate 在扩样后 alpha 消失（Sharpe 1.44 → 0.08）
- 类型：策略行为 · 假设证伪
- 状态：已证伪
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/expanded-report
- 影响：从原 40 合约扩至全部 145 合约（20 品种、2023-09→2026-07、~45,000 events）后，L_seg2_low_flat 净收益完全塌陷：n=1075，10h net mean +0.008%（CI [-0.10%, +0.12%]，p=0.878），年化 3.4%、Sharpe 0.08、DD -64.6%；6 tier 全景中 4/6 tier net 显著为负、2/6 近零；3-fold walk-forward test 全部 p>0.05；LGO 0/20 sector 通过；品种保留率降至 53.4% ≈ 随机基准。**KF-5 撤销、hypothesis-inventory H-3/H-4/H-5/H-6/H-17 全部证伪、F 系列新增 F-17 · Causal L_seg2 单信号策略**。
- 日期：2026-07-14

### KF-10 · 选样偏差自诊断法（随机 40 抽样 Sharpe 分布）
- 类型：方法论
- 状态：已证实
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/expanded-report
- 影响：从 145 合约随机抽 40 个 × 200 次跑相同 pipeline，得到 L_seg2 Sharpe 分布 mean 0.018 ± 0.572、95% 分位 1.06；原 40 合约 Sharpe 1.44 落在**98.5% 分位**——直接量化证明"少样本 alpha 是选样偏差假阳性"。**方法论沿用**：后续任何主题若在小样本合约池上发现 Sharpe > 1 的信号，扩样前必须先做同类"随机等大子样 Sharpe 分布"诊断，判断信号是否在分布 mid ± 1σ 内。
- 日期：2026-07-14

### KF-11 · 因果性铁证四层证据链方法
- 类型：方法论
- 状态：已证实
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/expanded-report
- 影响：对 causal event-driven pipeline，用两份数据 (Full vs Truncated `bars.iloc[:event_idx+1]`) 分别算特征，比较特征值一致性（本次 225 event × 3 特征 max_abs_diff = 0.00e+00）→ 值级一致 → rank 一致（单调函数传递）→ tier 一致（纯函数）→ pipeline 无未来函数。**方法论沿用**：后续任何 event-driven 因子研究，在 N-0 截断法（同源）之外补充"事件级双数据源对比"作为验证第 4 层。
- 日期：2026-07-14

### KF-12 · Skew 派生 7 大类假设全线证伪（成交量偏度含微弱信息但不可交易）
- 类型：策略行为 · 假设证伪 · 方法论
- 状态：已证伪
- 证据：archive:2026-07-14-va-asymmetry-revisit-full-refutation#raw-workbench/skew-derivative-report
- 影响：在 145 合约 55,877 events 上广度扫描 7 大类 skew 派生假设（|skew|→波动率/range/drawdown、短窗 4h/8h/24h、Δskew、cross-sectional rank、skew×trend、persistence 过滤）· 70 组 (feature, target) pair · **|IC| 最强候选 abs_skew_4h → future_range 只到 -0.022，通过门槛（|IC|>0.03 AND consistency≥65%）的候选：0**。TOP-1 深挖（Tercile mean、per-contract 保留率、walk-forward）显示均值差 <0.005%、方向 train/test 翻转、保留率 50%——skew 里**确实有微弱统计信息**（否则 IC=0），但**该信息量在期货 hourly-event 尺度 realistic cost 0.06-0.30% 下完全不可用**。**"含信息" ≠ "可交易 alpha" 需分开两个门槛**：前者只要 IC≠0，后者要 |IC|>0.03 + 均值差穿透成本。**F 系列新增 F-18 · Skew 派生特征全家族策略**。
- 日期：2026-07-14
