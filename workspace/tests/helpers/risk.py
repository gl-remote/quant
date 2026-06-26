"""策略风控测试 helper。"""

from dataclasses import dataclass
from datetime import datetime

from strategies.core.state import State
from strategies.core.types import Fill, StrategyPosition
from strategies.strategy_aspects.primitives import StrategyAspects


@dataclass
class RatioRiskParams:
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05


@dataclass
class EmptyRiskParams:
    pass


class MockCloseBar:
    def __init__(self, close: float) -> None:
        self.close = close


class MockDatetimeBar:
    def __init__(self, dt: datetime) -> None:
        self.datetime = dt


class MockCloseCtx:
    def __init__(self, close: float) -> None:
        self.bar = MockCloseBar(close)
        self.aspects = StrategyAspects()


class MockDatetimeCtx:
    def __init__(self, dt: datetime) -> None:
        self.bar = MockDatetimeBar(dt)
        self.aspects = StrategyAspects()


def make_ratio_risk_state(
    direction: str,
    entry_price: float = 100.0,
    volume: int = 10,
    stop_loss_ratio: float = 0.03,
    take_profit_ratio: float = 0.05,
) -> State[RatioRiskParams]:
    return State(
        symbol="TEST",
        period="1m",
        strategy_config=RatioRiskParams(stop_loss_ratio=stop_loss_ratio, take_profit_ratio=take_profit_ratio),
        capital=100000.0,
        contract_size=10,
        position=StrategyPosition(
            direction=direction,
            entry_price=entry_price,
            volume=volume,
            highest_price=entry_price,
            lowest_price=entry_price,
        ),
    )


def make_no_position_ratio_state(
    stop_loss_ratio: float = 0.03,
    take_profit_ratio: float = 0.05,
) -> State[RatioRiskParams]:
    return State(
        symbol="TEST",
        period="1m",
        strategy_config=RatioRiskParams(stop_loss_ratio=stop_loss_ratio, take_profit_ratio=take_profit_ratio),
        capital=100000.0,
        contract_size=10,
    )


def make_cooldown_state(
    fill_time: datetime | None = None,
    has_position: bool = False,
    reason: str = "",
) -> State[EmptyRiskParams]:
    fills = []
    if fill_time is not None:
        fills.append(
            Fill(
                timestamp=str(fill_time),
                symbol="TEST",
                action="buy",
                price=100,
                volume=1,
                reason=reason,
            )
        )

    position = StrategyPosition(direction="long", entry_price=100, volume=1) if has_position else StrategyPosition()

    return State(
        symbol="TEST",
        period="1m",
        strategy_config=EmptyRiskParams(),
        fills=fills,
        position=position,
    )


def assert_single_reason(reasons):
    assert len(reasons) == 1
    return reasons[0]
