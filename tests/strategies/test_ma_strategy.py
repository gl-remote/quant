"""MA 交叉策略集成测试 — 验证多空进场、止盈止损、ATR 止盈止损

覆盖:
  - State 构造
  - data_requirements（通用校验，不依赖具体周期/指标数量）
  - on_bar(state, ctx) 纯决策
  - 多空进场
  - 固定比例止盈止损（多空）
  - ATR 止盈止损（多空）
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
from strategies.core.indicators import IndicatorSpec, generate_indicator_column_name
from strategies.core.types import Bar, StrategyPosition
from strategies.ma_strategy import MACrossParams, MaStrategyCore
from strategies.runtime.data_feed import DataFeed
from strategies.runtime.requirements import BarContext, DataRequirements

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


def _prepare_test_data(bars: list[Bar], config: MACrossParams) -> tuple[DataFeed, DataRequirements]:
    """准备 DataFeed 和 DataRequirements。

    不预设具体周期/指标内容，完全由策略的 data_requirements 决定。
    """
    feed = DataFeed("TEST")
    strat = MaStrategyCore()
    reqs = strat.data_requirements(config)
    assert reqs is not None

    feed.apply_requirements(reqs)

    # 测试数据是 1 分钟线，设置为基础周期，所有高周期自动从 1m 聚合
    feed.register_period("1m")
    feed._base_period = "1m"
    all_periods = set(feed._periods.keys())
    feed._aggregation_targets = [p for p in all_periods if p != "1m"]

    # 加载历史数据
    data = [
        {
            "datetime": pd.Timestamp(b.datetime),
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
    df = pd.DataFrame(data).set_index("datetime")
    feed.load_history_df("1m", df)

    return feed, reqs


def _get_indicator_specs(reqs: DataRequirements, indicator_name: str) -> list[tuple[str, IndicatorSpec]]:
    """从 DataRequirements 中提取指定名称的所有指标规格。

    Returns:
        [(period, IndicatorSpec), ...] 按周期名排序。
    """
    result = []
    for period, indicators in reqs.indicators.items():
        for ind in indicators:
            if ind.name == indicator_name:
                result.append((period, ind))
    result.sort(key=lambda x: x[0])
    return result


def _feed_all_periods(feed: DataFeed, reqs: DataRequirements, latest_bar: Bar) -> None:
    """将最新 bar 喂入所有声明的周期。

    先喂入基础周期（触发聚合到高周期），再将 bar 直接写入各高周期 DataFrame。
    不硬编码任何周期名，完全由 reqs 决定。
    """
    # 基础周期（1m）：触发 _step_aggregation
    if "1m" not in feed._periods:
        feed.register_period("1m")
    feed.update_bar(latest_bar, "1m")

    # 所有高周期：直接写入 DataFrame（与聚合形成的 bar 时间戳一致时，形成重复）
    for period in reqs.indicators:
        if period != "1m":
            feed.update_bar(latest_bar, period)


def _set_indicator_value(
    feed: DataFeed, timeframe: str, indicator_name: str, value: float, offset: int = 0, **kwargs
) -> None:
    """设置指标值（测试用）。

    通过 PeriodData._df 直接写入指标列，模拟指标计算结果。
    同时同步 forming bar 指标缓存，保证视图读取正确。
    """
    col_name = generate_indicator_column_name(indicator_name, kwargs)
    period_data = feed._periods[timeframe]
    df = period_data._df

    # 确保 df 有足够行数（向前填充，不改变最后一行的时间戳）
    if len(df) == 0:
        first_idx = pd.Timestamp(datetime.now())
        df.loc[first_idx] = {col: pd.NA for col in df.columns}
    while len(df) <= abs(offset):
        first_idx = df.index[0]
        new_idx = first_idx - pd.Timedelta(minutes=1)
        row_data = df.iloc[0].to_dict()
        df.loc[new_idx] = row_data
        df.sort_index(inplace=True)

    idx = df.index[offset] if offset >= 0 else df.index[offset]
    df.at[idx, col_name] = value

    # 同步 forming bar 指标缓存
    if period_data._forming_bar is not None:
        forming_time = pd.Timestamp(period_data._forming_bar.datetime)
        if forming_time == idx:
            period_data._forming_indicators[col_name] = value


def _create_entry_context(
    feed: DataFeed,
    config: MACrossParams,
    latest_price: float,
    is_long: bool,
) -> BarContext:
    """创建进场上下文（做多或做空条件满足）。

    从 reqs 动态发现指标所在的周期，不硬编码周期名。
    """
    reqs = MaStrategyCore().data_requirements(config)
    latest_dt = datetime(2024, 1, 12, 0, 0)
    latest_bar = _make_test_bar(latest_price, latest_dt)

    _feed_all_periods(feed, reqs, latest_bar)

    # --- 从 reqs 发现 SMA 周期分布 ---
    sma_specs = _get_indicator_specs(reqs, "sma")
    short_period = None
    long_period = None
    for period, spec in sma_specs:
        p = spec.params.get("period")
        if p == config.sma_short:
            short_period = period
        elif p == config.sma_long:
            long_period = period

    # 根据方向设置 SMA 值：做多 short > long，做空 short < long
    if is_long:
        if short_period:
            _set_indicator_value(feed, short_period, "sma", 100.0, -1, period=config.sma_short)
        if long_period:
            _set_indicator_value(feed, long_period, "sma", 99.0, -1, period=config.sma_long)
    else:
        if short_period:
            _set_indicator_value(feed, short_period, "sma", 99.0, -1, period=config.sma_short)
        if long_period:
            _set_indicator_value(feed, long_period, "sma", 100.0, -1, period=config.sma_long)

    # --- MACD/KDJ：从 reqs 提取指标参数，避免硬编码 ---
    macd_specs = _get_indicator_specs(reqs, "macd")
    kdj_specs = _get_indicator_specs(reqs, "kdj")
    atr_specs = _get_indicator_specs(reqs, "atr")

    macd_params = macd_specs[0][1].params if macd_specs else {"fast": 12, "slow": 26, "signal": 9}
    kdj_params = kdj_specs[0][1].params if kdj_specs else {"n": 9, "k_period": 3, "d_period": 3}
    atr_params = atr_specs[0][1].params if atr_specs else {"period": 14}

    macd_value = 0.1 if is_long else -0.1
    kdj_value = 15.0 if is_long else 85.0

    for period, _ in macd_specs:
        _set_indicator_value(feed, period, "macd", macd_value, -1, **macd_params)
    for period, _ in kdj_specs:
        _set_indicator_value(feed, period, "kdj", kdj_value, -1, **kdj_params)
    for period, _ in atr_specs:
        _set_indicator_value(feed, period, "atr", 2.0, -1, **atr_params)

    feed.calculate_all()
    return feed.build_context(reqs, latest_bar)


def _create_stop_or_tp_context(
    feed: DataFeed,
    config: MACrossParams,
    latest_price: float,
) -> BarContext:
    """创建止盈止损测试上下文。

    设置所有指标为中性值，不触发进场信号，让止损/止盈逻辑自行判断。
    完全从 reqs 动态发现周期和指标，不硬编码。
    """
    reqs = MaStrategyCore().data_requirements(config)
    latest_dt = datetime(2024, 1, 1, 12, 0, 0)
    latest_bar = _make_test_bar(latest_price, latest_dt)

    _feed_all_periods(feed, reqs, latest_bar)

    # 设置所有已注册指标的值为中性
    for indicator_name in ("sma", "macd", "kdj", "atr"):
        specs = _get_indicator_specs(reqs, indicator_name)
        if not specs:
            continue
        params = specs[0][1].params
        for period, spec in specs:
            p = spec.params.get("period")
            if p is not None:
                # SMA: 用 config 中的 period 参数
                if indicator_name == "sma":
                    if p == config.sma_short:
                        _set_indicator_value(feed, period, indicator_name, 100.0, -1, period=p)
                    elif p == config.sma_long:
                        _set_indicator_value(feed, period, indicator_name, 99.0, -1, period=p)
                else:
                    _set_indicator_value(feed, period, indicator_name, 2.0, -1, **params)
            else:
                # MACD/KDJ 等无 period 参数的指标
                neutral = 0.1 if indicator_name == "macd" else 50.0
                _set_indicator_value(feed, period, indicator_name, neutral, -1, **params)

    feed.calculate_all()
    return feed.build_context(reqs, latest_bar)


# --------------------------
# 基础测试
# --------------------------


class TestDataRequirements:
    """测试策略数据需求 — 不依赖具体的周期/指标数量和名称"""

    def test_returns_valid_requirements(self):
        """验证 data_requirements 返回有效的 DataRequirements 结构"""
        cfg = MACrossParams()
        reqs = MaStrategyCore().data_requirements(cfg)
        assert isinstance(reqs, DataRequirements)
        assert len(reqs.periods) > 0, "至少需要一个周期"
        assert len(reqs.indicators) > 0, "至少需要一个指标"

    def test_requirements_can_be_applied(self):
        """验证任意 DataRequirements 都能被 DataFeed 正确执行"""
        cfg = MACrossParams()
        reqs = MaStrategyCore().data_requirements(cfg)

        feed = DataFeed("TEST")
        feed.apply_requirements(reqs)
        feed.register_period("1m")
        feed._base_period = "1m"
        all_periods = set(feed._periods.keys())
        feed._aggregation_targets = [p for p in all_periods if p != "1m"]

        # 加载少量历史数据并喂入最新 bar
        bars = _generate_test_bars(50, start_dt=datetime(2024, 1, 1, 10, 0, 0))
        data = [
            {
                "datetime": pd.Timestamp(b.datetime),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ]
        df = pd.DataFrame(data).set_index("datetime")
        feed.load_history_df("1m", df)

        latest_bar = _make_test_bar(100.0, datetime(2024, 1, 1, 12, 0, 0))
        _feed_all_periods(feed, reqs, latest_bar)
        feed.calculate_all()

        ctx = feed.build_context(reqs, latest_bar)
        # 验证所有声明的周期都在 ctx.multi 中
        for period in reqs.periods:
            assert period in ctx.multi, f"周期 {period} 应在 ctx.multi 中"


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
        strat = MaStrategyCore()
        cfg = MACrossParams()

        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg)
        ctx = _create_entry_context(feed, cfg, 100.0, is_long=True)

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

        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg)
        ctx = _create_entry_context(feed, cfg, 100.0, is_long=False)

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
        strat = MaStrategyCore()
        cfg = MACrossParams()

        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg)
        ctx = _create_entry_context(feed, cfg, 100.0, is_long=True)

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


# --------------------------
# 固定比例止盈止损测试
# --------------------------


class TestMaStrategyFixedStopLoss:
    """测试固定比例止损（多空）"""

    def test_long_fixed_stop_loss(self):
        strat = MaStrategyCore()
        cfg = MACrossParams(stop_loss_ratio=0.03)

        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 96.0)  # 跌 4%，超过 3% 止损

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
        strat = MaStrategyCore()
        cfg = MACrossParams(stop_loss_ratio=0.03)

        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 104.0)  # 涨 4%，超过 3% 止损

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

        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 106.0)  # 涨 6%，超过 5% 止盈

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

        bars = _generate_test_bars(100)
        feed, _ = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 94.0)  # 跌 6%，超过 5% 止盈

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
        strat = MaStrategyCore()
        cfg = MACrossParams(
            atr_period=14,
            atr_stop_loss_multiplier=2.0,
            stop_loss_ratio=0.10,
        )

        bars = _generate_test_bars(100)
        feed, reqs = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 95.0)  # ATR=2, 2*2=4, 100-4=96, 95<96 触发

        # 覆盖 ATR 值以确保精确触发
        atr_specs = _get_indicator_specs(reqs, "atr")
        for period, spec in atr_specs:
            _set_indicator_value(feed, period, "atr", 2.0, -1, **spec.params)
        feed.calculate_all()
        ctx = feed.build_context(reqs, ctx.bar)

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
        strat = MaStrategyCore()
        cfg = MACrossParams(
            atr_period=14,
            atr_stop_loss_multiplier=2.0,
            stop_loss_ratio=0.10,
        )

        bars = _generate_test_bars(100)
        feed, reqs = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 105.0)  # ATR=2, 2*2=4, 100+4=104, 105>104 触发

        atr_specs = _get_indicator_specs(reqs, "atr")
        for period, spec in atr_specs:
            _set_indicator_value(feed, period, "atr", 2.0, -1, **spec.params)
        feed.calculate_all()
        ctx = feed.build_context(reqs, ctx.bar)

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
        strat = MaStrategyCore()
        cfg = MACrossParams(
            atr_period=14,
            atr_take_profit_multiplier=3.0,
            take_profit_ratio=0.10,
        )

        bars = _generate_test_bars(100)
        feed, reqs = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 107.0)  # ATR=2, 3*2=6, 100+6=106, 107>106 触发

        atr_specs = _get_indicator_specs(reqs, "atr")
        for period, spec in atr_specs:
            _set_indicator_value(feed, period, "atr", 2.0, -1, **spec.params)
        feed.calculate_all()
        ctx = feed.build_context(reqs, ctx.bar)

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
        strat = MaStrategyCore()
        cfg = MACrossParams(
            atr_period=14,
            atr_take_profit_multiplier=3.0,
            take_profit_ratio=0.10,
        )

        bars = _generate_test_bars(100)
        feed, reqs = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 93.0)  # ATR=2, 3*2=6, 100-6=94, 93<94 触发

        atr_specs = _get_indicator_specs(reqs, "atr")
        for period, spec in atr_specs:
            _set_indicator_value(feed, period, "atr", 2.0, -1, **spec.params)
        feed.calculate_all()
        ctx = feed.build_context(reqs, ctx.bar)

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

        bars = _generate_test_bars(100)
        feed, reqs = _prepare_test_data(bars, cfg)
        ctx = _create_stop_or_tp_context(feed, cfg, 100.0)

        state = State(
            symbol="TEST",
            period="1m",
            strategy_config=cfg,
            capital=100000.0,
            contract_size=10,
        )

        signal = strat.on_bar(state, ctx)
        assert signal.action == ""
