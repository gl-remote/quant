"""MaStrategyCore 核心策略测试 — 适配新的 Strategy + Bridge 架构"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from strategies.ma_strategy import MaStrategyCore, TradingConfig
from strategies.core import Bar, Signal, Fill, StrategyPosition


def _make_bar(close: float, idx: int = 0,
              open: float = 0, high: float = 0, low: float = 0,
              symbol: str = "TEST") -> Bar:
    return Bar(
        symbol=symbol,
        datetime=f"2026-01-{idx+1:02d}",
        open=open or close,
        high=high or close + 1,
        low=low or close - 1,
        close=close,
        volume=1000,
    )


def _feed_bars(strategy: MaStrategyCore, closes: list) -> Signal:
    """喂入价格序列，返回最后一个信号"""
    sig = Signal()
    for i, p in enumerate(closes):
        sig = strategy.on_bar(_make_bar(p, i))
    return sig


class TestSma:
    def test_calculate_sma_basic(self):
        core = MaStrategyCore()
        core._close_history = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = core._calc_sma(3)
        assert result == 4.0

    def test_calculate_sma_period_beyond_data(self):
        core = MaStrategyCore()
        core._close_history = [1.0, 2.0, 3.0]
        result = core._calc_sma(10)
        assert result == 2.0

    def test_calculate_sma_empty_data(self):
        core = MaStrategyCore()
        assert core._calc_sma(3) == 0.0

    def test_calculate_sma_zero_period(self):
        core = MaStrategyCore()
        core._close_history = [1.0, 2.0, 3.0]
        assert core._calc_sma(0) == 0.0


class TestCrossover:
    def test_golden_cross(self):
        core = MaStrategyCore()
        core._prev_sma_short = 19.0
        core._prev_sma_long = 20.0
        assert core._is_golden_cross(21.0, 20.0) is True

    def test_death_cross(self):
        core = MaStrategyCore()
        core._prev_sma_short = 21.0
        core._prev_sma_long = 20.0
        assert core._is_death_cross(19.0, 20.0) is True

    def test_no_cross_both_below(self):
        core = MaStrategyCore()
        core._prev_sma_short = 14.0
        core._prev_sma_long = 20.0
        assert core._is_golden_cross(15.0, 20.0) is False

    def test_no_cross_both_above(self):
        core = MaStrategyCore()
        core._prev_sma_short = 24.0
        core._prev_sma_long = 20.0
        assert core._is_death_cross(25.0, 20.0) is False

    def test_golden_cross_from_equal(self):
        core = MaStrategyCore()
        core._prev_sma_short = 20.0
        core._prev_sma_long = 20.0
        assert core._is_golden_cross(21.0, 20.0) is True


class TestStopLossTakeProfit:
    def _set_long(self, core: MaStrategyCore, entry: float, vol: int = 10):
        core.on_fill(Fill(
            timestamp="2026-01-01", symbol="TEST",
            action='buy', price=entry, volume=vol, reason='golden_cross'))

    def test_stop_loss_triggered(self):
        core = MaStrategyCore(TradingConfig(stop_loss_ratio=0.03))
        self._set_long(core, 100.0)
        assert core._check_stop_loss(96.0) is True

    def test_stop_loss_not_triggered(self):
        core = MaStrategyCore(TradingConfig(stop_loss_ratio=0.03))
        self._set_long(core, 100.0)
        assert core._check_stop_loss(98.0) is False

    def test_stop_loss_no_position(self):
        core = MaStrategyCore(TradingConfig(stop_loss_ratio=0.03))
        assert core._check_stop_loss(90.0) is False

    def test_take_profit_triggered(self):
        core = MaStrategyCore(TradingConfig(take_profit_ratio=0.05))
        self._set_long(core, 100.0)
        assert core._check_take_profit(106.0) is True

    def test_take_profit_not_triggered(self):
        core = MaStrategyCore(TradingConfig(take_profit_ratio=0.05))
        self._set_long(core, 100.0)
        assert core._check_take_profit(104.0) is False

    def test_take_profit_no_position(self):
        core = MaStrategyCore(TradingConfig(take_profit_ratio=0.05))
        assert core._check_take_profit(110.0) is False

    def test_stop_loss_exact_boundary(self):
        core = MaStrategyCore(TradingConfig(stop_loss_ratio=0.03))
        self._set_long(core, 100.0)
        assert core._check_stop_loss(97.0) is True

    def test_take_profit_exact_boundary(self):
        core = MaStrategyCore(TradingConfig(take_profit_ratio=0.05))
        self._set_long(core, 100.0)
        assert core._check_take_profit(105.0) is True


class TestOnBar:
    def test_buy_on_golden_cross(self):
        core = MaStrategyCore(TradingConfig(sma_short=3, sma_long=5))
        for i in range(5):
            core.on_bar(_make_bar(10.0, i))
        sig = core.on_bar(_make_bar(12.0, 5))
        assert sig.action == 'buy'
        assert sig.reason == 'golden_cross'
        assert sig.volume > 0

    def test_sell_on_death_cross_when_long(self):
        core = MaStrategyCore(
            TradingConfig(sma_short=3, sma_long=5, stop_loss_ratio=0.60))
        for i in range(5):
            core.on_bar(_make_bar(20.0, i))
        sig = core.on_bar(_make_bar(22.0, 5))
        assert sig.action == 'buy'
        core.on_fill(Fill(timestamp="t", symbol="TEST",
            action='buy', price=22.0, volume=sig.volume, reason=sig.reason))
        for i in range(5):
            core.on_bar(_make_bar(20.0, 6 + i))
        sig = core.on_bar(_make_bar(18.0, 11))
        assert sig.action == 'sell'
        assert sig.reason == 'death_cross'

    def test_sell_on_stop_loss(self):
        core = MaStrategyCore(
            TradingConfig(sma_short=3, sma_long=5, stop_loss_ratio=0.03))
        for i in range(5):
            core.on_bar(_make_bar(100.0, i))
        sig = core.on_bar(_make_bar(102.0, 5))
        assert sig.action == 'buy'
        core.on_fill(Fill(timestamp="t", symbol="TEST",
            action='buy', price=102.0, volume=sig.volume, reason=sig.reason))
        sig = core.on_bar(_make_bar(98.0, 6))
        assert sig.action == 'sell'
        assert sig.reason == 'stop_loss'

    def test_sell_on_take_profit(self):
        core = MaStrategyCore(
            TradingConfig(sma_short=3, sma_long=5, take_profit_ratio=0.05))
        for i in range(5):
            core.on_bar(_make_bar(100.0, i))
        sig = core.on_bar(_make_bar(102.0, 5))
        assert sig.action == 'buy'
        core.on_fill(Fill(timestamp="t", symbol="TEST",
            action='buy', price=102.0, volume=sig.volume, reason=sig.reason))
        sig = core.on_bar(_make_bar(108.0, 6))
        assert sig.action == 'sell'
        assert sig.reason == 'take_profit'

    def test_stop_loss_priority_over_take_profit(self):
        core = MaStrategyCore(
            TradingConfig(sma_short=3, sma_long=5,
                          stop_loss_ratio=0.03, take_profit_ratio=0.05))
        for i in range(5):
            core.on_bar(_make_bar(100.0, i))
        sig = core.on_bar(_make_bar(102.0, 5))
        assert sig.action == 'buy'
        core.on_fill(Fill(timestamp="t", symbol="TEST",
            action='buy', price=102.0, volume=sig.volume, reason=sig.reason))
        sig = core.on_bar(_make_bar(98.0, 6))
        assert sig.reason == 'stop_loss'


class TestPositionAndReset:
    def test_position_after_fill(self):
        core = MaStrategyCore()
        core.on_fill(Fill(timestamp="t", symbol="T", action='buy',
                          price=100.0, volume=10, reason='g'))
        assert core.position.direction == 'long'
        assert core.position.entry_price == 100.0
        assert core.position.volume == 10

    def test_position_cleared_after_sell(self):
        core = MaStrategyCore()
        core.on_fill(Fill(timestamp="t", symbol="T", action='buy',
                          price=100.0, volume=10, reason='g'))
        core.on_fill(Fill(timestamp="t2", symbol="T", action='sell',
                          price=110.0, volume=10, reason='tp'))
        assert core.position.direction == ''
        assert core.position.volume == 0

    def test_reset(self):
        core = MaStrategyCore()
        core.on_fill(Fill(timestamp="t", symbol="T", action='buy',
                          price=100.0, volume=10, reason='g'))
        core.reset()
        assert core.position.direction == ''
        assert core.position.volume == 0


class TestPositionSize:
    def test_calc_position_size_normal(self):
        core = MaStrategyCore(
            TradingConfig(position_ratio=0.1, capital=100000, contract_size=10))
        core.on_bar(_make_bar(100.0, 0))
        size = core._calc_position_size(100.0)
        assert size == 10

    def test_calc_position_size_minimum_1(self):
        core = MaStrategyCore(
            TradingConfig(position_ratio=0.001, capital=1000, contract_size=10))
        core.on_bar(_make_bar(100.0, 0))
        size = core._calc_position_size(100.0)
        assert size >= 1

    def test_calc_position_size_large_capital(self):
        core = MaStrategyCore(
            TradingConfig(position_ratio=0.5, capital=1000000, contract_size=10))
        core.on_bar(_make_bar(50.0, 0))
        size = core._calc_position_size(50.0)
        expected = int(1000000 * 0.5 / (50 * 10))
        assert size == expected


class TestDefaultConfig:
    def test_default_trading_config(self):
        config = TradingConfig()
        assert config.sma_short == 5
        assert config.sma_long == 20
        assert config.stop_loss_ratio == 0.03
        assert config.take_profit_ratio == 0.05
        assert config.position_ratio == 0.1
        assert config.capital == 100000.0
        assert config.contract_size == 10

    def test_custom_config(self):
        config = TradingConfig(sma_short=10, stop_loss_ratio=0.05)
        assert config.sma_short == 10
        assert config.stop_loss_ratio == 0.05
        assert config.sma_long == 20

    def test_config_setter(self):
        core = MaStrategyCore()
        core.config = TradingConfig(sma_short=8)
        assert core.config.sma_short == 8
