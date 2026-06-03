"""
策略工厂与桥接器集成模块

重构背景:
- 旧架构: VnpyBacktestEngine 内部直接构造策略，职责不清
- 新架构: 策略构造与 State 构造统一封装在 StrategyFactory 中
- 优势: 代码分离、可测试性提升、单一职责

职责:
  - 策略加载与配置解析
  - 策略与 VnpyBacktestBridge 的集成
  - 策略配置类型提取（泛型反射）
  - State 对象创建（封装构造逻辑）

设计理念:
  - Strategy 不持有任何状态，所有状态在 State 中
  - Bridge 作为容器，持有 Strategy 和 State
  - 工厂类封装复杂的注入逻辑，使 Engine 代码简化
"""

from __future__ import annotations

import typing
from dataclasses import fields as dc_fields, is_dataclass
from typing import TYPE_CHECKING, Any

from strategies import Strategy, State
from strategies.utils import load_strategy

if TYPE_CHECKING:
    from strategies.bridges import VnpyBacktestBridge


class StrategyFactory:
    """
    策略工厂 - 负责策略加载与集成

    【设计目的】
    封装策略加载、配置解析、State 构造、Bridge 注入的完整流程，
    使 VnpyBacktestEngine 的代码简化，职责更清晰。

    【为什么需要工厂类】
    1. 策略构造涉及泛型反射（提取配置类型），逻辑较复杂
    2. State 构造需要多个参数（symbol, period, capital, contract_size）
    3. Bridge 注入需要动态创建类，这部分逻辑应该封装
    4. 便于测试（可以 mock 工厂）
    """

    @staticmethod
    def extract_config_type(strategy_cls: type[Strategy[Any]]) -> type:
        """从策略类提取配置类型（泛型反射）

        【为什么需要这个】
        我们的 Strategy 基类是泛型的 Strategy[ConfigType]，
        需要通过反射提取出 ConfigType 的具体类型，
        然后才能从 strategy_params 字典构造出配置对象。

        【技术实现】
        使用 Python 的 typing 模块和 __orig_bases__ 属性，
        从泛型基类中提取出类型参数。

        Args:
            strategy_cls: Strategy 子类，如 MaStrategyCore

        Returns:
            策略配置 dataclass 类型，如 MACrossParams

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
        """创建 State 对象（封装构造逻辑）

        【设计目的】
        集中管理 State 的构造，避免 Engine 中重复写构造代码。
        所有 State 的构造逻辑都在这里，便于统一修改。

        Args:
            strategy_config: 策略配置对象
            symbol: 品种代码
            period: K线周期
            capital: 初始资金
            contract_size: 合约乘数

        Returns:
            初始化好的 State 对象
        """
        return State(
            symbol=symbol,
            period=period,
            strategy_config=strategy_config,
            capital=capital,
            contract_size=contract_size,
        )

    @staticmethod
    def _filter_params_to_config(strategy_params: dict[str, Any], config_cls: type) -> dict[str, Any]:
        """过滤 strategy_params，只保留 config_cls 接受的字段

        【为什么需要这个方法】
        strategy_params 来自 StrategyItemConfig.model_dump()，包含策略参数
        (如 sma_short/sma_long) 和配置元数据 (如 kline_period/search_space)。
        直接 ** 拆包传给 config_cls() 会导致 TypeError。

        本方法根据 config_cls 的实际 dataclass 字段进行过滤，确保只传入合法字段。
        对于非 dataclass 的 config_cls，直接透传（不做过滤）。

        Args:
            strategy_params: 原始参数字典（可能包含多余字段）
            config_cls: 目标配置类型（如 MACrossParams）

        Returns:
            过滤后的参数字典（仅包含 config_cls 接受的字段）
        """
        if not is_dataclass(config_cls):
            return dict(strategy_params)
        valid_keys = {f.name for f in dc_fields(config_cls)}
        return {k: v for k, v in strategy_params.items() if k in valid_keys}

    @staticmethod
    def create_injected_strategy_class(
        strategy_name: str,
        strategy_params: dict[str, Any],
        symbol: str,
        period: str,
        capital: float,
        contract_size: int,
    ) -> type[VnpyBacktestBridge]:
        """创建注入了策略实例和状态的 VnpyBacktestBridge 子类

        【为什么要动态创建类】
        因为 vnpy 的 BacktestingEngine 需要传入策略类（class），
        而不是策略实例（instance），引擎内部会自己调用构造函数。
        所以我们需要动态创建一个子类，在 __init__ 中注入 Strategy 和 State。

        【注入流程】
        1. 加载策略类（通过 strategy_name）
        2. 提取策略配置类型（泛型反射）
        3. 从 strategy_params 构造配置对象
        4. 动态创建 VnpyBacktestBridge 子类
        5. 在子类的 __init__ 中注入 Strategy 和 State

        Args:
            strategy_name: 策略名称，如 'ma'
            strategy_params: 策略参数字典
            symbol: 品种代码
            period: K线周期
            capital: 初始资金
            contract_size: 合约乘数

        Returns:
            继承自 VnpyBacktestBridge 的类，可直接传给 vnpy 引擎
        """
        from strategies.bridges import VnpyBacktestBridge

        # 步骤1: 加载策略类
        strategy_instance = load_strategy(strategy_name)
        strategy_cls: type[Strategy[Any]] = type(strategy_instance)

        # 步骤2: 提取配置类型并构造配置对象（过滤非策略参数）
        config_cls = StrategyFactory.extract_config_type(strategy_cls)
        filtered_params = StrategyFactory._filter_params_to_config(
            strategy_params, config_cls
        )
        strategy_config = config_cls(**filtered_params)

        # 步骤3: 动态创建注入子类
        class _InjectedStrategy(VnpyBacktestBridge):

            def _load_default_core(self, _setting: object | None = None) -> None:
                """禁用默认加载，因为我们会在 __init__ 中注入"""
                pass

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                """vnpy 引擎调用这个构造函数，我们在这里注入"""
                super().__init__(*args, **kwargs)

                # 注入 Strategy 实例（纯决策逻辑，不持有状态）
                self._core = strategy_cls()

                # 注入 State 实例（所有运行时数据）
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
) -> type[VnpyBacktestBridge]:
    """便捷函数：直接创建注入的策略桥接类

    这是 StrategyFactory.create_injected_strategy_class 的别名，
    便于在不需要完整工厂类的地方直接调用。
    """
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
    """加载策略类并构造配置对象

    【用途】
    在需要策略类和配置对象，但不需要完整 Bridge 的地方使用，
    比如优化器中需要提取参数空间。
    """
    strategy_instance = load_strategy(strategy_name)
    strategy_cls: type[Strategy[Any]] = type(strategy_instance)
    config_cls = StrategyFactory.extract_config_type(strategy_cls)
    filtered_params = StrategyFactory._filter_params_to_config(strategy_params, config_cls)  # pyright: ignore[reportPrivateUsage]
    strategy_config = config_cls(**filtered_params)
    return (strategy_cls, strategy_config)