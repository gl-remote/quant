#!/usr/bin/env python3
"""
va-asymmetry · 研究侧全量回测复现（当前代码基线）

目的：使用当前 repo 代码（poc_va.py / contract_specs 等）从 5m CSV 出发，
按研究侧原始参数（K_L=1.0, K_S=2.5, ATR=SMA(10), Cap=4.0, 5m 粒度）跑
143 合约全量回测，与归档 metrics_new.json 对比，验证：

    "当前代码是否仍能复现研究侧宣称的年化 63.44% / 夏普 3.47 / 613 笔？"

若能复现 → 15× 差距完全来自工程侧策略实现路径（Step 1-4 逐项对齐）。
若不能复现 → poc_va / 数据链发生了退化，先修数据链。

管道（与归档脚本完全一致，只保留"新版 MAD fix"单轨）：
  5m CSVs → build_events → build_daily_features(poc_va)
         → evaluate_dataset → simulate → compress → metrics

来源：docs/archive/strategy-research/2026/07/2026-07-13-va-asymmetry-engineering-fix/
      scripts/va_mad_fix_full_backtest.py 精简版

运行:
  uv run python docs/workbench/va-asymmetry-composite/scripts/reproduce_research_side.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]  # scripts/ → va-asymmetry-composite/ → workbench/ → docs/ → repo
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

# =====================================================================
# 配置（与研究侧 va_mad_fix_full_backtest.py 完全一致）
# =====================================================================
CSV_DIR = REPO / "project_data/market_data/csv"
OUT_DIR = REPO / "docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
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


# =====================================================================
# Step 1: 从 5m CSV 构建事件时间线
# =====================================================================
def get_tick(symbol: str) -> float:
    _, contract = symbol.split(".")
    prefix = "".join(c for c in contract if c.isalpha())
    return TICK_MAP.get(prefix, 1.0)


def discover_symbols() -> list[str]:
    symbols = []
    for p in sorted(CSV_DIR.glob("*.tqsdk.5m.csv")):
        symbols.append(p.name.replace(".tqsdk.5m.csv", ""))
    return symbols


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


# =====================================================================
# Step 2: 模拟引擎
# =====================================================================
def cost_oneway_bps(spec, price: float, lots: int = 1) -> float:
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
            "qty_raw": qty_raw, "qty_actual": qty_raw,
            "pnl_gross_bps": pnl_gross_bps,
            "cost_entry_bps": cost_entry, "cost_exit_bps": cost_exit,
            "pnl_net_bps": pnl_net_bps, "pnl_net_ccy": pnl_net_ccy,
            "_notional_frac": notional_frac,
            "_entry_date": ev["event_time"].date(),
            "_exit_date": pd.Timestamp(exit_bar).date(),
        })
    return rows


def compress(trades: pd.DataFrame, max_notional: float) -> pd.DataFrame:
    daily = trades.groupby("_entry_date")["_notional_frac"].sum()
    scale = (max_notional / daily).clip(upper=1.0)
    t = trades.copy()
    t["scale"] = t["_entry_date"].map(scale).fillna(1.0)
    t["qty_actual"] = t["qty_raw"] * t["scale"]
    t["pnl_net_ccy"] = t["pnl_net_ccy"] * t["scale"]
    return t


def assign_equity(trades: pd.DataFrame) -> pd.DataFrame:
    t = trades.sort_values("exit_bar").reset_index(drop=True)
    eq = EQUITY_INIT
    befs, afts = [], []
    for pnl in t["pnl_net_ccy"]:
        befs.append(eq); eq += pnl; afts.append(eq)
    t["equity_before"] = befs; t["equity_after"] = afts
    return t


# =====================================================================
# Step 3: 指标
# =====================================================================
def active_day_set(df: pd.DataFrame) -> set:
    days: set = set()
    for _, g in df.groupby("contract"):
        for d in g["event_date"]:
            ts = pd.Timestamp(d)
            if ts.weekday() < 5:
                days.add(ts.date())
    return days


def base_metrics(trades: pd.DataFrame, active_days=None) -> dict:
    t = trades.copy()
    t["day"] = t["_exit_date"]
    daily_pnl = t.groupby("day")["pnl_net_ccy"].sum()
    ret = daily_pnl / EQUITY_INIT
    if len(ret) == 0:
        return {"ann_ret": 0.0, "sharpe": 0.0, "max_dd": 0.0, "n_trades": len(trades)}
    if active_days:
        idx = sorted(active_days)
        ret = ret.reindex(idx, fill_value=0.0)
    ann = ret.mean() * ANNUAL_FACTOR
    std = ret.std() * np.sqrt(ANNUAL_FACTOR)
    sharpe = ann / std if std > 0 else 0.0
    cum = ret.cumsum()
    dd = (cum - cum.cummax()).min()
    return {"ann_ret": ann, "sharpe": sharpe, "max_dd": dd, "n_trades": len(trades)}


def monthly_win_rate(trades: pd.DataFrame) -> float:
    t = trades.copy()
    t["month"] = pd.to_datetime(t["_exit_date"]).dt.to_period("M")
    mret = t.groupby("month")["pnl_net_ccy"].sum()
    return float((mret > 0).mean()) if len(mret) else 0.0


def per_trade_ir(trades: pd.DataFrame) -> float:
    s = trades["pnl_net_bps"].std()
    return float(trades["pnl_net_bps"].mean() / s) if s > 0 else 0.0


def win_rate(trades: pd.DataFrame) -> float:
    return float((trades["pnl_net_bps"] > 0).mean()) if len(trades) else 0.0


# =====================================================================
# Main
# =====================================================================
def main() -> None:
    t0 = time.time()

    print("=" * 80)
    print("va-asymmetry · 研究侧全量回测复现（当前代码基线）")
    print("参数: K_L=1.0 · K_S=2.5 · ATR=SMA(10) · Cap=4.0 · 5m 粒度")
    print("对照: docs/archive/.../va_mad_fix_comparison/metrics_new.json")
    print("=" * 80)

    print("\n[1/4] 从 5m CSV 构建事件时间线 ...")
    symbols = discover_symbols()
    print(f"      发现 {len(symbols)} 个合约的 5m 数据")

    all_events = []
    skipped = 0
    error_samples: list[str] = []
    for i, sym in enumerate(symbols):
        if (i + 1) % 50 == 0:
            print(f"      [{i+1}/{len(symbols)}] ...")
        tick = get_tick(sym)
        try:
            ev = build_events(sym, tick)
            daily = build_daily_features(sym)
            if ev.empty or daily.empty:
                skipped += 1
                continue
            # ── 因果性修复（2026-07-13）：daily 特征 shift(1) ──
            # D 日收盘后才算出的 A3_skew_spec / daily_atr_spec / trend_ret_M_spec
            # 只能用于 D+1 交易日（含夜盘）起的事件。对 daily 的值列向下 shift(1)，
            # 再按原始 date merge，等价于：event_date=D_k 的事件用的是 D_{k-1} 收盘
            # 后算出的 daily 特征，完全无未来信息。
            daily_causal = daily.copy()
            for _c in ("A3_skew_spec", "daily_atr_spec", "trend_ret_M_spec",
                       "daily_atr_10_bps", "trend_ret_10d"):
                if _c in daily_causal.columns:
                    daily_causal[_c] = daily_causal[_c].shift(1)
            ev = ev.merge(daily_causal, left_on="event_date", right_on="date", how="left")
            all_events.append(ev)
        except Exception as e:
            if len(error_samples) < 5:
                error_samples.append(f"{sym}: {type(e).__name__}: {e}")
            skipped += 1
            continue

    if error_samples:
        print(f"      错误样本: {error_samples}")
    if not all_events:
        print("      FATAL: 所有合约均无有效事件，终止")
        return

    df = pd.concat(all_events, ignore_index=True)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"])
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    print(f"      有效合约: {df['contract'].nunique()} / 扫描: {len(symbols)} (跳过 {skipped})")
    print(f"      总事件行: {len(df)}")

    # 旧管线排名列（保持与归档脚本完全一致的数据链）
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
    print(f"      warmup({WARMUP_DAYS}d)后有效事件: {len(df)} | 合约: {df['contract'].nunique()}")

    active_days = active_day_set(df)

    print("\n[2/4] 分类（新版 MAD fix）...")
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
    print(f"      分类事件: {len(ev)} | 合约: {ev['contract'].nunique()} | "
          f"多: {(ev['direction']=='long').sum()} 空: {(ev['direction']=='short').sum()}")

    tier_dist = ev.groupby("tier").size()
    print("\n      阵营分布:")
    for t, n in tier_dist.items():
        print(f"        {t:<25} {n:>6}")

    ev.to_parquet(OUT_DIR / "events.parquet", index=False)

    print(f"\n[3/4] 逐合约 5m 精确模拟 (Cap={CAP}, K_L={K_L_SL}, K_S={K_S_SL}) ...")
    all_rows = []
    for c, g in ev.groupby("contract"):
        all_rows.extend(simulate_contract(c, g))
    raw = pd.DataFrame(all_rows)
    if raw.empty:
        print("      无模拟结果，终止")
        return
    trades = compress(raw, CAP)
    trades = assign_equity(trades)
    print(f"      {len(trades)} 笔交易 | SL: {(trades['exit_reason']=='SL').sum()} | "
          f"TIME: {(trades['exit_reason']=='TIME').sum()}")
    trades.to_parquet(OUT_DIR / "trades.parquet", index=False)

    print("\n[4/4] 指标 ...")
    m = base_metrics(trades, active_days)
    m["win_rate"] = win_rate(trades)
    m["monthly_win"] = monthly_win_rate(trades)
    m["ir"] = per_trade_ir(trades)
    m["n_contracts"] = int(ev["contract"].nunique())
    m["n_active_days"] = len(active_days)

    # 与归档 metrics_new.json 对比
    archive_metrics_path = (
        REPO / "docs/archive/strategy-research/2026/07/"
        "2026-07-13-va-asymmetry-engineering-fix/va_mad_fix_comparison/metrics_new.json"
    )
    ref = json.loads(archive_metrics_path.read_text()) if archive_metrics_path.exists() else {}

    print(f"\n{'='*80}")
    print("                    与归档基线对比")
    print(f"{'='*80}")
    print(f"| 指标           | 当前代码        | 归档基线        | Δ           |")
    print(f"|:---------------|:----------------|:----------------|:------------|")
    def fmt(v, f):
        try:
            return format(float(v), f)
        except Exception:
            return str(v)
    for key, label, f in [
        ("ann_ret", "年化收益", ".2%"),
        ("sharpe", "夏普", ".2f"),
        ("max_dd", "MaxDD", ".2%"),
        ("win_rate", "胜率", ".1%"),
        ("monthly_win", "月度胜率", ".1%"),
        ("ir", "单笔 IR", ".3f"),
    ]:
        cur = m.get(key, 0.0)
        ba = ref.get(key, 0.0)
        try:
            diff = float(cur) - float(ba)
            print(f"| {label:<14} | {fmt(cur, f):<15} | {fmt(ba, f):<15} | {fmt(diff, f):<11} |")
        except Exception:
            print(f"| {label:<14} | {cur} | {ba} | — |")
    for key, label in [("n_trades", "交易笔数"), ("n_contracts", "合约数")]:
        cur = m.get(key, 0)
        ba = ref.get(key, 0)
        try:
            diff = int(cur) - int(ba)
            print(f"| {label:<14} | {cur:<15} | {ba:<15} | {diff:<+11} |")
        except Exception:
            print(f"| {label:<14} | {cur} | {ba} | — |")

    (OUT_DIR / "metrics.json").write_text(
        json.dumps(m, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n输出: {OUT_DIR}")
    print(f"总耗时: {(time.time() - t0)/60:.1f} 分钟")


if __name__ == "__main__":
    main()
