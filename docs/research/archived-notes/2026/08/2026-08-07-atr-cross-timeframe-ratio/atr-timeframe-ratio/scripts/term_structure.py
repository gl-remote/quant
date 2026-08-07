"""
ATR 跨周期比值研究 · F 组：跨期限结构
======================================

构建 5m / 15m / 1h / daily 四周期 ATR 的期限结构曲线：
  R_5_15   = ATR_15m(14)  / ATR_5m(42)     # 时钟对齐，约 3.5 小时
  R_15_1h  = ATR_1h(14)   / ATR_15m(56)    # 约 14 小时
  R_1h_d   = ATR_d(14)    / ATR_1h(168)    # 约 7 天（日线从 1h 聚合）

也保留 bar 对齐口径：
  R_5_15_bar  = ATR_15m(14) / ATR_5m(14)
  R_15_1h_bar = ATR_1h(14)  / ATR_15m(14)
  R_1h_d_bar  = ATR_d(14)   / ATR_1h(14)

期限曲线形态：
- term_slope       = R_1h_d - R_15_1h - R_5_15（标准化）
- term_curve_state = 三个比值各自三分位的组合（27 种，简化为 7 种典型形态）
- term_convexity   = (R_1h_d + R_5_15) / 2 - R_15_1h

观察：
1. 三个比值分布和相关性；
2. 期限曲线形态分布；
3. 曲线形态对前向波动率/收益的预测力；
4. 极端期限结构（全高/全低/倒挂）后的市场行为；
5. 板块、年份差异。
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

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[5]
SCRIPT_DIR = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
OUT_DIR = SCRIPT_DIR / "outputs" / "term_structure"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)


def parse_symbol(sym: str):
    parts = sym.split(".")
    return parts[0], parts[1]


def wilder_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def aggregate_daily(df_1h: pd.DataFrame) -> pd.DataFrame:
    """从 1h 聚合日线。按交易日分组，商品夜盘算作下一日。"""
    df = df_1h.copy()
    # 简单按日期聚合（夜盘算当日）
    df["date"] = df["datetime"].dt.date
    daily = df.groupby("date").agg(
        datetime=("datetime", "last"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    ).reset_index(drop=True)
    return daily


def load_tf(sym: str, tf: str) -> pd.DataFrame | None:
    f = CSV_DIR / f"{sym}.tqsdk.{tf}.csv"
    if not f.exists():
        return None
    return pd.read_csv(f, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)


def compute_panel(sym: str) -> pd.DataFrame | None:
    df_1h = load_tf(sym, "1h")
    df_15 = load_tf(sym, "15m")
    df_5 = load_tf(sym, "5m")
    if df_1h is None or df_15 is None or df_5 is None:
        return None
    if len(df_1h) < 200 or len(df_15) < 400 or len(df_5) < 800:
        return None

    # ATR
    df_1h["H"] = wilder_atr(df_1h, 14)
    df_1h["H_clock"] = wilder_atr(df_1h, 168)  # 7 天 ≈ 168 根 1h
    df_1h["H_long"] = wilder_atr(df_1h, 50)
    df_15["L15"] = wilder_atr(df_15, 14)
    df_15["L15_clock"] = wilder_atr(df_15, 56)
    df_15["L15_long"] = wilder_atr(df_15, 200)
    df_5["L5"] = wilder_atr(df_5, 14)
    df_5["L5_clock"] = wilder_atr(df_5, 42)  # 42 根 5m ≈ 14 根 15m ≈ 3.5h
    df_5["L5_long"] = wilder_atr(df_5, 600)

    # 日线从 1h 聚合
    daily = aggregate_daily(df_1h)
    daily["D"] = wilder_atr(daily, 14)

    # 以 1h 收盘时间为主
    base = df_1h[["datetime", "open", "high", "low", "close", "H", "H_clock", "H_long"]].dropna().copy()
    base = base.sort_values("datetime")

    # merge_asof 15m / 5m
    for label, df_l in [("15", df_15), ("5", df_5)]:
        cols = ["datetime", f"L{label}", f"L{label}_clock", f"L{label}_long"]
        sub = df_l[cols].dropna().sort_values("datetime")
        base = pd.merge_asof(base, sub, on="datetime", direction="backward")

    # merge_asof daily（日线 ATR）
    d_sub = daily[["datetime", "D"]].dropna().sort_values("datetime")
    base = pd.merge_asof(base, d_sub, on="datetime", direction="backward")

    # 跨期限比值（bar 对齐）
    base["R_5_15_bar"] = base["L15"] / base["L5"]
    base["R_15_1h_bar"] = base["H"] / base["L15"]
    base["R_1h_d_bar"] = base["D"] / base["H"]

    # 时钟对齐
    base["R_5_15"] = base["L15_clock"] / base["L5_clock"]
    base["R_15_1h"] = base["H"] / base["L15_clock"]
    base["R_1h_d"] = base["D"] / base["H_clock"]

    # 理论缩放参考
    base["sqrt3"] = np.sqrt(3)    # 5m→15m
    base["sqrt4"] = 2.0          # 15m→1h
    # 1h→daily: 一天约 6 根 1h（日盘4+夜盘2），用 sqrt(6)≈2.45

    # 期限曲线形态（时钟对齐）
    base["term_slope"] = (base["R_1h_d"] - base["R_15_1h"]) - (base["R_15_1h"] - base["R_5_15"])
    # 简化：convexity > 0 表示中间段低于两端（U 型），<0 表示倒 U
    base["term_convexity"] = (base["R_1h_d"] + base["R_5_15"]) / 2 - base["R_15_1h"]
    # 整体水平
    base["term_level"] = (base["R_5_15"] + base["R_15_1h"] + base["R_1h_d"]) / 3

    # 三分位分类
    for col in ["R_5_15", "R_15_1h", "R_1h_d"]:
        base[f"{col}_tercile"] = pd.qcut(base[col], 3, labels=["low", "mid", "high"])

    # 典型曲线形态（7 种）
    def classify_curve(row):
        t1 = row["R_5_15_tercile"]
        t2 = row["R_15_1h_tercile"]
        t3 = row["R_1h_d_tercile"]
        if t1 == "high" and t2 == "high" and t3 == "high":
            return "all_high"
        if t1 == "low" and t2 == "low" and t3 == "low":
            return "all_low"
        if t1 == "high" and t2 == "low" and t3 == "high":
            return "U_shape"
        if t1 == "low" and t2 == "high" and t3 == "low":
            return "inverted_U"
        if t3 == "high" and t1 != "high":
            return "long_end_high"
        if t3 == "low" and t1 != "low":
            return "long_end_low"
        return "other"

    base["term_curve_state"] = base.apply(classify_curve, axis=1)

    # 同周期短长比
    base["S_H"] = base["H"] / base["H_long"]
    base["S_15"] = base["L15_clock"] / base["L15_long"]
    base["S_5"] = base["L5_clock"] / base["L5_long"]

    # 波动率水平
    base["H_norm"] = base["H"] / base["close"]

    # 前向
    base["fwd_ret_5"] = base["close"].shift(-5) / base["close"] - 1
    base["fwd_ret_20"] = base["close"].shift(-20) / base["close"] - 1
    base["fwd_ret_60"] = base["close"].shift(-60) / base["close"] - 1
    base["fwd_abs_ret_5"] = base["fwd_ret_5"].abs()
    base["fwd_abs_ret_20"] = base["fwd_ret_20"].abs()
    base["fwd_abs_ret_60"] = base["fwd_ret_60"].abs()

    base["symbol"] = sym
    ex, code = parse_symbol(sym)
    sector_map = {"SHFE": "有色/能化", "DCE": "农产品/黑色", "CZCE": "农产品", "INE": "能化", "GFEX": "黑色/能化"}
    base["sector"] = sector_map.get(ex, "其他")
    base["date"] = base["datetime"].dt.date
    base["year"] = base["datetime"].dt.year

    return base.dropna(subset=["R_5_15", "R_15_1h", "R_1h_d"])


def main() -> None:
    print("加载并计算所有合约...", flush=True)
    panels = []
    for f in sorted(CSV_DIR.glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = compute_panel(sym)
        if p is not None:
            panels.append(p)
    panel = pd.concat(panels, ignore_index=True)
    print(f"合并面板: {len(panel)} 行, {panel['symbol'].nunique()} 合约", flush=True)

    # ============================================================
    # 1. 三个比值分布
    # ============================================================
    print("\n=== 1. 三个跨期限比值分布（时钟对齐）===", flush=True)
    dist_rows = []
    for col in ["R_5_15", "R_15_1h", "R_1h_d"]:
        s = panel[col]
        dist_rows.append({
            "ratio": col,
            "mean": float(s.mean()), "median": float(s.median()),
            "std": float(s.std()),
            "p05": float(s.quantile(0.05)), "p95": float(s.quantile(0.95)),
            "min": float(s.min()), "max": float(s.max()),
            "skew": float(s.skew()),
        })
    dist_df = pd.DataFrame(dist_rows)
    dist_df.to_csv(OUT_DIR / "term_distribution.csv", index=False)
    print(dist_df.round(4).to_string(index=False), flush=True)
    print(f"\n理论参考: sqrt(3)={np.sqrt(3):.3f}, sqrt(4)=2.0, sqrt(6)={np.sqrt(6):.3f}", flush=True)

    # bar 对齐对比
    print("\n--- bar 对齐 ---", flush=True)
    for col in ["R_5_15_bar", "R_15_1h_bar", "R_1h_d_bar"]:
        s = panel[col]
        print(f"  {col:15s}: mean={s.mean():.3f}, median={s.median():.3f}, std={s.std():.3f}", flush=True)

    # ============================================================
    # 2. 相关性
    # ============================================================
    print("\n=== 2. 相关性 ===", flush=True)
    corr_cols = ["R_5_15", "R_15_1h", "R_1h_d", "R_5_15_bar", "R_15_1h_bar", "R_1h_d_bar",
                 "term_slope", "term_convexity", "term_level", "H_norm"]
    corr = panel[corr_cols].corr()
    corr.to_csv(OUT_DIR / "term_correlation.csv")
    print(corr.round(3).to_string(), flush=True)

    # ============================================================
    # 3. 期限曲线形态分布
    # ============================================================
    print("\n=== 3. 期限曲线形态分布 ===", flush=True)
    curve_counts = panel["term_curve_state"].value_counts(normalize=True)
    curve_counts.to_csv(OUT_DIR / "term_curve_state_dist.csv")
    print(curve_counts.round(4).to_string(), flush=True)

    # ============================================================
    # 4. 曲线形态 × 前向收益/波动
    # ============================================================
    print("\n=== 4. 曲线形态 × 前向表现 ===", flush=True)
    curve_rows = []
    for state, sub in panel.groupby("term_curve_state"):
        row = {
            "state": state, "n": len(sub),
            "fwd_ret_20_mean": float(sub["fwd_ret_20"].mean()),
            "fwd_ret_60_mean": float(sub["fwd_ret_60"].mean()),
            "fwd_abs_20": float(sub["fwd_abs_ret_20"].mean()),
            "fwd_abs_60": float(sub["fwd_abs_ret_60"].mean()),
            "win_rate_20": float((sub["fwd_ret_20"] > 0).mean()),
            "H_norm": float(sub["H_norm"].mean()),
            "R_5_15": float(sub["R_5_15"].mean()),
            "R_15_1h": float(sub["R_15_1h"].mean()),
            "R_1h_d": float(sub["R_1h_d"].mean()),
        }
        curve_rows.append(row)
    curve_df = pd.DataFrame(curve_rows).sort_values("n", ascending=False)
    curve_df.to_csv(OUT_DIR / "term_curve_fwd.csv", index=False)
    print(curve_df.round(4).to_string(index=False), flush=True)

    # ============================================================
    # 5. 三分位组合：R_5_15 × R_15_1h × R_1h_d
    # ============================================================
    print("\n=== 5. 三分位联合分组（前向 |r|_60）===", flush=True)
    grouped = panel.groupby(["R_5_15_tercile", "R_15_1h_tercile", "R_1h_d_tercile"])
    combo = grouped.agg(
        n=("fwd_abs_ret_60", "count"),
        fwd_abs_60=("fwd_abs_ret_60", "mean"),
        fwd_ret_60=("fwd_ret_60", "mean"),
        H_norm=("H_norm", "mean"),
    ).reset_index()
    combo.to_csv(OUT_DIR / "term_tercile_combo.csv", index=False)
    # 打印 n>100 的组合
    print(combo[combo["n"] > 100].sort_values("fwd_abs_60", ascending=False).round(4).to_string(index=False), flush=True)

    # ============================================================
    # 6. 预测力：与前向波动率/收益的相关性
    # ============================================================
    print("\n=== 6. 预测力相关性 ===", flush=True)
    pred_rows = []
    for metric in ["R_5_15", "R_15_1h", "R_1h_d", "term_level", "term_slope", "term_convexity",
                   "R_5_15_bar", "R_15_1h_bar", "R_1h_d_bar", "H_norm"]:
        for h in [5, 20, 60]:
            abs_col = f"fwd_abs_ret_{h}"
            ret_col = f"fwd_ret_{h}"
            mask = ~(panel[metric].isna() | panel[abs_col].isna())
            c_abs = float(np.corrcoef(panel.loc[mask, metric], panel.loc[mask, abs_col])[0, 1])
            c_ret = float(np.corrcoef(panel.loc[mask, metric], panel.loc[mask, ret_col])[0, 1])
            pred_rows.append({"metric": metric, "horizon": h, "corr_|r|": c_abs, "corr_r": c_ret})
    pred_df = pd.DataFrame(pred_rows)
    pred_df.to_csv(OUT_DIR / "term_predictive_corr.csv", index=False)
    print(pred_df.pivot(index="metric", columns="horizon", values=["corr_|r|", "corr_r"]).round(4).to_string(), flush=True)

    # ============================================================
    # 7. 板块和年份
    # ============================================================
    print("\n=== 7. 板块平均期限比值 ===", flush=True)
    sector_rows = []
    for sec, sub in panel.groupby("sector"):
        row = {"sector": sec, "n": len(sub)}
        for col in ["R_5_15", "R_15_1h", "R_1h_d", "term_level"]:
            row[col] = float(sub[col].mean())
        sector_rows.append(row)
    sector_df = pd.DataFrame(sector_rows)
    sector_df.to_csv(OUT_DIR / "term_by_sector.csv", index=False)
    print(sector_df.round(4).to_string(index=False), flush=True)

    print("\n=== 8. 年份平均期限比值 ===", flush=True)
    year_rows = []
    for yr, sub in panel.groupby("year"):
        row = {"year": int(yr), "n": len(sub)}
        for col in ["R_5_15", "R_15_1h", "R_1h_d", "term_level"]:
            row[col] = float(sub[col].mean())
        year_rows.append(row)
    year_df = pd.DataFrame(year_rows)
    year_df.to_csv(OUT_DIR / "term_by_year.csv", index=False)
    print(year_df.round(4).to_string(index=False), flush=True)

    # ============================================================
    # 9. R_1h_d 的极端值
    # ============================================================
    print("\n=== 9. R_1h_d 极端值后表现 ===", flush=True)
    for label, q in [("low_5pct", 0.05), ("low_20pct", 0.20), ("mid", 0.50), ("high_20pct", 0.80), ("high_5pct", 0.95)]:
        if q == 0.5:
            lo = panel["R_1h_d"].quantile(0.45)
            hi = panel["R_1h_d"].quantile(0.55)
            sub = panel[(panel["R_1h_d"] >= lo) & (panel["R_1h_d"] <= hi)]
        else:
            thresh = panel["R_1h_d"].quantile(q)
            if q < 0.5:
                sub = panel[panel["R_1h_d"] <= thresh]
            else:
                sub = panel[panel["R_1h_d"] >= thresh]
        print(f"  {label:12s}: n={len(sub):5d}  fwd_ret_20={sub['fwd_ret_20'].mean():.4f}  "
              f"fwd_abs_20={sub['fwd_abs_ret_20'].mean():.4f}  win20={(sub['fwd_ret_20']>0).mean():.3f}", flush=True)

    # ============================================================
    # 图表
    # ============================================================
    print("\n生成图表...", flush=True)

    # Fig 1: 三个比值分布
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, col, ref in [
        (axes[0], "R_5_15", np.sqrt(3)),
        (axes[1], "R_15_1h", 2.0),
        (axes[2], "R_1h_d", np.sqrt(6)),
    ]:
        ax.hist(panel[col].dropna(), bins=80, alpha=0.7, color="#4C72B0", density=True)
        ax.axvline(ref, color="red", linestyle="--", linewidth=1, label=f"sqrt(ref)={ref:.2f}")
        ax.axvline(panel[col].median(), color="green", linestyle=":", linewidth=1.5, label=f"中位 {panel[col].median():.2f}")
        ax.set_title(col, fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
    plt.suptitle("跨期限 ATR 比值分布（时钟对齐）", fontsize=13)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig1_term_distribution.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 2: 期限曲线形态（各形态的三段均值）
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.array([0, 1, 2])
    labels = ["R_5_15", "R_15_1h", "R_1h_d"]
    states_order = curve_counts.index.tolist()
    cmap = plt.cm.tab10
    for i, state in enumerate(states_order):
        sub = panel[panel["term_curve_state"] == state]
        if len(sub) < 50:
            continue
        means = [sub["R_5_15"].mean(), sub["R_15_1h"].mean(), sub["R_1h_d"].mean()]
        ax.plot(x, means, marker="o", label=f"{state} (n={len(sub)})", color=cmap(i % 10), linewidth=1.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("R 均值")
    ax.set_title("期限曲线形态（各段均值）")
    ax.legend(fontsize=8, loc="best")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_curve_shapes.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 3: 期限结构与前向波动
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, h in [(axes[0], 20), (axes[1], 60)]:
        for col, color in [("R_5_15", "#4C72B0"), ("R_15_1h", "#DD8452"), ("R_1h_d", "#55A868")]:
            # 十分位分组
            panel[f"{col}_decile"] = pd.qcut(panel[col], 10, labels=False, duplicates="drop")
            grp = panel.groupby(f"{col}_decile")[f"fwd_abs_ret_{h}"].mean()
            ax.plot(grp.index, grp.values * 100, marker="o", label=col, color=color)
        ax.set_xlabel("十分位")
        ax.set_ylabel(f"前向 {h} 根 |r| (%)")
        ax.set_title(f"期限比值 vs 前向波动（h={h}）")
        ax.legend()
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_term_vs_vol.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 4: 相关性热力图
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr.values, cmap="RdBu_r", aspect="auto", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr_cols)))
    ax.set_yticks(range(len(corr_cols)))
    ax.set_xticklabels(corr_cols, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(corr_cols, fontsize=9)
    for i in range(len(corr_cols)):
        for j in range(len(corr_cols)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if abs(corr.iloc[i, j]) > 0.5 else "black")
    plt.colorbar(im, ax=ax, fraction=0.046)
    ax.set_title("期限结构因子相关性")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig4_correlation_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 5: 板块和年份的期限曲线
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for sec, sub in panel.groupby("sector"):
        means = [sub["R_5_15"].mean(), sub["R_15_1h"].mean(), sub["R_1h_d"].mean()]
        axes[0].plot(x, means, marker="o", label=sec, linewidth=1.5)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_title("板块期限曲线")
    axes[0].legend(fontsize=9)
    axes[0].grid(alpha=0.3)
    for yr, sub in panel.groupby("year"):
        means = [sub["R_5_15"].mean(), sub["R_15_1h"].mean(), sub["R_1h_d"].mean()]
        axes[1].plot(x, means, marker="o", label=str(int(yr)), linewidth=1.5)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_title("年份期限曲线")
    axes[1].legend(fontsize=9)
    axes[1].grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig5_sector_year_curves.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Summary
    summary = {
        "n_rows": int(len(panel)),
        "n_symbols": int(panel["symbol"].nunique()),
        "date_range": [str(panel["datetime"].min()), str(panel["datetime"].max())],
        "distribution": dist_df.to_dict("records"),
        "curve_states": curve_counts.to_dict(),
        "predictive_best_for_abs_vol": pred_df.loc[pred_df["corr_|r|"].abs().idxmax()].to_dict(),
        "theoretical": {"sqrt3": float(np.sqrt(3)), "sqrt4": 2.0, "sqrt6": float(np.sqrt(6))},
    }
    with open(OUT_DIR / "term_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n输出已保存到 {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
