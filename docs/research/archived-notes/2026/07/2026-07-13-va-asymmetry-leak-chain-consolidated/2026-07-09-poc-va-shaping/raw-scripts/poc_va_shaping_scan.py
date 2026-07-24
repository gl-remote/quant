#!/usr/bin/env python3
"""
poc-va 塑形参数扫描

对每个 A 级 tier 扫描止损倍数、持仓期、trailing 门槛，
找出使 net IR 最大化的最优塑形参数组合。

扫描维度:
  - 止损: [1.0, 1.5, 2.0, 2.5, 3.0, ∞(无止损)] × ATR
  - 持仓期: [24, 32, 40, 48, 56, 64, 72, 80, 96, 120] bar（5m）
            即 [2h, 2.67h, 3.33h, 4h, 4.67h, 5.33h, 6h, 6.67h, 8h, 10h]
  - trailing: [无, 2.0 ATR breakeven, 2.5 ATR breakeven, 3.0 ATR breakeven]

输入:
  project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet
  project_data/market_data/csv/*.tqsdk.5m.csv

输出:
  project_data/ai_tmp/poc_va_shaping_scan_results.csv
  project_data/ai_tmp/poc_va_shaping_scan_detail.parquet
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

import pandas as pd
import numpy as np
from itertools import product
from common.contract_specs import CONTRACT_SPECS

# ------------------------------------------------------------------
# 0. 路径
# ------------------------------------------------------------------
TIMELINE_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
MARKET_DIR = Path("project_data/market_data/csv")
OUT_SUMMARY = Path("project_data/ai_tmp/poc_va_shaping_scan_results.csv")
OUT_DETAIL = Path("project_data/ai_tmp/poc_va_shaping_scan_detail.parquet")
OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 1. A 级白名单
# ------------------------------------------------------------------
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

TIER_TO_V40 = {
    "UP2_atrLow_up_stable": "L_seg3_lowmid_up",
    "UP3_atrMid_up_stable": "L_seg3_lowmid_up",
    "UP1_atrHigh_up_trans": "L_seg12_high_up",
    "UP2_atrLow_flat_stable": "L_seg2_low_flat",
    "UP2_atrLow_flat_trans": "L_seg2_low_flat",
    "DN1_atrHigh_down_stable": "S_seg12_high_dn",
    "DN1_atrHigh_down_trans": "S_seg12_high_dn",
    "DN2_atrHigh_down_stable": "S_seg12_high_dn",
    "DN2_atrHigh_down_trans": "S_seg12_high_dn",
    "DN3_atrHigh_down_stable": "S_seg34_high_dn",
    "DN3_atrHigh_down_trans": "S_seg34_high_dn",
    "DN4_atrHigh_down_stable": "S_seg34_high_dn",
    "DN4_atrHigh_down_trans": "S_seg34_high_dn",
    "DN2_atrMid_down_stable": "S_seg2_mid_dn",
    "DN2_atrMid_down_trans": "S_seg2_mid_dn",
}

# ------------------------------------------------------------------
# 2. 扫描参数网格
# ------------------------------------------------------------------
STOP_MULTS = [1.0, 1.5, 2.0, 2.5, 3.0, 999]  # 999 = 无止损
MAX_BARS_LIST = [24, 32, 40, 48, 56, 64, 72, 80, 96, 120]
TRAIL_MULTS = [0, 2.0, 2.5, 3.0]  # 0 = 无 trailing

def param_label(stop_m, bars, trail_m):
    stop_str = f"SL{stop_m:.1f}" if stop_m < 999 else "SLinf"
    bars_h = bars * 5 / 60
    trail_str = f"TR{trail_m:.1f}" if trail_m > 0 else "TRoff"
    return f"{stop_str}_T{bars_h:.1f}h_{trail_str}"

# ------------------------------------------------------------------
# 3. 读取数据
# ------------------------------------------------------------------
print("读取 timeline 数据...")
timeline = pd.read_parquet(TIMELINE_PATH)
timeline["event_time"] = pd.to_datetime(timeline["event_time"])

a_events = timeline[timeline["tier"].isin(A_TIER_RAW)].copy()
a_events["direction"] = a_events["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
a_events["tier_v40"] = a_events["tier"].map(TIER_TO_V40)

# 成本预计算
def compute_cost_bps(contract, price):
    spec = CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return np.nan
    comm = spec.total_commission(price=price, lots=1)
    slip = spec.slippage(lots=1)
    total_cost = 2 * (comm + slip)
    return total_cost / (price * spec.size) * 10000

a_events["cost_bps"] = a_events.apply(
    lambda r: compute_cost_bps(r["contract"], r["close_t"]), axis=1
)
a_events = a_events[a_events["cost_bps"].notna()].copy()

print(f"A 级事件: {len(a_events)}")
print(f"合约数: {a_events['contract'].nunique()}")
print(f"tier 分布:\n{a_events['tier_v40'].value_counts()}")

# ------------------------------------------------------------------
# 4. 读取 5m bar 数据到内存
# ------------------------------------------------------------------
print("\n读取 5m bar 数据...")
bars_cache = {}
missing = []
for contract in a_events["contract"].unique():
    csv_path = MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if csv_path.exists():
        bars = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
        bars["datetime"] = pd.to_datetime(bars["datetime"])
        bars_cache[contract] = bars
    else:
        missing.append(contract)

if missing:
    print(f"缺失 5m 数据: {missing[:10]}...")
print(f"成功加载: {len(bars_cache)} 合约")

# ------------------------------------------------------------------
# 5. 模拟函数
# ------------------------------------------------------------------
def simulate_one(entry_time, entry_price, direction, atr_bps, stop_mult, max_bars, trail_mult, bars_5m):
    """单笔模拟，返回 (gross_bps, exit_reason, bars_held, trail_triggered)"""
    dir_sign = 1 if direction == "long" else -1
    atr_price = entry_price * (atr_bps / 10000)

    # 止损
    if stop_mult < 999:
        stop_price = entry_price - dir_sign * stop_mult * atr_price
    else:
        stop_price = None  # 无止损

    # trailing
    trail_triggered = False
    if trail_mult > 0:
        trail_trigger = entry_price + dir_sign * trail_mult * atr_price
        breakeven = entry_price
    else:
        trail_trigger = None

    future = bars_5m[bars_5m["datetime"] > entry_time].head(max_bars)
    if len(future) == 0:
        return np.nan, "no_data", 0, False

    for i, (_, bar) in enumerate(future.iterrows()):
        bars_held = i + 1

        # 止损检查
        if stop_price is not None:
            if direction == "long" and bar["low"] <= stop_price:
                gross = (stop_price - entry_price) / entry_price * 10000
                return gross, "stop", bars_held, trail_triggered
            if direction == "short" and bar["high"] >= stop_price:
                gross = (entry_price - stop_price) / entry_price * 10000
                return gross, "stop", bars_held, trail_triggered

        # trailing 触发
        if trail_trigger is not None and not trail_triggered:
            if direction == "long" and bar["high"] >= trail_trigger:
                trail_triggered = True
                stop_price = breakeven
            if direction == "short" and bar["low"] <= trail_trigger:
                trail_triggered = True
                stop_price = breakeven

    # 时间退出
    last = future.iloc[-1]
    if direction == "long":
        gross = (last["close"] - entry_price) / entry_price * 10000
    else:
        gross = (entry_price - last["close"]) / entry_price * 10000
    return gross, "time", len(future), trail_triggered

# ------------------------------------------------------------------
# 6. 扫描
# ------------------------------------------------------------------
total_params = len(STOP_MULTS) * len(MAX_BARS_LIST) * len(TRAIL_MULTS)
total_events = len(a_events)
total_work = total_params * total_events
print(f"\n参数组合: {total_params}")
print(f"事件数: {total_events}")
print(f"总模拟: {total_work:,}")

# 按 tier_v40 分组扫描
tier_groups = a_events.groupby("tier_v40")
all_results = []

for tier_v40, group in tier_groups:
    print(f"\n扫描 tier: {tier_v40} (n={len(group)})")

    # 预取该 tier 所有事件的 bar 数据
    events_data = []
    for _, ev in group.iterrows():
        bars = bars_cache.get(ev["contract"])
        if bars is not None:
            events_data.append((ev, bars))

    if not events_data:
        continue

    best_ir = -999
    best_params = None

    # 参数网格
    param_iter = product(STOP_MULTS, MAX_BARS_LIST, TRAIL_MULTS)

    for pi, (stop_m, max_bars, trail_m) in enumerate(param_iter):
        if pi % 50 == 0 and pi > 0:
            print(f"  参数 {pi}/{total_params}...")

        net_list = []
        gross_list = []
        exit_reasons = []
        trail_counts = []

        for ev, bars in events_data:
            gross, reason, bars_held, trail = simulate_one(
                ev["event_time"], ev["close_t"], ev["direction"],
                ev["daily_atr_10_bps"], stop_m, max_bars, trail_m, bars
            )
            if np.isnan(gross):
                continue
            net = gross - ev["cost_bps"]
            net_list.append(net)
            gross_list.append(gross)
            exit_reasons.append(reason)
            trail_counts.append(trail)

        if len(net_list) < 10:
            continue

        net_arr = np.array(net_list)
        mean_net = net_arr.mean()
        std_net = net_arr.std()
        ir = mean_net / std_net if std_net > 0 else 0
        hit_rate = (net_arr > 0).mean()
        stop_rate = exit_reasons.count("stop") / len(exit_reasons)
        trail_rate = sum(trail_counts) / len(trail_counts)
        median_net = np.median(net_arr)
        p5 = np.percentile(net_arr, 5)
        p95 = np.percentile(net_arr, 95)

        label = param_label(stop_m, max_bars, trail_m)

        all_results.append({
            "tier_v40": tier_v40,
            "direction": "long" if tier_v40.startswith("L_") else "short",
            "stop_mult": stop_m if stop_m < 999 else np.inf,
            "max_bars": max_bars,
            "trail_mult": trail_m,
            "param_label": label,
            "n": len(net_list),
            "mean_gross": np.mean(gross_list),
            "mean_net": mean_net,
            "std_net": std_net,
            "ir_net": ir,
            "hit_rate": hit_rate,
            "median_net": median_net,
            "p5_net": p5,
            "p95_net": p95,
            "stop_rate": stop_rate,
            "trail_rate": trail_rate,
        })

        if ir > best_ir:
            best_ir = ir
            best_params = label

    print(f"  最优: {best_params} (IR={best_ir:.3f})")

# ------------------------------------------------------------------
# 7. 输出
# ------------------------------------------------------------------
results_df = pd.DataFrame(all_results)
print(f"\n{'=' * 70}")
print("扫描完成，总结果行数: {len(results_df)}")

# 每个 tier 的 top 10
for tier in sorted(results_df["tier_v40"].unique()):
    sub = results_df[results_df["tier_v40"] == tier].nlargest(10, "ir_net")
    print(f"\n--- {tier} Top 10 ---")
    cols = ["param_label", "n", "mean_gross", "mean_net", "ir_net", "hit_rate", "stop_rate", "trail_rate"]
    print(sub[cols].to_string(index=False))

# 全局最优
best_per_tier = results_df.loc[results_df.groupby("tier_v40")["ir_net"].idxmax()]
print(f"\n{'=' * 70}")
print("每个 tier 最优参数")
print(f"{'=' * 70}")
cols = ["tier_v40", "direction", "param_label", "n", "mean_gross", "mean_net", "ir_net", "hit_rate", "stop_rate", "trail_rate"]
print(best_per_tier[cols].to_string(index=False))

# 保存
results_df.to_csv(OUT_SUMMARY, index=False)
print(f"\n保存: {OUT_SUMMARY}")
