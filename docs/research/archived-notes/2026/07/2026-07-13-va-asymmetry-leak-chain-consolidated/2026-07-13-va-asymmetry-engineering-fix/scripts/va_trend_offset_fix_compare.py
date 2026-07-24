"""trend_offset 修复后对比：策略端与 workbench 端 tier 一致性。
修复前：策略 trend_offset=10（错），workbench trend_log_return shift=9（对）。
修复后：两方都用 shift=9，预期完全一致。
"""
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
    volume_weighted_skew,
    daily_atr_sma,
    trend_log_return,
)

# ── 配置 ──
SYMBOL = "DCE.m2501"
CSV = REPO / f"project_data/market_data/csv/{SYMBOL}.tqsdk.5m.csv"
WB_EVENTS = REPO / "docs/workbench/va_mad_fix_comparison/events_new.parquet"

ATR_ENTRY_WIN = 10
TREND_ENTRY_WIN = 10

# ── 1. 读 workbench events ──
wb = pd.read_parquet(WB_EVENTS)
wb_dce = wb[wb["contract"] == SYMBOL].copy()
wb_dce = wb_dce.sort_values("event_date").reset_index(drop=True)
print(f"workbench events for {SYMBOL}: {len(wb_dce)} rows")

# ── 2. 从 5m CSV 构建日线特征（与 workbench 完全一致）──
bars = pd.read_csv(CSV, usecols=["datetime", "open", "high", "low", "close", "volume"])
bars["datetime"] = pd.to_datetime(bars["datetime"])
bars["date"] = pd.to_datetime(bars["datetime"].dt.date)

daily = bars.groupby("date").agg(
    open=("open", "first"), high=("high", "max"),
    low=("low", "min"), close=("close", "last"),
    volume=("volume", "sum"),
).reset_index().sort_values("date").reset_index(drop=True)

# A3_skew
a3_map = {}
for date_val, g in bars.groupby("date"):
    prices = g["close"].to_numpy(dtype=float)
    volumes = g["volume"].to_numpy(dtype=float)
    a3_map[pd.Timestamp(date_val)] = volume_weighted_skew(prices, volumes)
daily["A3_skew"] = daily["date"].map(a3_map)

# ATR
daily["daily_atr"] = daily_atr_sma(daily["high"], daily["low"], daily["close"], ATR_ENTRY_WIN)

# Trend（趋势 log return，shift=9，与 workbench 一致）
daily["trend_ret_M"] = trend_log_return(daily["close"], TREND_ENTRY_WIN)

daily["contract"] = SYMBOL
print(f"daily features: {len(daily)} rows, date range {daily['date'].min()} ~ {daily['date'].max()}")

# ── 3. 分类 ──
config = ClassifierConfig(
    skew_rank_win=20, atr_rank_win=20, trend_win=20,
    atr_entry_win=ATR_ENTRY_WIN, trend_entry_win=TREND_ENTRY_WIN,
)
coords = build_coordinates(daily, config=config, contract_col="contract")
result = classify_dataframe(coords)
daily["tier"] = result.values

# ── 4. 逐日对比 ──
compare = daily[["date", "tier"]].copy()
compare["date_str"] = compare["date"].astype(str)
wb_dce["date_str"] = wb_dce["event_date"].astype(str)

merged = compare.merge(wb_dce[["date_str", "tier"]], on="date_str", how="outer", suffixes=("_calc", "_wb"))
merged["match"] = merged["tier_calc"] == merged["tier_wb"]
# NaN vs NaN 算匹配
merged.loc[merged["tier_calc"].isna() & merged["tier_wb"].isna(), "match"] = True

n_total = len(merged)
n_match = merged["match"].sum()
n_both_nonempty = ((~merged["tier_calc"].isna()) & (~merged["tier_wb"].isna())).sum()
n_dir_agree = 0
for _, r in merged.iterrows():
    tc = r["tier_calc"]
    tw = r["tier_wb"]
    if isinstance(tc, str) and isinstance(tw, str):
        if (tc.startswith("L_") and tw.startswith("L_")) or (tc.startswith("S_") and tw.startswith("S_")):
            n_dir_agree += 1

print(f"\n=== 对比结果 ===")
print(f"总日期数: {n_total}")
print(f"tier 完全一致: {n_match}/{n_total} ({n_match/n_total*100:.1f}%)")
if n_both_nonempty > 0:
    print(f"双方均有 tier 时一致: {(merged.loc[merged['tier_calc'].notna() & merged['tier_wb'].notna(), 'match'].sum())}/{n_both_nonempty}")
print(f"双方均有 tier 时方向一致: {n_dir_agree}/{n_both_nonempty}")

# 不一致详情
diff = merged[~merged["match"]]
if len(diff) > 0:
    print(f"\n不一致的日期 ({len(diff)} 个):")
    for _, r in diff.iterrows():
        print(f"  {r['date_str']}: calc={r['tier_calc']}  wb={r['tier_wb']}")
else:
    print("\n✅ 完全一致！")
