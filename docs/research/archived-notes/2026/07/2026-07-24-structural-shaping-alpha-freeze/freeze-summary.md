# structural-shaping-alpha · Freeze Summary

> 类型：主题冻结摘要（stage-final freeze）
> 状态：**主题研究完成 · 稳定内核已迁入 theorems/**
> 冻结日期：2026-07-24
> 主题活跃期：2026-07-05 ~ 2026-07-24（约 3 周）
> 归档批次：`archive:2026-07-24-structural-shaping-alpha-freeze`

---

## 一、主题定位（一句话）

**回答"何时双 barrier 塑形容器 $(K_S, K_T, T)$ 能产出 $\mathbb{E}[E_\text{net}] > 0$"** —— 从"证伪独立 alpha"到"识别双通道兑现工具"的完整认识跃升，最终定型为**两条独立 alpha 通道 + 一个工程可用参数优化器**。

## 二、主题最终定型

**Doob OST 两前提对偶结构**（[theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha](../../../../research/theorems/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md)）：

| 通道 | 打破的前提 | 数学机制 | 兑现规模（玉米 1h） |
|------|-----------|---------|------|
| **A · 方向 alpha 放大** | P1 鞅性（条件测度改变） | aligned 筛选 → $\nu_\text{cond} \ne 0$ | +0.25 ATR/笔（KF-19） |
| **B · 强段择时 + 非对称塑形** | P2 可测停时（入场信息含 $\|s\|$） | 混合期望 $E^\text{mix}_\text{gross} = \frac{K_T+K_S}{2}[P^+(\lambda)+P^-(\lambda)] - K_S$ | +1.22 ATR/笔（KF-26 MC）／ +20.2% 年化（KF-27 闭式） |

**核心结论**：塑形本身不创造 alpha（Doob 保守律），但作为方向或强段 alpha 的兑现容器，是让 alpha 在交易执行系统"活下来"的必要工程工具。

## 三、四阶段演化路线

| 阶段 | 主命题 | 关键 KF | 时间 |
|------|--------|---------|------|
| ① 证伪独立 alpha | DirRandom 下塑形无独立 alpha | KF-1..18 | 07-05 ~ 07-14 |
| ② 定型兑现容器 | 塑形三定律（Doob 保守 + 结构 alpha 兑现 + 方向 alpha 放大） | KF-19/20 | 07-14 |
| ③ 扩展两条通道 | 强段择时 + 非对称塑形（无需方向 alpha） | KF-26 | 07-15 |
| ④ 工程闭环 | 参数优化器：品种分布 → 闭式反解 $(K_S^\ast, K_T^\ast, \tau^\ast)$ | KF-27 | 07-15 |

## 四、关键发现清单（沉淀 KF-1 ~ KF-27）

**基石层（阶段 ①）**：
- **KF-1 Doob 保守律**：$\nu = 0 \Rightarrow E_\text{gross} \equiv 0 \Rightarrow E_\text{net} \equiv -2c$
- **KF-6 塑形暗物质带**：$K_S \in [1.0, 1.5]$ 是理论最干净、跳空最安全、有限时间效应最小的三重最优带
- **KF-9 显著漂移阈值**：$\|\nu\|/\sigma \ge 0.10$（后被认识为 per-bar Sharpe ≥ 0.10）
- **KF-10 双 null 框架**：FPT($\lambda=0$) 全面碾压 GBM($\mu=0$)，作为标准 null
- **KF-17 Fourier 精确解**：所有 barrier 结构 null 假设应从 $P_\text{win}^\infty$ 升级为 $P_\text{win}^\text{finiteT}$

**分层证伪层（阶段 ①）**：
- **KF-11/12/13/14/15**：波动率 / 板块 / 品种 / 成本 / 跨周期 / 极端 RR 6 维网格系统证伪独立 alpha
- **KF-16 Hurst 趋势凝聚**：中国期货 1h 上 19/20 合约 H > 0.55（子扩散）
- **KF-18 双通道校准表**：全 195 combo 通道 A (P_win) 71.3% 显著、通道 B (P(τ>T)) 96.9% 显著

**主命题定型层（阶段 ②-④）**：
- **KF-19 方向 alpha 放大律**（通道 A）：aligned/opposed 筛选打破 martingale，+0.25 ATR/笔
- **KF-20 塑形三定律**：Doob 保守 + 结构 alpha 兑现 + 方向 alpha 放大
- **KF-26 通道 B 混合公式**：$E^\text{mix}_\text{gross}$ 闭式解，事前不知方向也能产生显著正期望
- **KF-27 参数优化器**：分布输入闭式反解，玉米 1h 得 $K_S^\ast=3, K_T^\ast=9, R^\ast=3, \tau^\ast=$ 前 65%, Sharpe/年 +1.66

## 五、稳定内核提炼（theorems/）

**已提炼为独立数学文档**：

| 文档 | 承载内容 | 位置 |
|------|---------|------|
| [when-barrier-shaping-yields-alpha.md](../../../../research/theorems/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) | 从 Sharpe 借鉴市场强度 $s := \nu/\sigma$ + Doob OST 两前提对偶 + 通道 A/B 数学 + KF-27 参数优化 + 盈亏下界 $x_\min$ + 附录 A（KF 对应表）B（一致性检查）C（文献对照） | `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` |
| [winrate-payoff-tradeoff-under-frictions.md](../../../../research/theorems/structural-shaping-alpha/winrate-payoff-tradeoff-under-frictions.md) | 胜率-盈亏比权衡 + 摩擦成本修正 + 凯利仓位与破产风险 + 8 章论文式框架 | `theorem:structural-shaping-alpha#winrate-payoff-tradeoff-under-frictions` |

未来所有 barrier 型策略研究应先阅读 theorems/，其内容不再随实验演化。

## 六、共同教训（供跨主题参考）

1. **null 假设选错，"证伪"和"证实"会互换标签**：KF-11 从 T=∞ 近似升级到 Fourier 精确 null 后 K_S=4/RR=2 @ 5m 的 z 从 −6.53 翻成 +152.12
2. **多层对照 + cluster bootstrap + 跨周期护栏** 是 barrier 研究的必要方法论组合（继承自 value-area 家族冻结）
3. **参数扫描要覆盖足够维度**：本主题最终封闭于 9 维网格（K_S × RR × vol × sector × symbol × cost × period × 极端 RR × K_S<1 微 alpha）
4. **Doob OST 两前提对偶** 是 barrier 型 alpha 的完备分类：P1 失效 → 通道 A（Rogers-Imkeller / Ekström-Lindberg / Lopez de Prado Meta-Labeling）；P2 失效 → 通道 B（文献空白，主题原创）
5. **文献定位可对齐**：Lopez de Prado Triple Barrier / Akyildirim Statistical Arbitrage / Lo Sharpe SE / Rogers-Imkeller 已知漂移最优止损不存在（详见 theorem 附录 C）

## 七、未解决观察

主题冻结时下列**边界待定**条目未收敛：

- **通道 A × B 正交叠加**（KF-20 暗示但未系统验证）：理论 Sharpe/年可达 +2.5 以上
- **强度识别信号的 se ≤ 0.05 KPI**：本主题只给出 KPI，未产出满足 KPI 的识别器 —— 下游"强段识别信号"主题需承接
- **20h 强度窗口 → barrier 触达期信号衰减**：本主题未量化
- **多重比较修正（DSR）**：KF-27 Sharpe 1.66 未做 $\sqrt{2\ln K}$ 折减

## 八、下游承接

- **稳定数学基础**：`theorem:structural-shaping-alpha#*`（两份论文式定理文档）
- **工程工具**：First-Passage Designer / KF-27 参数优化器 / Fourier 精确 null 脚本，见 [raw-scripts/](raw-scripts/)
- **未来重激活**：若发现新的 alpha 通道（P1/P2 之外的第三条前提失效路径），可从 archived-notes 恢复主题目录

## 九、archive-references（本主题引用的其他归档批次）

- [archive:2026-07-05-value-area-rolling-reacceptance-freeze](../../../../research/archived-notes/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/) —— 反例 + 方法论遗产：ATR 归一化 / 期望净值 / cluster bootstrap / 多层对照
- [archive:2026-07-06-structural-shaping-alpha-stage1](../../../../research/archived-notes/2026/07/2026-07-06-structural-shaping-alpha-stage1/) —— 本主题阶段 1 归档
- [archive:2026-07-13-va-asymmetry-leak-chain-consolidated](../../../../research/archived-notes/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/) —— 下游主题曾引用本主题工具（塑形参数 / 真实成本模型 / ν_implied 归因）

## 十、批次内容清单

- `README.md` — 主题目录索引（活跃期版本）
- `research-status.md` — 完整 KF-1..27 演化史 + 变更记录
- `experiment-plan.md` — 实验计划（候选矩阵 / 验证顺序 / 判定标准）
- `archive-references.md` — 引用的其他归档批次说明
- `shaping-theory.md` — 主题完整叙事（14 章 + 5 证据簇 + KF-1..27 完整推导）
- `raw-scripts/` — 22 个研究脚本（barrier 探索器 / Fourier 验证 / KF-27 优化器 / 分层扫描等）
