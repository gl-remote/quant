#!/usr/bin/env python3
"""对比实验：开盘即开仓，30 分钟平仓 vs baseline(8h/10h 持仓)。
验证假设：日频信号 edge 是否集中在前 30 分钟兑现、日内几乎无择时空间。
同时输出事件级累积 pnl 曲线（按持仓分钟），看 edge 兑现节奏。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1

CAP = 5.0
HOLD_BARS_30 = 6  # 30 分钟 = 6 根 5m bar


def simulate(contract, g, hold_bars, bars_cache):
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
        if idx >= len(bars):
            continue
        ep = float(bars.iloc[idx]["close"])
        if ep <= 0:
            continue
        sp = ep - sign * K * ep * atr / 10000.0
        notional_frac = P1.RISK_PER_TRADE / (K * atr / 10000.0)
        qty = notional_frac * P1.EQUITY_INIT / (ep * spec.size)
        future = bars.iloc[idx: idx + hold_bars]
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
        pnl_gross = sign * (xp - ep) / ep * 10000.0
        pnl = pnl_gross - ce - cx
        entry_dt = bars.iloc[idx]["datetime"]
        out.append({"contract": contract, "direction": int(sign), "tier": ev["tier_v40"],
                    "pnl_net_bps": pnl, "pnl_gross_bps": pnl_gross, "exit_reason": reason,
                    "entry_bar": entry_dt, "exit_bar": exit_dt,
                    "symbol": (P1.extract_contract_prefix(contract) or "").lower(),
                    "_notional_frac": notional_frac, "_entry_date": pd.Timestamp(entry_dt).date(),
                    "_exit_date": pd.Timestamp(exit_dt).date(),
                    "qty_raw": qty, "pnl_net_ccy": pnl / 10000.0 * notional_frac * P1.EQUITY_INIT})
    return out


def simulate_cum(contract, g, max_bars, bars_cache):
    """返回每事件在 bar k(1..max_bars) 的累积 pnl_bps（SL 截断生效）。"""
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
        if idx >= len(bars):
            continue
        ep = float(bars.iloc[idx]["close"])
        if ep <= 0:
            continue
        sp = ep - sign * K * ep * atr / 10000.0
        notional_frac = P1.RISK_PER_TRADE / (K * atr / 10000.0)
        qty = notional_frac * P1.EQUITY_INIT / (ep * spec.size)
        ce = P1.cost_oneway_bps(spec, ep, qty)
        future = bars.iloc[idx: idx + max_bars]
        if len(future) == 0:
            continue
        row = []
        stopped = False
        for k, (_, fb) in enumerate(future.iterrows(), start=1):
            if not stopped:
                if sign == 1 and fb["low"] <= sp:
                    xp = sp; stopped = True
                elif sign == -1 and fb["high"] >= sp:
                    xp = sp; stopped = True
                else:
                    xp = float(fb["close"])
            else:
                xp = sp  # 已 SL，后续持stop价
            cx = P1.cost_oneway_bps(spec, xp, qty)
            row.append(sign * (xp - ep) / ep * 10000.0 - ce - cx)
        out.append(row)
    return out


def metrics_from_rows(rows):
    t = pd.DataFrame(rows)
    # 构造最小字段供 base_metrics：用 pnl_net_ccy 近似（notional 恒等，用 bps 直接当 ccy 比例）
    t = t.copy()
    t["pnl_net_ccy"] = t["pnl_net_bps"]  # 仅用于相对对比，量纲统一
    t["_exit_date"] = pd.Series(range(len(t)))
    t["equity_after"] = t["pnl_net_ccy"].cumsum()
    m = P1.base_metrics(t)
    m["ir"] = P1.per_trade_ir(t)
    m["nu"], m["pnu"] = P1.nu_implied(t)
    return m


def main():
    events = P1.load_events()
    print("=" * 70)
    print("对比实验：30min 平仓 vs baseline(8h/10h)  [Cap=5.0]")
    print("=" * 70)

    # (1) 主指标对比
    bc = {}
    base_rows = []
    for c, g in events.groupby("contract"):
        for _, ev in g.iterrows():
            H = P1.H_L if ev["direction"] == "long" else P1.H_S
            seg = simulate(c, g[g["event_time"] == ev["event_time"]], H * 12, bc)
            base_rows.extend(seg)
    bc2 = {}
    m30_rows = []
    for c, g in events.groupby("contract"):
        m30_rows.extend(simulate(c, g, HOLD_BARS_30, bc2))

    bt = P1.assign_equity(P1.compress(pd.DataFrame(base_rows), CAP))
    mt = P1.assign_equity(P1.compress(pd.DataFrame(m30_rows), CAP))
    mb = P1.base_metrics(bt); m3 = P1.base_metrics(mt)
    print(f"\n{'':>10} | {'交易数':>5} | {'年化':>7} | {'夏普':>6} | {'MaxDD':>7} | {'月度胜率':>7} | {'单笔IR':>6}")
    print("-" * 62)
    print(f"{'baseline':>10} | {len(bt):>5} | {mb['ann_ret']*100:6.2f}% | {mb['sharpe']:6.2f} | "
          f"{mb['max_dd']*100:6.2f}% | {P1.monthly_win_rate(bt)*100:6.1f}% | {P1.per_trade_ir(bt):6.3f}")
    print(f"{'30min':>10} | {len(mt):>5} | {m3['ann_ret']*100:6.2f}% | {m3['sharpe']:6.2f} | "
          f"{m3['max_dd']*100:6.2f}% | {P1.monthly_win_rate(mt)*100:6.1f}% | {P1.per_trade_ir(mt):6.3f}")

    # 配对增量（隔离 Cap）
    d = P1.paired_delta(bt, mt)
    print(f"\n配对(30min vs baseline): ΔSharpe={d['dsharpe']:+.2f}  μ_true={d['nu_true']*100:+.2f}%  P(μ>0)={d['p_nu_pos']:.3f}")

    # (2) 累积 pnl 曲线（按持仓分钟）
    print("\n" + "=" * 70)
    print("事件级累积平均 pnl(bps) 按持仓时间 — edge 兑现节奏")
    print("=" * 70)
    maxL = max(P1.H_L, P1.H_S) * 12
    bc3 = {}
    cumL, cumS = [], []
    for c, g in events.groupby("contract"):
        for direction, coll in [("long", cumL), ("short", cumS)]:
            gg = g[g["direction"] == direction]
            if len(gg):
                coll.extend(simulate_cum(c, gg, maxL, bc3))
    pts = [1, 3, 6, 12, 24, 48, 96, 120]  # 5,15,30,60,120,240,480,600 min
    print(f"{'分钟':>6} | {'平均累积pnl_bps':>16} | 占最终比例")
    print("-" * 42)
    finals = [r[-1] for r in (cumL + cumS) if len(r) >= maxL]
    final_mean = np.mean(finals) if finals else 0
    for p in pts:
        vals = [r[p-1] for r in (cumL + cumS) if len(r) >= p]
        if vals:
            m_ = np.mean(vals)
            print(f"{p*5:>6} | {m_:>16.2f} | {m_/final_mean*100:>8.1f}%")
    for tag, coll, Hh in [("LONG(8h终)", cumL, P1.H_L), ("SHORT(10h终)", cumS, P1.H_S)]:
        maxb = Hh * 12
        v30 = np.mean([r[5] for r in coll if len(r) >= 6])
        vf = np.mean([r[-1] for r in coll if len(r) >= maxb])
        print(f"  {tag}: 30min 平均 {v30:.2f}bps / 最终 {vf:.2f}bps → 占比 {v30/vf*100:.1f}%")
    print(f"\n注：30min=6 根 5m bar；baseline 持仓 long=96根(8h)、short=120根(10h)。")


if __name__ == "__main__":
    main()
