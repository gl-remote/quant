"""
文件级元信息：
- 创建背景：阶段 3 任务 2 补充深挖 · 任务 2 发现多头宽松（skew≤0.30 ·
  trend≥0.75）在高 ATR 反而更强（+45.6 vs 低 ATR +32.0）。用户假设：
  高低 ATR 下极限探底触发上涨可能是不同机制。
- 用途：
    (1) 收益分布形态对比：mean/median/std/skew/kurt/payoff/p05/p95
    (2) Horizon 敏感度对比：兑现时间是否不同（急速 vs 缓慢反弹）
    (3) 跨品种保留度对比：哪些品种在哪种机制下更有效
    (4) 触发时段对比：早盘/午后/夜盘的分布
    (5) 累计收益路径对比：1h/2h/4h/8h 兑现速度
- 假设检验：
    * 假设 A · 相同机制 · 只是波动率放大：高 ATR 组 std 更大 · 但 mean/hit/skew 一致
    * 假设 B · 不同机制 · 恐慌回补 vs 日常回归：高 ATR 组正偏 + 厚尾 + 慢兑现 · 低 ATR 组对称 + 稳定
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
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def describe_distribution(x, label):
    """描述性统计"""
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
        "p25": np.quantile(x, 0.25),
        "p75": np.quantile(x, 0.75),
        "p95": np.quantile(x, 0.95),
        "hit": (x > 0).mean(),
        "avg_win": wins.mean() if len(wins) else 0,
        "avg_loss": losses.mean() if len(losses) else 0,
        "payoff": payoff,
    }


def build_multi_horizon_events(symbol, tick):
    """构建含多 horizon 的事件表（1h/2h/4h/6h/8h）"""
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date
    mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    hourly_idx = bars.index[mask].to_list()
    rows = []
    for idx in hourly_idx:
        t = bars.loc[idx, "datetime"]
        close_t = bars.loc[idx, "close"]
        # 多 horizon
        horizons = {"1h": 12, "2h": 24, "4h": 48, "6h": 72, "8h": 96}
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
    print("任务 2 补充深挖 · 高低 ATR 下 DN 反弹机制对比")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()

    # 多头宽松基础条件（不含 ATR）
    base_mask = ((df["signed_skew_rank_roll"] <= 0.30) &
                 (df["trend_rank_roll"] >= 0.75))
    base = df[base_mask].dropna(subset=["ret_8h_bps"]).copy()
    base["event_hour"] = pd.to_datetime(base["event_time"]).dt.hour
    print(f"基础条件（skew≤0.30 + trend≥0.75）: n={len(base)}")

    # 分组
    low = base[base["atr_rank_roll"] <= 0.33].copy()
    mid = base[(base["atr_rank_roll"] > 0.33) & (base["atr_rank_roll"] < 0.67)].copy()
    high = base[base["atr_rank_roll"] >= 0.67].copy()
    print(f"  低 ATR: n={len(low)} · 中 ATR: n={len(mid)} · 高 ATR: n={len(high)}")

    # ============================================
    # 维度 1 · 收益分布形态对比
    # ============================================
    print("\n" + "=" * 100)
    print("维度 1 · 8h 收益分布形态对比")
    print("=" * 100)

    dists = [describe_distribution(g["ret_8h_bps"], lbl)
             for lbl, g in [("低 ATR", low), ("中 ATR", mid), ("高 ATR", high)]]

    print(f"\n{'指标':10s} {'低 ATR':>10s} {'中 ATR':>10s} {'高 ATR':>10s}  判读")
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
    # 维度 2 · Horizon 敏感度对比
    # ============================================
    print("\n" + "=" * 100)
    print("维度 2 · Horizon 敏感度（兑现速度）")
    print("=" * 100)

    # 需要多 horizon 数据 · 重新构建
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
    # 加 rolling rank
    from poc_va_asymmetry_stage2_grid_search import rolling_pct_rank, build_daily_features, ROLLING_EVENTS, ROLLING_DAYS, WARMUP_DAYS
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
    # warmup
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

    base_mh = df_mh[(df_mh["signed_skew_rank_roll"] <= 0.30) &
                    (df_mh["trend_rank_roll"] >= 0.75)]
    print(f"多 horizon 基础条件: n={len(base_mh)}")

    print(f"\n{'Horizon':10s} {'低 ATR mean':>12s} {'中 ATR mean':>12s} {'高 ATR mean':>12s}  {'兑现速度':10s}")
    for h_name in ["1h", "2h", "4h", "6h", "8h"]:
        col = f"ret_{h_name}"
        vals = []
        for atr_range in [(0, 0.33), (0.33, 0.67), (0.67, 1.01)]:
            seg = base_mh[(base_mh["atr_rank_roll"] >= atr_range[0]) &
                          (base_mh["atr_rank_roll"] < atr_range[1])]
            if len(seg) < 20:
                vals.append(np.nan)
            else:
                vals.append(seg[col].mean() * 1e4)
        print(f"{h_name:10s} {vals[0]:>+12.2f} {vals[1]:>+12.2f} {vals[2]:>+12.2f}")

    # 兑现速度 · 每 horizon 相对 8h 的百分比
    print(f"\n兑现速度（相对 8h 累计的百分比）:")
    print(f"{'Horizon':10s} {'低 ATR %':>10s} {'中 ATR %':>10s} {'高 ATR %':>10s}")
    ref_low = base_mh[base_mh["atr_rank_roll"] <= 0.33]["ret_8h"].mean() * 1e4
    ref_mid = base_mh[(base_mh["atr_rank_roll"] > 0.33) &
                       (base_mh["atr_rank_roll"] < 0.67)]["ret_8h"].mean() * 1e4
    ref_high = base_mh[base_mh["atr_rank_roll"] >= 0.67]["ret_8h"].mean() * 1e4
    for h_name in ["1h", "2h", "4h", "6h", "8h"]:
        col = f"ret_{h_name}"
        low_v = base_mh[base_mh["atr_rank_roll"] <= 0.33][col].mean() * 1e4
        mid_v = base_mh[(base_mh["atr_rank_roll"] > 0.33) &
                        (base_mh["atr_rank_roll"] < 0.67)][col].mean() * 1e4
        high_v = base_mh[base_mh["atr_rank_roll"] >= 0.67][col].mean() * 1e4
        print(f"{h_name:10s} {low_v/ref_low*100:>10.1f} {mid_v/ref_mid*100:>10.1f} "
              f"{high_v/ref_high*100:>10.1f}")

    # ============================================
    # 维度 3 · 跨品种保留度对比
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
                         "mean": gp["ret_8h_bps"].mean(),
                         "hit": (gp["ret_8h_bps"] > 0).mean()})
        pdf = pd.DataFrame(rows).sort_values("mean", ascending=False)
        for _, r in pdf.iterrows():
            print(f"  {r['prefix']:6s} n={int(r['n']):>4d} mean={r['mean']:>+8.2f} hit={r['hit']:>6.1%}")
        n_pos = (pdf["mean"] > 0).sum()
        print(f"  正 mean: {n_pos}/{len(pdf)} = {n_pos/max(1,len(pdf)):.1%}")

    # ============================================
    # 维度 4 · 触发时段分布
    # ============================================
    print("\n" + "=" * 100)
    print("维度 4 · 触发时段分布（8h ret · bps）")
    print("=" * 100)

    print(f"\n{'时段':15s} {'低 ATR n/mean':>18s} {'中 ATR n/mean':>18s} {'高 ATR n/mean':>18s}")
    hour_bands = [
        ("早盘 9-11", range(9, 12)),
        ("午后 13-14", [13, 14]),
        ("夜盘 21-23", range(21, 24)),
        ("凌晨 0-3", range(0, 4)),
    ]
    for lbl, hrs in hour_bands:
        vals = []
        for g in [low, mid, high]:
            seg = g[g["event_hour"].isin(hrs)]
            if len(seg) < 5:
                vals.append(f"n={len(seg)} 无效")
            else:
                vals.append(f"n={len(seg):3d} m={seg['ret_8h_bps'].mean():+7.1f}")
        print(f"{lbl:15s} {vals[0]:>18s} {vals[1]:>18s} {vals[2]:>18s}")

    # ============================================
    # 维度 5 · 累计收益路径的形态刻画
    # ============================================
    print("\n" + "=" * 100)
    print("维度 5 · 收益路径形态 · 高低 ATR 差异总结")
    print("=" * 100)

    # 判读逻辑
    low_stats = describe_distribution(low["ret_8h_bps"], "low")
    high_stats = describe_distribution(high["ret_8h_bps"], "high")

    print("\n判读表：")
    print(f"  {'指标':20s} {'低 ATR':>10s} {'高 ATR':>10s} 差异")
    print(f"  {'均值 mean':20s} {low_stats['mean']:>+10.2f} {high_stats['mean']:>+10.2f} "
          f"高 {'>' if high_stats['mean']>low_stats['mean'] else '<'} 低")
    print(f"  {'中位数 median':20s} {low_stats['median']:>+10.2f} {high_stats['median']:>+10.2f}")
    print(f"  {'std 波动':20s} {low_stats['std']:>10.2f} {high_stats['std']:>10.2f} "
          f"高/低 = {high_stats['std']/low_stats['std']:.2f}x")
    print(f"  {'skew 偏度':20s} {low_stats['skew']:>+10.2f} {high_stats['skew']:>+10.2f}")
    print(f"  {'kurt 峰度':20s} {low_stats['kurt']:>+10.2f} {high_stats['kurt']:>+10.2f}")
    print(f"  {'p95 右尾':20s} {low_stats['p95']:>+10.2f} {high_stats['p95']:>+10.2f}")
    print(f"  {'p05 左尾':20s} {low_stats['p05']:>+10.2f} {high_stats['p05']:>+10.2f}")
    print(f"  {'payoff 盈亏比':20s} {low_stats['payoff']:>10.2f} {high_stats['payoff']:>10.2f}")
    print(f"  {'avg_win 平均盈':20s} {low_stats['avg_win']:>+10.2f} {high_stats['avg_win']:>+10.2f}")
    print(f"  {'avg_loss 平均亏':20s} {low_stats['avg_loss']:>+10.2f} {high_stats['avg_loss']:>+10.2f}")

    print("\n机制判读：")
    print("  假设 A · 相同机制 · 波动率放大：高 ATR std 更大 · 但 skew/kurt/payoff 一致")
    print("  假设 B · 不同机制 · 恐慌回补 vs 日常回归：高 ATR 正偏 + 厚尾 + payoff 大 · 慢兑现")

    diff_skew = abs(high_stats["skew"] - low_stats["skew"])
    diff_kurt = abs(high_stats["kurt"] - low_stats["kurt"])
    diff_payoff = abs(high_stats["payoff"] - low_stats["payoff"])
    print(f"\n  |skew 差| = {diff_skew:.2f}（>0.5 说明形态不同）")
    print(f"  |kurt 差| = {diff_kurt:.2f}（>1 说明尾部形态不同）")
    print(f"  |payoff 差| = {diff_payoff:.2f}（>0.3 说明盈亏结构不同）")

    if (diff_skew > 0.5) or (diff_kurt > 1) or (diff_payoff > 0.3):
        print("\n  → 支持假设 B · 不同机制")
    else:
        print("\n  → 支持假设 A · 相同机制 · 只是波动率放大")

    # 保存
    all_dists = pd.DataFrame([
        describe_distribution(low["ret_8h_bps"], "low"),
        describe_distribution(mid["ret_8h_bps"], "mid"),
        describe_distribution(high["ret_8h_bps"], "high"),
    ])
    all_dists.to_csv(LOG_DIR / "task2_deep_dive_distribution.csv", index=False)
    print(f"\n输出：{LOG_DIR / 'task2_deep_dive_distribution.csv'}")


if __name__ == "__main__":
    main()
