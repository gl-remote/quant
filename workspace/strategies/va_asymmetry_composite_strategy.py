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
from typing import Any, override

import numpy as np
import pandas as pd
from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)

from .classifiers.poc_va import (
    TRANS_STABLE,
    ClassifierConfig,
    classify_tier,
    compute_transition_series,
    daily_atr_sma,
    roll_t_pit,
    tier_direction,
    trend_log_return,
    volume_weighted_skew,
)
from .core import (
    CORE_VERSION,
    Fill,
    Signal,
    State,
    Strategy,
)
from .core.diagnostics import AlphaDiagnostics, ExecutionDiagnostics, RiskDiagnostics
from .runtime import DataRequirements, EventsRequirements, PeriodRequirements
from .runtime.aggregate import parse_period_minutes
from .runtime.requirements import BarContext
from .strategy_aspects.indicators import DAILY_ATR_BPS

# ---------------------------------------------------------------------------
# spec §0：生产配置（可通过参数覆盖，默认对齐 spec）
# ---------------------------------------------------------------------------


@dataclass
class VAAsymmetryCompositeParams:
    """VA 非对称复合策略 B 层参数（对齐 spec §0）。"""

    # ── 周期 ─────────────────────────────────────────────────────
    base_tf: str = "5m"
    """spec §0 base_tf：波动率-时间退出的 bar 粒度（§2.3）。策略主周期。

    2026-07-13 修正：从 1m 改为 5m，与研究侧数据链对齐。
    改动原因：研究侧 va_mad_fix_full_backtest.py 全程使用 5m CSV（预制交易所标准
    切片），逐 5m bar 检查止损；工程侧原用 1m bar 时，session 内聚合边界会与
    交易所 5m CSV 边界差 1-2 秒，且 1m 粒度对日内噪声更敏感，K_S=1.75 时误杀
    率显著更高。切到 5m 后：
      1. bar 边界与研究侧 CSV 一致（datafeed 直接读 5m）；
      2. 止损粒度与研究侧一致（5m bar 逐根检查）；
      3. §2.3 波动率累积 ΔV_k 从 1m 换成 5m log return，H_vol 单位不变。
    """

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

    k_sl_short: float = 2.5
    """spec §0 K_SL{S}：空域止损 ATR 倍数。

    2026-07-13 修正：从 1.75 改为 2.5，与研究侧 va_mad_fix_full_backtest.py 对齐。
    改动原因：K_S=1.75 使空头止损距离过窄，V 转行情中空单被扫出；研究侧全量
    回测使用 K_S=2.5（比 K_L=1.0 宽 2.5×），空单能扛住回调。这是诊断报告
    §5 差异 2 的直接来源，影响权重 ★★★★。
    """

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

    weight_scheme: str = "uniform"
    """[legacy 2026-07-13 移除] 加权逻辑不应在分类器入口引入（R/E 共用同一分类器）；
    近因/重复值效应通过「A 层输入端状态管理」模拟（见 tier_calc_freq / daily_repeat_count），
    本字段保留仅为兼容旧 config，实际已不生效。"""

    tier_calc_freq: str = "hourly"
    """路径B（优先对齐研究侧行为）：A 层 tier/direction/trans/age 的重算频率。
    * "hourly"（默认 / 研究侧完全等价）— 每小时整点 + 每段首独立调用 t-PIT
      → trans/age 按小时级推进，等价研究侧 hourly_idx（9:00/10:00/11:00/14:00/
      15:00/21:00/22:00/23:00/00:00）重复推进。
    * "daily"（旧工程侧） — 每日只在新交易日首 bar 重算一次 tier。"""

    daily_repeat_count: int = 6
    """路径B：A 层 skew/atr/trend/close 日线缓冲区「每个交易日重复 append N 次」。
    等价研究侧 hourly 重复行（同日 6 次 skew=X 相同 → 离散排序后 median/MAD 断点退化
    + age/trans 同日推进 5 次）。默认=6，与研究侧 hourly_idx 每自然日 ~6 个整点对齐。"""

    grace_per_segment: bool = True
    """路径B：True（默认）= 每段首/每整点 各自独立应用 open_grace_min（段/整点后 ≥
    5min 才允许开仓），等价研究侧每小时独立候选 + 开盘 5min 不交易的惯例；
    False = 仅当日 session 首段统一应用 open_grace_min（旧工程侧语义）。"""


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
    # 路径B：段首/整点对齐点 + 每段/整点独立 open_grace
    # ------------------------------------------------------------

    _SEGMENT_STARTS_HM: tuple[tuple[int, int], ...] = (
        (9, 0),
        (10, 30),
        (13, 30),
        (21, 0),
        (23, 0),
    )
    """商品期货典型交易时段首：S1(09:00) / S2(10:30) / S3(13:30) / N1(21:00) / N2(23:00+)。
    整点（09:00/10:00/11:00/14:00/...）= minute==0 自动命中，不用列举。"""

    @staticmethod
    def _is_tier_align_point(dt: Any) -> bool:
        """当前 base_tf bar 是否对应研究侧 hourly_idx 的「整点开算点」+ 段首特例。
        * 整点（minute==0）无条件命中；
        * 非整点的段首（10:30 / 13:30 / 23:00 等）也命中；
        * 用于：hourly 模式下每小时触发 _recompute_tier + 在该对齐点后应用 open_grace_min。
        """
        if dt is None:
            return False
        hm = (dt.hour, dt.minute)
        if hm[1] == 0:
            return True
        return hm in VAAsymmetryCompositeStrategy._SEGMENT_STARTS_HM

    @staticmethod
    def _nearest_align_point_time(dt: Any) -> pd.Timestamp | None:
        """找到 ≤ 当前 bar datetime 的最近一个 tier 对齐点（整点 / 段首）时间戳。
        用于 grace_per_segment=True 时，每段/整点独立算「对齐点 + open_grace_min 才允许开仓」。
        """
        if dt is None:
            return None
        t = pd.Timestamp(dt)
        candidates = []
        # (a) 当前小时整点（若 hour:00 ≤ 当前时刻）
        top = t.replace(minute=0, second=0, microsecond=0)
        if top <= t:
            candidates.append(top)
        # (b) 段首时间（当日 + 跨日 23:00 等）
        for h, m in VAAsymmetryCompositeStrategy._SEGMENT_STARTS_HM:
            cand = t.replace(hour=h, minute=m, second=0, microsecond=0)
            if cand <= t:
                candidates.append(cand)
        # (c) 前一日 23:00（夜盘段首跨日，处理 00:xx / 01:xx 等情形）
        prev = t.normalize() - pd.Timedelta(days=1)
        prev_2300 = prev + pd.Timedelta(hours=23)
        if prev_2300 <= t:
            candidates.append(prev_2300)
        if not candidates:
            return None
        return max(candidates)

    # ------------------------------------------------------------
    # on_bar 主入口
    # ------------------------------------------------------------

    @override
    def on_bar(self, state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> Signal:
        # 每根 base_tf bar 维护 session 锚点（t_open）与前一日 5m bar 缓冲区
        self._anchor_session(state, ctx)
        self._accumulate_session_bar(state, ctx)

        # 1. 新交易日：初始化当日计数器（不立即 append）
        self._on_new_day(state, ctx)

        # 2. 路径B：对齐点 → 先 append 1 组重复样本 → 再独立重算 tier
        #    对应研究侧 hourly_idx：每推进一个 hourly 行就 append 1 个 + 重算一次，
        #    极端 r 值会在当日第 3~4 个对齐点自然出现，命中阵营区间。
        config = state.strategy_config
        if str(config.tier_calc_freq).lower() == "hourly":
            if VAAsymmetryCompositeStrategy._is_tier_align_point(ctx.bar.datetime):
                VAAsymmetryCompositeStrategy._append_one_repeat_if_needed(state)
                VAAsymmetryCompositeStrategy._recompute_tier(state, ctx)
                state.extra["va_last_tier_align_time"] = ctx.bar.datetime
        else:
            # daily 模式（旧工程侧，daily_repeat_count 应该为 1）：当日第一次算 tier
            if state.extra.get("va_day_initialized") == state.extra.get("va_session_date") and state.extra.get(
                "va_tier_daily_computed_date"
            ) != state.extra.get("va_session_date"):
                VAAsymmetryCompositeStrategy._append_one_repeat_if_needed(state)
                VAAsymmetryCompositeStrategy._recompute_tier(state, ctx)
                state.extra["va_tier_daily_computed_date"] = state.extra.get("va_session_date")

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
    # A 层状态机：新交易日结算 → 滚动缓冲区 append N 次（重复值模式）
    #            tier 重算从"每日一次"改成独立函数（被段首/整点触发）
    # ------------------------------------------------------------

    _INDICATOR_COL: str = "1d_daily_atr_bps_10"
    """generate_indicator_column_name("daily_atr_bps", {"period": 10}, period="1d") 的硬编码结果。"""

    _CSV_DIR: str = "project_data/market_data/csv"
    """5m CSV 数据目录（相对 repo 根）。"""

    @staticmethod
    def _buf_maxlen(days: int, repeat: int) -> int:
        """缓冲区 maxlen = 期望真实日数 × 每日重复次数。"""
        return max(days, 1) * max(1, repeat)

    @staticmethod
    def _precompute_va_daily_lookup(
        contract_symbol: str,
        atr_entry_win: int = 10,
        trend_entry_win: int = 10,
    ) -> dict[object, dict[str, float]]:
        """预计算单合约的 daily lookup 表，对齐研究侧 build_daily_features 逻辑。

        返回: {date(datetime.date): {
            "A3_skew_spec": float,        # 当日 session 量加权 skew（差异A：用当日值）
            "daily_atr_spec": float,      # SMA(10) 绝对 ATR（差异B：绝对价格单位）
            "trend_ret_M_spec": float,    # 10日累计 log return
            "close_session": float,       # 当日 session 收盘价（差异C：用当日值）
        }}
        """
        from pathlib import Path as _Path

        # __file__ = repo/workspace/strategies/va_asymmetry_composite_strategy.py
        # → parents[2] = repo 根
        repo = _Path(__file__).resolve().parents[2]
        csv_path = repo / VAAsymmetryCompositeStrategy._CSV_DIR / f"{contract_symbol}.tqsdk.5m.csv"
        lookup: dict[object, dict[str, float]] = {}
        if not csv_path.exists():
            return lookup

        try:
            bars = pd.read_csv(csv_path, usecols=["datetime", "open", "high", "low", "close", "volume"])
        except Exception:
            return lookup
        if bars.empty:
            return lookup
        bars["datetime"] = pd.to_datetime(bars["datetime"])
        bars["date"] = pd.to_datetime(bars["datetime"].dt.date)

        daily = (
            bars.groupby("date")
            .agg(
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
                volume=("volume", "sum"),
            )
            .reset_index()
            .sort_values("date")
            .reset_index(drop=True)
        )

        if len(daily) < max(atr_entry_win, trend_entry_win) + 1:
            return lookup

        a3_map: dict[pd.Timestamp, float] = {}
        for date_val, g in bars.groupby("date"):
            prices = g["close"].to_numpy(dtype=float)
            volumes = g["volume"].to_numpy(dtype=float)
            a3_map[pd.Timestamp(str(date_val))] = volume_weighted_skew(prices, volumes)
        daily["A3_skew_spec"] = daily["date"].map(a3_map)
        daily["daily_atr_spec"] = daily_atr_sma(daily["high"], daily["low"], daily["close"], atr_entry_win)
        daily["trend_ret_M_spec"] = trend_log_return(daily["close"], trend_entry_win)
        daily["close_session"] = daily["close"]

        # ── 因果性修复（2026-07-13）：值列全部 shift(1) ──
        # D 日收盘后才算出的 4 个 daily 特征，只能用于 D+1 交易日起的事件。
        # 对值列向下 shift(1) 再写入 lookup，等价于 lookup[今天] = 昨日收盘后算出的 daily 值，
        # 完全无未来信息。shift 后的第 1 行为 NaN（最早的一天无历史可用，合法）。
        for _c in ("A3_skew_spec", "daily_atr_spec", "trend_ret_M_spec", "close_session"):
            daily[_c] = daily[_c].shift(1)

        # 注意：SMA(10) ATR / 10日 trend 前 N-1 天**必须保持 NaN 原样**，
        # 禁止 ffill/bfill——否则会改变 roll_t_pit 因果滚动的窗口中位数，
        # 让所有后续 r_a/r_t 与研究侧完全偏离。
        # 「三个 deque 长度一致」由 _on_new_day 保证：即便值是 NaN，
        # 也强制 append 正好 N 个占位（NaN/前向填充），不允许跳过。
        for _, row in daily.iterrows():
            dt_key = pd.Timestamp(row["date"]).date()
            lookup[dt_key] = {
                "A3_skew_spec": float(row["A3_skew_spec"]) if pd.notna(row.get("A3_skew_spec")) else float("nan"),
                "daily_atr_spec": float(row["daily_atr_spec"]) if pd.notna(row.get("daily_atr_spec")) else float("nan"),
                "trend_ret_M_spec": float(row["trend_ret_M_spec"])
                if pd.notna(row.get("trend_ret_M_spec"))
                else float("nan"),
                "close_session": float(row["close_session"]) if pd.notna(row.get("close_session")) else float("nan"),
            }
        return lookup

    @staticmethod
    def _on_new_day(state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> None:
        """新交易日：初始化当日计数器 + 缓存当日特征值。

        **关键修正 (2026-07-13)：不再一次性 append N 个重复值！**

        研究侧实际推进语义：每 1 个 hourly_idx → append 1 个同值重复样本 → 重算 tier。
        同一天的 N 个对齐点（段首/整点）中，第1~N个对齐点各 append 1 次（累积 N 次）。
        否则若在 session open 时一次性 append N 个，_recompute_tier 取 iloc[-1] 永远
        是「该日最后一个重复样本」，此时 window(10) 内恰是 4+6 个重复值 → MAD≈0
        → roll_t_pit 兜底 0.5 → tier 永远 None。

        三大差异修复（输入端）：
        - A(skew日期)：用当日 event_date 的 A3_skew_spec，不用昨日 session
        - B(atr单位)：用绝对价格单位的 daily_atr_spec，不用 bps 百分比
        - C(close日期)：用当日 close_session，不用昨日 close
        """
        config = state.strategy_config
        today = state.extra.get("va_session_date")
        if state.extra.get("va_day_initialized") == today:
            return
        n_repeat = max(1, int(config.daily_repeat_count))
        contract_symbol = state.symbol

        # ── 0. 延迟初始化 daily lookup（从 5m CSV 预计算）──
        daily_lookup = state.extra.get("va_daily_lookup")
        if daily_lookup is None:
            daily_lookup = VAAsymmetryCompositeStrategy._precompute_va_daily_lookup(
                contract_symbol,
                atr_entry_win=config.atr_entry_win,
                trend_entry_win=config.trend_entry_win,
            )
            state.extra["va_daily_lookup"] = daily_lookup
        today_entry = daily_lookup.get(today, {}) if today else {}

        # ── 1. 取当日 A3_skew / 绝对ATR / close（修复差异A/B/C）──
        raw_skew = float(today_entry.get("A3_skew_spec", float("nan")))
        raw_atr = float(today_entry.get("daily_atr_spec", float("nan")))
        raw_close = float(today_entry.get("close_session", float("nan")))
        # 前向填充（保证对齐点不会因为 NaN 少 append 样本）
        prev_skew = float(state.extra.get("va_prev_day_skew", float("nan")))
        prev_atr = float(state.extra.get("va_prev_day_atr", float("nan")))
        prev_close = float(state.extra.get("va_prev_day_close", float("nan")))
        day_skew = raw_skew if np.isfinite(raw_skew) else prev_skew
        day_atr = raw_atr if np.isfinite(raw_atr) else prev_atr
        day_close = raw_close if np.isfinite(raw_close) else prev_close

        # ── 2. 初始化/重建缓冲区（maxlen 按重复次数放大）──
        buf_days = 40
        maxlen = VAAsymmetryCompositeStrategy._buf_maxlen(buf_days, n_repeat)
        for key in ("va_skew_buf", "va_atr_abs_buf", "va_close_buf"):
            buf: deque[float] | None = state.extra.get(key)
            if buf is None or getattr(buf, "maxlen", None) != maxlen:
                state.extra[key] = deque(list(buf or []), maxlen=maxlen)

        # ── 3. 写入当日计数器 + 缓存当日值 ──
        state.extra["va_day_initialized"] = today
        state.extra["va_day_append_count"] = 0  # 当日已 append 次数
        state.extra["va_day_skew"] = day_skew
        state.extra["va_day_atr"] = day_atr
        state.extra["va_day_close"] = day_close
        # 如果当日有有效值 → 记录给下一日 ffill；否则保持前一日
        if np.isfinite(raw_skew):
            state.extra["va_prev_day_skew"] = float(raw_skew)
        if np.isfinite(raw_atr):
            state.extra["va_prev_day_atr"] = float(raw_atr)
            state.extra["va_today_daily_atr_abs"] = float(raw_atr)
        if np.isfinite(raw_close):
            state.extra["va_prev_day_close"] = float(raw_close)
        # 清空 session bars（不用再计算昨日 skew，用 lookup 当日值）
        state.extra["va_session_5m_bars"] = []

    @staticmethod
    def _append_one_repeat_if_needed(state: State[VAAsymmetryCompositeParams]) -> None:
        """每个段首 / 整点对齐点：若当日 append 次数 < N → append 1 组（skew/atr/close 各1个）。

        精确对应研究侧 hourly_idx：每推进一个 hourly 行就 append 1 个同值重复样本，
        然后再重算 tier。这样 window(10) 的中位数/MAD 随推进自然变化，极端值就会
        在第 3~4 个重复点处出现，正确命中阵营区间。
        """
        config = state.strategy_config
        n_repeat = max(1, int(config.daily_repeat_count))
        count = int(state.extra.get("va_day_append_count", 0))
        if count >= n_repeat:
            return
        day_skew = float(state.extra.get("va_day_skew", float("nan")))
        day_atr = float(state.extra.get("va_day_atr", float("nan")))
        day_close = float(state.extra.get("va_day_close", float("nan")))
        half_eps: float = 1e-10
        mid = 0.5 * float(n_repeat - 1)
        j = count  # 当前 append 的是当日第 j 个重复（0..N-1）
        skews: deque[float] = state.extra["va_skew_buf"]
        atrs: deque[float] = state.extra["va_atr_abs_buf"]
        closes: deque[float] = state.extra["va_close_buf"]
        if np.isfinite(day_skew):
            delta = (float(j) - mid) * half_eps * max(1.0, abs(day_skew))
            skews.append(day_skew + delta)
        else:
            skews.append(float("nan"))
        if np.isfinite(day_atr):
            delta = (float(j) - mid) * half_eps * max(1.0, abs(day_atr))
            atrs.append(day_atr + delta)
        else:
            atrs.append(float("nan"))
        if np.isfinite(day_close):
            delta = (float(j) - mid) * half_eps * max(1.0, day_close)
            closes.append(day_close + delta)
        else:
            closes.append(float("nan"))
        state.extra["va_day_append_count"] = count + 1

    @staticmethod
    def _recompute_tier(state: State[VAAsymmetryCompositeParams], ctx: BarContext | None = None) -> None:
        """路径B核心：独立 tier 重算入口。

        对当前 skew/atr/close 缓冲区（含每日重复 N 行）跑 t-PIT + compute_transition_series
        → classify_tier。与研究侧 build_events L110-L143 hourly_idx 每次独立调用完全对应。
        结果存回 state.extra["va_today_{tier,direction,daily_atr_bps}"]。

        差异B修复：atr 缓冲区使用绝对价格单位（va_atr_abs_buf），daily_atr_bps 在
        这里用「绝对ATR / 参考价 * 10000」转换（对齐研究侧 entry_atr_bps 计算）。
        """
        config = state.strategy_config
        skews: deque[float] = state.extra.get("va_skew_buf", deque())
        atrs: deque[float] = state.extra.get("va_atr_abs_buf", deque())
        closes: deque[float] = state.extra.get("va_close_buf", deque())
        daily_atr_abs = float(state.extra.get("va_today_daily_atr_abs", float("nan")))
        ref_price = (
            float(ctx.bar.close) if (ctx is not None and ctx.bar is not None and ctx.bar.close > 0) else float("nan")
        )
        if np.isfinite(daily_atr_abs) and np.isfinite(ref_price) and ref_price > 0:
            daily_atr_bps = daily_atr_abs / ref_price * 10000.0
        else:
            daily_atr_bps = float("nan")

        class_config = ClassifierConfig(
            skew_rank_win=config.skew_rank_win,
            atr_rank_win=config.atr_rank_win,
            trend_win=config.trend_win,
            atr_entry_win=config.atr_entry_win,
            trend_entry_win=config.trend_entry_win,
        )
        tier_name: str | None = None
        direction: str = ""

        min_len = class_config.skew_rank_win
        trend_offset = class_config.trend_entry_win - 1
        # trend_min_len = 要生成 M-1 个空 + trend_win 个有效值，等价于至少有
        # trend_entry_win - 1 + trend_win 个 close 样本（每日重复 N 次后这个样本数
        # 非常容易达到，和研究侧 warmup 虚假早熟行为精确对齐）。
        trend_min_len = trend_offset + class_config.trend_win
        if len(skews) >= min_len and len(atrs) >= min_len and len(closes) >= trend_min_len:
            n_close = len(closes)
            s_skew = pd.Series(list(skews), dtype=float)
            s_atr = pd.Series(list(atrs), dtype=float)
            t_vals = []
            for i in range(trend_offset, n_close):
                c0 = float(closes[i - trend_offset])
                c1 = float(closes[i])
                if c0 > 0 and c1 > 0:
                    t_vals.append(float(log(c1 / c0)))
                else:
                    t_vals.append(float("nan"))
            s_trend = pd.Series(t_vals, dtype=float)

            # 分类器单一入口（均匀权重）—— 离散重复值的 MAD/断点效应完全由输入端
            # skew/atr/closes deque 的重复行带来，不再走加权分支，确保 R/E 使用
            # 完全相同的分类器逻辑。
            r_s_raw = roll_t_pit(s_skew, class_config.skew_rank_win)
            r_s = 1.0 - (float(r_s_raw.iloc[-1]) if len(r_s_raw) else float("nan"))
            r_a_series = roll_t_pit(s_atr, class_config.atr_rank_win)
            r_a = float(r_a_series.iloc[-1]) if len(r_a_series) else float("nan")
            r_t_series = roll_t_pit(s_trend, class_config.trend_win)
            r_t = float(r_t_series.iloc[-1]) if len(r_t_series) else float("nan")

            trans = TRANS_STABLE
            if len(r_a_series) > 0 and r_a_series.notna().any():
                trans_df = compute_transition_series(r_a_series)
                trans = str(trans_df["trans"].iloc[-1])

            if np.isfinite(r_s) and np.isfinite(r_a) and np.isfinite(r_t):
                tier_name = classify_tier(float(r_s), float(r_a), float(r_t), trans)
                if tier_name is not None:
                    direction = tier_direction(tier_name)

        state.extra["va_today_tier"] = tier_name
        state.extra["va_today_direction"] = direction
        state.extra["va_today_daily_atr_bps"] = daily_atr_bps

    # ------------------------------------------------------------
    # 持仓分支：§2.2 SL / §2.3 时间退出 / §2.4 优先级
    # ------------------------------------------------------------

    def _on_holding(self, state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> Signal:
        bar = ctx.bar
        direction = state.position.direction
        close_action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY

        stop_price = float(state.extra.get("va_stop_price", 0.0))
        volume = state.position.volume
        bars_held_now = int(state.extra.get("va_bars_held", 0))
        # §2.2 + §2.4：SL 优先
        hit_sl = (direction == TRADE_DIRECTION_LONG and bar.low <= stop_price) or (
            direction == TRADE_DIRECTION_SHORT and bar.high >= stop_price
        )
        if hit_sl and stop_price > 0:
            self._clear_holding(state)
            return Signal(
                action=close_action,
                reason="SL",
                volume=volume,
                diagnostics={"stop_price": stop_price},
                alpha=AlphaDiagnostics(
                    fields={
                        "direction_hypothesis": direction,
                        "entry_reason": "va_asymmetry_exit_sl",
                    }
                ),
                risk=RiskDiagnostics(
                    fields={
                        "actual_volume": volume,
                        "stop_price": stop_price,
                    }
                ),
                execution=ExecutionDiagnostics(
                    fields={
                        "exit_reason": "strict_failure",
                        "holding_bars": bars_held_now,
                        "actual_volume": volume,
                    }
                ),
            )

        # §2.3：先执行"上一根已触发的下一根 base_tf 收盘平仓"
        if state.extra.get("va_time_exit_pending"):
            bars_held = int(state.extra.get("va_bars_held", 0))
            hold_max = int(state.extra.get("va_hold_bars_max", 0))
            self._clear_holding(state)
            return Signal(
                action=close_action,
                reason="TIME",
                volume=volume,
                diagnostics={"bars_held": bars_held, "hold_bars_max": hold_max},
                alpha=AlphaDiagnostics(
                    fields={
                        "direction_hypothesis": direction,
                        "entry_reason": "va_asymmetry_exit_time",
                    }
                ),
                risk=RiskDiagnostics(
                    fields={
                        "actual_volume": volume,
                        "stop_price": stop_price,
                    }
                ),
                execution=ExecutionDiagnostics(
                    fields={
                        "exit_reason": "time_exit",
                        "holding_bars": bars_held,
                        "hold_bars_max": hold_max,
                        "actual_volume": volume,
                    }
                ),
            )

        # §2.3（2026-07-13 修正）：固定持仓时长 H_L=8h / H_S=10h（与研究侧对齐）
        # 5m base_tf 下 → H_L=96 根 / H_S=120 根。达到最大 bar 数时置 pending，
        # 下一根 base_tf 收盘平仓（保持与原语义一致：不当根平，避免同 bar 优先级冲突）。
        bars_held = int(state.extra.get("va_bars_held", 0)) + 1
        state.extra["va_bars_held"] = bars_held
        hold_max = int(state.extra.get("va_hold_bars_max", 0))
        if hold_max > 0 and bars_held >= hold_max:
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

        # §2.1 open_grace：
        #  * grace_per_segment=False（旧工程侧）：仅 session 首段统一 + open_grace_min；
        #  * grace_per_segment=True（路径B默认，研究侧对齐）：最近一个 tier 对齐点
        #    （整点/段首）后独立应用 open_grace_min，等价研究侧每小时独立候选、
        #    段首 5 分钟不开仓的惯例。
        if config.grace_per_segment:
            anchor = VAAsymmetryCompositeStrategy._nearest_align_point_time(bar.datetime)
            if anchor is None:
                anchor = pd.Timestamp(bar.datetime)
        else:
            anchor = pd.Timestamp(state.extra.get("va_session_open", bar.datetime))
        elapsed_min = (pd.Timestamp(bar.datetime) - pd.Timestamp(anchor)).total_seconds() / 60.0
        if elapsed_min < config.open_grace_min:
            return Signal()

        # A 层命中：从每日状态机读取
        direction = str(state.extra.get("va_today_direction", ""))
        if direction not in (TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT):
            return Signal()

        tier_name = str(state.extra.get("va_today_tier", ""))

        # §2.2 ATR：差异B修复——使用当日绝对ATR / 入场价 * 10000（对齐研究侧 entry_atr_bps）
        entry_price = float(bar.close)
        daily_atr_abs = float(state.extra.get("va_today_daily_atr_abs", float("nan")))
        if entry_price <= 0 or isnan(daily_atr_abs) or daily_atr_abs <= 0:
            return Signal()
        daily_atr_bps = daily_atr_abs / entry_price * 10000.0
        if daily_atr_bps <= 0:
            return Signal()
        atr_price = daily_atr_abs

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

        # §2.3 固定持仓 bar 上限（2026-07-13 修正，与研究侧对齐）：
        # H 单位为小时；base_tf 每小时 bar 数 = 60 / base_tf_min。
        base_tf_min = parse_period_minutes(config.base_tf)
        bars_per_hour = int(round(60 / base_tf_min)) if base_tf_min > 0 else 0
        hold_bars_max = int(h_vol * bars_per_hour)

        # 播种持仓 bookkeeping
        state.extra["va_stop_price"] = stop_price
        state.extra["va_h_vol"] = h_vol
        state.extra["va_sigma_day"] = sigma_day
        state.extra["va_bars_held"] = 0
        state.extra["va_hold_bars_max"] = hold_bars_max
        state.extra["va_time_exit_pending"] = False
        state.extra["va_last_entry_date"] = today

        action = TRADE_ACTION_BUY if is_long else TRADE_ACTION_SELL
        strict_distance = k_sl * atr_price
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
            alpha=AlphaDiagnostics(
                fields={
                    "direction_hypothesis": direction,
                    "entry_reason": "va_asymmetry_tier",
                    "signal_strength": 1.0,
                    "reference_price": entry_price,
                    "tier": tier_name,
                    "daily_atr_bps": daily_atr_bps,
                    "strict_failure_boundary": stop_price,
                    "expected_profit_boundary": None,
                }
            ),
            risk=RiskDiagnostics(
                fields={
                    "account_equity": state.capital,
                    "target_risk_ratio": config.risk_per_trade,
                    "actual_volume": qty,
                    "account_risk_ratio": config.risk_per_trade,
                    "risk_budget_passed": True,
                    "strict_failure_distance": strict_distance,
                    "target_risk_amount": config.risk_per_trade * state.capital,
                    "theoretical_volume": qty,
                    "stop_price": stop_price,
                    "k_sl": k_sl,
                    "notional_frac": notional_frac,
                    "raw_account_r_multiple": None,
                }
            ),
            execution=ExecutionDiagnostics(
                fields={
                    "entry_trigger": "bar_close",
                    "actual_volume": qty,
                    "hold_bars_max": hold_bars_max,
                }
            ),
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
            "va_bars_held",
            "va_hold_bars_max",
            "va_time_exit_pending",
        ):
            state.extra.pop(key, None)
