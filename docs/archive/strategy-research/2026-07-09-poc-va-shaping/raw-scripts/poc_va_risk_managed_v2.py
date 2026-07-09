#!/usr/bin/env python3
"""
poc-va 风控口径 v2 · 考虑期货保证金制度

风控规则:
  1. 所有 A 级信号都下注
  2. 单信号最大亏损 ≤ 总资本 2%（止损 + 成本后）
     → 仓位（名义价值）= 2% / 止损距离%
  3. 同时持有保证金占用 ≤ 总资本 80%（流动性约束）
  4. 同时持有名义风险暴露 ≤ 总资本 100%（方向性风险约束）
  5. 如果任一约束超限，按比例缩减所有仓位
  6. 保证金率从 contract_specs 读取（每个合约不同，5%~12%）

关键修正:
  - position_size 表示"名义价值 / 总资本"（如 2.0 = 200% 名义值）
  - 保证金占用 = position_size × margin_rate
  - 12% 风险暴露 = 保证金占用约束（非名义值约束）
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
OUT_PATH = Path("project_data/ai_tmp/poc_va_risk_managed_v2.csv")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 风控参数
# ------------------------------------------------------------------
MAX_LOSS_PCT = 0.02       # 单信号止损亏损 ≤ 2% 总资本
MAX_MARGIN_PCT = 0.80     # 保证金占用 ≤ 80% 总资本
MAX_NOTIONAL_PCT = 1.00   # 名义价值 ≤ 100% 总资本

# ------------------------------------------------------------------
# A 级白名单（排除 L_seg2_low_flat）
# ------------------------------------------------------------------
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
print(f"A 级事件: {len(a_events)}")

# ------------------------------------------------------------------
# 逐合约模拟
# ------------------------------------------------------------------
print("逐合约模拟...")
all_trades = []

for contract, grp in a_events.groupby("contract"):
    csv_path = MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not csv_path.exists():
        continue
    bars = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)

    spec = CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        continue
    margin_rate = spec.margin

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

        # 止损距离（占入场价的比例）
        stop_dist_pct = abs(entry_price - stop_price) / entry_price

        # 仓位（名义价值 / 总资本）：使止损亏损 = 2% 总资本
        position_notional = MAX_LOSS_PCT / stop_dist_pct

        # 保证金占用（占总资本比例）
        margin_used = position_notional * margin_rate

        # 5m bar 模拟
        idx = bars["datetime"].searchsorted(entry_time)
        future = bars.iloc[idx:idx + max_bars]

        if len(future) == 0:
            continue

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

        # 收益率（占名义价值）
        gross_ret = direction * (exit_price - entry_price) / entry_price
        net_ret = gross_ret - cost_bps / 10000

        # 占总资本的 P&L
        pnl_capital = position_notional * net_ret

        all_trades.append({
            "contract": contract,
            "tier_v40": tier_v40,
            "direction": ev["direction"],
            "entry_time": entry_time,
            "pnl_date": entry_time.date(),
            "position_notional": position_notional,  # 名义价值 / 总资本
            "margin_used": margin_used,                # 保证金 / 总资本
            "margin_rate": margin_rate,
            "stop_dist_pct": stop_dist_pct,
            "gross_ret": gross_ret * 10000,
            "cost_bps": cost_bps,
            "net_bps": net_ret * 10000,
            "pnl_capital": pnl_capital,  # 占总资本的 P&L
            "exit_reason": exit_reason,
        })

trades_df = pd.DataFrame(all_trades)
print(f"交易数: {len(trades_df)}")

# ------------------------------------------------------------------
# 风控约束：按日缩减
# ------------------------------------------------------------------
daily_agg = trades_df.groupby("pnl_date").agg(
    total_notional=("position_notional", "sum"),
    total_margin=("margin_used", "sum"),
    n_trades=("pnl_date", "count"),
).reset_index()

# 缩放因子：取三个约束中最紧的
scale_margin = np.where(
    daily_agg["total_margin"] > MAX_MARGIN_PCT,
    MAX_MARGIN_PCT / daily_agg["total_margin"],
    1.0
)
scale_notional = np.where(
    daily_agg["total_notional"] > MAX_NOTIONAL_PCT,
    MAX_NOTIONAL_PCT / daily_agg["total_notional"],
    1.0
)
daily_agg["scale"] = np.minimum(scale_margin, scale_notional)

trades_df = trades_df.merge(daily_agg[["pnl_date", "scale"]], on="pnl_date", how="left")
trades_df["scaled_pnl"] = trades_df["pnl_capital"] * trades_df["scale"]

# 统计
print(f"\n{'=' * 60}")
print(f"风控统计（保证金率来自 contract_specs）")
print(f"{'=' * 60}")
print(f"  单信号止损上限: {MAX_LOSS_PCT*100:.0f}% 总资本")
print(f"  保证金占用上限: {MAX_MARGIN_PCT*100:.0f}% 总资本")
print(f"  名义价值上限:   {MAX_NOTIONAL_PCT*100:.0f}% 总资本")
print(f"\n  日均名义暴露: {daily_agg['total_notional'].mean()*100:.1f}%")
print(f"  日均保证金:    {daily_agg['total_margin'].mean()*100:.1f}%")
print(f"  最大日名义:    {daily_agg['total_notional'].max()*100:.1f}%")
print(f"  最大日保证金:  {daily_agg['total_margin'].max()*100:.1f}%")
print(f"  触发缩减天数:  {(daily_agg['scale'] < 1.0).sum()} / {len(daily_agg)} ({(daily_agg['scale'] < 1.0).mean()*100:.1f}%)")
print(f"  平均缩减因子:  {daily_agg['scale'].mean():.4f}")

# 保证金约束 vs 名义约束
margin_limited = (scale_margin < scale_notional).sum()
notional_limited = (scale_notional < scale_margin).sum()
print(f"  保证金触发:    {margin_limited} 天")
print(f"  名义值触发:    {notional_limited} 天")

# ------------------------------------------------------------------
# 按日聚合
# ------------------------------------------------------------------
daily_pnl = trades_df.groupby("pnl_date")["scaled_pnl"].sum()

all_dates = pd.date_range(
    start=min(trades_df["pnl_date"]),
    end=max(trades_df["pnl_date"]),
    freq="D"
)
daily_full = daily_pnl.reindex(all_dates.date, fill_value=0)

trading_days = len(daily_full)
active_days = (daily_full != 0).sum()

ann_ret = daily_full.mean() * 252
ann_std = daily_full.std() * np.sqrt(252)
sharpe = ann_ret / ann_std if ann_std > 0 else 0

cum = daily_full.cumsum()
peak = cum.cummax()
drawdown = cum - peak
max_dd = drawdown.min()
calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0

# ------------------------------------------------------------------
# 按 tier 分档
# ------------------------------------------------------------------
tier_results = []
for tier in sorted(trades_df["tier_v40"].unique()):
    sub = trades_df[trades_df["tier_v40"] == tier]
    sub_daily = sub.groupby("pnl_date")["scaled_pnl"].sum().reindex(all_dates.date, fill_value=0)
    t_ann_ret = sub_daily.mean() * 252
    t_ann_std = sub_daily.std() * np.sqrt(252)
    t_cum = sub_daily.cumsum()
    t_peak = t_cum.cummax()
    t_dd = (t_cum - t_peak).min()
    tier_results.append({
        "tier": tier,
        "n_trades": len(sub),
        "active_days": (sub.groupby("pnl_date")["scaled_pnl"].sum() != 0).sum(),
        "avg_notional": sub["position_notional"].mean(),
        "avg_margin": sub["margin_used"].mean(),
        "avg_margin_rate": sub["margin_rate"].mean(),
        "avg_scale": sub["scale"].mean(),
        "annual_return": t_ann_ret,
        "annual_std": t_ann_std,
        "sharpe": t_ann_ret / t_ann_std if t_ann_std > 0 else 0,
        "max_dd": t_dd,
        "calmar": t_ann_ret / abs(t_dd) if t_dd != 0 else 0,
    })
tier_df = pd.DataFrame(tier_results)

# 多空
long_daily = trades_df[trades_df["direction"] == "long"].groupby("pnl_date")["scaled_pnl"].sum().reindex(all_dates.date, fill_value=0)
short_daily = trades_df[trades_df["direction"] == "short"].groupby("pnl_date")["scaled_pnl"].sum().reindex(all_dates.date, fill_value=0)
long_sharpe = long_daily.mean() * 252 / (long_daily.std() * np.sqrt(252)) if long_daily.std() > 0 else 0
short_sharpe = short_daily.mean() * 252 / (short_daily.std() * np.sqrt(252)) if short_daily.std() > 0 else 0

# ------------------------------------------------------------------
# 敏感性分析：不同约束水平
# ------------------------------------------------------------------
print(f"\n{'=' * 60}")
print("敏感性分析：不同保证金上限")
print(f"{'=' * 60}")
# 预计算每日 scale series
scale_map = daily_agg.set_index("pnl_date")["scale"]

for max_margin in [0.30, 0.50, 0.80, 1.00, 1.50, 2.00]:
    s_margin = np.where(daily_agg["total_margin"] > max_margin, max_margin / daily_agg["total_margin"], 1.0)
    s_notional = np.where(daily_agg["total_notional"] > max_margin * 2, max_margin * 2 / daily_agg["total_notional"], 1.0)
    scale_arr = np.minimum(s_margin, s_notional)
    scale_s = pd.Series(scale_arr, index=daily_agg["pnl_date"])

    daily_temp = trades_df.groupby("pnl_date")["pnl_capital"].sum()
    daily_temp_scaled = daily_temp * scale_s.reindex(daily_temp.index, fill_value=1.0)
    d_pnl = daily_temp_scaled.reindex(all_dates.date, fill_value=0)
    a_ret = d_pnl.mean() * 252
    a_std = d_pnl.std() * np.sqrt(252)
    s = a_ret / a_std if a_std > 0 else 0
    c = d_pnl.cumsum()
    p = c.cummax()
    dd = (c - p).min()
    margin_usage = daily_agg["total_margin"].mean() * 100
    print(f"  保证金≤{max_margin*100:>4.0f}%: 年化 {a_ret*100:>7.2f}%  波动 {a_std*100:>6.2f}%  Sharpe {s:>5.2f}  MaxDD {dd*100:>6.2f}%  日均保证金 {margin_usage:.1f}%")

# ------------------------------------------------------------------
# 输出
# ------------------------------------------------------------------
print(f"\n{'=' * 60}")
print("组合表现（保证金≤80%）")
print(f"{'=' * 60}")
print(f"数据跨度: {all_dates[0].date()} ~ {all_dates[-1].date()}")
print(f"总日历日: {trading_days}")
print(f"有触发日: {active_days} ({active_days/trading_days*100:.1f}%)")
print(f"\n  年化收益:     {ann_ret*100:>8.2f}%")
print(f"  年化波动:     {ann_std*100:>8.2f}%")
print(f"  夏普比率:     {sharpe:>8.2f}")
print(f"  最大回撤:     {max_dd*100:>8.2f}%")
print(f"  Calmar 比率:  {calmar:>8.2f}")

print(f"\n{'=' * 60}")
print("按方向")
print(f"{'=' * 60}")
print(f"  多头: 年化 {long_daily.mean()*252*100:.2f}%  Sharpe {long_sharpe:.2f}")
print(f"  空头: 年化 {short_daily.mean()*252*100:.2f}%  Sharpe {short_sharpe:.2f}")

print(f"\n{'=' * 60}")
print("按 tier 分档")
print(f"{'=' * 60}")
print(tier_df.to_string(index=False))

print(f"\n{'=' * 60}")
print("口径对比")
print(f"{'=' * 60}")
print(f"  不考虑保证金（v1）:     年化 2.89%  Sharpe 2.90  MaxDD -1.06%")
print(f"  考虑保证金（v2, 80%）:  年化 {ann_ret*100:.2f}%  Sharpe {sharpe:.2f}  MaxDD {max_dd*100:.2f}%")
print(f"  等权平均（口径A）:       年化 16.32% Sharpe 2.24")

# 月度
trades_df["month"] = pd.to_datetime(trades_df["pnl_date"]).dt.to_period("M")
monthly = trades_df.groupby("month")["scaled_pnl"].sum()
print(f"\n{'=' * 60}")
print("月度收益")
print(f"{'=' * 60}")
for m, v in monthly.items():
    print(f"  {m}: {v*100:+.2f}%")

tier_df.to_csv(OUT_PATH, index=False)
print(f"\n保存: {OUT_PATH}")
