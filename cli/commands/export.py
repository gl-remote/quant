# -*- coding: utf-8 -*-
"""
数据导出命令模块

负责从数据源导出 K 线数据为 Qlib 标准 CSV 格式。

功能特点:
    - 从天勤获取历史 K 线数据
    - 支持去重合并
    - 输出标准 Qlib CSV 格式
"""

import sys
import logging

from config import ConfigManager
from data import DataManager, export_csv

logger = logging.getLogger(__name__)


def cmd_export(args):
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
    cm = ConfigManager()
    dm = DataManager(cm)

    logger.info(f"数据导出: {args.symbol} {args.start} ~ {args.end}")
    dm.store.log('export', f"开始: {args.symbol} {args.start}~{args.end}",
           symbol=args.symbol, status='INFO')

    success = export_csv(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        dm=dm,
        config_manager=cm,
        output_path=args.output,
        force=args.force,
    )
    if success:
        logger.info("导出成功")
    else:
        logger.error("导出失败")
        sys.exit(1)