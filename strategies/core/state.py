from dataclasses import dataclass, field
from typing import Dict, Any, List, TypeVar, Generic

from .types import StrategyPosition, Fill

T = TypeVar('T')


@dataclass
class State(Generic[T]):
    """运行时配置和状态，用于 Bridge 初始化和策略运行

    职责划分:
    - State: 保存策略配置、环境配置、持仓、交易记录（所有运行时数据）
    - Strategy: 纯决策逻辑，不持有任何状态，通过 State 获取所有数据
    - BarContext: 保存行情数据、多周期数据、指标、事件（动态行情数据）
    - Bridge: 负责从 vnpy 获取交易状态，更新 State
    """
    symbol: str
    period: str
    strategy_config: T
    capital: float = 0.0
    contract_size: int = 1
    position: StrategyPosition = field(default_factory=StrategyPosition)
    fills: List[Fill] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
