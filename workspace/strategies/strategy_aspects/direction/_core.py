"""方向 DSL 核心实现 — 统一装饰器工厂 + 字符串 DSL 接口

装饰器行为：
  - 包装 data_requirements：自动注册谓词涉及的全部 MetricRef 指标需求。
  - 包装 on_bar：先评估谓词写入 ctx.aspects，再调用原始 on_bar。
  - 在类上注册 __direction_keys__：按方向收集所有 reason name。
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from typing import Any, Literal, Protocol, TypeVar

from ...core.indicators import generate_indicator_column_name
from ..primitives import DirectionReason, DirectionRole, MetricRef

T = TypeVar("T", bound=type)

_Direction = Literal["long", "short"]
_Op = Literal[">", "<"]


# ── 共享工具 ────────────────────────────────────────────────


def _resolve_template(value: Any, config: Any) -> Any:
    """解析模板值，支持完整模板和部分模板。

    完整模板：``'{sma_short}' -> config.sma_short``（如 10）
    部分模板：``'sma_{sma_short}' -> 'sma_10'``（保留前缀，仅替换 ``{...}`` 部分）

    非字符串原样返回。
    """
    if not isinstance(value, str):
        return value
    full_match = re.match(r"^\{(\w+)\}$", value)
    if full_match:
        return getattr(config, full_match.group(1))
    if "{" in value:

        def _replace(m: re.Match[str]) -> str:
            return str(getattr(config, m.group(1)))

        return re.sub(r"\{(\w+)\}", _replace, value)
    return value


def _build_indicator_requirements(metric: MetricRef, config: Any) -> Any:
    """从 MetricRef 构建 DataRequirements，解析模板值"""
    from ...core.indicators import IndicatorSpec
    from ...runtime.requirements import DataRequirements, PeriodRequirements

    resolved_params = {k: _resolve_template(v, config) for k, v in metric.indicator.params.items()}
    resolved_window = _resolve_template(metric.indicator.window, config)
    if isinstance(resolved_window, str):
        resolved_window = int(resolved_window)

    return DataRequirements(
        periods={metric.period: PeriodRequirements(lookback_bars=int(resolved_window) + 1)},
        indicators={
            metric.period: [
                IndicatorSpec(
                    name=metric.indicator.name,
                    params=resolved_params,
                    window=int(resolved_window),
                    func=metric.indicator.func,
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


def _read_metric(ctx: Any, metric: MetricRef, config: Any) -> Any:
    """读取某个 MetricRef 在当前 bar(-1) 上的指标值，周期缺失则返回 None"""
    view = ctx.multi.get(metric.period)
    if view is None:
        return None
    col = generate_indicator_column_name(metric.indicator.name, metric.indicator.params, period=metric.period)
    return view.indicator(_resolve_template(col, config), -1)


# ── 谓词 Protocol ───────────────────────────────────────────


class _Predicate(Protocol):
    """方向条件谓词 — 封装指标需求、默认理由名与评估逻辑"""

    @property
    def metrics(self) -> tuple[MetricRef, ...]:
        """谓词涉及的全部 MetricRef，用于自动注册指标需求"""
        ...

    @property
    def default_name(self) -> str:
        """未显式指定 tag 时的默认 reason name"""
        ...

    def evaluate(self, ctx: Any, config: Any) -> tuple[bool, dict[str, Any]] | None:
        """评估条件并写入 diagnostics；数据不足返回 None，否则返回 (是否满足, detail)"""
        ...


# ── 统一装饰器工厂 ──────────────────────────────────────────


def _direction_aspect(
    role: DirectionRole, direction: _Direction, predicate: _Predicate, tag: str | None
) -> Callable[[T], T]:
    """方向切面装饰器工厂 — role × direction × predicate 三轴的唯一实现。

    :param role: 理由角色，``"confirm"`` 或 ``"trend"``。
    :param direction: 方向，``"long"`` 或 ``"short"``。
    :param predicate: 条件谓词（满足 ``_Predicate`` Protocol 的对象）。
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
                base.merge(_build_indicator_requirements(metric, config))
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
