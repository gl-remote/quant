# -*- coding: utf-8 -*-
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
import logging

from config import ConfigManager
from data import DataManager, export_csv

logger = logging.getLogger(__name__)


def cmd_export(args: argparse.Namespace):
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
    interval: str = getattr(args, 'interval', '1m')  # pyright: ignore[reportAny]
    output: str | None = args.output  # pyright: ignore[reportAny]
    force: bool = args.force  # pyright: ignore[reportAny]

    cm = ConfigManager()
    dm = DataManager(cm)

    date_hint = f"{start or 'auto'} ~ {end or 'auto'}"
    logger.info(f"数据导出: {symbol} {date_hint} [source={source or 'default'}, interval={interval}]")
    dm.store.log('export', f"开始: {symbol} {date_hint} [source={source or 'default'}]",
                 symbol=symbol, status='INFO')

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
