# structural-shaping-alpha · Research Status

> 类型：Research Status
> 状态：**七维分层证伪闭环 · 主题达到归档条件（阶段 2a 挂起除外）** · **工具资产供下游主题引用**（2026-07-09 va-asymmetry-composite 立题拉起阶段 2a）
> 最近更新：2026-07-14（阶段 2b 跨周期 tail 闭环，KF-14 沉淀；主题闭环于 K_S × RR × vol × sector × symbol × cost_scale × 周期 七维网格）
> 主题 README：[README.md](README.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)
> 下游引用主题：[va-asymmetry-composite](../../va-asymmetry-composite/README.md)（塑形工具 / 真实成本模型 / ν_implied 归因 / KF 方法论 · 当前研究主线）

## 一句话结论

**在 DirRandom no-signal baseline 下，7 个行业共识组合 + 8 个探索性 combo
（A-N）全部未通过 mean 显著正 + realistic-cost + 15m 跨周期护栏**——
**结构塑形不构成独立 alpha 源**。5m × SCALE=5 下 L/M/N 曾 mean 显著正，
但 15m 复核仅 L 保留（mean=+0.041, p=0.060），且 μ_implied 反算的
ν_implied ≈ 0（martingale 恒等式精确成立），正 mean 主要来自 Itô 凸性
+ 时间尺度放大 + 采样噪声，非"市场有真实趋势"。

**2026-07-14 分层证伪补充**：进一步按 per-symbol entry_atr 分位切三档（低/中/高波），
8 关键 combo × 3 档 = 24 行分层统计确认**塑形不是「制度过滤器」**——短期区 12/12 行
martingale 精确成立，长期区偏离全部由 time_exit% 主导（非波动率制度效应），
所有档 |ν/σ| ≤ 0.030 且方向为负。主命题从"平均证伪"升级为"分层证伪"（KF-11）。

**2026-07-14 品种一致证伪补充**：沉降到板块级（5 sectors × 8 combo = 40 行）与
品种级（20 symbols × 8 combo = 160 行）归因：板块级短期区 20/20 martingale 精确成立；
品种级 |ν/σ| 100% 覆盖率落在 KF-9 阈值 0.10 内（极值 0.051）；长期区 5 板块同向偏离
且完全由 time_exit% 主导。主命题从"分层证伪"升级为"品种一致证伪"，
**五维网格 (K_S × RR × vol × sector × symbol) 全部封闭**（KF-12）。

**2026-07-14 成本稳健性补充**：反算隐含单边成本 c_side ≈ 0.258 ATR，
8 关键 combo × 成本乘数 {0.0, 0.5, 1.0, 1.5, 2.0, 3.0} 扫描：K_S=1.0 两 combo
|mean_gross| < 0.01 即使零成本；全部 combo breakeven 乘数 m\* < 1
（当前成本已远超盈亏线，减半也救不回）；唯一零成本下 CI_lo>0 的 K_S=4/RR=2
归因 time_exit tail 分布。**主题最终闭环于 6 维网格
(K_S × RR × vol × sector × symbol × cost_scale)**（KF-13）。

**2026-07-14 阶段 2b 跨周期 tail 补充**：补齐 20 合约 × {15m, 1h} 原始数据
（26 次 tqsdk export），boundary_explorer 加 --interval 参数并在三周期上重跑
完整 65 combo 网格。8 关键 combo × 3 周期 = 24 行归因：短期区 (K_S ≤ 1.5) 11/12 行
martingale 精确成立；K_S=4/RR=2 三周期 time_exit% ≈ 31.80/31.82/32.29（几乎完全一致），
**塑形失效机制与周期无关**——2b 原假设"长周期 tail 放大"证伪；|ν/σ| 极值 0.062
远低于 KF-9 阈值 0.10。主题最终封闭于 **7 维网格 (含周期维)**（KF-14）。

**2026-07-09 更新**：本主题降级为**必要条件 & 工具资产层**（非独立策略），
工具被下游主题 [va-asymmetry-composite](../../va-asymmetry-composite/README.md) 引用：
- **First-Passage Designer**：SL/TP/TH 塑形参数扫描与 lookup 表
- **真实成本模型**：滑点 0.15 ATR × (0.5+SlippageTier) + 手续费 0.03% 双边
- **ν_implied 归因**：Itô 分解净 edge，区分"凸性伪影"与"真实趋势 alpha"
- **KF 方法论**：多层对照 / cluster bootstrap / 跨周期护栏 / 参数平台检查
下游组合策略（alpha 源：archive:2026-07-13-va-asymmetry-leak-chain-consolidated/theme-poc-value-area-asymmetry 分类器 v4.0 + 塑形参数
archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-09-poc-va-shaping SL1.0/TP1.4/TH8h）已在 100% 名义暴露约束下
跑出年化净 15.45% / Sharpe 2.23 / MaxDD -7.51，验证了"alpha 源 + 塑形工具"
组合路径可行，**本主题阶段 2a（方向 alpha × 塑形受益条件扫描）被下游拉起**。

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
| 2026-07-09 | 登记下游主题 va-asymmetry-composite 引用（阶段 2a 拉起）；降级为"必要条件 + 工具资产层"；所有塑形/成本/归因参数视为 L2 冻结常量，供下游直接调用 |
| 2026-07-14 | **重启**：阶段 1 结论（盈亏比/胜率被首达定理支配）已确认；开新分支 `experiment/structural-shaping-alpha-phase2`，启动阶段 2b（跨周期 tail）和 2c（波动率制度过滤器）扫描 |
| 2026-07-14 | **首达定理边界探索器上线**：`raw-scripts/first_passage_boundary_explorer.py` (`schedule_barrier` → `run_barrier` 重命名)，扫描 `K_S × RR` 网格（13×5 combo × 20 品种）；双 null 框架：FPT(λ=0, P_win=1/(1+RR)) 作零假设，GBM(μ=0, λ=-1) 作对照基准；补充 μ_implied/ν_implied 反算 + T* 分区 + 双层 bootstrap CI |
| 2026-07-14 | **双重 null 结论出炉**：见 [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) Part II + KF-10。FPT(λ=0) 全面碾压 GBM(μ=0)（50/65 combo，avg|Δ| 0.065–0.099 vs 0.141–0.333）。K_S=0.75–2.5 区间 FPT 偏差 <0.02，实测精确成立 martingale 恒等式。GBM μ=0 系统性低估 P_win（Itô 凸性 ν=−σ²/2 太负），价值仅限于作为保守下界 |
| 2026-07-14 | **阶段 2c 波动率制度分层闭环**：见 [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §2.7 + KF-11。按 per-symbol entry_atr 分位切三档，8 关键 combo × 3 档 = 24 行分层统计。短期区 12/12 行 martingale 精确成立；长期区偏离全部由 time_exit% 主导，非波动率制度效应；所有档 \|ν/σ\| ≤ 0.030 且方向为负。**主命题从"平均证伪"升级为"分层证伪"**，脚本 [raw-scripts/vol_regime_stratifier.py](raw-scripts/vol_regime_stratifier.py) |
| 2026-07-14 | **品种/板块归因闭环**：见 [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §2.8 + KF-12。板块级 5 sectors × 8 combo = 40 行 + 品种级 20 symbols × 8 combo = 160 行分层。板块级短期区 20/20 martingale 精确成立，长期区 5 板块**同向偏离**（|Δ| 与 time_exit% 单调正相关）；品种级 \|ν/σ\| 100% 覆盖率落在 KF-9 阈值 0.10 之内，极值 0.051。**主命题从"分层证伪"升级为"品种一致证伪"**，五维网格 (K_S × RR × vol × sector × symbol) 均无独立 alpha 生效。§2.6.2 "per-symbol v2 分析" 欠账兑现，脚本 [raw-scripts/symbol_sector_stratifier.py](raw-scripts/symbol_sector_stratifier.py) |
| 2026-07-14 | **成本敏感性闭环**：见 [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §2.9 + KF-13。反算隐含单边成本 c_side≈0.258 ATR，8 关键 combo 扫描成本乘数 {0.0, 0.5, 1.0, 1.5, 2.0, 3.0}。K_S=1.0 两 combo \|mean_gross\| < 0.01 即使零成本；全部 combo breakeven 乘数 m\* < 1（当前成本已远超盈亏线，减半也救不回）；唯一零成本下 CI_lo > 0 的 K_S=4/RR=2 归因于 time_exit tail 分布，与 KF-6/KF-11 一致。**主题最终闭环于 6 维网格 (K_S × RR × vol × sector × symbol × cost_scale)**，脚本 [raw-scripts/cost_sensitivity_stratifier.py](raw-scripts/cost_sensitivity_stratifier.py) |
| 2026-07-14 | **阶段 2b 跨周期 tail 闭环**：见 [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §2.10 + KF-14。tqsdk 补齐 20 合约 × {15m, 1h} 数据（26 次 export），boundary_explorer 加 --interval 参数后在三周期上重跑 65 combo 网格。8 关键 combo × 3 周期 = 24 行跨周期归因：短期区 (K_S ≤ 1.5) 11/12 行 |z| < 2 martingale 精确成立；K_S=4/RR=2 三周期 time_exit% 分别 31.80/31.82/32.29（几乎完全相同），**塑形失效机制与周期无关**——2b 原假设"长周期 tail 放大"证伪；\|ν/σ\| 极值 0.062 远低于 KF-9 阈值 0.10。**主题最终封闭于 7 维网格 (含周期维)**，脚本 [raw-scripts/cross_period_stratifier.py](raw-scripts/cross_period_stratifier.py) |

## 整合论文

[first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) 为本主题**唯一权威文档**：整合了理论推导 + 双重 null 实验结果 + 完整实现规格（dataclass/函数签名/输出结构/单元测试基准）+ KF-1..10 + 阶段 2 路线图。

## 下一步

阶段 1 已证伪"结构塑形独立 alpha"（KF-1..9），阶段 2 命题反转为"塑形受益条件扫描"。

**2026-07-14 重启**：新分支 `experiment/structural-shaping-alpha-phase2` @ `dev/0.6:294c989`。

**优先执行顺序**：
- **2c**（波动率制度 × 塑形）：✅ **已完成 (2026-07-14)**——证伪。所有档 |ν/σ| ≤ 0.030 且方向为负，塑形非制度过滤器。详见 [first-passage-theory-and-evidence.md §2.7](first-passage-theory-and-evidence.md) + KF-11
- **2b**（跨周期 tail）：✅ **已完成 (2026-07-14)**——证伪。补齐 15m/1h 数据后跨三周期 martingale 一致精确成立，time_exit% 与周期无关。详见 [first-passage-theory-and-evidence.md §2.10](first-passage-theory-and-evidence.md) + KF-14
- **2a**（方向 alpha × 塑形）：挂起，等 alpha 主题事件源

阶段 1 归档：`docs/archive/strategy-research/2026/07/2026-07-06-structural-shaping-alpha-stage1/`
相关工具（First-Passage Designer）已沉 [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) Part IV
+ 实现脚本 `docs/archive/strategy-research/2026/07/2026-07-06-structural-shaping-alpha-stage1/raw-scripts/first_passage_designer.py`（增强版，含 query 模式）+ 对照表
`archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#first-passage-lookup-tables`
- **2026-07-09 下游拉起**：[va-asymmetry-composite](../../va-asymmetry-composite/README.md) 作为当前主线，
  承接"方向 alpha × 塑形工具 × 组合优化"全链路，本主题仅被动提供工具资产，不再独立发起实验。
  若下游发现塑形参数（SL/TP/TH 基准）或成本模型参数需要调整，通过 pull 模式反向登记到本文件。

## 关键发现清单

主题重要结论的唯一入口。格式与更新规则见 `quant-research-layout` skill
的"关键发现清单"与"命名引用协议"两章。产出证据快照见
`archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report` §4。

### KF-1 · 结构塑形在 no-signal DirRandom 下无独立 alpha
- 类型：策略行为 · 假设证伪
- 状态：已证伪（本主题核心假设）
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §2-3 · §8.7
- 影响：结构塑形不是独立 alpha 源；未来主题必须把 alpha 放在入场方向层面；
  数学根源见 [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §1.4
  （ν=0 下 E[gross]≡0，OSt 恒等式）
- 日期：2026-07-06

### KF-2 · Trailing 分两类 · 急性负 edge · 延迟中性偏正
- 类型：策略行为
- 状态：已证实（跨 6 场景稳健）
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.9 · §8.10
- 影响：急性 breakeven trailing（F: MFE≥1 · stop=entry）paired 显著负 edge
  (F vs A p=1.000)；延迟 chandelier trailing（M/N: MFE≥3+ · trail 1.5）
  短期区首次出现正 gross 期望。armed 阈值 / 缓冲 / 是否配止盈三元组决定方向，
  单看"是否 trailing"不能判决
- 日期：2026-07-06

### KF-3 · Trailing 组合机械诊断准则
- 类型：方法论
- 状态：已证实
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §4 · D 参数病诊断案例
- 影响：breakeven trailing 的 (armed 阈值, 缓冲, 是否配止盈) 三元组决定
  win_rate 机械上限；若 win_rate 与 armed / breakeven 出场比例强反相关，
  先排查参数病（放宽 armed + 加缓冲 + 加止盈），再定命题病
- 日期：2026-07-06

### KF-4 · "少输"型 paired 显著性 ≠ 独立 alpha
- 类型：方法论
- 状态：已证实（B/K 二维拆分）
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.6
- 影响：任何 gatekeeper 看到 paired diff CI 排除 0 但 mean<0 时，必须先做
  "绝对损益尺度归因"复核（单独变距离 vs 单独变时间的二维拆分），确认显著性
  不是紧止损缩小方差带来的机械副作用
- 日期：2026-07-06

### KF-5 · 扁平 ATR 成本模型跨品种低估 4.5 倍
- 类型：方法论
- 状态：已证实（跨 10 品种实测）
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.7
- 影响：5m 期货扁平 0.05 ATR/单边 vs realistic 平均 0.225，跨品种跨度
  0.043-0.405（9 倍）。所有跨品种 mean_net_atr 判决必须用 realistic-cost
  复核；扁平模式仅供快速原型 / debug；已升级至 quant-research-methodology
  skill §5.1
- 日期：2026-07-06

### KF-6 · 近距被首达定理支配 · 远距可捕获 tail 但样本极偏
- 类型：策略行为 · 方法论
- 状态：已证实（跨 3 档 SCALE 实测）
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.10 · [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §1.5
- 影响：5m × SCALE=1 (K<3 ATR) 下 A/B/C/E/G/H/I mean 恒 ≈ -2c，胜率由
  K_S/(K_S+K_T) 完全决定；SCALE=5 (K>7 ATR) 下 L/M/N mean 严格 > 0 且
  p<0.05，但 median 严重负（-7.6 ATR），是 tail 投注分布。数学分界
  T* = max(K_S,K_T)²/σ² 精确刻画短期/长期区
- 日期：2026-07-06

### KF-7 · 5m × SCALE=5 tail alpha 是重采样伪影
- 类型：方法论
- 状态：部分证实（M/N 证伪 · L 保留）
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.11
- 影响：M/N 在 15m × SCALE=1 复核（相近物理时间 20h）下 mean 反而 <0，
  确认是"5m 数据被 5x 堆叠"伪影；L 保留（15m mean=+0.041, p=0.060）。
  任何未来 tail 类 alpha 候选必须做**同物理尺度的跨周期护栏**才能立论
- 日期：2026-07-06

### KF-8 · "数学正 edge" ≠ 工业可用 alpha
- 类型：方法论
- 状态：已证实（L/M/N 案例）
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.10 · roadmap:strategy-research-framework §5
- 影响：满足 mean 显著正 + paired CI 排除 0 只是必要条件。还需通过 framework
  §5 四道账户闸门：(1) 单次风险 ≤3%、(2) MDD 可控、(3) 频率足够、(4)
  参数平台。L/M/N @ SCALE=5 仅过 mean 门（1 就失败：stop=7.5 ATR 对应
  账户风险 13-15%）。tail 类候选归档时必须明确标注四道通过状态
- 日期：2026-07-06

### KF-9 · 归因必须用 ν = μ - σ²/2，不能用 μ
- 类型：方法论
- 状态：已证实（数学 + 6 场景实测反算）
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#first-passage-lookup-tables 表 5 · [first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §1.2
- 影响：Itô 引理下 P_win(λ) 由 λ=2ν/σ² 决定，μ=0 时 ν=-σ²/2<0（凸性修正）。
  本主题所有 combo 反算 |ν/σ|≤0.04 → **martingale 恒等式在实测精确成立**，
  所有"正 mean"都是 Itô 凸性 + 时间尺度放大 + 采样噪声，无真实市场漂移。
  未来任何主题声称"找到方向 alpha"必须证明 ν_implied > 0 显著，不是 μ > 0
- 日期：2026-07-06

### KF-10 · FPT(λ=0) 作为首达零假设碾压 GBM(μ=0)
- 类型：方法论
- 状态：已证实（20 品种 × 65 combo 双重 null 对比）
- 证据：[first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) Part II
- 影响：FPT(λ=0, P_win=1/(1+RR)) 在 K_S=0.75–2.5 区间与实测偏差 <0.02（RR=1 时 0.497 vs 0.500），
  应作为首达问题的**标准零假设**。GBM(μ=0, λ=−1) 的 Itô 凸性负漂移 ν=−σ²/2 过强，
  系统性低估 P_win（RR=1 时预测 0.27 vs 实测 0.50），唯一价值是作为保守下界。
  两道线应同时输出：FPT 做主 null，GBM μ=0 做下限对照。P_win_obs 落在 P_win_gbm 与 P_win_fpt 之间时，
  偏离不来自 ν≠0，而是缓冲/价格空间 barrier（非 log 空间）/胖尾等非 GBM 属性
- 日期：2026-07-14

### KF-11 · 波动率制度分层不改变主命题
- 类型：策略行为 · 方法论
- 状态：已证实（8 关键 combo × 3 档 = 24 行分层统计）
- 证据：[first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §2.7 · [raw-scripts/vol_regime_stratifier.py](raw-scripts/vol_regime_stratifier.py)
- 影响：按 per-symbol entry_atr 分位切三档（低/中/高波）后：短期区（K_S ≤ 1.5）12/12 行 martingale
  精确成立；长期区偏离全部由 time_exit% 主导（K_S=4 高波档 time_exit=27%，是低波档 5.5% 的 5 倍），
  非波动率制度效应；所有档 |ν/σ| ≤ 0.030 且方向为负——**没有任何一档出现真实正漂移**。
  塑形不是「制度过滤器」，主命题从"平均证伪"升级为"分层证伪"。未来任何"塑形在特定
  波动档下有效"的主张必须先排除 time_exit% 有限 T 效应干扰
- 日期：2026-07-14

### KF-12 · 品种/板块归因一致 martingale
- 类型：策略行为 · 方法论
- 状态：已证实（5 sectors × 8 combo = 40 行板块级 + 20 symbols × 8 combo = 160 行品种级分层）
- 证据：[first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §2.8 · [raw-scripts/symbol_sector_stratifier.py](raw-scripts/symbol_sector_stratifier.py)
- 影响：板块级短期区（K_S ≤ 1.5）20/20 行 martingale 精确成立；长期区 5 板块**同向偏离**（全负 ν、
  |Δ| 与 time_exit% 单调正相关），排除板块结构差异。品种级 |ν/σ| 覆盖率 100%（160/160）落在
  KF-9 阈值 0.10 内，极值 0.051（棕榈油 p2605，样本量最小）；短期区仅 5/80 行显著偏离
  （≈6.3%，接近 α=0.05 假阳性率）。**主命题从"分层证伪 (K_S×RR×vol)"升级为"品种一致证伪
  (K_S×RR×vol×sector×symbol)"**——五维网格全部封闭。未来任何"某品种/板块塑形独立有效"的主张
  必须先证明 |ν/σ| > 0.10 且跨 K_S 一致背离，非单点偏离
- 日期：2026-07-14

### KF-13 · 塑形跨成本模型稳健证伪
- 类型：策略行为 · 方法论
- 状态：已证实（8 关键 combo × 6 成本乘数扫描 + cluster bootstrap 95% CI）
- 证据：[first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §2.9 · [raw-scripts/cost_sensitivity_stratifier.py](raw-scripts/cost_sensitivity_stratifier.py)
- 影响：反算隐含单边成本 c_side≈0.258 ATR（20 品种加权，含滑点+手续费）。扫描成本乘数
  {0.0, 0.5, 1.0, 1.5, 2.0, 3.0}：K_S=1.0 两 combo |mean_gross| < 0.01 即使零成本；全部 combo
  breakeven 乘数 m\* < 1（区间 [-0.04, +0.21]）——**当前实际成本已远超盈亏点，减半也救不回**；
  唯一零成本下 CI_lo > 0 的 K_S=4/RR=2 归因于 time_exit 主导 tail 分布（KF-6/KF-11），非塑形 alpha。
  **主题最终闭环于 6 维网格 (K_S × RR × vol × sector × symbol × cost_scale)**——所有可想到的
  替代解释（波动率制度、板块结构、单一品种、低成本环境）均已排除。未来任何"低成本环境下
  塑形有效"的主张必须先证明 breakeven m\* ≥ 1 才具备工业可行性
- 日期：2026-07-14

### KF-14 · 塑形失效机制与周期无关（阶段 2b 证伪）
- 类型：策略行为 · 方法论
- 状态：已证实（20 合约 × 3 周期 × 8 关键 combo = 24 行跨周期归因）
- 证据：[first-passage-theory-and-evidence.md](first-passage-theory-and-evidence.md) §2.10 · [raw-scripts/cross_period_stratifier.py](raw-scripts/cross_period_stratifier.py) · [raw-scripts/first_passage_boundary_explorer.py](raw-scripts/first_passage_boundary_explorer.py)（--interval 参数）
- 影响：补齐 20 合约 × {15m, 1h} 原始数据（26 次 tqsdk export），在三周期下重跑 65 combo 边界扫描。
  短期区 (K_S ≤ 1.5) 12 行中 11 行 |z| < 2 martingale 精确成立；K_S=4/RR=2 三周期 time_exit%
  分别为 31.80/31.82/32.29（几乎完全一致）——**塑形失效机制在物理时间上完全对称，与周期无关**。
  同 K_S 在 1h 的物理时间是 5m 的 12 倍，但 barrier 触达归一化后的行为不变。这直接证伪了阶段 2b
  原假设"长周期 tail 放大"。|ν/σ| 极值 0.062 远低于 KF-9 阈值 0.10，跨三周期无真实正漂移。
  **主题最终封闭于 7 维网格 (K_S × RR × vol × sector × symbol × cost_scale × 周期)**——除
  仍挂起的阶段 2a（依赖外部方向 alpha 主题）外，所有内部可解替代解释均已排除。未来任何
  "长周期塑形有效"的主张必须先证明 15m/1h 下 mean_gross 与 5m 系统性差异 > SE，且 ν/σ 显著正
- 日期：2026-07-14

## 立题日期

**2026-07-05**
