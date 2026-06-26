"""CLI data environment 参数与校验。"""

from __future__ import annotations

import argparse
from typing import Any

from config import CLI_DATA_ENVIRONMENTS, ConfigManager
from data import DataManager
from loguru import logger

COMMAND_ALLOWED_ENVS: dict[str, set[str]] = {
    "export": set(CLI_DATA_ENVIRONMENTS),
    "backtest": {"backtest"},
    "report": set(CLI_DATA_ENVIRONMENTS),
    "test": {"test"},
    "live": {"live"},
}


def add_environment_arguments(parser: Any) -> None:
    parser.add_argument("--env", choices=sorted(CLI_DATA_ENVIRONMENTS), default=None, help="数据环境")
    parser.add_argument("--config", default=None, help="环境配置覆盖文件路径")


def build_data_context(
    args: argparse.Namespace, command: str, *, create_database: bool = True
) -> tuple[ConfigManager, DataManager]:
    env: str | None = getattr(args, "env", None)
    config_file: str | None = getattr(args, "config", None)
    if env is None and config_file is None:
        raise ValueError("必须显式指定 --env 或 --config")

    cm = ConfigManager(config_file=config_file, env=env)
    resolved_env = cm.get_data_config().environment
    allowed_envs = COMMAND_ALLOWED_ENVS[command]
    if resolved_env not in allowed_envs:
        allowed = ", ".join(sorted(allowed_envs))
        raise ValueError(f"{command} 命令不允许使用 data environment={resolved_env!r}，允许值: {allowed}")

    db_path = cm.get_data_config().database_path
    logger.info(f"Data environment: {resolved_env} db={db_path}")
    return cm, DataManager(cm, create_database=create_database)
