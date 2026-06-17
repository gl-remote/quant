"""MA 交叉策略集成测试 — 验证多空进场、止盈止损、ATR 止盈止损

覆盖:
  - State 构造
  - data_requirements
  - on_bar(state, ctx) 纯决策
  - 多空进场
  - 固定比例止盈止损（多空）
  - ATR 止盈止损（多空）
"""

from datetime import datetime, timedelta

from common.constants import (
    SIGNAL_STOP_LOSS,
    SIGNAL_TAKE_PROFIT,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)
from strategies import (
    Bar,
    DataFeed,
    DataRequirements,
    EventsRequirements,
    IndicatorSpec,
    PeriodRequirements,
    State,
    StrategyPosition,
    build_context,
)
from strategies.core.indicators import sma_func
from strategies.ma_strategy import MACrossParams, MaStrategyCore

# --------------------------
# 辅助函数
# --------------------------


def _make_test_bar(close: float, dt: datetime = datetime(2024, 1, 1, 10, 0, 0), symbol: str = "TEST") -> Bar:
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
    count: int, start: float = 100.0, start_dt: datetime = datetime(2024, 1, 1, 10, 0, 0)
) -> list[Bar]:
    bars = []
    dt = start_dt
    for i in range(count):
        price = start + i * 0.1
        bars.append(_make_test_bar(price, dt))
        dt += timedelta(minutes=1)
    return bars


def _prepare_test_data(
    bars: list[Bar],
    config: MACrossParams,
    use_multi_period: bool = True,
) -> tuple[DataFeed, DataRequirements]:
    """准备 DataFeed 和 DataRequirements 用于测试"""
    feed = DataFeed("TEST")

    # 从策略获取数据需求（切面已自动注册所有周期和指标）
    strat = MaStrategyCore()
    reqs = strat.data_requirements(config)
    assert reqs is not None

    if use_multi_period:
        # 注册所有需要的周期和指标（从策略数据需求中获取）
        for period_name in reqs.periods:
            feed.register_period(period_name)
        for period_name, indicators in reqs.indicators.items():
            for ind in indicators:
                feed.register_indicator(period_name, ind)
    else:
        # 单周期模式（仅用于基础测试）
        feed.register_period("1m")
        feed.register_indicator(
            "1m", IndicatorSpec(name="sma", params={"period": config.sma_short}, window=config.sma_short, func=sma_func)
        )
        feed.register_indicator(
            "1m", IndicatorSpec(name="sma", params={"period": config.sma_long}, window=config.sma_long, func=sma_func)
        )

    # 加载历史数据
    feed.load_history_data(bars)

    feed.calculate_all()

    if not use_multi_period:
        # 单周期模式需要覆盖 reqs
        reqs = DataRequirements(
            periods={
                "1m": PeriodRequirements(lookback_bars=max(config.sma_short, config.sma_long) + 1),
            },
            indicators={
                "1m": [
                    IndicatorSpec(
                        name="sma", params={"period": config.sma_short}, window=config.sma_short, func=sma_func
                    ),
                    IndicatorSpec(
                        name="sma", params={"period": config.sma_long}, window=config.sma_long, func=sma_func
                    ),
                ],
            },
            events=EventsRequirements.no_events(),
        )

    return feed, reqs


def _set_indicator_value(feed: DataFeed, timeframe: str, indicator_name: str, value: float, offset: int = 0, **kwargs):
    """设置指标值（用于测试）

    通过 PeriodData._df 直接写入指标列，模拟指标计算结果。

    Args:
        timeframe: K线周期，如 '1m' / '5m' / '15m'
        indicator_name: 指标名称
        value: 要设置的值
        offset: 偏移量（-1 表示最新一行）
        **kwargs: 指标参数（如 period=10, fast=12 等），用于生成列名
    """
    from strategies.core.indicators import generate_indicator_column_name

    col_name = generate_indicator_column_name(indicator_name, kwargs)
    period_data = feed._periods[timeframe]
    df = period_data._df

    # 确保 df 有足够行数
    while len(df) <= abs(offset):
        # 用最后一行填充不足的行
        df.loc[df.index[-1] + (len(df) - abs(offset))] = df.iloc[-1]

    idx = df.index[offset] if offset >= 0 else df.index[offset]
    df.at[idx, col_name] = value


def _create_uptrend_context(feed: DataFeed, config: MACrossParams, latest_price: float):
    """创建上升趋势上下文（做多条件满足）"""
    latest_dt = datetime(2024, 1, 1, 12, 0, 0)
    latest_bar = _make_test_bar(latest_price, latest_dt)
    feed.update_bar(latest_bar, "1m")
    feed.update_bar(latest_bar, "5m")
    feed.update_bar(latest_bar, "15m")

    # 设置指标值：多头条件
    # 5m SMA(short) > 1h SMA(long)
    _set_indicator_value(feed, "5m", "sma", 100.0, -1, period=config.sma_short)
    _set_indicator_value(feed, "1h", "sma", 99.0, -1, period=config.sma_long)
    # 1m MACD > 0
    _set_indicator_value(feed, "1m", "macd", 0.1, -1, fast=12, slow=26, signal=9)
    # 1m KDJ < 20
    _set_indicator_value(feed, "1m", "kdj", 15.0, -1, n=9, k_period=3, d_period=3)
    # 5m MACD > 0
    _set_indicator_value(feed, "5m", "macd", 0.1, -1, fast=12, slow=26, signal=9)
    # 5m KDJ < 20
    _set_indicator_value(feed, "5m", "kdj", 15.0, -1, n=9, k_period=3, d_period=3)
    # 1h ATR
    _set_indicator_value(feed, "1h", "atr", 2.0, -1, period=config.atr_period)

    reqs = MaStrategyCore().data_requirements(config)
    return build_context(feed, reqs, latest_dt, latest_bar)


def _create_downtrend_context(feed: DataFeed, config: MACrossParams, latest_price: float):
    """创建下降趋势上下文（做空条件满足）"""
    latest_dt = datetime(2024, 1, 1, 12, 0, 0)
    latest_bar = _make_test_bar(latest_price, latest_dt)
    feed.update_bar(latest_bar, "1m")
    feed.update_bar(latest_bar, "5m")
    feed.update_bar(latest_bar, "1h")

    # 设置指标值：空头条件
    # 5m SMA(short) < 1h SMA(long)
    _set_indicator_value(feed, "5m", "sma", 99.0, -1, period=config.sma_short)
    _set_indicator_value(feed, "1h", "sma", 100.0, -1, period=config.sma_long)
    # 1m MACD < 0
    _set_indicator_value(feed, "1m", "macd", -0.1, -1, fast=12, slow=26, signal=9)
    # 1m KDJ > 80
    _set_indicator_value(feed, "1m", "kdj", 85.0, -1, n=9, k_period=3, d_period=3)
    # 5m MACD < 0
    _set_indicator_value(feed, "5m", "macd", -0.1, -1, fast=12, slow=26, signal=9)
    # 5m KDJ > 80
    _set_indicator_value(feed, "5m", "kdj", 85.0, -1, n=9, k_period=3, d_period=3)
    # 1h ATR
    _set_indicator_value(feed, "1h", "atr", 2.0, -1, period=config.atr_period)

    reqs = MaStrategyCore().data_requirements(config)
    return build_context(feed, reqs, latest_dt, latest_bar)


# --------------------------
# 基础测试
# --------------------------


class TestDataRequirements:
    """测试策略数据需求"""

    def test_data_requirements(self):
        """测试数据需求提取"""
        from strategies.ma_strategy import MACrossParams, MaStrategyCore

        cfg = MACrossParams()
        # 测试能否正常提取数据需求，不硬编码具体周期
        strat = MaStrategyCore()
        reqs = strat.data_requirements(cfg)
        assert isinstance(reqs, DataRequirements)
        assert len(reqs.periods) == 2
        # 每个周期都有指标
        for period in reqs.periods:
            assert period in reqs.indicators
            assert len(reqs.indicators[period]) > 0
        # 绑定到 1h 周期
        assert "1h" in reqs.indicators
        # 验证结构正确，不硬编码周期名称
        assert isinstance(reqs, DataRequirements)
        assert len(reqs.periods) == 2
        for period in reqs.periods:
            assert period in reqs.indicators
            assert len(reqs.indicators[period]) > 0
        strat = MaStrategyCore()
        reqs = strat.data_requirements(cfg)
        assert isinstance(reqs, DataRequirements)
        assert len(reqs.periods) == 2
        # 每个周期都有指标
        for period in reqs.periods:
            assert period in reqs.indicators
            assert len(reqs.indicators[period]) > 0
        # 绑定到 1h 周期
        assert "1h" in reqs.indicators


class TestMACrossParams:
    """测试策略配置"""

    def test_default_params(self):
        cfg = MACrossParams()
        assert cfg.sma_short == 10
        assert cfg.sma_long == 40
        assert cfg.atr_period == 14
        assert cfg.atr_stop_loss_multiplier == 2.0
        assert cfg.atr_take_profit_multiplier == 3.0
        assert cfg.kdj_oversold == 30
        assert cfg.kdj_overbought == 70

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


# --------------------------
# 多空进场测试
# --------------------------


class TestMaStrategyEntry:
    """测试多空进场逻辑"""

    def test_long_entry(self):
        """测试做多进场"""
        strat = MaStrategyCore()
        cfg = MACrossParams()

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)
        ctx = _create_uptrend_context(feed, cfg, 100.0)

        # 准备空仓状态
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
        """测试做空进场"""
        strat = MaStrategyCore()
        cfg = MACrossParams()

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)
        ctx = _create_downtrend_context(feed, cfg, 100.0)

        # 准备空仓状态
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

    def test_no_entry_when_position_exists(self):
        """测试持仓时不产生新进场信号"""
        strat = MaStrategyCore()
        cfg = MACrossParams()

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)
        ctx = _create_uptrend_context(feed, cfg, 100.0)

        # 准备多仓状态
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
        # 持仓时不应产生新进场信号
        assert signal.action == "" or (signal.action != TRADE_ACTION_BUY and signal.action != TRADE_ACTION_SELL)


# --------------------------
# 固定比例止盈止损测试
# --------------------------


class TestMaStrategyFixedStopLoss:
    """测试固定比例止损（多空）"""

    def test_long_fixed_stop_loss(self):
        """测试多头固定比例止损"""
        strat = MaStrategyCore()
        cfg = MACrossParams(stop_loss_ratio=0.03)

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        # 创建持有多仓的上下文，价格跌破止损线
        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(96.0, latest_dt)  # 从100跌到96，跌4%，超过3%止损
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值（不重要，因为止损优先）
        _set_indicator_value(feed, "5m", "sma", 100.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 99.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        # 准备多仓状态
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
        assert SIGNAL_STOP_LOSS in signal.reason

    def test_short_fixed_stop_loss(self):
        """测试空头固定比例止损"""
        strat = MaStrategyCore()
        cfg = MACrossParams(stop_loss_ratio=0.03)

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        # 创建持有空仓的上下文，价格涨破止损线
        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(104.0, latest_dt)  # 从100涨到104，涨4%，超过3%止损
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值（不重要，因为止损优先）
        _set_indicator_value(feed, "5m", "sma", 99.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 100.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        # 准备空仓状态
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
        """测试多头固定比例止盈"""
        strat = MaStrategyCore()
        cfg = MACrossParams(take_profit_ratio=0.05)

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        # 创建持有多仓的上下文，价格涨过止盈线
        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(106.0, latest_dt)  # 从100涨到106，涨6%，超过5%止盈
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值
        _set_indicator_value(feed, "5m", "sma", 100.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 99.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        # 准备多仓状态
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
        """测试空头固定比例止盈"""
        strat = MaStrategyCore()
        cfg = MACrossParams(take_profit_ratio=0.05)

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        # 创建持有空仓的上下文，价格跌破止盈线
        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(94.0, latest_dt)  # 从100跌到94，跌6%，超过5%止盈
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值
        _set_indicator_value(feed, "5m", "sma", 99.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 100.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        # 准备空仓状态
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


# --------------------------
# ATR 止盈止损测试
# --------------------------


class TestMaStrategyATRStopLoss:
    """测试 ATR 止损（多空）"""

    def test_long_atr_stop_loss(self):
        """测试多头 ATR 止损"""
        strat = MaStrategyCore()
        cfg = MACrossParams(
            atr_period=14,
            atr_stop_loss_multiplier=2.0,
            stop_loss_ratio=0.10,  # 设置较大的固定止损，让ATR止损先触发
        )

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        # 创建持有多仓的上下文，价格跌破ATR止损线
        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(95.0, latest_dt)  # 从100跌到95，ATR=2，2*2=4，100-4=96，95<96触发
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值
        _set_indicator_value(feed, "5m", "sma", 100.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 99.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        # 准备多仓状态
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
        assert SIGNAL_STOP_LOSS in signal.reason

    def test_short_atr_stop_loss(self):
        """测试空头 ATR 止损"""
        strat = MaStrategyCore()
        cfg = MACrossParams(
            atr_period=14,
            atr_stop_loss_multiplier=2.0,
            stop_loss_ratio=0.10,  # 设置较大的固定止损，让ATR止损先触发
        )

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        # 创建持有空仓的上下文，价格涨破ATR止损线
        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(105.0, latest_dt)  # 从100涨到105，ATR=2，2*2=4，100+4=104，105>104触发
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值
        _set_indicator_value(feed, "5m", "sma", 99.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 100.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        # 准备空仓状态
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


class TestMaStrategyATRTakeProfit:
    """测试 ATR 止盈（多空）"""

    def test_long_atr_take_profit(self):
        """测试多头 ATR 止盈"""
        strat = MaStrategyCore()
        cfg = MACrossParams(
            atr_period=14,
            atr_take_profit_multiplier=3.0,
            take_profit_ratio=0.10,  # 设置较大的固定止盈，让ATR止盈先触发
        )

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        # 创建持有多仓的上下文，价格涨过ATR止盈线
        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(107.0, latest_dt)  # 从100涨到107，ATR=2，3*2=6，100+6=106，107>106触发
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值
        _set_indicator_value(feed, "5m", "sma", 100.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 99.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        # 准备多仓状态
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

    def test_short_atr_take_profit(self):
        """测试空头 ATR 止盈"""
        strat = MaStrategyCore()
        cfg = MACrossParams(
            atr_period=14,
            atr_take_profit_multiplier=3.0,
            take_profit_ratio=0.10,  # 设置较大的固定止盈，让ATR止盈先触发
        )

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        # 创建持有空仓的上下文，价格跌破ATR止盈线
        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(93.0, latest_dt)  # 从100跌到93，ATR=2，3*2=6，100-6=94，93<94触发
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值
        _set_indicator_value(feed, "5m", "sma", 99.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 100.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        # 准备空仓状态
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
        """测试空仓且无进场信号"""
        strat = MaStrategyCore()
        cfg = MACrossParams()

        # 准备数据
        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg, use_multi_period=True)

        latest_dt = datetime(2024, 1, 1, 12, 0, 0)
        latest_bar = _make_test_bar(100.0, latest_dt)
        feed.update_bar(latest_bar, "1m")
        feed.update_bar(latest_bar, "5m")
        feed.update_bar(latest_bar, "15m")

        # 设置指标值：不满足多空进场条件
        _set_indicator_value(feed, "5m", "sma", 100.0, -1, period=cfg.sma_short)
        _set_indicator_value(feed, "15m", "sma", 100.0, -1, period=cfg.sma_long)
        _set_indicator_value(feed, "1m", "macd", 0.0, -1, fast=12, slow=26, signal=9)
        _set_indicator_value(feed, "1m", "kdj", 50.0, -1, n=9, k_period=3, d_period=3)
        _set_indicator_value(feed, "15m", "atr", 2.0, -1, period=cfg.atr_period)

        reqs = strat.data_requirements(cfg)
        ctx = build_context(feed, reqs, latest_dt, latest_bar)

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == ""
