"""P0: 三组品种 |ν|/σ 分布测绘

对玉米（DCE.c*）、玉米淀粉（DCE.cs*）、豆粕（DCE.m*）三个品种组
分别运行三视角强度探测，输出分布参数 (μ_D, σ_D) 汇总表。

上游参考: ../structural-shaping-alpha/raw-scripts/corn_1h_strength_three_views.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOL_GROUPS = {
    "corn":           ["DCE.c2601", "DCE.c2603", "DCE.c2605"],
    "corn_starch":    ["DCE.cs2601", "DCE.cs2603", "DCE.cs2605"],
    "soybean_meal":   ["DCE.m2601", "DCE.m2603", "DCE.m2605"],
    "palm_oil":       ["DCE.p2405", "DCE.p2409", "DCE.p2501", "DCE.p2505", "DCE.p2509", "DCE.p2601", "DCE.p2605"],
    "iron_ore":       ["DCE.i2509", "DCE.i2601"],
    "cotton":         ["CZCE.CF509", "CZCE.CF601"],
    "sugar":          ["CZCE.SR601", "CZCE.SR605"],
    "pta":            ["CZCE.TA509", "CZCE.TA601"],
    "rubber":         ["SHFE.rb2601", "SHFE.rb2605"],
    "crude_oil":      ["INE.sc2509", "INE.sc2512"],
}

WINDOWS_HOURS = [20, 40, 80, 160]
STRIDE = 4


def load_1h(sym: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
    return df


def scan_nu_abs(df: pd.DataFrame, W: int) -> np.ndarray:
    """滑动窗口扫描 |ν|/σ。
    返回所有窗口的 |ν|/σ 数组。
    """
    log_rets = df["log_ret"].to_numpy()
    vals = []
    for i in range(0, len(log_rets) - W, STRIDE):
        seg = log_rets[i : i + W]
        if len(seg) < 5:
            continue
        mu = float(np.mean(seg))
        sd = float(np.std(seg, ddof=1))
        if sd <= 0:
            continue
        vals.append(abs(mu) / sd)
    return np.array(vals)


def fit_folded_normal(x: np.ndarray) -> dict:
    """FoldedNormal(μ_D, σ_D) 拟合。
    矩估计：|ν|/σ 的均值 m1 和二阶矩 m2 → 反解 μ_D, σ_D。
    """
    m1 = float(np.mean(x))
    m2 = float(np.mean(x**2))
    # FoldedNormal: E[X] = σ_D * sqrt(2/π) * exp(-μ_D²/(2σ_D²)) + μ_D * (1-2*Φ(-μ_D/σ_D))
    # 矩估计有闭式近似: μ_D ≈ sqrt(m2 - σ_D²) … 但直接用数值优化最简单。
    # 这里用简单矩法: 假设 μ_D >> σ_D 时 E[X] ≈ μ_D, Var[X] ≈ σ_D²
    # 先粗取 μ_D ≈ m1，再调整
    mu_est = m1
    var_est = max(m2 - m1**2, 1e-8)
    sigma_est = math.sqrt(var_est)
    return {"mu_D": round(mu_est, 4), "sigma_D": round(sigma_est, 4)}


def main() -> None:
    rows = []
    for group_name, symbols in SYMBOL_GROUPS.items():
        group_nu_abs = {W: [] for W in WINDOWS_HOURS}
        for sym in symbols:
            df = load_1h(sym)
            print(f"[{group_name}] {sym}: {len(df)} bars")
            for W in WINDOWS_HOURS:
                vals = scan_nu_abs(df, W)
                group_nu_abs[W].extend(vals.tolist())
                print(f"    W={W}h: n={len(vals)}, mean(|ν|/σ)={np.mean(vals):.4f}")

        for W in WINDOWS_HOURS:
            arr = np.array(group_nu_abs[W])
            params = fit_folded_normal(arr)
            p10, p50, p90 = np.percentile(arr, [10, 50, 90])
            strong_pct = (arr >= 0.10).mean() * 100
            rows.append({
                "group": group_name,
                "window_h": W,
                "n_samples": len(arr),
                "mean": round(float(np.mean(arr)), 4),
                "std": round(float(np.std(arr, ddof=1)), 4),
                "mu_D": params["mu_D"],
                "sigma_D": params["sigma_D"],
                "p10": round(float(p10), 4),
                "p50": round(float(p50), 4),
                "p90": round(float(p90), 4),
                "pct_strong_ge_0.10": round(float(strong_pct), 2),
            })

    df_out = pd.DataFrame(rows)
    out_path = OUT_DIR / "p0_strength_profile.csv"
    df_out.to_csv(out_path, index=False)
    print(f"\n写入: {out_path}")
    print(df_out.to_string(index=False))


if __name__ == "__main__":
    main()
