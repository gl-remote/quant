#!/usr/bin/env python3
"""
va-composite · P6b · K_SL(tier/方向) 止损倍数正式扫描

位置: scripts/ai_tmp/va_p06b_k_sl_scan.py
主题: docs/research/themes/va-asymmetry-composite/

spec 定义（§0.1 / §3.2 / P6 候选）:
  - 多域 K_L ∈ {0.7, 1.0, 1.3}（各 ±30%）
  - 空域 K_S ∈ {1.75, 2.5, 3.25}（各 ±30%）
  - B0 基线 = (K_L=1.0, K_S=2.5)

设计:
  - 在**冻结 A 轨(=生产 B0 真相) + Cap=4.0** 上复用 P6/H_vol 框架，把"持仓时长网格"替换为
    "止损倍数网格"，单一变量隔离 K_SL。
  - P1 引擎里 K_L_SL/K_S_SL 是 per-direction 全局（va_composite_p1_cap.py L81-82,125-126），
    恰好等价于 spec 的 per-tier 退化设定（同方向所有 tier 取同 K）。monkey-patch 即可参数化，
    **不改动冻结引擎**。
  - K_SL 不改变事件集/分类/持仓时长 H，只改变：(1) 单笔名义仓位 notional_frac = RiskPerTrade/(K·ATR)
    （即 K 大→仓位小）；(2) 止损触发距离（K 大→止损更远→更少触发止损、更多单走 TIME 退出）。
    注意：单笔止损损失恒 = RiskPerTrade×Equity（2%），与 K 无关；K 的实质影响是"赔率结构/止损频率"。
  - 配对 vs B0 用 P1.paired_delta（单向门 ΔSh≥0.2 且 P(μ_true>0)≥0.95）；
    最优过门候选的 OOS 对称头对头复用 va_p03b_ab_headtohead.paired_dist/verdict（簇自助，双侧 CI）。

运行: uv run python scripts/ai_tmp/va_p06b_k_sl_scan.py
输出: project_data/ai_tmp/p6b_k_sl/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402
from va_p03b_ab_headtohead import paired_dist, verdict  # noqa: E402  # 复用对称簇自助

CAP = 4.0
N_FOLDS = 4
K_L_GRID = [0.7, 1.0, 1.3]
K_S_GRID = [1.75, 2.5, 3.25]
B0 = (1.0, 2.5)
N_BOOT = 4000
OUT = Path("project_data/ai_tmp/p6b_k_sl")
OUT.mkdir(parents=True, exist_ok=True)


def sim_all(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    return pd.DataFrame(rows)


def sim_with_k(kl: float, ks: float, evA: pd.DataFrame) -> pd.DataFrame:
    P1.K_L_SL, P1.K_S_SL = kl, ks
    raw = sim_all(evA)
    t = P1.compress(raw, CAP)
    t = P1.assign_equity(t)
    return t


def metric_block(name: str, t: pd.DataFrame, ad) -> dict:
    m = P1.base_metrics(t, active_days=ad)
    m["monthly_win"] = P1.monthly_win_rate(t)
    m["ir"] = P1.per_trade_ir(t)
    m["nu"], m["p"] = P1.nu_implied(t)
    m["name"] = name
    m["n"] = len(t)
    m["sl_frac"] = float((t["exit_reason"] == "SL").mean())
    m["time_frac"] = float((t["exit_reason"] == "TIME").mean())
    return m


def metrics_row(m: dict) -> str:
    return (f"| {m['name']} | {m['ann_ret']*100:6.2f}% | {m['sharpe']:5.2f} | "
            f"{m['max_dd']*100:6.2f}% | {m['monthly_win']*100:5.1f}% | "
            f"{m['ir']:5.3f} | {m['nu']:+.3f} | {m['p']:.3f} | "
            f"{m['sl_frac']*100:4.1f}% | {m['time_frac']*100:4.1f}% | {m['n']} |")


def main() -> None:
    print("=" * 78)
    print("va-composite · P6b · K_SL 止损倍数扫描  [冻结A轨=B0 · Cap=4.0 · 复用P6框架]")
    print(f"  K_L∈{K_L_GRID} × K_S∈{K_S_GRID} (共 {len(K_L_GRID)*len(K_S_GRID)} 组合) · "
          f"B0基线=({B0[0]},{B0[1]})")
    print("=" * 78)

    print("[1/4] 加载冻结 A 轨事件(=生产 B0)...")
    tl = pd.read_parquet(P1.TIMELINE_PATH)
    ad = P1.active_day_set(tl, "signed_skew_rank_roll")
    evA = P1.load_events()
    print(f"      A 事件 {len(evA)} | 合约 {evA['contract'].nunique()} | "
          f"多 {(evA['direction']=='long').sum()} / 空 {(evA['direction']=='short').sum()}")

    # OOS 切分点（与 P3 walk-forward 一致：后 50% 时间外持有期）
    times = np.sort(evA["event_time"].values)
    qs = [pd.Timestamp(t) for t in np.quantile(times, np.linspace(0, 1, N_FOLDS + 1))]
    split = qs[N_FOLDS // 2]
    print(f"      OOS 切点 = {split.date()}（后50% 时间外持有期）")

    print("\n[2/4] 扫 K_SL 网格（monkey-patch P1.K_L_SL/K_S_SL）...")
    blocks = {}
    for kl in K_L_GRID:
        for ks in K_S_GRID:
            t = sim_with_k(kl, ks, evA)
            blocks[(kl, ks)] = metric_block(f"K_L={kl}/K_S={ks}", t, ad)
            print("      " + metrics_row(blocks[(kl, ks)]).strip())

    # B0 基线块
    b0_t = sim_with_k(*B0, evA)
    b0_block = metric_block("B0(1.0/2.5)", b0_t, ad)

    print("\n[3/4] 配对增量 vs B0（单向门 ΔSh≥0.2 且 P(μ_true>0)≥0.95）...")
    pair_rows = []
    for (kl, ks), blk in blocks.items():
        t = sim_with_k(kl, ks, evA)  # 重跑以得 trades（上面 blk 只存指标；为省内存重跑，慢但稳）
        d = P1.paired_delta(b0_t, t)
        adopted = (d["dsharpe"] >= 0.2) and (d["p_nu_pos"] >= 0.95)
        pair_rows.append(((kl, ks), d, adopted))
        print(f"      K_L={kl}/K_S={ks}: ΔSh={d['dsharpe']:+.2f} μ_true={d['nu_true']*100:+.3f}% "
              f"P(μ_true>0)={d['p_nu_pos']:.3f} => {'过门 ✅' if adopted else '未过门 ❌'}")

    # 过门候选中夏普最高者 → 最优
    adopted = [(k, d) for (k, d, a) in pair_rows if a]
    if adopted:
        best_k = max(adopted, key=lambda kd: blocks[kd[0]]["sharpe"])[0]
    else:
        best_k = None

    print("\n[4/4] 最优候选 OOS 对称头对头 + 写 summary...")
    best_oos = None
    if best_k is not None:
        b0_oos = b0_t[b0_t["_entry_date"] >= split.date()]
        # 重跑最优候选 trades
        cb_t = sim_with_k(*best_k, evA)
        cb_oos = cb_t[cb_t["_entry_date"] >= split.date()]
        nus, shs, _, _ = paired_dist(b0_oos, cb_oos, 23)
        rv = verdict(nus, "Δν(候选−B0)")
        rs = verdict(shs, "ΔSh(候选−B0)")
        best_oos = (best_k, rv, rs)
        print(f"      最优 K_L={best_k[0]}/K_S={best_k[1]} OOS 对称: "
              f"Δν 点估 {rv['pt']:+.4f} 95%CI[{rv['lo95']:+.4f},{rv['hi95']:+.4f}] "
              f"P(候选>B0)={rv['p_pos']:.3f} Verdict={rv['verdict']}")
    else:
        print("      无候选过门 → 不做 OOS 对称（§3 先验：局部轴 0/N，B0 近最优）")

    # ---------------- 写 summary ----------------
    L = []
    L.append("# va-asymmetry-composite · P6b · K_SL(tier) 止损倍数扫描报告")
    L.append("")
    L.append(f"> 日期 2026-07-11 · 冻结 A 轨(=生产 B0 真相) + Cap={CAP} · 复用 P6/H_vol 框架")
    L.append("> 网格: 多域 K_L∈{0.7,1.0,1.3} × 空域 K_S∈{1.75,2.5,3.25}（spec §0.1/§3.2 各 ±30%）"
             "· B0基线=(1.0,2.5)")
    L.append("> 方法: monkey-patch P1.K_L_SL/K_S_SL（引擎 per-direction 全局，等价 spec per-tier 退化设定："
             "同方向所有 tier 取同 K），不改动冻结引擎。单一变量隔离 K_SL。")
    L.append("> K_SL 实质影响: 单笔止损损失恒=RiskPerTrade×Equity(2%)（与 K 无关）；K 只改赔率结构——"
             "K 大→止损更远→更少触发 SL、更多走 TIME 退出、单笔仓位更小。")
    L.append("> 门禁(spec §0.2): 候选 vs B0 配对须 **ΔSharpe≥0.2 且 P(μ_true>0)≥0.95** 同时成立方采用。")
    L.append("")
    L.append("## 1. 主指标（冻结A轨 · Cap=4.0 · 新·可交易日口径）")
    L.append("")
    L.append("| K 组合 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) | SL占比 | TIME占比 | 笔数 |")
    L.append("|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    L.append(metrics_row(b0_block))
    for (kl, ks), blk in blocks.items():
        L.append(metrics_row(blk))
    L.append("")
    L.append("## 2. 配对增量（候选 − B0，单向门 §0.1）")
    L.append("")
    L.append("| K_L | K_S | ΔSharpe | μ_true | P(μ_true>0) | 门禁 |")
    L.append("|:---:|:---:|---:|---:|---:|:---:|")
    for (kl, ks), d, a in pair_rows:
        L.append(f"| {kl} | {ks} | {d['dsharpe']:+.2f} | {d['nu_true']*100:+.3f}% | "
                 f"{d['p_nu_pos']:.3f} | {'过门 ✅' if a else '未过门 ❌'} |")
    L.append("")
    if best_oos is not None:
        (best_k, rv, rs) = best_oos
        L.append("## 3. 最优过门候选 OOS 对称头对头（后50% 时间外 · 簇自助 4000）")
        L.append("")
        L.append(f"- 最优组合: **K_L={best_k[0]} / K_S={best_k[1]}**")
        L.append(f"- Δν(候选−B0): 点估 {rv['pt']:+.4f} | 95%CI[{rv['lo95']:+.4f},{rv['hi95']:+.4f}] | "
                 f"80%CI[{rv['lo80']:+.4f},{rv['lo80'] and rv['hi80']:+.4f}] | "
                 f"P(候选>B0)={rv['p_pos']:.3f} | 双侧p={rv['p_two']:.3f}")
        L.append(f"- ΔSh(候选−B0): 点估 {rs['pt']:+.3f} | 95%CI[{rs['lo95']:+.3f},{rs['hi95']:+.3f}] | "
                 f"Verdict: {rs['verdict']}")
        L.append(f"- OOS Verdict(95%): {rv['verdict']}")
        L.append("")
    else:
        L.append("## 3. 最优候选 OOS 对称头对头")
        L.append("")
        L.append("- **无候选过门**（所有 K 组合均未同时满足 ΔSh≥0.2 且 P≥0.95）→ 跳过 OOS 对称，"
                 "结论见 §4。")
        L.append("")
    L.append("## 4. 结论与处置（领先于程序正确性）")
    L.append("")
    n_pass = len(adopted)
    if n_pass == 0:
        L.append("- **0/N 过门**：所有 9 个 K_SL 组合相对 B0 均未达采用门禁 → 符合计划 §3 先验"
                 "「局部塑形/风控轴普遍 0/N，B0 已近该维度最优」。**K_SL 维持描述性灵敏度，"
                 "不升格为主调节**（spec §12 原定位）。")
        L.append("- 机制解读：K_SL 仅改赔率结构（单笔止损损失恒 2%），不改变事件集/edge；"
                 "扫描未挖出显著增量，说明当前 (1.0/2.5) 已落在该维度稳健区，无需调。")
    else:
        L.append(f"- **{n_pass}/9 过门**：存在过门候选，最优=K_L={best_k[0]}/K_S={best_k[1]}；"
                 "已做 OOS 对称头对头（见 §3）确认方向。")
        L.append("- 若 OOS 对称仍 95% 不可区分（CI 含 0），则即便 in-sample 过门，也属风险偏好决策，"
                 "非数据强制升格。")
    L.append("- 与 P6 H_vol 对照：H_vol OOS 转负(ΔSh=−1.10/P=0.161)已证伪；K_SL 作为另一风控旋钮，"
             "本扫描评估其是否同样为 0/N。两者均落「局部风控轴增量小」区间，则 B0 在该维度锁定合理。")
    L.append("")
    L.append("> 局限：本扫描在冻结 A 轨（=生产 B0）上进行；K_SL 是独立于归一化的风控层，"
             "B 轨(默认候选)归一化只改事件集、不改 K_SL 机制，结论定性平移。若需在 B 轨复验可后续补。")
    L.append("")

    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n      写出: {OUT / 'summary.md'}")
    print("\nP6b K_SL 扫描终判:")
    if n_pass == 0:
        print("  0/N 过门 → K_SL 维持描述性灵敏度，B0(1.0/2.5) 近最优")
    else:
        print(f"  {n_pass}/9 过门 → 最优 K_L={best_k[0]}/K_S={best_k[1]}"
              f"（OOS Verdict: {best_oos[1]['verdict'] if best_oos else '—'}）")


if __name__ == "__main__":
    main()
