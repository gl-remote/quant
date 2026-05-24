# -*- coding: utf-8 -*-
"""
报告生成模块

  - sql_reporter.py:        基于 SQLite 数据库的只读报告 (生产用)
  - dataset_reporter.py:    单数据集 JSON 回测报告 (engine 调用)
  - comparison_reporter.py: 多品种合并报告与排名
"""

from .sql_reporter import (
    format_single_report,
    format_comparison_report,
    format_summary_report,
)
from .dataset_reporter import (
    generate_dataset_report,
    format_console_report,
)
from .comparison_reporter import (
    generate_merged_report,
    format_merged_report,
)

__all__ = [
    'format_single_report',
    'format_comparison_report',
    'format_summary_report',
    'generate_dataset_report',
    'format_console_report',
    'generate_merged_report',
    'format_merged_report',
]
