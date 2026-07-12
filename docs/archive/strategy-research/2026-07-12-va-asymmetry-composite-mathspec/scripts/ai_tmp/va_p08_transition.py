#!/usr/bin/env python3
"""
va-composite · Phase 8 · transition 候选 T2/T3 替换 T1

位置: scripts/ai_tmp/va_p08_transition.py
主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 B0 管线（复用 va_composite_p1_cap 的模拟/指标层）

目标（experiment-plan § Phase 8 / spec §1.3.4）:
  比较三种 transition 检测（T1/T2/T3）在「transition 拆分 edge」上的优劣：
    - T1（默认 B0）: 生产 transition_flag（session-ATR 桶 crossover，占比 44.6%，当前 B0 实际采用）
    - T2（ATR 原始动量）: m = tanh(k·Δ/W)，|m|>Θ_m 得 flag
    - T3（ATR z-score 突破）: ATR 滚动 z-score 跨 ±Θ_z 得 flag
  判定：仅当某 T 的 transition 拆分 edge 稳定优于 T1 时采用；否则保持 T1（B0）。

口径说明：
  - T1 基线用【生产 transition_flag】（= 当前 B0 实际采用的 whitelist 拆分），而非 spec 严格 T1(W=3, 21.2%)，
    因为 B0 真相建立在生产 flag 上；spec T1 与生产 flag 的 mismatch 已入档 §1.3.4.2。
  - T2/T3 阈值用合理默认 + 少量扫描（验证稳健），主报告取代表档。
  - 「拆分 edge 质量」度量：对每个 T，取 trans 子集（flag=1 的事件）跑无风控 B0，报年化/夏普/MaxDD；
    并算 trans_only 相对 full B0 的配对 ΔSharpe。trans 子集夏普越高、且配对 ΔSh≥0.2，表示该 T 的
    转期标记更干净地分离出 alpha。

运行: uv run python scripts/ai_tmp/va_p08_transition.py
输出: project_data/ai_tmp/p8_transition/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402

OUT_DIR = Path("project_data/ai_tmp/p8_transition")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CAP = 4.0


def run_subset(sub: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for contract, g in sub.groupby("contract"):
        rows.extend(P1.simulate_contract(contract, g))
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t = P1.compress(t, CAP)
    return t


def build_day_flags() -> pd.DataFrame:
    """从 timeline 构建 per-contract 日级 ATR 序列，并算 T2/T3 flag。"""
    tl = pd.read_parquet(P1.TIMELINE_PATH)
    day = (tl.groupby(["contract", "event_date"])
             .agg(atr=("daily_atr_10_bps", "first"))
             .reset_index())
    day["event_date"] = pd.to_datetime(day["event_date"])

    out_rows = []
    for contract, g in day.groupby("contract"):
        g = g.sort_values("event_date").reset_index(drop=True)
        atr = pd.Series(g["atr"].values, dtype=float)
        # T2: m = tanh(k·Δ/W)，Δ = atr 的 W 日归一化差分
        W = 5
        roll = atr.rolling(W).mean()
        diff = atr.diff(W)
        delta = (diff / roll).fillna(0.0).values
        m = np.tanh(1.0 * delta)
        t2 = pd.Series((np.abs(m) > 0.3).astype(int), index=g.index)
        # T3: ATR 滚动 z-score
        N = 20
        mu = atr.rolling(N).mean()
        sd = atr.rolling(N).std()
        z = ((atr - mu) / sd).fillna(0.0).values
        t3 = pd.Series((np.abs(z) > 1.5).astype(int), index=g.index)
        gg = g[["contract", "event_date"]].copy()
        gg["t2_flag"] = t2.values
        gg["t3_flag"] = t3.values
        out_rows.append(gg)
    return pd.concat(out_rows, ignore_index=True)


def scan_trans_pct(day: pd.DataFrame) -> dict:
    """扫描 T2/T3 不同阈值下的 trans 占比，用于稳健性。"""
    tl = pd.read_parquet(P1.TIMELINE_PATH)
    day2 = (tl.groupby(["contract", "event_date"]).agg(atr=("daily_atr_10_bps", "first")).reset_index())
    day2["event_date"] = pd.to_datetime(day2["event_date"])
    res = {}
    for contract, g in day2.groupby("contract"):
        g = g.sort_values("event_date").reset_index(drop=True)
        atr = pd.Series(g["atr"].values, dtype=float)
        W = 5
        roll = atr.rolling(W).mean()
        diff = atr.diff(W)
        delta = (diff / roll).fillna(0.0).values
        m = np.tanh(1.0 * delta)
        N = 20
        mu = atr.rolling(N).mean()
        sd = atr.rolling(N).std()
        z = ((atr - mu) / sd).fillna(0.0).values
        for th in [0.2, 0.3, 0.5]:
            key = f"T2@{th}"
            res.setdefault(key, []).append((np.abs(m) > th).mean())
        for th in [1.0, 1.5, 2.0]:
            key = f"T3@{th}"
            res.setdefault(key, []).append((np.abs(z) > th).mean())
    return {k: float(np.mean(v)) for k, v in res.items()}


def main() -> None:
    print("=" * 70)
    print("va-composite · Phase 8 · transition 候选 T2/T3 vs T1  [基线=冻结 B0 · Cap=4.0]")
    print("=" * 70)

    tl_full = pd.read_parquet(P1.TIMELINE_PATH)
    active_days = P1.active_day_set(tl_full, "signed_skew_rank_roll")
    events = P1.load_events()
    print(f"[load] events={len(events)}  active_days={len(active_days)}")

    # T1 = 生产 transition_flag
    events["t1_flag"] = events["transition_flag"].astype(int)
    # T2/T3 = 日级重建后 merge 回 event
    events["event_date"] = pd.to_datetime(events["event_date"])
    day = build_day_flags()
    events = events.merge(day, on=["contract", "event_date"], how="left")
    events["t2_flag"] = events["t2_flag"].fillna(0).astype(int)
    events["t3_flag"] = events["t3_flag"].fillna(0).astype(int)

    print("[scan] T2/T3 各阈值 trans 占比（均值跨合约）:")
    pct = scan_trans_pct(day)
    for k in sorted(pct):
        print(f"  {k}: {pct[k]*100:.1f}%")
    print(f"  T1(生产flag): {events['t1_flag'].mean()*100:.1f}%")

    # full B0
    full = run_subset(events)
    full_m = P1.base_metrics(full, active_days=active_days)

    def subset_metrics(flag_col: str, tag: str):
        sub_tr = events[events[flag_col] == 1]
        sub_st = events[events[flag_col] == 0]
        tr = run_subset(sub_tr)
        st = run_subset(sub_st)
        tr_m = P1.base_metrics(tr, active_days=active_days) if len(tr) else None
        st_m = P1.base_metrics(st, active_days=active_days) if len(st) else None
        d = P1.paired_delta(full, tr) if len(tr) else None
        print(f"\n[{tag}] trans n={len(tr)} stable n={len(st)}")
        if tr_m:
            print(f"  trans : ann={tr_m['ann_ret']*100:6.2f}%  sharpe={tr_m['sharpe']:.2f}  "
                  f"max_dd={tr_m['max_dd']*100:6.2f}%")
        if st_m:
            print(f"  stable: ann={st_m['ann_ret']*100:6.2f}%  sharpe={st_m['sharpe']:.2f}  "
                  f"max_dd={st_m['max_dd']*100:6.2f}%")
        if d:
            print(f"  trans vs full: ΔSh={d['dsharpe']:+.2f}  μ_true={d['nu_true']:+.2f}bps  "
                  f"P(μ_true>0)={d['p_nu_pos']:.3f}")
        return tr_m, st_m, d

    print("\n[metrics] 主指标（新·可交易日口径=只用 skew 拿到值, Cap=4.0）")
    print(f"  FULL B0: ann={full_m['ann_ret']*100:6.2f}%  sharpe={full_m['sharpe']:.2f}  "
          f"max_dd={full_m['max_dd']*100:6.2f}%  n={len(full)}")

    r_t1 = subset_metrics("t1_flag", "T1(生产flag)")
    r_t2 = subset_metrics("t2_flag", "T2(tanh@0.3)")
    r_t3 = subset_metrics("t3_flag", "T3(z@1.5)")

    # 写 summary
    s = []
    s.append("# Phase 8 · transition 候选 T2/T3 vs T1\n")
    s.append("> 基线 = 冻结 B0（Cap=4.0、风控全关）。T1 基线 = 生产 transition_flag（44.6%，当前 B0 实际采用）。\n")
    s.append("> 口径 = 新·可交易日口径。判定：仅当 T2/T3 的 transition 拆分 edge 稳定优于 T1 时采用。\n")
    s.append("\n## T2/T3 各阈值 trans 占比（均值跨合约）\n")
    s.append("| 方法 | trans 占比 |")
    s.append("|:---|---:|")
    s.append(f"| T1(生产flag) | {events['t1_flag'].mean()*100:.1f}% |")
    for k in sorted(pct):
        s.append(f"| {k} | {pct[k]*100:.1f}% |")
    s.append("\n## 主指标（trans / stable 子集 · Cap=4.0）\n")
    s.append(f"FULL B0: ann={full_m['ann_ret']*100:.2f}%  sharpe={full_m['sharpe']:.2f}  "
             f"max_dd={full_m['max_dd']*100:.2f}%  n={len(full)}\n")
    for tag, r in [("T1", r_t1), ("T2", r_t2), ("T3", r_t3)]:
        tr_m, st_m, d = r
        s.append(f"### {tag}\n")
        if tr_m:
            s.append(f"- trans : ann={tr_m['ann_ret']*100:.2f}%  sharpe={tr_m['sharpe']:.2f}  "
                     f"max_dd={tr_m['max_dd']*100:.2f}%\n")
        if st_m:
            s.append(f"- stable: ann={st_m['ann_ret']*100:.2f}%  sharpe={st_m['sharpe']:.2f}  "
                     f"max_dd={st_m['max_dd']*100:.2f}%\n")
        if d:
            s.append(f"- trans vs full: ΔSh={d['dsharpe']:+.2f}  μ_true={d['nu_true']:+.2f}bps  "
                     f"P(μ_true>0)={d['p_nu_pos']:.3f}\n")
    s.append("\n## 结论\n")
    s.append("- 比较三者 trans 子集 edge 质量（夏普 / trans vs full 配对 ΔSh）；无稳定优于 T1 者则保持 T1(B0)。\n")
    (OUT_DIR / "summary.md").write_text("\n".join(s))
    print("\n[done] 见", OUT_DIR / "summary.md")


if __name__ == "__main__":
    main()
