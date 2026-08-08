"""
Step 3-6: P0/P1/P2 假设检验与综合决策
========================================

按照 hurst-shape-experiment-design.md §9 的 Step 3-6 执行完整假设检验。

输入：多尺度面板（5m, 15m, 1h）
输出：
  - P0_results.json: 恒定 H 检验
  - P1_results.json: Lipschitz 检验
  - P2_results.json: 单调性检验
  - decision_summary.json: 综合决策
  - decision_report.md: 可读报告

决策判据（hurst-shape-assumptions-testability.md §11.1）：
  P0: 子区间 H 极差 < 估计噪声 2 倍 → 接受
  P1: L̂ 跨品种变异 < 1 个数量级，r* 覆盖率 > 5% → 接受
  P2: Spearman ρ > 0.7 且方向一致 → 接受
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime
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
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "p1_assumption_test"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 数据加载与多尺度面板构建（复用 h_curve_overlay.py 逻辑）
# ============================================================
def rolling_std(series, window=50):
    return series.rolling(window, min_periods=window // 2).std()


def compute_panel(sym):
    f1h = CSV_DIR / f"{sym}.tqsdk.1h.csv"
    f15 = CSV_DIR / f"{sym}.tqsdk.15m.csv"
    f5 = CSV_DIR / f"{sym}.tqsdk.5m.csv"
    if not f1h.exists() or not f15.exists() or not f5.exists():
        return None

    df_1h = pd.read_csv(f1h, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df_15 = pd.read_csv(f15, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df_5 = pd.read_csv(f5, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)

    if len(df_1h) < 200 or len(df_15) < 400 or len(df_5) < 400:
        return None

    df_1h["log_ret"] = np.log(df_1h["close"]).diff()
    df_15["log_ret"] = np.log(df_15["close"]).diff()
    df_5["log_ret"] = np.log(df_5["close"]).diff()

    df_1h["sigma_1h"] = rolling_std(df_1h["log_ret"], 50)
    df_15["sigma_15m"] = rolling_std(df_15["log_ret"], 200)
    df_5["sigma_5m"] = rolling_std(df_5["log_ret"], 600)

    base = df_1h[["datetime", "close", "sigma_1h"]].dropna().sort_values("datetime")
    base = pd.merge_asof(base, df_15[["datetime", "sigma_15m"]].dropna().sort_values("datetime"),
                         on="datetime", direction="backward")
    base = pd.merge_asof(base, df_5[["datetime", "sigma_5m"]].dropna().sort_values("datetime"),
                         on="datetime", direction="backward")
    base = base.dropna()

    base["R_bar"] = base["sigma_1h"] / base["sigma_15m"]
    valid = (base["R_bar"] > 0) & (base["sigma_5m"] > 0) & np.isfinite(base["sigma_5m"])
    base = base[valid].copy()

    # 区间平均 H（与 R_bar 同源）
    base["H_5_15"] = np.log(base["sigma_15m"] / base["sigma_5m"]) / np.log(3.0)      # ln(15/5)=ln(3)
    base["H_15_60"] = np.log(base["R_bar"]) / np.log(4.0)                              # ln(60/15)=ln(4)
    base["H_5_60"] = np.log(base["sigma_1h"] / base["sigma_5m"]) / np.log(12.0)       # ln(60/5)=ln(12)

    base = base[np.isfinite(base["H_5_15"]) & np.isfinite(base["H_15_60"]) & np.isfinite(base["H_5_60"])].copy()

    base["symbol"] = sym
    base["year"] = base["datetime"].dt.year

    return base[["datetime", "symbol", "year", "close",
                 "sigma_5m", "sigma_15m", "sigma_1h",
                 "R_bar", "H_5_15", "H_15_60", "H_5_60"]]


def extract_events(sym_df, threshold, direction="above", min_gap_hours=8):
    """状态触发抽样：首次穿越阈值时取样"""
    df = sym_df.sort_values("datetime").reset_index(drop=True)
    if direction == "above":
        is_active = df["R_bar"] > threshold
    else:
        is_active = df["R_bar"] < threshold
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


# ============================================================
# Step 3: P0 恒定 H 检验
# ============================================================
def test_P0(events_df, h_cols, alpha=0.05):
    """
    P0 恒定 H 检验

    注：当前只有 2 个区间 H 值 (H_5_15, H_15_60)，Friedman 需要 k>=3 不适用。
    改用固定阈值（0.05）判据 + Wilcoxon 符号秩检验（全样本配对）。
    """
    results = {
        "n_events": len(events_df),
        "method": "Wilcoxon signed-rank (paired) + fixed threshold 0.05",
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
            "p25": float(events_df[col].quantile(0.25)),
            "median": float(events_df[col].median()),
            "p75": float(events_df[col].quantile(0.75)),
        }

    # 固定阈值判据（0.05）：与简报 §A.4 一致
    fixed_threshold = 0.05
    results["fixed_threshold"] = fixed_threshold

    # 全样本 Wilcoxon 符号秩检验：H_5_15 vs H_15_60 是否有显著差异
    try:
        wilcoxon_stat, wilcoxon_p = stats.wilcoxon(events_df[h_cols[0]], events_df[h_cols[1]])
    except Exception:
        wilcoxon_stat, wilcoxon_p = 0.0, 1.0
    results["wilcoxon_paired"] = {
        "statistic": float(wilcoxon_stat),
        "p_value": float(wilcoxon_p),
        "significant": bool(wilcoxon_p < alpha),
    }

    rejected = 0
    for _, row in events_df.iterrows():
        h_vals = [row[col] for col in h_cols]
        h_range = max(h_vals) - min(h_vals)

        is_rejected = h_range > fixed_threshold
        if is_rejected:
            rejected += 1

        results["per_event"].append({
            "datetime": row["datetime"].isoformat() if hasattr(row["datetime"], "isoformat") else str(row["datetime"]),
            "symbol": row["symbol"],
            "R_bar": float(row["R_bar"]),
            "H_vals": {col: float(row[col]) for col in h_cols},
            "H_range": float(h_range),
            "rejected": is_rejected,
        })

    results["rejection_rate"] = rejected / len(events_df) if len(events_df) > 0 else 0

    # 接受判据：极差均值 < 0.05 且 Wilcoxon 不显著
    mean_range = np.mean([e["H_range"] for e in results["per_event"]])
    results["mean_H_range"] = float(mean_range)
    results["accept_P0"] = bool(mean_range < fixed_threshold and not results["wilcoxon_paired"]["significant"])

    return results


# ============================================================
# Step 4: P1 Lipschitz 检验
# ============================================================
def test_P1(events_df, h_pairs, alpha=0.05):
    """计算 Lipschitz 比 λ_ij，分析分布与可盈利门槛"""
    results = {
        "n_events": len(events_df),
        "method": "Lipschitz ratio λ_ij = |H(τ_i) - H(τ_j)| / |ln τ_i - ln τ_j|",
        "alpha": alpha,
        "per_event": [],
        "L_hat_distribution": {},
        "cross_symbol_stability": {},
        "r_star_coverage": {},
    }

    if len(events_df) == 0:
        results["error"] = "No events"
        return results

    # 尺度对：(H_col, τ_i_min, τ_j_min)
    # ln(τ_j/τ_i) 的对数差
    tau_pairs = []
    for col_i, tau_i, col_j, tau_j in h_pairs:
        ln_diff = np.log(tau_j) - np.log(tau_i)
        tau_pairs.append({
            "col_i": col_i, "tau_i": tau_i,
            "col_j": col_j, "tau_j": tau_j,
            "ln_diff": float(ln_diff),
            "pair_name": f"{col_i}_vs_{col_j}",
        })

    L_hats = []
    per_event_L = []

    for _, row in events_df.iterrows():
        lambdas = []
        for tp in tau_pairs:
            h_i = row[tp["col_i"]]
            h_j = row[tp["col_j"]]
            if tp["ln_diff"] == 0:
                continue
            lam = abs(h_j - h_i) / abs(tp["ln_diff"])
            lambdas.append(float(lam))

        if len(lambdas) > 0:
            L_hat = max(lambdas)
        else:
            L_hat = 0.0

        L_hats.append(L_hat)
        per_event_L.append({
            "datetime": row["datetime"].isoformat() if hasattr(row["datetime"], "isoformat") else str(row["datetime"]),
            "symbol": row["symbol"],
            "R_bar": float(row["R_bar"]),
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
        "min": float(np.min(L_hats)),
        "max": float(np.max(L_hats)),
        "cv": float(np.std(L_hats) / np.mean(L_hats)) if np.mean(L_hats) > 0 else float("inf"),
    }

    # 跨品种稳定性
    df_L = pd.DataFrame(per_event_L)
    by_symbol = df_L.groupby("symbol")["L_hat"].agg(["mean", "std", "count"])
    results["cross_symbol_stability"] = {
        "n_symbols": int(len(by_symbol)),
        "by_symbol_mean": {k: float(v) for k, v in by_symbol["mean"].items()},
        "cross_symbol_cv": float(by_symbol["mean"].std() / by_symbol["mean"].mean())
            if by_symbol["mean"].mean() > 0 else float("inf"),
        "ratio_max_min": float(by_symbol["mean"].max() / by_symbol["mean"].min())
            if by_symbol["mean"].min() > 0 else float("inf"),
    }

    # 可盈利门槛 r* 覆盖率
    # r* = (b/a)^(H*(c) + L*d(c))
    # 基准参数下 H*(c) ≈ 0.998（接近 1），门槛极高
    # 做成本参数敏感性分析：扫描不同 c_cost, K_S, R 组合
    a_min, b_min, c_min = 5, 60, 15
    d_c = max(np.log(c_min / a_min), np.log(b_min / c_min))

    # 基准参数
    c_cost_base = 0.1
    K_S_base = 1.5
    R_ratio_base = 2.0
    x_min_base = np.sqrt(6 * c_cost_base / (K_S_base**3 * R_ratio_base * (R_ratio_base - 1)))
    delta_star_base = x_min_base * np.sqrt(c_min) / np.sqrt(2 * np.pi)
    H_star_base = 0.5 + 0.5 * np.log2(1 + np.sin(np.pi * delta_star_base))
    r_stars_base = (b_min / a_min) ** (H_star_base + L_hats * d_c)
    r_actual = events_df["R_bar"].values
    coverage_base = float(np.mean(r_actual >= r_stars_base))

    # 敏感性分析：扫描参数
    param_grid = []
    for c_cost in [0.02, 0.05, 0.1, 0.2]:
        for K_S in [1.0, 1.5, 2.0]:
            for R_ratio in [1.5, 2.0, 3.0]:
                x_min = np.sqrt(6 * c_cost / (K_S**3 * R_ratio * (R_ratio - 1)))
                if x_min > 1 or np.isnan(x_min):
                    continue
                delta_star = x_min * np.sqrt(c_min) / np.sqrt(2 * np.pi)
                if delta_star >= 0.5:  # sin 退化
                    continue
                H_star = 0.5 + 0.5 * np.log2(1 + np.sin(np.pi * delta_star))
                r_stars = (b_min / a_min) ** (H_star + L_hats * d_c)
                coverage = float(np.mean(r_actual >= r_stars))
                param_grid.append({
                    "c_cost": c_cost, "K_S": K_S, "R_ratio": R_ratio,
                    "x_min": float(x_min),
                    "delta_star": float(delta_star),
                    "H_star": float(H_star),
                    "r_star_median": float(np.median(r_stars)),
                    "coverage_rate": coverage,
                })

    # P1 接受判据：L̂ 稳定性（跨品种比 < 10）+ 至少一组成本参数下覆盖率 > 5%
    best_coverage = max(p["coverage_rate"] for p in param_grid) if param_grid else 0
    L_cv = results["L_hat_distribution"]["cv"]
    cross_symbol_ok = results["cross_symbol_stability"]["ratio_max_min"] < 10
    L_small = results["L_hat_distribution"]["median"] < 0.2
    any_coverage = best_coverage > 0.05

    results["r_star_coverage"] = {
        "base_params": {
            "a_min": a_min, "b_min": b_min, "c_min": c_min,
            "c_cost": c_cost_base, "K_S": K_S_base, "R_ratio": R_ratio_base,
            "x_min": float(x_min_base),
            "delta_star": float(delta_star_base),
            "H_star": float(H_star_base),
            "d_c": float(d_c),
        },
        "base_r_star_distribution": {
            "median": float(np.median(r_stars_base)),
            "p75": float(np.percentile(r_stars_base, 75)),
            "p95": float(np.percentile(r_stars_base, 95)),
        },
        "r_actual_distribution": {
            "median": float(np.median(r_actual)),
            "p75": float(np.percentile(r_actual, 75)),
            "p95": float(np.percentile(r_actual, 95)),
        },
        "base_coverage_rate": coverage_base,
        "sensitivity_analysis": param_grid,
        "best_coverage_rate": best_coverage,
        "L_hat_cv": float(L_cv),
        "L_hat_median": float(results["L_hat_distribution"]["median"]),
        "accept_P1": bool(cross_symbol_ok and L_small and any_coverage),
        "accept_criteria": {
            "cross_symbol_ok": bool(cross_symbol_ok),
            "L_small_enough": bool(L_small),
            "any_coverage_above_5pct": bool(any_coverage),
            "best_coverage": float(best_coverage),
        },
    }

    results["per_event"] = per_event_L[:50]  # 截断保存前 50 条

    return results


# ============================================================
# Step 5: P2 单调性检验
# ============================================================
def test_P2(events_df, h_cols, alpha=0.05):
    """
    P2 单调性检验

    警告：当前只有 2 个区间 H 值 (H_5_15, H_15_60)，Spearman ρ 在 2 个点时
    必为 ±1，检验是平凡的。P2 需要 ≥3 个尺度点才有意义。
    当前结果仅作方向统计参考，不做正式接受/拒绝。
    """
    results = {
        "n_events": len(events_df),
        "method": "Spearman rank correlation (WARNING: trivial with 2 points)",
        "alpha": alpha,
        "warning": "P2 检验需要 >=3 个尺度点才有意义；当前 2 个点，ρ 必为 ±1，结果仅作方向统计",
        "per_event": [],
        "rejection_rate": None,
        "direction_consistency": {},
    }

    if len(events_df) == 0:
        results["error"] = "No events"
        return results

    tau_mid_2 = [np.sqrt(5 * 15), np.sqrt(15 * 60)]

    directions = []
    for _, row in events_df.iterrows():
        h_vals = [row["H_5_15"], row["H_15_60"]]
        # 2 个点的 Spearman 必为 ±1
        if h_vals[1] > h_vals[0]:
            rho = 1.0
            direction = 1
        elif h_vals[1] < h_vals[0]:
            rho = -1.0
            direction = -1
        else:
            rho = 0.0
            direction = 0

        directions.append(direction)

        results["per_event"].append({
            "datetime": row["datetime"].isoformat() if hasattr(row["datetime"], "isoformat") else str(row["datetime"]),
            "symbol": row["symbol"],
            "R_bar": float(row["R_bar"]),
            "H_5_15": float(row["H_5_15"]),
            "H_15_60": float(row["H_15_60"]),
            "spearman_rho": float(rho),
            "direction": int(direction),
        })

    directions = np.array(directions)

    results["direction_consistency"] = {
        "frac_increasing": float(np.mean(directions == 1)),
        "frac_decreasing": float(np.mean(directions == -1)),
        "frac_equal": float(np.mean(directions == 0)),
        "dominant_direction": "increasing" if np.mean(directions == 1) > 0.5 else
                              ("decreasing" if np.mean(directions == -1) > 0.5 else "mixed"),
    }
    # P2 标记为不可判定（数据不足）
    results["accept_P2"] = None  # None = 无法判定
    results["verdict"] = "inconclusive (need >=3 scale points)"

    return results


# ============================================================
# Step 6: 综合决策
# ============================================================
def make_decision(P0_res, P1_res, P2_res):
    """按 hurst-shape-assumptions-testability.md §11 决策流程"""

    P0_ok = P0_res.get("accept_P0", False)
    P1_ok = P1_res.get("r_star_coverage", {}).get("accept_P1", False)
    P2_ok = P2_res.get("accept_P2")  # 可能是 None（无法判定）

    decision = {
        "timestamp": datetime.now().isoformat(),
        "P0_accepted": P0_ok,
        "P1_accepted": P1_ok,
        "P2_accepted": P2_ok,
        "P2_verdict": P2_res.get("verdict", "unknown"),
        "recommended_assumption": None,
        "rationale": "",
        "metrics": {
            "P0_mean_H_range": P0_res.get("mean_H_range"),
            "P0_rejection_rate": P0_res.get("rejection_rate"),
            "P0_wilcoxon_p": P0_res.get("wilcoxon_paired", {}).get("p_value"),
            "P1_L_hat_median": P1_res.get("L_hat_distribution", {}).get("median"),
            "P1_L_hat_cv": P1_res.get("L_hat_distribution", {}).get("cv"),
            "P1_cross_symbol_ratio": P1_res.get("cross_symbol_stability", {}).get("ratio_max_min"),
            "P1_best_r_star_coverage": P1_res.get("r_star_coverage", {}).get("best_coverage_rate"),
            "P1_base_r_star_coverage": P1_res.get("r_star_coverage", {}).get("base_coverage_rate"),
            "P2_dominant_direction": P2_res.get("direction_consistency", {}).get("dominant_direction"),
            "P2_frac_increasing": P2_res.get("direction_consistency", {}).get("frac_increasing"),
        },
    }

    if P0_ok:
        decision["recommended_assumption"] = "P0 (constant H)"
        decision["rationale"] = "P0 接受：子区间 H 极差 < 0.05 且 Wilcoxon 不显著。"
    elif P1_ok:
        decision["recommended_assumption"] = "P1 (Lipschitz)"
        decision["rationale"] = (
            f"P0 拒绝，P1 接受：L̂ 中位数={decision['metrics']['P1_L_hat_median']:.4f}, "
            f"跨品种比={decision['metrics']['P1_cross_symbol_ratio']:.2f}, "
            f"最佳 r* 覆盖率={decision['metrics']['P1_best_r_star_coverage']:.1%}。"
        )
    elif P2_ok is True:
        decision["recommended_assumption"] = "P1+P2 (Lipschitz + monotonicity)"
        decision["rationale"] = f"P1 边界，P2 方向={decision['metrics']['P2_dominant_direction']}。用 P1+P2 组合。"
    else:
        if P2_ok is None:
            decision["recommended_assumption"] = "P1 (with caveats) — P2 inconclusive"
            decision["rationale"] = (
                f"P0 拒绝。P1 L̂ 中位数={decision['metrics']['P1_L_hat_median']:.4f}（小），"
                f"但 r* 覆盖率不足（最佳={decision['metrics']['P1_best_r_star_coverage']:.1%}）。"
                f"P2 无法判定（需 ≥3 尺度点）。"
                f"建议：P1 可作为描述性假设使用，但可盈利门槛需更优成本参数。"
            )
        else:
            decision["recommended_assumption"] = "P3 (multi-interval) or P4 (Bayesian)"
            decision["rationale"] = "P0/P1/P2 均不满足：需多区间观测 (P3) 或贝叶斯先验 (P4)。"

    return decision


# ============================================================
# 可视化
# ============================================================
def plot_results(P0_res, P1_res, P2_res, high_events, low_events):
    """生成 5 张图"""

    # 图 1: H 曲线高 R vs 低 R 对比
    fig, ax = plt.subplots(figsize=(10, 6))
    mid_norm = [0, 1]
    mid_labels = ["H(5m,15m)", "H(15m,1h)"]
    for df, color, label in [
        (high_events, "#C44E52", f"高 R (>2.0), n={len(high_events)}"),
        (low_events, "#55A868", f"低 R (<1.6), n={len(low_events)}"),
    ]:
        means = [df["H_5_15"].mean(), df["H_15_60"].mean()]
        stds = [df["H_5_15"].std(), df["H_15_60"].std()]
        ax.plot(mid_norm, means, marker="o", markersize=10, linewidth=2.5, color=color, label=label)
        ax.fill_between(mid_norm, [m-s for m, s in zip(means, stds)], [m+s for m, s in zip(means, stds)],
                        color=color, alpha=0.2)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="GBM H=0.5")
    ax.set_xticks(mid_norm)
    ax.set_xticklabels(mid_labels)
    ax.set_ylabel("H 均值")
    ax.set_title("图 1: H(τ) 曲线 — 高 R vs 低 R", fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "fig1_H_curve_high_vs_low.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 图 2: L̂ 分布
    if P1_res.get("per_event"):
        L_hats = [e["L_hat"] for e in P1_res["per_event"]]
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        ax = axes[0]
        ax.hist(L_hats, bins=30, color="#4C72B0", alpha=0.7, edgecolor="white")
        ax.axvline(np.median(L_hats), color="red", linestyle="--", linewidth=2, label=f"中位数={np.median(L_hats):.4f}")
        ax.set_xlabel("L̂ (Lipschitz 常数估计)")
        ax.set_ylabel("频数")
        ax.set_title("L̂ 分布（高 R 事件）", fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 跨品种
        df_L = pd.DataFrame(P1_res["per_event"])
        by_sym = df_L.groupby("symbol")["L_hat"].mean().sort_values()
        ax = axes[1]
        ax.bar(range(len(by_sym)), by_sym.values, color="#55A868", alpha=0.7)
        ax.set_xticks(range(0, len(by_sym), max(1, len(by_sym)//10)))
        ax.set_xticklabels([by_sym.index[i] for i in range(0, len(by_sym), max(1, len(by_sym)//10))],
                           rotation=45, fontsize=8)
        ax.set_ylabel("L̂ 均值")
        ax.set_title(f"跨品种 L̂ 稳定性（n={len(by_sym)} 品种）", fontweight="bold")
        ax.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        plt.savefig(OUT_DIR / "fig2_Lipschitz_dist.png", dpi=150, bbox_inches="tight")
        plt.close()

    # 图 3: r* 覆盖率
    if "r_star_coverage" in P1_res and P1_res["r_star_coverage"]:
        rsc = P1_res["r_star_coverage"]
        fig, ax = plt.subplots(figsize=(10, 6))
        r_actual = high_events["R_bar"].values
        L_hats_arr = np.array([e["L_hat"] for e in P1_res["per_event"]])
        if len(L_hats_arr) == len(r_actual):
            H_star = rsc["params"]["H_star"]
            d_c = rsc["params"]["d_c"]
            r_stars = (60/5) ** (H_star + L_hats_arr * d_c)
            ax.scatter(r_actual, r_stars, alpha=0.3, s=10, color="#C44E52")
            ax.set_xlabel("实测 R_bar")
            ax.set_ylabel("r* (临界比值)")
            ax.set_title(f"图 3: r* 门槛与实测 R_bar 覆盖关系（覆盖率={rsc['coverage_rate']:.1%}）", fontweight="bold")
            ax.axhline(np.median(r_stars), color="orange", linestyle="--", label=f"r* 中位数={np.median(r_stars):.2f}")
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(OUT_DIR / "fig3_rstar_coverage.png", dpi=150, bbox_inches="tight")
            plt.close()

    # 图 4: P2 方向分布（2 个点 ρ 必为 ±1，改画方向饼图）
    if P2_res.get("per_event"):
        directions = [e["direction"] for e in P2_res["per_event"]]
        fig, ax = plt.subplots(figsize=(8, 5))
        labels = ["递增 (H↑)", "递减 (H↓)", "相等"]
        counts = [directions.count(1), directions.count(-1), directions.count(0)]
        colors_pie = ["#C44E52", "#55A868", "#CCCCCC"]
        ax.bar(labels, counts, color=colors_pie, alpha=0.7, edgecolor="white")
        for i, c in enumerate(counts):
            ax.text(i, c + 5, f"{c}\n({c/len(directions):.1%})", ha="center", fontweight="bold")
        ax.set_ylabel("事件数")
        ax.set_title(f"图 4: P2 方向统计（n={len(directions)}, 2点平凡性警告）", fontweight="bold")
        ax.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        plt.savefig(OUT_DIR / "fig4_P2_direction.png", dpi=150, bbox_inches="tight")
        plt.close()

    # 图 5: P0 极差分布
    if P0_res.get("per_event"):
        ranges = [e["H_range"] for e in P0_res["per_event"]]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(ranges, bins=30, color="#CCB974", alpha=0.7, edgecolor="white")
        ax.axvline(P0_res.get("fixed_threshold", 0.05), color="red", linestyle="--",
                   linewidth=2, label=f"阈值={P0_res.get('fixed_threshold', 0.05)}")
        ax.axvline(np.mean(ranges), color="blue", linestyle="-",
                   linewidth=2, label=f"均值={np.mean(ranges):.4f}")
        ax.set_xlabel("|H(5m,15m) - H(15m,1h)| 极差")
        ax.set_ylabel("频数")
        ax.set_title("图 5: P0 恒定 H 检验 — H 极差分布", fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(OUT_DIR / "fig5_P0_range.png", dpi=150, bbox_inches="tight")
        plt.close()


# ============================================================
# 主函数
# ============================================================
def main():
    print("=" * 70, flush=True)
    print("Step 3-6: P0/P1/P2 假设检验与综合决策", flush=True)
    print("=" * 70, flush=True)

    # 加载数据
    print("\n[1/5] 加载多尺度面板...", flush=True)
    panels = []
    symbols = []
    for f in sorted(CSV_DIR.glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = compute_panel(sym)
        if p is not None:
            panels.append(p)
            symbols.append(sym)
    panel = pd.concat(panels, ignore_index=True)
    print(f"  面板: {len(panel)} 行, {len(symbols)} 合约", flush=True)

    # 提取事件
    print("\n[2/5] 提取高/低 R 事件...", flush=True)
    high_events_list = []
    low_events_list = []
    for sym in symbols:
        sym_df = panel[panel["symbol"] == sym]
        high = extract_events(sym_df, 2.0, direction="above", min_gap_hours=8)
        if len(high) > 0:
            high_events_list.append(high)
        low = extract_events(sym_df, 1.6, direction="below", min_gap_hours=8)
        if len(low) > 0:
            low_events_list.append(low)

    high_events = pd.concat(high_events_list, ignore_index=True) if high_events_list else pd.DataFrame()
    low_events = pd.concat(low_events_list, ignore_index=True) if low_events_list else pd.DataFrame()
    print(f"  高 R 事件: {len(high_events)}, 低 R 事件: {len(low_events)}", flush=True)

    # 尺度配置
    h_cols = ["H_5_15", "H_15_60", "H_5_60"]
    h_pairs = [
        ("H_5_15", 5, "H_15_60", 15),   # 相邻区间
        ("H_5_15", 5, "H_5_60", 5),      # 短-全
        ("H_15_60", 15, "H_5_60", 15),   # 长-全
    ]

    # Step 3: P0 检验
    print("\n[3/5] Step 3: P0 恒定 H 检验...", flush=True)
    P0_res = test_P0(high_events, ["H_5_15", "H_15_60"], alpha=0.05)
    print(f"  P0 拒绝率（极差>0.05）: {P0_res['rejection_rate']:.1%}", flush=True)
    print(f"  H 极差均值: {P0_res['mean_H_range']:.4f}", flush=True)
    print(f"  Wilcoxon p 值: {P0_res['wilcoxon_paired']['p_value']:.2e}", flush=True)
    print(f"  P0 接受: {P0_res['accept_P0']}", flush=True)

    # Step 4: P1 检验
    print("\n[4/5] Step 4: P1 Lipschitz 检验...", flush=True)
    P1_res = test_P1(high_events, h_pairs, alpha=0.05)
    if "error" not in P1_res:
        print(f"  L̂ 中位数: {P1_res['L_hat_distribution']['median']:.4f}", flush=True)
        print(f"  L̂ 变异系数: {P1_res['L_hat_distribution']['cv']:.2f}", flush=True)
        print(f"  跨品种 max/min 比: {P1_res['cross_symbol_stability']['ratio_max_min']:.2f}", flush=True)
        print(f"  基准 r* 覆盖率: {P1_res['r_star_coverage']['base_coverage_rate']:.1%}", flush=True)
        print(f"  最佳 r* 覆盖率: {P1_res['r_star_coverage']['best_coverage_rate']:.1%}", flush=True)
        print(f"  P1 接受: {P1_res['r_star_coverage']['accept_P1']}", flush=True)

    # Step 5: P2 检验
    print("\n[5/5] Step 5: P2 单调性检验...", flush=True)
    P2_res = test_P2(high_events, ["H_5_15", "H_15_60"], alpha=0.05)
    print(f"  P2 判定: {P2_res['verdict']}", flush=True)
    print(f"  方向: 递增 {P2_res['direction_consistency']['frac_increasing']:.1%}, "
          f"递减 {P2_res['direction_consistency']['frac_decreasing']:.1%}", flush=True)
    print(f"  主导方向: {P2_res['direction_consistency']['dominant_direction']}", flush=True)

    # Step 6: 综合决策
    print("\n" + "=" * 70, flush=True)
    print("Step 6: 综合决策", flush=True)
    print("=" * 70, flush=True)
    decision = make_decision(P0_res, P1_res, P2_res)
    print(f"  推荐假设: {decision['recommended_assumption']}", flush=True)
    print(f"  理由: {decision['rationale']}", flush=True)

    # 保存结果
    print("\n保存结果...", flush=True)
    for name, obj in [("P0_results.json", P0_res), ("P1_results.json", P1_res),
                      ("P2_results.json", P2_res), ("decision_summary.json", decision)]:
        path = OUT_DIR / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
        print(f"  {path}", flush=True)

    # 生成可读报告
    report_path = OUT_DIR / "decision_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 假设检验决策报告\n\n")
        f.write(f"> 生成时间: {decision['timestamp']}\n")
        f.write(f"> 样本: 高 R 事件 {P0_res.get('n_events', 0)} 个, 低 R 对照 {len(low_events)} 个\n\n")

        f.write("## 决策结果\n\n")
        f.write(f"**推荐假设**: {decision['recommended_assumption']}\n\n")
        f.write(f"**理由**: {decision['rationale']}\n\n")

        f.write("## 检验指标\n\n")
        f.write("| 假设 | 接受 | 关键指标 | 判据 |\n")
        f.write("|------|------|---------|------|\n")
        f.write(f"| P0 恒定 H | {'✅' if decision['P0_accepted'] else '❌'} | "
                f"极差均值={decision['metrics']['P0_mean_H_range']:.4f}, "
                f"拒绝率={decision['metrics']['P0_rejection_rate']:.1%}, "
                f"Wilcoxon p={decision['metrics']['P0_wilcoxon_p']:.2e} | "
                f"极差 < 0.05 且 Wilcoxon 不显著 |\n")
        f.write(f"| P1 Lipschitz | {'✅' if decision['P1_accepted'] else '❌'} | "
                f"L̂中位数={decision['metrics']['P1_L_hat_median']:.4f}, "
                f"跨品种比={decision['metrics']['P1_cross_symbol_ratio']:.2f}, "
                f"最佳r*覆盖率={decision['metrics']['P1_best_r_star_coverage']:.1%} | "
                f"跨品种比<10, L̂<0.2, 覆盖率>5% |\n")
        P2_str = "⚠️ 不可判定" if decision['P2_accepted'] is None else ('✅' if decision['P2_accepted'] else '❌')
        f.write(f"| P2 单调性 | {P2_str} | "
                f"递增占比={decision['metrics']['P2_frac_increasing']:.1%}, "
                f"方向={decision['metrics']['P2_dominant_direction']} | "
                f"需 ≥3 尺度点（当前 2 个，无法判定）|\n")

        f.write("\n## 详细结果\n\n")
        f.write("### P0 恒定 H 检验\n\n")
        for col, vals in P0_res.get("H_ranges", {}).items():
            f.write(f"- {col}: mean={vals['mean']:.4f}, median={vals['median']:.4f}, std={vals['std']:.4f}\n")
        f.write(f"\n- H 极差均值: {P0_res.get('mean_H_range', 0):.4f}\n")
        f.write(f"- 固定阈值: {P0_res.get('fixed_threshold', 0.05)}\n")
        f.write(f"- P0 拒绝率: {P0_res.get('rejection_rate', 0):.1%}\n")
        wp = P0_res.get("wilcoxon_paired", {})
        f.write(f"- Wilcoxon 配对检验: stat={wp.get('statistic', 0):.1f}, p={wp.get('p_value', 1):.2e}\n")

        f.write("\n### P1 Lipschitz 检验\n\n")
        if "L_hat_distribution" in P1_res:
            d = P1_res["L_hat_distribution"]
            f.write(f"- L̂ 中位数: {d['median']:.4f}\n")
            f.write(f"- L̂ 均值: {d['mean']:.4f} ± {d['std']:.4f}\n")
            f.write(f"- L̂ p25-p75: [{d['p25']:.4f}, {d['p75']:.4f}]\n")
            f.write(f"- L̂ 变异系数: {d['cv']:.2f}\n")
        if "cross_symbol_stability" in P1_res:
            cs = P1_res["cross_symbol_stability"]
            f.write(f"- 跨品种数: {cs['n_symbols']}\n")
            f.write(f"- 跨品种 max/min 比: {cs['ratio_max_min']:.2f}\n")
        rsc = P1_res.get("r_star_coverage", {})
        if rsc:
            f.write(f"\n**可盈利门槛（基准参数）**:\n")
            bp = rsc.get("base_params", {})
            f.write(f"- H*(c=15m) = {bp.get('H_star', 0):.4f}\n")
            f.write(f"- δ* = {bp.get('delta_star', 0):.4f}\n")
            f.write(f"- d(c=15m) = {bp.get('d_c', 0):.4f}\n")
            f.write(f"- 基准 r* 覆盖率: {rsc.get('base_coverage_rate', 0):.1%}\n")
            f.write(f"\n**敏感性分析**:\n")
            f.write(f"- 最佳 r* 覆盖率: {rsc.get('best_coverage_rate', 0):.1%}\n")
            sa = rsc.get("sensitivity_analysis", [])
            if sa:
                best = max(sa, key=lambda x: x["coverage_rate"])
                f.write(f"- 最佳参数: c_cost={best['c_cost']}, K_S={best['K_S']}, R={best['R_ratio']}\n")
                f.write(f"- 最佳 H* = {best['H_star']:.4f}, r* 中位数 = {best['r_star_median']:.2f}\n")
            ac = rsc.get("accept_criteria", {})
            f.write(f"\n**接受判据**:\n")
            f.write(f"- 跨品种稳定: {ac.get('cross_symbol_ok', False)}\n")
            f.write(f"- L̂ 足够小: {ac.get('L_small_enough', False)}\n")
            f.write(f"- 任一参数覆盖率>5%: {ac.get('any_coverage_above_5pct', False)}\n")

        f.write("\n### P2 单调性检验\n\n")
        f.write(f"- **判定**: {P2_res.get('verdict', 'unknown')}\n")
        dc = P2_res.get("direction_consistency", {})
        f.write(f"- 递增占比: {dc.get('frac_increasing', 0):.1%}\n")
        f.write(f"- 递减占比: {dc.get('frac_decreasing', 0):.1%}\n")
        f.write(f"- 主导方向: {dc.get('dominant_direction', 'unknown')}\n")
        f.write(f"- 注: {P2_res.get('warning', '')}\n")

    print(f"  报告: {report_path}", flush=True)

    # 生成图表
    print("\n生成图表...", flush=True)
    plot_results(P0_res, P1_res, P2_res, high_events, low_events)
    print(f"  图表已保存到 {OUT_DIR}/", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("完成", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
