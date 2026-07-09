"""方向 DSL 核心实现 — 统一装饰器工厂 + 字符串 DSL 接口

装饰器行为：
  - 包装 data_requirements：自动注册谓词涉及的全部 MetricRef 指标需求。
  - 包装 on_bar：先评估谓词写入 ctx.aspects，再调用原始 on_bar。
  - 在类上注册 __direction_keys__：按方向收集所有 reason name。
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, Literal, TypeVar

from ..predicate import AspectPredicate
from ..primitives import DirectionReason, DirectionRole
from ..requirements import build_indicator_requirements

T = TypeVar("T", bound=type)

_Direction = Literal["long", "short"]


# ── 共享工具 ────────────────────────────────────────────────


def _register_direction_key(cls: type, direction: str, name: str) -> None:
    """向类的 __direction_keys__ 注册一个 reason name。"""
    keys: dict[str, set[str]] | None = getattr(cls, "__direction_keys__", None)
    if keys is None:
        keys = {"long": set(), "short": set()}
        cls.__direction_keys__ = keys  # type: ignore[attr-defined]
    keys[direction].add(name)


# ── 统一装饰器工厂 ──────────────────────────────────────────


def _direction_aspect(
    role: DirectionRole, direction: _Direction, predicate: AspectPredicate, tag: str | None
) -> Callable[[T], T]:
    """方向切面装饰器工厂 — role × direction × predicate 三轴的唯一实现。

    :param role: 理由角色，``"confirm"`` 或 ``"trend"``。
    :param direction: 方向，``"long"`` 或 ``"short"``。
    :param predicate: 条件谓词（满足 ``AspectPredicate`` Protocol 的对象）。
    :param tag: 自定义理由名；``None`` 时回退到 ``predicate.default_name``。
    :returns: 类装饰器，包装目标类的 ``data_requirements`` 与 ``on_bar``。
    """

    reason_name = tag if tag is not None else predicate.default_name

    def _decorator(cls: T) -> T:
        _register_direction_key(cls, direction, reason_name)

        # ── 包装 data_requirements：自动注册谓词涉及的指标需求 ──
        original_dr = cls.data_requirements  # type: ignore[attr-defined]

        @functools.wraps(original_dr)
        def _dr_wrapper(self: Any, config: Any) -> Any:
            base = original_dr(self, config)
            if base is None:
                return base
            for metric in predicate.metrics:
                base.merge(build_indicator_requirements(metric, config))
            return base

        cls.data_requirements = _dr_wrapper  # type: ignore[attr-defined]

        # ── 包装 on_bar：先评估谓词写入 aspects，再调用原始 on_bar ──
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            # ctx 不自带 state 引用，内置函数（如 cooldown()、profit_abs()）需要
            # 通过 ctx.state 访问持仓/成交数据，在求值前显式注入。
            ctx.state = state
            result = predicate.evaluate(ctx, state.strategy_config)
            if result is not None and result[0]:
                reason = DirectionReason(role=role, name=reason_name, detail=result[1])
                side = ctx.aspects.direction.long if direction == "long" else ctx.aspects.direction.short
                getattr(side, role).append(reason)
            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator


# ── 对外接口：4 个字符串 DSL 装饰器 ────────────────────────


def confirm_long(expr: str, *, tag: str | None = None) -> Callable[[T], T]:
    """做多确认切面 — 表达式满足时向 ctx.aspects.direction.long.confirm 追加理由。

    :param expr: DSL 表达式，如 ``"macd@1m > 0"``。
    :param tag: 自定义理由名，默认由表达式自动生成。
    """
    from .._parser import parse_expr

    return _direction_aspect("confirm", "long", parse_expr(expr), tag)


def confirm_short(expr: str, *, tag: str | None = None) -> Callable[[T], T]:
    """做空确认切面 — 表达式满足时向 ctx.aspects.direction.short.confirm 追加理由。"""
    from .._parser import parse_expr

    return _direction_aspect("confirm", "short", parse_expr(expr), tag)


def trend_long(expr: str, *, tag: str | None = None) -> Callable[[T], T]:
    """做多趋势切面 — 表达式满足时向 ctx.aspects.direction.long.trend 追加理由。"""
    from .._parser import parse_expr

    return _direction_aspect("trend", "long", parse_expr(expr), tag)


def trend_short(expr: str, *, tag: str | None = None) -> Callable[[T], T]:
    """做空趋势切面 — 表达式满足时向 ctx.aspects.direction.short.trend 追加理由。"""
    from .._parser import parse_expr

    return _direction_aspect("trend", "short", parse_expr(expr), tag)
