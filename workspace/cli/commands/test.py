"""test 命令：通过天勤实时数据验证策略信号链路（不下单）

本模块负责 CLI 层面的 argparse 定义、参数翻译与路由分发。
具体业务编排由 `cli.workflows.realtime.TqsdkRealtimeWorkflow` 承担。

安全保证：test 命令代码路径中不包含下单逻辑，即使账号已绑定期货公司也不会下单。
"""

from __future__ import annotations

import argparse
from typing import Any

from cli.env import add_environment_arguments, build_data_context
from cli.workflows.realtime import TqsdkRealtimeRequest, TqsdkRealtimeWorkflow


def register(subparsers: Any) -> None:
    """注册 test 子命令的 argparse 选项"""
    p = subparsers.add_parser(
        "test",
        help="通过天勤实时数据验证策略信号链路（不下单）",
        description="连接天勤实时行情驱动策略，打印交易信号用于验证链路正确性。\n\n"
        "安全保证：test 命令代码路径中不包含下单逻辑，即使账号已绑定期货公司也不会下单。",
    )
    p.add_argument("--strategy", required=True, help="策略名称 (e.g. ma/ma_strategy/ma_strategy.py)")
    p.add_argument("--symbol", required=True, help="合约代码 (e.g. SHFE.rb2509)")
    p.add_argument("--gui", action="store_true", help="启用浏览器可视化 (默认关闭)")
    add_environment_arguments(p)


def cmd_test(args: argparse.Namespace) -> None:
    """test 命令：本地模拟，只验证信号链路，不下单。"""
    cm, dm = build_data_context(args, "test")
    req = TqsdkRealtimeRequest(
        strategy=args.strategy,
        symbol=args.symbol,
        gui=bool(args.gui),
        config=None,
    )
    TqsdkRealtimeWorkflow(cm=cm, dm=dm).run(
        req=req,
        mode="test",
        account_type="tqsim",
        require_account=False,
        trade=False,
    )
