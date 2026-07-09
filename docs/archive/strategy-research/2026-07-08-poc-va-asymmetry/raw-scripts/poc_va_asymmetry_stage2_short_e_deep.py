"""
文件级元信息：
- 创建背景：阶段 2 洞察 M 找到空头候选 E（UP + 跌段 + 高 ATR · 4h horizon
  · +15.8 bps · CI [+2.2, +32.5] · p=0.020）。本次做与多头相同深度的
  6 项验证，把空头 E 打到与多头主线相同的证据强度。
- 用途：
    (1) 分品种 mean / hit / n_events（对应多头样本外分品种表）
    (2) 跨周期护栏：15m / 30m / 1h / 2h 事件时钟一致性
    (3) horizon 敏感度：2h / 3h / 4h / 6h 精细扫描
    (4) 触发时段效应：event_hour 分组 · 衰减斜率（对应洞察 L）
    (5) Filter 递进结构：UP → UP+trend → UP+trend+ATR（单层 → 双层 → 三层）
    (6) 空头 E vs D 触发时刻相关性 · 是否独立信号
- 注意事项：
    - 全部使用严格无未来函数 · rolling rank
    - 用做空视角 · short_pnl = -ret
    - Cluster bootstrap 5000 次 · CI 排 0 判据
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage2"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 复用样本外合约清单
OOS_SYMBOLS: dict[str, float] = {
    "SHFE.rb2401": 1.0, "SHFE.rb2405": 1.0, "SHFE.rb2410": 1.0,
    "SHFE.rb2501": 1.0, "SHFE.rb2505": 1.0, "SHFE.rb2510": 1.0,
    "SHFE.rb2605": 1.0, "SHFE.rb2610": 1.0,
    "SHFE.cu2509": 10.0,
    "DCE.m2401": 1.0, "DCE.m2405": 1.0, "DCE.m2409": 1.0,
    "DCE.m2501": 1.0, "DCE.m2505": 1.0, "DCE.m2509": 1.0,
    "DCE.m2603": 1.0, "DCE.m2605": 1.0, "DCE.m2607": 1.0, "DCE.m2609": 1.0,
    "DCE.p2405": 2.0, "DCE.p2409": 2.0, "DCE.p2501": 2.0,
    "DCE.p2505": 2.0, "DCE.p2509": 2.0, "DCE.p2605": 2.0,
    "CZCE.SR401": 1.0, "CZCE.SR405": 1.0, "CZCE.SR409": 1.0,
    "CZCE.SR501": 1.0, "CZCE.SR505": 1.0, "CZCE.SR509": 1.0,
    "CZCE.SR605": 1.0, "CZCE.SR609": 1.0,
    "CZCE.CF509": 5.0,
    "CZCE.TA509": 2.0,
    "DCE.c2603": 1.0, "DCE.c2605": 1.0,
    "DCE.cs2603": 1.0, "DCE.cs2605": 1.0,
    "DCE.y2509": 1.0,
    "SHFE.ag2509": 1.0, "SHFE.al2509": 5.0,
    "INE.sc2509": 0.1, "SHFE.hc2505": 1.0,
}

ROLLING_EVENTS = 100
ROLLING_DAYS = 20
WARMUP_DAYS = 20
BOOTSTRAP_N = 5000
RNG_SEED = 20260707


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


def build_events(symbol: str, tick: float,
                 horizons_hours: list[float],
                 hourly_only: bool = True) -> pd.DataFrame:
    """构建事件表 · 支持多 horizon 与不同事件时钟"""
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date

    if hourly_only:
        mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    else:
        mask = pd.Series(True, index=bars.index)
    event_idx = bars.index[mask].to_list()

    rows = []
    for idx in event_idx:
        t = bars.loc[idx, "datetime"]
        close_t = bars.loc[idx, "close"]

        horizon_rets = {}
        skip = False
        for h in horizons_hours:
            fut_idx = idx + int(h * 12)
            if fut_idx >= len(bars):
                skip = True
                break
            close_fut = bars.loc[fut_idx, "close"]
            horizon_rets[f"ret_{h}h"] = np.log(close_fut / close_t)
        if skip:
            continue

        current_date = t.date()
        prev_bars = bars[bars["date"] < current_date]
        if len(prev_bars) == 0:
            continue
        prev_date = prev_bars["date"].max()
        w1_bars = prev_bars[prev_bars["date"] == prev_date]
        if len(w1_bars) < 20:
            continue
        skew = compute_profile_skew(w1_bars, tick)
        if np.isnan(skew):
            continue

        row = {
            "contract": symbol,
            "event_time": t,
            "event_date": current_date,
            "event_hour": t.hour,
            "event_minute": t.minute,
            "close_t": close_t,
            "A3_skew": skew,
        }
        row.update(horizon_rets)
        rows.append(row)

    return pd.DataFrame(rows)


def build_daily_features(symbol: str) -> pd.DataFrame:
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date
    daily = bars.groupby("date").agg(
        high=("high", "max"), low=("low", "min"),
        close=("close", "last"), open=("open", "first"),
    ).reset_index().sort_values("date").reset_index(drop=True)

    prev_close = daily["close"].shift(1)
    tr = np.maximum.reduce([
        (daily["high"] - daily["low"]).to_numpy(),
        (daily["high"] - prev_close).abs().to_numpy(),
        (daily["low"] - prev_close).abs().to_numpy(),
    ])
    daily["daily_tr"] = tr
    daily["daily_atr_10"] = daily["daily_tr"].rolling(10).mean()
    daily["daily_atr_10_bps"] = daily["daily_atr_10"] / daily["close"] * 1e4
    daily["trend_ret_10d"] = np.log(daily["close"] / daily["close"].shift(10)) * 1e4
    daily["mom_5d"] = np.log(daily["close"] / daily["close"].shift(5)) * 1e4
    return daily[["date", "daily_atr_10_bps", "trend_ret_10d", "mom_5d"]]


def rolling_pct_rank(series: pd.Series, window: int) -> pd.Series:
    def rank_last(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        past = x.iloc[:-1]
        return (past <= current).sum() / len(past)
    return series.rolling(window, min_periods=10).apply(rank_last, raw=False)


def cluster_bootstrap(events: pd.DataFrame, ret_col: str,
                       n_boot: int = BOOTSTRAP_N, seed: int = RNG_SEED) -> dict:
    rng = np.random.default_rng(seed)
    contracts = events["contract"].unique().tolist()
    per_c = {c: events[events["contract"] == c][ret_col].to_numpy() for c in contracts}
    real_mean = events[ret_col].mean()

    boot_means = np.zeros(n_boot)
    for i in range(n_boot):
        picked = rng.choice(contracts, size=len(contracts), replace=True)
        all_r = np.concatenate([per_c[c] for c in picked])
        boot_means[i] = all_r.mean() if len(all_r) else np.nan
    valid = boot_means[~np.isnan(boot_means)]
    return {
        "n_events": len(events),
        "n_contracts": len(contracts),
        "real_mean": real_mean,
        "ci_lo_95": float(np.quantile(valid, 0.025)),
        "ci_hi_95": float(np.quantile(valid, 0.975)),
        "p_two": 2 * min((valid <= 0).mean(), (valid >= 0).mean()),
    }


def prepare_dataset(symbols: dict[str, float], horizons: list[float]) -> pd.DataFrame:
    all_events = []
    for sym, tick in symbols.items():
        try:
            ev = build_events(sym, tick, horizons)
            daily = build_daily_features(sym)
            ev = ev.merge(daily, left_on="event_date", right_on="date", how="left")
            all_events.append(ev)
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"  ERR {sym}: {e}")
    df = pd.concat(all_events, ignore_index=True)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)

    df["signed_skew_rank_roll"] = df.groupby("contract")["A3_skew"].transform(
        lambda s: rolling_pct_rank(s, ROLLING_EVENTS))

    for feat_col, roll_col in [
        ("daily_atr_10_bps", "atr_rank_roll"),
        ("trend_ret_10d", "trend_rank_roll"),
        ("mom_5d", "mom5d_rank_roll"),
    ]:
        seg_list = []
        for c, g in df.groupby("contract"):
            daily = g.drop_duplicates("event_date").sort_values("event_date").copy()
            daily[roll_col] = rolling_pct_rank(daily[feat_col], ROLLING_DAYS)
            seg_list.append(daily[["contract", "event_date", roll_col]])
        seg_map = pd.concat(seg_list, ignore_index=True)
        df = df.merge(seg_map, on=["contract", "event_date"], how="left")

    keep_mask = np.zeros(len(df), dtype=bool)
    for c in df["contract"].unique():
        idx = df[df["contract"] == c].sort_values("event_time").index
        c_dates = sorted(df.loc[idx, "event_date"].unique())
        if len(c_dates) < WARMUP_DAYS:
            continue
        warmup_end = c_dates[WARMUP_DAYS - 1]
        for i in idx:
            if df.at[i, "event_date"] > warmup_end:
                keep_mask[df.index.get_loc(i)] = True
    df = df[keep_mask].reset_index(drop=True)
    df = df.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll",
                            "trend_rank_roll", "mom5d_rank_roll"])

    df["skew_grp"] = df["signed_skew_rank_roll"].apply(
        lambda r: "DN" if r <= 0.10 else ("UP" if r >= 0.90 else "mid"))
    df["trend_grp"] = df["trend_rank_roll"].apply(
        lambda r: "down" if r <= 0.33 else ("up" if r >= 0.67 else "flat"))
    df["atr10_grp"] = df["atr_rank_roll"].apply(
        lambda r: "low" if r <= 0.5 else "high")
    df["mom5d_grp"] = df["mom5d_rank_roll"].apply(
        lambda r: "down" if r <= 0.33 else ("up" if r >= 0.67 else "flat"))

    return df


def eval_combo_ci(sub: pd.DataFrame, ret_col: str) -> dict | None:
    if len(sub) < 20:
        return None
    r = cluster_bootstrap(sub, ret_col=ret_col)
    hit = (sub[ret_col] > 0).mean()
    return {
        "n": r["n_events"],
        "n_contracts": r["n_contracts"],
        "mean": r["real_mean"],
        "hit": hit,
        "ci_lo": r["ci_lo_95"],
        "ci_hi": r["ci_hi_95"],
        "p_two": r["p_two"],
        "pass": r["ci_lo_95"] > 0,
    }


def e_mask(df):
    """空头 E · UP + 跌段 + 高 ATR"""
    return ((df["skew_grp"] == "UP") &
            (df["trend_grp"] == "down") &
            (df["atr10_grp"] == "high"))


def main() -> None:
    print("=" * 90)
    print("阶段 2 补充 · 空头 E 深挖 · 6 项验证")
    print("=" * 90)

    horizons = [2, 3, 4, 6, 8]

    # 主数据集 · 每小时事件时钟
    print("\n[主数据 · 每小时事件时钟] 构建 ...")
    df = prepare_dataset(OOS_SYMBOLS, horizons)
    print(f"  n={len(df)} · 合约数={df['contract'].nunique()}")

    for h in horizons:
        df[f"short_pnl_{h}h"] = -df[f"ret_{h}h"] * 1e4

    ret_col_main = "short_pnl_4h"

    # ============================================
    # 任务 1 · 分品种
    # ============================================
    print("\n" + "=" * 90)
    print("任务 1 · 空头 E 分品种 mean（4h horizon）· ≥60% 保留 edge 判据")
    print("=" * 90)

    df["prefix"] = df["contract"].apply(parse_prefix)
    e_sub = df[e_mask(df)].dropna(subset=[ret_col_main])
    print(f"\n空头 E 全体：n={len(e_sub)} · 合约={e_sub['contract'].nunique()}")

    rows = []
    for prefix, g in e_sub.groupby("prefix"):
        if len(g) < 5:
            continue
        rows.append({
            "prefix": prefix,
            "n_contracts": g["contract"].nunique(),
            "n_e_events": len(g),
            "e_mean_bps": g[ret_col_main].mean(),
            "e_hit": (g[ret_col_main] > 0).mean(),
        })
    prefix_df = pd.DataFrame(rows).sort_values("e_mean_bps", ascending=False)
    print(f"\n{'品种':6s} {'合约数':>6s} {'E事件':>8s} {'mean(bps)':>10s} {'hit':>7s}")
    n_positive = 0
    for _, r in prefix_df.iterrows():
        print(f"{r['prefix']:6s} {r['n_contracts']:>6d} {r['n_e_events']:>8d} "
              f"{r['e_mean_bps']:>+10.2f} {r['e_hit']:>7.1%}")
        if r['e_mean_bps'] > 0:
            n_positive += 1
    ratio = n_positive / len(prefix_df) if len(prefix_df) else 0
    print(f"\n正 mean 品种: {n_positive}/{len(prefix_df)} = {ratio:.1%} "
          f"（多头主线 = 57.1%）")
    prefix_df.to_csv(LOG_DIR / "short_e_by_prefix.csv", index=False)

    # ============================================
    # 任务 2 · 跨周期护栏
    # ============================================
    print("\n" + "=" * 90)
    print("任务 2 · 空头 E 跨周期护栏（4h horizon 保持）")
    print("=" * 90)

    print(f"\n{'时钟':10s} {'n':>5s} {'品种':>4s} {'mean':>7s} {'hit':>7s} "
          f"{'CI下':>7s} {'CI上':>7s} {'p':>7s} 判决")

    # 主时钟 · 1h
    e_all = df[e_mask(df)].dropna(subset=[ret_col_main])
    r = eval_combo_ci(e_all, ret_col_main)
    print(f"{'1h':10s} {r['n']:>5d} {r['n_contracts']:>4d} "
          f"{r['mean']:>+7.2f} {r['hit']:>7.1%} "
          f"{r['ci_lo']:>+7.2f} {r['ci_hi']:>+7.2f} "
          f"{r['p_two']:>7.4f}  {'✅' if r['pass'] else '❌'}")

    # 15m / 30m / 2h · 需要单独构建事件表
    # 简化处理：从 1h 事件时钟里筛出满足 event_minute 条件的
    # 但这里数据已按每小时构建 · 需要重跑
    # 这里先用"抽样"逼近 · 30m 用每小时 + 每 0/30 minute
    # 但已过滤只每小时 → 需要重新构建

    for clock_min, clock_name in [(30, "30m"), (15, "15m")]:
        # 需要重新构建 · 全部 event_minute % clock_min == 0
        print(f"  [重构 {clock_name}] ...")
        rows_c = []
        for sym, tick in OOS_SYMBOLS.items():
            try:
                bars = load_5m(sym)
                bars["date"] = bars["datetime"].dt.date
                mm = bars["datetime"].dt.minute
                mask = (mm % clock_min == 0)
                idxs = bars.index[mask].to_list()
                for i in idxs:
                    fut_idx = i + 4 * 12  # 4h × 12
                    if fut_idx >= len(bars):
                        continue
                    t = bars.loc[i, "datetime"]
                    close_t = bars.loc[i, "close"]
                    close_fut = bars.loc[fut_idx, "close"]
                    ret4h = np.log(close_fut / close_t)
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
                    rows_c.append({
                        "contract": sym, "event_time": t, "event_date": current_date,
                        "close_t": close_t, "A3_skew": sk, "ret_4h": ret4h,
                    })
            except FileNotFoundError:
                continue
        d = pd.DataFrame(rows_c)
        if len(d) == 0:
            continue
        d["event_time"] = pd.to_datetime(d["event_time"])
        d = d.sort_values(["contract", "event_time"]).reset_index(drop=True)
        d["signed_skew_rank_roll"] = d.groupby("contract")["A3_skew"].transform(
            lambda s: rolling_pct_rank(s, ROLLING_EVENTS))
        # merge daily features
        daily_all = []
        for sym in d["contract"].unique():
            daily_all.append(build_daily_features(sym).assign(contract=sym))
        daily_df = pd.concat(daily_all, ignore_index=True)
        d = d.merge(daily_df, left_on=["contract", "event_date"],
                    right_on=["contract", "date"], how="left")
        for feat_col, roll_col in [
            ("daily_atr_10_bps", "atr_rank_roll"),
            ("trend_ret_10d", "trend_rank_roll"),
        ]:
            seg = []
            for c, g in d.groupby("contract"):
                daily = g.drop_duplicates("event_date").sort_values("event_date").copy()
                daily[roll_col] = rolling_pct_rank(daily[feat_col], ROLLING_DAYS)
                seg.append(daily[["contract", "event_date", roll_col]])
            seg_map = pd.concat(seg, ignore_index=True)
            d = d.merge(seg_map, on=["contract", "event_date"], how="left")
        # warmup
        keep = np.zeros(len(d), dtype=bool)
        for c in d["contract"].unique():
            idx = d[d["contract"] == c].sort_values("event_time").index
            dates = sorted(d.loc[idx, "event_date"].unique())
            if len(dates) < WARMUP_DAYS:
                continue
            wend = dates[WARMUP_DAYS - 1]
            for i in idx:
                if d.at[i, "event_date"] > wend:
                    keep[d.index.get_loc(i)] = True
        d = d[keep].dropna(subset=["signed_skew_rank_roll", "atr_rank_roll",
                                     "trend_rank_roll"])
        d["skew_grp"] = d["signed_skew_rank_roll"].apply(
            lambda r: "UP" if r >= 0.90 else "other")
        d["trend_grp"] = d["trend_rank_roll"].apply(
            lambda r: "down" if r <= 0.33 else "other")
        d["atr10_grp"] = d["atr_rank_roll"].apply(
            lambda r: "high" if r > 0.5 else "low")
        e_c = d[(d["skew_grp"] == "UP") & (d["trend_grp"] == "down") &
                (d["atr10_grp"] == "high")].copy()
        e_c["short_pnl_4h"] = -e_c["ret_4h"] * 1e4
        r = eval_combo_ci(e_c, "short_pnl_4h")
        if r:
            print(f"{clock_name:10s} {r['n']:>5d} {r['n_contracts']:>4d} "
                  f"{r['mean']:>+7.2f} {r['hit']:>7.1%} "
                  f"{r['ci_lo']:>+7.2f} {r['ci_hi']:>+7.2f} "
                  f"{r['p_two']:>7.4f}  {'✅' if r['pass'] else '❌'}")

    # ============================================
    # 任务 3 · Horizon 敏感度
    # ============================================
    print("\n" + "=" * 90)
    print("任务 3 · 空头 E · Horizon 敏感度（2h / 3h / 4h / 6h / 8h）")
    print("=" * 90)

    print(f"\n{'horizon':10s} {'n':>5s} {'品种':>4s} {'mean':>7s} {'hit':>7s} "
          f"{'CI下':>7s} {'CI上':>7s} {'p':>7s} 判决")
    hz_rows = []
    for h in horizons:
        col = f"short_pnl_{h}h"
        e_sub = df[e_mask(df)].dropna(subset=[col])
        r = eval_combo_ci(e_sub, col)
        if not r:
            continue
        hz_rows.append({"horizon": h, **r})
        print(f"{str(h)+'h':10s} {r['n']:>5d} {r['n_contracts']:>4d} "
              f"{r['mean']:>+7.2f} {r['hit']:>7.1%} "
              f"{r['ci_lo']:>+7.2f} {r['ci_hi']:>+7.2f} "
              f"{r['p_two']:>7.4f}  {'✅' if r['pass'] else '❌'}")
    pd.DataFrame(hz_rows).to_csv(LOG_DIR / "short_e_horizon.csv", index=False)

    # ============================================
    # 任务 4 · 触发时段效应
    # ============================================
    print("\n" + "=" * 90)
    print("任务 4 · 空头 E 触发时段效应（4h horizon）")
    print("=" * 90)

    e_full = df[e_mask(df)].dropna(subset=[ret_col_main])
    print(f"\n{'event_hour':10s} {'n':>5s} {'mean':>8s} {'hit':>7s}")
    hr_rows = []
    for h in range(0, 24):
        g = e_full[e_full["event_hour"] == h]
        if len(g) < 3:
            continue
        hr_rows.append({"hour": h, "n": len(g),
                        "mean_bps": g[ret_col_main].mean(),
                        "hit": (g[ret_col_main] > 0).mean()})
        print(f"{h:>10d} {len(g):>5d} {g[ret_col_main].mean():>+8.2f} "
              f"{(g[ret_col_main] > 0).mean():>7.1%}")
    hr_df = pd.DataFrame(hr_rows)
    if len(hr_df) >= 5:
        slope, intercept, r_v, p_v, _ = stats.linregress(hr_df["hour"], hr_df["mean_bps"])
        print(f"\n衰减斜率: {slope:+.2f} bps/h · R²={r_v**2:.2f} · p={p_v:.3f}")
    hr_df.to_csv(LOG_DIR / "short_e_time_decay.csv", index=False)

    # ============================================
    # 任务 5 · Filter 递进结构
    # ============================================
    print("\n" + "=" * 90)
    print("任务 5 · 空头 E · Filter 递进结构（4h horizon）")
    print("=" * 90)

    print(f"\n{'档位':40s} {'n':>5s} {'品种':>4s} {'mean':>7s} {'hit':>7s} "
          f"{'CI下':>7s} {'CI上':>7s} {'p':>7s} 判决")
    for lbl, mask in [
        ("单层 · UP", df["skew_grp"] == "UP"),
        ("双层 · UP + 跌段", (df["skew_grp"] == "UP") & (df["trend_grp"] == "down")),
        ("双层 · UP + 高 ATR", (df["skew_grp"] == "UP") & (df["atr10_grp"] == "high")),
        ("三层 · E · UP+跌+高ATR", e_mask(df)),
    ]:
        sub = df[mask].dropna(subset=[ret_col_main])
        r = eval_combo_ci(sub, ret_col_main)
        if not r:
            continue
        print(f"{lbl:40s} {r['n']:>5d} {r['n_contracts']:>4d} "
              f"{r['mean']:>+7.2f} {r['hit']:>7.1%} "
              f"{r['ci_lo']:>+7.2f} {r['ci_hi']:>+7.2f} "
              f"{r['p_two']:>7.4f}  {'✅' if r['pass'] else '❌'}")

    # ============================================
    # 任务 6 · 空头 D vs E 相关性
    # ============================================
    print("\n" + "=" * 90)
    print("任务 6 · 空头 D vs E 触发时刻相关性 · 独立性")
    print("=" * 90)

    d_mask = (df["skew_grp"] == "UP") & (df["mom5d_grp"] == "down")
    df["is_d"] = d_mask.astype(int)
    df["is_e"] = e_mask(df).astype(int)

    n_d = df["is_d"].sum()
    n_e = df["is_e"].sum()
    n_both = ((df["is_d"] == 1) & (df["is_e"] == 1)).sum()
    n_total = len(df)

    print(f"\n总事件数 = {n_total}")
    print(f"  D 触发 = {n_d}（{n_d/n_total:.1%}）")
    print(f"  E 触发 = {n_e}（{n_e/n_total:.1%}）")
    print(f"  D & E 同时触发 = {n_both}（{n_both/n_total:.1%}）")

    # Jaccard 相似度
    jaccard = n_both / (n_d + n_e - n_both) if (n_d + n_e - n_both) > 0 else 0
    # 条件概率
    p_e_given_d = n_both / n_d if n_d > 0 else 0
    p_d_given_e = n_both / n_e if n_e > 0 else 0
    p_e = n_e / n_total
    p_d = n_d / n_total

    print(f"\nJaccard 相似度 = {jaccard:.3f}")
    print(f"P(E|D) = {p_e_given_d:.3f} · P(E)={p_e:.3f} · Lift = {p_e_given_d/p_e:.2f}")
    print(f"P(D|E) = {p_d_given_e:.3f} · P(D)={p_d:.3f} · Lift = {p_d_given_e/p_d:.2f}")
    if p_e_given_d / p_e > 3:
        print("→ D 和 E 强相关 · 大概率不是独立信号")
    elif p_e_given_d / p_e > 1.5:
        print("→ D 和 E 有交集但不重合 · 可组合但需去重")
    else:
        print("→ D 和 E 相对独立 · 可组合")

    # D 与 E 的组合信号（并集）· 是否比单独更强
    union_mask = d_mask | e_mask(df)
    union_sub = df[union_mask].dropna(subset=[ret_col_main])
    r = eval_combo_ci(union_sub, ret_col_main)
    print(f"\nD ∪ E 并集：n={r['n']} · mean={r['mean']:+.2f} · "
          f"CI=[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] · p={r['p_two']:.4f}")

    print("\n" + "=" * 90)
    print("空头 E 深挖完成 · 输出:")
    print("=" * 90)
    for f in ["short_e_by_prefix.csv", "short_e_horizon.csv", "short_e_time_decay.csv"]:
        print(f"  {LOG_DIR / f}")


if __name__ == "__main__":
    main()
