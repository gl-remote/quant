#!/usr/bin/env python3
"""
poc-va 最优塑形参数 · 年化收益与夏普

基于扫描最优参数，用 5m bar 逐笔模拟的净收益，按日聚合计算年化指标。

最优塑形参数（来自 poc_va_shaping_scan_v2.py）:
  L_seg3_lowmid_up: SL1.0 ATR, 持仓 6h (72 bar)
  L_seg12_high_up:  SL1.0 ATR, 持仓 10h (120 bar)
  S_seg12_high_dn:  SL2.5 ATR(实际不触发), 持仓 10h (120 bar)
  S_seg34_high_dn:  SL2.0 ATR(实际不触发), 持仓 10h (120 bar)
  S_seg2_mid_dn:    SL2.5 ATR(实际不触发), 持仓 8h (96 bar)
  L_seg2_low_flat:  淘汰

口径:
  - 每事件投入等名义价值（标准化为 1 单位）
  - 空仓日收益 = 0
  - 同日多事件等权平均
  - 年化 = 日收益 × 252
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
OUT_PATH = Path("project_data/ai_tmp/poc_va_shaping_annual_sharpe.csv")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# A 级白名单（排除 L_seg2_low_flat）
# ------------------------------------------------------------------
A_TIER_RAW = {
    "UP2_atrLow_up_stable", "UP3_atrMid_up_stable",
    "UP1_atrHigh_up_trans",
    # L_seg2_low_flat 已排除
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

# 最优塑形参数（bar = 5m）
BEST_SHAPING = {
    "L_seg3_lowmid_up": {"stop_mult": 1.0, "max_bars": 72},   # 6h
    "L_seg12_high_up":  {"stop_mult": 1.0, "max_bars": 120},  # 10h
    "S_seg12_high_dn":  {"stop_mult": 2.5, "max_bars": 120},  # 10h
    "S_seg34_high_dn":  {"stop_mult": 2.0, "max_bars": 120},  # 10h
    "S_seg2_mid_dn":    {"stop_mult": 2.5, "max_bars": 96},   # 8h
}

MAX_FUTURE = 120

# ------------------------------------------------------------------
# 读取数据
# ------------------------------------------------------------------
print("读取 timeline...")
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
print(f"A 级事件（排除 L_seg2_low_flat）: {len(a_events)}")

# ------------------------------------------------------------------
# 读取 5m bars，提取未来窗口，模拟交易
# ------------------------------------------------------------------
print("逐合约模拟...")
all_trades = []
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
        tier_v40 = ev["tier_v40"]
        if tier_v40 not in BEST_SHAPING:
            continue

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

        if len(future) == 0:
            continue

        exit_price = np.nan
        exit_reason = "time"

        for bar_i in range(len(future)):
            bar = future.iloc[bar_i]
            # 止损
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
            "contract": contract,
            "event_time": entry_time,
            "date": entry_time.date(),
            "tier_v40": tier_v40,
            "direction": ev["direction"],
            "net_bps": net_bps,
            "gross_bps": gross_bps,
            "cost_bps": cost_bps,
            "exit_reason": exit_reason,
        })

trades_df = pd.DataFrame(all_trades)
print(f"模拟交易数: {len(trades_df)}")

# ------------------------------------------------------------------
# 按日聚合
# ------------------------------------------------------------------
trades_df["net_ret"] = trades_df["net_bps"] / 10000

all_dates = pd.date_range(
    start=trades_df["event_time"].min().normalize(),
    end=trades_df["event_time"].max().normalize(),
    freq="D"
)

# 口径 A: 等权平均
daily = trades_df.groupby("date")["net_ret"].mean()
daily_full = daily.reindex(all_dates.date, fill_value=0)

# 口径 B: 累加
daily_sum = trades_df.groupby("date")["net_ret"].sum()
daily_sum_full = daily_sum.reindex(all_dates.date, fill_value=0)

trading_days = len(daily_full)
active_days = (daily_full != 0).sum()

ann_ret_avg = daily_full.mean() * 252
ann_std_avg = daily_full.std() * np.sqrt(252)
sharpe_avg = ann_ret_avg / ann_std_avg if ann_std_avg > 0 else 0

ann_ret_sum = daily_sum_full.mean() * 252
ann_std_sum = daily_sum_full.std() * np.sqrt(252)
sharpe_sum = ann_ret_sum / ann_std_sum if ann_std_sum > 0 else 0

# ------------------------------------------------------------------
# 按 tier 分档
# ------------------------------------------------------------------
tier_results = []
for tier in sorted(trades_df["tier_v40"].unique()):
    sub = trades_df[trades_df["tier_v40"] == tier]
    sub_daily = sub.groupby("date")["net_ret"].mean().reindex(all_dates.date, fill_value=0)
    ann_ret = sub_daily.mean() * 252
    ann_std = sub_daily.std() * np.sqrt(252)
    tier_results.append({
        "tier": tier,
        "n_trades": len(sub),
        "active_days": (sub.groupby("date")["net_ret"].mean() != 0).sum(),
        "annual_return": ann_ret,
        "annual_std": ann_std,
        "sharpe": ann_ret / ann_std if ann_std > 0 else 0,
        "max_dd": (sub_daily.cumsum().max() - sub_daily.cumsum()).min(),
    })
tier_df = pd.DataFrame(tier_results)

# ------------------------------------------------------------------
# 多空分开
# ------------------------------------------------------------------
long_daily = trades_df[trades_df["direction"] == "long"].groupby("date")["net_ret"].mean().reindex(all_dates.date, fill_value=0)
short_daily = trades_df[trades_df["direction"] == "short"].groupby("date")["net_ret"].mean().reindex(all_dates.date, fill_value=0)

long_sharpe = long_daily.mean() * 252 / (long_daily.std() * np.sqrt(252)) if long_daily.std() > 0 else 0
short_sharpe = short_daily.mean() * 252 / (short_daily.std() * np.sqrt(252)) if short_daily.std() > 0 else 0

# ------------------------------------------------------------------
# 输出
# ------------------------------------------------------------------
print(f"\n{'=' * 70}")
print("最优塑形参数 · 年化收益与夏普（排除 L_seg2_low_flat）")
print(f"{'=' * 70}")

print(f"\n数据跨度: {all_dates[0].date()} ~ {all_dates[-1].date()}")
print(f"总日历日: {trading_days}")
print(f"有触发日: {active_days} ({active_days/trading_days*100:.1f}%)")

print(f"\n{'=' * 70}")
print("口径 A: 每日等权平均（空仓=0）")
print(f"{'=' * 70}")
print(f"  年化收益: {ann_ret_avg*100:.2f}%")
print(f"  年化波动: {ann_std_avg*100:.2f}%")
print(f"  夏普比率: {sharpe_avg:.2f}")

print(f"\n{'=' * 70}")
print("口径 B: 每日累加（多事件=多倍暴露）")
print(f"{'=' * 70}")
print(f"  年化收益: {ann_ret_sum*100:.2f}%")
print(f"  年化波动: {ann_std_sum*100:.2f}%")
print(f"  夏普比率: {sharpe_sum:.2f}")

print(f"\n{'=' * 70}")
print("按方向分")
print(f"{'=' * 70}")
print(f"  多头 Sharpe: {long_sharpe:.2f} (年化 {long_daily.mean()*252*100:.2f}%)")
print(f"  空头 Sharpe: {short_sharpe:.2f} (年化 {short_daily.mean()*252*100:.2f}%)")

print(f"\n{'=' * 70}")
print("按 tier 分档（口径 A）")
print(f"{'=' * 70}")
print(tier_df.to_string(index=False))

# 与无塑形对比
print(f"\n{'=' * 70}")
print("与之前口径对比")
print(f"{'=' * 70}")
print(f"  无塑形·全6 tier:    Sharpe 2.64  年化 23.46%")
print(f"  无塑形·排除L_seg2:   Sharpe {sharpe_avg:.2f}  年化 {ann_ret_avg*100:.2f}%  (本次口径)")
print(f"  扫描最优·排除L_seg2: Sharpe {sharpe_avg:.2f}  年化 {ann_ret_avg*100:.2f}%  (本次口径)")
print(f"  Combo L 套用:        Sharpe — (IR 仅 0.12)")

tier_df.to_csv(OUT_PATH, index=False)
print(f"\n保存: {OUT_PATH}")
