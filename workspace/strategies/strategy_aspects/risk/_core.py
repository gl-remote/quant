"""risk 切面共享工具 — 统一工厂 + ATR 注册

提取所有 risk 切面公共的包装逻辑：
- data_requirements 包装（主要是 ATR 指标自动注册）
- on_bar 包装中的 diagnostics 写入
- 通用谓词触发模式
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from strategies.strategy_aspects.primitives import RiskReason, RiskRole

T = TypeVar("T", bound=type)


# ── diagnostics 共享工具 ────────────────────────────────────


def _write_position_diagnostics(ctx: Any, state: Any, close: float) -> None:
    """写入持仓相关的 diagnostics 字段（entry_price, highest_price, lowest_price, current_close）"""
    ctx.aspects.diagnostics["entry_price"] = state.position.entry_price
    ctx.aspects.diagnostics["highest_price"] = state.position.highest_price
    ctx.aspects.diagnostics["lowest_price"] = state.position.lowest_price
    ctx.aspects.diagnostics["current_close"] = close


# ── data_requirements 包装工具 ──────────────────────────────


def _wrap_data_requirements(cls: type, builder: Callable[[Any], Any]) -> None:
    """包装类的 data_requirements，在原始基础上合并 builder 产生的额外需求。"""
    original_dr = cls.data_requirements  # type: ignore[attr-defined]

    @functools.wraps(original_dr)
    def _dr_wrapper(self: Any, config: Any) -> Any:
        base = original_dr(self, config)
        if base is None:
            return base
        extra = builder(config)
        if extra is not None:
            base.merge(extra)
        return base

    cls.data_requirements = _dr_wrapper  # type: ignore[attr-defined]


def _atr_data_requirements_builder(period: str) -> Callable[[Any], Any]:
    """返回一个 builder，为 data_requirements 合并 ATR 指标需求。"""

    def _build(config: Any) -> Any:
        from ...core.indicators import IndicatorSpec, atr_func
        from ...runtime.requirements import DataRequirements, PeriodRequirements

        return DataRequirements(
            periods={
                period: PeriodRequirements(lookback_bars=config.atr_period + 1),
            },
            indicators={
                period: [
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


# ── on_bar 统一工厂 ─────────────────────────────────────────


def _exit_aspect(
    role: RiskRole,
    reason_name: str,
    trigger_fn: Callable[[Any, Any, Any], tuple[bool, dict[str, Any]] | None],
) -> Callable[[T], T]:
    """出场切面统一工厂 — 有持仓时触发条件判断，满足则写入对应 exit 桶。

    :param role: ``"take_profit"`` 或 ``"stop_loss"``，决定写入哪个 RiskActionBucket。
    :param reason_name: 触发时 RiskReason 的 name（如 ``SIGNAL_TAKE_PROFIT``）。
    :param trigger_fn: 触发判断函数，签名为 ``(state, ctx, direction) -> (bool, detail) | None``。
        返回 ``None`` 表示数据不足，不触发；返回 ``(True, detail)`` 时写入理由。
    """

    def _decorator(cls: T) -> T:
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            direction = state.position.direction

            if direction:
                result = trigger_fn(state, ctx, direction)
                if result is not None and result[0]:
                    getattr(ctx.aspects.risk, role).exit.append(
                        RiskReason(
                            role=role,
                            name=reason_name,
                            detail=result[1],
                        )
                    )

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator


def _entry_block_aspect(
    role: RiskRole,
    reason_name: str,
    trigger_fn: Callable[[Any, Any], tuple[bool, dict[str, Any]] | None],
) -> Callable[[T], T]:
    """入场阻断切面统一工厂 — 空仓时触发条件判断，满足则写入对应 entry_block 桶。

    :param role: ``"take_profit"`` 或 ``"stop_loss"``，决定写入哪个 RiskActionBucket。
    :param reason_name: 触发时 RiskReason 的 name（如 ``SIGNAL_TRADE_COOLDOWN``）。
    :param trigger_fn: 触发判断函数，签名为 ``(state, ctx) -> (bool, detail) | None``。
        返回 ``None`` 表示数据不足，不触发；返回 ``(True, detail)`` 时写入理由。
    """

    def _decorator(cls: T) -> T:
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            if not state.position.direction and state.fills:
                result = trigger_fn(state, ctx)
                if result is not None and result[0]:
                    getattr(ctx.aspects.risk, role).entry_block.append(
                        RiskReason(
                            role=role,
                            name=reason_name,
                            detail=result[1],
                        )
                    )

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator


# ── 共享工具 ────────────────────────────────────────────────


def _parse_fill_time(timestamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        return None
