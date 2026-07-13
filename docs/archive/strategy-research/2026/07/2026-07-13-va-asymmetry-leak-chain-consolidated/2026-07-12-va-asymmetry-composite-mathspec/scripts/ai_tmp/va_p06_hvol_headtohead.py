#!/usr/bin/env python3
"""
va-composite · Phase 6 · `H_vol(tier)` 持仓时长分化 —— **对称头对头检验（不赋予默认特殊地位）**

动机：原 P6 门禁 `ΔSh≥0.2 且 P(μ_true>0)≥0.95` 是**单向在位者保护**——
只要求"挑战者 H_vol 必须被严格证明更优才能替换统一 8/10h"，从不问"统一是否被证明更优"。
导致"维持统一 8/10h"既非"统一优于分tier"的证据，也非"分tier弱"的证据，只是平局/方向判给在位者。

本脚本改用**对称工具**：直接对 Δν(H_vol−B0)、ΔSharpe(H_vol−B0) 做簇自助
(按 contract×exit_date 簇)，取完整分布与**双侧 95%/80% CI**，Verdict 由"CI 是否排除 0"决定，
H_vol 与 B0 完全对称：
  - CI95 下界>0  → 分tier(H_vol) 更优(95%)
  - CI95 上界<0  → 统一8/10h(B0) 更优(95%)
  - 含 0         → 95% 水平**统计不可区分**

复用 P6 walk-forward 已落盘的成对交易 parquet（oos_{T,C,B0} / ins_{T,C,B0}）。
运行: uv run python scripts/ai_tmp/va_p06_hvol_headtohead.py
输出: project_data/ai_tmp/p6_hvol_headtohead/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
import va_composite_p1_cap as P1  # noqa: E402

SRC = Path("project_data/ai_tmp/p6_hvol")
OUT = Path("project_data/ai_tmp/p6_hvol_headtohead")
OUT.mkdir(parents=True, exist_ok=True)
N_BOOT = 4000


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(SRC / name)


def paired_dist(tA: pd.DataFrame, tB: pd.DataFrame, seed: int):
    """对称簇自助：返回 Δν(B−A) 与 ΔSharpe(B−A) 的完整自助分布（A/B 完全对称）。

    B = 候选(H_vol, 分tier持仓)；A = B0(uniform, 统一8/10h)。
    """
    g0 = tA.groupby(["contract", "_exit_date"])["pnl_net_ccy"].sum()
    g1 = tB.groupby(["contract", "_exit_date"])["pnl_net_ccy"].sum()
    gi = g0.index.union(g1.index)
    g0 = g0.reindex(gi, fill_value=0.0)
    g1 = g1.reindex(gi, fill_value=0.0)
    dcl = (g1 - g0) / P1.EQUITY_INIT          # 每簇净值差（权益分数）
    arr = dcl.values
    k = len(arr)

    d0 = tA.groupby("_exit_date")["pnl_net_ccy"].sum() / P1.EQUITY_INIT
    d1 = tB.groupby("_exit_date")["pnl_net_ccy"].sum() / P1.EQUITY_INIT
    idx = d0.index.union(d1.index)
    d0 = d0.reindex(idx, fill_value=0.0)
    d1 = d1.reindex(idx, fill_value=0.0)
    delta = (d1 - d0).values
    nd = len(delta)

    rng = np.random.default_rng(seed)
    nus = np.empty(N_BOOT)
    shs = np.empty(N_BOOT)
    for i in range(N_BOOT):
        sel = rng.integers(0, k, size=k)
        s = arr[sel].sum()
        ss = (arr[sel] ** 2).sum()
        mean = s / k
        varc = ss / k - mean * mean
        nus[i] = mean * 252.0 - varc * 252.0 / 2.0
        sd = rng.integers(0, nd, size=nd)
        dd = delta[sd]
        shs[i] = dd.mean() * 252.0 / (dd.std() * np.sqrt(252.0)) if dd.std() > 0 else 0.0
    return nus, shs


def verdict(dist, label):
    lo95, hi95 = np.percentile(dist, [2.5, 97.5])
    lo80, hi80 = np.percentile(dist, [10, 90])
    pt = dist.mean()
    p_pos = float((dist > 0).mean())          # P(H_vol > B0)
    p_neg = float((dist < 0).mean())          # P(B0 > H_vol)
    p_two = 2.0 * min(p_pos, p_neg)           # 双侧 p
    if lo95 > 0:
        v = "分tier(H_vol) 更优(95% CI 排除0)"
    elif hi95 < 0:
        v = "统一8/10h(B0) 更优(95% CI 排除0)"
    else:
        v = "95% 不可区分(含0)"
    return dict(pt=pt, lo95=lo95, hi95=hi95, lo80=lo80, hi80=hi80,
                p_pos=p_pos, p_neg=p_neg, p_two=p_two, verdict=v, label=label)


def main() -> None:
    print("=" * 78)
    print("va-composite · Phase 6 · H_vol(tier) vs B0(uniform) —— 对称头对头（无默认特权）")
    print(f"  簇自助 N_BOOT={N_BOOT} · 复用 p6_hvol walk-forward 成对交易 parquet")
    print("=" * 78)

    tB0_oos, tT_oos, tC_oos = load("oos_B0.trades.parquet"), load("oos_T.trades.parquet"), load("oos_C.trades.parquet")
    tB0_ins, tT_ins, tC_ins = load("ins_B0.trades.parquet"), load("ins_T.trades.parquet"), load("ins_C.trades.parquet")

    cases = [
        ("OOS walk-forward · H_vol(T) vs B0(uniform)", tB0_oos, tT_oos, 31),
        ("OOS walk-forward · H_vol(C) vs B0(uniform)", tB0_oos, tC_oos, 37),
        ("in-sample · H_vol(T) vs B0(uniform)", tB0_ins, tT_ins, 41),
        ("in-sample · H_vol(C) vs B0(uniform)", tB0_ins, tC_ins, 47),
    ]

    res = {}
    for name, a, b, seed in cases:
        nus, shs = paired_dist(a, b, seed)
        rv = verdict(nus, "Δν(H_vol−B0)")
        rs = verdict(shs, "ΔSharpe(H_vol−B0)")
        res[name] = (rv, rs)
        print(f"\n[{name}]")
        print(f"  Δν(H_vol−B0) : 点估 {rv['pt']:+.4f} | 95%CI[{rv['lo95']:+.4f},{rv['hi95']:+.4f}] "
              f"| 80%CI[{rv['lo80']:+.4f},{rv['hi80']:+.4f}] | P(H_vol>B0)={rv['p_pos']:.3f} "
              f"P(B0>H_vol)={rv['p_neg']:.3f} 双侧p={rv['p_two']:.3f}")
        print(f"            Verdict: {rv['verdict']}")
        print(f"  ΔSh(H_vol−B0) : 点估 {rs['pt']:+.3f} | 95%CI[{rs['lo95']:+.3f},{rs['hi95']:+.3f}] "
              f"| Verdict: {rs['verdict']}")

    # ---- 写 summary ----
    L = []
    L.append("# va-asymmetry-composite · Phase 6 · H_vol(tier) vs B0(uniform) —— 对称头对头检验")
    L.append("")
    L.append("> 日期 2026-07-11 · 动机：原 P6 门禁 `ΔSh≥0.2 且 P(μ_true>0)≥0.95` 是**单向在位者保护**，"
             "把'默认=统一8/10h'当结论，无法回答'分tier持仓时长会不会更好'。")
    L.append("> 本工具**对称**：对 Δν(H_vol−B0)、ΔSharpe(H_vol−B0) 做簇自助(contract×exit_date)，"
             "取完整分布与**双侧 95%/80% CI**，Verdict 由'CI 是否排除 0'决定，H_vol 与 B0 无特殊地位。")
    L.append("> 复用 p6_hvol walk-forward 已落盘成对交易（oos_/ins_ 下 T/C/B0 三套，同一批事件、仅持仓时长 resolver 不同）。")
    L.append("")
    L.append("## 1. 对称 Verdict（核心）")
    L.append("")
    L.append("| 样本 | 量(H_vol−B0) 点估 | 95%CI | 80%CI | P(H_vol>B0) | P(B0>H_vol) | 双侧p | Verdict(95%) |")
    L.append("|:---|---:|---:|---:|---:|---:|---:|:---|")
    for name, (rv, rs) in res.items():
        L.append(f"| {name} · Δν | {rv['pt']:+.4f} | [{rv['lo95']:+.4f},{rv['hi95']:+.4f}] | "
                 f"[{rv['lo80']:+.4f},{rv['hi80']:+.4f}] | {rv['p_pos']:.3f} | {rv['p_neg']:.3f} | "
                 f"{rv['p_two']:.3f} | {rv['verdict']} |")
        L.append(f"| {name} · ΔSh | {rs['pt']:+.3f} | [{rs['lo95']:+.3f},{rs['hi95']:+.3f}] | "
                 f"— | — | — | — | {rs['verdict']} |")
    L.append("")
    L.append("## 2. 解读（先于程序正确性，对称视角）")
    L.append("")
    L.append("- **Δν 95% CI 整体 < 0** ⇒ 在 95% 双侧下**统一 8/10h 显著不差于（甚至优于）分tier持仓**；"
             "这与原 P6 门禁'未过'结论方向一致，但对称工具给出的是**可区分的诚实结论**，而非'挑战者没证明'的沉默。")
    L.append("- **Δν 95% CI 含 0** ⇒ 两者统计不可区分：分tier 不比统一差、也不显著更好，维持统一是惯例而非证据。")
    L.append("- **Δν 95% CI 整体 > 0** ⇒ 分tier 持仓时长确实更好（与原 P2 in-sample 信号呼应、且样本外成立）。")
    L.append("- 注意 H_vol 的 OOS 方向：若 Δν/ΔSh 点估为负且 CI 偏负，则属'in-sample 虚高/过拟合'性质"
             "（对照归一化 B 的 OOS 正向 +1.50，二者性质不同——B 是真实 edge 带噪，H_vol 是挑峰乐观）。")
    L.append("")
    L.append("## 3. 对称下的决策含义")
    L.append("")
    L.append("- 若对称结果显示 H_vol 在 95% CI 下**不可区分或显著更差**，则'维持统一 8/10h'不是 status-quo bias，"
             "而是**数据确实不支持分tier**——此时可更放心地锁定 §0.1 的 `H_vol(tier)` 为'候选不升格'。")
    L.append("- 若 80% 单侧下 H_vol 仍偏负，则连'风险偏好换更好估计'都不成立，H_vol 轴应在更大样本/跨期复验前搁置。")
    L.append("- 局限：本检验建立在 P6 同一事件集/引擎上，仅替换'判定工具'为对称 CI；未引入新数据。"

             "要真正分胜负仍需更大样本或跨期复验。")
    L.append("")

    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
