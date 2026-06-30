# value_area_reacceptance R9：POC 质量标签分桶诊断

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-06-30
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r8-profile-definition-contrast.md](./value-area-reacceptance-r8-profile-definition-contrast.md)

## 1. 实验问题

R8 已确认：

```text
close-profile POC 不是完全错误，
但单点 POC 无法处理多峰；
range-profile 不能直接替代 close-profile；
naive 全局 POC band 容易产生假阳性。
```

本轮继续实验线 C，不调参、不新增回测，而是给已有样本计算 POC 质量标签并分桶，回答：

```text
1. 哪些 POC 质量标签最能解释 POC 兑现和净收益；
2. 哪些标签只是噪声或需要进一步定义；
3. 后续是否应该进入局部连续 POC acceptance node 的实现；
4. 哪些标签可以先作为诊断字段，而不是硬过滤条件。
```

## 2. 样本范围

使用 R5/R6/R8 同一批 5m 回测样本：

```text
DCE.m2601: 401 / 402
CZCE.SR601: 403 / 404
SHFE.rb2601: 409 / 410
```

说明：

```text
2 ticks 和 3 ticks 结果有部分重复事件，
因此本轮分桶只用于解释性诊断，
不把统计数当作独立大样本显著性证据。
```

## 3. 标签定义

本轮计算以下标签。

### 3.1 POC edge distance

```text
poc_pct = (POC - VAL) / (VAH - VAL)
poc_edge = min(poc_pct, 1 - poc_pct)
```

分桶：

```text
edge: poc_edge < 0.20
mid_edge: 0.20 <= poc_edge < 0.35
central: poc_edge >= 0.35
```

### 3.2 POC local band

使用 close-profile，在 POC 附近向相邻 tick 扩展：

```text
local_band = 以 POC 为中心，
向左右连续扩展到 volume < POC_volume * 50% 为止。
```

分桶：

```text
tight: local_band_width / VA_width <= 0.10
medium: <= 0.25
wide: > 0.25
```

注意：

```text
这是局部连续 band，
不是 R8 中已经否定的 global high-volume min~max band。
```

### 3.3 multi-modal profile flag

在 close-profile 中，取：

```text
volume >= top_volume * 70%
```

如果这些高成交价格形成两个及以上不连续组件：

```text
multi_modal = True
```

### 3.4 close-vs-range POC divergence

```text
close_range_divergence = abs(close_poc - range_poc) / VA_width
```

分桶：

```text
low: <= 0.20
medium: <= 0.50
high: > 0.50
```

### 3.5 current-day acceptance migration

用入场前最近若干 5m close 的中位数近似当前日接受位置：

```text
migration_ratio = abs(recent_close_median - previous_POC) / VA_width
```

分桶：

```text
near_poc: <= 0.30
mid: <= 0.70
away: > 0.70
```

该标签用于观察：

```text
当前日是否已经形成背离旧 POC 的新接受区。
```

## 4. 全样本标签分桶结果

### 4.1 POC edge distance

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_target_to_va | avg_raw_rr |
|--------|---|---------|--------|-------------|---------|------------------|------------|
| central | 8 | 87.5% | 50.0% | 62.5% | 6498.424 | 0.359 | 1.175 |
| mid_edge | 17 | 52.9% | 41.2% | 52.9% | 4256.566 | 0.545 | 0.927 |
| edge | 16 | 12.5% | 6.2% | 6.2% | -8864.784 | 0.736 | 0.995 |

结论：

```text
POC edge distance 仍是最强的质量标签。
```

POC 靠边时，平均 `target_to_va` 明显偏大，POC hit 率和净收益都显著变差。

### 4.2 Current-day acceptance migration

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_target_to_va | avg_raw_rr |
|--------|---|---------|--------|-------------|---------|------------------|------------|
| near_poc | 2 | 100.0% | 100.0% | 100.0% | 1423.032 | 0.277 | 1.300 |
| mid | 17 | 70.6% | 41.2% | 58.8% | 6343.020 | 0.469 | 0.994 |
| away | 22 | 18.2% | 13.6% | 13.6% | -5875.846 | 0.699 | 0.981 |

结论：

```text
current-day acceptance migration 是另一个强解释变量。
```

当入场前当前日接受位置已经远离旧 POC 时，旧 POC 更像历史锚，不像短期可兑现目标。

### 4.3 POC local band width

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_target_to_va | avg_raw_rr |
|--------|---|---------|--------|-------------|---------|------------------|------------|
| medium | 5 | 60.0% | 60.0% | 60.0% | 1193.800 | 0.636 | 1.010 |
| tight | 36 | 41.7% | 25.0% | 33.3% | 696.406 | 0.576 | 1.001 |

结论：

```text
local band width 单独解释力不强。
```

原因是：

```text
POC local band 太窄不一定坏；
只要 POC 位置合理、当前日接受未迁移，单点 POC 也可以兑现。
```

DCE.m2601 就是反例：tight band 反而包含关键盈利样本。

### 4.4 Multi-modal profile

| multi_modal | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_target_to_va | avg_raw_rr |
|-------------|---|---------|--------|-------------|---------|------------------|------------|
| False | 11 | 63.6% | 36.4% | 63.6% | 162.708 | 0.498 | 0.842 |
| True | 30 | 36.7% | 26.7% | 26.7% | 1727.498 | 0.614 | 1.061 |

结论：

```text
multi_modal 会降低 POC hit 和胜率，
但不能单独决定净收益。
```

原因是：

```text
部分多峰样本仍可能有明确可兑现 POC；
多峰更适合作为“需要进一步解释”的警示标签，
而不是硬过滤。
```

### 4.5 Close-vs-range POC divergence

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_target_to_va | avg_raw_rr |
|--------|---|---------|--------|-------------|---------|------------------|------------|
| medium | 17 | 70.6% | 35.3% | 52.9% | 6794.732 | 0.493 | 0.942 |
| low | 23 | 26.1% | 26.1% | 26.1% | -4479.926 | 0.640 | 1.034 |
| high | 1 | 0.0% | 0.0% | 0.0% | -424.600 | 0.818 | 1.286 |

结论：

```text
close-vs-range POC divergence 不能简单理解为越小越好。
```

R8 已经说明：

```text
range-profile 有时会把短期可兑现目标推远；
close POC 与 range POC 背离，不一定表示 close POC 无效。
```

因此该标签只能作为结构警示，不适合作为当前硬过滤。

## 5. 分品种关键结果

### 5.1 POC edge distance 分品种

| symbol | bucket | n | win_pct | tp_pct | net_pnl |
|--------|--------|---|---------|--------|---------|
| DCE.m2601 | central | 3 | 100.0% | 66.7% | 6007.200 |
| DCE.m2601 | mid_edge | 6 | 33.3% | 33.3% | 619.200 |
| DCE.m2601 | edge | 2 | 0.0% | 0.0% | -716.800 |
| CZCE.SR601 | mid_edge | 5 | 80.0% | 40.0% | 2221.600 |
| CZCE.SR601 | central | 2 | 100.0% | 0.0% | 690.800 |
| CZCE.SR601 | edge | 8 | 25.0% | 12.5% | -1816.200 |
| SHFE.rb2601 | mid_edge | 6 | 50.0% | 50.0% | 1415.766 |
| SHFE.rb2601 | central | 3 | 66.7% | 66.7% | -199.576 |
| SHFE.rb2601 | edge | 6 | 0.0% | 0.0% | -6331.784 |

诊断：

```text
POC edge 在三个品种上都是风险信号；
DCE.m 的优势集中在 central；
SR 的 mid_edge 也能赚钱，但稳定性弱于 DCE.m；
rb 即使 central 有时胜率不差，也会被左尾吞噬。
```

### 5.2 Current-day migration 分品种

| symbol | bucket | n | win_pct | tp_pct | net_pnl |
|--------|--------|---|---------|--------|---------|
| DCE.m2601 | mid | 6 | 66.7% | 50.0% | 6472.000 |
| DCE.m2601 | away | 5 | 20.0% | 20.0% | -562.400 |
| CZCE.SR601 | mid | 6 | 100.0% | 33.3% | 3621.200 |
| CZCE.SR601 | away | 9 | 22.2% | 11.1% | -2525.000 |
| SHFE.rb2601 | near_poc | 2 | 100.0% | 100.0% | 1423.032 |
| SHFE.rb2601 | mid | 5 | 40.0% | 40.0% | -3750.180 |
| SHFE.rb2601 | away | 8 | 12.5% | 12.5% | -2788.446 |

诊断：

```text
migration away 在三个品种上都明显偏差；
这与 R7 的图形复盘一致：
当前日接受区已经迁移后，旧 POC 很难在短窗口内兑现。
```

## 6. 关键发现

### 6.1 最强标签是 POC edge + current-day migration

R9 进一步确认：

```text
POC 靠边说明前日共识锚本身脆弱；
current-day migration away 说明旧 POC 已经被当前日价格接受过程抛开。
```

两者本质上回答同一个问题：

```text
这个 POC 还是不是短期可兑现的共识锚？
```

### 6.2 local band continuity 还需要重新定义

本轮的 local band 使用 `POC_volume * 50%` 的相邻连续价格扩展，结果大部分样本是 tight。

这说明：

```text
当前 local band width 口径还不够有区分度。
```

但它并不否定 POC acceptance node 的方向。更合理的后续定义可能需要：

```text
1. 以 POC 为中心；
2. 使用累计局部成交比例，而不是固定 50% 阈值；
3. 限制最大宽度；
4. 遇到多峰时只保留 POC 所在局部组件；
5. 区分“POC 单点可兑现”和“POC 附近接受带可兑现”。
```

### 6.3 Multi-modal 是警示标签，不是硬过滤

多峰样本整体 POC hit 更低，但净收益没有直接恶化到不可用。

因此：

```text
multi_modal 更像“需要解释”的图形复杂度标签，
不能简单删除所有多峰样本。
```

### 6.4 close-vs-range divergence 不能机械使用

本轮再次确认 R8 的发现：

```text
close-vs-range divergence 不适合直接做硬过滤。
```

因为：

```text
range-profile 不一定更接近短期可兑现目标；
close-profile 在部分关键样本上更符合路径兑现。
```

## 7. 阶段结论

R9 的结论是：

```text
POC 质量标签中，当前最有解释力的是：
1. POC edge distance；
2. current-day acceptance migration。
```

它们比 `local_band_width`、`multi_modal`、`close-vs-range divergence` 更接近当前策略的核心问题：

```text
旧 POC 是否仍是短期可兑现共识锚。
```

但这些标签仍应先用于解释和分桶，而不是立即写成硬过滤。原因是：

```text
样本数量小；
2 ticks / 3 ticks 有重复事件；
rb 的左尾说明 POC 质量不能单独证明方向 edge；
local band / POC acceptance node 的定义还需要更严格。
```

下一步建议：

```text
R10 做 POC 质量标签的最小实现方案设计：
只把标签写入诊断 payload / clearing 统计，
不改变交易信号，
用于后续更大样本验证。
```
