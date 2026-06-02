#!/usr/bin/env python3
"""测试 MaStrategy 的向后兼容性"""

import sys
import os
from datetime import datetime

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from strategies.ma_strategy import MaStrategyCore, MACrossParams
from strategies import Bar, Fill
from common.types import TradeAction
from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    SIGNAL_GOLDEN_CROSS,
)


def _make_bar(close: float, dt: datetime = datetime(2024, 1, 1, 10, 0, 0)) -> Bar:
    return Bar(
        datetime=dt,
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        volume=10000,
    )


def test_compatibility_mode():
    """测试兼容模式（不使用 DataFeed）"""
    print("=== 测试兼容模式 ===\n")

    strat = MaStrategyCore(strategy_params={'use_data_feed': False})
    print(f"策略名称: {strat.name}")
    print(f"策略版本: {strat.VERSION}")
    print(f"use_data_feed: {strat.config.use_data_feed}")

    # 喂入数据
    for _ in range(25):
        signal = strat.on_bar(_make_bar(90.0))

    # 金叉信号
    signal = strat.on_bar(_make_bar(120.0))
    print(f"金叉信号: action={signal.action}, reason={signal.reason}")
    assert signal.action == TRADE_ACTION_BUY
    assert signal.reason == SIGNAL_GOLDEN_CROSS

    # 建仓
    strat.on_fill(Fill(
        timestamp='2024-01-25',
        symbol='test',
        action=TRADE_ACTION_BUY,
        price=100.0,
        volume=5,
        reason=SIGNAL_GOLDEN_CROSS,
    ))

    print(f"持仓状态: direction={strat.position.direction}, volume={strat.position.volume}")
    assert strat.position.direction == TRADE_DIRECTION_LONG

    print("\n兼容模式测试通过!")


def test_new_mode():
    """测试新模式（使用 DataFeed）"""
    print("\n=== 测试新模式 ===\n")

    strat = MaStrategyCore(strategy_params={'use_data_feed': True})
    print(f"策略名称: {strat.name}")
    print(f"策略版本: {strat.VERSION}")
    print(f"use_data_feed: {strat.config.use_data_feed}")

    # 查看数据需求
    requirements = strat.data_requirements()
    print(f"数据需求:")
    print(f"  周期需求: {list(requirements.periods.keys())}")
    print(f"  1m 周期指标: {[f'{ind.name}_{ind.params}' for ind in requirements.indicators['1m']]}")

    print("\n新模式测试通过!")


if __name__ == '__main__':
    test_compatibility_mode()
    test_new_mode()
    print("\n所有兼容性测试通过!")
