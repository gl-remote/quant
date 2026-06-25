"""risk 切面共享工具 — 统一工厂 + AST 节点集成

提取所有 risk 切面公共的包装逻辑：
- data_requirements 包装（AST 节点自动注册额外指标需求）
- on_bar 包装中的 diagnostics 写入 + AST 求值
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from common.constants import SIGNAL_STOP_LOSS, SIGNAL_TAKE_PROFIT, SIGNAL_TRADE_COOLDOWN

from strategies.strategy_aspects.primitives import RiskReason, RiskRole

from ._ast import RiskNode

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


# ── on_bar 统一工厂 ─────────────────────────────────────────


def _exit_aspect(
    role: RiskRole,
    reason_name: str,
    node: RiskNode,
) -> Callable[[T], T]:
    """出场切面统一工厂 — 有持仓时触发 AST 节点求值，满足则写入对应 exit 桶。"""

    def _decorator(cls: T) -> T:
        # 注册 data_requirements（如果节点需要）
        builder = node.data_requirements_builder()
        if builder is not None:
            _wrap_data_requirements(cls, builder)

        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            direction = state.position.direction

            if direction:
                close = ctx.bar.close
                _write_position_diagnostics(ctx, state, close)
                result = node.evaluate(state, ctx, direction, role=role)
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
    node: RiskNode,
) -> Callable[[T], T]:
    """入场阻断切面统一工厂 — 空仓时触发 AST 节点求值，满足则写入对应 entry_block 桶。"""

    def _decorator(cls: T) -> T:
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            if not state.position.direction and state.fills:
                result = node.evaluate(state, ctx, None, role=role)
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


# ── 公共切面函数 ────────────────────────────────────────────


def exit_take_profit(node: RiskNode) -> Callable[[T], T]:
    """止盈出场切面 — 有持仓时评估节点条件，触发则写入 ``risk.take_profit.exit``。"""
    return _exit_aspect("take_profit", SIGNAL_TAKE_PROFIT, node)


def exit_stop_loss(node: RiskNode) -> Callable[[T], T]:
    """止损出场切面 — 有持仓时评估节点条件，触发则写入 ``risk.stop_loss.exit``。"""
    return _exit_aspect("stop_loss", SIGNAL_STOP_LOSS, node)


def entry_block_take_profit(node: RiskNode) -> Callable[[T], T]:
    """止盈后入场阻断切面 — 空仓时评估节点条件，触发则写入 ``risk.take_profit.entry_block``。"""
    return _entry_block_aspect("take_profit", SIGNAL_TRADE_COOLDOWN, node)


def entry_block_stop_loss(node: RiskNode) -> Callable[[T], T]:
    """止损后入场阻断切面 — 空仓时评估节点条件，触发则写入 ``risk.stop_loss.entry_block``。"""
    return _entry_block_aspect("stop_loss", SIGNAL_TRADE_COOLDOWN, node)
