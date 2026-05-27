"""策略核心模块

提供策略基类、数据类型定义以及策略加载功能。

子模块:
  - base: Strategy ABC 基类
  - types: Bar, Signal, Fill, StrategyPosition 标准化数据类型

功能函数:
  - load_strategy: 动态加载策略实例
  - get_strategy_class_name: 获取策略类名
  - apply_strategy_config: 应用策略配置
  - serialize_strategy_params: 序列化策略参数
"""

import dataclasses
import importlib
import json
from pathlib import Path

from .base import Strategy
from .types import Bar, Signal, Fill, StrategyPosition
from common.constants import (
    STRATEGY_MA,
)

__all__ = [
    'Strategy', 'Bar', 'Signal', 'Fill', 'StrategyPosition',
    'load_strategy', 'get_strategy_class_name',
    'apply_strategy_config', 'serialize_strategy_params',
]


# ============================================================
# 策略动态加载
# ============================================================
def load_strategy(strategy_name: str | None = None,
                  **strategy_kwargs) -> Strategy:
    """根据名称动态加载策略实例

    支持三种传入方式:
      - 简化名: "ma" → 找 strategies/ma_strategy.py
      - 完整名: "ma_strategy" → 找 strategies/ma_strategy.py
      - 带扩展名: "ma_strategy.py" → 找 strategies/ma_strategy.py

    Args:
        strategy_name: 策略名称，None 则默认使用 ma
        **strategy_kwargs: 透传给策略构造函数的参数 (strategy_params/capital/contract_size)

    Returns:
        Strategy 实例

    Raises:
        FileNotFoundError: 策略文件不存在
        ValueError: 策略文件中未找到 Strategy 实现类
    """
    if not strategy_name:
        strategy_name = STRATEGY_MA

    name = strategy_name
    if name.endswith('.py'):
        name = name[:-3]
    if not name.endswith('_strategy'):
        name = f"{name}_strategy"

    strategies_dir = Path(__file__).parent.parent
    strategy_file = strategies_dir / f"{name}.py"

    if not strategy_file.exists():
        available = [f.stem for f in strategies_dir.glob('*_strategy.py')]
        raise FileNotFoundError(
            f"策略文件 {name}.py 不存在，可用策略: {', '.join(available)}"
        )

    module = importlib.import_module(f"strategies.{name}")

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (isinstance(attr, type) and
                issubclass(attr, Strategy) and
                attr is not Strategy and
                attr_name != 'Strategy'):
            if strategy_kwargs:
                return attr(**strategy_kwargs)
            return attr()

    raise ValueError(f"策略文件 {name}.py 中未找到 Strategy 实现类")


def get_strategy_class_name(strategy: Strategy) -> str:
    """获取策略类名用于日志显示"""
    return type(strategy).__name__


def apply_strategy_config(strategy: Strategy, config_manager):
    """将配置文件中的策略参数应用到策略实例的 config 上

    通过 dataclasses.fields() 校验 TOML 配置键是否对应合法数据类字段，
    避免 hasattr 静默跳过未知键导致的配置未生效问题。

    Args:
        strategy: 策略实例
        config_manager: ConfigManager 实例
    """
    import logging
    logger = logging.getLogger(__name__)

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


def serialize_strategy_params(strategy: Strategy) -> dict[str, float]:
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

