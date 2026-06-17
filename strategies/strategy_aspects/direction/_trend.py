"""trend_long_when_compare / trend_short_when_compare — 周期间趋势比较切面

语义：一个方向 + 两个 MetricRef 的比较 -> 一个 trend 方向理由

装饰器行为：
  - 包装 data_requirements：自动注册左右两个 MetricRef 的指标需求
  - 包装 on_bar：先评估条件写入 ctx.aspects.direction，再调用原始 on_bar
  - 在类上注册 __direction_keys__：按方向收集所有 reason name
"""

from __future__ import annotations

import functools
from typing import Any, Literal

from ...core.indicators import generate_indicator_column_name
from ..primitives import DirectionReason, MetricRef
from ._confirm import _build_indicator_requirements, _register_direction_key, _resolve_template


def _make_trend_decorator(
    direction: str,
    left: MetricRef,
    op: Literal[">", "<"],
    right: MetricRef,
    tag: str | None,
) -> Any:
    """trend 切面装饰器工厂的通用实现"""

    reason_name = tag if tag is not None else f"{left.name}_vs_{right.name}"

    def _decorator(cls: type) -> type:
        _register_direction_key(cls, direction, reason_name)

        # ── 包装 data_requirements：自动注册左右指标需求 ──
        original_dr = cls.data_requirements  # type: ignore[attr-defined]

        @functools.wraps(original_dr)
        def _dr_wrapper(self: Any, config: Any) -> Any:
            base = original_dr(self, config)
            if base is None:
                return base
            base.merge(_build_indicator_requirements(left, config))
            base.merge(_build_indicator_requirements(right, config))
            return base

        cls.data_requirements = _dr_wrapper  # type: ignore[attr-defined]

        # ── 包装 on_bar：先评估条件写入 aspects，再调用原始 on_bar ──
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            # 评估条件
            left_view = ctx.multi.get(left.period)
            right_view = ctx.multi.get(right.period)

            left_value = None
            right_value = None

            if left_view is not None:
                left_col = generate_indicator_column_name(left.indicator.name, left.indicator.params)
                left_col = _resolve_template(left_col, state.strategy_config)
                left_value = left_view.indicator(left_col, -1)

            if right_view is not None:
                right_col = generate_indicator_column_name(right.indicator.name, right.indicator.params)
                right_col = _resolve_template(right_col, state.strategy_config)
                right_value = right_view.indicator(right_col, -1)

            if left_value is not None and right_value is not None:
                # 写入左右指标值到 diagnostics
                ctx.aspects.diagnostics[left.name] = left_value
                ctx.aspects.diagnostics[right.name] = right_value
                satisfied = (left_value > right_value) if op == ">" else (left_value < right_value)
                if satisfied:
                    reason = DirectionReason(
                        role="trend",
                        name=reason_name,
                        detail={
                            "left": left.name,
                            "left_value": left_value,
                            "op": op,
                            "right": right.name,
                            "right_value": right_value,
                        },
                    )
                    side = ctx.aspects.direction.long if direction == "long" else ctx.aspects.direction.short
                    side.trend.append(reason)

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator


def trend_long_when_compare(
    left: MetricRef,
    op: Literal[">", "<"],
    right: MetricRef,
    *,
    tag: str | None = None,
) -> Any:
    """周期间趋势比较切面 — 满足条件时向 ctx.aspects.direction.long.trend 追加理由"""
    return _make_trend_decorator("long", left, op, right, tag)


def trend_short_when_compare(
    left: MetricRef,
    op: Literal[">", "<"],
    right: MetricRef,
    *,
    tag: str | None = None,
) -> Any:
    """周期间趋势比较切面 — 满足条件时向 ctx.aspects.direction.short.trend 追加理由"""
    return _make_trend_decorator("short", left, op, right, tag)
