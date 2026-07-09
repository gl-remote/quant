#!/usr/bin/env python3
"""
poc_va 整点开仓策略 · 年化收益与夏普粗算

基于 poc_va_cost_net_quick.detail.csv 的逐笔明细，按日聚合后计算年化指标。

口径说明：
- 每事件投入等名义价值（标准化为 1 单位）
- 空仓日收益 = 0（资金闲置）
- 多事件同日触发时，组合收益 = 当日各事件收益的平均（等权）
- 年化 = 日收益 × 252，年化波动 = 日收益标准差 × √252

用法:
    cd /Users/gaolei/Documents/src/quant
    unset PYTHONHOME && unset PYTHONPATH && uv run python scripts/ai_tmp/poc_va_annual_sharpe_quick.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

import pandas as pd
import numpy as np

# ------------------------------------------------------------------
# 0. 路径
# ------------------------------------------------------------------
DETAIL_PATH = Path("project_data/ai_tmp/poc_va_cost_net_quick.detail.csv")
OUT_PATH = Path("project_data/ai_tmp/poc_va_annual_sharpe_quick.csv")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 1. 读取明细
# ------------------------------------------------------------------
df = pd.read_csv(DETAIL_PATH, parse_dates=["event_time"])
df["date"] = df["event_time"].dt.date
df["net_ret"] = df["net_bps"] / 10000  # 转换为小数收益率

print(f"明细事件数: {len(df)}")
print(f"交易日期数: {df['date'].nunique()}")
print(f"合约数: {df['contract'].nunique()}")

# ------------------------------------------------------------------
# 2. 按日聚合（等权平均当日所有触发事件的收益）
# ------------------------------------------------------------------
daily = df.groupby("date").agg(
    n_events=("net_ret", "count"),
    avg_ret=("net_ret", "mean"),   # 当日等权平均收益
    sum_ret=("net_ret", "sum"),    # 当日总收益（等权累加）
).reset_index()

# 补齐所有日期（空仓日 = 0 收益）
all_dates = pd.date_range(start=df["event_time"].min().normalize(),
                          end=df["event_time"].max().normalize(),
                          freq="D")
daily_full = pd.DataFrame({"date": all_dates.date})
daily_full = daily_full.merge(daily, on="date", how="left")
daily_full["n_events"] = daily_full["n_events"].fillna(0).astype(int)
daily_full["avg_ret"] = daily_full["avg_ret"].fillna(0)
daily_full["sum_ret"] = daily_full["sum_ret"].fillna(0)

# ------------------------------------------------------------------
# 3. 计算年化指标（两种口径）
# ------------------------------------------------------------------
trading_days = len(daily_full)
active_days = daily_full["n_events"].gt(0).sum()

# 口径 A：等权平均收益（每日收益 = 当日触发事件的平均收益，空仓=0）
daily_avg = daily_full["avg_ret"]
annual_return_avg = daily_avg.mean() * 252
annual_std_avg = daily_avg.std() * np.sqrt(252)
sharpe_avg = annual_return_avg / annual_std_avg if annual_std_avg > 0 else np.nan

# 口径 B：累加收益（每日收益 = 当日所有事件收益之和，空仓=0）
# 这假设每事件固定名义价值，多事件=多倍暴露
daily_sum = daily_full["sum_ret"]
annual_return_sum = daily_sum.mean() * 252
annual_std_sum = daily_sum.std() * np.sqrt(252)
sharpe_sum = annual_return_sum / annual_std_sum if annual_std_sum > 0 else np.nan

# ------------------------------------------------------------------
# 4. 按 tier 分档计算
# ------------------------------------------------------------------
tier_results = []
for tier in df["tier"].unique():
    sub = df[df["tier"] == tier].copy()
    sub["date"] = sub["event_time"].dt.date
    sub_daily = sub.groupby("date")["net_ret"].mean().reindex(all_dates.date, fill_value=0)

    ann_ret = sub_daily.mean() * 252
    ann_std = sub_daily.std() * np.sqrt(252)
    tier_results.append({
        "tier": tier,
        "n_events": len(sub),
        "active_days": sub["date"].nunique(),
        "avg_events_per_active_day": len(sub) / sub["date"].nunique(),
        "annual_return": ann_ret,
        "annual_std": ann_std,
        "sharpe": ann_ret / ann_std if ann_std > 0 else np.nan,
        "max_daily_events": sub.groupby("date").size().max(),
    })

tier_df = pd.DataFrame(tier_results).sort_values("sharpe", ascending=False)

# ------------------------------------------------------------------
# 5. 输出
# ------------------------------------------------------------------
print("\n" + "=" * 70)
print("整点开仓策略 · 年化收益与夏普粗算")
print("=" * 70)

print(f"\n数据跨度: {daily_full['date'].min()} ~ {daily_full['date'].max()}")
print(f"总日历日: {trading_days}")
print(f"有触发日: {active_days} ({active_days/trading_days*100:.1f}%)")
print(f"平均每触发日事件数: {daily['n_events'].mean():.1f}")
print(f"最大单日事件数: {daily['n_events'].max()}")

print(f"\n{'=' * 70}")
print("口径 A：每日等权平均收益（空仓=0）")
print(f"{'=' * 70}")
print(f"  日平均收益: {daily_avg.mean()*100:.4f}%")
print(f"  日收益标准差: {daily_avg.std()*100:.4f}%")
print(f"  年化收益: {annual_return_avg*100:.2f}%")
print(f"  年化波动: {annual_std_avg*100:.2f}%")
print(f"  夏普比率: {sharpe_avg:.2f}")

print(f"\n{'=' * 70}")
print("口径 B：每日累加收益（多事件=多倍暴露，空仓=0）")
print(f"{'=' * 70}")
print(f"  日平均收益: {daily_sum.mean()*100:.4f}%")
print(f"  日收益标准差: {daily_sum.std()*100:.4f}%")
print(f"  年化收益: {annual_return_sum*100:.2f}%")
print(f"  年化波动: {annual_std_sum*100:.2f}%")
print(f"  夏普比率: {sharpe_sum:.2f}")

print(f"\n{'=' * 70}")
print("按 tier 分档（口径 A）")
print(f"{'=' * 70}")
print(tier_df.to_string(index=False))

# ------------------------------------------------------------------
# 6. 不同资金假设下的组合夏普
# ------------------------------------------------------------------
print(f"\n{'=' * 70}")
print("不同资金假设下的组合表现")
print(f"{'=' * 70}")

# 假设账户资金 = N × 单事件名义价值
# 每事件固定名义价值 = close_t × size，但我们已经标准化了
# 这里用"同时开仓的最大事件数"来估计资金需求
max_concurrent = daily["n_events"].max()
print(f"历史最大同时开仓事件数: {max_concurrent}")

for multiplier in [1, 2, 5, 10, max_concurrent]:
    # 假设账户资金 = multiplier × 单事件名义价值
    # 日收益率 = sum_ret / multiplier
    scaled_ret = daily_sum / multiplier
    ann_ret = scaled_ret.mean() * 252
    ann_std = scaled_ret.std() * np.sqrt(252)
    sharpe = ann_ret / ann_std if ann_std > 0 else np.nan
    print(f"  资金= {multiplier:>3}×单事件: 年化收益 {ann_ret*100:>7.2f}%  波动 {ann_std*100:>6.2f}%  Sharpe {sharpe:>5.2f}")

# ------------------------------------------------------------------
# 7. 保存
# ------------------------------------------------------------------
tier_df.to_csv(OUT_PATH, index=False)
print(f"\n保存: {OUT_PATH}")
