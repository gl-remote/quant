"""测试 data_feed 模块

这个脚本演示了如何使用新的数据管理系统。
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from strategies import (
    Bar, Event, BigTradeEvent, DataFeed,
    PeriodRequirements, IndicatorRequirements, EventsRequirements, DataRequirements,
    build_context,
    MaStrategyCore,
)
from strategies.runtime.cache import get_cached_feed, set_cached_feed, clear_cache
from strategies.ma_strategy import MACrossParams
from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    SIGNAL_STOP_LOSS,
    SIGNAL_TAKE_PROFIT,
    SIGNAL_DEATH_CROSS,
    SIGNAL_GOLDEN_CROSS,
)


def generate_test_bars(num_bars: int = 100) -> List[Bar]:
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

        bars.append(Bar(
            symbol="TEST",
            datetime=dt,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
        ))

    return bars


def make_view(
    bars: List[Bar],
    current_time: datetime,
    lookback_bars: Optional[int] = None,
    indicators: Optional[Dict[str, List[float]]] = None,
    events: Optional[List[Event]] = None,
) -> 'PeriodDataView':
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
            event_dicts.append({
                'datetime': pd.Timestamp(event.timestamp),
                'type': event.type,
                'symbol': event.symbol,
                'reason': event.reason,
                'period': event.period,
                'data': event.data
            })
        events_df = pd.DataFrame(event_dicts)
        events_df = events_df.set_index('datetime')

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
        bars, latest_bar.datetime, lookback_bars=10,
        indicators={"sma_5": closes, "sma_10": closes},
    )
    assert view_ind.indicator("sma_5", -1) is not None
    print(f"   sma_5 最新值: {view_ind.indicator('sma_5', -1):.2f}")
    print(f"   sma_10 最新值: {view_ind.indicator('sma_10', -1):.2f}\n")

    # 4. 带事件的视图
    print("4. 带事件的视图")
    test_events = [
        BigTradeEvent(
            timestamp=bars[5].datetime, type="big_trade", symbol="TEST",
            price=105.0, volume=1000, direction="buy",
        ),
        BigTradeEvent(
            timestamp=bars[10].datetime, type="big_trade", symbol="TEST",
            price=110.0, volume=2000, direction="sell",
        ),
    ]
    view_evt = make_view(
        bars, latest_bar.datetime, lookback_bars=15,
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
        bars, latest_bar.datetime, lookback_bars=20,
        indicators={"sma_5": closes},
        events=test_events,
    )
    assert view_full.indicator("sma_5", -1) is not None
    assert len(view_full.get_events()) > 0
    print(f"   视图长度: {view_full.length}")
    print(f"   指标存在: {view_full.indicator('sma_5', -1) is not None}")
    print(f"   事件存在: {len(view_full.get_events())}\n")


if __name__ == "__main__":
    print("开始测试数据管理系统...\n")

    test_data_feed_basic()
    test_data_feed_cache()
    test_build_context()
    test_strategy_with_data_feed()
    test_make_view()

    print("所有测试完成!")
