# structural-shaping-alpha · Research Status

> 类型：Research Status
> 状态：**塑形三定律定型（KF-20）· 主题完整认识跃升 · 主命题最终定型**
> 最近更新：2026-07-14（§2.18 塑形物理本质：不创造 alpha 但是方向 alpha 的兑现容器）
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

**2026-07-14 极端盈亏比补漏**：扩展 K_S × RR = {0.5..4.0} × {5, 8}，5m/15m/1h
三周期各重跑一次 boundary_explorer。12 combo × 3 周期 = 36 行归因：36/36 行
bootstrap CI 覆盖 0 → 工业级 alpha 一致证伪；但**首次记录 ν/σ = 0.117**
（K_S=0.5/RR=5 @ 1h）突破 KF-9 阈值 0.10，P_win 正偏离在该通道跨三周期
单调放大（z: 4.54 → 6.85 → 3.06），提示极小 barrier 下 GBM 假设本身不精确；
但成本 c_side/K_S = 52% 直接吞噬所有微 edge。**主题最终封闭于 8 维网格
（+极端 RR 边界维）**（KF-15）。

**2026-07-14 KF-15 三重扎实化**：新增 §2.12 做三层检验决定 KF-15 命运：
(1) 事件级 cluster bootstrap 显示 K_S=0.5/RR=5 三周期 ν/σ CI 全排除 0
（+0.0161/+0.0701/+0.1163）；(2) barrier 停时 skew 与 martingale 双峰理论对比，
实测 skew 略小于理论（与 P_win 抬高完全自洽），证伪 GBM 伪影解释；
(3) 20 合约 Hurst 指数跨周期上升（5m 0.542 → 1h 0.603，1h 上 19/20 合约 H>0.55），
KF-16 沉淀"中国期货存在 Hurst 趋势凝聚"。σ 跨周期实测 3.04 < √12=3.46（子扩散）
定量支持 H2 假设。**KF-15 从"边界发现"升级为"真实微 alpha 通道"**，工业不可用
条件不变（成本 c_side/K_S = 52%）。

**2026-07-14 KF-15 Fourier 精确解四重扎实化**：新增 §2.13 用 Fourier 级数
精确解替代 T=∞ 近似作为 null（KF-17 沉淀）。K_S=0.5/RR=5 三周期有限时间修正
P_win_finiteT − P_win_∞ **全部为负**（−0.011/−0.002/−0.002）——残余真实 alpha
(obs − finiteT) 反而**大于** T=∞ 偏离（+0.035/+0.066/+0.054）。
K_S=1/RR=1 参照实测与 Fourier 精确 null 差 −0.0005（1e-3 精度）。
P(τ>T) 理论 vs 实测差可作独立漂移探测器。**KF-15 强度不降反升**——
Fourier + 事件级 CI + 分布 skew + Hurst 四种独立方法一致支持真实方向漂移。

**2026-07-14 全套扎实化 + 已有结论重检**：新增 §2.14/§2.15/§2.16
+ 3 个脚本（recheck_kf11_fourier / drift_detector_full_scan / K_S<1 极端扫描）。
**KF-11 归因语言修正**：原口径 9/24 行 z_old<−2 归因"time_exit 主导负偏离"；
Fourier 精确 null 下 14/24 行符号翻转、16/24 行新显著正偏离——实际是"真实漂移
把 P_win 从零漂移 6% 抬到 20%"，Doob 定理保证 E_gross 仍为 0。**KF-14 强化**：
跨周期不变性由真实漂移主动补偿（K_S=4/RR=2 三周期 P(τ>T)_theory 剧变
0.877→0.556→0.071，实测 ≈ 0.32 恒定）。**KF-6 收窄**：短期区从 K_S≤1.5
收窄为 K_S∈[1.0, 1.5]（塑形"暗物质带"）。**KF-15 从边界扩展为区域**：
K_S ∈ [0.25, 1.0] × RR ∈ [3, 12] × 3 周期 = 60 行系统微 alpha，5m 上 20/20 显著
（z_new 极值 +105.77）。**KF-18 沉淀**：全 195 combo 双通道校准表——
通道 A (P_win) 71.3% 显著、通道 B (P(τ>T)) 96.9% 显著，53 行仅 B 显著。
主题最终封闭于 **9 维网格**，工业结论不变（E_net 全部不显著正）。

**2026-07-14 H4 跨周期趋势泄漏假设实证**：新增 §2.17 + hf_trend_leakage_probe.py。
读 5m trades 按同合约 1h EMA20 判断入场时刻的 1h 趋势方向，分 aligned/opposed
组重算。**K_S=4/RR=2 @ 5m aligned P_win = 0.2151 vs opposed = 0.1789**
（Δ=+0.036, z=+3.19），**ΔE_gross=+0.488 ATR/笔**——6/6 关键 combo 全部显著。
K_S=1/RR=1 martingale 参照 DirRandom 下 P_win=0.4963（精确成立），
aligned=0.5461/opposed=0.4490（方向筛选下打破 martingale）。**KF-19 沉淀**：
塑形从"独立 alpha"转为"跨周期趋势泄漏 alpha 的兑现工具"——阶段 2a 从
抽象等 alpha 变为具体等一个长周期趋势信号（如 EMA20/日线突破/结构信号）。
当前成本 c_side ≈ 0.258 ATR 使 E_net 仍负，需要 c_side ≤ 0.15 才可行。

**2026-07-14 塑形物理本质定型（KF-20）**：新增 §2.18 塑形三定律。
**定律 I Doob 保守律**：DirRandom 下即使零成本 E_gross ≈ 0，塑形本身不创造 alpha
（Doob 停时定理保证）。**定律 II 结构 alpha 兑现律**：市场结构 alpha
（KF-15 K_S<1 微 alpha 区、KF-16 Hurst 趋势凝聚）通过塑形 barrier 从
"每 bar 微漂移"累积成"每笔停时 barrier 差"。**定律 III 方向 alpha 放大律**：
外部方向信号（哪怕最朴素 EMA20）把停时从 non-adapted 变为 adapted，
打破 Doob 保守律，让塑形容器承载 +0.25 ATR/笔量级 alpha。
**主命题最终定型**：塑形不创造 alpha，但作为方向 alpha 的兑现容器，
是让 alpha 在交易执行系统"活下来"的必要工程工具。**主题从"证伪独立 alpha"
到"识别兑现工具"的完整认识跃升完成**——塑形研究的价值不在寻找 alpha，
而在建立方向 alpha 的兑现基础设施。

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
| 2026-07-14 | **双重 null 结论出炉**：见 [shaping-theory.md](shaping-theory.md) Part II + KF-10。FPT(λ=0) 全面碾压 GBM(μ=0)（50/65 combo，avg|Δ| 0.065–0.099 vs 0.141–0.333）。K_S=0.75–2.5 区间 FPT 偏差 <0.02，实测精确成立 martingale 恒等式。GBM μ=0 系统性低估 P_win（Itô 凸性 ν=−σ²/2 太负），价值仅限于作为保守下界 |
| 2026-07-14 | **阶段 2c 波动率制度分层闭环**：见 [shaping-theory.md](shaping-theory.md) §2.7 + KF-11。按 per-symbol entry_atr 分位切三档，8 关键 combo × 3 档 = 24 行分层统计。短期区 12/12 行 martingale 精确成立；长期区偏离全部由 time_exit% 主导，非波动率制度效应；所有档 \|ν/σ\| ≤ 0.030 且方向为负。**主命题从"平均证伪"升级为"分层证伪"**，脚本 [raw-scripts/vol_regime_stratifier.py](raw-scripts/vol_regime_stratifier.py) |
| 2026-07-14 | **品种/板块归因闭环**：见 [shaping-theory.md](shaping-theory.md) §2.8 + KF-12。板块级 5 sectors × 8 combo = 40 行 + 品种级 20 symbols × 8 combo = 160 行分层。板块级短期区 20/20 martingale 精确成立，长期区 5 板块**同向偏离**（|Δ| 与 time_exit% 单调正相关）；品种级 \|ν/σ\| 100% 覆盖率落在 KF-9 阈值 0.10 之内，极值 0.051。**主命题从"分层证伪"升级为"品种一致证伪"**，五维网格 (K_S × RR × vol × sector × symbol) 均无独立 alpha 生效。§2.6.2 "per-symbol v2 分析" 欠账兑现，脚本 [raw-scripts/symbol_sector_stratifier.py](raw-scripts/symbol_sector_stratifier.py) |
| 2026-07-14 | **成本敏感性闭环**：见 [shaping-theory.md](shaping-theory.md) §2.9 + KF-13。反算隐含单边成本 c_side≈0.258 ATR，8 关键 combo 扫描成本乘数 {0.0, 0.5, 1.0, 1.5, 2.0, 3.0}。K_S=1.0 两 combo \|mean_gross\| < 0.01 即使零成本；全部 combo breakeven 乘数 m\* < 1（当前成本已远超盈亏线，减半也救不回）；唯一零成本下 CI_lo > 0 的 K_S=4/RR=2 归因于 time_exit tail 分布，与 KF-6/KF-11 一致。**主题最终闭环于 6 维网格 (K_S × RR × vol × sector × symbol × cost_scale)**，脚本 [raw-scripts/cost_sensitivity_stratifier.py](raw-scripts/cost_sensitivity_stratifier.py) |
| 2026-07-14 | **阶段 2b 跨周期 tail 闭环**：见 [shaping-theory.md](shaping-theory.md) §2.10 + KF-14。tqsdk 补齐 20 合约 × {15m, 1h} 数据（26 次 export），boundary_explorer 加 --interval 参数后在三周期上重跑 65 combo 网格。8 关键 combo × 3 周期 = 24 行跨周期归因：短期区 (K_S ≤ 1.5) 11/12 行 |z| < 2 martingale 精确成立；K_S=4/RR=2 三周期 time_exit% 分别 31.80/31.82/32.29（几乎完全相同），**塑形失效机制与周期无关**——2b 原假设"长周期 tail 放大"证伪；\|ν/σ\| 极值 0.062 远低于 KF-9 阈值 0.10。**主题最终封闭于 7 维网格 (含周期维)**，脚本 [raw-scripts/cross_period_stratifier.py](raw-scripts/cross_period_stratifier.py) |
| 2026-07-14 | **极端盈亏比补漏闭环**：见 [shaping-theory.md](shaping-theory.md) §2.11 + KF-15。扩展 K_S × RR = {0.5..4.0} × {5, 8}，5m/15m/1h 三周期各重跑一次 boundary_explorer。12 combo × 3 周期 = 36 行归因：36/36 行 bootstrap CI 覆盖 0 → 工业级 alpha 一致证伪；但**首次记录 ν/σ = 0.117**（K_S=0.5/RR=5 @ 1h）突破 KF-9 阈值 0.10，P_win 正偏离在该通道跨三周期单调放大（z: 4.54 → 6.85 → 3.06），提示极小 barrier 下 GBM 假设本身不精确；但成本 c_side/K_S = 52% 直接吞噬所有微 edge——与 KF-8 精确对应。**主题最终封闭于 8 维网格（+极端 RR 边界维）**，脚本 [raw-scripts/extreme_rr_stratifier.py](raw-scripts/extreme_rr_stratifier.py) |
| 2026-07-14 | **KF-15 三重扎实化 + KF-16 沉淀**：见 [shaping-theory.md](shaping-theory.md) §2.12。三个独立扎实化脚本（kf15_significance_test / kf15_gbm_fit_test / hurst_stratifier）：(1) 事件级 cluster bootstrap 显示 K_S=0.5/RR=5 三周期 ν/σ CI 全排除 0（+0.0161/+0.0701/+0.1163）；(2) barrier 停时 skew 与 martingale 双峰理论对比，实测 skew 略小于理论（与 P_win 抬高完全自洽），证伪 GBM 伪影解释；(3) 20 合约 Hurst 指数跨周期上升（5m 0.542 → 1h 0.603，1h 上 19/20 合约 H>0.55），KF-16 "中国期货存在 Hurst 趋势凝聚"沉淀。σ 跨周期实测 3.04 < √12=3.46（子扩散）定量支持 H2。**KF-15 从"边界发现"升级为"真实微 alpha 通道"**，工业不可用条件不变 |
| 2026-07-14 | **KF-15 Fourier 精确解四重扎实化 + KF-17 沉淀**：见 [shaping-theory.md](shaping-theory.md) §2.13 + [raw-scripts/fourier_finite_time_test.py](raw-scripts/fourier_finite_time_test.py)。用 Fourier 级数精确解 P_win(T) = (2/π) Σ (−1)^{n+1}/n · sin(nπK_S/L) · (1−exp(−n²π²σ²T/(2L²))) 替代 T=∞ 近似作为 null。K_S=0.5/RR=5 三周期有限时间修正 P_win_finiteT − P_win_∞ **全部为负**（−0.011/−0.002/−0.002）——残余真实 alpha 反而**大于** T=∞ 偏离（+0.035/+0.066/+0.054）。K_S=1/RR=1 martingale 参照实测与理论差 −0.0005（1e-3 精度），Fourier 解通过独立验证。P(τ>T) 理论 vs 实测差成为独立漂移探测器。**KF-15 强度不降反升**——Fourier + 事件级 CI + 分布 skew + Hurst 四种独立方法一致支持真实方向漂移 |
| 2026-07-14 | **全套扎实化 + 已有结论重检**：见 [shaping-theory.md](shaping-theory.md) §2.14/§2.15/§2.16 + 3 个新脚本（recheck_kf11_fourier / drift_detector_full_scan / K_S<1 极端扫描）。**KF-11 归因语言修正**（Fourier null 下 14/24 行符号翻转，隐藏正漂移，Doob 保证 E_gross=0）；**KF-14 强化**（跨周期不变性由真实漂移主动补偿）；**KF-6 收窄**（K_S∈[1.0, 1.5] 暗物质带）；**KF-15 从边界扩展为 K_S<1 系统微 alpha 区**（60 行 5m 上 20/20 显著，z_new 极值 +105.77）；**KF-18 沉淀** 双通道漂移探测器全 195 combo 校准表。**主题最终封闭于 9 维网格**，工业结论不变 |
| 2026-07-14 | **H4 跨周期趋势泄漏实证 + KF-19 沉淀**：见 [shaping-theory.md](shaping-theory.md) §2.17 + [raw-scripts/hf_trend_leakage_probe.py](raw-scripts/hf_trend_leakage_probe.py)。读 5m trades 按 1h EMA20 判断入场时刻 1h 趋势方向，分 aligned/opposed 组重算。K_S=4/RR=2 @ 5m aligned P_win=0.2151 vs opposed=0.1789（Δ=+0.036, z=+3.19），**ΔE_gross=+0.488 ATR/笔**——6/6 关键 combo 全部显著。K_S=1/RR=1 martingale 参照 DirRandom 下精确（P_win=0.4963），方向筛选下打破（aligned=0.5461/opposed=0.4490）。**塑形从"独立 alpha"重定位为"跨周期趋势泄漏的兑现工具"**，阶段 2a 从抽象等 alpha 变为具体等一个 1h 趋势信号；工业实现需 c_side ≤ 0.15 ATR（当前 0.258） |
| 2026-07-14 | **塑形物理本质定型 + KF-20 沉淀**：见 [shaping-theory.md](shaping-theory.md) §2.18。**塑形三定律**：（I）Doob 保守律 DirRandom 下即使零成本 E_gross≈0；（II）结构 alpha 兑现律 KF-15/16 通过塑形 barrier 从每 bar 微漂移累积到每笔 barrier 差；（III）方向 alpha 放大律 aligned 筛选打破 non-adapted 停时前提，让塑形容器承载 +0.25 ATR/笔量级 alpha。**主命题最终定型**：塑形不创造 alpha，但作为方向 alpha 的兑现容器，是让 alpha 在交易执行系统"活下来"的必要工程工具。主题从"证伪独立 alpha"到"识别兑现工具"的完整认识跃升完成 |

## 整合论文

[shaping-theory.md](shaping-theory.md) 为本主题**唯一权威文档**：整合了理论推导 + 双重 null 实验结果 + 完整实现规格（dataclass/函数签名/输出结构/单元测试基准）+ KF-1..10 + 阶段 2 路线图。

## 下一步

阶段 1 已证伪"结构塑形独立 alpha"（KF-1..9），阶段 2 命题反转为"塑形受益条件扫描"。

**2026-07-14 重启**：新分支 `experiment/structural-shaping-alpha-phase2` @ `dev/0.6:294c989`。

**优先执行顺序**：
- **2c**（波动率制度 × 塑形）：✅ **已完成 (2026-07-14)**——证伪。所有档 |ν/σ| ≤ 0.030 且方向为负，塑形非制度过滤器。详见 [shaping-theory.md §2.7](shaping-theory.md) + KF-11
- **2b**（跨周期 tail）：✅ **已完成 (2026-07-14)**——证伪。补齐 15m/1h 数据后跨三周期 martingale 一致精确成立，time_exit% 与周期无关。详见 [shaping-theory.md §2.10](shaping-theory.md) + KF-14
- **2a**（方向 alpha × 塑形）：挂起，等 alpha 主题事件源

阶段 1 归档：`docs/archive/strategy-research/2026/07/2026-07-06-structural-shaping-alpha-stage1/`
相关工具（First-Passage Designer）已沉 [shaping-theory.md](shaping-theory.md) Part IV
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
  数学根源见 [shaping-theory.md](shaping-theory.md) §1.4
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
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report §8.10 · [shaping-theory.md](shaping-theory.md) §1.5
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
- 证据：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#first-passage-lookup-tables 表 5 · [shaping-theory.md](shaping-theory.md) §1.2
- 影响：Itô 引理下 P_win(λ) 由 λ=2ν/σ² 决定，μ=0 时 ν=-σ²/2<0（凸性修正）。
  本主题所有 combo 反算 |ν/σ|≤0.04 → **martingale 恒等式在实测精确成立**，
  所有"正 mean"都是 Itô 凸性 + 时间尺度放大 + 采样噪声，无真实市场漂移。
  未来任何主题声称"找到方向 alpha"必须证明 ν_implied > 0 显著，不是 μ > 0
- 日期：2026-07-06

### KF-10 · FPT(λ=0) 作为首达零假设碾压 GBM(μ=0)
- 类型：方法论
- 状态：已证实（20 品种 × 65 combo 双重 null 对比）
- 证据：[shaping-theory.md](shaping-theory.md) Part II
- 影响：FPT(λ=0, P_win=1/(1+RR)) 在 K_S=0.75–2.5 区间与实测偏差 <0.02（RR=1 时 0.497 vs 0.500），
  应作为首达问题的**标准零假设**。GBM(μ=0, λ=−1) 的 Itô 凸性负漂移 ν=−σ²/2 过强，
  系统性低估 P_win（RR=1 时预测 0.27 vs 实测 0.50），唯一价值是作为保守下界。
  两道线应同时输出：FPT 做主 null，GBM μ=0 做下限对照。P_win_obs 落在 P_win_gbm 与 P_win_fpt 之间时，
  偏离不来自 ν≠0，而是缓冲/价格空间 barrier（非 log 空间）/胖尾等非 GBM 属性
- 日期：2026-07-14

### KF-11 · 波动率制度分层不改变主命题
- 类型：策略行为 · 方法论
- 状态：已证实（8 关键 combo × 3 档 = 24 行分层统计）
- 证据：[shaping-theory.md](shaping-theory.md) §2.7 · [raw-scripts/vol_regime_stratifier.py](raw-scripts/vol_regime_stratifier.py)
- 影响：按 per-symbol entry_atr 分位切三档（低/中/高波）后：短期区（K_S ≤ 1.5）12/12 行 martingale
  精确成立；长期区偏离全部由 time_exit% 主导（K_S=4 高波档 time_exit=27%，是低波档 5.5% 的 5 倍），
  非波动率制度效应；所有档 |ν/σ| ≤ 0.030 且方向为负——**没有任何一档出现真实正漂移**。
  塑形不是「制度过滤器」，主命题从"平均证伪"升级为"分层证伪"。未来任何"塑形在特定
  波动档下有效"的主张必须先排除 time_exit% 有限 T 效应干扰
- 日期：2026-07-14

### KF-12 · 品种/板块归因一致 martingale
- 类型：策略行为 · 方法论
- 状态：已证实（5 sectors × 8 combo = 40 行板块级 + 20 symbols × 8 combo = 160 行品种级分层）
- 证据：[shaping-theory.md](shaping-theory.md) §2.8 · [raw-scripts/symbol_sector_stratifier.py](raw-scripts/symbol_sector_stratifier.py)
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
- 证据：[shaping-theory.md](shaping-theory.md) §2.9 · [raw-scripts/cost_sensitivity_stratifier.py](raw-scripts/cost_sensitivity_stratifier.py)
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
- 证据：[shaping-theory.md](shaping-theory.md) §2.10 · [raw-scripts/cross_period_stratifier.py](raw-scripts/cross_period_stratifier.py) · [raw-scripts/first_passage_boundary_explorer.py](raw-scripts/first_passage_boundary_explorer.py)（--interval 参数）
- 影响：补齐 20 合约 × {15m, 1h} 原始数据（26 次 tqsdk export），在三周期下重跑 65 combo 边界扫描。
  短期区 (K_S ≤ 1.5) 12 行中 11 行 |z| < 2 martingale 精确成立；K_S=4/RR=2 三周期 time_exit%
  分别为 31.80/31.82/32.29（几乎完全一致）——**塑形失效机制在物理时间上完全对称，与周期无关**。
  同 K_S 在 1h 的物理时间是 5m 的 12 倍，但 barrier 触达归一化后的行为不变。这直接证伪了阶段 2b
  原假设"长周期 tail 放大"。|ν/σ| 极值 0.062 远低于 KF-9 阈值 0.10，跨三周期无真实正漂移。
  **主题最终封闭于 7 维网格 (K_S × RR × vol × sector × symbol × cost_scale × 周期)**——除
  仍挂起的阶段 2a（依赖外部方向 alpha 主题）外，所有内部可解替代解释均已排除。未来任何
  "长周期塑形有效"的主张必须先证明 15m/1h 下 mean_gross 与 5m 系统性差异 > SE，且 ν/σ 显著正
- 日期：2026-07-14

### KF-15 · K_S=0.5/RR=5 通道存在真实微 alpha（工业不可用）
- 类型：策略行为 · 方法论 · 边界发现（三重扎实化）
- 状态：已证实（事件级 CI + 分布拟合 + Hurst 三重独立验证）
- 证据：[shaping-theory.md](shaping-theory.md) §2.11, §2.12 · [raw-scripts/extreme_rr_stratifier.py](raw-scripts/extreme_rr_stratifier.py) · [raw-scripts/kf15_significance_test.py](raw-scripts/kf15_significance_test.py) · [raw-scripts/kf15_gbm_fit_test.py](raw-scripts/kf15_gbm_fit_test.py)
- 影响：K_S=0.5/RR=5 通道三周期一致 P_win 显著高于 FPT null（z=4.54/6.85/3.06），
  ν/σ = 0.016/0.070/0.117 随周期单调放大。**三重扎实化确认**：
  (1) 事件级 cluster bootstrap CI 全排除 0（+0.0161/+0.0701/+0.1163）；
  (2) barrier 停时 skew 与 martingale 双峰理论一致（略小于理论证明 winners 真的更多）；
  (3) σ 跨周期实测 3.04 < √12=3.46（子扩散实证 H2 假设）。
  **数学层结论**：真实微 alpha，不是 GBM 伪影 / 不是 P_win 随机波动。
  **工业层结论**：成本 c_side/K_S = 52% 直接吞噬全部微 edge——36/36 行 E_net CI 覆盖 0。
  未来任何"K_S=0.5/RR=5 长周期塑形有 alpha"的主张，必须先给出：
  (1) 单边成本降到 ≤ 0.05 ATR 的实证（e.g. 做市 / 主动 taker rebate）；
  (2) 或事件级 ν/σ 显著性检验证明该通道是真实漂移而非 GBM 偏离
- 日期：2026-07-14

### KF-16 · 中国期货 5m/15m/1h 存在 Hurst 趋势凝聚 (H>0.55)
- 类型：市场结构 · 方法论
- 状态：已证实（20 合约 × 3 周期 R/S 分析）
- 证据：[shaping-theory.md](shaping-theory.md) §2.12.4 · [raw-scripts/hurst_stratifier.py](raw-scripts/hurst_stratifier.py)
- 影响：20 合约跨周期 Hurst 指数 5m mean=0.542 / 15m mean=0.558 / 1h mean=0.603，
  **1h 上 19/20 合约 H > 0.55**（趋势凝聚），无任何合约 H < 0.45（均值回归）。
  Hurst 随周期单调上升，方向与 KF-15 ν/σ 放大方向完全一致。
  **对下游主题的意义**：
  (1) 长周期动量类策略（1h+）有 Hurst 趋势凝聚支持，先验偏向 alpha 存在
  (2) 短周期均值回归类策略（5m 极短距）Hurst 接近 0.5，先验偏向 martingale
  (3) 波动率子扩散实证（σ_1h/σ_5m = 3.04 < √12 = 3.46）：长周期趋势力"吸走"部分噪声
  (4) 时序动态 Hurst 分析（是否随波动率制度切换）是未来主题种子
- 日期：2026-07-14

### KF-17 · Fourier 精确解作为 barrier 停时研究的标准 null
- 类型：方法论 · 工具沉淀
- 状态：已证实（K_S=1/RR=1 martingale 参照精度 1e-3；K_S=0.5/RR=5 KF-15 分解证明工具威力）
- 证据：[shaping-theory.md](shaping-theory.md) §2.13, §2.16 · [raw-scripts/fourier_finite_time_test.py](raw-scripts/fourier_finite_time_test.py)
- 影响：零漂移双 barrier + 有限时间 T 下 P_win 与 P(τ>T) 的 Fourier 级数精确解
  P_win(T) = (2/π) Σ (−1)^{n+1}/n · sin(nπK_S/L) · (1−exp(−n²π²σ²T/(2L²)))
  作为**任何 barrier 停时研究的标准 null**，替代 T=∞ 近似 P_win = K_S/L。
  **三大工具用途**：
  (1) **归因分解**：把观测偏离拆成"有限时间修正 + 残余真实 alpha"两层
  (2) **独立漂移探测器**：P(τ>T)_theory vs P_time_exit_obs 的差，与 P_win 独立
  (3) **T\* 精确闭式**：给定 (K_S, K_T, σ) 反算让 time_exit% < 阈值的最小 T
  未来所有 barrier 结构策略都应用 Fourier 精确解替代 T=∞ 近似作为 null 检验
- 日期：2026-07-14

### KF-18 · 双通道漂移探测器（P_win + P(τ>T)）全 combo 校准表
- 类型：方法论 · 工具沉淀
- 状态：已证实（全 65 combo × 3 周期 = 195 行双通道扫描）
- 证据：[shaping-theory.md](shaping-theory.md) §2.16 · [raw-scripts/drift_detector_full_scan.py](raw-scripts/drift_detector_full_scan.py)
- 影响：全 195 行双通道对齐扫描：通道 A (P_win_obs vs P_win_finiteT) 71.3% 显著，
  通道 B (P_time_exit_obs vs P(τ>T)_theory) 96.9% 显著。**53 行仅 B 显著**——
  time_exit 通道**独立捕获**了 P_win 忽略的漂移信号，是下游主题重要的**双通道验证工具**。
  **使用建议**：
  (1) 事件级 alpha 验证应双通道并行
  (2) 判据组合：`(z_A > 2 且 z_B < −2)` 或 `(z_A > 2 且 z_B_valid=False)` 都可作真实漂移证据
  (3) 过滤 P(τ>T)_theory < 0.001 的格点（数值精度边界）
- 日期：2026-07-14

### KF-19 · 跨周期趋势泄漏 + 塑形放大 = 阶段 2a 潜在工业 alpha 路径
- 类型：策略行为 · 方法论 · 阶段 2a 桥梁
- 状态：已实证（6/6 关键 combo aligned vs opposed 全部显著）
- 证据：[shaping-theory.md](shaping-theory.md) §2.17 · [raw-scripts/hf_trend_leakage_probe.py](raw-scripts/hf_trend_leakage_probe.py) · 关联 KF-11 (§2.14.2) / KF-16 (§2.12.4)
- 影响：H4 跨周期趋势泄漏假设直接被实测证实——用 1h EMA20 作为最朴素方向 alpha
  分组 5m trades，K_S=4/RR=2 aligned P_win = 0.2151 vs opposed P_win = 0.1789
  （Δ=+0.036, z=+3.19），**ΔE_gross = +0.488 ATR/笔**。6/6 关键 combo (K_S ∈ [1, 4] × RR ∈ [1, 2])
  全部显著（z 从 +3.19 到 +6.94）。K_S=1/RR=1 对称 martingale 参照下，DirRandom 精确
  但方向筛选后 P_win=0.5461（超 martingale 0.5）——**martingale 恒等式只在方向随机时精确**。
  **塑形从"独立 alpha"转为"跨周期趋势泄漏 alpha 的兑现工具"**——阶段 2a 从"抽象等一个
  未来 alpha 主题"变为"具体等一个 1h 趋势信号"。工业实现门槛：
  (1) 单边成本降到 c_side ≤ 0.15 ATR（当前 0.258）
  (2) 或用更强的方向信号（日线突破 / 结构信号 / 外部主题）提高 ΔE_gross
  (3) 事件级验证配合 KF-18 双通道漂移探测器
  **未来任何塑形策略在设计入场信号时，都应保证与"1h 或更高周期"结构性动量方向一致**
- 日期：2026-07-14

### KF-20 · 塑形三定律（主命题最终定型）
- 类型：理论定型 · 主题总结
- 状态：已证实（KF-1..19 完整证据链聚合）
- 证据：[shaping-theory.md](shaping-theory.md) §2.18 · 主题所有前述 KF 与 §2.1-§2.17
- 影响：**塑形工具的物理本质从三个层级严格定型**：
  **定律 I（Doob 保守律）**：DirRandom 方向下，任何 barrier 结构 (K_S, K_T, T) 都保证 E_gross ≈ 0。
  塑形本身不创造 alpha，即使零成本也不变（Doob 停时定理保证）。
  **定律 II（结构 alpha 兑现律）**：市场结构 alpha（KF-15 K_S<1 微 alpha、KF-16 Hurst 趋势凝聚、
  跨周期动量泄漏）通过塑形 barrier 从"每 bar 微漂移"累积为"每笔停时 barrier 差"，量级放大 3-5 倍。
  **定律 III（方向 alpha 放大律）**：外部方向信号（哪怕最朴素 EMA20）把停时从
  non-adapted 变为 adapted，打破 Doob 保守律，让塑形容器承载 +0.25 ATR/笔量级 alpha。
  **主命题最终表述**：结构塑形本身不创造 alpha，但作为方向 alpha 的兑现容器，能把每 bar 的
  微漂移放大为每笔 stop-out 的显著收益结构。真正的 alpha 来自方向信号（trend、structure、event），
  塑形是让 alpha 在交易执行系统中"活下来"的必要工程工具。
  **对下游主题的意义**：任何方向 alpha 主题（value area、结构信号、机器学习方向预测）都可以
  接入塑形工具，把"每 bar 微 alpha"放大成"每笔 stop-out 结构化收益"；本主题的 barrier explorer、
  Fourier 精确解、双通道漂移探测器构成完整的"方向 alpha 兑现基础设施"
- 日期：2026-07-14

## 立题日期

**2026-07-05**
