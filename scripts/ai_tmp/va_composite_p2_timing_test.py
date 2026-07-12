#!/usr/bin/env python3
"""决定性测试：是否存在可剥削的择时空间。
方法：
  (1) 对每笔事件算 in-sample 最优出场点 t* = argmax(累积pnl)。
      若 t* 集中可预测 -> 存在择时结构；若 t* 分散随机 -> 无择时。
  (2) 择时上界增益：mean(峰值pnl) vs mean(固定终点pnl) 的差距 = 择时可达最大增益。
  (3) 真实可落地规则：trailing-stop(从峰值回撤 T%) 退出 vs 固定持有，全指标对比。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1

CAP = 5.0
MAXB = max(P1.H_L, P1.H_S) * 12  # 120 bars


def cum_series(contract, g, bars_cache):
    """每事件累积pnl_bps序列（SL截断），长度<=MAXB。"""
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
        future = bars.iloc[idx: idx + MAXB]
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
        out.append((row, sign))
    return out


def trailing_exit(cum, peak_frac):
    """从运行峰值回撤 peak_frac 比例的瞬时退出；永不回撤则持有至终点。"""
    if not cum:
        return 0.0
    peak = cum[0]; out = cum[0]
    for v in cum:
        if v > peak:
            peak = v
        if peak > 0 and v <= peak * (1 - peak_frac):
            return v
        out = v
    return out


def main():
    events = P1.load_events()
    bc = {}
    all_cum = []
    for c, g in events.groupby("contract"):
        all_cum.extend(cum_series(c, g, bc))

    n = len(all_cum)
    print("=" * 70)
    print(f"择时空间决定性测试  (样本事件 {n} 笔，最大持仓 {MAXB}根5m={MAXB*5}min)")
    print("=" * 70)

    # (1) 每笔 in-sample 最优出场点 t* 分布
    t_stars = []
    peak_vals = []
    end_vals = []
    monotonic = 0
    givebacks = []
    for cum, _ in all_cum:
        L = len(cum)
        t_star = int(np.argmax(cum)) + 1  # 1-indexed
        pv = cum[t_star - 1]
        ev_ = cum[-1]
        t_stars.append(t_star)
        peak_vals.append(pv)
        end_vals.append(ev_)
        if t_star == L:
            monotonic += 1
        else:
            if pv > 0:
                givebacks.append(pv - ev_)

    t_stars = np.array(t_stars) * 5  # 转成分钟
    buckets = [(1, 30, "0-30min"), (31, 60, "30-60min"), (61, 120, "60-120min"),
               (121, 240, "120-240min"), (241, 480, "240-480min"), (481, 600, "480-600min")]
    print("\n[1] in-sample 最优出场点 t*(分钟) 分布（是否集中可预测）")
    print(f"{'区间':>12} | {'笔数':>5} | {'占比':>6}")
    print("-" * 32)
    for lo, hi, name in buckets:
        m = ((t_stars >= lo) & (t_stars <= hi)).sum()
        print(f"{name:>12} | {m:>5} | {m/n*100:>5.1f}%")
    print(f"\n  t* 落在终点(即全程单调无更早峰值)占比: {monotonic/n*100:.1f}%")
    print(f"  t* 标准差: {np.std(t_stars):.0f}min  | 全距 {t_stars.min()}-{t_stars.max()}min")

    # (2) 择时上界增益
    print("\n[2] 择时上界（in-sample 峰值 vs 固定终点）")
    mp, me = np.mean(peak_vals), np.mean(end_vals)
    print(f"  mean(最优峰值pnl) = {mp:.2f} bps")
    print(f"  mean(固定终点pnl) = {me:.2f} bps")
    print(f"  择时可达上界增益   = {(mp-me):.2f} bps  ({ (mp-me)/abs(me)*100:+.1f}% vs 终点)")
    print(f"  有更早峰值的事件中，峰值后平均回吐 = {np.mean(givebacks):.2f} bps (n={len(givebacks)})")

    # (3) 可落地 trailing-stop 规则 vs 固定持有
    print("\n[3] 真实可落地规则：trailing-stop(峰值回撤退出) vs 固定持有")
    print(f"{'规则':>16} | {'笔数':>5} | {'平均pnl_bps':>11} | {'vs固定Δ':>9}")
    print("-" * 50)
    for frac in [0.2, 0.3, 0.5]:
        vals = [trailing_exit(cum, frac) for cum, _ in all_cum]
        print(f"{'trail_'+str(int(frac*100))+'%':>16} | {n:>5} | {np.mean(vals):>11.2f} | {np.mean(vals)-me:>+9.2f}")
    print(f"{'固定持有(终点)':>16} | {n:>5} | {me:>11.2f} | {'—':>9}")

    # 结论判定
    print("\n" + "=" * 70)
    print("判定：")
    print(f"  - 若 t* 高度分散(标准差>>60min) 且 单调占比高 -> 无择时结构(峰值不可预测)")
    print(f"  - 若 择时上界增益≈0 且 trailing 规则均不优于固定 -> 择时空间为零")
    print("=" * 70)


if __name__ == "__main__":
    main()
