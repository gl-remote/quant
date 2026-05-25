# -*- coding: utf-8 -*-
"""
报告生成模块

从数据库读取回测数据，生成格式化控制台文本报告。

  - single.py:  单次回测详细报告 (format_single_report)
  - summary.py: 回测记录汇总列表 (format_summary_report)
"""

from .single import format_single_report
from .summary import format_summary_report

__all__ = [
    'format_single_report',
    'format_summary_report',
]
