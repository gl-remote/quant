"""MA 交叉策略集成测试 — 验证多空进场、止盈止损、ATR 止盈止损

策略 on_bar(state, ctx) 是纯函数，不依赖 DataFeed 构造上下文。
测试中直接构造 BarContext，无需经过 DataFeed。

覆盖:
  - data_requirements 返回有效结构
  - 多空进场
  - 固定比例止盈止损（多空）
  - ATR 止盈止损（多空）
  - 无信号场景
"""

from datetime import datetime, timedelta

import pandas as pd
from common.constants import (
    SIGNAL_STOP_LOSS,
    SIGNAL_TAKE_PROFIT,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)
from strategies.core.base import State
from strategies.core.indicators import generate_indicator_column_name
from strategies.core.types import Bar, StrategyPosition
from strategies.ma_strategy import MACrossParams, MaStrategyCore
from strategies.runtime.period import PeriodDataView
from strategies.runtime.requirements import BarContext, DataRequirements

# --------------------------
# 辅助函数
# --------------------------


def _period_data_view(
    period_name: str,
    close_prices: list[float],
    indicator_values: dict[str, float] | None = None,
) -> PeriodDataView:
    """构造测试用的 PeriodDataView。

    用给定的收盘价构造 _df_ref，通过 IndicatorLUT 计算指标值，
    写入 _df_ref 列，供策略的 get_indicator 方法读取。
    """
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    times = [base_time + timedelta(minutes=i) for i in range(len(close_prices))]
    df = pd.DataFrame(
        {
            "open": close_prices,
            "high": [p * 1.001 for p in close_prices],
            "low": [p * 0.999 for p in close_prices],
            "close": close_prices,
            "volume": [1000] * len(close_prices),
        },
        index=pd.Index(times, name="datetime"),
    )

    # 直接构造 DataFrame，指标列通过 set 方式写入（不依赖 IndicatorLUT）
    return PeriodDataView(
        df_ref=df,
        events_ref=None,
        start_idx=0,
        end_idx=len(df) - 1,
        current_time=pd.Timestamp(times[-1]),
        period=period_name,
        forming_bar=None,
    )


def _ensure_indicator(name: str, periods: list[str], views: dict[str, PeriodDataView], value: float) -> None:
    """确保指定指标在视图中有预期的值。

    如果策略通过 ctx.multi[period].indicator(name, -1) 读取指标，
    这里确保该列在 _df_ref 中存在，且最后一行包含目标值。
    """
    for period in periods:
        view = views.get(period)
        if view is None:
            continue
        last_idx = view._end_idx
        if last_idx >= 0:
            view._df_ref.at[view._df_ref.index[last_idx], name] = value


def _make_ctx(
    close_prices: list[float],
    periods: dict[str, int],
    is_long: bool | None = None,
) -> BarContext:
    """构造 BarContext，用于策略 on_bar 测试。

    :param close_prices: 基础周期收盘价序列
    :param periods: {周期名: lookback_bars, ...}
    :param is_long: None=中性, True=多头信号, False=空头信号
    """
    latest_time = datetime(2024, 1, 1, 10, 0, 0) + timedelta(minutes=len(close_prices) - 1)
    latest_bar = Bar(
        symbol="TEST",
        datetime=latest_time,
        open=close_prices[-1],
        high=close_prices[-1],
        low=close_prices[-1],
        close=close_prices[-1],
        volume=1000,
    )

    multi: dict[str, PeriodDataView] = {}
    for period_name, lookback in periods.items():
        view = _period_data_view(period_name, close_prices[-lookback:])
        multi[period_name] = view

    # 设置信号相关的指标值（每个视图用周期前缀的列名）
    if is_long is not None:
        for period_name, view in multi.items():
            last_idx = view._end_idx
            if last_idx < 0:
                continue
            df = view._df_ref
            last_time = df.index[last_idx]
            base_price = close_prices[-1]

            sma_short_col = generate_indicator_column_name("sma", {"period": 5}, period=period_name)
            sma_long_col = generate_indicator_column_name("sma", {"period": 20}, period=period_name)
            macd_col = generate_indicator_column_name("macd", {"fast": 12, "slow": 26, "signal": 9}, period=period_name)
            kdj_col = generate_indicator_column_name("kdj", {"n": 9, "k_period": 3, "d_period": 3}, period=period_name)

            if is_long:
                df.at[last_time, sma_short_col] = base_price * 1.01
                df.at[last_time, sma_long_col] = base_price
                df.at[last_time, macd_col] = 0.1
                df.at[last_time, kdj_col] = 15.0
            else:
                df.at[last_time, sma_short_col] = base_price
                df.at[last_time, sma_long_col] = base_price * 1.01
                df.at[last_time, macd_col] = -0.1
                df.at[last_time, kdj_col] = 85.0

    return BarContext(
        symbol="TEST",
        bar=latest_bar,
        multi=multi,
        events=[],
    )


# --------------------------
# 测试
# --------------------------


class TestDataRequirements:
    """测试策略数据需求 — 不依赖具体的周期/指标数量和名称"""

    def test_returns_valid_requirements(self):
        cfg = MACrossParams()
        reqs = MaStrategyCore().data_requirements(cfg)
        assert isinstance(reqs, DataRequirements)
        assert len(reqs.periods) > 0
        assert len(reqs.indicators) > 0

    def test_requirements_can_be_applied(self):
        """验证 reqs 中的周期和指标可解析"""
        cfg = MACrossParams()
        reqs = MaStrategyCore().data_requirements(cfg)
        for period in reqs.periods:
            assert period, f"周期名不能为空: {period}"
        for _period, indicators in reqs.indicators.items():
            for ind in indicators:
                assert ind.name, "指标名不能为空"
                assert ind.func is not None, f"指标 {ind.name} 未绑定实现"


class TestMACrossParams:
    def test_default_params(self):
        cfg = MACrossParams()
        assert cfg.sma_short == 5
        assert cfg.sma_long == 20
        assert cfg.atr_period == 14
        assert cfg.atr_stop_loss_multiplier == 2.0
        assert cfg.atr_take_profit_multiplier == 3.0
        assert cfg.kdj_oversold == 30
        assert cfg.kdj_overbought == 70
        assert cfg.signal_profile == "trend_macd"
        assert cfg.exit_on_reverse_signal is True
        assert cfg.kdj_pullback_long == 45
        assert cfg.kdj_pullback_short == 55
        assert cfg.reverse_confirm_bars == 0
        assert cfg.min_hold_bars == 0
        assert cfg.max_hold_bars == 0
        assert cfg.entry_cooldown_bars == 0
        assert cfg.trend_gap_atr == 0.0

    def test_custom_params(self):
        cfg = MACrossParams(
            sma_short=10,
            sma_long=30,
            atr_period=10,
            atr_stop_loss_multiplier=1.5,
            atr_take_profit_multiplier=2.5,
        )
        assert cfg.sma_short == 10
        assert cfg.sma_long == 30
        assert cfg.atr_period == 10
        assert cfg.atr_stop_loss_multiplier == 1.5
        assert cfg.atr_take_profit_multiplier == 2.5


class TestState:
    def test_basic_state_creation(self):
        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=MACrossParams(),
            capital=100000.0,
            contract_size=10,
        )
        assert state.symbol == "TEST"
        assert state.position.direction == ""

    def test_state_with_position(self):
        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=MACrossParams(),
            position=StrategyPosition(
                direction=TRADE_DIRECTION_LONG,
                entry_price=100.0,
                volume=10,
            ),
        )
        assert state.position.direction == TRADE_DIRECTION_LONG


class TestMaStrategyEntry:
    """测试多空进场逻辑"""

    def test_long_entry(self):
        strat = MaStrategyCore()
        cfg = MACrossParams()
        ctx = _make_ctx(
            close_prices=[100.0] * 30,
            periods={"1m": 30, "5m": 10, "15m": 10},
            is_long=True,
        )

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_BUY
        assert "long" in signal.reason.lower() or "entry" in signal.reason.lower()
        assert signal.volume > 0

    def test_short_entry(self):
        strat = MaStrategyCore()
        cfg = MACrossParams()
        ctx = _make_ctx(
            close_prices=[100.0] * 30,
            periods={"1m": 30, "5m": 10, "15m": 10},
            is_long=False,
        )

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_SELL
        assert "short" in signal.reason.lower() or "entry" in signal.reason.lower()
        assert signal.volume > 0

    def test_trend_only_profile_allows_entry_without_confirm_keys(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(signal_profile="sma_only")
        ctx = _make_ctx(
            close_prices=[100.0] * 30,
            periods={"1m": 30, "5m": 10, "15m": 10},
        )
        trend_key = "sma_sma_short_15m_gt_sma_sma_long_15m"
        ctx.aspects.direction.long.trend.append(type("Reason", (), {"key": trend_key})())

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_BUY

    def test_full_profile_requires_confirm_keys(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(signal_profile="full")
        ctx = _make_ctx(
            close_prices=[100.0] * 30,
            periods={"1m": 30, "5m": 10, "15m": 10},
        )
        trend_key = "sma_sma_short_15m_gt_sma_sma_long_15m"
        ctx.aspects.direction.long.trend.append(type("Reason", (), {"key": trend_key})())

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == ""

    def test_reverse_short_signal_exits_long_position(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(signal_profile="sma_only", exit_on_reverse_signal=True)
        ctx = _make_ctx(
            close_prices=[100.0] * 30,
            periods={"1m": 30, "5m": 10, "15m": 10},
            is_long=False,
        )

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
        assert signal.reason == "reverse_short_exit"

    def test_reverse_exit_disabled_keeps_position(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(signal_profile="sma_only", exit_on_reverse_signal=False)
        ctx = _make_ctx(
            close_prices=[100.0] * 30,
            periods={"1m": 30, "5m": 10, "15m": 10},
            is_long=False,
        )

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
        assert signal.action == ""

    def test_no_entry_when_position_exists(self):
        strat = MaStrategyCore()
        cfg = MACrossParams()
        ctx = _make_ctx(
            close_prices=[100.0] * 30,
            periods={"1m": 30, "5m": 10, "15m": 10},
            is_long=True,
        )

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
        assert signal.action == "" or (signal.action != TRADE_ACTION_BUY and signal.action != TRADE_ACTION_SELL)


class TestMaStrategyFixedStopLoss:
    """测试固定比例止损（多空）"""

    def test_long_fixed_stop_loss(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(stop_loss_ratio=0.03)

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

        # 当前价格 109.9（bar[99] = 100 + 99*0.1），离 97 很远，不会触发止损
        # 设置一个更低的 bar 触发止损
        ctx_with_low = _make_ctx(
            [100.0 + i * 0.1 for i in range(99)] + [96.0],  # bar[-1] close=96
            {"1m": 30, "5m": 10, "15m": 10},
        )

        signal = strat.on_bar(state, ctx_with_low)
        assert signal.action == TRADE_ACTION_SELL
        assert SIGNAL_STOP_LOSS in signal.reason

    def test_short_fixed_stop_loss(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(stop_loss_ratio=0.03)

        ctx = _make_ctx(
            [100.0 - i * 0.1 for i in range(99)] + [104.0],  # up 4%
            {"1m": 30, "5m": 10, "15m": 10},
        )

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
            position=StrategyPosition(
                direction=TRADE_DIRECTION_SHORT,
                entry_price=100.0,
                volume=10,
                lowest_price=100.0,
            ),
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_BUY
        assert SIGNAL_STOP_LOSS in signal.reason


class TestMaStrategyFixedTakeProfit:
    """测试固定比例止盈（多空）"""

    def test_long_fixed_take_profit(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(take_profit_ratio=0.05)

        ctx = _make_ctx(
            [100.0 + i * 0.1 for i in range(99)] + [107.0],  # up 7%
            {"1m": 30, "5m": 10, "15m": 10},
        )

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
        assert SIGNAL_TAKE_PROFIT in signal.reason

    def test_short_fixed_take_profit(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(take_profit_ratio=0.05)

        ctx = _make_ctx(
            [100.0 - i * 0.1 for i in range(99)] + [93.0],  # down 7%
            {"1m": 30, "5m": 10, "15m": 10},
        )

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
            position=StrategyPosition(
                direction=TRADE_DIRECTION_SHORT,
                entry_price=100.0,
                volume=10,
                lowest_price=100.0,
            ),
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == TRADE_ACTION_BUY
        assert SIGNAL_TAKE_PROFIT in signal.reason


class TestMaStrategyNoSignal:
    """测试无信号情况"""

    def test_no_position_no_signal(self):
        strat = MaStrategyCore()
        cfg = MACrossParams()
        ctx = _make_ctx(
            [100.0] * 30,
            {"1m": 30, "5m": 10, "15m": 10},
        )

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == ""
