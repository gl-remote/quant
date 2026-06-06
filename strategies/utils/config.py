"""
策略配置管理模块

提供策略配置应用与参数序列化功能。
"""

import dataclasses
from typing import Any

from loguru import logger


def apply_strategy_config(config: Any, config_manager: Any) -> None:
    """将配置文件中的策略参数应用到策略配置 dataclass 上

    通过 dataclasses.fields() 校验 TOML 配置键是否对应合法数据类字段，
    避免 hasattr 静默跳过未知键导致的配置未生效问题。

    Args:
        config: 策略配置 dataclass 实例
        config_manager: ConfigManager 实例
    """
    sc = config_manager.get_strategy_config(config.__class__.__name__)  # 通过类名查找
    try:
        valid_keys = {f.name for f in dataclasses.fields(config)}
    except TypeError:
        for key, value in sc.model_dump(exclude={"name", "enabled", "kline_period", "search_space"}).items():
            if hasattr(config, key):
                setattr(config, key, value)
        return

    for key, value in sc.model_dump(exclude={"name", "enabled", "kline_period", "search_space"}).items():
        if key in valid_keys:
            setattr(config, key, value)
        else:
            logger.warning(f"忽略未识别的策略配置键: '{key}'，合法键: {sorted(valid_keys)}")


def serialize_strategy_params(strategy_config: Any) -> dict[str, float]:
    """将策略配置序列化为参数字典，用于写入 backtest_params 表

    Args:
        strategy_config: 策略配置 dataclass 实例

    Returns:
        参数字典 {'sma_short': 20, 'sma_long': 70}
    """
    try:
        valid_keys = {f.name for f in dataclasses.fields(strategy_config)}
        return {k: float(getattr(strategy_config, k)) for k in valid_keys}
    except Exception:
        return {}
