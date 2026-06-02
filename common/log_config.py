"""loguru 全局日志配置

使用方式:
    from common.log_config import setup_logging
    setup_logging()  # cli/main.py 入口调用一次

    # 业务代码直接:
    from loguru import logger
    logger.info("message")
"""

from __future__ import annotations

import sys

from loguru import logger

from common.constants import DEFAULT_LOG_FORMAT


def setup_logging(level: str = "INFO", log_format: str | None = None) -> None:
    """初始化 loguru 全局配置

    移除默认 handler，添加 stderr handler。
    应在程序入口（cli/main.py）调用一次。

    :param level: 日志级别，如 "INFO", "DEBUG", "WARNING"
    :param log_format: loguru 格式字符串，默认使用 DEFAULT_LOG_FORMAT
    """
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=log_format or DEFAULT_LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
