"""策略基类接口

定义所有策略实现类必须具备的核心接口。
Strategy 是交易决策的中枢，拥有完整的状态和绩效数据。

职责边界:
  Strategy:  信号生成 + 仓位管理 + 绩效追踪 (业务逻辑)
  Bridge:    框架适配 + 数据转换 + 下单执行  (基础设施)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import Bar, Signal, Fill, StrategyPosition, Performance


class Strategy(ABC):
    """量化策略抽象基类

    Bridge 调用流程:
      bar = Bar(...)                     # Bridge 将框架数据转为标准 Bar
      signal = strategy.on_bar(bar)      # Strategy 产生完整决策
      bridge.execute(signal)             # Bridge 翻译为框架指令并执行
      strategy.on_fill(fill)             # 成交回执 → Strategy 更新状态

    调用方（回测引擎/CLI）通过 strategy.performance / strategy.position
    直接获取策略状态，不经过 Bridge 代理。
    """

    name: str = "base"

    # ---- 核心交易接口 ----

    @abstractmethod
    def on_bar(self, bar: Bar) -> Signal:
        """处理一根K线，返回完整交易决策

        Bridge 调用此方法获取信号，包括预计算的手数。
        Strategy 内部维护所需的技术指标缓存。

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
    def performance(self) -> Performance:
        """累计绩效"""

    @property
    @abstractmethod
    def config(self) -> Any:
        """策略配置"""

    @config.setter
    def config(self, value: Any) -> None:
        ...

    # ---- 生命周期 ----

    @abstractmethod
    def reset(self) -> None:
        """重置策略状态 (用于新一轮回测)"""
