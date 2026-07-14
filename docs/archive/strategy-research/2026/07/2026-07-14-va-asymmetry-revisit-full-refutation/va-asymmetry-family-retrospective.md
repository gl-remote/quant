# va-asymmetry 家族 · 全周期研究复盘

> 类型：Workbench 复盘文档
> 覆盖：2026-07-06 → 2026-07-14（8+ 天）
> 涉及主题：`poc-value-area-asymmetry` → `va-asymmetry-composite` → `va-asymmetry-revisit`
> 关联批次：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated`（6 个子批次）
> 状态：**主题冻结前的最终复盘 · 不为策略翻案，只为把方法学教训沉淀下来**

## 一、TL;DR

用 8+ 天时间、7 个 archive 批次、150+ 个脚本、55,877 event 数据，最终**没有产出任何可交易的策略**，主题需要冻结。这份复盘承认这个事实，把整个过程分成三段——**做得对的、做得局部严谨但全局失衡的、做错的**——分别沉淀。

- **做得对的**：文档规范、Barra 单因子筛选流程、因果性铁证方法、选样偏差诊断法
- **局部严谨但全局失衡**：把 6 天单押一个假设做 stage 1-4 深挖、跨阶段无 family-wise 多重比较控制、复杂化到藏了 7 天没发现的未来函数
- **做错的**：从一开始就选了一个 5m OHLCV 上先验成功概率极低的假设族（volume-profile skew），并把它当成"能挖出实盘策略"的核心方向

**主要价值不是 va-asymmetry 家族本身**，而是这条错误路径沉淀出的：
- **12 条 KF**（KF-1~KF-12），其中 6 条是可跨主题复用的方法论
- **6 条 F 系列反例**（F-13~F-18），后续主题禁止重跑
- **一套可复用的研究流程节点**（`factor-research-workflow.md` N-0~N-10）

## 二、时间线还原

### 阶段 1（2026-07-08，1 天）· poc-value-area-asymmetry

- 目标：单变量 A3_skew（成交量偏度）是否独立方向 alpha
- 数据：19 合约 · 5m
- 方法：pooled IC + cluster bootstrap + 分位扫参 + Bayesian 分层 + prev_ndays profile
- 输出：Stage 1 通过（DN 侧 A3_skew 独立信号）
- 判断：如果**当时立刻停下来做扩样 + LOPO + 换假设广度扫描**，本可以判决"skew 弱信号 · 不足以支撑策略"。但没有。

### 阶段 2（2026-07-08 后期，同天）· stage 2 跨周期护栏

- 目标：加入跨周期 + ν_implied + 4 主线 Bonferroni
- 数据：19 合约 → OOS 扩到 143 合约
- 结论：4/4 主线通过
- 判断：**这里发生了第一次质变**。原本应该做的是"跨假设广度扫描"（横向），实际做的是"同假设跨周期严格化"（纵向）。后续所有资源都锁进了这条纵深线。

### 阶段 3（2026-07-08 后期，同天）· stage 3 稳健性 12 格

- 目标：5 个任务 × ATR × trend 12 格 + prefix rank + 稳定/转换期
- 脚本：22 个 stage3 专属脚本
- 结论：5/5 任务全过 + 洞察 P~U + KF-16~24
- 判断：**stage 3 通过率非常高**（几乎 100%）本身就是过拟合信号。真实的 alpha 在 stage 1 就应该稳，而不是在 stage 3 通过更多约束——**这是幸存者偏差的教科书表现**。

### 阶段 4（2026-07-09 → 07-10，2 天）· stage 4 分类器 v4.0 + 6 tier

- 目标：三维 144 tier + FDR + 6 类合并降级
- 数据：143 合约 · 36,625 event
- 结论：144 tier 通过率 20% → 6 类合并 83% → 分类器 v4.0 冻结
- 判断：**"144 tier 通过 20% 就合并成 6 tier 让通过率变成 83%"** 这个操作在信息学上等价于"把不通过的 tier 平均到通过的 tier 里稀释噪声"。KF-29 说"合并降级优于精细切分"，但实际上是**用统计通过率来自证合并的合理性，循环论证**。

### 阶段 5（2026-07-09，同天）· poc-va-shaping

- 目标：塑形层（Cap / dedup / K_SL / H_vol / VW / W）
- 结论：B0 冻结 · Sharpe 2.70 · 年化 15.1% · MaxDD -2.4%
- 判断：Sharpe 2.70 / MaxDD -2.4% 是**离奇好**的指标。5m 期货组合策略在 2.5% MaxDD 下拿 2.70 Sharpe，任何有经验的量化经理看到都应该立刻怀疑"哪里进了未来信息"。**但当时的研究流程里没有这条 sanity check**。

### 阶段 6（2026-07-10，1 天）· va-asymmetry-composite v1.0 冻结

- 结论：策略层完成、B0 归档、写全套 spec/plan/params/impl/status 六件套
- 判断：**这是最应该刹车的时刻**。Sharpe 2.70 太可疑、B0 是 1/N 等权（说明组合层不产生 alpha）、名义暴露 653% 才 15% 年化（说明单笔 IR 很低）——**至少三个警告灯亮起，但都被"通过了就是通过了"的动量掩盖过去**。

### 阶段 7（2026-07-12，1 天）· mathspec + P0-P9

- 目标：把策略写成完整数学 spec，然后跑 P0-P9 参数敏感度
- 脚本：40+ 个 ai_tmp/*.py
- 结论：择时全灭（entry_mode 7 种全负），H_vol / K_SL / W / VW / Cap / dedup 全部无增量
- 判断：**P0-P9 结果诚实**——它告诉你"这个 B0 已经没有更好的调参方向了"。但**当时没有把这个结论解读为"整个策略架构没有 alpha"**，而是解读为"B0 是全局最优"。

### 阶段 8（2026-07-13，1 天）· engineering-fix

- 目标：工程侧（vnpy backtest）跟研究侧（notebook 回测）的 Sharpe 差 15 倍，找原因
- 脚本：MAD-fix + trend-offset-fix + batch backtest + R/E 对齐 + 5 次不同的 compare_R_E_*.py
- 结论：找了一整天没找到根本原因
- 判断：**这就是我"复杂化到藏了未来函数"的证据**。工程侧和研究侧 15× 差异，一天没排查出来，是因为特征侧 daily merge 泄漏被埋在了太多层抽象下面。

### 阶段 9（2026-07-13，同天）· future-info-leak 铁证

- 目标：R/E 对齐排查最后一步——检查特征侧是否有未来函数
- 关键脚本：`verify_leak_evidence_chain.py` + `verify_leak_by_truncation.py`
- 结论：**4 层证据链证明 daily 特征在 event_date merge 前未 shift(1)**，SHFE.rb2501 单事件 68 根未来 bar 泄漏
- 修复：shift(1) 后 Sharpe **3.47 → -1.60**、年化 **+63.44% → -38.25%**
- 判断：**这是本次 va-asymmetry 家族真正有价值的产出**——不是策略，而是"如何证明一个策略含未来函数的因果范式"。

### 阶段 10（2026-07-13）· 立 va-asymmetry-revisit 主题

- 目标：从灾难中回收资产
- 输出：`factor-research-workflow.md`（10 个流程节点）+ `hypothesis-inventory.md`（未验证假设）
- 判断：这个动作本身对——**把错误路径的资产做正交拆解**是标准的量化研究实践。

### 阶段 11（2026-07-14，本次会话 · 1 天）· revisit 落地

- H-1 判死（signed A3_skew 单变量 IC）
- Causal L_seg2 疑似 alpha → 扩样后判死
- 因果性铁证 + 选样偏差诊断
- Skew 派生 7 大类广度扫描 · 全线证伪
- 日线级 10d skew · 全线证伪
- **判决**：va-asymmetry 全家族在完整数据 + 严格 causal + 无选样偏差下**均无 alpha**

## 三、系统性错误清单

### 错误 1：**"广度优先"方法论写了但没执行**

主题 skill `quant-research-methodology` §1 明明说：

> 广度优先验证而非深度优先调参：假设生成 → 最简规则广度扫描 → 品种边界确认 → 深度优化 → 工程化

但整个 va-asymmetry 家族的实际路径是：

> 单假设最简规则（stage 1）→ **纵深跨周期严格化（stage 2）→ 稳健性 12 格（stage 3）→ 144 tier + 合并降级（stage 4）→ 塑形层参数扫描（Cap/dedup/W/VW）→ 择时 7 种（entry_mode）→ v4.0 冻结** → 组合层（Cap 4.0）→ 归档 v1.0

这是**从头到尾的深度优先**。中间没有一次退回来问"还有哪些 raw feature 我没测？"、"5m 期货上除了 skew 家族外的因子先验概率排序是什么？"。

**改法**：立项 checkpoint 就写死 "6 天预算里，前 3 天必须扫 ≥10 个正交假设"，任何主线不允许超过 40% 时间。

### 错误 2：**Stage 通过率单调递增没有触发过拟合警报**

Stage 1 通过 4/4 主线 → Stage 2 4/4 → Stage 3 5/5 → Stage 4 20% → 6-class 83%。

在**统计学上**，一条真实 alpha 在越严格的过滤下**应该通过率下降**（因为约束越多、噪声干扰越大）。如果通过率反而单调上升或者维持 100%，只有两种可能：
1. Alpha 极强（跟随机相比 SNR 极高）→ 但 Stage 1 A3_skew 单变量 IC 只有 0.02-0.03 级别，SNR 不高
2. **多重比较 + 幸存者偏差**（每一层都在筛掉不通过的样本再检验剩下的） ← **实际情况**

**改法**：**跨 stage family-wise 控制**——立项时预注册所有 stage 计划做多少次假设检验，用 total N 做 Bonferroni。KF-25 说"FDR 优于 Bonferroni"，但**FDR 只在同一层做多重比较有效，跨层深挖是它救不了的**。

### 错误 3：**Sharpe 2.70 + MaxDD 2.4% 没有触发 sanity check**

5m 期货组合策略在 MaxDD 2.4% 下拿 Sharpe 2.70，超过 AQR / DE Shaw / RenTech 公开披露的期货 CTA 部门业绩（这些顶尖机构长期 Sharpe 1.5-2.0）。

**如果一个模型的模拟业绩超过世界前 3 机构的实盘业绩，98% 概率是模型有 bug**——这是 López de Prado《Advances in Financial ML》里明确写的经验法则。

**改法**：**指标 sanity check checklist**——任何回测出来 Sharpe > 2.0、MaxDD < 5% 的策略，都不允许进入下一阶段，必须先做 3 层因果性检验（截断法 + shift(1) + 特征单测）。这条 checklist 应该固化到 `quant-research-methodology` skill。

### 错误 4：**架构复杂化到藏了 7 天未发现的未来函数**

从 poc_va (单变量) → va-asymmetry-composite (组合层)，中间涉及：
- 4 个 `_spec` 后缀的合成 daily 特征
- `_precompute_va_daily_lookup` 合成 lookup 表
- `roll_t_pit` PIT 归一化
- MAD-fix + trend-offset-fix
- 研究侧 (notebook) vs 工程侧 (vnpy) 双实现

**这些层之间没有 event-level unit test**。engineering-fix 那一整天在做 R/E 对齐，但**对齐的对象本身就有 bug**——两边算错的是同一个未来函数。

**改法**：**每个新特征入池前跑截断法单测**（`verify_leak_by_truncation` 范式，就是 e1_v2 里做的事）。这条应该固化为 CI/pre-commit 层的自动化检查。

### 错误 5：**先验假设选择错**

5m 期货 OHLCV 数据上，什么假设先验成功率高？

| 类型 | 5m OHLCV 上先验成功率 |
|---|---:|
| 微观结构因子（skew / kurtosis / imbalance）| **~10%**（微观信息大部分在 tick 尺度已经损失）|
| 动量族（多周期 MA / momentum）| ~50%（技术分析基础）|
| 波动率择时（HAR / GARCH forecast）| ~40% |
| 展期收益（basis / roll yield）| ~60%（但需要多合约同时）|
| 事件驱动（换月前后 / OI 突变 / gap 反转）| ~50% |
| 横截面动量 / 板块相对强弱 | ~40% |

我们选了**先验最差的一类**（微观结构 skew），投入了最多资源。这是**赛道选择错误**，不是执行错误。

**改法**：**立项时做假设先验概率评估**——任何主题的第一份文档应该是"这个方向为什么值得做 vs 其他候选"的对比表，不允许直接跳进 stage 1。

## 四、这条路径真正产出了什么

### 有价值的方法论（可跨主题复用）

- **KF-3 · 期货 hourly-event 半 tick 成本吞噬约束**：hourly event 因子 gross <0.1% 结构上无法穿透 realistic cost 0.06-0.30%
- **KF-8 · Rank-window 无关性**：per-contract rolling rank 240 vs 360 event 结果一致
- **KF-10 · 选样偏差自诊断法**：小样本 Sharpe>1 → 随机等大子样 Sharpe 分布诊断
- **KF-11 · 因果性铁证四层证据链**：值级 (max_abs_diff) → rank → tier → pipeline
- **KF-12 · "含信息" ≠ "可交易 alpha"**：IC≠0 与 |IC|>0.03+consistency>65% 是两个门槛
- **archive:2026-07-13-va-asymmetry-future-info-leak** · **双证据链未来函数检测范式**（值级证据 1-3 + 截断法证据 4）

**这些方法论在任何后续主题都直接可用**，价值远大于本次未产出的策略。

### 有价值的反例（后续主题禁止重跑）

- **F-11 · 6-tier 独立信号等权假设** · 事件重叠率过高
- **F-12 · ATR 扁平成本模型** · h>12h 会翻转
- **F-13 · signed A3_skew 一阶方向 alpha**
- **F-14 · signed A3_skew top/bottom 20% × ATR 三档直接下注**
- **F-15 · 6-tier 组合等权复合策略** · causal 修复后年化 -73%
- **F-16 · va-asymmetry-composite 原空头单机制假设** · S_seg12_high_dn 反向
- **F-17 · Causal L_seg2 单信号 6-10h 长持仓**
- **F-18 · Skew 派生 7 大类全家族**

**任何后续主题若提出这几类假设，必须直接引用 F-系列作反例，除非有强新证据**。

### 有价值的流程节点（`factor-research-workflow.md` N-0 ~ N-10）

- N-0 因果性 gate（截断法）· 复用
- N-1 sample 边界（cluster bootstrap 单位 = (contract, event_date)）· 复用
- N-2 判据（Spearman IC + per-symbol 一致性 + Bonferroni + 门槛）· 复用
- N-3 成本模型（realistic per-contract 单边）· 复用
- N-4 参数稳健（rank-window 200-300 events）· 复用
- N-5 OOS（时间维度 walk-forward + 品种维度 LGO）· 复用
- N-6 制度分层（波动率 / 趋势 / 时段）· 复用
- N-7 过拟合 vs 制度依赖辨析（拆制度维度）· 复用
- N-8 广度扫描（先扫多个正交假设，再深挖）· **本次执行失败** · 需强化
- N-9 工程化 gate（样本外双维度 + 品种保留率 80%）· 复用
- N-10 归档（分支差异枚举 + 命名引用协议）· 复用

## 五、如果重来一次会怎么做

**Day 0 · 立项** (0.5 天)
- 写"5m 期货 OHLCV 上的假设先验概率排序表"
- 从中选 3 个先验最高的方向作为候选
- 排除微观结构类（skew/kurtosis）除非有强新证据

**Day 1-3 · 广度扫描** (3 天)
- 选定的 3 个方向 × 每个方向 5-10 个 raw feature = 15-30 个 (feature, target) pair
- 全部跑 pooled IC + per-symbol 一致性 + Sharpe
- **每个特征入池前先跑截断法单测**（e1_v2 范式）
- 判决门槛：|IC|>0.03 AND consistency>65% AND per-symbol Sharpe>0.3
- **不允许深挖任何 fail 的假设**

**Day 4-5 · Top-3 候选深挖** (2 天)
- 只在广度扫描通过的候选上做 stage 2-3
- 制度分层 + walk-forward + LGO
- **跨 stage family-wise Bonferroni**（预注册总 N）

**Day 6-7 · 组合合成 + 工程化** (2 天)
- Ridge / LightGBM 合成通过的候选
- 加 Cap / turnover / VaR 约束
- vnpy backtest 端到端跑一次
- **Sharpe > 2.0 或 MaxDD < 5% 触发 sanity check**（必须做因果性铁证再进）

**Day 8 · 冻结或迭代** (1 天)
- 通过所有 gate → 归档 v1.0 + 模拟盘
- 未通过 → 复盘 + 假设降级 + 转下一方向

**8 天预算内出 1 个初步候选或明确的证伪判决**。而 va-asymmetry 家族 8 天出的是"没通过的策略 + 未发现的未来函数"。

## 六、给 skill 的补丁建议

复盘完之后，应该给 `quant-research-methodology` skill 加以下条款：

### 条款 A · 立项 checkpoint

任何新主题必须先写"假设先验概率排序表"，说明"为什么选这个方向而不是其他"。不允许直接跳进 stage 1。

### 条款 B · 广度优先硬约束

任何主题的前 40% 时间预算必须投在"横向扫 ≥ 10 个正交假设"，不允许在单一假设上超过 40% 时间。

### 条款 C · 特征入池自动化因果单测

任何新 raw feature 入 pipeline 前，必须跑 `verify_leak_by_truncation` 范式的截断法单测。集成到 pre-commit 或 CI。

### 条款 D · 跨 stage family-wise 多重比较

立项时预注册整个主题总共做多少次假设检验，用 total N 做 Bonferroni。FDR 只在同一层多重比较有效。

### 条款 E · 指标 sanity check

回测出来 Sharpe > 2.0 或 MaxDD < 5% 触发**强制因果性铁证**：截断法 + shift(1) 对比 + 特征单测三合一。不通过不允许进下一阶段。

### 条款 F · 数据集能力边界评估

任何主题立项时评估"这个数据集在这类假设上的理论上限"。例如 5m OHLCV 上微观结构因子 |IC| 上限约 0.03，如果假设需要 |IC| > 0.05 才能出实盘策略，直接判决"数据不够、放弃或换数据源"。

## 七、结论一句话

**va-asymmetry 家族的 8 天不是浪费**，如果我们把它当成"发现 5 条方法论 + 8 条反例 + 一套研究流程 + 一整套错误清单"的教材来看，它值这个投入。**但如果把它当成"应该产出策略的研究项目"来看，它是失败的，且失败的原因是系统性的（赛道选择 + 广度不足 + 复杂化 + 缺 sanity check）**。

主题冻结建议：**整个 va-asymmetry 家族**（`poc-value-area-asymmetry` + `va-asymmetry-composite` + `va-asymmetry-revisit`）迁到 `themes-frozen/va-asymmetry/`，KF-1~KF-12 与 F-13~F-18 作为家族级方法论遗产保留在家族 README。

## 附：本次会话（2026-07-14）产出清单

- 4 份 workbench 报告：`h1-report` / `causal-tier-report` / `expanded-report` / `skew-derivative-report`
- 1 份 session summary：`va-asymmetry-revisit-session-summary.md`
- 1 份复盘（本文）：`va-asymmetry-family-retrospective.md`
- 13 个可复用脚本（`h1_*` / `c1-c5_*` / `e1_v2-e3_*` / `s2-s3_*` / `d1_*`）
- 主题目录：`research-status.md`（KF-1~KF-12）+ `factor-research-workflow.md`（F-13~F-18）全部回填
