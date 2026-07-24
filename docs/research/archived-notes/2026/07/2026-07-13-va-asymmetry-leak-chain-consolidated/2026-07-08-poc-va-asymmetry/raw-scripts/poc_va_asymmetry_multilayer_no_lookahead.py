"""
文件级元信息：
- 创建背景：daily_atr / conditional_alpha / event_vs_nonevent 系列脚本用了
  全样本 rank 分位，含"轻度未来信息"。本脚本把三个 rank 全部换成 rolling
  版本，做严格无未来函数验证。
- 用途：读 daily_atr_events.csv → 用 rolling rank 重算三层组合的 cluster
  bootstrap CI，对比原（含未来）结果。
    三个 rolling rank:
      (a) signed_skew rank -> 前 200 事件的 rolling rank
      (b) daily_atr_10 rank -> 前 60 交易日的 rolling rank
      (c) trend_ret_10d rank -> 前 60 交易日的 rolling rank
    warmup 期: 每合约前 60 交易日 + 前 200 事件（取严格者），跳过评估
    然后重跑 5 个候选的 cluster bootstrap CI
- 注意事项：rolling rank 需要按 event_time 排序 + 严格前向；ret_8h 单位 bps
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
DAILY_PATH = LOG_DIR / "daily_atr_events.csv"

BOOTSTRAP_N = 5000
RNG_SEED = 20260707
ROLLING_EVENTS = 100      # skew rolling 事件窗口（缩短，60-72 天数据平均 300+ 事件够用）
ROLLING_DAYS = 20         # ATR / trend rolling 日线窗口（4 周）
WARMUP_DAYS = 20          # 排除前 20 交易日


def rolling_pct_rank(series: pd.Series, window: int) -> pd.Series:
    """严格前向的 rolling rank：第 i 行的 rank 只用 [i-window, i-1]。"""
    def rank_last(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        # 用前 window-1 个值算 rank
        past = x.iloc[:-1]
        return (past <= current).sum() / len(past)
    return series.rolling(window, min_periods=10).apply(rank_last, raw=False)


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
    ci_lo_one_sided = float(np.quantile(valid, 0.05))
    p_two = 2 * min((valid <= 0).mean(), (valid >= 0).mean())
    return {
        "n_events": len(events),
        "n_contracts": len(contracts),
        "real_mean": real_mean,
        "ci_lo_95": ci_lo,
        "ci_hi_95": ci_hi,
        "ci_lo_90_one_sided": ci_lo_one_sided,
        "p_two": p_two,
    }


def report(label: str, mask: pd.Series, df: pd.DataFrame,
           short_view: bool = False) -> None:
    sub = df[mask].dropna(subset=["ret_bps"])
    if len(sub) < 5:
        print(f"\n【{label}】\n  ⚠️ 样本不足 n={len(sub)}")
        return
    if short_view:
        sub = sub.assign(pnl_bps=-sub["ret_bps"])
        stats = cluster_bootstrap(sub, ret_col="pnl_bps")
        hit = (sub["ret_bps"] < 0).mean()
        view = "做空"
    else:
        stats = cluster_bootstrap(sub, ret_col="ret_bps")
        hit = (sub["ret_bps"] > 0).mean()
        view = "做多"
    print(f"\n【{label}】({view})")
    print(f"  n={stats['n_events']} · {stats['n_contracts']} 合约 · hit={hit:.1%}")
    print(f"  mean = {stats['real_mean']:+.2f} bps")
    print(f"  95% CI = [{stats['ci_lo_95']:+.2f}, {stats['ci_hi_95']:+.2f}]")
    print(f"  90% CI 下限 = {stats['ci_lo_90_one_sided']:+.2f}")
    print(f"  p_two = {stats['p_two']:.4f}")
    judge = "✅ 严格排 0" if stats['ci_lo_95'] > 0 else (
            "⚠️ 90% 单侧排 0" if stats['ci_lo_90_one_sided'] > 0 else "❌ CI 触 0")
    print(f"  判读: {judge}")


def main() -> None:
    print("加载 daily_atr_events.csv ...")
    df = pd.read_csv(DAILY_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = df["event_time"].dt.date
    df["ret_bps"] = df["ret_8h"] * 1e4
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)

    print(f"事件数: {len(df)} · 合约数: {df['contract'].nunique()}")

    # ========================================================================
    # 三个 rolling rank
    # ========================================================================
    print("\n构建 rolling rank ...")

    # (a) skew rolling 200 事件（事件级）
    print("  (a) signed_skew_rank_rolling200 ...")
    df["signed_skew_rank_roll"] = df.groupby("contract")["A3_skew"].transform(
        lambda s: rolling_pct_rank(s, ROLLING_EVENTS))

    # (b) daily_atr_10_bps rolling 60 日（日线级 → 事件级）
    print("  (b) daily_atr_10_rank_rolling60d ...")
    daily_atr_series = []
    for c, g in df.groupby("contract"):
        # 提取 (event_date, atr_10) 唯一对
        daily = g.drop_duplicates("event_date").sort_values("event_date").copy()
        daily["atr_rank_roll"] = rolling_pct_rank(daily["daily_atr_10_bps"], ROLLING_DAYS)
        daily_atr_series.append(daily[["contract", "event_date", "atr_rank_roll"]])
    daily_atr_map = pd.concat(daily_atr_series, ignore_index=True)
    df = df.merge(daily_atr_map, on=["contract", "event_date"], how="left")

    # (c) trend_ret_10d rolling 60 日
    print("  (c) trend_ret_10d_rank_rolling60d ...")
    trend_series = []
    for c, g in df.groupby("contract"):
        daily = g.drop_duplicates("event_date").sort_values("event_date").copy()
        daily["trend_rank_roll"] = rolling_pct_rank(daily["trend_ret_10d"], ROLLING_DAYS)
        trend_series.append(daily[["contract", "event_date", "trend_rank_roll"]])
    trend_map = pd.concat(trend_series, ignore_index=True)
    df = df.merge(trend_map, on=["contract", "event_date"], how="left")

    # Warmup 排除
    print(f"\n排除每合约前 {WARMUP_DAYS} 交易日 + 前 {ROLLING_EVENTS} 事件 ...")
    def apply_warmup(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("event_time").reset_index(drop=True)
        # 交易日 warmup
        all_dates = sorted(g["event_date"].unique())
        if len(all_dates) < WARMUP_DAYS:
            return g.iloc[0:0]
        warmup_end = all_dates[WARMUP_DAYS - 1]
        g = g[g["event_date"] > warmup_end]
        return g

    # Warmup 排除：每合约前 WARMUP_DAYS 交易日的事件跳过
    print(f"\n排除每合约前 {WARMUP_DAYS} 交易日 + 前 {ROLLING_EVENTS} 事件 ...")
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

    # ========================================================================
    # 分组
    # ========================================================================
    def q_skew(r: float) -> str:
        if r <= 0.10:
            return "DN"
        if r >= 0.90:
            return "UP"
        return "mid"

    def q_trend(r: float) -> str:
        if r <= 0.33:
            return "down"
        if r >= 0.67:
            return "up"
        return "flat"

    def q_atr(r: float) -> str:
        return "low" if r <= 0.5 else "high"

    df["skew_grp"] = df["signed_skew_rank_roll"].apply(q_skew)
    df["trend_grp"] = df["trend_rank_roll"].apply(q_trend)
    df["atr10_grp"] = df["atr_rank_roll"].apply(q_atr)

    # ========================================================================
    # 5 个候选重跑
    # ========================================================================
    print("\n" + "=" * 90)
    print("严格无未来函数版本 · 5 个候选的 cluster bootstrap CI")
    print("=" * 90)

    print("\n" + "-" * 90)
    print("候选 1 · 多头主线增强 · DN + up + low ATR_10")
    print("-" * 90)
    mask = (df["skew_grp"] == "DN") & (df["trend_grp"] == "up") & (df["atr10_grp"] == "low")
    report("DN + up + low ATR_10", mask, df)

    print("\n" + "-" * 90)
    print("候选 2 · 空头反转 A · DN + flat + high ATR_10（做空）")
    print("-" * 90)
    mask = (df["skew_grp"] == "DN") & (df["trend_grp"] == "flat") & (df["atr10_grp"] == "high")
    report("DN + flat + high ATR_10", mask, df, short_view=True)

    print("\n" + "-" * 90)
    print("候选 4 · 单层对照 · DN + low ATR_10")
    print("-" * 90)
    mask = (df["skew_grp"] == "DN") & (df["atr10_grp"] == "low")
    report("DN + low ATR_10", mask, df)

    print("\n" + "-" * 90)
    print("候选 单层 · DN 单独（同当前主线，替换 rolling skew rank）")
    print("-" * 90)
    mask = df["skew_grp"] == "DN"
    report("DN 单独", mask, df)

    # ========================================================================
    # 对比：单层原口径（sigma_full 已在洞察 E 报 CI [+3.9, +74]）
    # ========================================================================
    print("\n" + "=" * 90)
    print("对比参照（含未来函数版本 · 已在 §7 报过）")
    print("=" * 90)
    print("  候选 1 (含未来): n=144 · mean=+58.0 · CI [+17.1, +114.9] · p=0.0008")
    print("  候选 2 (含未来): n=140 · short_mean=+42.9 · CI [-0.03, +85.3] · p=0.050")
    print("  候选 4 (含未来): n=286 · mean=+39.8 · CI [+9.7, +71.8] · p=0.0044")
    print("  单层 sigma_full: n=87 · mean=+32.2 · CI [+3.9, +74.0] · p=0.013")

    # 保存
    out_path = LOG_DIR / "multilayer_no_lookahead_events.csv"
    df.to_csv(out_path, index=False)
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
