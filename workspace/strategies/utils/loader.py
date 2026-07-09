"""
策略动态加载模块

提供根据策略名称动态加载策略实例的功能。
"""

import importlib
from pathlib import Path

from common.constants import STRATEGY_MA

from ..core import Strategy


def load_strategy(strategy_name: str | None = None, **strategy_kwargs: object) -> Strategy[object]:
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
    if name.endswith(".py"):
        name = name[:-3]
    if not name.endswith("_strategy"):
        name = f"{name}_strategy"

    strategies_dir = Path(__file__).parent.parent
    strategy_file = strategies_dir / f"{name}.py"

    if not strategy_file.exists():
        available = [f.stem for f in strategies_dir.glob("*_strategy.py")]
        raise FileNotFoundError(f"策略文件 {name}.py 不存在，可用策略: {', '.join(available)}")

    module = importlib.import_module(f"strategies.{name}")
    requested_simple_name = name.removesuffix("_strategy")

    strategy_classes: list[type[Strategy[object]]] = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, Strategy) and attr is not Strategy and attr_name != "Strategy":
            strategy_classes.append(attr)

    for strategy_cls in strategy_classes:
        if getattr(strategy_cls, "name", None) == requested_simple_name:
            if strategy_kwargs:
                return strategy_cls(**strategy_kwargs)
            return strategy_cls()

    if strategy_classes:
        strategy_cls = strategy_classes[0]
        if strategy_kwargs:
            return strategy_cls(**strategy_kwargs)
        return strategy_cls()

    raise ValueError(f"策略文件 {name}.py 中未找到 Strategy 实现类")


def get_strategy_class_name(strategy: Strategy[object]) -> str:
    """获取策略类名用于日志显示"""
    return type(strategy).__name__
