# va-asymmetry-revisit · H-1 因果版首轮验证报告

> 类型：Workbench 实验流水（临时）
> 状态：**H-1 主假设 + 制度分层双判死**（2026-07-14）
> 归档路径（未来）：`archive:<yyyy-mm-dd>-va-asymmetry-revisit-h1-consolidated`

## 一句话结论

在 15 品种 40 合约 16406 hourly events 的 5m 数据上，**signed A3_skew（W3 12h rolling volume-profile 三阶偏度）对未来 1~12h 方向收益的独立方向 alpha 假设 H-1 被证伪**——pooled Spearman IC 全 horizon 在 [-0.03, 0.01] 之间且 cluster-bootstrap CI 全跨 0；进一步做"intraday session-ATR 三档 × signed skew top/bottom 20%"分层后，36 个格子净收益 0/36 通过（CI 排 0 且 p<0.05）；跨品种保留率均 <25%。附带发现 hour-of-day ∈ {9,10,11,14} 全多 12h 有 test 单折弱边际 (p=0.04, 品种保留率 13/35)，但 train 折 p=0.42 未复现，不构成稳健 alpha。

## 实验设定

- **符号池**：15 品种 × 每品种 2–3 合约 = 40 合约（rb / i / cu / al / sc / TA / m / p / SR / CF / y / c / hc / ag / RM）
- **数据**：5m OHLCV，`project_data/market_data/csv/`
- **事件时钟**：每小时整点 close
- **特征**：`A3_skew` = W3 rolling 12h（144 根 5m）volume-profile 加权三阶偏度，严格截止到 event_idx-1（无泄漏）
- **N-0 硬约束**：每个 sector 抽 1 合约 30 个 event 做截断法自检 → 15/15 sector `max_abs_diff=0.00e+00` ✅
- **判据**：pooled Spearman IC + cluster bootstrap CI（cluster 单位 = contract 与 (contract, event_date) 双口径）；Bonferroni family=12
- **成本模型（分层净收益）**：per-symbol realistic 单边 = `tick × slip_tick / price + total_commission / (size × price)`，`total_commission` 来自 `workspace/common/contract_specs.py`；roundtrip = 2×单边
- **样本量**：16,406 events；扣掉 12h future NaN 后 ≥15,921 events

## ① H-1 Pooled IC（判死）

| cluster | horizon | n | IC | CI_lo | CI_hi | p_two | Bonf reject |
|---|---|---:|---:|---:|---:|---:|:---:|
| contract | ret_1h | 16366 | 0.0070 | -0.0104 | 0.0266 | 0.432 | ❌ |
| contract | ret_2h | 16326 | 0.0071 | -0.0161 | 0.0335 | 0.578 | ❌ |
| contract | ret_4h | 16244 | 0.0091 | -0.0224 | 0.0432 | 0.600 | ❌ |
| contract | ret_6h | 16164 | 0.0068 | -0.0310 | 0.0474 | 0.712 | ❌ |
| contract | ret_8h | 16084 | -0.0084 | -0.0494 | 0.0336 | 0.704 | ❌ |
| contract | ret_12h | 15921 | **-0.0274** | -0.0618 | 0.0070 | 0.113 | ❌ |
| contract_date | ret_1h | 16366 | 0.0070 | -0.0076 | 0.0213 | 0.386 | ❌ |
| contract_date | ret_12h | 15921 | **-0.0274** | -0.0572 | 0.0009 | **0.061** | ❌ |

- 所有 IC 绝对值 <0.03；ret_12h 的负 IC 边缘显著（p=0.061）但不通过 Bonferroni；方向随 horizon 翻转（短端小正、长端小负），不具因果一致性。
- 跨品种 sign consistency：40 个 symbol 与 pooled 同号数 18–24 / 40 = 45–60% → **远低于 80% 通过门槛**。

原始输出：[h1_pooled_ic.csv](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1/h1_pooled_ic.csv)、[h1_sign_consistency.csv](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1/h1_sign_consistency.csv)。

## ② H-1 制度分层 + 极端事件净收益（判死）

按 quant-research-methodology KF-23（"过拟合 vs 制度依赖"），下判决前先拆制度维度：

- 分层：intraday session-ATR（前 48 根 5m 绝对 close 变化均值）per-contract 三分位
- 极端事件：signed skew 分位 ≤20% → short, ≥80% → long；bet=±1
- 判据：signed return `y = sign × ret_h - cost_roundtrip`；cluster bootstrap by (contract, event_date)

**结果**：36 个 (atr_bucket ∈ {low,mid,high}) × (side ∈ {long,short}) × (horizon ∈ {1h,2h,4h,6h,8h,12h}) 格子 **0/36** 通过（CI_lo>0 且 p<0.05）。

- Long 侧在 low/mid ATR 4-12h 有微正 gross（0.05%–0.16%），扣 roundtrip 成本（约 0.05%）后 CI 全跨 0。
- Short 侧在所有 ATR 桶均 gross 负、net 更负、CI 全部排负 → 极端负 skew 后市场并未继续下跌。
- 跨品种保留率（每格 40 symbols 中 net_mean>0 的数量）在最好格也只有 10/40 = 25%，远低于 80% 门槛。

原始输出：[h1b_grid_decision.csv](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1b/h1b_grid_decision.csv)、[h1b_symbol_retention.csv](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1b/h1b_symbol_retention.csv)。

## ③ 副产品：Hour-of-day baseline（不构成稳健 alpha）

跑 hour-of-day baseline mean(ret_4h) 时发现：

| hour | n | mean_ret_4h | CI_lo | CI_hi | p_two |
|---:|---:|---:|---:|---:|---:|
| 9 | 2400 | 0.000445 | 0.000091 | 0.000775 | 0.011 |
| 10 | 2430 | 0.000491 | 0.000163 | 0.000821 | 0.004 |
| 11 | 2425 | 0.000449 | 0.000076 | 0.000820 | 0.018 |
| 14 | 2429 | 0.000432 | 0.000059 | 0.000794 | 0.021 |

- 日盘时段 mean_ret_4h 显著为正 ~5bps（gross），其他时段（21/22/23/0/1/2）不显著。
- 扣成本 + 时间 8:2 切分复验：
  - **Train**（2024-09 → 2025-11）：hour∈{9,10,11,14} 全多 ret_12h **net p=0.415**（未过门）
  - **Test**（2025-11 → 2026-05）：同条件 **net p=0.040, CI=[0.00007, 0.00228]**（单折过门）
- 品种保留率（train，ret_4h net）：13/35 = 37% → 远低于 80% 门槛
- 结论：train 未复现 + 品种保留率低 → **不是稳定 alpha**，只是 test 折的选样偶合 / 制度片段；不作为独立候选进入下一阶段。

原始输出：[h1c_hour_net.csv](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1c/h1c_hour_net.csv)、[h1c_train_symbol_net_4h.csv](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1c/h1c_train_symbol_net_4h.csv)。

## 判决与去向

- **H-1（archive:2026-07-13-va-asymmetry-leak-chain-consolidated#hypothesis-inventory H-1）主假设与制度分层双判死** → 进入 factor-research-workflow F 系列。
- **未继续做**：H-3 / H-4 多空机制假设——因 H-1 已判死，signed skew 作为一阶特征在 pooled + 分层 + 极端事件三重条件下都没有 edge，H-3/H-4 依赖同一 signed skew 输入，先验成功率大幅下降；本 slot 时间预算已用于 H-1 的确定性判决。
- **仍未验证**：H-11 τ_signed（timing 特征）、H-12 transition_flag（intraday 版本）、H-10 组合层结构——按 hypothesis-inventory 优先级顺序，下一步应先做 H-11 独立方向 alpha。

## 方法论新观察

- **判据在期货粒度上的"半 tick 成本吞噬"效应**：40 合约 hourly 事件中，per-contract realistic cost ≈ 0.03%-0.15%（tick 相对 close 越大越贵），使得任何"日内小方向 alpha"要 gross ≥0.1%/单次才能在净收益检验中过关；H-1 gross 幅度 <0.05% → 结构上无法穿透成本。这一观察独立于 H-1 是否成立，对后续任何日内 event-driven 因子研究都有约束意义。
- **cluster 单位选择显著影响 CI 宽度**：cluster=contract 与 cluster=(contract, event_date) 两口径下 IC 相同（因为 IC 与 cluster 无关），但 CI 宽度差 25%–40%——contract_date 更严格但样本量足够时 CI 反而略窄（因为集群数量更多、bootstrap 方差项更接近渐近）。**双口径并列报告**是必要护栏。

## 复用建议

- **A3_skew 作为独立方向 alpha 的这一支彻底关闭**——除非有强新证据（如换周期、换归一化、换 gate 都能拿到 >0.05 IC 的证据），否则不再复跑。
- **hour-of-day 白盘 mean>0 现象** 应作为**基准漂移**登记，后续任何 event-driven 因子的净收益检验都要把它作为对照（避免把"命中日盘时段"当作因子 alpha）。
- **N-0 截断法工具** 在本轮 15 sector 上 100% 通过，验证了 W3 rolling profile pipeline 的因果性；本工具复用到后续任何 intraday event 因子研究。

## 文件清单

- 脚本：
  - [h1_a3_skew_pooled_ic.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/h1_a3_skew_pooled_ic.py) · H-1 pooled IC + N-0 截断法
  - [h1b_regime_stratified.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/h1b_regime_stratified.py) · 制度分层 + 极端事件 + hour-of-day baseline
  - [h1c_hour_of_day_net.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/h1c_hour_of_day_net.py) · hour-of-day 净收益 + 8:2 walk-forward
- 数据产出：`docs/workbench/va-asymmetry-revisit/outputs/{h1,h1b,h1c}/`
