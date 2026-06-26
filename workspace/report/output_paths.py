"""报告域输出路径

定义 report 生成物与日志派生文件路径。
原始日志位于 ``project_data/logs``，报告消费的 ``logs.json`` 位于 report run data 目录。
"""

from __future__ import annotations

from pathlib import Path

from data.output_paths import reports_root, run_logs_dir, worker_logs_dir


def report_assets_dir() -> Path:
    """project_data/reports/assets/"""
    return reports_root() / "assets"


def report_runs_root() -> Path:
    """project_data/reports/runs/"""
    return reports_root() / "runs"


def run_report_dir(run_id: int) -> Path:
    """project_data/reports/runs/r{run_id}/"""
    return report_runs_root() / f"r{run_id}"


def run_report_data_dir(run_id: int) -> Path:
    """project_data/reports/runs/r{run_id}/data/"""
    return run_report_dir(run_id) / "data"


def run_dir(run_id: int) -> Path:
    """兼容历史名称，返回 report run 目录。"""
    return run_report_dir(run_id)


def run_data_dir(run_id: int) -> Path:
    """兼容历史名称，返回 report run data 目录。"""
    return run_report_data_dir(run_id)


def run_log_path(run_id: int) -> Path:
    """project_data/logs/runs/r{run_id}/run.log"""
    return run_logs_dir(run_id) / "run.log"


def logs_json_path(run_id: int) -> Path:
    """project_data/reports/runs/r{run_id}/data/logs.json"""
    return run_report_data_dir(run_id) / "logs.json"


def nav_json_path() -> Path:
    """project_data/reports/data/nav.json"""
    return reports_root() / "data" / "nav.json"


def report_nav_path() -> Path:
    """project_data/reports/data/nav.json"""
    return nav_json_path()


def workers_dir(run_id: int) -> Path:
    """project_data/logs/runs/r{run_id}/workers/"""
    return worker_logs_dir(run_id)
