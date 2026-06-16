"""confirm_long_when / confirm_short_when — 指标阈值确认切面

语义：一个方向 + 一个 MetricRef + 一个判断条件 -> 一个 confirm 方向理由

装饰器行为：
  - 包装 data_requirements：自动注册 MetricRef 对应的指标需求
  - 包装 on_bar：先评估条件写入 ctx.aspects.direction，再调用原始 on_bar
  - 在类上注册 __direction_keys__：按方向收集所有 reason name
"""

from __future__ import annotations

import functools
import re
from typing import Any, Literal

from ..primitives import DirectionReason, MetricRef


def _resolve_template(value: Any, config: Any) -> Any:
    """解析模板值，支持完整模板和部分模板。

    完整模板：'{sma_short}' -> config.sma_short（如 10）
    部分模板：'sma_{sma_short}' -> 'sma_10'
    """
    if not isinstance(value, str):
        return value
    # 完整模板：整个字符串就是 {xxx}
    full_match = re.match(r"^\{(\w+)\}$", value)
    if full_match:
        return getattr(config, full_match.group(1))
    # 部分模板：字符串中包含 {xxx}
    if "{" in value:

        def _replace(m: re.Match) -> str:
            return str(getattr(config, m.group(1)))

        return re.sub(r"\{(\w+)\}", _replace, value)
    return value


def _resolve_threshold(threshold: float | str, config: Any) -> float:
    """解析阈值：字符串从 config 取值，数值直接返回"""
    if isinstance(threshold, str):
        return float(getattr(config, threshold))
    return float(threshold)


def _build_indicator_requirements(metric: MetricRef, config: Any) -> Any:
    """从 MetricRef 构建 IndicatorRequirements，解析模板值"""
    from ...runtime.requirements import DataRequirements, IndicatorRequirements, PeriodRequirements

    resolved_params = {k: _resolve_template(v, config) for k, v in metric.indicator.params.items()}
    resolved_window = _resolve_template(metric.indicator.window, config)
    if isinstance(resolved_window, str):
        resolved_window = int(resolved_window)

    return DataRequirements(
        periods={
            metric.period: PeriodRequirements(lookback_bars=int(resolved_window) + 1),
        },
        indicators={
            metric.period: [
                IndicatorRequirements(
                    name=metric.indicator.name,
                    params=resolved_params,
                    window=int(resolved_window),
                )
            ],
        },
    )


def _register_direction_key(cls: type, direction: str, name: str) -> None:
    """向类的 __direction_keys__ 注册一个 reason name"""
    keys: dict[str, set[str]] | None = getattr(cls, "__direction_keys__", None)
    if keys is None:
        keys = {"long": set(), "short": set()}
        cls.__direction_keys__ = keys  # type: ignore[attr-defined]
    keys[direction].add(name)


def _make_confirm_decorator(
    direction: str,
    metric: MetricRef,
    op: Literal[">", "<"],
    threshold: float | str,
    tag: str | None,
) -> Any:
    """confirm 切面装饰器工厂的通用实现"""

    reason_name = tag if tag is not None else metric.name

    def _decorator(cls: type) -> type:
        _register_direction_key(cls, direction, reason_name)

        # ── 包装 data_requirements：自动注册指标需求 ──
        original_dr = cls.data_requirements  # type: ignore[attr-defined]

        @functools.wraps(original_dr)
        def _dr_wrapper(self: Any, config: Any) -> Any:
            base = original_dr(self, config)
            if base is None:
                return base
            extra = _build_indicator_requirements(metric, config)
            base.merge(extra)
            return base

        cls.data_requirements = _dr_wrapper  # type: ignore[attr-defined]

        # ── 包装 on_bar：先评估条件写入 aspects，再调用原始 on_bar ──
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            # 评估条件
            period_view = ctx.multi.get(metric.period)
            if period_view is not None:
                col = metric.indicator.column
                # 模板列名需要解析
                resolved_col = _resolve_template(col, state.strategy_config)
                value = period_view.indicator(resolved_col, -1)
                if value is not None:
                    resolved_threshold = _resolve_threshold(threshold, state.strategy_config)
                    satisfied = (value > resolved_threshold) if op == ">" else (value < resolved_threshold)
                    # 写入指标值到 diagnostics
                    ctx.aspects.diagnostics[metric.name] = value
                    if satisfied:
                        reason = DirectionReason(
                            role="confirm",
                            name=reason_name,
                            detail={
                                "metric": metric.name,
                                "value": value,
                                "op": op,
                                "threshold": resolved_threshold,
                            },
                        )
                        side = ctx.aspects.direction.long if direction == "long" else ctx.aspects.direction.short
                        side.confirm.append(reason)

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator


def confirm_long_when(
    metric: MetricRef,
    op: Literal[">", "<"],
    threshold: float | str,
    *,
    tag: str | None = None,
) -> Any:
    """指标阈值确认切面 — 满足条件时向 ctx.aspects.direction.long.confirm 追加理由"""
    return _make_confirm_decorator("long", metric, op, threshold, tag)


def confirm_short_when(
    metric: MetricRef,
    op: Literal[">", "<"],
    threshold: float | str,
    *,
    tag: str | None = None,
) -> Any:
    """指标阈值确认切面 — 满足条件时向 ctx.aspects.direction.short.confirm 追加理由"""
    return _make_confirm_decorator("short", metric, op, threshold, tag)
