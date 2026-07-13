#!/usr/bin/env python3
"""
va-composite · Phase 7 · 风控件（trailing / TP / cb）

位置: scripts/ai_tmp/va_p07_risk.py
主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 B0 管线（classifier_v31_timeline.parquet + 5m CSV），复用 va_composite_p1_cap 的数据/指标层

目标（experiment-plan § Phase 7）:
  在冻结 B0（Cap=4.0、dedup=8h、H_L/H_S=8/10、K_SL L/S=1.0/2.5、风控全关）上，
  逐件叠加风控件，测相对 B0 的净夏普增量（§0.1 门限：ΔSh≥0.2 且 P≥0.95 方采用）：
    - trailing-stop：从峰值回撤 trail_k×ATR 退出（H 内提前退）
    - TP（take profit）：触达 +tp_k×ATR 退出（H 内提前止盈）
    - cb（circuit breaker）：组合权益从 peak 回撤 > cb_dd（默认 -5%）后，暂停新开仓 cb_pause 个交易日

判定: 任一风控件无正净夏普增量 → 不启用（保持 B0）。

运行: uv run python scripts/ai_tmp/va_p07_risk.py
输出: project_data/ai_tmp/p7_risk/summary.md + 各候选 trades.parquet
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402

OUT_DIR = Path("project_data/ai_tmp/p7_risk")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CAP = 4.0

# 风控代表参数（plan 未给具体值，取贴近 B0 的合理默认；若有增量再扫）
TRAIL_K = 1.0       # trailing 回撤 = 1×ATR
TP_K = 1.5          # TP 触达 = 1.5×ATR
CB_DD = -0.05       # 组合回撤 > 5% 触发熔断
CB_PAUSE = 5        # 暂停新开仓 5 个交易日


# =====================================================================
# 信号模拟（冻结口径 + 可叠加 trailing/TP）
# =====================================================================
def simulate_contract(contract: str, g: pd.DataFrame, sp: dict) -> list[dict]:
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    csv_path = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not csv_path.exists():
        return []
    bars = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)
    if bars.empty:
        return []

    rows: list[dict] = []
    for _, ev in g.iterrows():
        direction = ev["direction"]
        sign = 1 if direction == "long" else -1
        K = P1.K_L_SL if direction == "long" else P1.K_S_SL
        H = P1.H_L if direction == "long" else P1.H_S
        entry_price = float(ev["close_t"])
        atr_bps = float(ev["entry_atr_bps"])
        if entry_price <= 0 or atr_bps <= 0:
            continue
        atr_price = entry_price * atr_bps / 10000.0
        stop_price = entry_price - sign * K * atr_price
        stop_dist_frac = K * atr_bps / 10000.0
        notional_frac = P1.RISK_PER_TRADE / stop_dist_frac
        qty_raw = notional_frac * P1.EQUITY_INIT / (entry_price * spec.size)

        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        future = bars.iloc[idx: idx + H * 12]
        if len(future) == 0:
            continue
        exit_price = np.nan
        exit_reason = "TIME"
        exit_bar = future.iloc[-1]["datetime"]
        peak_price = entry_price
        for _, bar in future.iterrows():
            # 固定止损 SL
            if sign == 1 and bar["low"] <= stop_price:
                exit_price = stop_price
                exit_reason = "SL"
                exit_bar = bar["datetime"]
                break
            if sign == -1 and bar["high"] >= stop_price:
                exit_price = stop_price
                exit_reason = "SL"
                exit_bar = bar["datetime"]
                break
            # 止盈 TP
            if sp["use_tp"]:
                tp_price = entry_price + sign * sp["tp_k"] * atr_price
                if sign == 1 and bar["high"] >= tp_price:
                    exit_price = tp_price
                    exit_reason = "TP"
                    exit_bar = bar["datetime"]
                    break
                if sign == -1 and bar["low"] <= tp_price:
                    exit_price = tp_price
                    exit_reason = "TP"
                    exit_bar = bar["datetime"]
                    break
            # trailing-stop（峰值回撤）
            if sp["use_trailing"]:
                peak_price = max(peak_price, bar["high"]) if sign == 1 else min(peak_price, bar["low"])
                trail_stop = peak_price - sign * sp["trail_k"] * atr_price
                if sign == 1 and bar["low"] <= trail_stop:
                    exit_price = trail_stop
                    exit_reason = "TRAIL"
                    exit_bar = bar["datetime"]
                    break
                if sign == -1 and bar["high"] >= trail_stop:
                    exit_price = trail_stop
                    exit_reason = "TRAIL"
                    exit_bar = bar["datetime"]
                    break
        if np.isnan(exit_price):
            exit_price = float(future.iloc[-1]["close"])
            exit_bar = future.iloc[-1]["datetime"]

        cost_entry_bps = P1.cost_oneway_bps(spec, entry_price, qty_raw)
        cost_exit_bps = P1.cost_oneway_bps(spec, exit_price, qty_raw)
        gross_ret = sign * (exit_price - entry_price) / entry_price
        pnl_gross_bps = gross_ret * 10000.0
        pnl_net_bps = pnl_gross_bps - cost_entry_bps - cost_exit_bps
        notional_ccy = qty_raw * entry_price * spec.size
        pnl_net_ccy = pnl_net_bps / 10000.0 * notional_ccy

        sym = (P1.extract_contract_prefix(contract) or "").lower()
        rows.append({
            "contract": contract,
            "symbol": sym,
            "symbol_type": P1.SYMBOL_TYPE.get(sym, "C"),
            "entry_bar": ev["event_time"],
            "exit_bar": exit_bar,
            "direction": int(sign),
            "tier": ev["tier_v40"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "entry_atr_bps": atr_bps,
            "qty_raw": qty_raw,
            "qty_actual": qty_raw,
            "pnl_gross_bps": pnl_gross_bps,
            "cost_entry_bps": cost_entry_bps,
            "cost_exit_bps": cost_exit_bps,
            "pnl_net_bps": pnl_net_bps,
            "pnl_net_ccy": pnl_net_ccy,
            "_notional_frac": notional_frac,
            "_entry_date": ev["event_time"].date(),
            "_exit_date": pd.Timestamp(exit_bar).date(),
        })
    return rows


def build_trades(events: pd.DataFrame, sp: dict) -> pd.DataFrame:
    rows = []
    for contract, g in events.groupby("contract"):
        rows.extend(simulate_contract(contract, g, sp))
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t = P1.compress(t, CAP)
    return t


# =====================================================================
# 组合层熔断 cb（回撤 > cb_dd 后暂停新开仓 cb_pause 个交易日）
# =====================================================================
def apply_cb(trades: pd.DataFrame, active_days) -> pd.DataFrame:
    if trades.empty:
        return trades
    t = trades.copy()
    t["day"] = t["_exit_date"]
    daily = t.groupby("day")["pnl_net_ccy"].sum()
    ad = sorted(active_days)
    daily = daily.reindex(ad, fill_value=0.0)
    eq = P1.EQUITY_INIT + daily.cumsum()
    peak = eq.cummax()
    dd = (eq - peak) / peak
    ad_dates = list(ad)
    pause = set()
    for i, d in enumerate(ad_dates):
        if pd.isna(dd.loc[d]):
            continue
        if dd.loc[d] < CB_DD:
            for k in range(i + 1, min(i + 1 + CB_PAUSE, len(ad_dates))):
                pause.add(ad_dates[k])
    mask = ~t["day"].isin(pause)
    return t[mask].copy()


# =====================================================================
# 主流程
# =====================================================================
def main() -> None:
    print("=" * 70)
    print("va-composite · Phase 7 · 风控件（trailing / TP / cb）  [基线=冻结 B0 · Cap=4.0]")
    print("=" * 70)

    tl_full = pd.read_parquet(P1.TIMELINE_PATH)
    active_days = P1.active_day_set(tl_full, "signed_skew_rank_roll")
    events = P1.load_events()
    print(f"[load] events={len(events)}  active_days={len(active_days)}")

    sp_base = {"use_trailing": False, "trail_k": 0.0, "use_tp": False, "tp_k": 0.0}
    sp_trail = {"use_trailing": True, "trail_k": TRAIL_K, "use_tp": False, "tp_k": 0.0}
    sp_tp = {"use_trailing": False, "trail_k": 0.0, "use_tp": True, "tp_k": TP_K}
    sp_cb = {"use_trailing": False, "trail_k": 0.0, "use_tp": False, "tp_k": 0.0}

    print("[sim] B0 (风控全关) ...")
    b0 = build_trades(events, sp_base)
    b0_m = P1.base_metrics(b0, active_days=active_days)

    print("[sim] trailing (TRAIL_K=%.1f×ATR) ..." % TRAIL_K)
    tr = build_trades(events, sp_trail)
    tr_m = P1.base_metrics(tr, active_days=active_days)

    print("[sim] TP (TP_K=%.1f×ATR) ..." % TP_K)
    tp = build_trades(events, sp_tp)
    tp_m = P1.base_metrics(tp, active_days=active_days)

    print("[sim] cb (DD>%.0f%% 暂停 %d 日) ..." % (CB_DD * 100, CB_PAUSE))
    cb_raw = build_trades(events, sp_cb)
    cb = apply_cb(cb_raw, active_days)
    cb_m = P1.base_metrics(cb, active_days=active_days)

    # 留存明细
    b0.to_parquet(OUT_DIR / "b0.trades.parquet")
    tr.to_parquet(OUT_DIR / "trailing.trades.parquet")
    tp.to_parquet(OUT_DIR / "tp.trades.parquet")
    cb.to_parquet(OUT_DIR / "cb.trades.parquet")

    def line(name, m, t):
        print(f"  {name:10s} n={len(t):4d}  ann_ret={m['ann_ret']*100:6.2f}%  "
              f"sharpe={m['sharpe']:.2f}  max_dd={m['max_dd']*100:6.2f}%")

    print("\n[metrics] 主指标（新·可交易日口径=只用 skew 拿到值）")
    line("B0", b0_m, b0)
    line("trailing", tr_m, tr)
    line("TP", tp_m, tp)
    line("cb", cb_m, cb)

    def paired(name, cand):
        d = P1.paired_delta(b0, cand)
        gate = (d["dsharpe"] >= 0.2) and (d["p_nu_pos"] >= 0.95)
        print(f"  {name:10s} ΔSh={d['dsharpe']:+.2f}  μ_true={d['nu_true']:+.2f}bps  "
              f"P(μ_true>0)={d['p_nu_pos']:.3f}  -> {'过门✅ 采用' if gate else '未过门❌ 保持B0'}")
        return d, gate

    print("\n[paired] 候选 vs B0（§0.1 门限: ΔSh≥0.2 且 P≥0.95）")
    d_tr, g_tr = paired("trailing", tr)
    d_tp, g_tp = paired("TP", tp)
    d_cb, g_cb = paired("cb", cb)

    # 退出原因分布（trailing/TP 提前退出占比）
    def exit_dist(t):
        return t["exit_reason"].value_counts().to_dict()
    print("\n[exit-reason] 分布")
    print("  B0      :", exit_dist(b0))
    print("  trailing:", exit_dist(tr))
    print("  TP      :", exit_dist(tp))
    print("  cb      :", exit_dist(cb), " (n after cb =", len(cb), "vs raw", len(cb_raw), ")")

    # 写 summary
    summary = []
    summary.append("# Phase 7 · 风控件（trailing / TP / cb）\n")
    summary.append("> 基线 = 冻结 B0（Cap=4.0、dedup=8h、H_L/H_S=8/10、K_SL L/S=1.0/2.5、风控全关）。\n")
    summary.append("> 口径 = 新·可交易日口径（只用 skew 拿到值）。配对增量门限（§0.1）：ΔSharpe≥0.2 且 P(μ_true>0)≥0.95。\n")
    summary.append("> 风控代表参数：TRAIL_K=%.1f×ATR，TP_K=%.1f×ATR，cb=DD>%.0f%% 暂停 %d 交易日。\n" % (TRAIL_K, TP_K, CB_DD * 100, CB_PAUSE))
    summary.append("\n## 主指标\n")
    summary.append("| 方案 | 交易数 | 年化 | 净夏普 | MaxDD |\n|:---|---:|---:|---:|---:|")
    for nm, m, t in [("B0", b0_m, b0), ("trailing", tr_m, tr), ("TP", tp_m, tp), ("cb", cb_m, cb)]:
        summary.append(f"| {nm} | {len(t)} | {m['ann_ret']*100:.2f}% | {m['sharpe']:.2f} | {m['max_dd']*100:.2f}% |")
    summary.append("\n## 配对增量（vs B0）\n")
    summary.append("| 方案 | ΔSharpe | μ_true(bps) | P(μ_true>0) | 门禁 |\n|:---|---:|---:|---:|:---|")
    for nm, d, g in [("trailing", d_tr, g_tr), ("TP", d_tp, g_tp), ("cb", d_cb, g_cb)]:
        summary.append(f"| {nm} | {d['dsharpe']:+.2f} | {d['nu_true']:+.2f} | {d['p_nu_pos']:.3f} | {'过门✅' if g else '未过门❌'} |")
    summary.append("\n## 退出原因分布\n")
    summary.append(f"- B0      : {exit_dist(b0)}")
    summary.append(f"- trailing: {exit_dist(tr)}")
    summary.append(f"- TP      : {exit_dist(tp)}")
    summary.append(f"- cb      : {exit_dist(cb)}（熔断后保留 {len(cb)}/{len(cb_raw)} 笔）")
    summary.append("\n## 结论\n")
    summary.append("- 逐件相对 B0 测净夏普增量；无正增量则保持 B0（风控全关）。详见正文。\n")

    (OUT_DIR / "summary.md").write_text("\n".join(summary))
    print("\n[done] 见", OUT_DIR / "summary.md")


if __name__ == "__main__":
    main()
