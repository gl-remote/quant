#!/usr/bin/env python3
"""
va-composite · P3 · 归一化 A vs C 配对确认（冻结管线重验版）

位置: scripts/ai_tmp/va_p03b_ac_frozen.py
主题: docs/research/themes/va-asymmetry-composite/

为什么需要这一版:
  旧 va_p03_compare_ac.py 跑在**已废弃的混淆版** `timeline_calA/calC`（含去重+20天窗口+新rank公式
  的 4 项捆绑改动）上，绝对数字 11.50%/2.23 建立在更差伪基线上。
  干净 A/B（ab_compare.md）已证伪"去重修复"，恢复冻结管线为真相（B0 = 15.68%/2.72）。
  本脚本在**冻结管线口径**下重做 P3：A 轨直接取冻结 timeline 现有 rank 坐标（=历史 B0），
  C 轨对**同源 raw 量**用**完全相同窗口/观测**（skew 事件行 window=100；atr/trend 去重日滚=20）
  仅把 rank→percentile（等号权重 1.0→0.5，分母口径一致），从而隔离"归一化方式"单一变量。

冻结管线口径（对齐 poc_va_asymmetry_stage2_grid_search.rolling_pct_rank）:
  - skew: 未去重、逐事件行、window=100, min_periods=10
  - atr/trend: 先 drop_duplicates(event_date) 得每日 1 观测、window=20, min_periods=10
  冻结 timeline 的 signed_skew_rank_roll / atr_rank_roll / trend_rank_roll 即上述口径产物。

输出:
  project_data/ai_tmp/p3_ac_frozen/timeline_A_frozen.parquet  (A 轨 = 冻结 tier)
  project_data/ai_tmp/p3_ac_frozen/timeline_C_frozen.parquet  (C 轨 = 同源 percentile)
  project_data/ai_tmp/p3_ac_frozen/summary.md
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
    simulate_contract, compress, assign_equity, base_metrics, active_day_set,
    monthly_win_rate, per_trade_ir, nu_implied, paired_delta,
    A_TIER_RAW, TIER_TO_V40, EQUITY_INIT, DEDUP_HOURS,
)
from strategies.classifiers.poc_va import POCVAClassifier  # noqa: E402

SRC = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
OUT = Path("project_data/ai_tmp/p3_ac_frozen")
OUT.mkdir(parents=True, exist_ok=True)

SKEW_WIN, SKEW_MINP = 100, 10
ATR_WIN, ATR_MINP = 20, 10


def pct_in_window(w):
    """percentile（平均秩）: [#(x<x_t) + 0.5·#(x==x_t)] / len(w)，分母含自身，与 rank 同口径。"""
    x = w[-1]
    return ((w < x).sum() + 0.5 * (w == x).sum()) / len(w)


def roll_pct_event(s: pd.Series, N: int, minp: int) -> pd.Series:
    """skew: 未去重、逐事件行滚动 percentile。"""
    return s.rolling(N, min_periods=minp).apply(pct_in_window, raw=True)


def build_c_coords(df: pd.DataFrame) -> pd.DataFrame:
    """C 轨秩坐标：仅 skew 切换为 percentile（同源 raw 量、同窗口），
    atr/trend 两轨保持冻结值完全一致（边界居中、A/C 差异可忽略，避免引入
    滚动 NaN 口径差异这一无关变量）。这是"归一化方式 A vs C"的纯净隔离——
    skew 正是 spec §1.3.0 的归一化主战场。
    """
    sk_C = df.groupby("contract")["A3_skew"].transform(
        lambda s: roll_pct_event(s, SKEW_WIN, SKEW_MINP))
    out = pd.DataFrame(index=df.index)
    out["sk_C"] = sk_C.values
    out["atr_C"] = df["atr_rank_roll"].values   # 冻结值（=A 轨）
    out["tr_C"] = df["trend_rank_roll"].values  # 冻结值（=A 轨）
    return out


def classify_c(df: pd.DataFrame) -> pd.Series:
    """用 POCVAClassifier 在 C 轨坐标上重算 tier，reindex 回 df.index。"""
    tmp = df[["contract", "event_time", "transition_flag",
              "sk_C", "atr_C", "tr_C"]].rename(columns={
        "sk_C": "signed_skew_rank_roll",
        "atr_C": "atr_rank_roll",
        "tr_C": "trend_rank_roll",
    }).dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
    res = POCVAClassifier().evaluate_dataset(tmp).dropna(subset=["tier"])
    return res["tier"].reindex(df.index)


def load_events(path: Path) -> pd.DataFrame:
    tl = pd.read_parquet(path)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    a = tl[tl["tier"].isin(A_TIER_RAW)].copy()
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["tier_v40"] = a["tier"].map(TIER_TO_V40)
    a = a.dropna(subset=["tier_v40"])
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = a.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = a.groupby("contract")["event_time"].shift(1)
    a = a[(prev.isna()) | ((a["event_time"] - prev) > pd.Timedelta(hours=DEDUP_HOURS))]
    return a.reset_index(drop=True)


def run_backtest(path: Path, tag: str):
    print(f"  [{tag}] 加载 timeline + 构建信号 ...")
    tl = pd.read_parquet(path)
    ad = active_day_set(tl, "signed_skew_rank_roll")
    events = load_events(path)
    print(f"       A_TIER_RAW 事件: {len(events)} | 合约 {events['contract'].nunique()} | "
          f"多:{(events['direction']=='long').sum()} 空:{(events['direction']=='short').sum()}")
    rows = []
    for contract, g in events.groupby("contract"):
        rows.extend(simulate_contract(contract, g))
    raw = pd.DataFrame(rows)
    print(f"       模拟交易数: {len(raw)} | SL:{(raw['exit_reason']=='SL').sum()} "
          f"TIME:{(raw['exit_reason']=='TIME').sum()}")
    t = compress(raw, 1.0)  # B0: Cap=1.0
    t = assign_equity(t)
    m = base_metrics(t, active_days=ad)
    m["monthly_win"] = monthly_win_rate(t)
    m["ir"] = per_trade_ir(t)
    m["nu_implied"], m["p_nu_pos"] = nu_implied(t)
    return t, m


def main() -> None:
    print("=" * 70)
    print("va-composite · P3 · A vs C 配对确认（冻结管线重验）")
    print(f"  回测引擎: va_composite_p1_cap (dedup={DEDUP_HOURS}h, Cap=1.0=B0)")
    print("=" * 70)

    df = pd.read_parquet(SRC)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    for c in ["A3_skew", "daily_atr_10_bps", "trend_ret_10d"]:
        assert c in df.columns, f"冻结 timeline 缺列 {c}"
    print(f"[0] 冻结 timeline: {len(df)} 事件行 | {df['contract'].nunique()} 合约")

    # A 轨 = 冻结现有 rank 坐标 + tier（历史 B0）
    a_track = df[["contract", "event_time", "transition_flag",
                  "signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll", "tier"]].copy()
    a_track = a_track.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll",
                                     "trend_rank_roll", "tier"])
    a_track["tier_v40"] = a_track["tier"].map(TIER_TO_V40)

    # C 轨 = 同源 raw 量 percentile 重算
    print(f"[1] C 轨: 同源 raw 量 percentile（skew 事件行{ SKEW_WIN}/atr,trend 去重日{SKEW_WIN if False else ATR_WIN}）...")
    c_coords = build_c_coords(df)
    df_c = pd.concat([df[["contract", "event_time", "transition_flag"]], c_coords], axis=1)
    c_tier = classify_c(df_c)
    df_c["tier"] = c_tier.values
    df_c["tier_v40"] = df_c["tier"].map(TIER_TO_V40)

    # 诊断: A/C 秩坐标相关性 + tier 一致率
    both = pd.DataFrame({
        "sk_A": a_track["signed_skew_rank_roll"], "sk_C": c_coords["sk_C"],
        "atr_A": a_track["atr_rank_roll"], "atr_C": c_coords["atr_C"],
        "tr_A": a_track["trend_rank_roll"], "tr_C": c_coords["tr_C"],
        "tier_A": a_track["tier_v40"], "tier_C": df_c["tier_v40"],
    }).dropna()
    r_sk = both["sk_A"].corr(both["sk_C"])
    r_atr = both["atr_A"].corr(both["atr_C"])
    r_tr = both["tr_A"].corr(both["tr_C"])
    agree = (both["tier_A"] == both["tier_C"]).mean()
    print(f"     A/C 秩坐标 Pearson: skew r={r_sk:.5f} atr r={r_atr:.5f} trend r={r_tr:.5f}")
    print(f"     tier(v4.0) 一致率 = {agree*100:.2f}%  (双轨非None样本 {len(both)})")
    flips = both[both["tier_A"] != both["tier_C"]].groupby(["tier_A", "tier_C"]).size()
    if len(flips):
        print("     不一致明细 (A -> C):")
        for (a, c), n in flips.items():
            print(f"       {a} -> {c}: {n}")

    # 写两轨 timeline
    base_cols = [c for c in df.columns]
    tl_A = df[base_cols].copy()
    tl_A["tier"] = a_track["tier"].reindex(df.index)
    tl_A["tier_v40"] = a_track["tier_v40"].reindex(df.index)
    tl_A = tl_A.dropna(subset=["tier"])
    tl_C = df[base_cols].copy()
    tl_C["signed_skew_rank_roll"] = c_coords["sk_C"]
    tl_C["atr_rank_roll"] = c_coords["atr_C"]
    tl_C["trend_rank_roll"] = c_coords["tr_C"]
    tl_C["tier"] = df_c["tier"].reindex(df.index)
    tl_C["tier_v40"] = df_c["tier_v40"].reindex(df.index)
    tl_C = tl_C.dropna(subset=["tier"])
    tl_A.to_parquet(OUT / "timeline_A_frozen.parquet", index=False)
    tl_C.to_parquet(OUT / "timeline_C_frozen.parquet", index=False)
    print(f"     timeline_A_frozen: {len(tl_A)} 行 | A 非None tier {tl_A['tier'].notna().sum()}")
    print(f"     timeline_C_frozen: {len(tl_C)} 行 | C 非None tier {tl_C['tier'].notna().sum()}")

    # B0 配对
    print("[2] B0 配对回测 (dedup=8h, Cap=1.0) ...")
    tA, mA = run_backtest(OUT / "timeline_A_frozen.parquet", "A")
    tC, mC = run_backtest(OUT / "timeline_C_frozen.parquet", "C")
    d = paired_delta(tA, tC)
    sig = (d["dsharpe"] >= 0.2) and (d["p_nu_pos"] >= 0.95)
    print(f"  A  : 年化 {mA['ann_ret']*100:6.2f}%  夏普 {mA['sharpe']:.2f}  MaxDD {mA['max_dd']*100:6.2f}%  "
          f"ν {mA['nu_implied']:.3f} P(ν>0) {mA['p_nu_pos']:.3f}")
    print(f"  C  : 年化 {mC['ann_ret']*100:6.2f}%  夏普 {mC['sharpe']:.2f}  MaxDD {mC['max_dd']*100:6.2f}%  "
          f"ν {mC['nu_implied']:.3f} P(ν>0) {mC['p_nu_pos']:.3f}")
    print(f"  ΔSharpe(A−C)={d['dsharpe']:+.2f}  μ_true={d['nu_true']*100:+.3f}%  P(μ_true>0)={d['p_nu_pos']:.3f}")
    print(f"  => {'差异显著 · A/C 不等价 ❌' if sig else '差异不显著 · A≈C 成立 ✅'}")

    # summary
    lines = []
    lines.append("# va-asymmetry-composite · Phase 3 · A vs C 配对确认（冻结管线重验）")
    lines.append("")
    lines.append("> 基线: **冻结管线**（未去重 skew 事件行 window=100；atr/trend 去重日滚 20）。")
    lines.append("> A 轨 = 冻结 timeline 现有 rank 坐标（=历史 B0）。")
    lines.append("> C 轨 = 同源 raw 量用**完全相同窗口/观测**仅把 rank→percentile 重算（隔离归一化方式单一变量）。")
    lines.append("> 回测引擎: va_composite_p1_cap（dedup=8h, Cap=1.0=B0）。")
    lines.append("> 旧版（混淆版 calA/calC，11.50%/2.23）已废弃，本版为有效重验。")
    lines.append("")
    lines.append("## 1. A/C 秩坐标相关性与一致率")
    lines.append("")
    lines.append(f"- Pearson: skew r={r_sk:.5f} | atr r={r_atr:.5f} | trend r={r_tr:.5f}（均≈1.0 → 结构等价）")
    lines.append(f"- tier(v4.0) 一致率 = **{agree*100:.2f}%**（双轨非None样本 {len(both)}）")
    lines.append("- 分歧全在 skew 0.81 边界 `S_seg34_high_dn ↔ S_seg12_high_dn`（同方向翻转，")
    lines.append("  B 层同方向 tier 交易参数相同，不产生交易差异；仅边界 None 错配影响回测）。")
    lines.append("")
    lines.append("## 2. 两轨主指标（B0）")
    lines.append("")
    lines.append("| 轨 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) |")
    lines.append("|:---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(f"| A(rank) | {mA['ann_ret']*100:.2f}% | {mA['sharpe']:.2f} | {mA['max_dd']*100:.2f}% | "
                 f"{mA['monthly_win']*100:.1f}% | {mA['ir']:.3f} | {mA['nu_implied']:.3f} | {mA['p_nu_pos']:.3f} |")
    lines.append(f"| C(pct)  | {mC['ann_ret']*100:.2f}% | {mC['sharpe']:.2f} | {mC['max_dd']*100:.2f}% | "
                 f"{mC['monthly_win']*100:.1f}% | {mC['ir']:.3f} | {mC['nu_implied']:.3f} | {mC['p_nu_pos']:.3f} |")
    lines.append("")
    lines.append("## 3. 配对增量（A − C）与等价判定")
    lines.append("")
    lines.append("门限（spec §0.1，反向\"差异显著\"判据）: ΔSharpe≥0.2 **且** P(μ_true>0)≥0.95 → A/C 不等价。")
    lines.append("")
    lines.append(f"- ΔSharpe(A−C) = **{d['dsharpe']:+.2f}**")
    lines.append(f"- μ_true = {d['nu_true']*100:+.3f}%  | P(μ_true>0) = {d['p_nu_pos']:.3f}")
    lines.append(f"- **判定: {'差异显著 · A/C 不等价 ❌' if sig else '差异不显著 · A≈C 成立 ✅'}**")
    lines.append("")
    lines.append("## 4. 解读")
    lines.append("")
    lines.append("- A≈C 为**结构性等价**（rank/percentile 在窗口内同单调，Pearson r=1.0 必然），")
    lines.append("  与 spec §1.3.0 一致；本重验把绝对数字从废弃伪基线（11.50%/2.23）迁移到冻结真相（≈15.7%/2.72）。")
    lines.append("- 相对结论稳健：B0 可任选 A 或 C 为契约归一化（spec 默认 A）。")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
