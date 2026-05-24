"""MaStrategyCore 核心策略测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from strategies.ma_strategy import (
    MaStrategyCore, TradingConfig, StrategyState,
)
from strategies.core import TradeRecord, PositionStatus


class TestSma:
    def test_calculate_sma_basic(self):
        core = MaStrategyCore()
        result = core.calculate_sma([1.0, 2.0, 3.0, 4.0, 5.0], 3)
        assert result == 4.0

    def test_calculate_sma_period_beyond_data(self):
        core = MaStrategyCore()
        result = core.calculate_sma([1.0, 2.0, 3.0], 10)
        assert result == 2.0

    def test_calculate_sma_empty_data(self):
        core = MaStrategyCore()
        assert core.calculate_sma([], 3) == 0.0

    def test_calculate_sma_zero_period(self):
        core = MaStrategyCore()
        assert core.calculate_sma([1.0, 2.0, 3.0], 0) == 0.0

    def test_calculate_sma_single_element(self):
        core = MaStrategyCore()
        assert core.calculate_sma([5.0], 1) == 5.0

    def test_calculate_sma_float_precision(self):
        core = MaStrategyCore()
        result = core.calculate_sma([100.0, 101.0, 102.0], 2)
        assert abs(result - 101.5) < 0.01


class TestCrossover:
    def test_golden_cross(self):
        core = MaStrategyCore()
        result = core.check_crossover(
            short=21.0, long=20.0,
            prev_short=19.0, prev_long=20.0,
        )
        assert result == 'golden_cross'

    def test_death_cross(self):
        core = MaStrategyCore()
        result = core.check_crossover(
            short=19.0, long=20.0,
            prev_short=21.0, prev_long=20.0,
        )
        assert result == 'death_cross'

    def test_no_cross_both_below(self):
        core = MaStrategyCore()
        result = core.check_crossover(
            short=15.0, long=20.0,
            prev_short=14.0, prev_long=20.0,
        )
        assert result == 'none'

    def test_no_cross_both_above(self):
        core = MaStrategyCore()
        result = core.check_crossover(
            short=25.0, long=20.0,
            prev_short=24.0, prev_long=20.0,
        )
        assert result == 'none'

    def test_no_cross_equal_both(self):
        core = MaStrategyCore()
        result = core.check_crossover(
            short=20.0, long=20.0,
            prev_short=20.0, prev_long=20.0,
        )
        assert result == 'none'

    def test_golden_cross_from_equal(self):
        core = MaStrategyCore()
        result = core.check_crossover(
            short=21.0, long=20.0,
            prev_short=20.0, prev_long=20.0,
        )
        assert result == 'golden_cross'


class TestStopLossTakeProfit:
    def test_stop_loss_triggered(self):
        core = MaStrategyCore(TradingConfig(stop_loss_ratio=0.03))
        core.on_enter(100.0, 10)
        assert core.check_stop_loss(96.0) is True

    def test_stop_loss_not_triggered(self):
        core = MaStrategyCore(TradingConfig(stop_loss_ratio=0.03))
        core.on_enter(100.0, 10)
        assert core.check_stop_loss(98.0) is False

    def test_stop_loss_no_position(self):
        core = MaStrategyCore(TradingConfig(stop_loss_ratio=0.03))
        assert core.check_stop_loss(90.0) is False

    def test_take_profit_triggered(self):
        core = MaStrategyCore(TradingConfig(take_profit_ratio=0.05))
        core.on_enter(100.0, 10)
        assert core.check_take_profit(106.0) is True

    def test_take_profit_not_triggered(self):
        core = MaStrategyCore(TradingConfig(take_profit_ratio=0.05))
        core.on_enter(100.0, 10)
        assert core.check_take_profit(104.0) is False

    def test_take_profit_no_position(self):
        core = MaStrategyCore(TradingConfig(take_profit_ratio=0.05))
        assert core.check_take_profit(110.0) is False

    def test_stop_loss_exact_boundary(self):
        core = MaStrategyCore(TradingConfig(stop_loss_ratio=0.03))
        core.on_enter(100.0, 10)
        assert core.check_stop_loss(97.0) is True

    def test_take_profit_exact_boundary(self):
        core = MaStrategyCore(TradingConfig(take_profit_ratio=0.05))
        core.on_enter(100.0, 10)
        assert core.check_take_profit(105.0) is True


class TestOnBarSignal:
    def _build_closes(self, start: float, trend: float, count: int):
        return [start + i * trend for i in range(count)]

    def test_buy_on_golden_cross(self):
        core = MaStrategyCore(TradingConfig(sma_short=3, sma_long=5))
        closes = [10.0] * 5 + [12.0, 14.0, 16.0, 18.0, 20.0]
        # After 10 bars: sma(3) ≈ 18, sma(5) ≈ 16 → golden cross
        core.state.prev_sma_short = 10.0
        core.state.prev_sma_long = 10.0
        signal, reason = core.on_bar_signal(closes, 20.0)
        assert signal == 'buy'
        assert reason == 'golden_cross'

    def test_sell_on_death_cross_when_long(self):
        core = MaStrategyCore(
            TradingConfig(sma_short=3, sma_long=5, stop_loss_ratio=0.60)
        )
        closes = [20.0] * 5 + [18.0, 16.0, 14.0, 12.0, 10.0]
        # After 10 bars: sma(3) ≈ 12, sma(5) ≈ 14 → death cross
        # stop_loss won't trigger: (20-10)/20=0.50 < 0.60
        core.on_enter(20.0, 10)
        core.state.prev_sma_short = 20.0
        core.state.prev_sma_long = 16.0
        signal, reason = core.on_bar_signal(closes, 10.0)
        assert signal == 'sell'
        assert reason == 'death_cross'

    def test_sell_on_stop_loss(self):
        core = MaStrategyCore(
            TradingConfig(sma_short=3, sma_long=5, stop_loss_ratio=0.03)
        )
        closes = [100.0] * 10
        core.on_enter(100.0, 10)
        core.state.prev_sma_short = 100.0
        core.state.prev_sma_long = 90.0
        signal, reason = core.on_bar_signal(closes, 96.0)
        assert signal == 'sell'
        assert reason == 'stop_loss'

    def test_sell_on_take_profit(self):
        core = MaStrategyCore(
            TradingConfig(sma_short=3, sma_long=5, take_profit_ratio=0.05)
        )
        closes = [100.0] * 10
        core.on_enter(100.0, 10)
        core.state.prev_sma_short = 100.0
        core.state.prev_sma_long = 90.0
        signal, reason = core.on_bar_signal(closes, 106.0)
        assert signal == 'sell'
        assert reason == 'take_profit'

    def test_no_signal_empty_closes(self):
        core = MaStrategyCore()
        signal, reason = core.on_bar_signal([], 100.0)
        assert signal is None
        assert reason == ''

    def test_sma_state_updated_after_signal(self):
        core = MaStrategyCore(TradingConfig(sma_short=3, sma_long=5))
        closes = [100.0] * 10
        core.state.prev_sma_short = 100.0
        core.state.prev_sma_long = 100.0
        core.on_bar_signal(closes, 100.0)
        assert core.state.prev_sma_short == 100.0
        assert core.state.prev_sma_long == 100.0

    def test_stop_loss_priority_over_take_profit(self):
        core = MaStrategyCore(
            TradingConfig(sma_short=3, sma_long=5,
                          stop_loss_ratio=0.03, take_profit_ratio=0.05)
        )
        closes = [100.0] * 10
        core.on_enter(100.0, 10)
        core.state.prev_sma_short = 100.0
        core.state.prev_sma_long = 90.0
        # Both stop loss and take profit could trigger — stop loss takes priority
        signal, reason = core.on_bar_signal(closes, 96.0)
        assert reason == 'stop_loss'


class TestEnterExit:
    def test_on_enter_sets_state(self):
        core = MaStrategyCore()
        core.on_enter(100.0, 10)
        assert core.state.position_status == PositionStatus.LONG_POSITION
        assert core.state.entry_price == 100.0
        assert core.state.current_position == 10

    def test_on_exit_profit(self):
        core = MaStrategyCore()
        core.on_enter(100.0, 10)
        profit = core.on_exit(110.0)
        assert profit == 100.0
        assert core.state.position_status == PositionStatus.NO_POSITION
        assert core.state.entry_price == 0.0
        assert core.state.current_position == 0

    def test_on_exit_loss(self):
        core = MaStrategyCore()
        core.on_enter(100.0, 10)
        profit = core.on_exit(90.0)
        assert profit == -100.0

    def test_on_exit_no_position(self):
        core = MaStrategyCore()
        profit = core.on_exit(100.0)
        assert profit == 0.0

    def test_on_exit_zero_entry_price(self):
        core = MaStrategyCore()
        core.state.position_status = PositionStatus.LONG_POSITION
        core.state.entry_price = 0.0
        profit = core.on_exit(100.0)
        assert profit == 0.0

    def test_on_exit_resets_state(self):
        core = MaStrategyCore()
        core.on_enter(100.0, 10)
        core.on_exit(110.0)
        assert core.state.position_status == PositionStatus.NO_POSITION
        assert core.state.entry_price == 0.0
        assert core.state.current_position == 0


class TestPositionSize:
    def test_calc_position_size_normal(self):
        core = MaStrategyCore(TradingConfig(position_ratio=0.1))
        size = core.calc_position_size(100.0, 100000.0, contract_size=10)
        assert size == 10

    def test_calc_position_size_minimum_1(self):
        core = MaStrategyCore(TradingConfig(position_ratio=0.001))
        size = core.calc_position_size(100.0, 1000.0, contract_size=10)
        assert size >= 1

    def test_calc_position_size_large_capital(self):
        core = MaStrategyCore(TradingConfig(position_ratio=0.5))
        size = core.calc_position_size(50.0, 1000000.0, contract_size=10)
        expected = int(1000000 * 0.5 / (50 * 10))
        assert size == expected


class TestPerformance:
    def test_get_performance_with_trades(self):
        core = MaStrategyCore()
        records = [
            TradeRecord(direction="buy", price=100, volume=10, reason="golden_cross"),
            TradeRecord(direction="sell", price=110, volume=10, profit=100, reason="take_profit"),
            TradeRecord(direction="buy", price=105, volume=10, reason="golden_cross"),
            TradeRecord(direction="sell", price=102, volume=10, profit=-30, reason="stop_loss"),
        ]
        perf = core.get_performance(records)
        assert perf['total_trades'] == 2
        assert perf['winning_trades'] == 1
        assert perf['losing_trades'] == 1
        assert perf['win_rate'] == 0.5
        assert perf['total_profit'] == 70.0

    def test_get_performance_no_sells(self):
        core = MaStrategyCore()
        records = [
            TradeRecord(direction="buy", price=100, volume=10),
        ]
        perf = core.get_performance(records)
        assert perf['total_trades'] == 0
        assert perf['win_rate'] == 0.0

    def test_get_performance_empty(self):
        core = MaStrategyCore()
        perf = core.get_performance([])
        assert perf['total_trades'] == 0
        assert perf['winning_trades'] == 0
        assert perf['total_profit'] == 0.0


class TestDefaultConfig:
    def test_default_trading_config(self):
        config = TradingConfig()
        assert config.sma_short == 5
        assert config.sma_long == 20
        assert config.stop_loss_ratio == 0.03
        assert config.take_profit_ratio == 0.05
        assert config.position_ratio == 0.1

    def test_custom_config(self):
        config = TradingConfig(sma_short=10, stop_loss_ratio=0.05)
        assert config.sma_short == 10
        assert config.stop_loss_ratio == 0.05
        assert config.sma_long == 20

    def test_default_strategy_state(self):
        state = StrategyState()
        assert state.position_status == PositionStatus.NO_POSITION
        assert state.entry_price == 0.0
        assert state.current_position == 0