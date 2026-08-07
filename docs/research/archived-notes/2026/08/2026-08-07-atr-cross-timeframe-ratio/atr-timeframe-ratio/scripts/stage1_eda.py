"""
ATR 跨周期比值研究 · 第一轮 EDA
================================

目标：
1. 计算 R_bar、R_clock、S_H、S_L 及 A–D、F 组因子；
2. 描述 R_bar 的分布形态（按合约、全样本）；
3. 描述 S_H / S_L 四象限样本占比；
4. 计算因子间相关矩阵；
5. 分层抽样查看极端分位的 R_bar 来源。

输出：
- outputs/eda_summary.json
- outputs/eda_correlation.csv
- outputs/eda_stateS_counts.csv
- outputs/eda_R_bar_by_symbol.csv
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# ---------- 路径 ----------
ROOT = Path(__file__).resolve().parents[5]
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
OUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ATR 周期
H_SHORT = 14  # 1h 短窗
H_LONG = 50  # 1h 长窗
L_SHORT = 56  # 15m 短窗（≈14h，时钟对齐）
L_LONG = 200  # 15m 长窗（≈50h，时钟对齐）

# 滚动分位窗口
ROLL_H = 100  # 1h
ROLL_L = 400  # 15m


def wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Wilder ATR。"""
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def load_symbol(sym: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载 15m 和 1h CSV，按 datetime 索引。"""
    f15 = CSV_DIR / f"{sym}.tqsdk.15m.csv"
    f1h = CSV_DIR / f"{sym}.tqsdk.1h.csv"
    df15 = pd.read_csv(f15, parse_dates=["datetime"]).set_index("datetime")
    df1h = pd.read_csv(f1h, parse_dates=["datetime"]).set_index("datetime")
    return df15, df1h


def compute_factors(df15: pd.DataFrame, df1h: pd.DataFrame) -> pd.DataFrame:
    """在 1h 主索引上计算全部因子。"""
    out = pd.DataFrame(index=df1h.index)
    out["close"] = df1h["close"]

    # ---- ATR ----
    out["H"] = wilder_atr(df1h["high"], df1h["low"], df1h["close"], H_SHORT)
    out["H_long"] = wilder_atr(df1h["high"], df1h["low"], df1h["close"], H_LONG)
    # 15m ATR 序列对齐到 1h 时间戳（取同时刻已完成的 15m ATR）
    L_series = wilder_atr(df15["high"], df15["low"], df15["close"], L_SHORT)
    L_long_series = wilder_atr(df15["high"], df15["low"], df15["close"], L_LONG)
    # reindex 到 1h：用 merge_asof 保证只取当时已知的 15m 值
    l_df = pd.DataFrame({"L": L_series, "L_long": L_long_series, "time": df15.index})
    h_df = pd.DataFrame({"time": df1h.index})
    merged = pd.merge_asof(h_df, l_df, on="time", direction="backward")
    out["L"] = merged["L"].values
    out["L_long"] = merged["L_long"].values

    # ---- A. 跨周期比值 ----
    out["R_bar"] = out["H"] / out["L"]
    out["log_R_bar"] = np.log(out["R_bar"])
    out["R_clock"] = out["H"] / out["L_long"]  # 时钟对齐：14h / 50h
    out["log_R_clock"] = np.log(out["R_clock"])
    out["R_bar_pct_100"] = out["R_bar"].rolling(ROLL_H, min_periods=50).rank(pct=True)
    out["R_bar_z_100"] = (
        out["R_bar"] - out["R_bar"].rolling(ROLL_H, min_periods=50).mean()
    ) / out["R_bar"].rolling(ROLL_H, min_periods=50).std()
    out["R_bar_excess"] = out["log_R_bar"] - out["log_R_bar"].rolling(ROLL_H, min_periods=50).median()
    out["R_clock_excess"] = out["log_R_clock"] - out["log_R_clock"].rolling(ROLL_H, min_periods=50).median()

    # ---- B. 单周期 ATR 水平 ----
    out["H_pct_100"] = out["H"].rolling(ROLL_H, min_periods=50).rank(pct=True)
    out["H_z_100"] = (
        out["H"] - out["H"].rolling(ROLL_H, min_periods=50).mean()
    ) / out["H"].rolling(ROLL_H, min_periods=50).std()
    out["H_norm"] = out["H"] / out["close"]
    # L 分位在 15m 上滚动，再对齐到 1h
    L_pct_15 = L_series.rolling(ROLL_L, min_periods=100).rank(pct=True)
    L_z_15 = (L_series - L_series.rolling(ROLL_L, min_periods=100).mean()) / L_series.rolling(
        ROLL_L, min_periods=100
    ).std()
    out["L_pct_400"] = L_pct_15.reindex(out.index, method="ffill")
    out["L_z_400"] = L_z_15.reindex(out.index, method="ffill")
    out["L_norm"] = out["L"] / out["close"]
    out["common_vol"] = np.sqrt(out["H_norm"] * out["L_norm"])

    # ---- C. 同周期短长 ATR 比（主因子） ----
    out["S_H"] = out["H"] / out["H_long"]
    out["S_L"] = out["L"] / out["L_long"]
    S_H_pct_15 = None  # S_H 在 1h 上，直接滚动
    out["S_H_pct"] = out["S_H"].rolling(ROLL_H, min_periods=50).rank(pct=True)
    S_L_pct_15 = (out["L"] / out["L_long"]).rolling(ROLL_H, min_periods=50).rank(pct=True)
    out["S_L_pct"] = S_L_pct_15
    out["S_diff"] = out["S_H_pct"] - out["S_L_pct"]
    out["S_ratio"] = np.log(out["S_H"] / out["S_L"])
    # state_S 四象限
    out["state_S"] = "other"
    out.loc[(out["S_H"] > 1) & (out["S_L"] > 1), "state_S"] = "co_expand"
    out.loc[(out["S_H"] > 1) & (out["S_L"] <= 1), "state_S"] = "H_only"
    out.loc[(out["S_H"] <= 1) & (out["S_L"] > 1), "state_S"] = "L_only"
    out.loc[(out["S_H"] <= 1) & (out["S_L"] <= 1), "state_S"] = "co_compress"

    # ---- D. 累计变化 ----
    for k in (5, 20):
        out[f"dLogH_{k}"] = np.log(out["H"] / out["H"].shift(k))
        out[f"dLogL_{k}"] = np.log(out["L"] / out["L"].shift(k))
        out[f"dLogR_{k}"] = out[f"dLogH_{k}"] - out[f"dLogL_{k}"]

    # ---- F. 跨周期比值持续性 ----
    out["R_rank_chg_5"] = out["R_bar_pct_100"] - out["R_bar_pct_100"].shift(5)
    out["R_vs_MA20"] = out["R_bar"] / out["R_bar"].rolling(20, min_periods=10).mean() - 1
    # R_persistence：当前处于高/低三分位的连续 bar 数
    hi = out["R_bar_pct_100"] > 2 / 3
    lo = out["R_bar_pct_100"] < 1 / 3

    def _persist(flag: pd.Series) -> pd.Series:
        grp = (flag != flag.shift()).cumsum()
        return flag.groupby(grp).cumsum().astype(float)

    out["R_persistence"] = 0.0
    out.loc[hi, "R_persistence"] = _persist(hi)[hi]
    out.loc[lo, "R_persistence"] = -_persist(lo)[lo]

    return out


def main() -> None:
    # 找到同时有 15m 和 1h 的合约
    syms_15 = {
        p.name.split(".tqsdk")[0]
        for p in CSV_DIR.glob("*.tqsdk.15m.csv")
    }
    syms_1h = {
        p.name.split(".tqsdk")[0]
        for p in CSV_DIR.glob("*.tqsdk.1h.csv")
    }
    syms = sorted(syms_15 & syms_1h)
    print(f"找到 {len(syms)} 个同时有 15m/1h 的合约")

    all_frames: dict[str, pd.DataFrame] = {}
    for sym in syms:
        df15, df1h = load_symbol(sym)
        fac = compute_factors(df15, df1h)
        fac["symbol"] = sym
        all_frames[sym] = fac

    # 合并（每合约独立计算，合起来只做整体描述）
    panel = pd.concat(all_frames.values(), ignore_index=True)
    panel_valid = panel.dropna(
        subset=[
            "R_bar", "R_clock", "H", "L", "S_H", "S_L",
            "H_pct_100", "L_pct_400", "R_bar_pct_100",
        ]
    ).copy()

    print(f"有效样本: {len(panel_valid)} (总 {len(panel)})")

    # ---------- 1. R_bar 分布描述 ----------
    rbar = panel_valid["R_bar"]
    log_rbar = panel_valid["log_R_bar"]
    rclock = panel_valid["R_clock"]

    dist_summary = {
        "n": int(len(panel_valid)),
        "R_bar": {
            "mean": float(rbar.mean()),
            "std": float(rbar.std()),
            "min": float(rbar.min()),
            "p05": float(rbar.quantile(0.05)),
            "p25": float(rbar.quantile(0.25)),
            "median": float(rbar.median()),
            "p75": float(rbar.quantile(0.75)),
            "p95": float(rbar.quantile(0.95)),
            "max": float(rbar.max()),
            "skew": float(rbar.skew()),
            "kurtosis": float(rbar.kurtosis()),
        },
        "log_R_bar": {
            "mean": float(log_rbar.mean()),
            "std": float(log_rbar.std()),
            "median": float(log_rbar.median()),
            "skew": float(log_rbar.skew()),
            "kurtosis": float(log_rbar.kurtosis()),
        },
        "R_clock": {
            "mean": float(rclock.mean()),
            "median": float(rclock.median()),
            "std": float(rclock.std()),
            "p05": float(rclock.quantile(0.05)),
            "p95": float(rclock.quantile(0.95)),
        },
        "sqrt4_reference": float(np.sqrt(4)),
    }
    print("\n=== R_bar 分布 ===")
    print(json.dumps(dist_summary["R_bar"], indent=2, ensure_ascii=False))
    print(f"log_R_bar: mean={dist_summary['log_R_bar']['mean']:.4f} std={dist_summary['log_R_bar']['std']:.4f}")
    print(f"R_clock: median={dist_summary['R_clock']['median']:.4f} (sqrt(4)={np.sqrt(4):.4f})")

    # ---------- 2. R_bar 按合约 ----------
    by_sym = (
        panel_valid.groupby("symbol")["R_bar"]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .round(4)
        .sort_values("mean", ascending=False)
    )
    by_sym.to_csv(OUT_DIR / "eda_R_bar_by_symbol.csv")
    print(f"\n=== R_bar 按合约（前 5 高 / 前 5 低）===")
    print(by_sym.head(5))
    print(by_sym.tail(5))

    # ---------- 3. S_H / S_L 四象限 ----------
    state_counts = (
        panel_valid["state_S"].value_counts(normalize=True).rename("frac").to_frame()
    )
    state_counts["count"] = panel_valid["state_S"].value_counts()
    state_counts.to_csv(OUT_DIR / "eda_stateS_counts.csv")
    print("\n=== state_S 四象限占比 ===")
    print(state_counts.round(4))

    # ---------- 4. 因子相关性 ----------
    factor_cols = [
        "R_bar", "log_R_bar", "R_clock",
        "H", "L", "H_pct_100", "L_pct_400", "H_norm", "L_norm", "common_vol",
        "S_H", "S_L", "S_H_pct", "S_L_pct", "S_diff", "S_ratio",
        "dLogH_5", "dLogL_5", "dLogR_5",
        "dLogH_20", "dLogL_20", "dLogR_20",
        "R_rank_chg_5", "R_vs_MA20",
    ]
    corr = panel_valid[factor_cols].corr()
    corr.to_csv(OUT_DIR / "eda_correlation.csv")
    # 只打印与 R_bar 相关系数 top
    print("\n=== 与 R_bar 的相关系数（绝对值 top 15）===")
    rbar_corr = corr["R_bar"].drop("R_bar").sort_values(key=lambda s: s.abs(), ascending=False)
    print(rbar_corr.head(15).round(3))

    # S_H / S_L 与 H/L 水平的相关性
    print("\n=== S_H 与 H_pct 相关、S_L 与 L_pct 相关 ===")
    print(f"S_H vs H_pct_100: {panel_valid['S_H'].corr(panel_valid['H_pct_100']):.3f}")
    print(f"S_L vs L_pct_400: {panel_valid['S_L'].corr(panel_valid['L_pct_400']):.3f}")
    print(f"S_H vs H_norm: {panel_valid['S_H'].corr(panel_valid['H_norm']):.3f}")
    print(f"S_L vs L_norm: {panel_valid['S_L'].corr(panel_valid['L_norm']):.3f}")

    # ---------- 5. 极端分位抽样：R_bar 高/低时 S_H 和 S_L 的分布 ----------
    print("\n=== R_bar 极端分位的 S_H / S_L 中位数 ===")
    for q_lo, q_hi, label in [
        (0.0, 0.05, "R_bar 最低 5%"),
        (0.05, 0.10, "R_bar 5-10%"),
        (0.45, 0.55, "R_bar 中位附近"),
        (0.90, 0.95, "R_bar 90-95%"),
        (0.95, 1.0, "R_bar 最高 5%"),
    ]:
        lo_v = panel_valid["R_bar"].quantile(q_lo)
        hi_v = panel_valid["R_bar"].quantile(q_hi)
        sub = panel_valid[(panel_valid["R_bar"] >= lo_v) & (panel_valid["R_bar"] <= hi_v)]
        print(
            f"{label:20s} n={len(sub):6d}  R_bar={sub['R_bar'].median():.3f}  "
            f"S_H={sub['S_H'].median():.3f}  S_L={sub['S_L'].median():.3f}  "
            f"H_pct={sub['H_pct_100'].median():.3f}  L_pct={sub['L_pct_400'].median():.3f}"
        )

    # ---------- 6. R_bar × state_S 二维表 ----------
    print("\n=== R_bar 三分位 × state_S 占比 ===")
    panel_valid["R_bar_tercile"] = pd.qcut(panel_valid["R_bar"], 3, labels=["low", "mid", "high"])
    ct = pd.crosstab(panel_valid["R_bar_tercile"], panel_valid["state_S"], normalize="index")
    print(ct.round(3))

    # ---------- 保存 JSON ----------
    dist_summary["n_symbols"] = len(syms)
    dist_summary["symbols"] = syms
    with open(OUT_DIR / "eda_summary.json", "w", encoding="utf-8") as f:
        json.dump(dist_summary, f, indent=2, ensure_ascii=False)

    print(f"\n输出已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
