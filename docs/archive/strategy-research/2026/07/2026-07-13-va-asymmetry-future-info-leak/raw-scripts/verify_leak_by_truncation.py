#!/usr/bin/env python3
"""
泄漏铁证 · 截断法验证（最小复现版）
==========================================================
思路：同一份泄漏版代码，喂两份不同 daily 数据，看单事件的分类是否一致。

  full  数据: 完整 CSV → daily 聚合到 event_date 当天（会用到 event_time 之后的 bars）
  trunc 数据: CSV 只保留 datetime <= event_time → daily 聚合（不含未来 bar）

对同一个 event_date，把两版 daily 分别喂给 poc_va.evaluate_dataset（只截取
[event_date - N 天, event_date] 窗口，N ≥ classifier_win + trans_win = 12），
比较 A3_skew_spec / r_s / tier / direction。

如果 full 与 trunc 有差异 → 铁证泄漏（唯一区别是 event_time 之后的 bars 可见性）。
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path("/Users/gaolei/Documents/src/quant")
sys.path.insert(0, str(REPO / "workspace"))

from strategies.classifiers.poc_va import (  # noqa: E402
    ClassifierConfig,
    daily_atr_sma,
    evaluate_dataset,
    trend_log_return,
    volume_weighted_skew,
)

CSV_DIR = REPO / "project_data/market_data/csv"
ATR_ENTRY_WIN = 10
TREND_ENTRY_WIN = 10
CLASSIFIER_WINDOW = 40  # 足够覆盖 skew_rank_win(10) + trans_win(12) + margin


# =====================================================================
# 泄漏版 daily 特征计算（不 shift）
# =====================================================================
def build_daily_features_from_bars(bars: pd.DataFrame) -> pd.DataFrame:
    b = bars.copy()
    b["date"] = pd.to_datetime(b["datetime"].dt.date)

    daily = b.groupby("date").agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index().sort_values("date").reset_index(drop=True)

    if len(daily) < max(ATR_ENTRY_WIN, TREND_ENTRY_WIN) + 1:
        return pd.DataFrame()

    a3_map: dict = {}
    for date_val, g in b.groupby("date"):
        prices = g["close"].to_numpy(dtype=float)
        volumes = g["volume"].to_numpy(dtype=float)
        a3_map[pd.Timestamp(date_val)] = volume_weighted_skew(prices, volumes)
    daily["A3_skew_spec"] = daily["date"].map(a3_map)
    daily["daily_atr_spec"] = daily_atr_sma(
        daily["high"], daily["low"], daily["close"], ATR_ENTRY_WIN
    )
    daily["trend_ret_M_spec"] = trend_log_return(daily["close"], TREND_ENTRY_WIN)
    return daily[["date", "A3_skew_spec", "daily_atr_spec", "trend_ret_M_spec"]]


def classify_at_event(daily_df: pd.DataFrame, symbol: str,
                      event_date: pd.Timestamp) -> dict | None:
    """把 daily_df 送 poc_va，只取 event_date 一行的 tier/direction/r_s"""
    if daily_df.empty:
        return None
    # 只保留 event_date 及之前的 daily（否则 roll_t_pit 会看到未来 daily）
    daily_df = daily_df[daily_df["date"] <= event_date].tail(CLASSIFIER_WINDOW).copy()
    if len(daily_df) < 12:
        return None
    # 伪装成 evaluate_dataset 需要的输入
    daily_df["contract"] = symbol
    daily_df["event_time"] = pd.to_datetime(daily_df["date"])
    daily_df["event_date"] = pd.to_datetime(daily_df["date"])
    config = ClassifierConfig()
    out = evaluate_dataset(
        daily_df, config,
        a3_skew_col="A3_skew_spec",
        atr_col="daily_atr_spec",
        trend_col="trend_ret_M_spec",
    )
    row = out[out["date"] == event_date]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "A3_skew_spec": float(r["A3_skew_spec"]),
        "daily_atr_spec": float(r["daily_atr_spec"]),
        "trend_ret_M_spec": float(r["trend_ret_M_spec"]),
        "r_s": float(r["r_s"]),
        "r_a": float(r["r_a"]),
        "r_t": float(r["r_t"]),
        "trans": r["trans"],
        "tier": r["tier"],
        "direction": r["direction"],
    }


def run_experiment_for_event(symbol: str, event_time: pd.Timestamp) -> dict | None:
    csv_path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    bars = pd.read_csv(csv_path)
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)

    event_date = pd.Timestamp(event_time.date())

    # A. 完整 CSV → daily
    daily_full = build_daily_features_from_bars(bars)
    r_full = classify_at_event(daily_full, symbol, event_date)

    # B. 截断到 event_time → daily
    bars_trunc = bars[bars["datetime"] <= event_time].reset_index(drop=True)
    daily_trunc = build_daily_features_from_bars(bars_trunc)
    r_trunc = classify_at_event(daily_trunc, symbol, event_date)

    if r_full is None or r_trunc is None:
        return {"skipped": True, "reason": f"full={r_full is None} trunc={r_trunc is None}"}

    return {
        "skipped": False, "symbol": symbol,
        "event_time": event_time, "event_date": event_date,
        "full": r_full, "trunc": r_trunc,
    }


def print_comparison(r: dict) -> None:
    if r.get("skipped"):
        print(f"    ⚠️  跳过: {r.get('reason')}")
        return
    print(f"\n{'='*90}")
    print(f"事件: {r['symbol']} @ {r['event_time']}  (event_date={r['event_date'].date()})")
    print(f"{'='*90}")
    print(f"{'字段':<18} {'全量泄漏版':>18} {'截断诚实版':>18}  说明")
    print("-" * 90)
    fields = [
        ("A3_skew_spec",     "%.6f"),
        ("daily_atr_spec",   "%.4f"),
        ("trend_ret_M_spec", "%.6f"),
        ("r_s",              "%.6f"),
        ("r_a",              "%.6f"),
        ("r_t",              "%.6f"),
        ("trans",            "%s"),
        ("tier",             "%s"),
        ("direction",        "%s"),
    ]
    for k, fmt in fields:
        v_full, v_trunc = r["full"][k], r["trunc"][k]
        try:
            match = "✅ 一致" if abs(float(v_full) - float(v_trunc)) < 1e-9 else "🔥 不同"
        except (TypeError, ValueError):
            match = "✅ 一致" if v_full == v_trunc else "🔥 不同"
        sf = (fmt % v_full) if v_full is not None else "None"
        st = (fmt % v_trunc) if v_trunc is not None else "None"
        print(f"{k:<18} {sf:>18} {st:>18}  {match}")


# =====================================================================
# Main
# =====================================================================
def main() -> None:
    events_path = REPO / "docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side/events.parquet"
    trades_path = REPO / "docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side/trades.parquet"

    events = pd.read_parquet(events_path)
    trades = pd.read_parquet(trades_path)
    trades["entry_bar"] = pd.to_datetime(trades["entry_bar"])
    events["event_time"] = pd.to_datetime(events["event_time"])

    pnl_map = trades.set_index(["contract", "entry_bar"])["pnl_net_ccy"].to_dict()
    events["pnl"] = [pnl_map.get((c, t), np.nan)
                     for c, t in zip(events["contract"], events["event_time"], strict=True)]
    ev_with_pnl = events.dropna(subset=["pnl"]).copy()

    t_sorted = ev_with_pnl.sort_values("pnl", ascending=False)
    picked = pd.concat([
        t_sorted.head(5).assign(bucket="TOP_WIN"),
        t_sorted.tail(5).assign(bucket="TOP_LOSS"),
        t_sorted.iloc[len(t_sorted)//2 - 2 : len(t_sorted)//2 + 3].assign(bucket="MID"),
    ], ignore_index=True)

    print(f"截断法泄漏验证（最小复现版）· 选取 {len(picked)} 个事件")
    print()

    results = []
    for _, row in picked.iterrows():
        sym = row["contract"]
        etime = pd.Timestamp(row["event_time"])
        print(f"\n>>> [{row['bucket']}] {sym} @ {etime}  pnl=¥{row['pnl']:+,.0f}  "
              f"orig_tier={row['tier']} orig_dir={row['direction']}")
        r = run_experiment_for_event(sym, etime)
        if r is not None:
            r["bucket"] = row["bucket"]
            r["actual_pnl"] = float(row["pnl"])
            print_comparison(r)
            results.append(r)

    # 汇总
    print("\n" + "=" * 90)
    print("汇总")
    print("=" * 90)
    total, dir_diff, tier_diff, val_diff, r_s_diff = 0, 0, 0, 0, 0
    dir_flip_events: list[str] = []
    for r in results:
        if r.get("skipped"):
            continue
        total += 1
        if abs(r["full"]["A3_skew_spec"] - r["trunc"]["A3_skew_spec"]) > 1e-9:
            val_diff += 1
        if abs(r["full"]["r_s"] - r["trunc"]["r_s"]) > 1e-9:
            r_s_diff += 1
        if r["full"]["tier"] != r["trunc"]["tier"]:
            tier_diff += 1
        if r["full"]["direction"] != r["trunc"]["direction"]:
            dir_diff += 1
            dir_flip_events.append(
                f"{r['symbol']} @ {r['event_time']}: {r['full']['direction']} → {r['trunc']['direction']}"
            )

    print(f"  参与对比事件数:                {total}")
    print(f"  A3_skew_spec 值不同的事件:      {val_diff}/{total} ({100*val_diff/max(total,1):.0f}%)"
          f"  ← 铁证：full 用了 event_time 之后的 bars")
    print(f"  r_s 归一化值不同的事件:         {r_s_diff}/{total} ({100*r_s_diff/max(total,1):.0f}%)")
    print(f"  tier 分类不同的事件:            {tier_diff}/{total} ({100*tier_diff/max(total,1):.0f}%)")
    print(f"  direction 方向不同的事件:       {dir_diff}/{total} ({100*dir_diff/max(total,1):.0f}%)")

    if dir_flip_events:
        print("\n  🔥 方向反转案例:")
        for line in dir_flip_events:
            print(f"      · {line}")

    if val_diff == 0:
        print("\n  ❌ 无 A3_skew_spec 差异 → 未观察到泄漏")
    else:
        print(f"\n  🔥 结论：{val_diff}/{total} 事件的 A3_skew_spec 因看到未来 bar 而变化 → 泄漏存在")


if __name__ == "__main__":
    main()
