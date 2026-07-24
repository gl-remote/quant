"""
文件级元信息：
- 创建背景：c4 显示 L_seg2 (+L_seg3) 是"制度依赖 alpha"——在数据末段(2025-11
  之后)持续通过 test，跨阈值 8 组同向、rank_win 240/360 一致。本脚本把
  "研究口径 signed pnl" 转成"逐笔 trade 序列 → 年化/夏普/回撤/月度胜率"
  等实用指标，让用户能判断规模是否够用。
- 用途：三种参数集 (L_seg2 单信号 / L_seg2+L_seg3 组合 / L_seg2+L_seg3+atr_looser)
  在全期与末段的实用性能对比；用 realistic cost + 逐笔风险归一化。
- 注意事项：临时研究脚本，产物在
  docs/workbench/va-asymmetry-revisit/outputs/c5/。这不是完整 vnpy 回测，
  是"每笔用 8h 收益 - 成本"的净收益序列；用于快速估算，正式回测须
  写策略代码用 workspace/backtest engine。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c5"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

EVENTS_PATH = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c1/c1_events_with_tier.csv"
)

# 假设风险预算：每笔目标风险 = 权益 × RISK_PER_TRADE / (SL_stop = 1 ATR-bps 单位)
# 简化：每笔 pnl_bps 直接乘 sizing 因子（假设固定杠杆 · 与 archive B0 一致）
# 这里我们只报告"逐笔净收益率（log return 单位）"和"每天累积收益"的年化指标


def performance(pnl_series: pd.Series, dt_series: pd.Series, label: str) -> dict:
    """基于逐笔 net log return 序列 + trade 日期 → 日收益序列 → 年化/夏普/DD."""
    df = pd.DataFrame({"pnl": pnl_series.to_numpy(), "date": pd.to_datetime(dt_series).dt.date})
    daily = df.groupby("date")["pnl"].sum().rename("daily_pnl")
    if daily.empty:
        return {"label": label}
    daily.index = pd.to_datetime(daily.index)
    full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(full_idx, fill_value=0.0)
    n_days = len(daily)
    ann_ret = daily.mean() * 252
    ann_vol = daily.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else float("nan")
    cum = daily.cumsum()
    peak = cum.cummax()
    dd = (cum - peak).min()
    hit = (df["pnl"] > 0).mean()
    return {
        "label": label,
        "n_trades": int(len(df)),
        "trade_days": n_days,
        "hit_rate": float(hit),
        "mean_bps_per_trade": float(df["pnl"].mean() * 1e4),
        "annualized_return_%": float(ann_ret * 100),
        "annualized_vol_%": float(ann_vol * 100),
        "sharpe": float(sharpe),
        "max_dd_%": float(dd * 100),
    }


def main() -> None:
    df = pd.read_csv(EVENTS_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date

    # 定义：holding=10h, direction 由 tier 决定
    DIR = {
        "L_seg3_lowmid_up": +1, "L_seg12_high_up": +1, "L_seg2_low_flat": +1,
        "S_seg12_high_dn": -1, "S_seg34_high_dn": -1, "S_seg2_mid_dn": -1,
    }
    HORIZON = "ret_10h"

    # 每笔 net pnl
    df["direction"] = df["tier"].map(DIR).fillna(0)
    df["signed_ret"] = df["direction"] * df[HORIZON]
    df["pnl_net"] = df["signed_ret"] - df["cost_rt"]

    print("Data span:", df["event_time"].min(), "→", df["event_time"].max())
    print("Total events:", len(df))

    def run(subset: pd.DataFrame, label: str) -> dict:
        m = performance(subset["pnl_net"].dropna(), subset["event_time"], label)
        print(f"  [{label}] n={m.get('n_trades')}, days={m.get('trade_days')}, "
              f"ann={m.get('annualized_return_%'):.2f}%, sharpe={m.get('sharpe'):.2f}, "
              f"DD={m.get('max_dd_%'):.2f}%, hit={m.get('hit_rate'):.1%}, "
              f"mean_bps={m.get('mean_bps_per_trade'):.1f}")
        return m

    print("\n=== 候选 A · L_seg2 单信号 · 10h ===")
    a_all = df[(df["tier"] == "L_seg2_low_flat") & df["pnl_net"].notna()]
    all_metrics = []
    all_metrics.append(run(a_all, "A_full"))
    cut = pd.Timestamp("2025-11-01")
    a_late = a_all[a_all["event_time"] >= cut]
    a_early = a_all[a_all["event_time"] < cut]
    all_metrics.append(run(a_late, "A_late(2025-11+)"))
    all_metrics.append(run(a_early, "A_early(<2025-11)"))

    print("\n=== 候选 B · L_seg2 + L_seg3 池 · 10h ===")
    b_all = df[df["tier"].isin(["L_seg2_low_flat", "L_seg3_lowmid_up"]) & df["pnl_net"].notna()]
    all_metrics.append(run(b_all, "B_full"))
    all_metrics.append(run(b_all[b_all["event_time"] >= cut], "B_late"))
    all_metrics.append(run(b_all[b_all["event_time"] < cut], "B_early"))

    print("\n=== 候选 C · 全 6 tier · 10h ===")
    c_all = df[(df["tier"] != "none") & df["pnl_net"].notna()]
    all_metrics.append(run(c_all, "C_full_all_tiers"))
    all_metrics.append(run(c_all[c_all["event_time"] >= cut], "C_late"))

    print("\n=== 候选 D · L_seg2 + L_seg3, hour ∈ {9,10,11,14} filter · 10h ===")
    d_all = b_all[b_all["event_time"].dt.hour.isin([9, 10, 11, 14])]
    all_metrics.append(run(d_all, "D_full"))
    all_metrics.append(run(d_all[d_all["event_time"] >= cut], "D_late"))

    pd.DataFrame(all_metrics).to_csv(OUT_DIR / "c5_performance_summary.csv", index=False)

    # 月度累积净收益曲线 · 输出
    print("\n=== [E] 候选 B 月度净收益（每月对数收益）===")
    b_all = b_all.copy()
    b_all["month"] = b_all["event_time"].dt.to_period("M").astype(str)
    monthly = b_all.groupby("month")["pnl_net"].sum()
    print(monthly.to_string())
    monthly.to_csv(OUT_DIR / "c5_B_monthly.csv")

    print(f"\nAll outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
