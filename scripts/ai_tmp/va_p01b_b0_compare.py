#!/usr/bin/env python3
"""
va-composite · P0.1（干净版）· 三路 B0 轻量对比（仅 Cap=1.0, dedup=8h）

直接回答「skew 去重到底修了什么」：
  F = 冻结 tier              (历史 B0 基线)
  C = 当前分类器+冻结秩       (应 == F，验证可复现)
  M = 当前分类器+去重 skew 秩  (唯一修复)

每路只模拟一次 + Cap=1.0 压仓，输出 B0 主指标 + A 级事件数。
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402

FROZEN = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
CTRL = Path("project_data/ai_tmp/p0_calib/timeline_ctrl.parquet")
MIN = Path("project_data/ai_tmp/p0_calib/timeline_calA_min.parquet")

A_TIER_RAW = {
    "UP2_atrLow_up_stable", "UP3_atrMid_up_stable", "UP1_atrHigh_up_trans",
    "DN1_atrHigh_down_stable", "DN1_atrHigh_down_trans",
    "DN2_atrHigh_down_stable", "DN2_atrHigh_down_trans",
    "DN3_atrHigh_down_stable", "DN3_atrHigh_down_trans",
    "DN4_atrHigh_down_stable", "DN4_atrHigh_down_trans",
    "DN2_atrMid_down_stable", "DN2_atrMid_down_trans",
}


def b0(tl: Path) -> dict:
    P1.TIMELINE_PATH = tl
    P1.DEDUP_HOURS = 8
    events = P1.load_events()
    n_a = len(events)
    rows = []
    for c, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    raw = pd.DataFrame(rows)
    t = P1.assign_equity(P1.compress(raw, 1.0))
    m = P1.base_metrics(t)
    m["monthly_win"] = P1.monthly_win_rate(t)
    m["ir"] = P1.per_trade_ir(t)
    m["nu_implied"], m["p_nu_pos"] = P1.nu_implied(t)
    m["n_a_events"] = n_a
    m["n_trades"] = len(raw)
    m["n_sl"] = int((raw["exit_reason"] == "SL").sum())
    m["n_time"] = int((raw["exit_reason"] == "TIME").sum())
    return m


def main() -> None:
    print("=" * 78)
    print("va-composite · P0.1（干净版）· 三路 B0 对比（Cap=1.0, dedup=8h）")
    print("=" * 78)
    rF, rC, rM = b0(FROZEN), b0(CTRL), b0(MIN)
    print(f"\n{'指标':<16}{'F 冻结':>16}{'C 控制(当前分类器+冻结秩)':>26}{'M 去重skew(修复)':>20}")
    print("-" * 78)
    def row(name, key, pct=False, f=2):
        def fmt(v):
            if pct:
                return f"{v*100:.{f}f}%"
            return f"{v:.{f}f}"
        print(f"{name:<16}{fmt(rF[key]):>16}{fmt(rC[key]):>26}{fmt(rM[key]):>20}")
    row("年化", "ann_ret", True)
    row("净夏普", "sharpe")
    row("MaxDD", "max_dd", True)
    row("月度胜率", "monthly_win", True, 1)
    row("单笔IR", "ir", False, 3)
    row("ν_implied", "nu_implied", False, 3)
    row("P(ν>0)", "p_nu_pos", False, 3)
    row("A级事件数", "n_a_events", False, 0)
    row("交易数", "n_trades", False, 0)
    row("SL/Time", "n_sl", False, 0)  # 占位，下面单独打
    print("-" * 78)
    print(f"SL 次数:  F={rF['n_sl']}  C={rC['n_sl']}  M={rM['n_sl']}")
    print(f"TIME 次数:F={rF['n_time']}  C={rC['n_time']}  M={rM['n_time']}")
    print()
    print("效应分解：")
    print(f"  分类器漂移 (F→C): 年化 {rF['ann_ret']*100:.2f}%→{rC['ann_ret']*100:.2f}%  夏普 {rF['sharpe']:.2f}→{rC['sharpe']:.2f}  "
          f"A事件 {rF['n_a_events']}→{rC['n_a_events']} (应≈0差异，验证可复现)")
    print(f"  skew去重 (C→M): 年化 {rC['ann_ret']*100:.2f}%→{rM['ann_ret']*100:.2f}%  夏普 {rC['sharpe']:.2f}→{rM['sharpe']:.2f}  "
          f"A事件 {rC['n_a_events']}→{rM['n_a_events']} (=纯修复效应)")


if __name__ == "__main__":
    main()
