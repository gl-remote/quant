"""
CLI 工作流子包

包含命令级的运行编排与生命周期管理逻辑。

模块列表:
    - backtests_lifecycle: 批量回测运行生命周期（RunLogHelper + RunFinalizer）
    - backtests_run: 命令级回测编排（BacktestRunRequest + BacktestRunWorkflow）
"""

from cli.workflows.backtests_lifecycle import RunFinalizer, RunLogHelper
from cli.workflows.backtests_run import BacktestRunRequest, BacktestRunWorkflow

__all__ = [
    "RunLogHelper",
    "RunFinalizer",
    "BacktestRunRequest",
    "BacktestRunWorkflow",
]
