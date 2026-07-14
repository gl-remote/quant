# raw-strategies：阶段性策略归档（原始结构 + 随机基线）

> 类型：Archive / 原始研究策略代码  
> 状态：已归档  
> 所属阶段：结构型 Alpha 随机对照阶段  
> 阶段入口：[../README.md](../README.md)

## 1. 目录用途

本目录保存结构型 Alpha 随机对照阶段的**两类策略**：

1. **原始结构策略**（2026-07-15 从 `workspace/strategies/` 归档）— R2/R3/R4/R5/R6 五条结构分支的原始实现；
2. **随机基线策略**（本阶段临时编写）— 用于回答"结构入口是否至少比匹配随机入口更有信息量？"。

阶段结论：五条结构分支无一条通过随机对照检验，原始结构策略也不再在工程侧维护，
一并归档到本目录。

## 2. 文件说明

### 2.1 原始结构策略（2026-07-15 从 `workspace/strategies/` 归档）

| 文件 | 对应结构 |
|------|--------|
| `prevday_reacceptance_strategy.py` | R2：前日高低点重新接受 |
| `volume_shock_boundary_strategy.py` | R3：成交量爆发边界 |
| `prevday_volume_filter_strategy.py` | R4：前日边界 + 成交量过滤 |
| `hourly_liquidity_sweep_strategy.py` | R5：小时等高 / 等低流动性扫单 |
| `low_volatility_restart_strategy.py` | R6：压力释放后低波收敛再启动 |

对应的 pytest 回归测试同步归档到 `../raw-tests/`。

### 2.2 随机基线策略（原有条目）

| 文件 | 对应结构 | 用途 |
|------|----------|------|
| `value_area_random_baseline_strategy.py` | 前日价值区 VAH / VAL 重新接受 | 价值区结构的同事件 / 同方向 / 随机方向基线 |
| `prevday_random_baseline_strategy.py` | 前日高低点重新接受 | 前日边界结构的随机对照 |
| `volume_shock_random_baseline_strategy.py` | 成交量爆发边界 | volume shock 主边界的随机对照 |
| `prevday_volume_random_baseline_strategy.py` | 前日边界 + 成交量过滤 | 成交量质量过滤结构的随机对照 |
| `hourly_liquidity_random_baseline_strategy.py` | 小时等高 / 等低流动性扫单 | 小时流动性扫单结构的随机对照 |
| `low_volatility_random_baseline_strategy.py` | 压力释放后低波收敛再启动 | 低波再启动结构的随机对照 |

> 注：`value_area_random_baseline_strategy.py` 在 2026-07-15 之后仍有一份工程侧版本被归档到
> `docs/archive/strategy-research/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/raw-strategies/`，
> 本目录版本是随机对照阶段的原始版，两者语义相同但代码略有差异。

## 3. 与 active 策略目录的关系

active `workspace/strategies/` 中原本保留 R2-R6 五条原始结构策略作为"已跟踪代码"，
本次一并归档。归档原因：

- value-area 家族两个主题已冻结，structural-alpha 阶段亦已完成，
  这些原始结构策略无对应活跃研究主题继续维护；
- 阶段性随机对照结论已明确，无实盘上线路径；
- 继续放在 `workspace/strategies/` 会让后续 AI 误以为它们是可用主线策略。

## 4. 使用注意

本目录策略只作历史参考，不保证可直接运行。

原因：

```text
归档后相对 import 路径不再适合作为 Python 包直接导入；
相关 runner 也已在 raw-scripts；
active 策略目录已不再注册这些策略。
```

如果未来要重新做随机对照，应根据当前策略实现重新生成最小随机基线，而不是直接把这些文件复制回 active 目录。

## 5. 相关文档

- [随机对照阶段摘要](../random-baseline-experiment-summary.md)
- [价值区深耕摘要](../value-area-deepening-summary.md)
- [../raw-tests/](../raw-tests/)（对应 pytest 回归测试）
- [../raw-scripts/](../raw-scripts/)（阶段 runner 与对照脚本）
- [../raw-workbench/](../raw-workbench/)（各 R 分支实验流水）
