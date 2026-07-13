"""
文件级元信息：
- 创建背景：cu2601 在 W1 × A3_skew × q=8% × ret_8h 上 mean=+122.6 bps
  命中率 95%（38/40）· 是次强 rb2601 的 3.6 倍，明显异常。本脚本诊断
  该异常的可能原因。
- 用途：读 long_events.csv + cu2601 原始 5m CSV → 诊断
    (a) DN 事件的时间分布（是否聚集在几天）
    (b) DN 事件与整个样本 cu 价格趋势的关系（是否整体单边上涨样本）
    (c) 8h 后 close 采样时刻是否落在夜盘开盘 / 涨跌停附近
    (d) 事件重叠 / 相邻性
    (e) DN 组 hit 样本的具体 log_ret 分布 vs 全样本分布
- 注意事项：临时诊断脚本，仅用于本次排查，不长期保留。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"
CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")

SYMBOL = "SHFE.cu2601"
WINDOW = "W1"
METRIC = "A3_skew"
QUANTILE = 0.08


def main() -> None:
    # ============ 载入 long table + 原始 5m ============
    long_df = pd.read_csv(LONG_PATH)
    long_df["event_time"] = pd.to_datetime(long_df["event_time"])

    bars = pd.read_csv(CSV_DIR / f"{SYMBOL}.tqsdk.5m.csv")
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)

    print(f"=== {SYMBOL} 5m bar 全样本 ===")
    print(f"日期范围: {bars['datetime'].min()} -> {bars['datetime'].max()}")
    print(f"总行数: {len(bars)}")
    print(f"close 首/尾/最低/最高: "
          f"{bars['close'].iloc[0]:.0f} / {bars['close'].iloc[-1]:.0f} / "
          f"{bars['close'].min():.0f} / {bars['close'].max():.0f}")
    total_ret_bps = math.log(bars["close"].iloc[-1] / bars["close"].iloc[0]) * 1e4
    print(f"全样本 log ret: {total_ret_bps:.1f} bps ({total_ret_bps/100:.2f}%)")
    trading_days = bars["datetime"].dt.date.nunique()
    print(f"交易日数: {trading_days}")
    print(f"平均日涨跌 (log): {total_ret_bps/trading_days:.2f} bps/day")

    # ============ 提取 cu 的 W1 events ============
    cu_events = long_df[
        (long_df["contract"] == SYMBOL) & (long_df["window"] == WINDOW)
    ].copy()
    cu_events["date"] = cu_events["event_time"].dt.date
    print(f"\n=== cu2601 × W1 全部 1h events ===")
    print(f"events: {len(cu_events)}")
    print(f"date 覆盖: {cu_events['date'].min()} -> {cu_events['date'].max()}")

    # ============ 按 q=8% 阈值筛出 DN/UP ============
    lo = cu_events[METRIC].quantile(QUANTILE)
    hi = cu_events[METRIC].quantile(1 - QUANTILE)
    dn = cu_events[cu_events[METRIC] <= lo].copy()
    up = cu_events[cu_events[METRIC] >= hi].copy()
    print(f"\n阈值: DN <= {lo:.3f}  |  UP >= {hi:.3f}")
    print(f"DN 事件数: {len(dn)}  |  UP 事件数: {len(up)}")

    # ============ DN 事件时间分布 ============
    print("\n=== DN 事件按日期聚集情况 ===")
    dn_by_date = dn.groupby("date").size().sort_values(ascending=False)
    print(f"unique dates: {dn_by_date.size}")
    print("按日事件数 top 10:")
    print(dn_by_date.head(10).to_string())

    # ============ DN 事件的 8h 后 ret 分布 ============
    dn_valid = dn.dropna(subset=["ret_8h"]).copy()
    print("\n=== DN 事件 ret_8h 分布（bps）===")
    r_bps = dn_valid["ret_8h"] * 1e4
    print(f"n={len(r_bps)}  mean={r_bps.mean():.2f}  median={r_bps.median():.2f}")
    print(f"min/p10/p50/p90/max: "
          f"{r_bps.min():.1f} / {r_bps.quantile(0.10):.1f} / "
          f"{r_bps.quantile(0.50):.1f} / {r_bps.quantile(0.90):.1f} / "
          f"{r_bps.max():.1f}")
    print(f"hit_pos (r>0): {(r_bps > 0).mean():.2%}")
    print(f"top 10 大 ret_8h 事件（按 ret_8h 降序）：")
    top = dn_valid.sort_values("ret_8h", ascending=False).head(10)
    for _, row in top.iterrows():
        print(f"  {row['event_time']}  close_t={row['close_t']:.0f}  "
              f"skew={row[METRIC]:.3f}  ret_8h={row['ret_8h']*1e4:+.1f} bps")

    # ============ 检查事件重叠 ============
    # 每个 event 持有 8h = 96 根 5m bar，相邻事件时间差 < 8h 则重叠
    print("\n=== DN 事件相邻间隔（同一次趋势可能被多次计入）===")
    dn_sorted = dn_valid.sort_values("event_time").reset_index(drop=True)
    dn_sorted["gap_hours"] = dn_sorted["event_time"].diff().dt.total_seconds() / 3600
    overlap_count = int((dn_sorted["gap_hours"] < 8).sum())
    print(f"相邻 gap < 8h 的对数（意味着 8h 持仓重叠）: {overlap_count} / {len(dn_sorted)-1}")
    print(f"gap 分布: min={dn_sorted['gap_hours'].min():.1f}h  "
          f"median={dn_sorted['gap_hours'].median():.1f}h  "
          f"max={dn_sorted['gap_hours'].max():.1f}h")
    # 按每 24h 窗口聚合，看是否存在"一天多次 DN 事件"
    dn_valid["dt_hour"] = dn_valid["event_time"].dt.floor("h")
    print("\n=== 每日 DN 事件数 + 当日 mean ret_8h ===")
    daily = dn_valid.groupby("date").agg(
        n=("ret_8h", "size"), mean_ret_8h_bps=("ret_8h", lambda x: x.mean() * 1e4)
    ).sort_values("mean_ret_8h_bps", ascending=False)
    print(daily.head(15).to_string())

    # ============ 去重后重算：每个 date 只取第一个 DN 事件 ============
    print("\n=== 若每天最多算一次 DN 事件（去除时间重叠）===")
    dedup = dn_valid.sort_values("event_time").drop_duplicates(subset="date", keep="first")
    r_dedup = dedup["ret_8h"] * 1e4
    print(f"n={len(dedup)}  mean={r_dedup.mean():.2f}  median={r_dedup.median():.2f}  "
          f"hit_pos={(r_dedup>0).mean():.2%}")

    # ============ 更严：相邻事件间隔 >= 8h 才保留 ============
    print("\n=== 若相邻事件必须间隔 >= 8h（无重叠）===")
    kept: list[pd.Timestamp] = []
    for _, row in dn_valid.sort_values("event_time").iterrows():
        if not kept or (row["event_time"] - kept[-1]).total_seconds() / 3600 >= 8:
            kept.append(row["event_time"])
    non_overlap = dn_valid[dn_valid["event_time"].isin(kept)]
    r_no = non_overlap["ret_8h"] * 1e4
    print(f"n={len(non_overlap)}  mean={r_no.mean():.2f}  median={r_no.median():.2f}  "
          f"hit_pos={(r_no>0).mean():.2%}")

    # ============ 与随机采样对照：随机抽 40 个 event 计算 ret_8h ============
    print("\n=== 与随机 40 事件对照（作为 no-signal baseline）===")
    rng = np.random.default_rng(20260707)
    all_ret_8h = cu_events["ret_8h"].dropna() * 1e4
    print(f"全 events ret_8h: n={len(all_ret_8h)}  mean={all_ret_8h.mean():.2f} bps  "
          f"median={all_ret_8h.median():.2f}  hit_pos={(all_ret_8h>0).mean():.2%}")
    boot_means = []
    for _ in range(5000):
        sample = rng.choice(all_ret_8h.values, size=40, replace=False)
        boot_means.append(sample.mean())
    boot_arr = np.array(boot_means)
    print(f"随机抽 40 事件 mean 分布：p2.5={np.percentile(boot_arr, 2.5):.2f}  "
          f"p97.5={np.percentile(boot_arr, 97.5):.2f}  mean={boot_arr.mean():.2f}")
    print(f"DN 组观测 mean={r_bps.mean():.2f}, 相对随机 40 事件的分位: "
          f"{(boot_arr <= r_bps.mean()).mean():.4%}")

    # ============ 检查 5m 全样本自相关（看漂移程度）============
    bars["log_ret_5m"] = np.log(bars["close"] / bars["close"].shift(1))
    daily_bars = bars.groupby(bars["datetime"].dt.date).agg(
        first_close=("close", "first"), last_close=("close", "last")
    ).reset_index()
    daily_bars["log_ret_day"] = np.log(daily_bars["last_close"] / daily_bars["first_close"]) * 1e4
    print("\n=== 每日日内 log ret 分布（bps）===")
    dr = daily_bars["log_ret_day"]
    print(f"n_days={len(dr)}  mean={dr.mean():.2f}  median={dr.median():.2f}  "
          f"std={dr.std():.2f}")
    print(f"正天数: {(dr>0).sum()} / {len(dr)}  "
          f"平均正日 {dr[dr>0].mean():.1f} bps · 平均负日 {dr[dr<0].mean():.1f} bps")


if __name__ == "__main__":
    main()
