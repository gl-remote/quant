#!/usr/bin/env python3
"""t_pit vs quantile 回测对比：直接复用 va_composite_backtest 管线。

运行: uv run python scripts/ai_tmp/va_compare_norm_backtest.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

import va_composite_p1_cap as P1
from strategies.classifiers.poc_va import evaluate_dataset

TL = REPO / "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline_spec.parquet"
CAP = 4.0; DEDUP_H = 8


def events(nm: str):
    tl = pd.read_parquet(TL)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    r = evaluate_dataset(tl, a3_skew_col="A3_skew_tick", atr_col="daily_atr_spec",
                          trend_col="trend_ret_M_spec", norm_method=nm)
    df = r.dropna(subset=["tier"]).copy()
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = df.groupby("contract")["event_time"].shift(1)
    df = df[(prev.isna()) | ((df["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))]
    df["entry_atr_bps"] = df["daily_atr_spec"] / df["close_t"] * 10000.0
    return df.reset_index(drop=True)


def sim(df):
    rows = []
    for c, g in df.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    return P1.assign_equity(P1.compress(pd.DataFrame(rows), CAP))


def stats(tr, ad):
    m = P1.base_metrics(tr, active_days=ad)
    m["monthly_win"] = P1.monthly_win_rate(tr)
    return m


tl = pd.read_parquet(TL)
ad = P1.active_day_set(tl, "signed_skew_rank_roll")
print("active_days:", len(ad))
print()

import time

for nm in ["t_pit", "quantile"]:
    t0 = time.time()
    print(f"[{nm}] 构建事件...", end=" ", flush=True)
    ev = events(nm)
    print(f"事件{len(ev)}(多{(ev['direction']=='long').sum()}/空{(ev['direction']=='short').sum()})", end=" ", flush=True)
    tr = sim(ev)
    m = stats(tr, ad)
    ts = np.sort(tr["_entry_date"].values)
    sp = pd.Timestamp(np.quantile(ts, 0.5)).date()
    oos = tr[tr["_entry_date"] >= sp]
    mo = stats(oos, ad)
    print(f"耗时{time.time()-t0:.0f}s")
    print(f"  全量: 年化{m['ann_ret']*100:.2f}% 夏普{m['sharpe']:.2f} MaxDD{m['max_dd']*100:.2f}% 胜率{m['monthly_win']*100:.1f}%")
    print(f"  OOS : 年化{mo['ann_ret']*100:.2f}% 夏普{mo['sharpe']:.2f} MaxDD{mo['max_dd']*100:.2f}% 胜率{mo['monthly_win']*100:.1f}%")
    print()

print("done.")
