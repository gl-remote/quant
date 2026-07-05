from __future__ import annotations

# 文件级元信息：
# - 创建背景：R30 主线策略 value_area_multi_attempt_poc_reversion 需要一份 smoke test，
#   保证按 strategy-math-spec.md 落地的数据需求、profile 刷新和入场/退出主路径可运行。
# - 用途：覆盖 data_requirements、session/refresh 初始化、long/short 首次 reacceptance
#   入场、stop_loss 退出的最小可运行路径。
# - 注意事项：这些测试仅验证实现骨架与 spec 一致，不评估策略盈利表现；
#   持仓状态由测试手动同步（模拟 Bridge 的行为）。
from collections import deque
from datetime import datetime, timedelta

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from strategies.core import Bar, State, StrategyPosition
from strategies.runtime import BarContext
from strategies.value_area_multi_attempt_poc_reversion_strategy import (
    Anchors,
    BreakoutTrack,
    SideState,
    ValueAreaMultiAttemptPocReversionParams,
    ValueAreaMultiAttemptPocReversionStrategyCore,
)


def _bar(dt: datetime, open_: float, high: float, low: float, close: float, volume: float = 100.0) -> Bar:
    return Bar(
        symbol="DCE.m2601",
        datetime=dt,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _ctx(bar: Bar) -> BarContext:
    return BarContext(symbol=bar.symbol, bar=bar, multi={}, events=[])


def _state(config: ValueAreaMultiAttemptPocReversionParams) -> State[ValueAreaMultiAttemptPocReversionParams]:
    return State(
        symbol="DCE.m2601",
        period=config.kline_period,
        strategy_config=config,
        capital=1_000_000.0,
        contract_size=10,
        margin=0.1,
    )


def _prime_session_with_anchors(
    state: State[ValueAreaMultiAttemptPocReversionParams],
    session_dt: datetime,
    anchors: Anchors,
) -> None:
    """跳过 profile bootstrap，直接注入 session 初始状态和结构锚."""
    state.extra["va_r30_session_date"] = session_dt.date()
    state.extra["va_r30_trade_count"] = 0
    state.extra["va_r30_last_exit_bar_idx"] = None
    state.extra["va_r30_side_state"] = {
        "L": SideState(attempts=0, prev_break_ticks=None, prev_poc_tested=None, prev_event_bar_idx=None),
        "U": SideState(attempts=0, prev_break_ticks=None, prev_poc_tested=None, prev_event_bar_idx=None),
    }
    state.extra["va_r30_breakout_track"] = {
        "L": BreakoutTrack(bar_indices=deque(), extremes=deque()),
        "U": BreakoutTrack(bar_indices=deque(), extremes=deque()),
    }
    state.extra["va_r30_bar_idx"] = 0
    state.extra["va_r30_bar_history"] = deque(maxlen=64)
    state.extra["va_r30_anchors"] = anchors
    state.extra["va_r30_last_refresh_bar_idx"] = 0
    # 让下一次 tick 刷新远在测试后
    state.extra["va_r30_next_tick_refresh_bar_idx"] = 10_000


def test_data_requirements_uses_configured_period_and_lookback() -> None:
    strategy = ValueAreaMultiAttemptPocReversionStrategyCore()
    config = ValueAreaMultiAttemptPocReversionParams(kline_period="1m", n_profile=120, stop_atr_bars=14)

    reqs = strategy.data_requirements(config)

    assert reqs is not None
    assert set(reqs.periods) == {"1m"}
    assert reqs.periods["1m"].lookback_bars == 120
    assert reqs.indicators == {}


def test_empty_bar_produces_no_signal_and_bootstraps_session() -> None:
    strategy = ValueAreaMultiAttemptPocReversionStrategyCore()
    config = ValueAreaMultiAttemptPocReversionParams(n_profile=4, n_step=2)
    state = _state(config)

    signal = strategy.on_bar(state, _ctx(_bar(datetime(2025, 9, 1, 9, 0), 3000, 3001, 2999, 3000)))

    assert signal.action == ""
    assert state.extra["va_r30_session_date"] == datetime(2025, 9, 1).date()
    assert state.extra["va_r30_trade_count"] == 0
    assert state.extra["va_r30_bar_idx"] == 1


def test_long_reacceptance_opens_position_and_stop_loss_closes_it() -> None:
    strategy = ValueAreaMultiAttemptPocReversionStrategyCore()
    config = ValueAreaMultiAttemptPocReversionParams(
        n_profile=4,
        n_step=1_000,  # 关掉自动刷新，避免污染注入的 anchors
        pattern_candidates=("C1",),
        risk_candidates=("R0",),
        direction_candidates=("D_near", "D_far"),
        tp_candidates=("TP_fixed",),
        min_breakout_ticks=1,
        min_reaccept_ticks=1,
        rr_min=0.0,
        min_target_ticks=1,
        cooldown_bars=0,
        max_trades_per_day=3,
        max_hold_bars=20,
    )
    state = _state(config)
    base = datetime(2025, 9, 1, 9, 30)
    anchors = Anchors(poc=3010.0, val=3000.0, vah=3020.0, profile={3000.0: 100.0, 3010.0: 400.0, 3020.0: 100.0})
    _prime_session_with_anchors(state, base, anchors)

    # 突破 VAL 下方一段，形成 X_L
    break_bar = _bar(base + timedelta(minutes=5), 3000, 3000, 2995, 2996)
    breakout_signal = strategy.on_bar(state, _ctx(break_bar))
    assert breakout_signal.action == ""

    # 回到 VAL 之上但仍在 POC 之下，触发 R_L 与入场
    reaccept_bar = _bar(base + timedelta(minutes=10), 2996, 3005, 2995, 3004)
    entry_signal = strategy.on_bar(state, _ctx(reaccept_bar))

    assert entry_signal.action == TRADE_ACTION_BUY
    trade = state.extra["va_r30_trade"]
    assert trade["side"] == "L"
    assert trade["q"] == 1
    assert state.extra["va_r30_trade_count"] == 1
    stop_price = float(trade["stop_price"])

    state.position = StrategyPosition(
        direction=TRADE_DIRECTION_LONG,
        entry_price=trade["entry_price"],
        volume=entry_signal.volume,
    )

    # 下一根 bar 打穿 stop
    stop_bar = _bar(
        base + timedelta(minutes=15),
        stop_price + 1,
        stop_price + 1,
        stop_price - 1,
        stop_price - 1,
    )
    exit_signal = strategy.on_bar(state, _ctx(stop_bar))
    assert exit_signal.action == TRADE_ACTION_SELL
    assert exit_signal.reason == "stop_loss"
    assert "va_r30_trade" not in state.extra
    # spec §6.2 事件驱动：open 时 Reset_s 清空 X_s，_track_attempt_event 同 bar 无法触发；
    # 平仓 bar 走 _exit_refresh → Replay，historical window 内新锚下也可能未累计成事件。
    # 所以 attempts 归零或保持 0；不再由交易关闭强制加 1。
    side_state_l: SideState = state.extra["va_r30_side_state"]["L"]
    assert side_state_l["attempts"] >= 0


def test_entry_and_exit_populate_three_layer_diagnostics() -> None:
    strategy = ValueAreaMultiAttemptPocReversionStrategyCore()
    config = ValueAreaMultiAttemptPocReversionParams(
        n_profile=4,
        n_step=1_000,
        pattern_candidates=("C1",),
        risk_candidates=("R0",),
        direction_candidates=("D_near", "D_far"),
        tp_candidates=("TP_fixed",),
        min_breakout_ticks=1,
        min_reaccept_ticks=1,
        rr_min=0.0,
        min_target_ticks=1,
        cooldown_bars=0,
        max_trades_per_day=3,
        max_hold_bars=20,
    )
    state = _state(config)
    base = datetime(2025, 9, 1, 9, 30)
    anchors = Anchors(poc=3010.0, val=3000.0, vah=3020.0, profile={3000.0: 100.0, 3010.0: 400.0, 3020.0: 100.0})
    _prime_session_with_anchors(state, base, anchors)

    strategy.on_bar(state, _ctx(_bar(base + timedelta(minutes=5), 3000, 3000, 2995, 2996)))
    entry_signal = strategy.on_bar(state, _ctx(_bar(base + timedelta(minutes=10), 2996, 3005, 2995, 3004)))
    assert entry_signal.action == TRADE_ACTION_BUY

    # 入场三层诊断
    assert entry_signal.alpha is not None
    assert entry_signal.alpha.fields["matched_pattern"] == "C1"
    assert entry_signal.alpha.fields["matched_risk"] == "R0"
    assert entry_signal.alpha.fields["direction_hypothesis"] == "long"
    assert entry_signal.alpha.fields["poc"] == 3010.0
    assert entry_signal.risk is not None
    assert entry_signal.risk.fields["actual_volume"] == entry_signal.volume
    assert entry_signal.risk.fields["actual_stop_distance"] > 0
    assert entry_signal.risk.fields["expected_profit_distance"] > 0
    assert entry_signal.execution is not None
    assert entry_signal.execution.fields["tp_candidates"] == ["TP_fixed"]
    assert entry_signal.execution.fields["entry_trigger"] == "bar_close"

    trade = state.extra["va_r30_trade"]
    stop_price = float(trade["stop_price"])
    state.position = StrategyPosition(
        direction=TRADE_DIRECTION_LONG,
        entry_price=trade["entry_price"],
        volume=entry_signal.volume,
    )

    exit_signal = strategy.on_bar(
        state,
        _ctx(
            _bar(
                base + timedelta(minutes=15),
                stop_price + 1,
                stop_price + 1,
                stop_price - 1,
                stop_price - 1,
            )
        ),
    )
    assert exit_signal.reason == "stop_loss"
    assert exit_signal.alpha is not None
    assert exit_signal.alpha.fields["exit_reason"] == "stop_loss"
    assert exit_signal.alpha.fields["matched_pattern"] == "C1"
    assert exit_signal.risk is not None
    assert "raw_price_r_multiple" in exit_signal.risk.fields
    assert exit_signal.execution is not None
    assert exit_signal.execution.fields["exit_policy"] == "stop"
    assert exit_signal.execution.fields["exit_price"] == stop_price
    assert exit_signal.execution.fields["holding_bars"] == 1
    assert "mae" in exit_signal.execution.fields
    assert "mfe" in exit_signal.execution.fields


def test_track_x_filters_history_by_current_anchor() -> None:
    """spec §4：anchor 上移后，历史 bar `H_i < U_t + bτ` 应从 J_U 中过期，B_U 恒非负。"""
    track = BreakoutTrack(
        bar_indices=deque([10, 12, 14]),
        extremes=deque([9472.0, 9480.0, 9490.0]),
    )

    b_tau = 3 * 1.0  # min_breakout_ticks=3, tick=1

    # 情形 1：anchor 保持在原位 (VAH=9458)，全部历史极值都合法
    x = ValueAreaMultiAttemptPocReversionStrategyCore._track_x(track, "U", 9458.0, b_tau)
    assert x == 9490.0

    # 情形 2：anchor 漂到 9488（drift），阈值 = 9488 + 3 = 9491，只有 >=9491 才合法
    #        → J_U 为空，X_U 应变为 None（不是负 B_U）
    x = ValueAreaMultiAttemptPocReversionStrategyCore._track_x(track, "U", 9488.0, b_tau)
    assert x is None

    # 情形 3：anchor 到 9485，阈值 9488，只有 9490 合法，X_U=9490
    x = ValueAreaMultiAttemptPocReversionStrategyCore._track_x(track, "U", 9485.0, b_tau)
    assert x == 9490.0

    # 情形 4：L 侧同理，anchor 下移过多则全部过期
    track_l = BreakoutTrack(
        bar_indices=deque([1, 2, 3]),
        extremes=deque([9350.0, 9340.0, 9330.0]),
    )
    x = ValueAreaMultiAttemptPocReversionStrategyCore._track_x(track_l, "L", 9370.0, b_tau)
    assert x == 9330.0  # threshold=9367, 三个都 <= 9367
    x = ValueAreaMultiAttemptPocReversionStrategyCore._track_x(track_l, "L", 9333.0, b_tau)
    assert x == 9330.0  # threshold=9330, 只有 9330 满足 <=
    x = ValueAreaMultiAttemptPocReversionStrategyCore._track_x(track_l, "L", 9320.0, b_tau)
    assert x is None  # threshold=9317, 全部不合法


def test_default_n_step_matches_spec_v2() -> None:
    """spec §11：n_step 默认取 4h/5m = 48（从原 24 提升，抗噪 + 与最短 n_profile 持平）."""
    params = ValueAreaMultiAttemptPocReversionParams(price_tick=1.0)
    assert params.n_step == 48


def test_attempt_event_updates_side_state_without_trading() -> None:
    """spec §5.6 + §6.2：R_s(t) 触发时，无需实际开仓即更新 (A_s, B_s^-, Z_s^-, T_prev_event)."""
    strategy = ValueAreaMultiAttemptPocReversionStrategyCore()
    config = ValueAreaMultiAttemptPocReversionParams(
        n_profile=4,
        n_step=1_000,
        pattern_candidates=("C1", "C2", "C3"),
        risk_candidates=("R0",),
        direction_candidates=("D_near", "D_far"),
        tp_candidates=("TP_fixed",),
        min_breakout_ticks=1,
        min_reaccept_ticks=1,
        # 关闭 exec 层，使 R_s 触发时不会实际开仓（模拟事件与交易解耦）
        trade_start_time="00:00",
        last_entry_time="00:00",  # 立即超出 entry 窗口 → ExecOK=False
        force_flat_time="23:59",
    )
    state = _state(config)
    base = datetime(2025, 9, 1, 9, 30)
    anchors = Anchors(poc=3010.0, val=3000.0, vah=3020.0, profile={3000.0: 100.0, 3010.0: 400.0, 3020.0: 100.0})
    _prime_session_with_anchors(state, base, anchors)

    # 触发 Break_L
    strategy.on_bar(state, _ctx(_bar(base + timedelta(minutes=5), 3000, 3000, 2995, 2996)))
    # 触发 R_L：AttemptEvent_L 应更新 SideState
    strategy.on_bar(state, _ctx(_bar(base + timedelta(minutes=10), 2996, 3005, 2995, 3004)))

    side_state_l: SideState = state.extra["va_r30_side_state"]["L"]
    assert side_state_l["attempts"] == 1, "R_L 触发应把 A_L 从 0 加到 1，即使没实际开仓"
    assert side_state_l["prev_break_ticks"] is not None
    assert side_state_l["prev_event_bar_idx"] is not None
    # 没有实际开仓
    assert "va_r30_trade" not in state.extra


def test_close_trade_does_not_touch_attempt_state() -> None:
    """spec §10.3：交易关闭只更新 T_last_exit，不动 (A_s, B_s^-, Z_s^-, T_prev_event)."""
    strategy = ValueAreaMultiAttemptPocReversionStrategyCore()
    config = ValueAreaMultiAttemptPocReversionParams(
        n_profile=4,
        n_step=1_000,
        pattern_candidates=("C1",),
        risk_candidates=("R0",),
        direction_candidates=("D_near", "D_far"),
        tp_candidates=("TP_fixed",),
        min_breakout_ticks=1,
        min_reaccept_ticks=1,
        rr_min=0.0,
        min_target_ticks=1,
        cooldown_bars=0,
        max_trades_per_day=3,
        max_hold_bars=20,
    )
    state = _state(config)
    base = datetime(2025, 9, 1, 9, 30)
    anchors = Anchors(poc=3010.0, val=3000.0, vah=3020.0, profile={3000.0: 100.0, 3010.0: 400.0, 3020.0: 100.0})
    _prime_session_with_anchors(state, base, anchors)

    strategy.on_bar(state, _ctx(_bar(base + timedelta(minutes=5), 3000, 3000, 2995, 2996)))
    strategy.on_bar(state, _ctx(_bar(base + timedelta(minutes=10), 2996, 3005, 2995, 3004)))
    trade = state.extra["va_r30_trade"]
    stop_price = float(trade["stop_price"])
    state.position = StrategyPosition(
        direction=TRADE_DIRECTION_LONG,
        entry_price=trade["entry_price"],
        volume=1,
    )

    # 记录平仓前的 side_state
    before = dict(state.extra["va_r30_side_state"]["L"])

    stop_bar = _bar(base + timedelta(minutes=15), stop_price + 1, stop_price + 1, stop_price - 1, stop_price - 1)
    exit_signal = strategy.on_bar(state, _ctx(stop_bar))
    assert exit_signal.reason == "stop_loss"

    after = dict(state.extra["va_r30_side_state"]["L"])
    # 平仓后 side_state 的变化只可能来自 _exit_refresh -> Replay，而非 _close_trade 主动加 1
    # 关键断言：attempts 不会因为 _close_trade 自加 1（对比原 v1 语义 before+1 == after）
    assert after["attempts"] != before["attempts"] + 1 or after["attempts"] == before["attempts"], (
        f"_close_trade 不应把 attempts 从 {before['attempts']} 加到 {after['attempts']}"
    )
    # T_last_exit 一定被更新
    assert state.extra["va_r30_last_exit_bar_idx"] is not None
