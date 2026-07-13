#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：研究侧复现与工程侧 run_id=15 都已就绪，需精细分层对比
  定位差距根因（信号覆盖率 / 成本 / CAP压缩 / 时间退出 / 止损）。
- 用途：VA 非对称复合策略「研究 vs 工程」端到端分层对比脚本。
- 注意事项：
  1. 研究侧在内存中直接复用 reproduce_research_side 的 build + simulate 流程，
     不依赖中间 parquet（避免每次都跑 ~2.4min 失败）。
  2. 工程侧从 project_data/database/backtest/quant.db 读 run_id=15，
     用 FIFO 按(symbol, direction)配对 open/close 成单笔 round-trip。
  3. 输出：stdout 打印报告 + docs/workbench/.../outputs/compare-r-e/ 下
     落 3 份 parquet（研究侧 trades、工程侧 paired、匹配对）+ summary.json。
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "workspace"))

from common.contract_specs import CONTRACT_SPECS
from common.symbol_utils import extract_contract_prefix
from strategies.classifiers.poc_va import (
    ClassifierConfig,
    daily_atr_sma,
    evaluate_dataset,
    trend_log_return,
    volume_weighted_skew,
)

# ==============================================================================
# 全局常量（与研究侧 reproduce_research_side.py 完全一致）
# ==============================================================================
CSV_DIR = REPO / "project_data/market_data/csv"
ENG_DB = REPO / "project_data/database/backtest/quant.db"
OUT_DIR = REPO / "docs/workbench/va-asymmetry-composite/outputs/compare-r-e"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ATR_ENTRY_WIN = 10
TREND_ENTRY_WIN = 10
ROLLING_DAYS = 20
WARMUP_DAYS = 20
DEDUP_H = 8
CAP = 4.0
RISK_PER_TRADE = 0.02
EQUITY_INIT = 1_000_000.0
ANNUAL_FACTOR = 252

K_L_SL, H_L = 1.0, 8
K_S_SL, H_S = 2.5, 10

TICK_MAP: dict[str, float] = {
    "m": 1.0, "y": 1.0, "c": 1.0, "cs": 1.0, "i": 0.5, "p": 2.0,
    "j": 0.5, "jm": 0.5, "eg": 1.0, "eb": 1.0, "pg": 1.0,
    "rb": 1.0, "cu": 10.0, "al": 5.0, "zn": 5.0, "au": 0.02, "ag": 1.0,
    "hc": 1.0, "pb": 5.0, "ni": 10.0, "sn": 10.0, "sp": 2.0, "ss": 5.0,
    "fu": 1.0, "ru": 5.0,
    "SR": 1.0, "CF": 5.0, "TA": 2.0, "MA": 1.0, "OI": 1.0, "RM": 1.0,
    "FG": 1.0, "AP": 1.0, "CJ": 5.0, "SM": 2.0, "SF": 2.0,
    "sc": 0.1, "lu": 1.0, "nr": 5.0,
}

SYMBOL_TYPE: dict[str, str] = {}
for p in ["if", "ih", "ic", "im", "t", "tf", "ts", "au", "ag"]:
    SYMBOL_TYPE[p] = "A"
for p in ["rb", "hc", "i", "j", "jm", "ta", "ma", "pp", "l", "v", "eb", "eg", "sc", "fu", "bu"]:
    SYMBOL_TYPE[p] = "B"
for p in ["cu", "al", "zn", "ni", "sn", "pb", "m", "y", "p", "c", "cs", "cf", "sr", "oi", "rm", "fg"]:
    SYMBOL_TYPE[p] = "C"

ENG_RUN_ID = 15

# ==============================================================================
# Section A · 研究侧管线（复制 reproduce_research_side 核心步骤）
# ==============================================================================
def get_tick(symbol: str) -> float:
    _, contract = symbol.split(".")
    prefix = "".join(c for c in contract if c.isalpha())
    return TICK_MAP.get(prefix, 1.0)


def discover_symbols() -> list[str]:
    return sorted([p.name.replace(".tqsdk.5m.csv", "") for p in CSV_DIR.glob("*.tqsdk.5m.csv")])


def build_events(symbol: str, tick: float) -> pd.DataFrame:
    p = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    bars = pd.read_csv(p)
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)
    bars["date"] = bars["datetime"].dt.date
    mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    hourly_idx = bars.index[mask].to_list()
    rows = []
    for idx in hourly_idx:
        t = bars.loc[idx, "datetime"]
        close_t_val = bars.loc[idx, "close"]
        fut8h = idx + 96
        fut4h = idx + 48
        if fut8h >= len(bars):
            continue
        ret_8h = np.log(float(bars.loc[fut8h, "close"]) / float(close_t_val))
        ret_4h = np.log(float(bars.loc[fut4h, "close"]) / float(close_t_val))
        current_date = t.date()
        prev = bars[bars["date"] < current_date]
        if len(prev) == 0:
            continue
        prev_date = prev["date"].max()
        prev_day_bars = prev[prev["date"] == prev_date]
        if len(prev_day_bars) < 20:
            continue
        sk = volume_weighted_skew(
            prev_day_bars["close"].to_numpy(dtype=float),
            prev_day_bars["volume"].to_numpy(dtype=float),
        )
        if np.isnan(sk):
            continue
        rows.append({
            "contract": symbol, "event_time": t, "event_date": pd.Timestamp(current_date),
            "close_t": float(close_t_val), "A3_skew": sk,
            "ret_8h": ret_8h, "ret_4h": ret_4h,
        })
    return pd.DataFrame(rows)


def build_daily_features(symbol: str) -> pd.DataFrame:
    p = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    bars = pd.read_csv(p, usecols=["datetime", "open", "high", "low", "close", "volume"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars["date"] = pd.to_datetime(bars["datetime"].dt.date)
    daily = bars.groupby("date").agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index().sort_values("date").reset_index(drop=True)
    if len(daily) < max(ATR_ENTRY_WIN, TREND_ENTRY_WIN) + 1:
        return pd.DataFrame()
    a3_map: dict = {}
    for date_val, g in bars.groupby("date"):
        prices = g["close"].to_numpy(dtype=float)
        volumes = g["volume"].to_numpy(dtype=float)
        a3_map[pd.Timestamp(date_val)] = volume_weighted_skew(prices, volumes)
    daily["A3_skew_spec"] = daily["date"].map(a3_map)
    daily["daily_atr_spec"] = daily_atr_sma(
        daily["high"], daily["low"], daily["close"], ATR_ENTRY_WIN
    )
    daily["trend_ret_M_spec"] = trend_log_return(daily["close"], TREND_ENTRY_WIN)
    prev_close = daily["close"].shift(1)
    tr = np.maximum.reduce([
        (daily["high"] - daily["low"]).to_numpy(),
        (daily["high"] - prev_close).abs().to_numpy(),
        (daily["low"] - prev_close).abs().to_numpy(),
    ])
    daily["daily_atr_10"] = pd.Series(tr).rolling(10).mean()
    daily["daily_atr_10_bps"] = daily["daily_atr_10"] / daily["close"] * 1e4
    daily["trend_ret_10d"] = np.log(daily["close"] / daily["close"].shift(10)) * 1e4
    return daily[["date", "A3_skew_spec", "daily_atr_spec", "trend_ret_M_spec",
                  "daily_atr_10_bps", "trend_ret_10d"]]


def rolling_pct_rank(series: pd.Series, window: int) -> pd.Series:
    def rank_last(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        past = x.iloc[:-1]
        return (past <= current).sum() / len(past)
    return series.rolling(window, min_periods=10).apply(rank_last, raw=False)


def active_day_set(df: pd.DataFrame) -> set:
    days: set = set()
    for _, g in df.groupby("contract"):
        for d in g["event_date"]:
            ts = pd.Timestamp(d)
            if ts.weekday() < 5:
                days.add(ts.date())
    return days


def cost_oneway_bps(spec, price: float, lots: float) -> float:
    ccy = spec.total_commission(price=price, lots=1) + spec.slippage(lots=1)
    return ccy / (price * spec.size) * 10000.0


def simulate_contract(contract: str, g: pd.DataFrame) -> list[dict]:
    spec = CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    csv_path = CSV_DIR / f"{contract}.tqsdk.5m.csv"
    if not csv_path.exists():
        return []
    bars = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)
    if bars.empty:
        return []
    rows: list[dict] = []
    for _, ev in g.iterrows():
        direction = ev["direction"]
        sign = 1 if direction == "long" else -1
        K = K_L_SL if direction == "long" else K_S_SL
        H = H_L if direction == "long" else H_S
        entry_price = float(ev["close_t"])
        atr_bps = float(ev["entry_atr_bps"])
        if entry_price <= 0 or atr_bps <= 0:
            continue
        atr_price = entry_price * atr_bps / 10000.0
        stop_price = entry_price - sign * K * atr_price
        stop_dist_frac = K * atr_bps / 10000.0
        notional_frac = RISK_PER_TRADE / stop_dist_frac
        qty_raw = notional_frac * EQUITY_INIT / (entry_price * spec.size)
        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        future = bars.iloc[idx: idx + H * 12]
        if len(future) == 0:
            continue
        exit_price = np.nan
        exit_reason = "TIME"
        exit_bar = future.iloc[-1]["datetime"]
        for _, bar in future.iterrows():
            if sign == 1 and bar["low"] <= stop_price:
                exit_price = stop_price; exit_reason = "SL"
                exit_bar = bar["datetime"]; break
            if sign == -1 and bar["high"] >= stop_price:
                exit_price = stop_price; exit_reason = "SL"
                exit_bar = bar["datetime"]; break
        if np.isnan(exit_price):
            exit_price = float(future.iloc[-1]["close"])
            exit_bar = future.iloc[-1]["datetime"]
        cost_entry = cost_oneway_bps(spec, entry_price, qty_raw)
        cost_exit = cost_oneway_bps(spec, exit_price, qty_raw)
        gross_ret = sign * (exit_price - entry_price) / entry_price
        pnl_gross_bps = gross_ret * 10000.0
        pnl_net_bps = pnl_gross_bps - cost_entry - cost_exit
        notional_ccy = qty_raw * entry_price * spec.size
        pnl_net_ccy = pnl_net_bps / 10000.0 * notional_ccy
        sym = (extract_contract_prefix(contract) or "").lower()
        rows.append({
            "contract": contract, "symbol": sym,
            "symbol_type": SYMBOL_TYPE.get(sym, "C"),
            "entry_bar": ev["event_time"], "exit_bar": exit_bar,
            "direction": int(sign), "tier": ev["tier"],
            "entry_price": entry_price, "exit_price": exit_price,
            "exit_reason": exit_reason, "entry_atr_bps": atr_bps,
            "qty_raw": qty_raw, "qty_actual_raw_cap": qty_raw,
            "pnl_gross_bps": pnl_gross_bps,
            "cost_entry_bps": cost_entry, "cost_exit_bps": cost_exit,
            "pnl_net_bps": pnl_net_bps,
            "pnl_net_ccy_raw_no_cap": pnl_net_ccy,
            "_notional_frac": notional_frac,
            "_entry_date": ev["event_time"].date(),
            "_exit_date": pd.Timestamp(exit_bar).date(),
        })
    return rows


def compress(trades: pd.DataFrame, max_notional: float) -> pd.DataFrame:
    daily = trades.groupby("_entry_date")["_notional_frac"].sum()
    scale = (max_notional / daily).clip(upper=1.0)
    t = trades.copy()
    t["cap_scale"] = t["_entry_date"].map(scale).fillna(1.0)
    t["qty_actual"] = t["qty_raw"] * t["cap_scale"]
    t["pnl_net_ccy"] = t["pnl_net_ccy_raw_no_cap"] * t["cap_scale"]
    return t


def assign_equity(trades: pd.DataFrame) -> pd.DataFrame:
    t = trades.sort_values("exit_bar").reset_index(drop=True)
    eq = EQUITY_INIT
    befs, afts = [], []
    for pnl in t["pnl_net_ccy"]:
        befs.append(eq); eq += pnl; afts.append(eq)
    t["equity_before"] = befs; t["equity_after"] = afts
    return t


def run_research_pipeline() -> tuple[pd.DataFrame, pd.DataFrame, dict, set]:
    print("[R] 步骤 1/4 · 从 5m CSV 构建事件时间线 ...")
    symbols = discover_symbols()
    print(f"    发现 {len(symbols)} 合约的 5m 数据")
    all_events = []
    skipped = 0
    for i, sym in enumerate(symbols):
        if (i + 1) % 50 == 0:
            print(f"    [{i+1}/{len(symbols)}] ...")
        tick = get_tick(sym)
        try:
            ev = build_events(sym, tick)
            daily = build_daily_features(sym)
            if ev.empty or daily.empty:
                skipped += 1
                continue
            ev = ev.merge(daily, left_on="event_date", right_on="date", how="left")
            all_events.append(ev)
        except Exception:
            skipped += 1
            continue
    df = pd.concat(all_events, ignore_index=True)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"])
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    print(f"    有效合约: {df['contract'].nunique()} / 扫描: {len(symbols)} (跳过 {skipped})  事件行: {len(df)}")
    df["signed_skew"] = -df["A3_skew"]
    df["signed_skew_rank_roll"] = df.groupby("contract")["signed_skew"].transform(
        lambda s: rolling_pct_rank(s, 100)
    )
    for feat_col, roll_col in [("daily_atr_10_bps", "atr_rank_roll"),
                                 ("trend_ret_10d", "trend_rank_roll")]:
        seg_list = []
        for c, g in df.groupby("contract"):
            daily_g = g.drop_duplicates("event_date").sort_values("event_date").copy()
            daily_g[roll_col] = rolling_pct_rank(daily_g[feat_col], ROLLING_DAYS)
            seg_list.append(daily_g[["contract", "event_date", roll_col]])
        seg_map = pd.concat(seg_list, ignore_index=True)
        df = df.merge(seg_map, on=["contract", "event_date"], how="left")
    keep = np.zeros(len(df), dtype=bool)
    for c in df["contract"].unique():
        subset = df[df["contract"] == c].sort_values("event_time")
        dates = sorted(subset["event_date"].unique())
        if len(dates) < WARMUP_DAYS:
            continue
        wend = dates[WARMUP_DAYS - 1]
        keep |= (df["contract"] == c) & (df["event_date"] > wend)
    df = df[keep].reset_index(drop=True)
    df = df.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
    print(f"    warmup后事件: {len(df)} | 合约: {df['contract'].nunique()}")
    active_days = active_day_set(df)
    print("[R] 步骤 2/4 · 分类（新版 MAD fix）...")
    config = ClassifierConfig()
    result = evaluate_dataset(
        df, config, a3_skew_col="A3_skew_spec", atr_col="daily_atr_spec",
        trend_col="trend_ret_M_spec",
    )
    ev = result.dropna(subset=["tier"]).copy()
    ev = ev.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = ev.groupby("contract")["event_time"].shift(1)
    ev = ev[(prev.isna()) | ((ev["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))]
    ev["entry_atr_bps"] = ev["daily_atr_spec"] / ev["close_t"] * 10000.0
    ev = ev.reset_index(drop=True)
    print(f"    分类事件: {len(ev)} | 合约: {ev['contract'].nunique()} | "
          f"多: {(ev['direction']=='long').sum()} 空: {(ev['direction']=='short').sum()}")
    tier_dist = ev.groupby("tier").size()
    for t, n in tier_dist.items():
        print(f"      {t:<25} {n:>6}")
    print(f"[R] 步骤 3/4 · 逐合约 5m 精确模拟 (Cap={CAP}) ...")
    all_rows = []
    for c, g in ev.groupby("contract"):
        all_rows.extend(simulate_contract(c, g))
    raw = pd.DataFrame(all_rows)
    if raw.empty:
        raise RuntimeError("研究侧无模拟结果")
    trades_no_cap = raw.copy()
    trades_no_cap["qty_actual"] = raw["qty_raw"]
    trades_no_cap["pnl_net_ccy"] = raw["pnl_net_ccy_raw_no_cap"]
    trades_no_cap["cap_scale"] = 1.0
    trades_no_cap = assign_equity(trades_no_cap)
    trades_cap = compress(raw, CAP)
    trades_cap = assign_equity(trades_cap)
    print(f"    原始 {len(raw)} 笔 | SL: {(raw['exit_reason']=='SL').sum()} | "
          f"TIME: {(raw['exit_reason']=='TIME').sum()}")
    print("[R] 步骤 4/4 · 指标 (CAP 压缩口径) ...")
    m = compute_metrics(trades_cap, active_days)
    m["n_contracts"] = int(ev["contract"].nunique())
    m["n_active_days"] = len(active_days)
    m["n_classified_events"] = len(ev)
    print(f"    CAP口径指标: ann={m['ann_ret']:.2%} sharpe={m['sharpe']:.2f} "
          f"win={m['win_rate']:.1%} trades={m['n_trades']}")
    return ev, trades_cap, m, active_days, trades_no_cap


# ==============================================================================
# Section B · 指标
# ==============================================================================
def compute_metrics(trades: pd.DataFrame, active_days=None) -> dict:
    t = trades.copy()
    t["day"] = t["_exit_date"] if "_exit_date" in t.columns else pd.to_datetime(t["exit_bar"]).dt.date
    daily_pnl = t.groupby("day")["pnl_net_ccy"].sum() if "pnl_net_ccy" in t.columns else t.groupby("day")["net_pnl_ccy"].sum()
    ret = daily_pnl / EQUITY_INIT
    if len(ret) == 0:
        return {"ann_ret": 0.0, "sharpe": 0.0, "max_dd": 0.0, "n_trades": len(trades),
                "win_rate": 0.0, "total_net_pnl": 0.0, "total_cost": 0.0}
    if active_days:
        idx = sorted(active_days)
        ret = ret.reindex(idx, fill_value=0.0)
    ann = ret.mean() * ANNUAL_FACTOR
    std = ret.std() * np.sqrt(ANNUAL_FACTOR)
    sharpe = ann / std if std > 0 else 0.0
    cum = ret.cumsum()
    dd = float((cum - cum.cummax()).min())
    wr_key = "pnl_net_ccy" if "pnl_net_ccy" in t.columns else "net_pnl_ccy"
    wr = float((t[wr_key] > 0).mean()) if len(t) else 0.0
    total_pnl = float(t[wr_key].sum())
    if "commission_ccy" in t.columns and "slippage_ccy" in t.columns:
        total_cost = float(t["commission_ccy"].sum() + t["slippage_ccy"].sum())
    else:
        total_cost = 0.0
    return {"ann_ret": float(ann), "sharpe": float(sharpe), "max_dd": dd,
            "n_trades": int(len(trades)), "win_rate": wr,
            "total_net_pnl": total_pnl, "total_cost": total_cost}


# ==============================================================================
# Section C · 工程侧：从 DB 读 run_id=15 并 FIFO 配对
# ==============================================================================
@dataclass
class Pending:
    open_row: dict
    qty_left: float


def _tier_from_reason(reason: str) -> str | None:
    if reason.startswith("entry_"):
        return reason[len("entry_"):]
    return None


def load_engineering_trades(run_id: int = ENG_RUN_ID) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    返回 (backtests_agg, paired_round_trips)
    paired_round_trips 每一行是研究侧 trades 的"镜像"结构，含：
      contract, entry_bar, exit_bar, direction, tier, entry_price, exit_price,
      exit_reason, qty_actual, pnl_gross_ccy, commission_ccy, slippage_ccy,
      net_pnl_ccy, notional_frac, cap_scale
    """
    print(f"[E] 读取工程侧 run_id={run_id} ...")
    if not ENG_DB.exists():
        raise FileNotFoundError(f"工程侧 DB 不存在: {ENG_DB}")
    conn = sqlite3.connect(ENG_DB)
    # backtests 聚合（和工程侧报表口径一致）
    bt = pd.read_sql_query(
        "SELECT id, symbol, run_id, status, total_trades, win_trades, loss_trades, "
        "total_net_pnl, total_commission, total_slippage, annual_return, sharpe_ratio, "
        "max_drawdown, initial_capital, end_balance, start_date, end_date "
        "FROM backtests WHERE run_id=?",
        conn, params=(run_id,),
    )
    print(f"    backtests 行数: {len(bt)} | 合约: {bt['symbol'].nunique()}")
    print(f"    净盈亏合计: {bt['total_net_pnl'].sum():,.2f} | "
          f"手续费合计: {bt['total_commission'].sum():,.2f} | "
          f"滑点合计: {bt['total_slippage'].sum():,.2f}")
    # backtest_trades 逐条
    tr = pd.read_sql_query(
        "SELECT bt.*, b.symbol AS b_symbol FROM backtest_trades bt "
        "JOIN backtests b ON b.id=bt.backtest_id WHERE b.run_id=? "
        "ORDER BY b.symbol, bt.datetime ASC, bt.id ASC",
        conn, params=(run_id,),
    )
    conn.close()
    print(f"    trades 原始行: {len(tr)}")
    # FIFO 配对
    pending: dict[tuple[str, str], list[Pending]] = defaultdict(list)
    paired: list[dict] = []
    unmatched_open = 0
    unmatched_close = 0
    for _, row in tr.iterrows():
        sym = row["b_symbol"]
        # direction 保持 long/short 字符串
        side = row["direction"]
        offset = row["offset"]
        if offset == "open":
            pending[(sym, side)].append(Pending(open_row=row.to_dict(), qty_left=float(row["quantity"])))
            continue
        # close
        opp = "long" if side == "short" else "short"
        key = (sym, opp)
        qty_to_close = float(row["quantity"])
        while qty_to_close > 1e-9 and pending.get(key):
            p = pending[key][0]
            matched = min(qty_to_close, p.qty_left)
            ratio = matched / float(p.open_row["quantity"]) if float(p.open_row["quantity"]) > 0 else 1.0
            close_row = row.to_dict()
            # 配对比例下的各字段
            direction_int = 1 if p.open_row["direction"] == "long" else -1
            entry_price = float(p.open_row["open_price"])
            exit_price = float(close_row["close_price"])
            qty_actual = matched
            gross_ccy = direction_int * (exit_price - entry_price) * qty_actual * _contract_multiplier(sym, entry_price)
            comm_open = float(p.open_row["commission"]) * ratio
            comm_close = float(close_row["commission"]) * (matched / qty_to_close if qty_to_close > 0 else 1.0)
            # 简化：comm/slippage 按 quantity 线性分配（这里通常一次性 close = 一次性 open 的 qty）
            slippage_open = 0.0  # 工程侧 commission 已含？ slippage 列 trades 没暴露 → 用 backtests 级汇总
            # tier & notional_frac 从 decision_payload_json 读
            payload = json.loads(p.open_row["decision_payload_json"] or "{}")
            strat_diag = payload.get("diagnostics", {}).get("strategy", {}) if isinstance(payload, dict) else {}
            tier = strat_diag.get("tier") or _tier_from_reason(p.open_row["reason"])
            notional_frac = strat_diag.get("notional_frac")
            paired.append({
                "contract": sym,
                "symbol": (extract_contract_prefix(sym) or "").lower(),
                "entry_bar": pd.Timestamp(p.open_row["datetime"]),
                "exit_bar": pd.Timestamp(close_row["datetime"]),
                "direction": direction_int,
                "tier": tier,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_reason": close_row["reason"],
                "qty_actual": qty_actual,
                "gross_pnl_ccy": gross_ccy,
                "commission_ccy": comm_open + comm_close,
                "slippage_ccy": 0.0,
                "net_pnl_ccy": gross_ccy - (comm_open + comm_close),
                "notional_frac": notional_frac,
                "_entry_date": pd.Timestamp(p.open_row["datetime"]).date(),
                "_exit_date": pd.Timestamp(close_row["datetime"]).date(),
                "open_id": p.open_row["id"],
                "close_id": close_row["id"],
            })
            p.qty_left -= matched
            qty_to_close -= matched
            if p.qty_left <= 1e-9:
                pending[key].pop(0)
        if qty_to_close > 1e-9:
            unmatched_close += 1
    for k, lst in pending.items():
        for p in lst:
            if p.qty_left > 1e-9:
                unmatched_open += 1
    pdf = pd.DataFrame(paired)
    # 把 backtests 级总滑点分配到各合约每笔
    slip_per_contract = bt.set_index("symbol")["total_slippage"].to_dict()
    tr_per_contract = pdf.groupby("contract").size().to_dict()
    pdf["slippage_ccy"] = pdf.apply(
        lambda r: (slip_per_contract.get(r["contract"], 0.0) / tr_per_contract[r["contract"]])
        if tr_per_contract.get(r["contract"], 0) > 0 else 0.0, axis=1,
    )
    pdf["net_pnl_ccy"] = pdf["gross_pnl_ccy"] - pdf["commission_ccy"] - pdf["slippage_ccy"]
    # net_pnl_ccy 用 backtests 级汇总校准
    net_agg = pdf.groupby("contract")["net_pnl_ccy"].sum().to_dict()
    target_net = bt.set_index("symbol")["total_net_pnl"].to_dict()
    cal_factor = {}
    for c in pdf["contract"].unique():
        src = net_agg.get(c, 0.0)
        tgt = target_net.get(c, 0.0)
        cal_factor[c] = (tgt / src) if abs(src) > 1e-9 else 1.0
    # 保留原值不强行缩放，避免误判，只额外列个 bt_total_net_pnl 供参考
    pdf["contract_target_net_pnl"] = pdf["contract"].map(target_net)
    print(f"    配对后 round-trip: {len(pdf)} 笔 | "
          f"未配对 open: {unmatched_open} | 未配对 close: {unmatched_close}")
    print(f"    方向分布  多: {(pdf['direction']==1).sum()}  空: {(pdf['direction']==-1).sum()}")
    exit_dist = pdf.groupby("exit_reason").size().sort_values(ascending=False)
    for r, n in exit_dist.items():
        print(f"      exit_reason {r:<20} count={n}")
    return bt, pdf


def _contract_multiplier(symbol: str, price: float) -> float:
    """工程侧 quantity 单位：手。这里要转换成"每手合约张数/单位"。
    但 vnpy backtest 的 pnl 已算好（pnl 列），这里采用保守估计：
    如果有 CONTRACT_SPECS，则取 CONTRACT_SPECS.size（每张合约乘数）；
    否则用 1（后续会用 backtest 级合计作为校准参考）。
    实际上工程侧 FIFO 配对的净盈亏 = 配对 net 的 gross - commission/slippage；
    我们直接用 backtest 级汇总，交易级的 gross 绝对值允许偏差，用符号判定即可。
    """
    spec = CONTRACT_SPECS.get_symbol(symbol)
    return spec.size if spec is not None else 1.0


# ==============================================================================
# Section D · 匹配 & 分层对比
# ==============================================================================
MATCH_ENTRY_WINDOW = pd.Timedelta(minutes=10)


def match_trades(r_trades: pd.DataFrame, e_trades: pd.DataFrame) -> pd.DataFrame:
    """按 (contract, direction, 入场时间±10min) 贪心匹配研究侧到工程侧。"""
    print(f"\n[Match] 贪心匹配 (window={MATCH_ENTRY_WINDOW}) ...")
    r = r_trades.sort_values("entry_bar").reset_index(drop=True).copy()
    e = e_trades.sort_values("entry_bar").reset_index(drop=True).copy()
    r["_r_idx"] = r.index
    e["_e_idx"] = e.index
    used_e: set[int] = set()
    matches = []
    for _, rr in r.iterrows():
        lo = rr["entry_bar"] - MATCH_ENTRY_WINDOW
        hi = rr["entry_bar"] + MATCH_ENTRY_WINDOW
        # 方向相同，合约相同，时间在窗口内
        cands = e[(e["contract"] == rr["contract"]) &
                   (e["direction"] == rr["direction"]) &
                   (e["entry_bar"] >= lo) & (e["entry_bar"] <= hi) &
                   (~e["_e_idx"].isin(used_e))].copy()
        if cands.empty:
            matches.append({"r_idx": rr["_r_idx"], "e_idx": None,
                            "match_type": "research_only"})
            continue
        cands["dt_diff"] = (cands["entry_bar"] - rr["entry_bar"]).abs()
        cands = cands.sort_values(["dt_diff", "entry_bar"])
        best = cands.iloc[0]
        used_e.add(int(best["_e_idx"]))
        matches.append({"r_idx": int(rr["_r_idx"]), "e_idx": int(best["_e_idx"]),
                        "entry_dt_diff_sec": int(best["dt_diff"].total_seconds()),
                        "match_type": "matched"})
    for ei in e[~e["_e_idx"].isin(used_e)]["_e_idx"]:
        matches.append({"r_idx": None, "e_idx": int(ei), "match_type": "engine_only"})
    mdf = pd.DataFrame(matches)
    print(f"    matched={(mdf['match_type']=='matched').sum()}  "
          f"research_only={(mdf['match_type']=='research_only').sum()}  "
          f"engine_only={(mdf['match_type']=='engine_only').sum()}")
    return mdf


def build_pair_detail(r_trades: pd.DataFrame, e_trades: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    r = r_trades.copy().add_prefix("r_")
    e = e_trades.copy().add_prefix("e_")
    m2 = m.merge(r, left_on="r_idx", right_index=True, how="left") \
         .merge(e, left_on="e_idx", right_index=True, how="left")
    # 相对差
    if "r_entry_price" in m2.columns and "e_entry_price" in m2.columns:
        with np.errstate(divide="ignore", invalid="ignore"):
            m2["entry_price_reldiff"] = np.where(
                m2["r_entry_price"].fillna(0) != 0,
                (m2["e_entry_price"] - m2["r_entry_price"]) / m2["r_entry_price"],
                np.nan,
            )
            m2["exit_price_reldiff"] = np.where(
                m2["r_exit_price"].fillna(0) != 0,
                (m2["e_exit_price"] - m2["r_exit_price"]) / m2["r_exit_price"],
                np.nan,
            )
    return m2


def print_summary_block(title: str, r_metrics: dict, e_metrics: dict,
                        r_ev_count: int, r_n_contracts: int,
                        e_bt: pd.DataFrame | None = None) -> None:
    w = 22
    print()
    print("=" * 88)
    print(f"  {title}")
    print("=" * 88)
    def fmtp(v): return f"{v*100:>8.2f}%" if isinstance(v, float) else f"{str(v):>8}"
    def fmt(v, spec): return format(v, spec)
    rows = [
        ("分类事件数",      f"{r_ev_count:,}", "—",
         f"—"),
        ("回测合约数",      f"{r_n_contracts:,}",
         f"{e_bt['symbol'].nunique():,}" if e_bt is not None else "—",
         f"—"),
        ("交易笔数",        f"{r_metrics['n_trades']:,}",
         f"{e_metrics['n_trades']:,}",
         f"{int(e_metrics['n_trades'])-int(r_metrics['n_trades']):+,}"),
        ("胜率",            f"{r_metrics['win_rate']:.1%}",
         f"{e_metrics['win_rate']:.1%}",
         f"{(e_metrics['win_rate']-r_metrics['win_rate'])*100:+.1f}pp"),
        ("总净盈亏 (¥)",    f"{r_metrics['total_net_pnl']:>14,.2f}",
         f"{e_metrics['total_net_pnl']:>14,.2f}",
         f"{(e_metrics['total_net_pnl']-r_metrics['total_net_pnl']):>14,.2f}"),
        ("总成本 (¥)",      f"{r_metrics['total_cost']:>14,.2f}" if 'total_cost' in r_metrics else "—",
         f"{e_metrics['total_cost']:>14,.2f}" if 'total_cost' in e_metrics else "—",
         "—"),
        ("年化收益",        f"{r_metrics['ann_ret']:.2%}",
         f"{e_metrics['ann_ret']:.2%}",
         f"{(e_metrics['ann_ret']-r_metrics['ann_ret'])*100:+.2f}pp"),
        ("夏普",            f"{r_metrics['sharpe']:.2f}",
         f"{e_metrics['sharpe']:.2f}",
         f"{(e_metrics['sharpe']-r_metrics['sharpe']):+.2f}"),
        ("MaxDD",           f"{r_metrics['max_dd']:.2%}",
         f"{e_metrics['max_dd']:.2%}",
         f"{(e_metrics['max_dd']-r_metrics['max_dd'])*100:+.2f}pp"),
    ]
    hdr = f"  {'指标':<18}{'研究侧 (R)':>{w}}{'工程侧 (E)':>{w}}{'E-R':>{w}}"
    print(hdr)
    print("  " + "-" * (18 + w * 3))
    for name, rv, ev, dv in rows:
        print(f"  {name:<18}{rv:>{w}}{ev:>{w}}{dv:>{w}}")


def print_signal_tier_diff(r_ev: pd.DataFrame, e_pairs: pd.DataFrame) -> None:
    print("\n" + "-" * 88)
    print("  Tier / 方向 分布对比")
    print("-" * 88)
    r_tier = (r_ev.groupby(["direction", "tier"]).size().rename("R_cnt")
              .reset_index().assign(direction=lambda d: d["direction"].map({"long":1, "short":-1})))
    e_tier = e_pairs.groupby(["direction", "tier"]).size().rename("E_cnt").reset_index()
    comp = r_tier.merge(e_tier, on=["direction", "tier"], how="outer").fillna(0)
    comp["diff"] = comp["E_cnt"].astype(int) - comp["R_cnt"].astype(int)
    comp = comp.sort_values(["direction", "tier"]).reset_index(drop=True)
    print(f"  {'Dir':<4}{'Tier':<25}{'R_cnt':>8}{'E_cnt':>8}{'E-R':>8}")
    for _, r in comp.iterrows():
        dmap = {1: " L ", -1: " S "}
        print(f"  {dmap.get(r['direction'], ' ? '):<4}{str(r['tier']):<25}"
              f"{int(r['R_cnt']):>8,}{int(r['E_cnt']):>8,}{int(r['diff']):>+8,}")


def print_match_breakdown(detail: pd.DataFrame, r_trades: pd.DataFrame, e_trades: pd.DataFrame) -> None:
    print("\n" + "-" * 88)
    print("  匹配分类拆解")
    print("-" * 88)
    matched = detail[detail["match_type"] == "matched"]
    r_only = detail[detail["match_type"] == "research_only"]
    e_only = detail[detail["match_type"] == "engine_only"]
    print(f"  Matched           N = {len(matched):,}")
    if len(matched):
        ep = matched["entry_price_reldiff"].dropna()
        xp = matched["exit_price_reldiff"].dropna()
        dt = matched["entry_dt_diff_sec"].dropna().astype(float)
        print(f"     入场价相对差  median={ep.median():.4%}  mean={ep.mean():.4%}  "
              f"abs_max={ep.abs().max():.4%}")
        print(f"     出场价相对差  median={xp.median():.4%}  mean={xp.mean():.4%}  "
              f"abs_max={xp.abs().max():.4%}")
        print(f"     入场时间差(s) median={dt.median():.0f}  mean={dt.mean():.0f}  "
              f"max={dt.max():.0f}")
        # 匹配对的 pnl 对比（逐笔）
        r_pnl = matched["r_pnl_net_ccy"].dropna()
        e_pnl = matched["e_net_pnl_ccy"].dropna()
        print(f"     匹配对净盈亏  R合计={r_pnl.sum():>14,.2f}  "
              f"E合计={e_pnl.sum():>14,.2f}  Δ={e_pnl.sum()-r_pnl.sum():>14,.2f}")
        # 匹配对 exit_reason 一致率
        same_reason = (matched["r_exit_reason"] == matched["e_exit_reason"]).sum()
        print(f"     exit_reason 一致率 = {same_reason}/{len(matched)} = {same_reason/len(matched):.1%}")
    print(f"  Research-only     N = {len(r_only):,}")
    if len(r_only):
        r_only_tiers = r_only.groupby("r_tier").size().sort_values(ascending=False).head(8)
        r_only_direction = r_only.groupby("r_direction").size()
        print(f"     Tier Top8: " + ", ".join(f"{k}={int(v)}" for k, v in r_only_tiers.items()))
        dmap_r = {1.0: "L", -1.0: "S"}
        print(f"     方向分布: " + ", ".join(f"{dmap_r.get(k,'?')}={int(v)}" for k, v in r_only_direction.items()))
    print(f"  Engine-only       N = {len(e_only):,}")
    if len(e_only):
        e_only_tiers = e_only.groupby("e_tier").size().sort_values(ascending=False).head(8)
        e_only_direction = e_only.groupby("e_direction").size()
        print(f"     Tier Top8: " + ", ".join(f"{k}={int(v)}" for k, v in e_only_tiers.items()))
        dmap_e = {1.0: "L", -1.0: "S"}
        print(f"     方向分布: " + ", ".join(f"{dmap_e.get(k,'?')}={int(v)}" for k, v in e_only_direction.items()))


def print_per_contract_diff(r_trades: pd.DataFrame, e_pairs: pd.DataFrame,
                            e_bt: pd.DataFrame) -> None:
    print("\n" + "-" * 88)
    print("  逐合约 对比（净盈亏 Top10 赚钱/亏钱 + 交易笔数差异 Top10）")
    print("-" * 88)
    r_agg = r_trades.groupby("contract").agg(
        R_trades=("qty_raw", "size"),
        R_net_pnl=("pnl_net_ccy", "sum"),
    ).reset_index()
    e_agg = e_pairs.groupby("contract").agg(
        E_trades=("qty_actual", "size"),
        E_net_pnl=("net_pnl_ccy", "sum"),
    ).reset_index()
    bt_agg = e_bt.groupby("symbol").agg(E_bt_net=("total_net_pnl", "sum")).reset_index()
    comp = r_agg.merge(e_agg, on="contract", how="outer") \
                .merge(bt_agg, left_on="contract", right_on="symbol", how="left") \
                .fillna(0)
    comp["trades_diff"] = comp["E_trades"].astype(int) - comp["R_trades"].astype(int)
    comp["pnl_diff"] = comp["E_net_pnl"] - comp["R_net_pnl"]
    comp = comp.drop(columns=["symbol"], errors="ignore")
    print(f"\n  [净盈亏 E-R Top10 正差异(工程更赚)]")
    for _, r in comp.sort_values("pnl_diff", ascending=False).head(10).iterrows():
        print(f"    {r['contract']:<18} "
              f"R={r['R_net_pnl']:>12,.2f}  E(配)={r['E_net_pnl']:>12,.2f}  "
              f"E(BT)={r['E_bt_net']:>12,.2f}  "
              f"Δ={r['pnl_diff']:>12,.2f}  "
              f"Rtr={int(r['R_trades']):>3} Etr={int(r['E_trades']):>3} Δtr={int(r['trades_diff']):>+4}")
    print(f"\n  [净盈亏 E-R Top10 负差异(工程更亏)]")
    for _, r in comp.sort_values("pnl_diff", ascending=True).head(10).iterrows():
        print(f"    {r['contract']:<18} "
              f"R={r['R_net_pnl']:>12,.2f}  E(配)={r['E_net_pnl']:>12,.2f}  "
              f"E(BT)={r['E_bt_net']:>12,.2f}  "
              f"Δ={r['pnl_diff']:>12,.2f}  "
              f"Rtr={int(r['R_trades']):>3} Etr={int(r['E_trades']):>3} Δtr={int(r['trades_diff']):>+4}")
    print(f"\n  [交易笔数差异 Top10（信号覆盖率差异的直接表现）]")
    comp["abs_trade_diff"] = comp["trades_diff"].abs()
    for _, r in comp.sort_values("abs_trade_diff", ascending=False).head(10).iterrows():
        print(f"    {r['contract']:<18}  "
              f"Rtr={int(r['R_trades']):>3}  Etr={int(r['E_trades']):>3}  "
              f"Δtr={int(r['trades_diff']):>+4}  "
              f"R_pnl={r['R_net_pnl']:>12,.2f}  E_pnl={r['E_net_pnl']:>12,.2f}")
    comp.to_parquet(OUT_DIR / "per_contract_compare.parquet", index=False)


def save_outputs(r_ev: pd.DataFrame, r_trades: pd.DataFrame,
                 e_pairs: pd.DataFrame, e_bt: pd.DataFrame,
                 match_detail: pd.DataFrame, metrics: dict) -> None:
    r_ev.to_parquet(OUT_DIR / "research_events.parquet", index=False)
    r_trades.to_parquet(OUT_DIR / "research_trades.parquet", index=False)
    e_pairs.to_parquet(OUT_DIR / "engine_paired_trades.parquet", index=False)
    e_bt.to_parquet(OUT_DIR / "engine_backtests.parquet", index=False)
    match_detail.to_parquet(OUT_DIR / "matched_pair_detail.parquet", index=False)
    (OUT_DIR / "summary.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(f"\n✓ 所有落盘文件已保存到: {OUT_DIR}")


# ==============================================================================
# Main
# ==============================================================================
def main() -> None:
    t0 = time.time()
    print("=" * 88)
    print("  VA 非对称复合策略 · 研究侧复现 vs 工程侧 run_id=15 · 精细分层对比")
    print("=" * 88)
    # --- 研究侧 ---
    r_ev, r_trades_cap, r_m_cap, active_days, r_trades_nocap = run_research_pipeline()
    # --- 工程侧 ---
    e_bt, e_pairs = load_engineering_trades(ENG_RUN_ID)
    e_metrics = compute_metrics(e_pairs, active_days)
    # --- 匹配 ---
    m = match_trades(r_trades_cap, e_pairs)
    detail = build_pair_detail(r_trades_cap, e_pairs, m)
    # --- 打印总览 ---
    r_ev_count = len(r_ev)
    r_n_contracts = int(r_ev["contract"].nunique())
    print_summary_block("L1 · 总览层（交易 & 聚合指标）", r_m_cap, e_metrics,
                        r_ev_count, r_n_contracts, e_bt)
    # 研究侧 no-cap vs cap 对比（解释 CAP=4.0 带来的压缩影响）
    r_m_nocap = compute_metrics(r_trades_nocap, active_days)
    print_summary_block(
        "L2 · 研究侧内部对比（CAP=4.0 压缩效应）",
        r_m_nocap, r_m_cap, r_ev_count, r_n_contracts,
    )
    # 信号 tier 对比
    print_signal_tier_diff(r_ev, e_pairs)
    # 匹配拆解
    print_match_breakdown(detail, r_trades_cap, e_pairs)
    # 逐合约
    print_per_contract_diff(r_trades_cap, e_pairs, e_bt)
    # --- 汇总 JSON ---
    summary = {
        "research_cap": r_m_cap,
        "research_no_cap": r_m_nocap,
        "engine_pairs": e_metrics,
        "engine_bt_agg": {
            "n_backtests": int(len(e_bt)),
            "sum_total_net_pnl": float(e_bt["total_net_pnl"].sum()),
            "sum_commission": float(e_bt["total_commission"].sum()),
            "sum_slippage": float(e_bt["total_slippage"].sum()),
            "sum_total_trades": int(e_bt["total_trades"].sum()),
        },
        "match_stats": {
            "matched": int((m["match_type"] == "matched").sum()),
            "research_only": int((m["match_type"] == "research_only").sum()),
            "engine_only": int((m["match_type"] == "engine_only").sum()),
        },
    }
    save_outputs(r_ev, r_trades_cap, e_pairs, e_bt, detail, summary)
    print(f"\n总耗时: {(time.time() - t0)/60:.1f} 分钟")


if __name__ == "__main__":
    main()
