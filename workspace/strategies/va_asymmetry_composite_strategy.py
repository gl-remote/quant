"""
文件级元信息：
- 创建背景：va-asymmetry-composite 主题 B 层执行模块，被回测业务调用（Strategy 子类，
  由 Bridge 提供 State + BarContext）。严格实现
  docs/research/themes/va-asymmetry-composite/strategy-math-spec.md §2 / §3 定义的
  入场、止损、波动率-时间退出与 §3.1 名义暴露 sizing。
- 用途：单合约 on_bar 决策——A 层结论（tier / direction / daily_atr_bps [ / sigma_day ]）
  由上游 timeline parquet 提供，本策略只做 (contract, date)→tier 查表并按 spec 执行。
- 注意事项：
    * 严格按 spec §2/§3 落地，未定锚点（H_vol{L:B_L,S:B_S} / σ_day）通过参数暴露；
    * 主周期 = spec §0 base_tf = 1m（波动率-时间退出 §2.3 所需的对数收益粒度），
      §2.2 止损用的 1h RMA(10) ATR 由 data_requirements 声明 "1h" 周期 + ATR 指标；
    * §3.3 组合级 Cap 属于组合/桥接层职责，超出单合约 on_bar 范围；
    * §3.4 单日熔断按 spec §0 关闭；未实现，如需请由上层组装。
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import date as _date
from math import isnan, log
from pathlib import Path
from typing import Any, override

from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)

from .core import (
    CORE_VERSION,
    Fill,
    Signal,
    State,
    Strategy,
    placeholder_diagnostics,
)
from .core.indicators import generate_indicator_column_name
from .runtime import DataRequirements, EventsRequirements, PeriodRequirements
from .runtime.requirements import BarContext
from .strategy_aspects.indicators import ATR

# ---------------------------------------------------------------------------
# spec §0：生产配置（可通过参数覆盖，默认对齐 spec）
# ---------------------------------------------------------------------------

_DEFAULT_TIMELINE: str = "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet"


@dataclass
class VAAsymmetryCompositeParams:
    """VA 非对称复合策略 B 层参数（对齐 spec §0）。"""

    # ── 周期 ─────────────────────────────────────────────────────
    base_tf: str = "1m"
    """spec §0 base_tf：波动率-时间退出的 bar 粒度（§2.3）。策略主周期。"""

    entry_tf: str = "5m"
    """spec §0 entry_tf：入场 K 线粒度（§2.1）；用于 open_grace 语义对齐。"""

    atr_tf: str = "1h"
    """spec §2.2 止损 ATR 的 K 线粒度（1h RMA/Wilder）。"""

    atr_period: int = 10
    """spec §2.2 ATR 平滑 α = 1/atr_period；默认 10（即 α=0.1）。"""

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
    False 时须由 A 层 timeline parquet 提供 sigma_day 列（fraction，例 0.008）。"""

    # ── §3.1 目标仓位 ────────────────────────────────────────
    risk_per_trade: float = 0.02
    """spec §0 RiskPerTrade：单笔风险预算 × Equity。"""

    integer_lots: bool = False
    """True 时对手数向下取整（实盘整手约束）；False 保留分数手以对齐研究引擎口径。"""

    # ── A 层查表 ─────────────────────────────────────────────
    a_layer_timeline_path: str = _DEFAULT_TIMELINE
    """A 层 (contract, date)→(tier, direction, daily_atr_bps [, sigma_day]) 查表 parquet。"""


# ---------------------------------------------------------------------------
# spec §1.3：阵营名 → 多/空域
# ---------------------------------------------------------------------------


def _tier_direction(tier: str) -> str:
    """spec §1.3：L_* → long；S_* → short；其他 → 空串。"""
    if tier.startswith("L_"):
        return TRADE_DIRECTION_LONG
    if tier.startswith("S_"):
        return TRADE_DIRECTION_SHORT
    return ""


# ---------------------------------------------------------------------------
# 策略主体
# ---------------------------------------------------------------------------


class VAAsymmetryCompositeStrategy(Strategy[VAAsymmetryCompositeParams]):
    """VA 非对称复合策略 · B 层执行核心。

    严格实现 spec §2/§3.1：
      §2.1 入场：A 层命中 + 首根 bar 之后 + t_bar - t_open ≥ open_grace_min
                → 按 tier 方向开仓（Bridge 用当前 bar close 成交）。
      §2.2 止损：SL = entry ∓ K_SL·A，A = 入场当日盘前 1h RMA(10) ATR。
      §2.3 时间退出：ΔV_k = |log(C_k/C_{k-1})|/σ_day；V ≥ H_vol(τ) 后下一根 base_tf 收盘平仓。
      §2.4 优先级：SL > 时间退出（同 bar 同时触发取 SL）。
      §3.1 sizing：Notional = RiskPerTrade·Equity / (K_SL·ATR_bps)，qty = Notional/(price·contract_size)。
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
        """声明主周期 base_tf 与 §2.2 所需 1h RMA(10) ATR。

        主周期 = base_tf（1m）——回测引擎会按最小周期驱动 on_bar，符合 §2.3
        对数收益需 1m 粒度的语义；atr_tf（1h）通过 multi 视图 + ATR 指标提供。
        """
        return DataRequirements(
            periods={
                config.base_tf: PeriodRequirements(lookback_bars=2),
                config.atr_tf: PeriodRequirements(lookback_bars=config.atr_period + 5),
            },
            indicators={config.atr_tf: [ATR(config.atr_period)]},
            events=EventsRequirements.no_events(),
        )

    # ------------------------------------------------------------
    # on_bar 主入口
    # ------------------------------------------------------------

    @override
    @placeholder_diagnostics
    def on_bar(self, state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> Signal:
        self._ensure_a_table(state, state.strategy_config)

        # 每根 base_tf bar 都要维护 session 锚点与前一根收盘（用于 §2.3 累积）
        self._anchor_session(state, ctx)

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

        # A 层命中
        table: dict[_date, dict[str, Any]] = state.extra.get("va_table", {})
        record = table.get(today)
        if record is None:
            return Signal()

        direction = str(record["direction"])
        if direction not in (TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT):
            return Signal()

        # §2.2 ATR：入场当日盘前 1h RMA(10) ATR，取当前 multi["1h"] 最新值（回测中即最近可见）
        atr_price = self._latest_atr(ctx, config)
        entry_price = float(bar.close)
        if entry_price <= 0 or atr_price <= 0 or isnan(atr_price):
            return Signal()

        is_long = direction == TRADE_DIRECTION_LONG
        k_sl = config.k_sl_long if is_long else config.k_sl_short
        h_vol = config.h_vol_long if is_long else config.h_vol_short
        sign = 1 if is_long else -1

        # §2.2 止损价：SL = entry ∓ K_SL · A
        stop_price = entry_price - sign * k_sl * atr_price

        # §3.1 名义暴露 sizing
        atr_bps = atr_price / entry_price * 10000.0
        stop_dist_frac = k_sl * atr_bps / 10000.0
        if stop_dist_frac <= 0:
            return Signal()
        notional_frac = config.risk_per_trade / stop_dist_frac
        qty = notional_frac * state.capital / (entry_price * state.contract_size)
        if config.integer_lots:
            qty = float(int(qty))
        if qty <= 0:
            return Signal()

        # §2.3 σ_day：优先 A 层 timeline 提供；否则回退 daily_atr_bps/10000
        sigma_day = self._resolve_sigma_day(record, atr_bps, config)
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
            reason=f"entry_{record['tier']}",
            volume=qty,
            diagnostics={
                "tier": record["tier"],
                "direction": direction,
                "entry_price": entry_price,
                "atr_price": atr_price,
                "atr_bps": atr_bps,
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
    def _latest_atr(ctx: BarContext, config: VAAsymmetryCompositeParams) -> float:
        """从 ctx.multi[atr_tf] 读取 §2.2 需要的 1h RMA(atr_period) ATR。"""
        view = ctx.multi.get(config.atr_tf)
        if view is None:
            return float("nan")
        col = generate_indicator_column_name("atr", {"period": config.atr_period}, period=config.atr_tf)
        value = view.indicator(col)
        return float(value) if value is not None else float("nan")

    @staticmethod
    def _resolve_sigma_day(
        record: dict[str, Any],
        atr_bps: float,
        config: VAAsymmetryCompositeParams,
    ) -> float:
        """spec §2.3 σ_day：优先 A 层 record["sigma_day"]，否则 daily_atr_bps/10000。"""
        raw = record.get("sigma_day")
        if raw is not None:
            try:
                v = float(raw)
                if v > 0:
                    return v
            except (TypeError, ValueError):
                pass
        if not config.sigma_day_from_atr:
            return 0.0
        return atr_bps / 10000.0

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

    # ------------------------------------------------------------
    # A 层查表：从 timeline parquet 惰性预加载 (date → 记录)
    # ------------------------------------------------------------

    def _ensure_a_table(
        self,
        state: State[VAAsymmetryCompositeParams],
        config: VAAsymmetryCompositeParams,
    ) -> None:
        if state.extra.get("va_a_initialized"):
            return
        state.extra["va_a_initialized"] = True
        state.extra["va_table"] = self._load_a_table(config.a_layer_timeline_path, state.symbol)

    @staticmethod
    def _load_a_table(timeline_path: str, symbol: str) -> dict[_date, dict[str, Any]]:
        """加载 A 层 timeline parquet 并按 (contract=symbol) 折叠成 {date: 记录}。

        记录字段：
          - tier         : spec §1.3 阵营名（L_*/S_*）；供入场方向与 §2.2 K_SL 选择
          - direction    : 由 tier 派生（long/short）
          - daily_atr_bps: 日 ATR 归一化到 bps（用于 §2.3 σ_day 回退方案）
          - sigma_day    : 可选；上游提供的日波动率基准（fraction）
        同日多行取最早（event_time 最小）。文件缺失或无匹配返回空表。
        """
        import pandas as pd

        path = Path(timeline_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            return {}

        try:
            tl = pd.read_parquet(path)
        except Exception:
            return {}

        if "contract" not in tl.columns or "tier" not in tl.columns:
            return {}
        tl = tl[(tl["contract"] == symbol) & tl["tier"].notna()]
        if tl.empty:
            return {}

        # 时间列
        if "event_time" in tl.columns:
            tl = tl.copy()
            tl["event_time"] = pd.to_datetime(tl["event_time"])
            tl = tl.sort_values("event_time")
            date_series = tl["event_time"].dt.date
        elif "date" in tl.columns:
            tl = tl.copy()
            date_series = pd.to_datetime(tl["date"]).dt.date
        else:
            return {}

        # daily_atr_bps 列的可能命名（兼容 A 层预处理输出）
        atr_col = None
        for cand in ("daily_atr_bps", "daily_atr_10_bps", "entry_atr_bps"):
            if cand in tl.columns:
                atr_col = cand
                break

        sigma_col = "sigma_day" if "sigma_day" in tl.columns else None

        table: dict[_date, dict[str, Any]] = {}
        for pos, (_, row) in enumerate(tl.iterrows()):
            ev_date = date_series.iloc[pos]
            if ev_date in table:
                continue
            tier = str(row["tier"])
            direction = _tier_direction(tier)
            if not direction:
                continue
            atr_bps = float(row[atr_col]) if atr_col is not None else float("nan")
            record: dict[str, Any] = {
                "tier": tier,
                "direction": direction,
                "daily_atr_bps": atr_bps,
            }
            if sigma_col is not None:
                with contextlib.suppress(TypeError, ValueError):
                    record["sigma_day"] = float(row[sigma_col])
            table[ev_date] = record
        return table
