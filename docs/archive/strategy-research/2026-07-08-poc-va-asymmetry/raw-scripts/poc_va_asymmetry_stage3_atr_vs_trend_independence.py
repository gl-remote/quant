"""
文件级元信息：
- 创建背景：用户直觉——ATR regime 可能是"趋势兑现程度"的代理。
  若 ATR 和 trend rank 高度相关 · 则我们的 filter 存在变量冗余。
- 用途：
    (1) 计算 atr_rank_roll 和 trend_rank_roll 的 Spearman/Pearson 相关
    (2) 计算 |trend_rank - 0.5| 与 atr_rank 的相关（"趋势极端度"vs"波动"）
    (3) 3×3 交叉表 · 看联合分布
    (4) 分品种独立算相关 · 排除跨合约混淆
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import prepare_dataset  # noqa: E402


def main():
    print("=" * 100)
    print("ATR regime vs Trend rank · 变量独立性验证")
    print("=" * 100)

    df = prepare_dataset()
    df = df.dropna(subset=["atr_rank_roll", "trend_rank_roll"])
    print(f"\n有效事件: n={len(df)} · 合约: {df['contract'].nunique()}")

    # 1. Pool 层面的原始相关
    print("\n" + "=" * 90)
    print("1. Pool 层面 · atr_rank_roll vs trend_rank_roll 相关性")
    print("=" * 90)
    sp = stats.spearmanr(df["atr_rank_roll"], df["trend_rank_roll"])
    pe = stats.pearsonr(df["atr_rank_roll"], df["trend_rank_roll"])
    print(f"  Spearman: r={sp.statistic:+.4f} · p={sp.pvalue:.4g}")
    print(f"  Pearson:  r={pe.statistic:+.4f} · p={pe.pvalue:.4g}")
    print(f"  判读：|r| < 0.10 = 完全独立；0.10-0.30 = 弱相关；>0.30 = 强相关")

    # 2. "趋势极端度" vs atr
    df["trend_extremity"] = (df["trend_rank_roll"] - 0.5).abs()
    print("\n" + "=" * 90)
    print("2. atr_rank vs 趋势极端度 |trend_rank - 0.5|")
    print("=" * 90)
    sp2 = stats.spearmanr(df["atr_rank_roll"], df["trend_extremity"])
    pe2 = stats.pearsonr(df["atr_rank_roll"], df["trend_extremity"])
    print(f"  Spearman: r={sp2.statistic:+.4f} · p={sp2.pvalue:.4g}")
    print(f"  Pearson:  r={pe2.statistic:+.4f} · p={pe2.pvalue:.4g}")
    print("  假设：若 ATR ≈ 趋势极端度 · 则 r > +0.3（趋势越极端 · ATR 越高）")

    # 3. 3x3 交叉表 (n)
    print("\n" + "=" * 90)
    print("3. 3×3 交叉表 · atr_bucket × trend_bucket 事件数")
    print("=" * 90)
    df["atr_b"] = pd.cut(df["atr_rank_roll"], bins=[-.01, .33, .67, 1.01],
                          labels=["低", "中", "高"])
    df["trend_b"] = pd.cut(df["trend_rank_roll"], bins=[-.01, .33, .67, 1.01],
                            labels=["跌", "平", "涨"])
    ct = pd.crosstab(df["atr_b"], df["trend_b"])
    ct_pct = ct.div(len(df)) * 100
    print("\n事件数：")
    print(ct)
    print("\n占比 %：")
    print(ct_pct.round(1))

    # 卡方独立性
    chi2, p_chi, _, expected = stats.chi2_contingency(ct)
    print(f"\n卡方独立性检验：chi2={chi2:.2f} · p={p_chi:.4g}")
    if p_chi < 0.05:
        print("  ⚠️ 拒绝独立性假设 · atr 和 trend 相关")
    else:
        print("  ✅ 无法拒绝独立性 · atr 和 trend 独立")

    # 若完全独立 · 每格应占 1/9 = 11.1%
    print("\n期望占比（独立情况下）：")
    exp_df = pd.DataFrame(expected / len(df) * 100,
                          index=ct.index, columns=ct.columns)
    print(exp_df.round(1))

    print("\n实际 - 期望（%）：")
    diff = ct_pct.values - exp_df.values
    diff_df = pd.DataFrame(diff, index=ct.index, columns=ct.columns)
    print(diff_df.round(1))

    # 4. 分品种独立相关
    print("\n" + "=" * 90)
    print("4. 分品种独立相关（排除跨合约混淆）")
    print("=" * 90)
    df["prefix"] = df["contract"].str.extract(r"^([A-Za-z]+)")
    rows = []
    for p, g in df.groupby("prefix"):
        if len(g) < 100:
            continue
        r = stats.spearmanr(g["atr_rank_roll"], g["trend_rank_roll"])
        rows.append({"prefix": p, "n": len(g), "spearman_r": r.statistic, "p": r.pvalue})
    per_sym = pd.DataFrame(rows).sort_values("spearman_r")
    print(f"\n{'品种':6s} {'n':>6s} {'Spearman r':>12s} {'p':>10s}")
    for _, r in per_sym.iterrows():
        marker = "⚠️" if abs(r["spearman_r"]) > 0.15 else "✅"
        print(f"  {r['prefix']:6s} {int(r['n']):>6d} {r['spearman_r']:>+12.3f} {r['p']:>10.4g} {marker}")

    med = per_sym["spearman_r"].median()
    mean_r = per_sym["spearman_r"].mean()
    print(f"\n跨品种 Spearman r · 中位数 {med:+.3f} · 均值 {mean_r:+.3f}")
    if abs(mean_r) < 0.10:
        print("✅ 跨品种平均 · atr 和 trend 独立")
    elif abs(mean_r) < 0.20:
        print("⚠️ 弱相关 · 但不足以称为冗余")
    else:
        print("❗ 强相关 · 存在变量冗余风险")

    # 5. atr 是否是"趋势方向"的代理？
    print("\n" + "=" * 90)
    print("5. atr 是否偏向单方向趋势？")
    print("=" * 90)
    print(f"\n{'atr 分档':6s} {'均值 trend_rank':>15s} {'std':>8s} {'跌段占比':>10s} {'涨段占比':>10s}")
    for atr_b in ["低", "中", "高"]:
        seg = df[df["atr_b"] == atr_b]
        tr_mean = seg["trend_rank_roll"].mean()
        tr_std = seg["trend_rank_roll"].std()
        p_down = (seg["trend_rank_roll"] <= 0.33).mean()
        p_up = (seg["trend_rank_roll"] >= 0.67).mean()
        print(f"  {atr_b:6s} {tr_mean:>+15.3f} {tr_std:>8.3f} {p_down:>10.1%} {p_up:>10.1%}")

    print("\n判读：若 atr 是趋势代理 · 高 ATR 应集中在跌段（跌快于涨 · 波动大）")


if __name__ == "__main__":
    main()
