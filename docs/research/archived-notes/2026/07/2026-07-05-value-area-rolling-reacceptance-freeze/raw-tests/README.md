# raw-tests：value-area 家族原始测试归档

> 类型：Archive / 原始工程测试代码
> 状态：已归档（2026-07-15）
> 所属阶段：value-area-rolling-reacceptance 冻结批次
> 相关代码：[../raw-strategies/](../raw-strategies/)

## 目录用途

保存 value-area 家族三份策略在工程侧原有的 pytest 回归测试，随策略代码一起从
`workspace/tests/strategies/` 归档到本目录。

## 文件说明

| 文件 | 对应策略 |
|------|--------|
| `test_value_area_reacceptance_baseline_strategy.py` | `../raw-strategies/value_area_reacceptance_baseline_strategy.py` |
| `test_value_area_random_baseline_strategy.py` | `../raw-strategies/value_area_random_baseline_strategy.py` |
| `test_value_area_multi_attempt_poc_reversion_strategy.py` | `../raw-strategies/value_area_multi_attempt_poc_reversion_strategy.py` |

## 使用注意

- 测试文件保留了原有的 `from strategies.<name> import ...` 导入语句，归档后无法直接
  运行（对应策略已不在 `workspace/strategies/`）；
- 保留本目录的价值在于：如果未来需要复现 R29/R30 阶段的行为不变量，可以先把
  `../raw-strategies/` 复制回 active 目录，再复用这些测试作为最小回归验证。
