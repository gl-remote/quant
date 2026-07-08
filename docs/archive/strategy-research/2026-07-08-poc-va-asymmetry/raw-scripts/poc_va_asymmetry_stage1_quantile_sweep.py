"""
文件级元信息：
- 创建背景：阶段 1 · 用户提出以事件频率反推阈值（"每合约平均两天一次
  交易机会"）。当前每合约每天 ~6.3 个 1h 事件，目标频率 = 每两天一次
  → 每侧占样本 ~8%。本脚本扫描一系列阈值（每侧 5%/8%/10%/15%/20%
  分位），观察 UP-DN 条件均值差异随阈值变严格的变化曲线。
- 用途：读 long_events.csv → 按 per-contract 分位阈值分 UP/DN → 计算
  条件收益差 + cluster bootstrap CI。用分布分位而非绝对阈值，跨度量
  可比。
- 注意事项：临时研究脚本，不进入 workspace/。分位在 per-contract 内
  计算，避免跨品种绝对幅度差异污染阈值定义。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

METRIC_COLS = ["A1_vol_ratio", "A2_dist_ratio", "A3_skew", "A4_centroid_ratio"]
RET_COLS = ["ret_1h", "ret_2h", "ret_4h", "ret_8h"]

# 每侧分位（相当于 top q% 与 bottom q%）；共 5 档
Q_LEVELS = [0.20, 0.15, 0.10, 0.08, 0.05]

BOOTSTRAP_N = 5000
RNG_SEED = 20260707


def bootstrap_mean_diff(
    up_vals_by_contract: dict[str, np.ndarray],
    dn_vals_by_contract: dict[str, np.ndarray],
    n_boot: int = BOOTSTRAP_N,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float, float, float, float]:
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
    contracts = sorted(set(up_vals_by_contract) | set(dn_vals_by_contract))
    if len(contracts) < 2:
        return (float("nan"),) * 6

    all_up = np.concatenate([up_vals_by_contract[c] for c in contracts if c in up_vals_by_contract])
    all_dn = np.concatenate([dn_vals_by_contract[c] for c in contracts if c in dn_vals_by_contract])
    if len(all_up) < 20 or len(all_dn) < 20:
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
    idx = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    for i in range(n_boot):
        picked = [contracts[j] for j in idx[i]]
        u = [up_vals_by_contract[c] for c in picked if c in up_vals_by_contract]
        d = [dn_vals_by_contract[c] for c in picked if c in dn_vals_by_contract]
        if not u or not d:
            boot[i] = np.nan
            continue
        boot[i] = np.concatenate(u).mean() - np.concatenate(d).mean()
    valid = boot[~np.isnan(boot)]
    if len(valid) < 10:
        return mean_up, mean_dn, obs, float("nan"), float("nan"), float("nan")
    ci_lo, ci_hi = np.percentile(valid, [2.5, 97.5])
    p_gt = float(np.mean(valid > 0))
    p_lt = float(np.mean(valid < 0))
    return mean_up, mean_dn, obs, float(ci_lo), float(ci_hi), 2.0 * min(p_gt, p_lt)


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    print(f"Loaded long table: rows={len(df)}", flush=True)

    # 事件频率 baseline
    w1 = df[df["window"] == "W1"]
    avg_events_per_day = (
        w1.groupby("symbol")
        .apply(lambda g: len(g) / g["event_time"].pipe(pd.to_datetime).dt.date.nunique())
        .mean()
    )
    print(f"平均每合约每天 1h 事件数：{avg_events_per_day:.2f}")
    for q in Q_LEVELS:
        rate_per_day = 2 * q * avg_events_per_day  # UP+DN 合计
        print(f"  q={q:.2f} 每侧 → 每合约每天总触发 ≈ {rate_per_day:.2f} 次（每 {1/rate_per_day:.1f} 天一次）")

    rows: list[dict] = []
    for window in ["W1", "W2", "W3"]:
        for metric in METRIC_COLS:
            sub = df[df["window"] == window].copy()
            for q in Q_LEVELS:
                # per-contract 分位阈值
                grp_stats = sub.groupby("contract", sort=False)[metric].agg(
                    lo=lambda x: x.quantile(q), hi=lambda x: x.quantile(1 - q)
                )
                for ret_col in RET_COLS:
                    up_by_c: dict[str, np.ndarray] = {}
                    dn_by_c: dict[str, np.ndarray] = {}
                    for contract, g in sub.groupby("contract", sort=False):
                        lo = grp_stats.loc[contract, "lo"]
                        hi = grp_stats.loc[contract, "hi"]
                        up = g.loc[g[metric] >= hi, ret_col].dropna().to_numpy()
                        dn = g.loc[g[metric] <= lo, ret_col].dropna().to_numpy()
                        if len(up) > 0:
                            up_by_c[contract] = up
                        if len(dn) > 0:
                            dn_by_c[contract] = dn
                    mean_up, mean_dn, obs, ci_lo, ci_hi, p_two = bootstrap_mean_diff(
                        up_by_c, dn_by_c
                    )
                    n_up = sum(len(v) for v in up_by_c.values())
                    n_dn = sum(len(v) for v in dn_by_c.values())
                    rows.append(
                        {
                            "window": window,
                            "metric": metric,
                            "quantile": q,
                            "horizon": ret_col,
                            "n_up": n_up,
                            "n_dn": n_dn,
                            "mean_up": mean_up,
                            "mean_dn": mean_dn,
                            "diff_up_minus_dn": obs,
                            "ci_lo": ci_lo,
                            "ci_hi": ci_hi,
                            "p_two": p_two,
                            "avg_trigger_per_day": 2 * q * avg_events_per_day,
                            "days_per_trigger": 1 / (2 * q * avg_events_per_day),
                        }
                    )
    result = pd.DataFrame(rows)
    # Bonferroni family = 3 win × 4 metric × 5 quantile × 4 horizon = 240
    result["bonf_reject"] = result["p_two"] < (0.05 / len(result))
    out_path = LOG_DIR / "quantile_sweep.csv"
    result.to_csv(out_path, index=False)

    # 展示 A3_skew × W1 各分位 × 各 horizon 的变化曲线（用户关心的核心组合）
    print("\n=== A3_skew × W1 · 各分位 × 各 horizon ===")
    view = result[(result["window"] == "W1") & (result["metric"] == "A3_skew")].copy()
    view = view[
        ["quantile", "horizon", "n_up", "n_dn", "mean_up", "mean_dn", "diff_up_minus_dn", "ci_lo", "ci_hi", "p_two", "days_per_trigger"]
    ]
    print(view.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

    # 全 family top 10
    print("\n=== Top 10 by |diff_up_minus_dn|（全 family 排序）===")
    result["abs_diff"] = result["diff_up_minus_dn"].abs()
    top10 = result.sort_values("abs_diff", ascending=False).head(10)
    print(
        top10[
            ["window", "metric", "quantile", "horizon", "n_up", "n_dn", "diff_up_minus_dn", "ci_lo", "ci_hi", "p_two", "days_per_trigger", "bonf_reject"]
        ].to_string(index=False, float_format=lambda x: f"{x:.5f}")
    )

    print(f"\nBonferroni threshold p < {0.05/len(result):.6f}（family={len(result)}）")
    print(f"Passing: {int(result['bonf_reject'].sum())} / {len(result)}")
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
