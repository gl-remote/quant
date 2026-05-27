# -*- coding: utf-8 -*-
"""报告生成模块 — 数据导出 + 前端构建"""

from .builder import build_all, write_nav_json
from .reports import format_single_report, format_summary_report

__all__ = [
    "format_single_report",
    "format_summary_report",
    "build_all",
    "write_nav_json",
]