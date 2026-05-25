# -*- coding: utf-8 -*-
"""
CLI 命令子包

包含所有命令行命令的实现，每个命令独立为一个模块。

命令列表:
    - cmd_export:   数据导出命令
    - cmd_test:     策略测试命令
    - cmd_backtest: 统一回测命令（自动选择 TqSdk/vn.py 引擎）
    - cmd_live:     实盘交易命令
    - cmd_report:   报告生成命令
"""

from cli.commands.export import cmd_export
from cli.commands.test import cmd_test
from cli.commands.backtest import cmd_backtest
from cli.commands.live import cmd_live
from cli.commands.report import cmd_report

__all__ = [
    'cmd_export',
    'cmd_test',
    'cmd_backtest',
    'cmd_live',
    'cmd_report',
]