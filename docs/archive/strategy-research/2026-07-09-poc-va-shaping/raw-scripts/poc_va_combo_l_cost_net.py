#!/usr/bin/env python3
"""
poc_va 整点开仓策略 · Combo L 塑形方案成本后收益

用 structural-shaping-alpha 阶段 1 验证过的最优 combo（Combo L）参数：
  - 止损：1.5 × daily_atr_10_bps（固定初始止损）
  - trailing：MFE ≥ 3.0 × daily_atr_10_bps → 止损移至 breakeven（无缓冲）
  - 止盈：无
  - 时间退出：80 bar（5m）≈ 6.67h

在 poc-va 分类器 A 级事件上逐笔回测，计算 realistic-cost 后的 net 收益。

输入:
  project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet
  project_data/market_data/csv/*.tqsdk.5m.csv

输出:
  project_data/ai_tmp/poc_va_combo_l_cost_net.csv
  project_data/ai_tmp/poc_va_combo_l_cost_net.detail.csv
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

import pandas as pd
import numpy as np
from common.contract_specs import CONTRACT_SPECS

# ------------------------------------------------------------------
# 0. 路径
# ------------------------------------------------------------------
TIMELINE_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
MARKET_DIR = Path("project_data/market_data/csv")
OUT_PATH = Path("project_data/ai_tmp/poc_va_combo_l_cost_net.csv")
OUT_DETAIL = Path("project_data/ai_tmp/poc_va_combo_l_cost_net.detail.csv")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# A 级白名单（原始 144 tier 命名）
# 映射自 v4.0 合并版 A 级白名单
A_TIER_RAW = {
    # L_seg3_lowmid_up stable
    "UP2_atrLow_up_stable", "UP3_atrMid_up_stable",
    # L_seg12_high_up trans
    "UP1_atrHigh_up_trans",
    # L_seg2_low_flat full
    "UP2_atrLow_flat_stable", "UP2_atrLow_flat_trans",
    # S_seg12_high_dn full (stable + trans)
    "DN1_atrHigh_down_stable", "DN1_atrHigh_down_trans",
    "DN2_atrHigh_down_stable", "DN2_atrHigh_down_trans",
    # S_seg34_high_dn full
    "DN3_atrHigh_down_stable", "DN3_atrHigh_down_trans",
    "DN4_atrHigh_down_stable", "DN4_atrHigh_down_trans",
    # S_seg2_mid_dn full + trans
    "DN2_atrMid_down_stable", "DN2_atrMid_down_trans",
}

def tier_to_direction(tier_name):
    if tier_name.startswith("UP"):
        return "long"
    elif tier_name.startswith("DN"):
        return "short"
    return None

def tier_to_v40(tier_name):
    """原始 144 tier 映射到 v4.0 合并名"""
    mapping = {
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
    return mapping.get(tier_name, tier_name)

# ------------------------------------------------------------------
# 1. 读取 timeline 数据
# ------------------------------------------------------------------
timeline = pd.read_parquet(TIMELINE_PATH)
timeline["event_time"] = pd.to_datetime(timeline["event_time"])

# 只保留 A 级事件（原始 144 tier 命名）
a_events = timeline[timeline["tier"].isin(A_TIER_RAW)].copy()
a_events["direction"] = a_events["tier"].apply(tier_to_direction)
a_events["tier_v40"] = a_events["tier"].apply(tier_to_v40)

print(f"总事件: {len(timeline)}, A 级事件: {len(a_events)}")
print(f"A 级 tier 分布:\n{a_events['tier_v40'].value_counts()}")

# ------------------------------------------------------------------
# 2. Combo L 参数
# ------------------------------------------------------------------
STOP_ATR_MULT = 1.5      # 固定止损 = 1.5 × ATR
TRAIL_ATR_MULT = 3.0     # trailing 触发 = 3.0 × ATR
MAX_BARS = 80            # 时间退出 = 80 个 5m bar

def simulate_trade(row, bars_5m):
    """
    在 5m bar 序列上模拟一笔交易。
    
    参数:
      row: timeline 中的一行（含 entry_price, direction, daily_atr_10_bps）
      bars_5m: DataFrame, 5m bar 数据（datetime, open, high, low, close）
    
    返回:
      dict: 交易结果
    """
    entry_time = row["event_time"]
    entry_price = row["close_t"]
    direction = 1 if row["direction"] == "long" else -1
    atr_bps = row["daily_atr_10_bps"]
    
    # ATR 转换为价格单位
    atr_price = entry_price * (atr_bps / 10000)
    
    # 初始止损价
    if direction == 1:  # 多头
        stop_price = entry_price - STOP_ATR_MULT * atr_price
    else:  # 空头
        stop_price = entry_price + STOP_ATR_MULT * atr_price
    
    # trailing 触发价和 breakeven 止损
    trail_triggered = False
    if direction == 1:
        trail_trigger_price = entry_price + TRAIL_ATR_MULT * atr_price
        breakeven_stop = entry_price
    else:
        trail_trigger_price = entry_price - TRAIL_ATR_MULT * atr_price
        breakeven_stop = entry_price
    
    # 取触发时间之后的 bar
    future_bars = bars_5m[bars_5m["datetime"] > entry_time].head(MAX_BARS)
    
    if len(future_bars) == 0:
        return {
            "exit_time": None,
            "exit_price": np.nan,
            "bars_held": 0,
            "exit_reason": "no_data",
            "gross_ret": np.nan,
            "trail_triggered": False,
        }
    
    exit_price = np.nan
    exit_time = None
    exit_reason = None
    bars_held = 0
    
    for i, (_, bar) in enumerate(future_bars.iterrows()):
        bars_held = i + 1
        
        # 检查止损（用 high/low）
        if direction == 1:
            if bar["low"] <= stop_price:
                exit_price = stop_price
                exit_time = bar["datetime"]
                exit_reason = "stop"
                break
            # 检查 trailing 触发
            if not trail_triggered and bar["high"] >= trail_trigger_price:
                trail_triggered = True
                stop_price = breakeven_stop
        else:
            if bar["high"] >= stop_price:
                exit_price = stop_price
                exit_time = bar["datetime"]
                exit_reason = "stop"
                break
            # 检查 trailing 触发
            if not trail_triggered and bar["low"] <= trail_trigger_price:
                trail_triggered = True
                stop_price = breakeven_stop
    
    # 时间退出
    if exit_reason is None:
        last_bar = future_bars.iloc[-1]
        exit_price = last_bar["close"]
        exit_time = last_bar["datetime"]
        exit_reason = "time"
        bars_held = len(future_bars)
    
    # 收益率（小数）
    if direction == 1:
        gross_ret = (exit_price - entry_price) / entry_price
    else:
        gross_ret = (entry_price - exit_price) / entry_price
    
    return {
        "exit_time": exit_time,
        "exit_price": exit_price,
        "bars_held": bars_held,
        "exit_reason": exit_reason,
        "gross_ret": gross_ret,
        "trail_triggered": trail_triggered,
    }

# ------------------------------------------------------------------
# 3. 逐合约回测
# ------------------------------------------------------------------
results = []
contracts = a_events["contract"].unique()
print(f"\n需要处理的合约数: {len(contracts)}")

missing_contracts = []
for contract in contracts:
    csv_name = f"{contract}.tqsdk.5m.csv"
    csv_path = MARKET_DIR / csv_name
    
    if not csv_path.exists():
        missing_contracts.append(contract)
        continue
    
    # 读取 5m 数据
    bars = pd.read_csv(csv_path)
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    
    # 该合约的 A 级事件
    events = a_events[a_events["contract"] == contract].copy()
    
    for _, event in events.iterrows():
        trade = simulate_trade(event, bars)
        
        # 成本计算
        spec = CONTRACT_SPECS.get_symbol(contract)
        if spec is None:
            cost_bps = np.nan
        else:
            price = event["close_t"]
            comm = spec.total_commission(price=price, lots=1)
            slip = spec.slippage(lots=1)
            one_way = comm + slip
            total_cost = 2 * one_way
            notional = price * spec.size
            cost_bps = total_cost / notional * 10000
        
        gross_bps = trade["gross_ret"] * 10000
        net_bps = gross_bps - cost_bps
        
        results.append({
            "contract": contract,
            "event_time": event["event_time"],
            "tier_raw": event["tier"],
            "tier_v40": event["tier_v40"],
            "direction": event["direction"],
            "entry_price": event["close_t"],
            "exit_time": trade["exit_time"],
            "exit_price": trade["exit_price"],
            "bars_held": trade["bars_held"],
            "exit_reason": trade["exit_reason"],
            "trail_triggered": trade["trail_triggered"],
            "daily_atr_10_bps": event["daily_atr_10_bps"],
            "gross_bps": gross_bps,
            "cost_bps": cost_bps,
            "net_bps": net_bps,
        })
    
    print(f"  {contract}: {len(events)} events")

if missing_contracts:
    print(f"\n缺失 5m 数据的合约 ({len(missing_contracts)}): {missing_contracts[:10]}...")

# ------------------------------------------------------------------
# 4. 汇总
# ------------------------------------------------------------------
results_df = pd.DataFrame(results)
print(f"\n成功回测事件数: {len(results_df)}")

if len(results_df) == 0:
    print("没有成功回测的事件，退出。")
    sys.exit(0)

# 按 v40 tier 汇总
tier_summary = []
for tier in sorted(results_df["tier_v40"].unique()):
    sub = results_df[results_df["tier_v40"] == tier]
    tier_summary.append({
        "tier": tier,
        "n": len(sub),
        "mean_gross_bps": sub["gross_bps"].mean(),
        "mean_cost_bps": sub["cost_bps"].mean(),
        "mean_net_bps": sub["net_bps"].mean(),
        "std_net_bps": sub["net_bps"].std(),
        "hit_rate": (sub["net_bps"] > 0).mean(),
        "ir_net": sub["net_bps"].mean() / sub["net_bps"].std() if sub["net_bps"].std() > 0 else np.nan,
        "stop_rate": (sub["exit_reason"] == "stop").mean(),
        "trail_rate": sub["trail_triggered"].mean(),
        "avg_bars": sub["bars_held"].mean(),
    })

summary = pd.DataFrame(tier_summary)

# 总体
all_long = results_df[results_df["direction"] == "long"]["net_bps"].dropna()
all_short = results_df[results_df["direction"] == "short"]["net_bps"].dropna()
all_net = results_df["net_bps"].dropna()

print("\n" + "=" * 70)
print("Combo L 塑形方案 · 成本后收益（poc-va A 级事件）")
print("=" * 70)
print(summary.to_string(index=False))

print(f"\n{'=' * 70}")
print("总体汇总")
print(f"{'=' * 70}")
print(f"多头: n={len(all_long):>5}  mean={all_long.mean():>7.2f}  std={all_long.std():>7.2f}  IR={all_long.mean()/all_long.std():>5.2f}  胜率={(all_long>0).mean():>5.1%}")
print(f"空头: n={len(all_short):>5}  mean={all_short.mean():>7.2f}  std={all_short.std():>7.2f}  IR={all_short.mean()/all_short.std():>5.2f}  胜率={(all_short>0).mean():>5.1%}")
print(f"合计: n={len(all_net):>5}  mean={all_net.mean():>7.2f}  std={all_net.std():>7.2f}  IR={all_net.mean()/all_net.std():>5.2f}  胜率={(all_net>0).mean():>5.1%}")

# 与无塑形对比
print(f"\n{'=' * 70}")
print("与全程持仓（无塑形）对比")
print(f"{'=' * 70}")

try:
    old_detail = pd.read_csv("project_data/ai_tmp/poc_va_cost_net_quick.detail.csv", parse_dates=["event_time"])
    # 只保留 A 级 tier
    old_detail = old_detail[old_detail["tier"].isin(results_df["tier_v40"].unique())]
    old_net = old_detail["net_bps"].dropna()
    print(f"无塑形: n={len(old_net):>5}  mean={old_net.mean():>7.2f}  std={old_net.std():>7.2f}  IR={old_net.mean()/old_net.std():>5.2f}")
    print(f"Combo L: n={len(all_net):>5}  mean={all_net.mean():>7.2f}  std={all_net.std():>7.2f}  IR={all_net.mean()/all_net.std():>5.2f}")
    print(f"mean 变化: {all_net.mean() - old_net.mean():+.2f} bps")
    old_ir = old_net.mean() / old_net.std()
    new_ir = all_net.mean() / all_net.std()
    print(f"IR 变化: {new_ir - old_ir:+.2f}")
except Exception as e:
    print(f"无法读取对比数据: {e}")

# ------------------------------------------------------------------
# 5. 保存
# ------------------------------------------------------------------
summary.to_csv(OUT_PATH, index=False)
results_df.to_csv(OUT_DETAIL, index=False)
print(f"\n汇总保存: {OUT_PATH}")
print(f"明细保存: {OUT_DETAIL}")
