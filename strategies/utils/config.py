# -*- coding: utf-8 -*-
"""
策略配置管理模块

提供策略配置应用与参数序列化功能。
"""

import dataclasses
import logging
from typing import Any

from strategies import Strategy

logger = logging.getLogger(__name__)


def apply_strategy_config(strategy: Strategy[Any], config_manager: Any) -> None:
    """将配置文件中的策略参数应用到策略实例的 config 上

    通过 dataclasses.fields() 校验 TOML 配置键是否对应合法数据类字段，
    避免 hasattr 静默跳过未知键导致的配置未生效问题。

    Args:
        strategy: 策略实例
        config_manager: ConfigManager 实例
    """
    sc = config_manager.get_strategy_config(strategy.name)  # → StrategyItemConfig
    cfg = strategy.config
    try:
        valid_keys = {f.name for f in dataclasses.fields(cfg)}
    except TypeError:
        # 非 dataclass，回退到 hasattr 检查
        for key, value in sc.model_dump(exclude={"name", "enabled"}).items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return

    for key, value in sc.model_dump(exclude={"name", "enabled"}).items():
        if key in valid_keys:
            setattr(cfg, key, value)
        else:
            logger.warning(
                f"忽略未识别的策略配置键: '{key}'，"
                f"合法键: {sorted(valid_keys)}"
            )


def serialize_strategy_params(strategy: Strategy[Any]) -> dict[str, float]:
    """将策略配置序列化为参数字典，用于写入 backtest_params 表

    Args:
        strategy: 策略实例

    Returns:
        参数字典 {'sma_short': 20, 'sma_long': 70}
    """
    try:
        cfg = strategy.config
        valid_keys = {f.name for f in dataclasses.fields(cfg)}
        return {k: float(getattr(cfg, k)) for k in valid_keys}
    except Exception:
        return {}
