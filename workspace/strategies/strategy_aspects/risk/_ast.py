"""risk 切面 AST 节点 — 可复用的风控条件求值器

每个节点封装一种风控条件的判断逻辑，由 ``_core.py`` 中的切面工厂统一调用。
未来可在此基座上扩展通用表达式 DSL（值引用 + 运算符重载）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from common.constants import (
    SIGNAL_TAKE_PROFIT,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)

from strategies.core.indicators import generate_indicator_column_name


class RiskNode(Protocol):
    """风控条件节点协议 — 所有 AST 节点必须实现 evaluate"""

    def evaluate(
        self,
        state: Any,
        ctx: Any,
        direction: str | None = None,
        role: str | None = None,
    ) -> tuple[bool, dict[str, Any]] | None:
        """判断条件是否满足。

        :param role: 由切面工厂传入 ``"take_profit"`` 或 ``"stop_loss"``，
            节点内部据此读取对应 config 字段。
        :return: ``(True, detail)`` 如果触发；``None`` 如果未触发或数据不足。
        """
        ...

    def data_requirements_builder(self) -> Callable[[Any], Any] | None:
        """返回 ``(config) -> DataRequirements`` builder，或 ``None`` 如果不需要额外指标。"""
        return None


# ── 固定比例节点 ────────────────────────────────────────────


@dataclass
class FixedRatioNode:
    """固定比例止盈止损节点"""

    ratio: float | None = None

    def data_requirements_builder(self) -> Any | None:
        return None

    def evaluate(
        self,
        state: Any,
        ctx: Any,
        direction: str | None = None,
        role: str | None = None,
    ) -> tuple[bool, dict[str, Any]] | None:
        config = state.strategy_config
        entry_price = state.position.entry_price
        close = ctx.bar.close

        is_tp = role == "take_profit"
        ratio = (
            self.ratio if self.ratio is not None else (config.take_profit_ratio if is_tp else config.stop_loss_ratio)
        )

        if is_tp:
            if direction == TRADE_DIRECTION_LONG:
                triggered = close >= entry_price * (1 + ratio)
            else:
                triggered = close <= entry_price * (1 - ratio)
        else:
            if direction == TRADE_DIRECTION_LONG:
                triggered = close <= entry_price * (1 - ratio)
            else:
                triggered = close >= entry_price * (1 + ratio)

        if triggered:
            return True, {
                "type": "fixed_ratio",
                "direction": direction,
                "entry_price": entry_price,
                "current_close": close,
                f"{role}_ratio": float(ratio),
                "highest_price": state.position.highest_price,
                "lowest_price": state.position.lowest_price,
            }
        return None


# ── ATR 节点 ────────────────────────────────────────────────


@dataclass
class AtrNode:
    """ATR 止盈止损节点"""

    period: str = "15m"

    def evaluate(
        self,
        state: Any,
        ctx: Any,
        direction: str | None = None,
        role: str | None = None,
    ) -> tuple[bool, dict[str, Any]] | None:
        config = state.strategy_config
        entry_price = state.position.entry_price
        close = ctx.bar.close

        period_view = ctx.multi.get(self.period)
        if period_view is None:
            return None

        atr_col = generate_indicator_column_name("atr", {"period": config.atr_period}, period=self.period)
        atr_value = period_view.indicator(atr_col, -1)
        if atr_value is None or atr_value <= 0:
            return None

        if role == "take_profit":
            multiplier = config.atr_take_profit_multiplier
            target = atr_value * multiplier
            if direction == TRADE_DIRECTION_LONG:
                triggered = close > entry_price + target
            else:
                triggered = close < entry_price - target
        else:
            multiplier = config.atr_stop_loss_multiplier
            max_loss = atr_value * multiplier
            if direction == TRADE_DIRECTION_LONG:
                triggered = close < entry_price - max_loss
            else:
                triggered = close > entry_price + max_loss

        if triggered:
            return True, {
                "type": "atr",
                "direction": direction,
                "entry_price": entry_price,
                "current_close": close,
                "atr_value": float(atr_value),
                f"atr_{role}_multiplier": float(multiplier),
            }
        return None

    def data_requirements_builder(self) -> Callable[[Any], Any] | None:
        from ...core.indicators import IndicatorSpec, atr_func
        from ...runtime.requirements import DataRequirements, PeriodRequirements

        def _build(config: Any) -> Any:
            return DataRequirements(
                periods={
                    self.period: PeriodRequirements(lookback_bars=config.atr_period + 1),
                },
                indicators={
                    self.period: [
                        IndicatorSpec(
                            name="atr",
                            params={"period": config.atr_period},
                            func=atr_func,
                            window=config.atr_period,
                        )
                    ],
                },
            )

        return _build


# ── 回撤止盈节点 ────────────────────────────────────────────


@dataclass
class TrailingNode:
    """回撤止盈节点（峰值回撤触发）"""

    period: str = "15m"

    def evaluate(
        self,
        state: Any,
        ctx: Any,
        direction: str | None = None,
        role: str | None = None,
    ) -> tuple[bool, dict[str, Any]] | None:
        config = state.strategy_config
        entry_price = state.position.entry_price
        close = ctx.bar.close

        period_view = ctx.multi.get(self.period)
        if period_view is None:
            return None

        atr_col = generate_indicator_column_name("atr", {"period": config.atr_period}, period=self.period)
        atr_value = period_view.indicator(atr_col, -1)
        if atr_value is None or atr_value <= 0:
            return None

        peak_price = state.position.highest_price if direction == TRADE_DIRECTION_LONG else state.position.lowest_price

        if peak_price <= 0:
            return None

        activation_threshold = atr_value * config.trailing_activation_atr

        if direction == TRADE_DIRECTION_LONG:
            if peak_price <= entry_price + activation_threshold:
                return None
            triggered = (peak_price - close) / peak_price > config.trailing_drawdown_ratio
        elif direction == TRADE_DIRECTION_SHORT:
            if peak_price >= entry_price - activation_threshold:
                return None
            triggered = (close - peak_price) / peak_price > config.trailing_drawdown_ratio
        else:
            triggered = False

        if triggered:
            return True, {
                "type": "trailing_stop",
                "direction": direction,
                "entry_price": entry_price,
                "current_close": close,
                "peak_price": peak_price,
                "atr_value": float(atr_value),
                "trailing_activation_atr": float(config.trailing_activation_atr),
                "trailing_drawdown_ratio": float(config.trailing_drawdown_ratio),
            }
        return None

    def data_requirements_builder(self) -> Callable[[Any], Any] | None:
        from ...core.indicators import IndicatorSpec, atr_func
        from ...runtime.requirements import DataRequirements, PeriodRequirements

        def _build(config: Any) -> Any:
            return DataRequirements(
                periods={
                    self.period: PeriodRequirements(lookback_bars=config.atr_period + 1),
                },
                indicators={
                    self.period: [
                        IndicatorSpec(
                            name="atr",
                            params={"period": config.atr_period},
                            func=atr_func,
                            window=config.atr_period,
                        )
                    ],
                },
            )

        return _build


# ── 冷却期节点 ──────────────────────────────────────────────


@dataclass
class CooldownNode:
    """交易冷却期节点"""

    minutes: int

    def data_requirements_builder(self) -> Any | None:
        return None

    def evaluate(
        self,
        state: Any,
        ctx: Any,
        direction: str | None = None,
        role: str | None = None,
    ) -> tuple[bool, dict[str, Any]] | None:
        last_fill = state.fills[-1]

        if role == "take_profit":
            if SIGNAL_TAKE_PROFIT not in last_fill.reason:
                return None
        else:
            if SIGNAL_TAKE_PROFIT in last_fill.reason:
                return None

        last_fill_time = self._parse_fill_time(last_fill.timestamp)
        if last_fill_time is None:
            return None

        elapsed = ctx.bar.datetime - last_fill_time
        cooldown = timedelta(minutes=self.minutes)
        if elapsed < cooldown:
            return True, {
                "cooldown_minutes": float(self.minutes),
                "elapsed_seconds": elapsed.total_seconds(),
                "remaining_seconds": (cooldown - elapsed).total_seconds(),
            }
        return None

    @staticmethod
    def _parse_fill_time(timestamp: str) -> datetime | None:
        try:
            return datetime.fromisoformat(timestamp)
        except ValueError:
            return None
