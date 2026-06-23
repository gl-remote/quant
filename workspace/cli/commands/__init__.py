"""
CLI 命令子包

包含所有命令行命令的实现，每个命令独立为一个模块。

命令列表:
    - cmd_export:   数据导出命令
    - cmd_test:     策略测试命令（tqsdk 实时行情 + 策略驱动，不下单）
    - cmd_backtest: 统一回测命令（vnpy / tqsdk 引擎）
    - cmd_live:     实盘交易命令（tqsdk 下单）
    - cmd_report:   报告生成命令
"""

from cli.commands.backtest import cmd_backtest
from cli.commands.export import cmd_export
from cli.commands.live import cmd_live
from cli.commands.report import cmd_report
from cli.commands.test import cmd_test

__all__ = [
    "cmd_export",
    "cmd_test",
    "cmd_backtest",
    "cmd_live",
    "cmd_report",
]
