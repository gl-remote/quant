"""
文件级元信息：
- 创建背景：洞察 I 用 1h 级 ATR（12 根 5m TR 平均），发现"高 ATR 时 A3_skew 反向"。
  用户提出用**日线级 ATR** 结合，探索：
    (1) 不同日线 ATR 档位下 A3_skew 的表现
    (2) 是否形成趋势反转信号
    (3) 其他可能规律
  阶段 4 内容提前试。
- 用途：读 extended_long_events.csv（19 合约 7175 事件）
    Step 1 · 每合约从 5m bar 聚合日线 close，算 N 日 ATR
      N ∈ {5, 10, 14, 20}，用日线 True Range 的 N 日 rolling mean
    Step 2 · 每个 event 匹配前一日的日线 ATR
    Step 3 · 分档 (低/中/高) × A3_skew 触发（DN / UP / 中）做 3×3 交叉表
    Step 4 · 额外看：ATR 变化率（今日 ATR / 前 N 日 ATR）是否有增量
- 注意事项：日线 ATR = daily TR 的 N 日 rolling；单位 bps；ret_8h 是多头视角
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
EVENTS_PATH = LOG_DIR / "extended_long_events.csv"

ATR_N_LIST = [5, 10, 14, 20]  # 日线 ATR 窗口


def build_daily_atr(sym: str) -> pd.DataFrame:
    """从 5m bar 聚合成日线，然后算多个 N 日 ATR。"""
    bars = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.5m.csv")
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars["date"] = bars["datetime"].dt.date
    daily = bars.groupby("date").agg(
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        open=("open", "first"),
    ).reset_index()
    daily = daily.sort_values("date").reset_index(drop=True)

    prev_close = daily["close"].shift(1)
    tr = np.maximum.reduce([
        (daily["high"] - daily["low"]).to_numpy(),
        (daily["high"] - prev_close).abs().to_numpy(),
        (daily["low"] - prev_close).abs().to_numpy(),
    ])
    daily["daily_tr"] = tr
    for n in ATR_N_LIST:
        daily[f"daily_atr_{n}"] = daily["daily_tr"].rolling(n).mean()
    # 归一化 ATR (占价格的 bps)
    for n in ATR_N_LIST:
        daily[f"daily_atr_{n}_bps"] = daily[f"daily_atr_{n}"] / daily["close"] * 1e4

    # ATR 变化率：今日 ATR_5 / 前 20 日 ATR_20
    daily["atr_ratio_short_long"] = daily["daily_atr_5"] / daily["daily_atr_20"]
    # 近 N 日趋势
    for n in [5, 10, 20]:
        daily[f"trend_ret_{n}d"] = np.log(daily["close"] / daily["close"].shift(n)) * 1e4

    return daily[["date"] + [f"daily_atr_{n}_bps" for n in ATR_N_LIST]
                 + ["atr_ratio_short_long"]
                 + [f"trend_ret_{n}d" for n in [5, 10, 20]]]


def main() -> None:
    print("加载事件表 + 补日线 ATR ...")
    df = pd.read_csv(EVENTS_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = df["event_time"].dt.date

    # 分合约补日线 ATR
    all_daily = []
    for sym, g in df.groupby("contract"):
        try:
            d = build_daily_atr(sym)
        except FileNotFoundError:
            continue
        d["contract"] = sym
        # 用前一日的日线 ATR 匹配（避免未来函数）
        d["match_date"] = d["date"]
        d["prev_date"] = d["date"]
        # 我们用 event 当日的 daily ATR（该 ATR 只用了 <= event_date - N 天的数据）
        # 简单做法：匹配 event_date == daily.date 的行
        all_daily.append(d)

    daily_all = pd.concat(all_daily, ignore_index=True)
    # 合并
    df = df.merge(
        daily_all,
        left_on=["contract", "event_date"],
        right_on=["contract", "date"],
        how="left",
    )
    df = df.dropna(subset=[f"daily_atr_{ATR_N_LIST[0]}_bps"])
    print(f"合并后事件数: {len(df)} · 合约数: {df['contract'].nunique()}")

    df["ret_bps"] = df["ret_8h"] * 1e4
    df["abs_skew"] = df["A3_skew"].abs()

    # 每合约内 rank
    for col in [f"daily_atr_{n}_bps" for n in ATR_N_LIST] + ["atr_ratio_short_long"]:
        df[f"{col}_rank"] = df.groupby("contract")[col].rank(pct=True)
    df["signed_skew_rank"] = df.groupby("contract")["A3_skew"].rank(pct=True)

    # ========================================================================
    # 分析 1 · A3_skew 与日线 ATR 相关性
    # ========================================================================
    print("\n" + "=" * 90)
    print("分析 1 · A3_skew ↔ 日线 ATR 相关性")
    print("=" * 90)
    for n in ATR_N_LIST:
        col = f"daily_atr_{n}_bps"
        sub = df[df[col].notna()]
        if len(sub) < 100:
            print(f"  ATR_{n:>2d}:  n={len(sub)} 太少，跳过")
            continue
        r_abs = stats.spearmanr(sub["abs_skew"], sub[col]).statistic
        r_sgn = stats.spearmanr(sub["A3_skew"], sub[col]).statistic
        print(f"  ATR_{n:>2d}:  n={len(sub):>5d}   Spearman(|skew|, ATR) = {r_abs:+.3f}   "
              f"Spearman(skew, ATR) = {r_sgn:+.3f}")

    # ========================================================================
    # 分析 2 · DN/UP × 日线 ATR 分档 3x3 表
    # ========================================================================
    for n in ATR_N_LIST:
        atr_col = f"daily_atr_{n}_bps_rank"
        print(f"\n\n" + "=" * 90)
        print(f"分析 2 · DN/UP × 日线 ATR_{n} 分档（3×3）")
        print("=" * 90)

        def q_label_atr(r: float) -> str:
            if r <= 0.33:
                return "low"
            if r >= 0.67:
                return "high"
            return "mid"

        def q_label_skew(r: float) -> str:
            if r <= 0.10:
                return "DN"
            if r >= 0.90:
                return "UP"
            if 0.40 <= r <= 0.60:
                return "mid"
            return "other"

        df["atr_grp"] = df[atr_col].apply(q_label_atr)
        df["skew_grp"] = df["signed_skew_rank"].apply(q_label_skew)

        print(f"\n{'skew':6s} × {'atr':6s}  {'n':>6s} {'mean':>9s} {'median':>9s} {'hit':>6s} "
              f"{'std':>8s}")
        for sg in ["DN", "mid", "UP"]:
            for ag in ["low", "mid", "high"]:
                sub = df[(df["skew_grp"] == sg) & (df["atr_grp"] == ag)]
                if len(sub) < 5:
                    continue
                r = sub["ret_bps"]
                print(f"{sg:6s}   {ag:6s}  {len(sub):>6d} {r.mean():>+9.2f} "
                      f"{r.median():>+9.2f} {(r>0).mean():>6.1%} {r.std():>8.1f}")
        # baseline
        r_all = df["ret_bps"]
        print(f"{'base':6s}   {'all':6s}  {len(r_all):>6d} {r_all.mean():>+9.2f} "
              f"{r_all.median():>+9.2f} {(r_all>0).mean():>6.1%} {r_all.std():>8.1f}")

    # ========================================================================
    # 分析 3 · ATR 变化率作 filter
    # ========================================================================
    print("\n\n" + "=" * 90)
    print("分析 3 · ATR 变化率 (5日 ATR / 20 日 ATR) 与 DN 事件")
    print("=" * 90)
    print("  ratio > 1 = 近期波动上升（可能进入动荡）· ratio < 1 = 波动下降（趋于平稳）")

    df["atr_ratio_rank"] = df.groupby("contract")["atr_ratio_short_long"].rank(pct=True)
    df["ratio_grp"] = df["atr_ratio_rank"].apply(
        lambda r: "rising" if r >= 0.67 else ("falling" if r <= 0.33 else "stable"))

    print(f"\n{'skew':6s} × {'ratio':10s}  {'n':>6s} {'mean':>9s} {'hit':>6s}")
    for sg in ["DN", "mid", "UP"]:
        for rg in ["falling", "stable", "rising"]:
            sub = df[(df["skew_grp"] == sg) & (df["ratio_grp"] == rg)]
            if len(sub) < 5:
                continue
            r = sub["ret_bps"]
            print(f"{sg:6s}   {rg:10s}  {len(sub):>6d} {r.mean():>+9.2f} {(r>0).mean():>6.1%}")

    # ========================================================================
    # 分析 4 · 日线 ATR × 趋势 filter × A3_skew (三重条件)
    # ========================================================================
    print("\n\n" + "=" * 90)
    print("分析 4 · 三重条件：日线 ATR_10 × 近 10 日趋势 × A3_skew")
    print("=" * 90)

    df["trend_10d_rank"] = df.groupby("contract")["trend_ret_10d"].rank(pct=True)
    df["trend_grp"] = df["trend_10d_rank"].apply(
        lambda r: "up" if r >= 0.67 else ("down" if r <= 0.33 else "flat"))
    df["atr10_grp"] = df["daily_atr_10_bps_rank"].apply(
        lambda r: "low" if r <= 0.5 else "high")

    print(f"\n{'skew':6s} × {'trend':6s} × {'atr10':6s}  {'n':>6s} {'mean':>9s} {'hit':>6s}")
    for sg in ["DN", "UP"]:
        for tg in ["down", "flat", "up"]:
            for ag in ["low", "high"]:
                sub = df[(df["skew_grp"] == sg) & (df["trend_grp"] == tg) &
                         (df["atr10_grp"] == ag)]
                if len(sub) < 5:
                    continue
                r = sub["ret_bps"]
                print(f"{sg:6s}   {tg:6s}   {ag:6s}  {len(sub):>6d} "
                      f"{r.mean():>+9.2f} {(r>0).mean():>6.1%}")

    # 保存
    out_cols = ["contract", "event_time", "A3_skew", "ret_8h"] + \
               [f"daily_atr_{n}_bps" for n in ATR_N_LIST] + \
               ["atr_ratio_short_long", "trend_ret_5d", "trend_ret_10d", "trend_ret_20d"]
    df[out_cols].to_csv(LOG_DIR / "daily_atr_events.csv", index=False)
    print(f"\n\nOutput: {LOG_DIR / 'daily_atr_events.csv'}")


if __name__ == "__main__":
    main()
