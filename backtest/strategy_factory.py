"""
策略工厂与桥接器集成模块

职责:
  - 策略加载与配置解析
  - 策略与 VnpyStrategyBridge 的集成
  - 策略配置类型提取
  - 状态对象创建
"""

from __future__ import annotations

import typing
from typing import TYPE_CHECKING, Any

from strategies import Strategy, State
from strategies.utils import load_strategy

if TYPE_CHECKING:
    from strategies.bridges import VnpyStrategyBridge


class StrategyFactory:
    """
    策略工厂 - 负责策略加载与集成

    懒加载: 策略只在需要时被加载
    """

    @staticmethod
    def extract_config_type(strategy_cls: type[Strategy[Any]]) -> type:
        """从策略类提取配置类型

        Args:
            strategy_cls: Strategy 子类

        Returns:
            策略配置 dataclass 类型

        Raises:
            TypeError: 无法提取配置类型时抛出
        """
        config_cls: type | None = None
        for base in getattr(strategy_cls, '__orig_bases__', []):
            origin = typing.get_origin(base)
            if origin is not None and issubclass(origin, Strategy):
                args = typing.get_args(base)
                if args:
                    config_cls = args[0]
                    break
        if config_cls is None:
            raise TypeError(
                f"无法从 {strategy_cls.__name__} 提取策略配置类型，"
                f"请确保策略类继承自 Strategy[ConfigType]"
            )
        return config_cls

    @staticmethod
    def make_state(
        strategy_config: object,
        symbol: str,
        period: str,
        capital: float,
        contract_size: int,
    ) -> State[Any]:
        return State(
            symbol=symbol,
            period=period,
            strategy_config=strategy_config,
            capital=capital,
            contract_size=contract_size,
        )

    @staticmethod
    def create_injected_strategy_class(
        strategy_name: str,
        strategy_params: dict[str, Any],
        symbol: str,
        period: str,
        capital: float,
        contract_size: int,
    ) -> type[VnpyStrategyBridge]:
        """创建注入了策略实例和状态的 VnpyStrategyBridge 子类

        Args:
            strategy_name: 策略名称
            strategy_params: 策略参数字典
            symbol: 品种代码
            period: K线周期
            capital: 初始资金
            contract_size: 合约乘数

        Returns:
            继承自 VnpyStrategyBridge 的类
        """
        from strategies.bridges import VnpyStrategyBridge

        strategy_instance = load_strategy(strategy_name)
        strategy_cls: type[Strategy[Any]] = type(strategy_instance)
        config_cls = StrategyFactory.extract_config_type(strategy_cls)
        strategy_config = config_cls(**strategy_params)

        class _InjectedStrategy(VnpyStrategyBridge):

            def _load_default_core(self, _setting: object | None = None) -> None:
                pass

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self._core = strategy_cls()
                self._state = StrategyFactory.make_state(
                    strategy_config=strategy_config,
                    symbol=symbol,
                    period=period,
                    capital=capital,
                    contract_size=contract_size,
                )

        return _InjectedStrategy


def create_strategy_class(
    strategy_name: str,
    strategy_params: dict[str, Any],
    symbol: str,
    period: str,
    capital: float,
    contract_size: int,
) -> type[VnpyStrategyBridge]:
    """便捷函数：直接创建注入的策略桥接类"""
    return StrategyFactory.create_injected_strategy_class(
        strategy_name=strategy_name,
        strategy_params=strategy_params,
        symbol=symbol,
        period=period,
        capital=capital,
        contract_size=contract_size,
    )


def load_strategy_and_config(
    strategy_name: str,
    strategy_params: dict[str, Any],
) -> tuple[type[Strategy[Any]], object]:
    """加载策略类并构造配置对象"""
    strategy_instance = load_strategy(strategy_name)
    strategy_cls: type[Strategy[Any]] = type(strategy_instance)
    config_cls = StrategyFactory.extract_config_type(strategy_cls)
    strategy_config = config_cls(**strategy_params)
    return (strategy_cls, strategy_config)