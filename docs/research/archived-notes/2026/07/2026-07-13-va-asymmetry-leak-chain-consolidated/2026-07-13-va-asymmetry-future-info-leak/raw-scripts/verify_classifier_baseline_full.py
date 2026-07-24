"""修正版a3验证：用 reproduce 管道在 evaluate_dataset 前的 FULL 36625 行 hourly df（未去重）重跑，
然后按(contract, event_time)join 回 events.parquet 的 980 行，对比 r_s/r_a/r_t/trans/tier/dir。
"""
from __future__ import annotations
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docs", "workbench", "va-asymmetry-composite", "scripts"))

import pandas as pd
import numpy as np
from pathlib import Path
from strategies.classifiers.poc_va import (
    ClassifierConfig, evaluate_dataset, roll_t_pit,
)
import reproduce_research_side as R  # 直接 import 管道函数

R_DIR = "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
TARGET = ["SHFE.rb2501","SHFE.hc2501","DCE.m2501","DCE.y2501","DCE.i2501","INE.sc2503","CZCE.MA501","CZCE.TA501"]

config = ClassifierConfig()  # 与 reproduce L426 完全一致：全默认=10/10/10/10/10

# ── 1. 重建 reproduce Step1：36625 行 hourly df（warmup 后、evaluate_dataset 前）
t0 = time.time()
print("\n[1/3] 重建 Step1 df（warmup 后 evaluate_dataset 前，~36625 行）...")
symbols = R.discover_symbols()
all_events = []
for i, sym in enumerate(symbols):
    if (i+1) % 50 == 0:
        print(f"  [{i+1}/{len(symbols)}] ...")
    tick = R.get_tick(sym)
    ev = R.build_events(sym, tick)
    daily = R.build_daily_features(sym)
    if ev.empty or daily.empty:
        continue
    ev = ev.merge(daily, left_on="event_date", right_on="date", how="left")
    all_events.append(ev)
df = pd.concat(all_events, ignore_index=True)
df["event_time"] = pd.to_datetime(df["event_time"])
df["event_date"] = pd.to_datetime(df["event_date"])
df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
print(f"  合并后 raw: {len(df)} 行 / {df['contract'].nunique()} 合约")

# 旧管线排名列（reproduce L397-421 原样复刻，这几列不是喂给 evaluate_dataset 的，只是 warmup filter）
df["signed_skew"] = -df["A3_skew"]
df["signed_skew_rank_roll"] = df.groupby("contract")["signed_skew"].transform(
    lambda s: R.rolling_pct_rank(s, 100)
)
for feat_col, roll_col in [("daily_atr_10_bps", "atr_rank_roll"),
                           ("trend_ret_10d", "trend_rank_roll")]:
    seg_list = []
    for c, g in df.groupby("contract"):
        daily_g = g.drop_duplicates("event_date").sort_values("event_date").copy()
        daily_g[roll_col] = R.rolling_pct_rank(daily_g[feat_col], R.ROLLING_DAYS)
        seg_list.append(daily_g[["contract", "event_date", roll_col]])
    seg_map = pd.concat(seg_list, ignore_index=True)
    df = df.merge(seg_map, on=["contract", "event_date"], how="left")

keep = np.zeros(len(df), dtype=bool)
for c in df["contract"].unique():
    subset = df[df["contract"] == c].sort_values("event_time")
    dates = sorted(subset["event_date"].unique())
    if len(dates) < R.WARMUP_DAYS:
        continue
    wend = dates[R.WARMUP_DAYS - 1]
    keep |= (df["contract"] == c) & (df["event_date"] > wend)
df = df[keep].reset_index(drop=True)
df = df.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
print(f"  warmup({R.WARMUP_DAYS}d)+rank 非空后: {len(df)} 行 / {df['contract'].nunique()} 合约")
print(f"  构建耗时: {(time.time()-t0):.1f}s")

# ── 2. 跑 evaluate_dataset（和 reproduce L427-430 完全一致）
t1 = time.time()
print("\n[2/3] 跑 evaluate_dataset（git HEAD 分类器 + 默认 config）...")
recalc = evaluate_dataset(
    df, config,
    a3_skew_col="A3_skew_spec", atr_col="daily_atr_spec", trend_col="trend_ret_M_spec",
)
print(f"  recalc 总行数: {len(recalc)}，耗时 {(time.time()-t1):.1f}s")

# ── 3. 与 events.parquet（去重后 980 行）join 对比
print("\n[3/3] 与 events.parquet join 对比 tier/dir/r_s/r_a/r_t/trans...")
ev_orig = pd.read_parquet(os.path.join(R_DIR, "events.parquet"))
ev_orig["event_time"] = pd.to_datetime(ev_orig["event_time"])
print(f"  events.parquet 原始: {len(ev_orig)} 行 / {ev_orig['contract'].nunique()} 合约")

cmp_keys = ["contract", "event_time"]
recalc_sel = recalc[cmp_keys + ["r_s", "r_a", "r_t", "trans", "tier", "direction"]].copy()
orig_sel = ev_orig[cmp_keys + ["r_s", "r_a", "r_t", "trans", "tier", "direction"]].copy()
merged = orig_sel.merge(recalc_sel, on=cmp_keys, suffixes=("_orig", "_new"))
print(f"  merge 成功: {len(merged)} / 原始 {len(orig_sel)} 行")

def diff_rate(col, tol=1e-6):
    a = pd.to_numeric(merged[f"{col}_orig"], errors="coerce")
    b = pd.to_numeric(merged[f"{col}_new"], errors="coerce")
    # NaN 视为一致当且仅当两边都 NaN
    both_nan = a.isna() & b.isna()
    close_enough = (~a.isna() & ~b.isna() & ((a - b).abs() <= tol))
    match = (both_nan | close_enough).sum()
    return match, len(a), (a - b).abs().max()

print(f"\n{'指标':<10} {'一致数':>8} {'总数':>8} {'一致率':>8} {'max|Δ|':>12}")
for c in ["r_s", "r_a", "r_t"]:
    m, n, mx = diff_rate(c)
    print(f"{c:<10} {m:>8} {n:>8} {m/n*100:>7.2f}% {mx:>12.6e}")

for c in ["tier", "trans", "direction"]:
    a = merged[f"{c}_orig"].fillna("(NA)")
    b = merged[f"{c}_new"].fillna("(NA)")
    m = (a == b).sum()
    n = len(a)
    print(f"{c:<10} {m:>8} {n:>8} {m/n*100:>7.2f}% {'—':>12}")

# 目标8合约细分
print(f"\n{'='*80}\n目标 8 合约 tier/dir 复现率\n{'='*80}")
for c_ in TARGET:
    m_org = ev_orig[ev_orig["contract"]==c_].sort_values("event_time").reset_index(drop=True)
    m_new = merged[merged["contract"]==c_].sort_values("event_time").reset_index(drop=True)
    if len(m_org) == 0:
        print(f"  {c_}: 0 信号")
        continue
    mt = (m_org["tier"].fillna("NA").reset_index(drop=True) == m_new["tier_new"].fillna("NA").reset_index(drop=True)).sum()
    md = (m_org["direction"].fillna("NA").reset_index(drop=True) == m_new["direction_new"].fillna("NA").reset_index(drop=True)).sum()
    mr_s = diff_rate_t = (pd.to_numeric(m_new["r_s_orig"],errors="coerce").fillna(-999) - pd.to_numeric(m_new["r_s_new"],errors="coerce").fillna(-999)).abs().max()
    print(f"  {c_}: tier={mt}/{len(m_org)} ({mt/len(m_org)*100:>5.1f}%)  dir={md}/{len(m_org)} ({md/len(m_org)*100:>5.1f}%)  |Δr_s|max={mr_s:.2e}  n={len(m_org)}")

# short信号
print(f"\n{'='*80}\nS阵营(short)信号复现\n{'='*80}")
short_o = merged["tier_orig"].fillna("").str.startswith("S_")
short_n = merged["tier_new"].fillna("").str.startswith("S_")
print(f"  原始short: {short_o.sum()}   复现short: {short_n.sum()}   同时命中: {(short_o&short_n).sum()}   O-only: {(short_o&~short_n).sum()}   N-only: {(~short_o&short_n).sum()}")

# tier不一致的打出来（如果有的话）
mism_tier = merged[merged["tier_orig"].fillna("NA") != merged["tier_new"].fillna("NA")]
if len(mism_tier):
    print(f"\n⚠️  {len(mism_tier)} 行 tier 不一致（前5）:")
    cols = ["contract","event_time","r_s_orig","r_s_new","r_a_orig","r_a_new","r_t_orig","r_t_new","trans_orig","trans_new","tier_orig","tier_new","direction_orig","direction_new"]
    with pd.option_context("display.width", 320, "display.float_format", "{:.6f}".format):
        print(mism_tier[cols].head().to_string(index=False))
else:
    print(f"\n✅ tier 100% 完全一致 — 分类器基线 OK！")

# 保存结果供下游调试
out_dir = "/Users/gaolei/Documents/src/quant/project_data/ai_tmp/R_E_classifier_baseline_repro"
os.makedirs(out_dir, exist_ok=True)
merged.to_parquet(f"{out_dir}/classifier_baseline_merge_980rows.parquet", index=False)
print(f"\n明细已存: {out_dir}/classifier_baseline_merge_980rows.parquet")
