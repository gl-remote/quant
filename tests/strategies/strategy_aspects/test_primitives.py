"""基础数据结构单元测试

覆盖:
  - DirectionReason: key 生成、frozen、detail
  - MetricRef: name 格式、at 函数
  - DirectionSideAdvice: empty、reasons、keys
  - DirectionAdvice: default empty
  - BarContext 默认带有空 StrategyAspects
  - StrategyAspects.flush_direction_diagnostics()
"""

from datetime import datetime

from strategies import Bar, StrategyAspects
from strategies.core.indicators import IndicatorSpec
from strategies.runtime.requirements import BarContext
from strategies.strategy_aspects.primitives import (
    DirectionAdvice,
    DirectionReason,
    DirectionSideAdvice,
    MetricRef,
    at,
)

# --------------------------
# DirectionReason 测试
# --------------------------


class TestDirectionReason:
    """测试 DirectionReason"""

    def test_key_equals_name(self):
        reason = DirectionReason(role="confirm", name="macd_1m")
        assert reason.key == "macd_1m"

    def test_key_equals_name_trend(self):
        reason = DirectionReason(role="trend", name="sma_5m_vs_sma_15m")
        assert reason.key == "sma_5m_vs_sma_15m"

    def test_frozen(self):
        reason = DirectionReason(role="confirm", name="macd_1m")
        try:
            reason.name = "other"  # type: ignore[misc]
            raise AssertionError("Should raise AttributeError")
        except AttributeError:
            pass

    def test_detail_default_empty(self):
        reason = DirectionReason(role="confirm", name="macd_1m")
        assert reason.detail == {}

    def test_detail_with_values(self):
        reason = DirectionReason(role="confirm", name="macd_1m", detail={"value": 0.5, "threshold": 0})
        assert reason.detail["value"] == 0.5


# --------------------------
# MetricRef 测试
# --------------------------


class TestMetricRef:
    """测试 MetricRef"""

    def test_name_format(self):
        spec = IndicatorSpec(name="macd", params={"fast": 12}, window=35)
        ref = MetricRef(period="1m", indicator=spec)
        assert ref.name == "macd_1m"

    def test_at_function(self):
        spec = IndicatorSpec(name="sma", params={"period": 10}, window=10)
        ref = at(spec, "5m")
        assert ref.period == "5m"
        assert ref.name == "sma_5m"


# --------------------------
# DirectionSideAdvice 测试
# --------------------------


class TestDirectionSideAdvice:
    """测试 DirectionSideAdvice"""

    def test_empty(self):
        advice = DirectionSideAdvice()
        assert advice.reasons == []
        assert advice.keys == set()

    def test_reasons_flattens_trend_and_confirm(self):
        trend_r = DirectionReason(role="trend", name="sma_5m_vs_sma_15m")
        confirm_r = DirectionReason(role="confirm", name="macd_1m")
        advice = DirectionSideAdvice(trend=[trend_r], confirm=[confirm_r])
        assert advice.reasons == [trend_r, confirm_r]

    def test_keys_set(self):
        trend_r = DirectionReason(role="trend", name="sma_5m_vs_sma_15m")
        confirm_r = DirectionReason(role="confirm", name="macd_1m")
        advice = DirectionSideAdvice(trend=[trend_r], confirm=[confirm_r])
        assert advice.keys == {"sma_5m_vs_sma_15m", "macd_1m"}


# --------------------------
# DirectionAdvice 测试
# --------------------------


class TestDirectionAdvice:
    """测试 DirectionAdvice"""

    def test_default_empty(self):
        advice = DirectionAdvice()
        assert advice.long.keys == set()
        assert advice.short.keys == set()


# --------------------------
# BarContext 默认 StrategyAspects 测试
# --------------------------


class TestBarContextAspects:
    """测试 BarContext 默认带有空 StrategyAspects"""

    def test_default_aspects(self):
        bar = Bar(symbol="TEST", datetime=datetime(2024, 1, 1), open=100, high=101, low=99, close=100, volume=1000)
        ctx = BarContext(symbol="TEST", bar=bar, multi={}, events=[])
        assert isinstance(ctx.aspects, StrategyAspects)
        assert ctx.aspects.direction.long.keys == set()
        assert ctx.aspects.direction.short.keys == set()


# --------------------------
# flush_direction_diagnostics 测试
# --------------------------


class TestFlushDirectionDiagnostics:
    """测试 StrategyAspects.flush_direction_diagnostics() 方法"""

    def test_empty_direction(self):
        """空方向建议时写入空列表"""

        aspects = StrategyAspects()
        aspects.flush_direction_diagnostics()

        assert aspects.diagnostics["direction_long_trend"] == []
        assert aspects.diagnostics["direction_long_confirm"] == []
        assert aspects.diagnostics["direction_short_trend"] == []
        assert aspects.diagnostics["direction_short_confirm"] == []
        assert aspects.diagnostics["direction_detail"] == {}

    def test_with_long_reasons(self):
        """有 long 方向理由时正确展平"""

        aspects = StrategyAspects()
        trend_r = DirectionReason(role="trend", name="sma_cross", detail={"left": 100, "right": 99})
        confirm_r = DirectionReason(role="confirm", name="macd_above", detail={"value": 0.5})
        aspects.direction.long.trend.append(trend_r)
        aspects.direction.long.confirm.append(confirm_r)

        aspects.flush_direction_diagnostics()

        assert aspects.diagnostics["direction_long_trend"] == ["sma_cross"]
        assert aspects.diagnostics["direction_long_confirm"] == ["macd_above"]
        assert aspects.diagnostics["direction_short_trend"] == []
        assert aspects.diagnostics["direction_short_confirm"] == []
        assert "sma_cross" in aspects.diagnostics["direction_detail"]
        assert "macd_above" in aspects.diagnostics["direction_detail"]

    def test_with_short_reasons(self):
        """有 short 方向理由时正确展平"""

        aspects = StrategyAspects()
        trend_r = DirectionReason(role="trend", name="sma_cross_down", detail={"left": 99, "right": 100})
        aspects.direction.short.trend.append(trend_r)

        aspects.flush_direction_diagnostics()

        assert aspects.diagnostics["direction_short_trend"] == ["sma_cross_down"]
        assert aspects.diagnostics["direction_short_confirm"] == []

    def test_detail_contains_all_reasons(self):
        """direction_detail 包含 long 和 short 所有理由的 detail"""

        aspects = StrategyAspects()
        long_trend = DirectionReason(role="trend", name="lt", detail={"v": 1})
        long_confirm = DirectionReason(role="confirm", name="lc", detail={"v": 2})
        short_trend = DirectionReason(role="trend", name="st", detail={"v": 3})
        short_confirm = DirectionReason(role="confirm", name="sc", detail={"v": 4})
        aspects.direction.long.trend.append(long_trend)
        aspects.direction.long.confirm.append(long_confirm)
        aspects.direction.short.trend.append(short_trend)
        aspects.direction.short.confirm.append(short_confirm)

        aspects.flush_direction_diagnostics()

        detail = aspects.diagnostics["direction_detail"]
        assert detail == {"lt": {"v": 1}, "lc": {"v": 2}, "st": {"v": 3}, "sc": {"v": 4}}

    def test_preserves_existing_diagnostics(self):
        """flush 不覆盖已有的 diagnostics 键"""

        aspects = StrategyAspects()
        aspects.diagnostics["macd_1m"] = 0.5
        aspects.flush_direction_diagnostics()

        assert aspects.diagnostics["macd_1m"] == 0.5
        assert "direction_long_trend" in aspects.diagnostics
