"""
文件级元信息：
- 创建背景：阶段 4 · Step 2 品保只 60-70% · 猜测不同品种需要不同参数
- 用途：快速诊断 · 每个品种的最佳 skew/atr 组合是否一致
- 注意事项：只做描述性 · 不做严格判决 · 目的是发现品种特性
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage4_data_full import prepare_dataset_full  # noqa: E402

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4"
)


def parse_prefix(contract: str) -> str:
    """从 contract 提取品种前缀 · e.g. DCE.m2609 → DCE.m"""
    exchange, code = contract.split(".")
    prefix = "".join(c for c in code if c.isalpha())
    return f"{exchange}.{prefix}"


def analyze_symbol_prefix(df, prefix, ret_col_long="ret_8h_bps", ret_col_short="short_pnl_4h_bps"):
    """对一个品种前缀 · 报告不同 skew/atr 组合下的 mean."""
    sub = df[df["prefix"] == prefix].copy()
    if len(sub) < 100:
        return None

    # 多头档位（skew ≤ · atr ≤ · trend ≥ 0.75）
    long_configs = [
        ("LP", 0.10, 0.70),
        ("LL_only", (0.10, 0.30), 0.70),  # 严格互斥
        ("LP_wide", 0.10, 1.01),  # 放宽 atr
        ("LL_wide", (0.10, 0.30), 1.01),
    ]
    # 空头档位（skew ≥ 0.70 · atr > · trend ≤ 0.20）
    short_configs = [
        ("SP", 0.80),
        ("SC_only", (0.67, 0.80)),
        ("SL_only", (0.50, 0.67)),
    ]

    rows = []
    n_total = len(sub)
    n_contracts = sub["contract"].nunique()

    # 多头
    for name, skew_range, atr_hi in long_configs:
        if isinstance(skew_range, tuple):
            mask = (sub["signed_skew_rank_roll"] > skew_range[0]) & (sub["signed_skew_rank_roll"] <= skew_range[1])
        else:
            mask = sub["signed_skew_rank_roll"] <= skew_range
        mask &= (sub["atr_rank_roll"] <= atr_hi) & (sub["trend_rank_roll"] >= 0.75)
        seg = sub[mask & sub[ret_col_long].notna()]
        if len(seg) < 5:
            continue
        r = seg[ret_col_long]
        rows.append({
            "prefix": prefix,
            "n_total": n_total,
            "n_contracts": n_contracts,
            "class": name,
            "n": len(r),
            "mean": r.mean(),
            "hit": (r > 0).mean(),
            "trigger_rate": len(seg) / n_total,
        })

    # 空头
    for name, atr_range in short_configs:
        if isinstance(atr_range, tuple):
            mask = (sub["atr_rank_roll"] > atr_range[0]) & (sub["atr_rank_roll"] <= atr_range[1])
        else:
            mask = sub["atr_rank_roll"] > atr_range
        mask &= (sub["signed_skew_rank_roll"] >= 0.70) & (sub["trend_rank_roll"] <= 0.20)
        seg = sub[mask & sub[ret_col_short].notna()]
        if len(seg) < 5:
            continue
        r = seg[ret_col_short]
        rows.append({
            "prefix": prefix,
            "n_total": n_total,
            "n_contracts": n_contracts,
            "class": name,
            "n": len(r),
            "mean": r.mean(),
            "hit": (r > 0).mean(),
            "trigger_rate": len(seg) / n_total,
        })

    return rows


def main():
    print("=" * 110)
    print("阶段 4 · 快速诊断 · 品种特性 · 是否需要品种化参数")
    print("=" * 110)

    df = prepare_dataset_full()
    df["prefix"] = df["contract"].apply(parse_prefix)

    prefixes = sorted(df["prefix"].unique())
    print(f"\n品种前缀数：{len(prefixes)}")

    all_rows = []
    for pfx in prefixes:
        rows = analyze_symbol_prefix(df, pfx)
        if rows:
            all_rows.extend(rows)

    out_df = pd.DataFrame(all_rows)
    out_df.to_csv(LOG_DIR / "stage4_symbol_prefix_diagnosis.csv", index=False)

    # 主表 · 每品种 × 每档位的 mean
    pivot = out_df.pivot_table(
        index="prefix", columns="class", values="mean", aggfunc="first"
    )
    n_pivot = out_df.pivot_table(
        index="prefix", columns="class", values="n", aggfunc="first"
    )

    print(f"\n{'品种':12s} {'n_tot':>6s} " + " ".join([f"{c:>10s}" for c in pivot.columns]))
    print("-" * 130)
    for pfx in pivot.index:
        row_str = f"{pfx:12s} {int(out_df[out_df['prefix'] == pfx]['n_total'].iloc[0]):>6d} "
        for c in pivot.columns:
            m = pivot.loc[pfx, c]
            n = n_pivot.loc[pfx, c]
            if pd.isna(m):
                row_str += f" {'-':>10s}"
            else:
                marker = "🟢" if m > +20 else "🟡" if m > 0 else "🔴"
                row_str += f" {marker}{m:>+6.1f}({int(n):>3d})"
        print(row_str)

    # 按方向汇总
    print("\n" + "=" * 110)
    print("多头 (LP + LL) · 各品种最优")
    print("=" * 110)
    long_classes = ["LP", "LL_only", "LP_wide", "LL_wide"]
    for pfx in pivot.index:
        vals = {c: pivot.loc[pfx, c] for c in long_classes if c in pivot.columns and not pd.isna(pivot.loc[pfx, c])}
        if not vals:
            continue
        best = max(vals, key=vals.get)
        best_mean = vals[best]
        print(f"  {pfx:12s} · 最优 {best:>10s} · mean {best_mean:+.1f} · 全档 " + " · ".join(
            [f"{c[:10]}:{vals[c]:+.0f}" for c in long_classes if c in vals]
        ))

    print("\n" + "=" * 110)
    print("空头 (SP + SC + SL) · 各品种最优")
    print("=" * 110)
    short_classes = ["SP", "SC_only", "SL_only"]
    for pfx in pivot.index:
        vals = {c: pivot.loc[pfx, c] for c in short_classes if c in pivot.columns and not pd.isna(pivot.loc[pfx, c])}
        if not vals:
            continue
        best = max(vals, key=vals.get)
        best_mean = vals[best]
        print(f"  {pfx:12s} · 最优 {best:>10s} · mean {best_mean:+.1f} · 全档 " + " · ".join(
            [f"{c[:10]}:{vals[c]:+.0f}" for c in short_classes if c in vals]
        ))

    # 一致性诊断
    print("\n" + "=" * 110)
    print("品种参数一致性诊断")
    print("=" * 110)
    print("\n若不同品种最优参数一致 · 说明单一分类器可用")
    print("若各品种最优参数分散 · 说明需要品种化参数")

    long_best_counts = pd.Series(
        [max({c: pivot.loc[p, c] for c in long_classes if c in pivot.columns and not pd.isna(pivot.loc[p, c])},
             key=lambda x: pivot.loc[p, x] if not pd.isna(pivot.loc[p, x]) else -999)
         for p in pivot.index]
    ).value_counts()
    print("\n多头最优档位分布：")
    print(long_best_counts)

    short_best_counts = pd.Series(
        [max({c: pivot.loc[p, c] for c in short_classes if c in pivot.columns and not pd.isna(pivot.loc[p, c])},
             key=lambda x: pivot.loc[p, x] if not pd.isna(pivot.loc[p, x]) else -999)
         for p in pivot.index]
    ).value_counts()
    print("\n空头最优档位分布：")
    print(short_best_counts)

    print(f"\n输出：{LOG_DIR / 'stage4_symbol_prefix_diagnosis.csv'}")


if __name__ == "__main__":
    main()
