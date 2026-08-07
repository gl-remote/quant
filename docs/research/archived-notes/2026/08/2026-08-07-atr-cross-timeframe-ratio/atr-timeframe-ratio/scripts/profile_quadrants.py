"""
ATR 跨周期比值研究 · 四象限市场环境画像
========================================

基于 Stage 3 面板（state_S 四象限），做描述性统计和可视化：
1. R_bar / S_H / S_L 在四象限中的分布；
2. 波动水平（H_norm/L_norm/common_vol）按象限；
3. 累计变化（dLogH/dLogL/dLogR）按象限；
4. 趋势位置（MADEV_60/trend_strength）按象限；
5. 板块、年份、交易时段分布；
6. 前向收益和绝对收益按象限（描述性，不做交易判断）；
7. 状态持续时间和状态转换热力图；
8. 可视化图表输出。

不追求交易信号，目标是建立"四象限分别长什么样"的整体印象。
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

# 中文字体
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[5]
SCRIPT_DIR = Path(__file__).resolve().parents[1]
PANEL_PATH = SCRIPT_DIR / "outputs" / "stage3" / "stage3_panel.parquet"
OUT_DIR = SCRIPT_DIR / "outputs" / "profile"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

STATE_ORDER = ["co_compress", "H_only", "L_only", "co_expand"]
STATE_LABELS = {
    "co_compress": "双周期压缩",
    "H_only": "高周期独扩",
    "L_only": "低周期独扩",
    "co_expand": "共振扩张",
}
STATE_COLORS = {
    "co_compress": "#4C72B0",
    "H_only": "#DD8452",
    "L_only": "#55A868",
    "co_expand": "#C44E52",
}


def safe_corr(x, y):
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 10:
        return np.nan
    return float(np.corrcoef(x[mask], y[mask])[0, 1])


def main() -> None:
    panel = pd.read_parquet(PANEL_PATH)
    panel["datetime"] = pd.to_datetime(panel["datetime"])
    panel["hour"] = panel["datetime"].dt.hour
    panel["year"] = panel["datetime"].dt.year
    panel["month"] = panel["datetime"].dt.month
    print(f"面板: {len(panel)} 行, {panel['symbol'].nunique()} 合约", flush=True)

    # ============================================================
    # 1. 四象限基础画像
    # ============================================================
    print("\n=== 1. 四象限基础画像 ===", flush=True)
    metrics = [
        "R_bar", "R_clock", "S_H", "S_L",
        "H_norm", "L_norm", "common_vol",
        "dLogH_5", "dLogL_5", "dLogR_5",
        "dLogH_20", "dLogL_20", "dLogR_20",
        "MADEV_60", "trend_strength",
        "fwd_ret_5", "fwd_ret_20", "fwd_abs_ret_20",
    ]
    available = [m for m in metrics if m in panel.columns]

    profile_rows = []
    for state in STATE_ORDER:
        sub = panel[panel["state_S"] == state]
        row = {
            "state": state,
            "label": STATE_LABELS[state],
            "n": len(sub),
            "pct": len(sub) / len(panel),
        }
        for m in available:
            row[f"{m}_mean"] = float(sub[m].mean()) if m in sub.columns else np.nan
            row[f"{m}_median"] = float(sub[m].median()) if m in sub.columns else np.nan
            row[f"{m}_std"] = float(sub[m].std()) if m in sub.columns else np.nan
        # 方向胜率（描述性）
        for h in [5, 20]:
            col = f"fwd_ret_{h}"
            if col in sub.columns:
                row[f"win_rate_{h}"] = float((sub[col] > 0).mean())
        profile_rows.append(row)

    profile = pd.DataFrame(profile_rows)
    profile.to_csv(OUT_DIR / "profile_by_state.csv", index=False)
    print(profile[["state", "n", "pct", "R_bar_mean", "S_H_mean", "S_L_mean",
                   "H_norm_mean", "L_norm_mean", "fwd_ret_20_mean",
                   "fwd_abs_ret_20_mean", "win_rate_20"]].round(4).to_string(index=False),
          flush=True)

    # ============================================================
    # 2. 按板块
    # ============================================================
    print("\n=== 2. 按板块 × 象限 ===", flush=True)
    sector_state = (
        panel.groupby(["sector", "state_S"]).size().unstack(fill_value=0)
    )
    sector_pct = sector_state.div(sector_state.sum(axis=1), axis=0)
    sector_pct.to_csv(OUT_DIR / "profile_sector_state_pct.csv")
    sector_state.to_csv(OUT_DIR / "profile_sector_state_count.csv")
    print(sector_pct.round(3).to_string(), flush=True)

    # 板块×象限的前向收益
    sector_ret = panel.groupby(["sector", "state_S"])["fwd_ret_20"].agg(
        ["count", "mean", "median"]
    ).reset_index()
    sector_ret.to_csv(OUT_DIR / "profile_sector_fwd_ret20.csv", index=False)

    # ============================================================
    # 3. 按年份
    # ============================================================
    print("\n=== 3. 按年份 × 象限 ===", flush=True)
    year_state = panel.groupby(["year", "state_S"]).size().unstack(fill_value=0)
    year_pct = year_state.div(year_state.sum(axis=1), axis=0)
    year_pct.to_csv(OUT_DIR / "profile_year_state_pct.csv")
    print(year_pct.round(3).to_string(), flush=True)

    year_ret = panel.groupby(["year", "state_S"])["fwd_ret_20"].agg(
        ["count", "mean", "median"]
    ).reset_index()
    year_ret.to_csv(OUT_DIR / "profile_year_fwd_ret20.csv", index=False)

    # ============================================================
    # 4. 按交易时段
    # ============================================================
    print("\n=== 4. 按交易时段 ===", flush=True)

    def session(h):
        if 9 <= h < 11 or 13 <= h < 15:
            return "日盘"
        if 21 <= h <= 23 or 0 <= h < 3:
            return "夜盘"
        return "其他"

    panel["session"] = panel["hour"].apply(session)
    sess_state = panel.groupby(["session", "state_S"]).size().unstack(fill_value=0)
    sess_pct = sess_state.div(sess_state.sum(axis=1), axis=0)
    sess_pct.to_csv(OUT_DIR / "profile_session_state_pct.csv")
    print(sess_pct.round(3).to_string(), flush=True)

    # ============================================================
    # 5. 状态持续时间
    # ============================================================
    print("\n=== 5. 状态持续时间 ===", flush=True)
    panel_sorted = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    # 新段：与前一根状态不同，或换了 symbol
    sym_change = panel_sorted["symbol"] != panel_sorted["symbol"].shift(1)
    state_change = panel_sorted["state_S"] != panel_sorted["state_S"].shift(1)
    new_seg = sym_change | state_change
    panel_sorted["seg_id"] = new_seg.cumsum()
    durations = panel_sorted.groupby(["symbol", "seg_id", "state_S"]).size().reset_index(name="duration")

    dur_rows = []
    for state in STATE_ORDER:
        d = durations[durations["state_S"] == state]["duration"]
        dur_rows.append({
            "state": state,
            "n_segments": int(len(d)),
            "mean": float(d.mean()),
            "median": float(d.median()),
            "p25": float(d.quantile(0.25)),
            "p75": float(d.quantile(0.75)),
            "p90": float(d.quantile(0.90)),
            "max": int(d.max()),
        })
    dur_df = pd.DataFrame(dur_rows)
    dur_df.to_csv(OUT_DIR / "profile_state_duration.csv", index=False)
    print(dur_df.round(2).to_string(index=False), flush=True)

    # ============================================================
    # 6. 状态转换矩阵
    # ============================================================
    print("\n=== 6. 状态转换矩阵（1步）===", flush=True)
    panel_sorted["next_state"] = panel_sorted.groupby("symbol")["state_S"].shift(-1)
    trans = panel_sorted.dropna(subset=["next_state"])
    trans_matrix = pd.crosstab(trans["state_S"], trans["next_state"], normalize="index")
    trans_matrix = trans_matrix.reindex(index=STATE_ORDER, columns=STATE_ORDER, fill_value=0)
    trans_matrix.to_csv(OUT_DIR / "profile_transition_matrix.csv")
    print(trans_matrix.round(3).to_string(), flush=True)

    # 5步转换
    panel_sorted["next_state_5"] = panel_sorted.groupby("symbol")["state_S"].shift(-5)
    trans5 = panel_sorted.dropna(subset=["next_state_5"])
    trans5_matrix = pd.crosstab(trans5["state_S"], trans5["next_state_5"], normalize="index")
    trans5_matrix = trans5_matrix.reindex(index=STATE_ORDER, columns=STATE_ORDER, fill_value=0)
    trans5_matrix.to_csv(OUT_DIR / "profile_transition_matrix_5.csv")

    # ============================================================
    # 7. R_bar 分布与均值回归
    # ============================================================
    print("\n=== 7. R_bar 自相关与均值回归 ===", flush=True)
    acf_rows = []
    for sym, sub in panel_sorted.groupby("symbol"):
        sub = sub.dropna(subset=["R_bar"]).sort_values("datetime")
        if len(sub) < 100:
            continue
        r = sub["R_bar"].values
        acf1 = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if len(r) > 10 else np.nan
        acf5 = float(np.corrcoef(r[:-5], r[5:])[0, 1]) if len(r) > 20 else np.nan
        acf20 = float(np.corrcoef(r[:-20], r[20:])[0, 1]) if len(r) > 40 else np.nan
        # 半衰期：AR(1) 系数
        ar1 = np.corrcoef(r[:-1], r[1:])[0, 1]
        half_life = float(-np.log(2) / np.log(abs(ar1))) if 0 < ar1 < 1 else np.nan
        acf_rows.append({
            "symbol": sym,
            "sector": sub["sector"].iloc[0],
            "acf1": acf1, "acf5": acf5, "acf20": acf20,
            "half_life_bars": half_life,
        })
    acf_df = pd.DataFrame(acf_rows)
    acf_df.to_csv(OUT_DIR / "profile_rbar_autocorr.csv", index=False)
    print(f"  ACF(1) 中位: {acf_df['acf1'].median():.3f}")
    print(f"  ACF(5) 中位: {acf_df['acf5'].median():.3f}")
    print(f"  ACF(20) 中位: {acf_df['acf20'].median():.3f}")
    print(f"  半衰期（根）中位: {acf_df['half_life_bars'].median():.1f}", flush=True)

    # ============================================================
    # 8. R_bar 与前向波动率的关系（波动率预测力，非方向）
    # ============================================================
    print("\n=== 8. R_bar 与前向波动率 ===", flush=True)
    # 用 fwd_abs_ret 作为已实现波动率代理
    for h in [5, 20]:
        col = f"fwd_abs_ret_{h}"
        if col not in panel.columns:
            continue
        c_overall = safe_corr(panel["R_bar"].values, panel[col].values)
        c_sh = safe_corr(panel["S_H"].values, panel[col].values)
        c_sl = safe_corr(panel["S_L"].values, panel[col].values)
        c_h = safe_corr(panel["H_norm"].values, panel[col].values)
        c_l = safe_corr(panel["L_norm"].values, panel[col].values)
        c_cv = safe_corr(panel["common_vol"].values, panel[col].values)
        print(f"  h={h}: corr(R_bar,|r|)={c_overall:.3f}, corr(S_H)={c_sh:.3f}, "
              f"corr(S_L)={c_sl:.3f}, corr(H_norm)={c_h:.3f}, "
              f"corr(L_norm)={c_l:.3f}, corr(common_vol)={c_cv:.3f}",
              flush=True)

    # ============================================================
    # 图表 1: 四象限样本占比 + 因子均值
    # ============================================================
    print("\n生成图表...", flush=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1a: 占比饼图
    ax = axes[0, 0]
    sizes = profile["n"].values
    labels = [f"{STATE_LABELS[s]}\n{n} ({p:.1%})" for s, n, p in zip(profile["state"], sizes, profile["pct"])]
    colors = [STATE_COLORS[s] for s in profile["state"]]
    ax.pie(sizes, labels=labels, colors=colors, startangle=90, textprops={"fontsize": 9})
    ax.set_title("四象限样本占比", fontsize=12)

    # 1b: R_bar/S_H/S_L 均值
    ax = axes[0, 1]
    x = np.arange(len(STATE_ORDER))
    width = 0.25
    ax.bar(x - width, profile["R_bar_mean"], width, label="R_bar", color="#4C72B0")
    ax.bar(x, profile["S_H_mean"], width, label="S_H", color="#DD8452")
    ax.bar(x + width, profile["S_L_mean"], width, label="S_L", color="#55A868")
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
    ax.set_title("因子均值", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # 1c: 波动率水平
    ax = axes[1, 0]
    ax.bar(x - width, profile["H_norm_mean"] * 100, width, label="H_norm(%)", color="#DD8452")
    ax.bar(x, profile["L_norm_mean"] * 100, width, label="L_norm(%)", color="#55A868")
    ax.bar(x + width, profile["common_vol_mean"] * 100, width, label="common_vol(%)", color="#8172B2")
    ax.set_xticks(x)
    ax.set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
    ax.set_title("单周期波动率水平", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # 1d: 前向 |r|
    ax = axes[1, 1]
    ax.bar(x - width/2, profile["fwd_abs_ret_20_mean"] * 100, width, label="fwd_|r|_20(%)", color="#C44E52")
    ax2 = ax.twinx()
    ax2.bar(x + width/2, profile["fwd_ret_20_mean"] * 100, width, label="fwd_ret_20(%)", color="#4C72B0", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
    ax.set_title("前向收益（红=|r|, 蓝=方向）", fontsize=12)
    ax.grid(axis="y", alpha=0.3)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper left")

    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig1_quadrant_profile.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ============================================================
    # 图表 2: R_bar 分布直方图（按象限）
    # ============================================================
    fig, ax = plt.subplots(figsize=(12, 6))
    for state in STATE_ORDER:
        sub = panel[panel["state_S"] == state]
        ax.hist(sub["R_bar"].dropna(), bins=60, alpha=0.5,
                label=STATE_LABELS[state], color=STATE_COLORS[state], density=True)
    ax.axvline(2.0, color="black", linestyle="--", linewidth=1, label="sqrt(4)=2.0")
    ax.axvline(panel["R_bar"].median(), color="gray", linestyle=":", linewidth=1,
               label=f"中位 {panel['R_bar'].median():.2f}")
    ax.set_xlabel("R_bar = ATR_1h / ATR_15m")
    ax.set_ylabel("密度")
    ax.set_title("R_bar 分布（按四象限）", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_rbar_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ============================================================
    # 图表 3: S_H vs S_L 散点 + R_bar 等高线
    # ============================================================
    fig, ax = plt.subplots(figsize=(10, 8))
    sample = panel.dropna(subset=["S_H", "S_L", "R_bar"]).sample(
        min(3000, len(panel)), random_state=42
    )
    sc = ax.scatter(sample["S_L"], sample["S_H"], c=sample["R_bar"],
                    cmap="viridis", alpha=0.4, s=10)
    ax.axvline(1.0, color="gray", linestyle="--", linewidth=0.8)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlabel("S_L (15m 短长 ATR 比)")
    ax.set_ylabel("S_H (1h 短长 ATR 比)")
    ax.set_title("S_H vs S_L（颜色=R_bar）", fontsize=12)
    plt.colorbar(sc, ax=ax, label="R_bar")
    ax.grid(alpha=0.3)
    # 象限标注
    ax.text(0.05, 0.05, "双压缩", transform=ax.transAxes, fontsize=11,
            color=STATE_COLORS["co_compress"], fontweight="bold")
    ax.text(0.95, 0.05, "低周期独扩", transform=ax.transAxes, fontsize=11,
            color=STATE_COLORS["L_only"], fontweight="bold", ha="right")
    ax.text(0.05, 0.95, "高周期独扩", transform=ax.transAxes, fontsize=11,
            color=STATE_COLORS["H_only"], fontweight="bold", va="top")
    ax.text(0.95, 0.95, "共振扩张", transform=ax.transAxes, fontsize=11,
            color=STATE_COLORS["co_expand"], fontweight="bold", ha="right", va="top")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_sh_sl_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ============================================================
    # 图表 4: 状态转换热力图
    # ============================================================
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, mat, title in [(axes[0], trans_matrix, "1 步转换概率"),
                            (axes[1], trans5_matrix, "5 步转换概率")]:
        im = ax.imshow(mat.values, cmap="YlOrRd", aspect="auto", vmin=0, vmax=1)
        ax.set_xticks(range(len(STATE_ORDER)))
        ax.set_yticks(range(len(STATE_ORDER)))
        ax.set_xticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9, rotation=30, ha="right")
        ax.set_yticklabels([STATE_LABELS[s] for s in STATE_ORDER], fontsize=9)
        ax.set_xlabel("下一状态")
        ax.set_ylabel("当前状态")
        ax.set_title(title, fontsize=12)
        for i in range(len(STATE_ORDER)):
            for j in range(len(STATE_ORDER)):
                val = mat.iloc[i, j]
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        color="white" if val > 0.5 else "black", fontsize=9)
        plt.colorbar(im, ax=ax, fraction=0.046)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig4_transition_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ============================================================
    # 图表 5: 板块 × 象限堆叠柱状图
    # ============================================================
    fig, ax = plt.subplots(figsize=(12, 6))
    sectors = sector_pct.index.tolist()
    bottom = np.zeros(len(sectors))
    for state in STATE_ORDER:
        vals = sector_pct[state].values if state in sector_pct.columns else np.zeros(len(sectors))
        ax.bar(sectors, vals, bottom=bottom, label=STATE_LABELS[state], color=STATE_COLORS[state])
        bottom += vals
    ax.set_ylabel("占比")
    ax.set_title("板块 × 四象限分布", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig5_sector_quadrant.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ============================================================
    # 图表 6: R_bar 自相关衰减
    # ============================================================
    fig, ax = plt.subplots(figsize=(10, 6))
    # 全样本平均 ACF
    sym = panel["symbol"].iloc[0]
    # 画多个合约的 ACF
    for sym, sub in panel_sorted.groupby("symbol"):
        sub = sub.dropna(subset=["R_bar"]).sort_values("datetime")
        if len(sub) < 200:
            continue
        r = sub["R_bar"].values
        acfs = []
        for lag in [1, 2, 3, 5, 10, 20, 40, 60]:
            if len(r) > lag + 5:
                acfs.append(float(np.corrcoef(r[:-lag], r[lag:])[0, 1]))
            else:
                acfs.append(np.nan)
        ax.plot([1, 2, 3, 5, 10, 20, 40, 60], acfs, alpha=0.2, color="#4C72B0", linewidth=0.8)
    # 中位 ACF
    lags = [1, 2, 3, 5, 10, 20, 40, 60]
    med_acfs = []
    for lag in lags:
        vals = []
        for sym, sub in panel_sorted.groupby("symbol"):
            sub = sub.dropna(subset=["R_bar"]).sort_values("datetime")
            r = sub["R_bar"].values
            if len(r) > lag + 5:
                vals.append(float(np.corrcoef(r[:-lag], r[lag:])[0, 1]))
        med_acfs.append(np.nanmedian(vals))
    ax.plot(lags, med_acfs, color="red", linewidth=2.5, marker="o", label="中位 ACF", zorder=5)
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlabel("滞后（根 1h）")
    ax.set_ylabel("自相关系数")
    ax.set_title("R_bar 自相关衰减", fontsize=12)
    ax.set_xscale("log")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig6_rbar_acf.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ============================================================
    # 图表 7: 状态持续时间分布（对数刻度）
    # ============================================================
    fig, ax = plt.subplots(figsize=(10, 6))
    for state in STATE_ORDER:
        d = durations[durations["state_S"] == state]["duration"]
        if len(d) > 0:
            ax.hist(d, bins=50, alpha=0.5, label=STATE_LABELS[state],
                    color=STATE_COLORS[state], density=True)
    ax.set_xlabel("持续根数")
    ax.set_ylabel("密度")
    ax.set_title("状态持续时间分布", fontsize=12)
    ax.set_xscale("log")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig7_duration_dist.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ============================================================
    # Summary JSON
    # ============================================================
    summary = {
        "n_rows": int(len(panel)),
        "n_symbols": int(panel["symbol"].nunique()),
        "date_range": [str(panel["datetime"].min()), str(panel["datetime"].max())],
        "state_counts": {s: int((panel["state_S"] == s).sum()) for s in STATE_ORDER},
        "state_pct": {s: float((panel["state_S"] == s).mean()) for s in STATE_ORDER},
        "rbar_acf": {
            "median_acf1": float(acf_df["acf1"].median()),
            "median_acf5": float(acf_df["acf5"].median()),
            "median_acf20": float(acf_df["acf20"].median()),
            "median_half_life_bars": float(acf_df["half_life_bars"].median()),
        },
        "transition_1step": trans_matrix.round(3).to_dict(),
        "profile": profile[["state", "n", "pct", "R_bar_mean", "S_H_mean", "S_L_mean",
                            "H_norm_mean", "L_norm_mean", "fwd_ret_20_mean",
                            "fwd_abs_ret_20_mean", "win_rate_20"]].to_dict("records"),
    }
    with open(OUT_DIR / "profile_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n输出已保存到 {OUT_DIR}", flush=True)
    print(f"图表在 {FIG_DIR}", flush=True)


if __name__ == "__main__":
    main()
