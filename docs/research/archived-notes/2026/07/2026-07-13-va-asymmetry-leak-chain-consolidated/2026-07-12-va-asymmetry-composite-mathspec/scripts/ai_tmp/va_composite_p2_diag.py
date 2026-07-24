#!/usr/bin/env python3
"""Phase 2 诊断：entry_mode 把数据变差的两路分解
  (A) 入场价/延迟效应：触发的交易，mode_pnl - baseline_pnl（同事件）
  (B) 漏掉效应：被 mode 跳过（未触发）的事件，其 baseline 本可盈利被丢弃
逐事件配对 baseline(全触发) vs 各 mode，量化 (A)(B) 对总 pnl 变化的贡献。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1
import va_composite_p2_entry_mode as P2

MODES = ["boll", "macd", "kdj", "rsi", "breakout", "prevhi", "openrange"]


def simulate_per_event(contract, g, mode, bars_cache):
    """返回 list[dict]，每条 = 一个事件的结果（含未触发的）。"""
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    csv_path = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not csv_path.exists():
        return []
    if contract not in bars_cache:
        b = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.sort_values("datetime").reset_index(drop=True)
        bars_cache[contract] = P2.add_indicators(b) if not b.empty else None
    bars = bars_cache[contract]
    if bars is None:
        return []
    trig = P2.build_trigger(bars, mode)
    out = []
    for _, ev in g.iterrows():
        direction = ev["direction"]
        sign = 1 if direction == "long" else -1
        K = P1.K_L_SL if direction == "long" else P1.K_S_SL
        H = P1.H_L if direction == "long" else P1.H_S
        atr_bps = float(ev["entry_atr_bps"])
        if atr_bps <= 0:
            continue
        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        if mode == "baseline":
            entry_idx = idx
        else:
            fut = bars.index[idx: idx + H * 12]
            mask = trig[direction].loc[fut]
            if not mask.any():
                out.append({"evt": (contract, ev["event_time"]), "direction": sign,
                            "triggered": False, "pnl_net_bps": np.nan, "entry_price": np.nan})
                continue
            entry_idx = mask.idxmax()
        bar = bars.loc[entry_idx]
        entry_price = float(bar["close"])
        if entry_price <= 0:
            out.append({"evt": (contract, ev["event_time"]), "direction": sign,
                        "triggered": False, "pnl_net_bps": np.nan, "entry_price": np.nan})
            continue
        atr_price = entry_price * atr_bps / 10000.0
        stop_price = entry_price - sign * K * atr_price
        notional_frac = P1.RISK_PER_TRADE / (K * atr_bps / 10000.0)
        qty_raw = notional_frac * P1.EQUITY_INIT / (entry_price * spec.size)
        future = bars.iloc[entry_idx: entry_idx + H * 12]
        if len(future) == 0:
            continue
        exit_price = np.nan
        for _, fb in future.iterrows():
            if sign == 1 and fb["low"] <= stop_price:
                exit_price = stop_price; break
            if sign == -1 and fb["high"] >= stop_price:
                exit_price = stop_price; break
        if np.isnan(exit_price):
            exit_price = float(future.iloc[-1]["close"])
        cost_e = P1.cost_oneway_bps(spec, entry_price, qty_raw)
        cost_x = P1.cost_oneway_bps(spec, exit_price, qty_raw)
        pnl_gross_bps = sign * (exit_price - entry_price) / entry_price * 10000.0
        pnl_net_bps = pnl_gross_bps - cost_e - cost_x
        out.append({"evt": (contract, ev["event_time"]), "direction": sign,
                    "triggered": True, "pnl_net_bps": pnl_net_bps,
                    "entry_price": entry_price})
    return out


def main():
    print("=" * 78)
    print("Phase 2 诊断：entry_mode 变差两路分解 (A)入场价/延迟  (B)漏掉好交易")
    print("=" * 78)
    events = P1.load_events()
    bc = {}
    base = []
    for c, g in events.groupby("contract"):
        base.extend(simulate_per_event(c, g, "baseline", bc))
    base_df = pd.DataFrame(base)
    base_map = base_df.set_index("evt")["pnl_net_bps"].to_dict()

    print(f"\n总事件 N = {len(base_df)} | baseline 全触发")
    print(f"{'mode':>9} | {'触发':>4}/{'跳过':>4} | {'漏掉效应(bps)':>14} | {'入场价效应(bps)':>15} | 漏掉事件base均值 | 漏掉事件正占比")
    print("-" * 100)
    for mode in MODES:
        bc2 = {}
        rows = []
        for c, g in events.groupby("contract"):
            rows.extend(simulate_per_event(c, g, mode, bc2))
        df = pd.DataFrame(rows)
        trig = df[df["triggered"]]
        skip = df[~df["triggered"]]
        # 漏掉效应：跳过事件 baseline 本可盈利之和（正=漏掉好交易，损失）
        skip_base = skip["evt"].map(base_map)
        skip_effect = -skip_base.sum()  # 总 pnl 少掉这部分
        # 入场价效应：触发事件 mode_pnl - baseline_pnl
        trig["base_pnl"] = trig["evt"].map(base_map)
        price_effect = (trig["pnl_net_bps"] - trig["base_pnl"]).sum()
        n_skip = len(skip)
        n_trig = len(trig)
        print(f"{mode:>9} | {n_trig:>4}/{n_skip:>4} | {skip_effect:>14.1f} | {price_effect:>15.1f} | "
              f"{skip_base.mean():>14.1f} | {(skip_base>0).mean()*100:>10.1f}%")

    print("\n说明：")
    print("  漏掉效应(总bps) = Σ(被跳过事件的 baseline pnl) 取负；若这些 baseline pnl 多为正 → 漏掉好交易")
    print("  入场价效应(总bps) = Σ(触发事件 mode_pnl − baseline_pnl)；负值 → 改入场价导致每笔变差")
    print("  两者之和 ≈ 该 mode 相对 baseline 的总 pnl 变化（bps，未计 Cap 压仓，Cap 同口径已隔离）")


if __name__ == "__main__":
    main()
