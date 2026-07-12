#!/usr/bin/env python3
"""
va-composite · Phase 2 · 日内择时 entry_mode（第二大真实杠杆）粗筛

位置: scripts/ai_tmp/va_composite_p2_entry_mode.py
主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 B0 管线（旧口径 timeline + 5m CSV）；Cap 已定档 = 5.0（P1 用户指定）

设计（spec §3.1.2）:
  - baseline（B0 承诺路径）: 事件后首根 entry_tf(5m) bar 即按 tier 方向开仓。
  - 7 候选 mode: boll / macd / kdj / rsi / breakout / prevhi / openrange，
    均须「A 候选命中 + pred_mode 触发 + 方向与 tier 一致」方入场；
    在事件后 H*12 根 5m bar 窗口内扫描首个触发 bar 作为入场（超窗未触发则跳过该事件）。
  - 入场价 = 触发 bar 收盘；SL/时间退出同 B0（§3.2/§3.3），自入场 bar 起算。

配对评估（experiment-plan §0.1 / spec §9）:
  - 隔离效应: mode@Cap5.0  vs  baseline@Cap5.0  （Cap 恒定，隔离择时增量）—— 用于 §0.1 门限判定。
  - 对照:      mode@Cap5.0  vs  baseline@Cap1.0  （= 冻结 B0，含 Cap 效应）—— 仅作参照。
  - 门限: 隔离 ΔSharpe ≥ 0.2  AND  P(μ_true>0) ≥ 0.95，二者同时满足方采用（粗筛存活）。

运行: uv run python scripts/ai_tmp/va_composite_p2_entry_mode.py
输出: project_data/ai_tmp/p2_entry/summary.md + 各 mode 交易明细 parquet
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # 复用 load_events/compress/assign_equity/metrics/paired_delta/常量

TIMELINE_PATH = P1.TIMELINE_PATH
MARKET_DIR = P1.MARKET_DIR
OUT_DIR = Path("project_data/ai_tmp/p2_entry")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CAP_FWD = 5.0  # P1 定档
MODES = ["baseline", "boll", "macd", "kdj", "rsi", "breakout", "prevhi", "openrange"]


# =====================================================================
# 指标（在 5m bars 上预计算，所有 mode 复用）
# =====================================================================
def add_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    c, h, l = bars["close"], bars["high"], bars["low"]
    # boll(20, 2.0)
    ma = c.rolling(20).mean()
    sd = c.rolling(20).std()
    bars["BB_up"] = ma + 2.0 * sd
    bars["BB_low"] = ma - 2.0 * sd
    # macd(12,26,9)
    ema_f = c.ewm(span=12, adjust=False).mean()
    ema_s = c.ewm(span=26, adjust=False).mean()
    bars["DIF"] = ema_f - ema_s
    bars["DEA"] = bars["DIF"].ewm(span=9, adjust=False).mean()
    bars["DIF_prev"] = bars["DIF"].shift(1)
    bars["DEA_prev"] = bars["DEA"].shift(1)
    # kdj(9,3,3)
    low_n = c.rolling(9).min()
    high_n = c.rolling(9).max()
    rsv = ((c - low_n) / (high_n - low_n) * 100).fillna(50.0)
    K = rsv.ewm(com=2, adjust=False).mean()
    D = K.ewm(com=2, adjust=False).mean()
    bars["K"], bars["D"] = K, D
    bars["K_prev"] = K.shift(1)
    bars["D_prev"] = D.shift(1)
    # rsi(14)
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    bars["RSI"] = 100 - 100 / (1 + rs)
    # breakout(20)
    bars["HH20"] = h.rolling(20).max().shift(1)
    bars["LL20"] = l.rolling(20).min().shift(1)
    # session high/low（前一交易日）→ prevhi/prevlo
    bars["date"] = bars["datetime"].dt.date
    dates = sorted(bars["date"].unique())
    prev_map = {d: dates[i - 1] for i, d in enumerate(dates)}
    sess_h = bars.groupby("date")["high"].max()
    sess_l = bars.groupby("date")["low"].min()
    bars["PH_prev"] = bars["date"].map(lambda d: sess_h.get(prev_map.get(d)))
    bars["PL_prev"] = bars["date"].map(lambda d: sess_l.get(prev_map.get(d)))
    # openrange（开盘前 3 根 5m = 15min）
    bars["bar_in_session"] = bars.groupby("date").cumcount()
    orh = bars[bars["bar_in_session"] < 3].groupby("date")["high"].max()
    orl = bars[bars["bar_in_session"] < 3].groupby("date")["low"].min()
    bars["OR_high"] = bars["date"].map(orh)
    bars["OR_low"] = bars["date"].map(orl)
    return bars


def build_trigger(bars: pd.DataFrame, mode: str) -> dict[str, pd.Series]:
    """返回 {direction: boolean mask}，True=该 bar 触发开仓（方向已含）。"""
    if mode == "baseline":
        return {"long": pd.Series(True, index=bars.index),
                "short": pd.Series(True, index=bars.index)}
    if mode == "boll":
        long = bars["close"] <= bars["BB_low"]
        short = bars["close"] >= bars["BB_up"]
    elif mode == "macd":
        long = (bars["DIF"] > bars["DEA"]) & (bars["DIF_prev"] <= bars["DEA_prev"])
        short = (bars["DIF"] < bars["DEA"]) & (bars["DIF_prev"] >= bars["DEA_prev"])
    elif mode == "kdj":
        long = (bars["K"] > bars["D"]) & (bars["K_prev"] <= bars["D_prev"]) & (bars["K"] < 20)
        short = (bars["K"] < bars["D"]) & (bars["K_prev"] >= bars["D_prev"]) & (bars["K"] > 80)
    elif mode == "rsi":
        long = bars["RSI"] < 30
        short = bars["RSI"] > 70
    elif mode == "breakout":
        long = bars["close"] > bars["HH20"]
        short = bars["close"] < bars["LL20"]
    elif mode == "prevhi":
        long = bars["close"] > bars["PH_prev"]
        short = bars["close"] < bars["PL_prev"]
    elif mode == "openrange":
        long = (bars["bar_in_session"] >= 3) & (bars["close"] > bars["OR_high"])
        short = (bars["bar_in_session"] >= 3) & (bars["close"] < bars["OR_low"])
    else:
        raise ValueError(mode)
    return {"long": long.fillna(False), "short": short.fillna(False)}


# =====================================================================
# 逐合约模拟（按 mode）
# =====================================================================
def simulate_mode(contract: str, g: pd.DataFrame, mode: str,
                  bars_cache: dict) -> list[dict]:
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    csv_path = MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not csv_path.exists():
        return []

    if contract not in bars_cache:
        b = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.sort_values("datetime").reset_index(drop=True)
        if b.empty:
            bars_cache[contract] = None
        else:
            bars_cache[contract] = add_indicators(b)
    bars = bars_cache[contract]
    if bars is None:
        return []

    trig = build_trigger(bars, mode)
    rows: list[dict] = []
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
            fut_idx = bars.index[idx: idx + H * 12]
            mask = trig[direction].loc[fut_idx]
            if not mask.any():
                continue  # 窗口内未触发 → 跳过该事件
            entry_idx = mask.idxmax()
        bar = bars.loc[entry_idx]
        entry_price = float(bar["close"])
        if entry_price <= 0:
            continue
        atr_price = entry_price * atr_bps / 10000.0
        stop_price = entry_price - sign * K * atr_price
        stop_dist_frac = K * atr_bps / 10000.0
        notional_frac = P1.RISK_PER_TRADE / stop_dist_frac
        qty_raw = notional_frac * P1.EQUITY_INIT / (entry_price * spec.size)

        future = bars.iloc[entry_idx: entry_idx + H * 12]
        if len(future) == 0:
            continue
        exit_price = np.nan
        exit_reason = "TIME"
        exit_bar = future.iloc[-1]["datetime"]
        for _, fb in future.iterrows():
            if sign == 1 and fb["low"] <= stop_price:
                exit_price = stop_price
                exit_reason = "SL"
                exit_bar = fb["datetime"]
                break
            if sign == -1 and fb["high"] >= stop_price:
                exit_price = stop_price
                exit_reason = "SL"
                exit_bar = fb["datetime"]
                break
        if np.isnan(exit_price):
            exit_price = float(future.iloc[-1]["close"])
            exit_bar = future.iloc[-1]["datetime"]

        cost_e = P1.cost_oneway_bps(spec, entry_price, qty_raw)
        cost_x = P1.cost_oneway_bps(spec, exit_price, qty_raw)
        gross = sign * (exit_price - entry_price) / entry_price
        pnl_gross_bps = gross * 10000.0
        pnl_net_bps = pnl_gross_bps - cost_e - cost_x
        notional_ccy = qty_raw * entry_price * spec.size
        pnl_net_ccy = pnl_net_bps / 10000.0 * notional_ccy

        sym = (P1.extract_contract_prefix(contract) or "").lower()
        rows.append({
            "contract": contract, "symbol": sym,
            "symbol_type": P1.SYMBOL_TYPE.get(sym, "C"),
            "entry_bar": bar["datetime"], "exit_bar": exit_bar,
            "direction": int(sign), "tier": ev["tier_v40"],
            "entry_price": entry_price, "exit_price": exit_price,
            "exit_reason": exit_reason, "entry_atr_bps": atr_bps,
            "qty_raw": qty_raw, "qty_actual": qty_raw,
            "pnl_gross_bps": pnl_gross_bps, "cost_entry_bps": cost_e,
            "cost_exit_bps": cost_x, "pnl_net_bps": pnl_net_bps,
            "pnl_net_ccy": pnl_net_ccy,
            "_notional_frac": notional_frac,
            "_entry_date": bar["datetime"].date(),
            "_exit_date": pd.Timestamp(exit_bar).date(),
        })
    return rows


# =====================================================================
# 指标封装
# =====================================================================
def metrics(t: pd.DataFrame) -> dict:
    m = P1.base_metrics(t)
    m["monthly_win"] = P1.monthly_win_rate(t)
    m["ir"] = P1.per_trade_ir(t)
    m["nu_implied"], m["p_nu_pos"] = P1.nu_implied(t)
    return m


# =====================================================================
# 主流程
# =====================================================================
def main() -> None:
    print("=" * 70)
    print(f"va-composite · Phase 2 · entry_mode 粗筛  [Cap 定档={CAP_FWD}]")
    print("=" * 70)

    print("[1/5] 加载 timeline + 构建信号...")
    events = P1.load_events()
    print(f"      A 级去重后事件: {len(events)} | 合约: {events['contract'].nunique()} | "
          f"多:{(events['direction']=='long').sum()} 空:{(events['direction']=='short').sum()}")

    print("[2/5] 逐 mode 模拟（5m 指标预计算 + 入场扫描）...")
    bars_cache: dict = {}
    results: dict = {}
    for mode in MODES:
        all_rows: list[dict] = []
        for contract, g in events.groupby("contract"):
            all_rows.extend(simulate_mode(contract, g, mode, bars_cache))
        raw = pd.DataFrame(all_rows)
        t5 = P1.assign_equity(P1.compress(raw, CAP_FWD))
        t1 = P1.assign_equity(P1.compress(raw, 1.0))
        n_evt = len(events)
        n_trg = len(raw)
        results[mode] = {
            "raw": raw, "t5": t5, "t1": t1,
            "m5": metrics(t5), "m1": metrics(t1),
            "n_trg": n_trg, "trigger_rate": n_trg / n_evt,
        }
        m5 = results[mode]["m5"]
        print(f"      {mode:>9}: 触发 {n_trg:>3}/{n_evt} ({n_trg/n_evt*100:4.1f}%)  "
              f"年化 {m5['ann_ret']*100:6.2f}%  夏普 {m5['sharpe']:6.2f}  MaxDD {m5['max_dd']*100:6.2f}%")

    base5 = results["baseline"]["t5"]
    base1 = results["baseline"]["t1"]

    print("[3/5] 配对增量评估（隔离 Cap 恒定 + 对照 B0）...")
    rows = []
    for mode in MODES[1:]:
        iso = P1.paired_delta(base5, results[mode]["t5"])      # 隔离择时效应
        vsb = P1.paired_delta(base1, results[mode]["t5"])      # 含 Cap 效应（对照）
        adopted = (iso["dsharpe"] >= 0.2) and (iso["p_nu_pos"] >= 0.95)
        rows.append((mode, iso, vsb, adopted))
        print(f"      {mode:>9}: 隔离ΔSharpe={iso['dsharpe']:+.2f} P={iso['p_nu_pos']:.3f} | "
              f"vsB0 ΔSharpe={vsb['dsharpe']:+.2f} P={vsb['p_nu_pos']:.3f}  "
              f"=> {'存活 ✅' if adopted else '淘汰 ❌'}")

    print("[4/5] 写明细 + summary...")
    out_cols = ["contract", "symbol", "symbol_type", "entry_bar", "exit_bar", "direction", "tier",
                "entry_price", "exit_price", "exit_reason", "entry_atr_bps", "qty_raw", "qty_actual",
                "pnl_gross_bps", "cost_entry_bps", "cost_exit_bps",
                "pnl_net_bps", "pnl_net_ccy", "equity_before", "equity_after"]
    for mode in MODES:
        results[mode]["t5"][out_cols].to_parquet(OUT_DIR / f"{mode}.trades.parquet", index=False)
    _write_summary(results, rows, base5, base1)

    survivors = [m for m, _, _, a in rows if a]
    print()
    if survivors:
        print(f"Phase 2 粗筛存活: {survivors} → 进入 P2 细化（per-tier 风味映射校准）")
    else:
        print("Phase 2 粗筛: 0/N 存活 —— 按 §3 回溯协议，择时是弱轴，回到 P0.4 复核信号质量，非 mode 没选对。")


def _write_summary(results, paired_rows, base5, base1) -> None:
    L = []
    L.append("# va-asymmetry-composite · Phase 2 · entry_mode 粗筛报告")
    L.append("")
    L.append(f"> Cap 定档 = {CAP_FWD}（P1 用户指定）。基线 = 同 Cap baseline；对照 = 冻结 B0(Cap=1.0)。")
    L.append("> 入场价口径：P2 内所有 mode（含 baseline）统一用「触发 5m bar 收盘」，保证配对公平。")
    L.append("")
    L.append("## 1. 各 mode 主指标（Cap=5.0）")
    L.append("")
    L.append("| mode | 触发率 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) |")
    L.append("|:---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for mode in MODES:
        r = results[mode]
        m = r["m5"]
        L.append(f"| {mode} | {r['trigger_rate']*100:.1f}% | {m['ann_ret']*100:.2f}% | {m['sharpe']:.2f} | "
                 f"{m['max_dd']*100:.2f}% | {m['monthly_win']*100:.1f}% | {m['ir']:.3f} | "
                 f"{m['nu_implied']:.3f} | {m['p_nu_pos']:.3f} |")
    L.append("")
    L.append("## 2. 配对增量（门限判定用「隔离」列）")
    L.append("")
    L.append("§0.1 门限：隔离 ΔSharpe ≥ 0.2 **且** P(μ_true>0) ≥ 0.95。")
    L.append("")
    L.append("| mode | 隔离ΔSharpe | 隔离μ_true | 隔离P(μ>0) | vsB0ΔSharpe | vsB0 P(μ>0) | 判定 |")
    L.append("|:---|---:|---:|---:|---:|---:|:---:|")
    for mode, iso, vsb, adopted in paired_rows:
        L.append(f"| {mode} | {iso['dsharpe']:+.2f} | {iso['nu_true']*100:+.3f}% | {iso['p_nu_pos']:.3f} | "
                 f"{vsb['dsharpe']:+.2f} | {vsb['p_nu_pos']:.3f} | {'存活 ✅' if adopted else '淘汰 ❌'} |")
    L.append("")
    L.append("## 3. 解读（§3 / 研究备忘）")
    L.append("")
    surv = [m for m, _, _, a in paired_rows if a]
    if surv:
        L.append(f"- 存活 mode: **{surv}**。这些在「同 Cap 下」相对 baseline 显著改善风险调整收益，"
                 "说明择时是**有效杠杆**（区别于 Cap 的纯杠杆），门限被正确施加。")
        L.append("- 下一步：对存活 mode 按 spec §3.1.2 风味映射做 per-tier 校准"
                 "（如 L_seg3 动量类用 macd/breakout/prevhi；S_* 反转类用 boll/kdj/rsi）。")
    else:
        L.append("- **0/N 存活**：整体套用下无 mode 过门，说明「统一择时」是弱轴——问题在上游信号/事件选择"
                 "（呼应备忘：0/N 不增夏普 → 首要假设是轴选错，非 mode 没选对），回到 P0.4 复核，不进细化。")
    L.append("")
    L.append("> 注：「隔离」列隔离了 Cap 效应（mode 与 baseline 同为 Cap=5.0），是择时增量的诚实读数；"
             "「vsB0」列含 Cap 效应，仅作与冻结 B0 的参照。")
    L.append("")
    (OUT_DIR / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"      写出: {OUT_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
