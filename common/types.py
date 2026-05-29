"""
通用类型别名 — 全项目共享的类型定义

本文件遵循 common/ 零依赖原则：纯类型定义，不 import 任何业务模块。
所有类型别名仅供静态类型检查使用，零运行时开销。
BacktestResult dataclass 例外 — 它是跨层传递的数据容器，有运行时行为。

使用方式:
    from common.types import TradeAction, PositionDirection

    signal = Signal(action='buy')  # type checker validates 'buy' | 'sell' | ''

单一事实来源：全项目（core、strategies、bridges）共享同一组 Literal 类型。
与 common/constants.py 中同名运行时常量同源，修改时同步更新。
"""

from dataclasses import dataclass, field
from typing import Literal

from .constants import STATUS_FAILED

TradeAction = Literal['buy', 'sell', '']
"""交易动作: 'buy' (买入) | 'sell' (卖出) | '' (无操作)"""

PositionDirection = Literal['long', '']
"""持仓方向: 'long' (多头) | '' (空仓)"""


@dataclass
class BacktestResult:
    """回测结果 — 统一传递结构，在各层之间传递

    消除 dict[str, object] 在各层间手动 unpack，提供精确类型。
    """
    # 标识
    symbol: str
    strategy: str
    strategy_version: str | None = None
    # 状态
    status: str = STATUS_FAILED
    error_message: str | None = None
    success: bool = False
    # 日期
    start_date: str | None = None
    end_date: str | None = None
    # 绩效
    total_trades: int = 0
    end_balance: float = 0.0
    total_return: float = 0.0
    annual_return: float | None = None
    win_trades: int = 0
    loss_trades: int = 0
    win_rate: float | None = None
    max_consecutive_win: int | None = None
    max_consecutive_loss: int | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    win_loss_ratio: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    max_drawdown_duration: int | None = None
    daily_std: float | None = None
    return_drawdown_ratio: float | None = None
    # 引擎配置
    initial_capital: float = 0.0
    commission_rate: float = 0.0
    slippage: float = 0.0
    price_tick: float = 0.0
    contract_size: int = 0
    kline_interval: str = ""
    # 原始数据
    engine_config: dict[str, object] = field(default_factory=dict)
    strategy_params: dict[str, float] | None = None
    fills: list[dict[str, object]] = field(default_factory=list)
    daily_results: list[dict] = field(default_factory=list)
    # 链路信息
    git_hash: str | None = None