"""
跨合约 A3_skew 分布对比 · 验证是否可以用全池经验分布做先验

假设检验：
- H0: 所有合约的 A3_skew 分布来自同一潜在分布
  → 若成立 · 可用全池经验分布替代 per-contract rank · 大幅提升精度
- H1: 不同合约的 A3_skew 分布明显不同
  → 若成立 · 不能混用 · 必须保持 per-contract rank

诊断项：
1. 每合约的 mean/std/skew/kurt/p05/p50/p95 汇总
2. 跨合约的分位数一致性
3. Kolmogorov-Smirnov 两两检验（是否显著不同）
4. 全池 vs 单合约 CDF 曲线
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import prepare_dataset  # noqa: E402

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)


def per_contract_stats(df):
    """每合约独立 A3_skew 分布统计."""
    rows = []
    for contract, g in df.groupby("contract"):
        s = g["A3_skew"].dropna()
        if len(s) < 30:
            continue
        rows.append({
            "contract": contract,
            "n_events": len(s),
            "mean": s.mean(),
            "std": s.std(),
            "skew_of_skew": stats.skew(s),
            "kurt_of_skew": stats.kurtosis(s),
            "p05": s.quantile(0.05),
            "p10": s.quantile(0.10),
            "p25": s.quantile(0.25),
            "p50": s.quantile(0.50),
            "p75": s.quantile(0.75),
            "p90": s.quantile(0.90),
            "p95": s.quantile(0.95),
        })
    return pd.DataFrame(rows).sort_values("contract")


def ks_pairwise(df, top_n=15):
    """两两 KS 检验 · 看跨合约分布是否显著不同."""
    contracts = df.groupby("contract").size().sort_values(ascending=False).head(top_n).index.tolist()
    result = []
    for i, c1 in enumerate(contracts):
        s1 = df[df["contract"] == c1]["A3_skew"].dropna().values
        for c2 in contracts[i + 1:]:
            s2 = df[df["contract"] == c2]["A3_skew"].dropna().values
            if len(s1) < 30 or len(s2) < 30:
                continue
            stat, p = stats.ks_2samp(s1, s2)
            result.append({
                "c1": c1, "c2": c2,
                "n1": len(s1), "n2": len(s2),
                "ks_stat": stat, "p_value": p,
                "significantly_different": p < 0.05,
            })
    return pd.DataFrame(result)


def check_prefix_grouping(df):
    """按品种前缀（rb / cu / p 等）而不是合约月份分组 · 看是否同品种分布一致."""
    df = df.copy()
    df["prefix"] = df["contract"].str.extract(r"^([A-Za-z]+)")
    rows = []
    for prefix, g in df.groupby("prefix"):
        s = g["A3_skew"].dropna()
        if len(s) < 50:
            continue
        rows.append({
            "prefix": prefix,
            "n_events": len(s),
            "n_contracts": g["contract"].nunique(),
            "mean": s.mean(),
            "std": s.std(),
            "p05": s.quantile(0.05),
            "p10": s.quantile(0.10),
            "p50": s.quantile(0.50),
            "p90": s.quantile(0.90),
            "p95": s.quantile(0.95),
        })
    return pd.DataFrame(rows).sort_values("prefix")


def check_pool_vs_percontract_rank_diff(df):
    """比较 pooled rank vs per-contract rank 的差异分布."""
    df = df.copy()
    df = df.dropna(subset=["A3_skew"]).sort_values("event_time").reset_index(drop=True)

    # per-contract rank（当前使用）
    df["rank_per_c"] = df.groupby("contract")["A3_skew"].rank(pct=True)
    # pooled rank（全池 · 假设跨合约同分布）
    df["rank_pooled"] = df["A3_skew"].rank(pct=True)

    diff = (df["rank_per_c"] - df["rank_pooled"]).abs()
    return {
        "mean_abs_diff": diff.mean(),
        "median_abs_diff": diff.median(),
        "p95_abs_diff": diff.quantile(0.95),
        "correlation": df["rank_per_c"].corr(df["rank_pooled"]),
    }


def main():
    print("=" * 100)
    print("跨合约 A3_skew 分布诊断 · 判断是否可用全池经验分布做先验")
    print("=" * 100)

    df = prepare_dataset()
    print(f"\n数据规模：{len(df)} events · {df['contract'].nunique()} contracts")

    # ========== 1. 每合约分布统计 ==========
    print("\n" + "=" * 100)
    print("1. 每合约 A3_skew 分布统计（前 15 合约 · 按 n 降序）")
    print("=" * 100)
    stats_df = per_contract_stats(df).sort_values("n_events", ascending=False).head(15)
    stats_df.to_csv(LOG_DIR / "skew_dist_per_contract.csv", index=False)

    print(f"\n{'合约':10s} {'n':>5s} {'mean':>8s} {'std':>8s} "
          f"{'p05':>8s} {'p10':>8s} {'p50':>8s} {'p90':>8s} {'p95':>8s}")
    for _, r in stats_df.iterrows():
        print(f"{r['contract']:10s} {int(r['n_events']):>5d} "
              f"{r['mean']:>+8.3f} {r['std']:>8.3f} "
              f"{r['p05']:>+8.3f} {r['p10']:>+8.3f} {r['p50']:>+8.3f} "
              f"{r['p90']:>+8.3f} {r['p95']:>+8.3f}")

    # 全池 stats
    all_skew = df["A3_skew"].dropna()
    print(f"\n{'全池':10s} {int(len(all_skew)):>5d} "
          f"{all_skew.mean():>+8.3f} {all_skew.std():>8.3f} "
          f"{all_skew.quantile(0.05):>+8.3f} {all_skew.quantile(0.10):>+8.3f} "
          f"{all_skew.quantile(0.50):>+8.3f} "
          f"{all_skew.quantile(0.90):>+8.3f} {all_skew.quantile(0.95):>+8.3f}")

    # 分位数变异系数（跨合约 · CV = std / mean_abs）
    print(f"\n关键分位点跨合约的离散度：")
    for pct_col in ["p05", "p10", "p50", "p90", "p95"]:
        vals = stats_df[pct_col].values
        cv = vals.std() / abs(vals.mean()) if abs(vals.mean()) > 0.01 else np.inf
        rng = vals.max() - vals.min()
        print(f"  {pct_col}: 均值={vals.mean():+.3f} · std={vals.std():.3f} · "
              f"range=[{vals.min():+.3f}, {vals.max():+.3f}] · 极差={rng:.3f}")

    # ========== 2. 品种前缀分组 ==========
    print("\n" + "=" * 100)
    print("2. 按品种前缀分组（同品种不同月份合约合并）")
    print("=" * 100)
    prefix_df = check_prefix_grouping(df)
    prefix_df.to_csv(LOG_DIR / "skew_dist_per_prefix.csv", index=False)

    print(f"\n{'品种':6s} {'n':>6s} {'合约':>5s} {'mean':>8s} {'std':>8s} "
          f"{'p05':>8s} {'p10':>8s} {'p50':>8s} {'p90':>8s} {'p95':>8s}")
    for _, r in prefix_df.iterrows():
        print(f"{r['prefix']:6s} {int(r['n_events']):>6d} {int(r['n_contracts']):>5d} "
              f"{r['mean']:>+8.3f} {r['std']:>8.3f} "
              f"{r['p05']:>+8.3f} {r['p10']:>+8.3f} {r['p50']:>+8.3f} "
              f"{r['p90']:>+8.3f} {r['p95']:>+8.3f}")

    # ========== 3. KS 两两检验 ==========
    print("\n" + "=" * 100)
    print("3. 两两 Kolmogorov-Smirnov 检验（top 15 合约）")
    print("=" * 100)
    ks_df = ks_pairwise(df, top_n=15)
    ks_df.to_csv(LOG_DIR / "skew_ks_pairwise.csv", index=False)

    n_pairs = len(ks_df)
    n_sig = ks_df["significantly_different"].sum()
    print(f"\n共 {n_pairs} 对 · 显著不同（p<0.05）：{n_sig}/{n_pairs} = {n_sig / n_pairs:.1%}")
    print(f"KS 统计量均值：{ks_df['ks_stat'].mean():.3f}")
    print(f"KS 统计量 P95: {ks_df['ks_stat'].quantile(0.95):.3f}")

    print(f"\n最显著不同的 5 对：")
    for _, r in ks_df.nlargest(5, "ks_stat").iterrows():
        print(f"  {r['c1']:8s} vs {r['c2']:8s} · KS={r['ks_stat']:.3f} · p={r['p_value']:.4f}")

    print(f"\n最相似的 5 对：")
    for _, r in ks_df.nsmallest(5, "ks_stat").iterrows():
        print(f"  {r['c1']:8s} vs {r['c2']:8s} · KS={r['ks_stat']:.3f} · p={r['p_value']:.4f}")

    # ========== 4. pooled vs per-contract rank diff ==========
    print("\n" + "=" * 100)
    print("4. Pooled rank vs Per-contract rank · 若差异小则可用 pooled")
    print("=" * 100)
    r = check_pool_vs_percontract_rank_diff(df)
    print(f"  平均绝对差：{r['mean_abs_diff']:.3f}")
    print(f"  中位数绝对差：{r['median_abs_diff']:.3f}")
    print(f"  P95 绝对差：{r['p95_abs_diff']:.3f}")
    print(f"  相关性：{r['correlation']:.3f}")

    # ========== 5. 综合判读 ==========
    print("\n" + "=" * 100)
    print("综合判读")
    print("=" * 100)
    if ks_df["significantly_different"].mean() > 0.7:
        print("❌ 大部分合约两两显著不同 · 不能简单用全池经验分布")
        print("   建议方案：per-contract rank 保持不变 · 或用品种前缀分组")
    elif ks_df["significantly_different"].mean() > 0.3:
        print("⚠️ 部分合约分布不同 · 部分合约相似 · 建议按品种前缀分组")
        print("   或用贝叶斯混合模型：per-contract prior + pooled data")
    else:
        print("✅ 大部分合约分布相似 · 可考虑用全池经验分布做先验")
        print("   贝叶斯做法：pooled 分布做先验 · per-contract 观察做 update")

    if r["correlation"] > 0.95:
        print("✅ per-contract rank 与 pooled rank 相关性 > 0.95 · 两者近似等价")
    elif r["correlation"] > 0.85:
        print("⚠️ 中等相关 · 有 partial pooling 空间")
    else:
        print("❌ 弱相关 · pooled rank 会显著改变触发条件")


if __name__ == "__main__":
    main()
