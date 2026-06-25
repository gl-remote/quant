"""建议型切面测试 — 验证 with_stop_loss_atr

覆盖:
  - ATR 指标自动注册到 data_requirements
  - 无持仓透传
  - 多头/空头 ATR 止损触发（写入 aspects.risk）
  - 多头/空头 ATR 止损不触发
  - ATR 值为空/零时跳过
  - diagnostics 字段完整性
  - 多个 AOP 装饰器叠加
"""

from dataclasses import dataclass

from common.constants import (
    SIGNAL_STOP_LOSS,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)
from strategies import (
    DataRequirements,
    IndicatorSpec,
    PeriodRequirements,
    Signal,
    State,
    StrategyPosition,
)
from strategies.core.indicators import generate_indicator_column_name, sma_func
from strategies.strategy_aspects import exit_for_stop_loss
from strategies.strategy_aspects.primitives import StrategyAspects

# --------------------------
# 辅助类型
# --------------------------


@dataclass
class _ATRParams:
    """含 ATR 参数的策略配置"""

    atr_period: int = 14
    atr_stop_loss_multiplier: float = 2.0
    stop_loss_ratio: float = 0.03


class _MockPeriodView:
    """模拟 PeriodDataView — 仅暴露装饰器需要的 .indicator()"""

    def __init__(self, col_values: dict[str, float]):
        self._col_values = col_values

    def indicator(self, col: str, offset: int = -1) -> float | None:
        return self._col_values.get(col)


class _MockMultiCtx:
    """模拟 BarContext — 带 multi 多周期视图"""

    def __init__(self, close: float, atr_value: float | None = 2.0, period: str = "15m"):
        self.bar = _MockBar(close)
        self.multi: dict[str, _MockPeriodView] = {}
        self.aspects = StrategyAspects()
        if atr_value is not None:
            atr_col = generate_indicator_column_name("atr", {"period": 14}, period=period)
            self.multi[period] = _MockPeriodView({atr_col: atr_value})


class _MockBar:
    def __init__(self, close: float):
        self.close = close


# --------------------------
# 辅助函数
# --------------------------


def _make_state(
    direction: str = TRADE_DIRECTION_LONG,
    entry_price: float = 100.0,
    volume: int = 10,
    atr_stop_loss_multiplier: float = 2.0,
    atr_period: int = 14,
) -> State:
    return State(
        symbol="TEST",
        period="1m",
        strategy_config=_ATRParams(
            atr_period=atr_period,
            atr_stop_loss_multiplier=atr_stop_loss_multiplier,
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


def _make_no_position_state() -> State:
    return State(
        symbol="TEST",
        period="1m",
        strategy_config=_ATRParams(),
        capital=100000.0,
        contract_size=10,
    )


_ON_BAR_RETURN = Signal(action="", reason="mock_entry", volume=0)


# --------------------------
# 装饰器测试
# --------------------------


@exit_for_stop_loss("profit_abs() >= atr@15m * {atr_stop_loss_multiplier}")
class _ATRStrategy:
    """ATR 止损测试策略"""

    name = "test_atr"

    def data_requirements(self, config) -> DataRequirements:
        return DataRequirements(
            periods={
                "1m": PeriodRequirements(lookback_bars=60),
                "5m": PeriodRequirements(lookback_bars=30),
                "15m": PeriodRequirements(lookback_bars=30),
            },
            indicators={
                "1m": [IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func)],
                "5m": [IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func)],
            },
            events=None,
        )

    def on_bar(self, state, ctx):
        return _ON_BAR_RETURN


class TestExitStopLossATR:
    """测试 exit_for_stop_loss_atr 类装饰器"""

    def setup_method(self):
        self.strat = _ATRStrategy()

    # ── data_requirements ──

    def test_data_requirements_auto_register_atr(self):
        """data_requirements 自动注册 ATR 指标到 15m"""
        reqs = self.strat.data_requirements(_ATRParams())
        assert reqs is not None
        has_atr = any(ind.name == "atr" and ind.params.get("period") == 14 for ind in reqs.indicators.get("15m", []))
        assert has_atr, "15m 周期未自动注册 ATR 指标"

    def test_data_requirements_preserves_existing(self):
        """已有周期和指标不受影响"""
        reqs = self.strat.data_requirements(_ATRParams())
        assert "1m" in reqs.periods
        assert "5m" in reqs.periods

    # ── 无持仓 ──

    def test_no_position_passthrough(self):
        state = _make_no_position_state()
        ctx = _MockMultiCtx(close=50.0)
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    # ── 多头 ATR 止损 ──

    def test_long_atr_stop_loss_triggered(self):
        """多头 ATR 止损触发 (atr=2.0, multiplier=2.0, 损失线=96)"""
        state = _make_state(direction=TRADE_DIRECTION_LONG, entry_price=100.0, atr_stop_loss_multiplier=2.0)
        ctx = _MockMultiCtx(close=95.0, atr_value=2.0)  # 100-2*2=96, 95<96
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert len(ctx.aspects.risk.stop_loss.exit) == 1
        assert ctx.aspects.risk.stop_loss.exit[0].name == SIGNAL_STOP_LOSS

    def test_long_atr_stop_loss_not_triggered(self):
        state = _make_state(direction=TRADE_DIRECTION_LONG, entry_price=100.0, atr_stop_loss_multiplier=2.0)
        ctx = _MockMultiCtx(close=97.0, atr_value=2.0)  # 100-2*2=96, 97>96
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    # ── 空头 ATR 止损 ──

    def test_short_atr_stop_loss_triggered(self):
        """空头 ATR 止损触发 (atr=2.0, multiplier=2.0, 损失线=104)"""
        state = _make_state(direction=TRADE_DIRECTION_SHORT, entry_price=100.0, atr_stop_loss_multiplier=2.0)
        ctx = _MockMultiCtx(close=105.0, atr_value=2.0)  # 100+2*2=104, 105>104
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert len(ctx.aspects.risk.stop_loss.exit) == 1
        assert ctx.aspects.risk.stop_loss.exit[0].name == SIGNAL_STOP_LOSS

    def test_short_atr_stop_loss_not_triggered(self):
        state = _make_state(direction=TRADE_DIRECTION_SHORT, entry_price=100.0, atr_stop_loss_multiplier=2.0)
        ctx = _MockMultiCtx(close=103.0, atr_value=2.0)  # 100+2*2=104, 103<104
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    # ── ATR 为空/零 ──

    def test_atr_none_skips(self):
        """ATR 值为 None 时跳过检查"""
        state = _make_state(direction=TRADE_DIRECTION_LONG, entry_price=100.0)
        ctx = _MockMultiCtx(close=50.0, atr_value=None)
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    def test_atr_zero_skips(self):
        """ATR 值为 0 时跳过检查"""
        state = _make_state(direction=TRADE_DIRECTION_LONG, entry_price=100.0)
        ctx = _MockMultiCtx(close=50.0, atr_value=0.0)
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        assert ctx.aspects.risk.all_reasons == []

    # ── diagnostics ──

    def test_atr_diagnostics(self):
        """ATR 止损触发时 diagnostics 字段齐全"""
        state = _make_state(direction=TRADE_DIRECTION_LONG, entry_price=100.0, atr_stop_loss_multiplier=2.0)
        state.position.highest_price = 110.0
        state.position.lowest_price = 90.0
        ctx = _MockMultiCtx(close=95.0, atr_value=2.0)
        self.strat.on_bar(state, ctx)
        assert ctx.aspects.diagnostics.get("entry_price") == 100.0
        assert ctx.aspects.diagnostics.get("highest_price") == 110.0
        assert ctx.aspects.diagnostics.get("lowest_price") == 90.0
        assert ctx.aspects.diagnostics.get("current_close") == 95.0


# --------------------------
# 与固定比例止损叠加测试
# --------------------------


@exit_for_stop_loss("profit_pct() >= {stop_loss_ratio}")
@exit_for_stop_loss("profit_abs() >= atr@15m * {atr_stop_loss_multiplier}")
class _CombinedStrategy:
    """叠加固定比例 + ATR 止损的测试策略"""

    name = "test_combined"

    def data_requirements(self, config) -> DataRequirements:
        return DataRequirements(
            periods={
                "1m": PeriodRequirements(lookback_bars=60),
                "15m": PeriodRequirements(lookback_bars=30),
            },
            indicators={"1m": [IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func)]},
            events=None,
        )

    def on_bar(self, state, ctx):
        return _ON_BAR_RETURN


class TestCombinedDecorators:
    """测试多个 AOP 装饰器叠加"""

    def setup_method(self):
        self.strat = _CombinedStrategy()

    def test_data_requirements_has_atr(self):
        reqs = self.strat.data_requirements(_ATRParams())
        assert reqs is not None
        has_atr = any(ind.name == "atr" for ind in reqs.indicators.get("15m", []))
        assert has_atr

    def test_fixed_stop_loss_triggers(self):
        """固定比例止损触发 → aspects.risk 包含固定比例止损"""
        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=_ATRParams(stop_loss_ratio=0.03),
            capital=100000.0,
            contract_size=10,
            position=StrategyPosition(
                direction=TRADE_DIRECTION_LONG,
                entry_price=100.0,
                volume=10,
                highest_price=100.0,
                lowest_price=100.0,
            ),
        )
        # ATR 不止损，但固定比例止损
        ctx = _MockMultiCtx(close=96.0, atr_value=2.0)  # 跌 4%
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        risk_names = [r.name for r in ctx.aspects.risk.all_reasons]
        assert SIGNAL_STOP_LOSS in risk_names

    def test_atr_stop_loss_triggers(self):
        """ATR 止损触发 → aspects.risk 包含 ATR 止损"""
        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=_ATRParams(atr_stop_loss_multiplier=2.0),
            capital=100000.0,
            contract_size=10,
            position=StrategyPosition(
                direction=TRADE_DIRECTION_LONG,
                entry_price=100.0,
                volume=10,
                highest_price=100.0,
                lowest_price=100.0,
            ),
        )
        # 固定比例不动，但 ATR 止损
        ctx = _MockMultiCtx(close=95.0, atr_value=2.0)  # 100-2*2=96
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        risk_names = [r.name for r in ctx.aspects.risk.all_reasons]
        assert SIGNAL_STOP_LOSS in risk_names

    def test_both_stop_loss_trigger(self):
        """固定止损和 ATR 止损都触发时，两个切面都写入 risk"""
        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=_ATRParams(stop_loss_ratio=0.03, atr_stop_loss_multiplier=2.0),
            capital=100000.0,
            contract_size=10,
            position=StrategyPosition(
                direction=TRADE_DIRECTION_LONG,
                entry_price=100.0,
                volume=10,
                highest_price=100.0,
                lowest_price=100.0,
            ),
        )
        ctx = _MockMultiCtx(close=95.0, atr_value=2.0)  # 跌 5% > 3%, 且 < 96
        signal = self.strat.on_bar(state, ctx)
        assert signal is _ON_BAR_RETURN
        # 两个切面都写入了 risk
        risk_names = [r.name for r in ctx.aspects.risk.all_reasons]
        assert SIGNAL_STOP_LOSS in risk_names
        assert len(ctx.aspects.risk.stop_loss.exit) == 2
