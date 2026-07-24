"""
文件级元信息：
- 创建背景：阶段 2 门槛 1 · 跨周期护栏（KF-7 硬约束）。验证主线信号不
  依赖 1h 时钟采样。事件时钟改为 15m / 30m / 2h，profile 构建仍用 5m。
- 用途：读原 10 合约的 5m bar → 用不同事件时钟重跑主线三档 cluster CI
    时钟：15m / 30m / 1h（基线复现）/ 2h
    profile：始终用前一交易日 5m bar 建 W1
    未来 horizon：8h（固定不变，因为它才是真正的"信号覆盖时长"）
- 注意事项：dedup 也按 8h · 主线定义完全不变，只改采样密度
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage2"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 原 10 合约（阶段 1 主表）
SYMBOLS: dict[str, float] = {
    "SHFE.rb2601": 1.0, "DCE.i2601": 0.5, "SHFE.cu2601": 10.0,
    "SHFE.al2601": 5.0, "INE.sc2512": 0.1, "CZCE.TA601": 2.0,
    "DCE.m2601": 1.0, "DCE.p2601": 2.0, "CZCE.SR601": 1.0,
    "CZCE.CF601": 5.0,
}

VALUE_AREA_RATIO = 0.70
K_SIGMA = 1.5
DEDUP_GAP_HOURS = 8.0
FUTURE_HORIZON_BARS = 96      # 8h × 12 根 5m
ROLLING_EVENTS = 100
ROLLING_DAYS = 20
WARMUP_DAYS = 20
BOOTSTRAP_N = 5000
RNG_SEED = 20260707

# 事件时钟：分钟数（0 意味着每 X 分钟一个事件）
CLOCK_MINUTES = {
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
}


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
    return (((prices - mean) / std) ** 3 * w).sum()


def build_events_at_clock(symbol: str, clock_min: int) -> pd.DataFrame:
    tick = SYMBOLS[symbol]
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date

    # 事件时钟：datetime.minute 是 clock_min 的倍数 且 秒数为 0
    # 15m: minute in [0,15,30,45]  · 30m: [0,30]  · 1h: [0]  · 2h: hour%2==0 and minute==0
    if clock_min < 60:
        event_mask = (bars["datetime"].dt.minute % clock_min == 0) & \
                     (bars["datetime"].dt.second == 0)
    elif clock_min == 60:
        event_mask = (bars["datetime"].dt.minute == 0) & \
                     (bars["datetime"].dt.second == 0)
    elif clock_min == 120:
        event_mask = (bars["datetime"].dt.minute == 0) & \
                     (bars["datetime"].dt.hour % 2 == 0) & \
                     (bars["datetime"].dt.second == 0)
    else:
        raise ValueError(f"unsupported clock: {clock_min}")

    idx_list = bars.index[event_mask].to_list()

    rows = []
    for idx in idx_list:
        t = bars.loc[idx, "datetime"]
        close_t = bars.loc[idx, "close"]

        fut_idx = idx + FUTURE_HORIZON_BARS
        if fut_idx >= len(bars):
            continue
        close_fut = bars.loc[fut_idx, "close"]

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

        rows.append({
            "contract": symbol,
            "event_time": t,
            "event_date": current_date,
            "close_t": close_t,
            "A3_skew": skew,
            "ret_8h": np.log(close_fut / close_t),
        })
    return pd.DataFrame(rows)


def rolling_pct_rank(series: pd.Series, window: int) -> pd.Series:
    def rank_last(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        past = x.iloc[:-1]
        return (past <= current).sum() / len(past)
    return series.rolling(window, min_periods=10).apply(rank_last, raw=False)


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def cluster_bootstrap(events: pd.DataFrame, ret_col: str = "ret_bps",
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
    ci_lo = float(np.quantile(valid, 0.025))
    ci_hi = float(np.quantile(valid, 0.975))
    p_two = 2 * min((valid <= 0).mean(), (valid >= 0).mean())
    return {
        "n_events": len(events),
        "n_contracts": len(contracts),
        "real_mean": real_mean,
        "ci_lo_95": ci_lo,
        "ci_hi_95": ci_hi,
        "p_two": p_two,
    }


def process_clock(clock_label: str, clock_min: int) -> dict:
    print(f"\n{'='*90}")
    print(f"事件时钟: {clock_label} ({clock_min} 分钟)")
    print(f"{'='*90}")

    print("构建事件表 ...")
    all_events = []
    for i, sym in enumerate(SYMBOLS.keys()):
        ev = build_events_at_clock(sym, clock_min)
        all_events.append(ev)
        print(f"  [{i+1}/{len(SYMBOLS)}] {sym}  n={len(ev)}")

    df = pd.concat(all_events, ignore_index=True)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["ret_bps"] = df["ret_8h"] * 1e4
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)

    # rolling skew rank
    df["signed_skew_rank_roll"] = df.groupby("contract")["A3_skew"].transform(
        lambda s: rolling_pct_rank(s, ROLLING_EVENTS))

    # warmup 排除
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
    df = df.dropna(subset=["signed_skew_rank_roll"])

    # DN 事件 + dedup_8h
    dn = df[df["signed_skew_rank_roll"] <= 0.10]
    dedup_list = []
    for c, g in dn.groupby("contract"):
        d = dedup_gap(g, DEDUP_GAP_HOURS)
        dedup_list.append(d)
    dn_dedup = pd.concat(dedup_list, ignore_index=True) if dedup_list else pd.DataFrame(columns=dn.columns)

    # cluster bootstrap
    result = cluster_bootstrap(dn_dedup)
    hit = (dn_dedup["ret_bps"] > 0).mean()
    print(f"\nDN 单层 (skew rank ≤ 10% · rolling · dedup_8h):")
    print(f"  n={result['n_events']} · {result['n_contracts']} 合约 · hit={hit:.1%}")
    print(f"  mean = {result['real_mean']:+.2f} bps")
    print(f"  95% CI = [{result['ci_lo_95']:+.2f}, {result['ci_hi_95']:+.2f}]")
    print(f"  p_two = {result['p_two']:.4f}")
    judge = "✅ CI 排 0" if result['ci_lo_95'] > 0 else "❌ CI 触 0"
    print(f"  判读: {judge}")

    return {
        "clock": clock_label,
        "n_events": result['n_events'],
        "n_contracts": result['n_contracts'],
        "hit": hit,
        "mean_bps": result['real_mean'],
        "ci_lo_95": result['ci_lo_95'],
        "ci_hi_95": result['ci_hi_95'],
        "p_two": result['p_two'],
    }


def main() -> None:
    print("阶段 2 · 门槛 1 · 跨周期护栏（KF-7 硬门槛）")
    print(f"合约数: {len(SYMBOLS)} · 事件时钟档: {list(CLOCK_MINUTES.keys())}")

    results = []
    for label, m in CLOCK_MINUTES.items():
        r = process_clock(label, m)
        results.append(r)

    # 总结表
    print("\n\n" + "=" * 90)
    print("跨周期一致性汇总（DN 单层 rolling · dedup_8h · 未来 8h）")
    print("=" * 90)
    print(f"\n{'clock':6s} {'n':>6s} {'contracts':>10s} {'hit':>7s} "
          f"{'mean(bps)':>10s} {'CI_lo':>10s} {'CI_hi':>10s} {'p_two':>8s}")
    for r in results:
        print(f"{r['clock']:6s} {r['n_events']:>6d} {r['n_contracts']:>10d} "
              f"{r['hit']:>7.1%} {r['mean_bps']:>+10.2f} "
              f"{r['ci_lo_95']:>+10.2f} {r['ci_hi_95']:>+10.2f} "
              f"{r['p_two']:>8.4f}")

    # 判据
    print("\n判据（KF-7）:")
    print("  - 至少 30m/1h · 或 1h/2h 相邻周期方向一致（mean 同号 · CI 排 0）")
    print("  - 幅度差 ≤ 3 倍")
    print("  - 若跨周期方向反转 → KF-7 判决 · 主题冻结")

    # 一致性判断
    def same_sign_and_ratio_ok(r1: dict, r2: dict) -> tuple[bool, str]:
        if r1['mean_bps'] > 0 and r2['mean_bps'] > 0:
            same_sign = True
        elif r1['mean_bps'] < 0 and r2['mean_bps'] < 0:
            same_sign = True
        else:
            same_sign = False
        if not same_sign:
            return False, "方向反转"
        ratio = max(abs(r1['mean_bps']), abs(r2['mean_bps'])) / \
                max(min(abs(r1['mean_bps']), abs(r2['mean_bps'])), 1)
        if ratio > 3:
            return False, f"幅度差 {ratio:.1f}x > 3x"
        return True, "方向一致 · 幅度可比"

    print("\n相邻周期一致性检查:")
    for i in range(len(results) - 1):
        ok, note = same_sign_and_ratio_ok(results[i], results[i+1])
        mark = "✅" if ok else "⚠️"
        print(f"  {mark} {results[i]['clock']} vs {results[i+1]['clock']}: {note} "
              f"({results[i]['mean_bps']:+.1f} vs {results[i+1]['mean_bps']:+.1f})")

    # 保存
    result_df = pd.DataFrame(results)
    out_path = LOG_DIR / "cross_timeframe_guardrail.csv"
    result_df.to_csv(out_path, index=False)
    print(f"\n输出: {out_path}")


if __name__ == "__main__":
    main()
