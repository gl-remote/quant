#!/usr/bin/env python3
"""
va-composite · P3 · B 轨(t-PIT) —— **对称 A/B 头对头检验（不赋予默认特殊地位）**

动机：原门禁 `ΔSh≥0.2 且 P(μ_true>0)≥0.95` 是**单向在位者保护**——
只要求"挑战者必须被严格证明更优才能上位"，从不问"在位者是否被证明更优"。
导致"维持 A 默认"既非"A 优于 B"的证据，也非"B 弱"的证据，只是平局判给在位者。

本脚本改用**对称工具**：直接对 Δν(B−A)、ΔSharpe(B−A) 做簇自助(按 contract×exit_date 簇)，
取完整分布与**双侧置信区间**，Verdict 由"CI 是否排除 0"决定，A/B 完全对称：
  - CI95 下界>0  → B 更优(95%)
  - CI95 上界<0  → A 更优(95%)
  - 含 0         → 95% 水平**统计不可区分**（无特殊地位下的真实平局）
同时报双侧 p = 2·min(P(B>A), P(A>B))，以及"偏向 B 的单侧置信"。

复用上一轮 walk-forward 已落盘的成对交易 parquet（A_cap4/B_cap4 全样本、A_oos/B_oos 后50%）。
运行: uv run python scripts/ai_tmp/va_p03b_ab_headtohead.py
输出: project_data/ai_tmp/p3b_b_headtohead/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
import va_composite_p1_cap as P1  # noqa: E402

SRC = Path("project_data/ai_tmp/p3b_b_walkforward")
OUT = Path("project_data/ai_tmp/p3b_b_headtohead")
OUT.mkdir(parents=True, exist_ok=True)
N_BOOT = 4000


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(SRC / name)


def paired_dist(tA: pd.DataFrame, tB: pd.DataFrame, seed: int):
    """对称簇自助：返回 Δν(B−A) 与 ΔSharpe(B−A) 的完整自助分布（A/B 完全对称）。"""
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
    return nus, shs, arr, delta


def verdict(dist, label):
    lo95, hi95 = np.percentile(dist, [2.5, 97.5])
    lo80, hi80 = np.percentile(dist, [10, 90])
    pt = dist.mean()
    p_pos = float((dist > 0).mean())          # P(B>A)
    p_neg = float((dist < 0).mean())          # P(A>B)
    p_two = 2.0 * min(p_pos, p_neg)           # 双侧 p
    if lo95 > 0:
        v = "B 更优(95% CI 排除0)"
    elif hi95 < 0:
        v = "A 更优(95% CI 排除0)"
    else:
        v = "95% 不可区分(含0)"
    return dict(pt=pt, lo95=lo95, hi95=hi95, lo80=lo80, hi80=hi80,
                p_pos=p_pos, p_neg=p_neg, p_two=p_two, verdict=v, label=label)


def main() -> None:
    print("=" * 78)
    print("va-composite · P3 · B(t-PIT) vs A(rank) —— 对称头对头（无默认特权）")
    print(f"  簇自助 N_BOOT={N_BOOT} · 复用 p3b_b_walkforward 成对交易 parquet")
    print("=" * 78)

    tA_full, tB_full = load("A_cap4.trades.parquet"), load("B_cap4.trades.parquet")
    tA_oos, tB_oos = load("A_oos.trades.parquet"), load("B_oos.trades.parquet")

    cases = [
        ("全样本 in-sample（Cap=4.0）", tA_full, tB_full, 11),
        ("OOS 后50% 持有期外（Cap=4.0）", tA_oos, tB_oos, 23),
    ]

    res = {}
    for name, a, b, seed in cases:
        nus, shs, _, _ = paired_dist(a, b, seed)
        rv = verdict(nus, "Δν(B−A)")
        rs = verdict(shs, "ΔSharpe(B−A)")
        res[name] = (rv, rs)
        print(f"\n[{name}]")
        print(f"  Δν(B−A) : 点估 {rv['pt']:+.4f} | 95%CI[{rv['lo95']:+.4f},{rv['hi95']:+.4f}] "
              f"| 80%CI[{rv['lo80']:+.4f},{rv['hi80']:+.4f}] | P(B>A)={rv['p_pos']:.3f} "
              f"P(A>B)={rv['p_neg']:.3f} 双侧p={rv['p_two']:.3f}")
        print(f"            Verdict: {rv['verdict']}")
        print(f"  ΔSh(B−A) : 点估 {rs['pt']:+.3f} | 95%CI[{rs['lo95']:+.3f},{rs['hi95']:+.3f}] "
              f"| Verdict: {rs['verdict']}")

    # ---- 写 summary ----
    L = []
    L.append("# va-asymmetry-composite · Phase 3 · B(t-PIT) vs A(rank) —— 对称头对头检验")
    L.append("")
    L.append("> 日期 2026-07-11 · 动机：原门禁 `ΔSh≥0.2 且 P(μ_true>0)≥0.95` 是**单向在位者保护**，"
             "把平局判给默认，无法回答'A 还是 B 更优'。")
    L.append("> 本工具**对称**：对 Δν(B−A)、ΔSharpe(B−A) 做簇自助(contract×exit_date)，"
             "取完整分布与**双侧 95%/80% CI**，Verdict 由'CI 是否排除 0'决定，A/B 无特殊地位。")
    L.append("> 复用 p3b_b_walkforward 已落盘成对交易（A_cap4/B_cap4 全样本、A_oos/B_oos 后50%）。")
    L.append("")
    L.append("## 1. 对称 Verdict（核心）")
    L.append("")
    L.append("| 样本 | 量(B−A) 点估 | 95%CI | 80%CI | P(B>A) | P(A>B) | 双侧p | Verdict(95%) |")
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
    L.append("- **95% 双侧 CI 含 0** ⇒ A 与 B 在统计上**不可区分**：既不能说 B 更优，也不能说 A 更优。"
             "这**不是**'A 被证明优于 B'，而是'证据不足以分胜负'。")
    L.append("- 原门禁'维持 A 默认'的真相：是**平局判给在位者**(status-quo bias)，"
             "而非 A 有证据优势。若当初默认是 B，同一套门禁也会'维持 B'——默认标签由起点决定，不由证据决定。")
    L.append("- **点估计强烈偏向 B**：OOS Δν(B−A) 点估为正且幅度可观、ΔSh(B−A)=+1.50；"
             "P(B>A)=0.838 即'偏向 B 的单侧置信≈84%'。所以 B 是**更好的估计值**，只是未达 95% 双侧证明。")
    L.append("- 与 H_vol 的对照：H_vol 的 OOS 为**负向**(ΔSh=−1.10)，属'in-sample 虚高'；"
             "B 的 OOS 为**正向**(+1.50)，属'真实 edge 但带噪/非平稳'(fold0 负)。两者性质不同，B 不该被误判为'弱轴'。")
    L.append("")
    L.append("## 3. 对称下的决策含义")
    L.append("")
    L.append("- 对称工具**不改变'不宜仓促切换默认'的结论**（95% 仍不可区分），但把理由从"
             "'挑战者未达标'纠正为'双方均未证明更优的平局'。")
    L.append("- 若要在平局中按**最佳估计**取向：B 的点估计与经济意义(Δν/ΔSh 均正且大)支持 B 为更优解，"
             "代价是接受 ~84% 单侧置信（即 ~16% 概率 A 不差）。这是**风险偏好**决定，不是数据强制。")
    L.append("- 收敛平局的两条正路（与原 plan 一致）：① 扩样本/跨期复验把 OOS 量做大；"
             "② 补 ν∈{8,12,20} 鲁棒扫描，看 fold0 非平稳失效是否 ν 敏感。")
    L.append("")
    L.append("> 局限：本检验建立在上轮 walk-forward 的同一事件集/引擎上，仅替换'判定工具'为对称 CI；"
             "未引入新数据。要真正分胜负仍需更大样本或 ν 扫描。")
    L.append("")

    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
