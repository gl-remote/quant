"""全品种 roll_t_pit 窗口扫描：日频数据，正确 roll_t_pit，不同 window 的信号密度对比。"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

import pandas as pd
import numpy as np
from strategies.classifiers.poc_va import (
    volume_weighted_skew, roll_t_pit, daily_atr_sma, trend_log_return,
    classify_tier, tier_direction, compute_transition_series,
)

CSV_DIR = Path(__file__).resolve().parents[2] / "project_data/market_data/csv"
WINDOWS = [3, 5, 7, 10, 15, 20]
MIN_DAYS = 30  # 最少需要 30 天日线数据


def build_daily(sym_path: Path) -> pd.DataFrame:
    bars = pd.read_csv(sym_path, usecols=["datetime", "open", "high", "low", "close", "volume"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars["date"] = pd.to_datetime(bars["datetime"].dt.date)

    daily = bars.groupby("date").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"),
    ).reset_index().sort_values("date").reset_index(drop=True)

    a3_map = {}
    for d, g in bars.groupby("date"):
        a3_map[pd.Timestamp(d)] = volume_weighted_skew(
            g["close"].to_numpy(dtype=float), g["volume"].to_numpy(dtype=float)
        )
    daily["A3_skew"] = daily["date"].map(a3_map)
    daily["atr"] = daily_atr_sma(daily["high"], daily["low"], daily["close"], 10)
    daily["trend"] = trend_log_return(daily["close"], 10)
    daily = daily.dropna(subset=["A3_skew", "atr", "trend"])
    return daily


def classify_one(daily: pd.DataFrame, W: int) -> dict:
    """对一份日频数据按单窗口分类，返回统计 dict。"""
    r_s_raw = roll_t_pit(daily["A3_skew"].astype(float), W, min_periods=W)
    r_s = 1.0 - r_s_raw
    r_a = roll_t_pit(daily["atr"].astype(float), W, min_periods=W)
    r_t = roll_t_pit(daily["trend"].astype(float), W, min_periods=W)
    trans_df = compute_transition_series(r_a)

    d2 = daily.copy()
    d2["r_s"] = r_s
    d2["r_a"] = r_a
    d2["r_t"] = r_t
    d2["trans"] = trans_df["trans"]
    v = d2.dropna(subset=["r_s", "r_a", "r_t"])

    tiers = [classify_tier(float(rs), float(ra), float(rt), str(tr))
             for rs, ra, rt, tr in zip(v["r_s"], v["r_a"], v["r_t"], v["trans"])]
    dirs = [tier_direction(t) if isinstance(t, str) else "" for t in tiers]

    n_total = len(v)
    n_hit = sum(1 for t in tiers if isinstance(t, str))
    n_long = sum(1 for d in dirs if d == "long")
    n_short = sum(1 for d in dirs if d == "short")
    tier_counts = {}
    for t in tiers:
        if isinstance(t, str):
            tier_counts[t] = tier_counts.get(t, 0) + 1

    return dict(
        n_total=n_total, n_hit=n_hit, n_long=n_long, n_short=n_short,
        hit_rate=n_hit / n_total if n_total > 0 else 0,
        tier_counts=tier_counts,
    )


def contract_info(name: str):
    """从合约名提取交易所和品种。"""
    parts = name.split(".")
    exchange = parts[0] if len(parts) >= 1 else "?"
    product = "".join(c for c in parts[1] if c.isalpha()) if len(parts) >= 2 else "?"
    return exchange, product


def main():
    t0 = time.time()
    all_files = sorted(CSV_DIR.glob("*.tqsdk.5m.csv"))
    print(f"扫描 {len(all_files)} 个 5m CSV 文件 (最少 {MIN_DAYS} 天日线)", flush=True)

    # 聚合结构: results[W] = [{stats per contract}]
    results = {W: [] for W in WINDOWS}
    skipped = 0
    processed = 0

    for i, sym_path in enumerate(all_files):
        name = sym_path.name.replace(".tqsdk.5m.csv", "")
        exchange, product = contract_info(name)

        try:
            daily = build_daily(sym_path)
        except Exception as e:
            skipped += 1
            continue

        if len(daily) < MIN_DAYS:
            skipped += 1
            continue

        processed += 1
        if processed % 20 == 0:
            print(f"  进度: {processed}/{len(all_files)} ...", flush=True)

        for W in WINDOWS:
            if len(daily) <= W:
                continue
            r = classify_one(daily, W)
            r["contract"] = name
            r["exchange"] = exchange
            r["product"] = product
            r["n_days"] = len(daily)
            results[W].append(r)

    elapsed = time.time() - t0

    # === 汇总输出 ===
    print(f"\n{'='*90}")
    print(f"完成: {processed} 合约处理, {skipped} 跳过, 耗时 {elapsed:.0f}s")
    print(f"{'='*90}")

    # 全局汇总
    print(f"\n{'窗口':<8} {'合约数':>6} {'有效日':>8} {'命中':>6} {'命中率均值':>9} {'Long均值':>8} {'Short均值':>9} {'总Tier类型'}")
    print("-" * 90)
    for W in WINDOWS:
        rows = results[W]
        if not rows:
            continue
        n_contracts = len(rows)
        total_days = sum(r["n_total"] for r in rows)
        total_hit = sum(r["n_hit"] for r in rows)
        hit_rate_avg = np.mean([r["hit_rate"] for r in rows])
        long_avg = np.mean([r["n_long"] for r in rows])
        short_avg = np.mean([r["n_short"] for r in rows])

        # 收集所有 tier 类型
        all_tiers = set()
        for r in rows:
            all_tiers.update(r["tier_counts"].keys())

        print(f"W={W:<3d}   {n_contracts:>5}   {total_days:>6}   {total_hit:>5}   {hit_rate_avg:>8.1%}   {long_avg:>7.1f}   {short_avg:>8.1f}   {sorted(all_tiers)}")

    # 合约级别明细（按 W=20 命中率排序，top 20）
    print(f"\n{'─'*90}")
    print("合约级 Top-20 (按 W=20 命中率排序)")
    print(f"{'─'*90}")
    w20_rows = sorted(results[20], key=lambda r: r["hit_rate"], reverse=True)
    print(f"{'合约':<22} {'天数':>5}", end="")
    for W in WINDOWS:
        print(f"  W={W:<3d}", end="")
    print()
    print("-" * 90)
    for r in w20_rows[:20]:
        print(f"{r['contract']:<22} {r['n_days']:>4} ", end="")
        for W in WINDOWS:
            # 找到同合约同窗口的数据
            match = [x for x in results[W] if x["contract"] == r["contract"]]
            if match:
                hr = match[0]["hit_rate"]
                print(f"  {hr:>5.1%}", end="")
            else:
                print(f"  {'—':>5}", end="")
        print()

    # 按交易所汇总
    print(f"\n{'─'*90}")
    print("按交易所 & 窗口汇总")
    print(f"{'─'*90}")
    for W in WINDOWS:
        rows = results[W]
        if not rows:
            continue
        df = pd.DataFrame(rows)
        print(f"\n  W={W}:")
        for ex in sorted(df["exchange"].unique()):
            sub = df[df["exchange"] == ex]
            print(f"    {ex}: {len(sub)}合约, 命中率均值 {sub['hit_rate'].mean():.1%}, "
                  f"Long均值 {sub['n_long'].mean():.1f}, Short均值 {sub['n_short'].mean():.1f}")

    # 按品种汇总
    print(f"\n{'─'*90}")
    print("按品种 & 窗口: 日均信号密度 Top/Bottom")
    print(f"{'─'*90}")
    for W in WINDOWS:
        rows = results[W]
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["signal_per_day"] = df["n_hit"] / df["n_total"]
        prod_stats = df.groupby("product").agg(
            n=("contract", "count"),
            avg_hit_rate=("signal_per_day", "mean"),
            avg_long=("n_long", "mean"),
            avg_short=("n_short", "mean"),
        ).sort_values("avg_hit_rate", ascending=False)
        print(f"\n  W={W}:")
        for prod, row in prod_stats.iterrows():
            print(f"    {prod:<6} {int(row['n']):>2}合约 命中{row['avg_hit_rate']:>6.1%}  "
                  f"L={row['avg_long']:.1f} S={row['avg_short']:.1f}")

    # 空头信号：哪些窗口/品种有效
    print(f"\n{'─'*90}")
    print("空头信号统计 (有 Short > 0 的合约数)")
    print(f"{'─'*90}")
    for W in WINDOWS:
        rows = results[W]
        if not rows:
            continue
        has_short = sum(1 for r in rows if r["n_short"] > 0)
        print(f"  W={W}: {has_short}/{len(rows)} 合约有空头信号")
        if has_short > 0:
            short_contracts = [(r["contract"], r["n_short"]) for r in rows if r["n_short"] > 0]
            short_contracts.sort(key=lambda x: -x[1])
            for c, s in short_contracts[:10]:
                print(f"        {c}: {s} 空头")


if __name__ == "__main__":
    main()
