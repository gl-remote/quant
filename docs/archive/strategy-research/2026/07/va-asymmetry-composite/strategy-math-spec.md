# va-asymmetry-composite · Strategy Math Spec

> 类型：Strategy Math Spec
> 版本：v1.0（B0 冻结版 · 阶段 1 降级后冻结）
> 最近更新：2026-07-10
> 上游分类器：theme:poc-value-area-asymmetry#classifier-math-spec v4.0
> 塑形参考：theme:structural-shaping-alpha#first-passage-designer-math-spec
> 决策依据：research-status.md（阶段 1 降级 · B0 即最优 · 待工程化）

## 0. 版本状态 & 冻结规则

**v1.0 = B0 冻结版**。阶段 0 复现 + 阶段 1 三大方向 Gatekeeper 已结束，结论：
组合层（品种筛选 / 强度加权 / 多空权重）**0/6 增量夏普通过**，B0 = S1×W0×VW0
即最优（年化 15.10% · 夏普 2.70 · MaxDD −2.40%）。本版将 B0 锁死为工程化契约，
将已证伪的组合轴降级为审计附录（§11），并把主题下一步的真实杠杆重定向到
**名义暴露上限**（§7.2）与**事件层选择**（§8 / §12）。

> 方法论注：组合层 0/6 是「优化权重跑不赢朴素 1/N 等权」谜题的复现——估计误差下
> 组合权重难稳定超越等权，并非意外利好。因此本版不再把组合层当开放优化问题，
> 而是把研究精力转向组合层之外的杠杆（见 §12）。

**硬约束（不随实验变更）**：
- 分类器 tier 定义严格继承 v4.0（§1）
- ATR 归一化单位（§2）
- Realistic-cost 口径（§6）
- 单笔止损 2%（§7.1）

**B0 锁定配置（v1.0 唯一定义源）**：
- §4 品种筛选 = **S1**（全品种 5 档，不含 L_seg2_low_flat）
- §5.1 强度加权 = **W0**（等权，w = 1.0）
- §5.2 多空权重 = **VW0**（等权，w_L = w_S = 1.0）
- §3 塑形 = 基线（多头 SL 1.0 ATR·8h / 空头 SL 2.5 ATR·10h / 无 Trailing / 无硬 TP）

**可调参数（仅剩两个研究轴 · 见 §12）**：
- 名义暴露上限 `Cap ∈ {100%, 120%, 200%, 400%}`（§7.2，主杠杆，path B）
- 合约内去重窗口 `∈ {4h, 8h, 12h}`（§8.1，次杠杆）
- §3 塑形参数在 ±30% 平台内做描述性敏感性（不计入 gatekeeper）

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
| L_seg2_low_flat | 多 | (0.09, 0.19] | [0.00, 0.33] | (0.20, 0.75) | ❌（已淘汰 · IR<0） |
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

## 3. 交易执行 · 塑形（B0 基线参数 · 冻结）

### 3.1 入场

- 时刻：t = 分类器 tier 匹配的 1h bar close（整点）
- 成交价：`close_t`（理论价；工程化时改用下一 bar `open_{t+1}` + 滑点修正）
- 方向：tier 决定（多域 tier = 做多，空域 tier = 做空）
- 数量：见 §5 仓位计算（B0 下 w_dir = w_strength = 1.0，仅受 §7.2 名义上限压仓）

### 3.2 止损（SL）

| tier 类型 | SL（entry_atr 倍数） |
|:---|:---:|
| L_*（多头 tier） | **K_L^SL = 1.0** |
| S_*（空头 tier） | **K_S^SL = 2.5** |

止损触发价：
```
P_SL^long  = entry_price − K_L^SL × entry_atr_bps × entry_price / 10000
P_SL^short = entry_price + K_S^SL × entry_atr_bps × entry_price / 10000
```

### 3.3 时间退出（Time Exit = 主止盈机制）

| tier 类型 | 持仓期（bar 数 @ 1h） |
|:---|:---:|
| L_*（多头 tier） | **H_L = 8** |
| S_*（空头 tier） | **H_S = 10** |

到达 H_L / H_S 小时后的第一根 1h bar 的 close 平仓（等价于第 H×12 根 5m bar 的 close）。
优先级：SL > 时间退出（同时触发取 SL）。

### 3.4 Trailing（不启用）

archive:2026-07-09-poc-va-shaping 已验证 10h 内 trailing 触发率 < 2%，
净效果为 0 或负。v1.0 **默认不启用 trailing**。

### 3.5 硬止盈（TP，不启用）

archive:2026-07-09-poc-va-shaping 已验证硬 TP 劣于纯时间退出。
v1.0 **默认不设硬 TP**。

> 塑形参数（K_L^SL / H_L / K_S^SL / H_S）在阶段 2 末尾做 ±30% 平台描述性敏感性
> （Low/Mid/High），属可调参数最后一项，不计入 gatekeeper（见 §0）。

---

## 4. 品种筛选（B0 = S1 锁定）

### 4.1 决策

- **B0 采用 S1（全品种 5 档）**：不做品种筛选，A/B/C 所有品种都用 5 档（不含 L_seg2_low_flat）。
- **S2（按类型 tier 映射）已证伪（KF-4）**：阶段 1 实测 S2 vs B0 净夏普增量
  `ΔSh = −0.27`，按类型筛选反而剔除盈利组合。故 S2 **不进入 B0**。
- S2 的历史类型映射表保留于 §11 审计附录（供复现），不作为活动配置。

### 4.2 三大品种类型（仅作归因分组 · 继承 KF-24）

A/B/C 三类用于**归因报告**（implementation-notes §3 品种类型归因表），不再用于入参筛选。

| 类型 | 品种前缀 |
|:---|:---|
| A · 金融贵金属 | IF, IH, IC, IM, T, TF, TS, au, ag |
| B · 化工建材黑色 | rb, hc, i, j, jm, TA, MA, PP, pp, l, v, eb, eg, sc, fu, bu |
| C · 农产品有色主流 | cu, al, zn, ni, sn, pb, m, y, p, c, cs, CF, SR, OI, RM, FG |

**L_seg2_low_flat 默认淘汰**：archive 证塑形后 IR < 0；C 类专项补验结论见 §11。

---

## 5. 仓位与加权（B0 = W0×VW0 锁定）

### 5.1 信号强度加权 → W0 等权锁定

B0 采用 **W0（w = 1.0 恒等）**。W1/W2/W3 在阶段 1 测试（KF-1 / KF-2）：W1 与收益无区分度
（ΔSh = +0.00），三者均未达 ≥ 0.2 增量门槛，已降级。公式见 §11 附录（审计）。

### 5.2 多空权重 → VW0 等权锁定

B0 采用 **VW0（w_L = w_S = 1.0）**。VW1（IR 比例）/ VW2（频率平衡）阶段 1 未达增量门槛
（KF-1），已降级。公式见 §11 附录。

### 5.3 单品种单 tier 目标仓位（未压仓前）

```
notional_target(tier, sym, t)
  = w_dir(direction(tier))        # B0: = 1.0
  × w_strength(tier, t)           # B0: = 1.0
  × ( RiskPerTrade / (K_SL(tier) × entry_atr_bps / 10000) )
  × Equity(t)
```

其中：
- `RiskPerTrade = 0.02`（§7.1 单笔 2% 风控）
- `K_SL(tier)` = §3.2 的 SL 倍数（多头 1.0 / 空头 2.5）
- `entry_atr_bps / 10000` = ATR 占价格的比例（将 ATR 倍数转为价格距离分数）
- `Equity(t)` = t 时刻账户权益

解释：目标仓位 = 方向权重 × 强度权重 × 单笔 2% 风险对应的名义本金。
B0 下前两项均为 1.0，退化为 `RiskPerTrade / (K_SL × atr_frac) × Equity`。
`RiskPerTrade / (K_SL × atr_frac)` 将「最大可承受损失金额」转换为「最大可承受名义暴露」：
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

## 7. 风控

### 7.1 单笔止损 = 2% 权益（硬约束）

这是 §5.3 仓位公式的输入（不是事后检查）。
**事后保护**：若 pnl_gross 的 SL 触发价对应的损失 > 2.1%（含滑点偏离），则按 SL 执行。

### 7.2 总名义暴露上限（B0 默认 100% · 主题主研究杠杆）

B0 契约默认：
```
Σ_{所有持仓 i} |notional_i(t)| ≤ 1.0 × Equity(t)
```

但 archive 显示策略**日均名义暴露达 653%**，压到 100% 切掉约 85% 交易——这是年化
卡在 15.10%、未达 18% 目标的核心瓶颈（risk 6.3）。因此 **名义上限本身不视为不可动摇的
硬约束，而是主题前推的首要可调轴（path B）**：

| Cap | 含义 | 预期 / 状态 |
|:---|:---|:---|
| **100%（B0 默认）** | 当前契约 | 年化 15.10% · 夏普 2.70 · MaxDD −2.40% |
| 120% | path B 第一步 | 观察年化是否逼近 18% 且 MaxDD 可控 |
| 200% / 400% | 探索性 | 量化暴露压缩对夏普/年化的真实代价 |

超出时的砍仓优先级（压仓算法）保持不变：
1. 先砍 `w_strength` 最低的持仓（B0 下全为 1.0，退化为随机/顺序）
2. 再砍离到期最近的持仓
3. 最后按先进先出（FIFO）

### 7.3 保证金约束（自动满足，不做主动约束）

期货保证金率 5%~12% → 100% 名义暴露 = 5~12% 保证金占用 ≤ 80% 约束。
提高名义上限至 120%~400% 时，保证金占用按比例上升，仍低于 80% 约束上限，阶段内不做主动管理。

### 7.4 单日最大损失熔断（可选 · 默认关闭）

```
IF daily_pnl(t) ≤ −5% Equity(t) THEN
  当日剩余时间不开新仓（已有仓按原退出规则执行）
```

---

## 8. 事件并发与去重

### 8.1 合约内去重（可调窗口 · 次杠杆）

同一合约去重窗口内只接受第一个 tier ≠ 未分类 的信号，后续信号一律忽略。
与 KF-poc-va-04（事件重叠是 bias 源）一致。

- **B0 默认：8h 去重**
- **次研究杠杆**：窗口可放宽至 4h / 12h 做敏感性（§12），属于「事件选择/择时」旋钮，
  不触碰 v4.0 分类器契约。

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
| w_strength | float64 | §5.1 权重（B0 = 1.0） |
| w_dir | float64 | §5.2 权重（B0 = 1.0） |
| pnl_gross_bps | float64 | 毛收益（bps） |
| cost_entry_bps | float64 | 入场成本（bps of notional） |
| cost_exit_bps | float64 | 出场成本（bps） |
| pnl_net_bps | float64 | 净收益（bps） |
| pnl_net_ccy | float64 | 净收益（计价币，按合约乘数换算） |
| equity_before | float64 | 入场前账户权益 |
| equity_after | float64 | 出场后账户权益 |

阶段 0-2 可用简化权益模型（initial_equity + 累计 pnl_net_ccy）。
阶段 3+ 必须按时间顺序结算（含持仓估值）。

---

## 11. 已证伪 / 未通过组合轴（审计附录）

本附录保留阶段 1 测试过的组合轴公式与结论，**供复现与审计，不作为 B0 活动配置**。

### 11.1 S2 · 按类型 tier 映射（证伪 · KF-4）

类型 × 默认启用 tier 子集（历史定义，已不采用）：

| 类型 | 默认启用 tier 子集 |
|:---|:---|
| A | L_seg12_high_up, S_seg12_high_dn |
| B | L_seg3_lowmid_up, S_seg34_high_dn |
| C | L_seg3_lowmid_up, L_seg12_high_up, S_seg12_high_dn, S_seg34_high_dn, S_seg2_mid_dn（+ L_seg2_low_flat 补验） |

结论：S2 vs B0 净夏普增量 `ΔSh = −0.27`，反向拖累 → 不采用。

### 11.2 W1 / W2 / W3 · 信号强度加权（未通过 · KF-1 / KF-2）

| 方案 | 公式 w_strength(tier, t) ∈ [0.2, 1.0] | 结论 |
|:---|:---|:---|
| W1 · Skew 距离 | `clamp( \|skew_rank − thr_skew\| / \|thr_skew − 0.5 × thr_skew\|, 0.2, 1.0 )`，thr_skew = tier 对应 skew 段最近端点（多 0.30/0.19，空 0.60/0.81） | KF-2：与收益无区分度，ΔSh = +0.00 |
| W2 · ATR 匹配 | `clamp( 1 − 4 × \|atr_rank − 0.50\|, 0.2, 1.0 )` | 未达 ≥0.2 增量 |
| W3 · 三维乘积 | `w1=clamp(W1式); w2=clamp(W2式); w3=clamp(1 − 2×\|trend_rank − t_center\|, 0.2, 1.0); w=clamp(w1×w2×w3)`；t_center = 多 0.875 / 空 0.10 | 未达 ≥0.2 增量 |

### 11.3 VW1 / VW2 · 多空权重（未通过 · KF-1）

| 方案 | 公式 w_dir | 结论 |
|:---|:---|:---|
| VW1 · IR 比例 | `w_L = IR_L̄ / IR_max · w_S = IR_S̄ / IR_max`，IR_max = max(IR_L̄, IR_S̄)，clamp [0.5, 1.0] | 未达 ≥0.2 增量 |
| VW2 · 频率平衡 | `w_L = sqrt(N_S / N_L) · w_S = sqrt(N_L / N_S)`，clamp [0.5, 2.0] | 未达 ≥0.2 增量 |

### 11.4 L_seg2_low_flat × C 类补验（淘汰）

archive 证塑形后 IR < 0，全品种默认淘汰。阶段 1 末尾 C 类专项补验未翻转结论，
维持淘汰；C 类白名单不追加。

---

## 12. 主题前推的开放杠杆（Open Forward Levers）

组合层已证无增量（0/6，§11）。下一步**不应**在组合层加更多权重/筛选方案
（1/N 等权谜题：估计误差下组合权重难稳定超越等权）。真实杠杆在组合层之外：

1. **名义暴露上限敏感性（主杠杆）**：§7.2 的 100 / 120 / 200 / 400% 扫描。
   目标把年化推过 18% 且 MaxDD 不破 8%——这是 path B 的实验设计，也是
   年化未达标的高概率根因（653% → 100% 压缩砍掉 85% 交易）。
2. **事件层选择 / 择时（次杠杆）**：在 v4.0 分类器契约不变前提下，唯一可调的事件层
   旋钮是 §8.1 的合约内去重窗口（4h / 8h / 12h）与事件并发密度。这属于「事件选择」
   而非「组合加权」，是组合层 exhausted 后更可能的真实杠杆来源。
3. **（可选）B0 样本外重验**：阶段 3 OOS 双维度（品种 LGO + 时间 TS）在 B0 上重跑，
   确认样本外稳定后再进入阶段 4 工程化（path A）。

> 本版（v1.0）冻结 B0 作为工程化契约；上述杠杆作为主题继续推进的实验清单，
> 不改动 §1/§2/§3/§6/§9 的硬约束。
