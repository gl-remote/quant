"""A/B 对比：z-score→t-CDF vs 分位数排名 归一化方式 (DCE.m2405, W=5)

研究问题：分位数排名能否在短窗口下替代 z-score→t-CDF，复现 workbench 的信号密度？
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

import pandas as pd
import numpy as np
from strategies.classifiers.poc_va import (
    volume_weighted_skew, roll_t_pit, daily_atr_sma, trend_log_return,
    classify_tier, tier_direction, compute_transition_series, TIERS,
)

CSV_DIR = Path(__file__).resolve().parents[2] / "project_data/market_data/csv"
SYMBOL = "DCE.m2405"
W = 5  # 短窗口


def percentile_rank(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """滚动分位数排名：(0, 1] 归一化，rank 1 = 最低 = 0.0, rank N = 最高 ≈ 1.0"""
    if min_periods is None:
        min_periods = window
    rank = series.rolling(window, min_periods=min_periods).rank(pct=False)
    count = series.rolling(window, min_periods=min_periods).count()
    # rank/count → (0, 1], 最低值=1/count ≈ 0, 最高值=1.0
    return rank / count


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


def classify_method_A(daily: pd.DataFrame, W: int) -> pd.DataFrame:
    """方法 A：z-score → t-CDF (当前生产方法)"""
    out = daily.copy()
    r_s_raw = roll_t_pit(out["A3_skew"].astype(float), W, min_periods=W)
    out["r_s"] = 1.0 - r_s_raw
    out["r_a"] = roll_t_pit(out["atr"].astype(float), W, min_periods=W)
    out["r_t"] = roll_t_pit(out["trend"].astype(float), W, min_periods=W)
    trans_df = compute_transition_series(out["r_a"])
    out["trans"] = trans_df["trans"]
    out = out.dropna(subset=["r_s", "r_a", "r_t"])
    tiers = [classify_tier(float(rs), float(ra), float(rt), str(tr))
             for rs, ra, rt, tr in zip(out["r_s"], out["r_a"], out["r_t"], out["trans"])]
    out["tier"] = tiers
    out["direction"] = [tier_direction(t) if isinstance(t, str) else "" for t in tiers]
    return out


def classify_method_B(daily: pd.DataFrame, W: int) -> pd.DataFrame:
    """方法 B：分位数排名 (percentile rank)"""
    out = daily.copy()
    # skew 坐标：高=极端跌=short（同 spec 约定），故取互补
    r_s_raw = percentile_rank(out["A3_skew"].astype(float), W, min_periods=W)
    out["r_s"] = 1.0 - r_s_raw
    out["r_a"] = percentile_rank(out["atr"].astype(float), W, min_periods=W)
    out["r_t"] = percentile_rank(out["trend"].astype(float), W, min_periods=W)
    trans_df = compute_transition_series(out["r_a"])
    out["trans"] = trans_df["trans"]
    out = out.dropna(subset=["r_s", "r_a", "r_t"])
    tiers = [classify_tier(float(rs), float(ra), float(rt), str(tr))
             for rs, ra, rt, tr in zip(out["r_s"], out["r_a"], out["r_t"], out["trans"])]
    out["tier"] = tiers
    out["direction"] = [tier_direction(t) if isinstance(t, str) else "" for t in tiers]
    return out


def summarize(name: str, df: pd.DataFrame):
    """打印单个方法的汇总统计"""
    n = len(df)
    hit = df["tier"].notna() & (df["tier"] != "")
    n_hit = hit.sum()
    n_long = (df["direction"] == "long").sum()
    n_short = (df["direction"] == "short").sum()

    print(f"\n{'='*70}")
    print(f"方法: {name} (W={W})")
    print(f"  有效日: {n}")
    print(f"  命中: {n_hit} ({n_hit/n*100:.1f}%)")
    print(f"  Long: {n_long} (每合约 {n_long/n*100:.1f}% 的日)")
    print(f"  Short: {n_short} (每合约 {n_short/n*100:.1f}% 的日)")

    # tier 分布
    tier_counts = df.loc[hit, "tier"].value_counts()
    print(f"  Tier 分布:")
    for t, c in tier_counts.items():
        print(f"    {t}: {c} ({c/n*100:.1f}%)")

    # r_s 分布对比
    print(f"\n  坐标分布 (全有效日):")
    for col in ["r_s", "r_a", "r_t"]:
        s = df[col].dropna()
        print(f"    {col:>5s}: mean={s.mean():.3f}  std={s.std():.3f}  "
              f"P05={s.quantile(0.05):.3f}  P50={s.quantile(0.5):.3f}  P95={s.quantile(0.95):.3f}")
    return dict(n=n, n_hit=n_hit, n_long=n_long, n_short=n_short, tier_counts=tier_counts.to_dict())


def compare_daily_signals(df_a: pd.DataFrame, df_b: pd.DataFrame):
    """逐日对比 A/B 的信号差异"""
    print(f"\n{'='*70}")
    print("逐日信号对比 (按 date 对齐)")
    print(f"{'='*70}")

    merged = df_a[["date", "tier", "direction"]].merge(
        df_b[["date", "tier", "direction"]],
        on="date", suffixes=("_A", "_B"), how="inner"
    )
    n = len(merged)

    # A 有信号、B 无信号
    a_only = merged["tier_A"].notna() & (merged["tier_B"].isna() | (merged["tier_B"] == ""))
    b_only = (merged["tier_A"].isna() | (merged["tier_A"] == "")) & merged["tier_B"].notna()
    both = merged["tier_A"].notna() & merged["tier_B"].notna()
    neither = ~(merged["tier_A"].notna() | merged["tier_B"].notna())

    print(f"  A 独有信号: {a_only.sum()} 天")
    print(f"  B 独有信号: {b_only.sum()} 天")
    print(f"  两法共有: {both.sum()} 天")
    print(f"  两法皆无: {neither.sum()} 天")

    if a_only.sum() > 0:
        print(f"  A 独有 tier: {merged.loc[a_only, 'tier_A'].value_counts().to_dict()}")
    if b_only.sum() > 0:
        print(f"  B 独有 tier: {merged.loc[b_only, 'tier_B'].value_counts().to_dict()}")
    if both.sum() > 0:
        agree = (merged.loc[both, "tier_A"] == merged.loc[both, "tier_B"])
        print(f"  共有中 tier 一致: {agree.sum()}/{both.sum()} ({agree.sum()/both.sum()*100:.0f}%)")
        if agree.sum() < both.sum():
            disagree = merged.loc[both & ~agree, ["date", "tier_A", "tier_B"]]
            print(f"  不一致样本 (前 10):")
            for _, r in disagree.head(10).iterrows():
                print(f"    {r['date'].strftime('%Y-%m-%d')}: A={r['tier_A']}  B={r['tier_B']}")

    # 方向一致性
    a_dir = merged.loc[both, "direction_A"]
    b_dir = merged.loc[both, "direction_B"]
    dir_agree = (a_dir == b_dir)
    print(f"\n  共有信号中方向一致: {dir_agree.sum()}/{len(a_dir)} ({dir_agree.sum()/len(a_dir)*100:.0f}%)")

    # 坐标相关性
    for col in ["r_s", "r_a", "r_t"]:
        corr = df_a[col].corr(df_b[col])
        print(f"  {col} Pearson 相关: {corr:.4f}")


def main():
    sym_path = CSV_DIR / f"{SYMBOL}.tqsdk.5m.csv"
    if not sym_path.exists():
        print(f"文件不存在: {sym_path}")
        return

    daily = build_daily(sym_path)
    print(f"DCE.m2405 日线: {len(daily)} 天 ({daily['date'].min().strftime('%Y-%m-%d')} ~ {daily['date'].max().strftime('%Y-%m-%d')})")

    # 方法 A：z-score → t-CDF
    df_a = classify_method_A(daily, W)
    stats_a = summarize("A: z-score → t-CDF (生产方法)", df_a)

    # 方法 B：分位数排名
    df_b = classify_method_B(daily, W)
    stats_b = summarize("B: 分位数排名 (percentile rank)", df_b)

    # 对标 workbench：workbench 的信号密度有多少？
    print(f"\n{'='*70}")
    print("效果对比")
    print(f"{'='*70}")
    print(f"  A 命中率: {stats_a['n_hit']/stats_a['n']*100:.1f}%")
    print(f"  B 命中率: {stats_b['n_hit']/stats_b['n']*100:.1f}%")
    print(f"  相对提升: {(stats_b['n_hit'] - stats_a['n_hit']) / max(stats_a['n_hit'], 1) * 100:.0f}%")

    # 逐日对比
    compare_daily_signals(df_a, df_b)

    # 结论
    print(f"\n{'='*70}")
    print("结论")
    print(f"{'='*70}")
    if stats_b["n_hit"] > stats_a["n_hit"] * 1.5:
        print("  → 分位数排名显著提高信号密度，值得进一步回测验证")
    elif stats_b["n_hit"] > stats_a["n_hit"]:
        print("  → 分位数排名略提高信号密度，改善有限")
    else:
        print("  → 分位数排名未提升信号密度")


if __name__ == "__main__":
    main()
