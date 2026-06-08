"""
CLI 主入口模块

提供命令行参数解析和命令分发功能，是整个 CLI 系统的核心入口。

设计原则:
    - 单一职责: 只负责参数解析和命令路由
    - 无业务逻辑: 具体命令逻辑委托给各命令模块
    - 可扩展性: 支持动态添加新命令
"""

import argparse
import sys

from loguru import logger

from common.log_config import setup_logging
from config import ConfigManager

# 配置日志（必须在导入其他模块之前）
cm = ConfigManager()
log_cfg = cm.get_system_logging_config()
setup_logging(level=log_cfg.level, log_format=log_cfg.format)

from cli.commands.backtest import cmd_backtest  # noqa: E402
from cli.commands.export import cmd_export  # noqa: E402
from cli.commands.report import cmd_report  # noqa: E402
from cli.commands.tqsdk import cmd_live, cmd_test  # noqa: E402


def main() -> None:
    """CLI 主入口函数

    解析命令行参数并分发到对应的命令处理函数。
    """
    parser = argparse.ArgumentParser(
        description="策略工具箱 - 量化策略研发工具链",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例: python main.py backtest --strategy ma --symbol DCE.m2509",
    )
    sub = parser.add_subparsers(dest="command", title="子命令", required=True)

    # ---- export ----
    p = sub.add_parser(
        "export",
        help="导出Qlib格式CSV数据（支持多数据源，日期自动推算）",
        description="从指定数据源获取K线数据，导出为Qlib标准CSV格式\n\n"
        "日期默认由合约代码自动推算，例如 DCE.m2509 → 2025-05-01 ~ 2025-09-01",
    )
    p.add_argument("--symbol", required=True, help="品种代码，如 DCE.m2509")
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD（默认由合约自动推算）")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD（默认由合约自动推算）")
    p.add_argument("--source", default=None, choices=["tqsdk", "akshare"], help="数据源选择 (默认从配置文件读取)")
    p.add_argument("--interval", default="1m", choices=["1m", "5m", "15m", "30m", "1h", "1d"], help="K线周期 (默认 1m)")
    p.add_argument("--output", default=None, help="自定义输出路径（可选）")
    p.add_argument("--force", action="store_true", help="强制覆盖已有CSV和元数据")

    # ---- test（tqsdk 实时数据信号验证，不下单）----
    p = sub.add_parser(
        "test",
        help="通过天勤实时数据验证策略信号链路（不下单）",
        description="连接天勤实时行情驱动策略，打印交易信号用于验证链路正确性。\n\n"
        "安全保证：test 命令代码路径中不包含下单逻辑，即使账号已绑定期货公司也不会下单。",
    )
    p.add_argument("--strategy", required=True, help="策略名称 (e.g. ma/ma_strategy/ma_strategy.py)")
    p.add_argument("--symbol", required=True, help="合约代码 (e.g. SHFE.rb2509)")
    p.add_argument("--gui", action="store_true", help="启用浏览器可视化 (默认关闭)")

    # ---- backtest (统一回测命令) ----
    p = sub.add_parser(
        "backtest",
        help="统一回测（自动选择引擎）",
        description="""统一回测命令，根据标的数量自动选择回测引擎:

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
""",
    )
    p.add_argument("--symbol", default=None, help="品种代码（单品种模式，启用 TqSdk）")
    p.add_argument(
        "--pattern", default=None, help='文件名正则表达式（如 "DCE\\.m.*\\.1m\\." 匹配 DCE 豆粕的 1 分钟数据）'
    )
    p.add_argument("--start", default=None, help="开始日期 YYYY-MM-DD（可选）")
    p.add_argument("--end", default=None, help="结束日期 YYYY-MM-DD（可选）")
    p.add_argument("--strategy", required=True, help="策略名称 (e.g. ma/ma_strategy/ma_strategy.py)")
    p.add_argument("--capital", type=float, default=None, help="初始资金（默认从配置文件读取）")
    p.add_argument("--contract-size", type=int, default=None, help="合约乘数（默认从配置文件读取）")
    p.add_argument("--gui", action="store_true", help="启用图形界面（仅单品种模式生效）")
    p.add_argument(
        "--mode",
        choices=["search", "walk-forward"],
        default="search",
        help="回测模式: search=参数搜索(默认), walk-forward=滚动验证",
    )
    p.add_argument(
        "--optimizer",
        choices=["grid", "bayesian"],
        default=None,
        help="参数搜索引擎: grid=网格搜索, bayesian=贝叶斯优化 (默认读 TOML)",
    )
    p.add_argument("--trials", type=int, default=None, help="optimizer 最大试验次数（默认从配置文件读取）")

    # ---- report ----
    p = sub.add_parser(
        "report",
        help="管理与查看回测数据",
        description="""回测数据管理：列表、详情查看、数据清理、报告重建

用法:
  python main.py report                   列出最近 20 条回测
  python main.py report --id 42           查看指定回测详情
  python main.py report --clean 42        删除指定回测及关联数据
  python main.py report --build           重建所有运行的可视化报告
  python main.py report --build --run 1   重建指定运行的可视化报告
  python main.py report --symbol DCE.m2509  按品种过滤列表
  python main.py report --strategy ma      按策略名称过滤列表
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--id", type=int, default=None, help="查看指定 ID 的详细报告")
    p.add_argument("--clean", dest="clean_id", type=int, default=None, help="硬删除指定回测 ID 及关联数据 (不可撤销)")
    p.add_argument("--build", action="store_true", help="重建可视化 HTML 报告")
    p.add_argument("--run", type=int, default=None, dest="run_id", help="指定运行 ID (配合 --build 使用)")
    p.add_argument("--symbol", default=None, help="按品种代码过滤")
    p.add_argument("--strategy", default=None, help="按策略名称过滤")
    p.add_argument("--limit", type=int, default=20, help="列表最大条数 (默认 20)")

    # ---- live（天勤模拟/实盘交易）----
    p = sub.add_parser(
        "live",
        help="天勤模拟/实盘交易（会下单，模拟/实盘取决于账号是否绑定期货公司）",
        description="通过天勤 SDK 连接实时数据运行策略并下单。\n\n"
        "模拟 vs 实盘：取决于天勤账号是否绑定期货公司账户。\n"
        "  未绑定 → 模拟盘（虚拟资金，不影响真实账户）\n"
        "  已绑定 → 实盘（真金白银，慎用！）",
    )
    p.add_argument("--symbol", default="DCE.m2509", help="品种代码")
    p.add_argument("--gui", action="store_true", help="启用图形界面")
    p.add_argument("--config", default=None, help="配置文件路径")
    p.add_argument("--strategy", required=True, help="策略名称 (e.g. ma/ma_strategy/ma_strategy.py)")

    args = parser.parse_args()

    # 命令分发映射
    command_handlers = {
        "export": cmd_export,
        "test": cmd_test,
        "backtest": cmd_backtest,
        "report": cmd_report,
        "live": cmd_live,
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
