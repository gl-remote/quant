#!/usr/bin/env python3
"""va-composite · Phase 0 校验：复现并核对 B0（昨天的冻结数据）。

严格复刻 archive/.../va_composite_stage0_baseline.py 的指标口径，确保 B0 锚点一致：
- 日收益 = 当日 pnl_net_ccy 和 / EQUITY_INIT，reindex 到完整日历日（含周末）补 0
- 年化 = mean*252，波动 = std*sqrt(252)，夏普 = 年化/波动，MaxDD = 累计收益回撤
- ν_implied = μ − σ²/2（pnl_gross 转小数），cluster bootstrap（簇=contract×exit_date）算 P(ν>0)
- 不重新计算 rank/归一化（上游 classifier timeline 为旧口径生成，P0.1 另议）
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

REPO = Path("/Users/gaolei/Documents/src/quant")
B0_PARQUET = REPO / "project_data/ai_tmp/va_composite_stage0_baseline.trades.parquet"
EQUITY_INIT = 1_000_000.0


def daily_returns(trades: pd.DataFrame) -> pd.Series:
    t = trades.copy()
    t["day"] = t["exit_bar"].dt.date
    daily_pnl = t.groupby("day")["pnl_net_ccy"].sum()
    return daily_pnl / EQUITY_INIT


def base_metrics(trades: pd.DataFrame) -> dict:
    ret = daily_returns(trades)
    all_dates = pd.date_range(ret.index.min(), ret.index.max(), freq="D")
    ret = ret.reindex(all_dates.date, fill_value=0.0)
    ann = ret.mean() * 252
    std = ret.std() * np.sqrt(252)
    sharpe = ann / std if std > 0 else 0.0
    cum = ret.cumsum()
    dd = (cum - cum.cummax()).min()
    return {"ann_ret": ann, "ann_std": std, "sharpe": sharpe, "max_dd": dd}


def monthly_win_rate(trades: pd.DataFrame) -> float:
    t = trades.copy()
    t["month"] = pd.to_datetime(t["exit_bar"]).dt.to_period("M")
    mret = t.groupby("month")["pnl_net_ccy"].sum()
    return float((mret > 0).mean()) if len(mret) else 0.0


def per_trade_ir(trades: pd.DataFrame) -> float:
    s = trades["pnl_net_bps"].std()
    return float(trades["pnl_net_bps"].mean() / s) if s > 0 else 0.0


def nu_implied(trades: pd.DataFrame) -> tuple[float, float]:
    """§9: ν = μ − σ²/2（收益率小数）。cluster bootstrap 以 (contract, date) 为簇。"""
    g = trades["pnl_gross_bps"].to_numpy() / 10000.0
    mu = g.mean()
    var = g.var()
    nu_frac = mu - var / 2.0

    grp = trades.groupby(["contract", trades["exit_bar"].dt.date])["pnl_gross_bps"]
    sizes = grp.size().to_numpy(dtype=float)
    sums = (grp.sum().to_numpy()) / 10000.0
    sumsq = (grp.apply(lambda x: (x ** 2).sum()).to_numpy()) / 10000.0 ** 2
    N = sizes.sum()
    k = len(sizes)
    rng = np.random.default_rng(42)
    nu = np.empty(500)
    for i in range(500):
        sel = rng.integers(0, k, size=k)
        S = sums[sel].sum()
        SS = sumsq[sel].sum()
        mean = S / N
        var_c = SS / N - mean * mean
        nu[i] = mean - var_c / 2.0
    return float(nu_frac * 10000.0), float((nu > 0).mean())


def main() -> None:
    df = pd.read_parquet(B0_PARQUET)

    print("=" * 72)
    print("P0.2 · B0 策略层复现（原 stage0 口径，对标 freeze-summary v1.0）")
    print("=" * 72)
    m = base_metrics(df)
    m["monthly_win"] = monthly_win_rate(df)
    m["ir"] = per_trade_ir(df)
    m["nu_implied"], m["p_nu_pos"] = nu_implied(df)
    print(f"  trades      = {len(df)}")
    print(f"  年化净收益  = {m['ann_ret']*100:7.2f}%   (freeze: 15.10%)")
    print(f"  净夏普      = {m['sharpe']:7.2f}     (freeze:  2.70)")
    print(f"  MaxDD       = {m['max_dd']*100:7.2f}%   (freeze: -2.40%)")
    print(f"  月度胜率    = {m['monthly_win']*100:7.1f}%   (freeze:  83%)")
    print(f"  单笔 IR     = {m['ir']:7.3f}     (freeze:  0.30)")
    print(f"  ν_implied   = {m['nu_implied']:.3f}   p(ν>0)={m['p_nu_pos']:.3f}")

    long_m = base_metrics(df[df["direction"] == 1]); long_m["n"] = int((df["direction"] == 1).sum())
    short_m = base_metrics(df[df["direction"] == -1]); short_m["n"] = int((df["direction"] == -1).sum())
    print(f"  多头: n={long_m['n']}  年化 {long_m['ann_ret']*100:6.2f}%  Sharpe {long_m['sharpe']:.2f}")
    print(f"  空头: n={short_m['n']}  年化 {short_m['ann_ret']*100:6.2f}%  Sharpe {short_m['sharpe']:.2f}")

    # P0.4 · 6 tier 轻量 edge 归因（旧口径快照，供新口径确认对照）
    print()
    print("=" * 72)
    print("P0.4 · 6 tier 轻量 edge 归因（旧口径快照，新口径确认前的基线）")
    print("=" * 72)
    print(f"{'tier':22s} {'n':>4s} {'mean_bps':>9s} {'sd_bps':>9s} {'IR':>7s} {'ν_impl':>9s} {'P(ν>0)':>8s}")
    for tier in sorted(df["tier"].unique()):
        sub = df[df["tier"] == tier]
        ir = per_trade_ir(sub)
        nu, p = nu_implied(sub)
        print(f"{tier:22s} {len(sub):4d} {sub['pnl_net_bps'].mean():9.2f} {sub['pnl_net_bps'].std():9.2f} "
              f"{ir:7.2f} {nu:9.3f} {p:8.3f}")
    print("  （注：parquet 不含 L_seg2_low_flat → B0 下该 tier 已禁用，P0.4 定论=禁用）")

    # 品种类型 A/B/C 保留率
    print()
    print("=" * 72)
    print("品种类型保留率（正收益交易占比）")
    print("=" * 72)
    for st in ("A", "B", "C"):
        g = df[df["symbol_type"] == st]
        pos = (g["pnl_net_ccy"] > 0).sum()
        print(f"  类型{st}: n={len(g)}  正收益占比={pos/len(g)*100:5.1f}%  pnl_ccy_sum={g['pnl_net_ccy'].sum():,.0f}")


if __name__ == "__main__":
    main()
