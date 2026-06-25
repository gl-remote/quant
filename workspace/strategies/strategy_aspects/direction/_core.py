"""方向 DSL 核心实现 — 谓词 + 统一装饰器工厂 + 扁平公开接口

设计要点：
  - role(confirm/trend)、direction(long/short)、predicate(when/when_compare)
    三轴正交，本质都是「读数 + 谓词 -> 追加一个方向理由」。
  - 三轴差异收敛为参数：role 决定落桶字段、direction 决定多空、predicate
    决定如何评估并注册指标需求。
  - 对外暴露 8 个一行式函数（role × direction × predicate），全部委托给
    唯一的 _direction_aspect 工厂，零重复包装逻辑。

装饰器行为（与历史实现一致）：
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

    完整模板：'{sma_short}' -> config.sma_short（如 10）
    部分模板：'sma_{sma_short}' -> 'sma_10'
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


def _resolve_threshold(threshold: float | str, config: Any) -> float:
    """解析阈值：字符串从 config 取值，数值直接返回"""
    if isinstance(threshold, str):
        return float(getattr(config, threshold))
    return float(threshold)


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


# ── 谓词抽象 ────────────────────────────────────────────────


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


class _ThresholdPredicate:
    """when — 指标读数与阈值（常量或 config 字段）比较"""

    def __init__(self, metric: MetricRef, op: _Op, threshold: float | str) -> None:
        self.metric = metric
        self.op = op
        self.threshold = threshold

    @property
    def metrics(self) -> tuple[MetricRef, ...]:
        return (self.metric,)

    @property
    def default_name(self) -> str:
        return self.metric.name

    def evaluate(self, ctx: Any, config: Any) -> tuple[bool, dict[str, Any]] | None:
        value = _read_metric(ctx, self.metric, config)
        if value is None:
            return None
        ctx.aspects.diagnostics[self.metric.name] = value
        threshold = _resolve_threshold(self.threshold, config)
        satisfied = (value > threshold) if self.op == ">" else (value < threshold)
        detail = {"metric": self.metric.name, "value": value, "op": self.op, "threshold": threshold}
        return satisfied, detail


class _ComparePredicate:
    """when_compare — 两个指标读数之间比较（可跨周期）"""

    def __init__(self, left: MetricRef, op: _Op, right: MetricRef) -> None:
        self.left = left
        self.op = op
        self.right = right

    @property
    def metrics(self) -> tuple[MetricRef, ...]:
        return (self.left, self.right)

    @property
    def default_name(self) -> str:
        return f"{self.left.name}_vs_{self.right.name}"

    def evaluate(self, ctx: Any, config: Any) -> tuple[bool, dict[str, Any]] | None:
        left_value = _read_metric(ctx, self.left, config)
        right_value = _read_metric(ctx, self.right, config)
        if left_value is None or right_value is None:
            return None
        ctx.aspects.diagnostics[self.left.name] = left_value
        ctx.aspects.diagnostics[self.right.name] = right_value
        satisfied = (left_value > right_value) if self.op == ">" else (left_value < right_value)
        detail = {
            "left": self.left.name,
            "left_value": left_value,
            "op": self.op,
            "right": self.right.name,
            "right_value": right_value,
        }
        return satisfied, detail


# ── 统一装饰器工厂 ──────────────────────────────────────────


def _direction_aspect(
    role: DirectionRole, direction: _Direction, predicate: _Predicate, tag: str | None
) -> Callable[[T], T]:
    """方向切面装饰器工厂 — role × direction × predicate 三轴的唯一实现。

    :param role: 理由角色，``"confirm"`` 或 ``"trend"``。决定理由追加到
        ``DirectionSideAdvice`` 的哪个桶（``side.confirm`` 或 ``side.trend``），
        并写入 ``DirectionReason.role``。仅用于分桶与诊断，不改变评估逻辑。
    :param direction: 方向，``"long"`` 或 ``"short"``。决定理由写入
        ``ctx.aspects.direction.long`` 还是 ``.short``，以及注册到
        ``__direction_keys__`` 的哪个方向。
    :param predicate: 条件谓词（``_ThresholdPredicate`` 或 ``_ComparePredicate``）。
        提供待注册的指标需求（``metrics``）、默认理由名（``default_name``）
        与评估逻辑（``evaluate``）。
    :param tag: 自定义理由名（reason name）；``None`` 时回退到
        ``predicate.default_name``。

    tag 的影响范围（仅影响"理由名"，不影响是否/如何触发）：

    - 决定 ``DirectionReason.name``（即 ``.key``），进而决定该理由在
      ``ctx.aspects.direction.{side}.keys`` 中的字符串。
    - 决定注册进 ``cls.__direction_keys__[direction]`` 的名字——策略用
      ``__direction_keys__`` 做子集判断时比对的就是这个名字。
    - 决定 ``flush_direction_diagnostics`` 展平到 diagnostics 时的理由 key。
    - **不影响**：是否满足条件、指标读取、以及指标值写入
      ``diagnostics[metric.name]``（该 key 恒为 ``metric.name``，与 tag 无关）。

    同一方向上若多个切面产生相同 tag，会在 ``__direction_keys__`` 的 set 中
    去重为一个 key；需要区分时应为每个切面指定不同 tag。

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
            result = predicate.evaluate(ctx, state.strategy_config)
            if result is not None and result[0]:
                reason = DirectionReason(role=role, name=reason_name, detail=result[1])
                side = ctx.aspects.direction.long if direction == "long" else ctx.aspects.direction.short
                getattr(side, role).append(reason)
            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator


# ── 对外接口：role × direction × predicate 共 8 个组合 ──────


def confirm_long_when(
    metric: MetricRef, op: _Op, threshold: float | str, *, tag: str | None = None
) -> Callable[[T], T]:
    """confirm 阈值确认切面 — 满足时向 ctx.aspects.direction.long.confirm 追加理由"""
    return _direction_aspect("confirm", "long", _ThresholdPredicate(metric, op, threshold), tag)


def confirm_short_when(
    metric: MetricRef, op: _Op, threshold: float | str, *, tag: str | None = None
) -> Callable[[T], T]:
    """confirm 阈值确认切面 — 满足时向 ctx.aspects.direction.short.confirm 追加理由"""
    return _direction_aspect("confirm", "short", _ThresholdPredicate(metric, op, threshold), tag)


def trend_long_when(metric: MetricRef, op: _Op, threshold: float | str, *, tag: str | None = None) -> Callable[[T], T]:
    """trend 阈值确认切面 — 满足时向 ctx.aspects.direction.long.trend 追加理由"""
    return _direction_aspect("trend", "long", _ThresholdPredicate(metric, op, threshold), tag)


def trend_short_when(metric: MetricRef, op: _Op, threshold: float | str, *, tag: str | None = None) -> Callable[[T], T]:
    """trend 阈值确认切面 — 满足时向 ctx.aspects.direction.short.trend 追加理由"""
    return _direction_aspect("trend", "short", _ThresholdPredicate(metric, op, threshold), tag)


def confirm_long_when_compare(
    left: MetricRef, op: _Op, right: MetricRef, *, tag: str | None = None
) -> Callable[[T], T]:
    """confirm 指标比较切面 — 满足时向 ctx.aspects.direction.long.confirm 追加理由"""
    return _direction_aspect("confirm", "long", _ComparePredicate(left, op, right), tag)


def confirm_short_when_compare(
    left: MetricRef, op: _Op, right: MetricRef, *, tag: str | None = None
) -> Callable[[T], T]:
    """confirm 指标比较切面 — 满足时向 ctx.aspects.direction.short.confirm 追加理由"""
    return _direction_aspect("confirm", "short", _ComparePredicate(left, op, right), tag)


def trend_long_when_compare(left: MetricRef, op: _Op, right: MetricRef, *, tag: str | None = None) -> Callable[[T], T]:
    """trend 指标比较切面 — 满足时向 ctx.aspects.direction.long.trend 追加理由"""
    return _direction_aspect("trend", "long", _ComparePredicate(left, op, right), tag)


def trend_short_when_compare(left: MetricRef, op: _Op, right: MetricRef, *, tag: str | None = None) -> Callable[[T], T]:
    """trend 指标比较切面 — 满足时向 ctx.aspects.direction.short.trend 追加理由"""
    return _direction_aspect("trend", "short", _ComparePredicate(left, op, right), tag)
