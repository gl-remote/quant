"""策略切面 DSL 内置函数。

这些函数可在字符串 DSL 中以 ``name()`` 形式使用，主要服务于风控切面。
函数读取 ``ctx.state``、``ctx.bar`` 等运行时上下文；数据不足时返回 ``None``，
由表达式求值层静默跳过当前条件。

可用函数：
- ``cooldown()``：自上次匹配风控角色的成交以来的冷却分钟数
- ``profit_abs()`` / ``profit_pct()``：当前持仓浮盈点数 / 比例
- ``loss_abs()`` / ``loss_pct()``：当前持仓浮亏点数 / 比例
- ``peak_profit()``：入场以来峰值收益点数
- ``drawdown_pct()``：从最高价到当前价的回撤比例
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

BuiltinFn = Callable[[Any, Any], float | None]


def call_builtin(name: str, ctx: Any, config: Any) -> float | None:
    """调用 DSL 内置函数；数据不足或函数不存在时返回 None。"""
    builtin = BUILTIN_FUNCTIONS.get(name)
    if builtin is None:
        return None
    try:
        return builtin(ctx, config)
    except (AttributeError, TypeError):
        return None


def _cooldown(ctx: Any, config: Any) -> float | None:
    """自上次匹配风控角色的成交以来的冷却分钟数。

    角色过滤是一个关键设计决策：
    - take_profit 后的冷却：只匹配 reason 包含 "take_profit" 的成交
    - stop_loss 后的冷却：排除 reason 包含 "take_profit" 的成交（即只匹配止损成交）

    注意 ``SIGNAL_TAKE_PROFIT = "take_profit"``（小写），角色名需与常量一致。
    """
    fills = ctx.state.fills if hasattr(ctx, "state") else []
    if not fills:
        return None
    last_fill = fills[-1]

    risk_role = getattr(ctx, "risk_role", None)
    if risk_role == "take_profit":
        if "take_profit" not in last_fill.reason:
            return None
    elif risk_role == "stop_loss":
        if "take_profit" in last_fill.reason:
            return None

    bar_dt = getattr(ctx.bar, "datetime", None)
    if bar_dt is None:
        return None

    bar_ts = datetime.fromtimestamp(bar_dt / 1000) if isinstance(bar_dt, (int, float)) else bar_dt

    try:
        fill_ts = datetime.fromisoformat(str(last_fill.timestamp))
    except (ValueError, TypeError):
        return None

    return (bar_ts - fill_ts).total_seconds() / 60.0  # type: ignore[no-any-return]


def _profit_abs(ctx: Any, config: Any) -> float | None:
    """浮盈点数；没有浮盈时返回 0。"""
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if pos is None or not pos.direction:
        return None
    if pos.direction == "long":
        return max(ctx.bar.close - pos.entry_price, 0.0)  # type: ignore[no-any-return]
    return max(pos.entry_price - ctx.bar.close, 0.0)  # type: ignore[no-any-return]


def _profit_pct(ctx: Any, config: Any) -> float | None:
    """浮盈比例；没有浮盈时返回 0。"""
    profit_abs = _profit_abs(ctx, config)
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if profit_abs is None or pos is None or pos.entry_price == 0:
        return None
    return profit_abs / pos.entry_price  # type: ignore[no-any-return]


def _loss_abs(ctx: Any, config: Any) -> float | None:
    """浮亏点数；没有浮亏时返回 0。"""
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if pos is None or not pos.direction:
        return None
    if pos.direction == "long":
        return max(pos.entry_price - ctx.bar.close, 0.0)  # type: ignore[no-any-return]
    return max(ctx.bar.close - pos.entry_price, 0.0)  # type: ignore[no-any-return]


def _loss_pct(ctx: Any, config: Any) -> float | None:
    """浮亏比例；没有浮亏时返回 0。"""
    loss_abs = _loss_abs(ctx, config)
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if loss_abs is None or pos is None or pos.entry_price == 0:
        return None
    return loss_abs / pos.entry_price  # type: ignore[no-any-return]


def _peak_profit(ctx: Any, config: Any) -> float | None:
    """峰值收益 |highest_price - entry_price|。"""
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if pos is None or not pos.direction:
        return None
    return abs(pos.highest_price - pos.entry_price)  # type: ignore[no-any-return]


def _drawdown_pct(ctx: Any, config: Any) -> float | None:
    """回撤比例 |highest_price - close| / highest_price。"""
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if pos is None or not pos.direction or pos.highest_price == 0:
        return None
    return abs(pos.highest_price - ctx.bar.close) / pos.highest_price  # type: ignore[no-any-return]


BUILTIN_FUNCTIONS: dict[str, BuiltinFn] = {
    "cooldown": _cooldown,
    "profit_abs": _profit_abs,
    "profit_pct": _profit_pct,
    "loss_abs": _loss_abs,
    "loss_pct": _loss_pct,
    "peak_profit": _peak_profit,
    "drawdown_pct": _drawdown_pct,
}
