"""指标定义单元测试

覆盖:
  - MACD: name、params、window
  - KDJ: name、params、window
  - SMA() 工厂函数: 不同参数生成不同 IndicatorSpec
"""

from strategies.core.indicators import generate_indicator_column_name
from strategies.strategy_aspects.indicators import KDJ, MACD, SMA

# --------------------------
# MACD 测试
# --------------------------


class TestMACD:
    """测试 MACD 指标定义"""

    def test_name(self):
        assert MACD.name == "macd"

    def test_column(self):
        assert generate_indicator_column_name(MACD.name, MACD.params) == "macd_12_9_26"

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
        assert generate_indicator_column_name(KDJ.name, KDJ.params) == "kdj_3_3_9"

    def test_params(self):
        assert KDJ.params == {"n": 9, "k_period": 3, "d_period": 3}

    def test_window(self):
        assert KDJ.window == 20


# --------------------------
# SMA 工厂函数测试
# --------------------------


class TestSMAFactory:
    """测试 SMA() 工厂函数"""

    def test_sma_10(self):
        spec = SMA(10)
        assert spec.name == "sma"
        assert generate_indicator_column_name(spec.name, spec.params) == "sma_10"
        assert spec.params == {"period": 10}
        assert spec.window == 10

    def test_sma_40(self):
        spec = SMA(40)
        assert spec.name == "sma"
        assert generate_indicator_column_name(spec.name, spec.params) == "sma_40"
        assert spec.params == {"period": 40}
        assert spec.window == 40

    def test_different_params_produce_different_specs(self):
        """不同参数生成不同的 IndicatorSpec"""
        spec_10 = SMA(10)
        spec_40 = SMA(40)
        assert spec_10 != spec_40
        assert generate_indicator_column_name(spec_10.name, spec_10.params) != generate_indicator_column_name(
            spec_40.name, spec_40.params
        )
        assert spec_10.window != spec_40.window

    def test_sma_with_template_value(self):
        """SMA 支持模板值"""
        spec = SMA("{sma_short}")
        assert generate_indicator_column_name(spec.name, spec.params) == "sma_{sma_short}"
        assert spec.params == {"period": "{sma_short}"}
        assert spec.window == "{sma_short}"


# --------------------------
# IndicatorSpec 不可变测试
# --------------------------


class TestIndicatorSpecFrozen:
    """IndicatorSpec 是 frozen dataclass"""

    def test_macd_is_frozen(self):
        try:
            MACD.name = "other"  # type: ignore[misc]
            raise AssertionError("Should raise AttributeError")
        except AttributeError:
            pass
