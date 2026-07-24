# candidate · f13-volume-spike-20-60

> 类型：Wave 3 · 强度识别因子候选 · **MDH 假设检验**
> 状态：**L4 · 反例归档**（2026-07-17 · 成交量突增无预测力）
> 上游：experiment-plan.md § Wave 3 · shaping-theory §5.5

## Step 0 · 立项登记

| 字段 | 内容 |
|---|---|
| slug | `f13-volume-spike-20-60` |
| 假设陈述 | 短窗成交量 / 长窗成交量突破 → 信息到达 → 未来强漂移（MDH 混合分布假设） |
| 理论出处 | Clark (1973) MDH · Tauchen & Pitts (1983) · 成交量是信息到达速率的 proxy |
| 品种 × 周期 | DCE.c (c2601 / c2603 / c2605) × 1h |
| 成本档 | $c_{\text{side}} = 0.077$ ATR（现价单边） |
| 预期结论 | 成交量突增可能与**当下**波动相关，但对**未来** 20h 漂移强度的预测力存疑 · 若失败则进一步支持"过去价量 → 未来独立" |

## Step 1 · 参数准备（KF-27 反解）

数据源：`project_data/market_data/csv/DCE.c260{1,3,5}.tqsdk.1h.csv` · 共 1252 bar · 评估集 1012 点。

| 参数 | 值 | 来源 |
|---|---|---|
| $\mu_D$ | 0.2018 | 真值序列 $x^{\text{真}}(W=20)$ 的均值 |
| $\sigma_D$ | 0.1664 | 同上 std |
| $K_S^\ast$ | 2.500 ATR | KF-27 反解 |
| $K_T^\ast$ | 10.000 ATR | 同上 |
| $R^\ast$ | 4.000 | K_T/K_S |
| $\tau^\ast$ | 0.600（前 60% 段） | 同上 |
| $x^\ast$ | 0.1301 | $Q_D(0.40)$ · FoldedNormal(μ, σ) |
| $N_{\text{year}}^\ast$ | 39.0 | 裸口径 · 单合约 |
| Sharpe/年 | 2.183 | 目标 |
| **$x_{\min}$** | **0.0496** | `x_min_smallx(0.077, 2.5, 10.0)` |
| **$se_{\text{target}}$** | **0.0489** | $(0.1301 - 0.0496) / 1.645$ |

## Step 2 · Gate 0 · 因果性

因子只引用 $t - 60 .. t - 1$ 的 volume，**结构上因果**。成交量数据与价格同频 · 无时序错位。

## Step 3 · 真值构造

$$
x_t^{\text{真}}(W=20) = \frac{|\overline{r}_{t:t+20}|}{s_{r,\,t:t+20}}
$$

评估点 1012 · 每合约独立滑动。

## Step 4 · Gate 1 · SE 精度

因子定义：$\hat{x}_t = \max(0, V_{20,t} / V_{60,t} - 1)$

$$
\widehat{se}(f) = \sqrt{\frac{1}{n} \sum (\hat{x}_t - x_t^{\text{真}})^2} = 0.2576
$$

$$
\text{ratio} = \widehat{se} / se_{\text{target}} = 0.2576 / 0.0489 = 5.27
$$

**Gate 1**：❌ 失败（se_hat = 0.2576 > 阈值 0.0489）

## Step 4.5 · Gate 1.5 · 分布对齐

四项子判据：

| 检验 | 数值 | 阈值 | 通过 |
|---|---|---|---|
| C1 均值 | mean 差 38.1% (0.1249 vs 0.2018) | < 20% | ❌ |
| C2 尺度 | sd 比 0.949 (0.1579 / 0.1664) | ∈ [0.5, 1.5] | ✅ |
| C3 尾部 | Q90 差 13.5% (0.3578 vs 0.4137) | < 30% | ✅ |
| C4 KS | D = 0.375 | < 0.15 | ❌ |

**Gate 1.5**：❌ 失败 · C1 均值偏差 + C4 KS 统计量超限。

**修正提示**：`reject_dist_error`（均值差 38% + KS D=0.375 · 分布形态不一致 · 不可通过简单 rescale 修复）。

## Step 5 · Gate 2 · 覆盖率

| 参数 | 值 |
|---|---|
| $\theta_{\text{thresh}} = x_{\min} + 1.645 \cdot \widehat{se}$ | $0.0496 + 1.645 \cdot 0.2576 = 0.4736$ |
| **ratio** | **2.017** ≥ 0.70 |

**Gate 2**：✅ 通过（覆盖率超额）

## Step 6 · Gate 3 · 秩相关

$$
\widehat{r} = \text{Spearman}(\hat{x}_t, x_t^{\text{真}}) = -0.126
$$

**Gate 3**：❌ 失败（$-0.126 < 0.40$ · 负相关）

## Step 7 · 终审判决

- **accepted**：False
- **reject_reason**：`Gate1`
- **§7 分级**：**L4**（$\text{se\_ratio} = 5.27 > 3.0$ · Gate 3 $r \le 0.20$ · 归反例登记）

## Step 8 · 反模式复查

- 因子形式简单 · 无泄漏 · 无未来函数
- 成交量突增确实描述了**过去** 20-60h 的信息到达强度，但与**未来** 20h 的漂移强度负相关（r=-0.126）
- 这与 KF-B6 的模式一致：过去强 → 未来略弱（弱均值回归）

## Step 9 · 方向偏向审计

未跑（L4 直接归档 · 无需继续判方向）。

## Step 10 · 下游路径

不适用（L4）。

## 结论

- **MDH 在玉米 1h 上对未来强度无预测力**：成交量突增描述的是过去/当下的信息到达强度，与未来 20h 的 $|\nu|/\sigma$ 呈弱负相关（r=-0.126）。
- **强化 KF-B6 结论**：这是第 7 个跨类型因子（时序 / 长程记忆 / 波动率 / 横截面 / 成交量）全部失败，进一步支持"过去价量统计与未来 $|\nu|/\sigma$ 独立"。
- **弱均值回归特征**：7 个因子中有 6 个 r < 0，方向高度一致，提示"过去活跃 → 未来平静"的弱均值回归模式，但强度远不足以交易使用。
- **归档反例登记**：本因子进入 `rejected_factors.md`。

## 数据产出

- `docs/workbench/strength-factor-screening/outputs/f13-volume-spike-20-60.json` · 完整 CandidateReport
- driver：`docs/workbench/strength-factor-screening/scripts/f13_volume_spike.py`
- 共享工具：`docs/workbench/strength-factor-screening/scripts/_driver.py`

## 相关文档

- shaping-theory §5.5 · event-driven 因子清单
- screening-methodology §七 · 分级因子管理（本因子归 L4）
- kf:strength-factor-screening#KF-B6 · 过去价量统计与未来独立
