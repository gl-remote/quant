"""报表工作流（阶段 8：统一报表生成入口）

把"给定 run_id 生成报表"和"查询/删除回测"统一到 `ReportWorkflow`，
消除 `cmd_report --build` 与 `RunFinalizer` 各自编排报表的双轨局面。

设计要点：
- `build(request)` 串联 data_exports → frontend →（可选 hook）→ entry_html。
  hook 在 frontend 之后、entry_html 之前执行，供 `RunFinalizer` 注入
  "detach 日志 sink → 导出 logs.json"，确保 logs.json 在打包入口 HTML 前就绪。
- `cmd_report --build` 不传 hook，走全量重建；`RunFinalizer` 传 hook，走增量。
- workflow 只关心 run_id，不感知调用方是 CLI 还是其他 workflow。

工作流间调用规则：commands → workflow 单向；workflow 可委托另一个 workflow
（如 RunFinalizer → ReportWorkflow），只要被调用方不反向依赖 commands 层。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from data.manager import DataManager


# ── 请求对象 ─────────────────────────────────────────────


@dataclass(frozen=True)
class ReportBuildRequest:
    """报表构建请求

    Attributes:
        run_id: 目标运行 ID
        incremental: 是否启用基于数据指纹的增量导出（手动重建用 False，run 收尾用 True）
        output_dir: 输出目录，None 时取 output_root()
        before_entry_html: frontend 之后、entry_html 之前执行的回调（如导出 logs.json）
    """

    run_id: int
    incremental: bool = True
    output_dir: str | None = None
    before_entry_html: Callable[[], None] | None = None


@dataclass(frozen=True)
class ReportSummaryRequest:
    """回测汇总查询请求"""

    symbol: str | None = None
    strategy: str | None = None
    limit: int = 20


@dataclass(frozen=True)
class ReportDetailRequest:
    """单条回测详情查询请求"""

    backtest_id: int


@dataclass(frozen=True)
class ReportDeleteRequest:
    """回测硬删除请求"""

    backtest_id: int


# ── Workflow ─────────────────────────────────────────────


class ReportWorkflow:
    """统一报表生成与查询入口。

    `cmd_report` 与 `RunFinalizer` 都通过本类生成报表，消除双轨编排。
    """

    def __init__(self, dm: DataManager) -> None:
        self._dm = dm

    def build(self, request: ReportBuildRequest) -> None:
        """串联 data_exports → frontend →（可选 hook）→ entry_html

        执行步骤：
        1. 导出 JSON 数据文件（incremental 时基于数据指纹对比）
        2. 构建 React 前端
        3. 执行 before_entry_html 回调（如有）
        4. 写入入口 HTML（仅在有数据变更时）
        """
        from report.builder import build_frontend, run_data_exports, write_entry_html

        output_dir = request.output_dir or str(_output_root())
        start_time = time.time()
        success_count = 0
        failed_tasks: list[tuple[str, str]] = []

        logger.info(
            "开始构建报告: run_id={}, output_dir={}, incremental={}",
            request.run_id,
            output_dir,
            request.incremental,
        )

        exported, skipped = run_data_exports(output_dir, request.run_id, incremental=request.incremental, dm=self._dm)
        success_count += exported
        has_data_change = exported > 0 or not request.incremental

        try:
            build_frontend(output_dir)
            logger.info("✓ 构建前端完成")
            success_count += 1
        except Exception as e:
            logger.error("✗ 构建前端失败: {}", str(e))
            failed_tasks.append(("构建前端", str(e)))

        if request.before_entry_html is not None:
            # hook 通常会改写 logs.json 等数据文件，必须重新打包入口 HTML
            request.before_entry_html()
            has_data_change = True

        if has_data_change:
            try:
                write_entry_html(output_dir)
                logger.info("✓ 写入入口HTML完成")
                success_count += 1
            except Exception as e:
                logger.error("✗ 写入入口HTML失败: {}", str(e))
                failed_tasks.append(("写入入口HTML", str(e)))
        else:
            logger.info("○ 数据未变更，跳过写入入口HTML")

        duration = time.time() - start_time
        logger.info(
            "报告构建结束: 成功={}, 跳过={}, 失败={}, 耗时={:.2f}s",
            success_count,
            skipped,
            len(failed_tasks),
            duration,
        )
        if failed_tasks:
            logger.warning("失败任务列表:")
            for task_name, error in failed_tasks:
                logger.warning("  - {}: {}", task_name, error)

    def get_summary(self, request: ReportSummaryRequest) -> str:
        """生成回测汇总文本报告"""
        from report import format_summary_report

        return format_summary_report(
            self._dm,
            symbol=request.symbol,
            strategy=request.strategy,
            limit=request.limit,
        )

    def get_detail(self, request: ReportDetailRequest) -> str:
        """生成单条回测详情文本报告"""
        from report import format_single_report

        return format_single_report(self._dm, request.backtest_id)

    def delete_backtest(self, request: ReportDeleteRequest) -> bool:
        """硬删除回测记录及关联数据"""
        return self._dm.delete_backtest(request.backtest_id)


def _output_root() -> str:
    """延迟导入避免循环依赖"""
    from data.output_paths import output_root

    return str(output_root())
