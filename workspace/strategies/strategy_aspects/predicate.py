"""DSL 谓词协议。"""

from __future__ import annotations

from typing import Any, Protocol

from .primitives import MetricRef


class AspectPredicate(Protocol):
    """切面条件谓词 — 封装指标需求、默认理由名与评估逻辑。"""

    @property
    def metrics(self) -> tuple[MetricRef, ...]:
        """谓词涉及的全部 MetricRef，用于自动注册指标需求。"""
        ...

    @property
    def default_name(self) -> str:
        """未显式指定 tag 时的默认 reason name。"""
        ...

    def evaluate(self, ctx: Any, config: Any) -> tuple[bool, dict[str, Any]] | None:
        """评估条件；数据不足返回 None，否则返回 (是否满足, detail)。"""
        ...
