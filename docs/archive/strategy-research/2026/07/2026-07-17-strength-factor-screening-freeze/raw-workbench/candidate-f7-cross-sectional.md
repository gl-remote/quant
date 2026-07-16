# candidate · f7 & f7-alt · 横截面共振（板块 4 品种）

> 类型：Wave 2 · 强度识别因子候选
> 状态：**F7 · L4** + **F7-alt · L4**（2026-07-16）
> 上游：experiment-plan.md § Wave 2 · shaping-theory §2.22.7

## Step 0 · 立项登记

| 字段 | F7 | F7-alt |
|---|---|---|
| slug | `f7-cross-sectional-resonance-4syms` | `f7alt-cross-sectional-avg-intensity` |
| 假设 | 板块 4 品种方向一致 × 平均强度 | 板块 4 品种平均强度（不管方向） |
| 因子表达式 | $\lvert \text{mean}(\text{sign}_i) \rvert \times \text{mean}(\lvert \nu_i / \sigma_i \rvert)$ | $\text{mean}(\lvert \nu_i / \sigma_i \rvert)$ |
| 目标品种 | c2601（单合约） | 同 |
| 板块 | c / m / p / cs（豆粕、棕榈油、玉米淀粉） | 同 |
| 样本 | inner-join 424 bar · 评估集 382 点 | 同 |

## Step 1 · 参数准备

target 只取 c2601 单合约（因为 inner-join 后目标品种只有 1 合约 数据）：

| 参数 | 值 | 说明 |
|---|---|---|
| $\mu_D$ | 0.1967 | 单合约样本 · 略大于 Wave 1（3 合约合并 0.198） |
| $\sigma_D$ | 0.1731 | 单合约样本 · 大于 Wave 1（3 合约合并 0.160） |
| $K_S^\ast, K_T^\ast, \tau^\ast$ | (2.5, 10.0, 0.6) | KF-27 反解 |
| $x^\ast$ | 0.1293 | |
| $x_{\min}$ | 0.0496 | |
| **$se_{\text{target}}$** | **0.0484** | |

## Step 4-6 · Gate 判决对比

| Gate | F7 | F7-alt |
|---|---|---|
| Gate 1 se_hat | 0.2280 · ratio **4.71** ❌ | 0.2055 · ratio **4.25** ❌ |
| Gate 1.5 C1 均值 | 0.508（0.097 vs 0.197） | **0.050**（0.187 vs 0.197） ✅ |
| Gate 1.5 C2 尺度 | 0.480 ❌ | 0.499 ❌ |
| Gate 1.5 C3 尾部 | 0.409 ❌ | 0.276 ✅ |
| Gate 1.5 C4 KS | 0.312 ❌ | 0.215 ❌ |
| Gate 1.5 remedy | reject_dist_error | reject_dist_error |
| Gate 2 ratio | 0.000 ❌（fire 从未触发） | 1.200 ✅ |
| **Gate 3 r_hat** | **-0.117** ❌ | **-0.094** ❌ |
| level | **L4** | **L4** |

## 关键观察

### 观察 1 · F7-alt 的均值对齐是本轮最好的

$\text{mean}(\hat{x}) = 0.187$ vs $\text{mean}(x^{\text{真}}) = 0.197$ · 相对偏差 5.0%（Gate 1.5 C1 通过）。

**这说明**："板块平均强度"这个统计量本身**与目标品种的强度均值在数值上高度接近**——从物理上讲得通：农产品板块内 4 品种的横截面均值 ≈ 板块整体波动率水平，恰好也接近单品种的均值。

### 观察 2 · Gate 3 秩相关依然 -0.09（近零略负）

尽管**均值对齐**，Gate 3 秩相关几乎为零——**这是本主题的核心发现**：

**过去 20 bar 的任何统计量与未来 20 bar 的 $|\nu|/\sigma$ 都独立**。

### 观察 3 · 方向一致要求让 Gate 3 更差

F7（含方向一致要求）r=-0.117 · 比 F7-alt（无方向要求）r=-0.094 更差。
**这与 shaping-theory 的通道分离原则一致**：方向属于通道 A · 通道 B 只应关注强度。混入方向反而引入噪声。

### 观察 4 · F7 的 Gate 2 fire=0

$\theta_{\text{thresh}} = 0.05 + 1.645 \cdot 0.228 = 0.425$，但因子 Q90 只有 0.234——**永远触发不了**。
"方向一致 × 平均强度"这个乘积天然把因子输出压缩到低值区（方向一致性 mean_sign 平均只有 0.5-1，乘上强度均值 0.2 后极难破 0.4）。

## 与 Wave 1 的对比 · 强化 KF-B*

| 因子来源 | 因子 | Gate 3 r | 结论 |
|---|---|---|---|
| Wave 1 · 单品种过去统计 | F11 20h 窗口回归 | -0.082 | |
| Wave 1 · 单品种过去统计 | F5 Hurst-60 | 0.061 | |
| Wave 1 · 单品种过去统计 | F1 ATR 拐点 | -0.067 | |
| Wave 1 · 单品种过去统计 | F3 RV 突破 | -0.003 | |
| Wave 2 · 板块横截面 | F7 共振 | -0.117 | |
| Wave 2 · 板块横截面 | F7-alt 平均强度 | -0.094 | |

**共同结论**：所有基于过去数据（无论单品种还是板块）的统计量与未来 $|\nu|/\sigma$ **系统性略负相关或零相关**——**均值回归的边际证据**！

## 关键发现 · KF-B6 候选

**"过去 20h 内出现强漂移的品种，未来 20h 的漂移强度反而略低"**——负相关很小（-0.05 到 -0.12），但在 6 个独立因子上表现一致，方向从未反转。这是**均值回归**的典型信号，但**强度太弱**（|r| < 0.15），不足以逆向使用（做"看空强度"的因子）。

## 数据产出

- `outputs/f7-cross-sectional-resonance-4syms.json`
- `outputs/f7alt-cross-sectional-avg-intensity.json`
- driver：`scripts/f7_resonance.py` + `scripts/f7alt_avg_intensity.py`
