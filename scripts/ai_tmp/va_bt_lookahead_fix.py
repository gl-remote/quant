"""对照实验：修复 ATR/trend 的前视偏差（用前一日值而非当日值）。

原问题：build_daily_features 用当日 OHLC 计算 ATR/trend，events 按 event_date 合并，
       9:00 的事件拿到了当日的 H/L/Close → 前视。
修复：对 daily_atr_10_bps 和 trend_ret_10d 逐合约 shift(1)（A3_skew 已正确=前日偏度）。

两组对比：
  原口径(baseline)：A3(前日) + ATR(当日) + trend(当日)
  修复口径(fixed) ：A3(前日) + ATR(前日) + trend(前日)
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
sys.path.insert(0, str(REPO / "workspace"))

import va_composite_p1_cap as P1
from strategies.classifiers.poc_va import evaluate_dataset

DEDUP_H = 8

# ═══════════════════════════════════════════════════════════════════════
# 加载数据
tl = pd.read_parquet("project_data/ai_tmp/p0_calib/timeline_calAC.parquet")
tl["event_time"] = pd.to_datetime(tl["event_time"])
tl = tl.sort_values(["contract", "event_time"]).reset_index(drop=True)


def run_backtest(timeline: pd.DataFrame, label: str):
    """用 evaluate_dataset 分类 + P1 回测，返回 trades + 汇总。"""
    result = evaluate_dataset(
        timeline,
        a3_skew_col="A3_skew",
        atr_col="daily_atr_10_bps",
        trend_col="trend_ret_10d",
    )
    result["contract"] = timeline["contract"].values

    events = result.dropna(subset=["tier"]).copy()
    events = events[["contract", "event_time", "tier", "direction"]].merge(
        timeline[["contract", "event_time", "close_t", "daily_atr_10_bps"]],
        on=["contract", "event_time"], how="left",
    )
    events = events.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = events.groupby("contract")["event_time"].shift(1)
    events = events[
        (prev.isna()) | ((events["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))
    ].reset_index(drop=True)
    events["entry_atr_bps"] = events["daily_atr_10_bps"]

    if events.empty:
        print(f"  {label}: 无事件")
        return None, {}

    rows = []
    for c, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    trades = pd.DataFrame(rows)
    trades = P1.assign_equity(P1.compress(trades, 4.0))

    # 汇总
    eq = trades.sort_values("_entry_date").copy()
    eq["_entry_date"] = pd.to_datetime(eq["_entry_date"])

    ann_factor = 252
    annual_ret = eq["pnl_net_ccy"].sum() / eq["pnl_net_ccy"].count() * ann_factor
    stdev = eq["pnl_net_ccy"].std() * np.sqrt(ann_factor) if len(eq) > 1 else np.nan
    sharpe = annual_ret / stdev if stdev and stdev > 0 else np.nan

    cum = eq["pnl_net_ccy"].cumsum()
    dd = cum - cum.cummax()
    maxdd = dd.min()

    wins = eq[eq["pnl_net_ccy"] > 0]
    losses = eq[eq["pnl_net_ccy"] < 0]
    wr = len(wins) / len(eq) if len(eq) > 0 else np.nan
    wl = (
        abs(wins["pnl_net_ccy"].mean() / losses["pnl_net_ccy"].mean())
        if len(losses) > 0 else np.nan
    )

    # 月度
    eq["month"] = eq["_entry_date"].dt.to_period("M")
    month_ret = eq.groupby("month")["pnl_net_ccy"].sum()
    month_win = (month_ret > 0).mean()

    # OOS (后 50%)
    mid = len(eq) // 2
    oos = eq.iloc[mid:]
    oos_ret = oos["pnl_net_ccy"].sum()
    oos_sharpe = (
        oos["pnl_net_ccy"].mean() * ann_factor / (oos["pnl_net_ccy"].std() * np.sqrt(ann_factor))
        if len(oos) > 1 and oos["pnl_net_ccy"].std() > 0 else np.nan
    )

    multi = (events["direction"] == "long").sum()
    short = (events["direction"] == "short").sum()
    cap = 4.0

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  事件: {len(events)} 笔 (多{multi}/空{short}) | {events['contract'].nunique()} 合约")
    print(f"  交易: {len(eq)} 笔 | 胜率 {wr*100:.1f}% | 盈亏比 {wl:.2f}")
    print(f"  年化收益: {eq['pnl_net_ccy'].sum():.0f} | 夏普: {sharpe:.2f} | MaxDD: {maxdd*100:.2f}%")
    print(f"  月胜率: {month_win*100:.1f}% ({month_ret[month_ret>0].count()}/{len(month_ret)})")
    print(f"  OOS 夏普: {oos_sharpe:.2f}")

    return trades, {
        "label": label,
        "n_events": len(events),
        "n_trades": len(eq),
        "pnl": eq["pnl_net_ccy"].sum(),
        "sharpe": sharpe,
        "maxdd": maxdd,
        "wr": wr,
        "wl": wl,
        "month_win": month_win,
        "oos_sharpe": oos_sharpe,
    }


# ═══════════════════════════════════════════════════════════════════════
# 对照组 1: 原口径（baseline）
print("=" * 60)
print("  运行 baseline（原口径）...")
print("=" * 60)
_, m_base = run_backtest(tl.copy(), "baseline: ATR/trend 用当日值")

# ═══════════════════════════════════════════════════════════════════════
# 对照组 2: 修复口径
print("\n" + "=" * 60)
print("  运行 fixed（ATR/trend shift 1 天）...")
print("=" * 60)
tl_fixed = tl.copy()
# 逐合约 shift(1): 今日事件用昨日 ATR/trend
for c, g in tl_fixed.groupby("contract"):
    idx = g.index
    tl_fixed.loc[idx, "daily_atr_10_bps"] = g["daily_atr_10_bps"].shift(1)
    tl_fixed.loc[idx, "trend_ret_10d"] = g["trend_ret_10d"].shift(1)
# shift 后产生的 NaN: 这些事件没有前一天数据，分类器自然会判为 None tier → 丢弃
_, m_fixed = run_backtest(tl_fixed, "fixed: ATR/trend shift 1 天（前日值）")

# ═══════════════════════════════════════════════════════════════════════
# 对照组 3: 仅 ATR fix、trend 保持（隔离哪个贡献大）
print("\n" + "=" * 60)
print("  运行 atr-only-fix（仅 ATR shift 1 天）...")
print("=" * 60)
tl_atr_fix = tl.copy()
for c, g in tl_atr_fix.groupby("contract"):
    idx = g.index
    tl_atr_fix.loc[idx, "daily_atr_10_bps"] = g["daily_atr_10_bps"].shift(1)
_, m_atr = run_backtest(tl_atr_fix, "ATR fix only")

print("\n" + "=" * 60)
print("  运行 trend-only-fix（仅 trend shift 1 天）...")
print("=" * 60)
tl_trend_fix = tl.copy()
for c, g in tl_trend_fix.groupby("contract"):
    idx = g.index
    tl_trend_fix.loc[idx, "trend_ret_10d"] = g["trend_ret_10d"].shift(1)
_, m_trend = run_backtest(tl_trend_fix, "trend fix only")

# ═══════════════════════════════════════════════════════════════════════
# 汇总对比
print("\n" + "=" * 70)
print("  对比汇总")
print("=" * 70)
print(f"{'指标':<18s}  {'baseline':>10s}  {'fixed':>10s}  {'atr-fix':>10s}  {'trend-fix':>10s}")
for k in ["pnl", "sharpe", "maxdd", "wr", "wl", "month_win", "oos_sharpe"]:
    vals = [m_base.get(k), m_fixed.get(k), m_atr.get(k), m_trend.get(k)]
    fmt = []
    for v in vals:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            fmt.append("       N/A")
        elif isinstance(v, float):
            if abs(v) < 0.1:
                fmt.append(f"{v:10.4f}")
            else:
                fmt.append(f"{v:10.2f}")
        else:
            fmt.append(f"{v:>10}")
    print(f"  {k:<16s}  {'  '.join(fmt)}")

print(f"\n  n_events       baseline={m_base.get('n_events','?')}  fixed={m_fixed.get('n_events','?')}  atr-fix={m_atr.get('n_events','?')}  trend-fix={m_trend.get('n_events','?')}")
print(f"  n_trades       baseline={m_base.get('n_trades','?')}  fixed={m_fixed.get('n_trades','?')}  atr-fix={m_atr.get('n_trades','?')}  trend-fix={m_trend.get('n_trades','?')}")
