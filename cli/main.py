# -*- coding: utf-8 -*-
"""
CLI 主入口模块

提供命令行参数解析和命令分发功能，是整个 CLI 系统的核心入口。

设计原则:
    - 单一职责: 只负责参数解析和命令路由
    - 无业务逻辑: 具体命令逻辑委托给各命令模块
    - 可扩展性: 支持动态添加新命令
"""

import sys
import argparse
import logging

from config import ConfigManager
from common.constants import DEFAULT_INITIAL_CAPITAL

# 配置日志（必须在导入其他模块之前）
cm = ConfigManager()
log_cfg = cm.get_system_logging_config()
logging.basicConfig(
    level=getattr(logging, log_cfg.get('level', 'INFO'), logging.INFO),
    format=log_cfg.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)

from cli.commands.export import cmd_export
from cli.commands.test import cmd_test
from cli.commands.backtest import cmd_backtest
from cli.commands.live import cmd_live
from cli.commands.report import cmd_report

logger = logging.getLogger(__name__)


def main():
    """CLI 主入口函数

    解析命令行参数并分发到对应的命令处理函数。
    """
    parser = argparse.ArgumentParser(
        description='天勤量化均线交叉策略交易系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例: python main.py backtest --strategy ma --symbol DCE.m2509"
    )
    sub = parser.add_subparsers(dest='command', title='子命令', required=True)

    # ---- export ----
    p = sub.add_parser(
        'export',
        help='导出Qlib格式CSV数据（含去重合并）',
        description='从天勤获取K线数据，导出为Qlib标准CSV格式'
    )
    p.add_argument('--symbol', required=True, help='品种代码，如 DCE.m2509')
    p.add_argument('--start', required=True, help='开始日期 YYYY-MM-DD')
    p.add_argument('--end', required=True, help='结束日期 YYYY-MM-DD')
    p.add_argument('--output', default=None, help='自定义输出路径（可选）')
    p.add_argument('--force', action='store_true', help='强制覆盖已有CSV和元数据')

    # ---- test ----
    p = sub.add_parser('test', help='本地策略逻辑测试（不联网）')
    p.add_argument('--strategy', default=None,
                   help='策略名称 (e.g. ma/ma_strategy/ma_strategy.py)，默认 ma')

    # ---- backtest (统一回测命令) ----
    p = sub.add_parser(
        'backtest',
        help='统一回测（自动选择引擎）',
        description='''统一回测命令，根据标的数量自动选择回测引擎:

单标的模式: 当使用 --symbol 指定单一品种时，自动使用 TqSdk 进行图形化回测
  - 支持 GUI 界面展示
  - 实时查看回测过程
  - 示例: python main.py backtest --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31 --gui

批量模式: 当使用 --pattern 或省略 --symbol 时，自动使用 vn.py 进行批量回测
  - 支持正则表达式匹配多个品种
  - 仅生成文字报告
  - 数据自动落地到数据库
  - 示例: python main.py backtest --pattern "DCE\\.m"
          python main.py backtest  # 扫描全部品种

回测结果均会自动保存到数据库，可使用 report 命令查看详情。
'''
    )
    p.add_argument('--symbol', default=None, help='品种代码（单品种模式，启用 TqSdk）')
    p.add_argument('--pattern', default=None, help='品种代码正则表达式（批量模式，启用 vn.py）')
    p.add_argument('--start', default=None, help='开始日期 YYYY-MM-DD（可选）')
    p.add_argument('--end', default=None, help='结束日期 YYYY-MM-DD（可选）')
    p.add_argument('--strategy', default=None,
                   help='策略名称 (e.g. ma/ma_strategy/ma_strategy.py)，默认 ma')
    p.add_argument('--capital', type=float, default=DEFAULT_INITIAL_CAPITAL, help='初始资金（默认 100000）')
    p.add_argument('--gui', action='store_true', help='启用图形界面（仅单品种模式生效）')

    # ---- report ----
    p = sub.add_parser(
        'report',
        help='管理与查看回测数据',
        description='回测数据管理：列表、详情查看、数据清理\n\n'
                    '用法:\n'
                    '  python main.py report                   列出最近 20 条回测\n'
                    '  python main.py report --id 42           查看指定回测详情\n'
                    '  python main.py report --clean 42        删除指定回测及关联数据\n'
                    '  python main.py report --symbol DCE.m2509 按品种过滤列表'
    )
    p.add_argument('--id', type=int, default=None, help='查看指定 ID 的详细报告')
    p.add_argument('--clean', dest='clean_id', type=int, default=None,
                   help='硬删除指定回测 ID 及关联数据 (不可撤销)')
    p.add_argument('--symbol', default=None, help='按品种代码过滤')
    p.add_argument('--strategy', default=None, help='按策略名称过滤')
    p.add_argument('--limit', type=int, default=20, help='列表最大条数 (默认 20)')

    # ---- live ----
    p = sub.add_parser('live', help='实盘/模拟交易')
    p.add_argument('--symbol', default='DCE.m2509', help='品种代码')
    p.add_argument('--gui', action='store_true', help='启用图形界面')
    p.add_argument('--config', default=None, help='配置文件路径')
    p.add_argument('--strategy', default=None,
                   help='策略名称 (e.g. ma/ma_strategy/ma_strategy.py)，默认 ma')

    args = parser.parse_args()

    # 命令分发映射
    command_handlers = {
        'export': cmd_export,
        'test': cmd_test,
        'backtest': cmd_backtest,
        'report': cmd_report,
        'live': cmd_live,
    }

    try:
        handler = command_handlers.get(args.command)
        if handler:
            handler(args)
        else:
            logger.error(f"未知命令: {args.command}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n用户中断程序")
    except Exception as e:
        logger.error(f"程序执行错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()