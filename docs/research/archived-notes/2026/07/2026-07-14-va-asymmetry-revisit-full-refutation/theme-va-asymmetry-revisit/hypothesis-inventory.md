# 未验证猜想集（Hypothesis Inventory）

> **本文档定位**：从 va-asymmetry 错误路径中**分离出的核心 alpha 假设**——它们的因果叙事不完全依赖 daily 泄漏值，因此在因果修复后**仍需要独立验证**才能定论。每条 = 假设 / 出处 / 泄漏关系判断 / 重测方式。
>
> **本文档不承载**：架构性参数默认（见 [factor-research-workflow.md](factor-research-workflow.md)）、已证伪条目（见 factor-research-workflow.md 的 F-系列）、性能数字。
>
> **状态说明**：所有 H-N 条目**均为未验证候选**。开始验证时进入 experiment-plan.md；通过因果版实验后升级为 research-status.md 中的 KF-N；未通过后进入 factor-research-workflow.md 的 F-系列。

---

## 一、特征侧候选（分类器输入变体）

### H-1 · A3_skew（量加权价格三阶偏度）作为独立方向 alpha
- **假设**：signed A3_skew 在 event 后 h∈{2,4,6,8}h 内对方向收益有独立 IC；与 POC 距离的相关性 < 0.3，携带独立信息。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-08-poc-va-asymmetry stage-summary`（KF-02 ~ KF-05）；`stage2-symmetric-regime.md` 三重交互
- **泄漏关系**：**否**——A3_skew 本身在 5m/30m intraday 内计算，逻辑独立于 daily merge；泄漏受害者只是"用来分层的 atr/trend 桶"与"6-tier 阈值"。
- **重测方式**：改用 30m intraday A3_skew 直接检验对 h∈{2,4,6,8}h real 收益的 IC，**不做 tier 分层**，作为最小验证单元。若 pooled IC 显著再进入分层。

### H-11 · τ_signed（有向持仓时间）作为 timing 特征
- **假设**：τ_signed（进场后到 exit 的分钟数 × sign(direction)）与 real return 呈显著非线性关系，短 τ / 长 τ 存在双峰。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-12-va-asymmetry-composite-mathspec/p2-timing-holding-time`
- **泄漏关系**：**否**——τ 在盘中测量，与 daily merge 无关。
- **重测方式**：作为 exit-side timing 特征直接搬用；纯 intraday 环境下验证双峰 IC；可用作 H-1 通过后的第二层特征。

### H-12 · transition_flag（波动率制度切换 crossover）
- **假设**：过去 60 分钟内 ATR 桶发生跨档标记为 transition=1；transition=1 的样本 h4 real 均值显著 > transition=0。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-12-va-asymmetry-composite-mathspec/r1-transition-flag-scope`
- **泄漏关系**：**部分**——原实现的 ATR 桶来自 daily，是泄漏受害者之一；但"制度切换携带 alpha"的因果叙事本身独立于 daily 数值。
- **重测方式**：把 ATR 桶换成 30m intraday session-ATR 桶重跑；或改用 daily shift(1) 保守版；两种方式若结果一致则确认因果叙事成立。

### H-14 · ν_implied = μ − σ²/2 作为品种筛选 / 横截面对齐统计量
- **假设**：真正解释 tier 内跨合约收益差的是 ν_implied 而非算术均值 μ；对负偏合约（如 IF）尤其明显。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-08-poc-va-asymmetry stage-summary`（KF-27）
- **泄漏关系**：**否**——由 30m log return 派生。
- **重测方式**：直接作为方法论沿用（可视为 factor-research-workflow.md 的 N-系列扩展）；无需独立验证，但需在新因子横截面对齐时用它替代 μ。

---

## 二、结构侧候选（阵营 / 机制变体）

### H-3 · 多头存在多机制（延续 / 突破加速 / 争议 tier）
- **假设**：多头空间存在至少 3 种机制：
  - L_seg3_lowmid_up（低-中 ATR、上行趋势）—— **延续型**
  - L_seg12_high_up（高 ATR、上行趋势）—— **突破加速型**
  - L_seg2_low_flat（低 ATR、无趋势、B 区顺势）—— **争议 tier**（见 H-17）
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-08-poc-va-asymmetry stage-summary`（KF-08 ~ KF-11）
- **泄漏关系**：**部分**——原分类器阈值（trend_ret_M_spec 未 shift(1)）受泄漏，但"多头存在多机制"的定性叙事只依赖 A3_skew×h 的分段响应，与 daily 数值无关。
- **重测方式**：先做**无 tier 的 pooled 检验**证明多机制存在（分段响应显著且非线性）；证明后再重新做机制切分，不复用旧阈值。

### H-4 · 空头单机制假设（崩盘前奏必须高 ATR）
- **假设**：仅 S_seg12_high_dn / S_seg34_high_dn / S_seg2_mid_dn 三个 tier 在高波动下有信号；低 ATR 下空头无 alpha。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-08-poc-va-asymmetry stage-summary`（KF-12）
- **泄漏关系**：**部分**——分类器阈值受泄漏，但"高 ATR gate + skew 反转"的因果叙事独立于 daily 数值。
- **重测方式**：作为 minimal 版本"高 ATR gate + skew 反转触发"直接因果版重验；不复用旧 tier 阈值。

### H-17 · L_seg2_low_flat 争议 tier（可能应为均值回归 S）
- **假设**：这个 tier 在原分类下 alpha 边界性显著，但方向"顺势 L"与其"低 ATR 无趋势"环境不匹配，可能真正结构是**均值回归型 S**。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-12-va-asymmetry-composite-mathspec/p0-p9-summary`（P7）
- **泄漏关系**：**部分**
- **重测方式**：单独抽出做"方向反转 vs 保留"AB 测试；不并入其他 tier。

### H-5 · rank20 反转触发器（B 区顺势 S） / reaccept-symmetric-regime 主线
- **假设**：`sk_xsym × tr_unstable × atr_hi · downtrend × S`（B 区顺势 S）是 reaccept "对称三维协同"框架中**唯一存活分支**（其余 3 象限已被 F-6 证伪）。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-09-poc-va-asymmetry-reaccept-symmetric-regime`
- **泄漏关系**：**部分**——tr_unstable / atr_hi 由 daily 派生，是泄漏受害者；但"顺势 + 高波动 + 强偏度 → 空头反转窗口"叙事本身独立。
- **重测方式**：把 tr_unstable、atr_hi 改用 30m intraday z-score / session ATR 桶，重跑排 0 检验。

### H-6 · KF-23 分位 × ATR 甜蜜点
- **假设**：signed skew 分位（P80/P90/P95）与 ATR 桶（低/中/高）交叉后存在 2 个 h4 平均 real 显著为正的"甜蜜点"（P90×高 ATR-空头、P85×中 ATR-多头）。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-08-poc-va-asymmetry stage3-robustness`
- **泄漏关系**：**部分**——ATR 桶为泄漏源之一。
- **重测方式**：改用非泄漏 ATR 桶后重跑；甜蜜点位置可能漂移但结构值得复检。

---

## 三、组合层重估候选

### H-10 · 6-tier 组合结构 vs "6 独立信号等权" 假设
- **假设**：6 tier 存在**结构关系**（事件重叠、方向共振、收益相关），但**不是** 6 个独立信号等权（后者已被 F-11 证伪）。
- **出处**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated#2026-07-10-va-asymmetry-composite`
- **泄漏关系**：**否**（结构关系不依赖数值）
- **重测方式**：新主题在合并 tier 前必须先做**事件级重叠率 + 方向共振率 + 收益相关矩阵**三张表；根据结构结果重新设计组合层，不用等权作为默认。

---

## 附 · 建议首批验证顺序（默认）

按"泄漏关系纯净度 + 验证成本"排序：

1. **H-1 A3_skew 独立方向 alpha**（泄漏无关，最小验证单元，是否有 core alpha 的核心命题）
2. **H-11 τ_signed timing 特征**（泄漏无关，可作为 H-1 通过后的第二层特征）
3. **H-3 / H-4 多空机制假设**（泄漏部分，先做 pooled 检验绕开 tier 阈值污染）
4. **H-12 transition_flag**（泄漏部分，intraday 版本可绕开）
5. **H-5 / H-6 / H-17**（泄漏较深，验证成本高，靠后）
6. **H-10 组合层结构**（依赖至少 2 个 H 系列通过后才有意义）

**H-14** 作为方法论默认沿用，不需要独立验证——横截面对齐时用它替代 μ 即可。

**判死条件**：若 H-1 + H-11 + H-3/H-4 四个"纯净候选"全部因果版下未过门，本主题可判死并归档；不为原策略翻案。

---

## 与本主题的关系

- 本文档是**猜想侧资产**，不预设流程节点；
- 流程侧默认见 [factor-research-workflow.md](factor-research-workflow.md)（N-0 ~ N-10 + F-系列）；
- 开始验证任一 H-N 时，创建 experiment-plan.md 承载矩阵与顺序，本文档只登记假设本身。
