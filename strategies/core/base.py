"""策略基类接口

定义所有策略实现类必须具备的核心接口。
Strategy 是交易决策的中枢，拥有完整的状态和绩效数据。

职责边界:
  Strategy:  信号生成 + 仓位管理 + 绩效追踪 (业务逻辑)
  Bridge:    框架适配 + 数据转换 + 下单执行  (基础设施)
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

from .types import Bar, Signal, Fill, StrategyPosition
from .requirements import DataRequirements, BarContext

T = TypeVar('T')


class Strategy(ABC, Generic[T]):
    """量化策略抽象基类

    Bridge 调用流程:
      bar = Bar(...)                     # Bridge 将框架数据转为标准 Bar
      signal = strategy.on_bar(bar)      # Strategy 产生完整决策
      bridge.execute(signal)             # Bridge 翻译为框架指令并执行
      strategy.on_fill(fill)             # 成交回执 → Strategy 更新状态

    调用方（回测引擎/CLI）通过 strategy.position 直接获取策略状态，
    成交记录 (fills) 由 Bridge 管理，不经过策略接口。
    绩效数据统一由回测引擎（vnpy BacktestingEngine.calculate_statistics）
    计算和对外输出，Strategy 不再自行统计盈亏。

    【config 泛型化】
    Strategy(ABC, Generic[T]) 中的 T 由子类指定具体参数类型
    （如 Strategy[MACrossParams]），使调用方访问 strategy.config
    时静态类型检查能自动推断出具体字段，无需手动 cast。

    【数据需求声明】
    策略可以选择实现 data_requirements() 方法来声明所需的数据和指标，
    这样框架可以在回测前统一预计算并在 on_bar 时通过 BarContext 注入。

    【向后兼容】
    对于未实现 data_requirements() 的老策略，ctx 参数为 None，
    保持原有的 on_bar 签名兼容。
    """

    name: str = "base"
    VERSION: str = "v0.0.0"

    # ---- 数据需求声明 ----

    def data_requirements(self) -> Optional[DataRequirements]:
        """策略的数据需求声明，由 Bridge/Engine 在初始化时读取

        框架据此注册周期、注册指标，并在 on_bar 时构造 ctx。
        返回 None 表示策略不使用新的数据管理系统（向后兼容）。
        """
        return None

    # ---- 核心交易接口 ----

    @abstractmethod
    def on_bar(self, bar: Bar, ctx: Optional[BarContext] = None) -> Signal:
        """处理一根K线，接收已准备完毕的上下文，返回完整交易决策

        ctx 包含所有声明的跨周期数据和事件。
        ctx 参数可选：
          - 如果策略实现了 data_requirements()，ctx 会被注入
          - 如果策略没有实现 data_requirements()，ctx 为 None（向后兼容）

        Bridge 调用此方法获取信号，包括预计算的手数。
        Strategy 内部维护所需的技术指标缓存（或使用 ctx 中的预计算数据）。

        Returns:
            Signal: action='buy'/'sell'/'', 含预计算 volume 和 reason
        """

    @abstractmethod
    def on_fill(self, fill: Fill) -> None:
        """订单成交回调

        Bridge 在下单成交后调用，通知 Strategy 更新持仓状态和交易记录。

        Args:
            fill: 成交回执，含方向、价格、数量、盈亏
        """

    # ---- 状态查询 (调用方直接访问，不经 Bridge) ----

    @property
    @abstractmethod
    def position(self) -> StrategyPosition:
        """当前持仓"""

    @property
    @abstractmethod
    def config(self) -> T:
        """策略配置"""

    @config.setter
    def config(self, value: T) -> None:
        ...

    # ---- 生命周期 ----

    @abstractmethod
    def reset(self) -> None:
        """重置策略状态 (用于新一轮回测)"""


class UninitializedStrategy(Strategy[Any]):
    """注入前的占位策略 — 被调用时抛出 RuntimeError

    Bridge __init__ 时赋值为默认值，替换 None₀ sentinel₁
    避免每次使用时需要 None 判断。
    注入后（bridge._core = real_strategy）自动替换。
    """
    name = "_uninitialized"
    VERSION = ""

    def on_bar(self, bar: Bar, ctx: Optional[BarContext] = None) -> Signal:
        raise RuntimeError("Strategy core not yet injected into bridge")

    def on_fill(self, fill: Fill) -> None:
        raise RuntimeError("Strategy core not yet injected into bridge")

    @property
    def position(self) -> StrategyPosition:
        raise RuntimeError("Strategy core not yet injected into bridge")

    @property
    def config(self) -> Any:
        raise RuntimeError("Strategy core not yet injected into bridge")

    @config.setter
    def config(self, value: Any) -> None:
        raise RuntimeError("Strategy core not yet injected into bridge")

    def reset(self) -> None:
        raise RuntimeError("Strategy core not yet injected into bridge")
