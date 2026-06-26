"""项目本地数据目录路径

统一管理 ``project_data/`` 下的本地数据、报告、日志、缓存和诊断产物路径。
业务代码应通过本模块获取本地数据路径。
"""

from __future__ import annotations

from pathlib import Path

from config.schemas import DataEnvironment

# 从本文件位置推算项目根（workspace/data/output_paths.py → data/ → workspace/ → 项目根/）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def project_root() -> Path:
    """返回项目根目录。"""
    return _PROJECT_ROOT


def project_data_root() -> Path:
    """返回项目本地数据根目录: <项目根>/project_data/。"""
    return _PROJECT_ROOT / "project_data"


def market_data_dir() -> Path:
    """返回行情数据目录。"""
    return project_data_root() / "market_data"


def market_csv_dir() -> Path:
    """返回 CSV K 线数据目录。"""
    return market_data_dir() / "csv"


def database_root() -> Path:
    """返回 SQLite 数据库根目录。"""
    return project_data_root() / "database"


def database_dir() -> Path:
    """返回 SQLite 数据库根目录。"""
    return database_root()


def database_environment_dir(env: DataEnvironment) -> Path:
    """返回指定数据环境的 SQLite 数据库目录。"""
    return database_root() / env


def database_path(env: DataEnvironment) -> Path:
    """返回指定数据环境的 SQLite 数据库路径。"""
    return database_environment_dir(env) / "quant.db"


def reports_root() -> Path:
    """返回报告产物根目录。"""
    return project_data_root() / "reports"


def cache_root() -> Path:
    """返回可重建缓存根目录。"""
    return project_data_root() / "cache"


def report_build_cache_dir() -> Path:
    """返回报告增量构建缓存目录。"""
    return cache_root() / "report_build"


def kline_json_cache_dir() -> Path:
    """返回 K 线 JSON 转换缓存目录。"""
    return cache_root() / "kline_json"


def datafeed_cache_dir() -> Path:
    """返回 DataFeed 磁盘缓存目录。"""
    return cache_root() / "datafeed"


def logs_root() -> Path:
    """返回原始运行日志根目录。"""
    return project_data_root() / "logs"


def run_logs_dir(run_id: int) -> Path:
    """返回指定 run 的原始日志目录。"""
    return logs_root() / "runs" / f"r{run_id}"


def worker_logs_dir(run_id: int) -> Path:
    """返回指定 run 的 worker 原始日志目录。"""
    return run_logs_dir(run_id) / "workers"


def profiles_dir() -> Path:
    """返回性能分析文件目录。"""
    return project_data_root() / "profiles"


def coverage_dir() -> Path:
    """返回测试覆盖率 HTML 目录。"""
    return project_data_root() / "coverage"
