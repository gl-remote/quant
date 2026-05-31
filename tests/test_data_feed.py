"""测试 data_feed 模块

这个脚本演示了如何使用新的数据管理系统。
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from strategies import (
    Bar, DataFeedCache, DataFeed,
    PeriodRequirements, IndicatorRequirements, EventsRequirements, DataRequirements,
    build_context, make_view,
    MaStrategyCore,
)
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
    """测试 DataFeedCache 单例"""
    print("=== 测试 DataFeedCache 单例 ===\n")

    cache1 = DataFeedCache.get_instance()
    cache2 = DataFeedCache.get_instance()

    print(f"cache1 与 cache2 是否相同: {cache1 is cache2}")

    # 获取或创建 DataFeed
    feed = cache1.get_or_create("TEST2")
    print(f"DataFeed symbol: {feed.symbol}")
    print()


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
    ctx = build_context(feed, reqs, latest_bar.datetime)

    print(f"BarContext symbol: {ctx.symbol}")
    print(f"包含的周期: {list(ctx.multi.keys())}")
    print(f"事件数量: {len(ctx.events)}")
    print()


def test_strategy_with_data_feed():
    """测试策略使用 DataFeed"""
    print("=== 测试策略使用 DataFeed ===\n")

    # 配置策略使用数据管理系统
    strategy_params = {
        "sma_short": 5,
        "sma_long": 10,
        "use_data_feed": True,
    }
    strategy = MaStrategyCore(strategy_params)

    print(f"策略名称: {strategy.name}")
    print(f"策略版本: {strategy.VERSION}")

    # 查看策略的数据需求
    reqs = strategy.data_requirements()
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

    # 创建视图
    view = make_view(bars, latest_bar.datetime, lookback_bars=10)

    print(f"视图周期: {view.period}")
    print(f"视图 K 线数量: {view.length}")
    print(f"最新收盘价: {view.close(-1):.2f}")
    print()


if __name__ == "__main__":
    print("开始测试数据管理系统...\n")

    test_data_feed_basic()
    test_data_feed_cache()
    test_build_context()
    test_strategy_with_data_feed()
    test_make_view()

    print("所有测试完成!")
