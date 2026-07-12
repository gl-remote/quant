"""深度诊断：逐日对比策略端（纯日线 build_coordinates）与 workbench events 的 r_s/r_a/r_t 坐标。"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))

from strategies.classifiers.poc_va import (
    ClassifierConfig,
    build_coordinates,
    classify_dataframe,
    classify_tier,
    volume_weighted_skew,
    daily_atr_sma,
    trend_log_return,
    compute_transition_series,
    roll_t_pit,
    TRANS_STABLE, TRANS_EXPAND, TRANS_CONTRACT,
)

SYMBOL = "DCE.m2501"
CSV = REPO / f"project_data/market_data/csv/{SYMBOL}.tqsdk.5m.csv"
WB_EVENTS = REPO / "docs/workbench/va_mad_fix_comparison/events_new.parquet"
ATR_WIN = 10; TREND_WIN = 10

wb = pd.read_parquet(WB_EVENTS)
wb_dce = wb[wb["contract"] == SYMBOL].sort_values("event_date").reset_index(drop=True)

bars = pd.read_csv(CSV)
bars["datetime"] = pd.to_datetime(bars["datetime"])
bars["date"] = pd.to_datetime(bars["datetime"].dt.date)

daily = bars.groupby("date").agg(
    open=("open", "first"), high=("high", "max"),
    low=("low", "min"), close=("close", "last"),
    volume=("volume", "sum"),
).reset_index().sort_values("date").reset_index(drop=True)

a3_map = {}
for date_val, g in bars.groupby("date"):
    p = g["close"].to_numpy(dtype=float)
    v = g["volume"].to_numpy(dtype=float)
    a3_map[pd.Timestamp(date_val)] = volume_weighted_skew(p, v)
daily["A3_skew"] = daily["date"].map(a3_map)
daily["daily_atr"] = daily_atr_sma(daily["high"], daily["low"], daily["close"], ATR_WIN)
daily["trend_ret_M"] = trend_log_return(daily["close"], TREND_WIN)
daily["contract"] = SYMBOL

config = ClassifierConfig(skew_rank_win=20, atr_rank_win=20, trend_win=20,
                          atr_entry_win=ATR_WIN, trend_entry_win=TREND_WIN)
coords = build_coordinates(daily, config=config, contract_col="contract")
daily["tier"] = classify_dataframe(coords).values

# ── 只看双方都有的日期，对比坐标 ──
daily["date_str"] = daily["date"].astype(str)
wb_dce["date_str"] = wb_dce["event_date"].astype(str)
m = daily.merge(wb_dce[["date_str", "tier"]], on="date_str", how="outer", suffixes=("_calc", "_wb"))
m["match"] = m["tier_calc"].fillna("∅") == m["tier_wb"].fillna("∅")

print("=== 不一致日期详情 ===")
diff_dates = m[~m["match"]]["date_str"].tolist()
for d in diff_dates:
    rd = daily[daily["date_str"] == d]
    we = wb_dce[wb_dce["date_str"] == d]
    if len(rd) == 0:
        print(f"\n{d}: 仅 workbench 有数据 (tier={we.iloc[0]['tier']})")
        continue
    r = rd.iloc[0]
    # 获取当时的 feature 原始值
    raw_skew = r.get("A3_skew", np.nan)
    raw_atr = r.get("daily_atr", np.nan)
    raw_trend = r.get("trend_ret_M", np.nan)
    co = coords[coords.index == r.name]
    if len(co) > 0:
        c = co.iloc[0]
        print(f"\n{d}:")
        print(f"  原始: skew={raw_skew:.4f}  atr={raw_atr:.4f}  trend_ret={raw_trend:.6f}")
        print(f"  坐标: r_s={c.get('r_s',np.nan):.4f}  r_a={c.get('r_a',np.nan):.4f}  r_t={c.get('r_t',np.nan):.4f}  trans={c.get('trans','?')}")
        print(f"  calc tier: {r.get('tier')}  |  wb tier: {we.iloc[0]['tier'] if len(we)>0 else 'N/A'}")

# ── 同时对比 trend_ret_M 旧 vs 新 ──
daily["trend_ret_old"] = np.log(daily["close"] / daily["close"].shift(10))  # shift=10 (旧策略代码)
daily["trend_ret_new"] = trend_log_return(daily["close"], TREND_WIN)  # shift=9 (spec)
daily["trend_diff"] = daily["trend_ret_new"] - daily["trend_ret_old"]

print("\n\n=== trend_ret_M 新旧对比 (shift=9 vs shift=10) ===")
valid_t = daily.dropna(subset=["trend_ret_new", "trend_ret_old"])
print(f"有效日期数: {len(valid_t)}")
print(f"trend_ret_diff max={valid_t['trend_diff'].max():.6f}  min={valid_t['trend_diff'].min():.6f}  mean_abs={valid_t['trend_diff'].abs().mean():.6f}")
print(f"trend_ret_diff>1e-4 的日期数: {(valid_t['trend_diff'].abs()>1e-4).sum()}/{len(valid_t)}")

# ── 重新分类：旧 trend vs 新 trend ──
daily2 = daily.dropna(subset=["trend_ret_new"]).copy()
daily2["contract"] = SYMBOL
daily2["trend_ret_M"] = daily2["trend_ret_new"]
coords_new = build_coordinates(daily2, config=config, contract_col="contract")
daily2["tier_new"] = classify_dataframe(coords_new).values

daily3 = daily.dropna(subset=["trend_ret_old"]).copy()
daily3["contract"] = SYMBOL
daily3["trend_ret_M"] = daily3["trend_ret_old"]
coords_old = build_coordinates(daily3, config=config, contract_col="contract")
daily3["tier_old"] = classify_dataframe(coords_old).values

# 对齐
cmp = daily2[["date_str","tier_new"]].merge(daily3[["date_str","tier_old"]], on="date_str", how="inner")
cmp["tier_new"] = cmp["tier_new"].fillna("∅"); cmp["tier_old"] = cmp["tier_old"].fillna("∅")
cmp["changed"] = cmp["tier_new"] != cmp["tier_old"]
print(f"\n新旧 trend 导致 tier 变化的日期数: {cmp['changed'].sum()}/{len(cmp)}")
if cmp["changed"].sum() > 0:
    print("变化详情:")
    for _, r in cmp[cmp["changed"]].iterrows():
        print(f"  {r['date_str']}: old={r['tier_old']} → new={r['tier_new']}")
