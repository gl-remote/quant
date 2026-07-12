#!/usr/bin/env python3
"""对比 t_pit vs quantile 归一化在 v4.0 六阵营下的全管线表现。

运行: uv run python scripts/ai_tmp/va_compare_tpit_vs_quantile.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

import va_composite_p1_cap as P1  # noqa: E402
from strategies.classifiers.poc_va import evaluate_dataset  # noqa: E402

TL_PATH = REPO / "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline_spec.parquet"
CAP = 4.0
DEDUP_H = 8


def build_events(norm_method: str) -> pd.DataFrame:
    tl = pd.read_parquet(TL_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    result = evaluate_dataset(tl, a3_skew_col="A3_skew_tick", atr_col="daily_atr_spec",
                              trend_col="trend_ret_M_spec", norm_method=norm_method)
    df = result.dropna(subset=["tier"]).copy()
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = df.groupby("contract")["event_time"].shift(1)
    df = df[(prev.isna()) | ((df["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))]
    df["entry_atr_bps"] = df["daily_atr_spec"] / df["close_t"] * 10000.0
    return df.reset_index(drop=True)


def sim(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    return P1.assign_equity(P1.compress(pd.DataFrame(rows), CAP))


def make_metrics(trades: pd.DataFrame, ad) -> dict:
    m = P1.base_metrics(trades, active_days=ad)
    m["monthly_win"] = P1.monthly_win_rate(trades)
    return m


# ---- 1. tier 一致性 ----
print("=" * 72)
print("t_pit vs quantile · v4.0 六阵营对比")
print("=" * 72)

tl = pd.read_parquet(TL_PATH)
tl["event_time"] = pd.to_datetime(tl["event_time"])
r_tpit = evaluate_dataset(tl, a3_skew_col="A3_skew_tick", atr_col="daily_atr_spec",
                           trend_col="trend_ret_M_spec", norm_method="t_pit")
r_quant = evaluate_dataset(tl, a3_skew_col="A3_skew_tick", atr_col="daily_atr_spec",
                            trend_col="trend_ret_M_spec", norm_method="quantile")

both = pd.DataFrame({"tp": r_tpit["tier"], "q": r_quant["tier"]}).dropna()
total = len(both)
agree = (both["tp"] == both["q"]).sum()
print(f"\n有效判定: {total} | 一致: {agree} ({agree/total*100:.1f}%)")

print("\n按阵营分解:")
for tier in sorted(set(both["tp"].unique()) | set(both["q"].unique())):
    nt = (both["tp"] == tier).sum()
    nq = (both["q"] == tier).sum()
    ag = int(((both["tp"] == tier) & (both["q"] == tier)).sum())
    if nt > 0 or nq > 0:
        print(f"  {tier:30s}: t={nt:>5}  q={nq:>5}  交集={ag:>5}")

print("\n坐标相关性:")
for c in ["r_s", "r_a", "r_t"]:
    mask = r_tpit[c].notna() & r_quant[c].notna()
    cor = r_tpit.loc[mask, c].corr(r_quant.loc[mask, c])
    print(f"  {c}: r={cor:.4f}")

# ---- 2. 回测 ----
print("\n" + "=" * 72)
print("回测对比 (Cap=4.0, dedup=8h, grace=0)")
print("=" * 72)

ad = P1.active_day_set(tl, "signed_skew_rank_roll")
results = {}

for nm in ["t_pit", "quantile"]:
    print(f"\n[{nm}] 构建事件...")
    ev = build_events(nm)
    print(f"  事件: {len(ev)} | 多:{(ev['direction']=='long').sum()} 空:{(ev['direction']=='short').sum()}")
    print(f"  [{nm}] 模拟...")
    tr = sim(ev)
    m = make_metrics(tr, ad)

    times = np.sort(tr["_entry_date"].values)
    split = pd.Timestamp(np.quantile(times, 0.5)).date()
    tr_oos = tr[tr["_entry_date"] >= split]
    mo = make_metrics(tr_oos, ad)

    results[nm] = {"trades": tr, "trades_oos": tr_oos, "m": m, "m_oos": mo, "events": ev, "split": split}

    print(f"  全量: 年化{m['ann_ret']*100:6.2f}% 夏普{m['sharpe']:5.2f} MaxDD{m['max_dd']*100:6.2f}% 胜率{m['monthly_win']*100:4.1f}%")
    print(f"  OOS({split}~): 年化{mo['ann_ret']*100:6.2f}% 夏普{mo['sharpe']:5.2f} MaxDD{mo['max_dd']*100:6.2f}% 胜率{mo['monthly_win']*100:4.1f}%")

# ---- 3. 汇总 ----
print("\n" + "=" * 72)
print("终判")
print("=" * 72)
print(f"{'指标':<20} {'t_pit':>15} {'quantile':>15} {'Δ(q-t)':>15}")
for k in ["ann_ret", "sharpe", "max_dd", "monthly_win"]:
    tv = results["t_pit"]["m"][k] * 100 if k != "sharpe" else results["t_pit"]["m"][k]
    qv = results["quantile"]["m"][k] * 100 if k != "sharpe" else results["quantile"]["m"][k]
    dv = qv - tv
    print(f"{k:<20} {tv:>15.2f} {qv:>15.2f} {dv:>+15.2f}")
print()
for k in ["ann_ret", "sharpe", "max_dd", "monthly_win"]:
    tv = results["t_pit"]["m_oos"][k] * 100 if k != "sharpe" else results["t_pit"]["m_oos"][k]
    qv = results["quantile"]["m_oos"][k] * 100 if k != "sharpe" else results["quantile"]["m_oos"][k]
    dv = qv - tv
    label = f"{k}_OOS"
    print(f"{label:<20} {tv:>15.2f} {qv:>15.2f} {dv:>+15.2f}")
