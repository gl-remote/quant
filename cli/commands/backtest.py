"""统一回测命令模块

CLI 层职责（commands 在 CLI 体系中的定位）：
    - 把 argparse Namespace 转为明确请求对象（`BacktestRunRequest`）
    - 跨字段参数校验：argparse 不能表达的约束（如 TqSdk 必填、`--gui` 引擎兼容性）
    - 引擎路由：根据 `--engine` 选择调用对应的 workflow 入口
    - 用户交互层友好错误信息（`ValueError` 或 warn）

具体业务编排（数据加载、引擎初始化、run 生命周期、持久化）由
`cli.workflows.backtests_run.BacktestRunWorkflow` 承担。

阶段 3 重构（2026-06-20）：
    - 引擎选择由 `--engine` 显式触发（默认 vnpy），`--symbol`/`--pattern` 仅作标的过滤
    - `--gui` 仅在 `--engine tqsdk` 下生效，其他引擎下 warn 后忽略
    - 命令级编排迁入 `cli/workflows/backtests_run.py`
    - 参数校验 / 引擎路由保留在本层（commands 应承担的能力）
"""

from __future__ import annotations

import argparse

from loguru import logger

from cli.workflows.backtests_run import BacktestRunRequest, BacktestRunWorkflow


def cmd_backtest(args: argparse.Namespace) -> None:
    """执行统一回测命令

    引擎由 `--engine` 决定（默认 vnpy）：
      - `--engine vnpy`   批量回测（参数搜索 / Walk-Forward），可叠加 --symbol / --pattern
      - `--engine tqsdk`  单标的回测，必须指定 --symbol / --start / --end，可启用 --gui
    """
    request = BacktestRunRequest.from_args(args)
    _validate_request(request)

    workflow = BacktestRunWorkflow()
    if request.engine == "vnpy":
        workflow.run_vnpy(request)
    elif request.engine == "tqsdk":
        workflow.run_tqsdk(request)
    else:  # 实际由 argparse choices 已拦截，此处兜底
        raise ValueError(f"未知引擎: {request.engine!r}")


def _validate_request(request: BacktestRunRequest) -> None:
    """跨字段参数校验

    argparse 只能做单字段约束（type/choices/required）。对引擎间互斥、必填依赖等
    跨字段约束在此集中处理，便于未来扩展（例如阶段 10 后 `--engine tqsdk` 也支持
    `--mode walk-forward` 时仅在此处放开即可）。
    """
    # `--gui` 仅 tqsdk 下生效
    if request.gui and request.engine != "tqsdk":
        logger.warning("--gui 仅在 --engine tqsdk 下生效，已忽略当前 --gui 标志")

    # tqsdk 引擎必填项
    if request.engine == "tqsdk":
        if not request.symbol:
            raise ValueError("--engine tqsdk 必须指定 --symbol")
        if not request.start or not request.end:
            raise ValueError("--engine tqsdk 必须显式指定 --start / --end")
