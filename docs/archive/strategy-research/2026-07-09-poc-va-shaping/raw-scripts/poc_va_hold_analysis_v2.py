#!/usr/bin/env python3
"""持仓期 vs IR 趋势分析：判断放宽是否有效"""

import pandas as pd
import numpy as np

SCAN_PATH = "project_data/ai_tmp/poc_va_shaping_scan_results.csv"
df = pd.read_csv(SCAN_PATH)
df = df[df["trail_mult"] == 0].copy()  # trailing 无效，排除

tiers = sorted(df["tier_v40"].unique())
bar_list = sorted(df["max_bars"].unique())

print("=" * 70)
print("持仓期 vs IR（每个持仓期取最优止损，无 trailing）")
print("=" * 70)

for tier in tiers:
    sub = df[df["tier_v40"] == tier].copy()
    best_per_bar = sub.groupby("max_bars", group_keys=False).apply(
        lambda g: g.loc[g["ir_net"].idxmax()]
    ).reset_index()

    print(f"\n--- {tier} ({best_per_bar.iloc[0]['direction']}) ---")
    print(f"{'持仓':>6} {'stop':>6} {'n':>5} {'net':>8} {'IR':>7} {'胜率':>5} {'止损率':>5}")

    best_ir = -999
    best_bars = 0
    for _, row in best_per_bar.iterrows():
        h = row["max_bars"] * 5 / 60
        print(f"  {h:>4.1f}h {row['stop_mult']:>5.1f} {int(row['n']):>5} {row['mean_net']:>+8.1f} {row['ir_net']:>7.3f} {row['hit_rate']:>4.0%} {row['stop_rate']:>4.0%}")
        if row["ir_net"] > best_ir:
            best_ir = row["ir_net"]
            best_bars = row["max_bars"]

    is_max = best_bars == max(bar_list)
    is_min = best_bars == min(bar_list)
    if is_max:
        print(f"  >>> 最优在右边界 ({best_bars*5/60:.1f}h)，放宽可能有效")
    elif is_min:
        print(f"  >>> 最优在左边界 ({best_bars*5/60:.1f}h)，应缩短")
    else:
        print(f"  >>> 最优在内部 ({best_bars*5/60:.1f}h)")

# 无止损版本（排除止损干扰）
print(f"\n{'=' * 70}")
print("无止损版本：纯持仓期 vs IR")
print("=" * 70)

df_nosl = df[df["stop_mult"] == 999].copy()

for tier in tiers:
    sub = df_nosl[df_nosl["tier_v40"] == tier].sort_values("max_bars").reset_index(drop=True)
    if len(sub) < 3:
        continue

    print(f"\n--- {tier} ({sub.iloc[0]['direction']}) ---")
    print(f"{'持仓':>6} {'n':>5} {'net':>8} {'IR':>7} {'胜率':>5}")
    for _, row in sub.iterrows():
        h = row["max_bars"] * 5 / 60
        print(f"  {h:>4.1f}h {int(row['n']):>5} {row['mean_net']:>+8.1f} {row['ir_net']:>7.3f} {row['hit_rate']:>4.0%}")

    # 最后 3 个点的趋势
    last3_ir = sub.tail(3)["ir_net"].values
    if len(last3_ir) >= 3:
        if last3_ir[-1] > last3_ir[-2] > last3_ir[-3]:
            trend = "持续上升 ⬆⬆"
        elif last3_ir[-1] > last3_ir[-2]:
            trend = "尾部回升 ⬆"
        elif last3_ir[-1] < last3_ir[-2] < last3_ir[-3]:
            trend = "持续下降 ⬇⬇"
        else:
            trend = "平缓/波动 →"
    else:
        trend = "数据不足"

    best_bars = sub.loc[sub["ir_net"].idxmax(), "max_bars"]
    if best_bars == max(bar_list):
        print(f"  >>> 最优=10h, 尾部趋势={trend}")
    else:
        print(f"  >>> 最优={best_bars*5/60:.1f}h（内部）, 尾部趋势={trend}")
