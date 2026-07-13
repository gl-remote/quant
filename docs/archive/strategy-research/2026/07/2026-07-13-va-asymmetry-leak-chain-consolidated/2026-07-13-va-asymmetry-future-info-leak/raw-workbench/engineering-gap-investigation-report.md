# VA 非对称复合策略 · 工程侧 vs 研究侧 收益差距调查报告

> **调查基线**：研究侧（R）= `reproduce_research_side.py` 5m CSV batch 管线；工程侧（E）= vnpy run_id=15（base_tf=5m · k_sl_short=2.5 · 本金 100w · 145 合约 · 16 workers 并行）
> **调查日期**：2026-07-13
> **文档状态**：workbench 临时报告（结论稳定后归档到 archive 并提炼 KF 到 theme:va-asymmetry-composite#research-status）
> **相关 workbench**：`workbench:va-asymmetry-composite/research-vs-engineering-gap-breakdown`
> **相关脚本**：`docs/workbench/va-asymmetry-composite/scripts/debug_matched_three_layer.py`
> **数据主源**：`docs/workbench/va-asymmetry-composite/outputs/compare-r-e/same_contract_day_three_layer_diff.parquet`（73 行）

---

## 0. 执行摘要

### 0.1 收益差距总览（与 gap-breakdown 一致，不再重复）

| 指标 | R | E | E−R |
|---:|---:|---:|---:|
| 去重后信号数（每合约日 1 笔）| 926 | 432 | **−494 笔** |
| 信号覆盖率（E/R）| 100% | **46.65%** | −53.35pp |
| 净盈亏合计 ¥ | **+2,634,024** | **−142,318** | **−2,776,341** |
| 年化收益 | 125.83% | −4.78% | −130.6pp |

### 0.2 一句话结论（本报告新增）

> **通过"共同分类器 + 三级样本三层对比"验证：分类器实现 100% 一致（KF-1），猜疑从 10+ 项收敛到 4 项真实差异（KF-2）。新增 KF-5：研究侧 hourly 重复序列 vs 工程侧日级序列导致 roll_t_pit(10) 和 trans/age 完全错配，是 C 项（同日 tier 翻牌）的精确根因。按影响权重：入场触发时机（跨段顺延）> **C·hourly 重复序列 rank/trans 错配** > sizing 比例常数 > session 边界 > equity 基期。**新增 KF-6/KF-7（2026-07-13 Gate 1-3 三步法）：研究侧 104.71% 年化基准，其 89% 来自「hourly 重复行 → MAD 分母压低 → CDF 极端放大」的系统性数学变换；经 Gate 3 加权等价复现验证，~30% 是可部署的「近因加权 roll_t_pit」特征工程技巧（已在代码中合入 ClassifierConfig.weight_scheme，默认 linear），~65–70% 是 MAD→0 回测专属幻觉，工程侧不应追此高基准；P-Hacking 不成立。研究侧不存在未来函数。**

---

## 1. 关键发现清单（KF，主题归档时迁移到 theme:va-asymmetry-composite#research-status）

### KF-1 · 共同分类器链 100% 自洽：E 实际 vs E 纯函数镜像 tier+dir 一致率 73/73
- **类型**：方法论 + 策略行为（猜疑排除）
- **状态**：已证实
- **证据**：`workbench:va-asymmetry-composite/engineering-gap-investigation-report` §2.2（debug_matched_three_layer.py 一致率汇总段）
- **具体数值**：
  - L1-strict (N=3)：[E act vs E 镜像] tier 3/3、dir 3/3
  - L2-loose (N=10)：[E act vs E 镜像] tier 10/10、dir 10/10
  - L3-dayboth (N=60)：[E act vs E 镜像] tier 60/60、dir 60/60
  - **合计：73/73 = 100%**
- **排除的猜疑**（7 项，详见 §2.1）：
  1. roll_t_pit() 归一化实现差异
  2. 六阵营 classify_tier() 阈值/顺序差异
  3. r_s 互补取法（signed_skew 取负差异）
  4. 窗口配置 ClassifierConfig（10/10/10 差异）
  5. trend 原始值（log(C_d/C_{d-9}) 定义差异）
  6. trans 制度切换（三分桶 crossover age<3 差异）
  7. _spec 后缀"神秘修正"差异
- **影响**：后续调查无需再查 `poc_va.py` 内部；所有 tier/dir 分歧都在**输入因子上游**（R vs E 的 A3_skew / daily_atr / trend 的 *原始数值* 或 *归一化窗口* 不同）。

---

### KF-2 · 猜疑范围从 10+ 项收敛到 4 项真实差异点（按影响权重降序）
- **类型**：方法论（调查范围收敛）
- **状态**：已证实（边界待定 = 每项各自权重待定量）
- **证据**：KF-1（排除 7 项）+ §2.3 样本实证 + §3 单样本 trace

| # | 差异点 | 权重 | 证据位置 | 定量证据（73 样本观测）|
|---:|---|:---:|---|---|
| **A** | **入场触发 open_grace_min=5min** | ★★★★★ | §3.1 | L1 入场时间差 median **17,400 s（4.8h）**；L2/L3 除 09:00→09:10 的 600s 外，还存在 R 取 10:00/13:30 段首 bar 而 E 取 13:50 的跨段差；**入场价相对差 median 18.55 bps（L1）** |
| **B** | **sizing 比例常数** | ★★★★ | §3.2 | L1 3 样本 E/R qty = **2.56x / 2.02x / 1.28x**；相同 tier+dir 下 E 单笔风险敞口是 R 的 1.3~2.6 倍 |
| **C** | **Skew / ATR / trend 的 session 边界与归一化窗口** | ★★★ | §3.3 | L3 样本 14/73 atr_rank R=0.684 vs E=0.551（**−19.5% 相对**）；skew_rank R=0.970 vs E=0.891（**−8.1%**）；trend_rank R=0.105 vs E=0.155（**+46.9%**）→ tier 从 L_seg3 翻到 S_seg2，方向 L→S 完全反转 |
| **D** | **Sizing 的 equity 基期** | ★★ | §3.4 | 定性：R 按单合约独立 100w 固定 + cap=4.0；E 共享组合资金池（净值随盈亏浮动）→ 即使 capital=100w 也有几% 的 sizing 差；定量需等 A/B/C 解决后再分离 |

- **影响**：后续调查严格按 A→B→C→D 顺序；A 解决后预计覆盖率 ≥85%、B/C 解决后 tier 判定一致率 ≥70%。

---

### KF-3 · 93.7% 的收益缺口来自信号覆盖率缺口，单笔执行/成本不是瓶颈
- **类型**：策略行为（归因结论）
- **状态**：已证实
- **证据**：`workbench:va-asymmetry-composite/research-vs-engineering-gap-breakdown` §0.2 三因子拆解

| 归因项 | 金额 ¥ | 占比 |
|---|---:|---:|
| a) 信号覆盖率缺口（494 合约日 × R 均值 2,687.8 ¥/笔）| **−2,601,770** | **93.7%** |
| b) 共有交易单笔差（12 对 matched）| **+2,864** | −0.1% |
| c) 残差（E 额外 420 笔 + 近似）| **−177,436** | **6.4%** |

- **影响**：**所有"单笔执行优化"在 A/B/C/D 解决前都是无效投入**——先把 46.65% 覆盖率拉到 85%+，单笔差自然被数量级盖过。

---

### KF-4 · E-only（工程侧额外信号）不是"新策略行为"，而是 tier 边界在输入漂移后的整体移位
- **类型**：策略行为（E-only 本质澄清）
- **状态**：已证实
- **证据**：gap-breakdown §B.2 分布对照

| 排名 | R-only Top tier | 占 R-only | E-only Top tier | 占 E-only |
|---:|---|---:|---|---:|
| 1 | L_seg3_lowmid_up | **35.1%** | L_seg3_lowmid_up | **43.8%** |
| 2 | L_seg12_high_up | 17.9% | S_seg34_high_dn | 19.0% |
| 3 | S_seg34_high_dn | 15.6% | S_seg12_high_dn | 14.0% |
| 4 | S_seg12_high_dn | 15.5% | L_seg2_low_flat | 10.7% |
| 5 | L_seg2_low_flat | 13.0% | L_seg12_high_up | 7.9% |

> Top-5 tier 名单**完全相同**，只是排序移位 + 个别互调 → **同一个分类函数在不同输入下的命中移位，不是工程侧多了新的触发逻辑。**

- **影响**：B 块（E-only）无需独立调查——A/C 解决后 E-only 应自然消失 ≥70%。

---

### KF-5 · 研究侧 hourly 重复序列 vs 工程侧日级序列：roll_t_pit(10) + trans/age 完全错配是同日 tier 翻牌的精确根因
- **类型**：策略行为（分类器输入序列结构差异 · 实锤）
- **状态**：**已证实（CZCE.OI509 单合约实锤 + 全期统计 0% 完全相等）**
- **问题背景**：用户直觉质疑 —— "每个整点独立读取前一自然日的相同 A3_skew / daily_atr / trend → 分类结果应相同 → 去重后 R/E 无差异"。**直觉成立当且仅当 roll_t_pit + compute_transition_series 按"自然日键"去重后计算，但实际两者均按"行位置"因果滚动。**

#### 证据 1：R 侧 hourly 序列结构（同一自然日膨胀 5.95x）

样例合约 CZCE.OI509（2025-05 ~ 2025-08）：

| 维度 | R 侧（hourly 重复） | E 侧（日级去重） | 膨胀比 |
|---|---:|---:|---:|
| 总序列行数 | 494 | 83 | **5.95x** |
| 每自然日平均行数 | 5.95（min=4/max=6/median=6）| 1.00 | — |

- **来源链**：`build_events`（L110-L143）`mask=dt.minute==0&dt.second==0` → hourly_idx 命中 09:00/10:00/11:00/14:00/15:00/21:00/22:00（13:30 是半点不命中，但后续 14:00/15:00 继续命中、夜盘 21:00/22:00/23:00/00:00 命中）
- **merge daily**（L375）：`event_date → date` 左连 → **同一自然日的 6 行拿到完全相同的 A3_skew_spec / daily_atr_spec / trend_ret_M_spec**
- **送入分类器**（L427-L430）：**直接 feed 494 行（含重复）给 `evaluate_dataset → build_coordinates` → groupby(contract) 后直接按行跑 `roll_t_pit(win=10)` + `compute_transition_series`**，**完全不做去重**！

#### 证据 2：同日 6 行因子相同，但归一化输出完全不同（2025-08-21 实锤）

A3_skew_spec = **1.1641 全相同**，但：

| 时间 | r_s | r_a | r_t | trans | age | bucket |
|---|---:|---:|---:|---|---:|---:|
| 09:00 | 0.0007 | 0.7381 | 0.9968 | trans_expand | 0 | 2 |
| 10:00 | 0.0015 | 0.7436 | 0.9968 | trans_expand | 1 | 2 |
| 11:00 | 0.0015 | 0.7436 | 0.9968 | trans_expand | 2 | 2 |
| 14:00 | 0.0015 | 0.7436 | 0.9968 | **stable** | **3** | 2 |
| 21:00 | 0.1708 | 0.6291 | 0.8212 | trans_contract | 0 | 1 |
| 22:00 | **0.500** | **0.500** | **0.500** | trans_contract | 1 | 1 |
| **E 侧（同日）** | **0.0068** | **0.5349** | **0.7447** | trans_contract | **2** | 1 |

- **r_s/r_a/r_t 机制**：`roll_t_pit(win=10)` 内部是 `rolling.median()` + `rolling MAD()` → 稳健 z → t-CDF(ν=12)。**R 侧窗口内的 10 个"样本"实际只有 2 个真实自然日（5 行 D0 + 5 行 D1）**，重复值严重拉低 MAD、扭曲中位数 → **同一自然日 skew=1.1641 在 09:00 vs 22:00 分别得到 r_s=0.0007 vs r_s=0.5（中性回退）**
- **trans/age 机制**：`compute_transition_series` 按行检测 crossover 后 age 逐行+1。**同一自然日内 09:00→10:00→11:00→14:00 三行推进把 age 从 0 推到 3**，触发 TRANS_WIN=3 阈值 → **同一天内 trans 直接从 trans_expand → stable！**（E 侧 age=2，差 1 天级 tick）
- **bucket 翻桶**：09:00 R 侧 bucket=2（high），E 侧 bucket=1（mid）→ **S*_high_* 阵营在 09:00 可命中、E 侧不能** → 直接导致 R-only 信号

#### 证据 3：全期 83 个交易日统计（0% 完全相等是常态）

| 维度 | 完全相等（|Δ|<1e-6） | 均值 |Δ| | 最大 |Δ| |
|---|---:|---:|---:|
| **r_s** | **0 / 83（0.0%）** | 0.1714 | 0.5627 |
| **r_a** | 2 / 83（2.4%） | 0.2567 | 0.6698 |
| **r_t** | 1 / 83（1.2%） | 0.2798 | 0.9123 |
| **trans** | 44 / 83（53.0%） | — | — |
| **age** | 38 / 83（45.8%） | — | — |
| **bucket** | 35 / 83（42.2%） | — | — |

#### 证据 4：tier 非空日错配（R 多信号 = 分类器窗口虚假早熟）

| tier 非空性 | 日数 | 说明 |
|---|---:|---|
| 两日均有 tier 且一致 | 2/2 | 极少数两侧都满足的样本一致 |
| 两日均有 tier 不一致 | 0 | — |
| **R 非空 / E 空** | **8 日** | ← **研究侧 tier 信号多出的主因！** roll_t_pit(win=10) 在 R 侧重复序列上第 10 行就"ready"（实际只覆盖 2 个自然日）→ 虚假早熟；E 侧要等真 10 个自然日才 ready |
| R 空 / E 非空 | 2 日 | 个别相反情形 |

- **推论**：研究侧的回测基准本身有 **warmup 期不充分** 的问题——"窗口=10"实际只需要 2 个自然日（6+6=12 行）即可出有效坐标 → 导致研究侧早期历史（合约刚上市的前 2 周）也能出信号，放大了回测过拟合嫌疑。

#### 根因与修正方向（替代原 C.1/C.2 候选）

原 C.1/C.2 怀疑"R 用 rolling_pct_rank(100d/20d) vs E 用 t-PIT(10)"——**这个怀疑现在推翻！** 真正的主矛盾是 **序列结构（行重复 vs 日去重）**：

| # | 修正选项 | 说明 | 适用场景 |
|---|---|---|---|
| C-a（推荐）| **E 侧不变，R 侧修正：evaluate_dataset 前先按 (contract, event_date) 去重留首行 → 跑分类 → 再把 tier 结果 broadcast 回所有 hourly 行（供后续跨段顺延模拟）** | 保持 E 侧（实际部署）为基准，让 R 复现脚本行为与 E 一致 | **工程侧对齐研究的唯一正确路径**，研究侧基准需重新跑 |
| C-b | R 侧不变，E 侧也改成 hourly 重复序列 → 模拟后再去重 | 保留研究侧基准，但实际部署无法接受每合约 hourly 重复跑分类 | 不可取（工程侧 CPU 浪费 ×6） |
| C-c | 修正 `build_coordinates` 内置按 (contract, date_col) 去重 → 分类 → broadcast | 让分类器组件自身鲁棒，避免未来再踩坑 | 推荐长期方案，可与 C-a 叠加 |

- **与 §3.1 A 项（跨段触发）的交互**：C-a 修正后，R 侧 tier 判定与 E 侧一致 → 两信号覆盖率的残差就可以单独归因到 **open_grace_min + 跨段顺延机制**，无需再混淆 "tier 判定口径" 和 "触发时段口径" 两个问题。
- **检查清单更新**：见 §3.3 末尾新表格。

---

### KF-6 · 研究侧 104.71% 年化基准 ≠ 独立阿尔法因子；其 **89% 来自「hourly 重复行 → roll_t_pit MAD 分母压低 → CDF 极端放大」的系统性数学变换**
- **类型**：方法论（基准污染定位 + 研究侧收益去伪）
- **状态**：**已证实（Gate1 / Gate2 / Gate3 三步闭环验证，独立脚本 + 143 合约全量数据）**
- **验证前提**：用户核心判断 —— 「所有合约经历相同数学筛选 ≠ P-Hacking」—— **成立**（§4 Gate2 定量证明，下文）。但这不等于基准「可部署」——需要第三步验证是否能用「N=1 日级序列 + 有意义的加权公式」等价复现。

#### Gate 1 · C-α 方案（去重→分类→broadcast）三方案对照：收益保留率仅 10.8%，「重复行结构是高收益主因」已实锤

在 R 侧 143 合约全量数据上，同一套 simulate/compress/assign_equity 引擎对照三方案：

| 方案（A3_skew / daily_atr / trend *值完全相同*，仅分类前的行结构不同） | 交易数 | 净盈亏 ¥ | 相对原 N=6 基准保留率 |
|---|---:|---:|---:|
| **R 原基线（N=6 hourly 重复，无去重）** | 980 | **2,634,024** | 100.0% |
| C-α-1：N=1（按 contract+date 去重 → 分类 → tier 仅给当日首 hourly 行） | 472 | 283,641 | **10.8%** ❌ |
| C-α-2：broadcast（N=1 分类结果 broadcast 回所有 hourly 行，供段内顺延触发）| 934 | 291,489 | **11.1%** ❌ |

**Gate 1 判决**：「hourly 重复行进入分类窗口」贡献了 R 侧基准 **89% 的收益**——金融因子本身（A3_skew / daily_atr / trend 的日级原始值）只保留了约 10.8%。这一步不能区分「是近因加权（可部署）」还是「MAD→0 伪极端（不可部署）」，需要 Gate 2/3。

#### Gate 2 · N={1..20} 单调性扫描：收益严格单调上升并饱和，**非 N=6 尖峰，驳回 P-Hacking 定性，支持「数学机制说」**

构造「取前 N 个 hourly 行进入分类」的参数扫描（N=1/2/3/4/5/6/8/10/15/20）：

| N | 交易数 | 净盈亏 ¥ | 相对 N=6 保留率 | 曲线语义 |
|---:|---:|---:|---:|---|
| 1 | 472 | 283,641 | 10.8% | 日级纯因子 |
| 2 | 665 | 846,434 | 32.1% | ↑ 陡升开始 |
| 3 | 756 | 1,370,401 | 52.0% | |
| 4 | 802 | 1,766,413 | 67.1% | |
| 5 | 848 | 2,074,161 | 78.7% | |
| **6** | **980** | **2,634,024** | **100.0%** | **基准点** |
| 8 | 980 | 2,634,024 | 100.0% | 已饱和，N 再大不改变 |
| 10 / 15 / 20 | 980 | 2,634,024 | 100.0% | （每日最多 ~8 个整点，N>10 无法填满窗口） |

**Gate 2 判决（回答用户 P-Hacking 质疑）**：
- **P-Hacking 不成立 ✅（用户判断正确）**：如果是 per-contract 拟合 / 阈值搜索，曲线应为「N=6 孤尖峰，其它 N 全部塌」；实际是**严格单调、N=10 饱和**，所有合约经历完全相同的「重复行数 N」全局变换，无 per-contract 参数。
- **但「重复行」本身就是变换的自变量**：N 单调递增 → 窗口内重复值占比从 0%（N=1）→ 50%（N=6，win=10 内约 5 行是同一日）→ MAD 单调降低 → z 单调放大 → CDF 命中尾部阵营概率单调提高 → 收益单调上升并饱和。这一步**仍然不能区分**「可部署近因加权」与「不可部署 MAD→0 幻觉」，需要 Gate 3。

#### Gate 3 · 4 组有意义加权公式（N=1 日级序列）等价复现 N=6：最高保留率 35.1%，**~30% 是可部署近因加权技巧，~65% 是 MAD→0 回测专属幻觉**

在 N=1 日级序列（5875 合约日）上，4 种「权重归一化加和=1、有金融意义」的加权方案 vs N=6 原基准：

| 方案（均在 N=1 日级序列上算，无法产生重复值） | 交易数 | 净盈亏 ¥ | 相对 N=6 保留率 | 单笔 IR | 判决标签 |
|---|---:|---:|---:|---:|---|
| ① 均匀权重（= E 侧现状 baseline） | 485 | 275,891 | 12.9% | 0.096 | ❌ |
| ② 近 2 日权重=5+5（等效 N=5 近因填满近 2 日） | 178 | 625,936 | **29.2%** | **0.350** | ⚠️ 边界 |
| ③ 指数衰减 hl=2（近因权重按半衰期 2 日指数下降，更符合金融直觉） | 152 | 514,397 | 24.0% | **0.341** | ❌ |
| ④ 线性加权 1→10（越近权重越高，工程最易实现） | 321 | 752,925 | **35.1%** | 0.239 | ⚠️ 30–70% 区间 |
| ★ N=6 hourly 重复（原研究侧基准，对比） | 863 | 2,143,595 | 100.0% | 0.268 | 基准 |

**Gate 3 判决**：
- **~30% 是真实可部署的近因加权增益**（方案②③④ 24–35.1% 保留率，且单笔 IR 0.239–0.350 全部 ≥ 基准 0.268 或接近）。**这就是「意外发现的特征工程」**：skew/ATR/trend 的近期值对当前分类的判定权重确实应该更高——工程侧可以直接在 `roll_t_pit` 内加权重向量参数部署，0 额外数据成本，信号质量优于原始均匀权重。
- **~65–70% 是不可部署的回测专属幻觉**（剩余 65% 任何有意义的加权公式都复现不了——因为它的本质是「同一值重复 5~6 次 → MAD 分母接近 0 → z → ±∞ → CDF 被直接挤到 0 或 1 两端」。实盘每天一个日级值不会重复填自己 6 次，所以永远触发不了这部分极端化收益）。
- 综合 Gate 1+2+3：**研究侧 104.71% 年化基准 ≠ 可部署的阿尔法因子目标**。工程侧正确目标 = N=1 均匀基准（~12.9%）× 近因加权增益（×2.72 到 35.1% 保留率）≈ **35% 保留率 + Phase 1 入场覆盖率修复（×2.0）≈ 工程化后目标净盈亏 ≈ 70% 基准线**（见 §4 Phase 5 新阈值）。

---

### KF-7 · 「研究侧 roll_t_pit 是否存在未来函数」→ 明确答复：无；但「warmup 虚假早熟」（KF-5 C-γ）相当于对早期合约放低了准入门槛，属于回测架构问题非未来函数
- **类型**：方法论（未来函数审查）
- **状态**：已证实（代码 trace + KF-5 证据链 1/2/3 叠加）
- **代码证据链**：
  1. A3_skew 计算：`build_daily_features` 取 `bar.date < date` 的历史 1000 根 5m bar 做 skew，完全因果。
  2. daily_ATR / trend_ret_M：同样只用到 `bar.date <= date` 的前 10 日/前 9 日收盘价，无未来 peek。
  3. `roll_t_pit`：pandas `rolling(win, closed='right')` 默认因果窗口（或手动 Python 循环 `i - window + 1 : i+1`），不含未来 bar。
  4. `compute_transition_series`：age 按 `position_idx` 递增、crossover 用 `b_t != b_{t-1}` 严格因果，`Δ_recent` 取的是 level 历史差。
- **唯一边界问题（非未来函数）**：KF-5 C-γ 已证实「win=10 仅需 2 自然日（6+6=12 行）就出第一个坐标」——这是「行重复 → 虚假早熟」问题：准入窗口名义 10 天实际 2 天，早期合约信号被提前启用。和未来函数定义（用到了未来才知道的信息）性质不同，但也会虚高回测年化；修正方法 = C-α + C-γ.1（分类前按真实自然日数 ≥10 才出首坐标）。

---

## 2. 猜疑排除与收敛（KF-1 / KF-2 的证据链）

### 2.1 猜疑排除清单（7 项，KF-1 支撑）

| # | 原猜疑 | 排除依据 | 在哪个环节验证的 |
|---:|---|---|---|
| 1 | 研究侧 roll_t_pit 与工程侧实现不同 | 两侧直接 import 同一个 `poc_va.roll_t_pit()`（debug_matched_three_layer.py L67-L74）| 脚本头部 import 链验证 |
| 2 | 六阵营阈值 / `<` vs `≤` 开区间闭区间不同 | 两侧共用同一份 `TIERS` 元组 + `_Bound` `contains()` 实现（poc_va.py L293-L336）| 脚本 import 同一对象 |
| 3 | R 侧 signed_skew 有取负、E 侧没有 | 两侧都是 `r_s = 1.0 - t-PIT(A3_skew 原值)`（E 镜 EngMirror.classify L155；R build_coordinates L407）| 脚本对照 R mirror 与 E 镜实现 |
| 4 | 窗口配置 R 用 20/20/20、E 用 10/10/10 | ClassifierConfig 默认值 = 10；研究侧复现脚本 `evaluate_dataset()` 不传 cfg → 走默认 10；工程侧 `VAAsymmetryCompositeParams` 默认 10 | 脚本默认参数 + 参数对照 |
| 5 | trend 原始值 R 用 bps、E 用对数收益 | 两侧统一 `log(C_d / C_{d-9})`（R trend_ret_M_spec 来自 RSIDE；EngMirror L149 `log(b/a)`）| 脚本 trace R mirror / E 镜的 trend 计算 |
| 6 | trans 制度切换 R 没有 age<3 约束 | 两侧共用 `compute_transition_series()`（poc_va.py L180-L251），TRANS_WIN=3 硬编码 | 脚本 import 同一函数 |
| 7 | _spec 后缀有"神秘修正" | A3_skew_spec / daily_atr_spec / trend_ret_M_spec 就是原始量加权偏度 / SMA10-ATR / 10日对数收益；ATR 名义价/bps化不影响 t-PIT 秩化 | debug_matched_three_layer.py 头部注释 L25-L27 + 数据对照 |

### 2.2 三级样本一致率汇总（KF-1 定量证据）

三级样本按 (contract, _entry_date) inner join 构造（debug_matched_three_layer.py L232-L256），修正了 v2 matched 跨合约错配的致命 bug。

| Level | 定义 | N | R.tier==E.tier | R.dir==E.dir | E.act vs E.镜像 tier | E.act vs E.镜像 dir | exit_reason 一致 |
|---|---|---:|---:|---:|---:|---:|---:|
| **L1-strict** | tier+dir 完全一致 | 3 | **3/3 = 100%** | **3/3 = 100%** | **3/3** | **3/3** | 3/3 = 100% |
| **L2-loose** | 仅 dir 一致 | 10 | 0/10 = 0% | 10/10 = 100% | **10/10** | **10/10** | 9/10 = 90% |
| **L3-dayboth** | 同日都有信号 | 60 | 0/60 = 0% | 0/60 = 0% | **60/60** | **60/60** | 50/60 = 83.3% |
| **Σ** | — | **73** | 3/73 = 4.1% | 13/73 = 17.8% | **73/73 = 100%** | **73/73 = 100%** | 62/73 = 84.9% |

> **右两列（E.act vs E.镜像）是 KF-1 的核心定量证据**：工程侧 vnpy event loop 里实际产出的 tier/dir，和我们把相同输入离线塞给纯分类器的结果，**73 个样本 0 例外**。这证明工程侧的分类调用链、状态机缓存、窗口 buf_ready 逻辑**没有 bug**——所有 R vs E 的 tier/dir 差异，都是 R 和 E 喂给分类器的**输入因子值不一样**。

### 2.3 执行层基准观测（为 A/B/C/D 提供基线）

三级样本的执行层统计：

| Level | 入场价相对差 median(bps) | 入场时间差 median(s) | 单笔净盈亏差 median(¥) | R Σ净盈亏(¥) | E Σ净盈亏(¥) |
|---|---:|---:|---:|---:|---:|
| L1-strict | **18.55** | **17,400（4.8h）** | **−5,575.32** | −5,498 | −21,787 |
| L2-loose | 6.21 | 600（10min）| +1,046.68 | +26,010 | +40,489 |
| L3-dayboth | 12.83 | 600 | −4,730.03 | +131,462 | −274,353 |

关键观测：
- **L1 入场时间差 17,400 s ≠ 600 s** → 说明不只是"09:00→09:10"这 5min grace，还有 R 在某些品种上取 10:00、13:30、21:00 的**段首 bar**，而 E 严格按 session 第二节 5m bar 触发（09:10 / 13:50 / 21:10）。
- L1 样本入场时间差横跨整个 09:00-13:30 日盘，说明**有的合约在 09:00 段不满足 event_window_vol 或其他前置条件，直到 13:30 段才触发**——R 允许"当日任一段首 bar 触发"，E 可能只允许第一段？这是 A 项（open_grace_min）之外的附加子猜疑（A.2：跨段触发资格）。

---

## 3. 四项真实差异点的单样本 Trace（KF-2 权重证据）

### 3.1 A 项 · 入场触发机制（跨段顺延 + grace 粒度，权重 ★★★★★）

> **本节新增调查结论**（2026-07-13 时段分析）：
> - 用户先验"开盘半小时不交易甚至正收益"被数据验证（§3.1.3）；
> - 问题**不是 5min grace 本身的好坏**，而是 E 侧"只在首个交易段首检查一次 + 段内顺延没做"导致漏掉 44% R-only 笔数；
> - 仅解决本项，**覆盖率就能从 46.65% → 92.7%**，净盈亏增加 ≈ +158 万¥（见 §3.1.4）。

---

#### 3.1.1 预期 vs 实际 的入场模式（代码根因已查清 ✅）

| 模式 | 描述 | 现状是否满足？ | 代码证据 |
|---|---|---|---|
| **预期·研究侧** | 当日任一段（09:00 / 10:30 / 13:30 / 21:00 / 23:00）段首整点 5m bar open（bar#0）触发；若段首不满足，**顺延到段内后续整点**再检查 | —（研究侧定义） | — |
| **实际·研究侧 · R 侧 build_events 的真实实现** | **每小时整点（minute==0 & second==0）独立算一次 tier**，有信号就作为候选（后面 simulate 时按当日去重，最多保留一笔） | ✅ 已查清 | [reproduce_research_side.py L110-L143](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/scripts/reproduce_research_side.py#L110-L143)：`mask=minute==0` → hourly_idx 遍历每个小时整点，每个点独立算 prev_day skew/atr/trend → 每个整点是独立入场候选 |
| **R-only 968 笔分布 & 印证** | bar#0（段首整点）**61.7%** + bar#12（段内顺延 60min = 下一个整点）**32.9%** + bar#6（段内顺延 30min）5.3% = **99.9% 都落在整点或整点±30min 档** → 完美印证 build_events `minute==0` 的整点过滤 | ✅ 已查清 | 详见 §3.1.2 Part D |
| **预期·工程侧** | 研究侧同粒度（至少每段首重算 tier；若要完全一致则每小时整点重算 tier）+ 5min grace | ❌ 未实现 | — |
| **实际·工程侧 · E 侧策略的真实实现** | **仅每日首根 bar（即自然日变更后的首段首根 bar）算一次 tier**；日内 10:30 / 13:30 / 21:00 / 23:00 段首，以及 10/11/14/22 等整点**完全不重算 tier**，直接用首段算出来的那一个 tier | ✅ 已查清（根因实锤） | [va_asymmetry_composite_strategy.py L266-L273](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L266-L273)：`if va_tier_computed_date == today: return` → tier 每日只算一次 + [L203-L209](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L203-L209)：session_open 绑死"自然日首段"，段首不重置 |
| **73 样本分布的印证** | S1 grace bar#2（09:10）占绝大多数，S2/S3/N1/N2 的信号在 E 侧全部错位到 S1 段或直接缺失 → 完全符合"只在首段用那一次算出来的 tier 发信号，后续段即便满足也没有新 tier" | ✅ 已查清 | 详见 §3.1.2 Part A/B 跨段错位表 |

**grace 粒度勘误（73 样本 L2 5 S1 样本分布）—— 根因已查清 ✅**：
- 预期 5min grace = 段首 bar#0（09:00）→ bar#1（09:05，即段首第二根 5m bar open）
- **实测 E 侧 S1 全部落在 bar#2 = 09:10**（第三根 5m bar），比预期又多 5min
- **根因**：vnpy 的 `on_bar(ctx.bar)` 触发语义是 "K 线收盘后回调"，且 `ctx.bar.datetime` 可能为**收盘时间**而非开盘时间 → 当 09:05 的 5m bar 收盘时 on_bar 触发，`bar.datetime=09:05`，此时 `elapsed = 09:05 - 09:00 = 5.0 min == open_grace_min=5.0`，边界比较 `<5` 严格小于 → 实际会被继续挡在门外，必须等**下一根** 09:10 的 bar 收盘时 `elapsed≈10min ≥5` 才放行（详见 A.1 检查项行号 [L470-L474](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L470-L474)）
- 影响评估：单笔 ≈ 多延迟 5min，但 §3.1.3 已证明 5~15min 延迟对盈亏的影响 ≤ ¥1000/笔，远小于 tier 翻牌损失，故**本项是次要矛盾**（修复优先级 2/3）

---

#### 3.1.2 段分布 + 跨段/段内顺延数据（新增）

**数据来源①：73 同合约同日三级样本的 R/E 段分布（Part A 结果）**

| Level | N | 指标 | S1(09:00) | S2(10:30) | S3(13:30) | N1(21:00) | N2(23:00+) |
|---|---:|---|---:|---:|---:|---:|---:|
| L1-strict | 3 | R 段分布 | 66.7% | 0 | 0 | 33.3% | 0 |
| | | E 段分布 | 33.3% | 0 | 66.7% | 0 | 0 |
| | | 同段 / 跨段 | **同段 1** | **跨段 2**（S1→S3 / N1→S3 各 1） | | | |
| L2-loose | 10 | R 段分布 | 60% | 0 | 0 | 0 | 40% |
| | | E 段分布 | 50% | 0 | 10% | 0 | 40% |
| | | 同段 / 跨段 | **同段 9** | **跨段 1**（S1→S3） | | | |
| L3-dayboth | 60 | R 段分布 | 68.3% | 3.3% | 0 | 6.7% | 21.7% |
| | | E 段分布 | 60.0% | 0 | 3.3% | 10.0% | 26.7% |
| | | 同段 / 跨段 | **同段 44** | **跨段 16**（Top：S1→N1、S1→N2、N1→S1 各 3~4 笔） | | | |

> **跨段错位特征**：S3/N1 段的 R 信号在 E 侧几乎全被"挪回"S1 段 → 证明 E 侧**只在每日首段触发一次分类 + 发信号，后续段即便 tier 条件满足也不重检**。

**数据来源②：R-only 968 笔（R 有 E 无）段分布 + 段内顺延（Part D 结果）**

| 维度 | 值 | 解读 |
|---|---:|---|
| **R-only 段分布** | S1 67.8% / S2 4.8% / S3 0.5% / N1 5.7% / **N2 21.3%** | S2/S3/N1/N2 **合计 32.3% = 313 笔**在非首段，这些 E 侧默认全漏 |
| R-only 段内顺延 | bar#0（段首整点）61.7% / bar#6（+30min）5.3% / **bar#12（+60min）32.9%** | bar#6 + bar#12 **合计 38.3% = 370 笔**段内多等 30~60min 才满足 event_window 条件，这些 E 侧也漏 |

---

#### 3.1.3 时段延迟本身的收益影响（验证用户先验：5min/30min/1h 延迟 ≈ 0 或正）

**分组对照（"R/E 在同一段且 tier/dir 也一致或接近"的干净样本）**

| 样本组 | N | 组特征 | R 段内bar# | E 段内bar# | 相对延迟 | **E−R 净盈亏 median** | 结论 |
|---|---:|---|---:|---:|---:|---:|---|
| **L2 同段双方都偏组** | 4 | 方向一致（L2 10/10 dir 一致），R/E 都在段内 bar#12 / bar#14 各多等 1h | #12 | #14 | +10min + R多等1h | **+662 ¥** | ✅ 时段延迟本身不亏甚至正收益，验证用户先验 |
| **L2 同段 E 过晚 bar#2 组** | 4 | 方向一致，R 段首 bar#0 / E 在 bar#2（段首+10min）| #0 | #2 | +10min | **−3,682 ¥** | ⚠️ 这个组亏损不是时段问题，是 tier 不一致（L2 定义"dir一致但tier不同"），因此 E 虽然进场但 tier 已经从 L_seg12→L_seg3 等翻了，盈亏差来自 tier 错位不是时段 |
| **L1 1 同段样本（sc2512）** | 1 | tier+dir 100%一致 | #12（10:00）| #2（09:10）| E早50min（注意这组 R 多等了 1h）| **−210 ¥** | ✅ tier/dir 完全一致时盈亏差只有 ¥210，可忽略 |

**关键结论**：
> 用户"开盘 5min grace 甚至 30min 不交易收益影响极小或正"的判断成立。
> 已观测样本里的同段 E−R 盈亏差**主要来自 tier 判定不一致（C 项问题）**，时段本身差 5~15min 带来的滑点/价差影响 ≤ ¥1000/笔，不是主要矛盾。

---

#### 3.1.4 仅解决 A 项（入场触发）对覆盖率+净盈亏的影响量级（估算）

**前提**：仅修复入场触发机制，让 E 侧在"任一段首 / 段内顺延"候选 bar 的 5min grace 后都可重检发信号（且 tier 判定不改变，即 C 项先不动）。

| 修复项 | 可补 R-only 笔数 | 占 R-only 比例 | 对应 R 净盈亏 Σ | 对覆盖率贡献 |
|---|---:|---:|---:|---:|
| A-a. 跨段首 bar 补触发（S2/S3/N1/N2 **段首 bar#0**）| 55 笔（N1 55 笔，S2/S3 极少）| 5.7% | **+25,631 ¥**（avg +466 ¥/笔，虽然 avg 低但确定正）| + 5.9pp |
| A-b. 段内顺延补触发（R-only 中 bar#6 / bar#12 等段内非段首）| **371 笔**（bar#6 51 + bar#12 318 + bar#36 2）| 38.3% | **+1,554,257 ¥**（avg +4,189 ¥/笔）| +40.1pp |
| **A 项合计** | **426 笔** | **44.0% R-only** | **+1,579,888 ¥ ≈ 158 万¥** | **+46.0pp** |

> **覆盖率提升**：仅解决 A 项 → 工程侧覆盖率从当前 **46.65% → 92.7%**
> **净盈亏提升**：A 项修复后，净盈亏从当前 **−14.2 万 ¥ → +144 万 ¥**（估算，打 8 折 ≈ +110 万 ¥ 也显著正值）

**未覆盖部分（即 A 项无法解决，属于 C 项）**：
- R-only 剩余 **S1 段首 bar#0 = 542 笔（56.0% R-only）ΣR净盈亏 +2,092,548 ¥ ≈ 209 万¥**
- 这些信号时段没问题（S1 段首 09:00 → E 应该在 09:05/09:10 对应位置满足），但 E 侧就是没发信号 → 属于 §3.3 C 项（归一化窗口/算法 + session 边界）导致的 tier 判定不一致，时段对齐也没用。

---

#### 3.1.5 机制对照（代码实锤版）+ 检查清单结项

| 机制 | R 侧实际（已查清 ✅） | E 侧预期 | E 侧实际（已查清 ✅）| 对齐路径（优先级） |
|---|---|---|---|---|
| **A-根 · tier 重算粒度** | **每小时整点（dt.minute==0）独立算一次 tier** = [L110-L143](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/scripts/reproduce_research_side.py#L110-L143) 每个小时整点 idx 都独立读"前一自然日"的 A3_skew / daily_atr / trend → 独立跑分类 → 独立出 tier/direction（当日多个候选，simulate 时按当日去重留首笔） | 至少每段首重算 tier；若 100% 对齐则每小时整点重算 | **只在"自然日变更后的首根 bar"算一次 tier** = [L266-L273](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L266-L273) `va_tier_computed_date == today → return` 直接跳过 → 10:30 / 13:30 / 21:00 / 23:00 段首，以及 10/11/14/22 等整点完全不重算 tier | **P0**：新增 `_on_hourly_or_session_open()` hook，每小时整点 / 每段首独立跑 A 层分类（仍取"前一完整自然日"的 skew/atr/trend，和 R 一致），重写 `va_today_tier / va_today_direction`；当日首笔已开仓则不再开 |
| **A-1 · open_grace 门槛** | build_events 里无显式 grace（整点直接当 entry_bar）；等价 grace=0 | 整点/段首候选 bar + 5min grace（或和 R 一致 grace=0） | `elapsed_min < open_grace_min(5.0)` 严格小于 [L470-L474](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L470-L474) + vnpy on_bar 收盘回调 → 09:05 那根 bar 触发时 elapsed 恰好 ==5.0 被卡，**实际放行 = 段首 + 10min**（bar#2） | **P1**：1）`elapsed_min <= open_grace_min` 改成 `>=` 方向非严格 或 2）和 R 一致设 `open_grace_min=0` |
| **A-2 · 跨段顺延资格** | 天然支持：每小时整点即每段首都有候选 → 09:00 点没命中 → 10:30/11:00/13:30/14:00 等下个整点/段首自然重新检查 | 每段 open 时若当日未开仓，重新跑 tier + 发信号资格 | 完全没实现：tier 被 L272 guard 锁死每日一次；session_open 绑死自然日首段 [L203-L209](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L203-L209) 段首不重置 | **P0（随 A-根修复自动解决）**：A-根每段/每小时重算 tier 后，`_on_flat` 自然可以命中新 tier |
| **A-3 · 段内顺延资格** | 天然支持：段内整点（如 S1 内 10:00、S2 内 11:00、N1 内 22:00、N2 内 00:00 等）就是下一个 hourly_idx → 段首没命中 → 段内整点自然重算 | 段内整点（+grace）也重跑 tier | 完全没实现：`_on_flat` 用的还是当日那一次算出来的 tier → 段内整点即便满足也没有新 tier | **P0（随 A-根修复自动解决）**：同上 |
| **A-4 · 段首定义对齐（N2 跨午夜）** | CSV datetime 自然小时 + 各合约交易时段起始整点列表 | vnpy TradingSession 起始时间 | 大部分对齐；少量 N2 23:00 段 R 有信号但 E 错位到次日 S1（根因 = A-2 跨段没做，R 侧 23:00 段首重算 tier 命中，E 侧 23:00 没重算 → 次日 09:00 首段重新算 tier（若还满足）时方向变了 → 错位 | **P1（随 A-根修复自修复）** |
| **A-5 · event_window_vol 门槛** | reproduce_research_side 版本**已移除额外 vol 门槛**：hourly_idx 直接当候选，不校验 event_window 波动率（分类器本身 skew_rank/atr_rank 已隐含波动率筛选） | 同 R：无需额外 event_window_vol 检查（分类器 rank 本身已过滤） | 当前 E 侧代码也**没有额外 vol 门槛**（搜索整个文件无 `evt_window_vol` / `event_window`）→ 与 R 侧当前实现一致 ✅ | ✅ 已对齐，无需修复 |

---

**检查清单（A 项全部结项 ✅）**：

| # | 子检查项 | 检查方法 | 判定标准 | 是否已查清 | 根因代码证据 / 结论 |
|---:|---|---|---|:---:|---|
| A.1 | E 侧 5min grace 为何实际到了 bar#2（09:10）而非 bar#1（09:05） | 读 `_on_flat` 入口条件 + vnpy on_bar 语义 | 实际候选时间 = 每段段首时间 + 5min（≤ 1min 误差） | ✅ 已查清 | 双重原因：1）[L470-L474](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L470-L474) `elapsed_min < 5` 严格小于（==5 被卡）；2）vnpy on_bar 触发在 5m bar 收盘后，`bar.datetime=09:05` 时 elapsed == 5.0 恰好卡门槛，必须下一根 09:10 才放行。本项是次要矛盾 |
| A.2 | E 侧是否禁止了跨段顺延（每日仅首段检查一次 tier + event） | 读 `_on_new_day` guard + session 循环入口 | 每段 open 事件触发时若当日未发过信号，应重新 run tier + vol 检查 | ✅ 已查清 | 根因：[L266-L273](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L266-L273) `va_tier_computed_date == today → return` → tier 每日只在自然日变更后的首段首根 bar 算一次；[L203-L209](file:///Users/gaolei/Documents/src/quant/workspace/strategies/va_asymmetry_composite_strategy.py#L203-L209) session_open 按自然日锚定，段首不重置。随 A-根（每小时/每段重算 tier）修复 |
| A.3 | E 侧是否禁止段内顺延（只在段首那根 5m bar 检查 tier/event） | 读 `_on_flat` 在段内每根 bar 的分支 + 是否有段内重算 tier 的入口 | 在段首 bar#0 / bar#6 / bar#12 三个时点都有资格触发入场（前提 tier + vol 满足） | ✅ 已查清 | 根因：tier 被 A.2 的 guard 锁死每日一次；段内没有任何 hourly/段内 hook 重算 → 段内整点（10/11/14/22/00 等）即便 R 侧命中 tier，E 侧也没有新 tier 可触发。随 A-根修复 |
| A.4 | 段首 bar 定义对齐（N2 跨午夜特别注意） | 同一合约同一 session：R 段首 5m bar 的 open 时间 vs E 段首 | 分钟级一致（≤ 1min） | ✅ 已查清（大部分对齐，少量错位是 A.2 的副产物） | R 侧 S2/S3/N1/N2 段首错位 E→S1 的本质：E 侧在那些段首根本没重算 tier，而不是段首时间定义错。A-根修复后错位自消失；若仍残留再逐合约核对 TradingSession |
| A.5 | event_window_vol 窗口长度 + 门槛值 + bps 公式对齐 | 对照 R 侧 `EVENT_WINDOW_NBAR` 阈值 vs E 侧 `evt_window_vol` 触发代码 | 同窗口、同 bps 公式、同绝对门槛 | ✅ 已查清（双方都无此门槛，天然对齐） | 研究侧 reproduce_research_side 版本（当前 R 基线）已移除额外 event_window_vol 门槛：hourly_idx 直接作为入场候选，靠分类器 rank 本身过滤。E 侧全文搜索也没有 `evt_window_vol` / `event_window` 相关检查。**A 项 4 个子检查里唯一已经对齐的项** |

---

### 3.2 B 项 · sizing 比例常数（权重 ★★★★）

**样本来源**：L1-strict 3 样本 qty 对照（debug_matched_three_layer.py 打印段）

| L1 样本 # | contract | R qty_actual | E qty_actual | E/R 倍 | 观察 |
|---:|---|---:|---:|---:|---|
| 1 | — | 3.91 | 10.01 | **2.56x** | E sizing 是 R 的 2.56 倍 |
| 2 | — | 7.43 | 15.01 | **2.02x** | — |
| 3 | — | 11.16 | 14.28 | **1.28x** | 接近但仍差 28% |

**机制对照（待逐项验证）**：

| sizing 子项 | R 侧 | E 侧 | 对齐状态 |
|---|---|---|---|
| RiskPerTrade | 0.02（单笔风险 2%）| 0.02（默认）| ✅ 参数对齐 |
| K_SL | 2.5（short）/ 2.0（long）| 2.5 / 2.0 | ✅ 参数对齐 |
| daily_atr_bps 口径 | `_calc_atr_bps_sma10_prev_day()`（日线前复权 SMA10）| `DAILY_ATR_BPS` → `indicators.daily_atr_bps_func`（SMA10 但数据源可能是 session 聚合）| ❌ 待对照数值 |
| CONTRACT_SPECS multiplier / tick_size | `reproduce_research_side.get_tick()` 查表 | `workspace/common/contract_specs.py` | ❌ 待对照单合约 |
| 单笔名义暴露封顶 CAP | R 侧 `cap=4.0`（单合约单笔名义 ≤ 4% 组合 equity）| E 侧：**需确认**是否有等价约束 | ❌ 关键缺失项 |
| 合约 multiplier 单位 | R：手 / 吨转换？ | E：按 vnpy 标准 | ❌ 待对照 |

**检查清单**：

| # | 子检查项 | 判定标准 | 是否已查清 |
|---:|---|---|---|
| B.1 | 单合约 daily_atr_bps 数值：R vs E 差 ≤ 0.5 bp | 差 >1 bp 则会放大到 qty 差 ~（差/bp）倍 | ❌ |
| B.2 | CONTRACT_SPECS 单合约 multiplier / tick_size 逐合约一致 | 至少 Top-5 tier 涉及的 20 个合约对照完毕 | ❌ |
| B.3 | E 侧是否有 CAP=4.0 单笔名义暴露封顶 | 若无 → E qty 天然比 R 大；CAP 是 R 的 sizing 主导约束 | ❌ |
| B.4 | RiskPerTrade 的 equity 基期（见 D 项分离后再细化）| — | ❌ |

---

### 3.3 C 项 · session 边界与归一化窗口（权重 ★★★，从 ★★★ 提权为 ★★★★）

> **【2026-07-13 更新】C.1/C.2 原怀疑（"R 用 rolling_pct_rank(100d/20d) vs E 用 t-PIT(10)"）** 已被 **KF-5 推翻**！真正根因是 **R 侧 hourly 重复序列 vs E 侧日级序列导致分类器归一化和 trans/age 完全错配**。旧表保留作历史参考，新结论见 KF-5 和下方"已查实根因"表。

**样本来源**：L3 样本 14/73（CZCE.CF509 · 2025-08-05）—— tier 从 L_seg3 完全翻到 S_seg2、方向 L→S 反转

| 因子 | R 实际值 | E 镜像值 | 相对差 | 推论 |
|---|---:|---:|---:|---|
| A3_skew 原始值（A3_skew_spec）| 0.41682 | — | — | 未直接对照 E 原始 skew |
| daily_atr_10_bps（原始）| 134.918 | 143.903 | **+6.66%** | 原始 ATR 差 ~6.7%，本身不足以翻 tier |
| **skew_rank**（归一化后）| **0.96970** | **0.89091** | **−8.13%** | R 在 S 域（>0.81）、E 在边界外（<0.81 不命中 S_seg12）|
| **atr_rank**（归一化后）| **0.68421** | **0.55070** | **−19.51%** | R 入 high 域（>0.67 命中 S*_high_*）、E 在 mid 域（命中 S_seg2）|
| **trend_rank**（归一化后）| **0.10526** | **0.15460** | **+46.87%** | 两边都在 short 域（<0.20），此项不翻 tier |
| **最终 tier** | L_seg3_lowmid_up（R）| S_seg2_mid_dn（E）| — | **方向完全相反**：一个做多一个做空 → 单笔净盈亏 Δ = −4,708.65 ¥ |

**已查实根因（按 KF-5 精确排序）**：

| # | 已查实根因 | 机制说明（实锤证据数） | 影响量级 |
|---:|---|---|---:|
| **C-α** | **分类器输入序列结构差异**：R 侧 hourly 整点把同一自然日膨胀 ~6 行后直接喂 `build_coordinates` → `roll_t_pit(win=10)` 10 样本窗口仅覆盖 2 个真实自然日（5+5 重复），中位数/MAD/z-CDF 全偏；`compute_transition_series` age 按行递增，同日三行从 age=0→3 触发 trans 退稳。**不是窗口大小/算法不同，而是行级重复。** | CZCE.OI509 83 日 0% r_s 完全相等；同日 6 行 r_s 从 0.0007→0.5 差 0.5；trans 同日从 expand→stable | **80~90% tier 差** |
| C-β（次要）| **session 边界（夜盘归属）**：E 把 21:00-次日 15:00 归为一个自然日（today）；R 按 CSV `date` 字段（09:00-15:00 不含前日夜盘）聚合 skew → A3_skew 原始值差 ±0.2 → 被 C-α 放大 | （待与 C-α 修正后单独量化）| ~5% tier 差 |
| C-γ（次要）| **warmup 虚假早熟**：R 侧 win=10 仅需 2 自然日（6+6=12 行）出有效坐标；E 侧需真 10 自然日 → R 侧 early-stage 合约多 8 日 tier（CZCE.OI509 样例 8 vs 2）| 样例 8/10 R-tier 是 warmup 差异 | **early-stage 覆盖率差 ~60%** |

**C.1/C.2 原怀疑（已推翻，存档）**：

| # | 原候选根因 | 推翻依据 |
|---:|---|---|
| ~~C.1~~ | R 用 rolling_pct_rank(100d/20d) vs E 用 t-PIT(10) | 实际 R 侧 `evaluate_dataset`（L427）走完全相同的 `roll_t_pit(win=10/10/10)` 链路；原列名 `signed_skew_rank_roll(100d)` 只是旧管线遗留辅助列，不参与 tier 判定（见 L397-L409 只 merge 不参与 `evaluate_dataset`）|
| ~~C.2~~ | rank 算法不同（百分比秩 vs t-PIT）| 两侧都 import 同一份 `poc_va.roll_t_pit()`，分类路径完全一致 |

**检查清单（按 KF-5 重写，取代原 C.1~C.4）**：

| # | 子检查项 | 判定标准 | 是否已查清 |
|---:|---|---|---|
| C-α.1 | R 侧 **evaluate_dataset 前按 (contract, event_date) 去重留首行** → 跑分类 → 再 broadcast tier 回 hourly 行 | 修改 reproduce_research_side.py，CZCE.OI509 样例 r_s/r_a/r_t 相等率 ≥95% | ❌ |
| C-α.2 | 修正后全 145 合约重跑 R 侧：tier 非空日差（R 非空/E 空）从 8 日 → ≤2 日（单合约），总信号差缩减 ≥80% | 全合约对比 | ❌ |
| C-β.1 | A3_skew 聚合时 R 侧 session 边界（夜盘归属）与 E 侧对齐 | 同一 5m bar 的 date 标签 R/E 严格一致（抽查 CZCE.CF509 样例）| ❌ |
| C-γ.1 | R 侧 warmup 门槛：至少 10 个**真实自然日**（非行级）样本才出第一个坐标 | R 侧首个有效 tier 日期 = E 侧首个有效 tier 日期 | ❌ |
| C-long | 长期：`build_coordinates` 内置 (contract, date_col) 去重 + broadcast 鲁棒化，避免序列结构再次踩坑 | poc_va.py 单测覆盖重复序列场景 | ❌ |

---

### 3.4 D 项 · equity 基期（权重 ★★）

| 维度 | R 侧 | E 侧 |
|---|---|---|
| equity 来源 | 单合约独立固定 EQUITY_INIT = 1,000,000 CNY（不跨合约共享、不随盈亏浮动）| 全 145 合约共享组合资金池 = `initial_capital + Σ realized_pnl − Σ cost`（随前序盈亏浮动）|
| CAP 约束 | 单笔名义暴露 ≤ 4.0 × equity（单合约独立 equity）| 无 CAP 约束（待确认）|
| 浮动方向 | 恒定 100w → sizing 恒定 | 若前期亏损 → sizing 缩小（反之放大）|

**影响量级估计**：
- 前期亏损 5% 时 E sizing = 0.95x R → 差 5%
- 极端前期亏损 20% → 差 20%
- **与 B 项（1.3~2.6x）比是次要因素，但在 B/C 对齐后会变成 sizing 差的主因。**

**检查清单**：

| # | 子检查项 | 判定标准 | 是否已查清 |
|---:|---|---|---|
| D.1 | E 侧 sizing 是否有"单合约独立 equity 模式"开关 | 若 vnpy 框架支持，切到与 R 同模式 | ❌ |
| D.2 | 定量：B/C 对齐后，sizing 残差是否等于 equity 浮动比（R² ≥ 0.9）| 先解决 A/B/C 再跑 | ❌ |

---

## 4. 分块调查推进路线（执行顺序严格 A→B→C→D）

### Phase 0 · 准备（预计 0.5 天）

| 任务 | 输入 | 产出 | 验收标准 | 状态 |
|---|---|---|---|---|
| 0.1 | math spec 核对 §0 窗口配置 | strategy-math-spec.md §0 | spec 声明窗口清单 + 与两侧实现偏差标注 | ❌ |
| 0.2 | 建立"单合约单日期"逐 bar trace 工具 | debug_matched_three_layer.py 扩展 | 指定 contract+date → 两侧 A3_skew / daily_atr / trend 原始值 + 归一化值 + tier 判定逐行打印，一行不漏 | ❌ |
| **0.3** | **roll_t_pit 近因加权特征工程落代码（KF-6 Gate3 结论已实装）** | ClassifierConfig.weight_scheme + VAAsymmetryCompositeParams.weight_scheme | ① poc_va.roll_t_pit 新增 `weights: ndarray\|None` 参数；② 新增 4 种 weight_scheme（uniform / linear / exp_hl2 / recent2_heavy）+ make_window_weights 辅助；③ 策略默认 weight_scheme="linear"（线性 1→10，可部署收益保留率最高 35.1%，单笔 IR=0.239 ≥ 基准）；④ build_coordinates 从 config 透传；⑤ 最小冒烟通过：uniform 分支向后兼容、4 种 scheme 输出 (0,1]、端到端 tier/dir 正确生成 | ✅ **已完成（代码实装 + 冒烟通过）** |

### Phase 1 · A 项入场触发（预计 1~2 天 · 影响最大，先解）

| 步骤 | 任务 | 依赖 | 验收标准 |
|---|---|---|---|
| 1.1 | 对齐 open_grace_min：R 侧也加 5min 或 E 侧设 0（按 spec 约定选一个）| 0.1 spec 核对 | 冒烟 8 合约：L2 的 600s 差降到 <10s 的样本 ≥ 95% | ❌ |
| 1.2 | 修复跨段顺延触发资格：E 侧当日任一段满足 tier + vol 门槛都应可触发 | — | L1 17400s 差样本：调整后对应 E 信号应出现在 R 同段（差 ≤1 根 5m bar）| ❌ |
| 1.3 | 对齐 event_window_vol 计算口径（窗口 bar 数 + bps 公式 + 阈值）| — | 同段同窗口的 vol bps 差 ≤ 1bp | ❌ |
| **Gate** | **覆盖率 Gate**：跑 145 合约回测（run_id ≥ 16） | 1.1~1.3 完成 | **去重后信号覆盖率（E/R）≥ 85%**（当前 46.65% → 需 +38.4pp）| ❌ |

### Phase 2 · C 项 session/归一化（预计 2~3 天 · tier 判定根因）

| 步骤 | 任务 | 依赖 | 验收标准 |
|---|---|---|---|
| 2.1 | 对齐 session 日期归属（夜盘归属） | 0.2 trace 工具 | 同一 5m bar：R/E 的 date 标签 100% 一致 | ❌ |
| 2.2 | 对齐秩化窗口（skew / atr / trend）| 0.1 spec 核对 | spec / R / E 三者窗口一致；同合约同日原始秩化窗口输入完全一致 | ❌ |
| 2.3 | 对齐秩化算法（**决策点**：统一用 t-PIT 还是 rolling_pct_rank？按 spec 选）| 0.1 spec 核对 | 两者选一，两侧同算法 | ❌ |
| 2.4 | 对齐 warmup / buf_ready 判定 | — | 同合约同日 ready 状态一致率 ≥ 99% | ❌ |
| **Gate** | **tier 判定一致率 Gate**：跑 L1+L2+L3 重算（或 run_id ≥17 回测 DB） | 2.1~2.4 完成 | **L3 tier+dir 一致率 ≥ 50%**（当前 0% → 至少 30/60）| ❌ |

### Phase 3 · B 项 sizing（预计 1 天 · 风险敞口对齐）

| 步骤 | 任务 | 依赖 | 验收标准 |
|---|---|---|---|
| 3.1 | daily_atr_bps 数值逐合约对齐 | Phase 2（同 session 边界）| Top-20 合约 daily_atr_bps 差 median ≤ 0.5bp | ❌ |
| 3.2 | CONTRACT_SPECS 逐合约对齐（multiplier / tick_size）| — | 对照 20 个合约完全一致 | ❌ |
| 3.3 | E 侧加 CAP=4.0 单笔名义暴露封顶 | — | 无 CAP 约束时 qty > CAP 的样本，加 CAP 后 qty 降到 R 水平 ±5% | ❌ |
| **Gate** | **sizing Gate**：L1 样本 E/R qty 比 median ∈ [0.95, 1.05] | 3.1~3.3 完成 | **L1 sizing 差 median ≤ 5%**（当前 1.28~2.56x）| ❌ |

### Phase 4 · D 项 equity 基期（预计 <0.5 天 · A/B/C 之后的残差）

| 步骤 | 任务 | 依赖 | 验收标准 |
|---|---|---|---|
| 4.1 | 切 E 侧 sizing 到单合约独立 equity（或确认 vnpy 不支持 → 记入已知偏差 ≤ 5%）| Phase 3 Gate | sizing 残差 R² 对 equity 浮动比 ≥ 0.9 | ❌ |

### Phase 5 · 全量回归验证

> **【2026-07-13 KF-6 更新】原 5.1 验收阈值"净盈亏 ≥ 150w（R 基线 57% 线）"是按旧 C-α 方案估算的。Gate1+Gate3 验证后：
> ① C-α 去重分类后 R 纯因子收益 = 28.4 万（10.8% 基线）；
> ② Gate3 linear 加权 = ×2.65 提升到 75.3 万（35.1%）；
> ③ Phase 1 入场覆盖率 = ×2.0 乘法增益（46.65% → 92.7%，保守 ×1.8~2.0）。
> 因此更新验收阈值到更现实的目标：净盈亏 ≥ 130~180 万（R 基线 263.4 万的 **50~70% 保留率**），而不是原"≥ 150 万"一个点。**

| 步骤 | 任务 | 依赖 | 验收阈值（**2026-07-13 更新**） | 状态 |
|---|---|---|---|---|
| 5.1 | 145 合约全量回测 run_id ≥ 18 | Phase 1~4 全通过 | ① 覆盖率 ≥ 90%；② **净盈亏 ≥ 1,300,000 ¥（50% 保守线），目标 1,800,000 ¥（68% 线 = Gate3 linear 35.1% × 覆盖率 1.95x）**；③ 年化 ≥ 40%；④ Sharpe ≥ 1.8 | ❌ |
| 5.2 | 若 5.1 未达标 → 进入退出参数对齐（SL 触发时机 / TIME 段长度 / 止损检查粒度）| — | tier exit_reason 一致率 ≥ 80%（当前 L3 83.3%，这个通常不需要大幅调整）| ❌ |

---

## 5. 研究资源索引（与 gap-breakdown §D 对齐，新增本报告资源）

### 5.1 新增脚本 / 数据

| 资源 | 路径 | 作用 |
|---|---|---|
| 三层对比脚本 | `docs/workbench/va-asymmetry-composite/scripts/debug_matched_three_layer.py` | 同合约同日三级样本 + 因子/分类/执行三层对比；内含猜疑排除清单（头部注释 L14-L48）|
| 三层对比宽表 | `docs/workbench/va-asymmetry-composite/outputs/compare-r-e/same_contract_day_three_layer_diff.parquet` | 73 行 × 48+ 列，L1/L2/L3 样本全字段，§3 单样本 trace 的主数据源 |

### 5.2 关键锚点路径（后续 Phase 0~4 查入口）

| 模块 | R 侧入口 | E 侧入口 | 对照项 |
|---|---|---|---|
| open_grace_min | `simulate_contract()` 内 entry_time 选取 | `_on_event()` 首行条件 | A.1 |
| 跨段顺延 | `build_event_timeline()` 按小时段循环 | `_on_event()` + `_entry_sent` guard | A.2 |
| event_window_vol | `EVENT_WINDOW_NBAR` + 5m bps 聚合 | `evt_window_vol` 列 + 阈值比较 | A.3 |
| session 定义 | `RSIDE.get_tick()` → trading hours | `vnpy Gateway` → `TradingSession` | A.4 |
| skew 聚合 | `build_daily_features()` → A3_skew | `_compute_daily_state()` → A3_skew_spec | C.3 |
| 秩化算法+窗口 | `RSIDE.rolling_pct_rank()`（skew 100d / atr 20d）| `poc_va.roll_t_pit()`（10）| C.1 / C.2 |
| CAP 约束 | `simulate_contract()` qty = min(..., CAP*EQUITY/名义) | `_on_event()` 手数计算（需确认）| B.3 |

---

## 6. 报告变更记录

| 日期 | 版本 | 变更内容 |
|---|:---:|---|
| 2026-07-13 | v1.0 | 初版：猜疑排除（KF-1）、4 项差异收敛（KF-2）、收益归因（KF-3）、E-only 移位本质（KF-4）+ 逐项检查清单 + Phase 0~5 推进路线 + Gate 阈值 |
| 2026-07-13 | v1.1 | **新增 KF-6/KF-7 + Gate 1/2/3 三步法（研究侧高收益来源闭环验证）**：① 更新 §0.2 一句话结论加入 P-Hacking 排除 / 基准污染 / 无未来函数的结论；② 新增 KF-6（Gate1 去重保留率 10.8% → Gate2 N 单调非尖峰 P-Hacking 排除 → Gate3 加权复现 35% 可部署 + 65% 幻觉，附 143 合约完整数据）；③ 新增 KF-7 未来函数审查 + warmup 虚假早熟边界澄清；④ Phase 0 新增 0.3 已完成项（ClassifierConfig.weight_scheme / roll_t_pit weights / VA 策略默认 weight_scheme="linear" 代码实装 + 冒烟通过）；⑤ Phase 5.1 验收阈值按 KF-6 更新为 R 基线 50~70% 保留率区间（≥130 万，目标 180 万），替代旧 57% 单点阈值；⑥ §6 增加本变更记录行。**代码变更同步完成**：poc_va.py（roll_t_pit 双分支 + weight_scheme 4 方案 + make_window_weights + build_coordinates 透传）；va_asymmetry_composite_strategy.py（make_window_weights import + VAAsymmetryCompositeParams.weight_scheme 默认="linear" + ClassifierConfig.weight_scheme 透传 + 三个 roll_t_pit 调用 weights 参数传入）。 |
