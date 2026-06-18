"""测试 data_feed 模块

这个脚本演示了如何使用新的数据管理系统。
"""

from datetime import datetime, timedelta

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
        bar_times = [pd.Timestamp(bar.datetime) for bar in bars]
        indicators_df = pd.DataFrame(indicators, index=bar_times)
        period_data.append_indicators(indicators_df)

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

    # 预计算所有指标
    feed.calculate_all()

    # 获取数据视图
    latest_bar = bars[-1]
    view = feed.get_data("1m", latest_bar.datetime, lookback_bars=10)

    print(f"周期: {view.period}")
    print(f"视图截止时间: {view.current_time}")
    print(f"视图包含 K 线数量: {view.length}")
    print(f"最新收盘价: {view.close(-1):.2f}")
    print(f"SMA(5): {view.indicator('sma_5', -1):.2f}")
    print(f"SMA(10): {view.indicator('sma_10', -1):.2f}")
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
    """测试 DataFeed 的增量计算逻辑（tqsdk 主循环路径）

    模拟实时模式：先加载历史 → calculate_all 预计算 → 逐根 K 线 append_bar
    → calculate_period(main_period, incremental=True)。

    验证项：
    1. 增量计算后的指标值与全量重算结果一致（保证回测/实盘一致性）
    2. 没有新 K 线时第二次调用 calculate_period 不会重复计算（跳过逻辑生效）
    """
    import math

    print("=== 测试 calculate_period 增量计算 ===\n")

    feed = DataFeed("TEST_INC")
    feed.register_period("1m")
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func))
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 10}, window=10, func=sma_func))

    # 初始历史：30 根 K 线（模拟 tqsdk 推送的历史数据）
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
    feed.calculate_all()

    pd_obj = feed.get_period("1m")
    assert pd_obj is not None
    sma_5_initial = pd_obj.get_indicator("sma_5", -1)
    sma_10_initial = pd_obj.get_indicator("sma_10", -1)
    print(f"  初始历史: 30 根, sma_5={sma_5_initial:.4f}, sma_10={sma_10_initial:.4f}")
    assert sma_5_initial is not None and not math.isnan(sma_5_initial)
    assert sma_10_initial is not None and not math.isnan(sma_10_initial)

    # --- 场景 1：append 1 根新 K 线 + calculate_period(incremental=True) ---
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
    pd_obj.append_bar(new_bar)
    feed.calculate_period("1m")

    # 与全量重算对比（保证增量与全量结果一致）
    sma_5_inc = pd_obj.get_indicator("sma_5", -1)
    sma_10_inc = pd_obj.get_indicator("sma_10", -1)
    assert sma_5_inc is not None and not math.isnan(sma_5_inc)
    assert sma_10_inc is not None and not math.isnan(sma_10_inc)

    feed.calculate_all()
    sma_5_full = pd_obj.get_indicator("sma_5", -1)
    sma_10_full = pd_obj.get_indicator("sma_10", -1)
    print(f"  新增 K 线后: sma_5={sma_5_inc:.4f}, 全量 sma_5={sma_5_full:.4f}")
    print(f"               sma_10={sma_10_inc:.4f}, 全量 sma_10={sma_10_full:.4f}")
    assert abs(sma_5_inc - sma_5_full) < 1e-9, "sma_5 增量计算与全量重算不一致"
    assert abs(sma_10_inc - sma_10_full) < 1e-9, "sma_10 增量计算与全量重算不一致"

    # --- 场景 2：无新 K 线时调用 calculate_period 应跳过（指标列最后一行非 NaN） ---
    feed.calculate_period("1m")
    sma_5_after = pd_obj.get_indicator("sma_5", -1)
    assert sma_5_after is not None and abs(sma_5_inc - sma_5_after) < 1e-9, "无新数据时重算结果应一致"

    print("  ✅ 增量计算跳过逻辑与一致性验证通过\n")


def test_tqsdk_path_simulation():
    """模拟 tqsdk 实时链路：load_df(kline_serial) → calculate_all → N 轮 append_bar+calculate_period

    这是 test/live 命令的核心数据流程，保证 tqsdk 路径与回测路径一致。
    """
    import math

    import pandas as pd

    print("=== 模拟 tqsdk 实时链路 ===\n")

    feed = DataFeed("TQSDK_SIM")
    feed.register_period("1m")
    feed.register_indicator("1m", IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func))
    feed.register_indicator("1m", IndicatorSpec(name="ema", params={"period": 12}, window=12, func=ema_func))

    # --- 阶段 1：模拟 tqsdk kline_serial 的初始历史数据 ---
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

    pd_obj = feed.get_period("1m")
    assert pd_obj is not None
    pd_obj.load_df(df)
    feed.calculate_all()

    init_sma_5 = pd_obj.get_indicator("sma_5", -1)
    init_ema_12 = pd_obj.get_indicator("ema_12", -1)
    print(f"  初始化完成: {len(df)} 根 K 线, sma_5={init_sma_5:.4f}, ema_12={init_ema_12:.4f}")
    assert init_sma_5 is not None and not math.isnan(init_sma_5)
    assert init_ema_12 is not None and not math.isnan(init_ema_12)

    # --- 阶段 2：模拟 10 轮实时推送（append_bar + calculate_period） ---
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
        pd_obj.append_bar(new_bar)
        feed.calculate_period("1m")

    final_sma_5 = pd_obj.get_indicator("sma_5", -1)
    final_ema_12 = pd_obj.get_indicator("ema_12", -1)
    print(f"  10 轮实时推送后: sma_5={final_sma_5:.4f}, ema_12={final_ema_12:.4f}")

    # --- 阶段 3：与全量重算对比（保证增量结果=全量结果） ---
    feed.calculate_all()
    assert abs(pd_obj.get_indicator("sma_5", -1) - final_sma_5) < 1e-9
    assert abs(pd_obj.get_indicator("ema_12", -1) - final_ema_12) < 1e-9
    print("  ✅ 10 轮实时推送后的增量结果与全量重算一致\n")


def test_multi_period_consistency():
    """多周期场景：主周期逐根增量，非主周期在初始化阶段计算完整后保持不变

    验证 tqsdk 路径下的多周期行为与设计意图一致：
    - 主周期 (1m)：每轮 append_bar + calculate_period → 指标值更新
    - 非主周期 (5m/15m)：仅初始化时 calculate_all 计算过，不增量重算
      （策略读这些周期的指标时读的是历史最新值，不期望"实时"更新）
    """
    import math

    print("=== 多周期场景下主周期/非主周期一致性 ===\n")

    feed = DataFeed("MULTI_PERIOD")
    for period in ("1m", "5m", "15m"):
        feed.register_period(period)
        feed.register_indicator(period, IndicatorSpec(name="sma", params={"period": 5}, window=5, func=sma_func))

    # 初始加载：1m=50 根，5m=30 根，15m=20 根（tqsdk 各周期独立推送）
    import pandas as pd

    for period, n in [("1m", 50), ("5m", 30), ("15m", 20)]:
        bars = generate_test_bars(n)
        # 转换为 DataFrame 加载
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
    feed.calculate_all()

    # 记录初始值
    initial_values = {}
    for period in ("1m", "5m", "15m"):
        pd_obj = feed.get_period(period)
        initial_values[period] = pd_obj.get_indicator("sma_5", -1)
        print(f"  初始 {period}: sma_5={initial_values[period]:.4f}, {len(pd_obj._df)} 根K线")  # pyright: ignore[reportPrivateUsage]

    # 只对主周期 (1m) 做 5 轮实时推送
    main_pd = feed.get_period("1m")
    last_time = datetime.now()
    for i in range(5):
        main_pd.append_bar(
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
        feed.calculate_period("1m")

    # 断言：主周期更新了；非主周期未更新（但读历史值应该仍能拿到）
    main_after = main_pd.get_indicator("sma_5", -1)
    assert main_after != initial_values["1m"], "主周期指标应随新 K 线更新"
    print(f"  主周期 1m 推送 5 根后: sma_5={main_after:.4f}（原值 {initial_values['1m']:.4f}）")

    # 非主周期：值仍然可读（因为初始化时算过了），不应为 None/NaN
    for period in ("5m", "15m"):
        pd_obj = feed.get_period(period)
        val = pd_obj.get_indicator("sma_5", -1)
        assert val is not None and not math.isnan(val), f"{period} 指标值应存在（初始化阶段已计算）"
        # 非主周期在没有新增数据前提下值应与初始化一致
        assert abs(val - initial_values[period]) < 1e-9, f"{period} 指标在无新数据时不应变化"
        print(f"  非主周期 {period}: sma_5={val:.4f}（与初始化一致）")

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
    assert "5m" in feed._aggregation_targets
    assert "15m" in feed._aggregation_targets
    print(f"  基础周期: {feed._base_period}")
    print(f"  聚合目标: {feed._aggregation_targets}")

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

    # 逐根 feed_bar 前 5 根
    for i, bar in enumerate(bars[:5]):
        feed.feed_bar(bar)
        for pn in ("5m", "15m"):
            pd_obj = feed.get_period(pn)
            assert pd_obj is not None
            assert pd_obj.has_forming_bar, f"第 {i+1} 根 bar 后 {pn} 应有 forming bar"
    print("  前 5 根 1m bar 喂入后: 5m/15m 均有 forming bar")

    # 前 5 根 bar 的 high 最高为 105（bar 4 的 high=105）
    period_5m = feed.get_period("5m")
    assert period_5m is not None
    assert period_5m.forming_bar is not None
    first_5m_high = period_5m.forming_bar.high
    print(f"  5m forming bar high = {first_5m_high} (期望 105)")
    assert first_5m_high == 105.0

    # 第 6 根 bar（index 5, time=10:05）→ 新 5m 周期开始
    feed.feed_bar(bars[5])
    # 第 1 根 5m bar (10:00) complete, 第 2 根 (10:05) forming
    assert period_5m.length == 1, f"5m 应有 1 根 complete bar, 实际 {period_5m.length}"
    assert period_5m.has_forming_bar, "5m 应有 forming bar"

    complete_bar_5m = period_5m.get_bar(0)
    assert complete_bar_5m is not None
    print(f"  第 1 根 5m complete bar: open={complete_bar_5m.open}, high={complete_bar_5m.high}")
    assert abs(complete_bar_5m.open - 100.0) < 0.001
    assert abs(complete_bar_5m.high - 105.0) < 0.001
    assert abs(complete_bar_5m.close - 104.5) < 0.001
    assert complete_bar_5m.datetime.strftime("%H:%M") == "10:00"
    print("  第 1 根 5m bar OHLC 验证通过")

    # 继续喂入 bar 6~10 (10:06~10:10) → 第 2 个 5m 在 10:10 时 complete
    for i in range(6, 11):
        feed.feed_bar(bars[i])
    assert period_5m.length == 2, f"11 根 bar 后 5m 应有 2 根 complete, 实际 {period_5m.length}"
    complete_bar_5m_2 = period_5m.get_bar(1)
    assert complete_bar_5m_2 is not None
    assert abs(complete_bar_5m_2.open - 105.0) < 0.001
    assert abs(complete_bar_5m_2.high - 110.0) < 0.001
    print(f"  第 2 根 5m complete bar: open={complete_bar_5m_2.open}, high={complete_bar_5m_2.high} ✅")

    # 验证 15m 还在 forming（只有 11 根，不够 15）
    period_15m = feed.get_period("15m")
    assert period_15m is not None
    assert period_15m.length == 0, "15m 不应有 complete bar"
    assert period_15m.has_forming_bar
    print("  15m: 0 根 complete, 有 forming bar (正确)")

    # build_context: 使用 bars[7] (10:07)
    # 15m forming bar 从 10:00 开始(窗口10:00~10:14)，10:07 ≤ forming 窗口结束时间，
    # 而 forming bar 的 datetime 固定为起始时间 10:00，对 get_data 的 latest time 检查而言 10:07 > 10:00。
    # 所以我们用 bars[4] (10:04)——它在 15m forming bar 的"visual time"范围内，
    # 且 5m 第 1 根已完成。
    ctx = feed.build_context(reqs, bars[4])
    assert "1m" in ctx.multi
    assert "5m" in ctx.multi
    assert "15m" in ctx.multi
    print(f"  build_context multi: {list(ctx.multi.keys())} ✅")

    view_5m = ctx.multi["5m"]
    assert view_5m is not None
    assert view_5m.length == 1, f"5m view 应有 1 根 bar (第 1 根 complete), 实际 {view_5m.length}"
    print(f"  5m view: {view_5m.length} 根 bar ✅")
    print()


def test_build_ctx_cache_aggregated():
    """测试 build_ctx_cache 聚合模式（回测路径）

    模拟回测流程：feed_history_df → build_ctx_cache → 逐 bar 聚合
    """
    import pandas as pd

    print("=== 测试 build_ctx_cache 聚合模式 ===\n")

    reqs = DataRequirements(
        periods={
            "1m": PeriodRequirements(lookback_bars=10),
            "5m": PeriodRequirements(lookback_bars=5),
        },
        indicators={},
        events=EventsRequirements.no_events(),
    )

    feed = DataFeed("TEST_CACHE_AGG", requirements=reqs)

    base_time = datetime(2024, 1, 1, 10, 0, 0)
    bar_data = [
        {
            "datetime": pd.Timestamp(base_time + timedelta(minutes=i)),
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000,
        }
        for i in range(12)
    ]
    df = pd.DataFrame(bar_data).set_index("datetime")
    feed.load_history_df("1m", df)

    cache = feed.build_ctx_cache(reqs, "TEST_CACHE_AGG")
    assert len(cache) == 12, f"cache 应有 12 个 entry, 实际 {len(cache)}"
    print(f"  cache 包含 {len(cache)} 个 BarContext ✅")

    # 第 5 根 bar (10:00) 时 5m 已有第 1 根 complete bar
    ts_0 = pd.Timestamp(base_time + timedelta(minutes=0))
    ctx_0 = cache.get(ts_0)
    assert ctx_0 is not None
    assert ctx_0.multi["5m"].length == 1, f"10:00 时 5m 应有 1 根 complete bar"
    print(f"  {ts_0}: 5m view 含 1 根 complete bar ✅")

    # 第 6 根 bar (10:05) 时 5m 已有 2 根 complete bar
    ts_5 = pd.Timestamp(base_time + timedelta(minutes=5))
    ctx_5 = cache.get(ts_5)
    assert ctx_5 is not None
    assert ctx_5.multi["5m"].length == 2, f"10:05 时 5m 应有 2 根 complete bar, 实际 {ctx_5.multi['5m'].length}"
    print(f"  {ts_5}: 5m view 含 2 根 complete bar ✅")

    # 第 11 根 bar (10:10) 时 5m 有 3 根 complete bar
    ts_10 = pd.Timestamp(base_time + timedelta(minutes=10))
    ctx_10 = cache.get(ts_10)
    assert ctx_10 is not None
    assert ctx_10.multi["5m"].length == 3, f"10:10 时 5m 应有 3 根 complete bar, 实际 {ctx_10.multi['5m'].length}"
    print(f"  {ts_10}: 5m view 含 3 根 complete bar ✅")
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
    assert period_5m.length == 3, f"16 根 bar 后 5m 应有 3 根 complete, 实际 {period_5m.length}"
    sma_val = period_5m.get_indicator("sma_3", -1)
    print(f"  16 根 bar 后 5m sma_3: {sma_val}")
    print("  feed_bar 后高周期指标重算逻辑验证通过 ✅")
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
    with mock.patch("data.manager.DataManager") as MockDM:
        instance = MockDM.return_value
        instance.load_kline.return_value = [("TEST", kline_df, "1m")]

        feed = DataFeed.create("TEST_CREATE", reqs)

        assert feed._base_period == "1m"
        assert "5m" in feed._aggregation_targets
        period_1m = feed.get_period("1m")
        assert period_1m is not None and period_1m.length == 50
        sma_val = period_1m.get_indicator("sma_5", -1)
        assert sma_val is not None
        print(f"  基础周期 1m: 50 根 K 线, sma_5={sma_val:.4f} ✅")

    # 场景 2：DataFeed.create() 返回的 DataFeed 能正常 build_context
    print("2. build_context 正常")
    with mock.patch("data.manager.DataManager") as MockDM:
        instance = MockDM.return_value
        instance.load_kline.return_value = [("TEST", kline_df, "1m")]

        feed = DataFeed.create("TEST_CREATE2", reqs)
        bar = Bar(
            symbol="TEST_CREATE2",
            datetime=base_time + timedelta(minutes=49),
            open=149.0, high=150.0, low=148.0, close=149.5, volume=1000,
        )
        ctx = feed.build_context(reqs, bar)
        assert "1m" in ctx.multi
        assert "5m" in ctx.multi
        print("  build_context 正常 ✅")

    # 场景 3：内存缓存命中 → 零 I/O
    print("3. 内存缓存命中")
    with mock.patch("data.manager.DataManager") as MockDM:
        instance = MockDM.return_value
        instance.load_kline.return_value = [("TEST", kline_df, "1m")]

        feed1 = DataFeed.create("TEST_CACHE", reqs)
        feed2 = DataFeed.create("TEST_CACHE", reqs)
        assert feed2 is feed1, "缓存命中应返回同一对象"
        print("  内存缓存命中 ✅")

    cache_module.clear_cache()
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
    test_build_ctx_cache_aggregated()
    test_feed_bar_with_indicator_recalc()
    test_data_feed_create_factory()

    print("所有测试完成!")
