"""基于模板的文件名解析器 — 从 `filename_template` 反向解析出 symbol/provider/interval 等字段。

设计目标：
    - 完全由 `filename_template` 驱动，避免硬编码字符串分割
    - 支持字段约束（`field_patterns`），确保带 `.` 的字段（如 `DCE.m2509`）可以正确切分
    - 解析失败时返回 None，由调用方负责回退与日志

示例::

    parser = FilenameTemplateParser(
        "{symbol}.{provider}.{interval}.csv",
        field_patterns={
            "provider": "tqsdk|akshare",
            "interval": "1m|5m|1d",
        },
    )
    parser.parse("DCE.m2509.tqsdk.1m.csv")
    # {"symbol": "DCE.m2509", "provider": "tqsdk", "interval": "1m"}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FilenameTemplateParser:
    """基于 `str.format` 风格模板的文件名反向解析器

    Args:
        template: 文件名模板，如 ``"{symbol}.{provider}.{interval}.csv"``
        field_patterns: 字段名 → 正则片段。未指定的字段默认使用 ``.+?``（非贪婪）。
            对存在 `.` 等分隔符字符的字段（如 ``symbol``），务必给出下游字段
            的严格集合，以便正则能从右侧锚定切分。
    """

    template: str
    field_patterns: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._fields = _extract_field_names(self.template)
        self._regex = _build_regex(self.template, self._fields, self.field_patterns)

    @property
    def fields(self) -> tuple[str, ...]:
        """模板中的字段名，按出现顺序返回"""
        return self._fields

    def parse(self, filename: str) -> dict[str, str] | None:
        """反向解析文件名；匹配失败返回 None。"""
        match = self._regex.match(filename)
        if match is None:
            return None
        return match.groupdict()

    def format(self, **values: str) -> str:
        """正向格式化，等价于 `template.format(**values)`。"""
        return self.template.format(**values)


_FIELD_RE = re.compile(r"\{(\w+)\}")


def _extract_field_names(template: str) -> tuple[str, ...]:
    """从模板中按顺序提取字段名，允许重复出现（如 `{symbol}` 出现两次）。"""
    return tuple(_FIELD_RE.findall(template))


def _build_regex(
    template: str,
    fields: tuple[str, ...],
    field_patterns: dict[str, str],
) -> re.Pattern[str]:
    """把 `str.format` 风格模板转成命名组正则。

    - 模板中的非字段部分做 `re.escape`
    - 每个字段用 `(?P<name>pattern)`（首次出现）或反向引用 `(?P=name)`（重复出现）
    - 未提供 pattern 的字段默认 `.+?`
    - 整体锚定行首与行尾，避免部分匹配
    """
    parts: list[str] = ["^"]
    seen: set[str] = set()
    cursor = 0
    for match in _FIELD_RE.finditer(template):
        parts.append(re.escape(template[cursor : match.start()]))
        name = match.group(1)
        if name in seen:
            parts.append(f"(?P={name})")
        else:
            pattern = field_patterns.get(name, ".+?")
            parts.append(f"(?P<{name}>{pattern})")
            seen.add(name)
        cursor = match.end()
    parts.append(re.escape(template[cursor:]))
    parts.append("$")
    return re.compile("".join(parts))
