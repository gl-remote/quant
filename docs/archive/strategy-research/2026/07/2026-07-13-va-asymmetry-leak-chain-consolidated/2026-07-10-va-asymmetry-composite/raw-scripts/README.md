# raw-scripts：va-asymmetry-composite 工程侧启动脚本归档

> 类型：Archive / 原始工程脚本
> 状态：已归档（2026-07-15）
> 所属阶段：va-asymmetry 错误路径链条归并封装 · va-asymmetry-composite 主题

## 目录用途

保存 va-asymmetry-composite 主题在工程侧的一键回测启动脚本。

## 文件说明

| 文件 | 用途 |
|------|------|
| `backtest-va.sh` | 全量 145 合约 5m K 线 × 默认参数并行单次回测（用于「工程侧 vs 研究侧收益 gap 对比」基线），可通过 `MODE=search` 切换到贝叶斯参数搜索 |

## 使用注意

归档后：

- 脚本仍能通过相对路径调用 `run.sh backtest --strategy va_asymmetry_composite`，
  但 `va_asymmetry_composite` 已不在 `workspace/strategies/` 中注册，
  `load_strategy("va_asymmetry_composite")` 会抛 `FileNotFoundError`；
- 若需复现，需先把 `../raw-strategies/va_asymmetry_composite_strategy.py`
  临时复制回 `workspace/strategies/` 并处理其 `_CSV_DIR` 硬编码路径依赖。

**默认状态下此脚本不可直接运行**。
