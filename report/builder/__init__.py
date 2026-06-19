"""报告构建子包

把报告构建拆为三个职责单一、可独立调用的环节：

- data_exports: 导出数据 JSON（增量检查）
- frontend:     构建前端 bundle
- entry_html:   打包入口 HTML（快照内联）

orchestrator.build_all 是薄封装，按序串联三者，供手动重建使用。
run 收尾路径可直接调用各环节以精确控制时序。
"""

from __future__ import annotations

from ..writer import write_nav_json
from .data_exports import run_data_exports
from .entry_html import write_entry_html
from .frontend import build_frontend
from .orchestrator import build_all

__all__ = [
    "build_all",
    "run_data_exports",
    "build_frontend",
    "write_entry_html",
    "write_nav_json",
]
