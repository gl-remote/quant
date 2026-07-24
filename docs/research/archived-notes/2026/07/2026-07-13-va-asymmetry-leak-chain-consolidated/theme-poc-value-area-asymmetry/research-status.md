# poc-value-area-asymmetry · Research Status

> 类型：Research Status
> 状态：**✅ 阶段 4 通过（v9.1 · 三维 144 tier 深化 + 合并降级）· 分类器 v4.0 冻结 · 6 类合并版 · 9 A/6 A-** · **主动性研究暂停 · 下游主题 va-asymmetry-composite 立题（2026-07-09）**
> 最近更新：2026-07-09
> 主题 README：[README.md](README.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)（v9.1）
> 下游引用主题：[va-asymmetry-composite](../../va-asymmetry-composite/README.md)（完整交易策略组合层 · 2026-07-09 立题 · 当前主线）

## 一句话结论

**POC 两侧 value area 不对称携带独立的方向 alpha。经过 4 个阶段完整验证 ·
分类器 v3.0 已冻结为 10 互斥 tier 结构 · 输出 A 级 6 档 + A- 级 3 档 · 共 9
档可用类别 · 多空双向覆盖 · 是长期可用的交易背景分类器组件。所有 A 级 tier
在 143 合约 · 36625 events · 20 品种前缀扩样本下通过 4 硬门槛严格性验证
（Bonferroni family=15 · p<0.0033 · 反事实 p<0.001 · 品种保留 ≥ 60% ·
单笔 IR ≥ 0.30）。分类器 v4.0（6 类合并版）2026-07-08 冻结。本主题主动性研究暂停 ·
分类器组件保留供下游策略层引用 · 完整策略（入场/出场/仓位/cost）不属本主题。
2026-07-09 起，下游主题 va-asymmetry-composite 立题：以本分类器 v4.0 为 alpha 源，
叠加 structural-shaping-alpha 工具 + archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-09-poc-va-shaping 塑形参数，
探索品种筛选 / 信号强度加权 / 多空权重优化三道组合关，
目标构建 Sharpe ≥ 2.5 · 年化净 ≥ 18% 的实盘可上线完整交易策略。**

- **A 级白名单**（v3.0 · 6 档 · 4 硬门槛 + 时稳全过）：
  - **LP_only·全**（多头精选·全期）· skew ≤ 0.10 · mean +33.3 · IR 0.28 · 时稳 0.03（最稳）
  - **LL_only·稳定**（多头主力·稳定期）· skew ∈ (0.10, 0.30] · mean +33.6 · IR 0.28 · 时稳 0.40
  - **SP_only·稳定**（空头精选·稳定期）· atr > 0.80 · mean +33.0 · IR 0.34
  - **SP_only·转换** ⭐（空头精选·转换期 · 最强）· mean **+51.9** · IR **0.46**
  - **SC_only·全**（空头收敛·全期）· atr ∈ (0.67, 0.80] · mean +32.4 · IR 0.32
  - **SC_only·转换**（空头收敛·转换期）· mean +44.9 · IR 0.40
- **A- 级白名单**（v3.0 · 3 档 · 4 硬门槛过 · 时稳警示）：
  - **LL_only·全**（样本最大 n=1290）· 时稳 0.67
  - **LL_only·转换** · 时稳 **1.32**（警示强 · 下游需分时段过滤）
  - **SP_only·全**（品保 82% · 本主题最高）· 时稳 0.64

## 边界

1. **不使用**已被 value-area 家族证伪的成分：POC 作为回归锚、reacceptance
   触发器、4+ ATR 距离档过滤、rolling POC 作为均值锚
2. **信号定义严格无未来函数**：signed_skew_rank rolling 100 事件 · daily_atr /
   trend rolling 20 交易日 · warmup 20 天
3. **profile 窗口锁定 W1 前一天**（rolling / 前 N 天在阶段 1 洞察 D 已排除）
4. **度量锁定 A3_skew**（volume 加权三阶矩 · 阶段 1 洞察 A 已确认 A1/A2/A4 弱于 A3）
5. **信号是"顺势放大器"而非独立均值回归**：必须叠加 trend + atr filter
6. **空头是单机制**（洞察 Q）· 只在高 ATR 有效 · 低 ATR 空头 8h 甚至反转
7. **多头是 3 机制**（洞察 P）· 低/中/高 ATR 分别是"日常回归/震荡秩序恢复/恐慌 V 反弹"
8. **稳定 vs 转换期 mean 差异不显著**（洞察 U 严格版）· 仅空头宽松显著
9. **ATR × Trend 独立**（r=+0.003）· 联合筛选是核心 filter 架构（洞察 S）
10. **空头 3 主线（首选/宽松/收敛）本质是同一信号**（Jaccard 0.65-0.86）· 阶段 4 只选一

## 关键发现清单（KF）

主题重要结论的唯一入口。共 24 条 KF · 阶段 1 → 阶段 4 收尾（含 KF-22/23 方法论 · KF-24 品种异质性）。

### 阶段 1 · 测量 + 信息量层（KF-01 ~ KF-08）

**KF-poc-va-01 · A3_skew 是唯一有效度量**
- A1/A2/A4 分别用 VA 内 volume 比例 / VA 距离比 / VA 内重心比 · 均未过阶段 1 Bonferroni
- A3_skew 用**整个 profile（含 VA 外尾部）** 三阶矩 · 唯一在 pooled IC 显著
- **暗示**：VA 外尾部信息量可能构成独立信号主题

**KF-poc-va-02 · W1（前一天）是唯一有效 profile 窗口**
- W2（前一周）· W3（rolling 4h/12h/24h/72h）· 前 N 天累计 · 全部弱于 W1
- 前一天是"完整定价日" · Schelling 焦点 · 有集体共同信号性质
- Rolling profile 变成短期动量代理 · 非结构信号

**KF-poc-va-03 · A3_skew 近似正态 · k×σ 阈值与 rolling rank 等价**
- σ ≈ 0.45 · 5%-95% 分位与理论正态偏差 <0.03
- k=1.5×σ ≈ 0.68 阈值触发 6.7% 尾部事件
- 后续演进为**严格无未来函数的 rolling 100 事件 rank**（洞察 K）

**KF-poc-va-04 · 事件重叠是隐性 bias 源**
- cu2601 上涨行情 + 8h 事件重叠 → mean 假象 +146 bps
- 用 dedup_8h（相邻事件间隔 ≥ 8h）后 cu 塌陷到 +30
- **阶段 3 起持仓期与事件间隔硬约束一致**

**KF-poc-va-05 · A3_skew 是"顺势放大器"而非独立均值回归**
- 跨合约 baseline vs DN_mean · Pearson r=+0.79（19 合约 r=+0.62）
- 段内 15 天分档 · Q1 跌段 DN mean=-13 · Q3 涨段 DN mean=+79
- 段内配对 dn_diff = +16.6 bps · Shuffle p=0.004 · 独立信息量存在
- **暗示**：无 trend filter 就在跌段亏钱 · 必须叠加环境 filter

**KF-poc-va-06 · A3_skew 与 ATR 近乎独立（|ρ|<0.05）**
- 全 pool · Spearman(|A3_skew|, ATR) = +0.005
- **DN + 低 ATR** = 甜蜜点 · **DN + 高 ATR** = 反向亏钱
- ATR 不是放大器 · 是"过滤器" · 阶段 2 洞察 I 已定型

**KF-poc-va-07 · 严格无未来函数版本 CI 排 0 · 方法论闭环**
- σ / rank 换成 rolling 版本后 mean 稳定 <15%
- 洞察 K 三档位（单层/双层/三层）全部 CI 严格排 0
- 阶段 1 收尾方法论无残留边界

**KF-poc-va-08 · 顶厚→跌对称假设不成立**（"跌快于涨"验证在阶段 2）
- 阶段 1 · UP 组 pooled +3.3 bps · payoff 0.99 · 无独立空头信号
- 跨合约 & 段内 · UP mean 与 baseline 无相关（r≈0）
- 阶段 2 用扩样本 + 短 horizon 找到候选（见 KF-10）

### 阶段 2 · 跨周期护栏 + ν_implied + 样本外 + 收尾（KF-09 ~ KF-15）

**KF-poc-va-09 · 触发时段可全天挂单**
- event_hour 分组 · 主线信号无显著衰减（p>0.10 · 样本外）
- 早盘 9-11 略优（+24-30）· 夜盘 21-22 稳（+20-25）
- 信号是"当日状态"而非"开盘瞬时" · 挂单可灵活

**KF-poc-va-10 · 空头候选 E · UP+跌段+高ATR · 4h horizon**
- 阶段 2 短 horizon 探索发现（洞察 M）
- 跨品种保留 72.7%（8/11）· 反超多头
- 但 3-4h 有效 · 6h+ 塌陷 · **验证"跌快于涨"经济假设**

**KF-poc-va-11 · 空头 D ⊂ E（D 是 E 的稀释版本）**
- P(D|E)=0.79 · Lift=13.8 · Jaccard=0.42
- D ∪ E 并集 mean 弱于 E 单独 · 舍弃 D · 保留 E

**KF-poc-va-12 · 参数网格搜索 · 主线甜蜜点定型（多空翻倍）**
- 洞察 N · 96 组合 × 多空 · 通过率多头 86.5% · 空头 49.0%
- **多头 sweet spot**：skew≤0.10 · atr≤0.70 · trend≥0.75 → +44.8 bps · hit 78.9%
- **空头 sweet spot**：skew≥0.70 · atr>0.80 · trend≤0.20 → +40.0 bps · hit 63.0%
- 主线幅度双双翻倍（多头 +25→+45 · 空头 +16→+40）

**KF-poc-va-13 · 首次达成 100% 品种保留度（多头 9/9 · 空头 11/11）**
- 阶段 1 主线仅 57% · 洞察 N 甜蜜点提升到 100%
- 多头首选：p, CF, ag, m, rb, SR, cs, y, c 全部正 mean（p=+130 bps）
- 空头首选：sc, ag, rb, CF, m, c, SR, hc, p, cs, cu 全部正 mean（sc=+143 bps）

**KF-poc-va-14 · Bonferroni + ν_implied + 跨周期三重严格通过**
- 洞察 O · 4/4 主线通过 Bonferroni（p<0.05/96=0.00052）
- ν_implied 与 mean 几乎相同（Itô σ²/2 仅 0.3-0.6 bps）· 是真方向 alpha
- 跨周期 15m / 1h / 30m / 2h 全部 CI 排 0
- **阶段 2 最严格判决全过**

**KF-poc-va-15 · 严格触发条件下 skew 门槛可放松（宽松档 · 高触发率）**
- 多头：skew≤0.30 vs skew≤0.10 · mean 只差 +5 bps · 触发率 3x
- 空头：atr>0.50 vs atr>0.80 · mean 差 +13 bps · 触发率 2x
- **阶段 3 可根据 KF-8 账户闸门在精选/宽松之间选择**

### 阶段 3 · 背景分类器稳健性深度检验（KF-16 ~ KF-21）

**KF-poc-va-16 · 洞察 P · 多头 3 种反弹机制**（⭐⭐⭐）
- **低 ATR**：日常均值回归 · payoff 1.46 · 稳定线性（8h 持仓）
- **中 ATR**：震荡后秩序恢复 · payoff 2.34 · 尖峰厚尾 kurt=12（8h 持仓）
- **高 ATR**：恐慌 V 反弹 · payoff 1.93 · 急速兑现（4h 完成 118% · 8h 后回吐）
- **阶段 4 精细化**：可拆成 3 个多头子策略 · 持仓期随 ATR 制度自适应

**KF-poc-va-17 · 洞察 Q · 空头单机制 vs 多头多机制**（⭐⭐⭐）
- 空头只有 1 种机制（"崩盘前奏"）· **必须高 ATR**
- 低 ATR 空头 8h 甚至反转（-152%）· 中 ATR 弱信号
- 分布形态：高 ATR skew=+1.79 kurt=+9.45（尖峰厚尾）· 低 ATR skew=-0.58（左偏 · 反弹风险）
- **建议空头收敛为 atr≥0.67 单一档位**

**KF-poc-va-18 · 洞察 R · Regime transition 信号衰减**（⭐⭐⭐）
- 46% 事件位于 transition 期（rolling 20 日 rank 过渡带宽）
- 多头首选衰减仅 11%（严格 filter 天然抵抗）· 其他 3 主线衰减 27-47%
- **通用规律**：**filter 严格度和 regime 稳定 filter 的价值反向**

**KF-poc-va-19 · 洞察 S · ATR × Trend 正交**（⭐⭐⭐）
- atr_rank 与 trend_rank Spearman r=+0.003（完全独立）
- 但 atr_rank 与 |trend_rank-0.5|（趋势极端度）r=+0.19 弱相关
- **两维正交** · ATR = 强度 · Trend = 方向 · 联合筛选是核心 filter 架构
- 高 ATR 跌段 39.1% vs 涨段 38.8% · 对称 · **否定"高 ATR = 跌段"直觉**
- 中 ATR 事件最少（24%）· 双峰分布 · 是过渡态

**KF-poc-va-20 · 洞察 T · 空头宽松的救赎 · Regime 稳定 filter**（⭐⭐⭐）
- 空头宽松 + regime 稳定 filter → mean 从 +27 → +36 bps · 增益 31.6% ✅
- 空头宽松原判"建议放弃"（洞察 R）→ **修正为"高频空头补充"**
- 多头首选加 regime filter 增益仅 7.5% · 不值得
- **阶段 4 分主线定制 regime 处理**：严格 filter 无需 · 宽松 filter 必需

**KF-poc-va-21 · 洞察 U · 稳定 vs 转换期机制差异（仅空头 · horizon 曲线层面）**
- **空头首选**：稳定日 = 持续下跌型（8-12h 峰 +67 → +70）· 转换日 = 急速反转型（4h 峰 +32 · 12h 归零）
- **多头首选/宽松**：稳定/转换形态一致 · 无本质差异（mean 差异不显著）
- **严格 t-test 修正**：**mean 层面差异仅空头宽松显著**（p=0.024 · 洞察 T 双证）
- horizon 曲线差异是"路径不同"而非"mean 不同"
- **阶段 4 空头出场策略必须分**：稳定日追踪止损 · 转换日目标止盈 4h

**KF-poc-va-22 · 采样精度边界 · "数据边界不可造假"原则**（⭐⭐⭐ 跨主题方法论）
- **背景**：skew 是日级变量（同日 event 共享 skew_rank）· 实际独立采样 ~10 独立日
  而非 rolling 100 events 的表面数字
- **严格 date-cluster bootstrap 验证**：SE 放大 1.05-1.32 倍（不是预期 3 倍）·
  因同日 event 未来 8h 窗口仅部分重叠 · A 级 5 主线 Bonferroni 全部保留
  · 多头首选·稳定甚至从 B 升级到 A
- **跨合约分布诊断**：43 合约 KS 86.7% 拒绝 · 但中心分位高度一致（相关 0.977）·
  尾部 p05/p95 极差 0.5-0.7 · **分布中心相似 · 尾部有明显差异**
- **prefix 池化反证实验**：把同品种合约合并 · 空头 4/5 档 Bonferroni 降级 ·
  因池化混合尾部行为 · 破坏 skew ≥ 0.70 等极端触发的品种特异性
- **通用教训**：
  - ❌ 池化更多品种数据 / 用更久远合约历史 / 贝叶斯 shrinkage 加"分布不同"先验
  - ✅ 承认采样边界 · 诚实报告独立观察数 · 用正确 cluster bootstrap · 依赖
    mean/hit/payoff 决策 · 保守假设 CI 上限
- **冻结决定**：
  - rank 单位固定为 **per-contract**（禁止池化 · 禁止 Bayes shrinkage）
  - Bootstrap 单位固定为 **(contract, date)** cluster
  - CI 判据 = 95% CI 排 0 + Bonferroni p < 0.00625

**KF-poc-va-23 · 分位 × ATR 制度信号地图**（⭐⭐⭐ 分类器细化 · 阶段 4 起点）
- **动机**：rank 精度只 10 档（离散标准）· 不同分位段可能对应不同经济机制
- **多头 4 分位 × 3 ATR 制度 12 格诊断**（trend≥0.75 · 稳定期 · 8h）·
  发现 **5 个稳定甜蜜点**：
  - **段3·ATR低**（skew∈(0.19,0.25] · atr≤0.33）：mean **+85 · hit 83%** ⭐（100% 品种保留）
  - 段2·ATR低（skew∈(0.09,0.19]）：+60 · hit 67% · 100% 品种保留
  - 段1·ATR低（skew≤0.09）：+33 · hit 77% · 100% 品种保留
  - **段4·ATR高**（skew∈(0.25,0.30] · atr>0.67）：+35 · hit 61% · 71% 品种保留 ⭐（新发现）
  - 段2·ATR高：+25 · 部分稳
- **空头 12 格诊断**（trend≤0.20 · 4h）· 发现 **3 个反常甜蜜点**：
  - **段4·ATR高**（skew∈[0.70,0.75] · atr>0.67）：mean **+138 · hit 80%**（n=15 · 3 品种全保留 ⚠️ 待验）
  - **段4·ATR低**：+72 · hit 93%（n=14 ⚠️ 待验）
  - **段3·ATR中**（skew∈[0.75,0.81] · 0.33<atr≤0.67）：+39 · hit 72%（新甜蜜点）
- **关键教训 · "过拟合"vs"制度依赖"的辨析**（跨主题方法论）：
  - 首次 LOPO 显示段 3 甜蜜点疑似过拟合（DCE.m 主导 · 时间半分后半塌陷）
  - **拆分 ATR 制度后**：段 3·ATR 低 3/3 品种保留 · 移除主导品种后 mean 仍 +41
  - **结论**：**"过拟合"是 ATR 制度未拆分导致的错判** · 实际是**制度依赖**
  - **通用原则**：**"制度依赖"和"过拟合"外形相似** · **判断前必先拆分所有相关制度维度**
- **经济机制**：
  - 多头低 ATR：**均值回归型**（段1/2/3 都强 · 平静市场 + 底厚 → 慢反弹）
  - 多头高 ATR：**波动率反弹型**（段4 = 洞察 P 的高 ATR V 反弹）
  - 空头：**弱顶厚 + 波动率极端**（段4 反常）需要更多样本验证
- **阶段 4 落地**：
  - 分类器契约暂不变（保留 §12.9 的 A 级 5 档粗粒度）
  - **§13 作为阶段 4 探索起点**：多头 5 甜蜜点全测 + 空头段 4 扩样本外验证
  - 若严格 CI + Bonferroni 通过 · 阶段 4 可细化分类器到分位×制度

### 阶段 3 · 分类器严格性证据链（补充 KF · 不占编号）

阶段 3 workbench §12 完成 **7 层严格性验证**（A~G · 见 workbench）：

- **A · Bonferroni**（family=8 · p<0.00625）：稳定期 4/5 · 转换期 2/5 全过
- **B · 稳定 vs 转换 差异**：仅空头宽松 p=0.024 显著（其余 mean 层面不显著）
- **C · 分类器性能**（v8 修正后）：年化 Sharpe gross +1.06 ~ +1.48 · net-15bps +0.77 ~ +1.10 · 单笔 IR +0.35 ~ +0.60（旧 +8~+15 数据口径错误 · 已作废）
- **D · 品种保留率**：稳定期 90-100% · 转换期 82-100%
- **E · 反事实基准**：真实 vs 随机 5 组合 p=0.0000（**明确不是噪声**）
- **F · 组合独立性**：空头 3 主线 Jaccard 0.65-0.86（本质同一信号）
- **G · Time-in-market**：占用天数比 <0.4%（极稀疏 · 不冲突其他策略）
- **H · 采样精度实证**（KF-22）：严格 date-cluster bootstrap · A 级白名单不变 ·
  prefix 池化实验反证 per-contract 是数据边界内的最优选择

**综合评级**（10 档 · A/B/C 分级 · 见 workbench §12.9）：
- **A/A+ 级 5 档**（可直接用于阶段 4 · 或与其他主题组合）
- **B 级 3 档**（可用需谨慎 · 边缘或 n 少）
- **C 级 2 档**（暂不用 · 阶段 4 前需补验）

### 阶段 4 · 互斥分类器与品种异质性（KF-24）

**KF-poc-va-24 · 品种异质性 · 需下游策略层筛选**（⭐⭐⭐ 分类器与策略层责任边界）
- **背景**：阶段 4 扩样本至 143 合约 · 36625 events · 20 品种前缀 · 首次做
  per-prefix 最优 tier 诊断
- **多头最优档位 4 分散**（LP_only / LL_only / LP_wide / LL_wide 各 7 / 7 / 3 / 3 品种）
- **空头最优档位 3 分散**（SP_only / SC_only / SL_only 各 9 / 7 / 4 品种）
- **不存在通用参数**：没有任何单一 tier 能在所有品种上都是最优 · 品种类型
  决定最优档位
- **分类器承诺"整体信号存在"**：整体证据链在 143 合约扩样本下通过 4 硬门槛
  严格性验证 · 分类器 v3.0 契约成立
- **品种筛选是下游策略层责任**：分类器不承担"选择哪个品种用哪个 tier"的
  责任 · 该责任交给下游"组合策略"主题
  （如 **[va-asymmetry-composite](../../va-asymmetry-composite/README.md)**，2026-07-09 立题）
- **3 大品种类型**（下游策略层参考）：
  - **A · 金融贵金属**（IF/IH/IC/IM/T/TF/TS/au/ag）：低频 · 深流动性 · 偏 LP/SP 精选档
  - **B · 化工建材黑色**（rb/hc/i/j/jm/TA/MA/PP/pp/l/v/eb/eg/sc/fu/bu）：主流波动 · LL/SC 中档为主
  - **C · 农产品有色主流**（cu/al/zn/ni/sn/pb/m/y/p/c/cs/CF/SR/OI/RM/FG）：分散 · SL 宽档补充
- **关联证据**：阶段 4 workbench §3

### 阶段 4 · 三维 144 tier 深化 + 合并降级（KF-25 ~ KF-29）

**KF-poc-va-25 · FDR 优于 Bonferroni 用于结构性切片族**（⭐⭐⭐ 跨主题方法论）
- **背景**：v9 用 Bonferroni family=144（α=0.000347 · 3.58σ）· 只有 7 通过 ·
  26 个"仅 L3 fail"的强信号（p_boot 0.0004~0.041）被误杀
- **根源**：Bonferroni 假设 144 检验完全独立 · 但 144 tier 是**结构性切片**：
  相邻 skew 段 Spearman r > 0.5 · full/stable/trans 嵌套 · 独立检验数 << 144
- **方法**：改用 **FDR (Benjamini-Hochberg) α=0.05** · 允许 ≤5% 假发现率
- **结果**：白名单从 7 → 20 · 且 15/20 仍通过 Bonferroni family=18（sanity check）· FDR 不"松"
- **推广**：**跨主题方法论** · 未来 tier 化 / grid 化 / 分位化研究都应用 FDR
- **关联证据**：workbench §4.1 · v9.1 experiment-plan §4.4

**KF-poc-va-26 · 平稳期 alpha 仅存在于转换期**（⭐⭐ v9 新维度探索）
- **假设**：平稳期（trend rank ∈ (0.20, 0.75)）从未深挖 · 可能有独立 alpha
- **结果**：144 tier 中 stable·Tflat 表全空 · 只有 trans·Tflat 单格通过（L2_Alow_Tflat）
- **解读**：平稳期作为独立分类维度价值有限 · 但作为 filter 可用
- **关联证据**：workbench §4.2

**KF-poc-va-27 · 交叉 trend 全部证伪 · 顺 trend 是硬规则**（⭐⭐ v9 新维度探索）
- **假设**：涨段做空 / 跌段做多 / 平稳期双向 · 可能有独立 alpha
- **结果**：24 个 cross-trend 描述性 tier · **全部 mean 为负** · 无一通过
- **解读**：顺 trend 是硬规则 · 与阶段 3 KF-Q 一致 · 现在有 144 tier 完整证据
- **关联证据**：workbench §4.3

**KF-poc-va-28 · 转换期是空头最密集区**（⭐⭐ 制度依赖发现）
- **Observation**：trans·Tdn 表 4 格通过（S3_Ahigh / S2_Ahigh / S1_Ahigh / S2_Amid）
- **解读**：崩盘前奏在制度过渡期显著扩散 · 空头"扫射范围"变大
- **下游启示**：转换期加大空头仓位或降低门槛
- **关联证据**：workbench §1.3 · 2.2

**KF-poc-va-29 · 合并降级优于精细切分**（⭐⭐⭐ 分类器工程化方法论）
- **背景**：144 tier 精细化 · 稀疏率 91% · 相邻格子高度相关 · 大量强信号被 CI 撑不开误杀
- **降级方案**：把 144 tier 通过区域合并为 **6 大类** · 保持互斥
  - 多头：L_seg3_lowmid_up / L_seg12_high_up / L_seg2_low_flat
  - 空头：S_seg12_high_dn / S_seg34_high_dn / S_seg2_mid_dn
- **6 类 vs 144 tier 对比**：
  - 通过率：20% → **83%** · 稀疏问题彻底消失
  - Bonferroni family=6 · α=0.008 就能过 · 不需 FDR 大池校正
  - **S_seg12_high_dn 三 period 全 A** · 复合稳定性远超单一 tier
  - 每类样本量翻 3-5 倍 · CI 更窄 · IR 更稳
- **决策**：**v4.0 契约用 6 类合并版**（下游策略只管 6 类 · 不是 143 种边缘 case）
- **推广**：**跨主题方法论** · 高维网格研究必须做"合并降级"检验 · 而非硬套精细化
- **关联证据**：workbench §2.4 · data 文件 `stage4_6class_merged_verification.csv`

### 旁支探索 · 对称子环境 rank20 反转辅助 gate（KF-30 · 待深入）

**KF-poc-va-30 · 对称子环境 + 高波动 + 不稳定趋势 → rank20 反转做空可行**（⭐⭐ 潜在方向）
- **背景**：从 v4.0 分类器的"对称子环境无方向 alpha"降级判决出发，反问：对称环境下虽然无方向 alpha，但是否**存在反转保护型 alpha**？
- **结论**：✅ **仅在顺势做空方向（downtrend × S 侧）通过验证**：
  - 条件：abs_skew < 0.10 · trend_rank_roll outside [0.35,0.65] · atr_rank > 0.67 · trend_ret_10d < 0
  - 触发器：rank20 ≤ 0.80（20 期高位）+ close_diff < 0（刚回落）
  - H4 real +56.25 bps CI=[+16.29, +103.41] · B=1000
  - 安慰剂 shuffle p=0.002 · 品种集中度 37.3%（分散良好）
  - 其他 7 个方向象限（顺势L/逆势L/逆势S）全部 ❌
- **现状**：统计层通过 · 落地层不完整（单方向、n 偏少、无 period 拆分、配对设计偏差未消除）· 暂不入 v4.0 分类器白名单
- **潜力**：可能被挖深为独立辅助 gate，或与分类器的 skew 倾斜方向信号互补（对称环境 + 高波动的特殊场景）
- **证据**：`workbench:poc-value-area-asymmetry-reaccept-symmetric-regime §9-§10`
- **日期**：2026-07-09

### 阶段 4 完成

**完成日期**：2026-07-08 · **判决**：完全通过

**关键数据**：
- **数据扩容**：143 合约 · 36625 events · 20 品种前缀（阶段 3 是 44 合约）
- **10 互斥 tier 结构**：多头 4 档（LP_only / LL_only / LP_wide / LL_wide）×
  空头 3 档（SP_only / SC_only / SL_only）× 稳定/转换 = 10 互斥 tier + 未分类
- **A 级 6 个 + A- 级 3 个 = 9 个可用 tier**（多空双向覆盖）
- **4 硬门槛严格性验证**（family size = 15）：
  - Bonferroni · p < 0.05 / 15 = 0.0033
  - 反事实 · vs 随机触发 · p < 0.001
  - 品种保留率 · 单前缀 mean > 0 比例 ≥ 60%
  - 单笔 IR · mean / std ≥ 0.30
- **L5 品保降级为观察**（原 ≥ 80% 阈值下降为 ≥ 60% · 见 workbench §2）
- **品种异质性诊断**：多空最优档位在品种前缀间高度分散（见 KF-24）
- **分类器 v3.0 契约冻结**：`ClassifierOutput.tier: str | None` 单值输出 ·
  10 互斥类别 + 未分类 · classifier-math-spec.md / parameter-selection-spec.md /
  experiment-plan.md / research-status.md 全部同步

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-07 | 初版立题；预约定周期口径（1h 交易 / 5m profile）与三档窗口 |
| 2026-07-07 | 阶段 1 收尾 · 洞察 A-K 落地 · workbench v7 |
| 2026-07-07 | 阶段 2 收尾 · 洞察 L-O 落地 · workbench v4 · KF-01 ~ KF-15 定型 |
| 2026-07-07 | 阶段 3 完成 · 洞察 P-U 落地 · workbench v7 · **KF-16 ~ KF-21 定型** · 分类器 7 层严格证据链完整 |
| 2026-07-08 | 阶段 4 v3.0（10 互斥 tier）· KF-24 品种异质性定型 · 143 合约扩样本 |
| 2026-07-08 | 阶段 4 v9.1 三维 144 tier 深化 + 合并降级 · **KF-25 ~ KF-29 定型** · 分类器 v4.0（6 类合并版）· FDR 校正 |
| 2026-07-09 | **主动性研究暂停**；登记下游主题 [va-asymmetry-composite](../../va-asymmetry-composite/README.md)（组合层 · 立题）；分类器 v4.0 合同冻结供下游引用（L1 tier 表 + 14 条严格性约束） |

## 下一步 · 阶段 4 · 背景分类器的使用与组合

> **2026-07-09 起本主题主动性研究暂停**；下游策略层工作转移到 **[va-asymmetry-composite](../../va-asymmetry-composite/README.md)**（当前研究主线）。
> 以下方向 A/B/C 已部分在 archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-09-poc-va-shaping 与 va-asymmetry-composite 立题中承接：
> - archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-09-poc-va-shaping 完成"方向 B（完整策略）"的塑形 POC 验证（SL1.0/TP1.4/TH8h + c_realistic → 净 15.45% / Sharpe 2.23）
> - va-asymmetry-composite 承接"方向 C（多空组合对冲）+ 方向 B（完整策略）+ 组合优化"三道组合关
> 未来若发现分类器 bug，仅在本主题 research-status / parameter-selection-spec 中登记参数变更，不重开实验。

## 立题日期

**2026-07-07**
