#!/usr/bin/env python3
"""
va-composite · P3 · 归一化 B 轨尝试（冻结管线重验版 · 对齐 A/C）

位置: scripts/ai_tmp/va_p03c_b_track.py
主题: docs/research/themes/va-asymmetry-composite/

背景:
  P3 已确认 A(rank)≈C(percentile) 在冻结管线下等价（Pearson r≈1、tier 一致率~95%）。
  spec §1.3.0 把归一化候选列为 A/B/C/D 四档，其中 B = z-score 标准化（无界 ℝ），
  且 §1.3.0 注 (iii) 给出"若需 0~1 可比尺度"的对齐方案：
      稳健 loc/scale: med + 1.4826·MAD（非 σ，重尾撑大 σ）
      PIT(x) = F_t( (x−med)/(1.4826·MAD) ; ν=12 )  → 形状校正后的 0~1（参数化 t-PIT）
  §1.3.0 结论 (iv): t-PIT 仅在 N≲40（约 10–20 天窗口）时相对 rank 有增量（借已知 t 形状
  对极值收缩、稳 0.09/0.91）；常规 N≥60 天窗下 rank 已够平滑。本数据集 skew 有效窗口≈17 天
  （事件行 window=100≈17 不重复交易日），恰落"t-PIT 可能有增量"区间 → 值得一试。

本脚本严格对齐 P3 的 A-vs-C 单一变量隔离法：
  - 仅对 **skew** 切换为 B(t-PIT) 归一化；
  - **atr/trend 冻结为 A 轨（rank）值**，避免引入滚动 NaN 口径这一无关变量；
  - 同冻结管线口径（skew 事件行 window=100/min_periods=10；atr/trend 去重日滚 20）。
  因此 B vs A 是干净的"skew 归一化: rank vs t-PIT"单变量配对。

输出:
  project_data/ai_tmp/p3_b_track/timeline_B_frozen.parquet  (B 轨 = t-PIT 归一化)
  project_data/ai_tmp/p3_b_track/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

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
OUT = Path("project_data/ai_tmp/p3_b_track")
OUT.mkdir(parents=True, exist_ok=True)

SKEW_WIN, SKEW_MINP = 100, 10   # 对齐 A 轨 skew 口径（事件行）
ATR_WIN, ATR_MINP = 20, 10      # 对齐 A 轨 atr/trend 口径（去重日滚）
T_PIT_DF = 12                   # spec §1.3.0 注 (iii): ν=12


# ---------------------------------------------------------------------------
# B 归一化: 稳健 z-score + 参数化 t-PIT（spec §1.3.0 注 (iii)）
# ---------------------------------------------------------------------------
def t_pit_window(w: np.ndarray) -> float:
    """窗口内稳健 z-score → 参数化 t-PIT (ν=12) → 0~1。

    z = (x − med) / (1.4826·MAD)；PIT = F_t(z; ν=12)。
    恒定窗口（MAD≈0）信息为零 → 返回中位 0.5。
    """
    x = w[-1]
    med = np.median(w)
    mad = np.median(np.abs(w - med))
    scale = 1.4826 * mad
    if scale < 1e-12:
        return 0.5
    z = (x - med) / scale
    return float(t_dist.cdf(z, df=T_PIT_DF))


def roll_t_pit_event(s: pd.Series, N: int, minp: int) -> pd.Series:
    """skew: 未去重、逐事件行滚动 t-PIT（同 A 轨窗口/观测，仅变换不同）。"""
    return s.rolling(N, min_periods=minp).apply(t_pit_window, raw=True)


def build_b_coords(df: pd.DataFrame) -> pd.DataFrame:
    """B 轨秩坐标：仅 skew 切到 t-PIT；atr/trend 冻结为 A 轨（rank）值。

    与 P3 的 build_c_coords 对称——单变量隔离"归一化方式"。
    """
    sk_B = df.groupby("contract")["A3_skew"].transform(
        lambda s: roll_t_pit_event(s, SKEW_WIN, SKEW_MINP))
    out = pd.DataFrame(index=df.index)
    out["sk_B"] = sk_B.values
    out["atr_B"] = df["atr_rank_roll"].values    # 冻结值（=A 轨）
    out["tr_B"] = df["trend_rank_roll"].values   # 冻结值（=A 轨）
    return out


def classify_b(df: pd.DataFrame) -> pd.Series:
    """用 POCVAClassifier 在 B 轨坐标上重算 tier，reindex 回 df.index。"""
    tmp = df[["contract", "event_time", "transition_flag",
              "sk_B", "atr_B", "tr_B"]].rename(columns={
        "sk_B": "signed_skew_rank_roll",
        "atr_B": "atr_rank_roll",
        "tr_B": "trend_rank_roll",
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
    print("va-composite · P3 · B 轨(t-PIT)尝试 vs A(rank)（冻结管线重验）")
    print(f"  回测引擎: va_composite_p1_cap (dedup={DEDUP_HOURS}h, Cap=1.0=B0)")
    print(f"  B 变换: skew 稳健 z + t-PIT(ν={T_PIT_DF}); atr/trend 冻结=A 轨")
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

    # B 轨 = skew 切到 t-PIT，atr/trend 冻结
    print(f"[1] B 轨: skew 事件行{ SKEW_WIN}/minp{SKEW_MINP} 稳健z+t-PIT(ν={T_PIT_DF})；"
          f"atr/trend 冻结=A 轨 ...")
    b_coords = build_b_coords(df)
    df_b = pd.concat([df[["contract", "event_time", "transition_flag"]], b_coords], axis=1)
    b_tier = classify_b(df_b)
    df_b["tier"] = b_tier.values
    df_b["tier_v40"] = df_b["tier"].map(TIER_TO_V40)

    # 诊断: A/B 秩坐标相关性 + tier 一致率
    both = pd.DataFrame({
        "sk_A": a_track["signed_skew_rank_roll"], "sk_B": b_coords["sk_B"],
        "atr_A": a_track["atr_rank_roll"], "atr_B": b_coords["atr_B"],
        "tr_A": a_track["trend_rank_roll"], "tr_B": b_coords["tr_B"],
        "tier_A": a_track["tier_v40"], "tier_B": df_b["tier_v40"],
    }).dropna()
    r_sk = both["sk_A"].corr(both["sk_B"])
    r_atr = both["atr_A"].corr(both["atr_B"])
    r_tr = both["tr_A"].corr(both["tr_B"])
    agree = (both["tier_A"] == both["tier_B"]).mean()
    print(f"     A/B 秩坐标 Pearson: skew r={r_sk:.5f} atr r={r_atr:.5f} trend r={r_tr:.5f}")
    print(f"     tier(v4.0) 一致率 = {agree*100:.2f}%  (双轨非None样本 {len(both)})")
    flips = both[both["tier_A"] != both["tier_B"]].groupby(["tier_A", "tier_B"]).size()
    if len(flips):
        print("     不一致明细 (A -> B):")
        for (a, c), n in flips.items():
            print(f"       {a} -> {c}: {n}")

    # 写 B 轨 timeline
    base_cols = [c for c in df.columns]
    tl_B = df[base_cols].copy()
    tl_B["signed_skew_rank_roll"] = b_coords["sk_B"]
    tl_B["atr_rank_roll"] = b_coords["atr_B"]
    tl_B["trend_rank_roll"] = b_coords["tr_B"]
    tl_B["tier"] = df_b["tier"].reindex(df.index)
    tl_B["tier_v40"] = df_b["tier_v40"].reindex(df.index)
    tl_B = tl_B.dropna(subset=["tier"])
    tl_B.to_parquet(OUT / "timeline_B_frozen.parquet", index=False)
    print(f"     timeline_B_frozen: {len(tl_B)} 行 | B 非None tier {tl_B['tier'].notna().sum()}")

    # A / B 配对回测
    print("[2] A(rank) vs B(t-PIT) 配对回测 (dedup=8h, Cap=1.0) ...")
    tA, mA = run_backtest(OUT / "timeline_A_frozen.parquet", "A") \
        if (OUT / "timeline_A_frozen.parquet").exists() \
        else run_backtest(SRC, "A(frozen)")
    tB, mB = run_backtest(OUT / "timeline_B_frozen.parquet", "B")
    d = paired_delta(tA, tB)
    sig = (d["dsharpe"] >= 0.2) and (d["p_nu_pos"] >= 0.95)
    print(f"  A  : 年化 {mA['ann_ret']*100:6.2f}%  夏普 {mA['sharpe']:.2f}  MaxDD {mA['max_dd']*100:6.2f}%  "
          f"ν {mA['nu_implied']:.3f} P(ν>0) {mA['p_nu_pos']:.3f}")
    print(f"  B  : 年化 {mB['ann_ret']*100:6.2f}%  夏普 {mB['sharpe']:.2f}  MaxDD {mB['max_dd']*100:6.2f}%  "
          f"ν {mB['nu_implied']:.3f} P(ν>0) {mB['p_nu_pos']:.3f}")
    print(f"  ΔSharpe(A−B)={d['dsharpe']:+.2f}  μ_true={d['nu_true']*100:+.3f}%  P(μ_true>0)={d['p_nu_pos']:.3f}")
    print(f"  => {'差异显著 · A/B 不等价 ❌' if sig else '差异不显著 · A≈B 成立 ✅'}")

    # summary
    lines = []
    lines.append("# va-asymmetry-composite · Phase 3 · B 轨(t-PIT)尝试 vs A(rank)（冻结管线重验）")
    lines.append("")
    lines.append("> 基线: **冻结管线**（未去重 skew 事件行 window=100；atr/trend 去重日滚 20）。")
    lines.append("> A 轨 = 冻结 timeline 现有 rank 坐标（=历史 B0）。")
    lines.append(f"> B 轨 = 同源 raw 量对 **skew 切到 t-PIT**（稳健 z=med+1.4826·MAD，PIT=F_t(·;ν={T_PIT_DF})），"
                 "atr/trend 冻结=A 轨值，单一变量隔离'归一化方式'。")
    lines.append("> 回测引擎: va_composite_p1_cap（dedup=8h, Cap=1.0=B0）。")
    lines.append("> 口径(2026-07-11 改): 年化分母=只用 skew 秩拿到值(非NaN)的那天(交易日,剔周末)并集, 年因子 252。")
    lines.append("")
    lines.append("## 1. A/B 秩坐标相关性与一致率")
    lines.append("")
    lines.append(f"- Pearson: skew r={r_sk:.5f} | atr r={r_atr:.5f} | trend r={r_tr:.5f}（atr/trend 冻结故=1）")
    lines.append(f"- tier(v4.0) 一致率 = **{agree*100:.2f}%**（双轨非None样本 {len(both)}）")
    if len(flips):
        lines.append("- 不一致明细 (A -> B):")
        for (a, c), n in flips.items():
            lines.append(f"  - {a} -> {c}: {n}")
    lines.append("")
    lines.append("## 2. 两轨主指标（B0）")
    lines.append("")
    lines.append("| 轨 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) |")
    lines.append("|:---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(f"| A(rank) | {mA['ann_ret']*100:.2f}% | {mA['sharpe']:.2f} | {mA['max_dd']*100:.2f}% | "
                 f"{mA['monthly_win']*100:.1f}% | {mA['ir']:.3f} | {mA['nu_implied']:.3f} | {mA['p_nu_pos']:.3f} |")
    lines.append(f"| B(t-PIT) | {mB['ann_ret']*100:.2f}% | {mB['sharpe']:.2f} | {mB['max_dd']*100:.2f}% | "
                 f"{mB['monthly_win']*100:.1f}% | {mB['ir']:.3f} | {mB['nu_implied']:.3f} | {mB['p_nu_pos']:.3f} |")
    lines.append("")
    lines.append("## 3. 配对增量（A − B）与等价判定")
    lines.append("")
    lines.append("门限（spec §0.1，反向\"差异显著\"判据）: ΔSharpe≥0.2 **且** P(μ_true>0)≥0.95 → A/B 不等价。")
    lines.append("")
    lines.append(f"- ΔSharpe(A−B) = **{d['dsharpe']:+.2f}**")
    lines.append(f"- μ_true = {d['nu_true']*100:+.3f}%  | P(μ_true>0) = {d['p_nu_pos']:.3f}")
    lines.append(f"- **判定: {'差异显著 · A/B 不等价 ❌' if sig else '差异不显著 · A≈B 成立 ✅'}**")
    lines.append("")
    lines.append("## 4. 解读")
    lines.append("")
    lines.append("- 若 A≈B：印证 spec §1.3.0 结论——在固定窗口下 rank 已足够，t-PIT 未带来增量，")
    lines.append("  B 仅作 ℝ 尺度待校准变体、不优于默认 A。")
    lines.append("- 若 A≠B（B 更优）：说明本数据集 skew 窗口≈17天落 §1.3.0 注(iv)'N≲40 t-PIT 有增量'区间，")
    lines.append("  B 借已知 t(ν=12) 形状对极值收缩、稳住 0.09/0.91 边界，值得升级为默认归一化。")
    lines.append("- 相对结论稳健：无论 A≈B 与否，都已把 B 纳入归一化候选实测，补全 spec A/B/C/D 的 B 实测空缺。")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
