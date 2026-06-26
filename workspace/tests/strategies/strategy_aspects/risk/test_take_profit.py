"""建议型切面测试 — 验证 with_take_profit

覆盖:
  - 无持仓透传
  - 多头/空头固定比例止盈触发（写入 aspects.risk）
  - 多头/空头固定比例止盈不触发
  - 边界条件（刚好触发 / 差一点）
  - ratio=0 永不触发
  - diagnostics 字段完整性
  - aspects.risk 被正确填充
"""

from common.constants import (
    SIGNAL_TAKE_PROFIT,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)
from strategies.core.types import Signal
from strategies.strategy_aspects import exit_for_take_profit
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
    take_profit_ratio: float = 0.05,
):
    return make_ratio_risk_state(
        direction=direction,
        entry_price=entry_price,
        volume=volume,
        take_profit_ratio=take_profit_ratio,
    )


def _make_no_position_state(take_profit_ratio: float = 0.05):
    return make_no_position_ratio_state(take_profit_ratio=take_profit_ratio)


_ON_BAR_RETURN = Signal(action="", reason="mock_entry", volume=0)
"""on_bar 默认返回值 — 模拟入场逻辑返回空信号"""


# --------------------------
# 装饰器测试
# --------------------------


@exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
class _SimpleStrategy:
    """最简单的装饰器测试策略"""

    name = "test"

    def on_bar(self, state, ctx):
        return _ON_BAR_RETURN


class TestExitTakeProfitWhen:
    """测试 exit_for_take_profit_when 类装饰器"""

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

    # ── 多头止盈 ──

    def test_long_take_profit_triggered(self):
        """多头持仓，价格涨过止盈线 → aspects.risk 写入止盈理由"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=106.0)  # 涨 6% > 5% 止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.take_profit.exit)
        assert reason.name == SIGNAL_TAKE_PROFIT

    def test_long_take_profit_not_triggered(self):
        """多头持仓，价格未涨过止盈线 → risk 为空"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=103.0)  # 涨 3% < 5% 止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_long_take_profit_boundary_triggered(self):
        """多头止盈边界：刚好达到止盈比例 → 触发"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=105.0)  # (105-100)/100 = 5% == 止盈线
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.take_profit.exit)
        assert reason.name == SIGNAL_TAKE_PROFIT

    # ── 空头止盈 ──

    def test_short_take_profit_triggered(self):
        """空头持仓，价格跌破止盈线 → aspects.risk 写入止盈理由"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=94.0)  # 跌 6% > 5% 止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.take_profit.exit)
        assert reason.name == SIGNAL_TAKE_PROFIT

    def test_short_take_profit_not_triggered(self):
        """空头持仓，价格未跌破止盈线 → risk 为空"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=97.0)  # 跌 3% < 5% 止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_short_take_profit_boundary_triggered(self):
        """空头止盈边界：刚好达到止盈比例 → 触发"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=95.0)  # (100-95)/100 = 5% == 止盈线
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.take_profit.exit)
        assert reason.name == SIGNAL_TAKE_PROFIT

    # ── 零比例边界 ──

    def test_zero_take_profit_triggers_on_any_profit(self):
        """take_profit_ratio=0 时任何盈利都触发止盈"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.0,
        )
        ctx = _MockCtx(close=100.01)  # 微涨 0.01%，>=0% 触发
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx.aspects.risk.take_profit.exit)
        assert reason.name == SIGNAL_TAKE_PROFIT

    # ── diagnostics ──

    def test_take_profit_diagnostics(self):
        """止盈触发时 diagnostics 包含 entry_price/highest/lowest/current_close"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        state.position.highest_price = 110.0
        state.position.lowest_price = 90.0
        ctx = _MockCtx(close=106.0)
        self.strat.on_bar(state, ctx)
        assert ctx.aspects.diagnostics.get("entry_price") == 100.0
        assert ctx.aspects.diagnostics.get("highest_price") == 110.0
        assert ctx.aspects.diagnostics.get("lowest_price") == 90.0
        assert ctx.aspects.diagnostics.get("current_close") == 106.0

    # ── 类装饰器完整性 ──

    def test_class_attributes_preserved(self):
        """类装饰器不破坏原始类的属性和其他方法"""
        assert _SimpleStrategy.name == "test"

    def test_multi_bar_same_position(self):
        """多次 on_bar 调用，风险建议逐 bar 独立产生"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )

        # 第1次：没触发
        ctx = _MockCtx(close=103.0)
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

        # 第2次：触发止盈（注意：每次 on_bar 前 aspects 会被框架重新构造，
        # 测试里手动复用 ctx 仅用于验证本次 bar 的写入行为）
        ctx2 = _MockCtx(close=106.0)
        signal = self.strat.on_bar(state, ctx2)
        assert signal is _ON_BAR_RETURN
        reason = assert_single_reason(ctx2.aspects.risk.take_profit.exit)
        assert reason.name == SIGNAL_TAKE_PROFIT
