"""
R_1h_d 非重叠双向验证
=====================

F 组发现 R_1h_d（日 ATR / 1h ATR）低时后续收益偏正，高时偏负。
但这可能只是 2024–2026 多头 beta。本脚本验证：

1. 非重叠抽样：每周/每月取一个信号，避免重叠 bar 高估显著性；
2. 双向验证：
   - 做多组：R_1h_d 低三分位时做多；
   - 做空组：R_1h_d 高三分位时做空；
   - 多空组合：低买高卖（market neutral）；
3. 与买入持有基准对比；
4. 按年份拆分，看熊市/震荡市是否仍成立；
5. 按板块拆分；
6. 信号衰减：持有 5/20/60 根的收益；
7. 成本敏感性。

输出：outputs/term_validation/
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
PANEL_FACTORY = SCRIPT_DIR / "scripts" / "term_structure.py"
OUT_DIR = SCRIPT_DIR / "outputs" / "term_validation"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

BOOT_N = 1000
BOOT_SEED = 42


def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray) -> tuple[float, float]:
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


def build_panel() -> pd.DataFrame:
    """复用 term_structure.py 的 compute_panel。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("term_structure", PANEL_FACTORY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    panels = []
    for f in sorted((ROOT / "project_data/market_data/csv").glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = mod.compute_panel(sym)
        if p is not None:
            panels.append(p)
    panel = pd.concat(panels, ignore_index=True)
    panel["datetime"] = pd.to_datetime(panel["datetime"])
    panel["week"] = panel["datetime"].dt.isocalendar().year.astype(str) + "-" + panel["datetime"].dt.isocalendar().week.astype(str)
    panel["month"] = panel["datetime"].dt.to_period("M").astype(str)
    return panel


def make_terciles(panel: pd.DataFrame) -> pd.DataFrame:
    """每合约滚动三分位，避免跨合约池化。"""
    def tercile(x):
        return pd.qcut(x, 3, labels=["low", "mid", "high"])
    panel["R_1h_d_tercile"] = panel.groupby("symbol")["R_1h_d"].transform(tercile)
    return panel


def long_short_returns(low_df: pd.DataFrame, high_df: pd.DataFrame, h: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """构造多空组合：low 做多 + high 做空，按 symbol 内日期顺序一一对齐。

    不要求同一根 bar，而是对每个 symbol 分别把 low 和 high 信号按时间排序，
    按位置配对，构造 long-short 收益。这样能反映"做多低分位 + 做空高分位"的
    市场中性组合。
    """
    rets_list, dates_list = [], []
    for sym in sorted(set(low_df["symbol"]) & set(high_df["symbol"])):
        lo = low_df[low_df["symbol"] == sym].sort_values("datetime")
        hi = high_df[high_df["symbol"] == sym].sort_values("datetime")
        n = min(len(lo), len(hi))
        if n == 0:
            continue
        lo_ret = lo[f"fwd_ret_{h}"].values[:n]
        hi_ret = hi[f"fwd_ret_{h}"].values[:n]
        # long low - short high = lo_ret - hi_ret（做空 high 的收益是 -hi_ret）
        ls = lo_ret - hi_ret
        dates = lo["datetime"].values[:n]
        rets_list.append(ls)
        dates_list.append(dates)
    if not rets_list:
        return np.array([]), np.array([])
    return np.concatenate(rets_list), np.concatenate(dates_list)


def nonoverlap_sample(panel: pd.DataFrame, freq: str = "week") -> pd.DataFrame:
    """每合约每 freq 取第一根非 NaN 信号。"""
    key = "week" if freq == "week" else "month"
    return panel.sort_values("datetime").groupby(["symbol", key], as_index=False).first()


def direction_returns(sub: pd.DataFrame, direction: int, h: int = 20) -> pd.Series:
    col = f"fwd_ret_{h}"
    return direction * sub[col]


def stats_of(rets: np.ndarray, dates: np.ndarray, cost_bp: float = 0) -> dict:
    if len(rets) == 0:
        return {"n": 0, "win_rate": np.nan, "mean": np.nan, "median": np.nan,
                "ci_lo": np.nan, "ci_hi": np.nan, "avg_win": np.nan, "avg_loss": np.nan,
                "profit_factor": np.nan}
    # 先去掉 NaN
    mask = ~np.isnan(rets)
    rets = rets[mask]
    dates = dates[mask]
    if len(rets) == 0:
        return {"n": 0, "win_rate": np.nan, "mean": np.nan, "median": np.nan,
                "ci_lo": np.nan, "ci_hi": np.nan, "avg_win": np.nan, "avg_loss": np.nan,
                "profit_factor": np.nan}
    rets = rets - cost_bp / 10000.0
    n = len(rets)
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    ci_lo, ci_hi = cluster_bootstrap_ci(rets, dates.astype(str))
    return {
        "n": n,
        "win_rate": float((rets > 0).mean()),
        "mean": float(rets.mean()),
        "median": float(np.median(rets)),
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "avg_win": float(wins.mean()) if len(wins) else np.nan,
        "avg_loss": float(losses.mean()) if len(losses) else np.nan,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) and abs(losses.sum()) > 0 else np.inf,
    }


def main() -> None:
    print("构建面板（复用 term_structure）...", flush=True)
    panel = build_panel()
    panel = make_terciles(panel)
    print(f"面板: {len(panel)} 行, {panel['symbol'].nunique()} 合约", flush=True)

    results = {}

    # ============================================================
    # 1. 全样本重叠信号（对照基准）
    # ============================================================
    print("\n=== 1. 全样本重叠信号（h=20）===", flush=True)
    rows = []
    for label, direction, tercile in [
        ("long_low", +1, "low"),
        ("short_high", -1, "high"),
        ("long_short", 0, None),  # 多空组合
    ]:
        if label == "long_short":
            low_df = panel[panel["R_1h_d_tercile"] == "low"]
            high_df = panel[panel["R_1h_d_tercile"] == "high"]
            rets, dt_arr = long_short_returns(low_df, high_df, h=20)
            dates = pd.to_datetime(dt_arr).date
        else:
            sub = panel[panel["R_1h_d_tercile"] == tercile]
            rets = direction_returns(sub, direction, 20).values
            dates = sub["datetime"].dt.date.values
        s = stats_of(rets, dates)
        s["signal"] = label
        s["sample"] = "overlap"
        rows.append(s)
        print(f"  {label:12s}: n={s['n']:5d}  win={s['win_rate']:.1%}  "
              f"ret={s['mean']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  PF={s['profit_factor']:.2f}",
              flush=True)
    overlap_df = pd.DataFrame(rows)
    overlap_df.to_csv(OUT_DIR / "validation_overlap.csv", index=False)

    # ============================================================
    # 2. 非重叠抽样（每周/每月第一根）
    # ============================================================
    print("\n=== 2. 非重叠抽样（h=20）===", flush=True)
    nonoverlap_rows = []
    for freq in ["week", "month"]:
        no = nonoverlap_sample(panel, freq=freq)
        for label, direction, tercile in [
            ("long_low", +1, "low"),
            ("short_high", -1, "high"),
            ("long_short", 0, None),
        ]:
            if label == "long_short":
                low_df = no[no["R_1h_d_tercile"] == "low"]
                high_df = no[no["R_1h_d_tercile"] == "high"]
                rets, dt_arr = long_short_returns(low_df, high_df, h=20)
                dates = pd.to_datetime(dt_arr).date
            else:
                sub = no[no["R_1h_d_tercile"] == tercile]
                rets = direction_returns(sub, direction, 20).values
                dates = sub["datetime"].dt.date.values
            s = stats_of(rets, dates)
            s["signal"] = label
            s["sample"] = f"nonoverlap_{freq}"
            nonoverlap_rows.append(s)
            print(f"  [{freq:5s}] {label:12s}: n={s['n']:5d}  win={s['win_rate']:.1%}  "
                  f"ret={s['mean']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  PF={s['profit_factor']:.2f}",
                  flush=True)
    nonoverlap_df = pd.DataFrame(nonoverlap_rows)
    nonoverlap_df.to_csv(OUT_DIR / "validation_nonoverlap.csv", index=False)

    # ============================================================
    # 3. 按年份拆分（非重叠 weekly）
    # ============================================================
    print("\n=== 3. 按年份（非重叠 weekly, h=20）===", flush=True)
    no_week = nonoverlap_sample(panel, "week")
    year_rows = []
    for year, sub_all in no_week.groupby("year"):
        for label, direction, tercile in [
            ("long_low", +1, "low"),
            ("short_high", -1, "high"),
            ("long_short", 0, None),
        ]:
            if label == "long_short":
                low_df = sub_all[sub_all["R_1h_d_tercile"] == "low"]
                high_df = sub_all[sub_all["R_1h_d_tercile"] == "high"]
                if len(low_df) == 0 or len(high_df) == 0:
                    continue
                rets, dt_arr = long_short_returns(low_df, high_df, h=20)
                dates = pd.to_datetime(dt_arr).date
            else:
                sub = sub_all[sub_all["R_1h_d_tercile"] == tercile]
                if len(sub) == 0:
                    continue
                rets = direction_returns(sub, direction, 20).values
                dates = sub["datetime"].dt.date.values
            s = stats_of(rets, dates)
            s["signal"] = label
            s["year"] = int(year)
            year_rows.append(s)
            print(f"  {year} {label:12s}: n={s['n']:4d}  win={s['win_rate']:.1%}  "
                  f"ret={s['mean']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]", flush=True)
    year_df = pd.DataFrame(year_rows)
    year_df.to_csv(OUT_DIR / "validation_by_year.csv", index=False)

    # ============================================================
    # 4. 按板块
    # ============================================================
    print("\n=== 4. 按板块（非重叠 weekly, h=20）===", flush=True)
    sector_rows = []
    for sector, sub_all in no_week.groupby("sector"):
        for label, direction, tercile in [
            ("long_low", +1, "low"),
            ("short_high", -1, "high"),
            ("long_short", 0, None),
        ]:
            if label == "long_short":
                low_df = sub_all[sub_all["R_1h_d_tercile"] == "low"]
                high_df = sub_all[sub_all["R_1h_d_tercile"] == "high"]
                if len(low_df) == 0 or len(high_df) == 0:
                    continue
                rets, dt_arr = long_short_returns(low_df, high_df, h=20)
                dates = pd.to_datetime(dt_arr).date
            else:
                sub = sub_all[sub_all["R_1h_d_tercile"] == tercile]
                if len(sub) == 0:
                    continue
                rets = direction_returns(sub, direction, 20).values
                dates = sub["datetime"].dt.date.values
            s = stats_of(rets, dates)
            s["signal"] = label
            s["sector"] = sector
            sector_rows.append(s)
    sector_df = pd.DataFrame(sector_rows)
    sector_df.to_csv(OUT_DIR / "validation_by_sector.csv", index=False)
    print(sector_df[["sector", "signal", "n", "win_rate", "mean", "ci_lo", "ci_hi", "profit_factor"]].round(4).to_string(index=False), flush=True)

    # ============================================================
    # 5. 信号衰减（5/20/60 根）
    # ============================================================
    print("\n=== 5. 信号衰减（非重叠 weekly）===", flush=True)
    decay_rows = []
    for h in [5, 20, 60]:
        for label, direction, tercile in [
            ("long_low", +1, "low"),
            ("short_high", -1, "high"),
            ("long_short", 0, None),
        ]:
            if label == "long_short":
                low_df = no_week[no_week["R_1h_d_tercile"] == "low"]
                high_df = no_week[no_week["R_1h_d_tercile"] == "high"]
                rets, dt_arr = long_short_returns(low_df, high_df, h=h)
                dates = pd.to_datetime(dt_arr).date
            else:
                sub = no_week[no_week["R_1h_d_tercile"] == tercile]
                rets = (direction * sub[f"fwd_ret_{h}"]).values
                dates = sub["datetime"].dt.date.values
            s = stats_of(rets, dates)
            s["signal"] = label
            s["horizon"] = h
            decay_rows.append(s)
            print(f"  h={h:2d} {label:12s}: n={s['n']:4d}  win={s['win_rate']:.1%}  "
                  f"ret={s['mean']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]", flush=True)
    decay_df = pd.DataFrame(decay_rows)
    decay_df.to_csv(OUT_DIR / "validation_decay.csv", index=False)

    # ============================================================
    # 6. 成本敏感性（weekly nonoverlap long_short）
    # ============================================================
    print("\n=== 6. 成本敏感性（weekly long_short, h=20）===", flush=True)
    low_w = no_week[no_week["R_1h_d_tercile"] == "low"]
    high_w = no_week[no_week["R_1h_d_tercile"] == "high"]
    ls_rets, ls_dt = long_short_returns(low_w, high_w, h=20)
    ls_dates = pd.to_datetime(ls_dt).date
    cost_rows = []
    for bp in [0, 1, 2, 3, 5, 10]:
        s = stats_of(ls_rets, ls_dates, cost_bp=bp)
        s["cost_bp"] = bp
        cost_rows.append(s)
        print(f"  cost={bp:2d}bp: n={s['n']:4d}  win={s['win_rate']:.1%}  "
              f"ret={s['mean']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  PF={s['profit_factor']:.2f}",
              flush=True)
    cost_df = pd.DataFrame(cost_rows)
    cost_df.to_csv(OUT_DIR / "validation_cost.csv", index=False)

    # ============================================================
    # 7. 买入持有基准
    # ============================================================
    print("\n=== 7. 买入持有基准（每合约整段）===", flush=True)
    bh_rows = []
    for sym, sub in panel.groupby("symbol"):
        sub = sub.sort_values("datetime")
        ret = sub["close"].iloc[-1] / sub["close"].iloc[0] - 1
        bh_rows.append({"symbol": sym, "sector": sub["sector"].iloc[0], "buy_hold": ret})
    bh_df = pd.DataFrame(bh_rows)
    bh_df.to_csv(OUT_DIR / "buy_hold_benchmark.csv", index=False)
    print(f"  买入持有均值: {bh_df['buy_hold'].mean():.4f}")
    print(f"  上涨合约占比: {(bh_df['buy_hold']>0).mean():.1%}", flush=True)

    # ============================================================
    # 图表
    # ============================================================
    print("\n生成图表...", flush=True)

    # Fig 1: 多空对比
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, (df_, title) in [
        (axes[0], (overlap_df, "重叠样本")),
        (axes[1], (nonoverlap_df[nonoverlap_df["sample"] == "nonoverlap_week"], "非重叠（周）")),
        (axes[2], (nonoverlap_df[nonoverlap_df["sample"] == "nonoverlap_month"], "非重叠（月）")),
    ]:
        signals = df_["signal"].tolist()
        means = df_["mean"].values * 100
        ci_lo = df_["ci_lo"].values * 100
        ci_hi = df_["ci_hi"].values * 100
        x = np.arange(len(signals))
        ax.bar(x, means, color=["#4C72B0", "#C44E52", "#55A868"][:len(signals)])
        ax.errorbar(x, means, yerr=[means - ci_lo, ci_hi - means], fmt="none", color="black", capsize=5)
        ax.axhline(0, color="gray", linestyle="--")
        ax.set_xticks(x)
        ax.set_xticklabels(signals, rotation=15)
        ax.set_ylabel("fwd_ret_20 (%)")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig1_long_short_compare.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 2: 年份
    fig, ax = plt.subplots(figsize=(10, 6))
    years = sorted(year_df["year"].unique())
    width = 0.25
    x = np.arange(len(years))
    for i, (sig, color) in enumerate([("long_low", "#4C72B0"), ("short_high", "#C44E52"), ("long_short", "#55A868")]):
        sub = year_df[year_df.signal == sig].set_index("year").reindex(years)
        ax.bar(x + (i - 1) * width, sub["mean"] * 100, width, label=sig, color=color, yerr=[
            (sub["mean"] - sub["ci_lo"]) * 100, (sub["ci_hi"] - sub["mean"]) * 100
        ], capsize=3)
    ax.axhline(0, color="gray", linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.set_ylabel("fwd_ret_20 (%)")
    ax.set_title("按年份：R_1h_d 多空信号")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig2_by_year.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Fig 3: 信号衰减
    fig, ax = plt.subplots(figsize=(9, 6))
    for sig, color in [("long_low", "#4C72B0"), ("short_high", "#C44E52"), ("long_short", "#55A868")]:
        sub = decay_df[decay_df.signal == sig].sort_values("horizon")
        ax.errorbar(sub["horizon"], sub["mean"] * 100,
                    yerr=[(sub["mean"] - sub["ci_lo"]) * 100, (sub["ci_hi"] - sub["mean"]) * 100],
                    marker="o", label=sig, color=color, capsize=5)
    ax.axhline(0, color="gray", linestyle="--")
    ax.set_xlabel("持有周期（根 1h）")
    ax.set_ylabel("收益 (%)")
    ax.set_title("R_1h_d 信号衰减（非重叠 weekly）")
    ax.set_xscale("log")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIG_DIR / "fig3_decay.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Summary
    ls_weekly_row = nonoverlap_df[(nonoverlap_df["sample"] == "nonoverlap_week") & (nonoverlap_df["signal"] == "long_short")]
    ls_weekly = ls_weekly_row.iloc[0].to_dict() if len(ls_weekly_row) else {}
    summary = {
        "n_rows": int(len(panel)),
        "n_symbols": int(panel["symbol"].nunique()),
        "overlap": {r["signal"]: {k: r[k] for k in ["n", "mean", "ci_lo", "ci_hi", "win_rate"]} for _, r in overlap_df.iterrows()},
        "weekly_nonoverlap": {r["signal"]: {k: r[k] for k in ["n", "mean", "ci_lo", "ci_hi", "win_rate"]} for _, r in nonoverlap_df[nonoverlap_df["sample"] == "nonoverlap_week"].iterrows()},
        "monthly_nonoverlap": {r["signal"]: {k: r[k] for k in ["n", "mean", "ci_lo", "ci_hi", "win_rate"]} for _, r in nonoverlap_df[nonoverlap_df["sample"] == "nonoverlap_month"].iterrows()},
        "by_year": year_df[["year", "signal", "n", "mean", "ci_lo", "ci_hi", "win_rate"]].to_dict("records"),
        "cost_3bp_long_short_weekly": stats_of(ls_rets, ls_dates, cost_bp=3),
        "buy_hold_mean": float(bh_df["buy_hold"].mean()),
        "buy_hold_up_fraction": float((bh_df["buy_hold"] > 0).mean()),
    }
    with open(OUT_DIR / "validation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n输出已保存到 {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
