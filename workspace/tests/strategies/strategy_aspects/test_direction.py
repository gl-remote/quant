"""DSL 装饰器单元测试

覆盖:
  - confirm_long_when: satisfied、not_satisfied、missing、tag、string_threshold、keys
  - confirm_short_when: satisfied、keys
  - trend_long_when_compare: satisfied、not_satisfied、left_missing、right_missing、tag、keys
  - trend_short_when_compare: satisfied
  - 多装饰器叠加: keys_merged、all_reasons
  - data_requirements 自动合并: confirm_merges、trend_merges
  - diagnostics 自动写入
  - periods 自动注册
"""

from dataclasses import dataclass
from datetime import datetime

from strategies import Bar, State
from strategies.strategy_aspects import (
    KDJ,
    MACD,
    SMA,
    at,
    confirm_long_when,
    confirm_short_when,
    trend_long_when_compare,
    trend_short_when_compare,
)

# --------------------------
# 辅助类型
# --------------------------


@dataclass
class _TestParams:
    """测试用策略配置"""

    sma_short: int = 10
    sma_long: int = 40
    kdj_oversold: float = 20.0
    kdj_overbought: float = 80.0


class _MockBar:
    def __init__(self, close: float):
        self.close = close


class _MockPeriodView:
    """模拟 PeriodDataView — 支持设置指标值"""

    def __init__(self):
        self._values: dict[str, float] = {}

    def set_indicator(self, col: str, value: float):
        self._values[col] = value

    def indicator(self, col: str, idx: int):
        return self._values.get(col)


def _make_ctx(
    indicators: dict[str, dict[str, float]] | None = None,
):
    """创建测试用 BarContext"""
    from strategies.runtime.requirements import BarContext

    bar = Bar(symbol="TEST", datetime=datetime(2024, 1, 1), open=100, high=101, low=99, close=100, volume=1000)
    multi: dict[str, _MockPeriodView] = {}
    if indicators:
        for period, values in indicators.items():
            view = _MockPeriodView()
            for col, val in values.items():
                view.set_indicator(col, val)
            multi[period] = view
    return BarContext(symbol="TEST", bar=bar, multi=multi, events=[])  # type: ignore[arg-type]


def _make_state() -> State:
    return State(
        symbol="TEST",
        period="1m",
        strategy_config=_TestParams(),
        capital=100000.0,
        contract_size=10,
    )


# --------------------------
# confirm 切面测试
# --------------------------


class TestConfirmLongWhen:
    """测试 confirm_long_when"""

    def test_satisfied_writes_confirm(self):
        """指标满足阈值时写入 long.confirm"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}})

        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 1
        assert ctx.aspects.direction.long.confirm[0].name == "macd_1m"
        assert ctx.aspects.direction.long.confirm[0].role == "confirm"
        assert ctx.aspects.direction.long.confirm[0].detail["value"] == 0.5

    def test_not_satisfied_no_reason(self):
        """指标不满足阈值时不写入 reason"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": -0.5}})
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 0

    def test_missing_indicator_no_reason(self):
        """指标缺失时不写入 reason"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({"1m": {}})  # 没有 macd 列
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 0

    def test_missing_period_no_reason(self):
        """周期缺失时不写入 reason"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({})  # 没有 1m 周期
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 0

    def test_custom_tag(self):
        """自定义 tag 作为 reason name"""

        @confirm_long_when(at(MACD, "1m"), ">", 0, tag="my_macd")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}})
        state = _make_state()
        strat.on_bar(state, ctx)

        assert ctx.aspects.direction.long.confirm[0].name == "my_macd"

    def test_string_threshold_from_config(self):
        """字符串阈值从 strategy_config 取值"""

        @confirm_long_when(at(KDJ, "1m"), "<", "kdj_oversold")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({"1m": {"1m_kdj_3_3_9": 15.0}})
        state = _make_state()  # kdj_oversold = 20.0
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 1
        assert ctx.aspects.direction.long.confirm[0].detail["threshold"] == 20.0

    def test_direction_keys_registered(self):
        """__direction_keys__ 自动注册"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        @confirm_long_when(at(MACD, "5m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        assert _S.__direction_keys__["long"] == {"macd_1m", "macd_5m"}
        assert _S.__direction_keys__["short"] == set()


class TestConfirmShortWhen:
    """测试 confirm_short_when"""

    def test_satisfied_writes_confirm(self):
        """指标满足阈值时写入 short.confirm"""

        @confirm_short_when(at(MACD, "1m"), "<", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": -0.5}})
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.short.confirm) == 1
        assert ctx.aspects.direction.short.confirm[0].name == "macd_1m"

    def test_direction_keys_registered(self):
        """__direction_keys__ 注册到 short"""

        @confirm_short_when(at(MACD, "1m"), "<", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        assert _S.__direction_keys__["short"] == {"macd_1m"}
        assert _S.__direction_keys__["long"] == set()


# --------------------------
# trend 切面测试
# --------------------------


class TestTrendLongWhenCompare:
    """测试 trend_long_when_compare"""

    def test_satisfied_writes_trend(self):
        """比较条件满足时写入 long.trend"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {"5m_sma_10": 100.0},
                "15m": {"15m_sma_40": 99.0},
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.trend) == 1
        assert ctx.aspects.direction.long.trend[0].name == "sma_5m_vs_sma_15m"
        assert ctx.aspects.direction.long.trend[0].role == "trend"
        assert ctx.aspects.direction.long.trend[0].detail["left_value"] == 100.0
        assert ctx.aspects.direction.long.trend[0].detail["right_value"] == 99.0

    def test_not_satisfied_no_reason(self):
        """比较条件不满足时不写入 reason"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {"5m_sma_10": 99.0},
                "15m": {"15m_sma_40": 100.0},
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.trend) == 0

    def test_left_missing_no_reason(self):
        """左侧指标缺失时不写入 reason"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {},  # 缺失 sma_10
                "15m": {"15m_sma_40": 99.0},
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.trend) == 0

    def test_right_missing_no_reason(self):
        """右侧指标缺失时不写入 reason"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {"5m_sma_10": 100.0},
                "15m": {},  # 缺失 sma_40
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.trend) == 0

    def test_custom_tag(self):
        """自定义 tag 作为 reason name"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"), tag="ma_cross")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {"5m_sma_10": 100.0},
                "15m": {"15m_sma_40": 99.0},
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert ctx.aspects.direction.long.trend[0].name == "ma_cross"

    def test_direction_keys_registered(self):
        """__direction_keys__ 自动注册"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        assert _S.__direction_keys__["long"] == {"sma_5m_vs_sma_15m"}
        assert _S.__direction_keys__["short"] == set()


class TestTrendShortWhenCompare:
    """测试 trend_short_when_compare"""

    def test_satisfied_writes_trend(self):
        """比较条件满足时写入 short.trend"""

        @trend_short_when_compare(at(SMA(10), "5m"), "<", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {"5m_sma_10": 99.0},
                "15m": {"15m_sma_40": 100.0},
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.short.trend) == 1
        assert ctx.aspects.direction.short.trend[0].name == "sma_5m_vs_sma_15m"


# --------------------------
# 多装饰器叠加测试
# --------------------------


class TestMultipleDecorators:
    """测试多个装饰器叠加"""

    def test_direction_keys_merged(self):
        """多个同方向装饰器的 key 自动合并"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        @confirm_long_when(at(MACD, "5m"), ">", 0)
        @confirm_short_when(at(MACD, "1m"), "<", 0)
        @confirm_short_when(at(MACD, "5m"), "<", 0)
        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        @trend_short_when_compare(at(SMA(10), "5m"), "<", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        assert _S.__direction_keys__["long"] == {"sma_5m_vs_sma_15m", "macd_1m", "macd_5m"}
        assert _S.__direction_keys__["short"] == {"sma_5m_vs_sma_15m", "macd_1m", "macd_5m"}

    def test_all_reasons_written(self):
        """多个装饰器同时写入 aspects"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        @confirm_long_when(at(MACD, "5m"), ">", 0)
        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "1m": {"1m_macd_12_9_26": 0.5},
                "5m": {"5m_macd_12_9_26": 0.3, "5m_sma_10": 100.0},
                "15m": {"15m_sma_40": 99.0},
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        long_keys = ctx.aspects.direction.long.keys
        assert "macd_1m" in long_keys
        assert "macd_5m" in long_keys
        assert "sma_5m_vs_sma_15m" in long_keys

        # 检查分桶
        assert len(ctx.aspects.direction.long.trend) == 1
        assert len(ctx.aspects.direction.long.confirm) == 2


# --------------------------
# data_requirements 合并测试
# --------------------------


class TestDataRequirementsMerge:
    """测试建议型切面自动合并 data_requirements"""

    def test_confirm_merges_indicator(self):
        """confirm 切面自动注册指标需求"""

        from strategies import DataRequirements, PeriodRequirements

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return DataRequirements(
                    periods={"1m": PeriodRequirements(lookback_bars=50)},
                    indicators={},
                )

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        reqs = strat.data_requirements(_TestParams())
        assert reqs is not None
        assert "1m" in reqs.indicators
        macd_inds = [i for i in reqs.indicators["1m"] if i.name == "macd"]
        assert len(macd_inds) == 1
        assert macd_inds[0].params == {"fast": 12, "slow": 26, "signal": 9}

    def test_trend_merges_both_indicators(self):
        """trend 切面自动注册左右两个指标需求"""

        from strategies import DataRequirements, PeriodRequirements

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return DataRequirements(
                    periods={"5m": PeriodRequirements(lookback_bars=50), "15m": PeriodRequirements(lookback_bars=50)},
                    indicators={},
                )

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        reqs = strat.data_requirements(_TestParams())
        assert reqs is not None
        assert "5m" in reqs.indicators
        assert "15m" in reqs.indicators
        sma_5m = [i for i in reqs.indicators["5m"] if i.name == "sma"]
        sma_15m = [i for i in reqs.indicators["15m"] if i.name == "sma"]
        assert len(sma_5m) == 1
        assert len(sma_15m) == 1


# --------------------------
# diagnostics 自动写入测试
# --------------------------


class TestDiagnosticsAutoWrite:
    """测试切面评估时自动将指标值写入 ctx.aspects.diagnostics"""

    def test_confirm_writes_metric_value_to_diagnostics(self):
        """confirm 切面评估时自动将指标值写入 diagnostics[metric.name]"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}})
        state = _make_state()
        strat.on_bar(state, ctx)

        assert ctx.aspects.diagnostics["macd_1m"] == 0.5

    def test_confirm_writes_metric_value_even_if_not_satisfied(self):
        """confirm 切面条件不满足时仍然写入 diagnostics"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": -0.5}})
        state = _make_state()
        strat.on_bar(state, ctx)

        # 条件不满足，但指标值仍写入 diagnostics
        assert ctx.aspects.diagnostics["macd_1m"] == -0.5
        assert len(ctx.aspects.direction.long.confirm) == 0

    def test_confirm_no_diagnostics_when_period_missing(self):
        """confirm 切面周期缺失时不写入 diagnostics"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx({})
        state = _make_state()
        strat.on_bar(state, ctx)

        assert "macd_1m" not in ctx.aspects.diagnostics

    def test_trend_writes_left_right_to_diagnostics(self):
        """trend 切面评估时自动将左右指标值写入 diagnostics"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {"5m_sma_10": 100.0},
                "15m": {"15m_sma_40": 99.0},
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert ctx.aspects.diagnostics["sma_5m"] == 100.0
        assert ctx.aspects.diagnostics["sma_15m"] == 99.0

    def test_trend_writes_diagnostics_even_if_not_satisfied(self):
        """trend 切面条件不满足时仍然写入左右指标值"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {"5m_sma_10": 98.0},
                "15m": {"15m_sma_40": 99.0},
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert ctx.aspects.diagnostics["sma_5m"] == 98.0
        assert ctx.aspects.diagnostics["sma_15m"] == 99.0
        assert len(ctx.aspects.direction.long.trend) == 0

    def test_trend_no_diagnostics_when_one_side_missing(self):
        """trend 切面任一侧指标缺失时不写入 diagnostics"""

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "5m": {"5m_sma_10": 100.0},
                "15m": {},  # 缺失 sma_40
            }
        )
        state = _make_state()
        strat.on_bar(state, ctx)

        assert "sma_5m" not in ctx.aspects.diagnostics
        assert "sma_15m" not in ctx.aspects.diagnostics


# --------------------------
# periods 自动注册测试
# --------------------------


class TestPeriodsAutoRegistration:
    """测试切面在 data_requirements 中自动注册 period（含 lookback_bars）"""

    def test_confirm_registers_period_with_lookback(self):
        """confirm 切面自动注册 period，lookback_bars = window + 1"""

        from strategies import DataRequirements

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return DataRequirements(periods={}, indicators={})

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        reqs = strat.data_requirements(_TestParams())
        assert reqs is not None
        # MACD 的 window=35，所以 lookback_bars = 35 + 1 = 36
        assert "1m" in reqs.periods
        assert reqs.periods["1m"].lookback_bars == 36

    def test_confirm_period_lookback_max_on_merge(self):
        """confirm 切面与已有 period 合并时取 lookback_bars 最大值"""

        from strategies import DataRequirements, PeriodRequirements

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return DataRequirements(
                    periods={"1m": PeriodRequirements(lookback_bars=50)},
                    indicators={},
                )

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        reqs = strat.data_requirements(_TestParams())
        assert reqs is not None
        # 原有 50 vs 新注册 36，取最大值 50
        assert reqs.periods["1m"].lookback_bars == 50

    def test_trend_registers_both_periods(self):
        """trend 切面自动注册左右两个 period"""

        from strategies import DataRequirements

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return DataRequirements(periods={}, indicators={})

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        reqs = strat.data_requirements(_TestParams())
        assert reqs is not None
        # SMA(10) window=10, lookback_bars=11; SMA(40) window=40, lookback_bars=41
        assert "5m" in reqs.periods
        assert "15m" in reqs.periods
        assert reqs.periods["5m"].lookback_bars == 11
        assert reqs.periods["15m"].lookback_bars == 41

    def test_trend_period_lookback_max_on_merge(self):
        """trend 切面与已有 period 合并时取 lookback_bars 最大值"""

        from strategies import DataRequirements, PeriodRequirements

        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return DataRequirements(
                    periods={
                        "5m": PeriodRequirements(lookback_bars=5),
                        "15m": PeriodRequirements(lookback_bars=100),
                    },
                    indicators={},
                )

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        reqs = strat.data_requirements(_TestParams())
        assert reqs is not None
        # 5m: max(5, 11) = 11; 15m: max(100, 41) = 100
        assert reqs.periods["5m"].lookback_bars == 11
        assert reqs.periods["15m"].lookback_bars == 100
