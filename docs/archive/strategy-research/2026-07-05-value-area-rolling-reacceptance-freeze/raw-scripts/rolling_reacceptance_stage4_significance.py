#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：Stage 4 输出的期望净值是点估计，样本 n=40-60 偏小。用户要求做
  统计学显著性检验，判断 rolling 优势是否真实。
- 用途：对 Stage 4 的 trades.csv 做四类检验：
  1) 单锚点 vs 0：策略是否真的盈利（bootstrap 95% CI + one-sample t-test）
  2) 配对差值 rolling_60 vs fixed_POC：真实是否更优（paired t / Wilcoxon）
  3) 配对差值 rolling_60 vs PrevClose：真实是否更优（同上）
  4) 效应量 Cohen's d
  5) Cluster bootstrap（按 contract × date 聚类）作稳健性检验
- 注意事项：
  - 配对：仅保留同一 (contract, date, entry_time) 下同时有多锚点评估的事件
  - 距离档按 fixed_POC 定义（与 Stage 4 一致）
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

INPUT_CSV = Path("project_data/analysis/rolling_reacceptance_stage4/stage4_trades.csv")
OUTPUT_DIR = Path("project_data/analysis/rolling_reacceptance_stage4")

FOCUS_ANCHORS = ["rolling_POC_60", "rolling_POC_120", "rolling_POC_240", "fixed_POC", "PrevClose"]
FOCUS_BUCKETS = ["2.5-4.0", "4.0+"]
FOCUS_SECTORS = ["energy_chem", "black", "agri_czce", "agri_dce"]  # 排除 metals
N_BOOTSTRAP = 5000


def bootstrap_ci(x: np.ndarray, n_boot: int = N_BOOTSTRAP, alpha: float = 0.05) -> tuple[float, float, float]:
    """返回 (均值, ci_low, ci_high)。"""
    rng = np.random.default_rng(42)
    means = np.empty(n_boot)
    n = len(x)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        means[i] = x[idx].mean()
    return float(x.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def cohens_d(x: np.ndarray, y: np.ndarray | None = None) -> float:
    """单样本 (vs 0) 或配对样本的 Cohen's d。"""
    if y is None:
        return float(x.mean() / x.std(ddof=1)) if x.std(ddof=1) > 0 else 0.0
    diff = x - y
    return float(diff.mean() / diff.std(ddof=1)) if diff.std(ddof=1) > 0 else 0.0


def one_sample_test(x: np.ndarray) -> dict:
    """单样本检验：期望净值 > 0."""
    n = len(x)
    mean, ci_lo, ci_hi = bootstrap_ci(x)
    t_stat, p_two = stats.ttest_1samp(x, 0.0)
    p_one_side = p_two / 2 if t_stat > 0 else 1 - p_two / 2
    d = cohens_d(x)
    return {
        "n": n, "mean": mean, "ci_95_low": ci_lo, "ci_95_high": ci_hi,
        "t_stat": float(t_stat), "p_one_sided (H1: mean>0)": float(p_one_side),
        "cohens_d": d,
    }


def paired_test(x: np.ndarray, y: np.ndarray) -> dict:
    """配对检验：x - y > 0."""
    assert len(x) == len(y), "paired arrays must have same length"
    diff = x - y
    n = len(diff)
    mean_diff, ci_lo, ci_hi = bootstrap_ci(diff)
    t_stat, p_two = stats.ttest_rel(x, y)
    p_one_side = p_two / 2 if t_stat > 0 else 1 - p_two / 2
    try:
        w_stat, w_p = stats.wilcoxon(diff, alternative="greater")
    except ValueError:
        w_stat, w_p = np.nan, np.nan
    d = cohens_d(x, y)
    return {
        "n": n, "mean_diff": mean_diff, "ci_95_low": ci_lo, "ci_95_high": ci_hi,
        "t_stat": float(t_stat), "p_one_sided (H1: x>y)": float(p_one_side),
        "wilcoxon_p": float(w_p) if not np.isnan(w_p) else None,
        "cohens_d_diff": d,
    }


def cluster_bootstrap_diff(
    df: pd.DataFrame, x_col: str, y_col: str, cluster_col: str, n_boot: int = N_BOOTSTRAP,
) -> tuple[float, float, float, float]:
    """按 cluster 聚类的 bootstrap 差值 CI + 单侧 p-value。优化版本：预分组 numpy 数组。"""
    diff_col = df[x_col].to_numpy() - df[y_col].to_numpy()
    cluster_arr = df[cluster_col].to_numpy()
    clusters, inverse = np.unique(cluster_arr, return_inverse=True)
    # 每个 cluster 的 diff 索引列表
    cluster_indices: dict[int, np.ndarray] = {}
    for idx, cluster_key in enumerate(clusters):
        cluster_indices[idx] = np.where(inverse == idx)[0]
    n_clusters = len(clusters)
    rng = np.random.default_rng(42)
    boot_diffs = np.empty(n_boot)
    for i in range(n_boot):
        sampled_idx = rng.integers(0, n_clusters, size=n_clusters)
        all_indices = np.concatenate([cluster_indices[j] for j in sampled_idx])
        boot_diffs[i] = diff_col[all_indices].mean()
    observed = float(diff_col.mean())
    ci_lo = float(np.quantile(boot_diffs, 0.025))
    ci_hi = float(np.quantile(boot_diffs, 0.975))
    p_one_sided = float((boot_diffs <= 0).mean())
    return observed, ci_lo, ci_hi, p_one_sided


def build_paired_df(df: pd.DataFrame, sector: str | None, bucket: str) -> pd.DataFrame:
    """构造配对 dataframe：同一事件（contract+bucket+entry）下各锚点 pnl 对齐。
    这里假设同一 (contract, symbol, bucket) 下 anchors 是按顺序追加的；简化处理为
    reset_index + pivot。"""
    sub = df[df["bucket"] == bucket].copy()
    if sector is not None:
        sub = sub[sub["sector"] == sector]
    # 按 contract + row_within_contract 分组构造事件 id（用累计计数）
    sub["event_id"] = sub.groupby(["contract", "bucket", "anchor"]).cumcount()
    pivot = sub.pivot_table(
        index=["contract", "bucket", "event_id"],
        columns="anchor",
        values="pnl_atr",
        aggfunc="first",
    ).reset_index()
    # 只保留三个 focus anchor 都非空的行
    need_cols = ["rolling_POC_60", "fixed_POC", "PrevClose"]
    for c in need_cols:
        if c not in pivot.columns:
            return pd.DataFrame()
    pivot = pivot.dropna(subset=need_cols)
    return pivot


def main() -> None:
    df = pd.read_csv(INPUT_CSV)
    df = df[df["sector"].isin(FOCUS_SECTORS)]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# Stage 4 · 显著性检验 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(f"检验对象：Stage 4 期望净值结论。Bootstrap n={N_BOOTSTRAP}。\n")
    lines.append("排除 metals 板块（Stage 4 已判定禁用）。\n")

    # 1. 单锚点 vs 0（各板块 × 距离档 × 锚点）
    lines.append("## 1. 单锚点期望净值 vs 0（策略是否盈利）\n")
    lines.append("| sector | bucket | anchor | n | mean | 95% CI | p_one_sided | Cohen's d |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for sector in FOCUS_SECTORS + ["ALL_ex_metals"]:
        for bucket in FOCUS_BUCKETS:
            for anchor in FOCUS_ANCHORS:
                if sector == "ALL_ex_metals":
                    sub = df[(df["bucket"] == bucket) & (df["anchor"] == anchor)]
                else:
                    sub = df[(df["sector"] == sector) & (df["bucket"] == bucket) & (df["anchor"] == anchor)]
                x = sub["pnl_atr"].to_numpy()
                if len(x) < 20:
                    continue
                r = one_sample_test(x)
                lines.append(
                    f"| {sector} | {bucket} | {anchor} | {r['n']} | "
                    f"{r['mean']:+.3f} | [{r['ci_95_low']:+.3f}, {r['ci_95_high']:+.3f}] | "
                    f"{r['p_one_sided (H1: mean>0)']:.4f} | {r['cohens_d']:+.3f} |"
                )
    lines.append("")

    # 2. 配对差值 rolling_60 vs fixed_POC
    lines.append("## 2. 配对差值检验：rolling_POC_60 vs fixed_POC（H1: rolling > fixed）\n")
    lines.append("| sector | bucket | n | mean_diff | 95% CI | paired_p | wilcoxon_p | Cohen's d |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for sector in FOCUS_SECTORS + [None]:
        sec_label = sector if sector is not None else "ALL_ex_metals"
        for bucket in FOCUS_BUCKETS:
            paired = build_paired_df(df, sector, bucket)
            if len(paired) < 20:
                continue
            r = paired_test(
                paired["rolling_POC_60"].to_numpy(),
                paired["fixed_POC"].to_numpy(),
            )
            lines.append(
                f"| {sec_label} | {bucket} | {r['n']} | {r['mean_diff']:+.3f} | "
                f"[{r['ci_95_low']:+.3f}, {r['ci_95_high']:+.3f}] | "
                f"{r['t_stat']:.2f}, p={r['p_one_sided (H1: x>y)']:.4f} | "
                f"{r['wilcoxon_p']:.4f} | {r['cohens_d_diff']:+.3f} |"
            )
    lines.append("")

    # 3. 配对差值 rolling_60 vs PrevClose
    lines.append("## 3. 配对差值检验：rolling_POC_60 vs PrevClose（H1: rolling > PrevClose）\n")
    lines.append("| sector | bucket | n | mean_diff | 95% CI | paired_p | wilcoxon_p | Cohen's d |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for sector in FOCUS_SECTORS + [None]:
        sec_label = sector if sector is not None else "ALL_ex_metals"
        for bucket in FOCUS_BUCKETS:
            paired = build_paired_df(df, sector, bucket)
            if len(paired) < 20:
                continue
            r = paired_test(
                paired["rolling_POC_60"].to_numpy(),
                paired["PrevClose"].to_numpy(),
            )
            lines.append(
                f"| {sec_label} | {bucket} | {r['n']} | {r['mean_diff']:+.3f} | "
                f"[{r['ci_95_low']:+.3f}, {r['ci_95_high']:+.3f}] | "
                f"{r['t_stat']:.2f}, p={r['p_one_sided (H1: x>y)']:.4f} | "
                f"{r['wilcoxon_p']:.4f} | {r['cohens_d_diff']:+.3f} |"
            )
    lines.append("")

    # 4. Cluster bootstrap（按合约聚类）
    lines.append("## 4. Cluster Bootstrap（按合约聚类）：rolling_60 vs fixed_POC\n")
    lines.append("检验事件非独立性下的稳健差值。若同一合约内事件高度相关，t-test 会过乐观。\n")
    lines.append("| sector | bucket | n_events | observed_diff | cluster 95% CI | p_one_sided |")
    lines.append("|---|---|---|---|---|---|")
    for sector in FOCUS_SECTORS + [None]:
        sec_label = sector if sector is not None else "ALL_ex_metals"
        for bucket in FOCUS_BUCKETS:
            paired = build_paired_df(df, sector, bucket)
            if len(paired) < 20:
                continue
            obs, ci_lo, ci_hi, p = cluster_bootstrap_diff(
                paired, "rolling_POC_60", "fixed_POC", "contract"
            )
            lines.append(
                f"| {sec_label} | {bucket} | {len(paired)} | {obs:+.3f} | "
                f"[{ci_lo:+.3f}, {ci_hi:+.3f}] | {p:.4f} |"
            )
    lines.append("")

    # 5. 判决摘要
    lines.append("## 5. 判决摘要\n")
    lines.append("- **单锚点 vs 0**：p < 0.05 且 CI 下限 > 0 → 策略真实盈利")
    lines.append("- **配对 rolling vs fixed**：p < 0.05 且 CI 下限 > 0 → rolling 真实更优")
    lines.append("- **Cluster bootstrap**：与 paired t-test 对比，若 p 显著变大 → 事件非独立性问题严重")
    lines.append("- **Cohen's d**：|d| < 0.2 微弱 / 0.2-0.5 中等 / 0.5-0.8 强 / > 0.8 极强")
    lines.append("")

    md = "\n".join(lines) + "\n"
    out_path = OUTPUT_DIR / "stage4_significance_test.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
