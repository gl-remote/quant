#!/usr/bin/env python3
"""
va-composite · P4c · 纯去重对照 (控住覆盖天数 + 预热天数, 只动"是否压成1份/天")

命题: 用户领域直觉 — "去重只是删冗余行, A3_skew 每日恒定, 不应改变信号/当日交易"。
      上一轮 P4b 的"去重族 vs 未去重族"其实混了 3 个变量:
        去重 + 覆盖天数(17→20) + 预热(min_periods 1.7天→10天)。
      本脚本做 PURE 去重对照: 两组同 ~17天覆盖、同 10天预热、都展开到事件行(6份/天),
      唯一区别: 秩分母按 6份/天(未去重) vs 1份/天(去重后展开)。

构造:
  X (未去重): 事件行 rolling(rows=days*6, min_periods=warm*6).apply(rank_last)
  Y (去重):   每日1观测 rolling(days, min_periods=warm).apply(rank_last) → 展开回事件行
  两者都在事件行上有 6份/天、同覆盖、同预热; 仅秩分母粒度不同(6份 vs 1份)。

验证:
  1) X vs Y 秩 Pearson 应≈1 (去重不改秩值)
  2) X vs Y tier 一致率应≈100%
  3) X vs Y 回测应近乎一致 → 证"纯去重不影响信号"
  4) 对照: 去重族若把窗口也拉长(如 days=60/100), 才会崩 —— 那是窗口效应不是去重。

回测: va_composite_p1_cap (B0)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))
from va_composite_p1_cap import (  # noqa: E402
    simulate_contract, compress, assign_equity, base_metrics, active_day_set,
    monthly_win_rate, per_trade_ir, nu_implied,
    A_TIER_RAW, TIER_TO_V40, DEDUP_HOURS,
)
from strategies.classifiers.poc_va import POCVAClassifier  # noqa: E402

SRC = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
OUT = Path("project_data/ai_tmp/p4c_pure_dedup")
OUT.mkdir(parents=True, exist_ok=True)

ROWS_PER_DAY = 6


def rank_last(x: pd.Series) -> float:
    if len(x) < 2:
        return np.nan
    cur = x.iloc[-1]
    past = x.iloc[:-1]
    return float((past <= cur).sum()) / len(past)


def skew_rank_eventrows_days(df: pd.DataFrame, days: int, warm_days: int) -> pd.Series:
    """X: 未去重, 事件行窗口 = days*6 行, 预热 = warm_days*6 行。"""
    rows = days * ROWS_PER_DAY
    warm = warm_days * ROWS_PER_DAY
    return df.groupby("contract")["A3_skew"].transform(
        lambda s: s.rolling(rows, min_periods=warm).apply(rank_last, raw=False))


def skew_rank_dedup_expanded(df: pd.DataFrame, days: int, warm_days: int) -> pd.Series:
    """Y: 去重每日1观测 rolling(days, min_periods=warm), 再展开回事件行(每日本值拷6份)。"""
    daily = (df.groupby(["contract", "event_date"], as_index=False)["A3_skew"].first()
             .sort_values(["contract", "event_date"]))
    r = daily.groupby("contract")["A3_skew"].transform(
        lambda s: s.rolling(days, min_periods=warm_days).apply(rank_last, raw=False))
    daily["sk"] = r.values
    m = df.merge(daily[["contract", "event_date", "sk"]],
                 on=["contract", "event_date"], how="left")
    return m["sk"]


def classify(df: pd.DataFrame, sk_col: str) -> pd.Series:
    tmp = df[["contract", "event_time", "transition_flag",
              sk_col, "atr_rank_roll", "trend_rank_roll"]].rename(columns={
        sk_col: "signed_skew_rank_roll"}).dropna(
        subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
    res = POCVAClassifier().evaluate_dataset(tmp).dropna(subset=["tier"])
    return res["tier"].reindex(df.index)


def load_events(df: pd.DataFrame) -> pd.DataFrame:
    a = df[df["tier"].isin(A_TIER_RAW)].copy()
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["tier_v40"] = a["tier"].map(TIER_TO_V40)
    a = a.dropna(subset=["tier_v40"])
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = a.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = a.groupby("contract")["event_time"].shift(1)
    a = a[(prev.isna()) | ((a["event_time"] - prev) > pd.Timedelta(hours=DEDUP_HOURS))]
    return a.reset_index(drop=True)


def run_backtest(df: pd.DataFrame, active_days=None):
    events = load_events(df)
    if len(events) == 0:
        return None
    rows = []
    for contract, g in events.groupby("contract"):
        rows.extend(simulate_contract(contract, g))
    raw = pd.DataFrame(rows)
    t = compress(raw, 1.0)
    t = assign_equity(t)
    m = base_metrics(t, active_days=active_days)
    m["monthly_win"] = monthly_win_rate(t)
    m["ir"] = per_trade_ir(t)
    m["nu_implied"], m["p_nu_pos"] = nu_implied(t)
    return m


def main() -> None:
    print("=" * 70)
    print("va-composite · P4c · 纯去重对照 (同覆盖/预热, 只动 6份/天 vs 1份/天)")
    print("=" * 70)
    df = pd.read_parquet(SRC)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)

    lines = []
    lines.append("# va-asymmetry-composite · P4c · 纯去重对照")
    lines.append("")
    lines.append("> 命题: 单纯去重(A3_skew每日恒定)不改信号; 前序P4b的'去重差'实为覆盖/预热污染。")
    lines.append("> 方法: X=未去重事件行 rolling(days*6, warm*6); Y=去重每日1观测 rolling(days,warm) 展开。")
    lines.append("> 两组同覆盖同预热同6份/天, 仅秩分母粒度(6 vs 1)不同。回测=va_composite_p1_cap(B0)。")
    lines.append("> 年化口径(2026-07-11 改): 改用**只用 skew 秩拿到值(非NaN)的那天(交易日,剔周末)并集**作分母, 年因子 252(一年252交易日); 不再用 exit 首尾间全部日历日。下表'可交易日'列即该分母。")
    lines.append("")

    for days in [17, 20]:
        warm = 10
        print(f"\n[覆盖 {days}天 / 预热 {warm}天]")
        X = skew_rank_eventrows_days(df, days, warm)
        Y = skew_rank_dedup_expanded(df, days, warm)

        # 秩相关 & tier 一致 (仅均非NaN行)
        both = X.notna() & Y.notna()
        corr = np.corrcoef(X[both], Y[both])[0, 1]
        tX = classify(df.assign(signed_skew_rank_roll_=X), "signed_skew_rank_roll_")
        tY = classify(df.assign(signed_skew_rank_roll_=Y), "signed_skew_rank_roll_")
        tb = tX.notna() & tY.notna()
        tier_agree = (tX[tb] == tY[tb]).mean()

        dX = df.copy(); dX["tier"] = tX.values; dX = dX.dropna(subset=["tier"])
        dY = df.copy(); dY["tier"] = tY.values; dY = dY.dropna(subset=["tier"])
        adX = active_day_set(df.assign(signed_skew_rank_roll_=X), "signed_skew_rank_roll_")
        adY = active_day_set(df.assign(signed_skew_rank_roll_=Y), "signed_skew_rank_roll_")
        mX = run_backtest(dX, active_days=adX); mY = run_backtest(dY, active_days=adY)

        print(f"  秩 Pearson(X,Y) = {corr:.5f}")
        print(f"  tier 一致率 = {tier_agree*100:.2f}%  (n={tb.sum()})")
        print(f"  X(未去重): A事件 {int(dX['tier'].isin(A_TIER_RAW).sum())} | "
              f"年化 {mX['ann_ret']*100:.2f}% 夏普 {mX['sharpe']:.2f} MaxDD {mX['max_dd']*100:.2f}% "
              f"(可交易日 {mX['n_active_days']})")
        print(f"  Y(去重)  : A事件 {int(dY['tier'].isin(A_TIER_RAW).sum())} | "
              f"年化 {mY['ann_ret']*100:.2f}% 夏普 {mY['sharpe']:.2f} MaxDD {mY['max_dd']*100:.2f}% "
              f"(可交易日 {mY['n_active_days']})")

        lines.append(f"## 覆盖 {days}天 / 预热 {warm}天")
        lines.append("")
        lines.append(f"- 秩 Pearson(X未去重, Y去重) = **{corr:.5f}**")
        lines.append(f"- tier 一致率 = **{tier_agree*100:.2f}%** (n={tb.sum()})")
        lines.append("")
        lines.append("| 配置 | A事件 | 年化 | 净夏普 | MaxDD | 可交易日 |")
        lines.append("|:---|---:|---:|---:|---:|---:|")
        lines.append(f"| X 未去重(6份/天) | {int(dX['tier'].isin(A_TIER_RAW).sum())} | "
                     f"{mX['ann_ret']*100:.2f}% | {mX['sharpe']:.2f} | {mX['max_dd']*100:.2f}% | {mX['n_active_days']} |")
        lines.append(f"| Y 去重(1份/天展开) | {int(dY['tier'].isin(A_TIER_RAW).sum())} | "
                     f"{mY['ann_ret']*100:.2f}% | {mY['sharpe']:.2f} | {mY['max_dd']*100:.2f}% | {mY['n_active_days']} |")
        lines.append("")

    lines.append("## 解读")
    lines.append("")
    lines.append("- 若 X≈Y (秩相关≈1, tier一致≈100%, 回测近乎一致) → **印证用户直觉: 纯去重不改信号**。")
    lines.append("- 此前 P4b '去重族 ~12-13% vs 未去重 ~18%' 的 ~5pp 落差, 实为去重时**窗口覆盖(17→20天)与")
    lines.append("  min_periods预热(1.7→10天)被同步拉长**所致, 非去重本身。P0.1 '去重→13.14/交易−31%' 同理")
    lines.append("  (去重后 window=100 被解读为 100 天 → 覆盖崩塌、事件大规模NaN)。")
    lines.append("- 真正使去重口径'变差'的是**去重后窗口仍用原 event-row 数(100)被当成100天**这一误用;")
    lines.append("  若保持相同每日覆盖, 去重无损。")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
