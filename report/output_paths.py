"""报告域输出路径

定义 run 维度下的文件路径约定，底层调用 data.output_paths.output_root() 拼接。
"""

from __future__ import annotations

from pathlib import Path

from data.output_paths import output_root


def run_dir(run_id: int) -> Path:
    """output/r{run_id}/"""
    return output_root() / f"r{run_id}"


def run_data_dir(run_id: int) -> Path:
    """output/r{run_id}/data/"""
    return run_dir(run_id) / "data"


def run_log_path(run_id: int) -> Path:
    """output/r{run_id}/data/run.log"""
    return run_data_dir(run_id) / "run.log"


def logs_json_path(run_id: int) -> Path:
    """output/r{run_id}/data/logs.json"""
    return run_data_dir(run_id) / "logs.json"


def nav_json_path() -> Path:
    """output/data/nav.json（全局导航数据）"""
    return output_root() / "data" / "nav.json"
