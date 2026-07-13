"""
文件级元信息：
- 创建背景：阶段 1 · 用户明确"先做测量、只看显著不对称"。上一版 quintile
  分析把 Q2/Q3/Q4 = 对称样本全都算进去了，稀释了信号。这版按绝对阈值
  |log ratio| ≥ log(1.5) / |skew| ≥ 0.5 只保留显著不对称样本。
- 用途：读 long_events.csv → 每个度量的分布诊断（分位、显著占比）
  → 在显著子集上分 UP/DOWN 组做条件收益分布 + cluster bootstrap CI
  → 输出 asymmetry_distribution.csv / significant_subset_stats.csv /
  significant_up_down_diff.csv
- 注意事项：临时研究脚本，纯读现有 long_events.csv 加工，不重新构建 profile。
  只做描述性统计和条件均值差异，不判决"能否交易"。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

METRIC_COLS = ["A1_vol_ratio", "A2_dist_ratio", "A3_skew", "A4_centroid_ratio"]
RET_COLS = ["ret_1h", "ret_2h", "ret_4h", "ret_8h"]

# 显著不对称阈值（用户约定）
THRESHOLDS: dict[str, float] = {
    "A1_vol_ratio": math.log(1.5),
    "A2_dist_ratio": math.log(1.5),
    "A3_skew": 0.5,
    "A4_centroid_ratio": math.log(1.5),
}

BOOTSTRAP_N = 5000
RNG_SEED = 20260707


def bootstrap_mean_diff(
    up_vals_by_contract: dict[str, np.ndarray],
    dn_vals_by_contract: dict[str, np.ndarray],
    n_boot: int = BOOTSTRAP_N,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float, float, float, float]:
    """按 contract 聚类重抽样，返回：
    (mean_up, mean_dn, diff, ci_lo, ci_hi, p_two)。
    """
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
    contracts = sorted(set(up_vals_by_contract) | set(dn_vals_by_contract))
    if len(contracts) < 2:
        return float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan")

    all_up = np.concatenate(
        [up_vals_by_contract[c] for c in contracts if c in up_vals_by_contract]
    )
    all_dn = np.concatenate(
        [dn_vals_by_contract[c] for c in contracts if c in dn_vals_by_contract]
    )
    if len(all_up) < 30 or len(all_dn) < 30:
        return (
            float(all_up.mean()) if len(all_up) else float("nan"),
            float(all_dn.mean()) if len(all_dn) else float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
        )
    mean_up = float(all_up.mean())
    mean_dn = float(all_dn.mean())
    obs = mean_up - mean_dn

    n_clusters = len(contracts)
    boot = np.empty(n_boot, dtype=np.float64)
    idx_choices = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    for i in range(n_boot):
        picked = [contracts[j] for j in idx_choices[i]]
        u_vals = [
            up_vals_by_contract[c] for c in picked if c in up_vals_by_contract
        ]
        d_vals = [
            dn_vals_by_contract[c] for c in picked if c in dn_vals_by_contract
        ]
        if not u_vals or not d_vals:
            boot[i] = np.nan
            continue
        u = np.concatenate(u_vals)
        d = np.concatenate(d_vals)
        boot[i] = u.mean() - d.mean()
    valid = boot[~np.isnan(boot)]
    if len(valid) < 10:
        return mean_up, mean_dn, obs, float("nan"), float("nan"), float("nan")
    ci_lo, ci_hi = np.percentile(valid, [2.5, 97.5])
    p_gt = float(np.mean(valid > 0))
    p_lt = float(np.mean(valid < 0))
    p_two = 2.0 * min(p_gt, p_lt)
    return mean_up, mean_dn, obs, float(ci_lo), float(ci_hi), p_two


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    print(f"Loaded long table: rows={len(df)}", flush=True)

    # ---------------------------------------------------------------
    # 1. asymmetry 分布本身
    # ---------------------------------------------------------------
    dist_rows: list[dict] = []
    for window in ["W1", "W2", "W3"]:
        for metric in METRIC_COLS:
            thr = THRESHOLDS[metric]
            sub = df[df["window"] == window]
            vals = sub[metric].dropna().to_numpy()
            if len(vals) == 0:
                continue
            dist_rows.append(
                {
                    "window": window,
                    "metric": metric,
                    "threshold": thr,
                    "n": int(len(vals)),
                    "mean": float(vals.mean()),
                    "median": float(np.median(vals)),
                    "std": float(vals.std()),
                    "p05": float(np.quantile(vals, 0.05)),
                    "p25": float(np.quantile(vals, 0.25)),
                    "p75": float(np.quantile(vals, 0.75)),
                    "p95": float(np.quantile(vals, 0.95)),
                    "share_up": float((vals > thr).mean()),
                    "share_dn": float((vals < -thr).mean()),
                    "share_neutral": float((np.abs(vals) <= thr).mean()),
                    "share_significant": float((np.abs(vals) > thr).mean()),
                }
            )
    dist_df = pd.DataFrame(dist_rows)
    dist_path = LOG_DIR / "asymmetry_distribution.csv"
    dist_df.to_csv(dist_path, index=False)
    print("\n=== asymmetry 分布（含显著占比）===")
    show_cols = [
        "window",
        "metric",
        "n",
        "mean",
        "median",
        "std",
        "p05",
        "p95",
        "share_up",
        "share_dn",
        "share_significant",
    ]
    print(dist_df[show_cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # ---------------------------------------------------------------
    # 2. 显著子集下的 UP / DOWN 条件收益分布
    # ---------------------------------------------------------------
    subset_rows: list[dict] = []
    diff_rows: list[dict] = []
    for window in ["W1", "W2", "W3"]:
        for metric in METRIC_COLS:
            thr = THRESHOLDS[metric]
            sub = df[df["window"] == window].copy()
            for ret_col in RET_COLS:
                up_by_c: dict[str, np.ndarray] = {}
                dn_by_c: dict[str, np.ndarray] = {}
                for contract, grp in sub.groupby("contract", sort=False):
                    up = grp.loc[grp[metric] > thr, ret_col].dropna().to_numpy()
                    dn = grp.loc[grp[metric] < -thr, ret_col].dropna().to_numpy()
                    if len(up) > 0:
                        up_by_c[contract] = up
                    if len(dn) > 0:
                        dn_by_c[contract] = dn
                all_up = (
                    np.concatenate(list(up_by_c.values())) if up_by_c else np.array([])
                )
                all_dn = (
                    np.concatenate(list(dn_by_c.values())) if dn_by_c else np.array([])
                )
                for tag, arr in [("UP", all_up), ("DN", all_dn)]:
                    if len(arr) == 0:
                        continue
                    subset_rows.append(
                        {
                            "window": window,
                            "metric": metric,
                            "horizon": ret_col,
                            "group": tag,
                            "n": int(len(arr)),
                            "mean": float(arr.mean()),
                            "median": float(np.median(arr)),
                            "std": float(arr.std()),
                            "p05": float(np.quantile(arr, 0.05)),
                            "p25": float(np.quantile(arr, 0.25)),
                            "p75": float(np.quantile(arr, 0.75)),
                            "p95": float(np.quantile(arr, 0.95)),
                            "hit_pos": float((arr > 0).mean()),
                        }
                    )
                mean_up, mean_dn, obs, ci_lo, ci_hi, p_two = bootstrap_mean_diff(
                    up_by_c, dn_by_c
                )
                diff_rows.append(
                    {
                        "window": window,
                        "metric": metric,
                        "horizon": ret_col,
                        "n_up": int(sum(len(v) for v in up_by_c.values())),
                        "n_dn": int(sum(len(v) for v in dn_by_c.values())),
                        "mean_up": mean_up,
                        "mean_dn": mean_dn,
                        "diff_up_minus_dn": obs,
                        "ci_lo": ci_lo,
                        "ci_hi": ci_hi,
                        "p_two": p_two,
                    }
                )

    subset_df = pd.DataFrame(subset_rows)
    diff_df = pd.DataFrame(diff_rows)
    subset_path = LOG_DIR / "significant_subset_stats.csv"
    diff_path = LOG_DIR / "significant_up_down_diff.csv"
    subset_df.to_csv(subset_path, index=False)
    diff_df.to_csv(diff_path, index=False)

    print("\n=== 显著不对称子集 · UP-DN mean diff (Bonferroni family=48, alpha=0.05/48) ===")
    diff_df["abs_diff"] = diff_df["diff_up_minus_dn"].abs()
    diff_df["bonf_reject"] = diff_df["p_two"] < (0.05 / 48)
    diff_df_sorted = diff_df.sort_values("abs_diff", ascending=False)
    show_cols2 = [
        "window",
        "metric",
        "horizon",
        "n_up",
        "n_dn",
        "mean_up",
        "mean_dn",
        "diff_up_minus_dn",
        "ci_lo",
        "ci_hi",
        "p_two",
        "bonf_reject",
    ]
    print(diff_df_sorted[show_cols2].to_string(index=False, float_format=lambda x: f"{x:.5f}"))
    print(f"\nBonferroni threshold p < {0.05/48:.5f}")
    print(f"Passing: {int(diff_df['bonf_reject'].sum())} / {len(diff_df)}")

    # 展示 top-1 完整分布
    top1 = diff_df_sorted.iloc[0]
    print(f"\n=== Full distribution for top |diff|: ({top1['window']}, {top1['metric']}, {top1['horizon']}) ===")
    top_sub = subset_df[
        (subset_df["window"] == top1["window"])
        & (subset_df["metric"] == top1["metric"])
        & (subset_df["horizon"] == top1["horizon"])
    ]
    print(top_sub.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

    print("\nOutputs:")
    print(f"  asymmetry distribution -> {dist_path}")
    print(f"  significant subset stats -> {subset_path}")
    print(f"  significant UP-DN diff -> {diff_path}")


if __name__ == "__main__":
    main()
