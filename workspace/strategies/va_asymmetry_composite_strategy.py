"""VA 非对称复合策略 · B 层执行模块（框架标准 Strategy 子类）

【定位】
本文件是 va-asymmetry-composite 主题的 **B 层（执行/下单）**，严格实现
strategy-math-spec.md 的 §2（进出场）与 §3（仓位/风控）。A 层（日级分类）
由 workspace/strategies/classifiers/poc_va.py 及上游管线负责，产出
classifier_v31_timeline.parquet 的 `tier` 列；本策略只把 A 层结论作为
(contract, date) 查表输入，不重算分类。

【与研究引擎的一致性】
执行语义对齐冻结研究引擎 scripts/ai_tmp/va_composite_p1_cap.py::simulate_contract：
  - 进场:  按 tier 方向在「跳过开盘首根 bar、晚于开盘 ≥ open_grace_minutes(默认5min)」
           的首根 eligible bar 收盘价开仓（spec §2.1 baseline 增强）
  - 止损:  SL = entry ∓ K_SL(τ)·ATR，Long 减、Short 加（spec §2.2）
  - 时间退出: 固定持有 H×12 根 5m bar（Long 8h→96 根 / Short 10h→120 根），**按 K 线根数**
             判定（以首根持仓 bar = 真实成交 bar 起计数，held >= H×12 即退出）。
             这就是 spec §2.3「波动率-时间退出」落地口径——spec 中 H_vol{L:B_L,S:B_S}
             的 B_L/B_S 是「arg_solve 复现 8h/10h 中位持有」的未定锚点，且
             P2/P6 实证否证了波动率归一化与 H_vol(tier) 分档（详见
             docs/workbench/va-asymmetry-composite-p2-timing-holding-time.md），
             故此处等价落为固定 8h/10h 持有。
             【注意】必须用 K 线根数而非「墙钟小时」：5m 数据含午休/夜盘休市 gap，
             墙钟 8h/10h 会跨 gap 提前平仓（09:10 进场+8h=17:10 落在休市段，实际只在
             ~21:00 夜盘首根退出、仅持 ~47 根 bar），导致框架年化被系统性砍掉约一半；
             研究引擎 `bars[idx:idx+H*12]` 固定持 H×12 根，故框架须同口径对齐。
  - 优先级: SL 优先于时间退出（spec §2.4）
  - 仓位:  Notional_target = RiskPerTrade·Equity/(K_SL(τ)·ATR_bps)，
           qty = notional_frac·capital/(price·contract_size)（spec §3.1）

【范围外（out-of-scope）】
spec §3.3 组合级名义暴露 Cap（Σ notional ≤ Cap·Equity，跨合约按日聚合压仓）
属于 **组合/桥接层** 职责，无法在单合约 Strategy.on_bar 内执行，需由上层
portfolio/bridge 汇总后统一压仓。本策略只负责单合约的信号与单笔 sizing。

【适配说明】
框架 Strategy 无 on_init 钩子，A 层查表在首个 on_bar 惰性预加载到 state.extra
（等价 on_init 预加载）。触发时机采用「每日首根 entry_tf 触发」，与研究引擎按
event_time 触发存在轻微差异（研究引擎在盘中 event_time 进场），这是 bar 驱动
形态下的显式取舍。开仓额外受 open_grace_minutes 宽限约束（跳过开盘首根 bar，
晚于开盘 ≥5min 才进场），以与研究引擎「event_time 不落在开盘首根窗口」保持一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import override

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
from .runtime import DataRequirements, EventsRequirements, PeriodRequirements
from .runtime.requirements import Bar, BarContext

# ---------------------------------------------------------------------------
# CONTRACT LAYER 白名单与 v4.0 tier 映射
# 来源: strategy-math-spec.md §CONTRACT LAYER + 冻结引擎
#       scripts/ai_tmp/va_composite_p1_cap.py（A_TIER_RAW / TIER_TO_V40）
# 只有白名单内的 144-tier 才可交易；方向由前缀决定 UP->long / DN->short。
# ---------------------------------------------------------------------------
A_TIER_RAW: frozenset[str] = frozenset(
    {
        "UP2_atrLow_up_stable",
        "UP3_atrMid_up_stable",
        "UP1_atrHigh_up_trans",
        "DN1_atrHigh_down_stable",
        "DN1_atrHigh_down_trans",
        "DN2_atrHigh_down_stable",
        "DN2_atrHigh_down_trans",
        "DN3_atrHigh_down_stable",
        "DN3_atrHigh_down_trans",
        "DN4_atrHigh_down_stable",
        "DN4_atrHigh_down_trans",
        "DN2_atrMid_down_stable",
        "DN2_atrMid_down_trans",
    }
)

TIER_TO_V40: dict[str, str] = {
    "UP2_atrLow_up_stable": "L_seg3_lowmid_up",
    "UP3_atrMid_up_stable": "L_seg3_lowmid_up",
    "UP1_atrHigh_up_trans": "L_seg12_high_up",
    "DN1_atrHigh_down_stable": "S_seg12_high_dn",
    "DN1_atrHigh_down_trans": "S_seg12_high_dn",
    "DN2_atrHigh_down_stable": "S_seg12_high_dn",
    "DN2_atrHigh_down_trans": "S_seg12_high_dn",
    "DN3_atrHigh_down_stable": "S_seg34_high_dn",
    "DN3_atrHigh_down_trans": "S_seg34_high_dn",
    "DN4_atrHigh_down_stable": "S_seg34_high_dn",
    "DN4_atrHigh_down_trans": "S_seg34_high_dn",
    "DN2_atrMid_down_stable": "S_seg2_mid_dn",
    "DN2_atrMid_down_trans": "S_seg2_mid_dn",
}

# A 层默认时间线（可由参数覆盖），相对仓库根目录
_DEFAULT_TIMELINE = "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet"


@dataclass
class VAAsymmetryCompositeParams:
    """VA 非对称复合策略 B 层参数（映射 spec §0 冻结值）。"""

    base_tf: str = "1m"
    """基础周期（spec §0 base_tf）。"""

    entry_tf: str = "5m"
    """进场/主周期（spec §0 entry_tf），策略在此周期上驱动。"""

    open_grace_minutes: float = 5.0
    """开仓宽限期（spec §2.1 baseline 增强）：须晚于当日首根 bar 至少该分钟数才允许开仓，
    跳过开盘首根 bar（默认 5min → 跳过 09:05 首根，最早 09:10 进场），避免开盘竞价/首根噪声。
    以当日首根 bar 的 datetime 为 session open 基准，墙钟 elapsed >= open_grace_minutes 才开仓。"""

    k_sl_long: float = 1.0
    """Long 止损 ATR 倍数 K_SL(L)（spec §0 K_SL{L:1.0}）。"""

    k_sl_short: float = 2.5
    """Short 止损 ATR 倍数 K_SL(S)（spec §0 K_SL{S:2.5}）。"""

    hold_hours_long: int = 8
    """Long 固定持有小时数（spec §2.3 落地口径，替代未定锚 B_L）。"""

    hold_hours_short: int = 10
    """Short 固定持有小时数（spec §2.3 落地口径，替代未定锚 B_S）。"""

    risk_per_trade: float = 0.02
    """单笔风险预算 RiskPerTrade（spec §0 / §3.1）。"""

    a_layer_timeline_path: str = _DEFAULT_TIMELINE
    """A 层 (contract,date)->tier 查表来源 parquet 路径（相对仓库根或绝对路径）。"""

    integer_lots: bool = False
    """True 时对手数向下取整（实盘整手约束）；False 保留分数手以对齐研究引擎口径。"""


class VAAsymmetryCompositeStrategy(Strategy[VAAsymmetryCompositeParams]):
    """VA 非对称复合策略 · B 层执行核心（纯决策，无状态）。

    决策流程（每根 entry_tf bar）:
      1. 惰性预加载 A 层 (date -> 记录) 查表到 state.extra（首个 bar 一次）。
      2. 持仓中: SL 优先（§2.4）→ 否则固定持有到期时间退出（§2.3）。
       3. 空仓: 当日首根 bar 之后、且晚于开盘至少 open_grace_minutes（默认 5min）才允许开仓；
          若该日在 A 层白名单命中 → 按 tier 方向开仓，手数按 §3.1 名义暴露公式计算。
    """

    name: str = "va_asymmetry_composite"
    VERSION: str = f"{CORE_VERSION}-va-b1"

    def __init__(self) -> None:
        pass

    # ---- 数据需求声明 ----

    @override
    def data_requirements(self, config: VAAsymmetryCompositeParams) -> DataRequirements:
        """声明 entry_tf 主周期需求（on_bar 仅消费 entry_tf bar；base_tf 不在决策中使用）。

        注意：不可再额外声明 base_tf=1m，否则
        `BacktestRunWorkflow._strategy_required_interval` 会取最小周期 1m 作为回测
        interval，导致引擎以 1m bar 驱动本策略（持仓窗口按 5m 根数计算，会放大 12 倍）。
        """
        return DataRequirements(
            periods={config.entry_tf: PeriodRequirements(lookback_bars=1)},
            indicators={},
            events=EventsRequirements.no_events(),
        )

    # ---- 核心交易接口 ----

    @override
    @placeholder_diagnostics
    def on_bar(self, state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        self._ensure_a_table(state, config)

        bar = ctx.bar
        direction = state.position.direction

        # ── 持仓中：SL 优先，其次固定时间退出（§2.2 / §2.3 / §2.4）──
        if direction:
            return self._on_holding(state, ctx)

        # ── 空仓：当日首根 bar 之后 + 晚于开盘 open_grace_minutes + A 层命中 → 开仓（§2.1 / §3.1）──
        return self._on_flat(state, ctx, bar)

    @override
    def on_fill(self, fill: Fill) -> None:
        # State 为唯一真实数据源，成交后由 Bridge 同步 position；此处无需处理。
        pass

    # ---- 持仓管理 ----

    def _on_holding(self, state: State[VAAsymmetryCompositeParams], ctx: BarContext) -> Signal:
        bar = ctx.bar
        direction = state.position.direction
        stop_price = float(state.extra.get("va_stop_price", 0.0))

        # 首根持仓 bar 即真实成交 bar，作为持仓计数起点（§2.3 落地口径）。
        # 关键修正：不能用「墙钟小时」判定持有到期——5m 数据含午休/夜盘休市 gap，
        # 墙钟 8h/10h 会跨 gap 提前平仓（如 09:10 进场 +8h=17:10 落在休市段，
        # 实际只在 ~21:00 夜盘首根退出，仅持 ~47 根 bar），而研究引擎固定持
        # H*12 根 bar（bars[idx:idx+H*12]）。故此处改为固定 K 线根数对齐研究，
        # 否则框架年化会被系统性砍掉约一半（实证 fw/research 总盈亏比≈0.55）。
        if state.extra.get("va_await_entry"):
            state.extra["va_await_entry"] = False
            state.extra["va_bars_held"] = 0

        close_action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY

        # §2.2 + §2.4：硬止损优先
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

        # §2.3：固定持有 H*12 根 5m bar 后退出（对齐研究引擎 K 线时间口径）
        held = int(state.extra.get("va_bars_held", 0)) + 1
        state.extra["va_bars_held"] = held
        hold_bars = int(state.extra.get("va_hold_bars", 0))
        if hold_bars > 0 and held >= hold_bars:
            self._clear_holding(state)
            return Signal(
                action=close_action,
                reason="TIME",
                volume=state.position.volume,
                diagnostics={"bars_held": held, "hold_bars": hold_bars},
            )

        return Signal()

    def _on_flat(
        self,
        state: State[VAAsymmetryCompositeParams],
        ctx: BarContext,
        bar: Bar,
    ) -> Signal:
        config = state.strategy_config
        table: dict[_date, dict] = state.extra.get("va_table", {})
        if not table:
            return Signal()

        today = bar.datetime.date()
        # 每日首根 entry_tf 触发：同一日期只开一次
        if state.extra.get("va_last_entry_date") == today:
            return Signal()

        # 开盘宽限期（spec §2.1 baseline 增强）：跳过开盘首根 bar，避免开盘竞价/首根噪声。
        # 以当日首根 bar 的 datetime 为 session open 基准，elapsed >= open_grace_minutes 才允许开仓。
        # entry_tf=5m 时 open_grace=5 → 跳过 09:05 首根，最早 09:10(第二根)进场。
        # 注意：首根 bar 仅「锚定 session open」并跳过，不标记 va_last_entry_date，
        # 故下一根仍可正常开仓（当日只开一次由下方 va_last_entry_date 保证）。
        if state.extra.get("va_session_date") != today:
            state.extra["va_session_date"] = today
            state.extra["va_session_open"] = bar.datetime
        grace_s = config.open_grace_minutes * 60.0
        elapsed_s = (bar.datetime - state.extra.get("va_session_open", bar.datetime)).total_seconds()
        if elapsed_s < grace_s:
            return Signal()

        record = table.get(today)
        if record is None:
            return Signal()

        entry_price = float(bar.close)
        atr_bps = float(record["entry_atr_bps"])
        if entry_price <= 0 or atr_bps <= 0:
            return Signal()

        is_long = record["direction"] == TRADE_DIRECTION_LONG
        sign = 1 if is_long else -1
        k_sl = config.k_sl_long if is_long else config.k_sl_short
        hold_hours = config.hold_hours_long if is_long else config.hold_hours_short

        # §2.2 止损价
        atr_price = entry_price * atr_bps / 10000.0
        stop_price = entry_price - sign * k_sl * atr_price

        # §3.1 名义暴露 sizing
        stop_dist_frac = k_sl * atr_bps / 10000.0
        if stop_dist_frac <= 0:
            return Signal()
        notional_frac = config.risk_per_trade / stop_dist_frac
        qty = notional_frac * state.capital / (entry_price * state.contract_size)
        if config.integer_lots:
            qty = float(int(qty))
        if qty <= 0:
            return Signal()

        # 记录持仓 bookkeeping；墙钟起点在首根持仓 bar（真实成交）锚定，故此处只播种常量
        state.extra["va_stop_price"] = stop_price
        state.extra["va_hold_bars"] = int(round(hold_hours * 12))  # 5m 根数 = 小时×12（对齐研究 H*12）
        state.extra["va_await_entry"] = True
        state.extra["va_last_entry_date"] = today

        action = TRADE_ACTION_BUY if is_long else TRADE_ACTION_SELL
        return Signal(
            action=action,
            reason=f"entry_{record['tier_v40']}",
            volume=qty,
            diagnostics={
                "tier": record["tier"],
                "tier_v40": record["tier_v40"],
                "direction": record["direction"],
                "entry_price": entry_price,
                "atr_bps": atr_bps,
                "stop_price": stop_price,
                "k_sl": k_sl,
                "notional_frac": notional_frac,
                "hold_hours": hold_hours,
            },
        )

    @staticmethod
    def _clear_holding(state: State[VAAsymmetryCompositeParams]) -> None:
        for key in ("va_stop_price", "va_hold_bars", "va_bars_held", "va_await_entry"):
            state.extra.pop(key, None)

    # ---- A 层查表惰性预加载（等价 on_init 预加载）----

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
    def _load_a_table(timeline_path: str, symbol: str) -> dict[_date, dict]:
        """从 A 层 timeline parquet 构建 {date -> 记录} 查表（当前合约）。

        记录字段: tier / tier_v40 / direction / entry_atr_bps。
        同日多事件取最早 event_time。文件缺失或无命中返回空表（策略不交易）。
        """
        import pandas as pd

        path = Path(timeline_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            return {}

        cols = ["contract", "event_time", "tier", "daily_atr_10_bps"]
        try:
            tl = pd.read_parquet(path, columns=cols)
        except Exception:
            tl = pd.read_parquet(path)

        tl = tl[tl["contract"] == symbol]
        tl = tl[tl["tier"].isin(A_TIER_RAW)]
        if tl.empty:
            return {}

        tl = tl.copy()
        tl["event_time"] = pd.to_datetime(tl["event_time"])
        tl = tl.sort_values("event_time")

        table: dict[_date, dict] = {}
        for _, row in tl.iterrows():
            ev_date = row["event_time"].date()
            if ev_date in table:  # 同日取最早（已排序，首个即最早）
                continue
            tier = str(row["tier"])
            table[ev_date] = {
                "tier": tier,
                "tier_v40": TIER_TO_V40.get(tier, tier),
                "direction": TRADE_DIRECTION_LONG if tier.startswith("UP") else TRADE_DIRECTION_SHORT,
                "entry_atr_bps": float(row["daily_atr_10_bps"]),
            }
        return table
