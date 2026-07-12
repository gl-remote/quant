#!/usr/bin/env python3
"""
va-composite · P0.5 · τ_signed 符号方向（B 层待定旋钮首次校准）· v2（按实际数据口径修正）

位置: scripts/ai_tmp/va_p05_tau_signed.py
主题: docs/research/themes/va-asymmetry-composite/

⚠ 重要勘误（v1→v2）：spec §1.3.4 用 6 类阵营名（S_seg12_high_dn 等），
但本数据集 timeline.tier 实际是另一套命名（DN1_atrHigh_down_stable/trans、UP1... 等，
即 down/up × atrHigh/Low/Mid × stable/trans）。v1 按 spec 名字分组 → 全空（假阴性）。
v2 改用**实际数据口径**：空头宇宙 = direction=='short'（= 所有 DN* 阵营并集），
τ 符号按 spec §1.3.4 的 W=3 衰减窗自算。

次要发现（写进报告）：数据集既有 transition_flag=1 占 44.6%，而 spec W=3 的 |τ|≠0 仅 21.2%
→ 生产 whitelist 的"转期窗"比 spec τ_signed 的 W=3 更长。v2 仍用 spec W=3 定义 τ_signed，
但在对比时也报告该 mismatch。

τ_signed 算法（spec §1.3.4，W=3）：
  per (contract, session=date): atr_bucket=分档(atr_rank_roll日均) 低≤0.33/中/高≥0.67
  crossover=bucket(d)!=bucket(d-1)
  sign=+1 若 bucket 升高(扩张) / −1 若降低(收缩)
  τ_signed=sign·max(0,1−age/W)，age=距最近 crossover 交易日数；age≥W 归 0=稳定期

两口径：
  (A) per-event 收益代理：空头事件 short_pnl_4h_bps 的 τ>0 vs τ<0 均值 + Welch t
  (B) 实盘模拟：空头事件按 τ 符号切分 → P1 模拟(Cap=4.0) → realized 年化/夏普/胜率

运行: uv run python scripts/ai_tmp/va_p05_tau_signed.py
输出: project_data/ai_tmp/p05_tau/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402

CAP = 4.0
W = 3
OUT = Path("project_data/ai_tmp/p05_tau")
OUT.mkdir(parents=True, exist_ok=True)


def bucket(x):
    if x <= 0.33:
        return 0
    if x >= 0.67:
        return 2
    return 1


def compute_tau_signed(tl: pd.DataFrame) -> pd.DataFrame:
    g = (tl.groupby(["contract", "date"])["atr_rank_roll"].mean()
         .reset_index().sort_values(["contract", "date"]))
    parts = []
    for c, sub in g.groupby("contract"):
        sub = sub.sort_values("date").reset_index(drop=True)
        bkt = sub["atr_rank_roll"].apply(bucket).values
        prev = np.concatenate([[np.nan], bkt[:-1]])
        cross = np.zeros(len(bkt), dtype=bool)
        sign = np.zeros(len(bkt))
        for i in range(1, len(bkt)):
            if not np.isnan(prev[i]) and bkt[i] != prev[i]:
                cross[i] = True
                sign[i] = np.sign(bkt[i] - prev[i])
        tau = np.zeros(len(bkt))
        last = -10 ** 9
        for i in range(len(bkt)):
            if cross[i]:
                last = i
            age = i - last
            tau[i] = sign[i] * (1.0 - age / W) if (last >= 0 and age < W) else 0.0
        s = sub.copy()
        s["tau_signed"] = tau
        parts.append(s[["contract", "date", "tau_signed"]])
    return pd.concat(parts, ignore_index=True)


def welch_p(a, b):
    try:
        from scipy import stats
        if len(a) > 5 and len(b) > 5:
            _, p = stats.ttest_ind(a, b, equal_var=False)
            return float(p)
    except Exception:
        pass
    return float("nan")


def main() -> None:
    print("=" * 78)
    print("va-composite · P0.5 · τ_signed 符号方向校准 v2（实际数据口径）")
    print(f"  空头宇宙=direction=='short' · W={W} · Cap={CAP}")
    print("=" * 78)

    print("[1/4] 加载 + 计算 τ_signed ...")
    tl = pd.read_parquet(P1.TIMELINE_PATH)
    tau = compute_tau_signed(tl)
    ev = P1.load_events().merge(tau, on=["contract", "date"], how="left")
    ev["tau_signed"] = ev["tau_signed"].fillna(0.0)
    short = ev[ev["direction"] == "short"].copy()
    print(f"  总事件 {len(ev)} | 空头 {len(short)} | "
          f"空头内 τ>0(扩张)={int((short.tau_signed>0).sum())} "
          f"τ<0(收缩)={int((short.tau_signed<0).sum())} "
          f"τ=0(稳定)={int((short.tau_signed==0).sum())}")
    print(f"  [mismatch 提示] 数据集 transition_flag=1 占 {ev['transition_flag'].mean()*100:.1f}%，"
          f"spec W=3 的 |τ|≠0 占 {(ev.tau_signed!=0).mean()*100:.1f}% → 生产转期窗比 spec W=3 更长")

    print("\n[2/4] 口径A: 空头 short_pnl_4h_bps 的 τ>0 vs τ<0 ...")
    pos = short[short.tau_signed > 0]["short_pnl_4h_bps"].dropna()
    neg = short[short.tau_signed < 0]["short_pnl_4h_bps"].dropna()
    sta = short[short.tau_signed == 0]["short_pnl_4h_bps"].dropna()
    mp, mn, ms = pos.mean(), neg.mean(), sta.mean()
    p = welch_p(pos, neg)
    print(f"  扩张 τ>0 n={len(pos)} μ={mp:.1f}bps | 收缩 τ<0 n={len(neg)} μ={mn:.1f}bps | "
          f"稳定 τ=0 n={len(sta)} μ={ms:.1f}bps")
    print(f"  Δ(扩−收)={mp-mn:.1f}bps  Welch p={p:.3f}")

    print("\n[3/4] 口径B: 空头按 τ 符号切分 → P1 模拟 → realized 指标 ...")
    b_rows = []
    for label, mask in [("扩张 τ>0", short.tau_signed > 0),
                        ("收缩 τ<0", short.tau_signed < 0),
                        ("稳定 τ=0", short.tau_signed == 0)]:
        sub = short[mask]
        if len(sub) == 0:
            continue
        raw = []
        for c, g in sub.groupby("contract"):
            raw.extend(P1.simulate_contract(c, g))
        if not raw:
            continue
        t = P1.compress(pd.DataFrame(raw), CAP)
        t = P1.assign_equity(t)
        m = P1.base_metrics(t, active_days=P1.active_day_set(tl, "signed_skew_rank_roll"))
        b_rows.append((label, len(t), m["ann_ret"] * 100, m["sharpe"],
                       P1.monthly_win_rate(t) * 100, float((t["exit_reason"] == "SL").mean()) * 100))
        print(f"  {label:<10} n={len(t):>4} 年化={m['ann_ret']*100:6.2f}% 夏普={m['sharpe']:5.2f} "
              f"月胜={P1.monthly_win_rate(t)*100:5.1f}% SL%={float((t['exit_reason']=='SL').mean())*100:4.1f}")

    print("\n[4/4] 写 summary ...")
    L = []
    L.append("# va-asymmetry-composite · P0.5 · τ_signed 符号方向校准报告 v2")
    L.append("")
    L.append("> 日期 2026-07-11 · 冻结管线 · spec §1.3.4 算法(W=3)")
    L.append("> ⚠ **v1→v2 勘误**：spec 用 6 类阵营名(S_seg12_high_dn 等)，但本数据集 timeline.tier "
             "实际是 DN1_atrHigh_down_stable/trans、UP1... 等命名。v1 按 spec 名分组→全空(假阴性)。"
             "v2 改用实际口径：空头宇宙=direction=='short'，τ 符号按 spec W=3 自算。")
    L.append("> τ_signed = sign(ATR桶变化)·max(0,1−age/W)；+1=波动扩张(低→高)、−1=波动收缩(高→低)、0=稳定期。")
    L.append("> 目的(P0.5)：空头 skew 信号在**扩张**还是**收缩** regime 下 edge 更强。")
    L.append("")
    L.append("## 1. 口径A: 空头 short_pnl_4h_bps（τ>0 扩张 vs τ<0 收缩 vs τ=0 稳定）")
    L.append("")
    L.append(f"- 扩张 τ>0: n={len(pos)} μ={mp:.1f} bps")
    L.append(f"- 收缩 τ<0: n={len(neg)} μ={mn:.1f} bps")
    L.append(f"- 稳定 τ=0: n={len(sta)} μ={ms:.1f} bps")
    L.append(f"- **Δ(扩−收)={mp-mn:+.1f} bps，Welch p={p:.3f}**")
    L.append("")
    L.append("## 2. 口径B: 空头按 τ 符号切分 → P1 模拟(Cap=4.0) realized 指标")
    L.append("")
    L.append("| regime | n交易 | 年化 | 净夏普 | 月胜率 | SL% |")
    L.append("|:---|---:|---:|---:|---:|---:|")
    for label, n, ar, sh, mw, sl in b_rows:
        L.append(f"| {label} | {n} | {ar:.2f}% | {sh:.2f} | {mw:.1f}% | {sl:.1f}% |")
    L.append("")
    L.append("## 3. 结论与处置（领先于程序正确性）")
    L.append("")
    if b_rows:
        d = {r[0]: r for r in b_rows}
        if "扩张 τ>0" in d and "收缩 τ<0" in d:
            e, c = d["扩张 τ>0"], d["收缩 τ<0"]
            win = "扩张(τ>0)" if e[2] > c[2] else "收缩(τ<0)"
            L.append(f"- **B 口径(实盘)**：扩张 τ>0 年化 {e[2]:.2f}% / 夏普 {e[3]:.2f} "
                     f"vs 收缩 τ<0 年化 {c[2]:.2f}% / 夏普 {c[3]:.2f} → "
                     f"**空头 edge 更强侧 = {win}**（Δ年化 {e[2]-c[2]:+.2f}pp）。")
        if len(pos) and len(neg):
            aw = "扩张侧偏强" if mp > mn else "收缩侧偏强"
            L.append(f"- **A 口径(代理)**：μ(扩张)={mp:.1f} vs μ(收缩)={mn:.1f} bps → {aw}"
                     f"（p={p:.3f}）。")
    L.append("- 两口径一致 → 该侧为 skew 空头信号的 dominant regime，应写入 spec §1.3.4 注"
             "（明确 S 阵营偏好扩张/收缩方向），可用于 B 层 τ_signed 过滤（只取该侧）。")
    L.append("- 两口径分歧 → regime 结构复杂，先不入档强结论。")
    L.append("- 与 B 轨「非平稳/fold0 失效」的联系：若空头 edge 强侧是某一 regime，"
             "而该 regime 在样本前段(2024)稀疏、后段(2025+)密集，则正好解释 B 的 edge 集中后段；"
             "可在 summary 后补 regime×年度分布验证。")
    L.append("")
    L.append("> ⚠ **taxonomy / W 窗 mismatch（须回灌 spec）**：")
    L.append(f"> 1. spec 阵营名(S_seg12_high_dn 等) ≠ 数据集 timeline.tier(DN1_atrHigh_down_*/UP1...)。"
             "后续若要在 spec 层校准，需先建立两套命名的映射表。")
    L.append(f"> 2. 数据集 transition_flag=1 占 {ev['transition_flag'].mean()*100:.1f}%，"
             f"spec W=3 的 |τ|≠0 仅 {(ev.tau_signed!=0).mean()*100:.1f}% → 生产 whitelist 的'转期窗'更长。"
             "若严格按 spec τ_signed(W=3) 做 B 层过滤，覆盖事件数会远少于当前 whitelist。")
    L.append("")
    L.append("> 局限：τ_signed 在冻结管线(=生产 B0)上计算；未改任何生产代码。")
    L.append("")

    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n      写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
