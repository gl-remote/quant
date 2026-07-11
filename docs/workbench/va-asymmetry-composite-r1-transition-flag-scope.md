# va-asymmetry-composite · r1 · transition_flag 适用范围与原始分类器一致性核对

> 类型：Workbench（中间结论，未归档）
> 日期：2026-07-10
> 主题：transition_flag 是否应作为维度、适用范围、与 poc 最原始分类器（v4.0）的一致性
> 证据：`docs/research/themes/poc-value-area-asymmetry/parameter-selection-spec.md §4`（v4.0 白名单）、`classifier-math-spec.md §6.4/§7.2`；自检脚本 `scripts/ai_tmp/transition_flag_impact.py`

---

## 1. 问题背景

- 之前几轮把 composite §1.3 六 tier（当时编号 §1.2）写成仅 `(skew × ATR × trend)` 三维，`transition_flag` 以 `tier ≡ (…[, transition_flag])` 形式**悬空**——算出来但不参与分档。
- 用户判断：分析层（poc 白名单）明明按 stable/trans/full 拆了性能，"上个版本就写漏了"。
- 需回答两个问题：
  1. transition_flag 加为维度重不重要？
  2. transition_flag 适用范围是否与最原始分类器一致？

---

## 2. 与 poc 最原始分类器的一致性核对（核心结论）

证据（poc v4.0，正是 composite 继承的版本）：

| 出处 | 内容 |
|---|---|
| `classifier-math-spec.md §6.4` | `transition_flag` 对每个 warmup 满足的事件都计算（session 级 ATR 桶 crossover + `n_transition_window_days = 3` 衰减窗口） |
| `classifier-math-spec.md §7.2` | Tier 命名含 `<…>[_stable | _trans | _full]`；`_full` 为 stable∪trans 的报告口径（**非独立 tier**，只在性能报告中使用） |
| `parameter-selection-spec.md §4` 白名单 | 6 类 × 3 period = **18 格全列**（每类都有 stable / trans / full） |

**结论：transition_flag 适用范围与最原始分类器一致——对全部 6 类均计算，并参与 stable/trans/full 拆分（性能分层 + 出场选择）。composite 的 6 tier 应同样覆盖全类，不能只覆盖部分。** 之前写成"悬空/可选"是写漏，不是上游合并决策（v4.0 的合并是把 144 精细化 tier 并成 6 类，并未删掉 transition_flag 这一维的报告用途）。

---

## 3. 逐 tier 功能重要性（官方 whitelist 证据，v4.0 §4）

"重要性"指在**同一 tier 内**，trans 子期相对 stable 子期是否显著改变可交易性：

| tier | stable | trans | full | transition_flag 重要性 |
|---|---|---|---|---|
| L_seg3_lowmid_up | A +31.2 | A- +29.9 | A- +30.5 | **低**：stable≈trans 均过，full 即可 |
| L_seg12_high_up | FAIL +30.3 | A +57.7 | A- +45.5 | **高**：stable 失败、trans 为 A，仅 trans 可交易 |
| L_seg2_low_flat | FAIL +8.9 | A- +37.3 | A +18.3 | **高**：stable 失败、trans 为 A-，仅 trans 可交易 |
| S_seg12_high_dn | A +26.8 | A +37.1 | A +31.4 | **中**：trans 较 stable 强 ~38%，偏好 trans（核心） |
| S_seg34_high_dn | A- +25.3 | A- +50.8 | A +37.1 | **中**：trans 显著更强（≈2×），偏好 trans |
| S_seg2_mid_dn | FAIL +20.7 | A +24.5 | A +23.2 | **高**：stable 失败、trans 为 A，仅 trans 可交易 |

汇总：**高 3**（L_seg12_high_up、L_seg2_low_flat、S_seg2_mid_dn）｜**中 2**（S_seg34_high_dn、S_seg12_high_dn）｜**低 1**（L_seg3_lowmid_up）。

> 注（重要性口径）："高/中/低"按 trans 相对 stable 的**幅度**划分——高 = stable 不可交易（fail）、仅 trans 可做；中 = 两者均过但 trans 显著更强（≥ ~38%）；低 = 两者均过且幅度相近（≤ ~5%）。S_seg12_high_dn 原误标为"低"，按幅度应升为"中"（trans 较 stable +38%）。L_seg3_lowmid_up 在官方 whitelist 中 stable 31.2 ≈ trans 29.9（差 −4%），确为"低"；此前自算近似 flag 曾显示 ~30% 差异，属 `atr_rank_roll` 近似误差，非真实信号。

- "高"= stable 子期 CI 越 0 / p 不显著（不可交易），只有 trans 子期通过 → 回测时应**只做 trans**，不要把 stable 混进 full 拉低。
- "中"= 两子期都过，但 trans 显著更强 → 偏好 trans，stable 也可。
- "低"= 两子期都过且相近 → 直接用 full 即可。

---

## 4. 与上周自算分析的偏差（诚实校准）

上轮用**近似 flag**（`atr_rank_roll` 10 日滚动 ATR rank 桶）自算 transition_flag，结论"3 个 tier 无差异（L_seg3_lowmid_up / L_seg2_low_flat / S_seg2_mid_dn）"。核对官方 whitelist 后**纠正**：

| tier | 自算结论 | 官方结论 | 判定 |
|---|---|---|---|
| L_seg12_high_up | trans 显著强 | stable 失败、trans A | ✅ 一致（高） |
| S_seg34_high_dn | trans 强 | trans ≈2× stable | ✅ 一致（中） |
| S_seg12_high_dn | trans 略强 | 两者均 A | ✅ 方向一致（低） |
| L_seg3_lowmid_up | trans 更低、无差异 | 两者均过、相近 | ✅ 不重要结论一致（低） |
| **L_seg2_low_flat** | 无差异 | stable 失败、trans A- | ❌ **漏判**（实为高） |
| **S_seg2_mid_dn** | 无差异 | stable 失败、trans A | ❌ **漏判**（实为高） |

**根因**：自算 flag 用 `atr_rank_roll`（10 日滚动 ATR rank 桶），与官方 `atr_bucket_session`（session 级 ATR 桶）不同，未捕捉到 **low-ATR tier 的 regime 切换**。系统性低估了 low-ATR tier 上 transition_flag 的效果。

**教训**：transition_flag 必须用官方 `atr_bucket_session` 计算，复用 `atr_rank_roll` 会漏判。本次适用范围结论以官方 whitelist 为准，自算仅作方向交叉验证。

---

## 5. 对 strategy-math-spec.md 的修订（research 工作副本）

| 位置 | 项 | 改前 | 改后 | 依据 |
|---|---|---|---|---|
| §1.3 表 | 新增列 `transition_flag 适用范围` | — | 见 §1.3 表（高/中/低 + 仅 trans 可交易等） | 本节 §3 |
| §1.3 表注 | 一致性说明 | — | "适用范围与 poc 一致，全 6 类参与 stable/trans/full 拆分" | 本节 §2 |
| §1.3（tier 元组） | tier 元组 | `tier ≡ (skew_label, atr_regime, trend_regime[, transition_flag])` | 6 类为三维 `(skew×ATR×trend)`；transition_flag 全 6 类计算，作 stable/trans/full 第三维（与原始一致） | 本节 §2 |
| §1.3.4（τ_signed） | 新增 `transition_intensity_signed` | — | 有符号连续伴随量 ∈ [−1,+1]：0=稳定、+1=低→高波动扩张、−1=高→低波动收缩、3 日衰减；由 transition_flag 原子量导出 | 用户指定（推荐方案 τ_signed） |
| §1.3 表 + 表注 | transition 适用范围列 | 离散集合 `{0,1}`/`{1}` | 改用 `τ_signed` 区间写法（`τ_signed ∈ [−1,+1]` / `τ_signed ≠ 0` + 偏好 |τ|大）；表注补"方向待回测校准"说明 | 用户指定（区间写法 + 一致性） |

注：research 版与归档版为两份独立副本、已分叉，本次仅改 research 工作副本；归档版维持原样作历史基线。

---

## 6. 后续建议

- [ ] 回测接入时，**高重要性 tier 只做 trans 子期**（L_seg12_high_up / L_seg2_low_flat / S_seg2_mid_dn），勿混入 stable 拉低 full。
- [ ] 出场策略（洞察 U）按 stable/trans 区分：trans 用目标止盈、stable 用追踪止损，需在 B 层落实。
- [ ] 计算 `transition_flag` 必须用官方 `atr_bucket_session`，不得复用 `atr_rank_roll`。
- [ ] 文档全部改完后再跑"重新都试一下"回测，验证高重要性 tier 的 trans-only 拆法。
