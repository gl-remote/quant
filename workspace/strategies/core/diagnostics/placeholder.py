"""临时占位诊断工具 — 让既有策略跑通 decision_payload 非空校验。

placeholder_diagnostics 是一个临时脚手架，不是业务实现：
- 占位值没有任何分析含义，不应被报告 / 清算消费；
- 不走任何真实逻辑路径，只判断“层是否为空”，为空才填占位；
- 仅当某层为空时才写入占位，已填充的真实诊断不会被覆盖；
- 临时性：某策略实现了真实的 alpha / risk / execution 诊断后，
  应移除该策略 on_bar 上的本装饰器。

本模块独立于诊断层契约（alpha/risk/execution）所在的包入口，
以避免与 core.types 形成导入环。
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from .alpha import AlphaDiagnostics
from .execution import ExecutionDiagnostics
from .risk import RiskDiagnostics

if TYPE_CHECKING:
    from ...runtime.requirements import BarContext
    from ..state import State
    from ..types import Signal

T = TypeVar("T")

_PLACEHOLDER: dict[str, Any] = {"placeholder": True}


def placeholder_diagnostics(on_bar: Callable[..., Signal]) -> Callable[..., Signal]:
    """为带 action 的信号补齐占位的 alpha / risk / execution 诊断层。"""

    @wraps(on_bar)
    def wrapper(self: Any, state: State[T], ctx: BarContext) -> Signal:
        signal = on_bar(self, state, ctx)
        if signal.action:
            if signal.alpha.is_empty():
                signal.alpha = AlphaDiagnostics(fields=dict(_PLACEHOLDER))
            if signal.risk.is_empty():
                signal.risk = RiskDiagnostics(fields=dict(_PLACEHOLDER))
            if signal.execution.is_empty():
                signal.execution = ExecutionDiagnostics(fields=dict(_PLACEHOLDER))
        return signal

    return wrapper
