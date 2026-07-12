"""
文件级元信息：
- 创建背景：阶段 4 · 数据扩容后 · 自动扫描 CSV 目录构建扩容版数据集
- 用途：替代 stage2_grid_search.prepare_dataset · 使用全部已下载合约
- 注意事项：tick 由 contract_specs 自动查询 · 未知品种默认 tick=1.0
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
sys.path.insert(0, "/Users/gaolei/Documents/src/quant")

from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    ROLLING_DAYS, ROLLING_EVENTS, WARMUP_DAYS,
    build_daily_features, build_events, rolling_pct_rank,
)

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")


def get_tick(symbol: str) -> float:
    """按品种前缀查 tick · 未知返回 1.0."""
    tick_map: dict[str, float] = {
        # DCE
        "m": 1.0, "y": 1.0, "c": 1.0, "cs": 1.0, "i": 0.5, "p": 2.0,
        "j": 0.5, "jm": 0.5, "eg": 1.0, "eb": 1.0, "pg": 1.0,
        # SHFE
        "rb": 1.0, "cu": 10.0, "al": 5.0, "zn": 5.0, "au": 0.02, "ag": 1.0,
        "hc": 1.0, "pb": 5.0, "ni": 10.0, "sn": 10.0, "sp": 2.0, "ss": 5.0,
        "fu": 1.0, "ru": 5.0,
        # CZCE
        "SR": 1.0, "CF": 5.0, "TA": 2.0, "MA": 1.0, "OI": 1.0, "RM": 1.0,
        "FG": 1.0, "AP": 1.0, "CJ": 5.0, "SM": 2.0, "SF": 2.0,
        # INE
        "sc": 0.1, "lu": 1.0, "nr": 5.0,
    }
    _, contract = symbol.split(".")
    prefix = "".join(c for c in contract if c.isalpha())
    return tick_map.get(prefix, 1.0)


def discover_symbols() -> list[str]:
    """扫描 CSV 目录 · 返回所有 5m 合约."""
    symbols = []
    for p in CSV_DIR.glob("*.tqsdk.5m.csv"):
        symbol = p.name.replace(".tqsdk.5m.csv", "")
        symbols.append(symbol)
    return sorted(symbols)


def prepare_dataset_full() -> pd.DataFrame:
    """扩容版：自动扫描所有 CSV · tick 自动查询."""
    symbols = discover_symbols()
    print(f"发现 {len(symbols)} 个合约")

    all_events = []
    for i, sym in enumerate(symbols, 1):
        tick = get_tick(sym)
        try:
            ev = build_events(sym, tick)
            daily = build_daily_features(sym)
            ev = ev.merge(daily, left_on="event_date", right_on="date", how="left")
            all_events.append(ev)
            if i % 20 == 0:
                print(f"  [{i:>3}/{len(symbols)}] {sym} · {len(ev)} events")
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"  ERR {sym}: {e}")

    df = pd.concat(all_events, ignore_index=True)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    df["signed_skew_rank_roll"] = df.groupby("contract")["A3_skew"].transform(
        lambda s: rolling_pct_rank(s, ROLLING_EVENTS)
    )
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
    print(f"最终数据集：{len(df)} events · {df['contract'].nunique()} 合约")
    return df


if __name__ == "__main__":
    df = prepare_dataset_full()
    out_path = CSV_DIR.parent.parent / "logs/poc_va_asymmetry_stage4/dataset_full.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path)
    print(f"缓存：{out_path}")
