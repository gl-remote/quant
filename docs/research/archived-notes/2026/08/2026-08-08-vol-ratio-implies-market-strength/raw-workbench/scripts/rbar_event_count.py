"""
R_bar 事件数量统计
==================

统计不同阈值下的事件数量，验证样本量是否充足。
事件定义：R_bar 首次穿越阈值（状态触发抽样），带最小间隔约束。

阈值：R_bar > 1.9, 2.0, 2.1, 2.2
对照组：R_bar < 1.6

输出：事件数、品种分布、时间分布、非重叠样本量评估。
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[3]
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
OUT_DIR = Path(__file__).resolve().parent / "outputs" / "rbar_event_count"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def wilder_atr(df, length=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False, min_periods=length).mean()


def compute_rbar(sym):
    """计算单合约的 R_bar 序列（1h 对齐）。"""
    f1h = CSV_DIR / f"{sym}.tqsdk.1h.csv"
    f15 = CSV_DIR / f"{sym}.tqsdk.15m.csv"
    if not f1h.exists() or not f15.exists():
        return None
    df_1h = pd.read_csv(f1h, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df_15 = pd.read_csv(f15, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    if len(df_1h) < 200 or len(df_15) < 400:
        return None

    df_1h["H"] = wilder_atr(df_1h, 14)
    df_15["L_clock"] = wilder_atr(df_15, 56)

    base = df_1h[["datetime", "close", "H"]].dropna().sort_values("datetime")
    l_sub = df_15[["datetime", "L_clock"]].dropna().sort_values("datetime")
    base = pd.merge_asof(base, l_sub, on="datetime", direction="backward")
    base = base.dropna()
    base["R_bar"] = base["H"] / base["L_clock"]
    base["symbol"] = sym
    base["year"] = base["datetime"].dt.year
    base["month"] = base["datetime"].dt.to_period("M").astype(str)
    return base[["datetime", "symbol", "close", "R_bar", "year", "month"]]


def extract_events(sym_df, threshold, direction="above", min_gap_hours=8):
    """
    状态触发抽样：首次穿越阈值，带最小间隔约束。

    direction="above": 前一根 <= threshold，当前根 > threshold
    direction="below": 前一根 >= threshold，当前根 < threshold
    """
    df = sym_df.sort_values("datetime").reset_index(drop=True)
    if direction == "above":
        is_active = df["R_bar"] > threshold
    else:
        is_active = df["R_bar"] < threshold
    is_active_prev = is_active.shift(1, fill_value=False)
    crossings = df[(~is_active_prev) & is_active].copy()
    crossings["event_type"] = "enter"

    # 最小间隔约束
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
    print("R_bar 事件数量统计", flush=True)
    print("=" * 70, flush=True)

    # 加载所有合约
    print("\n加载合约数据...", flush=True)
    panels = []
    symbols = []
    for f in sorted(CSV_DIR.glob("*.1h.csv")):
        sym = f.name.replace(".tqsdk.1h.csv", "")
        p = compute_rbar(sym)
        if p is not None:
            panels.append(p)
            symbols.append(sym)
    panel = pd.concat(panels, ignore_index=True)
    print(f"面板: {len(panel)} 行, {len(symbols)} 合约", flush=True)
    print(f"时间: {panel['datetime'].min()} ~ {panel['datetime'].max()}", flush=True)

    # R_bar 分布概览
    print("\n--- R_bar 分布 ---", flush=True)
    print(f"中位数: {panel['R_bar'].median():.4f}", flush=True)
    print(f"均值:   {panel['R_bar'].mean():.4f}", flush=True)
    print(f"std:    {panel['R_bar'].std():.4f}", flush=True)
    print(f"p05:    {panel['R_bar'].quantile(0.05):.4f}", flush=True)
    print(f"p25:    {panel['R_bar'].quantile(0.25):.4f}", flush=True)
    print(f"p50:    {panel['R_bar'].quantile(0.50):.4f}", flush=True)
    print(f"p75:    {panel['R_bar'].quantile(0.75):.4f}", flush=True)
    print(f"p95:    {panel['R_bar'].quantile(0.95):.4f}", flush=True)

    # 不同阈值下的样本量
    thresholds_above = [1.9, 1.95, 2.0, 2.05, 2.1, 2.2]
    thresholds_below = [1.6, 1.5]

    print("\n" + "=" * 70, flush=True)
    print("一、阈值筛选下的原始行数（含重叠）", flush=True)
    print("=" * 70, flush=True)
    print(f"{'阈值':<12} {'行数':>8} {'占比':>8} {'品种数':>6}", flush=True)
    print("-" * 40, flush=True)
    raw_counts = {}
    for th in thresholds_above:
        sub = panel[panel["R_bar"] > th]
        n = len(sub)
        pct = n / len(panel)
        n_sym = sub["symbol"].nunique()
        raw_counts[f"R>{th}"] = {"n": n, "pct": pct, "n_symbols": n_sym}
        print(f"R > {th:<6} {n:>8} {pct:>8.2%} {n_sym:>6}", flush=True)
    for th in thresholds_below:
        sub = panel[panel["R_bar"] < th]
        n = len(sub)
        pct = n / len(panel)
        n_sym = sub["symbol"].nunique()
        raw_counts[f"R<{th}"] = {"n": n, "pct": pct, "n_symbols": n_sym}
        print(f"R < {th:<6} {n:>8} {pct:>8.2%} {n_sym:>6}", flush=True)

    # 状态触发事件数
    print("\n" + "=" * 70, flush=True)
    print("二、状态触发事件数（首次穿越 + 最小间隔约束）", flush=True)
    print("=" * 70, flush=True)

    min_gaps = [4, 8, 12, 24]
    event_counts = {}

    for min_gap in min_gaps:
        print(f"\n--- 最小间隔 {min_gap}h ---", flush=True)
        print(f"{'阈值':<12} {'事件数':>8} {'品种数':>6} {'均值/品种':>10}", flush=True)
        print("-" * 40, flush=True)

        for th in thresholds_above:
            all_events = []
            for sym in symbols:
                sym_df = panel[panel["symbol"] == sym]
                events = extract_events(sym_df, th, direction="above", min_gap_hours=min_gap)
                all_events.append(events)
            events_df = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
            n = len(events_df)
            n_sym = events_df["symbol"].nunique() if n > 0 else 0
            avg_per_sym = n / len(symbols) if symbols else 0
            key = f"R>{th}_gap{min_gap}h"
            event_counts[key] = {
                "n_events": n,
                "n_symbols": n_sym,
                "avg_per_symbol": avg_per_sym,
                "min_gap_hours": min_gap,
                "threshold": th,
                "direction": "above",
            }
            print(f"R > {th:<6} {n:>8} {n_sym:>6} {avg_per_sym:>10.1f}", flush=True)

        for th in thresholds_below:
            all_events = []
            for sym in symbols:
                sym_df = panel[panel["symbol"] == sym]
                events = extract_events(sym_df, th, direction="below", min_gap_hours=min_gap)
                all_events.append(events)
            events_df = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
            n = len(events_df)
            n_sym = events_df["symbol"].nunique() if n > 0 else 0
            avg_per_sym = n / len(symbols) if symbols else 0
            key = f"R<{th}_gap{min_gap}h"
            event_counts[key] = {
                "n_events": n,
                "n_symbols": n_sym,
                "avg_per_symbol": avg_per_sym,
                "min_gap_hours": min_gap,
                "threshold": th,
                "direction": "below",
            }
            print(f"R < {th:<6} {n:>8} {n_sym:>6} {avg_per_sym:>10.1f}", flush=True)

    # 重点阈值（R>2.0, gap=8h）的品种分布
    print("\n" + "=" * 70, flush=True)
    print("三、R > 2.0 事件（8h 间隔）的品种分布", flush=True)
    print("=" * 70, flush=True)

    all_events_20 = []
    for sym in symbols:
        sym_df = panel[panel["symbol"] == sym]
        events = extract_events(sym_df, 2.0, direction="above", min_gap_hours=8)
        all_events_20.append(events)
    events_20 = pd.concat(all_events_20, ignore_index=True) if all_events_20 else pd.DataFrame()

    if len(events_20) > 0:
        sym_dist = events_20["symbol"].value_counts()
        print(f"总事件数: {len(events_20)}", flush=True)
        print(f"参与品种: {events_20['symbol'].nunique()}", flush=True)
        print(f"\nTop 10 品种:", flush=True)
        print(sym_dist.head(10).to_string(), flush=True)
        print(f"\nBottom 5 品种:", flush=True)
        print(sym_dist.tail(5).to_string(), flush=True)
        print(f"\n品种覆盖率: {events_20['symbol'].nunique()} / {len(symbols)}", flush=True)

        # 单品种最大占比
        max_pct = sym_dist.iloc[0] / len(events_20)
        print(f"单品种最大占比: {sym_dist.index[0]} = {max_pct:.2%}", flush=True)

        # 时间分布
        print(f"\n--- 年月分布 ---", flush=True)
        events_20["year_month"] = events_20["datetime"].dt.to_period("M").astype(str)
        ym_dist = events_20["year_month"].value_counts().sort_index()
        print(f"覆盖月份数: {len(ym_dist)}", flush=True)
        print(f"Top 5 月份:", flush=True)
        print(ym_dist.head(5).to_string(), flush=True)
    else:
        print("无事件！", flush=True)

    # R > 1.9 的品种分布（对比）
    print("\n" + "=" * 70, flush=True)
    print("四、R > 1.9 事件（8h 间隔）的品种分布", flush=True)
    print("=" * 70, flush=True)

    all_events_19 = []
    for sym in symbols:
        sym_df = panel[panel["symbol"] == sym]
        events = extract_events(sym_df, 1.9, direction="above", min_gap_hours=8)
        all_events_19.append(events)
    events_19 = pd.concat(all_events_19, ignore_index=True) if all_events_19 else pd.DataFrame()

    if len(events_19) > 0:
        sym_dist_19 = events_19["symbol"].value_counts()
        print(f"总事件数: {len(events_19)}", flush=True)
        print(f"参与品种: {events_19['symbol'].nunique()}", flush=True)
        print(f"品种覆盖率: {events_19['symbol'].nunique()} / {len(symbols)}", flush=True)
        max_pct_19 = sym_dist_19.iloc[0] / len(events_19)
        print(f"单品种最大占比: {sym_dist_19.index[0]} = {max_pct_19:.2%}", flush=True)

    # 样本量评估
    print("\n" + "=" * 70, flush=True)
    print("五、样本量充足性评估", flush=True)
    print("=" * 70, flush=True)

    print("""
评估标准:
- 统计检验功效: 事件数 >= 200 可做基本统计检验
- 分品种分析: 事件数 >= 30 / 品种可做品种内分析
- Bootstrap 置信区间: 事件数 >= 100 可估计 95% CI
""", flush=True)

    for th in [1.9, 2.0]:
        for gap in [4, 8]:
            key = f"R>{th}_gap{gap}h"
            n = event_counts[key]["n_events"]
            print(f"R > {th} (gap={gap}h): {n} 事件", flush=True)
            if n >= 200:
                print(f"  -> 充足（>= 200）", flush=True)
            elif n >= 100:
                print(f"  -> 基本可用（100-200），建议 bootstrap", flush=True)
            elif n >= 30:
                print(f"  -> 不足（30-100），只能做描述性统计", flush=True)
            else:
                print(f"  -> 严重不足（< 30）", flush=True)

    # 图表
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 图1: R_bar 分布
    ax = axes[0, 0]
    ax.hist(panel["R_bar"], bins=100, color="steelblue", alpha=0.7, edgecolor="black")
    for th in [1.6, 1.9, 2.0]:
        ax.axvline(th, color="red" if th == 2.0 else "orange", linestyle="--",
                   label=f"R={th}")
    ax.axvline(2.0, color="red", linestyle="-", linewidth=2, label="GBM 基线 R=2.0")
    ax.set_xlabel("R_bar")
    ax.set_ylabel("频数")
    ax.set_title("R_bar 分布与阈值")
    ax.legend()

    # 图2: 事件数 vs 阈值（不同 gap）
    ax = axes[0, 1]
    for gap in min_gaps:
        ns = [event_counts[f"R>{th}_gap{gap}h"]["n_events"] for th in thresholds_above]
        ax.plot(thresholds_above, ns, marker="o", label=f"gap={gap}h")
    ax.axhline(200, color="red", linestyle="--", label="200 事件门槛")
    ax.axhline(100, color="orange", linestyle="--", label="100 事件门槛")
    ax.set_xlabel("R_bar 阈值")
    ax.set_ylabel("事件数")
    ax.set_title("事件数 vs 阈值（不同最小间隔）")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 图3: R>2.0 事件的品种分布
    ax = axes[1, 0]
    if len(events_20) > 0:
        top_syms = sym_dist.head(15)
        ax.barh(range(len(top_syms)), top_syms.values, color="steelblue")
        ax.set_yticks(range(len(top_syms)))
        ax.set_yticklabels(top_syms.index)
        ax.set_xlabel("事件数")
        ax.set_title("R > 2.0 事件数 Top 15 品种（gap=8h）")
        ax.invert_yaxis()

    # 图4: R>2.0 事件的月份分布
    ax = axes[1, 1]
    if len(events_20) > 0:
        ym_dist.plot(ax=ax, color="steelblue")
        ax.set_xlabel("年月")
        ax.set_ylabel("事件数")
        ax.set_title("R > 2.0 事件月度分布（gap=8h）")
        ax.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    fig_path = OUT_DIR / "rbar_event_count.png"
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n图表已保存: {fig_path}", flush=True)

    # 保存结果
    summary = {
        "n_total_rows": len(panel),
        "n_symbols": len(symbols),
        "date_range": [str(panel["datetime"].min()), str(panel["datetime"].max())],
        "rbar_stats": {
            "median": float(panel["R_bar"].median()),
            "mean": float(panel["R_bar"].mean()),
            "std": float(panel["R_bar"].std()),
            "p05": float(panel["R_bar"].quantile(0.05)),
            "p25": float(panel["R_bar"].quantile(0.25)),
            "p50": float(panel["R_bar"].quantile(0.50)),
            "p75": float(panel["R_bar"].quantile(0.75)),
            "p95": float(panel["R_bar"].quantile(0.95)),
        },
        "raw_counts": raw_counts,
        "event_counts": event_counts,
    }
    summary_path = OUT_DIR / "rbar_event_count_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"结果已保存: {summary_path}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("统计完成", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
