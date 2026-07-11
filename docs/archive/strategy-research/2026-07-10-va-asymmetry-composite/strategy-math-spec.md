# va-asymmetry-composite · Strategy Math Spec

> 类型：Strategy Math Spec
> 版本：v0.1（立题占位版 · 阶段 0 实验后冻结为 v1.0）
> 最近更新：2026-07-09
> 上游分类器：theme:poc-value-area-asymmetry#classifier-math-spec v4.0
> 塑形参考：theme:structural-shaping-alpha#first-passage-designer-math-spec

## 0. 版本状态 & 冻结规则

**v0.1 = 立题草案**：所有数值参数（塑形阈值 / 加权系数 / 多空比 / 品种映射）均为
立题时的初值，阶段 0~2 验证后锁定为 v1.0。锁定后任何行为变更必须升 minor 或
major 版本号。

**硬约束（不随实验变更）**：
- 分类器 tier 定义严格继承 v4.0（§1）
- ATR 归一化单位（§2）
- Realistic-cost 口径（§6）
- 风控上限（§7：单笔 2% · 名义 100%）

**可调参数（阶段 1~2 搜索空间内变更）**：
- §3 塑形参数的具体数值（在 ±30% 平台内）
- §4 品种筛选的 tier × 品种映射（按 A/B/C 三类粒度）
- §5 信号强度加权方案（W1/W2/W3 三选一 + 系数）
- §5 多空权重方案（VW1/VW2 二选一 + 系数）

---

## 1. 分类器输入输出（硬约束 · 继承 v4.0）

### 1.1 特征（3 维 rolling rank）

| 特征 | rolling 窗口 | rank 单位 | warmup |
|:---|:---|:---|:---|
| `signed_skew_rank` | 100 events | per-contract | 20 交易日 + 100 events |
| `daily_atr_bps_rank` | 20 交易日（~100 bars @ 1h） | per-contract | 20 交易日 |
| `trend_10d_ret_rank` | 20 交易日 | per-contract | 20 交易日 |

**signed_skew = A3_skew（volume 加权三阶矩）**，定义：

```
mean_p     = Σ_{p in profile} p · vol(p) / Σ vol(p)
std_p      = sqrt( Σ (p - mean_p)² · vol(p) / Σ vol(p) )
A3_skew    = Σ ((p - mean_p) / std_p)³ · vol(p) / Σ vol(p)
profile    = 前一交易日全部 5m bar（W1 窗口）
```

> VA（70% volume window）和 POC（volume mode）仅用于构造 profile 的 tick bin，
> 不参与本规格任何计算。定义见上游分类器 math-spec。

### 1.2 Tier 映射（6 类互斥 + 未分类）

| tier 名 | 方向 | skew 段 | ATR 段 | trend 段 | 初始启用 |
|:---|:---:|:---|:---|:---|:---:|
| L_seg3_lowmid_up | 多 | (0.09, 0.30] | [0.00, 0.67] | [0.75, 1.00] | ✅ |
| L_seg12_high_up | 多 | [0.00, 0.19] | (0.67, 1.00] | [0.75, 1.00] | ✅ |
| L_seg2_low_flat | 多 | (0.09, 0.19] | [0.00, 0.33] | (0.20, 0.75) | ❌（阶段 1 末尾补验 C 类） |
| S_seg12_high_dn | 空 | [0.81, 1.00] | (0.67, 1.00] | [0.00, 0.20] | ✅（核心） |
| S_seg34_high_dn | 空 | [0.60, 0.81] | (0.67, 1.00] | [0.00, 0.20] | ✅ |
| S_seg2_mid_dn | 空 | (0.81, 0.91] | (0.33, 0.67] | [0.00, 0.20] | ✅ |
| 未分类 | - | 其他 | 其他 | 其他 | - |

判定顺序：**先判多空（skew ≤ 0.30 为多域 · skew ≥ 0.60 为空域 · 否则未分类），
再在域内按区间匹配唯一 tier。当 skew 段在多 tier 间重叠时（如 S_seg12 与 S_seg2 在 [0.81, 0.91] 重叠），
按 ATR 段严格区分（ATR 段互不重叠，开闭边界保证唯一匹配）。**

### 1.3 触发时钟

每小时 1h bar close 时判定一次。event 去重：同一合约 8h 内只取第一个信号。

---

## 2. ATR 归一化（硬约束）

所有距离 / 止损 / 仓位 / 成本的单位均用 **entry_atr（触发前 10 日日化 ATR，
与 §1.1 daily_atr_10_bps 的同一度量，contract 面额归一化为 bps）**。

```
entry_atr_bps = daily_atr_10_bps at trigger t
```

> 注：§1.1 特征表写 `daily_atr_bps_rank` 窗口 20 交易日，但 timeline 实际列名为
> `daily_atr_10_bps`（10 日）。实现以实际数据列为准。

---

## 3. 交易执行 · 塑形（基线参数 · 阶段 1 固定 · 阶段 2 平台测试）

### 3.1 入场

- 时刻：t = 分类器 tier 匹配的 1h bar close（整点）
- 成交价：`close_t`（理论价；工程化时改用下一 bar `open_{t+1}` + 滑点修正）
- 方向：tier 决定（多域 tier = 做多，空域 tier = 做空）
- 数量：见 §5 仓位计算（含品种筛选 × 强度加权 × 多空比）

### 3.2 止损（SL）

| tier 类型 | SL（entry_atr 倍数） |
|:---|:---:|
| L_*（多头 tier） | **K_L^SL = 1.0**（基线 · 阶段 2 平台：0.7 ~ 1.3） |
| S_*（空头 tier） | **K_S^SL = 2.5**（基线 · 阶段 2 平台：2.0 ~ 3.0） |

止损触发价：
```
P_SL^long  = entry_price − K_L^SL × entry_atr_bps × entry_price / 10000
P_SL^short = entry_price + K_S^SL × entry_atr_bps × entry_price / 10000
```

### 3.3 时间退出（Time Exit = 主止盈机制）

| tier 类型 | 持仓期（bar 数 @ 1h） |
|:---|:---:|
| L_*（多头 tier） | **H_L = 8**（基线 · 阶段 2 平台：6 ~ 10） |
| S_*（空头 tier） | **H_S = 10**（基线 · 阶段 2 平台：8 ~ 12） |

到达 H_L / H_S 小时后的第一根 1h bar 的 close 平仓（等价于第 H×12 根 5m bar 的 close）。
优先级：SL > 时间退出（同时触发取 SL）。

### 3.4 Trailing（不启用）

archive:2026-07-09-poc-va-shaping 已验证 10h 内 trailing 触发率 < 2%，
净效果为 0 或负。阶段 0-3 **默认不启用 trailing**。如阶段 4 工程化时可做
开关参数，默认关闭。

### 3.5 硬止盈（TP，不启用）

archive:2026-07-09-poc-va-shaping 已验证硬 TP 劣于纯时间退出。
阶段 0-3 **默认不设硬 TP**。

---

## 4. 品种筛选（阶段 1 Gatekeeper C.1）

### 4.1 三大品种类型（继承 KF-24）

| 类型代码 | 类型名 | 品种前缀列表 | 默认启用 tier 子集 |
|:---:|:---|:---|:---|
| A | 金融贵金属 | IF, IH, IC, IM, T, TF, TS, au, ag | L_seg12_high_up, S_seg12_high_dn |
| B | 化工建材黑色 | rb, hc, i, j, jm, TA, MA, PP, pp, l, v, eb, eg, sc, fu, bu | L_seg3_lowmid_up, S_seg34_high_dn |
| C | 农产品有色主流 | cu, al, zn, ni, sn, pb, m, y, p, c, cs, CF, SR, OI, RM, FG | L_seg3_lowmid_up, L_seg12_high_up, S_seg12_high_dn, S_seg34_high_dn, S_seg2_mid_dn（+ 阶段 1 补验 L_seg2_low_flat） |

### 4.2 搜索方案（阶段 1 二选一）

| 方案 ID | 规则 | 含义 |
|:---:|:---|:---|
| **S1 · 全品种 5 档** | 不做品种筛选 · A/B/C 所有品种都用 5 档（不含 L_seg2_low_flat） | Baseline（对照用） |
| **S2 · 按类型 tier 映射** | A/B/C 三类分别用 §4.1 的子集（**默认方案**） | 阶段 1 主方案 |

判据：S2 vs S1，净夏普增量 ≥ 0.2 则保留 S2，否则回退 S1。

---

## 5. 仓位与加权（阶段 1 Gatekeeper C.2 + C.3）

仓位在单品种单 tier 维度计算，汇总后受 §7 名义暴露约束压仓。

### 5.1 信号强度加权（C.2 · 阶段 1 四选一）

| 方案 ID | 权重公式 w_strength(tier, t) ∈ [0.2, 1.0] | 说明 |
|:---:|:---|:---|
| **W0 · 等权** | w = 1.0（恒等） | Baseline（对照用） |
| **W1 · Skew 距离** | w = clamp( |skew_rank − thr_skew| / |thr_skew − 0.5 × thr_skew|, 0.2, 1.0 ) | 越远离阈值权重越大（多空对称）；thr_skew = tier 对应 skew 段最近端点（多 0.30/0.19，空 0.60/0.81） |
| **W2 · ATR 匹配** | w = clamp( 1 − 4 × |atr_rank − 0.50|, 0.2, 1.0 ) | ATR 靠近档位中心（0.50）权重越大 |
| **W3 · 三维乘积** | w1 = clamp(W1式, 0.2, 1.0); w2 = clamp(W2式, 0.2, 1.0); w3 = clamp(1 − 2×|trend_rank − t_center|, 0.2, 1.0); w = clamp(w1 × w2 × w3, 0.2, 1.0) | 先各自 clamp 再乘积（避免负值污染）；t_center = 多 0.875 / 空 0.10（默认） |

判据：W1/W2/W3 中最优 vs W0，净夏普增量 ≥ 0.2 则保留，否则回退 W0。

### 5.2 多空权重（C.3 · 含 VW0 共三选一）

| 方案 ID | 多空比 w_dir | 说明 |
|:---:|:---|:---|
| **VW0 · 等权** | w_L = 1.0 · w_S = 1.0 | Baseline（对照用） |
| **VW1 · IR 比例** | w_L = IR_L̄ / IR_max · w_S = IR_S̄ / IR_max · IR_max = max(IR_L̄, IR_S̄)（clamp [0.5, 1.0]） | 按 tier 组等权平均单笔 IR 分配（先算每 tier 的 mean(pnl_net_bps)/std(pnl_net_bps)，再在 tier 间等权平均；默认） |
| **VW2 · 频率平衡** | w_L = sqrt(N_S / N_L) · w_S = sqrt(N_L / N_S) · clamp [0.5, 2.0] | 按触发频率平方根反比分配，平衡多空年度贡献度 |

判据：VW1/VW2 中最优 vs VW0，净夏普增量 ≥ 0.2 则保留，否则回退 VW0。

### 5.3 单品种单 tier 目标仓位（未压仓前）

```
notional_target(tier, sym, t)
  = w_dir(direction(tier))
  × w_strength(tier, t)
  × ( RiskPerTrade / (K_SL(tier) × entry_atr_bps / 10000) )
  × Equity(t)
```

其中：
- `RiskPerTrade = 0.02`（§7 单笔 2% 风控）
- `K_SL(tier)` = §3.2 的 SL 倍数（多头 1.0 / 空头 2.5）
- `entry_atr_bps / 10000` = ATR 占价格的比例（将 ATR 倍数转为价格距离分数）
- `Equity(t)` = t 时刻账户权益（阶段 0-2 用初始权益 + 累计 PnL 简化；阶段 3+ 走真实资金曲线）

解释：目标仓位 = 方向权重 × 强度权重 × 单笔 2% 风险对应的名义本金。
`RiskPerTrade / (K_SL × atr_frac)` 将"最大可承受损失金额"转换为"最大可承受名义暴露"：
SL 距离越大（K_SL 大 or ATR 大），单笔名义越小。

---

## 6. 交易成本（硬约束 · realistic-cost）

### 6.1 单边成本公式

```
cost_bps_oneway(sym, entry_price, size, entry_atr_bps)
  = commission_bps(sym, entry_price, size)
  + slippage_bps(sym, size)
```

其中：
- `commission_bps`：佣金（按 entry_price × size × 佣金率），查表 `workspace/common/contract_specs.py`
- `slippage_bps`：`slip_tick(sym) × tick_size(sym) × size / entry_price × 10000`（slip_tick 默认 1 tick）
- 成本单位：bps of entry_notional = entry_price × size（与 §2 entry_atr 一致，可直接比较）

### 6.2 交易成本 ATR 倍率（诊断用）

```
cost_atr = cost_bps_oneway / entry_atr_bps
```

用于归档与阶段报告（参考 structural-shaping-alpha KF-5：5m 期货平均 0.225 ATR/单边）。

### 6.3 净 PnL

```
pnl_net = pnl_gross − cost_bps_oneway(entry) − cost_bps_oneway(exit)
        = pnl_gross − 2 × cost_bps_oneway（近似：entry≈exit 时）
```

---

## 7. 风控（硬约束）

### 7.1 单笔止损 = 2% 权益

这是 §5.3 仓位公式的输入（不是事后检查）。
**事后保护**：若 pnl_gross 的 SL 触发价对应的损失 > 2.1%（含滑点偏离），则按 SL 执行。

### 7.2 总名义暴露 = 100% 权益上限

```
Σ_{所有持仓 i} |notional_i(t)| ≤ 1.0 × Equity(t)
```

超时时按以下优先级砍仓（压仓算法，阶段 0-1 默认 · 阶段 2 可微调）：
1. 先砍 `w_strength` 最低的持仓
2. 再砍离到期最近的持仓
3. 最后按先进先出（FIFO）

### 7.3 保证金约束（自动满足，不做主动约束）

期货保证金率 5%~12% → 100% 名义暴露 = 5~12 保证金占用 ≤ 80% 约束。
阶段 0-3 不做主动保证金管理。

### 7.4 单日最大损失熔断（阶段 2+ 启用，默认关闭，可选）

```
IF daily_pnl(t) ≤ −5% Equity(t) THEN
  当日剩余时间不开新仓（已有仓按原退出规则执行）
```

---

## 8. 事件并发与去重（硬约束）

### 8.1 合约内去重

同一合约 `8h dedup`：8 小时内只接受第一个 tier ≠ 未分类 的信号，
后续信号一律忽略。与 KF-poc-va-04（事件重叠是 bias 源）一致。

### 8.2 多 tier 并发

同一时刻同一合约只能匹配唯一 tier（§1.2 互斥），不存在多 tier 并发。
跨品种并发允许（但被 §7.2 名义暴露约束聚合压仓）。

### 8.3 多空互斥

同一合约同一时刻不可能同时触发多域 tier 和空域 tier（skew ≤ 0.30 与 skew ≥ 0.60
严格互斥），不做自对冲逻辑。跨品种多空并存允许。

---

## 9. 归因（硬约束 · KF-9）

任何「某方案 mean > 0」的报告，必须同时报告：

```
μ         = mean(pnl_gross_bps)   # 平均毛收益（bps）
σ²        = var(pnl_gross_bps)    # 毛收益方差
ν_implied = μ − σ² / 2            # Itô 修正后的真实漂移
p(ν > 0)  = cluster bootstrap 概率（(contract, date) 单位）
```

只有 `ν_implied > 0` 且 `p(ν > 0) ≥ 0.95` 才可判为「真实正 edge」。

---

## 10. 输出（trade 明细字段）

阶段 0+ 所有实验输出 trade-level parquet，至少含：

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| contract | str | 合约（如 DCE.m2601） |
| symbol | str | 品种前缀（如 m） |
| symbol_type | str | A/B/C |
| entry_bar | datetime | 入场 bar 时间 |
| exit_bar | datetime | 出场 bar 时间 |
| direction | int8 | +1 多 / −1 空 |
| tier | str | L_seg3_lowmid_up 等 |
| entry_price | float64 | 入场价 |
| exit_price | float64 | 出场价 |
| exit_reason | str | SL / TIME / MARGIN_CUT（压仓） |
| entry_atr_bps | float64 | 入场 ATR（bps） |
| qty_raw | float64 | 压仓前数量（合约张数） |
| qty_actual | float64 | 压仓后实际数量 |
| w_strength | float64 | §5.1 权重 |
| w_dir | float64 | §5.2 权重 |
| pnl_gross_bps | float64 | 毛收益（bps） |
| cost_entry_bps | float64 | 入场成本（bps of notional） |
| cost_exit_bps | float64 | 出场成本（bps） |
| pnl_net_bps | float64 | 净收益（bps） |
| pnl_net_ccy | float64 | 净收益（计价币，按合约乘数换算） |
| equity_before | float64 | 入场前账户权益 |
| equity_after | float64 | 出场后账户权益 |

阶段 0-2 可用简化权益模型（initial_equity + 累计 pnl_net_ccy）。
阶段 3+ 必须按时间顺序结算（含持仓估值）。
