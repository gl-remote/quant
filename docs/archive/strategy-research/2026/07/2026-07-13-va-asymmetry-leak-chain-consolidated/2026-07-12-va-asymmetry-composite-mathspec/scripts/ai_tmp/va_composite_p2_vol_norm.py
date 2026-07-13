#!/usr/bin/env python3
"""波动率归一化持仓假设检验 (用户领域先验: 波动率大→率先兑现edge→最优时长差异)。

机制检验 (A):
  对每笔算 t* (累积raw pnl峰值分钟) + entry_atr_bps(σ代理)。
  vol_norm = t* * atr_bps  (波动率时间: 日历时长×波动率)。
  逐 tier 对比 t* 与 vol_norm 的 std 与 η²(symbol):
    - 若 vol_norm 的 η² 大幅下降 → 支持「合约聚集是波动率伪影」假设。

策略检验 (B):
  用波动率缩放持仓: 每事件 hold_bars = clip(round(V/atr_bps), 12, 144),
  V 为目标波动率时间(bps·bar)。扫 V, 看组合 IR/夏普 是否优于固定分钟 B0。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from collections import defaultdict

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1

GLOBAL = {}
VS = [1500, 2400, 3200, 4000, 5000, 6000]  # 目标波动率时间候选


def tstar_atr_of(contract, g):
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    cp = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not cp.exists():
        return []
    if contract not in GLOBAL:
        b = pd.read_csv(cp, usecols=["datetime", "high", "low", "close"])
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.sort_values("datetime").reset_index(drop=True)
        GLOBAL[contract] = b if not b.empty else None
    bars = GLOBAL[contract]
    if bars is None:
        return []
    out = []
    for _, ev in g.iterrows():
        d = ev["direction"]; sign = 1 if d == "long" else -1
        total = (P1.H_L if d == "long" else P1.H_S) * 12
        atr = float(ev["entry_atr_bps"])
        if atr <= 0:
            continue
        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        eidx = idx
        if eidx >= len(bars):
            continue
        ep = float(bars.iloc[eidx]["close"])
        if ep <= 0:
            continue
        future = bars.iloc[eidx: eidx + total]
        if len(future) == 0:
            continue
        closes = future["close"].to_numpy(dtype=float)
        raw = sign * (closes - ep) / ep * 10000.0
        k = int(np.argmax(raw))
        out.append({"symbol": (P1.extract_contract_prefix(contract) or "").lower(),
                    "tier": ev["tier_v40"], "tstar": k * 5, "atr": atr})
    return out


def eta_squared(g, col):
    if g["symbol"].nunique() < 2 or len(g) < 5:
        return float("nan")
    grand = g[col].mean()
    ss_total = ((g[col] - grand) ** 2).sum()
    ss_between = sum(len(sg) * (sg[col].mean() - grand) ** 2 for _, sg in g.groupby("symbol"))
    return ss_between / ss_total if ss_total > 0 else float("nan")


def vol_simulate(contract, g, V):
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    cp = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not cp.exists():
        return []
    if contract not in GLOBAL:
        b = pd.read_csv(cp, usecols=["datetime", "high", "low", "close"])
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.sort_values("datetime").reset_index(drop=True)
        GLOBAL[contract] = b if not b.empty else None
    bars = GLOBAL[contract]
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
        eidx = idx
        if eidx >= len(bars):
            continue
        ep = float(bars.iloc[eidx]["close"])
        if ep <= 0:
            continue
        # 波动率归一化持仓长度
        hold_bars = int(np.clip(round(V / atr), 12, 144))
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
        out.append({"tier": ev["tier_v40"], "pnl_net_bps": pnl})
    return out


def stats(rows):
    if not rows:
        return (0, 0.0, 0.0, 0.0)
    t = pd.DataFrame(rows)
    return (len(t), (t["pnl_net_bps"] > 0).mean() * 100,
            t["pnl_net_bps"].mean(), P1.per_trade_ir(t))


def main():
    events = P1.load_events()

    # ===== A: 机制检验 =====
    print("=" * 78)
    print("A. 波动率归一化机制检验: t* vs vol_norm=t*×atr 的集中性/η²")
    print("=" * 78)
    all_rows = []
    for c, g in events.groupby("contract"):
        all_rows.extend(tstar_atr_of(c, g))
    df = pd.DataFrame(all_rows)
    df["vol_norm"] = df["tstar"] * df["atr"]

    blocks = [("ALL", df)] + [(t, df[df["tier"] == t]) for t in df["tier"].unique()]
    for name, sub in blocks:
        if len(sub) < 10:
            continue
        ts, vn = sub["tstar"], sub["vol_norm"]
        e_t = eta_squared(sub, "tstar")
        e_v = eta_squared(sub, "vol_norm")
        flag = "↓显著下降" if (not np.isnan(e_v) and not np.isnan(e_t) and e_v < e_t * 0.6) else ""
        print(f"  {name:>16} | t* std={ts.std():.0f} η²={e_t:.3f} | "
              f"vol_norm std={vn.std():.0f} η²={e_v:.3f}  {flag}")

    # ===== B: 策略检验 =====
    print("\n" + "=" * 78)
    print("B. 波动率归一化持仓 vs 固定分钟 B0 (long 8h=96bars / short 10h=120bars)")
    print("=" * 78)
    # B0 基线 (按方向固定分钟, 每事件仅模拟一次)
    b0 = []
    for c, g in events.groupby("contract"):
        for d in ("long", "short"):
            sub = g[g["direction"] == d]
            if len(sub) == 0:
                continue
            tot = (P1.H_L if d == "long" else P1.H_S) * 12
            b0.extend(vol_simulate_fixed(c, sub, tot))
    n0, w0, m0, ir0 = stats(b0)
    print(f"  B0 固定分钟: n={n0} 胜率={w0:.1f}% 均值={m0:.2f}bps IR={ir0:.3f}")

    print(f"  {'V(波动率时间)':>14} | {'n':>4} | {'胜率':>6} | {'均值bps':>9} | {'IR':>6} | vsB0")
    best_v, best_ir = None, -9
    for V in VS:
        rows = []
        for c, g in events.groupby("contract"):
            rows.extend(vol_simulate(c, g, V))
        n, w, m, ir = stats(rows)
        d = ir - ir0
        mark = " *" if ir > best_ir else ""
        if ir > best_ir:
            best_v, best_ir = V, ir
        print(f"  {V:>14} | {n:>4} | {w:>5.1f}% | {m:>9.2f} | {ir:>6.3f} | ΔIR={d:+.3f}{mark}")
    if best_v is not None:
        print(f"  => 最优波动率时间 V={best_v} (IR={best_ir:.3f} vs B0 {ir0:.3f}, "
              f"Δ={best_ir-ir0:+.3f})")


def vol_simulate_fixed(contract, g, hold_bars):
    """B0 固定分钟基线模拟 (复用 vol_simulate 逻辑但 hold 固定)"""
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    cp = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not cp.exists():
        return []
    if contract not in GLOBAL:
        b = pd.read_csv(cp, usecols=["datetime", "high", "low", "close"])
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.sort_values("datetime").reset_index(drop=True)
        GLOBAL[contract] = b if not b.empty else None
    bars = GLOBAL[contract]
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
        eidx = idx
        if eidx >= len(bars):
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
        out.append({"tier": ev["tier_v40"], "pnl_net_bps": pnl})
    return out


if __name__ == "__main__":
    main()
