"""止损后交易冷却期切面测试（建议型）"""

from datetime import datetime, timedelta
from typing import Any

from common.constants import SIGNAL_TRADE_COOLDOWN
from strategies.core.state import State
from strategies.core.types import Fill, Signal
from strategies.strategy_aspects import entry_block_after_stop_loss
from tests.helpers.risk import EmptyRiskParams, MockDatetimeCtx, assert_single_reason, make_cooldown_state

_Params = EmptyRiskParams
_MockCtx = MockDatetimeCtx


_ON_BAR_RETURN = Signal(action="buy", reason="entry", volume=1)


@entry_block_after_stop_loss("cooldown() < 10")
class _CooldownStrategy:
    def on_bar(self, state: State[_Params], ctx: Any) -> Signal:
        return _ON_BAR_RETURN


def _make_state(
    fill_time: datetime | None = None,
    has_position: bool = False,
    reason: str = "",
) -> State[_Params]:
    return make_cooldown_state(fill_time=fill_time, has_position=has_position, reason=reason)


class TestWithCooldownAfterStopLoss:
    def setup_method(self) -> None:
        self.strategy = _CooldownStrategy()

    def test_no_fill_passthrough(self) -> None:
        state = _make_state()
        ctx = _MockCtx(datetime(2024, 1, 1, 10, 0, 0))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_blocks_entry_inside_cooldown(self) -> None:
        """冷却期内 → aspects.risk 写入 cooldown 理由"""
        fill_time = datetime(2024, 1, 1, 10, 0, 0)
        state = _make_state(fill_time=fill_time)
        ctx = _MockCtx(fill_time + timedelta(minutes=5))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.stop_loss.entry_block)
        assert reason.name == SIGNAL_TRADE_COOLDOWN
        assert reason.detail["left_value"] < 10.0
        assert reason.detail["op"] == "<"
        assert reason.detail["right_value"] == 10.0

    def test_passthrough_after_cooldown(self) -> None:
        fill_time = datetime(2024, 1, 1, 10, 0, 0)
        state = _make_state(fill_time=fill_time)
        ctx = _MockCtx(fill_time + timedelta(minutes=10))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_position_passthrough_even_inside_cooldown(self) -> None:
        """有持仓时 cooldown 不写入 risk"""
        fill_time = datetime(2024, 1, 1, 10, 0, 0)
        state = _make_state(fill_time=fill_time, has_position=True)
        ctx = _MockCtx(fill_time + timedelta(minutes=5))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_invalid_fill_timestamp_passthrough(self) -> None:
        state = _make_state()
        state.fills.append(Fill(timestamp="invalid", symbol="TEST"))
        ctx = _MockCtx(datetime(2024, 1, 1, 10, 0, 0))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_take_profit_fill_does_not_trigger_stop_loss_cooldown(self) -> None:
        """止盈成交不触发止损冷却期"""
        fill_time = datetime(2024, 1, 1, 10, 0, 0)
        state = _make_state(fill_time=fill_time, reason="take_profit")
        ctx = _MockCtx(fill_time + timedelta(minutes=5))

        signal = self.strategy.on_bar(state, ctx)

        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []
