# raw-tests：va-asymmetry-composite 工程侧回归测试归档

> 类型：Archive / 原始工程测试代码
> 状态：已归档（2026-07-15）· 空目录占位
> 所属阶段：va-asymmetry 错误路径链条归并封装 · va-asymmetry-composite 主题

## 归档说明

`workspace/tests/strategies/` 中原本没有专门的 `test_va_asymmetry_composite_strategy.py` 独立测试文件——该策略的验证主要走脚本方式（见 `../raw-scripts/backtest-va.sh` 与
`../2026-07-13-va-asymmetry-future-info-leak/raw-scripts/`）。

保留本目录作为占位，以便未来若需要补写归档级 smoke test，可以放到本目录并显式声明"仅供
归档复现，不进入工程侧 pytest 覆盖"的边界。
