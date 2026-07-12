#!/usr/bin/env python3
"""tick分桶 skew + quantile 归一化 vs t-PIT 归一化 直接对比。

复用 evaluate_dataset 的 tier 分配逻辑，但把归一化从 roll_t_pit 换成滚动 quantile rank。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

from strategies.classifiers.poc_va import (  # noqa: E402
    DEFAULT_CONFIG,
    build_coordinates,
    classify_dataframe,
    tier_direction,
)

TL_PATH = REPO / "project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline_spec.parquet"
DEDUP_H = 8
CAP = 4.0


def roll_quantile(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """滚动 quantile rank：因果、无未来泄漏。返回 (0,1] 归一化值。"""
    if min_periods is None:
        min_periods = window
    return series.rolling(window, min_periods=min_periods).apply(
        lambda w: (np.sum(w < w[-1]) + np.sum(w == w[-1]) * 0.5) / len(w),
        raw=True,
    )


def evaluate_quantile(df: pd.DataFrame) -> pd.DataFrame:
    """用 quantile rank 替代 t-PIT，其余与 build_coordinates 一致。"""
    out = df.copy()

    def _by_contract(series: pd.Series, window: int) -> pd.Series:
        return series.groupby(out["contract"]).transform(lambda s: roll_quantile(s, window))

    config = DEFAULT_CONFIG
    r_s_raw = _by_contract(out["A3_skew_tick"].astype(float), config.skew_rank_win)
    out["r_s"] = 1.0 - r_s_raw
    out["r_a"] = _by_contract(out["daily_atr_spec"].astype(float), config.atr_rank_win)
    out["r_t"] = _by_contract(out["trend_ret_M_spec"].astype(float), config.trend_win)

    # trans 复用现有函数
    from strategies.classifiers.poc_va import compute_transition_series  # noqa: E402
    trans_parts = []
    for contract, g in out.groupby("contract", sort=False):
        state = compute_transition_series(g["r_a"])
        state["contract"] = contract
        trans_parts.append(state)
    trans_df = pd.concat(trans_parts).reindex(out.index)
    out["bucket"] = trans_df["bucket"]
    out["trans"] = trans_df["trans"]
    out["transition_flag"] = trans_df["transition_flag"]
    out["age"] = trans_df["age"]
    out["delta_recent"] = trans_df["delta_recent"]

    out["tier"] = classify_dataframe(out)
    out["direction"] = out["tier"].map(tier_direction)
    return out


def build_events_qt() -> pd.DataFrame:
    tl = pd.read_parquet(TL_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    result = evaluate_quantile(tl)
    df = result.dropna(subset=["tier"]).copy()
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = df.groupby("contract")["event_time"].shift(1)
    df = df[(prev.isna()) | ((df["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))]
    df["entry_atr_bps"] = df["daily_atr_spec"] / df["close_t"] * 10000.0
    return df


def main():
    from va_composite_p1_cap import (  # noqa: E402
        simulate_contract,
        compress,
        assign_equity,
        paired_delta,
        monthly_win_rate,
        per_trade_ir,
    )

    print("=" * 70)
    print("tick分桶 skew + quantile归一化 + spec v4.0六阵营")
    print("=" * 70)

    ev = build_events_qt()
    print(f"事件数: {len(ev)} | 合约: {ev['contract'].nunique()} | "
          f"多: {(ev['direction']=='long').sum()} / 空: {(ev['direction']=='short').sum()}")
    print(f"tier分布:\n{ev['tier'].value_counts().to_string()}")

    # 冻结引擎模拟
    print("\n[模拟] Cap={} ...".format(CAP))
    rows = []
    for c, g in ev.groupby("contract", sort=False):
        rows.extend(simulate_contract(c, g))
    trades = pd.DataFrame(rows)
    if trades.empty:
        print("无交易，退出")
        return
    trades["pnl"] = trades["delta_nu"].astype(float)
    trades = compress(trades, CAP)
    trades = assign_equity(trades)

    t = trades
    print(f"交易笔数: {len(t)} | 胜率: {t['win'].mean()*100:.1f}%")
    print(f"总盈亏: {t['pnl'].sum():.1f} | 最终权益: {t['equity'].iloc[-1]:.1f}")

    # 年化
    from datetime import datetime
    start = pd.to_datetime(t["entry_time"]).min()
    end = pd.to_datetime(t["exit_time"]).max()
    years = max((end - start).total_seconds() / 31536000, 0.01)
    init_eq = t["equity"].iloc[0]
    final_eq = t["equity"].iloc[-1]
    cagr = (final_eq / init_eq) ** (1 / years) - 1
    print(f"区间: {start.date()} → {end.date()} ({years:.2f}年)")
    print(f"年化: {cagr*100:.2f}% | 总收益: {t['pnl'].sum():.0f}")

    # 夏普
    daily_ret = t.groupby(t["entry_time"].dt.date)["pnl"].sum()
    daily_ret = daily_ret.reindex(pd.date_range(daily_ret.index.min(), daily_ret.index.max()), fill_value=0)
    sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(252) if daily_ret.std() > 0 else 0
    print(f"夏普: {sharpe:.2f} | 月胜率: {monthly_win_rate(t)*100:.1f}%")
    print(f"每笔IR: {per_trade_ir(t):.3f}")


if __name__ == "__main__":
    main()
