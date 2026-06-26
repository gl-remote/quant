"""
统一量化统计计算公式库

项目内全部量化统计、交易指标、风控测算的唯一计算口径来源。
所有公式严格贴合金融量化行业通用标准，遵循 common/ 零依赖原则。

使用方式:
    from common.formulas import calculate_fifo_profit, position_size, total_return, win_rate

公式单元测试: tests/test_common.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

# ============================================================================
# FIFO 盈亏计算 (FIFO PnL Calculation)
# ============================================================================


def calculate_fifo_profit(fills: Sequence[object]) -> float:
    """按 FIFO 顺序计算已平仓交易的盈亏总额

    与笛卡尔积不同，此函数按先入先出规则将每笔买入与卖出匹配，
    正确处理多笔买入→单笔卖出、部分平仓等场景。

    输入数据结构要求:
        fills 列表中的每个元素需具有:
            - action 属性/键: 'buy' 或 'sell'
            - price 属性/键: 成交价格
            - volume 属性/键: 成交量

    Args:
        fills: 成交记录列表，按时间顺序排列

    Returns:
        FIFO 盈亏总额 (未扣除手续费/滑点)
    """

    def get_attr(obj: object, attr: str) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
        if hasattr(obj, attr):
            return getattr(obj, attr)  # pyright: ignore[reportAny]
        if isinstance(obj, dict):
            return obj.get(attr)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        return None

    buy_entries: list[tuple[float, float]] = []
    sell_entries: list[tuple[float, float]] = []

    for fill in fills:
        action = get_attr(fill, "action")  # pyright: ignore[reportAny]
        price = float(get_attr(fill, "price"))  # pyright: ignore[reportAny]
        volume = float(get_attr(fill, "volume"))  # pyright: ignore[reportAny]

        if action == "buy":
            buy_entries.append((price, volume))
        elif action == "sell":
            sell_entries.append((price, volume))

    total_profit: float = 0.0
    bi: int = 0  # 当前待匹配买入的索引
    bv: float = 0.0  # 当前买入剩余的未匹配量

    for sell_price, sell_vol in sell_entries:
        remaining: float = sell_vol
        while remaining > 0 and bi < len(buy_entries):
            if bv == 0:
                _, bv = buy_entries[bi]
            matched: float = min(remaining, bv)
            total_profit += (sell_price - buy_entries[bi][0]) * matched
            remaining -= matched
            bv -= matched
            if bv == 0:
                bi += 1

    return total_profit


# ============================================================================
# 收益类指标 (Return Metrics)
# ============================================================================


def total_return(initial_capital: float, final_equity: float, min_trades: int = 1, total_trades: int = 1) -> float:
    """计算简单总收益率

    金融行业通用定义: (期末权益 - 期初资金) / 期初资金

    Args:
        initial_capital: 初始资金
        final_equity: 最终权益
        min_trades: 最少交易次数阈值，低于此值返回 0.0
        total_trades: 实际交易次数

    Returns:
        总收益率 (比值，如 0.15 = 15%)
    """
    if initial_capital <= 0 or total_trades < min_trades:
        return 0.0
    return (final_equity - initial_capital) / initial_capital


# ============================================================================
# 胜率 (Win Rate)
# ============================================================================


def win_rate(win_trades: int, total_trades: int) -> float:
    """计算胜率

    行业标准: 盈利交易数 / 总交易数。总交易数为 0 时返回 0.0。

    Args:
        win_trades: 盈利交易次数
        total_trades: 总交易次数

    Returns:
        胜率 (比值，如 0.45 = 45%)
    """
    if total_trades <= 0:
        return 0.0
    return win_trades / total_trades


# ============================================================================
# 仓位计算 (Position Sizing)
# ============================================================================


def position_size(capital: float, position_ratio: float, price: float, contract_size: int, margin: float = 1.0) -> int:
    """计算下单手数

    期货: 手数 = capital × position_ratio / (price × contract_size × margin)
    股票: margin=1.0（等价全款，持仓 100% 保证金）

    Args:
        capital: 可用资金
        position_ratio: 仓位比例 (如 0.1 = 10%)
        price: 当前价格
        contract_size: 合约乘数
        margin: 保证金比例 (如 0.07 = 7%)

    Returns:
        下单手数 (整数，资金不足时返回 0)
    """
    if price <= 0 or contract_size <= 0 or margin <= 0:
        return 0
    vol = capital * position_ratio / (price * contract_size * margin)
    if vol < 1:
        return 0
    return int(vol)


# ============================================================================
# 盈利品种占比 (Profitable Ratio)
# ============================================================================


def profitable_ratio(positive_count: int, total_count: int) -> float:
    """计算盈利品种占比

    Args:
        positive_count: 正收益品种数
        total_count: 总品种数

    Returns:
        盈利占比 (比值)
    """
    if total_count <= 0:
        return 0.0
    return positive_count / total_count
