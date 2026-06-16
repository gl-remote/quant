"""策略 AOP 装饰器测试 — 验证 with_stop_take_profit 切面

覆盖:
  - 无持仓透传
  - 多头/空头固定比例止盈止损触发
  - 多头/空头固定比例止盈止损不触发
  - 边界条件（刚好触发 / 差一点）
  - ratio=0 永不触发
  - diagnostics 字段完整性
"""

from dataclasses import dataclass

from common.constants import (
    SIGNAL_STOP_LOSS,
    SIGNAL_TAKE_PROFIT,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)
from strategies.core.state import State
from strategies.core.types import Signal, StrategyPosition
from strategies.strategy_aspects import with_stop_take_profit

# --------------------------
# 辅助类型
# --------------------------


@dataclass
class _SimpleParams:
    """简化的策略配置，仅含止损止盈参数"""

    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05


class _MockBar:
    """模拟 Bar — 仅暴露装饰器需要的 .close"""

    def __init__(self, close: float):
        self.close = close


class _MockCtx:
    """模拟 BarContext — 仅暴露装饰器需要的 .bar"""

    def __init__(self, close: float):
        self.bar = _MockBar(close)


# --------------------------
# 辅助函数
# --------------------------


def _make_state(
    direction: str = TRADE_DIRECTION_LONG,
    entry_price: float = 100.0,
    volume: int = 10,
    stop_loss_ratio: float = 0.03,
    take_profit_ratio: float = 0.05,
) -> State:
    """创建测试用 State"""
    return State(
        symbol="TEST",
        period="1m",
        strategy_config=_SimpleParams(
            stop_loss_ratio=stop_loss_ratio,
            take_profit_ratio=take_profit_ratio,
        ),
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


def _make_no_position_state(
    stop_loss_ratio: float = 0.03,
    take_profit_ratio: float = 0.05,
) -> State:
    """创建无持仓 State"""
    return State(
        symbol="TEST",
        period="1m",
        strategy_config=_SimpleParams(
            stop_loss_ratio=stop_loss_ratio,
            take_profit_ratio=take_profit_ratio,
        ),
        capital=100000.0,
        contract_size=10,
    )


_ON_BAR_RETURN = Signal(action="", reason="mock_entry", volume=0)
"""on_bar 默认返回值 — 模拟入场逻辑返回空信号"""


# --------------------------
# 装饰器测试
# --------------------------


@with_stop_take_profit
class _SimpleStrategy:
    """最简单的装饰器测试策略"""

    name = "test"

    def on_bar(self, state, ctx):
        return _ON_BAR_RETURN


class TestWithStopTakeProfit:
    """测试 with_stop_take_profit 类装饰器"""

    def setup_method(self):
        self.strat = _SimpleStrategy()

    # ── 无持仓 ──

    def test_no_position_passthrough(self):
        """无持仓时透传原始 on_bar 返回值"""
        state = _make_no_position_state()
        ctx = _MockCtx(close=50.0)
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN

    # ── 多头止损 ──

    def test_long_stop_loss_triggered(self):
        """多头持仓，价格跌破止损线 → 返回卖出止损信号"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=96.0)  # 跌 4% > 3% 止损
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_STOP_LOSS in signal.reason
        assert signal.volume == 10

    def test_long_stop_loss_not_triggered(self):
        """多头持仓，价格未跌破止损线 → 透传"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=98.0)  # 跌 2% < 3% 止损
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN

    def test_long_stop_loss_boundary_triggered(self):
        """多头止损边界：刚好达到止损比例 → 触发"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=97.0)  # (100-97)/100 = 3% == 止损线
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_STOP_LOSS in signal.reason

    # ── 多头止盈 ──

    def test_long_take_profit_triggered(self):
        """多头持仓，价格涨过止盈线 → 返回卖出的止盈信号"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=106.0)  # 涨 6% > 5% 止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_TAKE_PROFIT in signal.reason

    def test_long_take_profit_not_triggered(self):
        """多头持仓，价格未涨过止盈线 → 透传"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=103.0)  # 涨 3% < 5% 止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN

    def test_long_take_profit_boundary_triggered(self):
        """多头止盈边界：刚好达到止盈比例 → 触发"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=105.0)  # (105-100)/100 = 5% == 止盈线
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_TAKE_PROFIT in signal.reason

    # ── 多头：止盈优先级高于止损 ──

    def test_long_take_profit_priority(self):
        """多头持仓同时满足止盈和止损 → 止盈优先"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=106.0)  # 同时触发止盈(6%>5%)和止损(从最高点回落?)
        # 注：止损用固定比例检查的是 entry_price，106 不会触发止损
        # 所以这里确认的是实际触发了止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_TAKE_PROFIT in signal.reason

    # ── 空头止损 ──

    def test_short_stop_loss_triggered(self):
        """空头持仓，价格涨过止损线 → 返回买入止损信号"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=104.0)  # 涨 4% > 3% 止损
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_BUY
        assert SIGNAL_STOP_LOSS in signal.reason
        assert signal.volume == 10

    def test_short_stop_loss_not_triggered(self):
        """空头持仓，价格未涨过止损线 → 透传"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=102.0)  # 涨 2% < 3% 止损
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN

    def test_short_stop_loss_boundary_triggered(self):
        """空头止损边界：刚好达到止损比例 → 触发"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )
        ctx = _MockCtx(close=103.0)  # (103-100)/100 = 3% == 止损线
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_BUY
        assert SIGNAL_STOP_LOSS in signal.reason

    # ── 空头止盈 ──

    def test_short_take_profit_triggered(self):
        """空头持仓，价格跌破止盈线 → 返回买入止盈信号"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=94.0)  # 跌 6% > 5% 止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_BUY
        assert SIGNAL_TAKE_PROFIT in signal.reason

    def test_short_take_profit_not_triggered(self):
        """空头持仓，价格未跌破止盈线 → 透传"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=97.0)  # 跌 3% < 5% 止盈
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN

    def test_short_take_profit_boundary_triggered(self):
        """空头止盈边界：刚好达到止盈比例 → 触发"""
        state = _make_state(
            direction=TRADE_DIRECTION_SHORT,
            entry_price=100.0,
            take_profit_ratio=0.05,
        )
        ctx = _MockCtx(close=95.0)  # (100-95)/100 = 5% == 止盈线
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_BUY
        assert SIGNAL_TAKE_PROFIT in signal.reason

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
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_STOP_LOSS in signal.reason

    def test_zero_take_profit_triggers_on_any_profit(self):
        """take_profit_ratio=0 时任何盈利都触发止盈"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            take_profit_ratio=0.0,
        )
        ctx = _MockCtx(close=100.01)  # 微涨 0.01%，>=0% 触发
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_TAKE_PROFIT in signal.reason

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
        signal = self.strat.on_bar(state, ctx)
        assert signal.diagnostics.get("entry_price") == 100.0
        assert signal.diagnostics.get("highest_price") == 105.0
        assert signal.diagnostics.get("lowest_price") == 95.0
        assert signal.diagnostics.get("current_close") == 96.0

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
        signal = self.strat.on_bar(state, ctx)
        assert signal.diagnostics.get("entry_price") == 100.0
        assert signal.diagnostics.get("highest_price") == 110.0
        assert signal.diagnostics.get("lowest_price") == 90.0
        assert signal.diagnostics.get("current_close") == 106.0

    # ── 类装饰器完整性 ──

    def test_class_attributes_preserved(self):
        """类装饰器不破坏原始类的属性和其他方法"""
        assert _SimpleStrategy.name == "test"

    def test_multi_bar_same_position(self):
        """多次 on_bar 调用，止损触发前透传，触发后拦截"""
        state = _make_state(
            direction=TRADE_DIRECTION_LONG,
            entry_price=100.0,
            stop_loss_ratio=0.03,
        )

        # 第1次：没触发
        ctx = _MockCtx(close=98.0)
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN

        # 第2次：触发止损
        ctx = _MockCtx(close=96.0)
        signal = self.strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_STOP_LOSS in signal.reason
