# candidate · f5-hurst-60

> 类型：Wave 1 · 强度识别因子候选
> 状态：**L4 · 反例归档**（2026-07-16）
> 上游：experiment-plan.md § Wave 1 · shaping-theory §2.12.4 KF-16

## Step 0 · 立项登记

| 字段 | 内容 |
|---|---|
| slug | `f5-hurst-60` |
| 假设陈述 | 60 bar 窗口 Hurst R/S 指数 · 线性映射 $\hat{x} = \max(0, 2 \cdot (H - 0.5))$ · H 高 → 趋势凝聚 → $|\nu|/\sigma$ 强 |
| 理论出处 | shaping-theory §2.12.4 · KF-16：1h 实测 mean H = 0.603，95% 合约 H > 0.55 |
| 预期结论 | Gate 1 边缘 · 若映射斜率对齐 → L2/L3 · **实测不通过** |

## Step 1 · 参数准备（同 F11）

见 [candidate-f11-window-regression-20h.md](candidate-f11-window-regression-20h.md#step-1--参数准备kf-27-反解) · 复用 `(K_S^\ast, K_T^\ast, \tau^\ast) = (2.5, 10.0, 0.6)` · $se_{\text{target}} = 0.0489$。

## Step 2 · Gate 0 · 因果性

因子只用 $t - 60 .. t - 1$ 的 log_ret · **结构上因果**。

## Step 3 · 真值构造

同 F11 · $W = 20$ · 1012 评估点（Hurst 窗口 60 消耗更多首段）。

## Step 4 · Gate 1 · SE 精度

$$
\widehat{se} = 0.3173, \qquad \widehat{se} / se_{\text{target}} = 6.49
$$

**Gate 1**：❌ 失败 · 6.49× 超阈 · 比 F11 更差。

**根本原因**：Hurst 线性映射 $\max(0, 2 \cdot (H - 0.5))$ 输出的**分布**与真值分布不匹配：

- 因子均值 0.269 vs 真值 0.202（偏高 33%）
- 因子标准差 0.269 vs 真值 0.166（偏宽 62%）
- 因子 Q_90 0.630 vs 真值 0.414（偏高 52%）

## Step 4.5 · Gate 1.5 · 分布对齐

| 检验 | 数值 | 阈值 | 通过 |
|---|---|---|---|
| C1 均值 | rel_err = 0.334 | < 0.20 | ❌ |
| C2 尺度 | sd_ratio = 1.617 | ∈ [0.5, 1.5] | ❌ |
| C3 尾部 | q90_rel_err = 0.523 | < 0.30 | ❌ |
| C4 KS | D = 0.306 | < 0.15 | ❌ |

**Gate 1.5**：❌ 四项全败 · remedy=`reject_dist_error`

**诊断**：Hurst 值 $\ge 0.5$ 的品种极多（1h 玉米 mean = 0.60），线性映射 $2(H-0.5)$ 系统性放大到 $\ge 0.2$ 的区间，导致整体分布**位置偏高、尺度偏宽**。若换成非线性变换（如 rank 归一 + 分布反变换），可能修复 C1-C3。

## Step 5 · Gate 2 · 覆盖率

ratio = 5.682 ≥ 0.70 · ✅（但同样是"se 大 → 阈值反解偏低 → fire 数量爆炸"的伪通过）

## Step 6 · Gate 3 · 秩相关

$$
\widehat{r} = 0.061 \not\ge 0.40 \quad ❌
$$

Spearman 秩相关几乎为零——**Hurst 与未来 20h 的 $|\nu|/\sigma$ 逐点独立**。这与 KF-16 的"1h 趋势凝聚"结论不冲突：Hurst 描述的是过去 60h 的**时间序列结构**（长程记忆强度），与未来 20h 的**具体漂移强度**没有直接映射关系。

## Step 7 · 终审

- **accepted**：False
- **reject_reason**：`Gate1`
- **§7 分级**：**L4**（se_ratio 6.49 > 3.0 · Gate 3 r=0.061 < 0.20）

## Step 10 · 未来修正方向

1. **rank 归一 + FoldedNormal 反变换**：Hurst 排 rank，按目标分布 $Q_D$ 反变换到 $\hat{x}$——可能修 C1/C2/C3 但不解决 Gate 3 秩相关问题
2. **短窗 Hurst**：将 W_HURST 从 60 缩到 30/20 · 可能提升时效性 · 但短窗 R/S 分析噪声大
3. **降级为 L3 融合过滤器**：Hurst 若与 Realized vol / ATR 拐点组合 · 或许能贡献辅助信号
4. **切换到不同映射**：如 $\hat{x} = \sigma_r \cdot (H - 0.5)$（结合波动率与 Hurst） · 属于 F6 融合因子的雏形

## 结论

Hurst 单独作为强度识别器**在 1h 玉米上失效**。逐点秩相关 $r=0.061$ 说明 Hurst 与未来 $|\nu|/\sigma$ 是两个几乎独立的量——**长程记忆强度 ≠ 短期漂移强度**。

## 数据产出

- `outputs/f5-hurst-60.json` · CandidateReport
- driver：`scripts/f5_hurst.py`
