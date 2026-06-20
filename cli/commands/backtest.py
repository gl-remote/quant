"""统一回测命令模块

CLI 层职责（commands 在 CLI 体系中的定位）：
    - 自定义 argparse subparser（`register`）
    - 把 argparse Namespace 翻译为对应的工作流请求对象（VnpySearchRequest /
      VnpyWalkForwardRequest / TqsdkRequest），每个对象字段最小化
    - 跨字段参数校验：argparse 不能表达的约束（如 TqSdk 必填、`--gui` 引擎兼容性）
    - 引擎与模式路由：根据 `--engine` / `--mode` 选择调用对应的 workflow 入口
    - 用户交互层友好错误信息（`ValueError` 或 warn）

具体业务编排（数据加载、引擎初始化、run 生命周期、持久化）由
`cli.workflows.backtests_run.BacktestRunWorkflow` 三个公开入口承担。

阶段 3.5 重构（多入口拆分）：
    - argparse 选项定义在本模块的 `register(subparsers)`
    - 三个工作流（vnpy search / vnpy walk-forward / tqsdk）有独立请求对象
    - workflow 不再感知 `engine` / `mode` 字段，路由完全在本模块完成
"""

from __future__ import annotations

import argparse
from typing import Any

from loguru import logger

from cli.workflows.backtests_run import (
    BacktestRunWorkflow,
    TqsdkRequest,
    VnpySearchRequest,
    VnpyWalkForwardRequest,
)


def register(subparsers: Any) -> None:
    """注册 backtest 子命令的 argparse 选项

    `subparsers` 是 `parser.add_subparsers()` 返回的对象（`argparse._SubParsersAction`），
    其类型在 argparse 中是私有的，因此使用 `Any` 表示。
    """
    p = subparsers.add_parser(
        "backtest",
        help="统一回测（默认 vnpy 引擎，可显式指定 --engine tqsdk）",
        description="""统一回测命令。引擎默认 vnpy，可通过 --engine 显式切换。

引擎选择:
  --engine vnpy    (默认) 使用 vn.py 进行批量回测，支持参数搜索 / Walk-Forward
                   - 单品种: --symbol DCE.m2509
                   - 批量:   --pattern "DCE\\.m"
                   - 全量:   省略 --symbol/--pattern
                   - 仅生成文字报告 + 数据库落地

  --engine tqsdk   使用 TqSdk 进行单标的回测，可启用 GUI（仅本引擎支持 --gui）
                   - 必须指定 --symbol / --start / --end
                   - 不支持 --pattern / --mode / --parallel
                   - GUI 默认关闭，需显式 --gui 开启

注意:
  - --symbol / --pattern 仅控制标的过滤，不再影响引擎选择。
  - --gui 仅在 --engine tqsdk 下生效，其他引擎下传入会给 warning。

示例:
  python main.py backtest --strategy ma --pattern "DCE\\.m"
  python main.py backtest --engine vnpy --strategy ma --symbol DCE.m2509
  python main.py backtest --engine tqsdk --strategy ma --symbol DCE.m2509 --start 2025-01-01 --end 2025-06-30 --gui

回测结果均会自动保存到数据库，可使用 report 命令查看详情。
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--engine",
        choices=["vnpy", "tqsdk"],
        default="vnpy",
        help="回测引擎（默认 vnpy；tqsdk 仅支持单标的，可启用 GUI）",
    )
    p.add_argument("--symbol", default=None, help="品种代码，仅作为标的过滤；与引擎选择解耦")
    p.add_argument(
        "--pattern", default=None, help='文件名正则表达式（如 "DCE\\.m.*\\.1m\\." 匹配 DCE 豆粕的 1 分钟数据）'
    )
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD（tqsdk 必填）")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD（tqsdk 必填）")
    p.add_argument("--strategy", required=True, help="策略名称 (e.g. ma/ma_strategy/ma_strategy.py)")
    p.add_argument("--capital", type=float, default=None, help="初始资金（默认从配置文件读取）")
    p.add_argument("--contract-size", type=int, default=None, help="合约乘数（默认从配置文件读取）")
    p.add_argument(
        "--gui", action="store_true", help="启用图形界面（仅 --engine tqsdk 生效，其他引擎下给 warning 后忽略）"
    )
    p.add_argument(
        "--mode",
        choices=["search", "walk-forward"],
        default="search",
        help="回测模式: search=参数搜索(默认), walk-forward=滚动验证（仅 --engine vnpy 生效）",
    )
    p.add_argument(
        "--optimizer",
        choices=["grid", "bayesian"],
        default=None,
        help="参数搜索引擎: grid=网格搜索, bayesian=贝叶斯优化 (默认读 TOML)",
    )
    p.add_argument("--trials", type=int, default=None, help="optimizer 最大试验次数（默认从配置文件读取）")
    p.add_argument("--parallel", action="store_true", help="启用多进程并行回测（默认关闭，仅 --engine vnpy 生效）")
    p.add_argument("--workers", type=int, default=None, help="并行进程数（默认 os.cpu_count()，仅 --parallel 时生效）")


def cmd_backtest(args: argparse.Namespace) -> None:
    """执行统一回测命令：根据 `--engine` + `--mode` 路由到对应的 workflow 入口"""
    _validate_cross_field(args)

    workflow = BacktestRunWorkflow()
    if args.engine == "vnpy":
        if args.mode == "walk-forward":
            workflow.run_vnpy_walk_forward(_build_walk_forward_request(args))
        else:
            workflow.run_vnpy_search(_build_search_request(args))
    elif args.engine == "tqsdk":
        workflow.run_tqsdk(_build_tqsdk_request(args))
    else:  # 实际由 argparse choices 已拦截，此处兜底
        raise ValueError(f"未知引擎: {args.engine!r}")


# ── 跨字段校验 ───────────────────────────────────────────


def _validate_cross_field(args: argparse.Namespace) -> None:
    """argparse 不能表达的跨字段约束集中在此

    例如 `--gui` 仅 tqsdk 下生效；TqSdk 必填项缺失需早期报错。
    """
    if args.gui and args.engine != "tqsdk":
        logger.warning("--gui 仅在 --engine tqsdk 下生效，已忽略当前 --gui 标志")

    if args.engine == "tqsdk":
        if not args.symbol:
            raise ValueError("--engine tqsdk 必须指定 --symbol")
        if not args.start or not args.end:
            raise ValueError("--engine tqsdk 必须显式指定 --start / --end")
        if args.mode != "search":
            logger.warning("--mode 仅在 --engine vnpy 下生效，TqSdk 路径已忽略")
        if args.parallel:
            logger.warning("--parallel 仅在 --engine vnpy 下生效，TqSdk 路径已忽略")


# ── argparse → request 翻译 ─────────────────────────────


def _build_search_request(args: argparse.Namespace) -> VnpySearchRequest:
    return VnpySearchRequest(
        strategy=args.strategy,
        capital=args.capital,
        contract_size=args.contract_size,
        symbol=args.symbol,
        pattern=args.pattern,
        start=args.start,
        end=args.end,
        optimizer=args.optimizer,
        trials=args.trials,
        parallel=bool(args.parallel),
        workers=args.workers,
    )


def _build_walk_forward_request(args: argparse.Namespace) -> VnpyWalkForwardRequest:
    return VnpyWalkForwardRequest(
        strategy=args.strategy,
        capital=args.capital,
        contract_size=args.contract_size,
        symbol=args.symbol,
        pattern=args.pattern,
        start=args.start,
        end=args.end,
    )


def _build_tqsdk_request(args: argparse.Namespace) -> TqsdkRequest:
    """构造 TqSdk 请求

    `_validate_cross_field` 已保证 symbol / start / end 非空，此处可安全使用。
    """
    assert args.symbol and args.start and args.end  # 由跨字段校验保证
    return TqsdkRequest(
        strategy=args.strategy,
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        capital=args.capital,
        gui=bool(args.gui),
    )
