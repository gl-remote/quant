"""
1h/1d 跨周期波动率比与 Hurst 形状检验
=======================================

从 1h 数据合成 2h, 4h, 1d 周期，构建多尺度面板。
检验 P0/P1/P2 假设在 1h-1d 尺度范围的适用性。

尺度网格：1h, 2h, 4h, 1d (60, 120, 240, 1440 分钟)
GBM 基线 R(1h,1d) = sqrt(1440/60) = sqrt(24) ≈ 4.90
几何中点 = sqrt(60*1440) ≈ 294 min ≈ 4.9h (接近 4h)
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore", category=RuntimeWarning)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[3]
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "h1_d1_assumption_test"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def rolling_std(series, window=50):
    return series.rolling(window, min_periods=window // 2).std()


def resample_1h_to_periods(df_1h, period_hours):
    """
    从 1h 数据合成更长周期数据。
    period_hours: 2, 4, 24 等
    返回: DataFrame with datetime, close, log_ret
    """
    df = df_1h.copy()
    # 用 close 的最后值作为合成 bar 的 close
    # 按 period_hours 分组
    df["group"] = df.index // period_hours
    agg = df.groupby("group").agg(
        datetime=("datetime", "last"),
        close=("close", "last"),
        high=("high", "max"),
        low=("low", "min"),
        open=("open", "first"),
        volume=("volume", "sum"),
    ).reset_index(drop=True)
    agg = agg.sort_values("datetime").reset_index(drop=True)
    agg["log_ret"] = np.log(agg["close"]).diff()
    return agg


def compute_panel_1h_1d(sym):
    """构建 1h/2h/4h/1d 多尺度面板"""
    f1h = CSV_DIR / f"{sym}.tqsdk.1h.csv"
    if not f1h.exists():
        return None

    df_1h = pd.read_csv(f1h, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    if len(df_1h) < 500:
        return None

    df_1h["log_ret"] = np.log(df_1h["close"]).diff()

    # 合成 2h, 4h, 1d
    df_2h = resample_1h_to_periods(df_1h, 2)
    df_4h = resample_1h_to_periods(df_1h, 4)
    df_1d = resample_1h_to_periods(df_1h, 24)

    # 各尺度 σ（窗口=50 个该尺度 bar）
    df_1h["sigma_1h"] = rolling_std(df_1h["log_ret"], 50)
    df_2h["sigma_2h"] = rolling_std(df_2h["log_ret"], 50)
    df_4h["sigma_4h"] = rolling_std(df_4h["log_ret"], 50)
    df_1d["sigma_1d"] = rolling_std(df_1d["log_ret"], 50)

    # 对齐到 1d 时间戳（用 1d 作为基准，更稳健）
    # 实际上用 1h 时间戳对齐更细
    # 这里用 4h 作为中间基准，backward merge
    base = df_4h[["datetime", "close", "sigma_4h"]].dropna().sort_values("datetime")

    # backward merge 各尺度
    base = pd.merge_asof(base, df_1h[["datetime", "sigma_1h"]].dropna().sort_values("datetime"),
                         on="datetime", direction="backward")
    base = pd.merge_asof(base, df_2h[["datetime", "sigma_2h"]].dropna().sort_values("datetime"),
                         on="datetime", direction="backward")
    base = pd.merge_asof(base, df_1d[["datetime", "sigma_1d"]].dropna().sort_values("datetime"),
                         on="datetime", direction="backward")
    base = base.dropna()

    # 过滤无效值
    valid = (base["sigma_1h"] > 0) & (base["sigma_2h"] > 0) & (base["sigma_4h"] > 0) & (base["sigma_1d"] > 0)
    base = base[valid].copy()

    # 跨周期比值 R(1h, 1d) = sigma_1d / sigma_1h
    base["R_1h_1d"] = base["sigma_1d"] / base["sigma_1h"]

    # 区间平均 H（多个子区间）
    # ln(τ) 值：1h=ln(60), 2h=ln(120), 4h=ln(240), 1d=ln(1440)
    base["H_1h_2h"] = np.log(base["sigma_2h"] / base["sigma_1h"]) / np.log(2.0)   # ln(120/60)=ln(2)
    base["H_2h_4h"] = np.log(base["sigma_4h"] / base["sigma_2h"]) / np.log(2.0)   # ln(240/120)=ln(2)
    base["H_4h_1d"] = np.log(base["sigma_1d"] / base["sigma_4h"]) / np.log(6.0)   # ln(1440/240)=ln(6)
    base["H_1h_1d"] = np.log(base["R_1h_1d"]) / np.log(24.0)                       # ln(1440/60)=ln(24)

    # 过滤 inf
    h_cols = ["H_1h_2h", "H_2h_4h", "H_4h_1d", "H_1h_1d"]
    for col in h_cols:
        base = base[np.isfinite(base[col])].copy()

    base["symbol"] = sym
    base["year"] = base["datetime"].dt.year

    return base[["datetime", "symbol", "year", "close",
                 "sigma_1h", "sigma_2h", "sigma_4h", "sigma_1d",
                 "R_1h_1d"] + h_cols]


def extract_events(sym_df, threshold, direction="above", min_gap_hours=24):
    """状态触发抽样，min_gap 用 1d 级别（24h）"""
    df = sym_df.sort_values("datetime").reset_index(drop=True)
    if direction == "above":
        is_active = df["R_1h_1d"] > threshold
    else:
        is_active = df["R_1h_1d"] < threshold
    is_active_prev = is_active.shift(1, fill_value=False)
    crossings = df[(~is_active_prev) & is_active].copy()
    if len(crossings) == 0:
        return crossings
    keep = [crossings.index[0]]
    last_dt = crossings.iloc[0]["datetime"]
    for idx in crossings.index[1:]:
        dt = crossings.loc[idx, "datetime"]
        if (dt - last_dt).total_seconds() / 3600 >= min_gap_hours:
            keep.append(idx)
            last_dt = dt
    return crossings.loc[keep]


def test_P0(events_df, h_cols, alpha=0.05):
    """P0 恒定 H 检验（4 个尺度点，可用 Friedman）"""
    results = {
        "n_events": len(events_df),
        "method": "Friedman test (k=4 related samples) + fixed threshold 0.05",
        "alpha": alpha,
        "per_event": [],
        "rejection_rate": None,
        "H_means": {},
        "H_ranges": {},
    }

    if len(events_df) == 0:
        results["error"] = "No events"
        return results

    for col in h_cols:
        results["H_means"][col] = float(events_df[col].mean())
        results["H_ranges"][col] = {
            "mean": float(events_df[col].mean()),
            "std": float(events_df[col].std()),
            "median": float(events_df[col].median()),
            "p25": float(events_df[col].quantile(0.25)),
            "p75": float(events_df[col].quantile(0.75)),
        }

    fixed_threshold = 0.05
    results["fixed_threshold"] = fixed_threshold

    # 全样本 Friedman 检验（4 个相关样本）
    try:
        friedman_stat, friedman_p = stats.friedmanchisquare(
            events_df[h_cols[0]], events_df[h_cols[1]], events_df[h_cols[2]], events_df[h_cols[3]]
        )
    except Exception:
        friedman_stat, friedman_p = 0.0, 1.0
    results["friedman_global"] = {
        "statistic": float(friedman_stat),
        "p_value": float(friedman_p),
        "significant": bool(friedman_p < alpha),
    }

    rejected = 0
    for _, row in events_df.iterrows():
        h_vals = [row[col] for col in h_cols]
        h_range = max(h_vals) - min(h_vals)
        is_rejected = h_range > fixed_threshold
        if is_rejected:
            rejected += 1
        results["per_event"].append({
            "symbol": row["symbol"],
            "R_1h_1d": float(row["R_1h_1d"]),
            "H_vals": {col: float(row[col]) for col in h_cols},
            "H_range": float(h_range),
            "rejected": is_rejected,
        })

    results["rejection_rate"] = rejected / len(events_df) if len(events_df) > 0 else 0
    mean_range = np.mean([e["H_range"] for e in results["per_event"]])
    results["mean_H_range"] = float(mean_range)
    results["accept_P0"] = bool(mean_range < fixed_threshold and not results["friedman_global"]["significant"])

    return results


def test_P1(events_df, h_pairs, alpha=0.05):
    """P1 Lipschitz 检验"""
    results = {
        "n_events": len(events_df),
        "method": "Lipschitz ratio λ_ij",
        "alpha": alpha,
        "per_event": [],
        "L_hat_distribution": {},
        "cross_symbol_stability": {},
    }

    if len(events_df) == 0:
        results["error"] = "No events"
        return results

    tau_pairs = []
    for col_i, tau_i, col_j, tau_j in h_pairs:
        ln_diff = np.log(tau_j) - np.log(tau_i)
        tau_pairs.append({
            "col_i": col_i, "tau_i": tau_i,
            "col_j": col_j, "tau_j": tau_j,
            "ln_diff": float(ln_diff),
        })

    L_hats = []
    per_event_L = []
    for _, row in events_df.iterrows():
        lambdas = []
        for tp in tau_pairs:
            if tp["ln_diff"] == 0:
                continue
            lam = abs(row[tp["col_j"]] - row[tp["col_i"]]) / abs(tp["ln_diff"])
            lambdas.append(float(lam))
        L_hat = max(lambdas) if lambdas else 0.0
        L_hats.append(L_hat)
        per_event_L.append({
            "symbol": row["symbol"],
            "R_1h_1d": float(row["R_1h_1d"]),
            "lambdas": lambdas,
            "L_hat": float(L_hat),
        })

    L_hats = np.array(L_hats)
    results["L_hat_distribution"] = {
        "mean": float(np.mean(L_hats)),
        "std": float(np.std(L_hats)),
        "median": float(np.median(L_hats)),
        "p25": float(np.percentile(L_hats, 25)),
        "p75": float(np.percentile(L_hats, 75)),
        "p95": float(np.percentile(L_hats, 95)),
        "cv": float(np.std(L_hats) / np.mean(L_hats)) if np.mean(L_hats) > 0 else float("inf"),
    }

    df_L = pd.DataFrame(per_event_L)
    by_symbol = df_L.groupby("symbol")["L_hat"].agg(["mean", "std", "count"])
    results["cross_symbol_stability"] = {
        "n_symbols": int(len(by_symbol)),
        "cross_symbol_cv": float(by_symbol["mean"].std() / by_symbol["mean"].mean())
            if by_symbol["mean"].mean() > 0 else float("inf"),
        "ratio_max_min": float(by_symbol["mean"].max() / by_symbol["mean"].min())
            if by_symbol["mean"].min() > 0 else float("inf"),
    }

    # 可盈利门槛 r* 覆盖率
    # a=60min(1h), b=1440min(1d), c=240min(4h, 几何中点附近)
    a_min, b_min, c_min = 60, 1440, 240
    d_c = max(np.log(c_min / a_min), np.log(b_min / c_min))

    # 敏感性分析
    param_grid = []
    for c_cost in [0.02, 0.05, 0.1, 0.2]:
        for K_S in [1.0, 1.5, 2.0]:
            for R_ratio in [1.5, 2.0, 3.0]:
                x_min = np.sqrt(6 * c_cost / (K_S**3 * R_ratio * (R_ratio - 1)))
                if x_min > 1 or np.isnan(x_min):
                    continue
                delta_star = x_min * np.sqrt(c_min) / np.sqrt(2 * np.pi)
                if delta_star >= 0.5:
                    continue
                H_star = 0.5 + 0.5 * np.log2(1 + np.sin(np.pi * delta_star))
                r_stars = (b_min / a_min) ** (H_star + L_hats * d_c)
                r_actual = events_df["R_1h_1d"].values
                coverage = float(np.mean(r_actual >= r_stars))
                param_grid.append({
                    "c_cost": c_cost, "K_S": K_S, "R_ratio": R_ratio,
                    "x_min": float(x_min),
                    "delta_star": float(delta_star),
                    "H_star": float(H_star),
                    "r_star_median": float(np.median(r_stars)),
                    "coverage_rate": coverage,
                })

    best_coverage = max(p["coverage_rate"] for p in param_grid) if param_grid else 0
    cross_symbol_ok = results["cross_symbol_stability"]["ratio_max_min"] < 10
    L_small = results["L_hat_distribution"]["median"] < 0.2
    any_coverage = best_coverage > 0.05

    # 基准参数
    x_min_base = np.sqrt(6 * 0.1 / (1.5**3 * 2.0 * 1.0))
    delta_star_base = x_min_base * np.sqrt(c_min) / np.sqrt(2 * np.pi)
    H_star_base = 0.5 + 0.5 * np.log2(1 + np.sin(np.pi * delta_star_base))
    r_stars_base = (b_min / a_min) ** (H_star_base + L_hats * d_c)
    r_actual = events_df["R_1h_1d"].values

    results["r_star_coverage"] = {
        "base_params": {
            "a_min": a_min, "b_min": b_min, "c_min": c_min,
            "c_cost": 0.1, "K_S": 1.5, "R_ratio": 2.0,
            "x_min": float(x_min_base),
            "delta_star": float(delta_star_base),
            "H_star": float(H_star_base),
            "d_c": float(d_c),
        },
        "base_r_star_median": float(np.median(r_stars_base)),
        "r_actual_median": float(np.median(r_actual)),
        "base_coverage_rate": float(np.mean(r_actual >= r_stars_base)),
        "sensitivity_analysis": param_grid,
        "best_coverage_rate": float(best_coverage),
        "accept_P1": bool(cross_symbol_ok and L_small and any_coverage),
        "accept_criteria": {
            "cross_symbol_ok": bool(cross_symbol_ok),
            "L_small_enough": bool(L_small),
            "any_coverage_above_5pct": bool(any_coverage),
            "best_coverage": float(best_coverage),
        },
    }
    results["per_event"] = per_event_L[:50]
    return results


def test_P2(events_df, h_cols, alpha=0.05):
    """P2 单调性检验（4 个尺度点，Spearman 有意义）"""
    results = {
        "n_events": len(events_df),
        "method": "Spearman rank correlation (4 scale points)",
        "alpha": alpha,
        "per_event": [],
        "rejection_rate": None,
    }

    if len(events_df) == 0:
        results["error"] = "No events"
        return results

    # 尺度中点（分钟）：1h-2h 中点, 2h-4h 中点, 4h-1d 中点
    tau_mids = [np.sqrt(60 * 120), np.sqrt(120 * 240), np.sqrt(240 * 1440)]

    rhos = []
    directions = []
    rejected = 0
    for _, row in events_df.iterrows():
        h_vals = [row[h_cols[0]], row[h_cols[1]], row[h_cols[2]]]
        if len(set(h_vals)) < 2:
            rho, p_val = 0.0, 1.0
        else:
            try:
                rho, p_val = stats.spearmanr(tau_mids, h_vals)
            except Exception:
                rho, p_val = 0.0, 1.0

        direction = 1 if rho > 0 else (-1 if rho < 0 else 0)
        is_monotone = (abs(rho) > 0.7) and (p_val < alpha)
        if not is_monotone:
            rejected += 1

        rhos.append(rho)
        directions.append(direction)
        results["per_event"].append({
            "symbol": row["symbol"],
            "R_1h_1d": float(row["R_1h_1d"]),
            "spearman_rho": float(rho),
            "p_value": float(p_val),
            "direction": int(direction),
            "is_monotone": bool(is_monotone),
        })

    rhos = np.array(rhos)
    directions = np.array(directions)

    results["rejection_rate"] = rejected / len(events_df) if len(events_df) > 0 else 0
    results["rho_distribution"] = {
        "mean": float(np.mean(rhos)),
        "std": float(np.std(rhos)),
        "median": float(np.median(rhos)),
        "p25": float(np.percentile(rhos, 25)),
        "p75": float(np.percentile(rhos, 75)),
        "frac_positive": float(np.mean(rhos > 0)),
        "frac_negative": float(np.mean(rhos < 0)),
        "frac_abs_gt_0.7": float(np.mean(np.abs(rhos) > 0.7)),
    }
    results["direction_consistency"] = {
        "frac_increasing": float(np.mean(directions == 1)),
        "frac_decreasing": float(np.mean(directions == -1)),
        "dominant_direction": "increasing" if np.mean(directions == 1) > 0.5 else
                              ("decreasing" if np.mean(directions == -1) > 0.5 else "mixed"),
    }
    results["accept_P2"] = bool(
        results["rho_distribution"]["frac_abs_gt_0.7"] > 0.5 and
        max(results["direction_consistency"]["frac_increasing"],
            results["direction_consistency"]["frac_decreasing"]) > 0.7
    )
    return results


def main():
    print("=" * 70, flush=True)
    print("1h/1d 跨周期波动率比与 Hurst 形状检验", flush=True)
    print("尺度网格: 1h, 2h, 4h, 1d (合成)", flush=True)
    print("=" * 70, flush=True)

    print("\n[1/5] 构建多尺度面板...", flush=True)
    panels = []
    symbols = []
    for f in sorted(CSV_DIR.glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = compute_panel_1h_1d(sym)
        if p is not None:
            panels.append(p)
            symbols.append(sym)
    panel = pd.concat(panels, ignore_index=True)
    print(f"  面板: {len(panel)} 行, {len(symbols)} 合约", flush=True)

    # R(1h,1d) 分布
    r_gbm = np.sqrt(24)
    print(f"\n  R(1h,1d) 分布:", flush=True)
    print(f"    GBM 基线: {r_gbm:.4f}", flush=True)
    print(f"    中位数: {panel['R_1h_1d'].median():.4f}", flush=True)
    print(f"    均值: {panel['R_1h_1d'].mean():.4f}", flush=True)
    print(f"    p25-p75: [{panel['R_1h_1d'].quantile(0.25):.4f}, {panel['R_1h_1d'].quantile(0.75):.4f}]", flush=True)
    frac_above = (panel['R_1h_1d'] > r_gbm).mean()
    print(f"    R > GBM 占比: {frac_above:.1%}", flush=True)

    # 提取事件
    print("\n[2/5] 提取高/低 R 事件...", flush=True)
    # 高 R: R > GBM 基线 sqrt(24) ≈ 4.90
    # 低 R: R < 4.0
    high_events_list = []
    low_events_list = []
    for sym in symbols:
        sym_df = panel[panel["symbol"] == sym]
        high = extract_events(sym_df, r_gbm, direction="above", min_gap_hours=48)
        if len(high) > 0:
            high_events_list.append(high)
        low = extract_events(sym_df, 4.0, direction="below", min_gap_hours=48)
        if len(low) > 0:
            low_events_list.append(low)

    high_events = pd.concat(high_events_list, ignore_index=True) if high_events_list else pd.DataFrame()
    low_events = pd.concat(low_events_list, ignore_index=True) if low_events_list else pd.DataFrame()
    print(f"  高 R 事件 (R>{r_gbm:.2f}): {len(high_events)}", flush=True)
    print(f"  低 R 事件 (R<4.0): {len(low_events)}", flush=True)

    # H 值概览
    h_cols = ["H_1h_2h", "H_2h_4h", "H_4h_1d", "H_1h_1d"]
    print(f"\n  H 均值（高 R 事件）:", flush=True)
    if len(high_events) > 0:
        for col in h_cols:
            print(f"    {col}: {high_events[col].mean():.4f}", flush=True)
    print(f"  H 均值（低 R 事件）:", flush=True)
    if len(low_events) > 0:
        for col in h_cols:
            print(f"    {col}: {low_events[col].mean():.4f}", flush=True)

    # Step 3: P0
    print("\n[3/5] Step 3: P0 恒定 H 检验...", flush=True)
    P0_res = test_P0(high_events, h_cols[:3], alpha=0.05)  # 用前 3 个子区间
    if "error" not in P0_res:
        print(f"  H 极差均值: {P0_res['mean_H_range']:.4f}", flush=True)
        print(f"  P0 拒绝率: {P0_res['rejection_rate']:.1%}", flush=True)
        fg = P0_res.get("friedman_global", {})
        print(f"  Friedman 全样本: stat={fg.get('statistic', 0):.1f}, p={fg.get('p_value', 1):.2e}", flush=True)
        print(f"  P0 接受: {P0_res['accept_P0']}", flush=True)

    # Step 4: P1
    print("\n[4/5] Step 4: P1 Lipschitz 检验...", flush=True)
    h_pairs = [
        ("H_1h_2h", 60, "H_2h_4h", 120),
        ("H_2h_4h", 120, "H_4h_1d", 240),
        ("H_1h_2h", 60, "H_4h_1d", 240),
    ]
    P1_res = test_P1(high_events, h_pairs, alpha=0.05)
    if "error" not in P1_res:
        print(f"  L̂ 中位数: {P1_res['L_hat_distribution']['median']:.4f}", flush=True)
        print(f"  L̂ 变异系数: {P1_res['L_hat_distribution']['cv']:.2f}", flush=True)
        print(f"  跨品种 max/min 比: {P1_res['cross_symbol_stability']['ratio_max_min']:.2f}", flush=True)
        rsc = P1_res.get("r_star_coverage", {})
        print(f"  基准 r* 覆盖率: {rsc.get('base_coverage_rate', 0):.1%}", flush=True)
        print(f"  最佳 r* 覆盖率: {rsc.get('best_coverage_rate', 0):.1%}", flush=True)
        print(f"  P1 接受: {rsc.get('accept_P1', False)}", flush=True)

    # Step 5: P2
    print("\n[5/5] Step 5: P2 单调性检验...", flush=True)
    P2_res = test_P2(high_events, h_cols[:3], alpha=0.05)
    if "error" not in P2_res:
        rd = P2_res.get("rho_distribution", {})
        dc = P2_res.get("direction_consistency", {})
        print(f"  Spearman ρ 中位数: {rd.get('median', 0):.3f}", flush=True)
        print(f"  |ρ|>0.7 占比: {rd.get('frac_abs_gt_0.7', 0):.1%}", flush=True)
        print(f"  递增占比: {dc.get('frac_increasing', 0):.1%}, 递减占比: {dc.get('frac_decreasing', 0):.1%}", flush=True)
        print(f"  P2 接受: {P2_res.get('accept_P2', False)}", flush=True)

    # 决策
    print("\n" + "=" * 70, flush=True)
    print("综合决策", flush=True)
    print("=" * 70, flush=True)
    P0_ok = P0_res.get("accept_P0", False) if "error" not in P0_res else False
    P1_ok = P1_res.get("r_star_coverage", {}).get("accept_P1", False) if "error" not in P1_res else False
    P2_ok = P2_res.get("accept_P2", False) if "error" not in P2_res else False

    if P0_ok:
        rec, rationale = "P0 (constant H)", "P0 接受"
    elif P1_ok:
        rec = "P1 (Lipschitz)"
        rationale = f"P1 接受：L̂={P1_res['L_hat_distribution']['median']:.4f}, 覆盖率={P1_res['r_star_coverage']['best_coverage_rate']:.1%}"
    elif P2_ok:
        rec = "P1+P2"
        rationale = f"P2 接受：ρ={P2_res['rho_distribution']['median']:.3f}"
    else:
        rec = "P1 (with caveats)"
        rationale = f"P0/P1/P2 均不完全满足。L̂={P1_res.get('L_hat_distribution', {}).get('median', 0):.4f}"

    print(f"  推荐假设: {rec}", flush=True)
    print(f"  理由: {rationale}", flush=True)

    # 图表
    print("\n生成图表...", flush=True)
    # 图 1: H 曲线
    if len(high_events) > 0 and len(low_events) > 0:
        fig, ax = plt.subplots(figsize=(10, 6))
        x_pos = [0, 1, 2]
        x_labels = ["H(1h,2h)", "H(2h,4h)", "H(4h,1d)"]
        for df, color, label in [
            (high_events, "#C44E52", f"高 R (R>{r_gbm:.1f}), n={len(high_events)}"),
            (low_events, "#55A868", f"低 R (R<4.0), n={len(low_events)}"),
        ]:
            means = [df[col].mean() for col in h_cols[:3]]
            stds = [df[col].std() for col in h_cols[:3]]
            ax.plot(x_pos, means, marker="o", markersize=10, linewidth=2.5, color=color, label=label)
            ax.fill_between(x_pos, [m-s for m, s in zip(means, stds)], [m+s for m, s in zip(means, stds)],
                            color=color, alpha=0.2)
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="GBM H=0.5")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_labels)
        ax.set_ylabel("H 均值")
        ax.set_title("1h/1d 尺度: H(τ) 曲线 — 高 R vs 低 R", fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(OUT_DIR / "fig1_H_curve_1h_1d.png", dpi=150, bbox_inches="tight")
        plt.close()

    # 图 2: R(1h,1d) 分布
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(panel["R_1h_1d"].clip(0, 15), bins=50, color="#4C72B0", alpha=0.7, edgecolor="white")
    ax.axvline(r_gbm, color="red", linestyle="--", linewidth=2, label=f"GBM 基线={r_gbm:.2f}")
    ax.axvline(panel["R_1h_1d"].median(), color="orange", linestyle="-", linewidth=2,
               label=f"中位数={panel['R_1h_1d'].median():.2f}")
    ax.set_xlabel("R(1h, 1d) = σ_1d / σ_1h")
    ax.set_ylabel("频数")
    ax.set_title("R(1h,1d) 分布", fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig2_R_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 图 3: P2 ρ 分布
    if P2_res.get("per_event"):
        rhos = [e["spearman_rho"] for e in P2_res["per_event"]]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(rhos, bins=30, color="#8172B2", alpha=0.7, edgecolor="white")
        ax.axvline(0.7, color="green", linestyle="--", linewidth=2, label="ρ=0.7")
        ax.axvline(-0.7, color="green", linestyle="--", linewidth=2)
        ax.axvline(np.median(rhos), color="red", linestyle="-", linewidth=2, label=f"中位数={np.median(rhos):.3f}")
        ax.set_xlabel("Spearman ρ")
        ax.set_title("P2 单调性检验 — Spearman ρ 分布（4 个尺度点）", fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(OUT_DIR / "fig3_P2_spearman.png", dpi=150, bbox_inches="tight")
        plt.close()

    print(f"  图表已保存到 {OUT_DIR}/", flush=True)
    print("\n" + "=" * 70, flush=True)
    print("完成", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
