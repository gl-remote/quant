"""
文件级元信息：
- 创建背景：阶段 2 补充 · 多头主线 + 空头 E 均已达到相同证据深度，现在
  用参数网格搜索探明各档位下的 sweet spot 与稳健区域。
- 用途：
    (1) 复用 stage2_oos 的事件表 + rolling rank
    (2) 多头 96 组合网格搜索（skew × atr × trend）
    (3) 空头 96 组合网格搜索（skew × atr × trend）
    (4) 每组合跑 5000 次 cluster bootstrap CI
    (5) 输出 top 20 排序表 · 热力图数据 · 前 5 名分品种保留度
- 注意事项：
    - 多头 horizon 固定 8h · 空头 horizon 固定 4h（阶段 2 已确认）
    - 严格无未来函数 rolling rank
    - 判据：CI 排 0 · n ≥ 30 · n_contracts ≥ 10
"""

from __future__ import annotations

from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage2"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)

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
    return (((prices - mean) / std) ** 3 * w).sum()


def build_events(symbol: str, tick: float) -> pd.DataFrame:
    bars = load_5m(symbol)
    bars["date"] = bars["datetime"].dt.date
    mask = (bars["datetime"].dt.minute == 0) & (bars["datetime"].dt.second == 0)
    hourly_idx = bars.index[mask].to_list()
    rows = []
    for idx in hourly_idx:
        t = bars.loc[idx, "datetime"]
        close_t = bars.loc[idx, "close"]
        # 多头 8h + 空头 4h
        fut8h = idx + 96
        fut4h = idx + 48
        if fut8h >= len(bars):
            continue
        ret_8h = np.log(bars.loc[fut8h, "close"] / close_t)
        ret_4h = np.log(bars.loc[fut4h, "close"] / close_t)
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
            "close_t": close_t, "A3_skew": sk,
            "ret_8h": ret_8h, "ret_4h": ret_4h,
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
        "ci_lo": float(np.quantile(valid, 0.025)),
        "ci_hi": float(np.quantile(valid, 0.975)),
        "p_two": 2 * min((valid <= 0).mean(), (valid >= 0).mean()),
    }


def prepare_dataset() -> pd.DataFrame:
    all_events = []
    for i, (sym, tick) in enumerate(OOS_SYMBOLS.items()):
        try:
            ev = build_events(sym, tick)
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
    ]:
        seg_list = []
        for c, g in df.groupby("contract"):
            daily = g.drop_duplicates("event_date").sort_values("event_date").copy()
            daily[roll_col] = rolling_pct_rank(daily[feat_col], ROLLING_DAYS)
            seg_list.append(daily[["contract", "event_date", roll_col]])
        seg_map = pd.concat(seg_list, ignore_index=True)
        df = df.merge(seg_map, on=["contract", "event_date"], how="left")
    keep = np.zeros(len(df), dtype=bool)
    for c in df["contract"].unique():
        idx = df[df["contract"] == c].sort_values("event_time").index
        dates = sorted(df.loc[idx, "event_date"].unique())
        if len(dates) < WARMUP_DAYS:
            continue
        wend = dates[WARMUP_DAYS - 1]
        for i in idx:
            if df.at[i, "event_date"] > wend:
                keep[df.index.get_loc(i)] = True
    df = df[keep].reset_index(drop=True)
    df = df.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
    df["ret_8h_bps"] = df["ret_8h"] * 1e4
    df["short_pnl_4h_bps"] = -df["ret_4h"] * 1e4
    return df


def grid_search_long(df: pd.DataFrame) -> pd.DataFrame:
    """多头网格：DN + 低 ATR + 涨段 · 8h horizon"""
    skew_thrs = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    atr_thrs = [0.40, 0.50, 0.60, 0.70]      # ATR ≤ 阈值
    trend_thrs = [0.50, 0.60, 0.67, 0.75]    # trend ≥ 阈值

    rows = []
    total = len(skew_thrs) * len(atr_thrs) * len(trend_thrs)
    print(f"多头网格：{total} 组合")
    for i, (sk, at, tr) in enumerate(product(skew_thrs, atr_thrs, trend_thrs)):
        mask = ((df["signed_skew_rank_roll"] <= sk) &
                (df["atr_rank_roll"] <= at) &
                (df["trend_rank_roll"] >= tr))
        sub = df[mask].dropna(subset=["ret_8h_bps"])
        if len(sub) < 20:
            rows.append({
                "skew_le": sk, "atr_le": at, "trend_ge": tr,
                "n": len(sub), "mean": np.nan, "hit": np.nan,
                "ci_lo": np.nan, "ci_hi": np.nan, "p": np.nan,
                "n_contracts": sub["contract"].nunique() if len(sub) else 0,
                "pass": False, "reason": "n<20",
            })
            continue
        r = cluster_bootstrap(sub, "ret_8h_bps")
        pass_ = (r["ci_lo"] > 0) and (r["n_events"] >= 30) and (r["n_contracts"] >= 10)
        rows.append({
            "skew_le": sk, "atr_le": at, "trend_ge": tr,
            "n": r["n_events"], "n_contracts": r["n_contracts"],
            "mean": r["real_mean"], "hit": (sub["ret_8h_bps"] > 0).mean(),
            "ci_lo": r["ci_lo"], "ci_hi": r["ci_hi"], "p": r["p_two"],
            "pass": pass_, "reason": "" if pass_ else (
                "CI触0" if r["ci_lo"] <= 0 else
                ("n<30" if r["n_events"] < 30 else "少品种")
            ),
        })
        if (i + 1) % 24 == 0:
            print(f"  {i+1}/{total} ...")
    return pd.DataFrame(rows)


def grid_search_short(df: pd.DataFrame) -> pd.DataFrame:
    """空头网格：UP + 高 ATR + 跌段 · 4h horizon（做空 pnl）"""
    skew_thrs = [0.95, 0.90, 0.85, 0.80, 0.75, 0.70]   # skew ≥ 阈值
    atr_thrs = [0.50, 0.60, 0.70, 0.80]                # ATR > 阈值
    trend_thrs = [0.20, 0.25, 0.33, 0.40]              # trend ≤ 阈值

    rows = []
    total = len(skew_thrs) * len(atr_thrs) * len(trend_thrs)
    print(f"空头网格：{total} 组合")
    for i, (sk, at, tr) in enumerate(product(skew_thrs, atr_thrs, trend_thrs)):
        mask = ((df["signed_skew_rank_roll"] >= sk) &
                (df["atr_rank_roll"] > at) &
                (df["trend_rank_roll"] <= tr))
        sub = df[mask].dropna(subset=["short_pnl_4h_bps"])
        if len(sub) < 20:
            rows.append({
                "skew_ge": sk, "atr_gt": at, "trend_le": tr,
                "n": len(sub), "mean": np.nan, "hit": np.nan,
                "ci_lo": np.nan, "ci_hi": np.nan, "p": np.nan,
                "n_contracts": sub["contract"].nunique() if len(sub) else 0,
                "pass": False, "reason": "n<20",
            })
            continue
        r = cluster_bootstrap(sub, "short_pnl_4h_bps")
        pass_ = (r["ci_lo"] > 0) and (r["n_events"] >= 30) and (r["n_contracts"] >= 10)
        rows.append({
            "skew_ge": sk, "atr_gt": at, "trend_le": tr,
            "n": r["n_events"], "n_contracts": r["n_contracts"],
            "mean": r["real_mean"], "hit": (sub["short_pnl_4h_bps"] > 0).mean(),
            "ci_lo": r["ci_lo"], "ci_hi": r["ci_hi"], "p": r["p_two"],
            "pass": pass_, "reason": "" if pass_ else (
                "CI触0" if r["ci_lo"] <= 0 else
                ("n<30" if r["n_events"] < 30 else "少品种")
            ),
        })
        if (i + 1) % 24 == 0:
            print(f"  {i+1}/{total} ...")
    return pd.DataFrame(rows)


def print_top(name: str, df: pd.DataFrame, top_n: int = 20):
    print(f"\n{'='*100}")
    print(f"{name} · Top {top_n} 按 mean 降序 · 通过判据(CI排0/n≥30/品种≥10)标 ✅")
    print("=" * 100)
    d = df.sort_values("mean", ascending=False).head(top_n)
    keys = [c for c in d.columns if c in {"skew_le", "atr_le", "trend_ge",
                                            "skew_ge", "atr_gt", "trend_le"}]
    header = "  ".join(f"{k:>8s}" for k in keys)
    print(f"{header} {'n':>5s} {'品种':>5s} {'mean':>7s} {'hit':>7s} "
          f"{'CI下':>7s} {'CI上':>7s} {'p':>7s} {'判决':>4s}")
    for _, r in d.iterrows():
        args = "  ".join(f"{r[k]:>8.2f}" for k in keys)
        judge = "✅" if r["pass"] else "❌"
        p_str = f"{r['p']:.4f}" if not np.isnan(r['p']) else "----"
        print(f"{args} {int(r['n']):>5d} {int(r['n_contracts']):>5d} "
              f"{r['mean']:>+7.2f} {r['hit']:>7.1%} "
              f"{r['ci_lo']:>+7.2f} {r['ci_hi']:>+7.2f} "
              f"{p_str:>7s}   {judge}")


def print_heatmap(name: str, df: pd.DataFrame, direction: str):
    """打印热力图 · 三层 trend 分面"""
    print(f"\n{'='*100}")
    print(f"{name} · 热力图 · 行=skew 阈值 · 列=ATR 阈值 · 单元=mean bps · 每个 trend 分面独立")
    print("=" * 100)
    if direction == "long":
        skew_col, atr_col, trend_col = "skew_le", "atr_le", "trend_ge"
    else:
        skew_col, atr_col, trend_col = "skew_ge", "atr_gt", "trend_le"
    for trend_val in sorted(df[trend_col].unique()):
        sub = df[df[trend_col] == trend_val]
        pivot = sub.pivot_table(index=skew_col, columns=atr_col, values="mean", aggfunc="first")
        pass_pivot = sub.pivot_table(index=skew_col, columns=atr_col, values="pass", aggfunc="first")
        n_pivot = sub.pivot_table(index=skew_col, columns=atr_col, values="n", aggfunc="first")
        print(f"\n{trend_col} = {trend_val:.2f}")
        cols = pivot.columns
        header = "        " + "  ".join(f"ATR={c:.2f}" for c in cols)
        print(header)
        for row_val, row in pivot.iterrows():
            parts = []
            for c in cols:
                v = row[c]
                p = pass_pivot.loc[row_val, c]
                n = n_pivot.loc[row_val, c]
                marker = "✅" if p else " "
                if np.isnan(v):
                    parts.append(f" {'n/a':>7s}  ")
                else:
                    parts.append(f"{v:>+7.1f}{marker}(n={int(n):3d})")
            print(f"skew={row_val:.2f}  " + "  ".join(parts))


def top_by_prefix(df: pd.DataFrame, best_row: pd.Series, direction: str, events_df: pd.DataFrame):
    """对 top 组合做分品种保留度分析"""
    if direction == "long":
        mask = ((events_df["signed_skew_rank_roll"] <= best_row["skew_le"]) &
                (events_df["atr_rank_roll"] <= best_row["atr_le"]) &
                (events_df["trend_rank_roll"] >= best_row["trend_ge"]))
        ret_col = "ret_8h_bps"
    else:
        mask = ((events_df["signed_skew_rank_roll"] >= best_row["skew_ge"]) &
                (events_df["atr_rank_roll"] > best_row["atr_gt"]) &
                (events_df["trend_rank_roll"] <= best_row["trend_le"]))
        ret_col = "short_pnl_4h_bps"
    sub = events_df[mask].dropna(subset=[ret_col]).copy()
    sub["prefix"] = sub["contract"].apply(parse_prefix)
    rows = []
    for prefix, g in sub.groupby("prefix"):
        if len(g) < 5:
            continue
        rows.append({
            "prefix": prefix,
            "n_contracts": g["contract"].nunique(),
            "n": len(g),
            "mean": g[ret_col].mean(),
            "hit": (g[ret_col] > 0).mean(),
        })
    return pd.DataFrame(rows).sort_values("mean", ascending=False)


def main():
    print("=" * 100)
    print("阶段 2 补充 · 参数网格搜索 · 多空双向 · 每方向 96 组合")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()
    print(f"  总事件: {len(df)} · 合约: {df['contract'].nunique()}")

    # 多头
    print("\n" + "=" * 100)
    print("多头方向 · 8h horizon · DN + 低 ATR + 涨段")
    print("=" * 100)
    long_grid = grid_search_long(df)
    long_grid.to_csv(LOG_DIR / "param_grid_long.csv", index=False)
    print_top("多头", long_grid, top_n=20)

    # 空头
    print("\n" + "=" * 100)
    print("空头方向 · 4h horizon · UP + 高 ATR + 跌段")
    print("=" * 100)
    short_grid = grid_search_short(df)
    short_grid.to_csv(LOG_DIR / "param_grid_short.csv", index=False)
    print_top("空头", short_grid, top_n=20)

    # 热力图
    print_heatmap("多头 8h", long_grid, direction="long")
    print_heatmap("空头 4h", short_grid, direction="short")

    # 前 5 名分品种深挖
    print("\n" + "=" * 100)
    print("多头 Top 5 组合 · 分品种保留度")
    print("=" * 100)
    for idx, (_, best) in enumerate(long_grid[long_grid["pass"]].sort_values("mean", ascending=False).head(5).iterrows()):
        print(f"\n#{idx+1} · skew≤{best['skew_le']} · atr≤{best['atr_le']} · trend≥{best['trend_ge']} · "
              f"mean={best['mean']:+.1f} · n={int(best['n'])}")
        pf = top_by_prefix(long_grid, best, "long", df)
        n_pos = (pf["mean"] > 0).sum()
        print(f"  正 mean: {n_pos}/{len(pf)} = {n_pos/max(1,len(pf)):.1%}")
        for _, r in pf.iterrows():
            print(f"    {r['prefix']:6s}  n={int(r['n']):>4d}  mean={r['mean']:>+7.2f}  hit={r['hit']:>6.1%}")

    print("\n" + "=" * 100)
    print("空头 Top 5 组合 · 分品种保留度")
    print("=" * 100)
    for idx, (_, best) in enumerate(short_grid[short_grid["pass"]].sort_values("mean", ascending=False).head(5).iterrows()):
        print(f"\n#{idx+1} · skew≥{best['skew_ge']} · atr>{best['atr_gt']} · trend≤{best['trend_le']} · "
              f"mean={best['mean']:+.1f} · n={int(best['n'])}")
        pf = top_by_prefix(short_grid, best, "short", df)
        n_pos = (pf["mean"] > 0).sum()
        print(f"  正 mean: {n_pos}/{len(pf)} = {n_pos/max(1,len(pf)):.1%}")
        for _, r in pf.iterrows():
            print(f"    {r['prefix']:6s}  n={int(r['n']):>4d}  mean={r['mean']:>+7.2f}  hit={r['hit']:>6.1%}")

    # 汇总统计
    print("\n" + "=" * 100)
    print("网格通过率汇总")
    print("=" * 100)
    print(f"多头: {long_grid['pass'].sum()}/{len(long_grid)} = {long_grid['pass'].mean():.1%}")
    print(f"空头: {short_grid['pass'].sum()}/{len(short_grid)} = {short_grid['pass'].mean():.1%}")

    print("\n输出：")
    print(f"  {LOG_DIR / 'param_grid_long.csv'}")
    print(f"  {LOG_DIR / 'param_grid_short.csv'}")


if __name__ == "__main__":
    main()
