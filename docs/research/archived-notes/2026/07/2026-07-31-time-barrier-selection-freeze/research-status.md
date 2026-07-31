# time-barrier-selection · Research Status

> 状态：🧊 **已冻结**（2026-07-31，主题使命完成）· Stage 1 已归档 · Stage 2/3/4 完成并冻结
> 最近更新：2026-07-31
> 冻结批次：`archive:2026-07-31-time-barrier-selection-freeze`（主题最终归档）
> 方向修正批次：`archive:2026-07-31-time-barrier-selection-redirection`（Stage 1 冻结）
> theorem 沉淀：`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` §10.5（p-混合闭式）

## 1. 当前一句话结论

```text
Stage 4 KF-27 参数喂入完成。c/m/rb × 5m/15m/1h 共 9 组 W=80 (μ_D, σ_D) 喂入 KF-27 闭式优化器:
(1) 最优参数高度稳定——(K_S*=4.0, K_T*=12.0, RR*=3.0, τ*=0.10) 跨品种跨周期一致,
    顶到网格上界, 说明弱漂移(μ_D≈0.05)下优化器想要更大 RR / 更松 τ;
(2) E_net 全正(1.3–1.8 ATR/笔), 比 KF-27 基线 (μ_D=0.198) 的 +1.56 略低但未崩溃——
    通道 B alpha 在弱漂移下依然成立;
(3) Sharpe/年 5m 最高(1.7–1.9)、1h 最低(0.6–0.8)——由 year_bars 主导, 周期越短笔数越多;
(4) 与 KF-6 (短周期 mean-reversion 压信号) 不矛盾: 单笔 E_net 5m 略低, 但 6x 笔数优势盖过.
```

## 2. 核心假设

**H1（存在性）**：存在有限的持仓周期 $T \in [T_\min, T_\max]$（以 bar 为单位），使得

$$
\mathbb{E}[E_{\text{net}}(T)] = \mathbb{E}[X_\tau] - 2c > 0
$$

在 ATR 归一化的双 barrier 容器 $(K_S, K_T)$ 下成立。

**H2（尺度定位）**：由 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 的 $T^\ast = \max(K_S, K_T)^2 / \sigma^2$（定义 4.4），$T^\ast$ 与 $\sigma^2$ 反相关；因此在短周期下 $T^\ast$ 应按 bar 数换算，判定合理的持仓 bar 数区间。

**H3（品种依赖）**：$T^\ast$ 的品种间可比性需要按 ATR 归一化后重新验证；玉米作为低波动农产品，其 $|s|$ 分布跨周期形态（递增斜率、$\rho_1$ 强度）与高波动工业品（rb）有显著差异。

**H4（跨周期强度结构）**（Stage 2 已证实）：$|s| = |\nu|/\sigma$ 跨周期量级一致但非严格相等——mean($|s|$) 随周期递增、$\rho_1$ 收敛到 0。

**H5（跨品种量级一致）**（Stage 3 新增）：$\mu_D$ 在三品种（c/m/rb）× 三周期（5m/15m/1h）上都落在 0.04–0.07 量级——KF-14 不变性在分布参数层跨品种成立。mean($|s|$) 递增斜率品种相关，$\sigma_D$ 跨品种单调排序（c < m < rb）。

> H4/H5 都是事实型假设。H1/H2/H3 仍待 Stage 4 引入塑形后验证。

## 3. 关键发现清单

### KF-1 · 玉米 mean($|s|$) 随周期变长单调递增（Stage 2）
- 类型：市场结构
- 状态：已证实（3 合约 × 4 周期，W=20/80）
- 证据：`archive:2026-07-31-time-barrier-selection-freeze#raw-workbench/cross-period-report` §3.1
- 影响：W=20 上 1m → 1h 单调递增 0.107 → 0.197（1.84x）；同一周期内 W=80/W=20 ≈ 0.5（统计收敛 $\alpha \approx 0.5$）
- 日期：2026-07-31

### KF-2 · cluster bootstrap 必须按周（方法论遗产，Stage 1 保留）
- 类型：方法论
- 状态：已证实（Stage 1 归档保留）
- 证据：`archive:2026-07-31-time-barrier-selection-redirection#raw-docs/experiment-plan` §2.3
- 影响：5m/1m 期货每日 bar 数有限，大窗口必须按周 cluster；该结论推广到所有短周期主题。Stage 2/3 沿用：5m 按日、15m/1h 按周
- 日期：2026-07-31

### KF-3 · rolling 窗口归属可简化为"末 bar 所在周"（方法论遗产，Stage 1 保留）
- 类型：方法论
- 状态：已证实（Stage 1 归档保留）
- 证据：`archive:2026-07-31-time-barrier-selection-redirection/raw-scripts/market_strength_scan.py`（45s → 1.6s，28x 加速）
- 影响：跨多周的大 W 窗口用末 bar 所在 cluster 足够稳健
- 日期：2026-07-31

### KF-4 · $\rho_1$ 跨周期收敛到 0（Stage 2 + Stage 3 跨品种强化）
- 类型：市场结构
- 状态：已证实（3 合约 × 4 周期；Stage 3 在三品种上也证实）
- 证据：`archive:2026-07-31-time-barrier-selection-freeze#raw-workbench/cross-period-report` §3.4 + `#raw-workbench/cross-symbol-report` §3.4
- 影响：1m -0.247 → 1h -0.012（c），跨品种 c 强 / m/rb 弱（-0.03 ~ -0.05 @5m）；microstructure mean reversion 短周期显著、长周期 i.i.d.
- 日期：2026-07-31

### KF-5 · FoldedNormal $\mu_D$ 跨周期与 KF-27 同量级（Stage 2 + Stage 3 强化）
- 类型：策略行为 + 方法论
- 状态：已证实（Stage 2 跨周期 + Stage 3 跨品种双重强化）
- 证据：`archive:2026-07-31-time-barrier-selection-freeze#raw-workbench/cross-symbol-report` §3.3
- 影响：跨周期 0.05–0.13、跨品种 0.04–0.07，都与 KF-27 玉米 1h `mu_D=0.198` 同一数量级；**KF-14 量级一致性在分布参数层跨品种成立**，这是迄今最干净的证据
- 日期：2026-07-31

### KF-6 · mean($|s|$) 跨周期递增斜率品种相关（Stage 3）
- 类型：市场结构
- 状态：已证实（c/m/rb × 3 周期）
- 证据：`archive:2026-07-31-time-barrier-selection-freeze#raw-workbench/cross-symbol-report` §3.1
- 影响：c 5m→1h ratio=1.38（递增）、m ratio=1.01（平坦）、rb ratio=0.93（略降）；农产品短周期 microstructure 压信号（|s| 偏低），工业品/油粕短周期本就足
- 日期：2026-07-31

### KF-7 · W=80/W=20 ≈ 0.5（α≈0.5）三品种都成立（Stage 3）
- 类型：方法论
- 状态：已证实（c/m/rb × 3 周期）
- 证据：`archive:2026-07-31-time-barrier-selection-freeze#raw-workbench/cross-symbol-report` §3.2
- 影响：W=80 已经把 mean reversion 自相关稀释干净，三品种比值都在 0.48–0.51；Doob martingale 统计本底
- 日期：2026-07-31

### KF-8 · KF-27 最优参数跨品种跨周期高度稳定（Stage 4）
- 类型：策略行为
- 状态：已证实（c/m/rb × 5m/15m/1h 共 9 组 W=80 分布喂入）
- 证据：`archive:2026-07-31-time-barrier-selection-freeze#raw-workbench/stage4-report` §3 + `#raw-outputs/stage4_kf27_sweep.csv`
- 影响：$(K_S^\ast=4.0, K_T^\ast=12.0, RR^\ast=3.0, \tau^\ast=0.10)$ 跨品种跨周期一致，E_net 全正 1.3–1.8 ATR/笔；Sharpe/年 5m 最高 1.7–1.9、1h 最低 0.6–0.8，由 year_bars 主导
- 日期：2026-07-31

### KF-9 · 方向概率 p=0.60 是实盘参数拐点（Stage 4b，已沉淀到 theorem §10.5）
- 类型：策略行为
- 状态：已证实（数值积分闭式解，玉米 1h μ_D=0.072）
- 证据：`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` §10.5（命题 10.6 p-混合闭式 + 实证锚点表）
- 影响：p=0.55（KF-19 EMA 量级）K_S*=3.5 仍偏宽；p≥0.60 → K_S*=2.5 进入实盘止损区间；**p=0.60 可作为方向识别器工程 KPI**（类比通道 B 的 se≤0.05）
- 日期：2026-07-31

## 4. 主题状态

🧊 **主题已冻结（2026-07-31）**——核心问题闭环，后续工作移交方向识别器新主题。

**已完成**：
- Stage 1（已归档）：`archive:2026-07-31-time-barrier-selection-redirection`（5m $|s|(T)$ 形态扫描，方向修正）
- Stage 2（跨周期，玉米 c，已冻结）：KF-1/4/5
- Stage 3（跨品种，c/m/rb，已冻结）：KF-5/6/7
- Stage 4（KF-27 参数喂入，已冻结）：KF-8/9
- 所有 workbench 产物归档于 `archive:2026-07-31-time-barrier-selection-freeze`

**沉淀到 theorem 的成果**：
- `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` §10.5 新增 p-混合闭式（命题 10.6/10.7/10.8），将通道 B 推广到任意方向命中率 p

**移交 / 未做**：
- 方向信号识别器（达到 p≥0.60 工程 KPI）→ 建议新主题 `direction-signal-identifier`
- KF-27 玉米 1h 校准 μ_D=0.198 可能高估 3x 的复核（theorem §10.4 加注）
- 5m 真实滑点 / 冲击成本模型验证

## 5. 边界与已知约束

- 本主题**不研究方向 alpha**（通道 A）——已沉淀 p-混合公式到 theorem §10.5，工程实现留给下游主题；
- 本主题**不研究仓位管理**——仓位管理由 `theorem:structural-shaping-alpha#piecewise-static-kelly-vs-fixed-risk` 覆盖；
- 所有结论基于 2026-07-31 的 3 品种 × 3 周期 × 3 合约数据，合约期重叠（26xx 系列），非全历史稳健性；
- Stage 4 最优参数顶到搜索网格上界（K_S≤5, RR≤3 原网格），Stage 4b 扩网格（K_S≤6, RR≤5）后 RR* 仍顶 5，真实最优可能更大但已不实用。
