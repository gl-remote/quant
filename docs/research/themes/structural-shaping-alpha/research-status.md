# structural-shaping-alpha · Research Status

> 类型：Research Status
> 状态：**阶段 1 完成 · 待冻结候选**（gatekeeper 未通过 · 阶段 2 已重构为塑形受益条件扫描，暂不启动）
> 最近更新：2026-07-06（阶段 1 gatekeeper 完成 + KF-1..9 全部沉入本文件）
> 主题 README：[README.md](README.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)

## 一句话结论

**在 DirRandom no-signal baseline 下，7 个行业共识组合 + 8 个探索性 combo
（A-N）全部未通过 mean 显著正 + realistic-cost + 15m 跨周期护栏**——
**结构塑形不构成独立 alpha 源**。5m × SCALE=5 下 L/M/N 曾 mean 显著正，
但 15m 复核仅 L 保留（mean=+0.041, p=0.060），且 μ_implied 反算的
ν_implied ≈ 0（martingale 恒等式精确成立），正 mean 主要来自 Itô 凸性
+ 时间尺度放大 + 采样噪声，非"市场有真实趋势"。

## 边界

1. **不使用 value-area 家族已证伪的入场信号**（POC / reacceptance / rolling POC / 距离档过滤）
2. **入场固定为 no_trigger baseline** + DirRandom（纯随机方向），避免变成入场信号研究
3. **阶段 1 测"整机"而非拆零件**：完整 combo（仓位 + 止损 + 止盈 + 时间 + trailing）直接对比
4. **判据必须多层对照**：Combo E 基准 + 配对差值检验 + cluster bootstrap + realistic-cost + 跨 SCALE + 跨周期

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-05 | 初版立题，v1 单维度扫描实验计划 |
| 2026-07-06 | v2 gatekeeper 精简改造：6 组合 × 120 次回测替代 v1 四子维度 |
| 2026-07-06 | 阶段 1 完成，工具 spec + 对照表脚本落地，KF-1..9 全部沉本文件 |

## 下一步

阶段 1 未通过 experiment-plan §0.6 判据（全部 combo mean ≈ -2c 或伪影），
按 §5 "任何阶段 gatekeeper 不通过即冻结主题" 处理：

- 阶段 2 已按 v2.2 重构为"塑形受益条件扫描"（2a 方向 alpha × 塑形 /
  2b 跨周期 tail / 2c 波动率制度）——**暂不启动**，等待方向 alpha 主题
  产出 baseline 后再拉起 2a
- 冻结批次准备中：`docs/archive/strategy-research/2026-07-XX-structural-shaping-alpha-frozen/`
- 相关工具（First-Passage Designer）已沉 [first-passage-designer-math-spec.md](first-passage-designer-math-spec.md)
  + 实现脚本 `scripts/ai_tmp/first_passage_designer.py` + 对照表
  `archive:2026-07-06-structural-shaping-alpha-stage1#first-passage-lookup-tables`

## 关键发现清单

主题重要结论的唯一入口。格式与更新规则见 `quant-research-layout` skill
的"关键发现清单"与"命名引用协议"两章。产出证据快照见
`archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report` §4。

### KF-1 · 结构塑形在 no-signal DirRandom 下无独立 alpha
- 类型：策略行为 · 假设证伪
- 状态：已证伪（本主题核心假设）
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §2-3 · §8.7
- 影响：结构塑形不是独立 alpha 源；未来主题必须把 alpha 放在入场方向层面；
  数学根源见 theme:structural-shaping-alpha#first-passage-designer-math-spec §2.5
  （ν=0 下 E[gross]≡0，OSt 恒等式）
- 日期：2026-07-06

### KF-2 · Trailing 分两类 · 急性负 edge · 延迟中性偏正
- 类型：策略行为
- 状态：已证实（跨 6 场景稳健）
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.9 · §8.10
- 影响：急性 breakeven trailing（F: MFE≥1 · stop=entry）paired 显著负 edge
  (F vs A p=1.000)；延迟 chandelier trailing（M/N: MFE≥3+ · trail 1.5）
  短期区首次出现正 gross 期望。armed 阈值 / 缓冲 / 是否配止盈三元组决定方向，
  单看"是否 trailing"不能判决
- 日期：2026-07-06

### KF-3 · Trailing 组合机械诊断准则
- 类型：方法论
- 状态：已证实
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §4 · D 参数病诊断案例
- 影响：breakeven trailing 的 (armed 阈值, 缓冲, 是否配止盈) 三元组决定
  win_rate 机械上限；若 win_rate 与 armed / breakeven 出场比例强反相关，
  先排查参数病（放宽 armed + 加缓冲 + 加止盈），再定命题病
- 日期：2026-07-06

### KF-4 · "少输"型 paired 显著性 ≠ 独立 alpha
- 类型：方法论
- 状态：已证实（B/K 二维拆分）
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.6
- 影响：任何 gatekeeper 看到 paired diff CI 排除 0 但 mean<0 时，必须先做
  "绝对损益尺度归因"复核（单独变距离 vs 单独变时间的二维拆分），确认显著性
  不是紧止损缩小方差带来的机械副作用
- 日期：2026-07-06

### KF-5 · 扁平 ATR 成本模型跨品种低估 4.5 倍
- 类型：方法论
- 状态：已证实（跨 10 品种实测）
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.7
- 影响：5m 期货扁平 0.05 ATR/单边 vs realistic 平均 0.225，跨品种跨度
  0.043-0.405（9 倍）。所有跨品种 mean_net_atr 判决必须用 realistic-cost
  复核；扁平模式仅供快速原型 / debug；已升级至 quant-research-methodology
  skill §5.1
- 日期：2026-07-06

### KF-6 · 近距被首达定理支配 · 远距可捕获 tail 但样本极偏
- 类型：策略行为 · 方法论
- 状态：已证实（跨 3 档 SCALE 实测）
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.10 · theme:structural-shaping-alpha#first-passage-designer-math-spec §2.7
- 影响：5m × SCALE=1 (K<3 ATR) 下 A/B/C/E/G/H/I mean 恒 ≈ -2c，胜率由
  K_S/(K_S+K_T) 完全决定；SCALE=5 (K>7 ATR) 下 L/M/N mean 严格 > 0 且
  p<0.05，但 median 严重负（-7.6 ATR），是 tail 投注分布。数学分界
  T* = max(K_S,K_T)²/σ² 精确刻画短期/长期区
- 日期：2026-07-06

### KF-7 · 5m × SCALE=5 tail alpha 是重采样伪影
- 类型：方法论
- 状态：部分证实（M/N 证伪 · L 保留）
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.11
- 影响：M/N 在 15m × SCALE=1 复核（相近物理时间 20h）下 mean 反而 <0，
  确认是"5m 数据被 5x 堆叠"伪影；L 保留（15m mean=+0.041, p=0.060）。
  任何未来 tail 类 alpha 候选必须做**同物理尺度的跨周期护栏**才能立论
- 日期：2026-07-06

### KF-8 · "数学正 edge" ≠ 工业可用 alpha
- 类型：方法论
- 状态：已证实（L/M/N 案例）
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.10 · roadmap:strategy-research-framework §5
- 影响：满足 mean 显著正 + paired CI 排除 0 只是必要条件。还需通过 framework
  §5 四道账户闸门：(1) 单次风险 ≤3%、(2) MDD 可控、(3) 频率足够、(4)
  参数平台。L/M/N @ SCALE=5 仅过 mean 门（1 就失败：stop=7.5 ATR 对应
  账户风险 13-15%）。tail 类候选归档时必须明确标注四道通过状态
- 日期：2026-07-06

### KF-9 · 归因必须用 ν = μ - σ²/2，不能用 μ
- 类型：方法论
- 状态：已证实（数学 + 6 场景实测反算）
- 证据：archive:2026-07-06-structural-shaping-alpha-stage1#first-passage-lookup-tables 表 5 · theme:structural-shaping-alpha#first-passage-designer-math-spec 顶部警告章节
- 影响：Itô 引理下 P_win(λ) 由 λ=2ν/σ² 决定，μ=0 时 ν=-σ²/2<0（凸性修正）。
  本主题所有 combo 反算 |ν/σ|≤0.04 → **martingale 恒等式在实测精确成立**，
  所有"正 mean"都是 Itô 凸性 + 时间尺度放大 + 采样噪声，无真实市场漂移。
  未来任何主题声称"找到方向 alpha"必须证明 ν_implied > 0 显著，不是 μ > 0
- 日期：2026-07-06

## 立题日期

**2026-07-05**
