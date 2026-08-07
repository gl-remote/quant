"""
R_1h_d 在 2022-2023 熊市/震荡市中的验证
=========================================

用新下载的 2022-2023 数据，复用 term_structure 的因子计算，
检验 R_1h_d 三分位策略在熊市是否仍然成立。

关键问题：
1. long_low（R_1h_d 低做多）在熊市中是否还赚钱？如果不赚，说明是 beta；
2. short_high（R_1h_d 高做空）在熊市中是否赚更多？如果是，说明信号独立于 beta；
3. long_short 多空组合是否稳定？
4. 2022 vs 2023 vs 2024-2026 对比。
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
OUT_DIR = SCRIPT_DIR / "outputs" / "term_bear_validation"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

BOOT_N = 1000
BOOT_SEED = 42


def cluster_bootstrap_ci(values, clusters):
    rng = np.random.default_rng(BOOT_SEED)
    mask = ~np.isnan(values)
    values, clusters = values[mask], clusters[mask]
    if len(values) < 10:
        return np.nan, np.nan
    uniq = np.unique(clusters)
    idx_map = {c: np.where(clusters == c)[0] for c in uniq}
    stats = np.empty(BOOT_N)
    for i in range(BOOT_N):
        sampled = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_map[c] for c in sampled])
        stats[i] = values[idx].mean()
    return float(np.nanpercentile(stats, 2.5)), float(np.nanpercentile(stats, 97.5))


# 复用 term_structure 的计算
import importlib.util
spec = importlib.util.spec_from_file_location("term_structure", SCRIPT_DIR / "scripts" / "term_structure.py")
ts_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts_mod)


def stats_of(rets, dates, cost_bp=0):
    if len(rets) == 0:
        return {"n": 0}
    mask = ~np.isnan(rets)
    rets = rets[mask] - cost_bp / 10000.0
    dates = dates[mask]
    if len(rets) == 0:
        return {"n": 0}
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    ci_lo, ci_hi = cluster_bootstrap_ci(rets, dates.astype(str))
    return {
        "n": len(rets),
        "win_rate": float((rets > 0).mean()),
        "mean": float(rets.mean()),
        "ci_lo": ci_lo, "ci_hi": ci_hi,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) and abs(losses.sum()) > 0 else np.inf,
    }


def long_short_returns(low_df, high_df, h=20):
    rets_list, dates_list = [], []
    for sym in sorted(set(low_df["symbol"]) & set(high_df["symbol"])):
        lo = low_df[low_df["symbol"] == sym].sort_values("datetime")
        hi = high_df[high_df["symbol"] == sym].sort_values("datetime")
        n = min(len(lo), len(hi))
        if n == 0:
            continue
        ls = lo[f"fwd_ret_{h}"].values[:n] - hi[f"fwd_ret_{h}"].values[:n]
        rets_list.append(ls)
        dates_list.append(lo["datetime"].values[:n])
    if not rets_list:
        return np.array([]), np.array([])
    return np.concatenate(rets_list), np.concatenate(dates_list)


def main():
    # 加载 2022-2023 合约
    bear_symbols = [
        "DCE.m2301", "DCE.m2305", "DCE.c2301", "DCE.c2305",
        "DCE.p2301", "DCE.p2305", "DCE.i2301", "DCE.i2305",
        "CZCE.SR301", "CZCE.SR305", "CZCE.TA301", "CZCE.TA305",
        "SHFE.cu2301", "SHFE.cu2305", "SHFE.al2301", "SHFE.al2305",
        "SHFE.rb2301", "SHFE.rb2305",
        "INE.sc2301", "INE.sc2305",
    ]
    # 同时加载 2024-2026 作为对比
    modern_symbols = sorted(f.name.replace(".tqsdk.1h.csv", "")
                           for f in CSV_DIR.glob("*.1h.csv")
                           if any(y in f.name for y in ["25", "26", "24"]) and "23" not in f.name)

    print(f"熊市合约: {len(bear_symbols)}, 近期合约: {len(modern_symbols)}", flush=True)

    panels = {}
    for label, syms in [("bear_2022_2023", bear_symbols), ("modern_2024_2026", modern_symbols)]:
        print(f"\n计算 {label}...", flush=True)
        parts = []
        for sym in syms:
            p = ts_mod.compute_panel(sym)
            if p is not None:
                parts.append(p)
        if parts:
            panels[label] = pd.concat(parts, ignore_index=True)
            print(f"  {label}: {len(panels[label])} 行, {panels[label]['symbol'].nunique()} 合约", flush=True)
            print(f"  时间: {panels[label]['datetime'].min()} ~ {panels[label]['datetime'].max()}", flush=True)

    # 三分位（每合约滚动）
    for label in panels:
        p = panels[label]
        p["R_1h_d_tercile"] = p.groupby("symbol")["R_1h_d"].transform(
            lambda x: pd.qcut(x, 3, labels=["low", "mid", "high"])
        )
        p["year"] = p["datetime"].dt.year

    # ============================================================
    # 1. 对比：熊市 vs 近期，三个信号
    # ============================================================
    print("\n=== 1. 熊市 vs 近期：信号对比（h=20）===", flush=True)
    comparison = []
    for label, p in panels.items():
        for sig, direction, tercile in [
            ("long_low", 1, "low"),
            ("short_high", -1, "high"),
        ]:
            sub = p[p["R_1h_d_tercile"] == tercile]
            rets = (direction * sub["fwd_ret_20"]).values
            dates = sub["datetime"].dt.date.values
            s = stats_of(rets, dates)
            s["period"] = label
            s["signal"] = sig
            comparison.append(s)
        # long_short
        low_df = p[p["R_1h_d_tercile"] == "low"]
        high_df = p[p["R_1h_d_tercile"] == "high"]
        ls_rets, ls_dates = long_short_returns(low_df, high_df, h=20)
        s = stats_of(ls_rets, pd.to_datetime(ls_dates).date)
        s["period"] = label
        s["signal"] = "long_short"
        comparison.append(s)

    comp_df = pd.DataFrame(comparison)
    comp_df.to_csv(OUT_DIR / "bear_vs_modern.csv", index=False)
    print(comp_df[["period", "signal", "n", "win_rate", "mean", "ci_lo", "ci_hi", "profit_factor"]].round(4).to_string(index=False), flush=True)

    # ============================================================
    # 2. 按年份拆分
    # ============================================================
    print("\n=== 2. 按年份拆分（long_short, h=20）===", flush=True)
    year_rows = []
    all_panels = pd.concat(panels.values(), ignore_index=True)
    for year, sub_all in all_panels.groupby("year"):
        for sig, direction, tercile in [("long_low", 1, "low"), ("short_high", -1, "high")]:
            sub = sub_all[sub_all["R_1h_d_tercile"] == tercile]
            rets = (direction * sub["fwd_ret_20"]).values
            dates = sub["datetime"].dt.date.values
            s = stats_of(rets, dates)
            s["year"] = int(year)
            s["signal"] = sig
            year_rows.append(s)
        low_df = sub_all[sub_all["R_1h_d_tercile"] == "low"]
        high_df = sub_all[sub_all["R_1h_d_tercile"] == "high"]
        ls_rets, ls_dates = long_short_returns(low_df, high_df, h=20)
        s = stats_of(ls_rets, pd.to_datetime(ls_dates).date)
        s["year"] = int(year)
        s["signal"] = "long_short"
        year_rows.append(s)
    year_df = pd.DataFrame(year_rows)
    year_df.to_csv(OUT_DIR / "bear_by_year.csv", index=False)
    print(year_df[["year", "signal", "n", "win_rate", "mean", "ci_lo", "ci_hi"]].round(4).to_string(index=False), flush=True)

    # ============================================================
    # 3. 按年份 × h（5/20/60）
    # ============================================================
    print("\n=== 3. 按年份 × 持仓周期（long_short）===", flush=True)
    decay_rows = []
    for year, sub_all in all_panels.groupby("year"):
        for h in [5, 20, 60]:
            low_df = sub_all[sub_all["R_1h_d_tercile"] == "low"]
            high_df = sub_all[sub_all["R_1h_d_tercile"] == "high"]
            ls_rets, ls_dates = long_short_returns(low_df, high_df, h=h)
            s = stats_of(ls_rets, pd.to_datetime(ls_dates).date)
            s["year"] = int(year)
            s["horizon"] = h
            decay_rows.append(s)
    decay_df = pd.DataFrame(decay_rows)
    decay_df.to_csv(OUT_DIR / "bear_decay.csv", index=False)
    print(decay_df[["year", "horizon", "n", "win_rate", "mean", "ci_lo", "ci_hi"]].round(4).to_string(index=False), flush=True)

    # ============================================================
    # 4. 买入持有基准
    # ============================================================
    print("\n=== 4. 买入持有基准 ===", flush=True)
    bh_rows = []
    for label, p in panels.items():
        for sym, sub in p.groupby("symbol"):
            sub = sub.sort_values("datetime")
            ret = sub["close"].iloc[-1] / sub["close"].iloc[0] - 1
            bh_rows.append({"period": label, "symbol": sym, "buy_hold": ret,
                            "start": str(sub["datetime"].iloc[0].date()),
                            "end": str(sub["datetime"].iloc[-1].date())})
    bh_df = pd.DataFrame(bh_rows)
    bh_df.to_csv(OUT_DIR / "bear_buy_hold.csv", index=False)
    print(bh_df.groupby("period")["buy_hold"].agg(["mean", "median", lambda x: (x > 0).mean()]).round(4), flush=True)

    # ============================================================
    # 图表
    # ============================================================
    print("\n生成图表...", flush=True)

    # Fig 1: 熊市 vs 近期，三个信号
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, sig in zip(axes, ["long_low", "short_high", "long_short"]):
        sub = comp_df[comp_df.signal == sig].set_index("period").reindex(["bear_2022_2023", "modern_2024_2026"])
        x = np.arange(len(sub))
        means = sub["mean"].values * 100
        ci_lo = (sub["mean"] - sub["ci_lo"]).values * 100
        ci_hi = (sub["ci_hi"] - sub["mean"]).values * 100
        ax.bar(x, means, color=["#C44E52", "#4C72B0"], yerr=[ci_lo, ci_hi], capsize=5)
        ax.axhline(0, color="gray", linestyle="--")
        ax.set_xticks(x)
        ax.set_xticklabels(["熊市\n2022-23", "近期\n2024-26"])
        ax.set_ylabel("fwd_ret_20 (%)")
        ax.set_title(sig)
        ax.grid(axis="y", alpha=0.3)
    plt.suptitle("R_1h_d 信号：熊市 vs 近期", fontsize=13)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig1_bear_vs_modern.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 2: 按年份
    fig, ax = plt.subplots(figsize=(11, 6))
    years = sorted(year_df["year"].unique())
    width = 0.25
    x = np.arange(len(years))
    for i, (sig, color) in enumerate([("long_low", "#4C72B0"), ("short_high", "#C44E52"), ("long_short", "#55A868")]):
        sub = year_df[year_df.signal == sig].set_index("year").reindex(years)
        ax.bar(x + (i-1)*width, sub["mean"]*100, width, label=sig, color=color,
               yerr=[(sub["mean"]-sub["ci_lo"])*100, (sub["ci_hi"]-sub["mean"])*100], capsize=3)
    ax.axhline(0, color="gray", linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.set_ylabel("fwd_ret_20 (%)")
    ax.set_title("R_1h_d 信号按年份（含 2022-23 熊市）")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    # 标注熊市区间
    ax.axvspan(-0.5, 1.5, alpha=0.1, color="red")
    ax.text(0.5, ax.get_ylim()[1]*0.9, "熊市/震荡", ha="center", color="red", fontsize=10)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_by_year.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 3: 按年份 × h
    fig, ax = plt.subplots(figsize=(10, 6))
    for year in years:
        sub = decay_df[decay_df.year == year].sort_values("horizon")
        ax.errorbar(sub["horizon"], sub["mean"]*100,
                    yerr=[(sub["mean"]-sub["ci_lo"])*100, (sub["ci_hi"]-sub["mean"])*100],
                    marker="o", label=str(year), capsize=4)
    ax.axhline(0, color="gray", linestyle="--")
    ax.set_xlabel("持仓周期（根 1h）")
    ax.set_ylabel("long_short 收益 (%)")
    ax.set_xscale("log")
    ax.set_title("多空组合在不同年份/周期的表现")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_decay_by_year.png", dpi=150, bbox_inches="tight")
    plt.close()

    summary = {
        "bear_period": {
            "n_rows": int(len(panels.get("bear_2022_2023", []))),
            "symbols": int(panels["bear_2022_2023"]["symbol"].nunique()) if "bear_2022_2023" in panels else 0,
        },
        "comparison": comp_df[["period", "signal", "n", "win_rate", "mean", "ci_lo", "ci_hi"]].to_dict("records"),
        "by_year": year_df[["year", "signal", "n", "mean", "ci_lo", "ci_hi"]].to_dict("records"),
        "buy_hold": bh_df.groupby("period")["buy_hold"].agg(["mean", "median"]).to_dict(),
    }
    with open(OUT_DIR / "bear_validation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n输出已保存到 {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
