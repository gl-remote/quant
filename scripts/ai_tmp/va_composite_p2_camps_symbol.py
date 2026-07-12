#!/usr/bin/env python3
"""按合约品种(symbol)拆分，检验逐阵营最优持仓时长的跨品种稳定性。

核心问题: 之前发现 S_seg34/L_seg3 前载(最优6h)、S_seg12 长持(10-12h)。
          这是真结构还是"某品种凑巧"? => 在每个品种内重扫时长，看是否一致。

设计:
  (a) symbol 维度分布: 每 symbol 事件数 + tier 覆盖。
  (b) 每 (symbol, direction) 持仓时长扫描 2/4/6/8/10/12h, 给最优时长(仅 n>=10)。
  (c) 重点: 对每个 symbol 内"前载 tier"(S_seg34_high_dn / L_seg3_lowmid_up) 重扫时长,
      与全局最优(6h)对比, 看是否跨品种稳定落在 6h 附近。
统一模拟器同 camps.py (SL 重锚, delay=0)。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1

HOLDS_H = [2, 4, 6, 8, 10, 12]
GLOBAL = {}


def simulate(contract, g, delay_bars, hold_bars):
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
        out.append({"symbol": (P1.extract_contract_prefix(contract) or "").lower(),
                    "direction": d, "tier": ev["tier_v40"], "pnl_net_bps": pnl})
    return out


def stats(rows):
    if not rows:
        return (0, 0.0, 0.0, 0.0)
    t = pd.DataFrame(rows)
    return (len(t), (t["pnl_net_bps"] > 0).mean() * 100,
            t["pnl_net_bps"].mean(), P1.per_trade_ir(t))


def scan_hold(sub, label):
    """对 sub(已按 contract 分组前的事件df) 扫时长, 返回最优时长与曲线"""
    best_h, best_ir = None, -9
    curve = []
    for h in HOLDS_H:
        rows = []
        for c, g in sub.groupby("contract"):
            rows.extend(simulate(c, g, 0, h * 12))
        n, w, m, ir = stats(rows)
        curve.append((h, n, w, m, ir))
        if n >= 10 and ir > best_ir:
            best_h, best_ir = h, ir
    return best_h, best_ir, curve


def main():
    events = P1.load_events()
    events["symbol"] = events["contract"].map(
        lambda c: (P1.extract_contract_prefix(c) or "").lower())

    # (a) symbol 分布
    sym = events.groupby("symbol").agg(
        n=("contract", "size"),
        tiers=("tier_v40", lambda s: ",".join(sorted(set(s))))).reset_index()
    sym = sym.sort_values("n", ascending=False)
    print("=" * 78)
    print(f"品种(symbol)分布: 共 {events['symbol'].nunique()} 个品种, {len(events)} 笔事件")
    print("=" * 78)
    for _, r in sym.iterrows():
        print(f"  {r['symbol']:>10} | n={r['n']:>3} | {r['tiers']}")

    # (b) 每 (symbol, direction) 时长扫描
    print("\n" + "#" * 78)
    print("每 (品种, 方向) 持仓时长扫描 — 最优时长")
    print("#" * 78)
    print(f"  {'symbol':>10} | {'dir':>5} | {'n':>4} | {'最优':>5} | "
          f"2h/4h/6h/8h/10h/12h 的 IR")
    rec = []
    for s, sg in events.groupby("symbol"):
        for d in ("long", "short"):
            sub = sg[sg["direction"] == d]
            if len(sub) < 10:
                continue
            best_h, best_ir, curve = scan_hold(sub, f"{s}/{d}")
            irs = "/".join(f"{c[4]:.2f}" for c in curve)
            print(f"  {s:>10} | {d:>5} | {len(sub):>4} | "
                  f"{str(best_h)+'h':>5} | {irs}")
            rec.append((s, d, len(sub), best_h, best_ir))

    # (c) 前载 tier 跨品种稳定性: S_seg34 / L_seg3 各自在每品种的最优时长
    print("\n" + "#" * 78)
    print("前载阵营跨品种时长稳定性 (S_seg34_high_dn / L_seg3_lowmid_up)")
    print("#" * 78)
    for tier in ("S_seg34_high_dn", "L_seg3_lowmid_up"):
        print(f"\n  >> 阵营 {tier} (全局最优=6h)")
        print(f"     {'symbol':>10} | {'n':>4} | {'最优':>5} | "
              f"2h/4h/6h/8h/10h/12h 的 IR")
        tdf = events[events["tier_v40"] == tier]
        hrs = []
        for s, sg in tdf.groupby("symbol"):
            if len(sg) < 4:
                continue
            best_h, best_ir, curve = scan_hold(sg, f"{tier}/{s}")
            irs = "/".join(f"{c[4]:.2f}" for c in curve)
            print(f"     {s:>10} | {len(sg):>4} | "
                  f"{str(best_h)+'h':>5} | {irs}")
            if best_h is not None:
                hrs.append(best_h)
        if hrs:
            from collections import Counter
            cc = Counter(hrs)
            print(f"     => 该阵营跨品种最优时长分布: "
                  f"{dict(sorted(cc.items()))}  | 众数={cc.most_common(1)[0][0]}h")
        else:
            print("     => 该阵营无单品种 n>=4 样本, 无法在品种级验证(仅组合层面显著)")


if __name__ == "__main__":
    main()
