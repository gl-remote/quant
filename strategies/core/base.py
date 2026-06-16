"""策略基类接口模块

定义所有策略实现类必须具备的核心接口。
Strategy 是交易决策的中枢，纯决策逻辑，不持有任何状态。

重构背景:
- 旧架构：Strategy 自己持有 config、position、fills 等所有状态
- 新架构：State 统一持有所有运行时数据，Strategy 成为纯决策逻辑
- 优势：职责清晰、易于测试、状态管理集中

职责边界 (核心设计原则):
  Strategy:   信号生成 (纯业务逻辑，不持有状态)
  State:      配置、持仓、交易记录 (运行时数据)
  BarContext: 行情数据、多周期数据、指标、事件 (动态行情数据)
  Bridge:     框架适配 + 数据转换 + 下单执行 + 状态同步 (基础设施)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from .state import State
from .types import Fill, Signal

if TYPE_CHECKING:
    from ..runtime.requirements import BarContext, DataRequirements

# 泛型类型变量，表示策略配置的具体类型
T = TypeVar("T")


class Strategy(ABC, Generic[T]):
    """量化策略抽象基类

    【设计理念】
    Strategy 是纯决策逻辑层，不持有任何运行时状态：
    - 所有运行时数据在 State 中，由 Bridge 持有和同步
    - 所有行情数据在 BarContext 中，由 Bridge 在 on_bar 时构造
    - Strategy 只关注"什么时候买/卖"，不关注"怎么买/卖"

    【与旧架构的区别】
    旧架构（已废弃）:
      - Strategy.__init__(strategy_params, capital, contract_size)
      - Strategy 持有 self._config、self._position、self._fills
      - Strategy.on_bar(bar, ctx)

    新架构（当前）:
      - Strategy.__init__() 不接收任何参数（由 Bridge 构造）
      - Strategy 不持有任何状态
      - Strategy.on_bar(state, ctx) 接收完整的运行时数据

    【Bridge 调用流程】
      1. Bridge.on_init():
         - 调用 strategy.data_requirements(config) 获取数据需求
         - 初始化 DataFeed，预加载非主周期数据，预计算指标
      2. Bridge.on_bar(vnpy_bar):
         - 将 vnpy BarData 转为标准 Bar
         - 调用 data_feed.update_bar() 更新数据
         - 调用 build_context() 构造 BarContext
         - 调用 strategy.on_bar(state, ctx) 获取信号
         - 执行下单（buy/sell）
      3. Bridge.on_trade(trade):
         - 用 vnpy 成交数据更新 state.position
         - 构造 Fill 并追加到 state.fills
         - 调用 strategy.on_fill(fill) 通知策略

    【数据需求声明机制】
    策略必须实现 data_requirements(config) 方法来声明所需的数据和指标：
      - 声明需要哪些周期（主周期 + 非主周期）
      - 声明每个周期需要多少历史 K 线
      - 声明需要计算哪些指标
    框架在初始化时统一预计算，避免在 on_bar 中重复计算。
    """

    name: str = "base"
    """策略名称，用于日志和标识"""

    VERSION: str = "v0.0.0"
    """策略版本号，用于追踪策略变更"""

    # ---- 数据需求声明 ----

    def data_requirements(self, config: T) -> DataRequirements | None:
        """策略的数据需求声明，由 Bridge 在 on_init 时调用

        【设计目的】
        让策略声明自己需要什么数据和指标，框架在初始化时统一准备好。
        避免在 on_bar 中重复计算指标，提高性能。

        【调用时机】
        Bridge.on_init() 中调用一次，结果缓存起来供后续使用。

        【返回值含义】
        - 返回 DataRequirements 实例：策略需要使用数据管理架构
        - 返回 None：策略不需要额外的数据管理（自己处理数据）

        【自动注册】
        使用切面装饰器的策略无需覆写此方法——装饰器会自动包装并 merge
        指标需求。基类默认返回空 DataRequirements，装饰器在此基础上追加。

        :param config: 策略配置对象，用于确定需要什么指标和参数
        :return: 数据需求声明，或 None 表示不需要
        """
        from ..runtime import DataRequirements, EventsRequirements

        return DataRequirements(periods={}, indicators={}, events=EventsRequirements.no_events())

    # ---- 核心交易接口 ----

    @abstractmethod
    def on_bar(self, state: State[T], ctx: BarContext) -> Signal:
        """处理一根K线，返回完整交易决策

        【设计理念】
        这是策略的核心决策方法，接收完整的运行时数据，返回交易决策。
        所有数据都通过参数传入，Strategy 不持有任何状态。

        【参数说明】
        state:
          - symbol / period: 标的和周期信息
          - strategy_config: 策略配置（不修改）
          - capital / contract_size: 环境配置（用于计算仓位）
          - position: 当前持仓（只读）
          - fills: 历史成交记录（只读）

        ctx:
          - bar: 当前 K 线
          - multi: 多周期数据视图
          - events: 事件列表

        【返回值】
        Signal 对象，包含：
          - action: 'buy'/'sell'/''
          - volume: 预计算的手数（基于 capital 和 contract_size）
          - reason: 信号原因（用于日志和分析）

        :param state: 运行时状态，包含配置、持仓、交易记录
        :param ctx: 行情上下文，包含当前 bar、多周期数据、指标
        :return: 交易决策信号
        """

    @abstractmethod
    def on_fill(self, fill: Fill) -> None:
        """订单成交回调

        【设计目的】
        通知策略订单已成交，策略可以根据成交信息调整后续逻辑。

        【重要原则】
        - State 是唯一真实的数据来源
        - on_fill 只是通知，不应该改变任何数据
        - Strategy 不应该自己更新持仓，应该从 state.position 读取

        【调用时机】
        Bridge 在 vnpy 的 on_trade 回调中，更新完 state 后调用。

        :param fill: 成交回执，含方向、价格、数量、时间等信息
        """

    # ---- 信号后处理 ----

    def _finalize_signal(self, signal: Signal, ctx: BarContext) -> Signal:
        """框架层信号后处理 — Bridge 在 on_bar 返回后统一调用

        处理所有策略共有的信号格式化逻辑，策略 on_bar 无需关心：
          1. 将方向建议展平写入 diagnostics
          2. 将 ctx.aspects.diagnostics 拷贝到 signal.diagnostics
          3. 有信号时将 reason 格式化为 JSON（含 diagnostics）

        :param signal: 策略 on_bar 返回的原始信号
        :param ctx: 行情上下文（含 aspects）
        :return: 处理后的信号
        """
        import json

        # 展平方向建议到 diagnostics
        ctx.aspects.flush_direction_diagnostics()

        # 拷贝 diagnostics
        signal.diagnostics = ctx.aspects.diagnostics

        # 有信号时 reason 改为 JSON 格式
        if signal.action:
            signal.reason = json.dumps(
                {
                    "r": signal.reason,
                    **signal.diagnostics,
                }
            )

        return signal

    # ---- 生命周期 ----

    def reset(self) -> None:
        """重置策略状态 (用于新一轮回测)

        【重构说明】
        旧架构中 Strategy 持有状态，需要 reset() 清空。
        新架构中 Strategy 不再持有任何状态，此方法退化为空实现。

        【状态重置的新方式】
        - State 由 Bridge 在每次回测时创建全新实例
        - Bridge 也由 vnpy 在每次 add_strategy() 时创建全新实例
        - 无需手动 reset，自然初始化为空状态

        【保留原因】
        保留此方法是为了向后兼容，旧代码可能还在调用它。
        """
        pass


class UninitializedStrategy(Strategy[Any]):
    """注入前的占位策略 — 被调用时抛出 RuntimeError

    【设计目的】
    Bridge.__init__ 时赋值为默认值，替换 None sentinel。
    避免每次使用 _core 时都需要 None 判断，提高代码可读性。

    【使用流程】
    1. Bridge.__init__(): self._core = UninitializedStrategy()
    2. 外部注入真实策略: bridge._core = real_strategy
    3. 如果在注入前调用方法，抛出清晰的错误信息

    【为什么不用 None】
    - 用 None 需要每次使用前判断: if self._core is not None: ...
    - 用占位策略可以提供更清晰的错误信息
    - 类型检查更友好（Strategy 类型而非 Optional[Strategy]）
    """

    name = "_uninitialized"
    VERSION = ""

    def on_bar(self, state: State[Any], ctx: BarContext) -> Signal:
        raise RuntimeError("Strategy core not yet injected into bridge")

    def on_fill(self, fill: Fill) -> None:
        raise RuntimeError("Strategy core not yet injected into bridge")

    def reset(self) -> None:
        pass
