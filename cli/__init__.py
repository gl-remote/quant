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

工具函数已迁移到核心模块:
    - load_strategy, apply_strategy_config, TradingContext → strategies.core
    - calculate_fifo_profit → common.formulas
"""

# 兼容性导入转发（保留原有 API）
from strategies.core import (
    load_strategy,
    get_strategy_class_name,
    apply_strategy_config,
    serialize_strategy_params,
    TradingContext,
)
from common.formulas import calculate_fifo_profit


def build_context(strategy, symbol, config_manager, capital=100000.0):
    """兼容性包装：委托给 TradingContext.build"""
    return TradingContext.build(strategy, symbol, config_manager, capital)


__all__ = [
    'calculate_fifo_profit',
    'load_strategy',
    'get_strategy_class_name',
    'build_context',
    'apply_strategy_config',
    'serialize_strategy_params',
]