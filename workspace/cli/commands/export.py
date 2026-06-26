"""
数据导出命令模块

负责从数据源导出 K 线数据为 Qlib 标准 CSV 格式。

功能特点:
    - 支持多数据源切换（tqsdk / akshare）
    - 日期范围默认从合约代码自动推算（交割月前4个月到交割月）
    - 支持去重合并已有数据
"""

import argparse
import sys
from typing import Any

from data import export_csv
from loguru import logger

from cli.env import add_environment_arguments, build_data_context


def register(subparsers: Any) -> None:
    """注册 export 子命令的 argparse 选项

    `subparsers` 是 `parser.add_subparsers()` 返回的对象（`argparse._SubParsersAction`），
    其类型在 argparse 中是私有的，因此使用 `Any` 表示。
    """
    p = subparsers.add_parser(
        "export",
        help="导出Qlib格式CSV数据（支持多数据源，日期自动推算）",
        description="从指定数据源获取K线数据，导出为Qlib标准CSV格式\n\n"
        "日期默认由合约代码自动推算，例如 DCE.m2509 → 2025-05-01 ~ 2025-09-01",
    )
    p.add_argument("--symbol", required=True, help="品种代码，如 DCE.m2509")
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD（默认由合约自动推算）")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD（默认由合约自动推算）")
    p.add_argument("--source", default=None, choices=["tqsdk", "akshare"], help="数据源选择 (默认从配置文件读取)")
    p.add_argument(
        "--interval",
        default="1m",
        choices=["1m", "5m", "15m", "30m", "1h", "1d"],
        help="K线周期 (默认 1m)",
    )
    p.add_argument("--output", default=None, help="自定义输出路径（可选）")
    p.add_argument("--force", action="store_true", help="强制覆盖已有CSV和元数据")
    add_environment_arguments(p)


def cmd_export(args: argparse.Namespace) -> None:
    """执行数据导出命令

    Args:
        args: argparse.Namespace 对象，包含:
            symbol: 品种代码
            start: 开始日期（可选）
            end: 结束日期（可选）
            source: 数据源（可选）
            interval: K线周期（默认 1m）
            output: 输出路径（可选）
            force: 是否强制覆盖
    """
    symbol: str = args.symbol  # pyright: ignore[reportAny]
    start: str | None = args.start  # pyright: ignore[reportAny]
    end: str | None = args.end  # pyright: ignore[reportAny]
    source: str | None = args.source  # pyright: ignore[reportAny]
    interval: str = getattr(args, "interval", "1m")  # pyright: ignore[reportAny]
    output: str | None = args.output  # pyright: ignore[reportAny]
    force: bool = args.force  # pyright: ignore[reportAny]

    cm, dm = build_data_context(args, "export")

    date_hint = f"{start or 'auto'} ~ {end or 'auto'}"
    logger.info(f"数据导出: {symbol} {date_hint} [source={source or 'default'}, interval={interval}]")
    dm.store.log("export", f"开始: {symbol} {date_hint} [source={source or 'default'}]", symbol=symbol, status="INFO")

    success = export_csv(
        symbol=symbol,
        start_date=start,
        end_date=end,
        dm=dm,
        config_manager=cm,
        output_path=output,
        force=force,
        interval=interval,
        source=source,
    )
    if success:
        logger.info("导出成功")
    else:
        logger.error("导出失败")
        sys.exit(1)
