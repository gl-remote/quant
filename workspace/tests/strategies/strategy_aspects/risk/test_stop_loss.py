"""建议型切面测试 — 验证 with_stop_loss

覆盖:
  - 无持仓透传
  - 多头/空头固定比例止损触发（写入 aspects.risk）
  - 多头/空头固定比例止损不触发
  - 边界条件（刚好触发 / 差一点）
  - ratio=0 永不触发
  - diagnostics 字段完整性
  - aspects.risk 被正确填充
"""

from common.constants import (
    SIGNAL_STOP_LOSS,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)
from strategies.core.types import Signal
from strategies.strategy_aspects import exit_for_stop_loss
from tests.helpers.risk import (
    MockCloseCtx,
    assert_single_reason,
    make_no_position_ratio_state,
    make_ratio_risk_state,
)

_MockCtx = MockCloseCtx


def _make_state(
    direction: str = TRADE_DIRECTION_LONG,
    entry_price: float = 100.0,
    volume: int = 10,
    stop_loss_ratio: float = 0.03,
):
    return make_ratio_risk_state(
        direction=direction,
        entry_price=entry_price,
        volume=volume,
        stop_loss_ratio=stop_loss_ratio,
    )


def _make_no_position_state(stop_loss_ratio: float = 0.03):
    return make_no_position_ratio_state(stop_loss_ratio=stop_loss_ratio)


_ON_BAR_RETURN = Signal(action="", reason="mock_entry", volume=0)
"""on_bar 默认返回值 — 模拟入场逻辑返回空信号"""


# --------------------------
# 装饰器测试
# --------------------------


@exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
class _SimpleStrategy:
    """最简单的装饰器测试策略"""

    name = "test"

    def on_bar(self, state, ctx):
        return _ON_BAR_RETURN


class TestExitStopLossWhen:
    """测试 exit_for_stop_loss_when 类装饰器"""

    def setup_method(self):
        self.strat = _SimpleStrategy()

    # ── 无持仓 ──

    def test_no_position_passthrough(self):
        """无持仓时透传原始 on_bar 返回值，不写入 risk"""
        state = _make_no_position_state()
        ctx = _MockCtx(close=50.0)
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    # ── 多头止损 ──

    def test_long_stop_loss_triggered(self):
        """多头持仓，价格跌破止损线 → aspects.risk 写入止损理由"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=96.0)  # 跌 4% > 3% 止损
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.stop_loss.exit)
        assert reason.name == SIGNAL_STOP_LOSS

    def test_long_stop_loss_not_triggered(self):
        """多头持仓，价格未跌破止损线 → risk 为空"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=98.0)  # 跌 2% < 3% 止损
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_long_stop_loss_boundary_triggered(self):
        """多头止损边界：刚好达到止损比例 → 触发"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=97.0)  # (100-97)/100 = 3% == 止损线
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.stop_loss.exit)
        assert reason.name == SIGNAL_STOP_LOSS

    # ── 空头止损 ──

    def test_short_stop_loss_triggered(self):
        """空头持仓，价格涨过止损线 → aspects.risk 写入止损理由"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=104.0)  # 涨 4% > 3% 止损
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.stop_loss.exit)
        assert reason.name == SIGNAL_STOP_LOSS

    def test_short_stop_loss_not_triggered(self):
        """空头持仓，价格未涨过止损线 → risk 为空"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=102.0)  # 涨 2% < 3% 止损
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_short_stop_loss_boundary_triggered(self):
        """空头止损边界：刚好达到止损比例 → 触发"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=103.0)  # (103-100)/100 = 3% == 止损线
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.stop_loss.exit)
        assert reason.name == SIGNAL_STOP_LOSS

    # ── 零比例边界 ──

    def test_zero_stop_loss_triggers_on_any_loss(self):
        """stop_loss_ratio=0 时任何亏损都触发止损"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.0,
        )
        ctx = _MockCtx(close=99.99)  # 微跌 0.01%，>=0% 触发
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.stop_loss.exit)
        assert reason.name == SIGNAL_STOP_LOSS

    # ── diagnostics ──

    def test_stop_loss_diagnostics(self):
        """止损触发时 diagnostics 包含 entry_price/highest/lowest/current_close"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        state.position.highest_price = 105.0
        state.position.lowest_price = 95.0
        ctx = _MockCtx(close=96.0)
        self.strat.on_bar(state, ctx)
        assert ctx.aspects.diagnostics.get("entry_price") == 100.0
        assert ctx.aspects.diagnostics.get("highest_price") == 105.0
        assert ctx.aspects.diagnostics.get("lowest_price") == 95.0
        assert ctx.aspects.diagnostics.get("current_close") == 96.0

    # ── 类装饰器完整性 ──

    def test_class_attributes_preserved(self):
        """类装饰器不破坏原始类的属性和其他方法"""
        assert _SimpleStrategy.name == "test"

    def test_multi_bar_same_position(self):
        """多次 on_bar 调用，风险建议逐 bar 独立产生"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )

        # 第1次：没触发
        ctx = _MockCtx(close=98.0)
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

        # 第2次：触发止损（注意：每次 on_bar 前 aspects 会被框架重新构造，
        # 测试里手动复用 ctx 仅用于验证本次 bar 的写入行为）
        ctx2 = _MockCtx(close=96.0)
        signal = self.strat.on_bar(state, ctx2)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx2.aspects.risk.stop_loss.exit)
        assert reason.name == SIGNAL_STOP_LOSS
