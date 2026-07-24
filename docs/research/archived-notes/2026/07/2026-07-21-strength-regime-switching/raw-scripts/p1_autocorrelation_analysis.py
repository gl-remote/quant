"""P1: |ν|/σ 时间序列自相关与 regime 持续性分析

对每个品种计算：
  1. x̂_{W=80}(t) 滚动窗口序列
  2. ACF/PACF，滞后 240h（10天）
  3. Ljung-Box 白噪声检验
  4. AR(1) 系数、ACF 半衰期（自相关衰减到 0.5 所需滞后）
  5. σ 与 |ν|/σ 的 Spearman 秩相关系数
  6. 三组品种 x̂ 序列间的交叉相关性

上游数据: project_data/market_data/csv/DCE.*.tqsdk.1h.csv
产出: project_data/research/strength_regime_switching/p1_autocorrelation.csv
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOL_GROUPS = {
    "corn": ["DCE.c2601", "DCE.c2603", "DCE.c2605"],
    "corn_starch": ["DCE.cs2601", "DCE.cs2603", "DCE.cs2605"],
    "soybean_meal": ["DCE.m2601", "DCE.m2603", "DCE.m2605"],
}

W_XHAT = 80
MAX_LAG = 240
STRIDE = 4


def load_1h(sym: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
    return df


def compute_x_hat_and_sigma(df: pd.DataFrame, W: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """计算滚动窗口 x̂_W(t) = |ν|/σ 和 σ_t（波动率）。
    返回对齐后的 DataFrame，包含 x_hat, sigma 列。
    """
    log_rets = df["log_ret"].to_numpy()
    x_hat_list = []
    sigma_list = []
    indices = []

    n = len(log_rets)
    for i in range(W-1, n, STRIDE):
        seg = log_rets[i-W+1:i+1]
        mu = np.mean(seg)
        sd = np.std(seg, ddof=1)
        if sd <= 0:
            continue
        x_hat = abs(mu) / sd
        x_hat_list.append(x_hat)
        sigma_list.append(sd)
        indices.append(i)

    df_out = df.iloc[indices].copy()
    df_out["x_hat"] = x_hat_list
    df_out["sigma"] = sigma_list
    return np.array(x_hat_list), np.array(sigma_list), df_out


def acf_half_life(acf_vals: np.ndarray, lags: np.ndarray) -> float:
    """ACF 半衰期：找到第一个 lag 使得 acf <= 0.5。线性插值。"""
    if len(acf_vals) == 0 or acf_vals[0] < 0.5:
        return 1.0
    if np.all(acf_vals > 0.5):
        return float(MAX_LAG)
    i = np.argmax(acf_vals <= 0.5)
    if i == 0:
        return 1.0
    # 插值 between lag i-1 and lag i
    lag_prev = lags[i-1]
    lag_curr = lags[i]
    acf_prev = acf_vals[i-1]
    acf_curr = acf_vals[i]
    # solve: acf_prev + (halflife - lag_prev)*(acf_curr - acf_prev)/(lag_curr - lag_prev) = 0.5
    t = (0.5 - acf_prev) / (acf_curr - acf_prev)
    halflife = lag_prev + t * (lag_curr - lag_prev)
    return float(halflife)


def ljung_box_test(x: np.ndarray, maxlag: int) -> tuple[float, float]:
    """Ljung-Box 检验 H0: 序列是白噪声。
    返回 (statistic, pvalue)。
    """
    from statsmodels.stats.diagnostic import acorr_ljungbox
    df_lb = acorr_ljungbox(x, lags=[maxlag], return_df=True)
    stat = float(df_lb["lb_stat"].iloc[0])
    pval = float(df_lb["lb_pvalue"].iloc[0])
    return stat, pval


def align_cross_corr(dfs: list[pd.DataFrame]) -> tuple[np.ndarray, list[str]]:
    """将三个品种的 x_hat 按 datetime 对齐，返回对齐后的矩阵。"""
    merged = None
    names = []
    for group_name, df in dfs:
        df_g = df[["datetime", "x_hat"]].rename(columns={"x_hat": f"x_{group_name}"})
        if merged is None:
            merged = df_g
        else:
            merged = merged.merge(df_g, on="datetime", how="inner")
        names.append(f"x_{group_name}")
    return merged[names].to_numpy(), names


def main() -> None:
    rows = []
    group_dfs = []
    group_names = []

    for group_name, symbols in SYMBOL_GROUPS.items():
        # 对组内多个合约拼接（保持时序连续性，忽略合约间不重叠）
        dfs_list = []
        for sym in symbols:
            df_raw = load_1h(sym)
            x_hat_arr, sigma_arr, df_window = compute_x_hat_and_sigma(df_raw, W_XHAT)
            dfs_list.append(df_window)
            print(f"[{group_name}] {sym}: n={len(df_window)} windows, mean(x̂)={np.mean(x_hat_arr):.4f}")
        df_group = pd.concat(dfs_list).sort_values("datetime").dropna(subset=["x_hat"]).reset_index(drop=True)
        x_hat = df_group["x_hat"].to_numpy()
        sigma = df_group["sigma"].to_numpy()

        # 计算 Spearman 秩相关 σ vs |ν|/σ
        corr_spearman, p_spearman = stats.spearmanr(x_hat, sigma)

        # Ljung-Box 检验
        if len(x_hat) < MAX_LAG + 5:
            lb_stat, lb_pval = np.nan, np.nan
        else:
            lb_stat, lb_pval = ljung_box_test(x_hat, MAX_LAG)

        # AR(1) 系数
        if len(x_hat) < 2:
            ar1 = np.nan
        else:
            ar1 = float(np.corrcoef(x_hat[:-1], x_hat[1:])[0, 1])

        # ACF 计算（用 statsmodels，因为 numpy 没有自带）
        from statsmodels.tsa.stattools import acf
        acf_vals = acf(x_hat, nlags=MAX_LAG, fft=True)
        # acf_vals[0] = 1.0, acf_vals[1:] = lag 1..MAX_LAG
        lags = np.arange(len(acf_vals))
        half_life_h = acf_half_life(acf_vals[1:], lags[1:])

        # 统计量保存
        rows.append({
            "group": group_name,
            "n_windows": len(x_hat),
            "mean_x_hat": round(float(np.mean(x_hat)), 4),
            "std_x_hat": round(float(np.std(x_hat, ddof=1)), 4),
            "ar1_coef": round(float(ar1) if not np.isnan(ar1) else np.nan, 4),
            "acf_half_life_h": round(half_life_h * STRIDE, 2),  # convert to original 1h bars
            "ljung_box_stat": round(float(lb_stat) if not np.isnan(lb_stat) else np.nan, 2),
            "ljung_box_p": round(float(lb_pval) if not np.isnan(lb_pval) else np.nan, 4),
            "spearman_corr_x_vs_sigma": round(float(corr_spearman), 3),
            "pct_x_ge_0.10": round((x_hat >= 0.10).mean() * 100, 2),
        })

        group_dfs.append((group_name, df_group))
        group_names.append(group_name)
        print(f"[{group_name}] done: ar1={ar1:.3f}, half-life={half_life_h*STRIDE:.1f}h, LB p={lb_pval:.4f}, spearman={corr_spearman:.3f}\n")

    # 计算品种间交叉相关性
    x_aligned, names = align_cross_corr(group_dfs)
    cross_corr_mat = np.corrcoef(x_aligned.T)
    cross_corr_records = []
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            cross_corr_records.append({
                "group_a": names[i].replace("x_", ""),
                "group_b": names[j].replace("x_", ""),
                "cross_corr": round(cross_corr_mat[i, j], 4),
            })

    # 写入汇总 CSV
    df_out = pd.DataFrame(rows)
    out_path = OUT_DIR / "p1_autocorrelation.csv"
    df_out.to_csv(out_path, index=False)
    print(f"\n=== P1 汇总结果写入: {out_path}")
    print(df_out.to_string(index=False))

    # 写入交叉相关性 CSV
    df_cross = pd.DataFrame(cross_corr_records)
    cross_path = OUT_DIR / "p1_cross_correlation.csv"
    df_cross.to_csv(cross_path, index=False)
    print(f"\n=== 交叉相关性写入: {cross_path}")
    print(df_cross.to_string(index=False))

    # 保存对齐后的时间序列（供后续 P2 使用）
    for group_name, df_group in group_dfs:
        ts_path = OUT_DIR / f"p1_xhat_ts_{group_name}.csv"
        df_group.to_csv(ts_path, index=False)
        print(f"\n=== 时间序列写入: {ts_path}")

    # write summary JSON for decision tree
    summary = {
        "gatekeeper": {},
        "decision_tree": {
            "ar1_threshold_0.5": {},
            "spearman_threshold_0.7": {},
        },
    }
    for row in rows:
        g = row["group"]
        summary["gatekeeper"][g] = {
            "ljung_box_p": row["ljung_box_p"],
            "mean_half_life_h": row["acf_half_life_h"],
        }
        summary["decision_tree"][g] = {
            "ar1": row["ar1_coef"],
            "half_life_h": row["acf_half_life_h"],
            "spearman_corr_x_vs_sigma": row["spearman_corr_x_vs_sigma"],
        }
    with open(OUT_DIR / "p1_decision_inputs.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n=== 决策树输入写入: {OUT_DIR / 'p1_decision_inputs.json'}")


if __name__ == "__main__":
    main()
