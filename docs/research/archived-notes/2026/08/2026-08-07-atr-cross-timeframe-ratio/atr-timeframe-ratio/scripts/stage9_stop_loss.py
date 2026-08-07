"""
ATR 跨周期比值研究 · Stage 9: 带止损/止盈的改进版回测
=====================================================

基于 Stage 8 结论：
- 短脉冲策略 +0.07%，CI 含 0，路径盈亏比仅 1.13；
- 第 3 根平仓规则误杀率高；
- 持有到期的 208 笔 +0.15% 优于被平仓的 168 笔 -0.02%。

改进：
1. 加入固定百分比止损（-0.5%, -1%, -1.5%, -2%）；
2. 加入可选止盈（+1%, +2%, +3%）；
3. 加入 ATR 止损（入场价 - k * ATR_1h）；
4. 对比多种组合，寻找最优退出规则；
5. 仍保持 t 时刻可执行，不用未来信息。

入场规则不变：每段 H_only 首根收盘买入。
退出规则（按优先级）：
  a. 止损触发（盘中 low <= 止损价）；
  b. 止盈触发（盘中 high >= 止盈价）；
  c. 持仓到期（t+20 收盘）；
  d. 可选：第 3 根仍 H_only 则平仓（保留对比）。

输出：outputs/stage9/
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[5]
SCRIPT_DIR = Path(__file__).resolve().parents[1]
PANEL_PATH = SCRIPT_DIR / "outputs" / "stage6" / "stage6_expanded_panel.parquet"
OUT_DIR = SCRIPT_DIR / "outputs" / "stage9"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BOOT_N = 1000
BOOT_SEED = 42
MAX_HOLD = 20


def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(BOOT_SEED)
    mask = ~np.isnan(values)
    values, clusters = values[mask], clusters[mask]
    if len(values) == 0:
        return np.nan, np.nan
    uniq = np.unique(clusters)
    idx_map = {c: np.where(clusters == c)[0] for c in uniq}
    stats = np.empty(BOOT_N)
    for i in range(BOOT_N):
        sampled = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_map[c] for c in sampled])
        stats[i] = values[idx].mean()
    return float(np.nanpercentile(stats, 2.5)), float(np.nanpercentile(stats, 97.5))


def find_entries(panel: pd.DataFrame) -> pd.DataFrame:
    """找每段 H_only 的首根入场点。"""
    panel = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    is_h = panel["state_S"] == "H_only"
    prev_is_h = is_h.shift(1).fillna(False)
    sym_change = panel["symbol"] != panel["symbol"].shift(1)
    prev_is_h = prev_is_h & ~sym_change
    new_ep = is_h & ~prev_is_h
    entries = panel[new_ep].copy()
    return entries


def simulate_trade(
    entry_row: pd.Series,
    sym_panel: pd.DataFrame,
    pos: int,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    atr_stop_mult: float | None = None,
    use_3rd_bar_exit: bool = False,
    max_hold: int = MAX_HOLD,
) -> dict | None:
    """模拟单笔交易。sym_panel 已包含 high/low 列。"""
    entry_price = entry_row["close"]
    entry_atr = entry_row["H"]
    entry_dt = entry_row["datetime"]

    stop_price = None
    if stop_loss_pct is not None:
        stop_price = entry_price * (1 - stop_loss_pct)
    if atr_stop_mult is not None:
        atr_stop = entry_price - atr_stop_mult * entry_atr
        stop_price = max(stop_price or 0, atr_stop) if stop_price is not None else atr_stop

    tp_price = entry_price * (1 + take_profit_pct) if take_profit_pct is not None else None

    exit_price = None
    exit_reason = None
    hold_bars = 0
    max_seen = entry_price
    min_seen = entry_price

    for k in range(1, max_hold + 1):
        idx = pos + k
        if idx >= len(sym_panel):
            return None

        bar = sym_panel.iloc[idx]
        bar_high = bar["high"]
        bar_low = bar["low"]
        max_seen = max(max_seen, bar_high)
        min_seen = min(min_seen, bar_low)

        if use_3rd_bar_exit and k == 2 and bar["state_S"] == "H_only":
            exit_price = bar["close"]
            exit_reason = "3rd_bar_H_only"
            hold_bars = k
            break

        if stop_price is not None and bar_low <= stop_price:
            exit_price = stop_price
            exit_reason = "stop_loss"
            hold_bars = k
            break

        if tp_price is not None and bar_high >= tp_price:
            exit_price = tp_price
            exit_reason = "take_profit"
            hold_bars = k
            break

        hold_bars = k

    if exit_price is None:
        exit_idx = pos + max_hold
        if exit_idx >= len(sym_panel):
            return None
        exit_price = sym_panel.iloc[exit_idx]["close"]
        exit_reason = "hold_end"

    max_ret = max_seen / entry_price - 1
    min_ret = min_seen / entry_price - 1

    exit_dt = sym_panel.iloc[min(pos + hold_bars, len(sym_panel)-1)]["datetime"]
    return {
        "symbol": entry_row["symbol"],
        "sector": entry_row["sector"],
        "entry_time": entry_dt,
        "exit_time": exit_dt,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "gross_ret": exit_price / entry_price - 1,
        "hold_bars": hold_bars,
        "exit_reason": exit_reason,
        "max_ret": max_ret,
        "min_ret": min_ret,
        "MADEV_60": entry_row.get("MADEV_60", np.nan),
        "trend_strength": entry_row.get("trend_strength", np.nan),
        "date": entry_row["date"],
        "entry_atr": entry_atr,
    }


def run_backtest(
    panel: pd.DataFrame,
    entries: pd.DataFrame,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    atr_stop_mult: float | None = None,
    use_3rd_bar_exit: bool = False,
    use_filter: bool = False,
    label: str = "",
) -> pd.DataFrame:
    """运行一组回测参数。"""
    ohlc_cache = {}

    def get_ohlc(sym):
        if sym not in ohlc_cache:
            f1h = ROOT / "project_data" / "market_data" / "csv" / f"{sym}.tqsdk.1h.csv"
            if f1h.exists():
                ohlc_cache[sym] = pd.read_csv(f1h, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
            else:
                ohlc_cache[sym] = pd.DataFrame(columns=["datetime", "high", "low"])
        return ohlc_cache[sym]

    if use_filter:
        entries = entries[entries["MADEV_60"] < 0].copy()

    trades = []
    for _, entry in entries.iterrows():
        sym = entry["symbol"]
        sym_panel = panel[panel["symbol"] == sym].sort_values("datetime").reset_index(drop=True)
        ohlc = get_ohlc(sym)
        pos_arr = sym_panel.index[sym_panel["datetime"] == entry["datetime"]]
        if len(pos_arr) == 0:
            continue
        pos = pos_arr[0]

        trade = simulate_trade(
            entry, sym_panel, ohlc, pos,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            atr_stop_mult=atr_stop_mult,
            use_3rd_bar_exit=use_3rd_bar_exit,
        )
        if trade is not None:
            trade["label"] = label
            trades.append(trade)

    return pd.DataFrame(trades)


def performance_stats(trades: pd.DataFrame, cost_bp: float = 0) -> dict:
    if len(trades) == 0:
        return {"n_trades": 0}
    rets = trades["gross_ret"].values - cost_bp / 10000.0
    n = len(rets)
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    ci_lo, ci_hi = cluster_bootstrap_ci(rets, trades["date"].values)
    avg_hold = float(trades["hold_bars"].mean()) if "hold_bars" in trades.columns else MAX_HOLD
    trades_per_year = 252 * 6 / avg_hold if avg_hold > 0 else 1
    std = float(np.std(rets, ddof=1)) if n > 1 else np.nan
    mean = float(np.mean(rets))
    pf = float(wins.sum() / np.abs(losses).sum()) if len(losses) and np.abs(losses).sum() > 0 else np.inf

    # exit reason counts
    exit_counts = trades["exit_reason"].value_counts().to_dict() if "exit_reason" in trades.columns else {}

    return {
        "n_trades": n,
        "win_rate": float((rets > 0).mean()),
        "mean_ret": mean,
        "median_ret": float(np.median(rets)),
        "std_ret": std,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "avg_win": float(np.mean(wins)) if len(wins) else np.nan,
        "avg_loss": float(np.mean(np.abs(losses))) if len(losses) else np.nan,
        "profit_factor": pf,
        "avg_hold_bars": avg_hold,
        "annual_ret_approx": mean * trades_per_year,
        "sharpe_approx": mean / std * np.sqrt(trades_per_year) if std and std > 0 else np.nan,
        "exit_hold_end": exit_counts.get("hold_end", 0),
        "exit_stop_loss": exit_counts.get("stop_loss", 0),
        "exit_take_profit": exit_counts.get("take_profit", 0),
        "exit_3rd_bar": exit_counts.get("3rd_bar_H_only", 0),
    }


def main() -> None:
    panel = pd.read_parquet(PANEL_PATH)
    panel = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    entries = find_entries(panel)
    print(f"面板: {len(panel)} 行, 入场点: {len(entries)}", flush=True)

    # 预加载所有 OHLC 并 merge high/low 到 sym_panel
    print("预加载 OHLC...", flush=True)
    sym_panels = {}
    for sym in panel["symbol"].unique():
        sym_df = panel[panel["symbol"] == sym].sort_values("datetime").reset_index(drop=True).copy()
        f1h = ROOT / "project_data" / "market_data" / "csv" / f"{sym}.tqsdk.1h.csv"
        if f1h.exists():
            ohlc = pd.read_csv(f1h, parse_dates=["datetime"])[["datetime", "high", "low"]]
            sym_df = sym_df.merge(ohlc, on="datetime", how="left")
            sym_df["high"] = sym_df["high"].fillna(sym_df["close"])
            sym_df["low"] = sym_df["low"].fillna(sym_df["close"])
        else:
            sym_df["high"] = sym_df["close"]
            sym_df["low"] = sym_df["close"]
        sym_panels[sym] = sym_df
    print(f"已加载 {len(sym_panels)} 个合约", flush=True)

    def run_fast(stop_loss_pct=None, take_profit_pct=None, atr_stop_mult=None,
                 use_3rd_bar_exit=False, use_filter=False, label=""):
        ents = entries[entries["MADEV_60"] < 0].copy() if use_filter else entries
        trades = []
        for _, entry in ents.iterrows():
            sym = entry["symbol"]
            sym_panel = sym_panels[sym]
            pos_arr = sym_panel.index[sym_panel["datetime"] == entry["datetime"]]
            if len(pos_arr) == 0:
                continue
            pos = pos_arr[0]
            trade = simulate_trade(
                entry, sym_panel, pos,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                atr_stop_mult=atr_stop_mult,
                use_3rd_bar_exit=use_3rd_bar_exit,
            )
            if trade is not None:
                trade["label"] = label
                trades.append(trade)
        return pd.DataFrame(trades)

    # ============================================================
    # 1. 止损参数扫描（固定持仓 20 根，不用第 3 根平仓）
    # ============================================================
    print("\n=== 1. 固定止损扫描（持仓 20 根，无第 3 根平仓）===")
    stop_configs = [
        ("no_stop", None, None, None),
        ("stop_0.5%", 0.005, None, None),
        ("stop_1.0%", 0.010, None, None),
        ("stop_1.5%", 0.015, None, None),
        ("stop_2.0%", 0.020, None, None),
        ("atr_stop_1.5", None, None, 1.5),
        ("atr_stop_2.0", None, None, 2.0),
        ("atr_stop_3.0", None, None, 3.0),
    ]

    stop_rows = []
    all_trades = {}
    for label, sl, tp, atr in stop_configs:
        trades = run_fast(stop_loss_pct=sl, take_profit_pct=tp,
                          atr_stop_mult=atr, label=label)
        all_trades[label] = trades
        s = performance_stats(trades)
        s["label"] = label
        stop_rows.append(s)
        print(f"  {label:15s}: n={s['n_trades']:4d}  win={s['win_rate']:.1%}  "
              f"ret={s['mean_ret']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  "
              f"PF={s['profit_factor']:.2f}  Sharpe={s['sharpe_approx']:.2f}  "
              f"SL={s['exit_stop_loss']:3d}  TP={s['exit_take_profit']:3d}  hold={s['exit_hold_end']:3d}", flush=True)

    stop_df = pd.DataFrame(stop_rows)
    stop_df.to_csv(OUT_DIR / "stage9_stop_loss_scan.csv", index=False)

    # ============================================================
    # 2. 止损 + 止盈组合
    # ============================================================
    print("\n=== 2. 止损 + 止盈组合 ===")
    tp_configs = [
        ("SL1.0%_TP1%", 0.010, 0.01, None),
        ("SL1.0%_TP2%", 0.010, 0.02, None),
        ("SL1.0%_TP3%", 0.010, 0.03, None),
        ("SL1.5%_TP2%", 0.015, 0.02, None),
        ("SL1.5%_TP3%", 0.015, 0.03, None),
        ("SL0.5%_TP1%", 0.005, 0.01, None),
        ("atr2_TP2%",    None,  0.02, 2.0),
        ("atr2_TP3%",    None,  0.03, 2.0),
        ("atr1.5_TP2%",  None,  0.02, 1.5),
    ]

    tp_rows = []
    for label, sl, tp, atr in tp_configs:
        trades = run_fast(stop_loss_pct=sl, take_profit_pct=tp,
                          atr_stop_mult=atr, label=label)
        all_trades[label] = trades
        s = performance_stats(trades)
        s["label"] = label
        tp_rows.append(s)
        print(f"  {label:15s}: n={s['n_trades']:4d}  win={s['win_rate']:.1%}  "
              f"ret={s['mean_ret']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  "
              f"PF={s['profit_factor']:.2f}  Sharpe={s['sharpe_approx']:.2f}  "
              f"SL={s['exit_stop_loss']:3d}  TP={s['exit_take_profit']:3d}  hold={s['exit_hold_end']:3d}", flush=True)

    tp_df = pd.DataFrame(tp_rows)
    tp_df.to_csv(OUT_DIR / "stage9_stop_take_profit.csv", index=False)

    # ============================================================
    # 3. 最优配置 + MADEV60<0 过滤
    # ============================================================
    print("\n=== 3. 最优配置 + MADEV60<0 过滤 ===")
    best_configs = [
        ("SL1.0%_no_filter", 0.010, None, None, False),
        ("SL1.0%_MADEV<0",   0.010, None, None, True),
        ("SL1.5%_TP2%_no_filter", 0.015, 0.02, None, False),
        ("SL1.5%_TP2%_MADEV<0",   0.015, 0.02, None, True),
        ("atr2_no_filter",  None, None, 2.0, False),
        ("atr2_MADEV<0",    None, None, 2.0, True),
        ("atr2_TP2%_no_filter", None, 0.02, 2.0, False),
        ("atr2_TP2%_MADEV<0",   None, 0.02, 2.0, True),
        # 对比：无止损（Stage 8 基准）
        ("no_stop_no_filter", None, None, None, False),
        ("no_stop_MADEV<0",   None, None, None, True),
    ]

    filt_rows = []
    for label, sl, tp, atr, use_f in best_configs:
        trades = run_fast(stop_loss_pct=sl, take_profit_pct=tp,
                          atr_stop_mult=atr, use_filter=use_f, label=label)
        all_trades[label] = trades
        s = performance_stats(trades)
        s["label"] = label
        s["MADEV60_filter"] = use_f
        filt_rows.append(s)
        print(f"  {label:25s}: n={s['n_trades']:4d}  win={s['win_rate']:.1%}  "
              f"ret={s['mean_ret']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  "
              f"PF={s['profit_factor']:.2f}  Sharpe={s['sharpe_approx']:.2f}", flush=True)

    filt_df = pd.DataFrame(filt_rows)
    filt_df.to_csv(OUT_DIR / "stage9_best_with_filter.csv", index=False)

    # ============================================================
    # 4. 成本敏感性（选最优 2 个配置）
    # ============================================================
    print("\n=== 4. 成本敏感性 ===")
    cost_rows = []
    for label in ["SL1.0%_MADEV<0", "atr2_TP2%_MADEV<0", "no_stop_MADEV<0"]:
        trades = all_trades.get(label)
        if trades is None or len(trades) == 0:
            continue
        for bp in [0, 1, 2, 3]:
            s = performance_stats(trades, cost_bp=bp)
            s["label"] = label
            s["cost_bp"] = bp
            cost_rows.append(s)
    cost_df = pd.DataFrame(cost_rows)
    cost_df.to_csv(OUT_DIR / "stage9_cost_sensitivity.csv", index=False)
    for _, r in cost_df.iterrows():
        print(f"  {r['label']:25s} cost={r['cost_bp']}bp  n={r['n_trades']:4d}  "
              f"ret={r['mean_ret']:.4f}  CI=[{r['ci_lo']:.4f},{r['ci_hi']:.4f}]  "
              f"PF={r['profit_factor']:.2f}")

    # ============================================================
    # 5. 最优配置的退出原因分布和板块
    # ============================================================
    best_label = "SL1.0%_MADEV<0"
    if best_label in all_trades and len(all_trades[best_label]) > 0:
        best_trades = all_trades[best_label]
        print(f"\n=== 5. {best_label} 退出原因分布 ===")
        print(best_trades["exit_reason"].value_counts())

        print(f"\n=== 6. {best_label} 按板块 ===")
        for sec, sub in best_trades.groupby("sector"):
            s = performance_stats(sub)
            print(f"  {sec:6s}: n={s['n_trades']:3d}  win={s['win_rate']:.1%}  "
                  f"ret={s['mean_ret']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]")

        best_trades.to_csv(OUT_DIR / "trades_best_config.csv", index=False)

    # ============================================================
    # 7. 随机基准（带同样止损）
    # ============================================================
    print("\n=== 7. 随机基准（SL1.0%）===", flush=True)
    rng = np.random.default_rng(BOOT_SEED)
    random_trades_list = []
    for sym in sym_panels:
        sym_panel = sym_panels[sym]
        valid = len(sym_panel) - MAX_HOLD
        if valid < 10:
            continue
        n_per = max(1, min(30, valid))
        positions = rng.choice(valid, size=n_per, replace=False)
        for pos in positions:
            entry_row = sym_panel.iloc[pos]
            trade = simulate_trade(entry_row, sym_panel, pos,
                                   stop_loss_pct=0.010, take_profit_pct=None,
                                   atr_stop_mult=None, use_3rd_bar_exit=False)
            if trade:
                random_trades_list.append(trade)
    rand_trades = pd.DataFrame(random_trades_list)
    rand_s = performance_stats(rand_trades)
    print(f"  random_SL1.0%: n={rand_s['n_trades']:4d}  win={rand_s['win_rate']:.1%}  "
          f"ret={rand_s['mean_ret']:.4f}  CI=[{rand_s['ci_lo']:.4f},{rand_s['ci_hi']:.4f}]  "
          f"PF={rand_s['profit_factor']:.2f}", flush=True)

    # summary
    summary = {
        "n_entries": int(len(entries)),
        "stop_scan": stop_df[["label", "n_trades", "win_rate", "mean_ret", "ci_lo", "ci_hi",
                              "profit_factor", "sharpe_approx"]].to_dict("records"),
        "tp_scan": tp_df[["label", "n_trades", "win_rate", "mean_ret", "ci_lo", "ci_hi",
                          "profit_factor", "sharpe_approx"]].to_dict("records"),
        "best_filtered": filt_df[["label", "n_trades", "win_rate", "mean_ret", "ci_lo", "ci_hi",
                                  "profit_factor", "sharpe_approx"]].to_dict("records"),
        "random_SL1pct": rand_s,
    }
    with open(OUT_DIR / "stage9_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nStage 9 输出已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
