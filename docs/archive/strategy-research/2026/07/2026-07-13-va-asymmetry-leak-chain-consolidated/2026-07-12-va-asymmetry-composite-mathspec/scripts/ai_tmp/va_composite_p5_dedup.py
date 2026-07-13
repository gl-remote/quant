#!/usr/bin/env python3
"""
va-composite · Phase 5 · 去重窗口 dedup（次可调轴，approach A 可测下游轴）

位置: scripts/ai_tmp/va_composite_p5_dedup.py
主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 B0 管线；Cap 定档 = 5.0（P1）。dedup 在 load_events 内对 timeline 事件做合约内去重。

候选: dedup ∈ {4h, 8h, 12h}（B0=8h；P_dedup=4h，spec §0.2）。
实质: 改变「同一合约在多少小时内只留首个信号」→ 直接影响事件样本量与并发密度。
      （属 B 层执行参数，不依赖上游分类器重跑，approach A 下可直接测。）

配对评估（§0.1）: 候选 vs B0(dedup=8h)@Cap=5.0，隔离配对（Cap 恒定）。
门限: ΔSharpe ≥ 0.2 且 P(μ_true>0) ≥ 0.95 方采用；否则保持 8h。

运行: uv run python scripts/ai_tmp/va_composite_p5_dedup.py
输出: project_data/ai_tmp/p5_dedup/summary.md + 各 dedup 交易明细
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1

OUT_DIR = Path("project_data/ai_tmp/p5_dedup")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CAP = 5.0
DEDUP_HOURS_LIST = [4, 8, 12]  # B0=8h；P_dedup=4h


def metrics(t: pd.DataFrame, active_days=None) -> dict:
    m = P1.base_metrics(t, active_days=active_days)
    m["monthly_win"] = P1.monthly_win_rate(t)
    m["ir"] = P1.per_trade_ir(t)
    m["nu_implied"], m["p_nu_pos"] = P1.nu_implied(t)
    return m


def run(dedup_h: int):
    P1.DEDUP_HOURS = dedup_h
    src = pd.read_parquet(P1.TIMELINE_PATH)
    ad = P1.active_day_set(src, "signed_skew_rank_roll")
    events = P1.load_events()
    rows = []
    for c, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    raw = pd.DataFrame(rows)
    t = P1.assign_equity(P1.compress(raw, CAP))
    return raw, t, events, metrics(t, ad)


def main() -> None:
    print("=" * 70)
    print(f"va-composite · Phase 5 · dedup 扫描  [Cap={CAP}, B0=8h]")
    print("=" * 70)

    res = {}
    for h in DEDUP_HOURS_LIST:
        raw, t, ev, m = run(h)
        res[h] = (raw, t, m, len(raw), len(ev))
        print(f"  dedup={h:>2}h: 事件 {len(ev):>3}  交易 {len(raw):>3}  "
              f"年化 {m['ann_ret']*100:6.2f}%  夏普 {m['sharpe']:6.2f}  MaxDD {m['max_dd']*100:6.2f}%")

    base = res[8][1]
    print("  配对增量（vs dedup=8h@Cap5，隔离）：")
    rows = []
    for h in [4, 12]:
        d = P1.paired_delta(base, res[h][1])
        adopted = (d["dsharpe"] >= 0.2) and (d["p_nu_pos"] >= 0.95)
        rows.append((h, d, adopted))
        print(f"    dedup={h}h: ΔSharpe={d['dsharpe']:+.2f}  μ_true={d['nu_true']*100:+.3f}%  "
              f"P(μ_true>0)={d['p_nu_pos']:.3f}  => {'采用 ✅' if adopted else '保持 8h ❌'}")

    # 写明细
    out_cols = ["contract", "symbol", "symbol_type", "entry_bar", "exit_bar", "direction", "tier",
                "entry_price", "exit_price", "exit_reason", "entry_atr_bps", "qty_raw", "qty_actual",
                "pnl_gross_bps", "cost_entry_bps", "cost_exit_bps",
                "pnl_net_bps", "pnl_net_ccy", "equity_before", "equity_after"]
    for h in DEDUP_HOURS_LIST:
        res[h][1][out_cols].to_parquet(OUT_DIR / f"dedup{h}.trades.parquet", index=False)

    # summary md
    L = []
    L.append("# va-asymmetry-composite · Phase 5 · dedup 报告")
    L.append("")
    L.append(f"> Cap 定档 = {CAP}。dedup 为 B 层执行参数（合约内去重窗口），approach A 下可直测。")
    L.append("")
    L.append("## 1. 各 dedup 主指标")
    L.append("")
    L.append("| dedup | 事件数 | 交易数 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) |")
    L.append("|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for h in DEDUP_HOURS_LIST:
        _, t, m, n_tr, n_ev = res[h]
        L.append(f"| {h}h | {n_ev} | {n_tr} | {m['ann_ret']*100:.2f}% | {m['sharpe']:.2f} | "
                 f"{m['max_dd']*100:.2f}% | {m['monthly_win']*100:.1f}% | {m['ir']:.3f} | "
                 f"{m['nu_implied']:.3f} | {m['p_nu_pos']:.3f} |")
    L.append("")
    L.append("## 2. 配对增量（vs 8h@Cap5，隔离）")
    L.append("")
    L.append("| dedup | ΔSharpe | μ_true | P(μ_true>0) | 判定 |")
    L.append("|:---:|---:|---:|---:|:---:|")
    for h, d, adopted in rows:
        L.append(f"| {h}h | {d['dsharpe']:+.2f} | {d['nu_true']*100:+.3f}% | {d['p_nu_pos']:.3f} | "
                 f"{'采用 ✅' if adopted else '保持 8h ❌'} |")
    L.append("")
    L.append("## 3. 解读")
    L.append("")
    adopt = [h for h, _, a in rows if a]
    if adopt:
        L.append(f"- 过门档: {adopt}。缩短/延长去重窗口带来显著增量，采用对应档。")
    else:
        L.append("- 无档过门：4h/12h 相对 8h 增量不显著（或为负），保持 **8h**。")
        L.append("- 符合「局部塑形轴增量本应小」先验（归档 KF）；dedup 非主调节，B0(8h) 已近该维最优。")
    L.append("")
    (OUT_DIR / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"  写出: {OUT_DIR / 'summary.md'}")

    if adopt:
        print(f"Phase 5 结论: 采用 dedup={adopt}")
    else:
        print("Phase 5 结论: 保持 dedup=8h（无候选过门）")


if __name__ == "__main__":
    main()
