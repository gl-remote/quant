# time-barrier-selection · 主题冻结归档（2026-07-31）

> **关系类型**：主题冻结归档（Stage 2/3/4 整批完成）
>
> **冻结原因**：主题核心研究问题——"在塑形理论 $(K_S, K_T, T)$ 容器中，时间维 $T$ 是否为独立决策变量、最优 $T$ 取何值"——经 Stage 2（跨周期）/ Stage 3（跨品种）/ Stage 4（KF-27 喂入）三轮实证后已形成闭环。结论指向：$T$ 不是主要 alpha 来源，最优塑形参数对周期/品种鲁棒（$K_S=4, RR=3, \tau=0.1$ 通吃），真正的 alpha 来源在方向识别器（通道 A），不在时间维本身。主题完成使命，整批冻结。
>
> **与上次归档的关系**：本批次是主题**第二次**归档——第一次是 `archive:2026-07-31-time-barrier-selection-redirection`（Stage 1 方向修正冻结）；本次是主题主线完成后的最终冻结，两份归档批次互相独立、均永久保留。

## 1. 主题一句话结论（冻结版）

```text
time-barrier-selection 主题三轮实证结论：
(1) 市场强度 |s| = |ν|/σ 在 c/m/rb × 5m/15m/1h 上 μ_D 稳定在 0.04–0.07 量级，
    KF-14 跨周期跨品种量级一致成立（最干净证据）；
(2) ρ_1 收敛到 0（短周期 microstructure mean reversion，长周期 i.i.d.），
    W=80/W=20 ≈ 0.5（α≈0.5，Doob martingale 统计本底）；
(3) 喂入 KF-27 闭式优化器后，最优参数跨品种跨周期高度稳定：
    (K_S*=4.0, K_T*=12.0, RR*=3.0, τ*=0.10)，E_net 全正 1.3–1.8 ATR/笔；
(4) Sharpe/年由 year_bars 主导：5m 1.7–1.9 > 15m 0.8–1.4 > 1h 0.6–0.8；
(5) 方向概率 p ≥ 0.60 是实盘拐点（K_S* 从 3.5 降到 2.5，进入实盘止损区间）。
结论：时间维 T 作为独立决策变量的价值有限，最优塑形参数"一套通吃"，
真正的 alpha 在方向识别器（通道 A）而非时间维本身。
```

## 2. 核心研究问题与最终回答

| 研究问题 | 最终回答 |
|----------|---------|
| 持仓周期 $T$ 是否存在"甜点"使塑形 alpha 最大？| ❌ 不存在。μ_D 跨周期量级一致，参数一套通吃 |
| 5m 上 $|s|(T)$ 是否随窗口长度呈特定形态？| 是幂律衰减，但那是统计收敛（α≈0.5）非市场结构（Stage 1 归档原因）|
| KF-14 跨周期不变性在 $|s|$ 分布层是否成立？| ✅ 量级一致（0.04–0.07），非严格相等；跨品种也成立（KF-5）|
| mean($|s|$) 随周期递增是否品种无关？| ❌ 品种相关：c 递增（microstructure 压信号）、m/rb 平坦（KF-6）|
| 跨周期跨品种最优 $(K_S^*, K_T^*, \tau^*)$ 是否稳定？| ✅ 高度稳定：K_S=4, K_T=12, RR=3, τ=0.10（KF-8）|
| 方向概率 p 多少才能让参数进入实盘区间？| p ≥ 0.60（K_S* 从 3.5→2.5 ATR）；KF-19 EMA aligned 仅 p≈0.55 不足 |

## 3. 关键发现清单（最终 KF）

### KF-1 · 玉米 mean(|s|) 随周期递增（Stage 2）
- 类型：市场结构；证据：cross-period-report §3.1
- 1m 0.107 → 1h 0.197（1.84x）；W=80/W=20 ≈ 0.5 是统计收敛本底

### KF-2 · cluster bootstrap 按周（Stage 1 方法论遗产）
- 类型：方法论；证据：archive:2026-07-31-time-barrier-selection-redirection
- 5m/1m 大窗口必须按周 cluster，推广到所有短周期主题

### KF-3 · rolling 窗口归属简化为末 bar cluster（Stage 1 方法论遗产）
- 类型：方法论；28x 加速，对 CI 估计无显著影响

### KF-4 · ρ_1 跨周期收敛到 0（Stage 2 + Stage 3 跨品种强化）
- 类型：市场结构；证据：cross-period §3.4 + cross-symbol §3.4
- 1m -0.25 → 1h -0.01（c）；c 短周期最强（-0.12），m/rb 弱（-0.03 ~ -0.05）

### KF-5 · FoldedNormal μ_D 跨周期跨品种量级一致（Stage 2 + Stage 3 强化）
- 类型：策略行为；证据：cross-symbol §3.3
- 跨周期 0.05–0.13（c）、跨品种 0.04–0.07（c/m/rb W=80），KF-14 分布层最干净证据

### KF-6 · mean(|s|) 递增斜率品种相关（Stage 3）
- 类型：市场结构；证据：cross-symbol §3.1
- c 5m→1h ratio=1.38、m=1.01、rb=0.93；农产品短周期被 microstructure 压信号

### KF-7 · W=80/W=20 ≈ 0.5（α≈0.5）三品种成立（Stage 3）
- 类型：方法论；证据：cross-symbol §3.2
- W=80 已稀释 mean reversion，三品种比值 0.48–0.51；Doob 统计本底

### KF-8 · KF-27 最优参数跨品种跨周期高度稳定（Stage 4）
- 类型：策略行为；证据：stage4-report §3
- $(K_S^*=4, K_T^*=12, RR^*=3, \tau^*=0.10)$ 一致顶到网格上界；E_net 1.3–1.8 ATR/笔
- Sharpe/年：5m 1.7–1.9 > 15m 0.8–1.4 > 1h 0.6–0.8（year_bars 主导）

### KF-9 · 方向概率 p=0.60 是实盘参数拐点（Stage 4b）
- 类型：策略行为；证据：when-barrier-shaping-yields-alpha.md §10.5
- p=0.55（KF-19 EMA 量级）K_S*=3.5 仍偏宽；p≥0.60 → K_S*=2.5 进入实盘区间
- 命题 10.6 p-混合闭式 + 实证锚点表已补入 theorem §10.5

## 4. 归档文件清单

### 4.1 raw-workbench/（压缩结论已在本 README §1–3）

- `cross-period-plan.md` — Stage 2 跨周期实验计划
- `cross-period-report.md` — Stage 2 主报告（玉米 1m/5m/15m/1h）
- `cross-symbol-report.md` — Stage 3 主报告（c/m/rb × 5m/15m/1h）
- `stage4-report.md` — Stage 4 主报告（KF-27 参数喂入）

### 4.2 raw-scripts/

- `cross_period_strength.py` — Stage 2 跨周期扫描（向量化 cumsum + cluster bootstrap + FoldedNormal MLE）
- `cross_symbol_strength.py` — Stage 3 跨品种扫描（支持 DCE/SHFE 前缀）
- `stage4_kf27_sweep.py` — Stage 4 KF-27 喂入脚本（调用归档的 kf26_parameter_optimizer.py）
- `stage4b_direction_p_sensitivity.py` — Stage 4b 方向概率 p 敏感性（补 theorem §10.5 的数值基础）
- `atr_scaling.py` — ATR 缩放比 R 探针（Hurst 指数直接估计，验证 ρ_1 物理图像）

### 4.3 raw-outputs/

- `cross_period_summary.{csv,json}` + `cross_period_samples.csv`（39374 窗口，Stage 2）
- `cross_symbol_summary.{csv,json}` + `cross_symbol_samples.csv`（23587 窗口，Stage 3）
- `stage4_kf27_sweep.csv`（9 组最优解，Stage 4）

### 4.4 同步更新的 theorem 文件（不在本批次内，保留在活跃目录）

- `docs/research/theorems/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md` §10.5 新增：方向概率 p-混合闭式（命题 10.6/10.7/10.8）+ 玉米 1h p-敏感性实证锚点表
- 这是本次主题对上游塑形理论的反向贡献（KF-9 已沉淀到 theorem）

## 5. 方法论遗产（跨主题可复用）

1. **跨周期扫描范式**：固定 W=20/80 bar 窗口、stride=4、ddof=1、cluster bootstrap 按日/周分级——已在 `cross_period_strength.py` 实现为可复用骨架
2. **|s| 分布的"噪声 + 信号"分解**：mean(|s|) 含 ~50% 采样噪声（W=80/W=20≈0.5），μ_D（FoldedNormal 位移）是更干净的信号——后续主题应优先读 μ_D 而非 raw mean
3. **方向概率 p 作为识别器 KPI**：p=0.60 是实盘拐点（比通道 B 的 se≤0.05 更直观的工程 KPI）；命题 10.6 p-混合公式可直接用于任何 DirRandom baseline 的推广
4. **ATR 缩放比 R 探针**：一行代码即可估计 Hurst 指数，比 ρ_1 更直观反映波动率跨周期缩放

## 6. 主题结论对上游 / 下游的影响

### 对 `structural-shaping-alpha`（上游）
- ✅ KF-14 跨周期不变性在 $|s|$ 分布层被直接证实（KF-5），比原 P_win/time_exit 证据更干净
- ✅ KF-27 最优参数在弱漂移（μ_D≈0.05 vs 原校准 0.198）下仍稳定 E_net>0，通道 B alpha 鲁棒
- ⚠️ KF-27 玉米 1h 原校准 μ_D=0.198 可能高估 3x（Stage 2/3 实测 0.07）；旧解 K_S*=3 vs 新解 K_S*=4，建议 theorem §10.4 加注
- ✅ §10.5 p-混合推广已沉淀为 theorem 新增节

### 对下游方向识别器主题（通道 A）
- 明确了工程 KPI：方向命中率 p≥0.60 才能让止损进入实盘区间
- KF-19 EMA aligned 信号 p≈0.55 不足，需要更强信号或跨周期确认
- 这是未来工作的真正方向——time-barrier-selection 主题本身不再继续

## 7. 未解决 / 移交

- **扩网格验证边界解**：Stage 4 K_S*=4 顶到网格上界（原网格 K_S≤5, RR≤3）；扩网格 K_S≤8, RR≤5 后 Stage 4b 显示 RR* 仍顶到 5，真实最优可能 RR>5，但 RR>5 实盘不实用
- **5m 真实成本模型**：Stage 4 显示 5m Sharpe 最高，但 c_side=0.077 是 1h 标定，5m 高频交易滑点/冲击成本未建模，实盘 5m Sharpe 可能高估
- **更多品种 / 1d 周期**：三品种已够稳，但 1d 是否出现正自相关（动量）未验证，移交给未来主题
- **方向识别器研究**：这是真正的 alpha 来源，本主题不再覆盖，作为新主题立题（建议 slug: `direction-signal-identifier`）

## 8. 复现信息

- 所有脚本：`raw-scripts/*.py`，依赖 `numpy, pandas, scipy`（项目 uv 环境已含）
- Stage 2：`uv run python raw-scripts/cross_period_strength.py --n-boot 1000`（6:25）
- Stage 3：`uv run python raw-scripts/cross_symbol_strength.py --n-boot 1000`（~4 min）
- Stage 4：`uv run python raw-scripts/stage4_kf27_sweep.py`（<1s）
- Stage 4b：`uv run python raw-scripts/stage4b_direction_p_sensitivity.py`（<1 min）
- ATR 探针：`uv run python raw-scripts/atr_scaling.py`（<1s）

## 9. 命名引用

`archive:2026-07-31-time-barrier-selection-freeze` — 本批次（主题最终冻结）
`archive:2026-07-31-time-barrier-selection-redirection` — Stage 1 方向修正归档
`theme:time-barrier-selection` — 主题目录（已标记冻结）
`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` §10.5 — p-混合公式（本次新增）
`kf:time-barrier-selection#KF-1..9` — 主题所有 KF
