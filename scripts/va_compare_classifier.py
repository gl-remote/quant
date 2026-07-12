#!/usr/bin/env python3
"""
A/B 对比：旧白名单分类器 vs 新 spec 六阵营
用同一份 tick 分桶 skew 数据，仅换分类逻辑
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

import numpy as np
import pandas as pd

# ── 旧分类逻辑（从 POCVAClassifier 提取） ──

SKEW_THRESHOLDS = (0.09, 0.19, 0.25, 0.30, 0.70, 0.75, 0.81, 0.91)
ATR_THRESHOLDS = (0.33, 0.67)
TREND_THRESHOLDS = (0.20, 0.75)

_SKEW_SEG = {"DN_1": "DN1", "DN_2": "DN2", "DN_3": "DN3", "DN_4": "DN4",
             "UP_1": "UP1", "UP_2": "UP2", "UP_3": "UP3", "UP_4": "UP4"}
_ATR_SEG = {"low": "atrLow", "mid": "atrMid", "high": "atrHigh"}
_TREND_SEG = {"down": "down", "flat": "flat", "up": "up"}

# 旧 A 级白名单（13 raw tiers）
A_TIER_RAW = {
    "UP2_atrLow_up_stable", "UP3_atrMid_up_stable",
    "UP1_atrHigh_up_trans",
    "UP2_atrLow_flat_stable", "UP2_atrLow_flat_trans",
    "DN1_atrHigh_down_stable", "DN1_atrHigh_down_trans",
    "DN2_atrHigh_down_stable", "DN2_atrHigh_down_trans",
    "DN3_atrHigh_down_stable", "DN3_atrHigh_down_trans",
    "DN4_atrHigh_down_stable", "DN4_atrHigh_down_trans",
    "DN2_atrMid_down_stable", "DN2_atrMid_down_trans",
}


def _skew_label(rank: float) -> str | None:
    if rank is None or not np.isfinite(rank):
        return None
    t = SKEW_THRESHOLDS
    if rank <= t[0]: return "DN_1"
    if rank <= t[1]: return "DN_2"
    if rank <= t[2]: return "DN_3"
    if rank <= t[3]: return "DN_4"
    if rank < t[4]: return "NEUTRAL"
    if rank < t[5]: return "UP_4"
    if rank < t[6]: return "UP_3"
    if rank < t[7]: return "UP_2"
    return "UP_1"


def _atr_regime(rank: float) -> str | None:
    if rank is None or not np.isfinite(rank): return None
    lo, hi = ATR_THRESHOLDS
    if rank <= lo: return "low"
    if rank < hi: return "mid"
    return "high"


def _trend_regime(rank: float) -> str | None:
    if rank is None or not np.isfinite(rank): return None
    lo, hi = TREND_THRESHOLDS
    if rank <= lo: return "down"
    if rank < hi: return "flat"
    return "up"


def old_tier_id(skew_label: str | None, atr_regime: str | None,
                trend_regime: str | None, transition_flag: bool | None) -> str | None:
    if skew_label is None or skew_label == "NEUTRAL":
        return None
    if atr_regime is None or trend_regime is None or transition_flag is None:
        return None
    d = _SKEW_SEG.get(skew_label)
    a = _ATR_SEG.get(atr_regime)
    t = _TREND_SEG.get(trend_regime)
    p = "trans" if transition_flag else "stable"
    if d is None or a is None or t is None:
        return None
    return f"{d}_{a}_{t}_{p}"


# ── 新 spec 六阵营分类 ──

from strategies.classifiers.poc_va import (
    evaluate_dataset, classify_tier, tier_direction,
    roll_quantile, build_coordinates, classify_dataframe,
    DEFAULT_CONFIG,
)

# ── 主流程 ──

TL_PATH = REPO / "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline_spec.parquet"
OLD_PATH = REPO / "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet"

print("加载数据...")
spec = pd.read_parquet(TL_PATH)
old = pd.read_parquet(OLD_PATH)
spec["event_time"] = pd.to_datetime(spec["event_time"])
old["event_time"] = pd.to_datetime(old["event_time"])

# 合并旧 rank 列
rank_cols = ["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll", "transition_flag"]
spec = spec.merge(old[["contract", "event_time"] + rank_cols],
                  on=["contract", "event_time"], how="left")

print(f"spec 行数: {len(spec)}")

# ── 方案 A：旧白名单分类 ──
print("\n=== 方案 A：旧白名单分类（13 tier） ===")
sl = spec["signed_skew_rank_roll"].apply(_skew_label)
ar = spec["atr_rank_roll"].apply(_atr_regime)
tr = spec["trend_rank_roll"].apply(_trend_regime)
tf = spec["transition_flag"]

old_tiers = []
for i in range(len(spec)):
    tid = old_tier_id(sl.iloc[i], ar.iloc[i], tr.iloc[i], tf.iloc[i])
    old_tiers.append(tid)

spec["old_tier_raw"] = old_tiers
spec["old_tier_active"] = spec["old_tier_raw"].isin(A_TIER_RAW)
spec["old_direction"] = spec["old_tier_raw"].apply(
    lambda t: "long" if (t and t.startswith("UP")) else ("short" if (t and t.startswith("DN")) else "")
)

active_a = spec["old_tier_active"].sum()
long_a = (spec["old_direction"] == "long").sum()
short_a = (spec["old_direction"] == "short").sum()
print(f"活跃事件: {active_a}  (多 {long_a} / 空 {short_a})")
print(f"旧 tier 分布:")
print(spec.loc[spec["old_tier_active"], "old_tier_raw"].value_counts().to_string())

# ── 方案 B：新 spec 六阵营（quantile 归一化） ──
print("\n=== 方案 B：新 spec 六阵营（quantile） ===")
rB = evaluate_dataset(
    spec,
    a3_skew_col="A3_skew_tick",
    atr_col="daily_atr_spec",
    trend_col="trend_ret_M_spec",
    norm_method="quantile",
)
active_b = rB["tier"].notna().sum()
long_b = (rB["direction"] == "long").sum()
short_b = (rB["direction"] == "short").sum()
print(f"活跃事件: {active_b}  (多 {long_b} / 空 {short_b})")
print(f"新 tier 分布:")
print(rB["tier"].value_counts(dropna=True).to_string())

# ── 合并对照 ──
print("\n=== 交集分析 ===")
rB["old_tier_active"] = spec["old_tier_active"].values
rB["old_direction"] = spec["old_direction"].values

both = (rB["old_tier_active"]) & (rB["tier"].notna())
only_old = (rB["old_tier_active"]) & (rB["tier"].isna())
only_new = (~rB["old_tier_active"]) & (rB["tier"].notna())

print(f"双方都活跃: {both.sum()}")
print(f"仅旧活跃: {only_old.sum()}")
print(f"仅新活跃: {only_new.sum()}")

# 方向一致率
both_df = rB[both].copy()
dir_match = both_df["old_direction"] == both_df["direction"]
print(f"交集方向一致: {dir_match.sum()}/{len(both_df)} ({dir_match.mean()*100:.1f}%)")

print("\nDone. 准备写入 backtest...")
# 写回 spec 文件
spec.to_parquet(TL_PATH, index=False)
print(f"Updated {TL_PATH}")
