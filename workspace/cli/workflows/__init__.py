"""
CLI 工作流子包

包含命令级的运行编排与生命周期管理逻辑。

模块列表:
    - backtests_lifecycle: 批量回测运行生命周期（RunLogHelper + RunFinalizer）
    - backtests_run: 命令级回测编排（多入口 + 三个 *Request 数据类）
    - realtime: 实时行情工作流（TqsdkRealtimeWorkflow + TqsdkRealtimeRequest）
    - report: 统一报表工作流（ReportWorkflow + 四个 *Request 数据类）
"""

from cli.workflows.backtests_lifecycle import RunFinalizer, RunLogHelper
from cli.workflows.backtests_run import (
    BacktestRunWorkflow,
    TqsdkRequest,
    VnpySearchRequest,
    VnpyWalkForwardRequest,
)
from cli.workflows.realtime import TqsdkRealtimeRequest, TqsdkRealtimeWorkflow
from cli.workflows.report import (
    ReportBuildRequest,
    ReportDeleteRequest,
    ReportDetailRequest,
    ReportSummaryRequest,
    ReportWorkflow,
)

__all__ = [
    "BacktestRunWorkflow",
    "ReportBuildRequest",
    "ReportDeleteRequest",
    "ReportDetailRequest",
    "ReportSummaryRequest",
    "ReportWorkflow",
    "RunFinalizer",
    "RunLogHelper",
    "TqsdkRealtimeRequest",
    "TqsdkRealtimeWorkflow",
    "TqsdkRequest",
    "VnpySearchRequest",
    "VnpyWalkForwardRequest",
]
