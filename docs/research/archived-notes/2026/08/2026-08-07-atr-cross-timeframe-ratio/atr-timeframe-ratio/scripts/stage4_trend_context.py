"""
Stage 4: H_only confirmed 在趋势位置是否更有效
================================================

基于 Stage 3 面板，补充以下分析：
1. MADEV_20 / MADEV_60 × H_only_outcome 交叉；
2. ret_20 / ret_60 动量 × H_only_outcome 交叉；
3. trend_strength × H_only_outcome；
4. 趋势方向与 confirmed 后收益方向是否一致；
5. 按板块/年份拆分稳定性。

输出：outputs/stage4/
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
PANEL_PATH = Path(__file__).resolve().parents[1] / "outputs" / "stage3" / "stage3_panel.parquet"
OUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "stage4"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_N = 30
BOOT_N = 1000
SEED = 42


def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray, n_boot: int = BOOT_N) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    values = np.asarray(values, dtype=float)
    clusters = np.asarray(clusters)
    mask = ~np.isnan(values)
    values, clusters = values[mask], clusters[mask]
    if len(values) == 0:
        return np.nan, np.nan
    uniq = np.unique(clusters)
    idx_map = {c: np.where(clusters == c)[0] for c in uniq}
    stats = np.empty(n_boot)
    for i in range(n_boot):
        sampled = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_map[c] for c in sampled])
        stats[i] = values[idx].mean()
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def summarize(sub: pd.DataFrame, metric: str) -> dict:
    vals = sub[metric].dropna().values
    if len(vals) < 1:
        return {"n": 0, "mean": np.nan, "median": np.nan, "ci_lo": np.nan, "ci_hi": np.nan}
    ci_lo, ci_hi = (np.nan, np.nan)
    if len(vals) >= MIN_N:
        ci_lo, ci_hi = cluster_bootstrap_ci(vals, sub["date"].values)
    return {
        "n": int(len(vals)),
        "mean": float(np.nanmean(vals)),
        "median": float(np.nanmedian(vals)),
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
    }


def cross_tab(
    h_only: pd.DataFrame,
    group_col: str,
    label_prefix: str = "",
) -> pd.DataFrame:
    """对 H_only 子样本按 group_col × H_only_outcome 做汇总。"""
    rows = []
    for g_val, g_sub in h_only.groupby(group_col, observed=True):
        for outcome in ("confirmed", "failed"):
            s = g_sub[g_sub["H_only_outcome"] == outcome]
            for metric in ("fwd_ret_5", "fwd_ret_20", "fwd_abs_ret_20", "fwd_max_ret_20", "fwd_min_ret_20"):
                r = summarize(s, metric)
                r.update({
                    "group_var": group_col,
                    "group": str(g_val),
                    "outcome": outcome,
                    "metric": metric,
                    "label": f"{label_prefix}{group_col}={g_val}",
                })
                rows.append(r)
    return pd.DataFrame(rows)


def direction_alignment(h_only: pd.DataFrame) -> pd.DataFrame:
    """检验 confirmed 后 fwd_ret_20 方向是否与前置趋势方向一致。"""
    rows = []
    h = h_only.copy()
    h["trend_dir"] = np.sign(h["MADEV_60"])
    h["fwd_dir"] = np.sign(h["fwd_ret_20"])
    for outcome in ("confirmed", "failed"):
        s = h[h["H_only_outcome"] == outcome]
        aligned = (s["trend_dir"] == s["fwd_dir"]) & (s["trend_dir"] != 0)
        n = len(s)
        n_aligned = int(aligned.sum())
        # 分组别
        for trend_dir, label in [(1, "uptrend"), (-1, "downtrend"), (0, "flat")]:
            ss = s[s["trend_dir"] == trend_dir]
            if len(ss) < MIN_N:
                continue
            for metric in ("fwd_ret_20", "fwd_abs_ret_20"):
                r = summarize(ss, metric)
                r.update({
                    "outcome": outcome,
                    "trend_dir": label,
                    "n_trend_dir": len(ss),
                    "metric": metric,
                })
                rows.append(r)
        # 方向一致性
        rows.append({
            "outcome": outcome,
            "trend_dir": "alignment_rate",
            "n_trend_dir": n,
            "metric": "fwd_ret_20",
            "n": n,
            "mean": n_aligned / n if n else np.nan,
            "median": np.nan,
            "ci_lo": np.nan,
            "ci_hi": np.nan,
        })
    return pd.DataFrame(rows)


def main() -> None:
    panel = pd.read_parquet(PANEL_PATH)
    h_only = panel[panel["state_S"] == "H_only"].copy()
    print(f"H_only 样本: {len(h_only)}")
    print(f"  confirmed: {(h_only['H_only_outcome']=='confirmed').sum()}")
    print(f"  failed:    {(h_only['H_only_outcome']=='failed').sum()}")

    # 先看 confirmed/failed 在不同趋势位置的占比
    print("\n=== confirmed 率按 trend_group ===")
    ct = h_only.groupby("trend_group", observed=True).agg(
        n=("H_only_outcome", "size"),
        confirm_rate=("fwd_S_L_up_5", "mean"),
    )
    print(ct.round(4))
    ct.to_csv(OUT_DIR / "stage4_confirm_rate_by_trend_group.csv")

    # 1. MADEV 三分位 × outcome
    h_only["MADEV_20_q"] = pd.qcut(h_only["MADEV_20"].rank(method="first"), 3, labels=["low", "mid", "high"])
    h_only["MADEV_60_q"] = pd.qcut(h_only["MADEV_60"].rank(method="first"), 3, labels=["low", "mid", "high"])
    h_only["ret_20_q"] = pd.qcut(h_only["ret_20"].rank(method="first"), 3, labels=["low", "mid", "high"])
    h_only["ret_60_q"] = pd.qcut(h_only["ret_60"].rank(method="first"), 3, labels=["low", "mid", "high"])
    h_only["trend_strength_q"] = pd.qcut(
        h_only["trend_strength"].rank(method="first"), 3, labels=["weak", "mid", "strong"]
    )

    all_rows = []
    for col in ("MADEV_20_q", "MADEV_60_q", "ret_20_q", "ret_60_q", "trend_strength_q"):
        all_rows.append(cross_tab(h_only, col))

    # MADEV 方向三分位：用 sign × |MADEV_60| 三分位
    h_only["MADEV_60_dir"] = np.where(
        h_only["MADEV_60"] > h_only["MADEV_60"].quantile(0.66), "up_high",
        np.where(h_only["MADEV_60"] < h_only["MADEV_60"].quantile(0.33), "down_low", "flat_mid"),
    )
    all_rows.append(cross_tab(h_only, "MADEV_60_dir"))

    result = pd.concat(all_rows, ignore_index=True)
    result.to_csv(OUT_DIR / "stage4_trend_cross.csv", index=False)

    # 2. 方向一致性
    dir_df = direction_alignment(h_only)
    dir_df.to_csv(OUT_DIR / "stage4_direction_alignment.csv", index=False)

    # 3. 关键 pivot：MADEV_60_q × outcome → fwd_ret_20
    print("\n=== MADEV_60 三分位 × outcome, fwd_ret_20 ===")
    p1 = result[
        (result["group_var"] == "MADEV_60_q") & (result["metric"] == "fwd_ret_20")
    ].pivot(index="group", columns="outcome", values=["mean", "n", "ci_lo", "ci_hi"])
    print(p1.round(4))

    print("\n=== trend_strength 三分位 × outcome, fwd_ret_20 ===")
    p2 = result[
        (result["group_var"] == "trend_strength_q") & (result["metric"] == "fwd_ret_20")
    ].pivot(index="group", columns="outcome", values=["mean", "n", "ci_lo", "ci_hi"])
    print(p2.round(4))

    print("\n=== MADEV_60 方向 × outcome, fwd_ret_20 ===")
    p3 = result[
        (result["group_var"] == "MADEV_60_dir") & (result["metric"] == "fwd_ret_20")
    ].pivot(index="group", columns="outcome", values=["mean", "n", "ci_lo", "ci_hi"])
    print(p3.round(4))

    print("\n=== 方向一致性 ===")
    print(dir_df[dir_df["trend_dir"].isin(["uptrend", "downtrend", "alignment_rate"])].round(4))

    # 4. confirmed 样本内：ret_20 方向 vs MADEV_60 方向
    conf = h_only[h_only["H_only_outcome"] == "confirmed"].copy()
    print(f"\n=== confirmed 子样本: 前置趋势方向 vs fwd_ret_20 ===")
    conf["m60_sign"] = np.sign(conf["MADEV_60"])
    for m60, label in [(1, "MADEV60>0"), (-1, "MADEV60<0"), (0, "MADEV60≈0")]:
        s = conf[conf["m60_sign"] == m60]
        if len(s) < MIN_N:
            continue
        m = summarize(s, "fwd_ret_20")
        print(f"  {label:12s} n={m['n']:4d}  fwd_ret_20={m['mean']:.4f}  CI=[{m['ci_lo']:.4f},{m['ci_hi']:.4f}]")

    # 5. confirmed + 强趋势组合（H_only confirmed 且 trend_strength high）
    print("\n=== confirmed × trend_strength=strong ===")
    for strength, label in [("weak", "weak"), ("mid", "mid"), ("strong", "STRONG")]:
        s = conf[conf["trend_strength_q"] == strength]
        if len(s) < MIN_N:
            print(f"  {label:8s} n={len(s)} 样本不足")
            continue
        m20 = summarize(s, "fwd_ret_20")
        m_abs = summarize(s, "fwd_abs_ret_20")
        m_max = summarize(s, "fwd_max_ret_20")
        m_min = summarize(s, "fwd_min_ret_20")
        print(
            f"  {label:8s} n={m20['n']:4d}  ret20={m20['mean']:.4f} [{m20['ci_lo']:.4f},{m20['ci_hi']:.4f}]  "
            f"|r|20={m_abs['mean']:.4f}  max={m_max['mean']:.4f}  min={m_min['mean']:.4f}"
        )

    # 6. 按板块/年份稳定性（confirmed 内）
    print("\n=== confirmed 按板块, fwd_ret_20 ===")
    sector_rows = []
    for sec, s in conf.groupby("sector"):
        if len(s) < MIN_N:
            continue
        m = summarize(s, "fwd_ret_20")
        m_abs = summarize(s, "fwd_abs_ret_20")
        sector_rows.append({"sector": sec, "n": m["n"], "ret20": m["mean"], "ret20_ci_lo": m["ci_lo"],
                            "ret20_ci_hi": m["ci_hi"], "abs_ret20": m_abs["mean"]})
    sec_df = pd.DataFrame(sector_rows)
    sec_df.to_csv(OUT_DIR / "stage4_confirmed_by_sector.csv", index=False)
    print(sec_df.round(4))

    print("\n=== confirmed 按年份, fwd_ret_20 ===")
    year_rows = []
    for yr, s in conf.groupby("year"):
        if len(s) < MIN_N:
            continue
        m = summarize(s, "fwd_ret_20")
        m_abs = summarize(s, "fwd_abs_ret_20")
        year_rows.append({"year": int(yr), "n": m["n"], "ret20": m["mean"],
                          "ret20_ci_lo": m["ci_lo"], "ret20_ci_hi": m["ci_hi"],
                          "abs_ret20": m_abs["mean"]})
    yr_df = pd.DataFrame(year_rows)
    yr_df.to_csv(OUT_DIR / "stage4_confirmed_by_year.csv", index=False)
    print(yr_df.round(4))

    # 7. 保存 summary
    summary = {
        "n_H_only": int(len(h_only)),
        "n_confirmed": int((h_only["H_only_outcome"] == "confirmed").sum()),
        "n_failed": int((h_only["H_only_outcome"] == "failed").sum()),
        "confirm_rate_by_trend_group": ct.reset_index().to_dict(orient="records"),
    }
    with open(OUT_DIR / "stage4_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n输出已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
