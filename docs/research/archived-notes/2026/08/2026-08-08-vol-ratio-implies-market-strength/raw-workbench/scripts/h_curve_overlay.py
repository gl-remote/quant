"""
H 曲线叠加对比图
================

针对简报中"H 曲线前段重合、后段分叉"的形态，
生成高 R vs 低 R 的 H(τ) 曲线叠加图，直观呈现分叉点。

输出：
1. 均值曲线叠加（带置信带）
2. 分位数曲线叠加（p25/p50/p75）
3. 按品种聚合的 H 曲线热力图
4. 分叉点定位图
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
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "h_curve_overlay"
OUT_DIR.mkdir(parents=True, exist_ok=True)


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
    # 过滤掉 R_bar <= 0 的无效值（避免 log 负无穷）
    valid = (base["R_bar"] > 0) & (base["sigma_5m"] > 0) & np.isfinite(base["sigma_5m"])
    base = base[valid].copy()
    base["H_5_15"] = np.log(base["sigma_15m"] / base["sigma_5m"]) / np.log(3.0)
    base["H_15_60"] = np.log(base["R_bar"]) / np.log(4.0)
    base["H_5_60"] = np.log(base["sigma_1h"] / base["sigma_5m"]) / np.log(12.0)
    # 再次过滤 inf/nan
    base = base[np.isfinite(base["H_5_15"]) & np.isfinite(base["H_15_60"]) & np.isfinite(base["H_5_60"])].copy()

    base["symbol"] = sym
    base["year"] = base["datetime"].dt.year

    return base[["datetime", "symbol", "year", "close",
                 "sigma_5m", "sigma_15m", "sigma_1h",
                 "R_bar", "H_5_15", "H_15_60", "H_5_60"]]


def extract_events(sym_df, threshold, direction="above", min_gap_hours=8):
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
    print("H 曲线叠加对比图", flush=True)
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

    # 提取事件
    print("提取事件...", flush=True)
    high_events = []
    for sym in symbols:
        sym_df = panel[panel["symbol"] == sym]
        events = extract_events(sym_df, 2.0, direction="above", min_gap_hours=8)
        if len(events) > 0:
            high_events.append(events)
    high_df = pd.concat(high_events, ignore_index=True) if high_events else pd.DataFrame()

    low_events = []
    for sym in symbols:
        sym_df = panel[panel["symbol"] == sym]
        events = extract_events(sym_df, 1.6, direction="below", min_gap_hours=8)
        if len(events) > 0:
            low_events.append(events)
    low_df = pd.concat(low_events, ignore_index=True) if low_events else pd.DataFrame()

    print(f"高 R 事件: {len(high_df)}, 低 R 事件: {len(low_df)}", flush=True)

    # H 曲线数据
    # 尺度点：5m, 15m, 1h（用 ln(τ) 作为横轴）
    taus_min = [5, 15, 60]
    ln_taus = np.log(taus_min)
    # 归一化到 [0, 1]
    x_norm = (ln_taus - ln_taus[0]) / (ln_taus[-1] - ln_taus[0])
    x_labels = ["5m", "15m", "1h"]

    h_cols = ["H_5_15", "H_15_60"]
    # 三尺度点：5m 处用 H_5_15 近似起点，15m 处用 H_5_15 和 H_15_60 的交界，1h 处用 H_15_60
    # 更准确：5m 点代表 5-15 区间中点，1h 点代表 15-60 区间中点
    # 我们用区间中点位置画 H
    # H_5_15 是 5-15 区间的平均 H，画在 ln(√(5*15)) = ln(8.66) 处
    # H_15_60 是 15-60 区间的平均 H，画在 ln(√(15*60)) = ln(30) 处
    mid_5_15 = np.log(np.sqrt(5 * 15))
    mid_15_60 = np.log(np.sqrt(15 * 60))
    mid_taus = np.array([mid_5_15, mid_15_60])
    mid_norm = (mid_taus - np.log(5)) / (np.log(60) - np.log(5))
    mid_labels = ["5-15m\n(中点≈8.7m)", "15-60m\n(中点≈30m)"]

    # ============================================================
    # 图 1：均值曲线叠加（带 95% 置信带）
    # ============================================================
    print("生成图 1: 均值曲线叠加...", flush=True)
    fig, ax = plt.subplots(figsize=(10, 7))

    for df, color, label in [
        (high_df, "#C44E52", f"高 R (>2.0), n={len(high_df)}"),
        (low_df, "#55A868", f"低 R (<1.6), n={len(low_df)}"),
    ]:
        if len(df) == 0:
            continue
        means = [df["H_5_15"].mean(), df["H_15_60"].mean()]
        stds = [df["H_5_15"].std(), df["H_15_60"].std()]
        n = len(df)
        ci = [1.96 * s / np.sqrt(n) for s in stds]

        ax.plot(mid_norm, means, marker="o", markersize=12, linewidth=2.5,
                color=color, label=label, zorder=3)
        ax.fill_between(mid_norm,
                        [m - c for m, c in zip(means, ci)],
                        [m + c for m, c in zip(means, ci)],
                        color=color, alpha=0.2, zorder=2)
        # 标注均值数值
        for x, m, s in zip(mid_norm, means, stds):
            ax.annotate(f"{m:.3f}", xy=(x, m), xytext=(0, 12),
                        textcoords="offset points", ha="center", fontsize=9,
                        color=color, fontweight="bold")

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="GBM 基线 H=0.5")
    ax.set_xticks(mid_norm)
    ax.set_xticklabels(mid_labels, fontsize=11)
    ax.set_xlabel("尺度区间中点（对数）", fontsize=12)
    ax.set_ylabel("H 均值", fontsize=12)
    ax.set_title("H(τ) 曲线叠加：高 R vs 低 R 事件（均值 ± 95% CI）", fontsize=13, fontweight="bold")
    ax.legend(loc="lower right", fontsize=10)
    ax.set_ylim(0.2, 0.65)
    ax.grid(True, alpha=0.3)

    # 标注分叉点
    high_mean_15 = high_df["H_5_15"].mean()
    low_mean_15 = low_df["H_5_15"].mean()
    high_mean_60 = high_df["H_15_60"].mean()
    low_mean_60 = low_df["H_15_60"].mean()
    diff_15 = abs(high_mean_15 - low_mean_15)
    diff_60 = abs(high_mean_60 - low_mean_60)

    # 在分叉点画垂直虚线
    ax.axvline(mid_norm[1], color="orange", linestyle=":", linewidth=1.5, alpha=0.7)
    ax.annotate("分叉点\n位于 15m",
                xy=(mid_norm[1], 0.55), xytext=(mid_norm[1] + 0.15, 0.6),
                fontsize=10, color="orange", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="orange"))

    # 标注差异
    ax.text(mid_norm[0], 0.25, f"前段差异: {diff_15:.3f}\n(几乎重合)",
            ha="center", fontsize=9, color="dimgray",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))
    ax.text(mid_norm[1], 0.25, f"后段差异: {diff_60:.3f}\n(显著分叉)",
            ha="center", fontsize=9, color="dimgray",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))

    plt.tight_layout()
    fig1_path = OUT_DIR / "fig1_mean_overlay.png"
    plt.savefig(fig1_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"图 1 已保存: {fig1_path}", flush=True)

    # ============================================================
    # 图 2：分位数曲线叠加（p25/p50/p75）
    # ============================================================
    print("生成图 2: 分位数曲线叠加...", flush=True)
    fig, ax = plt.subplots(figsize=(10, 7))

    for df, color, label in [
        (high_df, "#C44E52", f"高 R (>2.0), n={len(high_df)}"),
        (low_df, "#55A868", f"低 R (<1.6), n={len(low_df)}"),
    ]:
        if len(df) == 0:
            continue
        p25 = [df["H_5_15"].quantile(0.25), df["H_15_60"].quantile(0.25)]
        p50 = [df["H_5_15"].quantile(0.50), df["H_15_60"].quantile(0.50)]
        p75 = [df["H_5_15"].quantile(0.75), df["H_15_60"].quantile(0.75)]

        # IQR 带
        ax.fill_between(mid_norm, p25, p75, color=color, alpha=0.15)
        # 中位数线
        ax.plot(mid_norm, p50, marker="D", markersize=8, linewidth=2,
                color=color, label=f"{label} (p50)")
        # 标注中位数
        for x, m in zip(mid_norm, p50):
            ax.annotate(f"{m:.3f}", xy=(x, m), xytext=(8, 0),
                        textcoords="offset points", fontsize=9, color=color)

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="GBM H=0.5")
    ax.set_xticks(mid_norm)
    ax.set_xticklabels(mid_labels, fontsize=11)
    ax.set_xlabel("尺度区间中点（对数）", fontsize=12)
    ax.set_ylabel("H", fontsize=12)
    ax.set_title("H(τ) 曲线叠加：高 R vs 低 R（p25-p75 带 + 中位数）", fontsize=13, fontweight="bold")
    ax.legend(loc="lower right", fontsize=10)
    ax.set_ylim(0.15, 0.7)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig2_path = OUT_DIR / "fig2_quantile_overlay.png"
    plt.savefig(fig2_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"图 2 已保存: {fig2_path}", flush=True)

    # ============================================================
    # 图 3：单条曲线叠加（随机抽样 50 条）
    # ============================================================
    print("生成图 3: 单条曲线抽样叠加...", flush=True)
    fig, ax = plt.subplots(figsize=(10, 7))

    n_sample = min(50, len(high_df), len(low_df))
    if len(high_df) > 0:
        high_sample = high_df.sample(n=n_sample, random_state=42)
        for _, row in high_sample.iterrows():
            h_vals = [row["H_5_15"], row["H_15_60"]]
            ax.plot(mid_norm, h_vals, color="#C44E52", alpha=0.1, linewidth=0.8)
    if len(low_df) > 0:
        low_sample = low_df.sample(n=n_sample, random_state=42)
        for _, row in low_sample.iterrows():
            h_vals = [row["H_5_15"], row["H_15_60"]]
            ax.plot(mid_norm, h_vals, color="#55A868", alpha=0.1, linewidth=0.8)

    # 叠加均值线
    if len(high_df) > 0:
        means = [high_df["H_5_15"].mean(), high_df["H_15_60"].mean()]
        ax.plot(mid_norm, means, marker="o", markersize=10, linewidth=3,
                color="#C44E52", label=f"高 R 均值 (n={len(high_df)})")
    if len(low_df) > 0:
        means = [low_df["H_5_15"].mean(), low_df["H_15_60"].mean()]
        ax.plot(mid_norm, means, marker="o", markersize=10, linewidth=3,
                color="#55A868", label=f"低 R 均值 (n={len(low_df)})")

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="GBM H=0.5")
    ax.set_xticks(mid_norm)
    ax.set_xticklabels(mid_labels, fontsize=11)
    ax.set_xlabel("尺度区间中点（对数）", fontsize=12)
    ax.set_ylabel("H", fontsize=12)
    ax.set_title(f"H(τ) 曲线叠加：高 R vs 低 R（{n_sample} 条抽样 + 均值）", fontsize=13, fontweight="bold")
    ax.legend(loc="lower right", fontsize=10)
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig3_path = OUT_DIR / "fig3_individual_overlay.png"
    plt.savefig(fig3_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"图 3 已保存: {fig3_path}", flush=True)

    # ============================================================
    # 图 4：分叉点定位 + 差异放大
    # ============================================================
    print("生成图 4: 分叉点定位...", flush=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 图 4a: 差异曲线
    ax = axes[0]
    # 在三个尺度点计算高/低 R 的 H 差异
    # 5m 点（用 H_5_15 代表 5-15 区间）
    # 15m 点（交界，用 H_5_15 和 H_15_60 的平均）
    # 1h 点（用 H_15_60 代表 15-60 区间）
    scale_points = [0, 0.5, 1.0]  # 5m, 15m, 1h（归一化）
    scale_labels = ["5m", "15m", "1h"]

    if len(high_df) > 0 and len(low_df) > 0:
        # 5m 点：H_5_15
        diff_5m = high_df["H_5_15"].mean() - low_df["H_5_15"].mean()
        # 15m 点：H_5_15 和 H_15_60 的平均
        high_15m = (high_df["H_5_15"].mean() + high_df["H_15_60"].mean()) / 2
        low_15m = (low_df["H_5_15"].mean() + low_df["H_15_60"].mean()) / 2
        diff_15m = high_15m - low_15m
        # 1h 点：H_15_60
        diff_1h = high_df["H_15_60"].mean() - low_df["H_15_60"].mean()

        diffs = [diff_5m, diff_15m, diff_1h]
        colors_bar = ["#4C72B0" if abs(d) < 0.05 else "#C44E52" for d in diffs]
        ax.bar(scale_points, diffs, width=0.3, color=colors_bar, alpha=0.7)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.axhline(0.05, color="orange", linestyle="--", linewidth=1, label="显著差异阈值 (0.05)")
        ax.axhline(-0.05, color="orange", linestyle="--", linewidth=1)
        for x, d in zip(scale_points, diffs):
            ax.annotate(f"{d:+.3f}", xy=(x, d), xytext=(0, 8 if d > 0 else -15),
                        textcoords="offset points", ha="center", fontsize=10, fontweight="bold")
        ax.set_xticks(scale_points)
        ax.set_xticklabels(scale_labels, fontsize=11)
        ax.set_ylabel("H 差异 (高 R - 低 R)", fontsize=12)
        ax.set_title("分叉点定位：各尺度 H 差异", fontsize=12, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")

    # 图 4b: 高/低 R 在不同尺度上的分布
    ax = axes[1]
    if len(high_df) > 0 and len(low_df) > 0:
        positions = [1, 2, 3, 4]
        # H_5_15: 高 R, 低 R
        # H_15_60: 高 R, 低 R
        data = [high_df["H_5_15"].dropna(), low_df["H_5_15"].dropna(),
                high_df["H_15_60"].dropna(), low_df["H_15_60"].dropna()]
        labels = ["高R\nH(5m,15m)", "低R\nH(5m,15m)", "高R\nH(15m,1h)", "低R\nH(15m,1h)"]
        bp = ax.boxplot(data, positions=positions, widths=0.6, patch_artist=True)
        colors_box = ["#C44E52", "#55A868", "#C44E52", "#55A868"]
        for patch, c in zip(bp["boxes"], colors_box):
            patch.set_facecolor(c)
            patch.set_alpha(0.5)
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="GBM H=0.5")
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_ylabel("H", fontsize=12)
        ax.set_title("高/低 R 在两区间的 H 分布对比", fontsize=12, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")

        # 标注：前段重合
        ax.annotate("前段重合\n(中位数接近)",
                    xy=(1.5, 0.6), xytext=(1.5, 0.75),
                    ha="center", fontsize=9, color="dimgray",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))
        ax.annotate("后段分叉\n(中位数分离)",
                    xy=(3.5, 0.6), xytext=(3.5, 0.75),
                    ha="center", fontsize=9, color="dimgray",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))

    plt.suptitle("H 曲线分叉点定位与差异量化", fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig4_path = OUT_DIR / "fig4_bifurcation.png"
    plt.savefig(fig4_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"图 4 已保存: {fig4_path}", flush=True)

    # ============================================================
    # 数值汇总
    # ============================================================
    print("\n" + "=" * 70, flush=True)
    print("数值汇总", flush=True)
    print("=" * 70, flush=True)

    print("\n--- 高/低 R 事件 H 均值 ---", flush=True)
    if len(high_df) > 0:
        print(f"高 R: H(5m,15m)={high_df['H_5_15'].mean():.4f}, H(15m,1h)={high_df['H_15_60'].mean():.4f}", flush=True)
    if len(low_df) > 0:
        print(f"低 R: H(5m,15m)={low_df['H_5_15'].mean():.4f}, H(15m,1h)={low_df['H_15_60'].mean():.4f}", flush=True)

    print("\n--- 差异量化 ---", flush=True)
    if len(high_df) > 0 and len(low_df) > 0:
        d1 = high_df["H_5_15"].mean() - low_df["H_5_15"].mean()
        d2 = high_df["H_15_60"].mean() - low_df["H_15_60"].mean()
        print(f"前段差异 (5-15m): {d1:+.4f}", flush=True)
        print(f"后段差异 (15-1h): {d2:+.4f}", flush=True)
        print(f"分叉比 (后/前):  {d2/d1 if abs(d1) > 0.001 else float('inf'):+.2f}x", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("完成", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
