"""测试 data_feed 模块

这个脚本演示了如何使用新的数据管理系统。
"""

from datetime import datetime, timedelta

from strategies import (
    Bar,
    BigTradeEvent,
    DataFeed,
    DataRequirements,
    Event,
    EventsRequirements,
    IndicatorRequirements,
    MaStrategyCore,
    PeriodRequirements,
    build_context,
)
from strategies.ma_strategy import MACrossParams
from strategies.runtime.cache import clear_cache, get_cached_feed, set_cached_feed
from strategies.runtime.period import PeriodDataView


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
    feed.register_indicator("1m", "sma", period=5)
    feed.register_indicator("1m", "sma", period=10)

    # 生成测试数据
    bars = generate_test_bars(50)
    feed.load_history_data("1m", bars)

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
    feed.register_indicator("1m", "sma", period=5)
    feed.register_indicator("1m", "sma", period=10)

    # 加载数据
    bars = generate_test_bars(30)
    feed.load_history_data("1m", bars)

    # 定义数据需求
    reqs = DataRequirements(
        periods={
            "1m": PeriodRequirements(lookback_bars=20),
        },
        indicators={
            "1m": [
                IndicatorRequirements(name="sma", params={"period": 5}),
                IndicatorRequirements(name="sma", params={"period": 10}),
            ],
        },
        events=EventsRequirements.no_events(),
    )

    # 构建上下文
    latest_bar = bars[-1]
    ctx = build_context(feed, reqs, latest_bar.datetime, latest_bar)

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
    feed.register_indicator("1m", "sma", period=5)
    feed.register_indicator("1m", "sma", period=10)

    # 初始历史：30 根 K 线（模拟 tqsdk 推送的历史数据）
    bars = generate_test_bars(30)
    feed.load_history_data("1m", bars)
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
    feed.calculate_period("1m", incremental=True)

    # 与全量重算对比（保证增量与全量结果一致）
    sma_5_inc = pd_obj.get_indicator("sma_5", -1)
    sma_10_inc = pd_obj.get_indicator("sma_10", -1)
    assert sma_5_inc is not None and not math.isnan(sma_5_inc)
    assert sma_10_inc is not None and not math.isnan(sma_10_inc)

    pd_obj._calculated_indicators = set()  # pyright: ignore[reportPrivateUsage]
    pd_obj._indicator_last_calc_idx = {}  # pyright: ignore[reportPrivateUsage]
    feed.calculate_all()
    sma_5_full = pd_obj.get_indicator("sma_5", -1)
    sma_10_full = pd_obj.get_indicator("sma_10", -1)
    print(f"  新增 K 线后: sma_5={sma_5_inc:.4f}, 全量 sma_5={sma_5_full:.4f}")
    print(f"               sma_10={sma_10_inc:.4f}, 全量 sma_10={sma_10_full:.4f}")
    assert abs(sma_5_inc - sma_5_full) < 1e-9, "sma_5 增量计算与全量重算不一致"
    assert abs(sma_10_inc - sma_10_full) < 1e-9, "sma_10 增量计算与全量重算不一致"

    # --- 场景 2：无新 K 线时调用 calculate_period 应跳过（避免重复计算） ---
    last_idx_before = len(pd_obj._df) - 1  # pyright: ignore[reportPrivateUsage]
    calc_idx_before = pd_obj.get_indicator_last_calc_idx("sma_5")
    feed.calculate_period("1m", incremental=True)
    calc_idx_after = pd_obj.get_indicator_last_calc_idx("sma_5")
    print(
        f"  无新数据时: last_idx={last_idx_before}, calc_idx_before={calc_idx_before}, calc_idx_after={calc_idx_after}"
    )
    assert calc_idx_before == calc_idx_after, "incremental=True 时不应在无新数据时重算"

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
    feed.register_indicator("1m", "sma", period=5)
    feed.register_indicator("1m", "ema", period=12)

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
        feed.calculate_period("1m", incremental=True)

    final_sma_5 = pd_obj.get_indicator("sma_5", -1)
    final_ema_12 = pd_obj.get_indicator("ema_12", -1)
    print(f"  10 轮实时推送后: sma_5={final_sma_5:.4f}, ema_12={final_ema_12:.4f}")

    # --- 阶段 3：与全量重算对比（保证增量结果=全量结果） ---
    pd_obj._calculated_indicators = set()  # pyright: ignore[reportPrivateUsage]
    pd_obj._indicator_last_calc_idx = {}  # pyright: ignore[reportPrivateUsage]
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
        feed.register_indicator(period, "sma", period=5)

    # 初始加载：1m=50 根，5m=30 根，15m=20 根（tqsdk 各周期独立推送）
    for period, n in [("1m", 50), ("5m", 30), ("15m", 20)]:
        bars = generate_test_bars(n)
        feed.load_history_data(period, bars)
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
        feed.calculate_period("1m", incremental=True)

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

    print("所有测试完成!")
