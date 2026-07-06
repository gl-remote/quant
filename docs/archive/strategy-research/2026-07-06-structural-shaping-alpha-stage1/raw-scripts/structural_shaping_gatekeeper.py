"""
文件级元信息：
- 创建背景：主题 structural-shaping-alpha 阶段 1 gatekeeper。experiment-plan v2
  要求用 6 种行业共识组合（A-F）在 DirRandom 入场、uniform_20bar 采样下检验
  "结构塑形是否具有独立 alpha"。若走 CLI + vnpy 引擎需要新增策略类并处理平仓
  配对 issue，成本远高于本命题所需。
- 用途：轻量 Python 模拟器。读 5m CSV → 生成 uniform_20bar 事件 → 对每个事件
  独立随机方向 → 6 combos 用同一份事件模拟出场 → 输出每笔 ATR 归一化净收益 →
  paired diff vs E + cluster bootstrap（按合约聚类）→ 判决 gate 条件。
- 注意事项：
  1. 仅用于阶段 1 gatekeeper 判决。任何"通过"结论都必须进入阶段 2 加严采样
     （多方向 / 多采样 / overlap_control）复核。
  2. 事件级 mean 用 ATR/笔（归一化），仓位差异（A vs E）仅在 combo D 的
     Sharpe/Sortino/MDD 汇总里体现。gatekeeper 主要判据是 mean 净值。
  3. 成本 0.05 ATR/笔单边（已按 value-area 家族一致口径）。
  4. 一次性脚本；阶段 1 结束后随 workbench 一起归档到
     archive/strategy-research/<batch>/raw-scripts/。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from common.contract_specs import BROKER_ADDON_DFCF, CONTRACT_SPECS, ContractSpec
from data.output_paths import market_csv_dir, project_data_root

Side = Literal[1, -1]
ComboKey = Literal["A", "B", "C", "D", "E", "F", "D2", "G", "H", "I", "J", "K", "L", "M", "N"]

# ────────────────────── 品种覆盖 ──────────────────────
# 10 品种 × 2 主力合约 = 20 合约。sc2601 数据未落库，替换为 sc2512。
SYMBOLS: list[tuple[str, str, str]] = [
    # (sector, symbol, csv_file)
    ("black", "rb2601", "SHFE.rb2601.tqsdk.5m.csv"),
    ("black", "rb2605", "SHFE.rb2605.tqsdk.5m.csv"),
    ("black", "i2601", "DCE.i2601.tqsdk.5m.csv"),
    ("black", "i2509", "DCE.i2509.tqsdk.5m.csv"),
    ("metals", "cu2601", "SHFE.cu2601.tqsdk.5m.csv"),
    ("metals", "cu2509", "SHFE.cu2509.tqsdk.5m.csv"),
    ("metals", "al2601", "SHFE.al2601.tqsdk.5m.csv"),
    ("metals", "al2509", "SHFE.al2509.tqsdk.5m.csv"),
    ("energy_chem", "sc2512", "INE.sc2512.tqsdk.5m.csv"),
    ("energy_chem", "sc2509", "INE.sc2509.tqsdk.5m.csv"),
    ("energy_chem", "TA601", "CZCE.TA601.tqsdk.5m.csv"),
    ("energy_chem", "TA509", "CZCE.TA509.tqsdk.5m.csv"),
    ("agri_dce", "m2601", "DCE.m2601.tqsdk.5m.csv"),
    ("agri_dce", "m2605", "DCE.m2605.tqsdk.5m.csv"),
    ("agri_dce", "p2601", "DCE.p2601.tqsdk.5m.csv"),
    ("agri_dce", "p2605", "DCE.p2605.tqsdk.5m.csv"),
    ("agri_czce", "SR601", "CZCE.SR601.tqsdk.5m.csv"),
    ("agri_czce", "SR605", "CZCE.SR605.tqsdk.5m.csv"),
    ("agri_czce", "CF601", "CZCE.CF601.tqsdk.5m.csv"),
    ("agri_czce", "CF509", "CZCE.CF509.tqsdk.5m.csv"),
]

# ────────────────────── Combo 规格 ──────────────────────
@dataclass(frozen=True)
class ComboSpec:
    key: ComboKey
    label: str
    stop_atr: float  # 初始止损（ATR 倍数）
    take_atr: float | None  # 止盈（ATR 倍数），None 代表无止盈
    max_bars: int  # 时间退出（bar 数），99999 代表 EOD 强平
    trailing_breakeven: bool  # MFE ≥ arm_mfe_atr 后止损移到 entry + buffer
    eod_exit: bool  # True: 日盘结束强平（Combo A）
    arm_mfe_atr: float = 1.0  # 触发 armed 的 MFE 阈值（ATR 倍数）
    breakeven_buffer_atr: float = 0.0  # armed 后 stop 相对 entry 的缓冲（顺方向 ATR 倍数）
    trailing_chandelier_atr: float | None = None  # 若非 None：armed 后 stop = max_mfe_price - N ATR（chandelier trailing）


COMBOS: list[ComboSpec] = [
    ComboSpec("A", "教科书 R:R=2:1 + EOD", stop_atr=1.5, take_atr=3.0, max_bars=99999, trailing_breakeven=False, eod_exit=True),
    ComboSpec("B", "紧止损短线 R:R=2:1", stop_atr=0.5, take_atr=1.0, max_bars=40, trailing_breakeven=False, eod_exit=False),
    ComboSpec("C", "宽止损波段 R:R=3:1", stop_atr=2.5, take_atr=7.5, max_bars=160, trailing_breakeven=False, eod_exit=False),
    ComboSpec("D", "波动率目标 + breakeven trailing 无止盈", stop_atr=1.0, take_atr=None, max_bars=80, trailing_breakeven=True, eod_exit=False),
    ComboSpec("E", "基准（固定 lot / ATR 止损止盈）", stop_atr=1.5, take_atr=2.0, max_bars=80, trailing_breakeven=False, eod_exit=False),
    ComboSpec("F", "教科书 + breakeven trailing", stop_atr=1.5, take_atr=3.0, max_bars=80, trailing_breakeven=True, eod_exit=False),
    # D2 = D 修正版：MFE ≥ 2 ATR 才 armed + 0.5 ATR 缓冲 + 加 3 ATR 止盈
    ComboSpec(
        "D2",
        "波动率目标 v2（MFE≥2 armed / 缓冲 0.5 / 止盈 3.0）",
        stop_atr=1.0,
        take_atr=3.0,
        max_bars=80,
        trailing_breakeven=True,
        eod_exit=False,
        arm_mfe_atr=2.0,
        breakeven_buffer_atr=0.5,
    ),
    # G/H/I：低 R:R 震荡收割猜想（用户 §8.4）
    ComboSpec("G", "对称 R:R=1:1", stop_atr=1.0, take_atr=1.0, max_bars=80, trailing_breakeven=False, eod_exit=False),
    ComboSpec("H", "反 R:R=1:2（宽止损小止盈）", stop_atr=2.0, take_atr=1.0, max_bars=80, trailing_breakeven=False, eod_exit=False),
    ComboSpec("I", "极反 R:R=1:3（宽止损极小止盈）", stop_atr=3.0, take_atr=1.0, max_bars=80, trailing_breakeven=False, eod_exit=False),
    # J/K：B vs E 的二维拆分（stop 大小 × max_bars）——用户 §8.6
    ComboSpec("J", "E 距离 + 短时（40 bar）", stop_atr=1.5, take_atr=2.0, max_bars=40, trailing_breakeven=False, eod_exit=False),
    ComboSpec("K", "短距（0.5/1.0）+ E 时间（80 bar）", stop_atr=0.5, take_atr=1.0, max_bars=80, trailing_breakeven=False, eod_exit=False),
    # L：A 的 take-to-trail 变体（MFE ≥ 3 ATR 后 stop 移到 entry，无止盈）——用户 §8.8
    ComboSpec(
        "L",
        "A + take→trail（MFE≥3 后 breakeven，无止盈）",
        stop_atr=1.5,
        take_atr=None,
        max_bars=80,
        trailing_breakeven=True,
        eod_exit=False,
        arm_mfe_atr=3.0,
        breakeven_buffer_atr=0.0,
    ),
    # M：A + chandelier trailing（MFE≥3 armed，stop 跟随 MFE - 1.5 ATR，不低于 entry）
    ComboSpec(
        "M",
        "A + chandelier（armed@3 · trail 1.5 · floor=entry）",
        stop_atr=1.5,
        take_atr=None,
        max_bars=80,
        trailing_breakeven=True,
        eod_exit=False,
        arm_mfe_atr=3.0,
        breakeven_buffer_atr=0.0,
        trailing_chandelier_atr=1.5,
    ),
    # N：A + chandelier trailing 延后 armed（MFE≥4.5 才开始跟，之后同 M）
    ComboSpec(
        "N",
        "A + chandelier（armed@4.5 · trail 1.5 · floor=entry）",
        stop_atr=1.5,
        take_atr=None,
        max_bars=80,
        trailing_breakeven=True,
        eod_exit=False,
        arm_mfe_atr=4.5,
        breakeven_buffer_atr=0.0,
        trailing_chandelier_atr=1.5,
    ),
]

# ────────────────────── 常量 ──────────────────────
COST_PER_TRADE_ATR = 0.05  # 单边成本 ATR/笔
ATR_PERIOD = 14
SAMPLING_STRIDE = 20  # uniform_20bar
DIR_RANDOM_SEED = 20260706  # 全局方向 rng 种子（固定，便于复现）
BOOTSTRAP_ITER = 5000


def realistic_cost_atr_per_side(spec: ContractSpec, entry_price: float, entry_atr_price: float) -> float:
    """按实际合约规格计算单笔单边成本占 entry_atr 的比例。

    - 佣金：按当前 price 估价（含费率/固定），单边
    - 滑点：单边 lots × size × tick × slip_tick
    - 换算为 ATR：cost_yuan / (entry_atr_price × contract_size)

    entry_atr_price 是"以价格单位表示的 ATR"（未乘合约乘数）。
    """
    commission_yuan = spec.total_commission(price=entry_price, lots=1, broker_addon=BROKER_ADDON_DFCF)
    slippage_yuan = spec.slippage(lots=1)
    cost_yuan_per_side = commission_yuan + slippage_yuan
    atr_yuan = entry_atr_price * max(spec.size, 1)
    if atr_yuan <= 0:
        return COST_PER_TRADE_ATR
    return cost_yuan_per_side / atr_yuan

# ────────────────────── 数据加载 & ATR ──────────────────────

def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    # ATR(14) - 简化：TR = max(H-L, |H-C_prev|, |L-C_prev|)
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    # Wilder smoothing 近似为 SMA(14)
    atr = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["atr"] = atr
    df["session_date"] = df["datetime"].dt.date
    return df


# ────────────────────── 事件生成 ──────────────────────

@dataclass(frozen=True)
class Event:
    symbol: str
    sector: str
    entry_idx: int  # 入场 bar index（在下一根 bar open 入场）
    side: Side
    entry_price: float
    entry_atr: float
    session_date: object


def make_events(sector: str, symbol: str, df: pd.DataFrame, rng: random.Random) -> list[Event]:
    events: list[Event] = []
    n = len(df)
    # 首个可用采样点：确保 ATR 已成型（idx >= ATR_PERIOD），且下一根 bar 存在
    first = ATR_PERIOD
    for i in range(first, n - 1, SAMPLING_STRIDE):
        entry_idx = i + 1  # 入场在下一根 bar 开盘
        if entry_idx >= n:
            break
        entry_atr = df["atr"].iat[i]
        if not math.isfinite(entry_atr) or entry_atr <= 0:
            continue
        entry_price = df["open"].iat[entry_idx]
        if not math.isfinite(entry_price):
            continue
        side: Side = 1 if rng.random() < 0.5 else -1
        events.append(
            Event(
                symbol=symbol,
                sector=sector,
                entry_idx=entry_idx,
                side=side,
                entry_price=float(entry_price),
                entry_atr=float(entry_atr),
                session_date=df["session_date"].iat[entry_idx],
            )
        )
    return events


# ────────────────────── Combo 出场模拟 ──────────────────────

@dataclass
class TradeOutcome:
    exit_reason: str
    exit_bars: int
    net_atr: float  # 每笔 ATR 归一化净收益（已扣双边成本）


def simulate_combo(event: Event, df: pd.DataFrame, combo: ComboSpec, cost_atr_per_side: float = COST_PER_TRADE_ATR) -> TradeOutcome:
    side = event.side
    entry = event.entry_price
    atr = event.entry_atr
    stop_dist = combo.stop_atr * atr
    take_dist = combo.take_atr * atr if combo.take_atr is not None else None
    stop_price = entry - side * stop_dist  # long 时低于入场；short 时高于入场
    take_price = entry + side * take_dist if take_dist is not None else None
    breakeven_armed = False
    max_mfe_price = entry  # 追踪最高浮盈价，用于 chandelier trailing
    two_way_cost = 2 * cost_atr_per_side
    n = len(df)

    max_bars = combo.max_bars
    for step in range(1, max_bars + 1):
        j = event.entry_idx + step
        if j >= n:
            # 数据末端强平：按最后一根 close 出
            j = n - 1
            close_j = df["close"].iat[j]
            gross = side * (close_j - entry) / atr
            net = gross - two_way_cost
            return TradeOutcome(exit_reason="data_end", exit_bars=step, net_atr=float(net))

        # EOD 强平（Combo A）：当前 bar session_date 与入场不同 → 上一 bar 尾盘出场
        if combo.eod_exit:
            cur_date = df["session_date"].iat[j]
            if cur_date != event.session_date:
                prev_close = df["close"].iat[j - 1]
                gross = side * (prev_close - entry) / atr
                net = gross - two_way_cost
                return TradeOutcome(exit_reason="eod", exit_bars=step - 1, net_atr=float(net))

        high_j = df["high"].iat[j]
        low_j = df["low"].iat[j]

        # 追踪最高浮盈价（chandelier trailing 的锚点）
        if side == 1 and high_j > max_mfe_price:
            max_mfe_price = high_j
        elif side == -1 and low_j < max_mfe_price:
            max_mfe_price = low_j

        # Trailing breakeven：MFE ≥ arm_mfe_atr 后 stop 移到 entry + buffer（顺方向）
        if combo.trailing_breakeven and not breakeven_armed:
            mfe = (high_j - entry) if side == 1 else (entry - low_j)
            if mfe >= combo.arm_mfe_atr * atr:
                breakeven_armed = True
                stop_price = entry + side * combo.breakeven_buffer_atr * atr

        # Chandelier trailing：armed 后 stop 跟随 max_mfe_price 保持 trailing_chandelier_atr 距离
        # stop 只能沿顺方向移动（不倒退），且不能低于 entry + breakeven_buffer（保本兜底）
        if combo.trailing_breakeven and breakeven_armed and combo.trailing_chandelier_atr is not None:
            trail_dist = combo.trailing_chandelier_atr * atr
            chandelier_stop = max_mfe_price - side * trail_dist
            floor = entry + side * combo.breakeven_buffer_atr * atr
            if side == 1:
                new_stop = max(stop_price, chandelier_stop, floor)
            else:
                new_stop = min(stop_price, chandelier_stop, floor)
            stop_price = new_stop

        # 判断触发（保守：同 bar 触发 stop 与 take 都算 stop 先，因 gatekeeper 需保守估计）
        stop_hit = (low_j <= stop_price) if side == 1 else (high_j >= stop_price)
        take_hit = False
        if take_price is not None:
            take_hit = (high_j >= take_price) if side == 1 else (low_j <= take_price)

        if stop_hit:
            exit_price = stop_price
            gross = side * (exit_price - entry) / atr
            net = gross - two_way_cost
            reason = "breakeven" if breakeven_armed else "stop"
            return TradeOutcome(exit_reason=reason, exit_bars=step, net_atr=float(net))
        if take_hit:
            exit_price = take_price
            gross = side * (exit_price - entry) / atr
            net = gross - two_way_cost
            return TradeOutcome(exit_reason="take", exit_bars=step, net_atr=float(net))

    # 到达时间上限
    j = min(event.entry_idx + max_bars, n - 1)
    exit_price = df["close"].iat[j]
    gross = side * (exit_price - entry) / atr
    net = gross - two_way_cost
    return TradeOutcome(exit_reason="time_exit", exit_bars=max_bars, net_atr=float(net))


# ────────────────────── 统计 ──────────────────────

@dataclass
class ComboAggregate:
    key: ComboKey
    label: str
    n: int
    mean_net_atr: float
    median_net_atr: float
    win_rate: float
    mean_exit_bars: float
    exit_reason_counts: dict[str, int]

    # vs E paired diff
    paired_diff_mean: float | None = None
    paired_diff_ci_lo: float | None = None
    paired_diff_ci_hi: float | None = None
    paired_diff_p_gt_0: float | None = None


def cluster_bootstrap_paired_diff(
    diff_by_contract: dict[str, list[float]],
    n_iter: int,
    rng: np.random.Generator,
) -> tuple[float, float, float]:
    """按合约聚类的 paired diff bootstrap。返回 (mean, ci_lo, ci_hi)。"""
    contracts = list(diff_by_contract.keys())
    if not contracts:
        return (0.0, 0.0, 0.0)
    means = []
    n_contracts = len(contracts)
    for _ in range(n_iter):
        sampled = rng.choice(n_contracts, size=n_contracts, replace=True)
        collected: list[float] = []
        for idx in sampled:
            collected.extend(diff_by_contract[contracts[idx]])
        means.append(float(np.mean(collected)) if collected else 0.0)
    arr = np.asarray(means)
    return float(arr.mean()), float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def bootstrap_p_gt_0(
    diff_by_contract: dict[str, list[float]],
    n_iter: int,
    rng: np.random.Generator,
) -> float:
    """单侧 H1: mean > 0 的 bootstrap p-value（等价于 mean ≤ 0 的比例）。"""
    contracts = list(diff_by_contract.keys())
    if not contracts:
        return 1.0
    n_contracts = len(contracts)
    n_ge0 = 0
    for _ in range(n_iter):
        sampled = rng.choice(n_contracts, size=n_contracts, replace=True)
        collected: list[float] = []
        for idx in sampled:
            collected.extend(diff_by_contract[contracts[idx]])
        if collected and float(np.mean(collected)) > 0:
            n_ge0 += 1
    return 1.0 - n_ge0 / n_iter


# ────────────────────── 主流程 ──────────────────────

@dataclass
class TradeRow:
    combo: ComboKey
    symbol: str
    sector: str
    entry_idx: int
    side: int
    entry_price: float
    entry_atr: float
    exit_reason: str
    exit_bars: int
    net_atr: float


def main() -> None:
    args = _parse_args()
    scale = args.scale
    use_realistic_cost = not args.flat_cost_debug
    csv_dir = market_csv_dir()
    out_dir = project_data_root() / "research" / "structural_shaping_gatekeeper"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    scaled_combos = _scale_combos(COMBOS, scale)

    rng_dir = random.Random(DIR_RANDOM_SEED)
    rng_np = np.random.default_rng(DIR_RANDOM_SEED)

    all_events: list[Event] = []
    trades: list[TradeRow] = []
    symbol_stats: list[dict[str, object]] = []

    for sector, symbol, csv_file in SYMBOLS:
        path = csv_dir / csv_file
        if not path.exists():
            print(f"[skip] missing csv: {path}")
            continue
        df = load_bars(path)
        events = make_events(sector, symbol, df, rng_dir)
        all_events.extend(events)
        # 每合约的成本 spec：realistic 模式下按 contract_specs 查询
        symbol_full = csv_file.split(".tqsdk")[0]  # "SHFE.rb2601" 等
        spec = CONTRACT_SPECS.get_symbol(symbol_full) if use_realistic_cost else None
        cost_stats: list[float] = []
        for combo in scaled_combos:
            for ev in events:
                if use_realistic_cost and spec is not None:
                    cost_side = realistic_cost_atr_per_side(spec, ev.entry_price, ev.entry_atr)
                else:
                    cost_side = COST_PER_TRADE_ATR
                if combo.key == "E":
                    cost_stats.append(cost_side)
                outcome = simulate_combo(ev, df, combo, cost_atr_per_side=cost_side)
                trades.append(
                    TradeRow(
                        combo=combo.key,
                        symbol=symbol,
                        sector=sector,
                        entry_idx=ev.entry_idx,
                        side=int(ev.side),
                        entry_price=ev.entry_price,
                        entry_atr=ev.entry_atr,
                        exit_reason=outcome.exit_reason,
                        exit_bars=outcome.exit_bars,
                        net_atr=outcome.net_atr,
                    )
                )
        avg_cost = float(np.mean(cost_stats)) if cost_stats else COST_PER_TRADE_ATR
        symbol_stats.append({"sector": sector, "symbol": symbol, "bars": len(df), "events": len(events), "avg_cost_atr_side": avg_cost})
        print(f"[ok] {sector:12s} {symbol:8s} bars={len(df):5d} events={len(events):4d} avg_cost_atr_side={avg_cost:.4f}")

    # ── 写全量 CSV ──
    cost_tag = "realcost" if use_realistic_cost else "flat005"
    csv_path = out_dir / f"structural_shaping_gatekeeper_scale{scale:g}_{cost_tag}_{timestamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["combo", "symbol", "sector", "entry_idx", "side", "entry_price", "entry_atr",
                          "exit_reason", "exit_bars", "net_atr"])
        for t in trades:
            writer.writerow([t.combo, t.symbol, t.sector, t.entry_idx, t.side,
                             f"{t.entry_price:.4f}", f"{t.entry_atr:.4f}",
                             t.exit_reason, t.exit_bars, f"{t.net_atr:.6f}"])

    # ── 汇总每 combo ──
    aggregates: dict[ComboKey, ComboAggregate] = {}
    trades_by_combo: dict[ComboKey, list[TradeRow]] = {c.key: [] for c in scaled_combos}
    for t in trades:
        trades_by_combo[t.combo].append(t)

    # E baseline 对齐（按 event key 索引）
    def event_key(t: TradeRow) -> tuple[str, int, int]:
        return (t.symbol, t.entry_idx, t.side)

    e_map: dict[tuple[str, int, int], TradeRow] = {event_key(t): t for t in trades_by_combo["E"]}

    for combo in scaled_combos:
        combo_trades = trades_by_combo[combo.key]
        nets = [t.net_atr for t in combo_trades]
        reasons: dict[str, int] = {}
        for t in combo_trades:
            reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
        agg = ComboAggregate(
            key=combo.key,
            label=combo.label,
            n=len(combo_trades),
            mean_net_atr=float(np.mean(nets)) if nets else 0.0,
            median_net_atr=float(np.median(nets)) if nets else 0.0,
            win_rate=float(np.mean([1 if x > 0 else 0 for x in nets])) if nets else 0.0,
            mean_exit_bars=float(np.mean([t.exit_bars for t in combo_trades])) if combo_trades else 0.0,
            exit_reason_counts=reasons,
        )

        if combo.key != "E":
            diff_by_contract: dict[str, list[float]] = {}
            for t in combo_trades:
                ek = event_key(t)
                if ek not in e_map:
                    continue
                diff = t.net_atr - e_map[ek].net_atr
                diff_by_contract.setdefault(t.symbol, []).append(diff)
            mean, lo, hi = cluster_bootstrap_paired_diff(diff_by_contract, BOOTSTRAP_ITER, rng_np)
            p = bootstrap_p_gt_0(diff_by_contract, BOOTSTRAP_ITER, rng_np)
            agg.paired_diff_mean = mean
            agg.paired_diff_ci_lo = lo
            agg.paired_diff_ci_hi = hi
            agg.paired_diff_p_gt_0 = p

        aggregates[combo.key] = agg

    # F vs A 特别诊断
    a_map: dict[tuple[str, int, int], TradeRow] = {event_key(t): t for t in trades_by_combo["A"]}
    fa_diff_by_contract: dict[str, list[float]] = {}
    for t in trades_by_combo["F"]:
        ek = event_key(t)
        if ek in a_map:
            fa_diff_by_contract.setdefault(t.symbol, []).append(t.net_atr - a_map[ek].net_atr)
    fa_mean, fa_lo, fa_hi = cluster_bootstrap_paired_diff(fa_diff_by_contract, BOOTSTRAP_ITER, rng_np)
    fa_p = bootstrap_p_gt_0(fa_diff_by_contract, BOOTSTRAP_ITER, rng_np)

    # ── 组合层 Sharpe（仅 Combo D 使用完整量化阈值，其他做 mean 判据）──
    def combo_sharpe(combo_trades: list[TradeRow]) -> tuple[float, float]:
        vals = np.asarray([t.net_atr for t in combo_trades])
        if len(vals) < 2 or vals.std(ddof=1) == 0:
            return 0.0, 0.0
        sharpe = float(vals.mean() / vals.std(ddof=1))
        # 简易 Sortino
        downside = vals[vals < 0]
        if len(downside) < 2 or downside.std(ddof=1) == 0:
            sortino = 0.0
        else:
            sortino = float(vals.mean() / downside.std(ddof=1))
        return sharpe, sortino

    sharpe_map: dict[ComboKey, tuple[float, float]] = {c.key: combo_sharpe(trades_by_combo[c.key]) for c in scaled_combos}

    # ── 判决 ──
    e_agg = aggregates["E"]
    e_sharpe, e_sortino = sharpe_map["E"]
    verdicts: dict[ComboKey, str] = {}
    any_pass_mean = False
    any_pass_risk = False
    for combo in scaled_combos:
        if combo.key == "E":
            verdicts[combo.key] = "baseline"
            continue
        agg = aggregates[combo.key]
        pass_mean = (
            agg.mean_net_atr > 0
            and agg.paired_diff_mean is not None
            and agg.paired_diff_ci_lo is not None
            and agg.paired_diff_ci_lo > 0
        )
        sharpe, sortino = sharpe_map[combo.key]
        pass_risk = (sharpe - e_sharpe) > 0.3 or (sortino - e_sortino) > 0.3
        if pass_mean:
            any_pass_mean = True
        if pass_risk:
            any_pass_risk = True
        tag = []
        if pass_mean:
            tag.append("mean_pass")
        if pass_risk:
            tag.append("risk_pass")
        if not tag:
            tag.append("no_edge")
        verdicts[combo.key] = "+".join(tag)

    gate_pass = any_pass_mean or any_pass_risk

    summary: dict[str, object] = {
        "timestamp": timestamp,
        "scale": scale,
        "cost_per_trade_atr": COST_PER_TRADE_ATR,
        "use_realistic_cost": use_realistic_cost,
        "sampling_stride": SAMPLING_STRIDE,
        "atr_period": ATR_PERIOD,
        "seed": DIR_RANDOM_SEED,
        "bootstrap_iter": BOOTSTRAP_ITER,
        "symbols": symbol_stats,
        "combos": [
            {
                "key": agg.key,
                "label": agg.label,
                "n": agg.n,
                "mean_net_atr": agg.mean_net_atr,
                "median_net_atr": agg.median_net_atr,
                "win_rate": agg.win_rate,
                "mean_exit_bars": agg.mean_exit_bars,
                "sharpe": sharpe_map[agg.key][0],
                "sortino": sharpe_map[agg.key][1],
                "paired_diff_vs_E_mean": agg.paired_diff_mean,
                "paired_diff_vs_E_ci_lo": agg.paired_diff_ci_lo,
                "paired_diff_vs_E_ci_hi": agg.paired_diff_ci_hi,
                "paired_diff_vs_E_p_gt_0": agg.paired_diff_p_gt_0,
                "verdict": verdicts[agg.key],
                "exit_reasons": agg.exit_reason_counts,
            }
            for agg in aggregates.values()
        ],
        "F_vs_A": {"mean": fa_mean, "ci_lo": fa_lo, "ci_hi": fa_hi, "p_gt_0": fa_p},
        "gate_pass": gate_pass,
        "csv_path": str(csv_path),
    }

    json_path = out_dir / f"structural_shaping_gatekeeper_scale{scale:g}_{cost_tag}_{timestamp}.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("\n" + "=" * 70)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"\nSCALE: {scale}")
    print(f"CSV:  {csv_path}")
    print(f"JSON: {json_path}")
    print(f"GATE: {'PASS' if gate_pass else 'FROZEN'}")


def _scale_combos(combos: list[ComboSpec], scale: float) -> list[ComboSpec]:
    """把所有距离档 (ATR 倍数) 与时间窗按同一系数放大。

    - stop_atr / take_atr / arm_mfe_atr / breakeven_buffer_atr：直接乘 scale
    - max_bars：正比放大（EOD 的 sentinel 99999 保持不变）
    - eod_exit / trailing_breakeven：仅结构参数，不变
    """
    if scale == 1.0:
        return list(combos)
    out: list[ComboSpec] = []
    for c in combos:
        new_max_bars = c.max_bars if c.max_bars >= 99999 else int(round(c.max_bars * scale))
        out.append(
            ComboSpec(
                key=c.key,
                label=f"{c.label} [x{scale:g}]",
                stop_atr=c.stop_atr * scale,
                take_atr=(c.take_atr * scale) if c.take_atr is not None else None,
                max_bars=new_max_bars,
                trailing_breakeven=c.trailing_breakeven,
                eod_exit=c.eod_exit,
                arm_mfe_atr=c.arm_mfe_atr * scale,
                breakeven_buffer_atr=c.breakeven_buffer_atr * scale,
                trailing_chandelier_atr=(c.trailing_chandelier_atr * scale) if c.trailing_chandelier_atr is not None else None,
            )
        )
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Structural-shaping-alpha stage 1 gatekeeper (lightweight)")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="把所有 combo 的距离档（ATR 倍数）与时间窗按同一系数放大，用于跳出短距回归带的稳健性对照。默认 1.0。",
    )
    parser.add_argument(
        "--flat-cost-debug",
        action="store_true",
        help="回退到扁平成本模型（0.05 ATR/单边）——**已知跨品种低估 4.5 倍**，"
             "仅供快速原型/历史对比 debug；生产判决必须走默认 realistic-cost。",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
