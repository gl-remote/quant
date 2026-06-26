"""live 命令：天勤模拟/实盘交易（会下单）

本模块负责 CLI 层面的 argparse 定义、参数翻译与路由分发。
具体业务编排由 `cli.workflows.realtime.TqsdkRealtimeWorkflow` 承担。

模拟 vs 实盘：取决于天勤账号是否绑定期货公司账户。
  未绑定 → 模拟盘（虚拟资金，不影响真实账户）
  已绑定 → 实盘（真金白银，慎用！）
"""

from __future__ import annotations

import argparse
from typing import Any

from cli.env import add_environment_arguments, build_data_context
from cli.workflows.realtime import TqsdkRealtimeRequest, TqsdkRealtimeWorkflow


def register(subparsers: Any) -> None:
    """注册 live 子命令的 argparse 选项"""
    p = subparsers.add_parser(
        "live",
        help="天勤模拟/实盘交易（会下单，模拟/实盘取决于账号是否绑定期货公司）",
        description="通过天勤 SDK 连接实时数据运行策略并下单。\n\n"
        "模拟 vs 实盘：取决于天勤账号是否绑定期货公司账户。\n"
        "  未绑定 → 模拟盘（虚拟资金，不影响真实账户）\n"
        "  已绑定 → 实盘（真金白银，慎用！）",
    )
    p.add_argument("--symbol", default="DCE.m2509", help="品种代码")
    p.add_argument("--gui", action="store_true", help="启用图形界面")
    p.add_argument("--strategy", required=True, help="策略名称 (e.g. ma/ma_strategy/ma_strategy.py)")
    add_environment_arguments(p)


def cmd_live(args: argparse.Namespace) -> None:
    """live 命令：走 TargetPosTask 下单，账户类型读配置。"""
    cm, dm = build_data_context(args, "live")
    req = TqsdkRealtimeRequest(
        strategy=args.strategy,
        symbol=args.symbol,
        gui=bool(args.gui),
        config=None,
    )
    TqsdkRealtimeWorkflow(cm=cm, dm=dm).run(
        req=req,
        mode="live",
        account_type=None,
        require_account=True,
        trade=True,
    )
