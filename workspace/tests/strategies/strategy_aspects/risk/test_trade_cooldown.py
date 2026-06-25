"""交易冷却期切面测试"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from common.constants import SIGNAL_TRADE_COOLDOWN, TRADE_DIRECTION_LONG
from strategies.core.state import State
from strategies.core.types import Fill, Signal, StrategyPosition
from strategies.strategy_aspects import with_trade_cooldown


@dataclass
class _Params:
    pass


class _MockBar:
    def __init__(self, dt: datetime) -> None:
        self.datetime = dt


class _MockCtx:
    def __init__(self, dt: datetime) -> None:
        self.bar = _MockBar(dt)


_ON_BAR_RETURN = Signal(action="buy", reason="entry", volume=1)


@with_trade_cooldown(minutes=10)
class _CooldownStrategy:
    def on_bar(self, state: State[_Params], ctx: Any) -> Signal:
        return _ON_BAR_RETURN


def _make_state(fill_time: datetime | None = None, has_position: bool = False) -> State[_Params]:
    fills = []
    if fill_time is not None:
        fills.append(
            Fill(
                timestamp=str(fill_time),
                symbol="TEST",
                action="buy",
                price=100,
                volume=1,
                reason="entry",
            )
        )

    position = (
        StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=100, volume=1)
        if has_position
        else StrategyPosition()
    )

    return State(
        symbol="TEST",
        period="1m",
        strategy_config=_Params(),
        fills=fills,
        position=position,
    )


class TestWithTradeCooldown:
    def setup_method(self) -> None:
        self.strategy = _CooldownStrategy()

    def test_no_fill_passthrough(self) -> None:
        state = _make_state()
        ctx = _MockCtx(datetime(2024, 1, 1, 10, 0, 0))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN

    def test_blocks_entry_inside_cooldown(self) -> None:
        fill_time = datetime(2024, 1, 1, 10, 0, 0)
        state = _make_state(fill_time=fill_time)
        ctx = _MockCtx(fill_time + timedelta(minutes=5))

        signal = self.strategy.on_bar(state, ctx)

        assert signal.action == ""
        assert signal.reason == SIGNAL_TRADE_COOLDOWN
        assert signal.diagnostics["cooldown_minutes"] == 10.0
        assert signal.diagnostics["remaining_seconds"] == 300.0

    def test_passthrough_after_cooldown(self) -> None:
        fill_time = datetime(2024, 1, 1, 10, 0, 0)
        state = _make_state(fill_time=fill_time)
        ctx = _MockCtx(fill_time + timedelta(minutes=10))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN

    def test_position_passthrough_even_inside_cooldown(self) -> None:
        fill_time = datetime(2024, 1, 1, 10, 0, 0)
        state = _make_state(fill_time=fill_time, has_position=True)
        ctx = _MockCtx(fill_time + timedelta(minutes=5))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN

    def test_invalid_fill_timestamp_passthrough(self) -> None:
        state = _make_state()
        state.fills.append(Fill(timestamp="invalid", symbol="TEST"))
        ctx = _MockCtx(datetime(2024, 1, 1, 10, 0, 0))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN
