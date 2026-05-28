# -*- coding: utf-8 -*-
"""
报告生成模块 — 数据导出 + 前端构建
主要功能：
- 生成回测报告
- 导出JSON数据
- 构建前端界面
"""

# 从子模块导入核心功能
from .builder import build_all, write_nav_json
from .reporter import format_single_report, format_summary_report, build_optuna_spec

# 向后兼容 - 支持旧的导入路径
try:
    from .reporter.text import _na_str, _get_attr
except ImportError:
    pass

# 公开API列表，供外部模块使用
__all__ = [
    "format_single_report",  # 格式化单个回测报告
    "format_summary_report",  # 格式化回测汇总报告
    "build_all",  # 构建完整报告（数据+前端）
    "write_nav_json",  # 写入导航JSON数据
    "build_optuna_spec",  # 生成Optuna图表配置
]