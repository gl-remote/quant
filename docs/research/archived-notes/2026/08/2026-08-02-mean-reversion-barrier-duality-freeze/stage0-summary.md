# 阶段 0 摘要 · mean-reversion-barrier-duality

> 类型：Archive / 策略实验摘要（阶段 0 · 合成数据）
> 状态：已完成（阶段 0，数学框架自洽；真实数据未验证）
> 归档日期：2026-08-02
> 主题：theme:mean-reversion-barrier-duality

---

## 1. 核心问题

`structural-shaping-alpha` 的趋势通道 B 给出 $E\sim K_S^3R(R-1)$，结论偏向"高盈亏比 / 低胜率（$R>1$）最优"。本阶段补上被遗漏的另一半：

> 在什么市场结构与约束下，低盈亏比 / 高胜率（$R=K_T/K_S<1$）会成为 barrier 塑形的最优选择？

## 2. 方法与设定

- 以 Ornstein–Uhlenbeck 过程 $dX_t=-\kappa X_t\,dt+\sigma\,dW_t$ 为均值回归原型，均衡 0；
- **入场于偏离处** $x_0=-K_T$（价格低于均衡），止盈于 0（距离 $K_T$，指向均衡）、止损于 $-(K_T+K_S)$（距离 $K_S$，背离均衡），$R=K_T/K_S<1$；
- 用三对角 ODE 数值求解首达胜率 $p(x)$ 与平均首达时间 $m(x)$，Monte Carlo 交叉验证；
- 推导小 $\kappa$ 闭式展开、$R^\ast(\kappa)$ 单调性、Péclet 数判据；
- 做成本盈亏平衡、regime 破裂、均衡估计误差三类现实化压力测试。

## 3. 关键结果

1. **Doob 保守律（鞅基线）**：$\kappa=0$ 时 $E_{\text{gross}}\equiv0$、$E_{\text{net}}=-2c<0$，对任意 $R$ 成立——$R<1$ 必须以真实均值回归漂移为前提（KF-1）。
2. **OU 首达胜率闭式**：$p(x)=\int_{-L}^{x}e^{\kappa u^2/\sigma^2}du/\int_{-L}^{0}e^{\kappa u^2/\sigma^2}du$，$L=K_T+K_S$。
3. **小 κ 展开**（ODE 数值吻合，κ=0.1 误差 <0.001）：
   $p_{\text{win}}=\frac{K_S}{L}+\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3L}+O(\kappa^2)$，
   $E_{\text{gross}}=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3}+O(\kappa^2)$。
   正期望对任意 $R>0$ 成立（不含趋势通道的 $R(R-1)$ 符号因子），与趋势侧对偶（KF-2）。
4. **$R^\ast$ 随 κ 单调下降**（固定 $L=2,\sigma=1$，年化 Sharpe 口径）：κ=0.1→$R^\ast$=4.0（24% 胜率）、κ=0.5→1.1（73%）、κ=1.0→0.42（96%）、κ≥2→0.2–0.3（≥99.9%）；交叉点 κ_c≈0.7–1.0（KF-3，解析单调性待补）。
5. **Péclet 数判据**：$\mathrm{Pe}=\kappa K_S^2/\sigma^2$ 比较回归时间 $1/\kappa$ 与噪声扩散时间 $K_S^2/\sigma^2$。Pe≫1 时亏损概率指数衰减 $1-p\sim\frac{L}{K_T}\exp(-\kappa K_S(2K_T+K_S)/\sigma^2)$，即"噪声还没摸到远止损就被拉回均衡"。
6. **纯反持续不够**：AR(1) 增量 ρ=−0.3（无回归漂移）下 $E\approx0$；必须有指向均衡的 $-\kappa x$ 漂移，区分了"反持续（H<1/2）"与"均值回归漂移"（KF-4）。
7. **$R<1$ 严格最优依赖四类约束之一**：强回归、按时间计持有成本、下行风险敏感、结构性紧止损（KF-5）。弱 κ + 单笔 Sharpe + 仅每笔固定成本下最优在 $R\approx1.1\text{–}1.7$，不是 $R<1$。
8. **高胜率防伪**：紧止盈 + 不设时间止损可伪造胜率（KF-6）。

## 4. 怀疑先验（关键边界）

阶段 0 只证明机制在 OU 模型内自洽，**未证明真实市场存在可交易 regime**。结合仓库已有真实数据（KF-16 Hurst 全线 >0.5、零合约 H<0.5；玉米 1h ρ₁≈−0.012、仅 1m/5m 有 bid-ask bounce 级负相关）：

- $R<1$ 所需 κ（Pe≳2）只在不可交易的微结构尺度出现；可交易尺度（≥15m）κ≈0 甚至偏趋势；
- 模型在 $L=2$ 容器下的单笔毛利（0.5–0.8 ATR）与可承受成本（0.23–0.41 ATR）对方向性交易高得不真实；
- 均衡点估计误差在弱 κ 下可直接翻负（接飞刀），宽止损带来 steamroller 回撤。

**先验偏向"方向性单品种 $R<1$ 在真实成本后不可交易"**，阶段 1 是证伪门槛而非确认练习。真正可能成立的形态收窄到：市场中性配对/篮子（cointegration 已知）、事件驱动过度反应短窗、有做市能力的微结构尺度。

## 5. 复现资产

原始脚本位于 `raw-scripts/`：

| 脚本 | 用途 |
|---|---|
| `explore_ou_duality.py` | OU vs BM、多空混合、R 扫描初验 |
| `verify_ou_analytic.py` | ODE 数值 vs 小 κ 闭式（三对角求解） |
| `r_optimality_study.py` | 固定宽度 L 下 R 扫描、单笔/年化 Sharpe |
| `r_optimality_regimes.py` | 固定止损 / 时间成本 / fBm 代理三大约束 |
| `objectives_study.py` | 多目标（Sharpe / Kelly / 下行惩罚） |
| `kappa_threshold_study.py` | $R^\ast(\kappa)$ 交叉点定位 |
| `regime_realism_check.py` | 成本盈亏平衡 + regime 破裂压力测试 |
| `equilibrium_error_check.py` | 均衡点估计误差 + steamroller 回撤分布 |
| `timescale_competition.py` | Péclet 数与大 κ 指数渐近验证 |

依赖：`numpy`、`scipy`（`solve_banded`）；无真实数据加载，全部合成 OU/BM。

## 6. 下一步

阶段 1：先做廉价 κ/H 测量门（不跑完整 barrier 回测），在多品种多周期估计价格偏离水平的 AR(1) κ 与 Hurst，画 Pe 上分位；可交易周期上分位成本后仍低于临界则判定方向性 null，否则进入回测。详见 theme:mean-reversion-barrier-duality#experiment-plan。
