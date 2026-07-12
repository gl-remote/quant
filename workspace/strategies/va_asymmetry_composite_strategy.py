"""
文件级元信息：
- 创建背景：va-asymmetry-composite 主题 B 层执行模块，被回测业务调用（Strategy 子类，
  由 Bridge 提供 State + BarContext）。严格实现
  docs/research/themes/va-asymmetry-composite/strategy-math-spec.md §2 / §3 定义的
  入场、止损、波动率-时间退出与 §3.1 名义暴露 sizing。
- 用途：单合约 on_bar 决策——A 层 tier/direction/daily_atr_bps 由策略内部每日状态机
  自算（datafeed 提供 1d 指标 + 策略自维护日线缓冲区 → t-PIT → 六阵营），
  不再依赖外部 timeline parquet。
- 注意事项：
    * 严格按 spec §2/§3 落地，未定锚点（H_vol{L:B_L,S:B_S} / σ_day）通过参数暴露；
    * 主周期 = spec §0 base_tf = 1m（波动率-时间退出 §2.3 所需的对数收益粒度）；
    * spec §7.1（2026-07-12 修正）：止损 ATR 改用 A 层日线 SMA(10) ATR（daily_atr_bps），
      不再通过桥梁请求 1h RMA(10) ATR 指标；
    * §3.3 组合级 Cap 属于组合/桥接层职责，超出单合约 on_bar 范围；
    * §3.4 单日熔断按 spec §0 关闭；未实现，如需请由上层组装。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import isnan, log
from typing import override

import numpy as np
import pandas as pd
from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)

from .classifiers.poc_va import (
    ClassifierConfig,
    classify_tier,
    compute_transition_series,
    roll_t_pit,
    tier_direction,
    volume_weighted_skew,
)
from .core import (
    CORE_VERSION,
    Fill,
    Signal,
    State,
    Strategy,
    placeholder_diagnostics,
)
from .runtime import DataRequirements, EventsRequirements, PeriodRequirements
from .runtime.requirements import BarContext
from .strategy_aspects.indicators import DAILY_ATR_BPS

# ---------------------------------------------------------------------------
# spec §0：生产配置（可通过参数覆盖，默认对齐 spec）
# ---------------------------------------------------------------------------


@dataclass
class VAAsymmetryCompositeParams:
    """VA 非对称复合策略 B 层参数（对齐 spec §0）。"""

    # ── 周期 ─────────────────────────────────────────────────────
    base_tf: str = "1m"
    """spec §0 base_tf：波动率-时间退出的 bar 粒度（§2.3）。策略主周期。"""

    entry_tf: str = "5m"
    """spec §0 entry_tf：入场 K 线粒度（§2.1）；用于 open_grace 语义对齐。"""

    atr_tf: str = "1h"
    """[legacy] spec §7.1 已修正：止损 ATR 改用 A 层日线 SMA(10) ATR，本字段不再生效。"""

    atr_period: int = 10
    """[legacy] spec §7.1 已修正：止损 ATR 改用 A 层日线 SMA(10) ATR，本字段不再生效。"""

    # ── §2.1 入场 baseline 增强 ─────────────────────────────────
    open_grace_min: float = 5.0
    """spec §0 open_grace_min：晚于当日 session open ≥ 该分钟数才允许开仓。"""

    # ── §2.2 止损 ─────────────────────────────────────────────
    k_sl_long: float = 1.0
    """spec §0 K_SL{L}：多域止损 ATR 倍数。"""

    k_sl_short: float = 1.75
    """spec §0 K_SL{S}：空域止损 ATR 倍数。"""

    # ── §2.3 波动率-时间退出 ─────────────────────────────────
    h_vol_long: float = 8.0
    """spec §0 H_vol{L: B_L}：多域累积波动率预算 (× σ_day)。B_L 由研究锚定。"""

    h_vol_short: float = 10.0
    """spec §0 H_vol{S: B_S}：空域累积波动率预算 (× σ_day)。B_S 由研究锚定。"""

    sigma_day_from_atr: bool = True
    """spec §2.3 σ_day 缺省来源：True 时 σ_day := daily_atr_bps / 10000；
    False 时须由外部提供 sigma_day 值。"""

    # ── §3.1 目标仓位 ────────────────────────────────────────
    risk_per_trade: float = 0.02
    """spec §0 RiskPerTrade：单笔风险预算 × Equity。"""

    integer_lots: bool = False
    """True 时对手数向下取整（实盘整手约束）；False 保留分数手以对齐研究引擎口径。"""

    # ── 分类器参数 ───────────────────────────────────────────
    skew_rank_win: int = 10
    atr_rank_win: int = 10
    trend_win: int = 10
    atr_entry_win: int = 10
    trend_entry_win: int = 10
    """spec §0 窗口生产配置：各参数独立归一化窗口。与 ClassifierConfig 对齐。"""


# ---------------------------------------------------------------------------
# 策略主体
# ---------------------------------------------------------------------------


class VAAsymmetryCompositeStrategy(Strategy[VAAsymmetryCompositeParams]):
    """VA 非对称复合策略 · B 层执行核心。

    严格实现 spec §2/§3.1：
      §2.1 入场：A 层命中 + 首根 bar 之后 + t_bar - t_open ≥ open_grace_min
                → 按 tier 方向开仓（Bridge 用当前 bar close 成交）。
      §2.2 止损：SL = entry ∓ K_SL·A，A = 入场当日盘前日线 SMA(10) ATR（spec §7.1）。
      §2.3 时间退出：ΔV_k = |log(C_k/C_{k-1})|/σ_day；V ≥ H_vol(τ) 后下一根 base_tf 收盘平仓。
      §2.4 优先级：SL > 时间退出（同 bar 同时触发取 SL）。
      §3.1 sizing：Notional = RiskPerTrade·Equity / (K_SL·daily_atr_bps)，qty = Notional/(price·contract_size)。
    """

    name: str = "va_asymmetry_composite"
    VERSION: str = f"{CORE_VERSION}-va-b2"

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------
    # 数据需求
    # ------------------------------------------------------------

    @override
    def data_requirements(self, config: VAAsymmetryCompositeParams) -> DataRequirements:
        """声明 base_tf（1m）用于 §2.3 波动率-时间退出 + 1d 周期用于日线 ATR 指标。

        止损 ATR 来源：datafeed 在 1d 周期上计算 DAILY_ATR_BPS(10)，
        策略通过 ctx.multi["1d"].indicator(...) 读取昨日已完成值。
        """
        return DataRequirements(
            periods={
                config.base_tf: PeriodRequirements(lookback_bars=2),
                "1d": PeriodRequirements(lookback_bars=25),
            },
            indicators={
                "1d": [DAILY_ATR_BPS],
            },
            events=EventsRequirements.no_events(),
        )

    # ------------------------------------------------------------
    # on_bar 主入口
    # ------------------------------------------------------------

    @override
    @placeholder_diagnostics
    def on_bar(self, state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> Signal:
        # 每根 base_tf bar 维护 session 锚点（t_open）与前一日 5m bar 缓冲区
        self._anchor_session(state, ctx)
        self._accumulate_session_bar(state, ctx)

        # 新交易日：结算昨日 A3_skew → 更新滚动缓冲区 → t-PIT → 今日 tier
        self._on_new_day(state, ctx)

        if state.position.direction:
            return self._on_holding(state, ctx)
        return self._on_flat(state, ctx)

    @override
    def on_fill(self, fill: Fill) -> None:
        # State 是唯一真实数据源；Bridge 会同步 position。
        pass

    # ------------------------------------------------------------
    # session 锚定：spec §2.1 需要 t_open 基准；§2.3 需要 prev_close
    # ------------------------------------------------------------

    @staticmethod
    def _anchor_session(state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> None:
        bar = ctx.bar
        today = bar.datetime.date()
        if state.extra.get("va_session_date") != today:
            state.extra["va_session_date"] = today
            state.extra["va_session_open"] = bar.datetime

    # ------------------------------------------------------------
    # A 层每日状态机：1m bar → 5m 聚合 → session 缓冲区 → 新日结算
    # ------------------------------------------------------------

    @staticmethod
    def _accumulate_session_bar(state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> None:
        """将 1m bar 聚合到 5m 粒度并追加到 session 缓冲区。

        session 缓冲区 (va_session_5m_bars) 存储当日每个已完成 5m bar 的 OHLCV，
        供收盘/下一交易日开盘时计算 A3_skew 使用。
        """
        bar = ctx.bar
        bar_time = bar.datetime
        five_min_key = (bar_time.hour * 60 + bar_time.minute) // 5

        last_key = state.extra.get("va_last_5m_key", -1)
        if five_min_key != last_key:
            # 新 5m bar：刷出上一个
            prev_bar = state.extra.get("va_current_5m")
            if prev_bar is not None:
                bars: list[dict[str, float]] = state.extra.setdefault("va_session_5m_bars", [])
                bars.append(prev_bar)
            state.extra["va_current_5m"] = {
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
            state.extra["va_last_5m_key"] = five_min_key
        else:
            # 同一 5m bar 内：更新 OHLC
            cur = state.extra.setdefault("va_current_5m", {})
            if not cur:
                cur.update(
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                )
            else:
                cur["high"] = max(float(cur.get("high", 0)), float(bar.high))
                cur["low"] = min(float(cur.get("low", float("inf"))), float(bar.low))
                cur["close"] = float(bar.close)
                cur["volume"] = float(cur.get("volume", 0)) + float(bar.volume)

    # ------------------------------------------------------------
    # A 层每日状态机：新交易日结算 → 滚动缓冲区 → t-PIT → tier
    # ------------------------------------------------------------

    _INDICATOR_COL: str = "1d_daily_atr_bps_10"
    """generate_indicator_column_name("daily_atr_bps", {"period": 10}, period="1d") 的硬编码结果。"""

    @staticmethod
    def _on_new_day(state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> None:
        """新交易日结算：昨日 A3_skew → 更新滚动缓冲区 → t-PIT → 今日 tier。

        仅在 va_session_date 变更后的首根 bar 执行一次。
        tier 结果存为 state.extra["va_today_{tier,direction,daily_atr_bps}"]。
        """
        if state.extra.get("va_tier_computed_date") == state.extra.get("va_session_date"):
            return

        config = state.strategy_config
        today = state.extra["va_session_date"]

        # ── 1. 结算昨日 session：计算 A3_skew ──
        yesterday_skew = float("nan")
        yesterday_close = float("nan")
        bars: list[dict[str, float]] = state.extra.get("va_session_5m_bars", [])
        if bars:
            session_closes = np.array([b["close"] for b in bars], dtype=float)
            session_volumes = np.array([b["volume"] for b in bars], dtype=float)
            yesterday_skew = volume_weighted_skew(session_closes, session_volumes)
            yesterday_close = float(session_closes[-1])
            # 清空旧缓冲区，开始新 session
            state.extra["va_session_5m_bars"] = []

        # ── 2. 读取昨日 daily_atr_bps（idx=-2 = 昨日已完成 1d bar）──
        atr_view = ctx.multi.get("1d")
        yesterday_atr_bps = float("nan")
        if atr_view is not None:
            val = atr_view.indicator(VAAsymmetryCompositeStrategy._INDICATOR_COL, -2)
            if val is not None:
                yesterday_atr_bps = float(val)

        # ── 3. 更新滚动缓冲区 ──
        skews: deque[float] = state.extra.setdefault("va_skew_buf", deque(maxlen=40))
        atrs: deque[float] = state.extra.setdefault("va_atr_bps_buf", deque(maxlen=40))
        closes: deque[float] = state.extra.setdefault("va_close_buf", deque(maxlen=40))

        if not np.isnan(yesterday_skew):
            skews.append(yesterday_skew)
        if not np.isnan(yesterday_atr_bps):
            atrs.append(yesterday_atr_bps)
        if not np.isnan(yesterday_close):
            closes.append(yesterday_close)

        # ── 4. t-PIT → tier 分类（至少需要 window=20 天历史）──
        class_config = ClassifierConfig(
            skew_rank_win=config.skew_rank_win,
            atr_rank_win=config.atr_rank_win,
            trend_win=config.trend_win,
            atr_entry_win=config.atr_entry_win,
            trend_entry_win=config.trend_entry_win,
        )
        tier_name: str | None = None
        direction: str = ""
        daily_atr_bps = float("nan")

        min_len = class_config.skew_rank_win  # 20
        trend_min_len = (class_config.trend_entry_win - 1) + class_config.trend_win  # (M-1)+trend_win, spec §1.1
        if len(skews) >= min_len and len(atrs) >= min_len and len(closes) >= trend_min_len:
            # spec §1.1: trend_ret_M = log(C_d / C_{d-M+1}), M = trend_entry_win
            trend_offset = class_config.trend_entry_win - 1  # M-1 = 9 (C_d vs C_{d-M+1})
            n_close = len(closes)

            # 构造滚动窗口 Series（用全部可用数据，使 MAD 有足够有效样本）
            s_skew = pd.Series(list(skews), dtype=float)
            s_atr = pd.Series(list(atrs), dtype=float)
            # trend: 从最早的 (offset, close_offset) 开始逐日计算 log return
            t_vals = []
            for i in range(trend_offset, n_close):
                if closes[i - trend_offset] > 0 and closes[i] > 0:
                    t_vals.append(float(log(closes[i] / closes[i - trend_offset])))
                else:
                    t_vals.append(float("nan"))
            s_trend = pd.Series(t_vals, dtype=float)

            # t-PIT 归一化
            r_s_raw = roll_t_pit(s_skew, class_config.skew_rank_win)
            r_s = 1.0 - r_s_raw.iloc[-1]  # 互补
            r_a_series = roll_t_pit(s_atr, class_config.atr_rank_win)
            r_a = float(r_a_series.iloc[-1])
            r_t_series = roll_t_pit(s_trend, class_config.trend_win)
            r_t = float(r_t_series.iloc[-1])

            # trans 从 r_a 系列派生
            trans_df = compute_transition_series(r_a_series)
            trans = str(trans_df["trans"].iloc[-1])

            if not np.isnan(r_s) and not np.isnan(r_a) and not np.isnan(r_t):
                tier_name = classify_tier(float(r_s), float(r_a), float(r_t), trans)
                if tier_name is not None:
                    direction = tier_direction(tier_name)

            # 今日使用的 daily_atr_bps = 昨日值 (止损/sizing/sigma)
            daily_atr_bps = yesterday_atr_bps

        state.extra["va_today_tier"] = tier_name
        state.extra["va_today_direction"] = direction
        state.extra["va_today_daily_atr_bps"] = daily_atr_bps
        state.extra["va_tier_computed_date"] = today

    # ------------------------------------------------------------
    # 持仓分支：§2.2 SL / §2.3 时间退出 / §2.4 优先级
    # ------------------------------------------------------------

    def _on_holding(self, state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> Signal:
        bar = ctx.bar
        direction = state.position.direction
        close_action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY

        stop_price = float(state.extra.get("va_stop_price", 0.0))
        # §2.2 + §2.4：SL 优先
        hit_sl = (direction == TRADE_DIRECTION_LONG and bar.low <= stop_price) or (
            direction == TRADE_DIRECTION_SHORT and bar.high >= stop_price
        )
        if hit_sl and stop_price > 0:
            self._clear_holding(state)
            return Signal(
                action=close_action,
                reason="SL",
                volume=state.position.volume,
                diagnostics={"stop_price": stop_price},
            )

        # §2.3：先执行"上一根已触发的下一根 base_tf 收盘平仓"
        if state.extra.get("va_time_exit_pending"):
            v_final = float(state.extra.get("va_cum_vol", 0.0))
            h_vol = float(state.extra.get("va_h_vol", 0.0))
            self._clear_holding(state)
            return Signal(
                action=close_action,
                reason="TIME",
                volume=state.position.volume,
                diagnostics={"cum_vol": v_final, "h_vol": h_vol},
            )

        # §2.3：累积当根 base_tf 波动增量 ΔV_k = |log(C_k/C_{k-1})|/σ_day
        prev_close = float(state.extra.get("va_prev_close", 0.0))
        sigma_day = float(state.extra.get("va_sigma_day", 0.0))
        if prev_close > 0 and sigma_day > 0 and bar.close > 0:
            r_k = log(bar.close / prev_close)
            delta_v = abs(r_k) / sigma_day
            cum_vol = float(state.extra.get("va_cum_vol", 0.0)) + delta_v
            state.extra["va_cum_vol"] = cum_vol
            h_vol = float(state.extra.get("va_h_vol", 0.0))
            if h_vol > 0 and cum_vol >= h_vol:
                # 触发：下一根 base_tf bar 收盘平仓
                state.extra["va_time_exit_pending"] = True

        state.extra["va_prev_close"] = float(bar.close)
        return Signal()

    # ------------------------------------------------------------
    # 空仓分支：§2.1 baseline 入场 + §3.1 sizing
    # ------------------------------------------------------------

    def _on_flat(self, state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        bar = ctx.bar

        # 更新 prev_close 供 §2.3 用；空仓时不累积，只保持基准
        state.extra["va_prev_close"] = float(bar.close)

        today = bar.datetime.date()
        # 当日只开一次（spec §2.1 baseline）
        if state.extra.get("va_last_entry_date") == today:
            return Signal()

        # §2.1：t_bar - t_open ≥ open_grace_min
        session_open = state.extra.get("va_session_open", bar.datetime)
        elapsed_min = (bar.datetime - session_open).total_seconds() / 60.0
        if elapsed_min < config.open_grace_min:
            return Signal()

        # A 层命中：从每日状态机读取
        direction = str(state.extra.get("va_today_direction", ""))
        if direction not in (TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT):
            return Signal()

        tier_name = str(state.extra.get("va_today_tier", ""))

        # §2.2 ATR：spec §7.1 修正——使用 datafeed 1d 周期 DAILY_ATR_BPS 指标昨日值
        entry_price = float(bar.close)
        daily_atr_bps = float(state.extra.get("va_today_daily_atr_bps", float("nan")))
        if entry_price <= 0 or isnan(daily_atr_bps) or daily_atr_bps <= 0:
            return Signal()
        atr_price = entry_price * daily_atr_bps / 10000.0

        is_long = direction == TRADE_DIRECTION_LONG
        k_sl = config.k_sl_long if is_long else config.k_sl_short
        h_vol = config.h_vol_long if is_long else config.h_vol_short
        sign = 1 if is_long else -1

        # §2.2 止损价：SL = entry ∓ K_SL · A，其中 A = entry_price × daily_atr_bps/10000
        stop_price = entry_price - sign * k_sl * atr_price

        # §3.1 名义暴露 sizing
        stop_dist_frac = k_sl * daily_atr_bps / 10000.0
        if stop_dist_frac <= 0:
            return Signal()
        notional_frac = config.risk_per_trade / stop_dist_frac
        qty = notional_frac * state.capital / (entry_price * state.contract_size)
        if config.integer_lots:
            qty = float(int(qty))
        if qty <= 0:
            return Signal()

        # §2.3 σ_day：daily_atr_bps / 10000（不再依赖外部 timeline）
        sigma_day = daily_atr_bps / 10000.0
        if sigma_day <= 0:
            return Signal()

        # 播种持仓 bookkeeping
        state.extra["va_stop_price"] = stop_price
        state.extra["va_h_vol"] = h_vol
        state.extra["va_sigma_day"] = sigma_day
        state.extra["va_cum_vol"] = 0.0
        state.extra["va_time_exit_pending"] = False
        state.extra["va_last_entry_date"] = today

        action = TRADE_ACTION_BUY if is_long else TRADE_ACTION_SELL
        return Signal(
            action=action,
            reason=f"entry_{tier_name}",
            volume=qty,
            diagnostics={
                "tier": tier_name,
                "direction": direction,
                "entry_price": entry_price,
                "atr_price": atr_price,
                "daily_atr_bps": daily_atr_bps,
                "stop_price": stop_price,
                "k_sl": k_sl,
                "h_vol": h_vol,
                "sigma_day": sigma_day,
                "notional_frac": notional_frac,
            },
        )

    # ------------------------------------------------------------
    # helper
    # ------------------------------------------------------------

    @staticmethod
    def _clear_holding(state: State[VAAsymmetryCompositeParams]) -> None:
        for key in (
            "va_stop_price",
            "va_h_vol",
            "va_sigma_day",
            "va_cum_vol",
            "va_time_exit_pending",
        ):
            state.extra.pop(key, None)
