# Freeze Summary · mean-reversion-barrier-duality

> 类型：Archive / 主题冻结摘要
> 冻结日期：2026-08-02
> 归档批次：archive:2026-08-02-mean-reversion-barrier-duality-freeze
> 主题状态：**冻结**——数学内核已沉淀为 theorem，方向性单品种可交易性被怀疑先验否证，不进入真实数据阶段 1。
> 稳定内核：`theorem:structural-shaping-alpha#factor-filtering-and-dgp-boundary`、`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`

---

## 1. 主题解决了什么

补上 `structural-shaping-alpha` 遗漏的镜像：在什么条件下**低盈亏比 / 高胜率（$R<1$）**会成为 barrier 塑形的最优选择。

结论：$R<1$ 成为最优，当且仅当存在**指向均衡的状态依赖均值回归漂移**（OU 的 $-\kappa x$），且满足强回归 / 时间成本 / 下行敏感 / 紧止损四类约束之一。它与趋势侧 $R>1$ 最优互为镜像，不是"放弃盈亏比换胜率"的退而求其次。

---

## 2. 核心数学结论

### 2.1 OU 首达胜率与小 κ 展开（已 ODE 数值验证，误差 <0.001）

$$dX_t=-\kappa X_t\,dt+\sigma dW_t,\quad x_0=-K_T,\quad R=K_T/K_S$$

$$p_{\text{win}}=\frac{K_S}{K_T+K_S}+\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3(K_T+K_S)}+O(\kappa^2)$$

$$E_{\text{gross}}=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3}+O(\kappa^2)>0$$

对任意 $R>0$ 为正，与趋势通道 $E\sim K_S^3R(R-1)$（仅 $R>1$ 正）对偶。

### 2.2 Doob 保守律（KF-1）

$\kappa=0$（鞅）下 $E_{\text{gross}}\equiv0$，扣成本后所有 $R$ 都亏。**纯反持续增量（$H<1/2$ 无回归漂移）不产生 alpha**（KF-4）——必须有真正指向均衡的条件漂移。

### 2.3 $R^\ast$ 随 κ 单调下降（KF-3，数值已证）

固定容器宽度 $L=2$：κ=0.1→R*=4.0（24% 胜率），κ=1.0→R*=0.42（96%），κ≥2→R*≈0.2–0.3（≥99.9%）。交叉点 $\kappa_c\approx0.7\text{–}1.0$。

### 2.4 统一的 DGP 适用边界（沉淀为 theorem）

主题讨论进一步发现：**因子筛选后条件过程是否还是 GBM，是套用任何 barrier 闭式的前提**。该结论已提炼为独立 theorem `theorem:structural-shaping-alpha#factor-filtering-and-dgp-boundary`：

- 因子形式化为条件测度 $\mathbb{P}_A$，条件过程 $dX=b_A(X)dt+\sigma dW$；
- 小漂移下 $E_{\text{gross}}=\frac{2}{\sigma^2}\int b_A(u)g(u)du$（Green 核 $g$）；
- 常数漂移方向已知 $\propto R$；方向未知混合 $\propto R(R-1)$；OU 回复恒正；
- **GBM 闭式成立当且仅当 $b_A(x)\equiv$ 常数**；状态依赖漂移必须换尺度函数积分，fBm 非半鞅扩散框架失效；
- 套闭式前必须经五步识别门，弱识别按鞅处理。

这是主题最重要的方法论遗产，已超越原"$R<1$ 何时最优"问题本身。

---

## 3. 为什么冻结（怀疑先验）

阶段 0 只证明了机制在 OU 模型内自洽，**没有**证明真实可交易市场存在让 $R<1$ 对方向性单品种最优的 regime。三类压力测试揭示合成模型掩盖的问题：

1. **毛利量级被容器归一化放大**：$L=2$ ATR 下 $R<1$ 工作点单笔毛利 0.5–0.8 ATR，可承受单边成本 0.23–0.41 ATR，远高于真实方向性交易（0.05–0.2 ATR）；
2. **所需 κ 对应 91–100% 胜率的"秒回均衡"**：这种 regime 在可交易尺度主要属于做市 / 微结构（方向性交易者进不去），或市场中性配对 / 统计套利（cointegration 已知，已非单品种方向性问题域）；
3. **均衡点估计是杀手**：弱 κ 下入场偏差误判 2× 直接翻负（接飞刀），宽止损 $K_S$ 是 steamroller 风险；真实 Hurst 数据（20 合约）零个 $H<0.5$，可交易周期 κ≈0 甚至偏趋势。

仓库真实数据先验（玉米 ρ₁：1m −0.25、5m −0.12、15m −0.08、1h ≈0；Hurst 全线 >0.5）一致指向：**唯一 κ 够大的尺度（微结构）不可交易，可交易尺度 κ 不足**。

---

## 4. 冻结结论

- **数学定理（长期保留）**：$R^\ast$ 随 κ 单调下降、GBM/OU 对偶、$R(R-1)$ 与 $K_TK_S(2K_T+K_S)$ 的统一 Green 泛函、DGP 识别门——已沉淀进 theorems，独立于本主题存活；
- **可交易策略假设（方向性单品种 $R<1$）**：在原始问题域（单品种 + 净多空 + barrier）内**大概率不成立**，阶段 1 真实数据扫描的预期产出为负，故不启动；
- **真正可能成立的三个形态**（已偏离原问题域，若未来研究需另立主题）：
  - (a) 市场中性配对 / 篮子统计套利（cointegration 保证价差 OU）；
  - (b) 事件驱动过度反应后的短窗回复；
  - (c) 有做市能力的微结构尺度。

---

## 5. 关键发现清单（继承自 research-status）

| KF | 结论 | 状态 |
|---|---|---|
| KF-1 | 鞅过程下 $R<1$ 不存在生存区（Doob OST） | 已证实 |
| KF-2 | OU 小 κ 闭式 $E\propto\kappa K_TK_S(2K_T+K_S)$，任意 R 正 | 已证实（数值 <0.001） |
| KF-3 | $R^\ast(\kappa)$ 单调下降，κ_c≈0.7–1.0 | 数值已证 / 解析单调性待补 |
| KF-4 | 纯反持续增量（无回归漂移）不产生 $R<1$ alpha | 已证实 |
| KF-5 | $R<1$ 严格最优依赖四类约束之一，非无条件 | 边界待定 |
| KF-6 | 高胜率易被"扛单 + 紧止盈"伪造，需固定 T + 随机对照 | 方法论 |

证据源：本批次 `raw-scripts/`（9 个原始脚本）与 `stage0-summary.md`（阶段 0 合成数据摘要，已并入本冻结批次）。

---

## 6. 未闭合项（不阻塞冻结）

- 命题 7.1（$R^\ast$ 单调性）解析证明未闭合，当前为数值定律；
- 有限时间 $T$ 的 Fourier/谱展开解未做（当前 $T=\infty$）；
- 阶段 1 真实数据 κ/H 测量门未执行（因怀疑先验预期负产出而主动放弃）。

若未来在配对 / 事件 / 微结构三个形态重启，应新立主题并复用本冻结的 math-spec 与 theorem，不在本目录继续。

---

## 7. 文件清单

| 文件 | 内容 |
|---|---|
| freeze-summary.md | 本摘要 |
| README.md | 原主题索引（已改冻结状态） |
| research-status.md | KF-1..6 完整证据链 |
| strategy-math-spec.md | OU 首达闭式、小 κ 展开、四条充分条件 |
| experiment-plan.md | 阶段 1–4 实验设计（未执行阶段 1） |
| parameter-selection-spec.md / implementation-notes.md | 占位（未推进） |
| archive-references.md | 与 structural-shaping-freeze 的关系 |
| stage0-summary.md | 阶段 0 合成数据压缩摘要 |
| raw-scripts/ | 阶段 0 原始脚本（9 个：OU 对偶、闭式验证、κ 阈值、多目标、约束 regime、真实化压力测试等） |

稳定数学内核见 `theorem:structural-shaping-alpha#factor-filtering-and-dgp-boundary` 与 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`。
