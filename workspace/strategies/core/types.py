"""标准化数据类型 — 框架无关，贯穿 Strategy ↔ Bridge 的通信协议

Strategy 产生决策 (Signal)，Bridge 转换为框架指令。
Bridge 接收行情 (Bar)，喂给 Strategy 产生信号。

volume 全部使用 float，兼容整手数（期货）和分数股（股票）场景。

【类型选择说明】
- Bar.datetime 使用 datetime 对象而非 str：策略内可直接
  bar.datetime.hour / .weekday() 做时间维度逻辑，无需自行 strptime。
- Fill.timestamp 保持 str：成交时间戳在 Bridge 中已有格式化逻辑 (strftime)，
  且语义不同。Bar.datetime → Fill.timestamp 时通过 str() 显式转换。

【扩展准则】
  新增类型应判断：如果是 Strategy 和 Bridge 之间传递的数据 → 放 core；
  如果是回测或实盘运行产生的衍生数据 → 放对应模块（如 backtest / report）。
"""

from dataclasses import dataclass, field
from datetime import datetime as dt
from typing import Any

from common.types import PositionDirection, TradeAction


@dataclass
class Bar:
    """标准化K线数据 — 框架无关

    所有 Bridge 将自身框架的原始数据转换为此格式后再传给 Strategy，
    Strategy 因此无需感知 vnpy BarData / tqsdk kline_serial 等异构格式。
    """

    symbol: str = ""
    datetime: dt = dt.min
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0


@dataclass
class Signal:
    """策略产生的完整交易决策

    Strategy.on_bar() 返回此对象，Bridge 据此执行或转发。
    volume 由策略预计算，Bridge 只需执行，不做数量决策。
    """

    action: TradeAction = ""  # 'buy' | 'sell' | ''
    reason: str = ""  # 'golden_cross' | 'stop_loss' | ...
    volume: float = 0  # 策略预计算的开仓手数
    diagnostics: dict[str, Any] = field(default_factory=dict)
    """决策快照，策略将决策时依赖的指标值塞入此 dict，Bridge 统一用于诊断日志
    例如: {"entry_price": 4000, "highest_price": 4200, "atr": 50, ...}"""


@dataclass
class StrategyPosition:
    """持仓快照"""

    direction: PositionDirection = ""  # 'long' | ''
    entry_price: float = 0.0
    volume: float = 0
    highest_price: float = 0.0
    """持仓期间最高价（多头：价格高点；空头：价格低点，用于回撤止盈）"""
    lowest_price: float = 0.0
    """持仓期间最低价（多头：价格低点；空头：价格高点，信息量参考）"""


@dataclass
class Fill:
    """订单成交记录 — Bridge 通知 Strategy 的成交回执

    注意: Fill 不含 pnl/commission 等盈亏字段。
    盈亏计算依赖开平仓配对，属于回测层逻辑（见 BacktestTrade / TradeRecord），
    不属于 Strategy ↔ Bridge 通信协议的范畴。
    """

    timestamp: str = ""
    symbol: str = ""
    action: TradeAction = ""  # 'buy' | 'sell'
    price: float = 0.0
    volume: float = 0
    reason: str = ""  # 触发原因
