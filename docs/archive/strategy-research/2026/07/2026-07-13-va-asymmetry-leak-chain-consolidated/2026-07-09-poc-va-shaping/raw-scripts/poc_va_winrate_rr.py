#!/usr/bin/env python3
"""
poc-va 策略 · 胜率和盈亏比分析

基于 poc_va_risk_managed_v2.py 的交易明细，计算：
  - 胜率（盈利笔数 / 总笔数）
  - 盈亏比（平均盈利额 / 平均亏损额，绝对值）
  - 净期望值（胜率的 EV）
  - 分 tier、分方向、分止损/时间退出的详细拆分
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

import pandas as pd
import numpy as np
from common.contract_specs import CONTRACT_SPECS

# ------------------------------------------------------------------
# 路径
# ------------------------------------------------------------------
TIMELINE_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
MARKET_DIR = Path("project_data/market_data/csv")

A_TIER_RAW = {
    "UP2_atrLow_up_stable", "UP3_atrMid_up_stable",
    "UP1_atrHigh_up_trans",
    "DN1_atrHigh_down_stable", "DN1_atrHigh_down_trans",
    "DN2_atrHigh_down_stable", "DN2_atrHigh_down_trans",
    "DN3_atrHigh_down_stable", "DN3_atrHigh_down_trans",
    "DN4_atrHigh_down_stable", "DN4_atrHigh_down_trans",
    "DN2_atrMid_down_stable", "DN2_atrMid_down_trans",
}

TIER_TO_V40 = {
    "UP2_atrLow_up_stable": "L_seg3_lowmid_up", "UP3_atrMid_up_stable": "L_seg3_lowmid_up",
    "UP1_atrHigh_up_trans": "L_seg12_high_up",
    "DN1_atrHigh_down_stable": "S_seg12_high_dn", "DN1_atrHigh_down_trans": "S_seg12_high_dn",
    "DN2_atrHigh_down_stable": "S_seg12_high_dn", "DN2_atrHigh_down_trans": "S_seg12_high_dn",
    "DN3_atrHigh_down_stable": "S_seg34_high_dn", "DN3_atrHigh_down_trans": "S_seg34_high_dn",
    "DN4_atrHigh_down_stable": "S_seg34_high_dn", "DN4_atrHigh_down_trans": "S_seg34_high_dn",
    "DN2_atrMid_down_stable": "S_seg2_mid_dn", "DN2_atrMid_down_trans": "S_seg2_mid_dn",
}

BEST_SHAPING = {
    "L_seg3_lowmid_up": {"stop_mult": 1.0, "max_bars": 72},
    "L_seg12_high_up":  {"stop_mult": 1.0, "max_bars": 120},
    "S_seg12_high_dn":  {"stop_mult": 2.5, "max_bars": 120},
    "S_seg34_high_dn":  {"stop_mult": 2.0, "max_bars": 120},
    "S_seg2_mid_dn":    {"stop_mult": 2.5, "max_bars": 96},
}

# ------------------------------------------------------------------
# 读取数据
# ------------------------------------------------------------------
print("读取并模拟交易...")
timeline = pd.read_parquet(TIMELINE_PATH)
timeline["event_time"] = pd.to_datetime(timeline["event_time"])
a_events = timeline[timeline["tier"].isin(A_TIER_RAW)].copy()
a_events["direction"] = a_events["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
a_events["tier_v40"] = a_events["tier"].map(TIER_TO_V40)

def _cost(contract, price):
    spec = CONTRACT_SPECS.get_symbol(contract)
    if spec is None: return np.nan
    c = spec.total_commission(price=price, lots=1) + spec.slippage(lots=1)
    return 2 * c / (price * spec.size) * 10000

a_events["cost_bps"] = a_events.apply(lambda r: _cost(r["contract"], r["close_t"]), axis=1)
a_events = a_events[a_events["cost_bps"].notna()].copy()

all_trades = []
for contract, grp in a_events.groupby("contract"):
    csv_path = MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not csv_path.exists(): continue
    bars = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)

    for _, ev in grp.iterrows():
        tier_v40 = ev["tier_v40"]
        if tier_v40 not in BEST_SHAPING: continue
        shaping = BEST_SHAPING[tier_v40]
        entry_time = ev["event_time"]
        entry_price = ev["close_t"]
        direction = 1 if ev["direction"] == "long" else -1
        atr_bps = ev["daily_atr_10_bps"]
        stop_mult = shaping["stop_mult"]
        max_bars = shaping["max_bars"]
        cost_bps = ev["cost_bps"]

        atr_price = entry_price * (atr_bps / 10000)
        stop_price = entry_price - direction * stop_mult * atr_price
        idx = bars["datetime"].searchsorted(entry_time)
        future = bars.iloc[idx:idx + max_bars]
        if len(future) == 0: continue

        exit_price = np.nan
        exit_reason = "time"
        for bar_i in range(len(future)):
            bar = future.iloc[bar_i]
            if direction == 1 and bar["low"] <= stop_price:
                exit_price = stop_price
                exit_reason = "stop"
                break
            if direction == -1 and bar["high"] >= stop_price:
                exit_price = stop_price
                exit_reason = "stop"
                break
        if np.isnan(exit_price):
            exit_price = future.iloc[-1]["close"]

        gross_bps = direction * (exit_price - entry_price) / entry_price * 10000
        net_bps = gross_bps - cost_bps

        all_trades.append({
            "tier_v40": tier_v40,
            "direction": ev["direction"],
            "net_bps": net_bps,
            "gross_bps": gross_bps,
            "cost_bps": cost_bps,
            "exit_reason": exit_reason,
        })

trades_df = pd.DataFrame(all_trades)

# ------------------------------------------------------------------
# 胜率与盈亏比
# ------------------------------------------------------------------
def compute_stats(df):
    n = len(df)
    if n == 0: return pd.Series([0]*6, index=["n","win_rate","avg_win","avg_loss","rr","ev"])
    wins = df[df["net_bps"] > 0]["net_bps"]
    losses = df[df["net_bps"] < 0]["net_bps"]
    win_rate = len(wins) / n
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
    rr = avg_win / avg_loss if avg_loss > 0 else 0
    ev = win_rate * avg_win - (1 - win_rate) * avg_loss
    return pd.Series([n, win_rate, avg_win, avg_loss, rr, ev],
                     index=["n","win_rate","avg_win","avg_loss","rr","ev"])

# 总体
total_stats = compute_stats(trades_df)

# 按 tier
tier_stats = trades_df.groupby("tier_v40").apply(compute_stats).reset_index()

# 按方向
dir_stats = trades_df.groupby("direction").apply(compute_stats).reset_index()

# 按退出原因
reason_stats = trades_df.groupby("exit_reason").apply(compute_stats).reset_index()

# 按 tier × exit_reason
tier_reason = trades_df.groupby(["tier_v40", "exit_reason"]).apply(compute_stats).reset_index()

# ------------------------------------------------------------------
# 输出
# ------------------------------------------------------------------
print(f"\n{'=' * 70}")
print("poc-va 策略 · 胜率和盈亏比")
print(f"{'=' * 70}")

print(f"\n总体（所有 tier 合并）")
print(f"  总交易数:     {total_stats['n']:.0f}")
print(f"  胜率:         {total_stats['win_rate']*100:.1f}%")
print(f"  平均盈利:     +{total_stats['avg_win']:.1f} bps")
print(f"  平均亏损:     −{total_stats['avg_loss']:.1f} bps")
print(f"  盈亏比:       {total_stats['rr']:.2f}")
print(f"  期望值(EV):   +{total_stats['ev']:.1f} bps/笔")

print(f"\n{'=' * 70}")
print("按方向")
print(f"{'=' * 70}")
print(dir_stats.to_string(index=False))

print(f"\n{'=' * 70}")
print("按 tier")
print(f"{'=' * 70}")
print(tier_stats.to_string(index=False))

print(f"\n{'=' * 70}")
print("按退出原因")
print(f"{'=' * 70}")
print(reason_stats.to_string(index=False))

print(f"\n{'=' * 70}")
print("按 tier × 退出原因")
print(f"{'=' * 70}")
print(tier_reason.to_string(index=False))

# 凯利公式
print(f"\n{'=' * 70}")
print("凯利最优仓位")
print(f"{'=' * 70}")
for _, row in tier_stats.iterrows():
    if row["win_rate"] > 0 and row["rr"] > 0:
        kelly = (row["win_rate"] * row["rr"] - (1 - row["win_rate"])) / row["rr"]
        print(f"  {row['tier_v40']}: 凯利 = {kelly*100:.1f}%")
