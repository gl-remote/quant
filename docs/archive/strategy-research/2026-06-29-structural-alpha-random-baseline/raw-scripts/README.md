# raw-scripts：阶段性研究 runner 归档

> 类型：Archive / 原始研究脚本  
> 状态：已归档  
> 所属阶段：结构型 Alpha 随机对照阶段  
> 阶段入口：[../README.md](../README.md)

## 1. 目录用途

本目录保存结构型 Alpha 随机对照阶段临时编写的研究 runner。

这些脚本用于复现当时的批量实验、随机对照和价值区深耕诊断，但不再作为 active `scripts/tools` 工具维护。

原因：

```text
这些 runner 绑定了本阶段的固定参数、实验命名、输出路径和临时诊断字段；
如果继续留在 scripts/tools，后续 AI 或人工容易误认为它们是长期通用工具。
```

后续如需继续研究，应优先根据 [../../../../research/strategy-current.md](../../../../research/strategy-current.md) 的当前主线重新设计最小 runner，而不是直接扩展本目录脚本。

## 2. 文件说明

| 文件 | 用途 |
|------|------|
| `run_value_area_random_baseline.py` | 价值区 VAH / VAL 重新接受的第一轮多 seed 随机对照 |
| `run_structural_random_baselines.py` | 多结构入口随机对照 loop，覆盖前日、成交量、小时流动性、低波等方向 |
| `run_value_area_deepening_r1.py` | 价值区重新接受质量第一轮深耕，对比 quick / deep reaccept 变体 |
| `run_value_area_deepening_r2.py` | 价值区 `min_reaccept_ticks = 1/2/3` 多品种、同方向随机稳健性检查 |
| `run_value_area_deepening_r3_diagnostics.py` | 价值区机制诊断，输出 MAE / MFE、亏损簇、exit reason、成本占比等 |
| `run_value_area_deepening_r4_time_exit.py` | 价值区 time_exit / POC 兑现诊断，比较 `max_hold_bars = 6/12/18/24` |

## 3. 重要注意事项

这些脚本只作为历史复现素材，不保证：

- 与当前策略代码完全兼容；
- 与当前 CLI / config / data requirements 完全一致；
- 适合作为新的正式研究 runner；
- 输出结果可直接覆盖归档结论。

使用前应先检查：

```text
1. 当前策略实现是否仍与归档时一致；
2. 相关随机基准策略是否仍存在；
3. data_requirements / interval 选择是否仍正确；
4. vnpy 成交配对 issue 是否影响目标实验；
5. 输出路径是否仍符合当前 project_data 约定。
```

## 4. 已知相关 issue

- [vnpy 平仓未配对警告影响成交级统计口径](../../../backtest/vnpy-close-trade-pairing-warning.md)
- [prevday_volume_filter 随机对照批量运行性能异常偏慢](../../../../issues/prevday-volume-random-baseline-performance.md)

## 5. 推荐阅读顺序

如需理解这些脚本对应的阶段结论，不要直接从脚本开始，推荐：

```text
../README.md
→ ../structural-alpha-stage-final-report.md
→ ../random-baseline-experiment-summary.md
→ ../value-area-deepening-summary.md
→ 本目录脚本
```
