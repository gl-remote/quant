# Parameter Selection Spec · volume-spike-regime-shift

> r1 阶段本文件只占位。参数选择规则在实验推进到 Stage 2 之后才需要固化；当前参数网格直接写在 [strategy-math-spec.md](strategy-math-spec.md) §2 与 [experiment-plan.md](experiment-plan.md) 中。

---

## 1. 参数分层（r1 初步）

| 层 | 参数 | 取值 | 选择方式 |
|----|------|------|---------|
| 因子 | lookback $N$ | 20（主）；Stage 3 扫 {20, 60, 120} | 固定，r1 不优化 |
| 因子 | 阈值 $z_0$ | {1.5, 2.0, 2.5, 3.0, 4.0, 5.0} | 固定网格，主规格 2.0 |
| 因子 | baseline 带 | $z_\ell=-0.5, z_u=0.5$ | 固定 |
| 响应 | 后窗 $h$ | {1, 3, 6, 12, 20} | 固定网格 |
| 响应 | barrier 容器 | $(K_S,K_T)\in\{(1,1),(1,2),(2,1)\}$ ATR | 固定 |
| 响应 | 方向 | {多, 空, DirRandom} | 固定 |
| 统计 | cluster key | `(contract, session_date)` | 固定 |
| 统计 | bootstrap 次数 | 5000 | 固定 |
| 统计 | FDR 阈值 | BH $q<0.10$（主规格 30 个检验） | 固定 |
| 成本 | ATR 口径 | SMA(TR,14) | 与 structural-shaping gatekeeper 一致 |
| 成本 | 成本模型 | `CONTRACT_SPECS` 真实成本（Stage 5） | 固定，禁用扁平 0.05 ATR |

---

## 2. 选择规则（待 Stage 2 后回填）

- **r1 原则**：不用优化器选参数；所有网格固定，结论靠跨网格 sign 一致性 + 跨品种保留率而非"最优点"。
- **若 r1 出现制度信号**：r2 再考虑用 walk-forward / 嵌套 CV 选阈值与后窗；r1 不做。

---

## 3. 回填触发条件

当出现以下任一情况，本文件从占位升级为正式规格：

1. Stage 2 判决某个度量分量通过 FDR + 保留率，需要固化主规格 $(z_0, h, \text{container})$；
2. Stage 3 发现 $N$ / baseline 带 / ATR 口径需要从扫描值收敛到单点；
3. Stage 5 成本现实化需要固化仓位 / 成本参数。
