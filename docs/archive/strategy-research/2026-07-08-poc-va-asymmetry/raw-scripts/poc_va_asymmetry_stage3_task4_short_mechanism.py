"""
文件级元信息：
- 创建背景：阶段 3 任务 4 · 空头 4h horizon 版本的机制分解（对应任务 2
  深挖的洞察 P 但用空头方向）。
- 用途：
    (1) 空头宽松基础条件（skew≥0.70 + trend≤0.20 · 剥离 ATR filter）
    (2) 低/中/高 ATR 下的分布形态对比
    (3) Horizon 敏感度（做空 pnl · 1h/2h/3h/4h/6h/8h）
    (4) 跨品种保留度对比
    (5) 判断空头是否也有 3 种不同机制 · 还是单一机制（高 ATR 独占）
- 假设：
    * 空头基础判据（任务 2）已发现：低 ATR 完全无信号（+3）· 高 ATR 独强（+29）
    * 猜测：空头可能是"单一机制"（恐慌前奏）· 只在高 ATR 有效
    * 不像多头有 3 种机制
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, cluster_bootstrap, parse_prefix,
    OOS_SYMBOLS, load_5m, compute_profile_skew,
    build_daily_features, rolling_pct_rank,
    ROLLING_EVENTS, ROLLING_DAYS, WARMUP_DAYS,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)


def describe_distribution(x, label):
    x = np.asarray(x)
    wins = x[x > 0]
    losses = x[x < 0]
    payoff = (wins.mean() / abs(losses.mean())) if len(losses) > 0 and losses.mean() != 0 else np.nan
    return {
        "label": label,
        "n": len(x),
        "mean": x.mean(),
        "median": np.median(x),
        "std": x.std(),
        "skew": stats.skew(x) if len(x) > 3 else np.nan,
        "kurt": stats.kurtosis(x) if len(x) > 3 else np.nan,
        "p05": np.quantile(x, 0.05),
        "p95": np.quantile(x, 0.95),
        "hit": (x > 0).mean(),
        "avg_win": wins.mean() if len(wins) else 0,
        "avg_loss": losses.mean() if len(losses) else 0,
        "payoff": payoff,
    }


def build_multi_horizon_events(symbol, tick):
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date
    mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    hourly_idx = bars.index[mask].to_list()
    rows = []
    for idx in hourly_idx:
        t = bars.loc[idx, "datetime"]
        close_t = bars.loc[idx, "close"]
        horizons = {"1h": 12, "2h": 24, "3h": 36, "4h": 48, "6h": 72, "8h": 96}
        h_rets = {}
        skip = False
        for h_name, h_bars in horizons.items():
            fut = idx + h_bars
            if fut >= len(bars):
                skip = True
                break
            h_rets[f"ret_{h_name}"] = np.log(bars.loc[fut, "close"] / close_t)
        if skip:
            continue
        current_date = t.date()
        prev = bars[bars["date"] < current_date]
        if len(prev) == 0:
            continue
        pd_date = prev["date"].max()
        w1 = prev[prev["date"] == pd_date]
        if len(w1) < 20:
            continue
        sk = compute_profile_skew(w1, tick)
        if np.isnan(sk):
            continue
        rows.append({
            "contract": symbol, "event_time": t, "event_date": current_date,
            "event_hour": t.hour, "close_t": close_t, "A3_skew": sk, **h_rets,
        })
    return pd.DataFrame(rows)


def main():
    print("=" * 100)
    print("任务 4 · 空头 4h horizon 机制分解（对应洞察 P 的空头版本）")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()

    # 空头宽松基础条件（不含 ATR）
    base_mask = ((df["signed_skew_rank_roll"] >= 0.70) &
                 (df["trend_rank_roll"] <= 0.20))
    base = df[base_mask].dropna(subset=["short_pnl_4h_bps"]).copy()
    base["event_hour"] = pd.to_datetime(base["event_time"]).dt.hour
    print(f"基础条件（skew≥0.70 + trend≤0.20）: n={len(base)}")

    low = base[base["atr_rank_roll"] <= 0.33].copy()
    mid = base[(base["atr_rank_roll"] > 0.33) & (base["atr_rank_roll"] < 0.67)].copy()
    high = base[base["atr_rank_roll"] >= 0.67].copy()
    print(f"  低 ATR: n={len(low)} · 中 ATR: n={len(mid)} · 高 ATR: n={len(high)}")

    # ============================================
    # 维度 1 · 4h 做空 pnl 分布形态对比
    # ============================================
    print("\n" + "=" * 100)
    print("维度 1 · 4h 做空 pnl 分布形态对比")
    print("=" * 100)

    dists = [describe_distribution(g["short_pnl_4h_bps"], lbl)
             for lbl, g in [("低 ATR", low), ("中 ATR", mid), ("高 ATR", high)]]

    print(f"\n{'指标':10s} {'低 ATR':>10s} {'中 ATR':>10s} {'高 ATR':>10s}")
    keys = [("n", "样本量"), ("mean", "均值 bps"), ("median", "中位数 bps"),
             ("std", "std bps"), ("skew", "偏度"), ("kurt", "峰度"),
             ("p05", "p05 bps"), ("p95", "p95 bps"),
             ("hit", "命中率"), ("payoff", "payoff"),
             ("avg_win", "平均盈"), ("avg_loss", "平均亏")]
    for k, lbl in keys:
        vals = [d[k] for d in dists]
        if k == "hit":
            print(f"{lbl:10s} {vals[0]:>10.1%} {vals[1]:>10.1%} {vals[2]:>10.1%}")
        elif k in ("n",):
            print(f"{lbl:10s} {int(vals[0]):>10d} {int(vals[1]):>10d} {int(vals[2]):>10d}")
        else:
            print(f"{lbl:10s} {vals[0]:>+10.2f} {vals[1]:>+10.2f} {vals[2]:>+10.2f}")

    # ============================================
    # 维度 2 · Horizon 敏感度
    # ============================================
    print("\n" + "=" * 100)
    print("维度 2 · 空头 Horizon 敏感度")
    print("=" * 100)

    print("\n[重新构建多 horizon 事件表] ...")
    all_ev = []
    for sym, tick in OOS_SYMBOLS.items():
        try:
            ev = build_multi_horizon_events(sym, tick)
            all_ev.append(ev)
        except FileNotFoundError:
            continue
    df_mh = pd.concat(all_ev, ignore_index=True)
    df_mh["event_time"] = pd.to_datetime(df_mh["event_time"])
    df_mh = df_mh.sort_values(["contract", "event_time"]).reset_index(drop=True)
    df_mh["signed_skew_rank_roll"] = df_mh.groupby("contract")["A3_skew"].transform(
        lambda s: rolling_pct_rank(s, ROLLING_EVENTS))
    for fc, rc in [("daily_atr_10_bps", "atr_rank_roll"),
                    ("trend_ret_10d", "trend_rank_roll")]:
        seg = []
        for c, g in df_mh.groupby("contract"):
            daily_feat = build_daily_features(c)
            g2 = g.merge(daily_feat, left_on="event_date", right_on="date", how="left")
            g2_daily = g2.drop_duplicates("event_date").sort_values("event_date").copy()
            g2_daily[rc] = rolling_pct_rank(g2_daily[fc], ROLLING_DAYS)
            seg.append(g2_daily[["contract", "event_date", rc]])
        seg_map = pd.concat(seg, ignore_index=True)
        df_mh = df_mh.merge(seg_map, on=["contract", "event_date"], how="left")
    keep = np.zeros(len(df_mh), dtype=bool)
    for c in df_mh["contract"].unique():
        idx = df_mh[df_mh["contract"] == c].sort_values("event_time").index
        dates = sorted(df_mh.loc[idx, "event_date"].unique())
        if len(dates) < WARMUP_DAYS:
            continue
        wend = dates[WARMUP_DAYS - 1]
        for i in idx:
            if df_mh.at[i, "event_date"] > wend:
                keep[df_mh.index.get_loc(i)] = True
    df_mh = df_mh[keep].dropna(subset=["signed_skew_rank_roll", "atr_rank_roll",
                                         "trend_rank_roll"])

    base_mh = df_mh[(df_mh["signed_skew_rank_roll"] >= 0.70) &
                    (df_mh["trend_rank_roll"] <= 0.20)]
    print(f"多 horizon 基础条件: n={len(base_mh)}")

    print(f"\n做空 pnl 均值（bps）· 各 horizon:")
    print(f"{'Horizon':10s} {'低 ATR':>10s} {'中 ATR':>10s} {'高 ATR':>10s}")
    for h_name in ["1h", "2h", "3h", "4h", "6h", "8h"]:
        col = f"ret_{h_name}"
        vals = []
        for atr_range in [(0, 0.33), (0.33, 0.67), (0.67, 1.01)]:
            seg = base_mh[(base_mh["atr_rank_roll"] >= atr_range[0]) &
                          (base_mh["atr_rank_roll"] < atr_range[1])]
            if len(seg) < 20:
                vals.append(np.nan)
            else:
                # 做空 · pnl = -ret
                vals.append(-seg[col].mean() * 1e4)
        print(f"{h_name:10s} {vals[0]:>+10.2f} {vals[1]:>+10.2f} {vals[2]:>+10.2f}")

    # 兑现速度（相对 4h · 因为空头主 horizon 是 4h）
    print(f"\n兑现速度（相对 4h 做空 pnl 的百分比）:")
    print(f"{'Horizon':10s} {'低 ATR %':>10s} {'中 ATR %':>10s} {'高 ATR %':>10s}")
    refs = {}
    for atr_range, atr_lbl in [((0, 0.33), "low"), ((0.33, 0.67), "mid"), ((0.67, 1.01), "high")]:
        seg = base_mh[(base_mh["atr_rank_roll"] >= atr_range[0]) &
                       (base_mh["atr_rank_roll"] < atr_range[1])]
        if len(seg) < 20:
            refs[atr_lbl] = np.nan
        else:
            refs[atr_lbl] = -seg["ret_4h"].mean() * 1e4
    for h_name in ["1h", "2h", "3h", "4h", "6h", "8h"]:
        col = f"ret_{h_name}"
        pcts = []
        for atr_range, atr_lbl in [((0, 0.33), "low"), ((0.33, 0.67), "mid"), ((0.67, 1.01), "high")]:
            seg = base_mh[(base_mh["atr_rank_roll"] >= atr_range[0]) &
                           (base_mh["atr_rank_roll"] < atr_range[1])]
            if len(seg) < 20 or refs[atr_lbl] == 0:
                pcts.append(np.nan)
            else:
                pcts.append(-seg[col].mean() * 1e4 / refs[atr_lbl] * 100)
        print(f"{h_name:10s} {pcts[0]:>10.1f} {pcts[1]:>10.1f} {pcts[2]:>10.1f}")

    # ============================================
    # 维度 3 · 跨品种保留度
    # ============================================
    print("\n" + "=" * 100)
    print("维度 3 · 跨品种保留度对比")
    print("=" * 100)

    for lbl, g in [("低 ATR", low), ("中 ATR", mid), ("高 ATR", high)]:
        g = g.copy()
        g["prefix"] = g["contract"].apply(parse_prefix)
        print(f"\n【{lbl} · n={len(g)}】")
        rows = []
        for p, gp in g.groupby("prefix"):
            if len(gp) < 5:
                continue
            rows.append({"prefix": p, "n": len(gp),
                         "mean": gp["short_pnl_4h_bps"].mean(),
                         "hit": (gp["short_pnl_4h_bps"] > 0).mean()})
        if not rows:
            print("  无有效品种")
            continue
        pdf = pd.DataFrame(rows).sort_values("mean", ascending=False)
        for _, r in pdf.iterrows():
            print(f"  {r['prefix']:6s} n={int(r['n']):>4d} mean={r['mean']:>+8.2f} hit={r['hit']:>6.1%}")
        n_pos = (pdf["mean"] > 0).sum()
        print(f"  正 mean: {n_pos}/{len(pdf)} = {n_pos/max(1,len(pdf)):.1%}")

    # ============================================
    # 维度 4 · 机制判读
    # ============================================
    print("\n" + "=" * 100)
    print("维度 4 · 机制判读")
    print("=" * 100)

    low_stats = describe_distribution(low["short_pnl_4h_bps"], "low")
    mid_stats = describe_distribution(mid["short_pnl_4h_bps"], "mid")
    high_stats = describe_distribution(high["short_pnl_4h_bps"], "high")

    print("\n对比表：")
    print(f"  {'指标':20s} {'低 ATR':>10s} {'中 ATR':>10s} {'高 ATR':>10s}")
    for k in ["mean", "std", "skew", "kurt", "p95", "p05", "payoff", "hit", "avg_win", "avg_loss"]:
        if k == "hit":
            print(f"  {k:20s} {low_stats[k]:>10.1%} {mid_stats[k]:>10.1%} {high_stats[k]:>10.1%}")
        else:
            print(f"  {k:20s} {low_stats[k]:>+10.2f} {mid_stats[k]:>+10.2f} {high_stats[k]:>+10.2f}")

    print("\n判据（与洞察 P 的多头对比）:")
    diff_skew = abs(high_stats["skew"] - low_stats["skew"])
    diff_kurt = abs(high_stats["kurt"] - low_stats["kurt"])
    diff_payoff = abs(high_stats["payoff"] - low_stats["payoff"])
    print(f"  低 vs 高 · |skew 差| = {diff_skew:.2f}")
    print(f"  低 vs 高 · |kurt 差| = {diff_kurt:.2f}")
    print(f"  低 vs 高 · |payoff 差| = {diff_payoff:.2f}")

    print("""
判读结论候选：
  假设 A · 多机制（如多头）：低/中/高 ATR 是 3 种不同机制
  假设 B · 单机制（高 ATR 独占）：低/中 ATR 完全无信号 · 只有高 ATR 有效
""")

    # 保存
    all_dists = pd.DataFrame([low_stats, mid_stats, high_stats])
    all_dists.to_csv(LOG_DIR / "task4_short_mechanism.csv", index=False)
    print(f"输出：{LOG_DIR / 'task4_short_mechanism.csv'}")


if __name__ == "__main__":
    main()
