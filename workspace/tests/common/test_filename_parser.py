"""FilenameTemplateParser 单元测试

覆盖:
    - 标准模板 (symbol/provider/interval) 反向解析
    - symbol 含 `.` 时按下游字段严格集合正确切分
    - 未提供 field_patterns 的默认非贪婪行为
    - 匹配失败返回 None
"""

from __future__ import annotations

from common.filename_parser import FilenameTemplateParser


class TestFilenameTemplateParser:
    def _make(self) -> FilenameTemplateParser:
        return FilenameTemplateParser(
            "{symbol}.{provider}.{interval}.csv",
            field_patterns={
                "symbol": r".+",
                "provider": "tqsdk|akshare",
                "interval": "1m|5m|15m|1d",
            },
        )

    def test_parse_symbol_with_dot(self):
        parser = self._make()
        result = parser.parse("DCE.m2509.tqsdk.1m.csv")
        assert result == {"symbol": "DCE.m2509", "provider": "tqsdk", "interval": "1m"}

    def test_parse_symbol_without_dot(self):
        parser = self._make()
        result = parser.parse("m2509.akshare.5m.csv")
        assert result == {"symbol": "m2509", "provider": "akshare", "interval": "5m"}

    def test_parse_returns_none_on_unknown_interval(self):
        parser = self._make()
        assert parser.parse("DCE.m2509.tqsdk.7m.csv") is None

    def test_parse_returns_none_on_unknown_provider(self):
        parser = self._make()
        assert parser.parse("DCE.m2509.unknown.1m.csv") is None

    def test_parse_returns_none_on_wrong_extension(self):
        parser = self._make()
        assert parser.parse("DCE.m2509.tqsdk.1m.txt") is None

    def test_format_roundtrip(self):
        parser = self._make()
        filename = parser.format(symbol="DCE.m2509", provider="tqsdk", interval="1m")
        assert filename == "DCE.m2509.tqsdk.1m.csv"
        assert parser.parse(filename) == {
            "symbol": "DCE.m2509",
            "provider": "tqsdk",
            "interval": "1m",
        }

    def test_fields_property(self):
        parser = self._make()
        assert parser.fields == ("symbol", "provider", "interval")

    def test_default_pattern_is_non_greedy(self):
        parser = FilenameTemplateParser("{name}_{ext}")
        # 默认 `.+?` 使得首个 `_` 之前的部分归入 name
        assert parser.parse("foo_bar_baz") == {"name": "foo", "ext": "bar_baz"}

    def test_repeated_field_uses_backreference(self):
        parser = FilenameTemplateParser(
            "{sym}/{sym}.csv",
            field_patterns={"sym": r"[A-Za-z0-9]+"},
        )
        assert parser.parse("abc/abc.csv") == {"sym": "abc"}
        assert parser.parse("abc/def.csv") is None
