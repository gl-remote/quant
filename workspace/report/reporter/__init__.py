"""报告生成模块

提供各类报告生成功能：
- text: 文本报告（控制台输出）
- optimizer: Optuna 优化报告（ECharts 配置）
"""

from .optimizer import build_optuna_spec
from .text import format_single_report, format_summary_report

__all__ = [
    "format_single_report",
    "format_summary_report",
    "build_optuna_spec",
]
