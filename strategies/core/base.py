"""策略基类接口

定义所有策略实现类必须具备的核心方法和属性。
任何策略只需实现此接口，即可被回测引擎、网关适配器和 CLI 统一调用。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """持仓状态"""
    NO_POSITION = "no_position"
    LONG_POSITION = "long_position"


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: str = ""
    direction: str = ""
    price: float = 0.0
    volume: int = 0
    reason: str = ""
    profit: float = 0.0


class Strategy(ABC):
    """量化策略抽象基类

    所有策略必须继承此类并实现全部抽象方法。
    网关和回测引擎通过此接口实现与具体策略的解耦。

    Attributes:
        name: 策略名称标识 (子类覆盖)
    """

    name: str = "base"

    @abstractmethod
    def on_bar_signal(self, closes: List[float], current_price: float) -> Tuple[Optional[str], str]:
        """处理一根K线，返回交易信号

        Args:
            closes: 历史收盘价序列 (含当前)
            current_price: 当前收盘价

        Returns:
            (signal, reason): signal 为 'buy'/'sell'/None，reason 为信号来源
        """

    @abstractmethod
    def on_enter(self, price: float, volume: int):
        """持仓入场"""

    @abstractmethod
    def on_exit(self, exit_price: float) -> float:
        """持仓出场，返回盈亏金额"""

    @abstractmethod
    def calc_position_size(self, price: float, capital: float,
                           contract_size: int = 10) -> int:
        """计算开仓手数"""

    @abstractmethod
    def get_performance(self, trade_records: List[Any]) -> Dict[str, Any]:
        """计算策略绩效统计

        Args:
            trade_records: 交易记录列表

        Returns:
            包含 total_trades / winning_trades / win_rate / total_profit 等字段的字典
        """

    @property
    @abstractmethod
    def config(self) -> Any:
        """策略配置"""

    @property
    @abstractmethod
    def state(self) -> Any:
        """策略运行时状态"""