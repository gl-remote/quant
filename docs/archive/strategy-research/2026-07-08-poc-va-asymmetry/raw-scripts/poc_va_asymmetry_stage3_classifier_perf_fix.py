"""
分类器指标修正 · 用正确的年化 Sharpe 口径重算 · 替代 classifier_stat_2 的错误 Sharpe

关键修正：
1. Sharpe 用"日度"而不是"每次交易"聚合 · sqrt(252) 而不是 sqrt(yearly_events)
2. 补充"单笔 IR"作为真正无假设的分类器指标
3. gross vs 假设扣 15 bps 成本双版本
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import prepare_dataset, parse_prefix  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)

TRADING_DAYS = 252
COST_BPS = 15.0  # realistic-cost 保守估计


def compute_annualized_sharpe(returns_bps: pd.Series, event_time: pd.Series, cost_bps: float = 0.0):
    """
    正确的年化 Sharpe 计算 · 按交易日聚合。

    - 输入：每笔交易的收益（bps）+ 触发时刻
    - 聚合：按 date 求和（多笔同一天累加 · 假设并行独立小仓位）
    - 年化：mean_daily / std_daily × sqrt(TRADING_DAYS)

    注：这仍然只是"分类器信号本身"的 Sharpe · 未考虑：
    - 仓位管理（Kelly / 定额）
    - 跨品种协方差
    - 具体入场出场的价格差
    """
    if len(returns_bps) < 20:
        return None

    df = pd.DataFrame({
        "date": pd.to_datetime(event_time).dt.date,
        "ret_bps": returns_bps.values - cost_bps,  # 扣除成本
    })

    # 按日聚合：每日累计收益（bps）· 假设每笔独立小仓位
    daily = df.groupby("date")["ret_bps"].sum()

    # 补齐无信号的日子为 0
    date_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily_full = daily.reindex(date_range, fill_value=0.0)

    if daily_full.std() == 0:
        return None

    # 年化 Sharpe
    mean_daily = daily_full.mean()
    std_daily = daily_full.std()
    sharpe = mean_daily / std_daily * np.sqrt(TRADING_DAYS)

    # 单笔 IR（无年化 · 直接 mean/std of trade-level returns after cost）
    trade_returns = df["ret_bps"].values
    ir_per_trade = trade_returns.mean() / trade_returns.std() if trade_returns.std() > 0 else 0

    # 期望年化 P&L（bps · 假设覆盖全年）
    n_days_active = (daily > 0).sum() + (daily < 0).sum()
    n_days_total = len(daily_full)
    active_ratio = n_days_active / n_days_total if n_days_total > 0 else 0

    # 简单估计 · 每年触发次数
    n_events = len(df)
    n_days_sample = n_days_total
    yearly_events_est = n_events * TRADING_DAYS / n_days_sample if n_days_sample > 0 else 0
    annual_mean_bps = trade_returns.mean() * yearly_events_est

    return {
        "n_events": n_events,
        "n_days_sample": n_days_total,
        "n_days_active": int(n_days_active),
        "active_ratio": active_ratio,
        "trade_mean_bps": trade_returns.mean(),
        "trade_std_bps": trade_returns.std(),
        "ir_per_trade": ir_per_trade,
        "daily_mean_bps": mean_daily,
        "daily_std_bps": std_daily,
        "sharpe_annualized": sharpe,
        "yearly_events_est": yearly_events_est,
        "annual_mean_bps_est": annual_mean_bps,
        "hit_rate": (trade_returns > 0).mean(),
    }


def run_combo(df, name, mask, ret_col):
    sub = df[mask].dropna(subset=[ret_col, "transition_flag", "event_time"])
    stable = sub[~sub["transition_flag"]]
    trans = sub[sub["transition_flag"]]

    rows = []
    for tag, seg in [("full", sub), ("stable", stable), ("trans", trans)]:
        if len(seg) < 20:
            continue
        for cost, cost_tag in [(0.0, "gross"), (COST_BPS, "net_15bps")]:
            metrics = compute_annualized_sharpe(seg[ret_col], seg["event_time"], cost_bps=cost)
            if metrics is None:
                continue
            metrics["combo"] = name
            metrics["period"] = tag
            metrics["cost"] = cost_tag
            rows.append(metrics)
    return rows


def main():
    print("=" * 100)
    print("分类器指标修正 · 正确年化 Sharpe（按交易日聚合 · sqrt(252)）+ 单笔 IR + 净收益版")
    print("=" * 100)
    print(f"\n注：年化口径 = 按 event_time 的日期聚合每日累计 bps · 年化 sqrt(252)")
    print(f"    单笔 IR = trade_mean / trade_std · 无年化 · 更贴近'分类器信号质量'\n")

    df = prepare_dataset()
    df = flag_regime_transition(df)

    signals = [
        ("多头首选", "long", 0.10, 0.70, 0.75, "ret_8h_bps"),
        ("多头宽松", "long", 0.30, 0.70, 0.75, "ret_8h_bps"),
        ("空头首选", "short", 0.70, 0.80, 0.20, "short_pnl_4h_bps"),
        ("空头宽松", "short", 0.70, 0.50, 0.20, "short_pnl_4h_bps"),
        ("空头收敛", "short", 0.70, 0.67, 0.20, "short_pnl_4h_bps"),
    ]

    rows = []
    for name, direction, sk, at, tr, ret_col in signals:
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= at) &
                    (df["trend_rank_roll"] >= tr))
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > at) &
                    (df["trend_rank_roll"] <= tr))
        rows.extend(run_combo(df, name, mask, ret_col))

    out_df = pd.DataFrame(rows)
    out_df.to_csv(LOG_DIR / "classifier_perf_corrected.csv", index=False)

    # 分组打印
    print(f"\n{'组合':12s} {'期别':8s} {'成本':10s} "
          f"{'n':>5s} {'日样本':>7s} {'活跃日':>7s} {'单笔mean':>10s} "
          f"{'单笔IR':>8s} {'年Sharpe':>10s} {'年触发':>8s} {'年P&L bps':>10s}")
    print("-" * 130)
    for _, r in out_df.iterrows():
        print(f"{r['combo']:12s} {r['period']:8s} {r['cost']:10s} "
              f"{int(r['n_events']):>5d} {int(r['n_days_sample']):>7d} {int(r['n_days_active']):>7d} "
              f"{r['trade_mean_bps']:>+10.2f} "
              f"{r['ir_per_trade']:>+8.3f} {r['sharpe_annualized']:>+10.2f} "
              f"{int(r['yearly_events_est']):>8d} {r['annual_mean_bps_est']:>+10.1f}")

    print(f"\n输出：{LOG_DIR / 'classifier_perf_corrected.csv'}")

    # 关键对比表
    print("\n" + "=" * 100)
    print("关键对比 · gross vs net · 稳定期 · 5 主线")
    print("=" * 100)
    filt = (out_df["period"] == "stable")
    for cost_tag in ["gross", "net_15bps"]:
        sub = out_df[filt & (out_df["cost"] == cost_tag)]
        print(f"\n【{cost_tag}】")
        print(f"{'主线':12s} {'年Sharpe':>10s} {'单笔IR':>8s} {'单笔mean':>10s} {'Hit':>6s}")
        for _, r in sub.iterrows():
            print(f"{r['combo']:12s} {r['sharpe_annualized']:>+10.2f} "
                  f"{r['ir_per_trade']:>+8.3f} {r['trade_mean_bps']:>+10.2f} "
                  f"{r['hit_rate']:>6.1%}")


if __name__ == "__main__":
    main()
