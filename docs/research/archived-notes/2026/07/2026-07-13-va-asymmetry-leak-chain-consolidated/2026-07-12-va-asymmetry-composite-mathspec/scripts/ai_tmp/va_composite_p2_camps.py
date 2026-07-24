#!/usr/bin/env python3
"""按阵营(tier_v40)拆分分析：
(1) 每阵营是否成立：n / 胜率 / 均值bps / 单笔IR
(2) 每阵营最优入场缓冲区：延迟 0/5/15/30/45/60min（同日历退出）
(3) 每阵营最优持仓时长：2/4/6/8/10/12h（delay=0）
统一模拟器：simulate(delay_bars, hold_bars) 入场 idx+delay，持有 hold_bars 根5m，SL 重锚。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1

DELAYS = [(0, 0), (5, 1), (15, 3), (30, 6), (45, 9), (60, 12)]
HOLDS_H = [2, 4, 6, 8, 10, 12]


def simulate(contract, g, delay_bars, hold_bars, bars_cache):
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    cp = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not cp.exists():
        return []
    if contract not in bars_cache:
        b = pd.read_csv(cp, usecols=["datetime", "high", "low", "close"])
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.sort_values("datetime").reset_index(drop=True)
        bars_cache[contract] = b if not b.empty else None
    bars = bars_cache[contract]
    if bars is None:
        return []
    out = []
    for _, ev in g.iterrows():
        d = ev["direction"]; sign = 1 if d == "long" else -1
        K = P1.K_L_SL if d == "long" else P1.K_S_SL
        atr = float(ev["entry_atr_bps"])
        if atr <= 0:
            continue
        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        eidx = idx + delay_bars
        if eidx >= len(bars):
            continue
        if hold_bars <= 0:
            continue
        ep = float(bars.iloc[eidx]["close"])
        if ep <= 0:
            continue
        sp = ep - sign * K * ep * atr / 10000.0
        notional_frac = P1.RISK_PER_TRADE / (K * atr / 10000.0)
        qty = notional_frac * P1.EQUITY_INIT / (ep * spec.size)
        future = bars.iloc[eidx: eidx + hold_bars]
        if len(future) == 0:
            continue
        xp = np.nan; reason = "TIME"; exit_dt = None
        for _, fb in future.iterrows():
            if sign == 1 and fb["low"] <= sp:
                xp = sp; reason = "SL"; exit_dt = fb["datetime"]; break
            if sign == -1 and fb["high"] >= sp:
                xp = sp; reason = "SL"; exit_dt = fb["datetime"]; break
        if np.isnan(xp):
            xp = float(future.iloc[-1]["close"]); exit_dt = future.iloc[-1]["datetime"]
        ce = P1.cost_oneway_bps(spec, ep, qty); cx = P1.cost_oneway_bps(spec, xp, qty)
        pnl = sign * (xp - ep) / ep * 10000.0 - ce - cx
        out.append({"contract": contract, "direction": int(sign), "tier": ev["tier_v40"],
                    "pnl_net_bps": pnl, "exit_reason": reason,
                    "entry_bar": bars.iloc[eidx]["datetime"], "exit_bar": exit_dt,
                    "symbol": (P1.extract_contract_prefix(contract) or "").lower(),
                    "_notional_frac": notional_frac, "_entry_date": pd.Timestamp(bars.iloc[eidx]["datetime"]).date(),
                    "_exit_date": pd.Timestamp(exit_dt).date(),
                    "qty_raw": qty, "pnl_net_ccy": pnl / 10000.0 * notional_frac * P1.EQUITY_INIT})
    return out


def stats(rows):
    if not rows:
        return (0, 0.0, 0.0, 0.0)
    t = pd.DataFrame(rows)
    n = len(t)
    win = (t["pnl_net_bps"] > 0).mean() * 100
    mean = t["pnl_net_bps"].mean()
    ir = P1.per_trade_ir(t)
    return (n, win, mean, ir)


def main():
    events = P1.load_events()
    camps = events["tier_v40"].value_counts()
    print("=" * 78)
    print("按阵营拆分分析 (Cap 隔离，同批事件，全局缓存)")
    print("=" * 78)
    print("\n阵营分布:")
    for c, n in camps.items():
        sub = events[events["tier_v40"] == c]
        print(f"  {c:>22} | n={n:>3} | 方向={sub['direction'].iloc[0]}")

    GLOBAL = {}  # 合约CSV全局只读一次

    for camp, n0 in camps.items():
        sub = events[events["tier_v40"] == camp]
        direction = sub["direction"].iloc[0]
        tot_bars = (P1.H_L if direction == "long" else P1.H_S) * 12
        print("\n" + "#" * 78)
        print(f"# 阵营 {camp}  (方向={direction}, n={n0})")
        print("#" * 78)

        # (1) baseline
        rows = []
        for c, g in sub.groupby("contract"):
            rows.extend(simulate(c, g, 0, tot_bars, GLOBAL))
        n, win, mean, ir = stats(rows)
        print(f"\n[1] 基线(delay=0, hold={tot_bars//12}h): n={n} 胜率={win:.1f}% 均值={mean:.2f}bps IR={ir:.3f}")

        # (2) 入场缓冲区扫描
        print(f"\n[2] 入场延迟扫描 (同日历退出, hold={tot_bars//12}h):")
        print(f"     {'延迟':>6} | {'n':>4} | {'胜率':>6} | {'均值bps':>9} | {'IR':>6}")
        best_d, best_d_ir = 0, -9
        for dmin, d in DELAYS:
            rows = []
            for c, g in sub.groupby("contract"):
                rows.extend(simulate(c, g, d, tot_bars - d, GLOBAL))
            nn, w, m, ir = stats(rows)
            mark = " *" if ir > best_d_ir else ""
            if ir > best_d_ir:
                best_d, best_d_ir = dmin, ir
            print(f"     {dmin:>4}min | {nn:>4} | {w:>5.1f}% | {m:>9.2f} | {ir:>6.3f}{mark}")
        print(f"     => 最优入场缓冲: {best_d}min (IR={best_d_ir:.3f})")

        # (3) 持仓时长扫描
        print(f"\n[3] 持仓时长扫描 (delay=0):")
        print(f"     {'时长':>6} | {'n':>4} | {'胜率':>6} | {'均值bps':>9} | {'IR':>6}")
        best_h, best_h_ir = tot_bars // 12, -9
        for h in HOLDS_H:
            rows = []
            for c, g in sub.groupby("contract"):
                rows.extend(simulate(c, g, 0, h * 12, GLOBAL))
            nn, w, m, ir = stats(rows)
            mark = " *" if ir > best_h_ir else ""
            if ir > best_h_ir:
                best_h, best_h_ir = h, ir
            print(f"     {h:>4}h | {nn:>4} | {w:>5.1f}% | {m:>9.2f} | {ir:>6.3f}{mark}")
        print(f"     => 最优持仓时长: {best_h}h (IR={best_h_ir:.3f}, 当前B0={tot_bars//12}h)")


if __name__ == "__main__":
    main()
