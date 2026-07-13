"""Step a3: 验证恢复git HEAD后，用研究侧完全相同的输入序列喂 roll_t_pit / build_coordinates
能否复现 events.parquet 中的 r_s/r_a/r_t/trans/tier。
若能复现 → 分类器基准 ok，差异全在策略输入端构造。
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docs", "workbench", "va-asymmetry-composite", "scripts"))

import pandas as pd
import numpy as np
from strategies.classifiers.poc_va import (
    ClassifierConfig, evaluate_dataset, roll_t_pit, classify_tier,
    compute_transition_series, tier_direction,
)

R_DIR = "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
TARGET = ["SHFE.rb2501","DCE.m2501","DCE.y2501","DCE.i2501","INE.sc2503","CZCE.MA501","CZCE.TA501","SHFE.hc2501"]

config = ClassifierConfig(skew_rank_win=10, atr_rank_win=10, trend_win=10,
                         atr_entry_win=10, trend_entry_win=10)

ev_full = pd.read_parquet(os.path.join(R_DIR, "events.parquet"))
print(f"\n原始 events.parquet 总行数: {len(ev_full)}，合约数: {ev_full['contract'].nunique()}")

# 取全量 events 重跑 evaluate_dataset（保证每个合约有足够 window=10 的长度）
recalc_all = evaluate_dataset(ev_full.copy(), config,
                              contract_col="contract",
                              a3_skew_col="A3_skew_spec",
                              atr_col="daily_atr_spec",
                              trend_col="trend_ret_M_spec")
print(f"重跑成功: recalc 行数 {len(recalc_all)}")

# 然后切回 TARGET 子集对比
ev = ev_full[ev_full["contract"].isin(TARGET)].copy().reset_index(drop=True)
recalc_sub = recalc_all[recalc_all["contract"].isin(TARGET)].copy().reset_index(drop=True)
print(f"目标合约 events 行数: {len(ev)}")
print(f"列: {[c for c in ev.columns if c in ('contract','event_time','event_date','A3_skew_spec','daily_atr_spec','trend_ret_M_spec','r_s','r_a','r_t','trans','tier','direction')]}")

# 取 CZCE.MA501 作为单样本验证
sample = ev[ev["contract"]=="CZCE.MA501"].sort_values("event_time").reset_index(drop=True)
print(f"\n=== CZCE.MA501 样本行数: {len(sample)} ===")
cols_s = ["event_time","A3_skew_spec","daily_atr_spec","trend_ret_M_spec","r_s","r_a","r_t","trans","tier"]
print(sample[cols_s].head(10).to_string())

cmp_cols = ["contract","event_time",
            "r_s","r_a","r_t","trans","tier","direction"]
orig = ev[cmp_cols].copy().sort_values(["contract","event_time"]).reset_index(drop=True)
reca = recalc_sub[cmp_cols].copy().sort_values(["contract","event_time"]).reset_index(drop=True)
# merge
merged = orig.merge(reca, on=["contract","event_time"], suffixes=("_orig","_new"))
print(f"\nmerged: {len(merged)} 行 / orig: {len(orig)} / reca: {len(reca)}")

def diff_stats(col, tol=1e-6):
    a = merged[f"{col}_orig"].astype(float)
    b = merged[f"{col}_new"].astype(float)
    mask = (a - b).abs() > tol
    return mask.sum(), len(a)

for c in ["r_s","r_a","r_t"]:
    bad, n = diff_stats(c)
    print(f"  {c}: 差异>1e-6的行数 = {bad}/{n}")

# tier 一致率
tier_match = (merged["tier_orig"].fillna("NA") == merged["tier_new"].fillna("NA")).sum()
print(f"  tier 一致: {tier_match}/{len(merged)} = {tier_match/len(merged)*100:.1f}%")
trans_match = (merged["trans_orig"].fillna("NA") == merged["trans_new"].fillna("NA")).sum()
print(f"  trans 一致: {trans_match}/{len(merged)} = {trans_match/len(merged)*100:.1f}%")
dir_match = (merged["direction_orig"].fillna("NA") == merged["direction_new"].fillna("NA")).sum()
print(f"  direction 一致: {dir_match}/{len(merged)} = {dir_match/len(merged)*100:.1f}%")

# 不一致的样本打印
if tier_match < len(merged):
    mism = merged[merged["tier_orig"].fillna("NA") != merged["tier_new"].fillna("NA")].head(10)
    print(f"\ntier不一致样本（前10）:")
    cols_show = ["contract","event_time",
                 "r_s_orig","r_s_new","r_a_orig","r_a_new","r_t_orig","r_t_new",
                 "trans_orig","trans_new","tier_orig","tier_new"]
    with pd.option_context("display.width", 280, "display.float_format", "{:.4f}".format):
        print(mism[cols_show].to_string(index=False))

# 汇总：全部 7 个合约的 tier 一致率
print(f"\n{'='*80}\n全部7合约 tier 复现率\n{'='*80}")
for c_ in TARGET:
    o = ev[ev["contract"]==c_].sort_values("event_time").reset_index(drop=True)
    r = recalc_sub[recalc_sub["contract"]==c_].sort_values("event_time").reset_index(drop=True)
    if len(o) != len(r):
        print(f"  {c_}: 行数不符 orig={len(o)} new={len(r)} — 跳过")
        continue
    m_ = (o["tier"].fillna("NA").reset_index(drop=True) == r["tier"].fillna("NA").reset_index(drop=True)).sum()
    d_ = (o["direction"].fillna("NA").reset_index(drop=True) == r["direction"].fillna("NA").reset_index(drop=True)).sum()
    print(f"  {c_}: tier={m_}/{len(o)} ({m_/max(1,len(o))*100:.1f}%)  dir={d_}/{len(o)} ({d_/max(1,len(o))*100:.1f}%)")

# short信号的复现
print(f"\n{'='*80}\nS阵营(short)信号复现情况\n{'='*80}")
short_mask_o = ev["tier"].fillna("").str.startswith("S_")
short_mask_r = recalc_sub["tier"].fillna("").str.startswith("S_").reset_index(drop=True)
s_both = (short_mask_o & short_mask_r).sum()
s_only_o = (short_mask_o & ~short_mask_r).sum()
s_only_r = (~short_mask_o & short_mask_r).sum()
print(f"  原始events.short信号数: {short_mask_o.sum()}")
print(f"  复现recalc.short信号数: {short_mask_r.sum()}")
print(f"  两者都命中: {s_both}   R-only: {s_only_o}   recalc-only: {s_only_r}")
