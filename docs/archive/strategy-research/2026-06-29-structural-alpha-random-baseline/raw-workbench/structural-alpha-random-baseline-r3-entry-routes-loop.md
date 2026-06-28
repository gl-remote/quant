# structural-alpha-random-baseline-r3-entry-routes-loop

> 类型：Workbench / 随机对照批量实验  
> 状态：阶段完成，`prevday_volume` 待单独处理  
> 日期：2026-06-28  
> 对应计划：[结构入口随机对照基准](../roadmap/strategy-random-entry-baseline-plan.md)  
> 前序：[价值区多 seed 随机对照](./structural-alpha-random-baseline-r2-value-area-multiseed.md)

## 1. 本轮目的

本阶段主任务不是继续优化价值区，也不是寻找新入口，而是按随机对照补充计划，把已经实现的结构入口逐个放入随机基准中。

本轮问题：

```text
除价值区外，其余已实现结构入口，
是否至少比匹配随机开仓更稳定、更收敛？
```

## 2. 本轮实现

新增通用随机对照基础设施：

```text
scripts/tools/run_structural_random_baselines.py
```

新增随机基线策略包装：

```text
workspace/strategies/prevday_random_baseline_strategy.py
workspace/strategies/volume_shock_random_baseline_strategy.py
workspace/strategies/prevday_volume_random_baseline_strategy.py
workspace/strategies/hourly_liquidity_random_baseline_strategy.py
workspace/strategies/low_volatility_random_baseline_strategy.py
```

并修正策略加载器：

```text
workspace/strategies/utils/loader.py
```

修正目的：当随机基线模块 import 原结构 core 时，`load_strategy()` 必须优先加载 `Strategy.name == 请求名` 的类，避免误加载被 import 进模块的原结构类。

## 3. 实验配置

统一设置：

```text
symbol = DCE.m2601
random_seeds = 50
workers = 4
modes = same, random
batch_mode = true
```

`same`：同事件同方向随机风险空间。  
`random`：同事件随机方向。

本轮已完成：

| 结构 | 原策略 | 随机基线 | 结果文件 |
|------|--------|----------|----------|
| 前日高低点重新接受 | `prevday_reacceptance` | `prevday_random_baseline` | `structural_random_baselines_20260628_231214.json` |
| 成交量爆发边界 | `volume_shock_boundary` | `volume_shock_random_baseline` | `structural_random_baselines_20260628_231234.json` |
| 小时流动性扫单 | `hourly_liquidity_sweep` | `hourly_liquidity_random_baseline` | `structural_random_baselines_20260628_231928.json` |
| 低波收敛再启动 | `low_volatility_restart` | `low_volatility_random_baseline` | `structural_random_baselines_20260628_232410.json` |

未完成：

| 结构 | 状态 | 原因 |
|------|------|------|
| 前日边界 + 成交量过滤 | 中止 | 批量运行明显慢于其他结构，需单独降 seeds 或优化后再跑 |

## 4. 前日高低点重新接受

结果文件：

```text
project_data/research/random_baseline/structural_random_baselines_20260628_231214.json
```

### 4.1 原结构

| 指标 | 数值 |
|------|------:|
| total_return | `-4.7667%` |
| total_net_pnl | `-4,766.73` |
| max_drawdown | `-6,136.89` |
| win_rate | `53.33%` |
| win_trades / loss_trades | `16 / 14` |
| total_trades | `64` |
| win_loss_ratio | `1.0334` |
| total_commission | `2,346.73` |
| total_slippage | `4,190.00` |

### 4.2 随机对照

| 口径 | 净收益均值 | 净收益中位数 | 原结构收益分位 | 随机胜率均值 | 原结构胜率优势 |
|------|-----------:|-------------:|---------------:|-------------:|----------------:|
| 同方向随机 | `-5,414.98` | `-5,800.31` | `68%` | `51.27%` | `+2.07` 个百分点 |
| 随机方向 | `-6,530.49` | `-6,669.45` | `68%` | `47.75%` | `+5.58` 个百分点 |

### 4.3 判断

前日高低点重新接受有一定方向信息：

```text
相对随机方向胜率优势约 +5.6 个百分点。
```

但它不满足强保留标准：

```text
净收益只在随机分布 68% 分位，未到 75%；
同方向随机下胜率优势只有约 +2 个百分点；
成本后仍明显亏损。
```

结论：

```text
前日高低点重新接受不是完全随机，方向层有弱信息；
但同方向风险空间优势不足，暂不作为优先继续研究入口。
```

## 5. 成交量爆发边界

结果文件：

```text
project_data/research/random_baseline/structural_random_baselines_20260628_231234.json
```

### 5.1 原结构

| 指标 | 数值 |
|------|------:|
| total_return | `-1.5120%` |
| total_net_pnl | `-1,511.95` |
| max_drawdown | `-2,076.22` |
| win_rate | `83.33%` |
| win_trades / loss_trades | `5 / 1` |
| total_trades | `16` |
| win_loss_ratio | `0.2271` |
| total_commission | `611.95` |
| total_slippage | `1,090.00` |

### 5.2 随机对照

| 口径 | 净收益均值 | 净收益中位数 | 原结构收益分位 | 随机胜率均值 | 原结构胜率优势 |
|------|-----------:|-------------:|---------------:|-------------:|----------------:|
| 同方向随机 | `-1,427.96` | `-1,651.94` | `62%` | `72.86%` | `+10.48` 个百分点 |
| 随机方向 | `-2,179.02` | `-2,250.51` | `74%` | `56.79%` | `+26.54` 个百分点 |

### 5.3 判断

成交量爆发边界的方向 / 胜率信息很强，但盈亏比极差：

```text
win_rate = 83.33%
win_loss_ratio = 0.2271
```

这意味着：

```text
大量小赢被少数大亏和成本吞噬。
```

相对随机方向，原结构接近 `74%` 分位，接近继续研究阈值，但仍未达到 `75%`。相对同方向随机，只有 `62%` 分位，说明具体风险空间没有显著优势。

结论：

```text
成交量爆发边界不适合作为主入口；
但成交量冲击可能有方向 / 胜率诊断价值，适合降级为状态变量或质量标签。
```

## 6. 小时等高 / 等低流动性扫单

结果文件：

```text
project_data/research/random_baseline/structural_random_baselines_20260628_231928.json
```

### 6.1 原结构

| 指标 | 数值 |
|------|------:|
| total_return | `-14.6995%` |
| total_net_pnl | `-14,699.46` |
| max_drawdown | `-14,699.46` |
| win_rate | `34.29%` |
| win_trades / loss_trades | `12 / 23` |
| total_trades | `78` |
| win_loss_ratio | `1.1192` |
| total_commission | `2,879.46` |
| total_slippage | `5,150.00` |

### 6.2 随机对照

| 口径 | 净收益均值 | 净收益中位数 | 原结构收益分位 | 随机胜率均值 | 原结构胜率优势 |
|------|-----------:|-------------:|---------------:|-------------:|----------------:|
| 同方向随机 | `-16,437.24` | `-16,290.77` | `86%` | `32.93%` | `+1.36` 个百分点 |
| 随机方向 | `-8,623.30` | `-8,128.99` | `20%` | `49.18%` | `-14.89` 个百分点 |

### 6.3 判断

这个结果比较明确：

```text
原方向明显差于随机方向。
```

虽然原结构优于同方向随机风险空间，说明入场 / 风险空间可能比同方向随机略好，但方向本身错得更严重。

结论：

```text
小时等高 / 等低流动性扫单作为当前方向假设应暂停；
如果保留，只能作为“反向诊断”或流动性风险状态标签，而不是入口结构。
```

## 7. 低波收敛再启动

结果文件：

```text
project_data/research/random_baseline/structural_random_baselines_20260628_232410.json
```

### 7.1 原结构

| 指标 | 数值 |
|------|------:|
| total_return | `0.0000%` |
| total_net_pnl | `0.00` |
| total_trades | `0` |

随机基线同样全部为 0 交易。

### 7.2 判断

本轮配置下无法形成可评价样本：

```text
原结构 0 交易；
同方向随机 0 交易；
随机方向 0 交易。
```

结论：

```text
低波收敛再启动在当前参数 / DCE.m2601 样本下没有随机对照评价意义；
应按“交易机会不足”暂停，不继续为了凑样本放宽条件。
```

## 8. 本轮横向结论

| 结构 | 是否优于随机方向 | 是否优于同方向随机风险空间 | 当前定位 |
|------|------------------|----------------------------|----------|
| 价值区 VAH / VAL 重新接受 | 强，是 | 否 | 方向线索保留，风险空间未通过 |
| 前日高低点重新接受 | 弱，是 | 弱 | 弱方向线索，非优先入口 |
| 成交量爆发边界 | 强，是 | 弱 | 降级为状态 / 质量标签 |
| 小时流动性扫单 | 否，明显差 | 是 | 暂停入口，可考虑反向诊断 |
| 低波收敛再启动 | 不可评价 | 不可评价 | 交易机会不足，暂停 |
| 前日边界 + 成交量过滤 | 待处理 | 待处理 | 批量运行过慢，需单独处理 |

当前最重要的结论：

```text
已测结构里，并不是所有都等同随机。
价值区、前日高低点、成交量爆发都存在不同程度的方向 / 胜率信息。

但没有一个结构在“同事件同方向随机风险空间”下表现出足够强的优势。
```

这意味着：

```text
共识边界或事件方向本身可能有信息；
但当前具体入场点、strict failure、止损和账户风险空间塑形整体未通过。
```

## 9. 对 roadmap 的阶段影响

当前不应立即说“所有结构彻底失去意义”。更准确是：

```text
方向层没有完全失败；
风险空间层普遍失败或未通过。
```

下一步不应新增入口，也不应优化单个结构，而应完成剩余随机对照素材：

1. 单独处理 `prevday_volume_filter`，必要时降低 seeds 或优化运行性能；
2. 若存在 IB 策略实现缺口，需要先确认它是否只有报告无代码；
3. 最后输出随机对照阶段总表，决定哪些结构：
   - 暂停；
   - 降级为诊断变量；
   - 保留为方向线索。

## 10. 运行与校验备注

批量命令：

```text
PYTHONPATH=workspace uv run python scripts/tools/run_structural_random_baselines.py \
  --experiments prevday volume_shock hourly_liquidity low_volatility \
  --seeds 50 \
  --workers 4
```

`prevday_volume` 初次与其他结构混跑时速度明显异常，已中止，未纳入本报告结论。
