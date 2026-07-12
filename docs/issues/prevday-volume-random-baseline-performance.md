# prevday_volume_filter 随机对照批量运行性能异常偏慢

> 类型：性能问题 / 回测链路 / 实验 runner  
> 状态：待排查  
> 发现日期：2026-06-29  
> 发现分支：`feature/random-entry-baseline-roadmap`  
> 关联实验：结构入口随机对照 loop  
> 相关归档：[结构型 Alpha 随机对照阶段归档](../archive/strategy-research/2026/06/2026-06-29-structural-alpha-random-baseline/README.md)  
> 相关代码：[prevday_volume_filter_strategy.py](../../workspace/strategies/prevday_volume_filter_strategy.py)，[prevday_volume_random_baseline_strategy.py](../../workspace/strategies/prevday_volume_random_baseline_strategy.py)，[run_structural_random_baselines.py](../../scripts/tools/run_structural_random_baselines.py)

## 背景

结构入口随机对照阶段计划覆盖：

```text
前日边界 + 成交量质量过滤
```

该结构已有原策略和随机基准实现，但在与其他结构一起进行 50 seeds 批量随机对照时，运行速度明显慢于其他结构，最终被中止，未纳入阶段主结论。

相关记录：

- [随机对照阶段摘要](../archive/strategy-research/2026/06/2026-06-29-structural-alpha-random-baseline/random-baseline-experiment-summary.md)
- [raw workbench: r3 entry routes loop](../archive/strategy-research/2026/06/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-random-baseline-r3-entry-routes-loop.md)

## 现象

实验记录中描述：

```text
前日边界 + 成交量过滤：批量运行明显慢于其他结构，需单独降 seeds 或优化后再跑。
prevday_volume 初次与其他结构混跑时速度明显异常，已中止，未纳入本报告结论。
```

其他结构 50 seeds 可以完成，但 `prevday_volume_filter` / `prevday_volume_random_baseline` 明显拖慢批量 loop。

## 影响

| 影响面 | 说明 |
|--------|------|
| 随机对照覆盖完整性 | `prevday_volume_filter` 未完成同口径随机对照 |
| 实验效率 | 多 seed / 多结构 loop 被单一结构拖慢 |
| 后续研究 | 成交量作为质量标签仍有研究价值，但该结构不能直接纳入批量随机对照主流程 |
| 阶段结论 | 不影响价值区主线结论，但影响“前日边界 + 成交量过滤”的覆盖审计 |

## 初步判断

可能原因包括：

1. 策略每根 K 线维护 volume / range rolling list，窗口或列表操作成本偏高；
2. 随机基准复用原策略逻辑后，每个 seed 重复计算完整事件状态；
3. 批量 runner 每个 seed 独立启动完整 vnpy 回测，未复用事件缓存；
4. 报告 / 结果持久化开销与回测本身叠加；
5. 该结构交易事件或诊断状态远多于其他结构。

## 最小复现方向

建议单独运行小规模性能复现：

```text
prevday_volume_filter: 1 seed / 5 seeds / 10 seeds
prevday_volume_random_baseline: same-direction / random-direction
workers = 1 / 2 / 4
```

需要记录：

- 单 seed 总耗时；
- 策略 on_bar 耗时；
- vnpy engine 耗时；
- 报告 / DB 写入耗时；
- 每日事件数和交易数；
- 是否存在异常多的 diagnostics。

## 当前处理建议

1. 暂不把该结构放入大批量随机对照 loop；
2. 若后续需要覆盖审计，先用 10 或 20 seeds 单独跑；
3. 若仍显著偏慢，先做 profile，再决定：
   - 缓存前日边界 + volume shock 事件；
   - 预生成事件表，随机基准只抽样事件；
   - 关闭非必要 diagnostics；
   - 增加 runner 的 `--skip-report` / 轻量结果模式。

## 修复记录

待补。

## 验证记录

待补。
