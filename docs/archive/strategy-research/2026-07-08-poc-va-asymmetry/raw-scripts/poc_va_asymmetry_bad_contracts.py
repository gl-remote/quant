"""
文件级元信息：
- 创建背景：rb / SR / p 三个合约在 W1 × A3_skew 主线上方向反（DN 做多 net<0）。
  需要排查是"单边趋势主导（类似 cu）" · "A3_skew 分布结构性偏差" ·
  "样本期特殊事件"三种原因中的哪种。
- 用途：对每个反向合约展开：
  (1) 全样本期价格走势（起止 close · 全样本 log ret · 全样本 mean ret_8h）
  (2) A3_skew 分布诊断（是否显著偏斜、是否与其他合约类似）
  (3) DN 事件的日期聚集情况（是否只来自 3-5 天）
  (4) DN 事件的 ret_8h top/bottom 展示（是否几个大负样本主导）
  (5) 和 top 合约（sc/al）的对照差异
- 注意事项：临时诊断脚本；ret_8h 单位 bps。
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
LONG_PATH = LOG_DIR / "long_events.csv"

BAD_SYMBOLS = ["SHFE.rb2601", "CZCE.SR601", "DCE.p2601"]
GOOD_SYMBOLS = ["INE.sc2512", "SHFE.al2601"]  # 对照
WINDOW = "W1"
METRIC = "A3_skew"
K_SIGMA = 1.5
DEDUP_GAP_HOURS = 8.0


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def diag(long_df: pd.DataFrame, symbol: str, tag: str) -> None:
    print(f"\n{'='*90}\n=== [{tag}] {symbol} ===\n{'='*90}")

    # 原始 5m 走势
    bars = pd.read_csv(CSV_DIR / f"{symbol}.tqsdk.5m.csv")
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)
    total_days = bars["datetime"].dt.date.nunique()
    total_log_ret_bps = np.log(bars["close"].iloc[-1] / bars["close"].iloc[0]) * 1e4
    print(f"5m 全样本: {bars['datetime'].min().date()} → {bars['datetime'].max().date()} "
          f"({total_days} 交易日 · {len(bars)} bar)")
    print(f"  close 首/尾: {bars['close'].iloc[0]:.2f} → {bars['close'].iloc[-1]:.2f}  "
          f"= 总 log ret: {total_log_ret_bps:+.1f} bps ({total_log_ret_bps/100:+.2f}%)")

    # 全 events baseline
    events = long_df[
        (long_df["contract"] == symbol) & (long_df["window"] == WINDOW)
    ].copy()
    events["event_time"] = pd.to_datetime(events["event_time"])
    ret_all = events["ret_8h"].dropna() * 1e4
    print(f"\n全 events (W1) mean_ret_8h: {ret_all.mean():+.2f} bps  "
          f"(n={len(ret_all)} · hit={(ret_all>0).mean():.1%})")

    # A3_skew 分布
    skew = events[METRIC].dropna()
    print(f"\nA3_skew 分布:")
    print(f"  n={len(skew)}  mean={skew.mean():+.3f}  std={skew.std():.3f}  "
          f"skewness={stats.skew(skew):+.3f}  kurt={stats.kurtosis(skew):+.3f}")
    print(f"  分位 p05/p25/p50/p75/p95: "
          f"{np.quantile(skew, 0.05):+.3f} / {np.quantile(skew, 0.25):+.3f} / "
          f"{np.quantile(skew, 0.50):+.3f} / {np.quantile(skew, 0.75):+.3f} / "
          f"{np.quantile(skew, 0.95):+.3f}")

    # DN 事件（k=1.5σ）
    std_c = skew.std()
    dn_thr = -K_SIGMA * std_c
    dn = events[events[METRIC] <= dn_thr].copy()
    dn_dedup = dedup_gap(dn, DEDUP_GAP_HOURS)

    print(f"\nDN 事件 (skew ≤ {dn_thr:+.3f}, k={K_SIGMA}σ):")
    print(f"  原始: n={len(dn)} · dedup_8h: n={len(dn_dedup)}")
    if len(dn_dedup) > 0:
        r_dn = dn_dedup["ret_8h"] * 1e4
        print(f"  DN dedup ret_8h: mean={r_dn.mean():+.2f}  median={r_dn.median():+.2f}  "
              f"hit={(r_dn>0).mean():.1%}")
        # 日期聚集
        dn_dedup["date"] = dn_dedup["event_time"].dt.date
        unique_dates = dn_dedup["date"].nunique()
        print(f"  DN 事件覆盖 {unique_dates} 个不同交易日 (n_events={len(dn_dedup)}, "
              f"每日均值 {len(dn_dedup)/unique_dates:.1f})")
        # top / bottom 5 展开
        r_sorted = dn_dedup.sort_values("ret_8h")
        print(f"\n  bottom 5 DN 事件 (亏损最大):")
        for _, row in r_sorted.head(5).iterrows():
            print(f"    {row['event_time']}  close={row['close_t']:.2f}  "
                  f"skew={row[METRIC]:+.3f}  ret_8h={row['ret_8h']*1e4:+.1f} bps")
        print(f"\n  top 5 DN 事件 (盈利最大):")
        for _, row in r_sorted.tail(5).iloc[::-1].iterrows():
            print(f"    {row['event_time']}  close={row['close_t']:.2f}  "
                  f"skew={row[METRIC]:+.3f}  ret_8h={row['ret_8h']*1e4:+.1f} bps")


def main() -> None:
    long_df = pd.read_csv(LONG_PATH)

    print("\n\n" + "#" * 90)
    print("# 反向合约诊断（rb / SR / p）")
    print("#" * 90)
    for sym in BAD_SYMBOLS:
        diag(long_df, sym, "BAD")

    print("\n\n" + "#" * 90)
    print("# 正向合约对照（sc / al）")
    print("#" * 90)
    for sym in GOOD_SYMBOLS:
        diag(long_df, sym, "GOOD")


if __name__ == "__main__":
    main()
