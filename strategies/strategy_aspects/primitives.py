"""DSL 基础结构和协议类型

包含建议型切面 DSL 的核心数据结构：
- DirectionReason / DirectionSideAdvice / DirectionAdvice / StrategyAspects
- MetricRef / at()
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from ..core.indicators import IndicatorSpec

DirectionRole = Literal["trend", "confirm"]


@dataclass(frozen=True)
class DirectionReason:
    """方向理由 — 由 DSL 装饰器内部生成，使用者不直接构造"""

    role: DirectionRole
    name: str
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return self.name


@dataclass
class DirectionSideAdvice:
    """某个方向上的理由集合，按 role 分桶"""

    trend: list[DirectionReason] = field(default_factory=list)
    confirm: list[DirectionReason] = field(default_factory=list)

    @property
    def reasons(self) -> list[DirectionReason]:
        return [*self.trend, *self.confirm]

    @property
    def keys(self) -> set[str]:
        return {reason.key for reason in self.reasons}


@dataclass
class DirectionAdvice:
    """方向建议 — 包含多空两个方向的理由集合"""

    long: DirectionSideAdvice = field(default_factory=DirectionSideAdvice)
    short: DirectionSideAdvice = field(default_factory=DirectionSideAdvice)


@dataclass
class StrategyAspects:
    """当前 bar 上由策略切面产生的临时建议和诊断。

    生命周期仅限本次 on_bar 调用，不应跨 bar 持久化。
    跨 bar 状态应放到 state 或未来的 state.aspect_state。
    """

    direction: DirectionAdvice = field(default_factory=DirectionAdvice)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def flush_direction_diagnostics(self) -> None:
        """将方向建议展平写入 diagnostics，供策略一次性调用。"""
        self.diagnostics["direction_long_trend"] = [r.key for r in self.direction.long.trend]
        self.diagnostics["direction_long_confirm"] = [r.key for r in self.direction.long.confirm]
        self.diagnostics["direction_short_trend"] = [r.key for r in self.direction.short.trend]
        self.diagnostics["direction_short_confirm"] = [r.key for r in self.direction.short.confirm]
        self.diagnostics["direction_detail"] = {
            r.key: r.detail for r in [*self.direction.long.reasons, *self.direction.short.reasons]
        }


@dataclass(frozen=True)
class MetricRef:
    """指标引用 — 某个周期上的某个指标"""

    period: str
    indicator: IndicatorSpec

    @property
    def name(self) -> str:
        return f"{self.indicator.name}_{self.period}"


def at(indicator: IndicatorSpec, period: str) -> MetricRef:
    """构造 MetricRef 的便捷函数"""
    return MetricRef(period=period, indicator=indicator)
