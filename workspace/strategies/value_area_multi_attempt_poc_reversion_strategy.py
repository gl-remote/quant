from __future__ import annotations

# 文件级元信息：
# - 创建背景：R30 主线策略 value_area_multi_attempt_poc_reversion 需要一份严格按照
#   docs/research/themes/value-area-reacceptance/strategy-math-spec.md 的可运行实现，
#   用于跑首轮 Ω_pattern × Ω_risk × Ω_direction × Ω_tp 小矩阵。
# - 用途：实现 spec §1–§10 定义的 profile 滚动刷新、突破跟踪、四维正交入场候选、
#   三类止盈候选，以及 stop_loss > strict_failure_close > TP_fixed > TP_soft >
#   force_flat > time_exit 的退出优先级。
# - 注意事项：策略行为由 strategy-math-spec.md 唯一确定，若发现实现与 spec 不一致，
#   先回补 spec 再改代码；本文件不定义诊断字段（暂用 placeholder_diagnostics 占位），
#   实验结果与参数选择另行由 workbench / parameter-selection-spec.md 承接。
import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, time
from typing import Literal, TypedDict, cast, override

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL
from common.formulas import position_size

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .core.diagnostics import AlphaDiagnostics, ExecutionDiagnostics, RiskDiagnostics
from .runtime import BarContext, DataRequirements, EventsRequirements, PeriodRequirements

Side = Literal["L", "U"]
DirectionMode = Literal["to_poc", "away_from_poc"]
PocMode = Literal["close", "range"]
VaMode = Literal["greedy_from_poc"]
PatternCondition = Literal["C1", "C2", "C3"]
RiskCondition = Literal["R0", "R1"]
DirectionCondition = Literal["D_near", "D_far"]
TpCandidate = Literal["TP_fixed", "TP_armed_retrace", "TP_fast_time"]


@dataclass
class ValueAreaMultiAttemptPocReversionParams:
    """R30 多次 POC 回归策略参数（对照 strategy-math-spec.md §2 θ_*）."""

    kline_period: str = "5m"

    # θ_profile
    poc_mode: PocMode = "close"
    va_mode: VaMode = "greedy_from_poc"
    value_area_ratio: float = 0.7
    n_profile: int = 288  # 24h / 5m
    n_step: int = 24  # 2h / 5m

    # θ_signal
    direction_mode: DirectionMode = "to_poc"
    pattern_candidates: tuple[PatternCondition, ...] = ("C1", "C2", "C3")
    risk_candidates: tuple[RiskCondition, ...] = ("R0",)
    direction_candidates: tuple[DirectionCondition, ...] = ("D_near", "D_far")
    min_breakout_ticks: int = 1
    min_reaccept_ticks: int = 1
    poc_touch_tolerance_ticks: int = 0
    min_target_ticks: int = 1
    rr_raw_min: float = 1.0
    max_trades_per_day: int = 3
    cooldown_bars: int = 1
    trade_start_time: str = "09:00"
    last_entry_time: str = "14:30"
    force_flat_time: str = "14:55"

    # θ_exec
    target_fraction: float = 0.8  # α
    failure_buffer_ticks: int = 1  # β
    stop_widen_multiplier: float = 1.0  # λ
    stop_atr_bars: int = 0
    stop_atr_multiplier: float = 0.0
    rr_min: float = 0.8
    max_hold_bars: int = 60
    strict_close_exit: bool = True
    tp_candidates: tuple[TpCandidate, ...] = ("TP_fixed",)
    arm_fraction: float = 0.5  # η_arm
    retrace_fraction: float = 0.5  # η_retrace
    fast_window_bars: int = 6  # n_fast
    fast_fraction: float = 0.5  # η_fast
    fast_hold_bars: int = 0  # n_fast_hold

    # θ_size
    price_tick: float = 1.0
    risk_per_trade: float = 0.02
    max_position_ratio: float = 0.3


# ── 数据容器 ─────────────────────────────────────────────


class Anchors(TypedDict):
    """采用型刷新后的结构锚 (P_t, D_t, U_t) 快照."""

    poc: float
    val: float
    vah: float
    profile: dict[float, float]


class BreakoutTrack(TypedDict):
    """单侧 s ∈ {L, U} 的突破极值 X_s 追踪窗口（按 bar 条数）."""

    bar_indices: deque[int]
    extremes: deque[float]


class SideState(TypedDict):
    """spec §5 状态变量：单侧 session 级 (A_s, B_s^-, Z_s^-)."""

    attempts: int
    prev_break_ticks: float | None
    prev_poc_tested: bool | None


class TradeInfo(TypedDict):
    """持仓期间冻结变量（spec §8）与在线跟踪指标（MAE / MFE / 触达 POC）."""

    side: Side
    q: int  # +1 long / -1 short
    entry_price: float
    stop_price: float
    target_price: float
    strict_failure_price: float  # F
    anchor_gain: float  # |P - E|
    d_strict: float
    d_stop_eff: float
    entry_bar_idx: int
    entry_datetime: datetime
    entry_break_ticks: float  # B_s(t_entry)，用于回填 B_s^-
    matched_pattern: str  # 命中的 Ω_pattern 候选（用于诊断归因）
    matched_risk: str
    matched_direction: str
    rr_raw: float  # 原始盈亏比（G_raw / L_raw），R0 时也记录以便对照
    volume: int
    peak_pnl: float  # MFE，单位价格
    trough_pnl: float  # MAE，单位价格
    fast_hit_bar: int | None


# ── 策略实现 ──────────────────────────────────────────────


class ValueAreaMultiAttemptPocReversionStrategyCore(Strategy[ValueAreaMultiAttemptPocReversionParams]):
    """R30 多次 POC 回归主线策略."""

    name: str = "value_area_multi_attempt_poc_reversion"
    VERSION: str = f"{CORE_VERSION}-value-area-multi-attempt-poc-reversion-r1"

    # ---- Strategy 接口 ----

    @override
    def data_requirements(self, config: ValueAreaMultiAttemptPocReversionParams) -> DataRequirements | None:
        lookback = max(config.n_profile, config.stop_atr_bars, 1)
        return DataRequirements(
            periods={config.kline_period: PeriodRequirements(lookback_bars=lookback)},
            indicators={},
            events=EventsRequirements.no_events(),
        )

    @override
    def on_bar(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
    ) -> Signal:
        config = state.strategy_config
        self._ensure_session(state, ctx)
        self._append_bar_history(state, ctx.bar)

        # spec §10.3 刷新调度：InitEvent + TickEvent（Enter 前评估）
        self._maybe_init_refresh(state, config)
        self._maybe_tick_refresh(state, config)
        # 当前 bar 的 Break_s(t) 需在 R_s(t) 判定前纳入 X_s
        self._track_breakout(state, ctx, config)

        if state.position.direction:
            signal = self._exit_signal(state, ctx, config)
        else:
            signal = self._entry_signal(state, ctx, config)

        self._advance_bar_index(state)
        return signal

    @override
    def on_fill(self, fill: Fill) -> None:
        pass

    # ── session 与 bar 索引 ────────────────────────────────

    def _ensure_session(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
    ) -> None:
        """spec §10.1 Session reset：新 session 的首根 bar 上初始化状态."""
        bar = ctx.bar
        session = bar.datetime.date()
        current_session = state.extra.get("va_r30_session_date")
        if current_session == session:
            return

        state.extra["va_r30_session_date"] = session
        state.extra["va_r30_trade_count"] = 0
        state.extra["va_r30_last_exit_bar_idx"] = None
        state.extra["va_r30_side_state"] = {
            "L": SideState(attempts=0, prev_break_ticks=None, prev_poc_tested=None),
            "U": SideState(attempts=0, prev_break_ticks=None, prev_poc_tested=None),
        }
        # §10.2：新 session 首根 bar 上 Reset_s=1，历史突破清空
        state.extra["va_r30_breakout_track"] = {
            "L": BreakoutTrack(bar_indices=deque(), extremes=deque()),
            "U": BreakoutTrack(bar_indices=deque(), extremes=deque()),
        }
        state.extra["va_r30_last_refresh_bar_idx"] = None
        state.extra["va_r30_next_tick_refresh_bar_idx"] = None
        state.extra["va_r30_bar_idx"] = 0

    def _append_bar_history(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        bar: Bar,
    ) -> None:
        history: deque[Bar] | None = state.extra.get("va_r30_bar_history")
        if history is None:
            history = deque(maxlen=self._history_maxlen(state))
            state.extra["va_r30_bar_history"] = history
        history.append(bar)

    def _advance_bar_index(self, state: State[ValueAreaMultiAttemptPocReversionParams]) -> None:
        state.extra["va_r30_bar_idx"] = int(state.extra.get("va_r30_bar_idx", 0)) + 1

    def _current_bar_idx(self, state: State[ValueAreaMultiAttemptPocReversionParams]) -> int:
        return int(state.extra.get("va_r30_bar_idx", 0))

    def _history_maxlen(self, state: State[ValueAreaMultiAttemptPocReversionParams]) -> int:
        config = state.strategy_config
        return max(config.n_profile, config.stop_atr_bars, config.n_step, 1) + 1

    # ── §10.3 profile 刷新调度 ────────────────────────────

    def _maybe_init_refresh(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> None:
        """InitEvent(t)：session 内首次可用 bar 上刷新一次."""
        if state.extra.get("va_r30_anchors") is not None:
            return
        anchors = self._compute_anchors(state, config)
        if anchors is None:
            return
        cur_idx = self._current_bar_idx(state)
        state.extra["va_r30_anchors"] = anchors
        state.extra["va_r30_last_refresh_bar_idx"] = cur_idx
        state.extra["va_r30_next_tick_refresh_bar_idx"] = cur_idx + config.n_step

    def _maybe_tick_refresh(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> None:
        """TickEvent(t)：累计 n_step 根 bar 触发；仅空仓时采用（Adopt 规则）."""
        next_idx = state.extra.get("va_r30_next_tick_refresh_bar_idx")
        if next_idx is None:
            return
        cur_idx = self._current_bar_idx(state)
        if cur_idx < int(next_idx):
            return
        state.extra["va_r30_next_tick_refresh_bar_idx"] = cur_idx + config.n_step
        if state.position.direction:
            return
        anchors = self._compute_anchors(state, config)
        if anchors is None:
            return
        state.extra["va_r30_anchors"] = anchors
        state.extra["va_r30_last_refresh_bar_idx"] = cur_idx

    def _exit_refresh(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> None:
        """ExitEvent(t)：平仓刷新，恒 Adopt."""
        anchors = self._compute_anchors(state, config)
        if anchors is None:
            return
        cur_idx = self._current_bar_idx(state)
        state.extra["va_r30_anchors"] = anchors
        state.extra["va_r30_last_refresh_bar_idx"] = cur_idx
        state.extra["va_r30_next_tick_refresh_bar_idx"] = cur_idx + config.n_step

    def _compute_anchors(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> Anchors | None:
        history: deque[Bar] | None = state.extra.get("va_r30_bar_history")
        if not history:
            return None
        window = list(history)[-config.n_profile :]
        if not window:
            return None
        profile = self._build_profile(window, config)
        if not profile:
            return None
        window_close = window[-1].close
        poc = self._select_poc(profile, window_close)
        val, vah = self._greedy_value_area(profile, poc, config.value_area_ratio)
        return Anchors(poc=poc, val=val, vah=vah, profile=profile)

    def _build_profile(
        self,
        bars: list[Bar],
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> dict[float, float]:
        profile: dict[float, float] = {}
        tick = config.price_tick
        if tick <= 0:
            return profile
        for bar in bars:
            if bar.volume <= 0:
                continue
            if config.poc_mode == "close":
                p = self._round_tick(bar.close, tick)
                profile[p] = profile.get(p, 0.0) + bar.volume
                continue
            low_tick = int(round(bar.low / tick))
            high_tick = int(round(bar.high / tick))
            if high_tick < low_tick:
                low_tick, high_tick = high_tick, low_tick
            bucket_count = high_tick - low_tick + 1
            share = bar.volume / bucket_count
            for k in range(low_tick, high_tick + 1):
                p = k * tick
                profile[p] = profile.get(p, 0.0) + share
        return profile

    @staticmethod
    def _select_poc(profile: dict[float, float], window_close: float) -> float:
        """spec §3.1 POC tie-break：max volume；等值取距 C̄ 近且更高的桶."""
        max_volume = max(profile.values())
        candidates = [p for p, v in profile.items() if v == max_volume]
        candidates.sort(key=lambda p: (abs(p - window_close), -p))
        return candidates[0]

    @staticmethod
    def _greedy_value_area(profile: dict[float, float], poc: float, ratio: float) -> tuple[float, float]:
        """spec §3.2 greedy_from_poc：相邻桶取更大成交量，等值先扩上边界."""
        total = sum(profile.values())
        target = total * max(0.0, min(ratio, 1.0))
        prices = sorted(profile)
        try:
            poc_index = prices.index(poc)
        except ValueError:
            return poc, poc
        selected_volume = profile[poc]
        low_idx = poc_index
        high_idx = poc_index
        while selected_volume < target:
            can_up = high_idx < len(prices) - 1
            can_down = low_idx > 0
            if not can_up and not can_down:
                break
            up_volume = profile[prices[high_idx + 1]] if can_up else -math.inf
            down_volume = profile[prices[low_idx - 1]] if can_down else -math.inf
            if can_up and (not can_down or up_volume >= down_volume):
                high_idx += 1
                selected_volume += profile[prices[high_idx]]
            else:
                low_idx -= 1
                selected_volume += profile[prices[low_idx]]
        return prices[low_idx], prices[high_idx]

    # ── §4 事件与突破跟踪 ────────────────────────────────

    def _track_breakout(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> None:
        anchors = state.extra.get("va_r30_anchors")
        if anchors is None:
            return
        anchors_t = cast(Anchors, anchors)
        tracks = cast(dict[str, BreakoutTrack], state.extra["va_r30_breakout_track"])
        bar = ctx.bar
        tick = config.price_tick
        b = config.min_breakout_ticks
        cur_idx = self._current_bar_idx(state)

        if bar.low <= anchors_t["val"] - b * tick:
            self._track_add(tracks["L"], cur_idx, bar.low)
        if bar.high >= anchors_t["vah"] + b * tick:
            self._track_add(tracks["U"], cur_idx, bar.high)
        for side in ("L", "U"):
            self._track_evict(tracks[side], cur_idx - config.n_step + 1)

    @staticmethod
    def _track_add(track: BreakoutTrack, bar_idx: int, extreme: float) -> None:
        track["bar_indices"].append(bar_idx)
        track["extremes"].append(extreme)

    @staticmethod
    def _track_evict(track: BreakoutTrack, min_idx: int) -> None:
        while track["bar_indices"] and track["bar_indices"][0] < min_idx:
            track["bar_indices"].popleft()
            track["extremes"].popleft()

    @staticmethod
    def _track_x(track: BreakoutTrack, side: Side) -> float | None:
        if not track["extremes"]:
            return None
        return min(track["extremes"]) if side == "L" else max(track["extremes"])

    def _reset_side_track(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        side: Side,
    ) -> None:
        tracks = cast(dict[str, BreakoutTrack], state.extra["va_r30_breakout_track"])
        tracks[side]["bar_indices"].clear()
        tracks[side]["extremes"].clear()

    # ── §7 入场判定 ────────────────────────────────────

    def _entry_signal(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> Signal:
        if not self._exec_ok(state, ctx, config):
            return Signal()
        anchors = state.extra.get("va_r30_anchors")
        if anchors is None:
            return Signal()
        anchors_t = cast(Anchors, anchors)
        tracks = cast(dict[str, BreakoutTrack], state.extra["va_r30_breakout_track"])
        tick = config.price_tick
        r = config.min_reaccept_ticks

        for side in ("L", "U"):
            x_s = self._track_x(tracks[side], side)
            if x_s is None:
                continue
            if side == "L":
                if not (ctx.bar.close >= anchors_t["val"] + r * tick):
                    continue
            else:
                if not (ctx.bar.close <= anchors_t["vah"] - r * tick):
                    continue

            signal = self._try_open(state, ctx, config, side, x_s, anchors_t)
            if signal.action:
                return signal
        return Signal()

    def _exec_ok(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> bool:
        bar_time = ctx.bar.datetime.time()
        if not self._in_entry_window(bar_time, config):
            return False
        if self._is_force_flat_time(bar_time, config):
            return False
        trade_count = int(state.extra.get("va_r30_trade_count", 0))
        if trade_count >= config.max_trades_per_day:
            return False
        last_exit_idx = state.extra.get("va_r30_last_exit_bar_idx")
        if last_exit_idx is not None:
            elapsed = self._current_bar_idx(state) - int(last_exit_idx)
            if elapsed < config.cooldown_bars:
                return False
        return True

    def _try_open(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
        config: ValueAreaMultiAttemptPocReversionParams,
        side: Side,
        x_s: float,
        anchors_t: Anchors,
    ) -> Signal:
        q = self._direction_q(side, config.direction_mode)
        tick = config.price_tick
        entry = self._round_to_side(ctx.bar.close, tick, q, mode="submit")
        p = anchors_t["poc"]

        # DirOK / SpaceOK
        if q == 1 and not (p - entry > 0):
            return Signal()
        if q == -1 and not (p - entry < 0):
            return Signal()
        if entry == p:
            return Signal()
        if abs(p - entry) < config.min_target_ticks * tick:
            return Signal()

        side_state = cast(dict[str, SideState], state.extra["va_r30_side_state"])[side]
        break_ticks = self._break_ticks(side, x_s, anchors_t, tick)
        matched_pattern = self._pattern_match(config, side_state, break_ticks)
        if matched_pattern is None:
            return Signal()
        matched_direction = self._direction_class_match(config, side, anchors_t, tick)
        if matched_direction is None:
            return Signal()

        # §8 止损 / F / d_stop
        f_price = x_s - q * config.failure_buffer_ticks * tick
        d_strict = abs(entry - f_price)
        d_atr = self._atr_stop_distance(state, config)
        d_stop = max(d_strict * max(config.stop_widen_multiplier, 1.0), d_atr)
        stop_price = self._round_to_side(entry - q * d_stop, tick, q, mode="stop")
        d_stop_eff = abs(entry - stop_price)
        if d_stop_eff <= 0:
            return Signal()

        anchor_gain = abs(p - entry)
        target_price = self._round_to_side(entry + q * config.target_fraction * anchor_gain, tick, q, mode="target")

        # 原始盈亏比（§6.2 default）
        loss_raw = abs(entry - x_s)
        rr_raw = (anchor_gain / loss_raw) if loss_raw > 0 else math.inf

        # RiskOK
        if q * (target_price - entry) <= 0:
            return Signal()
        if abs(target_price - entry) < config.min_target_ticks * tick:
            return Signal()
        if abs(target_price - entry) / d_stop_eff < config.rr_min:
            return Signal()

        matched_risk = self._risk_class_match(config, rr_raw)
        if matched_risk is None:
            return Signal()

        volume = self._calc_volume(state, entry, d_stop_eff, config)
        if volume <= 0:
            return Signal()

        trade_info: TradeInfo = {
            "side": side,
            "q": q,
            "entry_price": entry,
            "stop_price": stop_price,
            "target_price": target_price,
            "strict_failure_price": f_price,
            "anchor_gain": anchor_gain,
            "d_strict": d_strict,
            "d_stop_eff": d_stop_eff,
            "entry_bar_idx": self._current_bar_idx(state),
            "entry_datetime": ctx.bar.datetime,
            "entry_break_ticks": break_ticks,
            "matched_pattern": matched_pattern,
            "matched_risk": matched_risk,
            "matched_direction": matched_direction,
            "rr_raw": rr_raw,
            "volume": volume,
            "peak_pnl": 0.0,
            "trough_pnl": 0.0,
            "fast_hit_bar": None,
        }
        state.extra["va_r30_trade"] = trade_info
        state.extra["va_r30_trade_count"] = int(state.extra.get("va_r30_trade_count", 0)) + 1
        state.extra["va_r30_poc_touched"] = False

        # §10.2：Enter => Reset_s=1，清空本侧突破跟踪
        self._reset_side_track(state, side)

        action = TRADE_ACTION_BUY if q == 1 else TRADE_ACTION_SELL
        reason = f"va_r30_open_{side}_{matched_pattern}"
        signal = Signal(action=action, reason=reason, volume=volume)
        target_distance = abs(target_price - entry)
        rr_target = (target_distance / d_stop_eff) if d_stop_eff > 0 else math.inf
        signal.alpha = AlphaDiagnostics(
            fields={
                "direction_hypothesis": "long" if q == 1 else "short",
                "entry_reason": "value_area_multi_attempt_poc_reversion",
                "consensus_zone_type": "rolling_value_area",
                "structure_source": f"poc_{config.poc_mode}_profile",
                "entry_boundary": entry,
                "strict_failure_boundary": f_price,
                "expected_profit_boundary": target_price,
                "reference_price": p,
                "poc": p,
                "val": anchors_t["val"],
                "vah": anchors_t["vah"],
                "side": side,
                "direction_mode": config.direction_mode,
                "matched_pattern": matched_pattern,
                "matched_risk": matched_risk,
                "matched_direction": matched_direction,
                "tp_candidates": list(config.tp_candidates),
                "attempts_prev": side_state["attempts"],
                "prev_break_ticks": side_state["prev_break_ticks"],
                "prev_poc_tested": side_state["prev_poc_tested"],
                "break_ticks": break_ticks,
                "anchor_gain": anchor_gain,
                "reacceptance_evidence": "close_re_enters_value_area",
            }
        )
        signal.risk = RiskDiagnostics(
            fields={
                "account_equity": state.capital,
                "target_risk_ratio": config.risk_per_trade,
                "actual_volume": volume,
                "strict_failure_distance": d_strict,
                "actual_stop_distance": d_stop_eff,
                "expected_profit_distance": target_distance,
                "raw_price_r_multiple": rr_target,
                "raw_account_r_multiple": rr_target,
                "rr_raw_default": rr_raw,
                "rr_raw_min": config.rr_raw_min,
                "rr_min": config.rr_min,
                "stop_price": stop_price,
                "target_price": target_price,
                "stop_widen_multiplier": config.stop_widen_multiplier,
                "stop_atr_bars": config.stop_atr_bars,
                "stop_atr_multiplier": config.stop_atr_multiplier,
                "matched_risk": matched_risk,
                "risk_budget_passed": True,
            }
        )
        signal.execution = ExecutionDiagnostics(
            fields={
                "entry_trigger": "bar_close",
                "actual_volume": volume,
                "exit_policy": "priority_stack",
                "strict_stop_distance": d_strict,
                "actual_stop_distance": d_stop_eff,
                "stop_relaxation_multiple": (d_stop_eff / d_strict) if d_strict > 0 else 0.0,
                "entry_bar_idx": trade_info["entry_bar_idx"],
                "tp_candidates": list(config.tp_candidates),
                "strict_close_exit": config.strict_close_exit,
                "max_hold_bars": config.max_hold_bars,
            }
        )
        signal.diagnostics = {
            "entry_price": entry,
            "stop_price": stop_price,
            "target_price": target_price,
            "strict_failure_price": f_price,
            "poc": p,
            "val": anchors_t["val"],
            "vah": anchors_t["vah"],
            "anchor_gain": anchor_gain,
            "break_ticks": break_ticks,
            "side": side,
            "matched_pattern": matched_pattern,
            "matched_risk": matched_risk,
            "matched_direction": matched_direction,
        }
        return signal

    # ── §6 候选判定 ────────────────────────────────────

    @staticmethod
    def _direction_q(side: Side, mode: DirectionMode) -> int:
        if mode == "to_poc":
            return +1 if side == "L" else -1
        return -1 if side == "L" else +1

    @staticmethod
    def _break_ticks(side: Side, x_s: float, anchors_t: Anchors, tick: float) -> float:
        if side == "L":
            return (anchors_t["val"] - x_s) / tick
        return (x_s - anchors_t["vah"]) / tick

    def _pattern_match(
        self,
        config: ValueAreaMultiAttemptPocReversionParams,
        side_state: SideState,
        break_ticks: float,
    ) -> str | None:
        """返回命中的 Ω_pattern 候选标签（C1/C2/C3），无命中返回 None."""
        if not config.pattern_candidates:
            return "none"
        for c in config.pattern_candidates:
            if c == "C1" and side_state["attempts"] == 0:
                return "C1"
            if c == "C2":
                prev = side_state["prev_break_ticks"]
                if prev is not None and break_ticks < prev:
                    return "C2"
            if c == "C3":
                if side_state["prev_poc_tested"] is False:
                    return "C3"
        return None

    def _direction_class_match(
        self,
        config: ValueAreaMultiAttemptPocReversionParams,
        side: Side,
        anchors_t: Anchors,
        tick: float,
    ) -> str | None:
        if not config.direction_candidates:
            return "none"
        d_l = (anchors_t["poc"] - anchors_t["val"]) / tick
        d_u = (anchors_t["vah"] - anchors_t["poc"]) / tick
        tie = d_l == d_u
        near = (side == "L" and d_l < d_u) or (side == "U" and d_u < d_l)
        far = (side == "L" and d_l > d_u) or (side == "U" and d_u > d_l)
        for c in config.direction_candidates:
            if c == "D_near" and (near or tie):
                return "D_near_tie" if tie else "D_near"
            if c == "D_far" and (far or tie):
                return "D_far_tie" if tie else "D_far"
        return None

    def _risk_class_match(
        self,
        config: ValueAreaMultiAttemptPocReversionParams,
        rr_raw: float,
    ) -> str | None:
        if not config.risk_candidates:
            return "none"
        for c in config.risk_candidates:
            if c == "R0":
                return "R0"
            if c == "R1" and rr_raw >= config.rr_raw_min:
                return "R1"
        return None

    # ── §9 退出判定 ────────────────────────────────────

    def _exit_signal(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> Signal:
        trade = state.extra.get("va_r30_trade")
        if trade is None:
            return Signal()
        info = cast(TradeInfo, trade)
        bar = ctx.bar
        q = info["q"]

        anchors = state.extra.get("va_r30_anchors")
        if anchors is not None:
            anchors_t = cast(Anchors, anchors)
            self._update_poc_touch(state, ctx, config, q, anchors_t)

        signed = q * (bar.close - info["entry_price"])
        bar_high_pnl = q * (bar.high - info["entry_price"])
        bar_low_pnl = q * (bar.low - info["entry_price"])
        # MFE：多单看 bar.high、空单看 bar.low（较入场价的最有利偏移）
        bar_mfe = max(bar_high_pnl, bar_low_pnl)
        bar_mae = min(bar_high_pnl, bar_low_pnl)
        if bar_mfe > info["peak_pnl"]:
            info["peak_pnl"] = bar_mfe
        if bar_mae < info["trough_pnl"]:
            info["trough_pnl"] = bar_mae

        # fast_hit：进场后 n_fast 根 bar 内首次达到 η_fast · Anchor
        bars_since_entry = self._current_bar_idx(state) - info["entry_bar_idx"]
        if (
            info["fast_hit_bar"] is None
            and bars_since_entry <= config.fast_window_bars
            and info["peak_pnl"] >= config.fast_fraction * info["anchor_gain"]
        ):
            info["fast_hit_bar"] = self._current_bar_idx(state)

        exit_reason = self._resolve_exit(state, ctx, config, info, signed)
        if not exit_reason:
            return Signal()

        exit_price = self._exit_price(info, bar, exit_reason)
        action = TRADE_ACTION_SELL if q == 1 else TRADE_ACTION_BUY
        signal = Signal(action=action, reason=exit_reason, volume=state.position.volume)
        realized_pnl_per_unit = q * (exit_price - info["entry_price"])
        d_stop_eff = info["d_stop_eff"] if info["d_stop_eff"] > 0 else 0.0
        mfe_r = (info["peak_pnl"] / d_stop_eff) if d_stop_eff > 0 else 0.0
        mae_r = (info["trough_pnl"] / d_stop_eff) if d_stop_eff > 0 else 0.0
        signal.alpha = AlphaDiagnostics(
            fields={
                "direction_hypothesis": "long" if q == 1 else "short",
                "entry_reason": "value_area_multi_attempt_poc_reversion_exit",
                "exit_reason": exit_reason,
                "matched_pattern": info["matched_pattern"],
                "matched_risk": info["matched_risk"],
                "matched_direction": info["matched_direction"],
                "poc_touched": bool(state.extra.get("va_r30_poc_touched", False)),
                "strict_failure_boundary": info["strict_failure_price"],
                "expected_profit_boundary": info["target_price"],
            }
        )
        signal.risk = RiskDiagnostics(
            fields={
                "actual_volume": info["volume"],
                "strict_failure_distance": info["d_strict"],
                "actual_stop_distance": info["d_stop_eff"],
                "expected_profit_distance": abs(info["target_price"] - info["entry_price"]),
                "raw_price_r_multiple": realized_pnl_per_unit / d_stop_eff if d_stop_eff > 0 else 0.0,
                "raw_account_r_multiple": realized_pnl_per_unit / d_stop_eff if d_stop_eff > 0 else 0.0,
                "rr_raw_default": info["rr_raw"],
                "matched_risk": info["matched_risk"],
            }
        )
        signal.execution = ExecutionDiagnostics(
            fields={
                "exit_reason": exit_reason,
                "exit_policy": self._exit_policy_for(exit_reason),
                "exit_price": exit_price,
                "holding_bars": bars_since_entry,
                "actual_volume": info["volume"],
                "strict_stop_distance": info["d_strict"],
                "actual_stop_distance": info["d_stop_eff"],
                "stop_relaxation_multiple": (info["d_stop_eff"] / info["d_strict"]) if info["d_strict"] > 0 else 0.0,
                "mae": info["trough_pnl"],
                "mfe": info["peak_pnl"],
                "mae_r": mae_r,
                "mfe_r": mfe_r,
                "realized_pnl_per_unit": realized_pnl_per_unit,
            }
        )
        signal.diagnostics = {
            "exit_reason": exit_reason,
            "exit_price": exit_price,
            "entry_price": info["entry_price"],
            "stop_price": info["stop_price"],
            "target_price": info["target_price"],
            "holding_bars": float(bars_since_entry),
            "peak_pnl": info["peak_pnl"],
            "trough_pnl": info["trough_pnl"],
        }
        self._close_trade(state, config, info)
        return signal

    @staticmethod
    def _exit_price(info: TradeInfo, bar: Bar, exit_reason: str) -> float:
        """按 spec §9.2 退出价规则给出成交价：
        - stop_loss / TP_fixed 用挂单价（stop_price / target_price）
        - 其它策略级退出用 bar.close."""
        if exit_reason == "stop_loss":
            return info["stop_price"]
        if exit_reason == "take_profit_fixed":
            return info["target_price"]
        return bar.close

    @staticmethod
    def _exit_policy_for(exit_reason: str) -> str:
        if exit_reason == "stop_loss":
            return "stop"
        if exit_reason == "strict_failure_close":
            return "strict"
        if exit_reason.startswith("take_profit"):
            return "take_profit"
        if exit_reason == "force_flat":
            return "force_flat"
        if exit_reason == "time_exit":
            return "time_exit"
        return "unknown"

    def _resolve_exit(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
        config: ValueAreaMultiAttemptPocReversionParams,
        info: TradeInfo,
        current_signed: float,
    ) -> str:
        """spec §9.2 退出优先级：
        stop_loss > strict_failure_close > TP_fixed > TP_soft > force_flat > time_exit."""
        bar = ctx.bar
        q = info["q"]

        if q == 1 and bar.low <= info["stop_price"]:
            return "stop_loss"
        if q == -1 and bar.high >= info["stop_price"]:
            return "stop_loss"

        if config.strict_close_exit:
            if q == 1 and bar.close <= info["strict_failure_price"]:
                return "strict_failure_close"
            if q == -1 and bar.close >= info["strict_failure_price"]:
                return "strict_failure_close"

        if "TP_fixed" in config.tp_candidates:
            if q == 1 and bar.high >= info["target_price"]:
                return "take_profit_fixed"
            if q == -1 and bar.low <= info["target_price"]:
                return "take_profit_fixed"

        if self._tp_armed_retrace_hit(config, info, current_signed):
            return "take_profit_armed_retrace"
        if self._tp_fast_time_hit(state, config, info):
            return "take_profit_fast_time"

        if self._is_force_flat_time(bar.datetime.time(), config):
            return "force_flat"

        bars_since_entry = self._current_bar_idx(state) - info["entry_bar_idx"]
        if bars_since_entry >= config.max_hold_bars:
            return "time_exit"

        return ""

    @staticmethod
    def _tp_armed_retrace_hit(
        config: ValueAreaMultiAttemptPocReversionParams,
        info: TradeInfo,
        current_signed: float,
    ) -> bool:
        if "TP_armed_retrace" not in config.tp_candidates:
            return False
        arm_level = config.arm_fraction * info["anchor_gain"]
        if info["peak_pnl"] < arm_level:
            return False
        retrace = info["peak_pnl"] - current_signed
        return retrace >= config.retrace_fraction * info["anchor_gain"]

    def _tp_fast_time_hit(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        config: ValueAreaMultiAttemptPocReversionParams,
        info: TradeInfo,
    ) -> bool:
        if "TP_fast_time" not in config.tp_candidates:
            return False
        hit_bar = info["fast_hit_bar"]
        if hit_bar is None:
            return False
        return self._current_bar_idx(state) - hit_bar >= config.fast_hold_bars

    def _update_poc_touch(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        ctx: BarContext,
        config: ValueAreaMultiAttemptPocReversionParams,
        q: int,
        anchors_t: Anchors,
    ) -> None:
        if state.extra.get("va_r30_poc_touched", False):
            return
        bar = ctx.bar
        delta = config.poc_touch_tolerance_ticks * config.price_tick
        touched = (q == 1 and bar.high >= anchors_t["poc"] - delta) or (q == -1 and bar.low <= anchors_t["poc"] + delta)
        if touched:
            state.extra["va_r30_poc_touched"] = True

    def _close_trade(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        config: ValueAreaMultiAttemptPocReversionParams,
        info: TradeInfo,
    ) -> None:
        """spec §9.3：交易关闭后回填 A_s / B_s^- / Z_s^- / T_last_exit + ExitEvent 刷新."""
        side_state = cast(dict[str, SideState], state.extra["va_r30_side_state"])[info["side"]]
        side_state["attempts"] += 1
        side_state["prev_break_ticks"] = info["entry_break_ticks"]
        side_state["prev_poc_tested"] = bool(state.extra.get("va_r30_poc_touched", False))
        state.extra["va_r30_last_exit_bar_idx"] = self._current_bar_idx(state)
        state.extra.pop("va_r30_trade", None)
        state.extra.pop("va_r30_poc_touched", None)
        self._exit_refresh(state, config)

    # ── 辅助 ─────────────────────────────────────────────

    @staticmethod
    def _round_tick(price: float, tick: float) -> float:
        return round(price / tick) * tick

    @staticmethod
    def _round_to_side(
        price: float,
        tick: float,
        q: int,
        mode: Literal["submit", "stop", "target"],
    ) -> float:
        """按 §2 tick 舍入规则将订单价对齐到桶."""
        if tick <= 0:
            return price
        k = price / tick
        if mode == "submit":
            return (math.ceil(k) if q == 1 else math.floor(k)) * tick
        if mode == "stop":
            return (math.floor(k) if q == 1 else math.ceil(k)) * tick
        return (math.floor(k) if q == 1 else math.ceil(k)) * tick

    def _atr_stop_distance(
        self,
        state: State[ValueAreaMultiAttemptPocReversionParams],
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> float:
        if config.stop_atr_bars <= 0 or config.stop_atr_multiplier <= 0:
            return 0.0
        history: deque[Bar] | None = state.extra.get("va_r30_bar_history")
        if not history:
            return 0.0
        bars = list(history)[-(config.stop_atr_bars + 1) :]
        if len(bars) < 2:
            return 0.0
        trs: list[float] = []
        prev_close = bars[0].close
        for bar in bars[1:]:
            tr = max(
                bar.high - bar.low,
                abs(bar.high - prev_close),
                abs(bar.low - prev_close),
            )
            trs.append(tr)
            prev_close = bar.close
        if not trs:
            return 0.0
        return (sum(trs) / len(trs)) * config.stop_atr_multiplier

    @staticmethod
    def _calc_volume(
        state: State[ValueAreaMultiAttemptPocReversionParams],
        entry: float,
        d_stop_eff: float,
        config: ValueAreaMultiAttemptPocReversionParams,
    ) -> int:
        risk_amount = state.capital * config.risk_per_trade
        risk_per_lot = d_stop_eff * state.contract_size
        if risk_per_lot <= 0:
            return 0
        risk_volume = int(risk_amount / risk_per_lot)
        margin_volume = position_size(
            state.capital, config.max_position_ratio, entry, state.contract_size, state.margin
        )
        return max(0, min(risk_volume, margin_volume))

    @staticmethod
    def _parse_time(value: str) -> time:
        hour, minute = value.split(":", maxsplit=1)
        return time(int(hour), int(minute))

    @classmethod
    def _in_entry_window(cls, current: time, config: ValueAreaMultiAttemptPocReversionParams) -> bool:
        return cls._parse_time(config.trade_start_time) <= current <= cls._parse_time(config.last_entry_time)

    @classmethod
    def _is_force_flat_time(cls, current: time, config: ValueAreaMultiAttemptPocReversionParams) -> bool:
        return current >= cls._parse_time(config.force_flat_time)
