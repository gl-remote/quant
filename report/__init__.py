# -*- coding: utf-8 -*-
"""
报告生成模块 — 基于 SQLite 数据库的只读报告

完全独立于 backtest/data/strategies 业务逻辑，
仅通过 data.database.Database 读取回测结果。
"""

from .sql_reporter import (
    format_single_report,
    format_comparison_report,
    format_summary_report,
)

__all__ = [
    'format_single_report',
    'format_comparison_report',
    'format_summary_report',
]
