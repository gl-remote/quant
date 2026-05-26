# -*- coding: utf-8 -*-
"""数据源抽象层 — 统一数据源接口 + 工厂/注册模式

支持通过 provider 名称动态切换数据源，便于扩展新数据源。

架构:
    BaseDataSource  (抽象基类)
    ├── TqSdkDataSource   — 天勤量化 (原始)
    └── AkShareDataSource — AkShare 免费数据

用法:
    from data.datasource import get_data_source

    source = get_data_source("akshare")        # 按名称获取
    df = source.fetch_kline("DCE.m2509", ...)

    source = get_data_source()                 # 从配置读取 provider
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import BaseDataSource
from .tqsdk_source import TqSdkDataSource
from .akshare_source import AkShareDataSource

if TYPE_CHECKING:
    from config.app_config import ConfigManager

logger = logging.getLogger(__name__)

# 数据源注册表: provider_name → DataSource class
_REGISTRY: dict[str, type[BaseDataSource]] = {
    "tqsdk": TqSdkDataSource,
    "akshare": AkShareDataSource,
}


def register_source(name: str, cls: type[BaseDataSource]) -> None:
    """注册自定义数据源（供扩展使用）"""
    _REGISTRY[name] = cls
    logger.info(f"已注册数据源: {name} → {cls.__name__}")


def list_sources() -> list[str]:
    """列出所有已注册的数据源名称"""
    return list(_REGISTRY.keys())


def get_data_source(
    provider: str | None = None,
    config_manager: ConfigManager | None = None,
) -> BaseDataSource:
    """获取数据源实例

    Args:
        provider: 数据源名称，如 "tqsdk" / "akshare"
                  None 时从 config_manager 读取 DataConfig.provider
        config_manager: 配置管理器，provider 为 None 时必需

    Returns:
        对应数据源实例

    Raises:
        ValueError: 未知的 provider
    """
    if provider is None:
        if config_manager is None:
            raise ValueError("provider 为 None 时必须提供 config_manager")
        provider = config_manager.get_data_config().provider

    cls = _REGISTRY.get(provider)
    if cls is None:
        available = ", ".join(_REGISTRY.keys())
        raise ValueError(
            f"未知数据源: {provider!r}，可用数据源: {available}"
        )

    return cls()


__all__ = [
    "BaseDataSource",
    "TqSdkDataSource",
    "AkShareDataSource",
    "get_data_source",
    "register_source",
    "list_sources",
]
