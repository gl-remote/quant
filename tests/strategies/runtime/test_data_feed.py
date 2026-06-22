"""测试 data_feed 模块

这个脚本演示了如何使用新的数据管理系统。
"""

from datetime import datetime, timedelta

import numpy as np

from strategies.core.indicators import IndicatorSpec, ema_func, sma_func
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


def generate_test_bars(num_bars: int = 100) -> list[Bar]:
    """生成测试用的 K 线数据"""
    bars = []
    now = datetime.now()
    base_price = 100.0

    for i in range(num_bars):
        dt = now - timedelta(minutes=num_bars - i - 1)
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
    print("=== 测试 DataFeed 基本功能 ===\n")

    # 创建 DataFeed
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

    print(f"周期: {view.period}")
    print(f"视图截止时间: {view.current_time}")
    print(f"视图包含 K 线数量: {view.length}")
    print(f"最新收盘价: {view.close(-1):.2f}")
    print(f"SMA(5): {view.indicator('1m_sma_5', -1):.2f}")
    print(f"SMA(10): {view.indicator('1m_sma_10', -1):.2f}")
    print()


def test_data_feed_cache():
    """测试全局 DataFeed 内存缓存"""
    print("=== 测试 DataFeed 内存缓存 ===\n")

    feed = DataFeed("TEST2")

    clear_cache()
    # 未命中
    f1 = get_cached_feed("TEST2", "2024-01-01", "2024-12-31")
    print(f"空缓存读取: {f1 is None}")

    # set + get 命中
    set_cached_feed("TEST2", feed, "2024-01-01", "2024-12-31")
    f2 = get_cached_feed("TEST2", "2024-01-01", "2024-12-31")
    print(f"缓存命中: {f2 is feed}")

    # 日期不匹配 → 失效
    f3 = get_cached_feed("TEST2", "2024-01-01", "2025-06-01")
    print(f"日期不匹配失效: {f3 is None}")

    clear_cache()
    print("缓存已清空\n")


def test_build_context():
    """测试 build_context 函数"""
    print("=== 测试 build_context 函数 ===\n")

    # 创建 DataFeed
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

    print(f"BarContext symbol: {ctx.symbol}")
    print(f"包含的周期: {list(ctx.multi.keys())}")
    print(f"事件数量: {len(ctx.events)}")
    print()


def test_strategy_with_data_feed():
    """测试策略使用 DataFeed"""
    print("=== 测试策略使用 DataFeed ===\n")

    # 新架构策略不需要参数构造
    strategy = MaStrategyCore()
    cfg = MACrossParams(sma_short=5, sma_long=10)

    print(f"策略名称: {strategy.name}")
    print(f"策略版本: {strategy.VERSION}")

    # 查看策略的数据需求
    reqs = strategy.data_requirements(cfg)
    if reqs:
        print(f"策略需求的周期: {list(reqs.periods.keys())}")
        for period, indicators in reqs.indicators.items():
            print(f"  {period} 周期指标: {[ind.name for ind in indicators]}")

    print()


def test_make_view():
    """测试 make_view 工具函数"""
    print("=== 测试 make_view 工具函数 ===\n")

    # 生成测试数据
    bars = generate_test_bars(20)
    latest_bar = bars[-1]

    # 1. 基础测试：指定 lookback_bars
    print("1. 基础视图（lookback_bars=10）")
    view = make_view(bars, latest_bar.datetime, lookback_bars=10)
    assert view.period == "test", f"Expected test, got {view.period}"
    assert view.length == 10, f"Expected 10 bars, got {view.length}"
    print(f"   视图包含 K 线数量: {view.length}")
    print(f"   最新收盘价: {view.close(-1):.2f}\n")

    # 2. None = 全部 K 线
    print("2. 全部 K 线视图（lookback_bars=None）")
    view_all = make_view(bars, latest_bar.datetime, lookback_bars=None)
    assert view_all.length == len(bars), f"Expected {len(bars)} bars, got {view_all.length}"
    print(f"   视图包含 K 线数量: {view_all.length}\n")

    # 3. 带指标的视图
    print("3. 带指标的视图")
    closes = [bar.close for bar in bars]
    view_ind = make_view(
        bars,
        latest_bar.datetime,
        lookback_bars=10,
        indicators={"sma_5": closes, "sma_10": closes},
    )
    assert view_ind.indicator("sma_5", -1) is not None
    print(f"   sma_5 最新值: {view_ind.indicator('sma_5', -1):.2f}")
    print(f"   sma_10 最新值: {view_ind.indicator('sma_10', -1):.2f}\n")

    # 4. 带事件的视图
    print("4. 带事件的视图")
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
    view_events = view_evt.get_events()
    print(f"   事件数量: {len(view_events)}")
    for evt in view_events:
        print(f"   - {evt.type} @ {evt.timestamp}: {evt.symbol}")
    print()

    # 5. 带指标 + 事件的视图
    print("5. 带指标 + 事件的视图")
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

    print("=== 测试惰性计算（get_data 自动指标计算）===\n")

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
    print(f"  初始历史: 30 根, 1m_sma_5={sma_5_initial:.4f}, 1m_sma_10={sma_10_initial:.4f}")
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
    print(f"  新增 K 线后: 1m_sma_5={sma_5_after:.4f}")
    print(f"               1m_sma_10={sma_10_after:.4f}")
    assert abs(sma_5_after - view_after2.indicator("1m_sma_5", -1)) < 1e-9, "同时间点 get_data 结果应一致"
    assert abs(sma_10_after - view_after2.indicator("1m_sma_10", -1)) < 1e-9, "同时间点 get_data 结果应一致"

    # --- 场景 2：无新 K 线时多次 get_data 结果应一致 ---
    view_repeat = feed.get_data("1m", new_bar.datetime, lookback_bars=30)
    feed.calculate_indicators(view_repeat, "1m")
    assert abs(view_repeat.indicator("1m_sma_5", -1) - sma_5_after) < 1e-9, "无新数据时结果应一致"

    print("  ✅ 惰性计算一致性验证通过\n")


def test_tqsdk_path_simulation():
    """模拟 tqsdk 实时链路：feed_bar 逐根推送 → get_data 惰性计算指标

    test/live 命令的核心数据流程，保证 tqsdk 路径与回测路径一致。
    """
    import math

    import pandas as pd

    print("=== 模拟 tqsdk 实时链路（惰性计算模式）===\n")

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
    print(f"  初始化完成: {len(df)} 根 K 线, 1m_sma_5={init_sma_5:.4f}, 1m_ema_12={init_ema_12:.4f}")
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
    print(f"  10 轮实时推送后: 1m_sma_5={final_sma_5:.4f}, 1m_ema_12={final_ema_12:.4f}")

    # --- 阶段 3：同时间点结果一致性验证 ---
    final_view2 = feed.get_data("1m", last_ts + timedelta(minutes=10), lookback_bars=50)
    feed.calculate_indicators(final_view2, "1m")
    assert abs(final_view2.indicator("1m_sma_5", -1) - final_sma_5) < 1e-9
    assert abs(final_view2.indicator("1m_ema_12", -1) - final_ema_12) < 1e-9
    print("  ✅ 10 轮实时推送后的惰性计算结果一致\n")


def test_multi_period_consistency():
    """多周期场景：feed_bar 逐根写入 → get_data 惰性计算指标

    验证 tgsk 路径下的多周期行为：
    - 主周期 (1m)：每轮 feed_bar → get_data 指标值更新
    - 非主周期 (5m/15m)：仅历史数据，通过 get_data 惰性计算
    """
    import math

    print("=== 多周期场景下主周期/非主周期一致性 ===\n")

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
        print(f"  初始 {period}: {period}_sma_5={initial_values[period]:.4f}")

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
    print(f"  主周期 1m 推送 5 根后: 1m_sma_5={main_after:.4f}（原值 {initial_values['1m']:.4f}）")

    # 非主周期：值仍然可读，不应为 None/NaN
    for period in ("5m", "15m"):
        view = feed.get_data(period, loaded_bars[period][-1].datetime, lookback_bars=20)
        feed.calculate_indicators(view, period)
        val = view.indicator(f"{period}_sma_5", -1)
        assert val is not None and not math.isnan(val), f"{period} 指标值应存在（初始化阶段已计算）"
        assert abs(val - initial_values[period]) < 1e-9, f"{period} 指标在无新数据时不应变化"
        print(f"  非主周期 {period}: {period}_sma_5={val:.4f}（与初始化一致）")

    print("  ✅ 多周期一致性验证通过\n")


def test_multi_period_feed_bar_aggregation():
    """测试 feed_bar → 多周期聚合链路（tqsdk/vnpy 实时路径）

    模拟实时流程：apply_requirements → 逐根 feed_bar → 自动聚合到高周期

    验证:
    - feed_bar 后各高周期 forming bar 存在
    - forming bar high 为近期正确的最高价
    - 第 6 根 1m bar 喂入后第 1 根 5m bar complete
    - build_context 拿到的 multi 包含所有周期
    """
    print("=== 测试 feed_bar → 多周期聚合链路 ===\n")

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
    print(f"  基础周期: {feed._base_period}")

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
    print("  前 5 根 1m bar 喂入完成")

    # build_context 验证：用 bars[4] (10:04) 触发聚合
    ctx = feed.build_context(reqs, bars[4])
    assert "1m" in ctx.multi
    assert "5m" in ctx.multi
    assert "15m" in ctx.multi
    print(f"  build_context multi: {list(ctx.multi.keys())} ✅")

    view_5m = ctx.multi["5m"]
    assert view_5m is not None
    # 5m: bars[0..4] = 5 根 1m = 1 个完整 5m bar (10:00)
    assert view_5m.length == 1, f"5m view 应有 1 根 bar, 实际 {view_5m.length}"
    first_5m = view_5m.get_bar(0)
    assert first_5m is not None
    print(f"  5m view first bar: open={first_5m.open}, high={first_5m.high}")
    assert abs(first_5m.open - 100.0) < 0.001
    assert abs(first_5m.high - 105.0) < 0.001
    assert abs(first_5m.close - 104.5) < 0.001
    assert first_5m.datetime.strftime("%H:%M") == "10:00"
    print("  5m bar OHLC 验证通过 ✅")

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
    print(f"  第 2 根 5m bar: open={second_5m.open}, high={second_5m.high} ✅")

    # build_context 验证 15m 存在（只有 11 根 1m，不够 15）
    ctx3 = feed.build_context(reqs, bars[10])
    assert "15m" in ctx3.multi
    view_15m = ctx3.multi["15m"]
    assert view_15m is not None
    assert view_15m.length == 1, f"15m view 应有 0 根 complete + 1 forming, 实际 {view_15m.length}"
    print("  15m view: 0 根 complete + 1 forming (正确) ✅")
    print()


def test_feed_bar_with_indicator_recalc():
    """测试 feed_bar 后高周期指标自动重算

    feed_bar → _step_aggregation → forming bar 更新 → 5m 指标重算
    """
    import pandas as pd

    print("=== 测试 feed_bar 后高周期指标自动重算 ===\n")

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
    print(f"  16 根 bar 后 5m 5m_sma_3: {sma_val}")
    print("  build_context 多周期聚合 + 指标计算验证通过 ✅")
    print()


def test_data_feed_create_factory():
    """测试 DataFeed.create() 工厂方法（mock 数据库层）

    覆盖：全量构造、build_context 正常、内存缓存命中
    """
    import unittest.mock as mock

    import pandas as pd

    print("=== 测试 DataFeed.create() 工厂方法 ===\n")

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
    print("1. 全量构造路径")
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
        print(f"  基础周期 1m: 50 根 K 线, 1m_sma_5={sma_val:.4f} ✅")

    # 场景 2：DataFeed.create() 返回的 DataFeed 能正常 build_context
    print("2. build_context 正常")
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
        print("  build_context 正常 ✅")

    # 场景 3：内存缓存命中 → 零 I/O
    print("3. 内存缓存命中")
    with mock.patch("data.manager.DataManager") as mock_dm:
        instance = mock_dm.return_value
        instance.load_kline.return_value = [("TEST", kline_df, "1m")]

        feed1 = DataFeed.create("TEST_CACHE", reqs)
        feed2 = DataFeed.create("TEST_CACHE", reqs)
        assert feed2 is feed1, "缓存命中应返回同一对象"
        print("  内存缓存命中 ✅")
    cache_module.clear_cache()
    print()


def test_aggregate_period_semantic():
    """测试高周期聚合语义：15m@10:00 = 5m[10:00, 10:05, 10:10]

    验证语义约束（用户确定的定义）：
    - 10:00 → 15m 新周期开始，有 forming bar
    - 10:05 → forming bar 更新（含 2 根 5m bar）
    - 10:10 → 集齐 3 根 5m bar，15m@10:00 定型为完整 bar 写入 PeriodData
    - 10:15 → 新周期 15m@10:15 有新的 forming bar
    """
    print("=== 测试高周期聚合语义：15m@10:00 = 5m[10:00, 10:05, 10:10] ===\n")

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
    print("  10:00 — forming bar (1 根 5m): open=100, high=101 ✅")

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
    print("  10:05 — forming bar (2 根 5m): open=100, high=103, close=102 ✅")

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
    print("  10:10 — 15m@10:00 定型为完整 bar: O=100 H=105 L=99 C=104 ✅")

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
    print("  10:15 — 1 根完整(10:00) + 1 forming(10:15) ✅")
    print()


def test_aggregate_with_existing_data():
    """测试回测场景：高周期 PeriodData 预载了全部未来 bar 时，视图只取已可见的完整 bar

    回测时 15m PeriodData 一开始就持有所有未来 K 线。视图必须按可见性
    语义切片：15m@T 须等 current_time >= T+(15m-5m)=T+10m 才可见，
    不能因为 PeriodData 里有未来数据就提前看到。
    """
    print("=== 测试高周期预载全部未来 bar 时的可见性 ===\n")

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
    print("  预载 15m PeriodData: 完整 bar @10:00/10:15/10:30 (值 200+) ✅")

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
    print("  10:05 — 完整 15m@10:00 不可见，forming 15m@10:00 用实时 base 顶替 ✅")

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
    print("  10:10 — 15m@10:00 完整 bar 转正可见，预载未来 bar(10:15/10:30) 不可见 ✅")
    print()


if __name__ == "__main__":
    print("开始测试数据管理系统...\n")

    test_data_feed_basic()
    test_data_feed_cache()
    test_build_context()
    test_strategy_with_data_feed()
    test_make_view()
    test_calculate_period_incremental()
    test_tqsdk_path_simulation()
    test_multi_period_consistency()
    test_multi_period_feed_bar_aggregation()
    test_feed_bar_with_indicator_recalc()
    test_data_feed_create_factory()
    test_aggregate_period_semantic()
    test_aggregate_with_existing_data()

    print("所有测试完成!")
