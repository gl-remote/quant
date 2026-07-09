"""DSL 指标需求构造工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.indicators import IndicatorSpec
from .primitives import MetricRef
from .templates import resolve_template_value

if TYPE_CHECKING:
    from ..runtime.requirements import DataRequirements


def build_indicator_requirements(metric: MetricRef, config: Any) -> DataRequirements:
    """从 MetricRef 构建 DataRequirements，解析模板参数和窗口。"""
    from ..runtime.requirements import DataRequirements, PeriodRequirements

    resolved_params = {key: resolve_template_value(value, config) for key, value in metric.indicator.params.items()}
    resolved_window = resolve_template_value(metric.indicator.window, config)
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
