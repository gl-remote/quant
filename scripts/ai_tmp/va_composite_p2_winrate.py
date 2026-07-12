#!/usr/bin/env python3
"""Phase 2 胜率诊断：各 mode 触发子集的胜率/单笔均值 vs baseline 全样本。"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1
import va_composite_p2_entry_mode as P2

MODES = ["baseline", "boll", "macd", "kdj", "rsi", "breakout", "prevhi", "openrange"]


def per_event(contract, g, mode, bc):
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    cp = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not cp.exists():
        return []
    if contract not in bc:
        b = pd.read_csv(cp, usecols=["datetime", "high", "low", "close"])
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.sort_values("datetime").reset_index(drop=True)
        bc[contract] = P2.add_indicators(b) if not b.empty else None
    bars = bc[contract]
    if bars is None:
        return []
    trig = P2.build_trigger(bars, mode)
    out = []
    for _, ev in g.iterrows():
        d = ev["direction"]; sign = 1 if d == "long" else -1
        K = P1.K_L_SL if d == "long" else P1.K_S_SL
        H = P1.H_L if d == "long" else P1.H_S
        atr = float(ev["entry_atr_bps"])
        if atr <= 0:
            continue
        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        if mode == "baseline":
            ei = idx
        else:
            fut = bars.index[idx: idx + H * 12]
            m = trig[d].loc[fut]
            if not m.any():
                continue
            ei = m.idxmax()
        bar = bars.loc[ei]
        ep = float(bar["close"])
        if ep <= 0:
            continue
        sp = ep - sign * K * ep * atr / 10000.0
        qty = (P1.RISK_PER_TRADE / (K * atr / 10000.0)) * P1.EQUITY_INIT / (ep * spec.size)
        fut = bars.iloc[ei: ei + H * 12]
        if len(fut) == 0:
            continue
        xp = np.nan
        for _, fb in fut.iterrows():
            if sign == 1 and fb["low"] <= sp:
                xp = sp; break
            if sign == -1 and fb["high"] >= sp:
                xp = sp; break
        if np.isnan(xp):
            xp = float(fut.iloc[-1]["close"])
        ce = P1.cost_oneway_bps(spec, ep, qty); cx = P1.cost_oneway_bps(spec, xp, qty)
        pnl = sign * (xp - ep) / ep * 10000.0 - ce - cx
        out.append(pnl)
    return out


def main():
    events = P1.load_events()
    print(f"{'mode':>9} | {'n':>4} | {'胜率%':>7} | {'平均pnl_bps':>12} | {'中位pnl_bps':>12}")
    print("-" * 56)
    for mode in MODES:
        bc = {}
        vals = []
        for c, g in events.groupby("contract"):
            vals.extend(per_event(c, g, mode, bc))
        a = np.array(vals)
        wr = (a > 0).mean() * 100
        print(f"{mode:>9} | {len(a):>4} | {wr:>7.1f} | {a.mean():>12.1f} | {np.median(a):>12.1f}")


if __name__ == "__main__":
    main()
