"""策略基类接口

定义所有策略实现类必须具备的核心接口。
Strategy 是交易决策的中枢，纯决策逻辑，不持有状态。

职责边界:
  Strategy:  信号生成 (纯业务逻辑)
  State:     配置、持仓、交易记录 (运行时数据)
  BarContext: 行情数据、多周期数据、指标、事件 (动态行情数据)
  Bridge:    框架适配 + 数据转换 + 下单执行 + 状态同步 (基础设施)
"""

from abc import ABC, abstractmethod
from typing import Optional, TypeVar, Generic, Any

from .types import Signal, Fill
from .state import State
from ..runtime.requirements import DataRequirements, BarContext

T = TypeVar('T')


class Strategy(ABC, Generic[T]):
    """量化策略抽象基类

    Bridge 调用流程:
      bar = Bridge 将框架数据转为标准 Bar
      signal = strategy.on_bar(state, ctx)   # Strategy 产生完整决策
      bridge.execute(signal)                  # Bridge 翻译为框架指令并执行
      strategy.on_fill(fill)                  # 成交回执 → Strategy 通知

    Strategy 是纯决策逻辑：
    - 所有运行时数据在 State 中，由 Bridge 持有和同步
    - 所有行情数据在 BarContext 中，由 Bridge 在 on_bar 时构造
    - Strategy 不持有 config、position、fills 等状态

    【数据需求声明】
    策略必须实现 data_requirements(config) 方法来声明所需的数据和指标，
    框架在初始化时统一预计算并在 on_bar 时通过 BarContext 注入。
    """

    name: str = "base"
    VERSION: str = "v0.0.0"

    # ---- 数据需求声明 ----

    def data_requirements(self, config: T) -> Optional[DataRequirements]:
        """策略的数据需求声明，由 Bridge 在 on_init 时调用

        框架据此注册周期、注册指标，并在 on_bar 时构造 ctx。
        返回 None 表示策略不需要额外的数据管理。

        :param config: 策略配置
        """
        return None

    # ---- 核心交易接口 ----

    @abstractmethod
    def on_bar(self, state: State[T], ctx: BarContext) -> Signal:
        """处理一根K线，返回完整交易决策

        state 包含策略配置、持仓、交易记录等所有运行时数据。
        ctx 包含当前 bar、多周期数据、指标、事件等动态行情数据。

        Bridge 调用此方法获取信号，包括预计算的手数。

        Returns:
            Signal: action='buy'/'sell'/'', 含预计算 volume 和 reason
        """

    @abstractmethod
    def on_fill(self, fill: Fill) -> None:
        """订单成交回调

        Bridge 在下单成交后调用，通知 Strategy。
        注意：State 是唯一真实的数据来源，on_fill 只是通知，不改变数据。

        Args:
            fill: 成交回执，含方向、价格、数量、盈亏
        """

    # ---- 生命周期 ----

    def reset(self) -> None:
        """重置策略状态 (用于新一轮回测)

        Strategy 不再持有任何状态，此方法退化为空实现。
        State 由 Bridge 在每次回测时创建全新实例。
        """
        pass


class UninitializedStrategy(Strategy[Any]):
    """注入前的占位策略 — 被调用时抛出 RuntimeError

    Bridge __init__ 时赋值为默认值，替换 None sentinel
    避免每次使用时需要 None 判断。
    注入后（bridge._core = real_strategy）自动替换。
    """
    name = "_uninitialized"
    VERSION = ""

    def on_bar(self, state: State, ctx: BarContext) -> Signal:
        raise RuntimeError("Strategy core not yet injected into bridge")

    def on_fill(self, fill: Fill) -> None:
        raise RuntimeError("Strategy core not yet injected into bridge")

    def reset(self) -> None:
        pass
