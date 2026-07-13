#!/usr/bin/env python3
"""
va-composite · Phase 6 · H_vol(tier) —— **逐 tier 分解检验**

动机：P6 整体 OOS Δν(H_vol−B0)=−0.088（偏负、95% 含0）。但整体聚合可能掩盖结构：
某些 tier 的持仓时长调整**其实更优**、只是被其他 tier 拖累。本脚本把 OOS 拆到逐 tier，
对每个 tier 单独做配对簇自助 Δν(H_vol−B0) 的 95%/80% CI，看是否存在"部分 tier 更优"。

复用 p6_hvol walk-forward 已落盘成对交易 parquet（oos_T / oos_B0，同一批事件、仅持仓时长不同）。
运行: uv run python scripts/ai_tmp/va_p06_hvol_tierwise.py
输出: project_data/ai_tmp/p6_hvol_tierwise/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
import va_composite_p1_cap as P1  # noqa: E402

SRC = Path("project_data/ai_tmp/p6_hvol")
OUT = Path("project_data/ai_tmp/p6_hvol_tierwise")
OUT.mkdir(parents=True, exist_ok=True)
N_BOOT = 4000


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(SRC / name)


def boot_tier(sub: pd.DataFrame, seed: int):
    """对单个 tier 子集做配对簇自助 Δν(H_vol−B0)（按 contract×exit_date 簇）。"""
    g0 = sub.groupby(["contract", "_exit_date"])["b0"].sum()
    g1 = sub.groupby(["contract", "_exit_date"])["tt"].sum()
    gi = g0.index.union(g1.index)
    g0 = g0.reindex(gi, fill_value=0.0)
    g1 = g1.reindex(gi, fill_value=0.0)
    dcl = (g1 - g0) / P1.EQUITY_INIT
    arr = dcl.values
    k = len(arr)
    rng = np.random.default_rng(seed)
    nus = np.empty(N_BOOT)
    for i in range(N_BOOT):
        sel = rng.integers(0, k, size=k)
        s = arr[sel].sum()
        ss = (arr[sel] ** 2).sum()
        mean = s / k
        varc = ss / k - mean * mean
        nus[i] = mean * 252.0 - varc * 252.0 / 2.0
    return nus


def main() -> None:
    print("=" * 78)
    print("va-composite · Phase 6 · H_vol(tier) —— 逐 tier 分解检验（OOS walk-forward）")
    print(f"  簇自助 N_BOOT={N_BOOT} · 复用 p6_hvol oos_T / oos_B0 成对交易")
    print("=" * 78)

    tB0 = load("oos_B0.trades.parquet")
    tT = load("oos_T.trades.parquet")

    kB = tB0[["contract", "entry_bar", "tier", "_exit_date", "pnl_net_ccy"]].rename(
        columns={"pnl_net_ccy": "b0"})
    kT = tT[["contract", "entry_bar", "_exit_date", "pnl_net_ccy"]].rename(
        columns={"pnl_net_ccy": "tt"})
    m = kB.merge(kT, on=["contract", "entry_bar", "_exit_date"], how="inner")
    print(f"  配对笔数 {len(m)} | tier 数 {m['tier'].nunique()}")

    rows = []
    for i, (tier, sub) in enumerate(m.groupby("tier")):
        nus = boot_tier(sub, 100 + i)
        pt = nus.mean()
        lo95, hi95 = np.percentile(nus, [2.5, 97.5])
        lo80, hi80 = np.percentile(nus, [10, 90])
        p_pos = float((nus > 0).mean())
        p_neg = float((nus < 0).mean())
        n = len(sub)
        if lo95 > 0:
            v = "H_vol更优(95%)"
        elif hi95 < 0:
            v = "统一更优(95%)"
        else:
            v = "95%不可区分"
        rows.append((tier, n, pt, lo95, hi95, lo80, hi80, p_pos, p_neg, v))
        print(f"\n[tier={tier}] 配对{n}笔")
        print(f"  Δν(H_vol−B0): 点估 {pt:+.4f} | 95%CI[{lo95:+.4f},{hi95:+.4f}] "
              f"| 80%CI[{lo80:+.4f},{hi80:+.4f}] | P(H_vol>B0)={p_pos:.3f} "
              f"P(B0>H_vol)={p_neg:.3f}")
        print(f"  Verdict: {v}")

    # ---- 写 summary ----
    L = []
    L.append("# va-asymmetry-composite · Phase 6 · H_vol(tier) —— 逐 tier 分解检验")
    L.append("")
    L.append("> 日期 2026-07-11 · 动机：P6 整体 OOS Δν(H_vol−B0)=−0.088（偏负、95%含0），"
             "但整体聚合可能掩盖结构——本脚本拆到逐 tier，看是否存在'部分 tier 更优'被其他 tier 拖累。")
    L.append("> 方法：对 oos_T / oos_B0 按 (contract,entry_bar) 配对，逐 tier 做配对簇自助 Δν(H_vol−B0) 的 95%/80% CI。")
    L.append("")
    L.append("## 1. 逐 tier Verdict（核心）")
    L.append("")
    L.append("| tier | 配对笔数 | Δν点估 | 95%CI | 80%CI | P(H_vol>B0) | P(B0>H_vol) | Verdict |")
    L.append("|:---|---:|---:|---:|---:|---:|---:|:---|")
    for tier, n, pt, lo95, hi95, lo80, hi80, p_pos, p_neg, v in rows:
        L.append(f"| {tier} | {n} | {pt:+.4f} | [{lo95:+.4f},{hi95:+.4f}] | "
                 f"[{lo80:+.4f},{hi80:+.4f}] | {p_pos:.3f} | {p_neg:.3f} | {v} |")
    L.append("")
    L.append("## 2. 解读（先于程序正确性）")
    L.append("")
    L.append("- **逐 tier 样本薄**（每 tier 仅数十笔），单 tier 通常难达 95% 显著；重点看**方向结构**："
             "哪些 tier 的 Δν 点估偏正（倾向更优）、哪些偏负（拖累整体）。")
    L.append("- 若存在'部分 tier 明显偏正、其余中性/偏负'的结构，则 H_vol 轴**并非整体无效**，而是"
             "'部分 tier 的持仓时长调整有效、但不足以逆转整体'——此时可考虑'仅在有效 tier 上分化持仓'的定向方案。")
    L.append("- 若所有 tier 均偏负或中性，则 H_vol 轴确为弱轴，维持统一 8/10h 是整体最优。")
    L.append("- 与 P2 workbench §6 预言对照：前载阵营（S_seg34 / L_seg3）偏好缩短(≈0.6×)、L_seg12 偏好拉长；"
             "若前载 tier 偏正而后载偏负，则与'前载信息衰减快、宜缩短'的机理一致。")
    L.append("")
    L.append("> 局限：逐 tier 拆分后样本更小，结论以'方向结构'为主、显著性为辅；"
             "要精确定向方案仍需更大样本或跨期复验。")
    L.append("")

    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
