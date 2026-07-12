# raw-strategies：阶段性随机基线策略归档

> 类型：Archive / 原始研究策略代码  
> 状态：已归档  
> 所属阶段：结构型 Alpha 随机对照阶段  
> 阶段入口：[../README.md](../README.md)

## 1. 目录用途

本目录保存结构型 Alpha 随机对照阶段临时编写的随机基线策略。

这些策略用于回答：

```text
结构入口是否至少比匹配随机入口更有信息量？
```

它们不再作为 active `workspace/strategies` 策略维护。

原因：

```text
这些策略绑定阶段性随机对照定义，
不是长期可交易策略，
继续放在 workspace/strategies 会让后续 AI 误以为它们是可用主线策略。
```

## 2. 文件说明

| 文件 | 对应结构 | 用途 |
|------|----------|------|
| `value_area_random_baseline_strategy.py` | 前日价值区 VAH / VAL 重新接受 | 价值区结构的同事件 / 同方向 / 随机方向基线 |
| `prevday_random_baseline_strategy.py` | 前日高低点重新接受 | 前日边界结构的随机对照 |
| `volume_shock_random_baseline_strategy.py` | 成交量爆发边界 | volume shock 主边界的随机对照 |
| `prevday_volume_random_baseline_strategy.py` | 前日边界 + 成交量过滤 | 成交量质量过滤结构的随机对照 |
| `hourly_liquidity_random_baseline_strategy.py` | 小时等高 / 等低流动性扫单 | 小时流动性扫单结构的随机对照 |
| `low_volatility_random_baseline_strategy.py` | 压力释放后低波收敛再启动 | 低波再启动结构的随机对照 |

## 3. 与 active 策略目录的关系

这些随机基线策略已经从 active `workspace/strategies` 移出。

active `workspace/strategies` 中保留的原始结构策略包括：

```text
value_area_reacceptance_strategy.py
prevday_reacceptance_strategy.py
volume_shock_boundary_strategy.py
prevday_volume_filter_strategy.py
hourly_liquidity_sweep_strategy.py
low_volatility_restart_strategy.py
```

保留原因：

- `value_area_reacceptance_strategy.py` 是当前研究主线；
- 其他原始结构策略是已跟踪代码并有对应测试，删除会牵连测试与历史策略基线；
- 它们不是随机基线临时代码，是否删除应另开一次工程清理决策。

## 4. 使用注意

本目录策略只作历史参考，不保证可直接运行。

原因：

```text
归档后相对 import 路径不再适合作为 Python 包直接导入；
相关 runner 也已移动到 raw-scripts；
active 策略目录已不再注册这些 random_baseline 策略。
```

如果未来要重新做随机对照，应根据当前策略实现重新生成最小随机基线，而不是直接把这些文件复制回 active 目录。

## 5. 相关文档

- [随机对照阶段摘要](../random-baseline-experiment-summary.md)
- [价值区深耕摘要](../value-area-deepening-summary.md)
- [raw-scripts](../raw-scripts/README.md)
