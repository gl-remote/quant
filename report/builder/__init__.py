"""报告构建子包

把报告构建拆为三个职责单一、可独立调用的环节：

- data_exports: 导出数据 JSON（增量检查）
- frontend:     构建前端 bundle
- entry_html:   打包入口 HTML（快照内联）

三个环节由 `cli.workflows.report.ReportWorkflow.build()` 统一串联，
供手动重建（cmd_report）与 run 收尾（RunFinalizer）复用。
"""

from __future__ import annotations

from ..writer import write_nav_json
from .data_exports import run_data_exports
from .entry_html import write_entry_html
from .frontend import build_frontend

__all__ = [
    "run_data_exports",
    "build_frontend",
    "write_entry_html",
    "write_nav_json",
]
