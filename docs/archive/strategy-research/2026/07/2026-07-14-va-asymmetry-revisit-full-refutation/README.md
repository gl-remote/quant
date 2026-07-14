# 2026-07-14 · va-asymmetry-revisit · Full Refutation

> 批次类型：主题最终证伪归档 + **主题目录整体废弃归档**（不迁往 themes-frozen，直接搬入本批次）
> 主题：`theme:va-asymmetry-revisit`（**已于 2026-07-14 彻底废弃 · 不再作为独立候选**）
> 归档日期：2026-07-14
> 结论标签：❌ 全线证伪 · 🧪 方法论（因果性铁证四层证据链 + 选样偏差自诊断法）· ⚠️ 复盘（跨阶段方法学问题清单 + 6 条 skill 补丁建议）· 🔒 主题目录整体废弃

## 一句话结论

在 145 合约 · 55,877 events · 33 个月扩样数据上，对 va-asymmetry 家族的**全部剩余假设**做因果版验证——signed A3_skew 一维方向 IC、Causal 6-tier 三维联合、Skew 派生 7 大类（|skew|、短窗、Δskew、xs-rank、skew×trend、persistence、drawdown proxy）、日线 10 天 skew——**均无 alpha**。因果性铁证 225 event × 3 特征 max_abs_diff = 0.00e+00（pipeline 无未来函数），选样偏差诊断证明前一轮报告的 L_seg2 "Sharpe 1.48 alpha 候选"实为原 40 合约在随机 40 抽样分布的 top 1.5% 极右尾选样偏差。

## 阅读顺序

1. [session-summary.md](session-summary.md) · **顶层总览**（首读）· 一天内 4 轮实验的关键数字表 + 12 条 KF 全览 + 6 条 F 系列 + 5 份实验流水的索引
2. [va-asymmetry-family-retrospective.md](va-asymmetry-family-retrospective.md) · **8+ 天全周期复盘**（跨批次视角）· 11 阶段时间线 + 5 条系统性错误 + 6 条 skill 补丁建议
3. [theme-va-asymmetry-revisit/](theme-va-asymmetry-revisit/) · **主题目录整体废弃搬迁**（原 `docs/research/themes/va-asymmetry-revisit/`）
   - `README.md` · 主题目录索引（标 Frozen 2026-07-14）
   - `research-status.md` · KF-1~KF-12 完整清单
   - `factor-research-workflow.md` · N-0~N-10 决策节点 + F-13~F-18 反例档案
   - `hypothesis-inventory.md` · H-系列未验证猜想集（历史记录，不再回验）
   - `archive-references.md` · 主题级 archive 索引
4. [raw-workbench/](raw-workbench/) · 4 份实验流水
   - `h1-report.md` · 一轮 H-1 判死（15 品种 · 40 合约）
   - `causal-tier-report.md` · 二轮 Causal 6-tier · L_seg2 疑似 alpha
   - `expanded-report.md` · 三轮扩样 + 因果性铁证 + 选样偏差诊断
   - `skew-derivative-report.md` · 四轮 skew 派生 7 大类广度扫描
5. [raw-scripts/](raw-scripts/) · 16 个可复用脚本
6. [raw-outputs/](raw-outputs/) · <10MB 数据产出（14 个 outputs 子目录）
7. [DATA-INDEX.md](DATA-INDEX.md) · 3 个 >10MB 数据文件的路径 + md5 + 行数（不搬运）

## 4 轮实验概览

| 轮 | 假设 | 结果 | KF |
|:-:|---|---|---|
| 1 | H-1：signed A3_skew 一维方向 IC | 判死 · 全 horizon IC ∈ [-0.03, 0.01]，CI 全跨 0 | KF-1, KF-2 |
| 2 | Causal 6-tier 三维联合 | 疑似发现 L_seg2 Sharpe 1.48（40 合约） | KF-5 (后撤销), KF-6, KF-7 |
| 3 | 扩样 145 合约 + 因果性铁证 + 选样偏差诊断 | 判死 · Sharpe 塌至 0.08 · 原 40 合约在随机分布 98.5% 分位 | KF-9, KF-10, KF-11 |
| 4 | Skew 派生 7 大类（|skew|/短窗/Δskew/xs-rank/交互/persistence/drawdown） | 全线证伪 · 70 组 pair · |IC| 最强 -0.022 · 通过门槛 0 | KF-12 |

补充：日线 10 天 skew（d1_daily_skew.py）· 7,332 daily events · top |IC| = -0.022 · 净收益 L-S 最大 gross +11 bps vs cost 12 bps · 仍不足以过关

## 关键 KF 沉淀（方法论价值）

- **KF-10 · 选样偏差自诊断法**：小样本 Sharpe>1 → 强制"随机等大子样 Sharpe 分布"诊断。原 40 合约 Sharpe 1.44 落在随机 40 抽 200 次分布的 98.5% 分位 → 直接量化证明选样偏差假阳性
- **KF-11 · 因果性铁证四层证据链**：值级（`bars.iloc[:event_idx+1]` vs 完整数据 max_abs_diff=0）→ rank 一致（单调传递）→ tier 一致（纯函数）→ pipeline 无未来函数
- **KF-12 · "含信息" ≠ "可交易 alpha"**：IC≠0 与 |IC|>0.03+consistency>65%+均值差穿透成本是三个不同门槛，缺一不可
- **KF-3 · 期货 hourly-event 半 tick 成本吞噬约束**：任何 gross <0.1% 的信号结构上不可能穿透 realistic cost 0.06-0.30%
- **KF-8 · Rank-window 240 vs 360 结果一致**：后续无需扫参
- **KF-4 · Hour-of-day 白盘 mean(ret) 漂移基准**：作为后续任何 event-driven 因子的对照基准

## 系统性错误清单（供 skill 补丁参考）

来自 `va-asymmetry-family-retrospective.md` §三：

1. **广度优先方法论写了但没执行**：va-asymmetry 家族 8 天从头到尾深度优先，无一次横向扫其他假设
2. **Stage 通过率单调递增没触发过拟合警报**：Stage 1→4 通过率 100%→100%→100%→83% 是幸存者偏差的教科书表现
3. **Sharpe 2.70 + MaxDD 2.4% 没触发 sanity check**：5m 期货组合 Sharpe 超顶尖机构实盘 → López de Prado 经验法则应立即触发因果性铁证
4. **架构复杂化到藏了 7 天未发现的未来函数**：daily merge 未 shift(1)，engineering-fix 一整天没找到根因
5. **先验假设选择错**：5m OHLCV 上微观结构因子先验成功率 ~10%，选错赛道

对应的 6 条 skill 补丁建议（A-F）见复盘文档 §六。

## 与其他 archive 批次的关系

- **前置批次**：archive:2026-07-13-va-asymmetry-leak-chain-consolidated · 7 批错误路径链条 · 本批次的**因果修复起点**
  - 子批次 `2026-07-13-va-asymmetry-future-info-leak` 的**双证据链未来函数检测范式**（值级 1-3 + 截断法 4）在本批次演化为 `verify_leak_by_truncation` 范式 → `e1_v2_causality_ironproof.py`（225 event × 3 特征 max_abs_diff=0）
- **主题目录状态**：`theme:va-asymmetry-revisit` **已于 2026-07-14 彻底废弃**，主题目录整包搬入本批次的 `theme-va-asymmetry-revisit/` 子目录（不迁往 themes-frozen，因家族已判死无恢复计划）

## 目录结构

```text
2026-07-14-va-asymmetry-revisit-full-refutation/
├── README.md                                 # 本文
├── session-summary.md                        # 顶层总览（一日 4 轮）
├── va-asymmetry-family-retrospective.md      # 8+ 天全周期复盘（跨批次）
├── DATA-INDEX.md                             # >10MB 数据文件登记
├── raw-workbench/                            # 4 份实验流水
│   ├── h1-report.md
│   ├── causal-tier-report.md
│   ├── expanded-report.md
│   └── skew-derivative-report.md
├── raw-scripts/                              # 16 个可复用脚本
│   ├── h1_a3_skew_pooled_ic.py               # H-1 pooled IC + N-0 截断法
│   ├── h1b_regime_stratified.py              # 制度分层 + 极端事件 + hour baseline
│   ├── h1c_hour_of_day_net.py                # Hour-of-day 净收益 walk-forward
│   ├── c1_causal_tier_scan.py                # Causal 三特征 + 6 tier
│   ├── c2_l2_robustness.py                   # L_seg2 walk-forward + IR + 反向
│   ├── c3_l2_lgo_retention.py                # LGO + 品种保留率 + 随机对照
│   ├── c4_sensitivity.py                     # 阈值敏感度 + 3-fold + 组合池
│   ├── c5_performance_estimate.py            # 逐笔 net pnl → 年化/夏普/回撤
│   ├── e1_causality_ironproof.py             # 因果性铁证 v1（有截断参数错误 · 已废）
│   ├── e1_v2_causality_ironproof.py          # 因果性铁证 v2（正确版 · 225 event × 3 特征 max_abs_diff=0）
│   ├── e2_expanded_causal_tier.py            # 扩样 145 合约完整链路
│   ├── e3_selection_bias_check.py            # 选样偏差诊断（随机 40 抽样 Sharpe 分布）
│   ├── s1_skew_multi_angle.py                # 多窗 skew 计算（4h/8h/24h 特征缓存）
│   ├── s2_broad_ic_scan.py                   # 7 大类 skew 派生 70 组 pair 广度 IC
│   ├── s3_abs_skew_deep.py                   # TOP-1 abs_skew_4h → future_range 深挖
│   └── d1_daily_skew.py                      # 日线 10 天 skew + 未来 3 天验证
└── raw-outputs/                              # <10MB 数据产出（14 目录）
    ├── c1/                                    # Causal tier 全景
    ├── c2/                                    # L_seg2 walk-forward
    ├── c3/                                    # LGO + 品种保留率 + 随机对照
    ├── c4/                                    # 阈值敏感度
    ├── c5/                                    # 逐笔性能估算
    ├── daily_skew/                            # d1 日线 skew 全景
    ├── e1/                                    # 因果性铁证 v1
    ├── e1_v2/                                 # 因果性铁证 v2
    ├── e3/                                    # 选样偏差诊断
    ├── expand/                                # 145 合约扩样 (子集 <10MB 部分)
    ├── h1/                                    # H-1 pooled IC
    ├── h1b/                                   # 制度分层
    ├── h1c/                                   # Hour-of-day
    └── skew_wide/                             # 7 大类广度扫描
```

## 复现要点

- Python 环境：`uv run python` · 依赖 `workspace/common/contract_specs.py` 的 CONTRACT_SPECS
- 数据源：`project_data/market_data/csv/*.tqsdk.5m.csv` · 145 合约 · 5m OHLCV
- 关键复现顺序：
  1. `h1_a3_skew_pooled_ic.py` → 生成 `h1_long_events.csv`（16,406 events, 40 合约）
  2. `c1_causal_tier_scan.py` → 生成 `c1_events_with_tier.csv`（含 tier 分类）
  3. `e2_expanded_causal_tier.py` → **扩到 145 合约** 生成 `expand/events_with_tier.csv`（55,877 events）
  4. `s1_skew_multi_angle.py` → 生成 `skew_wide/events_with_multi_skew.csv`（含 4h/8h/24h skew）
  5. `d1_daily_skew.py` → 生成 `daily_skew/daily_events.csv`（7,332 daily events）
- 因果性验证：`e1_v2_causality_ironproof.py` 225 event × 3 特征全部 max_abs_diff = 0.0000e+00

## 引用与后续

本批次可作为**后续任何 event-driven 因子主题的方法论参考**：

- 立题时读 `va-asymmetry-family-retrospective.md` 的"系统性错误清单"避免重蹈覆辙
- 特征入池前跑 `e1_v2_causality_ironproof.py` 范式的双数据源对比
- 小样本 Sharpe>1 时跑 `e3_selection_bias_check.py` 范式的随机等大子样诊断
- 广度扫描时用 `s2_broad_ic_scan.py` 范式（不做慢的 cluster bootstrap，先算 pooled IC + per-symbol 一致性）
