"""装饰器交叉行为测试

覆盖建议型切面之间的交互场景：
1. risk 切面触发时 direction 切面仍正常执行
2. risk 未触发时 direction 切面正常执行
3. cooldown + 止损叠加
4. 方向建议 + risk 切面叠加 — diagnostics 完整性
5. 多个 risk 切面叠加
6. 建议型切面之间不互相干扰
7. data_requirements 合并 — risk + 建议型

装饰器执行顺序说明：
  Python 装饰器从下到上应用，从上到下执行。
  所有切面都是建议型，都会执行，不会短路。
"""

from dataclasses import dataclass
from datetime import datetime

from common.constants import SIGNAL_STOP_LOSS, SIGNAL_TAKE_PROFIT, SIGNAL_TRADE_COOLDOWN
from strategies import Bar
from strategies.core.state import State
from strategies.core.types import Fill, StrategyPosition
from strategies.strategy_aspects import (
    confirm_long,
    entry_block_after_stop_loss,
    entry_block_after_take_profit,
    exit_for_stop_loss,
    exit_for_take_profit,
    trend_long,
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
# 测试 1: risk 切面触发时 direction 切面仍正常执行
# --------------------------


class TestRiskExecutesWithDirection:
    """risk 切面和 direction 切面都是建议型，都会执行"""

    def test_stop_loss_with_confirm(self):
        """止损触发时 confirm 切面也执行"""

        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        @confirm_long("macd@1m > 0")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=101.0, lowest_price=96.0)
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}}, close=96.0)

        signal = strat.on_bar(state, ctx)

        # on_bar 返回 None
        assert signal is None
        # risk 切面写入止损理由
        assert len(ctx.aspects.risk.stop_loss.exit) == 1
        assert ctx.aspects.risk.stop_loss.exit[0].name == SIGNAL_STOP_LOSS
        # direction 切面也正常执行
        assert len(ctx.aspects.direction.long.confirm) == 1

    def test_take_profit_with_confirm(self):
        """止盈触发时 confirm 切面也执行"""

        @exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
        @confirm_long("macd@1m > 0")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=106.0, lowest_price=99.0)
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}}, close=106.0)

        signal = strat.on_bar(state, ctx)

        assert signal is None
        assert len(ctx.aspects.risk.take_profit.exit) == 1
        assert ctx.aspects.risk.take_profit.exit[0].name == SIGNAL_TAKE_PROFIT
        assert len(ctx.aspects.direction.long.confirm) == 1


# --------------------------
# 测试 2: risk 未触发时 direction 切面正常执行
# --------------------------


class TestRiskPassesThrough:
    """risk 未触发时 direction 切面正常执行"""

    def test_no_position_confirm_executes(self):
        """无持仓时 risk 不触发，confirm 切面正常写入"""

        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        @exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
        @confirm_long("macd@1m > 0")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        state = _make_state()  # 无持仓
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}})

        strat.on_bar(state, ctx)

        assert ctx.aspects.risk.all_reasons == []
        assert len(ctx.aspects.direction.long.confirm) == 1
        assert ctx.aspects.direction.long.confirm[0].name == "macd_1m_gt_0"

    def test_position_no_trigger_confirm_executes(self):
        """有持仓但止损未触发时 confirm 切面正常写入"""

        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        @exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
        @confirm_long("macd@1m > 0")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=101.0, lowest_price=99.0)
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}}, close=99.0)

        strat.on_bar(state, ctx)

        assert ctx.aspects.risk.all_reasons == []
        assert len(ctx.aspects.direction.long.confirm) == 1


# --------------------------
# 测试 3: 冷却期 + 止损叠加
# --------------------------


class TestCooldownPlusStopLoss:
    """entry_block_after_stop_loss + exit_for_stop_loss 交叉行为

    两个切面都是建议型，都会执行。
    """

    def test_has_position_cooldown_passes_stop_checks(self):
        """有持仓 + 冷却期内 → cooldown 不写入，止损正常触发"""

        @entry_block_after_stop_loss("cooldown() < 30")
        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
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
        ctx = _make_ctx(close=96.0, bar_dt=bar_dt)

        signal = strat.on_bar(state, ctx)

        # 有持仓时 cooldown 不写入，但止损触发
        assert len(ctx.aspects.risk.stop_loss.exit) == 1
        assert ctx.aspects.risk.stop_loss.exit[0].name == SIGNAL_STOP_LOSS
        # on_bar 返回 None
        assert signal is None

    def test_no_position_cooldown_blocks_stop_not_checked(self):
        """无持仓 + 冷却期内 → cooldown 写入 risk，止损不检查"""

        @entry_block_after_stop_loss("cooldown() < 30")
        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        bar_dt = datetime(2024, 1, 1, 12, 10)
        fills = [Fill(timestamp="2024-01-01T12:00:00", symbol="TEST", action="buy", price=100.0, volume=1)]
        state = _make_state(fills=fills)
        ctx = _make_ctx(close=100.0, bar_dt=bar_dt)

        signal = strat.on_bar(state, ctx)

        # cooldown 写入 stop_loss.entry_block（Fill 无 reason，默认非止盈）
        assert len(ctx.aspects.risk.stop_loss.entry_block) == 1
        assert ctx.aspects.risk.stop_loss.entry_block[0].name == SIGNAL_TRADE_COOLDOWN
        # 无持仓不检查止损
        assert "stop_loss" not in [r.name for r in ctx.aspects.risk.all_reasons]
        assert signal is None


# --------------------------
# 测试 4: 方向建议 + risk 切面叠加 — diagnostics 完整性
# --------------------------


class TestDiagnosticsCompleteness:
    """risk 触发时 diagnostics 同时包含 direction 和 risk 信息"""

    def test_stop_loss_diagnostics_with_direction(self):
        """止损触发 → diagnostics 有止损信息，direction 切面 diagnostics 也在"""

        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        @confirm_long("macd@1m > 0")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=101.0, lowest_price=96.0)
        ctx = _make_ctx({"1m": {"1m_macd_12_9_26": 0.5}}, close=96.0)

        strat.on_bar(state, ctx)

        # risk 触发
        assert len(ctx.aspects.risk.stop_loss.exit) == 1
        assert ctx.aspects.risk.stop_loss.exit[0].name == SIGNAL_STOP_LOSS
        # diagnostics 有止损信息
        assert "entry_price" in ctx.aspects.diagnostics
        assert ctx.aspects.diagnostics["entry_price"] == 100.0
        # direction 切面也执行了
        assert len(ctx.aspects.direction.long.confirm) == 1


# --------------------------
# 测试 5: 多个 risk 切面叠加
# --------------------------


class TestMultipleRiskAdvisory:
    """多个 exit_for_stop_loss 叠加 — 两个切面都执行"""

    def test_fixed_stop_and_atr_stop_both_trigger(self):
        """固定止损和 ATR 止损都触发时，两个切面都写入 risk"""

        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        @exit_for_stop_loss("loss_abs() >= atr@15m * {atr_stop_loss_multiplier}")
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

        assert signal is None
        # 两个切面都写入了 risk
        risk_names = [r.name for r in ctx.aspects.risk.all_reasons]
        assert SIGNAL_STOP_LOSS in risk_names
        # 固定止损先执行（外层装饰器），atr 后执行（内层装饰器）
        # 两者都是 stop_loss，都写入 stop_loss.exit
        assert len(ctx.aspects.risk.stop_loss.exit) == 2

    def test_fixed_take_profit_only(self):
        """只有固定止盈触发时，只有固定比例切面写入"""

        @exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
        @exit_for_take_profit("profit_abs() >= atr@15m * {atr_take_profit_multiplier}")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        # 固定止盈触发(5%: close>105), ATR 止盈需要 106
        state = _make_state(direction="long", entry_price=100.0, volume=1, highest_price=100.0, lowest_price=100.0)
        ctx = _make_ctx({"15m": {"15m_atr_14": 2.0}}, close=105.5)

        signal = strat.on_bar(state, ctx)

        assert signal is None
        risk_names = [r.name for r in ctx.aspects.risk.all_reasons]
        assert SIGNAL_TAKE_PROFIT in risk_names
        # ATR 止盈未触发
        assert len(ctx.aspects.risk.take_profit.exit) == 1


# --------------------------
# 测试 6: 建议型切面之间不互相干扰
# --------------------------


class TestAdvisoryIsolation:
    """confirm 和 trend 切面独立写入，不互相干扰"""

    def test_both_satisfied(self):
        """两个都满足 → long.trend 和 long.confirm 各有 1 条"""

        @confirm_long("macd@1m > 0")
        @trend_long("sma(10)@5m > sma(40)@15m")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        strat = _S()
        ctx = _make_ctx(
            {
                "1m": {"1m_macd_12_9_26": 0.5},
                "5m": {"5m_sma_10.0": 100.0},
                "15m": {"15m_sma_40.0": 99.0},
            }
        )
        state = _make_state()

        strat.on_bar(state, ctx)

        assert len(ctx.aspects.direction.long.confirm) == 1
        assert len(ctx.aspects.direction.long.trend) == 1
        assert ctx.aspects.direction.long.confirm[0].name == "macd_1m_gt_0"
        assert ctx.aspects.direction.long.trend[0].name == "sma_10.0_5m_gt_sma_40.0_15m"

    def test_only_confirm_satisfied(self):
        """只有 confirm 满足 → long.confirm 有 1 条，long.trend 为空"""

        @confirm_long("macd@1m > 0")
        @trend_long("sma(10)@5m > sma(40)@15m")
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
# 测试 7: data_requirements 合并 — risk + 建议型
# --------------------------


class TestRiskInvariants:
    """策略风控核心不变量。"""

    def test_exit_risk_never_triggers_without_position(self):
        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        @exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        state = _make_state()
        ctx = _make_ctx(close=1.0)

        _S().on_bar(state, ctx)

        assert ctx.aspects.risk.stop_loss.exit == []
        assert ctx.aspects.risk.take_profit.exit == []
        assert ctx.aspects.risk.all_reasons == []
        assert "entry_price" not in ctx.aspects.diagnostics
        assert "current_close" not in ctx.aspects.diagnostics

    def test_entry_cooldown_never_blocks_open_position_exit(self):
        @entry_block_after_stop_loss("cooldown() < 30")
        @entry_block_after_take_profit("cooldown() < 30")
        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        fills = [Fill(timestamp="2024-01-01T12:00:00", symbol="TEST", action="sell", price=100.0, volume=1)]
        state = _make_state(
            direction="long",
            entry_price=100.0,
            volume=1,
            highest_price=101.0,
            lowest_price=96.0,
            fills=fills,
        )
        ctx = _make_ctx(close=96.0, bar_dt=datetime(2024, 1, 1, 12, 10))

        _S().on_bar(state, ctx)

        assert ctx.aspects.risk.stop_loss.entry_block == []
        assert ctx.aspects.risk.take_profit.entry_block == []
        assert len(ctx.aspects.risk.stop_loss.exit) == 1
        assert ctx.aspects.risk.stop_loss.exit[0].name == SIGNAL_STOP_LOSS

    def test_multiple_risk_advisories_survive_flush_without_overwrite(self):
        @entry_block_after_stop_loss("cooldown() < 30")
        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        class _StopLossStrategy:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        @entry_block_after_take_profit("cooldown() < 30")
        @exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
        class _TakeProfitStrategy:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        stop_fills = [
            Fill(
                timestamp="2024-01-01T12:00:00", symbol="TEST", action="sell", price=100.0, volume=1, reason="stop_loss"
            )
        ]
        take_fills = [
            Fill(
                timestamp="2024-01-01T12:00:00",
                symbol="TEST",
                action="sell",
                price=100.0,
                volume=1,
                reason="take_profit",
            )
        ]
        stop_state = _make_state(fills=stop_fills)
        take_state = _make_state(fills=take_fills)
        stop_ctx = _make_ctx(bar_dt=datetime(2024, 1, 1, 12, 10))
        take_ctx = _make_ctx(bar_dt=datetime(2024, 1, 1, 12, 10))

        _StopLossStrategy().on_bar(stop_state, stop_ctx)
        _TakeProfitStrategy().on_bar(take_state, take_ctx)
        stop_ctx.aspects.flush_risk_diagnostics()
        take_ctx.aspects.flush_risk_diagnostics()

        assert [r.name for r in stop_ctx.aspects.risk.stop_loss.entry_block] == [SIGNAL_TRADE_COOLDOWN]
        assert [r.name for r in take_ctx.aspects.risk.take_profit.entry_block] == [SIGNAL_TRADE_COOLDOWN]
        assert stop_ctx.aspects.diagnostics["risk_entry_block_stop_loss"] == [SIGNAL_TRADE_COOLDOWN]
        assert stop_ctx.aspects.diagnostics["risk_entry_block_take_profit"] == []
        assert take_ctx.aspects.diagnostics["risk_entry_block_stop_loss"] == []
        assert take_ctx.aspects.diagnostics["risk_entry_block_take_profit"] == [SIGNAL_TRADE_COOLDOWN]

    def test_fixed_ratio_long_short_stop_loss_boundaries_are_symmetric(self):
        @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        long_state = _make_state(direction="long", entry_price=100.0, volume=1)
        short_state = _make_state(direction="short", entry_price=100.0, volume=1)
        long_ctx = _make_ctx(close=97.0)
        short_ctx = _make_ctx(close=103.0)

        strat = _S()
        strat.on_bar(long_state, long_ctx)
        strat.on_bar(short_state, short_ctx)

        assert [r.name for r in long_ctx.aspects.risk.stop_loss.exit] == [SIGNAL_STOP_LOSS]
        assert [r.name for r in short_ctx.aspects.risk.stop_loss.exit] == [SIGNAL_STOP_LOSS]

    def test_atr_none_and_zero_do_not_pollute_risk_diagnostics(self):
        @exit_for_stop_loss("loss_abs() >= atr@15m * {atr_stop_loss_multiplier}")
        class _S:
            def data_requirements(self, config):
                return None

            def on_bar(self, state, ctx):
                return None

        state = _make_state(direction="long", entry_price=100.0, volume=1)
        none_ctx = _make_ctx({"15m": {}}, close=50.0)
        zero_ctx = _make_ctx({"15m": {"15m_atr_14": 0.0}}, close=50.0)

        strat = _S()
        strat.on_bar(state, none_ctx)
        strat.on_bar(state, zero_ctx)
        none_ctx.aspects.flush_risk_diagnostics()
        zero_ctx.aspects.flush_risk_diagnostics()

        assert none_ctx.aspects.risk.all_reasons == []
        assert zero_ctx.aspects.risk.all_reasons == []
        assert none_ctx.aspects.diagnostics["risk_exit_stop_loss"] == []
        assert zero_ctx.aspects.diagnostics["risk_exit_stop_loss"] == []
        assert none_ctx.aspects.diagnostics["risk_detail"] == {}
        assert zero_ctx.aspects.diagnostics["risk_detail"] == {}


class TestDataRequirementsCrossMerge:
    """risk 和建议型切面的 data_requirements 正确合并"""

    def test_atr_stop_and_confirm_merge(self):
        """exit_for_stop_loss_atr + confirm_long → 同时有 ATR(15m) 和 MACD(1m)"""

        from strategies import DataRequirements

        @exit_for_stop_loss("loss_abs() >= atr@15m * {atr_stop_loss_multiplier}")
        @confirm_long("macd@1m > 0")
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
        assert atr_inds[0].window == 15
        assert reqs.periods["15m"].lookback_bars == 16

        # MACD 指标注册在 1m 周期
        assert "1m" in reqs.indicators
        macd_inds = [i for i in reqs.indicators["1m"] if i.name == "macd"]
        assert len(macd_inds) == 1
        assert macd_inds[0].params == {"fast": 12, "slow": 26, "signal": 9}
