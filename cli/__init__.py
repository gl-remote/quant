"""
CLI 模块包

提供命令行界面功能，包含策略测试、回测、实盘交易等命令。

模块结构:
    - cli/main.py          # 主入口和参数解析
    - cli/commands/        # 命令实现子包
        - export.py        # 数据导出命令
        - test.py          # 策略测试命令
        - backtest.py      # 统一回测命令 (TqSdk / vn.py)
        - live.py          # 实盘交易命令
        - report.py        # 报告生成命令

【推荐导入方式】
  from cli import load_strategy, apply_strategy_config  # 通过 cli 转发导入
  from strategies import load_strategy  # 或者直接从 strategies 导入
  from strategies.utils import load_strategy  # 或者直接从 utils 导入
"""

# 转发导入（便于外部按 cli.xxx 直接引用）
from common.formulas import calculate_fifo_profit
from strategies import (
    apply_strategy_config,
    get_strategy_class_name,
    load_strategy,
    serialize_strategy_params,
)

__all__ = [
    "calculate_fifo_profit",
    "load_strategy",
    "get_strategy_class_name",
    "apply_strategy_config",
    "serialize_strategy_params",
]
