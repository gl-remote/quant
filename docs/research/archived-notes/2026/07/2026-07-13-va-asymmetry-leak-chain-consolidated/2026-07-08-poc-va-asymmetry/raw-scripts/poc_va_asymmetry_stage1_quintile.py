"""
文件级元信息：
- 创建背景：poc-value-area-asymmetry 阶段 1 · IC 已确认存在方向一致的
  微弱负相关（48/48 均负 · |IC|≤0.08）。Spearman IC 只捕捉整体单调关联，
  可能被中段样本稀释；本脚本深入到"极值分位组条件分布"层，看信号是否
  集中在 asymmetry 极端分位、是否存在 U 型 / 尾部效应。
- 用途：读 project_data/logs/poc_va_asymmetry_stage1/long_events.csv
  → 按 contract 内 quintile 分组 → 输出 (window, metric, horizon, quintile)
  的 mean / median / std / p05 / p25 / p75 / p95 / hit_rate / n
  → 计算 top-bottom (Q5-Q1) diff 的 cluster bootstrap 95% CI
  → 单调性检验（Spearman rank of quintile vs mean）。
- 注意事项：临时研究脚本，不进入 workspace/。log 收益单位是 log price ratio
  （无量纲），跨品种可直接汇总；未做 ATR 归一化——若跨品种幅度可比性成
  问题再补。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

METRIC_COLS = ["A1_vol_ratio", "A2_dist_ratio", "A3_skew", "A4_centroid_ratio"]
RET_COLS = ["ret_1h", "ret_2h", "ret_4h", "ret_8h"]
N_QUINTILES = 5
BOOTSTRAP_N = 5000
RNG_SEED = 20260707


def assign_quintile_within_contract(df: pd.DataFrame, metric: str, n: int = N_QUINTILES) -> pd.Series:
    """按 contract 内 rank 分成 n 组（1..n）。"""

    def _quintile(g: pd.Series) -> pd.Series:
        ranks = g.rank(method="first")
        return pd.qcut(ranks, q=n, labels=False, duplicates="drop") + 1

    return df.groupby("contract")[metric].transform(_quintile)


def cluster_bootstrap_diff_mean(
    df: pd.DataFrame,
    ret_col: str,
    quintile_col: str,
    top: int,
    bot: int,
    n_boot: int = BOOTSTRAP_N,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float, float]:
    """按 contract 聚类重抽样，计算 mean(Q_top) - mean(Q_bot) 的 95% CI 与
    双侧 p 值（H0: diff=0）。
    """
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
    top_by_contract: dict[str, np.ndarray] = {}
    bot_by_contract: dict[str, np.ndarray] = {}
    for contract, sub in df.groupby("contract", sort=False):
        top_vals = sub.loc[sub[quintile_col] == top, ret_col].dropna().to_numpy()
        bot_vals = sub.loc[sub[quintile_col] == bot, ret_col].dropna().to_numpy()
        if len(top_vals) > 0:
            top_by_contract[contract] = top_vals
        if len(bot_vals) > 0:
            bot_by_contract[contract] = bot_vals
    contracts = sorted(set(top_by_contract) & set(bot_by_contract))
    if len(contracts) < 2:
        return float("nan"), float("nan"), float("nan"), float("nan")

    all_top = np.concatenate([top_by_contract[c] for c in contracts])
    all_bot = np.concatenate([bot_by_contract[c] for c in contracts])
    obs = float(all_top.mean() - all_bot.mean())

    n_clusters = len(contracts)
    boot = np.empty(n_boot, dtype=np.float64)
    idx_choices = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    for i in range(n_boot):
        picked = idx_choices[i]
        t = np.concatenate([top_by_contract[contracts[j]] for j in picked])
        b = np.concatenate([bot_by_contract[contracts[j]] for j in picked])
        boot[i] = t.mean() - b.mean()
    ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])
    p_gt = float(np.mean(boot > 0))
    p_lt = float(np.mean(boot < 0))
    p_two = 2.0 * min(p_gt, p_lt)
    return obs, float(ci_lo), float(ci_hi), p_two


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    print(f"Loaded long table: rows={len(df)}", flush=True)

    quintile_stats_rows: list[dict] = []
    tb_diff_rows: list[dict] = []
    monotone_rows: list[dict] = []

    for window in ["W1", "W2", "W3"]:
        for metric in METRIC_COLS:
            sub = df[df["window"] == window].copy()
            if sub.empty:
                continue
            sub["q"] = assign_quintile_within_contract(sub, metric)
            sub = sub.dropna(subset=["q"])
            sub["q"] = sub["q"].astype(int)

            for ret_col in RET_COLS:
                # 分位组统计
                for q in range(1, N_QUINTILES + 1):
                    grp = sub[sub["q"] == q][ret_col].dropna()
                    if grp.empty:
                        continue
                    quintile_stats_rows.append(
                        {
                            "window": window,
                            "metric": metric,
                            "horizon": ret_col,
                            "quintile": q,
                            "n": int(len(grp)),
                            "mean": float(grp.mean()),
                            "median": float(grp.median()),
                            "std": float(grp.std()),
                            "p05": float(grp.quantile(0.05)),
                            "p25": float(grp.quantile(0.25)),
                            "p75": float(grp.quantile(0.75)),
                            "p95": float(grp.quantile(0.95)),
                            "hit_pos": float((grp > 0).mean()),
                        }
                    )

                # Q5-Q1 差 + cluster bootstrap
                obs, ci_lo, ci_hi, p_two = cluster_bootstrap_diff_mean(
                    sub, ret_col, "q", top=N_QUINTILES, bot=1
                )
                tb_diff_rows.append(
                    {
                        "window": window,
                        "metric": metric,
                        "horizon": ret_col,
                        "diff_Q5_Q1": obs,
                        "ci_lo": ci_lo,
                        "ci_hi": ci_hi,
                        "p_two": p_two,
                    }
                )

                # 单调性：Q1..Q5 mean 序列的 Spearman rank vs quintile index
                means_by_q = [
                    sub[sub["q"] == q][ret_col].dropna().mean() for q in range(1, N_QUINTILES + 1)
                ]
                if any(math.isnan(m) for m in means_by_q):
                    mono_rho, mono_p = float("nan"), float("nan")
                else:
                    mono_rho, mono_p = stats.spearmanr(range(1, N_QUINTILES + 1), means_by_q)
                monotone_rows.append(
                    {
                        "window": window,
                        "metric": metric,
                        "horizon": ret_col,
                        "monotonic_rho": float(mono_rho) if mono_rho is not None else float("nan"),
                        "monotonic_p": float(mono_p) if mono_p is not None else float("nan"),
                        "mean_Q1": means_by_q[0],
                        "mean_Q3": means_by_q[2],
                        "mean_Q5": means_by_q[4],
                    }
                )

    q_df = pd.DataFrame(quintile_stats_rows)
    tb_df = pd.DataFrame(tb_diff_rows)
    mono_df = pd.DataFrame(monotone_rows)

    q_path = LOG_DIR / "quintile_stats.csv"
    tb_path = LOG_DIR / "top_bottom_diff.csv"
    mono_path = LOG_DIR / "monotonic.csv"
    q_df.to_csv(q_path, index=False)
    tb_df.to_csv(tb_path, index=False)
    mono_df.to_csv(mono_path, index=False)

    # 打印摘要：按 |diff| 降序展示 top 10 组合
    tb_df["abs_diff"] = tb_df["diff_Q5_Q1"].abs()
    print("\n=== Top 10 by |Q5 - Q1| diff ===")
    top10 = tb_df.sort_values("abs_diff", ascending=False).head(10)
    print(
        top10[["window", "metric", "horizon", "diff_Q5_Q1", "ci_lo", "ci_hi", "p_two"]].to_string(
            index=False, float_format=lambda x: f"{x:.5f}"
        )
    )

    # Bonferroni 校正门槛（family=48）
    bonf_alpha = 0.05 / 48
    tb_df["bonf_reject"] = tb_df["p_two"] < bonf_alpha
    print(f"\nBonferroni threshold (alpha=0.05, family=48): p < {bonf_alpha:.5f}")
    print(f"Q5-Q1 diffs passing Bonferroni: {tb_df['bonf_reject'].sum()} / {len(tb_df)}")

    # 单调性摘要
    print("\n=== Monotonicity (Spearman rho of Q1..Q5 mean vs quintile index) ===")
    mono_df["abs_rho"] = mono_df["monotonic_rho"].abs()
    top_mono = mono_df.sort_values("abs_rho", ascending=False).head(10)
    print(
        top_mono[["window", "metric", "horizon", "monotonic_rho", "monotonic_p", "mean_Q1", "mean_Q3", "mean_Q5"]].to_string(
            index=False, float_format=lambda x: f"{x:.5f}"
        )
    )

    # 展示最强组合的完整 Q1..Q5 分布
    print("\n=== Full quintile distribution for the top |Q5-Q1| combo ===")
    top1 = top10.iloc[0]
    win, met, hor = top1["window"], top1["metric"], top1["horizon"]
    sub_q = q_df[(q_df["window"] == win) & (q_df["metric"] == met) & (q_df["horizon"] == hor)]
    print(f"({win}, {met}, {hor})")
    print(sub_q.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

    print("\nOutputs:")
    print(f"  quintile stats -> {q_path}")
    print(f"  top-bottom diff -> {tb_path}")
    print(f"  monotonicity -> {mono_path}")


if __name__ == "__main__":
    main()
