"""
报告生成模块 — 数据导出 + 前端构建
主要功能：
- 生成回测报告
- 导出JSON数据
- 构建前端界面
"""

# 从子模块导入核心功能
import contextlib

from .builder import write_nav_json
from .output_paths import (
    logs_json_path,
    nav_json_path,
    report_assets_dir,
    report_nav_path,
    report_runs_root,
    run_data_dir,
    run_dir,
    run_log_path,
    run_report_data_dir,
    run_report_dir,
    workers_dir,
)
from .reporter import build_optuna_spec, format_single_report, format_summary_report

# 向后兼容 - 支持旧的导入路径
with contextlib.suppress(ImportError):
    from .reporter.text import _get_attr, _na_str  # noqa: F401 — 向后兼容导出

# 公开API列表，供外部模块使用
__all__ = [
    "format_single_report",  # 格式化单个回测报告
    "format_summary_report",  # 格式化回测汇总报告
    "write_nav_json",  # 写入导航JSON数据
    "build_optuna_spec",  # 生成Optuna图表配置
    "run_dir",
    "run_data_dir",
    "run_report_dir",
    "run_report_data_dir",
    "run_log_path",
    "logs_json_path",
    "nav_json_path",
    "report_nav_path",
    "report_assets_dir",
    "report_runs_root",
    "workers_dir",
]
