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

# setup_logging() 调用后保存 stderr handler id，供需要精确移除的场景使用
_stderr_sink_id: int | None = None


def get_stderr_sink_id() -> int | None:
    """返回 setup_logging 创建的 stderr handler id，未初始化则返回 None"""
    return _stderr_sink_id


def setup_logging(level: str = "INFO", log_format: str | None = None) -> None:
    """初始化 loguru 全局配置

    移除默认 handler，添加 stderr handler。
    应在程序入口（cli/main.py）调用一次。

    :param level: 日志级别，如 "INFO", "DEBUG", "WARNING"
    :param log_format: loguru 格式字符串，默认使用 DEFAULT_LOG_FORMAT
    """
    global _stderr_sink_id
    logger.remove()
    # 设置默认 extra，{extra[bt_id]} 在非回测场景为空字符串
    logger.configure(extra={"bt_id": ""})
    _stderr_sink_id = logger.add(
        sys.stderr,
        level=level,
        format=log_format or DEFAULT_LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
