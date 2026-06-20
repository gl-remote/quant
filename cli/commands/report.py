"""
回测数据管理命令

管理已完成的回测数据: 列表、详情查看、数据清理。

子命令:
    list:         列出可用的回测记录 (默认)
    show <id>:    展示指定回测的详细报告
    --clean <id>: 硬删除指定回测记录及关联数据
"""

import argparse
import sys
from typing import Any

from loguru import logger

from config import ConfigManager
from data import DataManager
from data.output_paths import output_root
from report import build_all, format_single_report, format_summary_report


def register(subparsers: Any) -> None:
    """注册 report 子命令的 argparse 选项

    `subparsers` 是 `parser.add_subparsers()` 返回的对象（`argparse._SubParsersAction`），
    其类型在 argparse 中是私有的，因此使用 `Any` 表示。
    """
    p = subparsers.add_parser(
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


def cmd_report(args: argparse.Namespace) -> None:
    """回测数据管理入口

    Args:
        args: argparse.Namespace，包含:
            id:       回测 ID (show 模式)
            clean_id: 要删除的回测 ID (--clean)
            build:    是否重建可视化报告 (--build)
            run_id:   指定运行 ID (--run，配合 --build)
            symbol:   按品种过滤 (list 模式)
            strategy: 按策略过滤 (list 模式)
            limit:    最大条数 (list 模式)
    """
    if args.build:
        _cmd_build(args.run_id)
        return

    cm = ConfigManager()
    dm = DataManager(cm)

    try:
        if args.clean_id is not None:
            _cmd_clean(dm, args.clean_id)
        elif args.id is not None:
            _cmd_show(dm, args.id)
        else:
            _cmd_list(dm, args.symbol, args.strategy, args.limit or 20)

    except Exception as e:
        logger.exception(f"report 命令执行失败: {e}")
        sys.exit(1)


def _cmd_list(dm: DataManager, symbol: str | None = None, strategy: str | None = None, limit: int = 20) -> None:
    """列出回测记录"""
    report = format_summary_report(dm, symbol=symbol, strategy=strategy, limit=limit)
    print(report)


def _cmd_show(dm: DataManager, backtest_id: int) -> None:
    """展示单条回测详细报告"""
    report = format_single_report(dm, backtest_id)
    print(report)

    print("\n💡 可视化报告: python main.py report --build  (或打开 output/index.html)")


def _cmd_build(run_id: int | None = None) -> None:
    """重建可视化 HTML 报告

    Args:
        run_id: 指定重建某个 run（None 则重建所有）
    """
    if run_id is not None:
        # 重建指定 run
        print(f"重建运行 r{run_id} 的可视化报告...")
        build_all(output_dir=str(output_root()), run_id=run_id, incremental=False)
    else:
        # 重建所有 run（从数据库查询，不依赖 output 目录）
        print("重建所有运行的可视化报告...")
        cm = ConfigManager()
        dm = DataManager(cm)
        runs = dm.get_all_runs()
        dm.close()
        if not runs:
            print("没有找到运行记录")
            return
        for r in runs:
            rid = r["id"]
            print(f"  → 重建 r{rid}...")
            build_all(output_dir=str(output_root()), run_id=int(str(rid)), incremental=False)
    print("完成。")


def _cmd_clean(dm: DataManager, backtest_id: int) -> None:
    """硬删除回测记录"""
    print(f"\n⚠️  即将删除回测记录 id={backtest_id} 及其所有关联数据")
    print("   此操作不可撤销！\n")

    confirm = input("   确认删除？[y/N] ").strip().lower()
    if confirm not in ("y", "yes"):
        print("   已取消。")
        return

    ok = dm.delete_backtest(backtest_id)
    if ok:
        print(f"   ✓ 已删除回测记录 id={backtest_id}")
    else:
        print(f"   ✗ 删除失败: 回测记录 id={backtest_id} 不存在或数据库异常")
