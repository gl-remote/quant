#!/usr/bin/env python3
"""
poc-va 风控口径 · 年化收益与夏普

风控规则:
  1. 所有 A 级信号都下注（不筛选）
  2. 单信号最大亏损 ≤ 总资本 2%（止损 + 成本后）
  3. 同时持有风险暴露 ≤ 总资本 12%
  4. 仓位计算：根据止损距离反算手数，使止损金额 = 2% × 总资本
     如果按此手数计算的风险暴露超过 12%，则缩减手数至 12% 约束
  5. 可用资金 = 总资金量（即不需要预留保证金之外的空闲资金）
  6. 总资本标准化为 1.0

等价于:
  - 每笔交易仓位 = min(2% / 止损距离%, 12% / 已用风险暴露的剩余)
  - 日收益 = Σ(仓位_i × net_ret_i)，sum over all active positions that closed today

输入:
  基于扫描最优塑形参数的逐笔模拟结果（在脚本内重新计算）

输出:
  project_data/ai_tmp/poc_va_risk_managed_sharpe.csv
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
OUT_PATH = Path("project_data/ai_tmp/poc_va_risk_managed_sharpe.csv")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 风控参数
# ------------------------------------------------------------------
MAX_LOSS_PCT = 0.02     # 单信号最大亏损 = 2% 总资本
MAX_RISK_PCT = 0.12     # 同时持有风险暴露 ≤ 12% 总资本
TOTAL_CAPITAL = 1.0     # 标准化总资本

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
# 逐合约模拟：计算每笔交易的实际持仓期和每日 P&L
# ------------------------------------------------------------------
print("逐合约模拟（每日 P&L 模式）...")
all_trade_daily_pnl = []

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

        # 仓位计算：使止损亏损 = MAX_LOSS_PCT
        # position_size = MAX_LOSS_PCT / stop_dist_pct（占总资本的比例）
        raw_position = MAX_LOSS_PCT / stop_dist_pct
        # 但 position 不能超过 1.0（不可能投入超过总资本）
        position = min(raw_position, 1.0)

        idx = bars["datetime"].searchsorted(entry_time)
        future = bars.iloc[idx:idx + max_bars]

        if len(future) == 0:
            continue

        # 逐日计算 P&L
        entry_date = entry_time.date()
        prev_close = entry_price

        for bar_i in range(len(future)):
            bar = future.iloc[bar_i]
            bar_time = bar["datetime"]
            bar_date = bar_time.date()

            # 止损检查
            if direction == 1 and bar["low"] <= stop_price:
                exit_price = stop_price
                pnl_pct = direction * (exit_price - entry_price) / entry_price
                net_pnl = position * (pnl_pct * 10000 - cost_bps) / 10000
                all_trade_daily_pnl.append({
                    "contract": contract,
                    "tier_v40": tier_v40,
                    "direction": ev["direction"],
                    "entry_time": entry_time,
                    "pnl_date": bar_date,
                    "position": position,
                    "stop_dist_pct": stop_dist_pct,
                    "net_pnl": net_pnl,  # 占总资本的比例
                    "exit_reason": "stop",
                })
                break

            if direction == -1 and bar["high"] >= stop_price:
                exit_price = stop_price
                pnl_pct = direction * (exit_price - entry_price) / entry_price
                net_pnl = position * (pnl_pct * 10000 - cost_bps) / 10000
                all_trade_daily_pnl.append({
                    "contract": contract,
                    "tier_v40": tier_v40,
                    "direction": ev["direction"],
                    "entry_time": entry_time,
                    "pnl_date": bar_date,
                    "position": position,
                    "stop_dist_pct": stop_dist_pct,
                    "net_pnl": net_pnl,
                    "exit_reason": "stop",
                })
                break

            # 时间退出：最后一个 bar
            if bar_i == len(future) - 1:
                exit_price = bar["close"]
                pnl_pct = direction * (exit_price - entry_price) / entry_price
                net_pnl = position * (pnl_pct * 10000 - cost_bps) / 10000
                all_trade_daily_pnl.append({
                    "contract": contract,
                    "tier_v40": tier_v40,
                    "direction": ev["direction"],
                    "entry_time": entry_time,
                    "pnl_date": bar_date,
                    "position": position,
                    "stop_dist_pct": stop_dist_pct,
                    "net_pnl": net_pnl,
                    "exit_reason": "time",
                })
                break

pnl_df = pd.DataFrame(all_trade_daily_pnl)
print(f"PnL 记录数: {len(pnl_df)}")

# ------------------------------------------------------------------
# 应用 12% 风险暴露上限
# ------------------------------------------------------------------
# 每日所有 active position 的 sum，如果超过 12%，按比例缩减
daily_position = pnl_df.groupby("pnl_date")["position"].sum().reset_index()
daily_position.columns = ["pnl_date", "total_position"]

# 缩放因子
daily_position["scale"] = np.where(
    daily_position["total_position"] > MAX_RISK_PCT,
    MAX_RISK_PCT / daily_position["total_position"],
    1.0
)

# merge 回 pnl_df
pnl_df = pnl_df.merge(daily_position[["pnl_date", "scale"]], on="pnl_date", how="left")
pnl_df["scaled_pnl"] = pnl_df["net_pnl"] * pnl_df["scale"]

print(f"\n风控统计:")
print(f"  总交易数: {len(pnl_df)}")
print(f"  交易日数: {pnl_df['pnl_date'].nunique()}")
print(f"  触发缩减的交易日: {(daily_position['scale'] < 1.0).sum()} ({(daily_position['scale'] < 1.0).mean()*100:.1f}%)")
print(f"  平均缩减因子: {daily_position['scale'].mean():.4f}")
print(f"  最小缩减因子: {daily_position['scale'].min():.4f}")
print(f"  日均总仓位: {daily_position['total_position'].mean():.4f}")

# ------------------------------------------------------------------
# 按日聚合
# ------------------------------------------------------------------
daily_pnl = pnl_df.groupby("pnl_date")["scaled_pnl"].sum()

all_dates = pd.date_range(
    start=min(pnl_df["pnl_date"]),
    end=max(pnl_df["pnl_date"]),
    freq="D"
)
daily_full = daily_pnl.reindex(all_dates.date, fill_value=0)

trading_days = len(daily_full)
active_days = (daily_full != 0).sum()

ann_ret = daily_full.mean() * 252
ann_std = daily_full.std() * np.sqrt(252)
sharpe = ann_ret / ann_std if ann_std > 0 else 0

# 最大回撤
cum = daily_full.cumsum()
peak = cum.cummax()
drawdown = cum - peak
max_dd = drawdown.min()

# Calmar ratio
calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0

# ------------------------------------------------------------------
# 按 tier 分档
# ------------------------------------------------------------------
tier_results = []
for tier in sorted(pnl_df["tier_v40"].unique()):
    sub = pnl_df[pnl_df["tier_v40"] == tier]
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
        "avg_position": sub["position"].mean(),
        "avg_scale": sub["scale"].mean(),
        "annual_return": t_ann_ret,
        "annual_std": t_ann_std,
        "sharpe": t_ann_ret / t_ann_std if t_ann_std > 0 else 0,
        "max_dd": t_dd,
        "calmar": t_ann_ret / abs(t_dd) if t_dd != 0 else 0,
    })
tier_df = pd.DataFrame(tier_results)

# ------------------------------------------------------------------
# 多空分开
# ------------------------------------------------------------------
long_daily = pnl_df[pnl_df["direction"] == "long"].groupby("pnl_date")["scaled_pnl"].sum().reindex(all_dates.date, fill_value=0)
short_daily = pnl_df[pnl_df["direction"] == "short"].groupby("pnl_date")["scaled_pnl"].sum().reindex(all_dates.date, fill_value=0)

long_sharpe = long_daily.mean() * 252 / (long_daily.std() * np.sqrt(252)) if long_daily.std() > 0 else 0
short_sharpe = short_daily.mean() * 252 / (short_daily.std() * np.sqrt(252)) if short_daily.std() > 0 else 0

# ------------------------------------------------------------------
# 输出
# ------------------------------------------------------------------
print(f"\n{'=' * 70}")
print("风控口径 · 年化收益与夏普")
print(f"{'=' * 70}")
print(f"风控规则: 单信号止损 ≤ {MAX_LOSS_PCT*100:.0f}% · 同时暴露 ≤ {MAX_RISK_PCT*100:.0f}%")

print(f"\n数据跨度: {all_dates[0].date()} ~ {all_dates[-1].date()}")
print(f"总日历日: {trading_days}")
print(f"有触发日: {active_days} ({active_days/trading_days*100:.1f}%)")

print(f"\n{'=' * 70}")
print("组合表现")
print(f"{'=' * 70}")
print(f"  年化收益:     {ann_ret*100:>8.2f}%")
print(f"  年化波动:     {ann_std*100:>8.2f}%")
print(f"  夏普比率:     {sharpe:>8.2f}")
print(f"  最大回撤:     {max_dd*100:>8.2f}%")
print(f"  Calmar 比率:  {calmar:>8.2f}")

print(f"\n{'=' * 70}")
print("按方向")
print(f"{'=' * 70}")
print(f"  多头: 年化 {long_daily.mean()*252*100:.2f}%  Sharpe {long_sharpe:.2f}")
print(f"  空头: 年化 {short_daily.mean()*252*100:.2f}%  Sharpe {short_sharpe:.2f}")

print(f"\n{'=' * 70}")
print("按 tier 分档")
print(f"{'=' * 70}")
print(tier_df.to_string(index=False))

# 与其他口径对比
print(f"\n{'=' * 70}")
print("口径对比")
print(f"{'=' * 70}")
print(f"  等权平均（口径A）:    年化 16.32%  Sharpe 2.24")
print(f"  累加（口径B）:        年化 138.47% Sharpe 2.21")
print(f"  风控口径（本次）:      年化 {ann_ret*100:.2f}%  Sharpe {sharpe:.2f}  MaxDD {max_dd*100:.2f}%")

# ------------------------------------------------------------------
# 月度收益热力图数据
# ------------------------------------------------------------------
pnl_df["month"] = pd.to_datetime(pnl_df["pnl_date"]).dt.to_period("M")
monthly = pnl_df.groupby("month")["scaled_pnl"].sum()
print(f"\n{'=' * 70}")
print("月度收益")
print(f"{'=' * 70}")
for m, v in monthly.items():
    print(f"  {m}: {v*100:+.2f}%")

tier_df.to_csv(OUT_PATH, index=False)
print(f"\n保存: {OUT_PATH}")
