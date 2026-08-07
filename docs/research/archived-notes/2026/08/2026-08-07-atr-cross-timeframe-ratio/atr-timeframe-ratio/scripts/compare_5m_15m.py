"""
ATR 跨周期比值研究 · 5m/1h vs 15m/1h 对比
==========================================

对比两个跨周期比值：
  R_15_1h  = ATR_1h(14) / ATR_15m(14)    （主口径，已有）
  R_5_1h   = ATR_1h(14) / ATR_5m(14)     （新口径）

时钟对齐对照：
  R_15_clock = ATR_1h(14) / ATR_15m(56)
  R_5_clock  = ATR_1h(14) / ATR_5m(168)

同周期短长比：
  S_H    = ATR_1h(14) / ATR_1h(50)
  S_15   = ATR_15m(56) / ATR_15m(200)
  S_5    = ATR_5m(168) / ATR_5m(600)

观察：
1. 两个比值的分布差异；
2. 相关性（15m 和 5m 口径是否包含相同信息）；
3. 四象限状态分布（用 5m 口径重新计算 state_S）；
4. 前向波动率/收益的预测力对比；
5. R_bar 极值后的行为差异；
6. 板块、年份差异。
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
OUT_DIR = SCRIPT_DIR / "outputs" / "compare_5m_15m"
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
    atr = tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    return atr


def load_tf(sym: str, tf: str) -> pd.DataFrame | None:
    f = CSV_DIR / f"{sym}.tqsdk.{tf}.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    return df


def compute_panel_for_symbol(sym: str) -> pd.DataFrame | None:
    """同时计算 15m/1h 和 5m/1h 两组因子，对齐到 1h。"""
    df_1h = load_tf(sym, "1h")
    df_15 = load_tf(sym, "15m")
    df_5 = load_tf(sym, "5m")
    if df_1h is None or df_15 is None or df_5 is None:
        return None
    if len(df_1h) < 100 or len(df_15) < 200 or len(df_5) < 400:
        return None

    # ATR
    df_1h["H"] = wilder_atr(df_1h, 14)
    df_1h["H_long"] = wilder_atr(df_1h, 50)
    df_15["L15"] = wilder_atr(df_15, 14)
    df_15["L15_clock"] = wilder_atr(df_15, 56)
    df_15["L15_long"] = wilder_atr(df_15, 200)
    df_5["L5"] = wilder_atr(df_5, 14)
    df_5["L5_clock"] = wilder_atr(df_5, 168)
    df_5["L5_long"] = wilder_atr(df_5, 600)

    # 以 1h 收盘时间为主，merge_asof 取同一时刻最近的 15m/5m ATR
    base = df_1h[["datetime", "close", "high", "low", "H", "H_long"]].dropna().copy()
    base = base.sort_values("datetime")

    for label, df_l in [("15", df_15), ("5", df_5)]:
        sub = df_l[["datetime", f"L{label}", f"L{label}_clock", f"L{label}_long"]].dropna().sort_values("datetime")
        base = pd.merge_asof(base, sub, on="datetime", direction="backward")

    # 跨周期比值
    base["R_15"] = base["H"] / base["L15"]
    base["R_15_clock"] = base["H"] / base["L15_clock"]
    base["R_5"] = base["H"] / base["L5"]
    base["R_5_clock"] = base["H"] / base["L5_clock"]

    # 同周期短长比
    base["S_H"] = base["H"] / base["H_long"]
    base["S_15"] = base["L15_clock"] / base["L15_long"]
    base["S_5"] = base["L5_clock"] / base["L5_long"]

    # 归一化波动率
    base["H_norm"] = base["H"] / base["close"]
    base["common_vol"] = np.sqrt(base["H_norm"] * (base["L15_clock"] / base["close"]))

    # 四象限（两套）
    for tf, S_L in [("15", "S_15"), ("5", "S_5")]:
        sh = base["S_H"] > 1
        sl = base[S_L] > 1
        base[f"state_{tf}"] = "co_compress"
        base.loc[sh & sl, f"state_{tf}"] = "co_expand"
        base.loc[sh & ~sl, f"state_{tf}"] = "H_only"
        base.loc[~sh & sl, f"state_{tf}"] = "L_only"

    # 前向收益和波动
    base["fwd_ret_5"] = base["close"].shift(-5) / base["close"] - 1
    base["fwd_ret_20"] = base["close"].shift(-20) / base["close"] - 1
    base["fwd_abs_ret_5"] = base["fwd_ret_5"].abs()
    base["fwd_abs_ret_20"] = base["fwd_ret_20"].abs()

    base["symbol"] = sym
    ex, code = parse_symbol(sym)
    sector_map = {"SHFE": "有色/能化", "DCE": "农产品/黑色", "CZCE": "农产品", "INE": "能化", "GFEX": "黑色/能化"}
    base["sector"] = sector_map.get(ex, "其他")
    base["date"] = base["datetime"].dt.date
    base["year"] = base["datetime"].dt.year

    return base.dropna(subset=["R_15", "R_5", "S_H", "S_15", "S_5"])


def main() -> None:
    print("加载并计算所有合约...", flush=True)
    panels = []
    for f in sorted(CSV_DIR.glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = compute_panel_for_symbol(sym)
        if p is not None:
            panels.append(p)
    panel = pd.concat(panels, ignore_index=True)
    print(f"合并面板: {len(panel)} 行, {panel['symbol'].nunique()} 合约", flush=True)

    # ============================================================
    # 1. 分布对比
    # ============================================================
    print("\n=== 1. 分布对比 ===", flush=True)
    dist_rows = []
    for col in ["R_15", "R_15_clock", "R_5", "R_5_clock"]:
        s = panel[col]
        dist_rows.append({
            "metric": col,
            "mean": float(s.mean()),
            "median": float(s.median()),
            "std": float(s.std()),
            "p05": float(s.quantile(0.05)),
            "p95": float(s.quantile(0.95)),
            "min": float(s.min()),
            "max": float(s.max()),
            "skew": float(s.skew()),
        })
    dist_df = pd.DataFrame(dist_rows)
    dist_df.to_csv(OUT_DIR / "distribution_compare.csv", index=False)
    print(dist_df.round(4).to_string(index=False), flush=True)

    # 理论缩放比
    print("\n理论参考：sqrt(4)=2.0, sqrt(12)=3.464", flush=True)

    # ============================================================
    # 2. 相关性
    # ============================================================
    print("\n=== 2. 相关性 ===", flush=True)
    corr_cols = ["R_15", "R_15_clock", "R_5", "R_5_clock", "S_H", "S_15", "S_5", "H_norm"]
    corr = panel[corr_cols].corr()
    corr.to_csv(OUT_DIR / "correlation_matrix.csv")
    print(corr.round(3).to_string(), flush=True)

    # R_15 vs R_5
    c = panel[["R_15", "R_5"]].corr().iloc[0, 1]
    print(f"\ncorr(R_15, R_5) = {c:.3f}", flush=True)

    # ============================================================
    # 3. 四象限分布对比
    # ============================================================
    print("\n=== 3. 四象限分布 ===", flush=True)
    state_compare = []
    for tf in ["15", "5"]:
        counts = panel[f"state_{tf}"].value_counts(normalize=True)
        for state in ["co_compress", "H_only", "L_only", "co_expand"]:
            state_compare.append({
                "timeframe": f"{tf}m",
                "state": state,
                "pct": float(counts.get(state, 0)),
                "count": int((panel[f"state_{tf}"] == state).sum()),
            })
    state_df = pd.DataFrame(state_compare)
    state_df.to_csv(OUT_DIR / "state_distribution_compare.csv", index=False)
    print(state_df.pivot(index="state", columns="timeframe", values="pct").round(4).to_string(), flush=True)

    # 一致性：两个口径在多少 bar 上分类一致
    agree = (panel["state_15"] == panel["state_5"]).mean()
    print(f"\n两套口径状态一致率: {agree:.1%}", flush=True)
    # 混淆矩阵
    conf = pd.crosstab(panel["state_15"], panel["state_5"], normalize="index")
    conf.to_csv(OUT_DIR / "state_confusion_15_vs_5.csv")
    print(conf.round(3).to_string(), flush=True)

    # ============================================================
    # 4. 前向波动/收益预测力
    # ============================================================
    print("\n=== 4. 前向波动率相关性 ===", flush=True)
    pred_rows = []
    for metric in ["R_15", "R_15_clock", "R_5", "R_5_clock", "S_H", "S_15", "S_5", "H_norm", "common_vol"]:
        for h in [5, 20]:
            col = f"fwd_abs_ret_{h}"
            mask = ~(panel[metric].isna() | panel[col].isna())
            c = float(np.corrcoef(panel.loc[mask, metric], panel.loc[mask, col])[0, 1])
            pred_rows.append({"metric": metric, "horizon": h, "corr_with_|fwd_ret|": c})
    pred_df = pd.DataFrame(pred_rows)
    pred_df.to_csv(OUT_DIR / "predictive_corr.csv", index=False)
    print(pred_df.pivot(index="metric", columns="horizon", values="corr_with_|fwd_ret|").round(4).to_string(), flush=True)

    # 前向方向收益（均值，按状态）
    print("\n=== 5. 各状态前向收益对比 ===", flush=True)
    ret_rows = []
    for tf in ["15", "5"]:
        for state in ["co_compress", "H_only", "L_only", "co_expand"]:
            sub = panel[panel[f"state_{tf}"] == state]
            ret_rows.append({
                "tf": f"{tf}m", "state": state,
                "n": len(sub),
                "fwd_ret_5": float(sub["fwd_ret_5"].mean()),
                "fwd_ret_20": float(sub["fwd_ret_20"].mean()),
                "fwd_abs_20": float(sub["fwd_abs_ret_20"].mean()),
                "win_rate_20": float((sub["fwd_ret_20"] > 0).mean()),
            })
    ret_df = pd.DataFrame(ret_rows)
    ret_df.to_csv(OUT_DIR / "state_fwd_returns.csv", index=False)
    print(ret_df.round(4).to_string(index=False), flush=True)

    # ============================================================
    # 6. 按板块
    # ============================================================
    print("\n=== 6. 板块平均 R 值 ===", flush=True)
    sector_rows = []
    for sec, sub in panel.groupby("sector"):
        row = {"sector": sec, "n": len(sub)}
        for col in ["R_15", "R_5", "R_15_clock", "R_5_clock"]:
            row[col] = float(sub[col].mean())
        sector_rows.append(row)
    sector_df = pd.DataFrame(sector_rows)
    sector_df.to_csv(OUT_DIR / "sector_compare.csv", index=False)
    print(sector_df.round(4).to_string(index=False), flush=True)

    # ============================================================
    # 7. R_5 的"额外信息"：R_5/R_15 比值
    # ============================================================
    print("\n=== 7. R_5/R_15 比值（短周期相对结构）===", flush=True)
    panel["R_ratio_5_15"] = panel["R_5"] / panel["R_15"]
    s = panel["R_ratio_5_15"]
    print(f"  mean={s.mean():.3f}, median={s.median():.3f}, std={s.std():.3f}")
    print(f"  p05={s.quantile(0.05):.3f}, p95={s.quantile(0.95):.3f}", flush=True)
    # 与前向波动/收益相关
    for h in [5, 20]:
        col = f"fwd_abs_ret_{h}"
        mask = ~(panel["R_ratio_5_15"].isna() | panel[col].isna())
        c = float(np.corrcoef(panel.loc[mask, "R_ratio_5_15"], panel.loc[mask, col])[0, 1])
        print(f"  corr(R_5/R_15, |fwd_ret_{h}|) = {c:.4f}", flush=True)

    # ============================================================
    # 图表
    # ============================================================
    print("\n生成图表...", flush=True)

    # Fig 1: 分布对比
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, cols, title in [
        (axes[0], ["R_15", "R_5"], "bar 对齐：14根 ATR"),
        (axes[1], ["R_15_clock", "R_5_clock"], "时钟对齐：相同物理窗口"),
    ]:
        for col in cols:
            ax.hist(panel[col].dropna(), bins=80, alpha=0.5, density=True, label=col)
        ax.axvline(2.0, color="gray", linestyle="--", linewidth=0.8)
        ax.axvline(3.464, color="red", linestyle=":", linewidth=0.8)
        ax.legend(fontsize=10)
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("R")
        ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig1_distribution_compare.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 2: R_15 vs R_5 散点
    fig, ax = plt.subplots(figsize=(8, 8))
    sample = panel.dropna(subset=["R_15", "R_5"]).sample(min(5000, len(panel)), random_state=42)
    ax.scatter(sample["R_15"], sample["R_5"], alpha=0.2, s=8, c=sample["H_norm"], cmap="viridis")
    lims = [min(sample["R_15"].min(), sample["R_5"].min()),
            max(sample["R_15"].max(), sample["R_5"].max())]
    ax.plot(lims, lims, "r--", linewidth=1, label="y=x")
    ax.set_xlabel("R_15 = ATR_1h/ATR_15m")
    ax.set_ylabel("R_5 = ATR_1h/ATR_5m")
    ax.set_title(f"R_15 vs R_5 (corr={c:.3f})")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_r15_vs_r5_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 3: 四象限分布对比
    fig, ax = plt.subplots(figsize=(10, 6))
    states = ["co_compress", "H_only", "L_only", "co_expand"]
    x = np.arange(len(states))
    w = 0.35
    p15 = [state_df[(state_df.timeframe == "15m") & (state_df.state == s)]["pct"].iloc[0] for s in states]
    p5 = [state_df[(state_df.timeframe == "5m") & (state_df.state == s)]["pct"].iloc[0] for s in states]
    ax.bar(x - w/2, p15, w, label="15m 口径", color="#4C72B0")
    ax.bar(x + w/2, p5, w, label="5m 口径", color="#DD8452")
    ax.set_xticks(x)
    ax.set_xticklabels(states, rotation=15)
    ax.set_ylabel("占比")
    ax.set_title("四象限分布：15m vs 5m 口径")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_state_compare.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 4: 各状态前向 |r|
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(states))
    v15 = [ret_df[(ret_df.tf == "15m") & (ret_df.state == s)]["fwd_abs_20"].iloc[0] for s in states]
    v5 = [ret_df[(ret_df.tf == "5m") & (ret_df.state == s)]["fwd_abs_20"].iloc[0] for s in states]
    ax.bar(x - w/2, np.array(v15) * 100, w, label="15m 口径", color="#4C72B0")
    ax.bar(x + w/2, np.array(v5) * 100, w, label="5m 口径", color="#DD8452")
    ax.set_xticks(x)
    ax.set_xticklabels(states, rotation=15)
    ax.set_ylabel("前向 20 根 |r| (%)")
    ax.set_title("各状态前向波动率对比")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig4_fwd_vol_compare.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Summary
    summary = {
        "n_rows": int(len(panel)),
        "n_symbols": int(panel["symbol"].nunique()),
        "date_range": [str(panel["datetime"].min()), str(panel["datetime"].max())],
        "distribution": dist_df.to_dict("records"),
        "corr_R15_R5": float(panel[["R_15", "R_5"]].corr().iloc[0, 1]),
        "state_agreement": float(agree),
        "r_ratio_5_15": {
            "mean": float(panel["R_ratio_5_15"].mean()),
            "median": float(panel["R_ratio_5_15"].median()),
        },
    }
    with open(OUT_DIR / "compare_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n输出已保存到 {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
