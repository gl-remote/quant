#!/usr/bin/env python3
"""
va-composite · Phase 9 · 治理裁剪与最优组合

位置: scripts/ai_tmp/va_p09_governance.py
主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 B0 管线（复用 va_composite_p1_cap 的模拟/指标层）

目标（experiment-plan § Phase 9）:
  1. sym(tier) 个别裁剪：按 symbol / symbol_type / tier 归因，识别不稳定 / 拖累个体，测试剔除后增量。
  2. 最优参数集 vs B0 终验：本轮过门候选仅 Cap=4.0（P1 采纳），其余保持 B0 默认；
     故"最优集"本质 = Cap=4.0 + 默认其余，与 B0 等价（已在 P1 验证）。本脚本聚焦治理裁剪。

判定（§0.1）：裁剪后相对 B0 净夏普增量 ΔSh≥0.2 且 P(μ_true>0)≥0.95 方采用；否则保留 B0 为生产基线。
分层：最优集须在全样本 + A/B/C 子样本上均满足门限。

运行: uv run python scripts/ai_tmp/va_p09_governance.py
输出: project_data/ai_tmp/p9_governance/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402

OUT_DIR = Path("project_data/ai_tmp/p9_governance")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CAP = 4.0


def run_full(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for contract, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(contract, g))
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    return P1.compress(t, CAP)


def group_stats(trades: pd.DataFrame, key: str) -> pd.DataFrame:
    out = []
    for name, g in trades.groupby(key):
        bps = g["pnl_net_bps"].values
        n = len(bps)
        if n < 5:
            continue
        bps_d = bps / 10000.0  # 转小数，μ_true=μ−σ²/2 需同量纲
        mu = bps_d.mean()
        sd = bps_d.std()
        ir = bps.mean() / bps.std() if bps.std() > 0 else 0.0
        rng = np.random.default_rng(0)
        nus = np.empty(2000)
        for i in range(2000):
            s = rng.choice(bps_d, n, replace=True)
            nus[i] = s.mean() - s.var() / 2.0
        p = float((nus > 0).mean())
        out.append((name, n, bps.mean(), bps.std(), ir, p))
    return pd.DataFrame(out, columns=[key, "n", "mean_bps", "std_bps", "IR", "P_mu_pos"])


def main() -> None:
    print("=" * 70)
    print("va-composite · Phase 9 · 治理裁剪与最优组合  [基线=冻结 B0 · Cap=4.0]")
    print("=" * 70)

    tl_full = pd.read_parquet(P1.TIMELINE_PATH)
    ad = P1.active_day_set(tl_full, "signed_skew_rank_roll")
    events = P1.load_events()
    events["symbol"] = events["contract"].apply(lambda c: (P1.extract_contract_prefix(c) or "").lower())
    events["symbol_type"] = events["symbol"].map(P1.SYMBOL_TYPE).fillna("C")

    trades = run_full(events)
    full_m = P1.base_metrics(trades, active_days=ad)
    print(f"[full B0] n={len(trades)} ann={full_m['ann_ret']*100:.2f}% sharpe={full_m['sharpe']:.2f} "
          f"max_dd={full_m['max_dd']*100:.2f}%")

    print("\n[attribution] by symbol_type")
    st = group_stats(trades, "symbol_type")
    print(st.to_string(index=False))
    print("\n[attribution] by tier")
    print(group_stats(trades, "tier").to_string(index=False))
    print("\n[attribution] by symbol (sorted by P_mu_pos)")
    sym = group_stats(trades, "symbol").sort_values("P_mu_pos")
    print(sym.to_string(index=False))

    # ---- 裁剪 1: 剔除拖累 symbol (P_mu_pos < 0.5) ----
    bad_sym = set(sym[sym["P_mu_pos"] < 0.5]["symbol"])
    print(f"\n[prune] 剔除拖累 symbol (P<0.5): {bad_sym}")
    pruned = events[~events["symbol"].isin(bad_sym)]
    tr_p = run_full(pruned)
    d_sym = P1.paired_delta(trades, tr_p)
    print(f"  剔除后 n={len(tr_p)} ΔSh={d_sym['dsharpe']:+.2f} μ_true={d_sym['nu_true']:+.2f}bps "
          f"P(μ_true>0)={d_sym['p_nu_pos']:.3f} -> {'过门✅' if (d_sym['dsharpe']>=0.2 and d_sym['p_nu_pos']>=0.95) else '未过门❌'}")

    # 按 A/B/C 分层配对
    layer = {}
    for s in ["A", "B", "C"]:
        sub = trades[trades["symbol_type"] == s]
        subp = tr_p[tr_p["symbol_type"] == s]
        if len(sub) and len(subp):
            dd = P1.paired_delta(sub, subp)
            layer[s] = (dd["dsharpe"], dd["p_nu_pos"])
            print(f"    {s} 层: ΔSh={dd['dsharpe']:+.2f} P={dd['p_nu_pos']:.3f}")

    # ---- 裁剪 2: 剔除拖累 tier (IR<0 整类) ----
    tier_stat = group_stats(trades, "tier")
    bad_tier = set(tier_stat[tier_stat["IR"] < 0]["tier"])
    print(f"\n[prune] 剔除拖累 tier (IR<0): {bad_tier}")
    if bad_tier:
        pruned_t = events[~events["tier_v40"].isin(bad_tier)]
        tr_t = run_full(pruned_t)
        d_t = P1.paired_delta(trades, tr_t)
        print(f"  剔除后 n={len(tr_t)} ΔSh={d_t['dsharpe']:+.2f} P(μ_true>0)={d_t['p_nu_pos']:.3f} -> "
              f"{'过门✅' if (d_t['dsharpe']>=0.2 and d_t['p_nu_pos']>=0.95) else '未过门❌'}")
    else:
        d_t = None
        print("  无 IR<0 的 tier（全部 tier 正贡献），无需剔除")

    # ---- 写 summary ----
    s = []
    s.append("# Phase 9 · 治理裁剪与最优组合\n")
    s.append("> 基线 = 冻结 B0（Cap=4.0、风控全关、T1 生产 flag）。本轮过门候选仅 Cap=4.0（P1 采纳），其余保持默认。\n")
    s.append(f"> FULL B0: n={len(trades)} ann={full_m['ann_ret']*100:.2f}% sharpe={full_m['sharpe']:.2f} "
             f"max_dd={full_m['max_dd']*100:.2f}%\n")
    s.append("\n## 归因（symbol_type / tier / symbol）\n")
    s.append("### by symbol_type\n" + st.to_string(index=False) + "\n")
    s.append("### by tier\n" + group_stats(trades, 'tier').to_string(index=False) + "\n")
    s.append("### by symbol (sorted by P_mu_pos)\n" + sym.to_string(index=False) + "\n")
    s.append("\n## 裁剪测试（配对 ΔSh / P(μ_true>0)，§0.1 门限 ΔSh≥0.2 且 P≥0.95）\n")
    s.append(f"- 剔除拖累 symbol (P<0.5) {sorted(bad_sym)}: ΔSh={d_sym['dsharpe']:+.2f} "
             f"P={d_sym['p_nu_pos']:.3f} -> {'过门✅' if (d_sym['dsharpe']>=0.2 and d_sym['p_nu_pos']>=0.95) else '未过门❌'}")
    for k, (ds, p) in layer.items():
        s.append(f"  - {k} 层: ΔSh={ds:+.2f} P={p:.3f}")
    if bad_tier:
        s.append(f"- 剔除拖累 tier (IR<0) {sorted(bad_tier)}: ΔSh={d_t['dsharpe']:+.2f} "
                 f"P={d_t['p_nu_pos']:.3f} -> {'过门✅' if (d_t['dsharpe']>=0.2 and d_t['p_nu_pos']>=0.95) else '未过门❌'}")
    else:
        s.append("- 剔除拖累 tier: 无 IR<0 的 tier，全部正贡献，无需剔除")
    s.append("\n## 结论\n")
    s.append("- 治理裁剪结论见正文；最优参数集 = Cap=4.0 + 默认其余（已逐项验证等价于 B0）。\n")
    (OUT_DIR / "summary.md").write_text("\n".join(s))
    print("\n[done] 见", OUT_DIR / "summary.md")


if __name__ == "__main__":
    main()
