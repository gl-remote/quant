from __future__ import annotations

# 文件级元信息：
# - 创建背景：R29 新增长期随机入场基准策略后，需要覆盖 loader、数据需求和基本入场行为。
# - 用途：验证 value_area_random_baseline 能基于 VA baseline 事件生成随机基准信号。
# - 注意事项：测试只校验基准策略机制，不评估随机基准的统计显著性。
from datetime import datetime

from common.constants import TRADE_ACTION_BUY
from strategies.core import Bar, State
from strategies.runtime import BarContext
from strategies.utils import load_strategy
from strategies.value_area_random_baseline_strategy import (
    ValueAreaRandomBaselineParams,
    ValueAreaRandomBaselineStrategyCore,
)
from strategies.value_area_reacceptance_baseline_strategy import CurrentSession, ValueAreaLevels


def _ctx(dt: datetime, open_price: float, high: float, low: float, close: float, volume: float = 1000) -> BarContext:
    return BarContext(
        symbol="DCE.m2601",
        bar=Bar(
            symbol="DCE.m2601",
            datetime=dt,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        ),
        multi={},
        events=[],
    )


def _state(config: ValueAreaRandomBaselineParams | None = None) -> State[ValueAreaRandomBaselineParams]:
    return State(
        symbol="DCE.m2601",
        period="1m",
        strategy_config=config or ValueAreaRandomBaselineParams(),
        capital=100000,
        contract_size=10,
        margin=0.1,
    )


def _seed_value_area_state(state: State[ValueAreaRandomBaselineParams]) -> None:
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3010.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
        profile={},
        range_profile={},
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(),
        high=3005.0,
        low=3005.0,
        close=3005.0,
        open=3005.0,
        profile={},
        range_profile={},
    )


def test_value_area_random_baseline_can_be_loaded() -> None:
    strategy = load_strategy("value_area_random_baseline")

    assert isinstance(strategy, ValueAreaRandomBaselineStrategyCore)


def test_data_requirements_reuse_value_area_reacceptance_baseline_requirements() -> None:
    reqs = ValueAreaRandomBaselineStrategyCore().data_requirements(ValueAreaRandomBaselineParams(kline_period="1m"))

    assert reqs is not None
    assert set(reqs.periods) == {"1m"}


def test_direction_matched_random_baseline_enters_on_reacceptance_event() -> None:
    strategy = ValueAreaRandomBaselineStrategyCore()
    state = _state(
        ValueAreaRandomBaselineParams(
            kline_period="1m",
            profile_mode="close",
            take_profit_mode="poc",
            min_breakout_ticks=2,
            min_reaccept_ticks=0,
            random_seed=1,
            random_baseline_mode="direction_matched",
            random_direction_mode="same",
            random_entry_probability=1.0,
        )
    )
    _seed_value_area_state(state)

    breakout = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 31), 2998, 3006, 2998, 3001))

    assert breakout.action == ""
    assert signal.action == TRADE_ACTION_BUY
    assert signal.reason.startswith("random_value_area_val_reaccept_long")
    assert signal.diagnostics["random_baseline"] == "direction_matched"
    assert signal.diagnostics["random_direction_mode"] == "same"
    trade = state.extra["value_area_trade"]
    assert trade["context_label"] == "random_direction_matched_same"
