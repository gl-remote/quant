# value-area-rolling-reacceptance · 主题

> 类型：Theme / **已冻结（Frozen 2026-07-05）**
> 状态：**主题假设完全证伪，不再作为独立策略推进**
> 前置主题：[../value-area-reacceptance/README.md](../value-area-reacceptance/README.md)（已冻结）
> 创建时间：2026-07-03
> 冻结时间：2026-07-05
> 结论文档：[research-status.md](research-status.md)
> 归档：[../../../../archive/strategy-research/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md](../../../../archive/strategy-research/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md)

## 冻结摘要（2026-07-05）

主题于 2026-07-03 立题，2026-07-05 冻结。Stage 1 / 1.5 / 4 / 4b 完整实验
链条（20 品种 × 70 合约 × 5m/15m 双周期）证伪了主题的全部核心假设：

1. **POC 特殊性证伪**（Stage 1.5-A5/A5b）：跨 7 种前日锚点距离-到达率函数
   完全重合；POC 相对 PrevClose 等锚点无独立价值
2. **Rolling POC 独立价值证伪**（Stage 4 显著性检验）：配对差值 -0.137,
   p=0.646；cluster bootstrap CI 跨 0
3. **Reacceptance 触发器特殊性证伪**（Stage 4b）：vs no_trigger baseline
   差值 +0.019 (5m) / -0.088 (15m)，p 均不显著
4. **4+ ATR 距离档本身无 edge**（Stage 4b）：no_trigger baseline 期望 ≈ 0

详见 [research-status.md](research-status.md) 与
[freeze-summary.md](../../../../archive/strategy-research/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md)。

**以下 §1-§8 为立题时的动机推演，冻结后仅作历史记录保留，其中的策略假设
已全部证伪，请勿再作为策略依据。**

---

## 1. 动机与建模选择

### 1.1 上一主题为什么失败

前置主题 `value-area-reacceptance` 采用「离散刷新 POC/VA + 跨 bar 累积
attempt state」的实现，暴露了三个结构性问题（详见前主题 README §1.2）：

1. **§11.3.5 Replay 反事实计算**：需要用新锚在过去 n_step 根 bar 上重扫
   attempt，专门写了一节 spec 例外解释；
2. **策略核心持有大量跨 bar 状态**（`SideState` / `BreakoutTrack` /
   `T_prev_event` / `va_r30_anchors`），POC/VA 无法提炼为 indicator；
3. **C2 语义在两个坐标系纠缠**："最近一次 vs 上一次"和"当前锚 vs 上一
   次锚"混合，spec 花了 3 版才修好 X_s 极值化定义。

Stage B v2/v3 双 Q 判据未通过，主策略走 feature-only 降级路径。

### 1.2 三条建模路径对比（jump-process 假设下）

POC 是**订单流堆积释放**的产物（Kyle 1985 / Glosten-Milgrom 1985 /
Hamilton 1989 regime switching）——本质是 jump process 或 regime
switching，而非平滑漂移。在 jump 假设下三种建模路径：

| 方案 | 对 jump process 的建模 | 工程成本 | 排名 | 采纳？ |
|---|---|---|---|---|
| A. Discrete + change-point detector（CUSUM/BOCPD）| **理论最贴合** | 高（500-1000 行 detector + 参数调优） | 最好 | 否 |
| **B. Rolling window（隐式追踪）** | **隐式检测**，跳变时窗口自动过渡 | 低 | 次好 | **✓ 本主题** |
| C. Discrete 定时刷新（前主题现状）| 假设 τ 对齐采样时钟（错） | 中 | **最差** | 否 |

### 1.3 为什么选 B 而不是 A

- **A 的理论最优性不等于工程可行性**：CUSUM 有 `threshold` 和 `drift`、
  BOCPD 有 `hazard rate` 和 `changepoint prior`——新参数总量并不比 B
  少，反而多；每品种/时段可能都要调，构成新的过拟合来源。
- **A 也不是"零延迟"**：CUSUM 平均检测延迟 ≈ 5-15 根 bar，BOCPD ≈ 3-10
  根 bar；rolling 每 bar 就开始响应，均摊到 n_profile 根 bar 完成过渡，
  延迟量级接近。
- **A 会让 spec 更复杂**：detector 定义 + 阈值 + 后置 hazard 更新 + 与
  attempt state 的耦合，比现状**更**复杂；B 直接删掉一整套结构，spec
  从 ~1000 行到 ~500 行。
- **文献立场**：jump-diffusion 的 nonparametric 估计（Ait-Sahalia 2004
  / Mancini 2009）主流方法就是 rolling window + smoothing。显式 change-
  point detection（BNS 2006 / Lee-Mykland 2008）只在 tick-level 超高频
  数据上有明确优势。

**结论**：B 是**理论次优 + 工程最简的帕累托最优点**。A 保留作为 §8.6
提到的"rolling 过渡态失败后的补丁路径"，不作为主入口。

## 2. rolling 版本的核心设计

每 bar 都 rolling recompute POC / VA / breakout / reacceptance，参照
布林带 rolling 突破再接受语义。C1/C2/C3 从滚动窗口的 attempt 序列上派生：

- POC / VAH / VAL 每 bar 都是"最近 n_profile 根 bar 的 volume profile"
- 每根历史 bar `i` 有它自己那一刻的 `(P_i, U_i, D_i)`（rolling 锚）
- C1/C2/C3 是"最近 n_step 根 bar 上按 rolling 锚重扫 attempt"的滚动统计
- 策略核心零跨 bar 状态

## 3. 语义定义（草稿）

### 3.1 每 bar rolling 锚（indicator 层）

```text
Window(t) := 最近 n_profile 根已收盘 bar
Profile_t := volume_profile(Window(t))          # rolling
P_t       := select_poc(Profile_t, C_t)
(D_t, U_t):= greedy_value_area(Profile_t, P_t, ratio)
```

### 3.2 每 bar rolling 事件（indicator 层）

```text
Break_L(i)  := 1[L_i <= D_i - b_tau]            # 用 bar i 自己的 D_i
Break_U(i)  := 1[H_i >= U_i + b_tau]
R_L(i)      := 1[Break_L(i-k..i) 存在 ∧ C_i >= D_i + r_tau]
R_U(i)      := 1[Break_U(i-k..i) 存在 ∧ C_i <= U_i - r_tau]
```

即每根 bar 上 breakout / reacceptance 都用 **bar 自己那一刻的 rolling 锚**
判定，跟布林带突破逻辑完全同构。

### 3.3 t 时刻的滚动统计（strategy 层，纯查表）

```text
Events_s(t) := { i ∈ [t-n_step+1, t] : R_s(i) = 1 }        # 最近 n_step 内的 attempt
A_s(t)      := |Events_s(t)|
i_last(t)   := max(Events_s(t))                            # 最近一次 attempt
i_prev(t)   := 第二大 idx in Events_s(t)
B_s^-(t)    := B_s(i_prev(t))                              # 上一次 attempt 的 B_s
B_s(t)      := 当前 bar 的 B_s（用 t 时刻的 U_t / D_t 和最近突破 bar 的 extreme）
Z_s^-(t)    := TouchPOC_q(i_prev(t)+1, i_last(t)-1)        # 相邻两次 attempt 间是否触 POC
```

C1/C2/C3 判定：

```text
C1_s(t) := A_s(t) = 0     # 最近 n_step 内还没有 attempt
C2_s(t) := A_s(t) >= 1 ∧ B_s(t) < B_s^-(t)
C3_s(t) := A_s(t) >= 1 ∧ Z_s^-(t) = False
```

### 3.4 TouchPOC 判定的锚选择

两种可选：

- **B-per-bar**：每根中间 bar `i` 用它自己那一刻的 `P_i` 判定
  `L_i <= P_i - δ_tau <= H_i`（**推荐**，与布林带 rolling 语义完全一致）
- **B-current**：整段 window 都用当前 `P_t` 判定（简单，但混合坐标系）

## 4. 优点

1. **完全无状态**：策略核心只读 indicator，不维护跨 bar 变量
   - `SideState` / `BreakoutTrack` / `T_prev_event` / `va_r30_anchors`
     全部删除
2. **spec 大幅简化**：§5.3 `Reset_s / i_start / τ_s`、§6.2 attempt 更新
   规则、§11.3 三类刷新事件、§11.3.5 Replay 全部删除，spec 长度约减半
3. **多策略复用**：POC / VA 提炼为 `VolumeProfileIndicator`，别的策略
   （比如未来 continuation 对照线）能直接读同一 indicator
4. **反事实计算问题消失**：每 bar 都是 rolling 计算，历史 bar 用历史锚，
   spec §5.7「TouchPOC 逐 bar 用自身锚」是唯一规则，没有例外
5. **C2 语义天然成立**：`B_s(t)` 用 t 时刻的 U_t 和最近 breakout 的 extreme，
   `B_s^-` 是 i_prev 时刻的 U_{i_prev} 和当时的 breakout extreme，两者可
   自然比较

## 5. 代价

### 5.1 计算量

1m 数据 190k bar 单品种：

| 操作 | 每 bar 开销 | 全回测总量 | 估计 wall-clock |
|---|---|---|---|
| Rolling profile 重算（增量 add/remove）| O(K̄) | O(N · K̄) | <100ms |
| Profile → POC / VA 计算 | O(B log B) | O(N · B log B) | 1-3s |
| Break / R 判定（当前 bar）| O(1) | O(N) | <10ms |
| C1/C2/C3 滚动统计（查表）| O(n_step) | O(N · n_step) | ~1s |
| **合计** | ~5k op | | **~5-10s 单品种 1m** |

对比当前 Stage B 5m 数据单跑 0.4-0.8s，1m 数据每 bar 刷新版本约 20-30x，
仍在可接受范围。Stage B 225 runs 1m 数据估计 30-60min。

### 5.2 增量维护 rolling profile 的工程复杂度

- `range` 模式：bar 进入时 volume 摊到 K̄ 个桶（add），bar 离开时同样 K̄ 个
  桶反向 subtract，需要保留每根 bar 的 volume 分布（deque[dict]）
- `close` 模式：每 bar 一个桶 add/remove，简单
- POC / VA 计算：每 bar 从 rolling_profile 全量重算（O(B log B)）；也可以
  加缓存但收益有限

### 5.3 语义变化

- C1 定义从"本次刷新以来还没触发过 attempt"变成"最近 n_step 内还没触发过
  attempt"——n_step 大时含义变化不大；n_step 小时差别显著
- Adopt 时机消失：不再有"刷新采纳新锚"这个概念，也没有"Adopt 后不能立即
  开仓"的约束。策略随时可用最新 POC / VA
- 「持仓期间锚不变」的行为消失：不需要区分是否持仓，锚永远是 rolling 的
- session reset 从"清空 attempt state"变成"清空 rolling window 里跨 session
  的 bar"——需要在 indicator 层处理

## 6. 未决问题

- **n_step 保留还是删除？** 保留作为 attempt 追溯长度（推荐）；或者直接
  用 n_profile 判 attempt（简化）
- **Session 边界处理**：rolling window 是否允许跨夜盘 → 日盘 → 夜盘？
  当前 spec 规定 session_start 时 Reset。rolling 版本需要在
  VolumeProfileIndicator 里明确 session boundary 规则
- **参数命名**：`n_profile` / `n_step` 语义都保留，但含义从"离散刷新周期"
  变成"滚动窗口长度"，需要 spec 与代码同步更名或加注释
- **诊断字段**：`va_r30_last_refresh_bar_idx` 等成为无意义字段，需要
  三层诊断（Alpha / Risk / Execution）里的相关字段一并清理

## 7. 实施路线图

前置条件（**已满足**）：
- ✓ 前置主题 `value-area-reacceptance` 冻结（README 已更新为"已冻结"）
- ✓ Stage B v2/v3 结论稳定（[Stage B 归档](../../../../archive/strategy-research/2026-07-03-value-area-reacceptance-stage-b/README.md)）
- ✓ 建模路径决策：B（rolling window），A/C 已排除，理由见 §1.3

阶段规划：

| Stage | 输出 | 判据 | 备注 |
|---|---|---|---|
| **S0 · Spec 编写** | `strategy-math-spec.md` | 一致性 pass，无跨 bar 状态 | 参考本 README §3 |
| **S1 · Indicator 抽取** | `VolumeProfileIndicator`（rolling profile / POC / VA / breakout / R 每 bar 值）| 单元测试 pass；1m 单品种 <5s | 先本策略内部实现，等有第二策略需要再上升为 shared |
| **S2 · 策略实现** | `value_area_rolling_reacceptance_strategy.py` | 策略核心零跨 bar state；275+ 测试 pass | 参考旧策略但删除 SideState / BreakoutTrack |
| **S3 · Smoke test** | 单样本 1m backtest 报告 | 与前主题在同 bar 下 breakout 事件个数近似（±10%）| p2601 单跑，5m + 1m 各一份 |
| **S4 · Stage A（结构对齐）** | 5m 上 rolling vs discrete 对照 backtest | 同 15 symbols × 3 pattern set × 3 n_profile；比较 trade 分布 | 目标：证明 rolling 至少不劣于 discrete |
| **S5 · Stage B（1m 泛化验证）** | 1m 数据 Stage B 完整跑 | 双 Q 判据：Group_P PF≥1.6 & Group_M ≥5/8 profitable | 触发时启动 |
| **S6 · 参数选择归档** | `parameter-selection-spec.md` 填充 | 参数固定成候选组 | Stage B 通过后 |

失败退出路径：
- S3 失败（rolling event 数与 discrete 差异 >30%）→ 检查 rolling window
  是否正确落地，回 §3 定义修
- S4 失败（rolling 显著劣于 discrete on same data）→ 触发 §8.6 平滑变
  体：B+（debouncing）或 B++（EWMA）
- S5 失败（Stage B 双 Q 仍不通过）→ 主题走 feature-only 降级，
  与前主题结论一致
- 若 S5 后仍需追求更高质量，考虑 §1.2 方案 A（显式 change-point
  detector），但工程成本大，仅作最后手段

## 8. 理论依据：为什么 rolling 反而更贴合 "POC 是跳变量" 的直觉

一个反直觉的结论：**即使我们相信 POC / VA 是分段稳定的跳变量，当前
discrete 刷新也不是正确建模，rolling 反而更贴合**。本节展开这个论证。

### 8.1 POC 是跳变量的两种叙事

**叙事 A（订单簿 / order-flow 视角）**：POC 是"人为堆单、大量交易堆积"
的产物。堆完了不动，直到有人搬走或补充新单，才跳到下一个位置。
- 对应数学模型：**跳跃过程（jump process）**，Poisson jump / Hawkes 过程
- POC 在 `[t_k, t_{k+1}]` 内恒定于 `θ_k`；在跳变时刻 `t_{k+1}` 瞬间跳到
  `θ_{k+1}`

**叙事 B（能量-释放视角）**：POC 是市场积攒动能的位置，VA 边界是能量
释放。积攒一段时间，能量在 VA 释放后 POC 转移到新位置。
- 对应数学模型：**regime switching**（Hamilton 1989 / hidden Markov）
- 存在离散状态 `s_t ∈ {1, 2, ...}`，每个状态对应一个 θ_s，状态切换
  驱动 POC 跳变

两种叙事都指向"POC 是随机离散变量，持续一段时间，变一下，再持续一段
时间"。这个假设是有金融微观结构文献支持的：Kyle (1985)、Glosten-Milgrom
(1985)、Easley-O'Hara (1987) 讨论的 informed trader / order flow /
equilibrium price shifts 全都是**离散跳变**的，不是布朗运动。

### 8.2 从 jump 假设出发，重新审视 n_profile 敏感性

Stage B 观察到 `n_profile = 4h vs 8h vs 12h` 结果差异极大（同 group、
同 pattern set，ret_mean 可以差 1-2 个百分点）。乍看这是"POC 不稳定"的
反证，但按 jump 假设重新解释：

- `n = 4h` 短窗口 → 窗口内**大概率只覆盖 1 个 regime** → 估当前 regime
  的 θ_k，精度低但"跟得上跳变"
- `n = 12h` 长窗口 → 窗口内**可能横跨 2-3 个 regime** → 估的 θ 是多个
  regime 的"混合分布"中心
- **两者估的本来就不是同一个东西**（当前 regime vs 混合分布），差异大
  完全合理

**结论**：jump 假设跟数据完全 compatible，不构成反证。

### 8.3 但 discrete 刷新 ≠ jump process 的正确建模

关键点：**"POC 是跳变的"不等于"我们的 discrete 刷新是正确建模"**。

看当前 discrete 刷新做的事：
- 每 n_step 采一次样，得到 θ_k
- 隐含假设：θ 在 `[t_k, t_{k+1}]` 稳定 = θ_k
- 隐含假设：**跳变时刻 τ 对齐 n_step 采样时钟**

问题：**跳变时刻 τ 是不可预测的**，不会好心地对齐我们的采样时钟。

- 若 τ 恰好落在两次采样之间 `t_k < τ < t_{k+1}`，从 τ 到 t_{k+1} 这段
  时间 **我们用旧 θ_k 判定信号，是错的**
- 平均延迟期望 `E[延迟] = n_step / 2`
- n_step = 4h 意味着**平均 2h 的信号用旧锚判定**

处理 jump process 的**正确方式**是 change-point detection：不按时钟
刷新，而是**检测到跳变时立即刷新**。经典算法：
- CUSUM (Page 1954)
- Bayesian Online Change Point Detection (Adams & MacKay 2007)
- Adaptive filtering / Kalman with regime switch prior

### 8.4 Rolling 是 jump process 下的"隐式 change-point detection"

Rolling window 恰恰是不显式建模跳变但**隐式追踪**的做法：

- 跳变发生后，rolling window 每 bar 把最老一根挤出、最新一根挤入
- 大约 n_profile 根 bar 内，`θ_t` 从 `θ_{k-1}` 自动过渡到 `θ_k`
- 相当于 **"detection + estimation" 一体化**，不需要写显式 detector

理论支持：jump-diffusion 的 nonparametric 估计（Aït-Sahalia 2004、
Mancini 2009 的 realized variance / jump activity estimator）主流方
法就是 **rolling window + smoothing / thresholding**。

### 8.5 三种方案在 jump 假设下的正确性排序

| 方案 | 对 jump process 的建模 | 工程成本 | 排名 |
|---|---|---|---|
| A. Discrete + change-point detector | **理论最贴合** | 高（CUSUM/BOCPD）| 最好 |
| B. Rolling window | **隐式检测**，跳变时窗口过渡 | 低 | 次好 |
| C. Discrete 定时刷新（**现状**）| 假设 τ 对齐采样时钟（错） | 中 | **最差** |

C 是"把时间轴 discretize"的偷懒做法，**既没 A 的显式检测，也没 B 的
连续追踪**。它成立的前提是"跳变周期 = n_step 的整数倍"，这是最强假设，
经验上不成立。

### 8.6 Rolling window 抖动担忧的化解

对 rolling window 的常见担忧是"θ 抖动"。在 jump 假设下这个担忧可拆解：

- **regime 稳定期**内：window 里全是同一 θ 的样本，rolling 估计 `θ̂_t`
  抖动只来自 `1/N` 采样噪声，n_profile 大（144/288）时抖动小
- **regime 过渡期**（跳变后 n_profile 根 bar 内）：window 混合了新旧
  regime，`θ̂_t` 呈现过渡态斜坡。这是**正确反映了"我们对新 regime
  的确信度还没到 100%"**，不是 bug，是特性

若仍觉过渡期斜坡不可接受，有两种平滑手段：

- **B+ (debouncing)**：锚必须持续变化 k 根 bar 才采纳到策略层，滤除
  单 bar 毛刺跳变
- **B++ (EWMA)**：`profile_ewm_t = α · new_bar + (1-α) · profile_ewm_{t-1}`。
  Kalman filter 特例；对"underlying θ 慢漂移 + 观测噪声"模型是**最优
  线性估计器**。是"跳变模型"与"平滑模型"的折中

### 8.7 一句话

**"POC 是跳变量"这个直觉是对的，但它并不是 discrete 刷新的理由；恰恰
相反，它是切换到 rolling 的理由**——因为 rolling 是不知道跳变时刻的
情况下，最简单的"隐式 change-point detection"实现。当前 discrete 刷
新（方案 C）在 jump 假设下反而是最差的近似。

真正贴合 jump 假设的极致方案是 A（显式 change-point detection），但
工程复杂度过高；B 是理论次优 + 工程最简的**帕累托最优点**，因此本主题
选择 B（可选加 debouncing 或 EWMA 平滑）。

## 9. 参考

- 布林带 rolling 突破再接受：mid / upper / lower 每 bar rolling，
  breakout / reaccept 每 bar 用当时锚判定，无跨 bar 状态。是本提案的
  参考模型。
- 当前 spec 的 Replay 机制（§11.3.5）是"想吃 rolling 的直觉，但被离散
  刷新 + 跨 bar 状态设计束缚"的折中产物；rolling 版本让这个 workaround
  自然消失。
- Kyle 1985 / Glosten-Milgrom 1985：市场微观结构里 order flow-driven
  equilibrium price 的经典 jump 模型。
- Hamilton 1989 / Dahlhaus 1997：regime switching 与 locally stationary
  processes 的正统框架，正是"POC 分段稳定"直觉的数学化。
- Page 1954 CUSUM / Adams & MacKay 2007 BOCPD：change-point detection
  经典算法，对应 §8.5 方案 A 的显式实现路径（本主题暂不采纳）。
- Aït-Sahalia 2004 / Mancini 2009：jump-diffusion 的 nonparametric
  rolling estimator，是 §8.4 隐式追踪思路的文献依据。
