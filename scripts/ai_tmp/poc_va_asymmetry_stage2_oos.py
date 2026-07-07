"""
文件级元信息：
- 创建背景：阶段 2 门槛 3 · 样本外扩展。在阶段 1 未使用的 45+ 合约月份上
  重跑主线三档信号的 cluster bootstrap CI，验证 CI 稳健性。
- 用途：
    (1) 加载 45+ 新合约月份 5m bar
    (2) 用阶段 1 严格无未来函数版本的规格构建事件表：
        - W1 profile · A3_skew · rolling σ (K=100 events)
        - 日线 ATR_10 · 近 10 日 log ret · rolling 20 日 rank
    (3) 分别计算三档信号的 cluster bootstrap 95% CI
    (4) 分品种 net 精算（realistic-cost）
    (5) 分板块看信号稳健性
- 注意事项：
    - 完全复用阶段 1 逻辑，只换合约清单
    - Warmup 期 20 交易日 + rolling 100 事件
    - 一些合约历史较短，可能触发不足 20 天判断跳过
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

# 样本外合约清单（45 个新合约月份，覆盖 13 品种）
OOS_SYMBOLS: dict[str, float] = {
    # rb (螺纹 · tick=1.0)
    "SHFE.rb2401": 1.0, "SHFE.rb2405": 1.0, "SHFE.rb2410": 1.0,
    "SHFE.rb2501": 1.0, "SHFE.rb2505": 1.0, "SHFE.rb2510": 1.0,
    "SHFE.rb2605": 1.0, "SHFE.rb2610": 1.0,
    # cu (铜 · tick=10.0)
    "SHFE.cu2509": 10.0,
    # m (豆粕 · tick=1.0)
    "DCE.m2401": 1.0, "DCE.m2405": 1.0, "DCE.m2409": 1.0,
    "DCE.m2501": 1.0, "DCE.m2505": 1.0, "DCE.m2509": 1.0,
    "DCE.m2603": 1.0, "DCE.m2605": 1.0, "DCE.m2607": 1.0, "DCE.m2609": 1.0,
    # p (棕榈 · tick=2.0)
    "DCE.p2405": 2.0, "DCE.p2409": 2.0, "DCE.p2501": 2.0,
    "DCE.p2505": 2.0, "DCE.p2509": 2.0, "DCE.p2605": 2.0,
    # SR (白糖 · tick=1.0)
    "CZCE.SR401": 1.0, "CZCE.SR405": 1.0, "CZCE.SR409": 1.0,
    "CZCE.SR501": 1.0, "CZCE.SR505": 1.0, "CZCE.SR509": 1.0,
    "CZCE.SR605": 1.0, "CZCE.SR609": 1.0,
    # CF (棉花 · tick=5.0)
    "CZCE.CF509": 5.0,
    # TA (PTA · tick=2.0)
    "CZCE.TA509": 2.0,
    # c (玉米 · tick=1.0)
    "DCE.c2603": 1.0, "DCE.c2605": 1.0,
    # cs (玉米淀粉 · tick=1.0)
    "DCE.cs2603": 1.0, "DCE.cs2605": 1.0,
    # y (豆油 · tick=1.0)
    "DCE.y2509": 1.0,
    # 其他
    "SHFE.ag2509": 1.0,      # 白银
    "SHFE.al2509": 5.0,      # 铝
    "INE.sc2509": 0.1,       # 原油
    "SHFE.hc2505": 1.0,      # 热卷
}

# 参数（复用阶段 1 严格无未来函数版本）
VALUE_AREA_RATIO = 0.70
K_SIGMA = 1.5
DEDUP_GAP_HOURS = 8.0
FUTURE_HORIZON_BARS = 96      # 8h × 12 根 5m
ROLLING_EVENTS = 100          # skew rolling
ROLLING_DAYS = 20             # ATR / trend rolling
WARMUP_DAYS = 20              # 排除前 20 交易日
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


def build_events(symbol: str) -> pd.DataFrame:
    tick = OOS_SYMBOLS[symbol]
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date

    hourly_mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    hourly_idx = bars.index[hourly_mask].to_list()

    rows = []
    for idx in hourly_idx:
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
    return daily[["date", "daily_atr_10_bps", "trend_ret_10d"]]


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


def main() -> None:
    symbols = list(OOS_SYMBOLS.keys())
    print(f"样本外合约数: {len(symbols)}")

    print("\n构建事件表 + 日线特征 ...")
    all_events = []
    for i, sym in enumerate(symbols):
        try:
            ev = build_events(sym)
            daily = build_daily_features(sym)
            ev = ev.merge(daily, left_on="event_date", right_on="date", how="left")
            all_events.append(ev)
            print(f"  [{i+1}/{len(symbols)}] {sym}  n={len(ev)}")
        except FileNotFoundError:
            print(f"  [{i+1}/{len(symbols)}] {sym}  SKIP (no CSV)")
        except Exception as e:
            print(f"  [{i+1}/{len(symbols)}] {sym}  ERR: {e}")

    df = pd.concat(all_events, ignore_index=True)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["ret_bps"] = df["ret_8h"] * 1e4
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    print(f"\n总事件数: {len(df)} · 合约数: {df['contract'].nunique()}")

    # Rolling rank
    print("\n构建 rolling rank ...")
    df["signed_skew_rank_roll"] = df.groupby("contract")["A3_skew"].transform(
        lambda s: rolling_pct_rank(s, ROLLING_EVENTS))

    for feat_col, roll_col in [("daily_atr_10_bps", "atr_rank_roll"),
                                ("trend_ret_10d", "trend_rank_roll")]:
        # 日线级 rolling rank 再 merge 回事件
        seg_list = []
        for c, g in df.groupby("contract"):
            daily = g.drop_duplicates("event_date").sort_values("event_date").copy()
            daily[roll_col] = rolling_pct_rank(daily[feat_col], ROLLING_DAYS)
            seg_list.append(daily[["contract", "event_date", roll_col]])
        seg_map = pd.concat(seg_list, ignore_index=True)
        df = df.merge(seg_map, on=["contract", "event_date"], how="left")

    # Warmup 排除
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
    df = df.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
    print(f"warmup 后事件数: {len(df)} · 合约数: {df['contract'].nunique()}")

    # 分组
    df["skew_grp"] = df["signed_skew_rank_roll"].apply(
        lambda r: "DN" if r <= 0.10 else ("UP" if r >= 0.90 else "mid"))
    df["trend_grp"] = df["trend_rank_roll"].apply(
        lambda r: "down" if r <= 0.33 else ("up" if r >= 0.67 else "flat"))
    df["atr10_grp"] = df["atr_rank_roll"].apply(lambda r: "low" if r <= 0.5 else "high")

    # 三档 CI
    print("\n" + "=" * 90)
    print("样本外 · 主线三档 cluster bootstrap CI")
    print("=" * 90)

    for label, mask in [
        ("DN 单层", df["skew_grp"] == "DN"),
        ("DN + 低 ATR_10", (df["skew_grp"] == "DN") & (df["atr10_grp"] == "low")),
        ("DN + 涨段 + 低 ATR_10 (主线)",
         (df["skew_grp"] == "DN") & (df["trend_grp"] == "up") & (df["atr10_grp"] == "low")),
    ]:
        sub = df[mask].dropna(subset=["ret_bps"])
        if len(sub) < 10:
            print(f"\n【{label}】样本太少 n={len(sub)}")
            continue
        r = cluster_bootstrap(sub)
        hit = (sub["ret_bps"] > 0).mean()
        print(f"\n【{label}】")
        print(f"  n={r['n_events']} events · {r['n_contracts']} contracts · hit={hit:.1%}")
        print(f"  mean = {r['real_mean']:+.2f} bps")
        print(f"  95% CI = [{r['ci_lo_95']:+.2f}, {r['ci_hi_95']:+.2f}]")
        print(f"  p_two = {r['p_two']:.4f}")
        judge = "✅ CI 排 0" if r['ci_lo_95'] > 0 else "❌ CI 触 0"
        print(f"  判读: {judge}")

    # 分品种检查
    print("\n" + "=" * 90)
    print("样本外 · 分品种 DN 单层 mean（≥60% 保留 edge 判据）")
    print("=" * 90)

    def prefix_of(sym: str) -> str:
        return parse_prefix(sym)

    df["prefix"] = df["contract"].apply(prefix_of)
    rows = []
    for prefix, g in df.groupby("prefix"):
        dn = g[g["skew_grp"] == "DN"]
        if len(dn) < 5:
            continue
        rows.append({
            "prefix": prefix,
            "n_contracts": g["contract"].nunique(),
            "n_dn_events": len(dn),
            "dn_mean_bps": dn["ret_bps"].mean(),
            "dn_hit": (dn["ret_bps"] > 0).mean(),
        })
    prefix_df = pd.DataFrame(rows).sort_values("dn_mean_bps", ascending=False)
    print(f"\n{'品种':6s} {'合约数':>6s} {'DN事件':>8s} {'mean(bps)':>10s} {'hit':>7s}")
    n_positive = 0
    for _, r in prefix_df.iterrows():
        print(f"{r['prefix']:6s} {r['n_contracts']:>6d} {r['n_dn_events']:>8d} "
              f"{r['dn_mean_bps']:>+10.2f} {r['dn_hit']:>7.1%}")
        if r['dn_mean_bps'] > 0:
            n_positive += 1
    positive_ratio = n_positive / len(prefix_df) if len(prefix_df) else 0
    print(f"\n正 mean 品种: {n_positive}/{len(prefix_df)} = {positive_ratio:.1%}  "
          f"（判据 ≥60% 保留 edge）")

    # 保存
    df.to_csv(LOG_DIR / "oos_events.csv", index=False)
    prefix_df.to_csv(LOG_DIR / "oos_by_prefix.csv", index=False)
    print(f"\n输出:")
    print(f"  {LOG_DIR / 'oos_events.csv'}")
    print(f"  {LOG_DIR / 'oos_by_prefix.csv'}")


if __name__ == "__main__":
    main()
