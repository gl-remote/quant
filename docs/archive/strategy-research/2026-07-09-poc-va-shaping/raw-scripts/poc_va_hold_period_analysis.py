#!/usr/bin/env python3
"""
分析持仓期与收益的关系：最优是否在边界上？

读取 poc_va_shaping_scan_results.csv，对每个 tier 绘制
max_bars vs IR / mean_net 的趋势，判断是否有"更长更好"的迹象。

如果最优在边界（10h），说明放宽可能有效。
如果最优在内部（如 6h），说明已经是最优。
"""

import pandas as pd
import numpy as np

SCAN_PATH = "project_data/ai_tmp/poc_va_shaping_scan_results.csv"
df = pd.read_csv(SCAN_PATH)

# 只看无 trailing 的结果（trailing 无效，避免噪声）
df = df[df["trail_mult"] == 0].copy()

# 只看 stop_mult = 999（无止损）和各 stop 的最优
# 但为了简化，固定取每个 tier 最常用的 stop_mult

# 按 tier 分组，绘制 max_bars vs IR
tiers = sorted(df["tier_v40"].unique())
bars_hours = df["max_bars"].unique()
bars_hours = sorted(bars_hours)
bars_labels = [f"{b*5/60:.1f}h" for b in bars_hours]

print("=" * 70)
print("持仓期 vs IR（固定止损=最优，无 trailing）")
print("=" * 70)

for tier in tiers:
    sub = df[(df["tier_v40"] == tier)]
    # 对每个 max_bars，取所有 stop_mult 中 IR 最高的
    best_per_bar = sub.groupby("max_bars").apply(lambda g: g.loc[g["ir_net"].idxmax()]).reset_index(drop=True)
    # groupby 后 max_bars 变成了 index
    best_per_bar = best_per_bar.reset_index()
    if "max_bars" not in best_per_bar.columns:
        best_per_bar.rename(columns={"level_0": "max_bars"}, inplace=True, errors="ignore")

    print(f"\n--- {tier} (方向: {best_per_bar.iloc[0]['direction']}) ---")
    print(f"{'持仓期':>8} {'n':>6} {'stop':>6} {'net_mean':>10} {'IR':>8} {'胜率':>6} {'止损率':>6}")
    best_ir = -999
    best_bars = 0
    for _, row in best_per_bar.iterrows():
        h = row["max_bars"] * 5 / 60
        print(f"  {h:>5.1f}h  {int(row['n']):>6} {row['stop_mult']:>5.1f}  {row['mean_net']:>+10.1f}  {row['ir_net']:>8.3f}  {row['hit_rate']:>5.1%}  {row['stop_rate']:>5.1%}")
        if row["ir_net"] > best_ir:
            best_ir = row["ir_net"]
            best_bars = row["max_bars"]

    # 判断是否在边界
    if best_bars == max(bars_hours):
        print(f"  >>> 最优在右边界 ({best_bars*5/60:.1f}h)，放宽可能有效")
    elif best_bars == min(bars_hours):
        print(f"  >>> 最优在左边界 ({best_bars*5/60:.1f}h)，缩短可能有效")
    else:
        print(f"  >>> 最优在内部 ({best_bars*5/60:.1f}h)，当前已是最优区间")

# 额外分析：无止损版本的趋势（排除止损干扰）
print(f"\n{'=' * 70}")
print("持仓期 vs IR（无止损 + 无 trailing）")
print(f"{'=' * 70}")

df_nosl = df[df["stop_mult"] == 999].copy()

for tier in tiers:
    sub = df_nosl[df_nosl["tier_v40"] == tier].sort_values("max_bars")
    if len(sub) == 0:
        continue

    print(f"\n--- {tier} ---")
    print(f"{'持仓期':>8} {'n':>6} {'net_mean':>10} {'IR':>8} {'胜率':>6}")
    best_ir = -999
    best_bars = 0
    for _, row in sub.iterrows():
        h = row["max_bars"] * 5 / 60
        print(f"  {h:>5.1f}h  {int(row['n']):>6} {row['mean_net']:>+10.1f}  {row['ir_net']:>8.3f}  {row['hit_rate']:>5.1%}")
        if row["ir_net"] > best_ir:
            best_ir = row["ir_net"]
            best_bars = row["max_bars"]

    if best_bars == max(bars_hours):
        print(f"  >>> 最优在右边界，放宽持仓期可能有提升")
    else:
        print(f"  >>> 最优在 {best_bars*5/60:.1f}h")

# 汇总判断
print(f"\n{'=' * 70}")
print("结论汇总")
print(f"{'=' * 70}")
for tier in tiers:
    sub = df[df["tier_v40"] == tier]
    no_sl = sub[sub["stop_mult"] == 999].sort_values("max_bars")
    if len(no_sl) < 2:
        continue

    # 看最后两个点的趋势
    last2 = no_sl.tail(2)
    rising = last2.iloc[-1]["ir_net"] > last2.iloc[-2]["ir_net"]
    boundary = no_sl.iloc[-1]["max_bars"] == max(bars_hours)
    best_at_max = no_sl.loc[no_sl["ir_net"].idxmax(), "max_bars"] == max(bars_hours)

    tier_short = tier
    direction = "多头" if tier.startswith("L_") else "空头"
    if best_at_max and rising:
        print(f"  {tier_short} ({direction}): IR 在 10h 仍在上升 → 放宽有效 ⬆")
    elif best_at_max and not rising:
        print(f"  {tier_short} ({direction}): IR 在 10h 为最优但已平缓 → 放宽可能无效 →")
    else:
        print(f"  {tier_short} ({direction}): IR 在内部已最优 → 不需要放宽 ✕")
