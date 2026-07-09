"""DSL 模板值解析工具。"""

from __future__ import annotations

import re
from typing import Any


def resolve_template_value(value: Any, config: Any) -> Any:
    """解析 DSL 模板值，支持完整模板和部分模板。"""
    if not isinstance(value, str):
        return value
    full_match = re.match(r"^\{(\w+)\}$", value)
    if full_match:
        return getattr(config, full_match.group(1), value)
    if "{" in value:

        def _replace(match: re.Match[str]) -> str:
            return str(getattr(config, match.group(1)))

        return re.sub(r"\{(\w+)\}", _replace, value)
    return value
