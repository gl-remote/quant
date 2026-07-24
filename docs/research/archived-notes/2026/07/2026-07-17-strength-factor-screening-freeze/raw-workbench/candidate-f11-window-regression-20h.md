# candidate · f11-window-regression-20h

> 类型：Wave 1 · 强度识别因子候选 · **对照证伪**
> 状态：**L4 · 反例归档**（2026-07-16 · 实测符合理论预期）
> 上游：experiment-plan.md § Wave 1 · shaping-theory §2.23.5.5

## Step 0 · 立项登记

| 字段 | 内容 |
|---|---|
| slug | `f11-window-regression-20h` |
| 假设陈述 | 20h 窗口对数收益 (mean/std) 直接估计 $|\nu|/\sigma$——把因子当作"真值构造函数"的完美对齐版 |
| 理论出处 | shaping-theory §2.23.5.5 · KF-15 窗口回归 se ≈ $1/\sqrt{N}$ = 0.224 · 远超 se_target |
| 品种 × 周期 | DCE.c (c2601 / c2603 / c2605) × 1h |
| 成本档 | $c_{\text{side}} = 0.077$ ATR（现价单边） |
| 预期结论 | Gate 1 SE 必挂（se_hat ≈ 0.22 · 4.5× 超阈）· 归 L4 反例 · **本次跑一次为归档 shaping-theory §2.23.5.5 的证伪** |

## Step 1 · 参数准备（KF-27 反解）

数据源：`project_data/market_data/csv/DCE.c260{1,3,5}.tqsdk.1h.csv` · 共 1252 bar · 剔除首尾 W=20 后评估集 1192 点。

| 参数 | 值 | 来源 |
|---|---|---|
| $\mu_D$ | 0.1979 | 真值序列 $x^{\text{真}}(W=20)$ 的均值 |
| $\sigma_D$ | 0.1598 | 同上 std |
| $K_S^\ast$ | 2.500 ATR | KF-27 反解（`research.optimizer`） |
| $K_T^\ast$ | 10.000 ATR | 同上 |
| $R^\ast$ | 4.000 | K_T/K_S |
| $\tau^\ast$ | 0.600（前 60% 段） | 同上 |
| $x^\ast$ | 0.1301 | $Q_D(0.40)$ · FoldedNormal(μ, σ) |
| $N_{\text{year}}^\ast$ | 39.0 | 裸口径 · 单合约 |
| Sharpe/年 | 2.183 | 目标 |
| **$x_{\min}$** | **0.0496** | `x_min_smallx(0.077, 2.5, 10.0)` |
| **$se_{\text{target}}$** | **0.0489** | $(0.1301 - 0.0496) / 1.645$ |

注：本次 KF-27 输出 $K_S^\ast = 2.5, R^\ast = 4$，与主题 methodology §四示例的 $(3.0, 3.0)$ 不同——因为**实测数据的 $\sigma_D = 0.16$ 远大于示例的 0.108**（3 合约合并后波动率更宽厚尾），KF-27 因此偏好更窄止损 + 更高盈亏比。

## Step 2 · Gate 0 · 因果性

因子只引用 $t - W .. t - 1$ 的 log_ret，**结构上因果**。未跑截断法验证（因子形式简单且确定性）。

## Step 3 · 真值构造

$$
x_t^{\text{真}}(W=20) = \frac{|\overline{r}_{t:t+20}|}{s_{r,\,t:t+20}}
$$

评估点 1192 · 每合约独立滑动。**注意：因子 $\hat{x}$ 用 $t-20..t$ 窗口、真值 $x^{\text{真}}$ 用 $t..t+20$ 窗口——两个窗口在时间上完全不重叠**，这正是"直接窗口回归为什么天然做不好识别器"的根本原因。

## Step 4 · Gate 1 · SE 精度

$$
\widehat{se}(f) = \sqrt{\frac{1}{n} \sum (\hat{x}_t - x_t^{\text{真}})^2} = 0.2394
$$

$$
\text{ratio} = \widehat{se} / se_{\text{target}} = 0.2394 / 0.0489 = 4.89
$$

**Gate 1**：❌ 失败（se_hat = 0.2394 > 阈值 0.0489）

与 shaping-theory §2.23.5.5 预测 $se \approx 1/\sqrt{20} = 0.224$ 高度吻合（差距 6.9%）——**理论完全预测实测**。

## Step 4.5 · Gate 1.5 · 分布对齐

四项子判据：

| 检验 | 数值 | 阈值 | 通过 |
|---|---|---|---|
| C1 均值 | mean 差 0.20% (0.1985 vs 0.1981) | < 20% | ✅ |
| C2 尺度 | sd 比 0.986 (0.1600 / 0.1623) | ∈ [0.5, 1.5] | ✅ |
| C3 尾部 | Q90 差 1.4% (0.3946 vs 0.4002) | < 30% | ✅ |
| C4 KS | 未失败 | < 0.15 | ✅ |

**Gate 1.5**：✅ 通过 · 因子分布与真值分布完美对齐。

**为什么完美对齐但精度极差**：窗口回归输出的**边缘分布**与真值代理确实是同分布（同一构造方式），但**逐点相关性**因时间错位而消失。Gate 1.5 只测边缘分布对齐，Gate 3 才测逐点相关——两者独立。

## Step 5 · Gate 2 · 覆盖率

| 参数 | 值 |
|---|---|
| $\theta_{\text{thresh}} = x_{\min} + 1.645 \cdot \widehat{se}$ | $0.0496 + 1.645 \cdot 0.2394 = 0.4436$ |
| Fire 数 | (未打印，但 ratio 2.797 意味有 109 fire) |
| $N_{\text{year}}$ | ~109 |
| $N_{\text{year}}^\ast$ | 39 |
| **ratio** | **2.797** ≥ 0.70 |

**Gate 2**：✅ 通过（覆盖率超额 · 因为阈值反解用了大 se）

注：Gate 2 数值上"过"是因为 se_hat 高、阈值反而低于 $x^\ast$——**这是伪通过**。若用 se_target 反解阈值（$0.0496 + 1.645 \cdot 0.0489 = 0.1301 = x^\ast$），fire 数量会大幅下降。这也是为什么 §四 Step 5 的 fire 阈值明确用 `x_min + 1.645 · se_hat` 而非 `x_min + 1.645 · se_target`——**故意让 Gate 2 与实测精度耦合**，识别器越粗糙、fire 越多、但每次触发的真实强度越模糊。

## Step 6 · Gate 3 · 秩相关

$$
\widehat{r} = \text{Spearman}(\hat{x}_t, x_t^{\text{真}}) = -0.082
$$

**Gate 3**：❌ 失败（$-0.082 < 0.40$，甚至接近零 · 略微负相关）

## Step 7 · 终审判决

- **accepted**：False
- **reject_reason**：`Gate1`
- **§7 分级**：**L4**（$\text{se\_ratio} = 4.89 > 3.0$ · Gate 3 $r \le 0.20$ · 归反例登记）

## Step 8 · 反模式复查

无 · 因子定义简单 · 无泄漏 · 无阈值调整。

## Step 9 · 方向偏向审计

未跑（L4 直接归档 · 无需继续判方向）。

## Step 10 · 下游路径

不适用（L4）。

## 结论

- **完全对齐理论预期**：shaping-theory §2.23.5.5 预测的 $se \approx 1/\sqrt{20} = 0.224$，实测 0.2394（相差 6.9%）。窗口回归作为强度识别器的证伪**在实测层面被固定**。
- **Gate 1.5 揭示关键洞察**：因子分布与真值分布**完美对齐**（C1-C4 全过），但秩相关 $r=-0.082$ 近似零——**分布对齐 ≠ 逐点预测能力**。窗口回归天然是"同一噪声在不同时间片上的重复采样"，边缘分布相同但没有任何逐点相关。
- **归档反例登记**：本因子进入 `rejected_factors.md` · Wave 1 完成第一项对照。

## 数据产出

- `docs/workbench/strength-factor-screening/outputs/f11-window-regression-20h.json` · 完整 CandidateReport
- driver：`docs/workbench/strength-factor-screening/scripts/f11_window_regression.py`
- 共享工具：`docs/workbench/strength-factor-screening/scripts/_driver.py`

## 相关文档

- shaping-theory §2.23.5.5 · §2.23.6.7 · 双视角矩阵表最下行（20h 窗口回归）
- screening-methodology §六 · 双置信度视角
- screening-methodology §七 · 分级因子管理（本因子归 L4）
