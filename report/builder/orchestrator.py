"""报告构建编排

`build_all` 薄封装：按 数据导出 → 前端构建 → 入口 HTML 打包 顺序串联三个独立环节。

供 `cli/commands/report.py` 手动重建报告使用。run 收尾路径（RunFinalizer）
则直接调用三个环节以精确控制时序（如 logs.json 落盘后再打包 HTML）。
"""

from __future__ import annotations

import time

from loguru import logger

from data import DataManager

from .data_exports import run_data_exports
from .entry_html import write_entry_html
from .frontend import build_frontend


def build_all(output_dir: str, run_id: int, incremental: bool = True) -> None:
    """回测完成后统一入口，生成完整报告

    执行步骤：
    1. 增量导出 JSON 数据文件（基于数据指纹对比）
    2. 构建 React 前端
    3. 写入入口 HTML（仅在有数据变更时）
    """
    start_time = time.time()
    success_count = 0
    skip_count = 0
    failed_tasks: list[tuple[str, str]] = []

    logger.info("开始构建报告: run_id={}, output_dir={}, incremental={}", run_id, output_dir, incremental)

    dm = DataManager()

    exported, skipped = run_data_exports(output_dir, run_id, incremental=incremental, dm=dm)
    success_count += exported
    skip_count += skipped
    has_data_change = exported > 0 or not incremental

    # 构建前端
    try:
        build_frontend(output_dir)
        logger.info("✓ 构建前端完成")
        success_count += 1
    except Exception as e:
        logger.error("✗ 构建前端失败: {}", str(e))
        failed_tasks.append(("构建前端", str(e)))

    # 写入入口 HTML
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
        "报告构建结束: 成功={}, 跳过={}, 失败={}, 耗时={:.2f}s", success_count, skip_count, len(failed_tasks), duration
    )

    if failed_tasks:
        logger.warning("失败任务列表:")
        for task_name, error in failed_tasks:
            logger.warning("  - {}: {}", task_name, error)
