"""
统一量化统计计算公式库

项目内全部量化统计、交易指标、风控测算的唯一计算口径来源。
所有公式严格贴合金融量化行业通用标准，遵循 common/ 零依赖原则。

使用方式:
    from common.formulas import (
        total_return, annualized_return, win_rate,
        profit_factor, simple_moving_average, position_size,
        golden_cross, death_cross, stop_loss_triggered,
        take_profit_triggered, trade_cost,
    )

公式单元测试: tests/test_common.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from common.constants import (
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)

# 每交易日交易秒数 (4 小时日盘，不含夜盘)
# 注意: 国内期货实际交易时段因夜盘而异（部分品种夜盘至 23:00，上期所品种至次日 2:30），
# 此常量取日盘 4 小时作为保守近似。convert_annual_factor 以此为基准计算年化因子，
# 对于有夜盘的品种会低估实际交易时长，导致年化指标偏高。
# 精确场景可通过策略配置按交易所指定实际交易时段。
_SECONDS_PER_TRADING_DAY = 14400


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


def annualized_return(total_ret: float, days: int, annual_factor: int = 252) -> float:
    """将总收益率年化

    公式: (1 + R)^(252/days) - 1
    当 days 不足一年时外推，超过一年时折算。
    当 days=0 或 R<=-1 (破产) 时返回安全的边界值。

    Args:
        total_ret: 总收益率 (比值)
        days: 实际交易天数
        annual_factor: 年交易日数 (默认 252)

    Returns:
        年化收益率 (比值)
    """
    if days <= 0 or total_ret <= -1:
        return total_ret if days <= 0 else -1.0
    return float((1 + total_ret) ** (annual_factor / days) - 1)  # pyright: ignore[reportAny]


# ============================================================================
# 胜率与盈亏比 (Win Rate & Profit Factor)
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


def profit_factor(total_win: float, total_loss: float) -> float:
    """计算盈亏比 (Profit Factor)

    行业标准定义: 总盈利 / |总亏损|
    不是平均盈利 / 平均亏损。

    Args:
        total_win: 总盈利金额 (正值)
        total_loss: 总亏损金额 (负值或正值)

    Returns:
        盈亏比，total_loss 为 0 时返回 0.0
    """
    abs_loss = abs(total_loss)
    if abs_loss == 0:
        return 0.0
    return total_win / abs_loss


# ============================================================================
# 交易成本 (Trade Cost)
# ============================================================================


def trade_cost(price: float, quantity: int, commission_rate: float, slippage: float) -> float:
    """计算单边交易成本

    行业标准: 手续费 + 滑点
      - 手续费 = commission_rate × price × quantity
      - 滑点 = slippage × quantity

    Args:
        price: 成交价格
        quantity: 成交量 (手)
        commission_rate: 手续费率 (如 0.0003 = 0.03%)
        slippage: 每手滑点成本 (如 1.0)

    Returns:
        单边交易成本总额
    """
    return commission_rate * price * quantity + slippage * quantity


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
# 均线计算 (Moving Average)
# ============================================================================


def simple_moving_average(prices: list[float], period: int) -> float:
    """计算简单移动平均线 (SMA)

    行业标准: 最近 period 个值的算术平均。
    数据不足 period 时，使用全部可用数据的均值作为近似。

    Args:
        prices: 价格序列 (按时间升序)
        period: 均线周期

    Returns:
        SMA 值，prices 为空或 period<=0 时返回 0.0
    """
    if not prices or period <= 0:
        return 0.0
    actual_period = min(period, len(prices))
    chunk = prices[-actual_period:]
    return sum(chunk) / len(chunk)


# ============================================================================
# 金叉/死叉检测 (Cross Detection)
# ============================================================================


def golden_cross(prev_short: float, prev_long: float, cur_short: float, cur_long: float) -> bool:
    """检测金叉信号

    金叉定义: 前一时刻短期均线 <= 长期均线，当前短期均线 > 长期均线。
    即短期均线上穿长期均线，通常为买入信号。

    Args:
        prev_short: 前一时刻短期均线值
        prev_long:  前一时刻长期均线值
        cur_short:  当前时刻短期均线值
        cur_long:   当前时刻长期均线值

    Returns:
        True 表示发生金叉
    """
    return prev_short <= prev_long and cur_short > cur_long


def death_cross(prev_short: float, prev_long: float, cur_short: float, cur_long: float) -> bool:
    """检测死叉信号

    死叉定义: 前一时刻短期均线 >= 长期均线，当前短期均线 < 长期均线。
    即短期均线下穿长期均线，通常为卖出信号。

    Args:
        prev_short: 前一时刻短期均线值
        prev_long:  前一时刻长期均线值
        cur_short:  当前时刻短期均线值
        cur_long:   当前时刻长期均线值

    Returns:
        True 表示发生死叉
    """
    return prev_short >= prev_long and cur_short < cur_long


# ============================================================================
# 止损/止盈检测 (Stop Loss & Take Profit)
# ============================================================================


def stop_loss_triggered(entry_price: float, current_price: float, stop_loss_ratio: float, direction: str) -> bool:
    """检测止损条件

    行业标准公式:
      多头: (入场价 - 当前价) / 入场价 >= 止损比例
      空头: (当前价 - 入场价) / 入场价 >= 止损比例

    Args:
        entry_price: 入场价格
        current_price: 当前价格
        stop_loss_ratio: 止损比例 (如 0.03 = 3%)
        direction: 持仓方向 (TRADE_DIRECTION_LONG or TRADE_DIRECTION_SHORT

    Returns:
        True 表示触发止损
    """
    if entry_price <= 0:
        return False
    if direction == TRADE_DIRECTION_LONG:
        return (entry_price - current_price) / entry_price >= stop_loss_ratio
    elif direction == TRADE_DIRECTION_SHORT:
        return (current_price - entry_price) / entry_price >= stop_loss_ratio
    return False


def take_profit_triggered(entry_price: float, current_price: float, take_profit_ratio: float, direction: str) -> bool:
    """检测止盈条件

    行业标准公式:
      多头: (当前价 - 入场价) / 入场价 >= 止盈比例
      空头: (入场价 - 当前价) / 入场价 >= 止盈比例

    Args:
        entry_price: 入场价格
        current_price: 当前价格
        take_profit_ratio: 止盈比例 (如 0.05 = 5%)
        direction: 持仓方向 (TRADE_DIRECTION_LONG or TRADE_DIRECTION_SHORT

    Returns:
        True 表示触发止盈
    """
    if entry_price <= 0:
        return False
    if direction == TRADE_DIRECTION_LONG:
        return (current_price - entry_price) / entry_price >= take_profit_ratio
    elif direction == TRADE_DIRECTION_SHORT:
        return (entry_price - current_price) / entry_price >= take_profit_ratio
    return False


# ============================================================================
# 持仓均价 (Average Entry Price)
# ============================================================================


def average_entry_price(old_position: int, old_price: float, new_quantity: int, new_price: float) -> float:
    """计算加仓后的加权平均持仓成本

    行业标准:
      均价 = (旧持仓×旧均价 + 新成交量×新价格) / 总持仓

    Args:
        old_position: 加仓前持仓量
        old_price: 加仓前均价
        new_quantity: 新增数量
        new_price: 新增价格

    Returns:
        加权平均持仓成本
    """
    total = old_position + new_quantity
    if total <= 0:
        return 0.0
    return (old_position * old_price + new_quantity * new_price) / total


# ============================================================================
# 每点回撤 (Single-Point Drawdown)
# ============================================================================


def drawdown_at_point(peak: float, current: float) -> float:
    """计算权益曲线在某个时点的回撤率

    行业标准: (峰值 - 当前值) / 峰值

    Args:
        peak: 历史最高权益
        current: 当前权益

    Returns:
        回撤率 (比值，如 0.08 = 8%)
    """
    if peak <= 0:
        return 0.0
    return (peak - current) / peak


# ============================================================================
# 日均交易 (Average Trades Per Day)
# ============================================================================


def avg_trades_per_day(total_trades: int, total_days: int) -> float:
    """计算日均交易次数

    当 total_days<=0 时使用 1 作为除数（对应原 max(total_days, 1) 逻辑），
    避免除零错误同时保证单日交易数据仍然有意义。

    Args:
        total_trades: 总交易次数
        total_days: 总交易天数

    Returns:
        日均交易次数
    """
    if total_days <= 0:
        return float(total_trades)
    return total_trades / total_days


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


# ============================================================================
# 年化因子换算 (Annual Factor Conversion)
# ============================================================================


def convert_annual_factor(kline_seconds: int) -> int:
    """根据K线周期秒数计算年化因子

    以中国市场 252 个交易日、每日 4 小时交易时间为基准。

    Args:
        kline_seconds: K线周期秒数 (60=1分钟, 3600=1小时, 86400=日线)

    Returns:
        年化因子 (一年内的K线数量)
    """
    if kline_seconds <= 0:
        return 252
    seconds_per_day = _SECONDS_PER_TRADING_DAY
    periods_per_day = seconds_per_day / kline_seconds
    return int(periods_per_day * 252)
