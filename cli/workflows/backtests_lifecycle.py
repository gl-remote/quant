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
        """内部收尾，单调线性时序（每步只做一件事）：

        1. finish_run        — DB 状态标记，让数据导出读到最新 status
        2. run_data_exports  — 导出业务数据 JSON
        3. build_frontend    — 构建前端 bundle（增量可跳过）
        4. detach            — 停止写 run.log，避免后续日志污染 logs.json
        5. export_json       — run.log + worker 日志 → logs.json
        6. write_entry_html  — 最后一步，此时所有 JSON（含 logs.json）已就绪，只打包一次
        """
        from report.builder import build_frontend, run_data_exports, write_entry_html

        output_dir = str(_output_root())
        self._dm.store.finish_run(run_id, status)
        run_data_exports(output_dir, run_id)
        build_frontend(output_dir)
        self._helper.detach()
        self._helper.export_json(run_id)
        write_entry_html(output_dir)

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
        """执行失败（异常路径，标记状态 → detach sink → 导出日志 → 打包入口 HTML，不构建前端）"""
        from report.builder import write_entry_html

        self._dm.store.finish_run(run_id, "failed")
        self._helper.detach()
        self._helper.export_json(run_id)
        write_entry_html(str(_output_root()))


def _output_root() -> Path:
    """延迟导入避免循环依赖"""
    from data.output_paths import output_root as _or

    return _or()
