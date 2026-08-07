"""
ATR 跨周期比值研究 · Stage 7: state_duration 拆分验证
=====================================================

按机制备忘 mechanism-oversold-vs-trend.md 第 8.1 节：
- 用 state_duration 把 H_only 分成短脉冲（1–2 根）vs 持续（5+ 根）；
- 对比两类的前向路径、MADEV 位置、量/OI 模式、收益曲线；
- 用 5 根后 S_H 是否维持 >1 做事后机制分类。

输入：outputs/stage6/stage6_expanded_panel.parquet
输出：outputs/stage7/
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[5]
SCRIPT_DIR = Path(__file__).resolve().parents[1]
PANEL_PATH = SCRIPT_DIR / "outputs" / "stage6" / "stage6_expanded_panel.parquet"
OUT_DIR = SCRIPT_DIR / "outputs" / "stage7"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BOOT_N = 1000
BOOT_SEED = 42
MIN_N = 10


def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(BOOT_SEED)
    mask = ~np.isnan(values)
    values, clusters = values[mask], clusters[mask]
    if len(values) == 0:
        return np.nan, np.nan
    uniq = np.unique(clusters)
    idx_map = {c: np.where(clusters == c)[0] for c in uniq}
    stats = np.empty(BOOT_N)
    for i in range(BOOT_N):
        sampled = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_map[c] for c in sampled])
        stats[i] = values[idx].mean()
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def summarize(sub: pd.DataFrame, metric: str = "fwd_ret_20") -> dict:
    vals = sub[metric].dropna().values
    if len(vals) == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "win_rate": np.nan}
    ci_lo, ci_hi = (np.nan, np.nan)
    if len(vals) >= MIN_N:
        ci_lo, ci_hi = cluster_bootstrap_ci(vals, sub["date"].values)
    return {
        "n": int(len(vals)),
        "mean": float(np.mean(vals)),
        "median": float(np.median(vals)),
        "abs_mean": float(np.mean(np.abs(vals))),
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "win_rate": float((vals > 0).mean()),
    }


def main() -> None:
    panel = pd.read_parquet(PANEL_PATH)
    print(f"面板: {len(panel)} 行, {panel['symbol'].nunique()} 合约")

    h_only = panel[panel["state_S"] == "H_only"].copy()
    # stage6 面板没有 state_duration，按 episode 内累计行数计算
    h_only = h_only.sort_values(["symbol", "datetime"])
    h_only["state_duration"] = h_only.groupby("episode_id").cumcount() + 1
    print(f"H_only: {len(h_only)} 行")

    # episode_id 已在 stage6 面板中
    n_episodes = h_only["episode_id"].nunique()
    print(f"H_only episode 数: {n_episodes}")

    # ============================================================
    # 1. 每段 H_only 的持续长度分布
    # ============================================================
    episode_dur = h_only.groupby("episode_id").agg(
        duration=("state_duration", "max"),
        symbol=("symbol", "first"),
        date=("date", "first"),
        sector=("sector", "first"),
        MADEV_60=("MADEV_60", "first"),
        trend_strength=("trend_strength", "first"),
        S_H_start=("S_H", "first"),
        S_H_peak=("S_H", "max"),
        fwd_ret_20_first=("fwd_ret_20", "first"),
        outcome=("H_only_outcome", "first"),
        vol_ratio=("vol_ratio", "first"),
    ).reset_index()

    print("\n=== H_only episode 持续长度分布 ===")
    print(episode_dur["duration"].describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.95]))

    # 分三组
    episode_dur["dur_group"] = pd.cut(
        episode_dur["duration"],
        bins=[0, 2, 5, 1000],
        labels=["short_1_2", "mid_3_5", "long_6_plus"],
    )
    dur_counts = episode_dur["dur_group"].value_counts().sort_index()
    print("\n持续长度分组：")
    print(dur_counts)

    # ============================================================
    # 2. 按持续长度分组对比
    # ============================================================
    rows = []
    for grp, sub in episode_dur.groupby("dur_group", observed=True):
        r = {"group": grp, "n_episodes": len(sub)}
        # 确认率（用 episode first outcome）
        r["confirm_rate"] = float((sub["outcome"] == "confirmed").mean())
        r["fail_rate"] = float((sub["outcome"] == "failed").mean())
        # 首根收益
        s = summarize(sub, "fwd_ret_20_first")
        r["ret20_mean"] = s["mean"]
        r["ret20_median"] = s["median"]
        r["ret20_abs"] = s["abs_mean"]
        r["ret20_ci_lo"] = s["ci_lo"]
        r["ret20_ci_hi"] = s["ci_hi"]
        r["win_rate"] = s["win_rate"]
        # 前置趋势
        r["madev60_mean"] = float(sub["MADEV_60"].mean())
        r["madev60_lt0_frac"] = float((sub["MADEV_60"] < 0).mean())
        r["trend_strength_mean"] = float(sub["trend_strength"].mean())
        # S_H 峰值
        r["SH_peak_mean"] = float(sub["S_H_peak"].mean())
        rows.append(r)

    dur_df = pd.DataFrame(rows)
    dur_df.to_csv(OUT_DIR / "stage7_by_duration.csv", index=False)
    print("\n=== 按持续长度分组 ===")
    print(dur_df.round(4).to_string(index=False))

    # ============================================================
    # 3. confirmed 按持续长度分组
    # ============================================================
    conf_episodes = episode_dur[episode_dur["outcome"] == "confirmed"]
    fail_episodes = episode_dur[episode_dur["outcome"] == "failed"]

    print("\n=== confirmed episode 按持续长度 ===")
    conf_by_dur = []
    for grp, sub in conf_episodes.groupby("dur_group", observed=True):
        s = summarize(sub, "fwd_ret_20_first")
        conf_by_dur.append({
            "dur_group": grp, "n": s["n"], "ret20": s["mean"],
            "median": s["median"], "ci_lo": s["ci_lo"], "ci_hi": s["ci_hi"],
            "win_rate": s["win_rate"],
            "madev60_mean": float(sub["MADEV_60"].mean()),
            "madev60_lt0_frac": float((sub["MADEV_60"] < 0).mean()),
        })
    conf_dur_df = pd.DataFrame(conf_by_dur)
    conf_dur_df.to_csv(OUT_DIR / "stage7_confirmed_by_duration.csv", index=False)
    print(conf_dur_df.round(4).to_string(index=False))

    # ============================================================
    # 4. 前向路径：短 vs 长 H_only 后 1/3/5/10/20 根状态
    # ============================================================
    # 在全 panel 中标记 episode 持续长度组
    panel = panel.merge(
        episode_dur[["episode_id", "dur_group"]], on="episode_id", how="left"
    )

    # 取每段 H_only 的首根（episode first bar），在全 panel 上看前向状态
    # panel 已经 merge 了 dur_group，直接从 panel 取
    first_bars = (
        panel[(panel["state_S"] == "H_only") & panel["dur_group"].notna()]
        .sort_values(["symbol", "datetime"])
        .groupby("episode_id")
        .first()
        .reset_index()
    )

    path_rows = []
    for dur_g in ["short_1_2", "mid_3_5", "long_6_plus"]:
        sub = first_bars[first_bars["dur_group"] == dur_g].copy()
        if len(sub) == 0:
            continue
        for k in (1, 3, 5, 10, 20):
            # 在全 panel 中按 symbol/datetime 对齐前向状态
            sub = sub.sort_values("datetime")
            # 构造全 panel 的 state_S shift
            for sym in sub["symbol"].unique():
                mask_sym = sub["symbol"] == sym
                sym_idx = sub[mask_sym].index
                panel_sym = panel[panel["symbol"] == sym].sort_values("datetime")
                state_shifted = panel_sym["state_S"].shift(-k)
                # map by datetime
                dt_to_state = dict(zip(panel_sym["datetime"], state_shifted))
                sub.loc[sym_idx, f"fwd_state_{k}"] = sub.loc[sym_idx, "datetime"].map(dt_to_state)
            counts = sub[f"fwd_state_{k}"].value_counts(normalize=True)
            for state in ["co_compress", "co_expand", "H_only", "L_only"]:
                path_rows.append({
                    "dur_group": dur_g,
                    "horizon": k,
                    "state": state,
                    "prob": float(counts.get(state, 0.0)),
                    "n": int(len(sub)),
                })

    path_df = pd.DataFrame(path_rows)
    path_df.to_csv(OUT_DIR / "stage7_state_paths.csv", index=False)

    print("\n=== 前向状态路径（5 步）===")
    for dur_g in ["short_1_2", "mid_3_5", "long_6_plus"]:
        p5 = path_df[(path_df["dur_group"] == dur_g) & (path_df["horizon"] == 5)]
        print(f"\n{dur_g}:")
        print(p5[["state", "prob"]].to_string(index=False))

    # ============================================================
    # 5. 事后机制分类：5 根后 S_H 是否维持 >1
    # ============================================================
    # 对每段 H_only，看 5 根后 S_H 是否仍 >1
    # 用 panel 中每段最后一根的 5 根后 S_H
    episode_last = h_only.sort_values("datetime").groupby("episode_id").last().reset_index()
    episode_last["SH_5after"] = episode_last.groupby("symbol")["S_H"].shift(-5)
    episode_last = episode_last.merge(
        episode_dur[["episode_id", "dur_group", "duration", "fwd_ret_20_first"]],
        on="episode_id", how="left", suffixes=("", "_ep"),
    )

    # 机制分类
    episode_last["mechanism"] = "unknown"
    episode_last.loc[
        (episode_last["SH_5after"] > 1.0) & (episode_last["dur_group"] != "short_1_2"),
        "mechanism",
    ] = "trend_start"
    episode_last.loc[
        (episode_last["SH_5after"] <= 1.0) | (episode_last["dur_group"] == "short_1_2"),
        "mechanism",
    ] = "oversold_bounce"

    mech_counts = episode_last["mechanism"].value_counts()
    print("\n=== 事后机制分类（5 根后 S_H 路径）===")
    print(mech_counts)

    mech_rows = []
    for mech, sub in episode_last.groupby("mechanism"):
        if len(sub) < 5:
            continue
        s = summarize(sub, "fwd_ret_20_first")
        mech_rows.append({
            "mechanism": mech,
            "n": s["n"],
            "ret20": s["mean"],
            "median": s["median"],
            "ci_lo": s["ci_lo"],
            "ci_hi": s["ci_hi"],
            "win_rate": s["win_rate"],
            "dur_mean": float(sub["duration"].mean()),
            "madev60_mean": float(sub["MADEV_60"].mean()),
            "madev60_lt0_frac": float((sub["MADEV_60"] < 0).mean()),
            "SH_peak": float(sub["S_H"].max()),
            "confirm_rate": float((sub["H_only_outcome"] == "confirmed").mean()),
        })
    mech_df = pd.DataFrame(mech_rows)
    mech_df.to_csv(OUT_DIR / "stage7_mechanism_classification.csv", index=False)
    print("\n机制分类结果：")
    print(mech_df.round(4).to_string(index=False))

    # ============================================================
    # 6. 前向累计收益曲线（episode first bar）
    # ============================================================
    curve_rows = []
    for dur_g in ["short_1_2", "mid_3_5", "long_6_plus"]:
        eps = episode_dur[episode_dur["dur_group"] == dur_g]
        first_bars_sub = first_bars[first_bars["episode_id"].isin(eps["episode_id"])].copy()
        for k in (1, 3, 5, 10, 20):
            # 从 panel 按 symbol/datetime 对齐前向 close
            for sym in first_bars_sub["symbol"].unique():
                mask_sym = first_bars_sub["symbol"] == sym
                idx = first_bars_sub[mask_sym].index
                panel_sym = panel[panel["symbol"] == sym].sort_values("datetime")
                close_future = panel_sym["close"].shift(-k)
                dt_to_close = dict(zip(panel_sym["datetime"], close_future))
                first_bars_sub.loc[idx, f"close_future_{k}"] = first_bars_sub.loc[idx, "datetime"].map(dt_to_close)
            first_bars_sub[f"ret_{k}"] = first_bars_sub[f"close_future_{k}"] / first_bars_sub["close"] - 1
            vals = first_bars_sub[f"ret_{k}"].dropna()
            if len(vals) >= MIN_N:
                ci_lo, ci_hi = cluster_bootstrap_ci(vals.values, first_bars_sub.loc[vals.index, "date"].values)
            else:
                ci_lo, ci_hi = np.nan, np.nan
            curve_rows.append({
                "dur_group": dur_g,
                "horizon": k,
                "n": int(len(vals)),
                "mean_ret": float(vals.mean()) if len(vals) else np.nan,
                "median_ret": float(vals.median()) if len(vals) else np.nan,
                "ci_lo": ci_lo,
                "ci_hi": ci_hi,
                "win_rate": float((vals > 0).mean()) if len(vals) else np.nan,
            })

    curve_df = pd.DataFrame(curve_rows)
    curve_df.to_csv(OUT_DIR / "stage7_return_curve.csv", index=False)

    print("\n=== 前向累计收益曲线 ===")
    for dur_g in ["short_1_2", "mid_3_5", "long_6_plus"]:
        print(f"\n{dur_g}:")
        sub = curve_df[curve_df["dur_group"] == dur_g]
        print(sub[["horizon", "n", "mean_ret", "median_ret", "ci_lo", "ci_hi", "win_rate"]].round(4).to_string(index=False))

    # ============================================================
    # 7. summary
    # ============================================================
    summary = {
        "n_episodes": int(n_episodes),
        "duration_distribution": dur_counts.to_dict(),
        "short_pulse": {
            "n": int(dur_df.loc[dur_df["group"] == "short_1_2", "n_episodes"].iloc[0]),
            "confirm_rate": float(dur_df.loc[dur_df["group"] == "short_1_2", "confirm_rate"].iloc[0]),
            "ret20": float(dur_df.loc[dur_df["group"] == "short_1_2", "ret20_mean"].iloc[0]),
            "win_rate": float(dur_df.loc[dur_df["group"] == "short_1_2", "win_rate"].iloc[0]),
        },
        "long_sustained": {
            "n": int(dur_df.loc[dur_df["group"] == "long_6_plus", "n_episodes"].iloc[0]),
            "confirm_rate": float(dur_df.loc[dur_df["group"] == "long_6_plus", "confirm_rate"].iloc[0]),
            "ret20": float(dur_df.loc[dur_df["group"] == "long_6_plus", "ret20_mean"].iloc[0]),
            "win_rate": float(dur_df.loc[dur_df["group"] == "long_6_plus", "win_rate"].iloc[0]),
        },
        "mechanism_counts": mech_counts.to_dict(),
    }
    with open(OUT_DIR / "stage7_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nStage 7 输出已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
