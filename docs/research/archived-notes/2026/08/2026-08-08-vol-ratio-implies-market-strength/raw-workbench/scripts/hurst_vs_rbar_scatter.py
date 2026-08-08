"""
Hurst 指数与 R_bar 散点分布图
============================

目标：观察 R_bar（跨周期波动率比）与多尺度 Hurst 指数 H(τ) 的关系，
验证是否存在明显的形态特征（如高 R 区域 H 系统性偏高）。

尺度范围：5m, 15m, 1h（数据可用周期）
H(τ) 口径：区间平均法（与 R_bar 同源）
    H_bar(5m, 15m) = ln(σ_15m / σ_5m) / ln(15/5)
    H_bar(15m, 1h) = ln(σ_1h / σ_15m) / ln(60/15)
    R_bar = σ_1h / σ_15m  =>  H_bar(15m,1h) = ln(R_bar) / ln(4)

筛选组：
- 高 R: R > 2.0
- 中 R: 1.6 <= R <= 2.0
- 低 R: R < 1.6
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[3]
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "hurst_vs_rbar"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def rolling_std(series, window=50):
    """滚动标准差（用于 σ_τ 估计）"""
    return series.rolling(window, min_periods=window // 2).std()


def compute_panel(sym):
    """计算单合约的多尺度 σ_τ 和 R_bar，对齐到 1h 时间戳。"""
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

    # 对数收益
    df_1h["log_ret"] = np.log(df_1h["close"]).diff()
    df_15["log_ret"] = np.log(df_15["close"]).diff()
    df_5["log_ret"] = np.log(df_5["close"]).diff()

    # σ_τ 估计（50 bar 滚动窗口）
    df_1h["sigma_1h"] = rolling_std(df_1h["log_ret"], 50)
    df_15["sigma_15m"] = rolling_std(df_15["log_ret"], 200)  # 200 × 15m ≈ 50h
    df_5["sigma_5m"] = rolling_std(df_5["log_ret"], 600)  # 600 × 5m ≈ 50h

    # 对齐到 1h 时间戳
    base = df_1h[["datetime", "close", "sigma_1h"]].dropna().sort_values("datetime")
    sub_15 = df_15[["datetime", "sigma_15m"]].dropna().sort_values("datetime")
    sub_5 = df_5[["datetime", "sigma_5m"]].dropna().sort_values("datetime")
    base = pd.merge_asof(base, sub_15, on="datetime", direction="backward")
    base = pd.merge_asof(base, sub_5, on="datetime", direction="backward")
    base = base.dropna()

    # R_bar = σ_1h / σ_15m
    base["R_bar"] = base["sigma_1h"] / base["sigma_15m"]

    # 多尺度 H (区间平均法)
    # H(5m, 15m) = ln(σ_15m/σ_5m) / ln(15/5) = ln(σ_15m/σ_5m) / ln(3)
    base["H_5_15"] = np.log(base["sigma_15m"] / base["sigma_5m"]) / np.log(3.0)
    # H(15m, 1h) = ln(σ_1h/σ_15m) / ln(60/15) = ln(R_bar) / ln(4)
    base["H_15_60"] = np.log(base["R_bar"]) / np.log(4.0)
    # H(5m, 1h) = ln(σ_1h/σ_5m) / ln(60/5) = ln(σ_1h/σ_5m) / ln(12)
    base["H_5_60"] = np.log(base["sigma_1h"] / base["sigma_5m"]) / np.log(12.0)

    # GBM 基线对应的 R_bar
    base["R_gbm"] = 2.0  # sqrt(60/15) = 2

    base["symbol"] = sym
    base["year"] = base["datetime"].dt.year
    base["month"] = base["datetime"].dt.to_period("M").astype(str)

    return base[["datetime", "symbol", "close", "year", "month",
                 "sigma_5m", "sigma_15m", "sigma_1h",
                 "R_bar", "H_5_15", "H_15_60", "H_5_60", "R_gbm"]]


def extract_events(sym_df, threshold, direction="above", min_gap_hours=8):
    """状态触发抽样：首次穿越阈值，带最小间隔约束。"""
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


def main():
    print("=" * 70, flush=True)
    print("Hurst 指数与 R_bar 散点分布分析", flush=True)
    print("=" * 70, flush=True)

    # 加载数据
    print("\n加载多尺度面板...", flush=True)
    panels = []
    symbols = []
    for f in sorted(CSV_DIR.glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = compute_panel(sym)
        if p is not None:
            panels.append(p)
            symbols.append(sym)
    panel = pd.concat(panels, ignore_index=True)
    print(f"面板: {len(panel)} 行, {len(symbols)} 合约", flush=True)
    print(f"时间: {panel['datetime'].min()} ~ {panel['datetime'].max()}", flush=True)

    # 描述性统计
    print("\n--- 多尺度 H 描述统计 ---", flush=True)
    for col in ["H_5_15", "H_15_60", "H_5_60"]:
        s = panel[col]
        print(f"{col}: median={s.median():.4f}, mean={s.mean():.4f}, "
              f"p25={s.quantile(0.25):.4f}, p75={s.quantile(0.75):.4f}", flush=True)

    # 分组
    print("\n--- 分组样本量 ---", flush=True)
    panel["group"] = "中 R (1.6-2.0)"
    panel.loc[panel["R_bar"] > 2.0, "group"] = "高 R (>2.0)"
    panel.loc[panel["R_bar"] < 1.6, "group"] = "低 R (<1.6)"
    print(panel["group"].value_counts().to_string(), flush=True)

    # 分组统计
    print("\n--- 分组 H 中位数 ---", flush=True)
    group_stats = panel.groupby("group")[["R_bar", "H_5_15", "H_15_60", "H_5_60"]].median()
    print(group_stats.round(4).to_string(), flush=True)

    # ============================================================
    # 图 1：主散点图矩阵（2×2）
    # ============================================================
    print("\n生成图 1: 散点图矩阵...", flush=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    colors = {"高 R (>2.0)": "#C44E52", "中 R (1.6-2.0)": "#4C72B0", "低 R (<1.6)": "#55A868"}
    groups_order = ["低 R (<1.6)", "中 R (1.6-2.0)", "高 R (>2.0)"]

    # 图 1a: R_bar vs H(15m, 1h) — 核心图
    ax = axes[0, 0]
    for g in groups_order:
        sub = panel[panel["group"] == g]
        ax.scatter(sub["R_bar"], sub["H_15_60"], s=3, alpha=0.3,
                   color=colors[g], label=f"{g} (n={len(sub)})")
    ax.axvline(2.0, color="red", linestyle="--", linewidth=1, label="GBM 基线 R=2.0")
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5 (GBM)")
    # 理论关系线 H = ln(R) / ln(4)
    r_theory = np.linspace(1.0, 3.5, 100)
    h_theory = np.log(r_theory) / np.log(4)
    ax.plot(r_theory, h_theory, "k-", linewidth=1.5, alpha=0.5, label="理论: H = ln(R)/ln(4)")
    ax.set_xlabel("R_bar (σ_1h / σ_15m)")
    ax.set_ylabel("H(15m, 1h) = ln(R_bar)/ln(4)")
    ax.set_title("R_bar vs H(15m, 1h)")
    ax.legend(loc="upper left", fontsize=8, markerscale=3)
    ax.set_xlim(1.0, 3.5)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    # 图 1b: R_bar vs H(5m, 15m) — 短周期 H
    ax = axes[0, 1]
    for g in groups_order:
        sub = panel[panel["group"] == g]
        ax.scatter(sub["R_bar"], sub["H_5_15"], s=3, alpha=0.3,
                   color=colors[g], label=f"{g} (n={len(sub)})")
    ax.axvline(2.0, color="red", linestyle="--", linewidth=1)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5 (GBM)")
    ax.set_xlabel("R_bar (σ_1h / σ_15m)")
    ax.set_ylabel("H(5m, 15m)")
    ax.set_title("R_bar vs H(5m, 15m)")
    ax.legend(loc="upper right", fontsize=8, markerscale=3)
    ax.set_xlim(1.0, 3.5)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    # 图 1c: R_bar vs H(5m, 1h) — 全区间 H
    ax = axes[1, 0]
    for g in groups_order:
        sub = panel[panel["group"] == g]
        ax.scatter(sub["R_bar"], sub["H_5_60"], s=3, alpha=0.3,
                   color=colors[g], label=f"{g} (n={len(sub)})")
    ax.axvline(2.0, color="red", linestyle="--", linewidth=1)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5 (GBM)")
    # 理论关系线 H = ln(R_total)/ln(12), 但 R_bar 只覆盖 15m-1h，需要换算
    # σ_1h/σ_5m = (σ_1h/σ_15m) × (σ_15m/σ_5m) = R_bar × (σ_15m/σ_5m)
    # 这里画的是 R_bar vs H(5m,1h)，非线性关系，不画理论线
    ax.set_xlabel("R_bar (σ_1h / σ_15m)")
    ax.set_ylabel("H(5m, 1h) = ln(σ_1h/σ_5m)/ln(12)")
    ax.set_title("R_bar vs H(5m, 1h) — 全区间 Hurst")
    ax.legend(loc="upper right", fontsize=8, markerscale=3)
    ax.set_xlim(1.0, 3.5)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    # 图 1d: H(5m,15m) vs H(15m,1h) — H 曲线形状
    ax = axes[1, 1]
    for g in groups_order:
        sub = panel[panel["group"] == g]
        ax.scatter(sub["H_5_15"], sub["H_15_60"], s=3, alpha=0.3,
                   color=colors[g], label=f"{g} (n={len(sub)})")
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1)
    ax.axvline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5 (GBM)")
    # 对角线（恒定 H 假设 P0: H_5_15 = H_15_60）
    ax.plot([0, 1], [0, 1], "k-", linewidth=1, alpha=0.5, label="恒定 H (P0)")
    ax.set_xlabel("H(5m, 15m)")
    ax.set_ylabel("H(15m, 1h)")
    ax.set_title("H 曲线形状: 短周期 vs 长周期")
    ax.legend(loc="upper left", fontsize=8, markerscale=3)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    plt.suptitle("Hurst 指数与 R_bar 散点分布（全样本）", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig1_path = OUT_DIR / "fig1_scatter_matrix.png"
    plt.savefig(fig1_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"图 1 已保存: {fig1_path}", flush=True)

    # ============================================================
    # 图 2：高 R 事件子样本（非重叠）的散点图
    # ============================================================
    print("\n生成图 2: 高 R 事件子样本散点图...", flush=True)

    # 提取高 R 事件（R > 2.0, gap=8h）
    high_events = []
    for sym in symbols:
        sym_df = panel[panel["symbol"] == sym]
        events = extract_events(sym_df, 2.0, direction="above", min_gap_hours=8)
        if len(events) > 0:
            high_events.append(events)
    high_df = pd.concat(high_events, ignore_index=True) if high_events else pd.DataFrame()
    print(f"高 R 事件数: {len(high_df)}", flush=True)

    # 提取低 R 事件（对照组）
    low_events = []
    for sym in symbols:
        sym_df = panel[panel["symbol"] == sym]
        events = extract_events(sym_df, 1.6, direction="below", min_gap_hours=8)
        if len(events) > 0:
            low_events.append(events)
    low_df = pd.concat(low_events, ignore_index=True) if low_events else pd.DataFrame()
    print(f"低 R 事件数: {len(low_df)}", flush=True)

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # 图 2a: 高 R 事件 R_bar vs H(15m, 1h)
    ax = axes[0, 0]
    if len(high_df) > 0:
        ax.scatter(high_df["R_bar"], high_df["H_15_60"], s=15, alpha=0.5,
                   color="#C44E52", label=f"高 R 事件 (n={len(high_df)})")
    if len(low_df) > 0:
        ax.scatter(low_df["R_bar"], low_df["H_15_60"], s=15, alpha=0.5,
                   color="#55A868", label=f"低 R 事件 (n={len(low_df)})")
    ax.axvline(2.0, color="red", linestyle="--", linewidth=1, label="GBM 基线 R=2.0")
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5")
    r_theory = np.linspace(1.0, 3.5, 100)
    h_theory = np.log(r_theory) / np.log(4)
    ax.plot(r_theory, h_theory, "k-", linewidth=1.5, alpha=0.5, label="理论: H = ln(R)/ln(4)")
    ax.set_xlabel("R_bar")
    ax.set_ylabel("H(15m, 1h)")
    ax.set_title("事件样本: R_bar vs H(15m, 1h)")
    ax.legend(fontsize=8, markerscale=2)
    ax.set_xlim(1.0, 3.5)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    # 图 2b: H(5m,15m) vs H(15m,1h) — 事件样本形状
    ax = axes[0, 1]
    if len(high_df) > 0:
        ax.scatter(high_df["H_5_15"], high_df["H_15_60"], s=15, alpha=0.5,
                   color="#C44E52", label=f"高 R 事件 (n={len(high_df)})")
    if len(low_df) > 0:
        ax.scatter(low_df["H_5_15"], low_df["H_15_60"], s=15, alpha=0.5,
                   color="#55A868", label=f"低 R 事件 (n={len(low_df)})")
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1)
    ax.axvline(0.5, color="gray", linestyle="--", linewidth=1)
    ax.plot([0, 1], [0, 1], "k-", linewidth=1, alpha=0.5, label="恒定 H (P0)")
    ax.set_xlabel("H(5m, 15m)")
    ax.set_ylabel("H(15m, 1h)")
    ax.set_title("事件样本: H 曲线形状")
    ax.legend(fontsize=8, markerscale=2)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    # 图 2c: 高 R 事件的 H 分布对比
    ax = axes[1, 0]
    bins = np.linspace(0, 1.0, 50)
    if len(high_df) > 0:
        ax.hist(high_df["H_15_60"], bins=bins, alpha=0.5, color="#C44E52",
                label=f"高 R: H(15m,1h) 中位={high_df['H_15_60'].median():.3f}", density=True)
    if len(low_df) > 0:
        ax.hist(low_df["H_15_60"], bins=bins, alpha=0.5, color="#55A868",
                label=f"低 R: H(15m,1h) 中位={low_df['H_15_60'].median():.3f}", density=True)
    ax.axvline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5 (GBM)")
    ax.set_xlabel("H(15m, 1h)")
    ax.set_ylabel("密度")
    ax.set_title("高 R vs 低 R 事件的 H(15m,1h) 分布")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 图 2d: 高 R 事件的 H(5m,15m) 分布
    ax = axes[1, 1]
    if len(high_df) > 0:
        ax.hist(high_df["H_5_15"], bins=bins, alpha=0.5, color="#C44E52",
                label=f"高 R: H(5m,15m) 中位={high_df['H_5_15'].median():.3f}", density=True)
    if len(low_df) > 0:
        ax.hist(low_df["H_5_15"], bins=bins, alpha=0.5, color="#55A868",
                label=f"低 R: H(5m,15m) 中位={low_df['H_5_15'].median():.3f}", density=True)
    ax.axvline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5 (GBM)")
    ax.set_xlabel("H(5m, 15m)")
    ax.set_ylabel("密度")
    ax.set_title("高 R vs 低 R 事件的 H(5m,15m) 分布")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.suptitle("Hurst 指数与 R_bar 散点分布（事件样本，gap=8h）", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig2_path = OUT_DIR / "fig2_event_scatter.png"
    plt.savefig(fig2_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"图 2 已保存: {fig2_path}", flush=True)

    # ============================================================
    # 图 3：H 曲线形状特征（箱线图 + 均值连线）
    # ============================================================
    print("生成图 3: H 曲线形状特征...", flush=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 图 3a: 三组的 H 曲线（H(5m,15m) 和 H(15m,1h) 均值连线）
    ax = axes[0]
    groups_plot = ["低 R (<1.6)", "中 R (1.6-2.0)", "高 R (>2.0)"]
    colors_plot = ["#55A868", "#4C72B0", "#C44E52"]
    x_scales = [1, 2]  # 5m-15m, 15m-1h
    x_labels = ["H(5m,15m)", "H(15m,1h)"]

    for i, g in enumerate(groups_plot):
        sub = panel[panel["group"] == g]
        means = [sub["H_5_15"].mean(), sub["H_15_60"].mean()]
        stds = [sub["H_5_15"].std(), sub["H_15_60"].std()]
        ax.errorbar(x_scales, means, yerr=stds, marker="o", markersize=8,
                    color=colors_plot[i], label=f"{g} (n={len(sub)})",
                    capsize=5, linewidth=2)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5 (GBM)")
    ax.set_xticks(x_scales)
    ax.set_xticklabels(x_labels)
    ax.set_ylabel("H 均值")
    ax.set_title("三组的 H 曲线形状（均值 ± std）")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 图 3b: 高 R 事件按年份的 H 分布
    ax = axes[1]
    if len(high_df) > 0:
        high_df["year"] = high_df["datetime"].dt.year
        year_data = [high_df[high_df["year"] == y]["H_15_60"].values for y in sorted(high_df["year"].unique())]
        year_labels = [str(y) for y in sorted(high_df["year"].unique())]
        bp = ax.boxplot(year_data, labels=year_labels, patch_artist=True)
        for patch in bp["boxes"]:
            patch.set_facecolor("#C44E52")
            patch.set_alpha(0.5)
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="H=0.5")
    ax.set_xlabel("年份")
    ax.set_ylabel("H(15m, 1h)")
    ax.set_title("高 R 事件按年份的 H 分布")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.suptitle("H 曲线形状特征", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig3_path = OUT_DIR / "fig3_h_shape.png"
    plt.savefig(fig3_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"图 3 已保存: {fig3_path}", flush=True)

    # ============================================================
    # 数值汇总
    # ============================================================
    print("\n" + "=" * 70, flush=True)
    print("数值汇总", flush=True)
    print("=" * 70, flush=True)

    print("\n--- 三组 H 中位数对比 ---", flush=True)
    for g in groups_plot:
        sub = panel[panel["group"] == g]
        print(f"{g}:", flush=True)
        print(f"  H(5m,15m):  median={sub['H_5_15'].median():.4f}, mean={sub['H_5_15'].mean():.4f}", flush=True)
        print(f"  H(15m,1h):  median={sub['H_15_60'].median():.4f}, mean={sub['H_15_60'].mean():.4f}", flush=True)
        print(f"  H(5m,1h):   median={sub['H_5_60'].median():.4f}, mean={sub['H_5_60'].mean():.4f}", flush=True)

    # P0 检验：H(5m,15m) vs H(15m,1h) 是否相等
    print("\n--- P0 恒定 H 检验（H_5_15 vs H_15_60）---", flush=True)
    for g in groups_plot:
        sub = panel[panel["group"] == g]
        diff = (sub["H_5_15"] - sub["H_15_60"]).dropna()
        print(f"{g}: 均值差={diff.mean():.4f}, std={diff.std():.4f}, "
              f"|差|>0.05 占比={ (diff.abs() > 0.05).mean():.2%}", flush=True)

    # 高 R 事件中 H > 0.5 的比例
    if len(high_df) > 0:
        print("\n--- 高 R 事件中 H > 0.5 的比例 ---", flush=True)
        print(f"H(15m,1h) > 0.5: {(high_df['H_15_60'] > 0.5).mean():.2%}", flush=True)
        print(f"H(5m,15m) > 0.5: {(high_df['H_5_15'] > 0.5).mean():.2%}", flush=True)
        print(f"H(5m,1h) > 0.5:  {(high_df['H_5_60'] > 0.5).mean():.2%}", flush=True)

    # 低 R 对照
    if len(low_df) > 0:
        print("\n--- 低 R 事件中 H > 0.5 的比例（对照）---", flush=True)
        print(f"H(15m,1h) > 0.5: {(low_df['H_15_60'] > 0.5).mean():.2%}", flush=True)
        print(f"H(5m,15m) > 0.5: {(low_df['H_5_15'] > 0.5).mean():.2%}", flush=True)
        print(f"H(5m,1h) > 0.5:  {(low_df['H_5_60'] > 0.5).mean():.2%}", flush=True)

    # 相关性
    print("\n--- R_bar 与 H 的 Pearson 相关 ---", flush=True)
    for col in ["H_5_15", "H_15_60", "H_5_60"]:
        corr = panel[["R_bar", col]].corr().iloc[0, 1]
        print(f"corr(R_bar, {col}) = {corr:.4f}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("分析完成", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
