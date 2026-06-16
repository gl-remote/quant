"""指标定义单元测试

覆盖:
  - MACD: name、column、params、window
  - KDJ: name、column、params、window
  - SMA() 工厂函数: 不同参数生成不同 IndicatorSpec
  - at() 函数与指标组合
"""

from strategies.strategy_aspects.indicators import KDJ, MACD, SMA
from strategies.strategy_aspects.primitives import MetricRef, at

# --------------------------
# MACD 测试
# --------------------------


class TestMACD:
    """测试 MACD 指标定义"""

    def test_name(self):
        assert MACD.name == "macd"

    def test_column(self):
        assert MACD.column == "macd_12_9_26"

    def test_params(self):
        assert MACD.params == {"fast": 12, "slow": 26, "signal": 9}

    def test_window(self):
        assert MACD.window == 35


# --------------------------
# KDJ 测试
# --------------------------


class TestKDJ:
    """测试 KDJ 指标定义"""

    def test_name(self):
        assert KDJ.name == "kdj"

    def test_column(self):
        assert KDJ.column == "kdj_3_3_9"

    def test_params(self):
        assert KDJ.params == {"n": 9, "k_period": 3, "d_period": 3}

    def test_window(self):
        assert KDJ.window == 9


# --------------------------
# SMA 工厂函数测试
# --------------------------


class TestSMAFactory:
    """测试 SMA() 工厂函数"""

    def test_sma_10(self):
        spec = SMA(10)
        assert spec.name == "sma"
        assert spec.column == "sma_10"
        assert spec.params == {"period": 10}
        assert spec.window == 10

    def test_sma_40(self):
        spec = SMA(40)
        assert spec.name == "sma"
        assert spec.column == "sma_40"
        assert spec.params == {"period": 40}
        assert spec.window == 40

    def test_different_params_produce_different_specs(self):
        """不同参数生成不同的 IndicatorSpec"""
        spec_10 = SMA(10)
        spec_40 = SMA(40)
        assert spec_10 != spec_40
        assert spec_10.column != spec_40.column
        assert spec_10.window != spec_40.window

    def test_sma_with_template_value(self):
        """SMA 支持模板值"""
        spec = SMA("{sma_short}")
        assert spec.column == "sma_{sma_short}"
        assert spec.params == {"period": "{sma_short}"}
        assert spec.window == "{sma_short}"


# --------------------------
# at() 与指标组合测试
# --------------------------


class TestAtWithIndicators:
    """测试 at() 函数与指标组合"""

    def test_at_macd(self):
        ref = at(MACD, "1m")
        assert isinstance(ref, MetricRef)
        assert ref.period == "1m"
        assert ref.name == "macd_1m"

    def test_at_kdj(self):
        ref = at(KDJ, "5m")
        assert isinstance(ref, MetricRef)
        assert ref.period == "5m"
        assert ref.name == "kdj_5m"

    def test_at_sma(self):
        ref = at(SMA(10), "5m")
        assert isinstance(ref, MetricRef)
        assert ref.period == "5m"
        assert ref.name == "sma_5m"
        assert ref.indicator.column == "sma_10"

    def test_at_sma_different_periods(self):
        """同一指标在不同周期产生不同 MetricRef"""
        ref_5m = at(SMA(10), "5m")
        ref_15m = at(SMA(10), "15m")
        assert ref_5m.name == "sma_5m"
        assert ref_15m.name == "sma_15m"

    def test_indicator_spec_is_frozen(self):
        """IndicatorSpec 是 frozen dataclass"""
        try:
            MACD.name = "other"  # type: ignore[misc]
            raise AssertionError("Should raise AttributeError")
        except AttributeError:
            pass
