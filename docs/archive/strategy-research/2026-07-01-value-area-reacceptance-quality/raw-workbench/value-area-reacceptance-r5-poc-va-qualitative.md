# value_area_reacceptance R5：POC / VA 定义定性诊断实验报告

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-06-30
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r4-period-sensitivity.md](./value-area-reacceptance-r4-period-sensitivity.md)

## 1. 实验问题

R3 和 R4 后，阶段计划已将实验线 C 从“继续寻找 reaccept 深度归一化参数”修正为：

```text
reaccept 深度、POC 与价值区定义诊断。
```

本轮不跑新参数，不改策略代码，只使用已有 5m 主线样本，回答：

```text
1. 当前 POC / VA 是否足以解释“共识价格区间”？
2. 2~3 ticks 敏感性是否更像真实接受深度，还是 POC / VA 锚点脆弱的表现？
3. DCE.m、SR、rb 的差异是否能通过 POC 空间、VA 宽度、POC 位置解释？
```

## 2. 数据来源

本轮使用已有 5m 主线与对照回测：

| backtest_id | symbol | ticks | 用途 |
|-------------|--------|-------|------|
| 401 | DCE.m2601 | 2 | 主线样本 |
| 402 | DCE.m2601 | 3 | 主线样本 |
| 403 | CZCE.SR601 | 2 | 观察样本 |
| 404 | CZCE.SR601 | 3 | 观察样本 |
| 409 | SHFE.rb2601 | 2 | 负面对照 |
| 410 | SHFE.rb2601 | 3 | 负面对照 |

抽取字段来自：

```text
backtest_trades.decision_payload_json.diagnostics.strategy
trade_clearings
```

核心派生字段：

```text
VA width = VAH - VAL；
target_dist = abs(target_price - entry_price)；
target_to_va = target_dist / VA width；
reaccept_depth_pct = entry 在重新接受方向进入 VA 的比例；
poc_pct = (POC - VAL) / VA width；
raw_rr = target_dist / strict_failure_distance；
exit_type = close_reason 前缀；
net_pnl = 清算后净盈亏。
```

## 3. 汇总结果

| symbol | ticks | n | avg_va_width | avg_target_dist | avg_target_to_va | avg_reaccept_depth_pct | avg_poc_pct | avg_raw_rr | win_pct | tp_n | time_n | force_n | net_pnl |
|--------|-------|---|--------------|-----------------|------------------|------------------------|-------------|------------|---------|------|--------|---------|---------|
| CZCE.SR601 | 2 | 9 | 20.78 | 10.33 | 0.583 | 0.156 | 0.327 | 0.785 | 55.56% | 2 | 5 | 2 | 213.4 |
| CZCE.SR601 | 3 | 6 | 24.83 | 11.17 | 0.529 | 0.164 | 0.351 | 0.769 | 50.00% | 1 | 4 | 1 | 882.8 |
| DCE.m2601 | 2 | 6 | 23.83 | 13.50 | 0.585 | 0.124 | 0.295 | 1.368 | 50.00% | 2 | 3 | 1 | 3516.8 |
| DCE.m2601 | 3 | 5 | 24.80 | 14.00 | 0.585 | 0.150 | 0.270 | 1.388 | 40.00% | 2 | 3 | 0 | 2392.8 |
| SHFE.rb2601 | 2 | 8 | 23.88 | 13.38 | 0.612 | 0.118 | 0.538 | 1.007 | 25.00% | 2 | 4 | 0 | -3314.18 |
| SHFE.rb2601 | 3 | 7 | 23.57 | 13.00 | 0.594 | 0.174 | 0.549 | 0.886 | 42.86% | 3 | 3 | 0 | -1801.41 |

## 4. 胜负样本对照

| symbol | ticks | outcome | n | avg_va_width | avg_target_dist | avg_target_to_va | avg_reaccept_depth_pct | avg_poc_pct | avg_raw_rr | avg_pnl | tp_n |
|--------|-------|---------|---|--------------|-----------------|------------------|------------------------|-------------|------------|---------|------|
| CZCE.SR601 | 2 | loss | 4 | 16.25 | 10.50 | 0.659 | 0.183 | 0.401 | 0.917 | -472.40 | 0 |
| CZCE.SR601 | 2 | win | 5 | 24.40 | 10.20 | 0.523 | 0.135 | 0.268 | 0.679 | 420.60 | 2 |
| CZCE.SR601 | 3 | loss | 3 | 18.67 | 13.00 | 0.702 | 0.198 | 0.312 | 0.861 | -309.27 | 0 |
| CZCE.SR601 | 3 | win | 3 | 31.00 | 9.33 | 0.355 | 0.130 | 0.391 | 0.677 | 603.53 | 1 |
| DCE.m2601 | 2 | loss | 3 | 22.33 | 14.67 | 0.663 | 0.151 | 0.186 | 1.351 | -363.47 | 0 |
| DCE.m2601 | 2 | win | 3 | 25.33 | 12.33 | 0.507 | 0.098 | 0.404 | 1.384 | 1535.73 | 2 |
| DCE.m2601 | 3 | loss | 3 | 22.33 | 14.67 | 0.663 | 0.151 | 0.186 | 1.351 | -363.47 | 0 |
| DCE.m2601 | 3 | win | 2 | 28.50 | 13.00 | 0.468 | 0.150 | 0.395 | 1.444 | 1741.60 | 2 |
| SHFE.rb2601 | 2 | loss | 6 | 21.33 | 14.00 | 0.665 | 0.123 | 0.486 | 0.998 | -812.23 | 0 |
| SHFE.rb2601 | 2 | win | 2 | 31.50 | 11.50 | 0.451 | 0.105 | 0.694 | 1.035 | 779.59 | 2 |
| SHFE.rb2601 | 3 | loss | 4 | 21.75 | 15.50 | 0.712 | 0.171 | 0.430 | 0.892 | -871.65 | 0 |
| SHFE.rb2601 | 3 | win | 3 | 26.00 | 9.67 | 0.437 | 0.178 | 0.707 | 0.878 | 561.73 | 3 |

## 5. 目标空间分桶

按 `target_to_va = abs(target-entry)/(VAH-VAL)` 分桶：

| symbol | ticks | target_bucket | n | win_pct | tp_n | net_pnl | avg_raw_rr |
|--------|-------|---------------|---|---------|------|---------|------------|
| CZCE.SR601 | 2 | target_lt_50pct_va | 2 | 100.00% | 0 | 996.6 | 0.708 |
| CZCE.SR601 | 2 | target_50_65pct_va | 4 | 25.00% | 1 | -651.0 | 0.750 |
| CZCE.SR601 | 2 | target_ge_65pct_va | 3 | 66.67% | 1 | -132.2 | 0.882 |
| CZCE.SR601 | 3 | target_lt_50pct_va | 2 | 100.00% | 0 | 996.6 | 0.708 |
| CZCE.SR601 | 3 | target_50_65pct_va | 3 | 33.33% | 1 | 57.8 | 0.833 |
| CZCE.SR601 | 3 | target_ge_65pct_va | 1 | 0.00% | 0 | -171.6 | 0.700 |
| DCE.m2601 | 2 | target_lt_50pct_va | 2 | 100.00% | 1 | 3425.6 | 1.291 |
| DCE.m2601 | 2 | target_50_65pct_va | 2 | 50.00% | 1 | 963.2 | 1.619 |
| DCE.m2601 | 2 | target_ge_65pct_va | 2 | 0.00% | 0 | -872.0 | 1.193 |
| DCE.m2601 | 3 | target_lt_50pct_va | 1 | 100.00% | 1 | 2581.6 | 1.889 |
| DCE.m2601 | 3 | target_50_65pct_va | 2 | 50.00% | 1 | 683.2 | 1.333 |
| DCE.m2601 | 3 | target_ge_65pct_va | 2 | 0.00% | 0 | -872.0 | 1.193 |
| SHFE.rb2601 | 2 | target_lt_50pct_va | 2 | 50.00% | 1 | -911.09 | 1.150 |
| SHFE.rb2601 | 2 | target_50_65pct_va | 3 | 33.33% | 1 | 547.76 | 0.923 |
| SHFE.rb2601 | 2 | target_ge_65pct_va | 3 | 0.00% | 0 | -2950.84 | 0.995 |
| SHFE.rb2601 | 3 | target_lt_50pct_va | 1 | 100.00% | 1 | 711.52 | 1.300 |
| SHFE.rb2601 | 3 | target_50_65pct_va | 3 | 66.67% | 2 | 868.01 | 0.778 |
| SHFE.rb2601 | 3 | target_ge_65pct_va | 3 | 0.00% | 0 | -3380.94 | 0.856 |

## 6. 定性发现

### 6.1 raw_rr 本身不是充分解释变量

DCE.m 的 raw_rr 明显好于 SR：

```text
DCE.m2601: avg_raw_rr ≈ 1.37~1.39；
CZCE.SR601: avg_raw_rr ≈ 0.77~0.79。
```

这解释了为什么 DCE.m 是当前主线、SR 只能观察。

但 raw_rr 不是充分条件：

```text
DCE.m 亏损样本 avg_raw_rr 仍有 1.351；
rb 也有 avg_raw_rr 接近或高于 1，但整体仍失败。
```

说明仅仅“到 POC 有空间”不够，POC 是否可达、是否是合适共识锚点更关键。

### 6.2 大 target_to_va 不是好事，反而可能是风险信号

三个品种都有类似现象：

```text
target_to_va >= 65% 的样本表现很差。
```

尤其是：

```text
DCE.m2601 / target_ge_65pct_va: 4 笔，0% 胜率，0 次 take_profit；
SHFE.rb2601 / target_ge_65pct_va: 6 笔，0% 胜率，0 次 take_profit。
```

这与“目标空间越大越好”的直觉相反。更合理的解释是：

```text
当 entry 到 POC 距离占 VA 宽度过大时，
POC 可能已经不是短期可回归锚点，
或者这代表价格重新接受位置距离 POC 太远，
短持仓窗口内难以兑现。
```

因此，POC 不能只作为单点目标，还需要结合 VA 内部位置解释。

### 6.3 盈利样本更偏向“中等 POC 空间”，而非最大 POC 空间

DCE.m 的盈利样本：

```text
avg_target_to_va: win 约 0.47~0.51；loss 约 0.66；
```

SR 和 rb 也大致相似：盈利样本的 `target_to_va` 往往低于亏损样本。

这说明当前结构更像：

```text
边界失败后，价格回到价值区内部较近的共识锚；
而不是从边界一路穿越大半个 VA 去打远端 POC。
```

这支持后续考虑 `POC band` 或 `内部目标带`，而不是把单点 POC 视为越远越好的目标。

### 6.4 POC 在 VA 内部的位置存在品种差异

平均 POC 分位：

```text
DCE.m2601: avg_poc_pct ≈ 0.27~0.30；
CZCE.SR601: avg_poc_pct ≈ 0.33~0.35；
SHFE.rb2601: avg_poc_pct ≈ 0.54~0.55。
```

rb 的 POC 更接近 VA 中部，但策略仍失败。这说明：

```text
POC 位置居中不等于可交易；
当前 close-profile POC 可能只是成交密集位置，不一定代表可回归的短期共识锚。
```

### 6.5 tick 敏感性更像 POC / VA 锚点脆弱，而不是精确 tick 阈值

R3 的 2~3 ticks 现象仍重要，但本轮显示：

```text
重新接受深度本身的比例差异并不大；
胜负差异更多体现在 target_to_va、POC 可达性、退出兑现上；
POC 若作为单点目标偏远或不稳定，会使 1~2 ticks 的入场差异被放大。
```

因此，当前不能把 `min_reaccept_ticks = 2~3` 解释成稳定市场规律。更稳妥的阶段结论是：

```text
2~3 ticks 是当前 POC / VA 定义下对贴边噪声的经验补偿；
它提示 POC / VA 定义需要更严格解释，而不是马上继续调参。
```

## 7. 对后续实验线 C 的影响

本轮支持阶段计划中的修正：

```text
C 线不应继续扩大 fixed ticks 网格；
也不应立即切换交易周期；
应优先审查 POC / VA 是否足以表达共识价格区间。
```

下一步更有价值的是：

```text
1. 对 DCE.m 盈利/亏损样本做逐笔图形复盘，确认 POC 是否真是可回归锚点；
2. 把 target_to_va 作为定性质量标签，而不是简单追求更大 POC 空间；
3. 检查 POC band 或内部目标带是否比单点 POC 更符合实际；
4. 对比 close-profile 与 range-profile 只作为解释性诊断，不作为收益调参；
5. 若需要新增字段，优先记录 VA shape / POC stability / target_to_va，而不是直接增加新参数。
```

## 8. 本轮结论

```text
当前 POC / VA 定义具备一定解释力，但不足以作为严格、稳定的共识价格区间定义。
```

更具体地说：

```text
DCE.m 的优势主要来自更好的 raw_rr 和较好的 POC 兑现，但亏损样本说明远 POC 并不可靠；
SR 的 POC 空间和成本结构偏薄，3 ticks 改善不能掩盖 POC 兑现不稳定；
rb 即使 POC 位于 VA 中部也不能形成正期望，说明单一 POC 位置不是充分解释变量；
2~3 ticks 敏感性应作为 POC / VA 锚点脆弱性的证据，而不是参数优化目标。
```

阶段判断：

```text
保留 5m 执行周期；
保留 DCE.m2601 为主线观察；
不扩大 fixed ticks 参数；
不直接进入尾部/成本压力测试前的大规模参数验证；
下一步先做 POC / VA 逐笔定性复盘或补充 VA shape / POC stability 诊断字段。
```
