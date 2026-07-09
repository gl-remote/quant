#!/usr/bin/env python3
"""
poc-va 塑形参数扫描 v2（向量化）

对每个 A 级 tier 扫描止损倍数、持仓期，用 numpy 向量化加速。
先做无 trailing 版本（快 4 倍），再做有 trailing 版本。

扫描维度:
  - 止损: [1.0, 1.5, 2.0, 2.5, 3.0, ∞] × ATR
  - 持仓期: [24, 32, 40, 48, 56, 64, 72, 80, 96, 120] bar（5m）
  - trailing: [无, 2.0, 2.5, 3.0] × ATR breakeven

输入:
  project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet
  project_data/market_data/csv/*.tqsdk.5m.csv

输出:
  project_data/ai_tmp/poc_va_shaping_scan_results.csv
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
OUT_SUMMARY = Path("project_data/ai_tmp/poc_va_shaping_scan_results.csv")
OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# A 级白名单
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
    "UP2_atrLow_up_stable": "L_seg3_lowmid_up", "UP3_atrMid_up_stable": "L_seg3_lowmid_up",
    "UP1_atrHigh_up_trans": "L_seg12_high_up",
    "UP2_atrLow_flat_stable": "L_seg2_low_flat", "UP2_atrLow_flat_trans": "L_seg2_low_flat",
    "DN1_atrHigh_down_stable": "S_seg12_high_dn", "DN1_atrHigh_down_trans": "S_seg12_high_dn",
    "DN2_atrHigh_down_stable": "S_seg12_high_dn", "DN2_atrHigh_down_trans": "S_seg12_high_dn",
    "DN3_atrHigh_down_stable": "S_seg34_high_dn", "DN3_atrHigh_down_trans": "S_seg34_high_dn",
    "DN4_atrHigh_down_stable": "S_seg34_high_dn", "DN4_atrHigh_down_trans": "S_seg34_high_dn",
    "DN2_atrMid_down_stable": "S_seg2_mid_dn", "DN2_atrMid_down_trans": "S_seg2_mid_dn",
}

# ------------------------------------------------------------------
# 参数
# ------------------------------------------------------------------
STOP_MULTS = [1.0, 1.5, 2.0, 2.5, 3.0, 999.0]
MAX_BARS_LIST = [24, 32, 40, 48, 56, 64, 72, 80, 96, 120]
TRAIL_MULTS = [0.0, 2.0, 2.5, 3.0]
MAX_FUTURE = 120  # 预取的最大 bar 数

# ------------------------------------------------------------------
# 读取
# ------------------------------------------------------------------
print("读取 timeline...")
timeline = pd.read_parquet(TIMELINE_PATH)
timeline["event_time"] = pd.to_datetime(timeline["event_time"])
a_events = timeline[timeline["tier"].isin(A_TIER_RAW)].copy()
a_events["direction"] = a_events["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
a_events["tier_v40"] = a_events["tier"].map(TIER_TO_V40)

# 成本
def _cost(contract, price):
    spec = CONTRACT_SPECS.get_symbol(contract)
    if spec is None: return np.nan
    c = spec.total_commission(price=price, lots=1) + spec.slippage(lots=1)
    return 2 * c / (price * spec.size) * 10000

a_events["cost_bps"] = a_events.apply(lambda r: _cost(r["contract"], r["close_t"]), axis=1)
a_events = a_events[a_events["cost_bps"].notna()].copy()
print(f"A 级事件: {len(a_events)}")

# ------------------------------------------------------------------
# 读取 5m bars，为每个事件提取未来 120 bar 的 high/low/close
# ------------------------------------------------------------------
print("读取 5m bars 并提取未来窗口...")
all_rows = []
missing = []
for contract, grp in a_events.groupby("contract"):
    csv_path = MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not csv_path.exists():
        missing.append(contract)
        continue
    bars = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)

    for _, ev in grp.iterrows():
        idx = bars["datetime"].searchsorted(ev["event_time"])
        future = bars.iloc[idx:idx + MAX_FUTURE]
        if len(future) == 0:
            continue
        # 填充到 MAX_FUTURE
        pad_len = MAX_FUTURE - len(future)
        if pad_len > 0:
            pad = pd.DataFrame({
                "high": [future["high"].iloc[-1]] * pad_len,
                "low": [future["low"].iloc[-1]] * pad_len,
                "close": [future["close"].iloc[-1]] * pad_len,
            })
            future = pd.concat([future[["high", "low", "close"]], pad], ignore_index=True)

        all_rows.append({
            "tier_v40": ev["tier_v40"],
            "direction": ev["direction"],
            "entry_price": ev["close_t"],
            "atr_bps": ev["daily_atr_10_bps"],
            "cost_bps": ev["cost_bps"],
            "f_high": future["high"].values,
            "f_low": future["low"].values,
            "f_close": future["close"].values,
        })

print(f"缺失 5m: {len(missing)} 合约")
print(f"构建事件数: {len(all_rows)}")

# 按 tier 分组
tier_groups = {}
for row in all_rows:
    tier_groups.setdefault(row["tier_v40"], []).append(row)

# ------------------------------------------------------------------
# 向量化扫描
# ------------------------------------------------------------------
print(f"\n开始扫描: {len(STOP_MULTS)}×{len(MAX_BARS_LIST)}×{len(TRAIL_MULTS)} = {len(STOP_MULTS)*len(MAX_BARS_LIST)*len(TRAIL_MULTS)} 参数组合")

all_results = []

for tier_v40, rows in sorted(tier_groups.items()):
    n_events = len(rows)
    print(f"\n--- {tier_v40} (n={n_events}) ---")

    # 向量化数组
    entry_prices = np.array([r["entry_price"] for r in rows])
    atr_bps = np.array([r["atr_bps"] for r in rows])
    cost_bps = np.array([r["cost_bps"] for r in rows])
    directions = np.array([1 if r["direction"] == "long" else -1 for r in rows])
    f_high = np.stack([r["f_high"] for r in rows])  # (n_events, MAX_FUTURE)
    f_low = np.stack([r["f_low"] for r in rows])
    f_close = np.stack([r["f_close"] for r in rows])

    atr_price = entry_prices * (atr_bps / 10000)  # (n_events,)

    best_ir = -999
    best_label = ""

    for stop_m in STOP_MULTS:
        has_stop = stop_m < 999
        for max_bars in MAX_BARS_LIST:
            for trail_m in TRAIL_MULTS:
                # 初始化
                exit_prices = np.full(n_events, np.nan)
                exit_reasons = np.zeros(n_events, dtype=int)  # 0=time, 1=stop
                trail_triggered = np.zeros(n_events, dtype=bool)

                # 活跃标志（未退出）
                active = np.ones(n_events, dtype=bool)

                # 初始止损价
                if has_stop:
                    stop_prices = entry_prices - directions * stop_m * atr_price
                else:
                    stop_prices = np.full(n_events, np.inf)

                # trailing 触发价
                if trail_m > 0:
                    trail_trigger_prices = entry_prices + directions * trail_m * atr_price
                    breakeven = entry_prices.copy()
                else:
                    trail_trigger_prices = np.full(n_events, np.inf)

                # 逐 bar 处理
                for bar_i in range(max_bars):
                    if not active.any():
                        break

                    h = f_high[active, bar_i]
                    l = f_low[active, bar_i]

                    if has_stop:
                        sp = stop_prices[active]

                        # 多头止损：low <= stop_price
                        long_active = directions[active] == 1
                        long_stop = long_active & (l <= sp)
                        # 空头止损：high >= stop_price
                        short_stop = (~long_active) & (h >= sp)
                        any_stop = long_stop | short_stop

                        # 记录止损退出
                        active_indices = np.where(active)[0]
                        stop_indices = active_indices[any_stop]
                        exit_prices[stop_indices] = stop_prices[stop_indices]
                        exit_reasons[stop_indices] = 1
                        active[stop_indices] = False

                    # trailing 触发
                    if trail_m > 0:
                        still_active = active & ~trail_triggered
                        if still_active.any():
                            sa_idx = np.where(still_active)[0]
                            tt = trail_trigger_prices[sa_idx]
                            h_sa = f_high[sa_idx, bar_i]
                            l_sa = f_low[sa_idx, bar_i]
                            d_sa = directions[sa_idx]

                            long_trail = (d_sa == 1) & (h_sa >= tt)
                            short_trail = (d_sa == -1) & (l_sa <= tt)
                            triggered_idx = sa_idx[long_trail | short_trail]
                            trail_triggered[triggered_idx] = True
                            stop_prices[triggered_idx] = breakeven[triggered_idx]

                # 时间退出（仍活跃的用 close）
                still_active = active
                if still_active.any():
                    exit_prices[still_active] = f_close[still_active, max_bars - 1]

                # 计算收益
                gross = directions * (exit_prices - entry_prices) / entry_prices * 10000
                net = gross - cost_bps

                valid = np.isfinite(net)
                n_valid = valid.sum()
                if n_valid < 10:
                    continue

                net_v = net[valid]
                mean_net = net_v.mean()
                std_net = net_v.std()
                ir = mean_net / std_net if std_net > 0 else 0
                hit = (net_v > 0).mean()
                sr = exit_reasons[valid].sum() / n_valid
                tr = trail_triggered[valid].sum() / n_valid

                label = f"SL{'inf' if not has_stop else f'{stop_m:.1f}'}_T{max_bars*5/60:.1f}h_{'TRoff' if trail_m==0 else f'TR{trail_m:.1f}'}"

                all_results.append({
                    "tier_v40": tier_v40,
                    "direction": "long" if tier_v40.startswith("L_") else "short",
                    "stop_mult": np.inf if not has_stop else stop_m,
                    "max_bars": max_bars,
                    "trail_mult": trail_m,
                    "param_label": label,
                    "n": n_valid,
                    "mean_net": mean_net,
                    "std_net": std_net,
                    "ir_net": ir,
                    "hit_rate": hit,
                    "stop_rate": sr,
                    "trail_rate": tr,
                    "median_net": np.median(net_v),
                    "p5_net": np.percentile(net_v, 5),
                    "p95_net": np.percentile(net_v, 95),
                })

                if ir > best_ir:
                    best_ir = ir
                    best_label = label

    print(f"  最优: {best_label} (IR={best_ir:.3f})")

# ------------------------------------------------------------------
# 输出
# ------------------------------------------------------------------
results_df = pd.DataFrame(all_results)
print(f"\n总结果行: {len(results_df)}")

for tier in sorted(results_df["tier_v40"].unique()):
    sub = results_df[results_df["tier_v40"] == tier].nlargest(10, "ir_net")
    print(f"\n--- {tier} Top 10 ---")
    print(sub[["param_label", "n", "mean_net", "ir_net", "hit_rate", "stop_rate", "trail_rate"]].to_string(index=False))

best = results_df.loc[results_df.groupby("tier_v40")["ir_net"].idxmax()]
print(f"\n{'='*60}")
print("各 tier 最优塑形参数")
print(f"{'='*60}")
print(best[["tier_v40", "direction", "param_label", "n", "mean_net", "ir_net", "hit_rate", "stop_rate", "trail_rate"]].to_string(index=False))

results_df.to_csv(OUT_SUMMARY, index=False)
print(f"\n保存: {OUT_SUMMARY}")
