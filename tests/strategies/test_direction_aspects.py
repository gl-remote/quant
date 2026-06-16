"""建议型切面 DSL 单元测试

覆盖:
  - DirectionReason.key 生成
  - MetricRef.name 生成
  - DirectionSideAdvice.reasons / keys 生成
  - BarContext 默认带有空 StrategyAspects
  - confirm_long_when / confirm_short_when:
    - 自动合并 data_requirements
    - 每个装饰器最多写入一个 reason
    - 指标满足阈值时写入对应方向的 confirm 桶
    - 指标缺失时不写入 reason
  - trend_long_when_compare / trend_short_when_compare:
    - 自动合并左右指标需求
    - 比较条件满足时写入对应方向的 trend 桶
    - 任一侧指标缺失时不写入 reason
    - 自动生成稳定 name
  - __direction_keys__ 自动注册
  - MA 策略:
    - 原有 long entry 行为保持
    - 原有 short entry 行为保持
"""

from dataclasses import dataclass
from datetime import datetime

from strategies import Bar, State, StrategyAspects
from strategies.runtime.requirements import BarContext
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
from strategies.strategy_aspects.primitives import (
    DirectionAdvice,
    DirectionReason,
    DirectionSideAdvice,
    IndicatorSpec,
    MetricRef,
)

# --------------------------
# 基础数据结构测试
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


class TestMetricRef:
    """测试 MetricRef"""

    def test_name_format(self):
        spec = IndicatorSpec(name="macd", column="macd_12_9_26", params={"fast": 12}, window=35)
        ref = MetricRef(period="1m", indicator=spec)
        assert ref.name == "macd_1m"

    def test_at_function(self):
        spec = IndicatorSpec(name="sma", column="sma_10", params={"period": 10}, window=10)
        ref = at(spec, "5m")
        assert ref.period == "5m"
        assert ref.name == "sma_5m"


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


class TestDirectionAdvice:
    """测试 DirectionAdvice"""

    def test_default_empty(self):
        advice = DirectionAdvice()
        assert advice.long.keys == set()
        assert advice.short.keys == set()


class TestBarContextAspects:
    """测试 BarContext 默认带有空 StrategyAspects"""

    def test_default_aspects(self):
        bar = Bar(symbol="TEST", datetime=datetime(2024, 1, 1), open=100, high=101, low=99, close=100, volume=1000)
        ctx = BarContext(symbol="TEST", bar=bar, multi={}, events=[])
        assert isinstance(ctx.aspects, StrategyAspects)
        assert ctx.aspects.direction.long.keys == set()
        assert ctx.aspects.direction.short.keys == set()


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
) -> BarContext:
    """创建测试用 BarContext"""
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
        ctx = _make_ctx({"1m": {"macd_12_9_26": 0.5}})
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
        ctx = _make_ctx({"1m": {"macd_12_9_26": -0.5}})
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
        ctx = _make_ctx({"1m": {"macd_12_9_26": 0.5}})
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
        ctx = _make_ctx({"1m": {"kdj_3_3_9": 15.0}})
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
        ctx = _make_ctx({"1m": {"macd_12_9_26": -0.5}})
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
                "5m": {"sma_10": 100.0},
                "15m": {"sma_40": 99.0},
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
                "5m": {"sma_10": 99.0},
                "15m": {"sma_40": 100.0},
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
                "15m": {"sma_40": 99.0},
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
                "5m": {"sma_10": 100.0},
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
                "5m": {"sma_10": 100.0},
                "15m": {"sma_40": 99.0},
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
                "5m": {"sma_10": 99.0},
                "15m": {"sma_40": 100.0},
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
                "1m": {"macd_12_9_26": 0.5},
                "5m": {"macd_12_9_26": 0.3, "sma_10": 100.0},
                "15m": {"sma_40": 99.0},
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
