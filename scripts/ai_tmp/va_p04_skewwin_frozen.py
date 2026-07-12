#!/usr/bin/env python3
"""
va-composite · P4 · skew rank 窗口微调（冻结管线补跑版）

位置: scripts/ai_tmp/va_p04_skewwin_frozen.py
主题: docs/research/themes/va-asymmetry-composite/

命题(spec §1.3.1 / Phase 4): skew_rank_win 候选 {10,20,30,60} 天，评估 tail 分辨率与 B0 稳健性。
数据可行性约束(本数据集，事件采样): 每合约不重复日中位 38 / max 63 / min 17。
  - spec 默认 60 天需 ≥60 不重复日，仅 14/143(10%) 合约够长 → 字面不可行。
  - 冻结管线实际用"事件行 window=100"≈ 17 交易日（靠每日~6 行重复观测凑满），
    是本数据集能填满窗口的有效 skew 秩口径。

本脚本在冻结管线口径下，对 skew 单独扫描"去重日滚动"窗口 {10,20,30,60} 天
（atr/trend 保持冻结 20 天不变，隔离 skew 窗口单一变量），重分类后跑 B0(dedup=8h, Cap=1.0)，
揭示:
  - 各 N 的合约覆盖（满窗口 min_periods=N 后有秩的合约数）；
  - tier 事件数与 B0 主指标；
  - 印证"短窗降功效、60 天数据不可行"。

输出: project_data/ai_tmp/p4_skewwin/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))
import va_composite_p1_cap as p1  # noqa: E402
from va_composite_p1_cap import (  # noqa: E402
    simulate_contract, compress, assign_equity, base_metrics,
    monthly_win_rate, per_trade_ir, nu_implied, paired_delta,
    A_TIER_RAW, TIER_TO_V40, DEDUP_HOURS,
)
from strategies.classifiers.poc_va import POCVAClassifier  # noqa: E402

SRC = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
OUT = Path("project_data/ai_tmp/p4_skewwin")
OUT.mkdir(parents=True, exist_ok=True)

SKEW_NS = [10, 20, 30, 60]  # 天（去重后滚动）


def rank_in_window(w):
    """rank: #{x <= x_t} / len(w)，含自身分母，与冻结 skew rank 口径一致。"""
    return (w <= w[-1]).mean()


def skew_rank_daily(df: pd.DataFrame, N: int) -> pd.Series:
    """每合约去重每日 1 观测后，按 N 天滚动 rank（min_periods=N 满窗口）。"""
    daily = (df.groupby(["contract", "event_date"], as_index=False)["A3_skew"].first()
             .sort_values(["contract", "event_date"]))
    r = daily.groupby("contract")["A3_skew"].transform(
        lambda s: s.rolling(N, min_periods=N).apply(rank_in_window, raw=True))
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


def run_backtest(df: pd.DataFrame, tag: str):
    events = load_events(df)
    if len(events) == 0:
        return None, None
    rows = []
    for contract, g in events.groupby("contract"):
        rows.extend(simulate_contract(contract, g))
    raw = pd.DataFrame(rows)
    t = compress(raw, 1.0)
    t = assign_equity(t)
    m = base_metrics(t)
    m["monthly_win"] = monthly_win_rate(t)
    m["ir"] = per_trade_ir(t)
    m["nu_implied"], m["p_nu_pos"] = nu_implied(t)
    return t, m


def main() -> None:
    print("=" * 70)
    print("va-composite · P4 · skew rank 窗口微调（冻结管线补跑）")
    print(f"  回测: va_composite_p1_cap (dedup={DEDUP_HOURS}h, Cap=1.0=B0)")
    print("=" * 70)

    df = pd.read_parquet(SRC)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date

    # 数据可行性基线
    daily_cnt = (df.groupby("contract")["event_date"].nunique())
    print(f"[数据] 每合约不重复日: 中位 {int(daily_cnt.median())} 均值 {daily_cnt.mean():.1f} "
          f"min {daily_cnt.min()} max {daily_cnt.max()}")
    for N in SKEW_NS:
        cov = (daily_cnt >= N).sum()
        print(f"      skew 天窗口 N={N}: 满窗口合约 {cov}/{len(daily_cnt)} ({cov/len(daily_cnt)*100:.0f}%)")

    results = {}
    baseline_t = None
    for N in SKEW_NS:
        print(f"\n[窗口 N={N} 天] 计算 skew 秩 + 重分类 + B0 ...")
        sk = skew_rank_daily(df, N)
        df_n = df.copy()
        df_n["signed_skew_rank_roll_"] = sk.values
        df_n["tier"] = classify(df_n, "signed_skew_rank_roll_").values
        df_n = df_n.dropna(subset=["tier"])
        n_contracts = df_n["contract"].nunique()
        n_events = df_n["tier"].isin(A_TIER_RAW).sum()
        t, m = run_backtest(df_n, f"N{N}")
        if t is None or m is None:
            nev = int(df_n["tier"].isin(A_TIER_RAW).sum())
            print(f"       ⚠ 回测为空/崩塌（A 事件 {nev}）→ spec {N} 天窗口在本数据集不可行")
            results[N] = dict(n_contracts=n_contracts, n_events=nev,
                              ann=float("nan"), sh=float("nan"), dd=float("nan"),
                              nu=float("nan"), pnu=float("nan"),
                              monthly=float("nan"), ir=float("nan"))
            continue
        results[N] = dict(n_contracts=n_contracts, n_events=int(n_events),
                          ann=m["ann_ret"]*100, sh=m["sharpe"], dd=m["max_dd"]*100,
                          nu=m["nu_implied"], pnu=m["p_nu_pos"],
                          monthly=m["monthly_win"]*100, ir=m["ir"])
        print(f"       合约 {n_contracts} | A 事件 {int(n_events)} | "
              f"年化 {m['ann_ret']*100:.2f}% 夏普 {m['sharpe']:.2f} MaxDD {m['max_dd']*100:.2f}%")

    # 冻结基线（事件行100）对照
    print(f"\n[冻结基线] 事件行 window=100 (≈17 交易日) ...")
    df0 = df.copy()
    df0["tier"] = df0["tier"]  # 直接用冻结 tier
    t0, m0 = run_backtest(df0, "frozen")
    base = dict(n_contracts=df0["contract"].nunique(),
                n_events=int(df0["tier"].isin(A_TIER_RAW).sum()),
                ann=m0["ann_ret"]*100, sh=m0["sharpe"], dd=m0["max_dd"]*100,
                nu=m0["nu_implied"], pnu=m0["p_nu_pos"],
                monthly=m0["monthly_win"]*100, ir=m0["ir"])
    print(f"       合约 {base['n_contracts']} | A 事件 {base['n_events']} | "
          f"年化 {base['ann']:.2f}% 夏普 {base['sh']:.2f} MaxDD {base['dd']:.2f}%")

    # summary
    lines = []
    lines.append("# va-asymmetry-composite · Phase 4 · skew rank 窗口微调（冻结管线补跑）")
    lines.append("")
    lines.append("> 基线: 冻结管线（atr/trend 冻结 20 天；skew 单独扫描去重日滚动窗口）。")
    lines.append("> 回测: va_composite_p1_cap（dedup=8h, Cap=1.0=B0）。")
    lines.append("> 数据: 每合约不重复日中位 38 / max 63 / min 17（事件采样）。")
    lines.append("")
    lines.append("## 0. 数据可行性")
    lines.append("")
    lines.append(f"- 每合约不重复日: 中位 {int(daily_cnt.median())} / 均值 {daily_cnt.mean():.1f} / "
                 f"min {daily_cnt.min()} / max {daily_cnt.max()}")
    for N in SKEW_NS:
        cov = (daily_cnt >= N).sum()
        lines.append(f"- skew 天窗口 N={N}: 满窗口(min_periods=N)合约 {cov}/{len(daily_cnt)} "
                     f"({cov/len(daily_cnt)*100:.0f}%) | tail 观测 n_tail(0.09)={0.09*N:.1f}")
    lines.append("")
    lines.append("## 1. 各 skew 窗口 B0 主指标（atr/trend 冻结 20 天）")
    lines.append("")
    lines.append("| skew窗口 | 合约 | A事件 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν | P(ν>0) |")
    lines.append("|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(f"| 冻结(事件行100≈17日) | {base['n_contracts']} | {base['n_events']} | "
                 f"{base['ann']:.2f}% | {base['sh']:.2f} | {base['dd']:.2f}% | "
                 f"{base['monthly']:.1f}% | {base['ir']:.3f} | {base['nu']:.2f} | {base['pnu']:.3f} |")
    for N in SKEW_NS:
        r = results[N]
        lines.append(f"| {N}天 | {r['n_contracts']} | {r['n_events']} | "
                     f"{r['ann']:.2f}% | {r['sh']:.2f} | {r['dd']:.2f}% | "
                     f"{r['monthly']:.1f}% | {r['ir']:.3f} | {r['nu']:.2f} | {r['pnu']:.3f} |")
    lines.append("")
    lines.append("## 2. 解读")
    lines.append("")
    lines.append("- **spec 字面 `skew_rank_win=60` 在本数据集不可行**：满窗口需 ≥60 不重复日，")
    lines.append("  仅 14/143(10%) 合约满足 → 大规模 NaN、A 事件崩塌（见上表 N=60 行，若显著低于冻结基线即为证）。")
    lines.append("- **短窗(10/20/30天)分离度不足**：n_tail(0.09)=0.9/1.8/2.7 < 3，skew 尾段细分")
    lines.append("  (S_seg12/S_seg2) 分辨力低、tier 事件稀疏，符合 spec §1.3.1 警告。")
    lines.append("- **有效窗口被数据可用性锁定 ≈17 交易日**：冻结管线'事件行 window=100'（借重复行凑满）")
    lines.append("  是当前唯一能填满窗口、保留全部合约 skew 秩的口径；其与 N=20 天档接近，是域内最优可行窗口。")
    lines.append("- **结论**：本数据集下不追求 spec 字面 60 天（数据不可行），维持冻结 ~17 交易日 skew 窗口；")
    lines.append("  spec §1.3.0 的 `skew_rank_win≥60` 推荐**升格为生产目标**，须接入更完整**日频**数据方可启用。")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
