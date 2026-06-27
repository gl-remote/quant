"""测试 data_feed 模块。"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from strategies.core.indicators import IndicatorSpec, ema_func, kdj_func, sma_func
from strategies.core.types import Bar
from strategies.ma_strategy import MACrossParams, MaStrategyCore
from strategies.runtime.cache import clear_cache, get_cached_feed, set_cached_feed
from strategies.runtime.data_feed import DataFeed
from strategies.runtime.events import BigTradeEvent, Event
from strategies.runtime.period import PeriodDataView
from strategies.runtime.requirements import (
    DataRequirements,
    EventsRequirements,
    PeriodRequirements,
)
from strategies.runtime.serialization import dump_feed, load_feed


def generate_test_bars(num_bars: int = 100) -> list[Bar]:
    """生成测试用的 K 线数据"""
    bars = []
    base_time = datetime(2024, 1, 1, 9, 0, 0)
    base_price = 100.0

    for i in range(num_bars):
        dt = base_time - timedelta(minutes=num_bars - i - 1)
        # 简单的正弦曲线价格
        import math

        price = base_price + 10 * math.sin(i / 10)
        open_ = price + (i % 3 - 1) * 0.5
        high = price + 2.0
        low = price - 2.0
        close = price
        volume = 1000 + i * 10

        bars.append(
            Bar(
                symbol="TEST",
                datetime=dt,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )

    return bars


def bars_to_df(bars: list[Bar]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "datetime": pd.Timestamp(bar.datetime),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]
    ).set_index("datetime")


def build_deterministic_feed(
    requirements: DataRequirements,
    bars: list[Bar],
    symbol: str = "TEST_FEED",
) -> DataFeed:
    feed = DataFeed(symbol, requirements=requirements)
    feed.feed_history_df(bars_to_df(bars))
    return feed


def view_signature(view: PeriodDataView) -> tuple[tuple[datetime, float, float, float, float, float], ...]:
    rows = []
    for idx in range(view.length):
        bar = view.get_bar(idx)
        assert bar is not None
        rows.append((bar.datetime, bar.open, bar.high, bar.low, bar.close, bar.volume))
    return tuple(rows)


def make_linear_bars(symbol: str, start: datetime, count: int, step_minutes: int = 1) -> list[Bar]:
    return [
        Bar(
            symbol=symbol,
            datetime=start + timedelta(minutes=step_minutes * i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1000.0 + i,
        )
        for i in range(count)
    ]


def make_datafeed_requirements(
    periods: dict[str, int] | None = None,
    indicators: dict[str, list[IndicatorSpec]] | None = None,
) -> DataRequirements:
    return DataRequirements(
        periods={
            period: PeriodRequirements(lookback_bars=lookback) for period, lookback in (periods or {"1m": 10}).items()
        },
        indicators=indicators or {},
        events=EventsRequirements.no_events(),
    )


def test_base_period_repeated_query_is_deterministic():
    reqs = make_datafeed_requirements({"1m": 5})
    bars = make_linear_bars("TEST_DETERMINISTIC", datetime(2024, 1, 1, 9, 0), 12)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_DETERMINISTIC")
    current_time = bars[8].datetime

    first = feed.get_data("1m", current_time, lookback_bars=5)
    second = feed.get_data("1m", current_time, lookback_bars=5)

    assert first is not None
    assert second is not None
    assert view_signature(second) == view_signature(first)
    assert view_signature(second)[-1][0] == current_time


def test_base_period_query_order_does_not_change_past_view():
    reqs = make_datafeed_requirements({"1m": 5})
    bars = make_linear_bars("TEST_ORDER", datetime(2024, 1, 1, 9, 0), 12)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_ORDER")
    early_time = bars[5].datetime
    later_time = bars[10].datetime

    direct_early = view_signature(feed.get_data("1m", early_time, lookback_bars=5))  # type: ignore[arg-type]
    _ = feed.get_data("1m", later_time, lookback_bars=5)
    early_after_later = view_signature(feed.get_data("1m", early_time, lookback_bars=5))  # type: ignore[arg-type]

    assert early_after_later == direct_early
    assert early_after_later[-1][0] == early_time


def test_base_period_lookback_window_is_monotonic():
    reqs = make_datafeed_requirements({"1m": 10})
    bars = make_linear_bars("TEST_LOOKBACK", datetime(2024, 1, 1, 9, 0), 12)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_LOOKBACK")
    current_time = bars[9].datetime

    short = view_signature(feed.get_data("1m", current_time, lookback_bars=3))  # type: ignore[arg-type]
    long = view_signature(feed.get_data("1m", current_time, lookback_bars=7))  # type: ignore[arg-type]

    assert long[-len(short) :] == short


def test_high_period_forming_bar_never_uses_future_base_bars():
    reqs = make_datafeed_requirements({"5m": 5, "15m": 3})
    bars = make_linear_bars("TEST_NO_FUTURE", datetime(2024, 1, 1, 10, 0), 5, step_minutes=5)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_NO_FUTURE")

    view = feed.get_data("15m", bars[1].datetime, lookback_bars=3)

    assert view is not None
    assert view.length == 1
    forming = view.get_bar(-1)
    assert forming is not None
    assert forming.datetime == bars[0].datetime
    assert forming.open == bars[0].open
    assert forming.high == max(b.high for b in bars[:2])
    assert forming.low == min(b.low for b in bars[:2])
    assert forming.close == bars[1].close
    assert forming.volume == sum(b.volume for b in bars[:2])
    assert forming.close != bars[2].close


def test_build_context_repeated_query_preserves_indicator_values():
    reqs = make_datafeed_requirements(
        {"1m": 8},
        indicators={"1m": [IndicatorSpec(name="sma", params={"period": 3}, window=3, func=sma_func)]},
    )
    bars = make_linear_bars("TEST_CTX_REPEAT", datetime(2024, 1, 1, 9, 0), 12)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_CTX_REPEAT")

    first = feed.build_context(reqs, bars[9])
    second = feed.build_context(reqs, bars[9])

    assert view_signature(second.multi["1m"]) == view_signature(first.multi["1m"])
    assert second.multi["1m"].indicator("1m_sma_3", -1) == first.multi["1m"].indicator("1m_sma_3", -1)


def test_data_feed_cache_is_explicitly_isolated():
    clear_cache()
    feed = DataFeed("TEST_CACHE_ISOLATED")

    set_cached_feed("TEST_CACHE_ISOLATED", feed, "2024-01-01", "2024-01-31")
    assert get_cached_feed("TEST_CACHE_ISOLATED", "2024-01-01", "2024-01-31") is feed

    clear_cache()

    assert get_cached_feed("TEST_CACHE_ISOLATED", "2024-01-01", "2024-01-31") is None


def make_view(
    bars: list[Bar],
    current_time: datetime,
    lookback_bars: int | None = None,
    indicators: dict[str, list[float]] | None = None,
    events: list[Event] | None = None,
) -> "PeriodDataView":
    """构造测试用的 PeriodDataView（测试辅助函数）

    Args:
        bars: K线列表
        current_time: 视图截止时间
        lookback_bars: 往前多少根K线（None 表示全部）
        indicators: 指标数据，key 为指标名，value 为值列表（与 bars 对齐）
        events: 事件列表
    """
    import pandas as pd
    from strategies.runtime.period import PeriodData

    period_data = PeriodData("test")
    period_data.append_bars(bars)

    # 添加指标
    if indicators:
        for col_name, values in indicators.items():
            period_data.set_indicator_column(col_name, np.array(values, dtype=np.float64))

    # 构建事件DataFrame
    events_df = None
    if events:
        event_dicts = []
        for event in events:
            event_dicts.append(
                {
                    "datetime": pd.Timestamp(event.timestamp),
                    "type": event.type,
                    "symbol": event.symbol,
                    "reason": event.reason,
                    "period": event.period,
                    "data": event.data,
                }
            )
        events_df = pd.DataFrame(event_dicts)
        events_df = events_df.set_index("datetime")

    if lookback_bars is None:
        lookback_bars = len(bars)

    return period_data.get_data(current_time, lookback_bars, events_df)


def test_data_feed_basic():
    """测试 DataFeed 的基本功能"""
    feed = DataFeed("TEST")

    # 注册周期
    feed.register_period("1m")

    # 注册指标
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func))
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 10}, window=10, func=sma_func))

    # 生成测试数据
    bars = generate_test_bars(50)
    # 转换为 DataFrame 加载
    import pandas as pd

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

    # 获取数据视图
    latest_bar = bars[-1]
    view = feed.get_data("1m", latest_bar.datetime, lookback_bars=10)
    feed.calculate_indicators(view, "1m")

    assert view.period == "1m"
    assert view.length == 10
    assert view.close(-1) == latest_bar.close
    assert view.indicator("1m_sma_5", -1) is not None
    assert view.indicator("1m_sma_10", -1) is not None


def test_data_feed_cache():
    """测试全局 DataFeed 内存缓存"""
    feed = DataFeed("TEST2")

    clear_cache()
    # 未命中
    f1 = get_cached_feed("TEST2", "2024-01-01", "2024-12-31")
    assert f1 is None

    # set + get 命中
    set_cached_feed("TEST2", feed, "2024-01-01", "2024-12-31")
    f2 = get_cached_feed("TEST2", "2024-01-01", "2024-12-31")
    assert f2 is feed

    # 日期不匹配 → 失效
    f3 = get_cached_feed("TEST2", "2024-01-01", "2025-06-01")
    assert f3 is None

    clear_cache()


def test_build_context():
    """测试 build_context 函数"""
    feed = DataFeed("TEST3")
    feed.register_period("1m")
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func))
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 10}, window=10, func=sma_func))

    # 加载数据
    bars = generate_test_bars(30)
    # 转换为 DataFrame 加载
    import pandas as pd

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

    # 定义数据需求
    reqs = DataRequirements(
        periods={
            "1m": PeriodRequirements(lookback_bars=20),
        },
        indicators={
            "1m": [
                IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func),
                IndicatorSpec(name="sma", params={"period": 10}, window=10, func=sma_func),
            ],
        },
        events=EventsRequirements.no_events(),
    )

    # 构建上下文
    latest_bar = bars[-1]
    ctx = feed.build_context(reqs, latest_bar)

    assert ctx.symbol == "TEST3"
    assert "1m" in ctx.multi
    assert ctx.events == []
    assert ctx.multi["1m"].length == 20


def test_strategy_with_data_feed():
    """测试策略使用 DataFeed"""
    # 新架构策略不需要参数构造
    strategy = MaStrategyCore()
    cfg = MACrossParams(sma_short=5, sma_long=10)

    # 查看策略的数据需求
    reqs = strategy.data_requirements(cfg)
    assert strategy.name == "ma"
    assert strategy.VERSION
    assert reqs is not None
    assert reqs.periods
    assert reqs.indicators


def test_make_view():
    """测试 make_view 工具函数"""
    # 生成测试数据
    bars = generate_test_bars(20)
    latest_bar = bars[-1]

    # 1. 基础测试：指定 lookback_bars
    view = make_view(bars, latest_bar.datetime, lookback_bars=10)
    assert view.period == "test", f"Expected test, got {view.period}"
    assert view.length == 10, f"Expected 10 bars, got {view.length}"

    # 2. None = 全部 K 线
    view_all = make_view(bars, latest_bar.datetime, lookback_bars=None)
    assert view_all.length == len(bars), f"Expected {len(bars)} bars, got {view_all.length}"

    # 3. 带指标的视图
    closes = [bar.close for bar in bars]
    view_ind = make_view(
        bars,
        latest_bar.datetime,
        lookback_bars=10,
        indicators={"sma_5": closes, "sma_10": closes},
    )
    assert view_ind.indicator("sma_5", -1) is not None

    # 4. 带事件的视图
    test_events = [
        BigTradeEvent(
            timestamp=bars[5].datetime,
            type="big_trade",
            symbol="TEST",
            price=105.0,
            volume=1000,
            direction="buy",
        ),
        BigTradeEvent(
            timestamp=bars[10].datetime,
            type="big_trade",
            symbol="TEST",
            price=110.0,
            volume=2000,
            direction="sell",
        ),
    ]
    view_evt = make_view(
        bars,
        latest_bar.datetime,
        lookback_bars=15,
        events=test_events,
    )
    assert len(view_evt.get_events()) == len(test_events)

    # 5. 带指标 + 事件的视图
    view_full = make_view(
        bars,
        latest_bar.datetime,
        lookback_bars=20,
        indicators={"sma_5": closes},
        events=test_events,
    )
    assert view_full.indicator("sma_5", -1) is not None
    assert len(view_full.get_events()) > 0


def test_calculate_period_incremental():
    """测试 DataFeed 惰性计算（get_data 自动触发的指标计算）

    模拟实时模式：先加载历史 → feed_bar 逐根推送 → get_data 读取指标。

    验证项：
    1. 初始数据加载后指标可读
    2. 新 bar 推送后指标更新（通过 get_data 惰性计算）
    3. 同时间点的 get_data 结果一致
    """
    import math

    import pandas as pd

    feed = DataFeed("TEST_INC")
    feed.register_period("1m")
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func))
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 10}, window=10, func=sma_func))

    # 初始历史：30 根 K 线
    bars = generate_test_bars(30)
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

    # 初始指标（通过 get_data 惰性计算）
    view_initial = feed.get_data("1m", bars[-1].datetime, lookback_bars=30)
    feed.calculate_indicators(view_initial, "1m")
    sma_5_initial = view_initial.indicator("1m_sma_5", -1)
    sma_10_initial = view_initial.indicator("1m_sma_10", -1)
    assert sma_5_initial is not None and not math.isnan(sma_5_initial)
    assert sma_10_initial is not None and not math.isnan(sma_10_initial)

    # --- 场景 1：feed_bar 1 根新 K 线后指标应更新 ---
    last_time = bars[-1].datetime
    new_bar = Bar(
        symbol="TEST",
        datetime=last_time + timedelta(minutes=1),
        open=105.0,
        high=106.0,
        low=104.0,
        close=105.5,
        volume=1500,
    )
    feed.get_period("1m").append_bar(new_bar)

    # 通过 get_data 读取指标（惰性计算）
    view_after = feed.get_data("1m", new_bar.datetime, lookback_bars=30)
    feed.calculate_indicators(view_after, "1m")
    sma_5_after = view_after.indicator("1m_sma_5", -1)
    sma_10_after = view_after.indicator("1m_sma_10", -1)
    assert sma_5_after is not None and not math.isnan(sma_5_after)
    assert sma_10_after is not None and not math.isnan(sma_10_after)

    # 同时间点两次 get_data 结果应一致
    view_after2 = feed.get_data("1m", new_bar.datetime, lookback_bars=30)
    feed.calculate_indicators(view_after2, "1m")
    assert abs(sma_5_after - view_after2.indicator("1m_sma_5", -1)) < 1e-9, "同时间点 get_data 结果应一致"
    assert abs(sma_10_after - view_after2.indicator("1m_sma_10", -1)) < 1e-9, "同时间点 get_data 结果应一致"

    # --- 场景 2：无新 K 线时多次 get_data 结果应一致 ---
    view_repeat = feed.get_data("1m", new_bar.datetime, lookback_bars=30)
    feed.calculate_indicators(view_repeat, "1m")
    assert abs(view_repeat.indicator("1m_sma_5", -1) - sma_5_after) < 1e-9, "无新数据时结果应一致"


def test_tqsdk_path_simulation():
    """模拟 tqsdk 实时链路：feed_bar 逐根推送 → get_data 惰性计算指标

    test/live 命令的核心数据流程，保证 tqsdk 路径与回测路径一致。
    """
    import math

    import pandas as pd

    feed = DataFeed("TQSDK_SIM")
    feed.register_period("1m")
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func))
    feed.register_indicator("1m", IndicatorSpec(name="ema", params={"period": 12}, window=12, func=ema_func))

    # --- 阶段 1：加载初始历史数据 ---
    bars = generate_test_bars(40)
    df = pd.DataFrame(
        [
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
    )
    df.set_index("datetime", inplace=True)
    feed.load_history_df("1m", df)

    # 初始指标（通过 get_data 惰性计算）
    view_init = feed.get_data("1m", bars[-1].datetime, lookback_bars=40)
    feed.calculate_indicators(view_init, "1m")
    init_sma_5 = view_init.indicator("1m_sma_5", -1)
    init_ema_12 = view_init.indicator("1m_ema_12", -1)
    assert init_sma_5 is not None and not math.isnan(init_sma_5)
    assert init_ema_12 is not None and not math.isnan(init_ema_12)

    # --- 阶段 2：模拟 10 轮实时推送（feed_bar 逐根推送） ---
    last_ts = bars[-1].datetime
    live_prices = [100 + i * 0.3 for i in range(10)]
    for i, price in enumerate(live_prices):
        new_bar = Bar(
            symbol="TQSDK_SIM",
            datetime=last_ts + timedelta(minutes=i + 1),
            open=price,
            high=price + 1,
            low=price - 1,
            close=price + 0.2,
            volume=1000 + i * 50,
        )
        feed.get_period("1m").append_bar(new_bar)

    # 循环结束后通过 get_data 读取指标
    final_view = feed.get_data("1m", last_ts + timedelta(minutes=10), lookback_bars=50)
    feed.calculate_indicators(final_view, "1m")
    final_sma_5 = final_view.indicator("1m_sma_5", -1)
    final_ema_12 = final_view.indicator("1m_ema_12", -1)

    # --- 阶段 3：同时间点结果一致性验证 ---
    final_view2 = feed.get_data("1m", last_ts + timedelta(minutes=10), lookback_bars=50)
    feed.calculate_indicators(final_view2, "1m")
    assert abs(final_view2.indicator("1m_sma_5", -1) - final_sma_5) < 1e-9
    assert abs(final_view2.indicator("1m_ema_12", -1) - final_ema_12) < 1e-9


def test_multi_period_consistency():
    """多周期场景：feed_bar 逐根写入 → get_data 惰性计算指标

    验证 tgsk 路径下的多周期行为：
    - 主周期 (1m)：每轮 feed_bar → get_data 指标值更新
    - 非主周期 (5m/15m)：仅历史数据，通过 get_data 惰性计算
    """
    import math

    feed = DataFeed("MULTI_PERIOD")
    for period in ("1m", "5m", "15m"):
        feed.register_period(period)
        feed.register_indicator(period, IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func))

    # 初始加载：1m=50 根，5m=30 根，15m=20 根
    import pandas as pd

    loaded_bars: dict[str, list[Bar]] = {}
    for period, n in [("1m", 50), ("5m", 30), ("15m", 20)]:
        bars = generate_test_bars(n)
        loaded_bars[period] = bars
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
        feed.load_history_df(period, df)

    # 记录初始值（通过 get_data）
    initial_values = {}
    for period in ("1m", "5m", "15m"):
        view = feed.get_data(period, loaded_bars[period][-1].datetime, lookback_bars=20)
        feed.calculate_indicators(view, period)
        initial_values[period] = view.indicator(f"{period}_sma_5", -1)

    # 只对主周期 (1m) 做 5 轮实时推送
    last_time = loaded_bars["1m"][-1].datetime
    for i in range(5):
        feed.get_period("1m").append_bar(
            Bar(
                symbol="MULTI_PERIOD",
                datetime=last_time + timedelta(minutes=i + 1),
                open=100 + i,
                high=101 + i,
                low=99 + i,
                close=100.5 + i,
                volume=1000,
            )
        )

    # 断言：主周期更新了；非主周期未更新（但读历史值应该仍能拿到）
    main_view = feed.get_data("1m", last_time + timedelta(minutes=5), lookback_bars=55)
    feed.calculate_indicators(main_view, "1m")
    main_after = main_view.indicator("1m_sma_5", -1)
    assert main_after != initial_values["1m"], "主周期指标应随新 K 线更新"

    # 非主周期：值仍然可读，不应为 None/NaN
    for period in ("5m", "15m"):
        view = feed.get_data(period, loaded_bars[period][-1].datetime, lookback_bars=20)
        feed.calculate_indicators(view, period)
        val = view.indicator(f"{period}_sma_5", -1)
        assert val is not None and not math.isnan(val), f"{period} 指标值应存在（初始化阶段已计算）"
        assert abs(val - initial_values[period]) < 1e-9, f"{period} 指标在无新数据时不应变化"


def test_multi_period_feed_bar_aggregation():
    """测试 feed_bar → 多周期聚合链路（tqsdk/vnpy 实时路径）

    模拟实时流程：apply_requirements → 逐根 feed_bar → 自动聚合到高周期

    验证:
    - feed_bar 后各高周期 forming bar 存在
    - forming bar high 为近期正确的最高价
    - 第 6 根 1m bar 喂入后第 1 根 5m bar complete
    - build_context 拿到的 multi 包含所有周期
    """
    reqs = DataRequirements(
        periods={
            "1m": PeriodRequirements(lookback_bars=10),
            "5m": PeriodRequirements(lookback_bars=5),
            "15m": PeriodRequirements(lookback_bars=3),
        },
        indicators={},
        events=EventsRequirements.no_events(),
    )

    feed = DataFeed("TEST_AGG", requirements=reqs)
    assert feed._base_period == "1m"

    # 构造 15 根 1m bar，时间步长 1 分钟
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    bars = [
        Bar(
            symbol="TEST_AGG",
            datetime=base_time + timedelta(minutes=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1000,
        )
        for i in range(15)
    ]

    # 逐根 feed_bar 前 5 根（聚合在 build_context 时现场做，PeriodData 中不再有 forming bar）
    for _i, bar in enumerate(bars[:5]):
        feed.feed_bar(bar)

    # build_context 验证：用 bars[4] (10:04) 触发聚合
    ctx = feed.build_context(reqs, bars[4])
    assert "1m" in ctx.multi
    assert "5m" in ctx.multi
    assert "15m" in ctx.multi

    view_5m = ctx.multi["5m"]
    assert view_5m is not None
    # 5m: bars[0..4] = 5 根 1m = 1 个完整 5m bar (10:00)
    assert view_5m.length == 1, f"5m view 应有 1 根 bar, 实际 {view_5m.length}"
    first_5m = view_5m.get_bar(0)
    assert first_5m is not None
    assert abs(first_5m.open - 100.0) < 0.001
    assert abs(first_5m.high - 105.0) < 0.001
    assert abs(first_5m.close - 104.5) < 0.001
    assert first_5m.datetime.strftime("%H:%M") == "10:00"

    # 继续喂入 bar 6~11 (10:05~10:10) → 第 2 个 5m 可聚合
    for i in range(5, 11):
        feed.feed_bar(bars[i])
    ctx2 = feed.build_context(reqs, bars[10])
    assert "5m" in ctx2.multi
    view_5m_2 = ctx2.multi["5m"]
    assert view_5m_2 is not None
    assert view_5m_2.length >= 2, f"11 根 bar 后 5m view 应有 >= 2 根 bar, 实际 {view_5m_2.length}"
    second_5m = view_5m_2.get_bar(1)
    assert second_5m is not None
    assert abs(second_5m.open - 105.0) < 0.001
    assert abs(second_5m.high - 110.0) < 0.001

    # build_context 验证 15m 存在（只有 11 根 1m，不够 15）
    ctx3 = feed.build_context(reqs, bars[10])
    assert "15m" in ctx3.multi
    view_15m = ctx3.multi["15m"]
    assert view_15m is not None
    assert view_15m.length == 1, f"15m view 应有 0 根 complete + 1 forming, 实际 {view_15m.length}"


def test_feed_bar_with_indicator_recalc():
    """测试 feed_bar 后高周期指标自动重算

    feed_bar → _step_aggregation → forming bar 更新 → 5m 指标重算
    """
    import pandas as pd

    reqs = DataRequirements(
        periods={
            "1m": PeriodRequirements(lookback_bars=10),
            "5m": PeriodRequirements(lookback_bars=5),
        },
        indicators={
            "5m": [
                IndicatorSpec(name="sma", params={"period": 3}, window=3, func=sma_func),
            ],
            "1m": [
                IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func),
            ],
        },
        events=EventsRequirements.no_events(),
    )

    feed = DataFeed("TEST_IND_RECALC", requirements=reqs)

    base_time = datetime(2024, 6, 1, 9, 0, 0)
    bars = [
        Bar(
            symbol="TEST_IND_RECALC",
            datetime=base_time + timedelta(minutes=i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000,
        )
        for i in range(16)
    ]

    # feed_history_df 加载历史 → 逐根 feed_bar
    df_data = [
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
    df = pd.DataFrame(df_data).set_index("datetime")
    feed.feed_history_df(df)

    # 逐根 feed_bar (只喂新的 bar，已加载的历史不应重复 feed)
    period_5m = feed.get_period("5m")
    assert period_5m is not None

    # 构造新的实时 bar（时间在历史之后）
    live_base = datetime(2024, 6, 1, 9, 16, 0)
    live_bars = [
        Bar(
            symbol="TEST_IND_RECALC",
            datetime=live_base + timedelta(minutes=i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000,
        )
        for i in range(16)
    ]

    for i in range(16):
        feed.feed_bar(live_bars[i])

    # 16 根 1m = 3 个完整 5m + 1 forming
    # 聚合改为 build_context 时现场做，PeriodData 中 5m 周期没有数据
    # 通过 build_context 验证 5m 视图正确
    ctx = feed.build_context(reqs, live_bars[-1])
    assert "1m" in ctx.multi
    assert "5m" in ctx.multi
    view_5m = ctx.multi["5m"]
    assert view_5m is not None
    assert view_5m.length >= 3, f"16 根 bar 后 5m view 应有 >= 3 根 bar, 实际 {view_5m.length}"
    sma_val = view_5m.indicator("5m_sma_3", -1)
    assert sma_val is not None


def test_indicator_history_uses_view_cache_without_dump_indicators():
    reqs = make_datafeed_requirements(
        {"1m": 2},
        indicators={"1m": [IndicatorSpec(name="sma", params={"period": 3}, window=3, func=sma_func)]},
    )
    bars = make_linear_bars("TEST_IND_HISTORY", datetime(2024, 1, 1, 9, 0), 10)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_IND_HISTORY")

    ctx1 = feed.build_context(reqs, bars[7])
    ctx2 = feed.build_context(reqs, bars[8])
    view = ctx2.multi["1m"]

    latest = view.indicator("1m_sma_3", -1)
    previous = view.indicator("1m_sma_3", -2)
    history = view.indicator_history("1m_sma_3", 2)

    assert latest is not None and not np.isnan(latest)
    assert previous is not None and not np.isnan(previous)
    assert history == [previous, latest]
    assert previous == ctx1.multi["1m"].indicator("1m_sma_3", -1)
    assert "1m_sma_3" not in feed.get_period("1m").data.columns  # type: ignore[union-attr]


def test_indicator_history_prefers_view_cache_when_persisted_column_changes():
    reqs = make_datafeed_requirements(
        {"1m": 2},
        indicators={"1m": [IndicatorSpec(name="sma", params={"period": 3}, window=3, func=sma_func)]},
    )
    bars = make_linear_bars("TEST_IND_HISTORY_PERSIST", datetime(2024, 1, 1, 9, 0), 10)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_IND_HISTORY_PERSIST")
    feed.dump_indicators = True

    ctx = feed.build_context(reqs, bars[7])
    view = ctx.multi["1m"]
    previous = view.indicator("1m_sma_3", -2)
    latest = view.indicator("1m_sma_3", -1)
    assert previous is not None and latest is not None

    period = feed.get_period("1m")
    assert period is not None
    calculation_index = view.to_calculation_df().index
    period.data.loc[calculation_index[-2:], "1m_sma_3"] = [999.0, 1000.0]

    history = view.indicator_history("1m_sma_3", 2)
    copied = view.indicator_series("1m_sma_3", 2)
    copied.iloc[-1] = 1000.0

    assert view.indicator("1m_sma_3", -2) == previous
    assert view.indicator("1m_sma_3", -1) == latest
    assert history == [previous, latest]
    assert view.indicator("1m_sma_3", -1) != copied.iloc[-1]


def test_indicator_history_falls_back_to_persisted_column_without_view_cache():
    reqs = make_datafeed_requirements(
        {"1m": 2},
        indicators={"1m": [IndicatorSpec(name="sma", params={"period": 3}, window=3, func=sma_func)]},
    )
    bars = make_linear_bars("TEST_IND_HISTORY_FALLBACK", datetime(2024, 1, 1, 9, 0), 10)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_IND_HISTORY_FALLBACK")
    feed.dump_indicators = True
    ctx = feed.build_context(reqs, bars[7])
    expected_history = ctx.multi["1m"].indicator_history("1m_sma_3", 2)

    view = feed.get_data("1m", bars[7].datetime, lookback_bars=4)
    assert view is not None
    fallback_history = view.indicator_history("1m_sma_3", 2)

    assert fallback_history == expected_history
    assert view.indicator_series("1m_sma_3", 2).tolist() == expected_history
    assert view.indicator("1m_sma_3", -2) == expected_history[0]
    assert view.indicator("1m_sma_3", -1) == expected_history[1]


def test_indicator_series_and_history_bars_boundaries():
    reqs = make_datafeed_requirements(
        {"1m": 2},
        indicators={"1m": [IndicatorSpec(name="sma", params={"period": 3}, window=3, func=sma_func)]},
    )
    bars = make_linear_bars("TEST_IND_HISTORY_BOUNDS", datetime(2024, 1, 1, 9, 0), 6)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_IND_HISTORY_BOUNDS")
    view = feed.build_context(reqs, bars[-1]).multi["1m"]

    with pytest.raises(ValueError, match="bars must be positive"):
        view.indicator_series("1m_sma_3", 0)
    with pytest.raises(ValueError, match="bars must be positive"):
        view.indicator_history("1m_sma_3", -1)

    full_history = view.indicator_history("1m_sma_3", 99)
    full_series = view.indicator_series("1m_sma_3")
    assert len(full_history) == view.length
    assert np.allclose(full_history, full_series.to_numpy(), equal_nan=True)


def test_period_indicator_lookback_uses_largest_int_window_and_ignores_non_int_windows():
    reqs = make_datafeed_requirements(
        {"1m": 5},
        indicators={
            "1m": [
                IndicatorSpec(name="sma", params={"period": 3}, window=3, func=sma_func),
                IndicatorSpec(name="ema", params={"period": 12}, window=12, func=ema_func),
                IndicatorSpec(name="sma", params={"period": "{sma_short}"}, window="{sma_short}", func=sma_func),
                IndicatorSpec(name="sma", params={"period": 7.5}, window=7.5, func=sma_func),
            ]
        },
    )
    feed = DataFeed("TEST_LOOKBACK_WINDOWS", requirements=reqs)

    assert feed._period_indicator_lookback("1m", 5) == 13

    template_only_reqs = make_datafeed_requirements(
        {"1m": 5},
        indicators={
            "1m": [
                IndicatorSpec(name="sma", params={"period": "{sma_short}"}, window="{sma_short}", func=sma_func),
                IndicatorSpec(name="sma", params={"period": 7.5}, window=7.5, func=sma_func),
            ]
        },
    )
    template_only_feed = DataFeed("TEST_LOOKBACK_TEMPLATE", requirements=template_only_reqs)

    assert template_only_feed._period_indicator_lookback("1m", 5) == 5


def test_get_data_rejects_non_positive_lookback_bars():
    reqs = make_datafeed_requirements({"1m": 5})
    bars = make_linear_bars("TEST_LOOKBACK_BOUNDS", datetime(2024, 1, 1, 9, 0), 3)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_LOOKBACK_BOUNDS")

    with pytest.raises(ValueError, match="lookback_bars must be positive"):
        feed.get_data("1m", bars[-1].datetime, lookback_bars=0)
    with pytest.raises(ValueError, match="lookback_bars must be positive"):
        feed.get_data("1m", bars[-1].datetime, lookback_bars=-1)


def test_indicator_window_expands_view_for_kdj():
    reqs = make_datafeed_requirements(
        {"1m": 2},
        indicators={
            "1m": [
                IndicatorSpec(
                    name="kdj",
                    params={"n": 9, "k_period": 3, "d_period": 3},
                    window=20,
                    func=kdj_func,
                )
            ]
        },
    )
    bars = make_linear_bars("TEST_KDJ_WARMUP", datetime(2024, 1, 1, 9, 0), 25)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_KDJ_WARMUP")

    ctx = feed.build_context(reqs, bars[-1])
    view = ctx.multi["1m"]

    assert view.length == 21
    latest = view.indicator("1m_kdj_3_3_9", -1)
    assert latest is not None and not np.isnan(latest)


def test_high_period_indicator_history_uses_forming_bar_without_future_data():
    reqs = make_datafeed_requirements(
        {"5m": 5, "15m": 2},
        indicators={"15m": [IndicatorSpec(name="sma", params={"period": 2}, window=2, func=sma_func)]},
    )
    bars = make_linear_bars("TEST_HIGH_IND_HISTORY", datetime(2024, 1, 1, 10, 0), 5, step_minutes=5)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_HIGH_IND_HISTORY")

    ctx = feed.build_context(reqs, bars[4])
    view = ctx.multi["15m"]

    assert view.length == 2
    latest = view.indicator("15m_sma_2", -1)
    history = view.indicator_history("15m_sma_2", 2)
    expected = (bars[2].close + bars[4].close) / 2

    assert latest == expected
    assert history[-1] == expected


def test_high_period_indicator_falls_back_to_base_persisted_column_without_view_cache():
    reqs = make_datafeed_requirements(
        {"5m": 5, "15m": 2},
        indicators={"15m": [IndicatorSpec(name="sma", params={"period": 2}, window=2, func=sma_func)]},
    )
    bars = make_linear_bars("TEST_HIGH_IND_FALLBACK", datetime(2024, 1, 1, 10, 0), 5, step_minutes=5)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_HIGH_IND_FALLBACK")
    feed.dump_indicators = True

    cached_view = feed.build_context(reqs, bars[4]).multi["15m"]
    expected_history = cached_view.indicator_history("15m_sma_2", 2)
    fallback_view = feed.get_data("15m", bars[4].datetime, lookback_bars=2)
    assert fallback_view is not None

    fallback_history = fallback_view.indicator_history("15m_sma_2", 2)

    assert np.allclose(fallback_history, expected_history, equal_nan=True)
    assert fallback_view.indicator("15m_sma_2", -1) == expected_history[-1]


def test_load_feed_uses_persisted_indicator_columns_without_recalculation(tmp_path):
    pytest.importorskip("pyarrow")
    reqs = make_datafeed_requirements(
        {"1m": 2},
        indicators={"1m": [IndicatorSpec(name="sma", params={"period": 3}, window=3, func=sma_func)]},
    )
    bars = make_linear_bars("TEST_SERIALIZED_IND", datetime(2024, 1, 1, 9, 0), 10)
    feed = build_deterministic_feed(reqs, bars, symbol="TEST_SERIALIZED_IND")
    feed.dump_indicators = True
    expected_history = feed.build_context(reqs, bars[7]).multi["1m"].indicator_history("1m_sma_3", 2)

    feeds_dir = tmp_path / "feeds"
    dump_feed(feed, str(feeds_dir))
    loaded = load_feed(str(feeds_dir))
    loaded_view = loaded.get_data("1m", bars[7].datetime, lookback_bars=2)
    assert loaded_view is not None

    assert loaded.get_registered_indicators("1m")[0].func is None
    assert loaded_view.indicator_history("1m_sma_3", 2) == expected_history
    assert loaded_view.indicator("1m_sma_3", -1) == expected_history[-1]


def test_data_feed_create_factory():
    """测试 DataFeed.create() 工厂方法（mock 数据库层）

    覆盖：全量构造、build_context 正常、内存缓存命中
    """
    import unittest.mock as mock

    import pandas as pd

    base_time = datetime(2024, 1, 1, 10, 0, 0)
    # DataFeed.create 需要 data_manager.load_kline 返回索引为 datetime 的 DataFrame
    kline_df = pd.DataFrame(
        {
            "datetime": [pd.Timestamp(base_time + timedelta(minutes=i)) for i in range(50)],
            "open": [100.0 + i for i in range(50)],
            "high": [101.0 + i for i in range(50)],
            "low": [99.0 + i for i in range(50)],
            "close": [100.5 + i for i in range(50)],
            "volume": [1000 for _ in range(50)],
        }
    ).set_index("datetime")

    reqs = DataRequirements(
        periods={
            "1m": PeriodRequirements(lookback_bars=10),
            "5m": PeriodRequirements(lookback_bars=5),
        },
        indicators={
            "1m": [
                IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func),
            ],
        },
        events=EventsRequirements.no_events(),
    )

    from strategies.runtime import cache as cache_module

    cache_module.clear_cache()

    # 场景 1：全量构造
    with mock.patch("data.manager.DataManager") as mock_dm:
        instance = mock_dm.return_value
        instance.load_kline.return_value = [("TEST", kline_df, "1m")]

        feed = DataFeed.create("TEST_CREATE", reqs)

        assert feed._base_period == "1m"
        period_1m = feed.get_period("1m")
        assert period_1m is not None and period_1m.length == 50
        # 指标改为通过 build_context 惰性计算
        bar = Bar(
            symbol="TEST_CREATE",
            datetime=base_time + timedelta(minutes=49),
            open=149.0,
            high=150.0,
            low=148.0,
            close=149.5,
            volume=1000,
        )
        ctx = feed.build_context(reqs, bar)
        sma_val = ctx.multi["1m"].indicator("1m_sma_5", -1)
        assert sma_val is not None

    # 场景 2：DataFeed.create() 返回的 DataFeed 能正常 build_context
    with mock.patch("data.manager.DataManager") as mock_dm:
        instance = mock_dm.return_value
        instance.load_kline.return_value = [("TEST", kline_df, "1m")]

        feed = DataFeed.create("TEST_CREATE2", reqs)
        bar = Bar(
            symbol="TEST_CREATE2",
            datetime=base_time + timedelta(minutes=49),
            open=149.0,
            high=150.0,
            low=148.0,
            close=149.5,
            volume=1000,
        )
        ctx = feed.build_context(reqs, bar)
        assert "1m" in ctx.multi
        assert "5m" in ctx.multi

    # 场景 3：内存缓存命中 → 零 I/O
    with mock.patch("data.manager.DataManager") as mock_dm:
        instance = mock_dm.return_value
        instance.load_kline.return_value = [("TEST", kline_df, "1m")]

        feed1 = DataFeed.create("TEST_CACHE", reqs)
        feed2 = DataFeed.create("TEST_CACHE", reqs)
        assert feed2 is feed1, "缓存命中应返回同一对象"
    cache_module.clear_cache()


def test_aggregate_period_semantic():
    """测试高周期聚合语义：15m@10:00 = 5m[10:00, 10:05, 10:10]

    验证语义约束（用户确定的定义）：
    - 10:00 → 15m 新周期开始，有 forming bar
    - 10:05 → forming bar 更新（含 2 根 5m bar）
    - 10:10 → 集齐 3 根 5m bar，15m@10:00 定型为完整 bar 写入 PeriodData
    - 10:15 → 新周期 15m@10:15 有新的 forming bar
    """
    reqs = DataRequirements(
        periods={
            "5m": PeriodRequirements(lookback_bars=5),
            "15m": PeriodRequirements(lookback_bars=3),
        },
        indicators={},
        events=EventsRequirements.no_events(),
    )

    feed = DataFeed("TEST_15M_SEMANTIC", requirements=reqs)
    assert feed._base_period == "5m"

    base_time = datetime(2024, 1, 1, 10, 0, 0)

    # ── 10:00 — 第 1 根 5m bar，15m@10:00 周期开始 ──
    bar_00 = Bar(
        symbol="TEST_15M_SEMANTIC",
        datetime=base_time,
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1000,
    )
    feed.feed_bar(bar_00)
    ctx = feed.build_context(reqs, bar_00)
    view_15m = ctx.multi["15m"]
    assert view_15m is not None
    assert view_15m.length == 1, f"10:00 应有 1 根(forming), 实际 {view_15m.length}"
    bar_10_00 = view_15m.get_bar(0)
    assert bar_10_00 is not None
    assert abs(bar_10_00.open - 100.0) < 0.001
    assert abs(bar_10_00.high - 101.0) < 0.001

    # ── 10:05 — 第 2 根 5m bar，forming bar 更新 ──
    bar_05 = Bar(
        symbol="TEST_15M_SEMANTIC",
        datetime=base_time + timedelta(minutes=5),
        open=101,
        high=103,
        low=100,
        close=102,
        volume=1000,
    )
    feed.feed_bar(bar_05)
    ctx2 = feed.build_context(reqs, bar_05)
    view_15m = ctx2.multi["15m"]
    assert view_15m is not None
    assert view_15m.length == 1, f"10:05 应有 1 根(forming), 实际 {view_15m.length}"
    bar_10_05 = view_15m.get_bar(0)
    assert bar_10_05 is not None
    assert abs(bar_10_05.open - 100.0) < 0.001  # open 始终是第一根 5m bar 的 open
    assert abs(bar_10_05.high - 103.0) < 0.001  # high 已包含 101→103
    assert abs(bar_10_05.close - 102.0) < 0.001  # close 是最后一根 5m bar

    # ── 10:10 — 第 3 根 5m bar，15m@10:00 集齐定型 ──
    bar_10 = Bar(
        symbol="TEST_15M_SEMANTIC",
        datetime=base_time + timedelta(minutes=10),
        open=102,
        high=105,
        low=101,
        close=104,
        volume=1000,
    )
    feed.feed_bar(bar_10)
    ctx3 = feed.build_context(reqs, bar_10)
    view_15m = ctx3.multi["15m"]
    assert view_15m is not None
    # 15m@10:00 已定型为完整 bar，当前时间 10:10 == 10:10 所在周期边界(10:00)
    # 15m@10:00 完整后应不再有 forming bar（当前周期已集齐/已定型）
    assert view_15m.length == 1, f"10:10 应有 1 根完整 bar, 实际 {view_15m.length}"
    complete = view_15m.get_bar(0)
    assert complete is not None
    assert complete.datetime.strftime("%H:%M") == "10:00"
    assert abs(complete.open - 100.0) < 0.001
    assert abs(complete.high - 105.0) < 0.001
    assert abs(complete.low - 99.0) < 0.001
    assert abs(complete.close - 104.0) < 0.001

    # ── 10:15 — 新 5m bar 进入 15m@10:15 周期 ──
    bar_15 = Bar(
        symbol="TEST_15M_SEMANTIC",
        datetime=base_time + timedelta(minutes=15),
        open=105,
        high=106,
        low=104,
        close=105,
        volume=1000,
    )
    feed.feed_bar(bar_15)
    ctx4 = feed.build_context(reqs, bar_15)
    view_15m = ctx4.multi["15m"]
    assert view_15m is not None
    # 1 根完整(10:00) + 1 forming(10:15)
    assert view_15m.length == 2, f"10:15 应有 2 根(1 complete + 1 forming), 实际 {view_15m.length}"
    bar_0 = view_15m.get_bar(0)
    assert bar_0 is not None
    assert bar_0.datetime.strftime("%H:%M") == "10:00"  # 完整 bar
    forming = view_15m.get_bar(-1)
    assert forming is not None
    assert forming.datetime.strftime("%H:%M") == "10:15"  # 新 forming
    assert abs(forming.open - 105.0) < 0.001


def test_aggregate_with_existing_data():
    """测试回测场景：高周期 PeriodData 预载了全部未来 bar 时，视图只取已可见的完整 bar

    回测时 15m PeriodData 一开始就持有所有未来 K 线。视图必须按可见性
    语义切片：15m@T 须等 current_time >= T+(15m-5m)=T+10m 才可见，
    不能因为 PeriodData 里有未来数据就提前看到。
    """
    reqs = DataRequirements(
        periods={
            "5m": PeriodRequirements(lookback_bars=5),
            "15m": PeriodRequirements(lookback_bars=3),
        },
        indicators={},
        events=EventsRequirements.no_events(),
    )

    feed = DataFeed("TEST_PRELOAD", requirements=reqs)

    # 预载全部未来 15m bar：10:00、10:15、10:30（值用 200+，便于和实时 base 区分）
    import pandas as pd

    times = [pd.Timestamp(datetime(2024, 1, 1, 10, 0, 0)) + timedelta(minutes=15 * i) for i in range(3)]
    df = pd.DataFrame(
        {
            "open": [200.0, 210.0, 220.0],
            "high": [205.0, 215.0, 225.0],
            "low": [199.0, 209.0, 219.0],
            "close": [204.0, 214.0, 224.0],
            "volume": [3000, 3000, 3000],
        },
        index=pd.Index(times, name="datetime"),
    )
    feed.get_period("15m").load_df(df, replace=True)  # type: ignore[union-attr]

    # 同时喂入 base 5m 数据（值 100+，与预载的 200+ 区分），让 base_df 推进
    for i in range(7):  # 10:00 ~ 10:30
        feed.feed_bar(
            Bar(
                symbol="TEST_PRELOAD",
                datetime=datetime(2024, 1, 1, 10, 0, 0) + timedelta(minutes=5 * i),
                open=100 + i,
                high=105 + i,
                low=99 + i,
                close=104 + i,
                volume=1000,
            )
        )

    # current=10:05 → 完整 15m@10:00 不可见（窗口前推）；但 forming 15m@10:00 用实时 base 生成
    bar_05 = Bar(
        symbol="TEST_PRELOAD",
        datetime=datetime(2024, 1, 1, 10, 5, 0),
        open=101,
        high=106,
        low=100,
        close=105,
        volume=1000,
    )
    ctx = feed.build_context(reqs, bar_05)
    view_15m = ctx.multi["15m"]
    assert view_15m is not None
    last_bar = view_15m.get_bar(-1)
    assert last_bar is not None
    # 最新可见 bar 是 forming 15m@10:00，值来自实时 base（100+），不是预载的 200+
    assert last_bar.datetime == datetime(2024, 1, 1, 10, 0, 0), (
        f"10:05 最新可见应为 forming 15m@10:00, 实际 {last_bar.datetime}"
    )
    assert last_bar.open < 150, f"forming bar 应来自实时 base(100+), 实际 open={last_bar.open}"

    # current=10:10 → 15m@10:00 最后子bar(10:10)到达，完整 bar 转正可见
    bar_10 = Bar(
        symbol="TEST_PRELOAD",
        datetime=datetime(2024, 1, 1, 10, 10, 0),
        open=102,
        high=107,
        low=101,
        close=106,
        volume=1000,
    )
    ctx2 = feed.build_context(reqs, bar_10)
    view_15m = ctx2.multi["15m"]
    assert view_15m is not None
    last_bar = view_15m.get_bar(-1)
    assert last_bar is not None
    # 15m@10:00 完整可见（窗口 visible_time=10:00 命中），10:15/10:30 仍不可见
    assert last_bar.datetime == datetime(2024, 1, 1, 10, 0, 0), (
        f"10:10 最新可见应为 15m@10:00, 实际 {last_bar.datetime}"
    )
