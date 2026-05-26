# -*- coding: utf-8 -*-
"""
数据导出命令模块

负责从数据源导出 K 线数据为 Qlib 标准 CSV 格式。

功能特点:
    - 从天勤获取历史 K 线数据
    - 支持去重合并
    - 输出标准 Qlib CSV 格式
"""

import argparse
import sys
import logging

from config import ConfigManager
from data import DataManager, export_csv

logger = logging.getLogger(__name__)


def cmd_export(args: argparse.Namespace):
    """执行数据导出命令

    从天勤获取指定品种的 K 线数据，导出为 Qlib 标准 CSV 格式。

    Args:
        args: argparse.Namespace 对象，包含:
            symbol: 品种代码
            start: 开始日期
            end: 结束日期
            output: 输出路径（可选）
            force: 是否强制覆盖
    """
    symbol: str = args.symbol  # pyright: ignore[reportAny]
    start: str = args.start  # pyright: ignore[reportAny]
    end: str = args.end  # pyright: ignore[reportAny]
    output: str | None = args.output  # pyright: ignore[reportAny]
    force: bool = args.force  # pyright: ignore[reportAny]

    cm = ConfigManager()
    dm = DataManager(cm)

    logger.info(f"数据导出: {symbol} {start} ~ {end}")
    dm.store.log('export', f"开始: {symbol} {start}~{end}",
           symbol=symbol, status='INFO')

    success = export_csv(
        symbol=symbol,
        start_date=start,
        end_date=end,
        dm=dm,
        config_manager=cm,
        output_path=output,
        force=force,
    )
    if success:
        logger.info("导出成功")
    else:
        logger.error("导出失败")
        sys.exit(1)