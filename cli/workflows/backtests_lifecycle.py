"""批量回测运行生命周期管理

- RunLogHelper：file log sink 的挂载/卸载/导出
- RunFinalizer：run 结束时统一收尾（日志导出 → 看板构建 → 状态标记）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from report.output_paths import logs_json_path, run_log_path, workers_dir

if TYPE_CHECKING:
    from data.manager import DataManager


class RunLogHelper:
    """管理 run 级 file log sink 生命周期

    Usage::

        helper = RunLogHelper()
        helper.attach(run_id)
        ...
        helper.detach()
        helper.export_json(run_id)
    """

    def __init__(self) -> None:
        self._sink_id: int | None = None

    def attach(self, run_id: int) -> None:
        """开启 file sink：DEBUG 级别全量写入 output/r{run_id}/data/run.log

        保留 stderr 输出不变。
        """
        log_path = run_log_path(run_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        fmt = (
            f"{{time:YYYY-MM-DD HH:mm:ss.SSS}} | [r{run_id}{{extra[bt_id]}}] "
            "{level: <8} | {name}:{function}:{line} | {message}"
        )
        self._sink_id = logger.add(
            str(log_path),
            level="DEBUG",
            format=fmt,
        )

    def detach(self) -> None:
        """移除 file sink，stderr 输出保持不变"""
        if self._sink_id is not None:
            logger.remove(self._sink_id)
            self._sink_id = None

    def export_json(self, run_id: int) -> None:
        """将 run.log + workers/*.log 合并写入 logs.json（前端可读）"""
        logger.complete()  # 确保所有缓冲日志落盘

        parts: list[str] = []

        # 主日志
        main_log = run_log_path(run_id)
        if main_log.exists():
            parts.append(main_log.read_text(encoding="utf-8"))

        # 并行 worker 日志
        wdir = workers_dir(run_id)
        if wdir.is_dir():
            for wf in sorted(wdir.glob("worker_*.log")):
                parts.append(f"\n=== {wf.name} ===\n")
                parts.append(wf.read_text(encoding="utf-8"))

        json_file = logs_json_path(run_id)
        json_file.write_text(json.dumps("".join(parts), ensure_ascii=False), encoding="utf-8")


class RunFinalizer:
    """统一 run 收尾动作

    确保正确的执行时序：
    1. 先 finish_run（DB 状态标记，让 build_dashboard 读到最新状态）
    2. 再 build_dashboard（report 日志进入 run.log，run.json 获取正确 status）
    3. 最后 export_json（此时日志完整）
    """

    def __init__(self, dm: DataManager, helper: RunLogHelper | None = None) -> None:
        self._dm = dm
        self._helper = helper or RunLogHelper()

    def _finalize(self, run_id: int, status: str) -> None:
        """内部收尾：标记状态 → 构建看板 → detach sink → 导出日志 → 重写入口 HTML

        detach 必须在 export_json 之前完成：
        - 否则 build_dashboard 之后的日志（write_entry_html、preload script）
          会继续写入 run.log，但 logs.json 已生成完毕，导致前端看不到这部分。
        - detach 后，后续的 write_entry_html 日志只输出到 stderr，不污染 logs.json。
        """
        from report.builder import build_all as build_dashboard
        from report.builder import write_entry_html

        output_dir = str(_output_root())
        self._dm.store.finish_run(run_id, status)
        build_dashboard(output_dir=output_dir, run_id=run_id)
        self._helper.detach()
        self._helper.export_json(run_id)
        # export_json 之后 logs.json 才落盘，需要重写入口 HTML 将其注入预加载
        write_entry_html(output_dir=output_dir)

    def finish_success(self, run_id: int) -> None:
        """正常完成"""
        self._finalize(run_id, "success")

    def finish_skipped(self, run_id: int) -> None:
        """搜索空间为空，跳过"""
        self._finalize(run_id, "skipped")

    def finish_no_result(self, run_id: int) -> None:
        """无有效结果"""
        self._finalize(run_id, "no_result")

    def finish_failed(self, run_id: int, error: str) -> None:
        """执行失败（异常路径，标记状态 → detach sink → 导出日志 → 重写入口 HTML，不构建看板）"""
        from report.builder import write_entry_html

        self._dm.store.finish_run(run_id, "failed")
        self._helper.detach()
        self._helper.export_json(run_id)
        write_entry_html(output_dir=str(_output_root()))


def _output_root() -> Path:
    """延迟导入避免循环依赖"""
    from data.output_paths import output_root as _or

    return _or()
