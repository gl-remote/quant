"""装饰器交叉行为测试

覆盖拦截器与建议型切面之间的交互场景：
1. 拦截器触发时建议型切面被跳过
2. 拦截器未触发时建议型切面正常执行
3. 冷却期 + 止损叠加
4. 方向建议 + 拦截器叠加 — diagnostics 完整性
5. 多个拦截器优先级
6. 建议型切面之间不互相干扰
7. data_requirements 合并 — 拦截器 + 建议型

装饰器执行顺序说明：
  Python 装饰器从下到上应用，从上到下执行。
  拦截器放在最上层（先执行），建议型切面放在下层（后执行），
  这样拦截器触发时提前返回，建议型切面不会被执行。
"""

from dataclasses import dataclass
from datetime import datetime

from strategies import Bar
from strategies.core.state import State
from strategies.core.types import Fill, StrategyPosition
from strategies.strategy_aspects import (
    MACD,
    SMA,
    at,
    confirm_long_when,
    trend_long_when_compare,
    with_atr_stop_take_profit,
    with_stop_take_profit,
    with_trade_cooldown,
)

# --------------------------
# 辅助类型
# --------------------------


@dataclass
class _TestParams:
    """测试用策略配置 — 包含止损止盈和 ATR 参数"""

    sma_short: int = 10
    sma_long: int = 40
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05
    atr_period: int = 14
    atr_stop_loss_multiplier: float = 2.0
    atr_take_profit_multiplier: float = 3.0


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
    close: float = 100.0,
    bar_dt: datetime | None = None,
):
    """创建测试用 BarContext"""
    from strategies.runtime.requirements import BarContext

    bar = Bar(
        symbol="TEST",
        datetime=bar_dt or datetime(2024, 1, 1, 12, 0),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )
    multi: dict[str, _MockPeriodView] = {}
    if indicators:
        for period, values in indicators.items():
            view = _MockPeriodView()
            for col, val in values.items():
                view.set_indicator(col, val)
            multi[period] = view
    return BarContext(symbol="TEST", bar=bar, multi=multi, events=[])  # type: ignore[arg-type]


def _make_state(
    direction: str = "",
    entry_price: float = 0.0,
    volume: float = 0,
    highest_price: float = 0.0,
    lowest_price: float = 0.0,
    fills: list[Fill] | None = None,
) -> State:
    """创建测试用 State，支持设置持仓和成交记录"""
    position = StrategyPosition(
        direction=direction,
        entry_price=entry_price,
        volume=volume,
        highest_price=highest_price,
        lowest_price=lowest_price,
    )
    return State(
        symbol="TEST",
        period="1m",
        strategy_config=_TestParams(),
        capital=100000.0,
        contract_size=10,
        position=position,
        fills=fills or [],
    )


# --------------------------
# 测试 1: 拦截器触发时建议型切面被跳过
# --------------------------


class TestInterceptorSkipsAdvisory:
    """有持仓 + 止损触发 → 拦截器提前返回，建议型切面不执行

    装饰器顺序：拦截器在上（外层先执行），建议型在下（内层后执行）。
    拦截器触发时提前返回 Signal，内层建议型切面不会被执行。
    """

    def test_stop_loss_skips_confirm(self):
        """止损触发时 confirm 切面未执行"""

        @with_stop_take_profit
        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        # 多头持仓，入场价 100，当前价 96 → 跌幅 4% > 3% 止损
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=101.0, lowest_price=96.0)
        ctx = _make_ctx({"1m": {"macd_12_9_26": 0.5}}, close=96.0)

        signal = strat.on_bar(state, ctx)

        # 返回止损信号
        assert signal is not None
        assert signal.reason == "stop_loss"
        # 建议型切面没执行，confirm 为空
        assert len(ctx.aspects.direction.long.confirm) == 0

    def test_take_profit_skips_confirm(self):
        """止盈触发时 confirm 切面未执行"""

        @with_stop_take_profit
        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        # 多头持仓，入场价 100，当前价 106 → 涨幅 6% > 5% 止盈
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=106.0, lowest_price=99.0)
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}}, close=106.0)

        signal = strat.on_bar(state, ctx)

        assert signal is not None
        assert signal.reason == "take_profit"
        assert len(ctx.aspects.direction.long.confirm) == 0


# --------------------------
# 测试 2: 拦截器未触发时建议型切面正常执行
# --------------------------


class TestInterceptorPassesThrough:
    """拦截器透传时建议型切面正常执行"""

    def test_no_position_confirm_executes(self):
        """无持仓时拦截器透传，confirm 切面正常写入"""

        @with_stop_take_profit
        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        state = _make_state()  # 无持仓
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}})

        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 1
        assert ctx.aspects.direction.long.confirm[0].name == "macd_1m"

    def test_position_no_trigger_confirm_executes(self):
        """有持仓但止损未触发时 confirm 切面正常写入"""

        @with_stop_take_profit
        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        # 多头持仓，入场价 100，当前价 99 → 跌幅 1% < 3% 止损，不触发
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=101.0, lowest_price=99.0)
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}}, close=99.0)

        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 1


# --------------------------
# 测试 3: 冷却期 + 止损叠加
# --------------------------


class TestCooldownPlusStopTake:
    """with_trade_cooldown + with_stop_take_profit 交叉行为

    冷却期在外层（先执行），止损在内层（后执行）。
    """

    def test_has_position_cooldown_passes_stop_checks(self):
        """有持仓 + 冷却期内 → 冷却期透传（有持仓不拦截），止损正常检查"""

        @with_trade_cooldown(30)
        @with_stop_take_profit
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        # 多头持仓 + 冷却期内（最近成交 10 分钟前）
        bar_dt = datetime(2024, 1, 1, 12, 10)
        fills = [Fill(timestamp="2024-01-01T12:00:00", symbol="TEST", action="buy", price=100.0, volume=1)]
        state = _make_state(
            direction="long",
            entry_price=100.0,
            volume=1,
            highest_price=101.0,
            lowest_price=96.0,
            fills=fills,
        )
        # 当前价 96 → 跌幅 4% > 3% 止损
        ctx = _make_ctx(close=96.0, bar_dt=bar_dt)

        signal = strat.on_bar(state, ctx)

        # 冷却期有持仓时透传，止损正常触发
        assert signal is not None
        assert signal.reason == "stop_loss"

    def test_no_position_cooldown_blocks_stop_not_checked(self):
        """无持仓 + 冷却期内 → 冷却期拦截，止损不检查"""

        @with_trade_cooldown(30)
        @with_stop_take_profit
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        # 无持仓 + 冷却期内
        bar_dt = datetime(2024, 1, 1, 12, 10)
        fills = [Fill(timestamp="2024-01-01T12:00:00", symbol="TEST", action="buy", price=100.0, volume=1)]
        state = _make_state(fills=fills)
        ctx = _make_ctx(close=100.0, bar_dt=bar_dt)

        signal = strat.on_bar(state, ctx)

        # 冷却期拦截
        assert signal is not None
        assert signal.reason == "trade_cooldown"


# --------------------------
# 测试 4: 方向建议 + 拦截器叠加 — diagnostics 完整性
# --------------------------


class TestDiagnosticsCompleteness:
    """止损触发时 diagnostics 只有止损信息，没有方向建议的 diagnostics"""

    def test_stop_loss_diagnostics_no_direction(self):
        """止损触发 → signal.diagnostics 有止损信息，但无方向建议 diagnostics"""

        @with_stop_take_profit
        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=101.0, lowest_price=96.0)
        ctx = _make_ctx({"1m": {"macd_12_9_26": 0.5}}, close=96.0)

        signal = strat.on_bar(state, ctx)

        # 止损信号
        assert signal.reason == "stop_loss"
        # diagnostics 有止损信息
        assert "entry_price" in signal.diagnostics
        assert signal.diagnostics["entry_price"] == 100.0
        assert "current_close" in signal.diagnostics
        assert signal.diagnostics["current_close"] == 96.0
        # 建议型切面没执行，ctx.aspects.diagnostics 没有 macd_1m
        assert "macd_1m" not in ctx.aspects.diagnostics


# --------------------------
# 测试 5: 多个拦截器优先级
# --------------------------


class TestMultipleInterceptorPriority:
    """with_stop_take_profit + with_atr_stop_take_profit — 外层装饰器先执行"""

    def test_fixed_stop_takes_priority(self):
        """固定止损和 ATR 止损都触发时，外层（固定止损）先拦截"""

        @with_stop_take_profit
        @with_atr_stop_take_profit("15m")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        # 多头持仓，入场价 100，当前价 96
        # 固定止损：跌幅 4% > 3% → 触发
        # ATR 止损：ATR=1.0, multiplier=2.0, max_loss=2.0, close(96) < 100-2=98 → 也触发
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=101.0, lowest_price=96.0)
        ctx = _make_ctx({"15m": {"15m_atr_14": 1.0}}, close=96.0)

        signal = strat.on_bar(state, ctx)

        # with_stop_take_profit 是外层装饰器（先执行），固定止损先拦截
        assert signal is not None
        assert signal.reason == "stop_loss"
        assert signal.diagnostics["entry_price"] == 100.0


# --------------------------
# 测试 6: 建议型切面之间不互相干扰
# --------------------------


class TestAdvisoryIsolation:
    """confirm 和 trend 切面独立写入，不互相干扰"""

    def test_both_satisfied(self):
        """两个都满足 → long.trend 和 long.confirm 各有 1 条"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
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
                "5m": {"5m_sma_10": 100.0},
                "15m": {"15m_sma_40": 99.0},
            }
        )
        state = _make_state()

        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 1
        assert len(ctx.aspects.direction.long.trend) == 1
        assert ctx.aspects.direction.long.confirm[0].name == "macd_1m"
        assert ctx.aspects.direction.long.trend[0].name == "sma_5m_vs_sma_15m"

    def test_only_confirm_satisfied(self):
        """只有 confirm 满足 → long.confirm 有 1 条，long.trend 为空"""

        @confirm_long_when(at(MACD, "1m"), ">", 0)
        @trend_long_when_compare(at(SMA(10), "5m"), ">", at(SMA(40), "15m"))
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        # SMA 5m < SMA 15m → trend 不满足
        ctx = _make_ctx(
            {
                "1m": {"1m_macd_12_9_26": 0.5},
                "5m": {"5m_sma_10": 98.0},
                "15m": {"15m_sma_40": 99.0},
            }
        )
        state = _make_state()

        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 1
        assert len(ctx.aspects.direction.long.trend) == 0


# --------------------------
# 测试 7: data_requirements 合并 — 拦截器 + 建议型
# --------------------------


class TestDataRequirementsCrossMerge:
    """拦截器和建议型切面的 data_requirements 正确合并"""

    def test_atr_stop_and_confirm_merge(self):
        """with_atr_stop_take_profit + confirm_long_when → 同时有 ATR(15m) 和 MACD(1m)"""

        from strategies import DataRequirements

        @with_atr_stop_take_profit("15m")
        @confirm_long_when(at(MACD, "1m"), ">", 0)
        class _S:
            def data_requirements(self, config):
                return DataRequirements(periods={}, indicators={})

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        reqs = strat.data_requirements(_TestParams())
        assert reqs is not None

        # ATR 指标注册在 15m 周期
        assert "15m" in reqs.indicators
        atr_inds = [i for i in reqs.indicators["15m"] if i.name == "atr"]
        assert len(atr_inds) == 1
        assert atr_inds[0].params == {"period": 14}

        # MACD 指标注册在 1m 周期
        assert "1m" in reqs.indicators
        macd_inds = [i for i in reqs.indicators["1m"] if i.name == "macd"]
        assert len(macd_inds) == 1
        assert macd_inds[0].params == {"fast": 12, "slow": 26, "signal": 9}
