# -*- coding: utf-8 -*-
"""
报告生成命令模块

从数据库读取回测结果并生成格式化报告。

功能特点:
    - 单次回测详细报告
    - 多次回测对比报告
    - 汇总列表报告
    - 支持 JSON 输出
"""

import sys
import logging

from config import ConfigManager
from data import DataManager
from report import format_single_report, format_comparison_report, format_summary_report
from common.constants import DEFAULT_REPORT_OUTPUT_DIR

logger = logging.getLogger(__name__)


def cmd_report(args):
    """执行报告生成命令

    从数据库读取回测结果并生成格式化报告，完全解耦于回测执行。

    Args:
        args: argparse.Namespace 对象，包含:
            id: 回测 ID（单次报告模式）
            compare: 逗号分隔的回测 ID 列表（对比模式）
            symbol: 按品种过滤（汇总模式）
            strategy: 按策略过滤（汇总模式）
            limit: 汇总模式最大条数
            save_json: 是否保存 JSON 文件
    """
    cm = ConfigManager()
    dm = DataManager(cm)

    try:
        if args.id is not None:
            report = format_single_report(dm, args.id)
            print(report)

        elif args.compare:
            try:
                ids = [int(i.strip()) for i in args.compare.split(',') if i.strip()]
            except ValueError:
                print("错误: --compare 参数格式无效，请使用逗号分隔的整数 ID，如 '1,2,3'")
                sys.exit(1)
            if not ids:
                print("错误: --compare 需要至少一个 ID")
                sys.exit(1)

            report = format_comparison_report(
                dm, ids,
                save_json=args.save_json,
                output_dir=cm.get_backtest_config().get('report', {}).get(
                    'output_dir', DEFAULT_REPORT_OUTPUT_DIR),
            )
            print(report)

        else:
            report = format_summary_report(
                dm,
                symbol=args.symbol,
                strategy=args.strategy,
                limit=args.limit or 20,
            )
            print(report)

    except Exception as e:
        logger.error(f"生成报告失败: {e}", exc_info=True)
        sys.exit(1)