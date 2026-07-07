"""
文件级元信息：
- 创建背景：主线信号 profile 用的是"前一天"5m 数据。前一天数据在当天开盘时
  是"最新鲜"的，随时间衰减。检验：DN 事件的 mean/hit 是否随 event_time 的
  小时段变化。若越早买越好 → 信号有衰减 → 实盘只能开盘前后触发；若全天
  一致 → 底厚是持续状态 → 全天挂单也行。
- 用途：读 multilayer_no_lookahead_events.csv（10 合约主表严格无未来版）
  + daily_atr_events.csv（19 合约扩展表）
  按 event_time.hour 分组，输出：
    (1) 每小时的 DN 事件数
    (2) 每小时的 mean ret_8h / hit / std
    (3) 三档主线信号在不同小时的表现
    (4) 若有明显衰减，用线性回归量化"每小时衰减多少 bps"
- 注意事项：中国期货交易时段: 日盘 9:00-11:30 + 13:30-15:00 · 夜盘视品种 21:00-次日 02:30
  Event 触发在 5m bar close 时刻 · 每小时整点作为事件锚
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
STAGE2_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage2"
)
OUT_DIR = STAGE2_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)


def analyze_by_hour(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """按 event_time 的小时分组。"""
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_hour"] = df["event_time"].dt.hour
    df["ret_bps"] = df["ret_8h"] * 1e4

    # 按小时聚合
    rows = []
    for h in sorted(df["event_hour"].unique()):
        sub = df[df["event_hour"] == h]
        if len(sub) < 5:
            continue
        rows.append({
            "event_hour": h,
            "n": len(sub),
            "mean_bps": sub["ret_bps"].mean(),
            "median_bps": sub["ret_bps"].median(),
            "std_bps": sub["ret_bps"].std(),
            "hit": (sub["ret_bps"] > 0).mean(),
        })
    result = pd.DataFrame(rows)

    print(f"\n{'='*90}")
    print(f"{label}")
    print(f"{'='*90}")
    print(f"{'hour':>4s} {'n':>5s} {'mean_bps':>10s} {'median':>8s} {'std':>8s} {'hit':>7s}")
    for _, r in result.iterrows():
        marker = ""
        if r["mean_bps"] > 30: marker = " ⭐"
        elif r["mean_bps"] < 0: marker = " ❌"
        print(f"{int(r['event_hour']):>4d} {int(r['n']):>5d} "
              f"{r['mean_bps']:>+10.2f} {r['median_bps']:>+8.2f} "
              f"{r['std_bps']:>8.2f} {r['hit']:>7.1%}{marker}")

    # 线性回归：mean_bps ~ event_hour
    if len(result) >= 3:
        # 按小时线性趋势
        slope, intercept, r_val, p_val, se = stats.linregress(
            result["event_hour"], result["mean_bps"])
        print(f"\n线性趋势: mean_bps = {slope:+.2f} × hour + {intercept:+.2f}")
        print(f"  R² = {r_val**2:.3f}  p_slope = {p_val:.4f}")
        if p_val < 0.05:
            direction = "衰减" if slope < 0 else "增强"
            print(f"  ✅ 显著{direction}趋势: 每小时 {slope:+.2f} bps")
        else:
            print(f"  · 无显著时段趋势（全天一致）")

    return result


def analyze_by_period(df: pd.DataFrame, label: str) -> None:
    """按更粗的时段：早盘 / 午后 / 夜盘。"""
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["hour"] = df["event_time"].dt.hour
    df["ret_bps"] = df["ret_8h"] * 1e4

    def period_of(h: int) -> str:
        if 9 <= h < 11 or h == 10:
            return "早盘 (09-11)"
        if 13 <= h < 15:
            return "午后 (13-15)"
        if 21 <= h <= 23 or h < 3:
            return "夜盘 (21-次日 03)"
        return "其他"

    df["period"] = df["hour"].apply(period_of)

    print(f"\n{'='*90}")
    print(f"{label} · 粗时段划分")
    print(f"{'='*90}")
    print(f"{'时段':22s} {'n':>5s} {'mean_bps':>10s} {'hit':>7s} {'std':>8s}")
    for p in ["早盘 (09-11)", "午后 (13-15)", "夜盘 (21-次日 03)", "其他"]:
        sub = df[df["period"] == p]
        if len(sub) < 5:
            continue
        r = sub["ret_bps"]
        marker = ""
        if r.mean() > 30: marker = " ⭐"
        elif r.mean() < 0: marker = " ❌"
        print(f"{p:22s} {len(sub):>5d} {r.mean():>+10.2f} "
              f"{(r>0).mean():>7.1%} {r.std():>8.2f}{marker}")


def main() -> None:
    # ============ 数据源 1: 阶段 1 严格无未来函数版 · 10 合约主表 ============
    print("\n\n" + "#" * 90)
    print("# 数据源 1: 阶段 1 严格无未来函数 · 10 合约 (multilayer_no_lookahead_events.csv)")
    print("#" * 90)

    df1 = pd.read_csv(LOG_DIR / "multilayer_no_lookahead_events.csv")
    df1["event_time"] = pd.to_datetime(df1["event_time"])
    print(f"总事件数: {len(df1)}")

    # DN 单层
    dn1 = df1[df1["skew_grp"] == "DN"]
    analyze_by_hour(dn1, "DN 单层 · 按小时分组")
    analyze_by_period(dn1, "DN 单层")

    # DN + 低 ATR
    dn_atr = df1[(df1["skew_grp"] == "DN") & (df1["atr10_grp"] == "low")]
    analyze_by_hour(dn_atr, "DN + 低 ATR_10 · 按小时分组")

    # DN + 涨 + 低 ATR（主线）
    main_signal = df1[(df1["skew_grp"] == "DN") &
                      (df1["trend_grp"] == "up") &
                      (df1["atr10_grp"] == "low")]
    analyze_by_hour(main_signal, "DN + 涨 + 低 ATR (主线) · 按小时分组")

    # ============ 数据源 2: 样本外扩展 44 合约 ============
    print("\n\n" + "#" * 90)
    print("# 数据源 2: 样本外扩展 · 44 合约 (oos_events.csv)")
    print("#" * 90)

    oos_path = STAGE2_DIR / "oos_events.csv"
    if oos_path.exists():
        df2 = pd.read_csv(oos_path)
        df2["event_time"] = pd.to_datetime(df2["event_time"])
        print(f"总事件数: {len(df2)}")

        dn2 = df2[df2["skew_grp"] == "DN"]
        analyze_by_hour(dn2, "样本外 · DN 单层 · 按小时分组")
        analyze_by_period(dn2, "样本外 · DN 单层")

        main2 = df2[(df2["skew_grp"] == "DN") &
                    (df2["trend_grp"] == "up") &
                    (df2["atr10_grp"] == "low")]
        analyze_by_hour(main2, "样本外 · DN + 涨 + 低 ATR (主线) · 按小时分组")


if __name__ == "__main__":
    main()
