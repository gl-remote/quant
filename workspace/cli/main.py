"""
CLI 主入口模块

提供命令行参数解析和命令分发功能，是整个 CLI 系统的核心入口。

设计原则:
    - 单一职责: 只负责子命令注册与分发
    - 无业务逻辑: 具体命令逻辑、argparse 选项定义都委托给各命令模块
    - 可扩展性: 新增命令只需在 commands/ 下加文件并在此处注册
"""

import argparse
import sys

from common.log_config import setup_logging
from config import ConfigManager
from loguru import logger

# 配置日志（必须在导入其他模块之前）
cm = ConfigManager()
log_cfg = cm.get_system_logging_config()
setup_logging(level=log_cfg.level, log_format=log_cfg.format)

from cli.commands import backtest as backtest_cmd  # noqa: E402
from cli.commands import export as export_cmd  # noqa: E402
from cli.commands import live as live_cmd  # noqa: E402
from cli.commands import report as report_cmd  # noqa: E402
from cli.commands import test as test_cmd  # noqa: E402


def main() -> None:
    """CLI 主入口函数

    解析命令行参数并分发到对应的命令处理函数。argparse 选项的具体定义由
    各命令模块的 `register(subparsers)` 函数负责，main 仅做注册与分发。
    """
    parser = argparse.ArgumentParser(
        description="策略工具箱 - 量化策略研发工具链",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例: python main.py backtest --strategy ma --symbol DCE.m2509",
    )
    sub = parser.add_subparsers(dest="command", title="子命令", required=True)

    # 注册子命令（args 定义在各命令模块内）
    export_cmd.register(sub)
    test_cmd.register(sub)
    backtest_cmd.register(sub)
    report_cmd.register(sub)
    live_cmd.register(sub)

    args = parser.parse_args()

    # 命令分发映射
    command_handlers = {
        "export": export_cmd.cmd_export,
        "test": test_cmd.cmd_test,
        "backtest": backtest_cmd.cmd_backtest,
        "report": report_cmd.cmd_report,
        "live": live_cmd.cmd_live,
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
