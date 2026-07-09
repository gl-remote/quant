#!/usr/bin/env python3
"""
poc_va 整点开仓策略 · 成本后收益粗算

用法:
    cd /Users/gaolei/Documents/src/quant
    unset PYTHONHOME && unset PYTHONPATH && uv run python scripts/ai_tmp/poc_va_cost_net_quick.py

输入:
    project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet

输出:
    project_data/ai_tmp/poc_va_cost_net_quick.csv
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
DATA_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet")
OUT_PATH = Path("project_data/ai_tmp/poc_va_cost_net_quick.csv")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 1. 读取数据
# ------------------------------------------------------------------
df = pd.read_parquet(DATA_PATH)
print(f"总事件数: {len(df)}")
print(f"合约数: {df['contract'].nunique()}")

# ------------------------------------------------------------------
# 2. v4.0 分类器规则（6 类合并版）
# ------------------------------------------------------------------
def classify_v40(row):
    """返回 (tier, direction) 或 (None, None)"""
    sk = row["signed_skew_rank_roll"]
    atr = row["atr_rank_roll"]
    tr = row["trend_rank_roll"]

    # 多头 3 类（trend >= 0.75）
    if tr >= 0.75:
        if 0.09 < sk <= 0.30 and atr <= 0.67:
            return "L_seg3_lowmid_up", "long"
        if 0.0 <= sk <= 0.19 and atr > 0.67:
            return "L_seg12_high_up", "long"

    # L_seg2_low_flat: skew ∈ (0.09, 0.19] · ATR ≤ 0.33 · trend ∈ (0.20, 0.75)
    if 0.09 < sk <= 0.19 and atr <= 0.33 and 0.20 < tr < 0.75:
        return "L_seg2_low_flat", "long"

    # 空头 3 类（trend ≤ 0.20，除 L_seg2_low_flat 外）
    if tr <= 0.20:
        if sk >= 0.81 and atr > 0.67:
            return "S_seg12_high_dn", "short"
        if 0.60 < sk <= 0.81 and atr > 0.67:
            return "S_seg34_high_dn", "short"
        if 0.81 < sk <= 0.91 and 0.33 < atr <= 0.67:
            return "S_seg2_mid_dn", "short"

    return None, None

# 应用分类
tiers = df.apply(classify_v40, axis=1)
df["tier"] = [t[0] for t in tiers]
df["direction"] = [t[1] for t in tiers]

# ------------------------------------------------------------------
# 3. 成本计算（realistic-cost）
# ------------------------------------------------------------------
def compute_cost_bps(row):
    """双边总成本（开仓+平仓）按名义价值归一化为 bps"""
    contract = row["contract"]
    price = row["close_t"]
    spec = CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return np.nan

    # 单边手续费 + 滑点
    comm = spec.total_commission(price=price, lots=1)
    slip = spec.slippage(lots=1)
    one_way_cost = comm + slip

    # 双边（开+平）
    total_cost = 2 * one_way_cost

    # 名义价值
    notional = price * spec.size

    # bps = cost / notional * 10000
    cost_bps = total_cost / notional * 10000
    return cost_bps

df["cost_bps"] = df.apply(compute_cost_bps, axis=1)

# 统计成本分布
print(f"\n成本统计 (bps):")
print(df["cost_bps"].describe())

# ------------------------------------------------------------------
# 4. 收益计算
# ------------------------------------------------------------------
# 多头用 8h 收益，空头用 4h 收益
df["gross_bps"] = np.where(
    df["direction"] == "long",
    df["ret_8h_bps"],
    np.where(df["direction"] == "short", df["short_pnl_4h_bps"], np.nan)
)

df["net_bps"] = df["gross_bps"] - df["cost_bps"]

# ------------------------------------------------------------------
# 5. 按 tier 汇总（full period = stable + trans 全部计入）
# ------------------------------------------------------------------
results = []
for tier in ["L_seg3_lowmid_up", "L_seg12_high_up", "L_seg2_low_flat",
             "S_seg12_high_dn", "S_seg34_high_dn", "S_seg2_mid_dn"]:
    sub = df[df["tier"] == tier].copy()
    if len(sub) == 0:
        continue

    direction = sub["direction"].iloc[0]
    results.append({
        "tier": tier,
        "direction": direction,
        "n": len(sub),
        "trigger_rate": len(sub) / len(df),
        "mean_gross_bps": sub["gross_bps"].mean(),
        "mean_cost_bps": sub["cost_bps"].mean(),
        "mean_net_bps": sub["net_bps"].mean(),
        "std_net_bps": sub["net_bps"].std(),
        "hit_rate": (sub["net_bps"] > 0).mean(),
        "ir_net": sub["net_bps"].mean() / sub["net_bps"].std() if sub["net_bps"].std() > 0 else np.nan,
        "median_net_bps": sub["net_bps"].median(),
        "min_net_bps": sub["net_bps"].min(),
        "max_net_bps": sub["net_bps"].max(),
    })

summary = pd.DataFrame(results)

# ------------------------------------------------------------------
# 6. 总体汇总
# ------------------------------------------------------------------
all_long = df[df["direction"] == "long"]["net_bps"].dropna()
all_short = df[df["direction"] == "short"]["net_bps"].dropna()
all_traded = df[df["tier"].notna()]["net_bps"].dropna()

print("\n" + "=" * 70)
print("整点开仓策略 · 成本后收益粗算（v4.0 全 tier · full period）")
print("=" * 70)
print(summary.to_string(index=False))

print(f"\n{'=' * 70}")
print("总体汇总")
print(f"{'=' * 70}")
print(f"多头总事件: {len(all_long):>6}  平均 net: {all_long.mean():>8.2f} bps  IR: {all_long.mean()/all_long.std():>5.2f}")
print(f"空头总事件: {len(all_short):>6}  平均 net: {all_short.mean():>8.2f} bps  IR: {all_short.mean()/all_short.std():>5.2f}")
print(f"任一方向总: {len(all_traded):>6}  平均 net: {all_traded.mean():>8.2f} bps  IR: {all_traded.mean()/all_traded.std():>5.2f}")
print(f"触发率: {len(all_traded)/len(df)*100:.2f}%")

# ------------------------------------------------------------------
# 7. 保存明细 + 汇总
# ------------------------------------------------------------------
# 只保存有 tier 的事件明细
detail = df[df["tier"].notna()][["contract", "event_time", "tier", "direction",
                                   "close_t", "gross_bps", "cost_bps", "net_bps"]].copy()
detail.to_csv(OUT_PATH.with_suffix(".detail.csv"), index=False)
summary.to_csv(OUT_PATH, index=False)

print(f"\n汇总保存: {OUT_PATH}")
print(f"明细保存: {OUT_PATH.with_suffix('.detail.csv')}")
