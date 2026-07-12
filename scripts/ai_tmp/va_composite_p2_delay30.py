#!/usr/bin/env python3
"""测试：从 30min 开始持仓（延迟入场 30min），看往后的积累是否优于 baseline。
即把"跳过负的头30min"当作一个固定时间择时规则，检验它是否成立。
- baseline: 信号即入场(idx)，持有 H*12 根(8h/10h)。
- delay30:  入场延到 idx+6(30min)，持有到原退出时刻(同日历窗口)。
同时输出"从30min往后的累积pnl曲线"(forward = cum[k]-cum[5])。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1

CAP = 5.0
DELAY = 6  # 30min = 6 根 5m bar
MAXB = max(P1.H_L, P1.H_S) * 12


def build_rows(contract, g, bars_cache, delay):
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
        H = P1.H_L if d == "long" else P1.H_S
        tot = H * 12
        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        eidx = idx + delay
        if eidx >= len(bars):
            continue
        hold = tot - delay  # 同日历退出
        if hold <= 0:
            continue
        ep = float(bars.iloc[eidx]["close"])
        if ep <= 0:
            continue
        sp = ep - sign * K * ep * atr / 10000.0
        notional_frac = P1.RISK_PER_TRADE / (K * atr / 10000.0)
        qty = notional_frac * P1.EQUITY_INIT / (ep * spec.size)
        future = bars.iloc[eidx: eidx + hold]
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
        entry_dt = bars.iloc[eidx]["datetime"]
        out.append({"contract": contract, "direction": int(sign), "tier": ev["tier_v40"],
                    "pnl_net_bps": pnl, "pnl_gross_bps": pnl_gross, "exit_reason": reason,
                    "entry_bar": entry_dt, "exit_bar": exit_dt,
                    "symbol": (P1.extract_contract_prefix(contract) or "").lower(),
                    "_notional_frac": notional_frac, "_entry_date": pd.Timestamp(entry_dt).date(),
                    "_exit_date": pd.Timestamp(exit_dt).date(),
                    "qty_raw": qty, "pnl_net_ccy": pnl / 10000.0 * notional_frac * P1.EQUITY_INIT})
    return out


def cum_series(contract, g, bars_cache):
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
        H = P1.H_L if d == "long" else P1.H_S
        tot = H * 12
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
        future = bars.iloc[idx: idx + tot]
        if len(future) == 0:
            continue
        row = []
        stopped = False
        for _, fb in future.iterrows():
            if not stopped:
                if sign == 1 and fb["low"] <= sp:
                    xp = sp; stopped = True
                elif sign == -1 and fb["high"] >= sp:
                    xp = sp; stopped = True
                else:
                    xp = float(fb["close"])
            else:
                xp = sp
            cx = P1.cost_oneway_bps(spec, xp, qty)
            row.append(sign * (xp - ep) / ep * 10000.0 - ce - cx)
        out.append(row)
    return out


def main():
    events = P1.load_events()
    bc = {}
    base_rows, delay_rows = [], []
    for c, g in events.groupby("contract"):
        base_rows.extend(build_rows(c, g, bc, 0))
        delay_rows.extend(build_rows(c, g, bc, DELAY))

    bt = P1.assign_equity(P1.compress(pd.DataFrame(base_rows), CAP))
    dt = P1.assign_equity(P1.compress(pd.DataFrame(delay_rows), CAP))
    mb = P1.base_metrics(bt); md = P1.base_metrics(dt)
    print("=" * 70)
    print("延迟入场 30min vs baseline (同批事件, Cap=5, 同日历退出窗口)")
    print("=" * 70)
    print(f"\n{'':>10} | {'交易数':>5} | {'年化':>7} | {'夏普':>6} | {'MaxDD':>7} | {'月度胜率':>7} | {'单笔IR':>6}")
    print("-" * 62)
    print(f"{'baseline':>10} | {len(bt):>5} | {mb['ann_ret']*100:6.2f}% | {mb['sharpe']:6.2f} | "
          f"{mb['max_dd']*100:6.2f}% | {P1.monthly_win_rate(bt)*100:6.1f}% | {P1.per_trade_ir(bt):6.3f}")
    print(f"{'delay30':>10} | {len(dt):>5} | {md['ann_ret']*100:6.2f}% | {md['sharpe']:6.2f} | "
          f"{md['max_dd']*100:6.2f}% | {P1.monthly_win_rate(dt)*100:6.1f}% | {P1.per_trade_ir(dt):6.3f}")
    d = P1.paired_delta(bt, dt)
    print(f"\n配对(delay30 vs baseline): ΔSharpe={d['dsharpe']:+.2f}  μ_true={d['nu_true']*100:+.2f}%  P(μ>0)={d['p_nu_pos']:.3f}")

    # 从30min往后的累积曲线 (forward = cum[k]-cum[5])
    print("\n" + "=" * 70)
    print("从 30min(第6根)往后的累积 pnl_bps = cum[k]-cum[5]")
    print("=" * 70)
    bc2 = {}
    all_cum = []
    for c, g in events.groupby("contract"):
        all_cum.extend(cum_series(c, g, bc2))
    if all_cum and len(all_cum[0]) >= 6:
        finals = [r[-1] for r in all_cum]
        f30 = [r[5] for r in all_cum]
        start_mean = np.mean(f30)
        end_mean = np.mean(finals)
        print(f"  30min 时均值 cum[5] = {start_mean:.2f} bps (负)")
        print(f"  终点 均值 cum[-1] = {end_mean:.2f} bps")
        print(f"  => 从30min往后净积累 = {end_mean-start_mean:.2f} bps (正, 跳过负头段)")
        pts = [6, 12, 24, 48, 96, 120]  # 30,60,120,240,480,600 min
        print(f"\n{'分钟':>6} | {'从30min起累积bps':>18} | 占往后净积累")
        print("-" * 46)
        for p in pts:
            vals = [r[p-1] - r[5] for r in all_cum if len(r) >= p]
            if vals:
                m_ = np.mean(vals)
                print(f"{p*5:>6} | {m_:>18.2f} | {m_/(end_mean-start_mean)*100:>8.1f}%")


if __name__ == "__main__":
    main()
