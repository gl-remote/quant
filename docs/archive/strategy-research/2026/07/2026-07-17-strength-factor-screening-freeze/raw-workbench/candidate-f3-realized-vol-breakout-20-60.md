# candidate · f3-realized-vol-breakout-20-60

> 类型：Wave 1 · 强度识别因子候选
> 状态：**L4 · 反例归档**（2026-07-16）
> 上游：experiment-plan.md § Wave 1

## Step 0 · 立项登记

| 字段 | 内容 |
|---|---|
| slug | `f3-realized-vol-breakout-20-60` |
| 假设陈述 | Realized vol 短窗突破长窗 · RV_20 快速上升 → 波动率突破 → 强段候选 |
| 因子表达式 | $\hat{x}_t = \max(0,\; \text{RV}_{20}(t) / \text{RV}_{60}(t) - 1)$，$\text{RV}_W(t) = \text{std}(\text{log\_ret}_{t-W..t-1})$ |

## Step 1 · 参数准备（同 F11）

复用 · $se_{\text{target}} = 0.0489$

## Step 4 · Gate 1

$\widehat{se} = 0.2469$ · ratio = **5.05** · ❌

## Step 4.5 · Gate 1.5

| 检验 | 数值 | 通过 |
|---|---|---|
| C1 均值 | 0.577 (mean 0.085 vs 0.202，低 58%) | ❌ |
| C2 尺度 | sd_ratio = 0.817 | ✅ |
| C3 尾部 | Q90 0.303 vs 0.414 = 0.267 相对偏差 | ✅（勉强） |
| C4 KS | 0.527 | ❌ |

**remedy_hint**：`reject_dist_error`

## Step 6 · Gate 3

$\widehat{r} = -0.003$ · **完全独立**（比 F1 的 -0.067 更接近零）

## Step 7 · 终审 · L4

## 结论

**与 F1 的对比 · 强化关键发现**：

| 因子 | 底层信号 | Gate 3 r | 结论 |
|---|---|---|---|
| F1 · ATR 拐点 | True Range 变化率 | -0.067 | 波动率上升与漂移强度独立 |
| F3 · RV 突破 | log_ret std 变化率 | **-0.003** | 更纯粹的波动率信号 · 更接近零 |

**方法论重要观察**：F3 的 Gate 3 r 更接近零，说明**去除 TR 中的价格跳空信息后（RV 只用 log_ret 而 TR 包含 open-close 跳空），波动率信号与漂移强度的独立性更强**。

这从**双通道漂移探测器**（screening-methodology §2.8）的角度可以解释：
- **通道 A**（$P_{\text{win}}$ 突破）：需要方向漂移
- **通道 B**（time-exit 变化）：需要 barrier 强度

**波动率突破改变的是 barrier 触达时间**（更快到止损/止盈），**不改变方向偏好** —— 所以对 $|\nu|/\sigma$ 无预测力。

## 方法论 KF 候选

**KF-B1** · 波动率变化率类因子（ATR / RV）与未来漂移强度独立
- 类型：方法论
- 状态：已证实（F1 + F3 两条独立证据链）
- 影响：Wave 2 融合时不应把波动率变化率作为强度权重，而应作为覆盖率保护条件
- 数据：F1 · F3 candidate 报告

## 数据产出

- `outputs/f3-realized-vol-breakout-20-60.json`
- driver：`scripts/f3_realized_vol.py`
