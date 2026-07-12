#!/usr/bin/env python3
"""从原始 5m CSV 按 spec §1.1 重新生成 A3_skew / daily_atr / trend_ret_M。

现有 timeline 列来自旧管线（tick 分桶 profile skew + bps 缩放），与 spec 不一致。
本脚本按 spec 函数 volume_weighted_skew / daily_atr_sma / trend_log_return 重新计算。

输出: project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline_spec.parquet
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "workspace"))

from strategies.classifiers.poc_va import (  # noqa: E402
    daily_atr_sma,
    trend_log_return,
    volume_weighted_skew,
)

TL_PATH = REPO / "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet"
MARKET_DIR = REPO / "project_data/market_data/csv"
OUT_PATH = REPO / "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline_spec.parquet"

ATR_WIN = 10   # spec §0: atr_entry_win
TREND_WIN = 10  # spec §0: trend_entry_win


def _daily_bars(csv_path: Path) -> pd.DataFrame:
    """从 5m CSV 构建日线 OHLC + 成交量。"""
    bars = pd.read_csv(csv_path, usecols=["datetime", "open", "high", "low", "close", "volume"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars["date"] = bars["datetime"].dt.date

    daily = bars.groupby("date").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    return daily.sort_values("date").reset_index(drop=True)


def _session_skew(csv_path: Path) -> pd.Series:
    """逐 session 的量加权偏度 A3_skew，返回 date → A3_skew Series。"""
    bars = pd.read_csv(csv_path, usecols=["datetime", "close", "volume"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars["date"] = pd.to_datetime(bars["datetime"].dt.date)

    results: dict[pd.Timestamp, float] = {}
    for date_val, g in bars.groupby("date"):
        prices = g["close"].to_numpy(dtype=float)
        volumes = g["volume"].to_numpy(dtype=float)
        results[date_val] = volume_weighted_skew(prices, volumes)

    return pd.Series(results, name="A3_skew_spec").sort_index()


def regenerate_contract(contract: str) -> pd.DataFrame | None:
    """单个合约：计算三参数日序列。"""
    p = MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not p.exists():
        print(f"  SKIP {contract}: no csv")
        return None

    daily = _daily_bars(p)
    if len(daily) < max(ATR_WIN, TREND_WIN) + 1:
        print(f"  SKIP {contract}: too few daily bars ({len(daily)})")
        return None

    # A3_skew（逐 session）
    a3 = _session_skew(p)
    daily["A3_skew_spec"] = daily["date"].map(a3)

    # ATR（spec: 原始 ATR，非 bps）
    daily["daily_atr_spec"] = daily_atr_sma(
        daily["high"], daily["low"], daily["close"], ATR_WIN
    )

    # trend（spec: 原始 log return，非 bps×10000）
    daily["trend_ret_M_spec"] = trend_log_return(daily["close"], TREND_WIN)

    return daily[["date", "A3_skew_spec", "daily_atr_spec", "trend_ret_M_spec"]]


def main() -> None:
    print("=" * 70)
    print("重新生成 spec 三参数: A3_skew / daily_atr / trend_ret_M")
    print(f"  输入: {TL_PATH}")
    print(f"  CSV: {MARKET_DIR}")
    print(f"  输出: {OUT_PATH}")
    print("=" * 70)

    # 1. 读取 timeline，获取合约列表
    tl = pd.read_parquet(TL_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    tl["event_date"] = pd.to_datetime(tl["event_date"])

    contracts = sorted(tl["contract"].unique())
    print(f"合约数: {len(contracts)}")
    print(f"原始事件行: {len(tl)}")

    # 2. 逐合约生成日线特征
    all_features: list[pd.DataFrame] = []
    skipped = 0
    for i, c in enumerate(contracts):
        if (i + 1) % 30 == 0:
            print(f"  [{i+1}/{len(contracts)}] {c} ...")
        daily = regenerate_contract(c)
        if daily is None:
            skipped += 1
            continue
        daily["contract"] = c
        all_features.append(daily)

    print(f"完成: {len(all_features)} 合约, 跳过 {skipped}")
    features = pd.concat(all_features, ignore_index=True)

    # 3. 将新列 join 到 timeline（按 contract + event_date）
    #    注意：A3_skew 使用 event 日期的特征（与"日内恒定"约定一致）
    tl_out = tl.merge(
        features,
        left_on=["contract", "event_date"],
        right_on=["contract", "date"],
        how="left",
    )

    # 4. 检查缺失
    missing = tl_out["A3_skew_spec"].isna().sum()
    print(f"A3_skew_spec 缺失: {missing} / {len(tl_out)}")
    print(f"daily_atr_spec 缺失: {tl_out['daily_atr_spec'].isna().sum()} / {len(tl_out)}")
    print(f"trend_ret_M_spec 缺失: {tl_out['trend_ret_M_spec'].isna().sum()} / {len(tl_out)}")

    # 5. 写出
    tl_out.to_parquet(OUT_PATH, index=False)
    print(f"\n写出: {OUT_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
