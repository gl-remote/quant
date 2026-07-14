# raw-tests：结构入口原始策略回归测试归档

> 类型：Archive / 原始工程测试代码
> 状态：已归档（2026-07-15）
> 所属阶段：结构型 Alpha 随机对照阶段
> 阶段入口：[../README.md](../README.md)
> 相关代码：[../raw-strategies/](../raw-strategies/)

## 目录用途

保存结构型 Alpha 随机对照阶段中，五个原始结构策略（`prevday_reacceptance` /
`prevday_volume_filter` / `volume_shock_boundary` / `hourly_liquidity_sweep` /
`low_volatility_restart`）在工程侧原有的 pytest 回归测试。

这批测试原本位于 `workspace/tests/strategies/`，与对应的策略代码一起在 2026-07-15
归档到本批次。策略代码同批次追加到 `../raw-strategies/`（在原有随机基线策略之外）。

## 文件说明

| 文件 | 对应策略 |
|------|--------|
| `test_prevday_reacceptance_strategy.py` | `../raw-strategies/prevday_reacceptance_strategy.py` |
| `test_prevday_volume_filter_strategy.py` | `../raw-strategies/prevday_volume_filter_strategy.py` |
| `test_volume_shock_boundary_strategy.py` | `../raw-strategies/volume_shock_boundary_strategy.py` |
| `test_hourly_liquidity_sweep_strategy.py` | `../raw-strategies/hourly_liquidity_sweep_strategy.py` |
| `test_low_volatility_restart_strategy.py` | `../raw-strategies/low_volatility_restart_strategy.py` |

## 使用注意

- 五个策略是 R2/R3/R4/R5/R6 五条结构分支的**原始实现**，随机基线（本批次
  `../raw-strategies/` 中的 `*_random_baseline_strategy.py`）就是围绕它们做对照生成的；
- 阶段结论：无一条通过随机对照的结构入口检验，因此原策略也不再在工程侧维护；
- 测试文件保留导入原有 `from strategies.<name> import ...` 语句，归档后不可直接
  运行；未来若需复现，需临时把 `../raw-strategies/` 中对应策略复制回 active 目录。

## 相关文档

- [随机对照阶段摘要](../random-baseline-experiment-summary.md)
- [../raw-strategies/README.md](../raw-strategies/README.md)（随机基线策略说明）
- [../raw-workbench/](../raw-workbench/)（各 R 分支实验流水）
