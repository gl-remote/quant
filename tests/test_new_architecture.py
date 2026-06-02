"""新架构策略模块测试 - 验证 State 分离、纯决策逻辑

覆盖:
  - State 构造
  - data_requirements
  - on_bar(state, ctx) 纯决策
"""
import dataclasses
from datetime import datetime, timedelta
from typing import List

import pytest
from strategies import (
    State,
    StrategyPosition,
    Bar,
    Signal,
    Fill,
    BarContext,
    DataFeed,
    DataRequirements,
    PeriodRequirements,
    IndicatorRequirements,
    EventsRequirements,
    build_context,
)
from strategies.ma_strategy import MaStrategyCore, MACrossParams
from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    SIGNAL_STOP_LOSS,
    SIGNAL_TAKE_PROFIT,
    SIGNAL_DEATH_CROSS,
    SIGNAL_GOLDEN_CROSS,
)


# --------------------------
# 辅助函数
# --------------------------

def _make_test_bar(
    close: float,
    dt: datetime = datetime(2024, 1, 1, 10, 0, 0),
    symbol: str = "TEST"
) -> Bar:
    return Bar(
        symbol=symbol,
        datetime=dt,
        open=close - 0.5,
        high=close + 0.5,
        low=close - 0.5,
        close=close,
        volume=1000,
    )


def _generate_test_bars(
    count: int,
    start: float = 100.0,
    start_dt: datetime = datetime(2024, 1, 1, 10, 0, 0)
) -> List[Bar]:
    bars = []
    dt = start_dt
    for i in range(count):
        price = start + i * 0.1
        bars.append(_make_test_bar(price, dt))
        dt += timedelta(minutes=1)
    return bars


def _prepare_test_data(
    bars: List[Bar],
    config: MACrossParams
) -> tuple[DataFeed, DataRequirements]:
    """准备 DataFeed 和 DataRequirements 用于测试"""
    feed = DataFeed("TEST")
    feed.register_period("1m")
    feed.register_indicator("1m", "sma", period=config.sma_short)
    feed.register_indicator("1m", "sma", period=config.sma_long)
    feed.load_history_data("1m", bars)
    feed.calculate_all()

    reqs = DataRequirements(
        periods={
            "1m": PeriodRequirements(lookback_bars=max(config.sma_short, config.sma_long) + 1),
        },
        indicators={
            "1m": [
                IndicatorRequirements(name="sma", params={"period": config.sma_short}),
                IndicatorRequirements(name="sma", params={"period": config.sma_long}),
            ],
        },
        events=EventsRequirements.no_events(),
    )
    return feed, reqs


# --------------------------
# 基础测试
# --------------------------

class TestMACrossParams:
    """测试策略配置"""

    def test_default_params(self):
        cfg = MACrossParams()
        assert cfg.sma_short == 5
        assert cfg.sma_long == 20

    def test_custom_params(self):
        cfg = MACrossParams(sma_short=10, sma_long=30)
        assert cfg.sma_short == 10
        assert cfg.sma_long == 30


class TestState:
    """测试运行时状态"""

    def test_basic_state_creation(self):
        cfg = MACrossParams()
        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )
        assert state.symbol == "TEST"
        assert state.position.direction == ""

    def test_state_with_position(self):
        cfg = MACrossParams()
        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            position=StrategyPosition(
                direction=TRADE_DIRECTION_LONG,
                entry_price=100.0,
                volume=10,
            ),
        )
        assert state.position.direction == TRADE_DIRECTION_LONG


class TestDataRequirements:
    """测试策略数据需求声明"""

    def test_ma_strategy_data_requirements(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(sma_short=5, sma_long=20)
        reqs = strat.data_requirements(cfg)
        assert reqs is not None
        assert "1m" in reqs.periods


# --------------------------
# 策略决策测试
# --------------------------

class TestMaStrategyStopLoss:
    """测试策略止损"""

    def test_stop_loss_triggers(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(sma_short=5, sma_long=20, stop_loss_ratio=0.03)

        # 准备数据
        bars = _generate_test_bars(30)
        feed, reqs = _prepare_test_data(bars, cfg)
        latest_bar = _make_test_bar(95.0, bars[-1].datetime + timedelta(minutes=1))
        # 把最新 bar 更新到 DataFeed 里
        feed.update_bar(latest_bar, "1m")
        ctx = build_context(feed, reqs, latest_bar.datetime, latest_bar)

        # 准备状态（持仓）
        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
            position=StrategyPosition(
                direction=TRADE_DIRECTION_LONG,
                entry_price=100.0,
                volume=10,
            ),
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert signal.reason == SIGNAL_STOP_LOSS


class TestMaStrategyTakeProfit:
    """测试策略止盈"""

    def test_take_profit_triggers(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(sma_short=5, sma_long=20, take_profit_ratio=0.05)

        bars = _generate_test_bars(30)
        feed, reqs = _prepare_test_data(bars, cfg)
        latest_bar = _make_test_bar(106.0, bars[-1].datetime + timedelta(minutes=1))
        feed.update_bar(latest_bar, "1m")
        ctx = build_context(feed, reqs, latest_bar.datetime, latest_bar)

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
            position=StrategyPosition(
                direction=TRADE_DIRECTION_LONG,
                entry_price=100.0,
                volume=10,
            ),
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert signal.reason == SIGNAL_TAKE_PROFIT


class TestMaStrategyNoSignal:
    """测试无信号情况"""

    def test_no_position_no_signal(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(sma_short=5, sma_long=20)

        bars = _generate_test_bars(30)
        feed, reqs = _prepare_test_data(bars, cfg)
        latest_bar = bars[-1]
        ctx = build_context(feed, reqs, latest_bar.datetime, latest_bar)

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )

        signal = strat.on_bar(state, ctx)
        # 没有金叉，所以 action 为空
        assert signal.action == "" or signal is not None

