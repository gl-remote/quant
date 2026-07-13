#!/usr/bin/env python3
"""组合验证：按阵营最优持仓时长(H_vol per tier) vs B0 统一8h/10h。
注：最优时长取自同批扫描(in-sample上界)，仅用于判断该轴是否值得正式配对验证。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1
from va_composite_p2_camps import simulate

# 取自扫描的每阵营 IR 最大点 (S_seg12 取保守10h避免12h截断)
OPT_H = {
    "S_seg12_high_dn": 10,
    "S_seg2_mid_dn": 8,
    "L_seg3_lowmid_up": 6,
    "S_seg34_high_dn": 6,
    "L_seg12_high_up": 10,
}
CAP = 5.0


def main():
    events = P1.load_events()
    GLOBAL = {}
    # B0 统一
    b0_rows, opt_rows = [], []
    for c, g in events.groupby("contract"):
        for _, ev in g.iterrows():
            direction = ev["direction"]
            tot = (P1.H_L if direction == "long" else P1.H_S) * 12
            b0_rows.extend(simulate(c, g[g["event_time"] == ev["event_time"]], 0, tot, GLOBAL))
            Hopt = OPT_H[ev["tier_v40"]] * 12
            opt_rows.extend(simulate(c, g[g["event_time"] == ev["event_time"]], 0, Hopt, GLOBAL))

    bt = P1.assign_equity(P1.compress(pd.DataFrame(b0_rows), CAP))
    ot = P1.assign_equity(P1.compress(pd.DataFrame(opt_rows), CAP))
    mb = P1.base_metrics(bt); mo = P1.base_metrics(ot)
    print("=" * 64)
    print("按阵营最优持仓时长 组合 vs B0 统一时长 (in-sample上界)")
    print("=" * 64)
    print(f"\n{'':>10} | {'交易数':>5} | {'年化':>7} | {'夏普':>6} | {'MaxDD':>7} | {'月度胜率':>7}")
    print("-" * 56)
    print(f"{'B0统一':>10} | {len(bt):>5} | {mb['ann_ret']*100:6.2f}% | {mb['sharpe']:6.2f} | "
          f"{mb['max_dd']*100:6.2f}% | {P1.monthly_win_rate(bt)*100:6.1f}%")
    print(f"{'按阵营最优':>10} | {len(ot):>5} | {mo['ann_ret']*100:6.2f}% | {mo['sharpe']:6.2f} | "
          f"{mo['max_dd']*100:6.2f}% | {P1.monthly_win_rate(ot)*100:6.1f}%")
    d = P1.paired_delta(bt, ot)
    print(f"\n配对(按阵营最优 vs B0): ΔSharpe={d['dsharpe']:+.2f}  μ_true={d['nu_true']*100:+.2f}%  P(μ>0)={d['p_nu_pos']:.3f}")
    print("\n注：最优时长取自同批数据扫描，属 in-sample 上界；正式采用须走 spec  adoption gate")
    print("（配对 ΔSharpe≥0.2 且 P≥0.95）并建议 walk-forward/分层抽样验证，防过拟合。")


if __name__ == "__main__":
    main()
