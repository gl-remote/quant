# mean-reversion-barrier-duality

> **主题定位**：回答一个对偶问题——**在什么市场结构与约束下，低盈亏比 / 高胜率（$R<1$）会成为 barrier 塑形的最优选择？** 它是已冻结主题 `structural-shaping-alpha`（结论偏向"强段择时 → 非对称塑形 $R>1$ 最优"）的**镜像补全**。
>
> **状态**：立题（2026-08-02）· 阶段 0（核心假设已用 OU 首达 ODE 数值 + 小 κ 闭式验证，尚未上真实数据）。
> **开发分支**：`experiment/low-payoff-high-winrate-optimality`（从 `dev/0.6` @ `3b0a727` 开出）。

---

## 一句话结论

低盈亏比 / 高胜率**不是**"放弃盈亏比换胜率"的退而求其次，而是**均值回归型条件漂移**下的数学最优：当入场点位于相对均衡的偏离处、且条件漂移指向均衡（OU 的 $\nu_{\text{cond}}$ 与位移反向）时，靠均衡一侧放近 barrier（止盈近、止损远，$R=K_T/K_S<1$）能在高频、短持仓、小回撤下最大化风险调整收益；这与趋势 / 持续过程（$H>1/2$、条件漂移顺位移方向）下"止盈远、止损近、$R>1$"互为镜像。

---

## 文档地图

| 文档 | 回答的问题 | 状态 |
|------|-----------|------|
| [README.md](README.md) | 主题索引与阅读顺序（本文件） | 初稿 |
| [research-status.md](research-status.md) | 当前结论、边界、关键发现清单（KF） | 初稿（KF-1..6） |
| [strategy-math-spec.md](strategy-math-spec.md) | 数学契约：OU 首达胜率、小 κ 闭式、$R^\ast$ 单调性、充分条件 | 初稿 |
| [experiment-plan.md](experiment-plan.md) | 怎么验证（OU 校准、真实品种广度扫描、随机/趋势对照、成本现实化） | 初稿 |
| [parameter-selection-spec.md](parameter-selection-spec.md) | 怎么选参数（κ 估计、入场偏离阈值、$R$ 档位、分层判据） | 占位 |
| [implementation-notes.md](implementation-notes.md) | 工程实现（OU 估计器、首达求解器、回测桥接） | 占位 |
| [archive-references.md](archive-references.md) | 与本主题相关的归档批次（继承 / 对偶 / 反例） | 初稿 |

---

## 阅读顺序

1. **先读** [research-status.md](research-status.md)：拿到 KF-1..6 的结论与边界，判断是否值得深入。
2. **再读** [strategy-math-spec.md](strategy-math-spec.md)：OU 过程、入场于偏离处、双 barrier 首达胜率 $p(\kappa,K_S,K_T)$、小 κ 展开、$R^\ast(\kappa)$ 单调性定理、四条 $R<1$ 严格最优充分条件。
3. **要验证**读 [experiment-plan.md](experiment-plan.md)：OU 校准 → 真实品种广度扫描 → 随机/趋势对照 → 成本现实化 → 样本外。
4. 工程化时再补 parameter-selection-spec / implementation-notes。

**与上游定理的接口**：数学骨架复用 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 的 Doob OST、首达记号、通道 A（方向 alpha 放大）；本主题是其**通道 A 在"条件漂移方向 = 指向均衡"情形下的镜像**，并把过程从 GBM（常数漂移）推广到 OU（均值回归漂移）。

---

## 命名引用

```markdown
theme:mean-reversion-barrier-duality
theme:mean-reversion-barrier-duality#strategy-math-spec
```
