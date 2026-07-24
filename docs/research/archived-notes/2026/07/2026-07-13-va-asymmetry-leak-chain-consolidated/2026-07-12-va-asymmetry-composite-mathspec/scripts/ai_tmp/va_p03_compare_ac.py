#!/usr/bin/env python3
"""
va-composite · P3 · 归一化 A vs C 配对确认（在 P0.1 正确口径双轨上）

位置: scripts/ai_tmp/va_p03_compare_ac.py
主题: docs/research/themes/va-asymmetry-composite/
依赖:
  - P0.1 产物: project_data/ai_tmp/p0_calib/timeline_calA.parquet (A 轨)
                              timeline_calC.parquet (C 轨)
  - 回测引擎复用 va_composite_p1_cap.py（同一套 B 层模拟/压仓/指标/配对增量，
    确保方法论与已跑 Phase 一致）。

P3 要确认的命题（spec §1.3.0: A≈C）:
  在正确口径下，A(rank) 与 C(percentile) 应给出等价策略。
  诊断(diag.md)已显示: 坐标 r=1.0（数值重合），但 tier 一致率 85.8%，
  分歧集中于 skew 0.81 边界 S_seg34↔S_seg12（同方向翻转）。
  由于 B 层同方向 tier 交易参数完全相同（short 均 K=2.5/H=10），
  同方向翻转不改变交易；唯一影响回测的是"落入 A_TIER_RAW 的 None 错配"
  （一端交易、另一端不交易）。故严谨确认 = 两轨跑同一 B 层回测比配对增量。

门限（spec §0.1，采用档判定；此处用于"是否差异显著"的反向判定）:
  ΔSharpe(d) ≥ 0.2  AND  P(μ_true>0) ≥ 0.95 同时成立 → 视为"差异显著、A/C 不等价"。
  P3 期望两轨差异远未过门（即 A≈C 成立）。

注意: 为隔离 A/C 效应，采用 B0 默认 dedup=8h（P3 在依赖链上早于 P5，不引入 P5 的 4h）。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))
import va_composite_p1_cap as p1  # noqa: E402  (复用 B 层引擎；导入不触发 main)

from va_composite_p1_cap import (  # noqa: E402
    simulate_contract, compress, assign_equity, base_metrics,
    monthly_win_rate, per_trade_ir, nu_implied, paired_delta,
    A_TIER_RAW, TIER_TO_V40, EQUITY_INIT, DEDUP_HOURS,
)

CALA = Path("project_data/ai_tmp/p0_calib/timeline_calA.parquet")
CALC = Path("project_data/ai_tmp/p0_calib/timeline_calC.parquet")
OUT = Path("project_data/ai_tmp/p3_ac")
OUT.mkdir(parents=True, exist_ok=True)


def load_events(path: Path) -> pd.DataFrame:
    """与 P1 load_events 同构，但 timeline 路径可配置；dedup 沿用 P1 全局 DEDUP_HOURS。"""
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


def run_backtest(path: Path, tag: str) -> pd.DataFrame:
    print(f"  [{tag}] 加载 timeline + 构建信号 ...")
    events = load_events(path)
    print(f"       A_TIER_RAW 过滤后事件: {len(events)} | 合约 {events['contract'].nunique()} | "
          f"多:{(events['direction']=='long').sum()} 空:{(events['direction']=='short').sum()}")
    print(f"  [{tag}] 逐合约 5m 精确模拟 ...")
    rows = []
    for contract, g in events.groupby("contract"):
        rows.extend(simulate_contract(contract, g))
    raw = pd.DataFrame(rows)
    print(f"       模拟交易数: {len(raw)} | SL:{(raw['exit_reason']=='SL').sum()} "
          f"TIME:{(raw['exit_reason']=='TIME').sum()}")
    t = compress(raw, 1.0)  # B0: Cap=1.0
    t = assign_equity(t)
    m = base_metrics(t)
    m["monthly_win"] = monthly_win_rate(t)
    m["ir"] = per_trade_ir(t)
    m["nu_implied"], m["p_nu_pos"] = nu_implied(t)
    t.to_parquet(OUT / f"ac_{tag}.trades.parquet", index=False)
    return t, m


def main() -> None:
    print("=" * 70)
    print("va-composite · P3 · 归一化 A vs C 配对确认（正确口径双轨）")
    print(f"  回测引擎: va_composite_p1_cap (dedup={DEDUP_HOURS}h, Cap=1.0=B0)")
    print("=" * 70)

    tA, mA = run_backtest(CALA, "A")
    tC, mC = run_backtest(CALC, "C")

    print("[P3] 配对增量（A vs C）...")
    d = paired_delta(tA, tC)
    # "差异显著" 反向判定：过门 = A/C 不等价
    sig = (d["dsharpe"] >= 0.2) and (d["p_nu_pos"] >= 0.95)

    print(f"  A  : 年化 {mA['ann_ret']*100:6.2f}%  夏普 {mA['sharpe']:.2f}  MaxDD {mA['max_dd']*100:6.2f}%  "
          f"月度胜率 {mA['monthly_win']*100:.1f}%  ν {mA['nu_implied']:.3f} P(ν>0) {mA['p_nu_pos']:.3f}")
    print(f"  C  : 年化 {mC['ann_ret']*100:6.2f}%  夏普 {mC['sharpe']:.2f}  MaxDD {mC['max_dd']*100:6.2f}%  "
          f"月度胜率 {mC['monthly_win']*100:.1f}%  ν {mC['nu_implied']:.3f} P(ν>0) {mC['p_nu_pos']:.3f}")
    print(f"  ΔSharpe(A−C)={d['dsharpe']:+.2f}  μ_true={d['nu_true']*100:+.3f}%  P(μ_true>0)={d['p_nu_pos']:.3f}")
    print(f"  => {'差异显著 · A/C 不等价 ❌' if sig else '差异不显著 · A≈C 成立 ✅'}")

    # 写 summary
    lines = []
    lines.append("# va-asymmetry-composite · Phase 3 · 归一化 A vs C 配对确认报告")
    lines.append("")
    lines.append("> 基线: P0.1 正确口径双轨（drop_duplicates 滚动；skew=20d/atr=20d/trend=20d，数据可行窗口）。")
    lines.append("> 回测引擎: 复用 va_composite_p1_cap（dedup=8h, Cap=1.0=B0），隔离 A/C 效应。")
    lines.append("> 命题: spec §1.3.0 主张 A(rank)≈C(percentile)；本 Phase 在正确口径下配对确认。")
    lines.append("")
    lines.append("## 1. 两轨主指标")
    lines.append("")
    lines.append("| 轨 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) |")
    lines.append("|:---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(f"| A(rank) | {mA['ann_ret']*100:.2f}% | {mA['sharpe']:.2f} | {mA['max_dd']*100:.2f}% | "
                 f"{mA['monthly_win']*100:.1f}% | {mA['ir']:.3f} | {mA['nu_implied']:.3f} | {mA['p_nu_pos']:.3f} |")
    lines.append(f"| C(pct)  | {mC['ann_ret']*100:.2f}% | {mC['sharpe']:.2f} | {mC['max_dd']*100:.2f}% | "
                 f"{mC['monthly_win']*100:.1f}% | {mC['ir']:.3f} | {mC['nu_implied']:.3f} | {mC['p_nu_pos']:.3f} |")
    lines.append("")
    lines.append("## 2. 配对增量（A − C）与等价判定")
    lines.append("")
    lines.append("门限（spec §0.1 采用判据，此处作反向\"差异显著\"判据）: ΔSharpe≥0.2 **且** P(μ_true>0)≥0.95 同时成立 → A/C 不等价。")
    lines.append("")
    lines.append(f"- ΔSharpe(A−C) = **{d['dsharpe']:+.2f}**")
    lines.append(f"- μ_g(年化) = {d['mu_g']*100:+.2f}%  | σ_g²(年化) = {d['var_g']*100:.2f}%")
    lines.append(f"- μ_true = {d['nu_true']*100:+.3f}%  | P(μ_true>0) = {d['p_nu_pos']:.3f}")
    lines.append(f"- **判定: {'差异显著 · A/C 不等价 ❌' if sig else '差异不显著 · A≈C 成立 ✅'}**")
    lines.append("")
    lines.append("## 3. 解读")
    lines.append("")
    lines.append("- 坐标层面: diag.md 显示 A/C 秩坐标 Pearson r=1.0（数值重合），与 spec §1.3.0 一致。")
    lines.append("- tier 层面: 一致率 85.8%，分歧全在 skew 0.81 边界 S_seg34↔S_seg12（同方向翻转）。")
    lines.append("  因 B 层同方向 tier 交易参数相同（short 均 K=2.5/H=10），该翻转不改变实际交易；")
    lines.append("  唯一影响回测的是\"落入 A_TIER_RAW 的 None 错配\"（一端交易、另一端不交易）。")
    lines.append(f"- 若配对增量未过门（ΔSharpe 远<0.2 或 P<0.95），即确认 A≈C 在交易意义上成立，")
    lines.append("  P3 通过；B0 可任选 A 或 C 为契约归一化（spec 默认 A）。")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
