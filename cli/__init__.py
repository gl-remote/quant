# -*- coding: utf-8 -*-
"""
CLI 模块包

提供命令行界面功能，包含策略测试、回测、实盘交易等命令。

模块结构:
    - cli/main.py           # 主入口和参数解析
    - cli/commands/         # 命令实现子包
        - export.py         # 数据导出命令
        - test.py           # 策略测试命令
        - backtest.py       # vn.py 批量回测命令
        - tq_backtest.py    # TqSdk 回测命令
        - live.py           # 实盘交易命令
        - report.py         # 报告生成命令

工具函数:
    - load_strategy, apply_strategy_config → strategies.core
    - calculate_fifo_profit → common.formulas
    - BacktestConfig / StrategyItemConfig → config.app_config (typed config models)
"""

# 兼容性导入转发
from strategies.core import (
    load_strategy,
    get_strategy_class_name,
    apply_strategy_config,
    serialize_strategy_params,
)
from common.formulas import calculate_fifo_profit
from common.constants import DEFAULT_INITIAL_CAPITAL


__all__ = [
    'calculate_fifo_profit',
    'load_strategy',
    'get_strategy_class_name',
    'apply_strategy_config',
    'serialize_strategy_params',
]