#!/usr/bin/env python3
"""
va-composite · P3 · B 轨(t-PIT) —— **ν∈{8,12,20} 鲁棒性扫描（对称头对头）**

动机（承接 2026-07-11 决策）：默认已在 80% 单侧门槛下升为 B(t-PIT)，但这是**风险偏好决定**
（原 95% 双侧门未过、fold0 非平稳）。升格前的关键遗留测试之一：B 的 OOS 优势是否**只在 ν=12
这一个自由度上成立**？若 ν=8 / ν=20 就垮，则"默认=B"是**参数脆弱假象**而非真 edge。

本脚本对 ν∈{8,12,20} 各重建一次 B 轨时间线（唯一变量=t-PIT 自由度 ν），A 轨固定（不依赖 ν，
只 build 一次），复用：
  - walk-forward 的因果 t-PIT 构建 / 冻结引擎模拟（va_p03b_b_walkforward，动态设 T_PIT_DF）；
  - 对称头对头的簇自助 paired_dist / verdict（va_p03b_ab_headtohead）。
对每个 ν 报 in-sample 与 OOS(后50%) 的 Δν(B−A)、ΔSh(B−A) 双侧 95%/80% CI 与 P(B>A)，
并按**已采纳的 80% 单侧门槛**（P(B>A)≥0.80 且 ΔSh≥0.2）判每个 ν 是否仍支持 B。

ν=12 一行应复现已知 OOS（P(B>A)≈0.837、ΔSh≈+1.50）作为自校验。

运行: uv run python scripts/ai_tmp/va_p03b_b_nu_scan.py
输出: project_data/ai_tmp/p3b_b_nu_scan/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402
import va_p03b_b_walkforward as WF  # noqa: E402
import va_p03b_ab_headtohead as HH  # noqa: E402

OUT = Path("project_data/ai_tmp/p3b_b_nu_scan")
OUT.mkdir(parents=True, exist_ok=True)

NUS = [8, 12, 20]
CAP = 4.0
N_FOLDS = WF.N_FOLDS

# 80% 单侧门槛（已采纳的 B 升格标准）
GATE_P = 0.80
GATE_DSH = 0.2


def oos_split(evA: pd.DataFrame):
    """与 walk-forward 完全一致的 OOS 切点（基于 A 事件时间分位数，A 不依赖 ν → 固定）。"""
    times = np.sort(evA["event_time"].values)
    qs = [pd.Timestamp(t) for t in np.quantile(times, np.linspace(0, 1, N_FOLDS + 1))]
    return qs[N_FOLDS // 2], qs


def build_track(cap: float, ad):
    """A 轨（固定，不依赖 ν）：返回全样本交易表。"""
    evA = P1.load_events()
    rawA = WF.sim_all(evA)
    tA, _ = WF.eval_trades(rawA, cap, ad)
    return evA, tA


def build_B(nu: int, cap: float, ad):
    """给定 ν 重建 B 轨时间线 → 模拟 → 全样本交易表。"""
    WF.T_PIT_DF = nu   # 动态注入自由度（t_pit_window 读模块级全局）
    b_tl = WF.make_b_timeline(P1.TIMELINE_PATH)
    evB = WF.load_events_from_frame(b_tl)
    rawB = WF.sim_all(evB)
    tB, _ = WF.eval_trades(rawB, cap, ad)
    return evB, tB


def slice_oos(t: pd.DataFrame, split: pd.Timestamp) -> pd.DataFrame:
    return t[t["_entry_date"] >= split.date()]


def run_headtohead(tA: pd.DataFrame, tB: pd.DataFrame, seed: int):
    nus, shs, _, _ = HH.paired_dist(tA, tB, seed)
    return HH.verdict(nus, "Δν(B−A)"), HH.verdict(shs, "ΔSharpe(B−A)")


def gate_pass(rv, rs) -> bool:
    """80% 单侧门：P(B>A)≥0.80 且 ΔSh 点估≥0.2。"""
    return (rv["p_pos"] >= GATE_P) and (rs["pt"] >= GATE_DSH)


def main() -> None:
    print("=" * 80)
    print(f"va-composite · P3 · B(t-PIT) ν 鲁棒扫描  ν∈{NUS} · Cap={CAP} · "
          f"OOS=后50% · 簇自助 N_BOOT={HH.N_BOOT}")
    print("=" * 80)

    tl_src = pd.read_parquet(P1.TIMELINE_PATH)
    ad = P1.active_day_set(tl_src, "signed_skew_rank_roll")

    print("[A] 构建 A 轨（固定，不依赖 ν）...")
    evA, tA = build_track(CAP, ad)
    split, _ = oos_split(evA)
    tA_oos = slice_oos(tA, split)
    print(f"    A 事件 {len(evA)} · 全样本交易 {len(tA)} · OOS 切点 {split.date()} · OOS 交易 {len(tA_oos)}")

    rows_ins, rows_oos = [], []
    for k, nu in enumerate(NUS):
        print(f"\n[ν={nu}] 重建 B 轨 + 模拟 + 对称头对头...")
        evB, tB = build_B(nu, CAP, ad)
        tB_oos = slice_oos(tB, split)

        # in-sample 全样本
        rv_i, rs_i = run_headtohead(tA, tB, seed=100 + k)
        # OOS 后50%
        rv_o, rs_o = run_headtohead(tA_oos, tB_oos, seed=200 + k)

        g_i = gate_pass(rv_i, rs_i)
        g_o = gate_pass(rv_o, rs_o)
        rows_ins.append((nu, rv_i, rs_i, g_i, len(tB)))
        rows_oos.append((nu, rv_o, rs_o, g_o, len(tB_oos)))

        print(f"    B 事件 {len(evB)} · 全样本交易 {len(tB)} · OOS 交易 {len(tB_oos)}")
        print(f"    in-sample: Δν 点估 {rv_i['pt']:+.4f} 95%CI[{rv_i['lo95']:+.4f},{rv_i['hi95']:+.4f}] "
              f"P(B>A)={rv_i['p_pos']:.3f} | ΔSh {rs_i['pt']:+.3f} | 80%门 {'过✅' if g_i else '未过❌'}")
        print(f"    OOS 后50%: Δν 点估 {rv_o['pt']:+.4f} 95%CI[{rv_o['lo95']:+.4f},{rv_o['hi95']:+.4f}] "
              f"80%CI[{rv_o['lo80']:+.4f},{rv_o['hi80']:+.4f}] P(B>A)={rv_o['p_pos']:.3f} | "
              f"ΔSh {rs_o['pt']:+.3f} | 80%门 {'过✅' if g_o else '未过❌'}")

    # ---------- 写 summary ----------
    n_pass_oos = sum(1 for _, _, _, g, _ in rows_oos if g)
    L = []
    L.append("# va-asymmetry-composite · Phase 3 · B(t-PIT) ν∈{8,12,20} 鲁棒性扫描")
    L.append("")
    L.append(f"> 日期 2026-07-11 · Cap={CAP} · OOS=后50%时段 · 簇自助 N_BOOT={HH.N_BOOT} · "
             f"门槛=已采纳的 80% 单侧（P(B>A)≥{GATE_P} 且 ΔSh≥{GATE_DSH}）")
    L.append("> 目的：检验 B 的 OOS 优势是否**仅在 ν=12 成立**。若 ν=8/20 垮 → 参数脆弱假象；"
             "若三值同向且过门 → edge 对自由度鲁棒，巩固'默认=B'。")
    L.append("> A 轨不依赖 ν（固定 build 一次），逐 ν 仅重建 B 轨 t-PIT 时间线（单一变量=ν）。")
    L.append("")
    L.append("## 1. OOS 后50%（核心 · 对称簇自助）")
    L.append("")
    L.append("| ν | B_OOS交易 | Δν(B−A) 点估 | 95%CI | 80%CI | P(B>A) | ΔSh(B−A) | 80%单侧门 |")
    L.append("|:--:|--:|--:|:--|:--|--:|--:|:--:|")
    for nu, rv, rs, g, nb in rows_oos:
        L.append(f"| {nu} | {nb} | {rv['pt']:+.4f} | [{rv['lo95']:+.4f},{rv['hi95']:+.4f}] | "
                 f"[{rv['lo80']:+.4f},{rv['hi80']:+.4f}] | {rv['p_pos']:.3f} | {rs['pt']:+.3f} | "
                 f"{'过 ✅' if g else '未过 ❌'} |")
    L.append("")
    L.append("## 2. in-sample 全样本（参照）")
    L.append("")
    L.append("| ν | B交易 | Δν(B−A) 点估 | 95%CI | P(B>A) | ΔSh(B−A) | 80%单侧门 |")
    L.append("|:--:|--:|--:|:--|--:|--:|:--:|")
    for nu, rv, rs, g, nb in rows_ins:
        L.append(f"| {nu} | {nb} | {rv['pt']:+.4f} | [{rv['lo95']:+.4f},{rv['hi95']:+.4f}] | "
                 f"{rv['p_pos']:.3f} | {rs['pt']:+.3f} | {'过 ✅' if g else '未过 ❌'} |")
    L.append("")
    L.append("## 3. 判读（先于程序正确性）")
    L.append("")
    L.append(f"- **OOS 过 80% 单侧门的 ν 数：{n_pass_oos}/{len(NUS)}**。")
    L.append("- 判读规则：")
    L.append("  - 若 **3/3 同向为正且过门** → B 的 OOS edge **对 ν 鲁棒**，不是 ν=12 挑参，巩固'默认=B'；")
    L.append("  - 若 **仅 ν=12 过、8/20 明显弱或转负** → B 优势**依赖 ν 自由度**（参数脆弱），"
             "应下调对'默认=B'的信心、回退 A/C 或以更保守 ν 复评；")
    L.append("  - 若 **点估方向随 ν 摆动**（有正有负） → 非稳健信号，视同弱轴。")
    L.append("- ν=12 行应与既有 walk-forward/头对头结论一致（OOS P(B>A)≈0.837、ΔSh≈+1.50）作自校验；"
             "若不一致须先排查口径漂移再解读扫描。")
    L.append("")
    L.append("> 局限：三 ν 共用同一事件集/引擎与同一 OOS 切点，仅隔离't-PIT 自由度'一个变量；"
             "跨期/更大样本复验仍是独立的另一道测试。")
    L.append("")

    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n写出: {OUT / 'summary.md'}")
    print(f"\nν 扫描终判: OOS 过 80% 单侧门 {n_pass_oos}/{len(NUS)}  "
          f"→ {'B edge 对 ν 鲁棒 ✅' if n_pass_oos == len(NUS) else 'B edge 存在 ν 依赖，需审视 ⚠'}")


if __name__ == "__main__":
    main()
