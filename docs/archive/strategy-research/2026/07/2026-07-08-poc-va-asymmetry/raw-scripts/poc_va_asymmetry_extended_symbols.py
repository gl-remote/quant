"""
文件级元信息：
- 创建背景：现有 10 合约样本量太小（UP 侧 79 事件 · DN 侧 87 事件），
  UP 侧条件 alpha 检验 r≈0，需要更多合约样本才能判断"UP 侧真无信号"
  还是"UP 侧样本量不足"。本脚本用扩展合约集重新做 UP + DN 双侧条件 alpha
  诊断。
- 用途：
    (1) 扩展合约到 ~19 个（原 10 + c/y/ag/hc/MA/OI/RM/FG/cs）
    (2) 全部按 W1 × A3_skew × 每小时事件构建 5m profile → skew → ret_8h
    (3) 分别做 UP 与 DN 侧的：
         - 全环境 pooled 分布形态（含分位数 + skew + kurt + payoff）
         - 跨合约条件 alpha (baseline_mean vs group_mean) 相关性
         - 段内 15 天条件 alpha 相关性 + Q1/Q2/Q3 分档
    (4) 对比原 10 合约 vs 扩展 19 合约的结果
- 注意事项：会重跑 profile 构建（3-5 分钟）；ret_8h 单位 bps；
  避免污染 stage1 长表，直接把结果写到独立 CSV
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)

# 原 10 合约 + 扩展 9 合约
EXTENDED_SYMBOLS: dict[str, float] = {
    # 原 10
    "SHFE.rb2601": 1.0,
    "DCE.i2601": 0.5,
    "SHFE.cu2601": 10.0,
    "SHFE.al2601": 5.0,
    "INE.sc2512": 0.1,
    "CZCE.TA601": 2.0,
    "DCE.m2601": 1.0,
    "DCE.p2601": 2.0,
    "CZCE.SR601": 1.0,
    "CZCE.CF601": 5.0,
    # 扩展 9
    "DCE.c2601": 1.0,      # 玉米
    "DCE.y2601": 1.0,      # 豆油
    "DCE.cs2601": 1.0,     # 玉米淀粉
    "SHFE.ag2601": 1.0,    # 白银
    "SHFE.hc2510": 1.0,    # 热卷（10 月主力）
    "CZCE.MA601": 1.0,     # 甲醇
    "CZCE.OI601": 1.0,     # 菜油
    "CZCE.RM601": 1.0,     # 菜粕
    "CZCE.FG601": 1.0,     # 玻璃
}

VALUE_AREA_RATIO = 0.70
K_SIGMA = 1.5
DEDUP_GAP_HOURS = 8.0
FUTURE_HORIZON_BARS = 96  # 8h × 12 根 5m
SEGMENT_SIZE_DAYS = 15


def parse_prefix(symbol: str) -> str:
    _, contract = symbol.split(".")
    return "".join(c for c in contract if c.isalpha())


def load_5m(symbol: str) -> pd.DataFrame:
    path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def compute_profile_skew(bars: pd.DataFrame, tick: float) -> float:
    """给定 5m bar 序列，用 close-based bucket + volume 加权算三阶矩 skew。"""
    if len(bars) == 0 or bars["volume"].sum() <= 0:
        return np.nan
    buckets = (bars["close"] / tick).round() * tick
    grouped = bars.groupby(buckets)["volume"].sum()
    prices = grouped.index.to_numpy()
    vols = grouped.to_numpy()
    total = vols.sum()
    if total <= 0:
        return np.nan
    w = vols / total
    mean = (prices * w).sum()
    var = ((prices - mean) ** 2 * w).sum()
    if var <= 0:
        return np.nan
    std = np.sqrt(var)
    skew = (((prices - mean) / std) ** 3 * w).sum()
    return skew


def build_events_for_symbol(symbol: str) -> pd.DataFrame:
    """构建每小时事件表：per event → (W1 skew, ret_8h)。"""
    tick = EXTENDED_SYMBOLS[symbol]
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date

    # 每小时整点事件
    hourly_mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    hourly_idx = bars.index[hourly_mask].to_list()

    rows = []
    for idx in hourly_idx:
        t = bars.loc[idx, "datetime"]
        close_t = bars.loc[idx, "close"]

        # 未来 8h close
        fut_idx = idx + FUTURE_HORIZON_BARS
        if fut_idx >= len(bars):
            continue
        close_fut = bars.loc[fut_idx, "close"]

        # W1 profile: 前一交易日全部 5m bar
        current_date = t.date()
        prev_bars = bars[bars["date"] < current_date]
        if len(prev_bars) == 0:
            continue
        # 找到最近一个交易日
        prev_date = prev_bars["date"].max()
        w1_bars = prev_bars[prev_bars["date"] == prev_date]
        if len(w1_bars) < 20:
            continue
        skew = compute_profile_skew(w1_bars, tick)
        if np.isnan(skew):
            continue

        rows.append({
            "contract": symbol,
            "event_time": t,
            "close_t": close_t,
            "A3_skew": skew,
            "ret_8h": np.log(close_fut / close_t),
        })

    return pd.DataFrame(rows)


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def analyze_side(all_events: pd.DataFrame, symbols: list[str], side: str) -> None:
    """side: 'DN' 或 'UP'。做完整的分布 + 条件 alpha 诊断。"""
    print(f"\n\n{'#'*90}")
    print(f"# {side} 侧诊断 · {len(symbols)} 合约")
    print(f"{'#'*90}")

    # 收集所有 UP/DN 事件
    dn_all = []
    up_all = []
    contract_stats = []

    for c in symbols:
        g = all_events[all_events["contract"] == c].copy()
        if len(g) < 20:
            continue
        skew = g["A3_skew"].dropna()
        std_c = skew.std()
        baseline = g["ret_8h"].dropna() * 1e4

        dn = g[g["A3_skew"] <= -K_SIGMA * std_c]
        up = g[g["A3_skew"] >= +K_SIGMA * std_c]
        dn_dedup = dedup_gap(dn, DEDUP_GAP_HOURS)
        up_dedup = dedup_gap(up, DEDUP_GAP_HOURS)

        dn_all.append(dn_dedup)
        up_all.append(up_dedup)

        r_dn = dn_dedup["ret_8h"].dropna() * 1e4
        r_up = up_dedup["ret_8h"].dropna() * 1e4
        contract_stats.append({
            "contract": c,
            "n_baseline": len(baseline),
            "baseline_mean_bps": baseline.mean(),
            "n_dn": len(r_dn),
            "dn_mean_bps": r_dn.mean() if len(r_dn) else np.nan,
            "n_up": len(r_up),
            "up_mean_bps": r_up.mean() if len(r_up) else np.nan,
        })

    stats_df = pd.DataFrame(contract_stats).sort_values("baseline_mean_bps")

    # ============ 分布形态 ============
    if side == "DN":
        pooled = pd.concat(dn_all, ignore_index=True)
    else:
        pooled = pd.concat(up_all, ignore_index=True)
    r_pool = pooled["ret_8h"].dropna().to_numpy() * 1e4

    # 做空视角的 pnl（UP 侧才用）
    r_signal = r_pool.copy() if side == "DN" else -r_pool

    print(f"\n【全环境 pooled · {side} 侧】n = {len(r_pool)}")
    print(f"  裸对数收益 mean: {r_pool.mean():>+8.2f} bps")
    if side == "UP":
        print(f"  做空 pnl mean:   {(-r_pool.mean()):>+8.2f} bps  ← 假设 UP 侧策略 = 做空")
    print(f"  median:         {np.median(r_pool):>+8.2f} bps")
    print(f"  skewness:       {stats.skew(r_pool):>+8.3f}")
    print(f"  kurtosis:       {stats.kurtosis(r_pool):>+8.3f}")
    hit = (r_signal > 0).mean() if side == "UP" else (r_pool > 0).mean()
    print(f"  hit rate (signal win): {hit:>7.1%}")
    win_mask = r_signal > 0
    avg_win = r_signal[win_mask].mean() if win_mask.any() else float("nan")
    avg_loss = r_signal[~win_mask].mean() if (~win_mask).any() else float("nan")
    payoff = abs(avg_win / avg_loss) if avg_loss and not np.isnan(avg_loss) else float("nan")
    print(f"  avg winner:     {avg_win:>+8.2f} bps")
    print(f"  avg loser:      {avg_loss:>+8.2f} bps")
    print(f"  payoff ratio:   {payoff:>7.2f}")

    # ============ 方式 A · 跨合约 ============
    print(f"\n{'-'*90}")
    print(f"方式 A · 跨合约条件性")
    print(f"{'-'*90}")
    col = "dn_mean_bps" if side == "DN" else "up_mean_bps"
    valid = stats_df.dropna(subset=[col])
    print(f"\n{'contract':16s} {'n_base':>6s} {'baseline':>10s} {'n_'+side.lower():>5s} "
          f"{col+'':>12s}")
    for _, r in valid.iterrows():
        n_side = int(r["n_dn"] if side == "DN" else r["n_up"])
        print(f"{r['contract']:16s} {r['n_baseline']:>6d} {r['baseline_mean_bps']:>+10.2f} "
              f"{n_side:>5d} {r[col]:>+12.2f}")

    x = valid["baseline_mean_bps"].to_numpy()
    y = valid[col].to_numpy()
    if len(x) >= 3:
        pear = stats.pearsonr(x, y)
        spear = stats.spearmanr(x, y)
        print(f"\n(baseline_mean, {side.lower()}_mean) 相关系数 (n={len(x)}):")
        print(f"  Pearson  r={pear.statistic:+.3f}  p={pear.pvalue:.4f}")
        print(f"  Spearman r={spear.statistic:+.3f}  p={spear.pvalue:.4f}")
        slope, intercept, rv, pv, _ = stats.linregress(x, y)
        print(f"  线性回归: {side.lower()}_mean = {slope:+.3f} × baseline + {intercept:+.2f}")
        print(f"  R² = {rv**2:.3f}  p_slope = {pv:.4f}")
        if side == "DN":
            print(f"  假设: 若信号成立，斜率 > 0（涨段 → DN mean 更大 → 做多更赚）")
        else:
            print(f"  假设: 若做空 UP 有效，斜率 < 0（跌段 → UP mean 更负 → 做空更赚）")

    # ============ 方式 B · 段内 ============
    print(f"\n{'-'*90}")
    print(f"方式 B · 段内条件性（{SEGMENT_SIZE_DAYS} 天一段）")
    print(f"{'-'*90}")

    seg_rows = []
    for c in symbols:
        g = all_events[all_events["contract"] == c].copy()
        if len(g) < 20:
            continue
        g["date"] = pd.to_datetime(g["event_time"]).dt.date
        skew = g["A3_skew"].dropna()
        std_c = skew.std()
        thr = -K_SIGMA * std_c if side == "DN" else +K_SIGMA * std_c
        cond = (g["A3_skew"] <= thr) if side == "DN" else (g["A3_skew"] >= thr)

        all_dates = sorted(g["date"].unique())
        n_seg = max(1, len(all_dates) // SEGMENT_SIZE_DAYS)
        segments = np.array_split(all_dates, n_seg)

        for seg_idx, seg_dates in enumerate(segments):
            seg_set = set(seg_dates)
            seg_events = g[g["date"].isin(seg_set)]
            if len(seg_events) < 5:
                continue
            seg_base = seg_events["ret_8h"].dropna() * 1e4
            seg_side = seg_events[cond & g["date"].isin(seg_set)]
            seg_side_dedup = dedup_gap(seg_side, DEDUP_GAP_HOURS)
            r = seg_side_dedup["ret_8h"].dropna() * 1e4
            seg_rows.append({
                "contract": c, "seg_idx": seg_idx,
                "seg_baseline_mean_bps": seg_base.mean(),
                "n_side": len(r),
                "seg_side_mean_bps": r.mean() if len(r) else np.nan,
            })

    seg_df = pd.DataFrame(seg_rows)
    seg_valid = seg_df.dropna(subset=["seg_side_mean_bps"])
    seg_valid = seg_valid[seg_valid["n_side"] >= 2]
    print(f"\n有效段 (n_side>=2): {len(seg_valid)}")
    x = seg_valid["seg_baseline_mean_bps"].to_numpy()
    y = seg_valid["seg_side_mean_bps"].to_numpy()
    if len(x) >= 3:
        pear = stats.pearsonr(x, y)
        spear = stats.spearmanr(x, y)
        print(f"(seg_baseline_mean, seg_{side.lower()}_mean) 相关系数:")
        print(f"  Pearson  r={pear.statistic:+.3f}  p={pear.pvalue:.4f}")
        print(f"  Spearman r={spear.statistic:+.3f}  p={spear.pvalue:.4f}")

        seg_valid = seg_valid.sort_values("seg_baseline_mean_bps").reset_index(drop=True)
        seg_valid["bucket"] = pd.qcut(seg_valid["seg_baseline_mean_bps"], 3,
                                       labels=["Q1", "Q2", "Q3"])
        print(f"\n按段 baseline_mean 分 3 档:")
        print(f"{'bucket':10s} {'n_seg':>5s} {'base_avg':>12s} "
              f"{side.lower()+'_mean(w)':>15s} {'n_'+side.lower()+'_total':>15s}")
        for b in ["Q1", "Q2", "Q3"]:
            sub = seg_valid[seg_valid["bucket"] == b]
            if len(sub) == 0:
                continue
            w_mean = np.average(sub["seg_side_mean_bps"], weights=sub["n_side"])
            n_tot = int(sub["n_side"].sum())
            print(f"{b:10s} {len(sub):>5d} {sub['seg_baseline_mean_bps'].mean():>+12.2f} "
                  f"{w_mean:>+15.2f} {n_tot:>15d}")

    return stats_df, seg_df


def main() -> None:
    symbols = list(EXTENDED_SYMBOLS.keys())
    print(f"合约: {symbols}\n共 {len(symbols)} 个")

    print("\n构建事件表（每合约 5m → 每小时事件 · W1 profile · A3_skew · ret_8h）...")
    all_events_list = []
    for i, sym in enumerate(symbols):
        print(f"  [{i+1}/{len(symbols)}] {sym} ... ", end="", flush=True)
        try:
            ev = build_events_for_symbol(sym)
            all_events_list.append(ev)
            print(f"n={len(ev)}")
        except FileNotFoundError:
            print("SKIP (no CSV)")
        except Exception as e:
            print(f"ERR: {e}")

    all_events = pd.concat(all_events_list, ignore_index=True)
    out_path = LOG_DIR / "extended_long_events.csv"
    all_events.to_csv(out_path, index=False)
    print(f"\n总事件数: {len(all_events)} · 合约数: {all_events['contract'].nunique()}")
    print(f"保存: {out_path}")

    actual_symbols = sorted(all_events["contract"].unique().tolist())
    print(f"\n实际参与合约: {actual_symbols}")

    # 分别对 DN 和 UP 做完整诊断
    analyze_side(all_events, actual_symbols, "DN")
    analyze_side(all_events, actual_symbols, "UP")


if __name__ == "__main__":
    main()
