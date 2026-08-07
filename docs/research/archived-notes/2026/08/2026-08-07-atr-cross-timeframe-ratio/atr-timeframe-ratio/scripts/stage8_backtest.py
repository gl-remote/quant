"""
ATR 跨周期比值研究 · Stage 8: 短脉冲做多策略原型回测
=====================================================

基于 Stage 7 结论：
- H_only 首根入场（不等 confirmed）；
- 只做短脉冲：第 3 根若状态仍为 H_only，平仓（说明是中长期 H_only，不赚钱）；
- 若第 2-3 根状态离开 H_only，持有到目标周期；
- 主要方向：MADEV_60 < 0 时做多（超卖反弹）；
- 持仓周期：20 根（或提前止损/止盈）。

t 时刻可执行规则：
- 入场：当根 state_S == H_only，且这是 H_only episode 的第 1 根（前一根 != H_only）；
- 第 3 根平仓：入场后第 2 根（0-indexed）若 state_S 仍是 H_only，收盘价平仓；
- 否则持有到第 20 根收盘价平仓；
- 可选过滤：MADEV_60 < 0；
- 可选止损：入场价 - k * ATR。

对比基准：
- buy & hold（每段 H_only 首根入场，持有 20 根，不管后续状态）；
- 等 confirmed 再入场（第 6 根才入场，持有 20 根）；
- 随机入场（随机选 1h bar，持有 20 根，作为基准）。

输出：outputs/stage8/
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
OUT_DIR = SCRIPT_DIR / "outputs" / "stage8"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BOOT_N = 1000
BOOT_SEED = 42
COST_BPS = [0, 1, 2, 3]


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
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def build_trades(panel: pd.DataFrame, use_filter: bool = False) -> pd.DataFrame:
    """模拟短脉冲策略，逐 bar 回放，生成交易记录。

    规则（t 时刻可执行）：
    1. 入场：当根 state_S == H_only 且前一根 != H_only（H_only episode 首根）；
       若 use_filter，还要 MADEV_60 < 0；
    2. 检查第 3 根：入场后第 2 根（t+2）若 state_S 仍为 H_only，按收盘价平仓；
    3. 否则持有到 t+20 收盘价平仓；
    """
    panel = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)

    # 重新计算 H_only 专属 episode_id
    # 注意：不用 groupby("symbol").shift(1)，因为 ArrowStringArray 在某些 pandas 版本
    # 下 groupby shift 行为异常。用已排序的 panel 直接 shift + 手动处理 symbol 边界。
    is_h_only = panel["state_S"] == "H_only"
    prev_is_h = is_h_only.shift(1).fillna(False)
    sym_change = panel["symbol"] != panel["symbol"].shift(1)
    prev_is_h = prev_is_h & ~sym_change
    new_episode = is_h_only & ~prev_is_h
    panel["h_only_episode"] = new_episode.cumsum().where(is_h_only)

    # 加载 high/low（stage6 面板没有，从 1h CSV 读）
    ohlc_cache = {}

    def get_ohlc(sym: str) -> pd.DataFrame:
        if sym not in ohlc_cache:
            f1h = ROOT / "project_data" / "market_data" / "csv" / f"{sym}.tqsdk.1h.csv"
            if f1h.exists():
                ohlc = pd.read_csv(f1h, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
            else:
                ohlc = pd.DataFrame(columns=["datetime", "high", "low"])
            ohlc_cache[sym] = ohlc
        return ohlc_cache[sym]

    # 找入场点：每段 H_only 的第一根
    entries = (
        panel[is_h_only & new_episode]
        .copy()
        .sort_values(["symbol", "datetime"])
        .groupby(["symbol", "h_only_episode"], as_index=False)
        .first()
    )

    if use_filter:
        entries = entries[entries["MADEV_60"] < 0].copy()

    trades = []
    for _, entry in entries.iterrows():
        sym = entry["symbol"]
        sym_panel = panel[panel["symbol"] == sym].sort_values("datetime").reset_index(drop=True)
        ohlc = get_ohlc(sym)
        pos = sym_panel.index[sym_panel["datetime"] == entry["datetime"]]
        if len(pos) == 0:
            continue
        pos = pos[0]

        entry_price = entry["close"]

        if pos + 2 < len(sym_panel):
            state_t2 = sym_panel.iloc[pos + 2]["state_S"]
        else:
            state_t2 = None

        if state_t2 == "H_only":
            exit_idx = pos + 2
            if exit_idx >= len(sym_panel):
                continue
            exit_price = sym_panel.iloc[exit_idx]["close"]
            exit_reason = "3rd_bar_H_only"
            hold_bars = 2
        else:
            exit_idx = pos + 20
            if exit_idx >= len(sym_panel):
                continue
            exit_price = sym_panel.iloc[exit_idx]["close"]
            exit_reason = "hold_20"
            hold_bars = 20

        # 路径分析
        if len(ohlc) > 0 and "high" in ohlc.columns:
            entry_dt = entry["datetime"]
            exit_dt = sym_panel.iloc[exit_idx]["datetime"]
            path_ohlc = ohlc[(ohlc["datetime"] > entry_dt) & (ohlc["datetime"] <= exit_dt)]
            if len(path_ohlc) > 0:
                max_price = path_ohlc["high"].max()
                min_price = path_ohlc["low"].min()
            else:
                max_price, min_price = exit_price, entry_price
        else:
            path = sym_panel.iloc[pos + 1 : exit_idx + 1]
            max_price = path["close"].max()
            min_price = path["close"].min()

        gross_ret = exit_price / entry_price - 1
        trades.append({
            "symbol": sym,
            "sector": entry["sector"],
            "entry_time": entry["datetime"],
            "exit_time": sym_panel.iloc[exit_idx]["datetime"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gross_ret": gross_ret,
            "hold_bars": hold_bars,
            "exit_reason": exit_reason,
            "max_ret": max_price / entry_price - 1,
            "min_ret": min_price / entry_price - 1,
            "MADEV_60": entry["MADEV_60"],
            "trend_strength": entry["trend_strength"],
            "vol_ratio": entry.get("vol_ratio", np.nan),
            "state_t2": state_t2,
            "outcome": entry["H_only_outcome"],
            "date": entry["date"],
        })

    return pd.DataFrame(trades)


def build_buyhold_trades(panel: pd.DataFrame) -> pd.DataFrame:
    """基准：每段 H_only 首根入场，持有 20 根，不管后续状态。"""
    panel = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    is_h_only = panel["state_S"] == "H_only"
    prev_is_h = is_h_only.shift(1).fillna(False)
    sym_change = panel["symbol"] != panel["symbol"].shift(1)
    prev_is_h = prev_is_h & ~sym_change
    new_episode = is_h_only & ~prev_is_h
    entries = panel[new_episode].copy()

    trades = []
    for _, entry in entries.iterrows():
        sym = entry["symbol"]
        sym_panel = panel[panel["symbol"] == sym].sort_values("datetime").reset_index(drop=True)
        pos = sym_panel.index[sym_panel["datetime"] == entry["datetime"]]
        if len(pos) == 0:
            continue
        pos = pos[0]
        exit_idx = pos + 20
        if exit_idx >= len(sym_panel):
            continue
        exit_price = sym_panel.iloc[exit_idx]["close"]
        trades.append({
            "symbol": sym, "sector": entry["sector"],
            "entry_time": entry["datetime"], "exit_time": sym_panel.iloc[exit_idx]["datetime"],
            "gross_ret": exit_price / entry["close"] - 1,
            "hold_bars": 20, "exit_reason": "buyhold_20",
            "date": entry["date"],
        })
    return pd.DataFrame(trades)


def build_confirmed_trades(panel: pd.DataFrame) -> pd.DataFrame:
    """基准：等 5 根 confirmed 后入场（t+5），持有 20 根。"""
    panel = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    is_h_only = panel["state_S"] == "H_only"
    prev_is_h = is_h_only.shift(1).fillna(False)
    sym_change = panel["symbol"] != panel["symbol"].shift(1)
    prev_is_h = prev_is_h & ~sym_change
    new_episode = is_h_only & ~prev_is_h
    first_bars = panel[new_episode].copy()

    trades = []
    for _, entry in first_bars.iterrows():
        if entry["H_only_outcome"] != "confirmed":
            continue
        sym = entry["symbol"]
        sym_panel = panel[panel["symbol"] == sym].sort_values("datetime").reset_index(drop=True)
        pos = sym_panel.index[sym_panel["datetime"] == entry["datetime"]]
        if len(pos) == 0:
            continue
        pos = pos[0]
        entry_idx = pos + 5
        exit_idx = entry_idx + 20
        if exit_idx >= len(sym_panel):
            continue
        entry_price = sym_panel.iloc[entry_idx]["close"]
        exit_price = sym_panel.iloc[exit_idx]["close"]
        trades.append({
            "symbol": sym, "sector": entry["sector"],
            "entry_time": sym_panel.iloc[entry_idx]["datetime"],
            "exit_time": sym_panel.iloc[exit_idx]["datetime"],
            "gross_ret": exit_price / entry_price - 1,
            "hold_bars": 20, "exit_reason": "confirmed_lag5",
            "date": entry["date"],
        })
    return pd.DataFrame(trades)


def build_random_baseline(panel: pd.DataFrame, n_sim: int = 1000) -> pd.DataFrame:
    """随机入场基准：随机选 1h bar，持有 20 根。"""
    rng = np.random.default_rng(BOOT_SEED)
    panel = panel.sort_values(["symbol", "datetime"]).reset_index(drop=True)
    # 每 symbol 随机选 n_sim/n_symbols 个入场点
    syms = panel["symbol"].unique()
    per_sym = max(1, n_sim // len(syms))
    trades = []
    for sym in syms:
        sym_panel = panel[panel["symbol"] == sym].sort_values("datetime").reset_index(drop=True)
        valid = len(sym_panel) - 20
        if valid < 10:
            continue
        positions = rng.choice(valid, size=min(per_sym, valid), replace=False)
        for pos in positions:
            trades.append({
                "symbol": sym,
                "gross_ret": sym_panel.iloc[pos + 20]["close"] / sym_panel.iloc[pos]["close"] - 1,
                "hold_bars": 20,
                "exit_reason": "random",
                "date": sym_panel.iloc[pos]["date"],
            })
    return pd.DataFrame(trades)


def performance_stats(trades: pd.DataFrame, label: str, cost_bp: float = 0) -> dict:
    """计算策略表现指标。"""
    if len(trades) == 0:
        return {"label": label, "n_trades": 0}
    rets = trades["gross_ret"].values - cost_bp / 10000.0
    n = len(rets)
    win_rate = float((rets > 0).mean())
    mean_ret = float(np.mean(rets))
    median_ret = float(np.median(rets))
    std_ret = float(np.std(rets, ddof=1)) if n > 1 else np.nan
    # 年化：假设平均持仓 hold_bars 根 1h，一年约 252*24/持仓周期（简化）
    avg_hold = float(trades["hold_bars"].mean()) if "hold_bars" in trades.columns else 20
    # 每次交易 mean_ret，粗略年化（不考虑资金时间价值）
    trades_per_year = 252 * 6 / avg_hold  # 商品一天约 6 根 1h（日盘4+夜盘2）
    annual_ret = mean_ret * trades_per_year
    sharpe = mean_ret / std_ret * np.sqrt(trades_per_year) if std_ret and std_ret > 0 else np.nan
    # 最大回撤（按交易顺序）
    if "entry_time" in trades.columns:
        sorted_rets = trades.sort_values("entry_time")["gross_ret"].values - cost_bp / 10000.0
    else:
        sorted_rets = rets
    cum = np.cumprod(1 + sorted_rets)
    running_max = np.maximum.accumulate(cum)
    max_dd = float(np.min((cum - running_max) / running_max)) if len(cum) else np.nan

    ci_lo, ci_hi = cluster_bootstrap_ci(rets, trades["date"].values)

    # 盈亏比
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    avg_win = float(np.mean(wins)) if len(wins) else np.nan
    avg_loss = float(np.mean(np.abs(losses))) if len(losses) else np.nan
    profit_factor = (
        float(wins.sum() / np.abs(losses).sum())
        if len(losses) and np.abs(losses).sum() > 0
        else np.inf if len(wins) else np.nan
    )

    return {
        "label": label,
        "n_trades": n,
        "win_rate": win_rate,
        "mean_ret": mean_ret,
        "median_ret": median_ret,
        "std_ret": std_ret,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "avg_hold_bars": avg_hold,
        "annual_ret_approx": annual_ret,
        "sharpe_approx": sharpe,
        "max_drawdown": max_dd,
        "cost_bp": cost_bp,
    }


def main() -> None:
    panel = pd.read_parquet(PANEL_PATH)
    print(f"面板: {len(panel)} 行, {panel['symbol'].nunique()} 合约")

    # 构造交易
    trades_short = build_trades(panel, use_filter=False)
    trades_short_filtered = build_trades(panel, use_filter=True)
    trades_buyhold = build_buyhold_trades(panel)
    trades_confirmed = build_confirmed_trades(panel)
    trades_random = build_random_baseline(panel)

    print(f"\n交易数：")
    print(f"  短脉冲做多（无过滤）:     {len(trades_short)}")
    print(f"  短脉冲做多（MADEV60<0）:  {len(trades_short_filtered)}")
    print(f"  buy & hold 20根:         {len(trades_buyhold)}")
    print(f"  等 confirmed 后入场:     {len(trades_confirmed)}")
    print(f"  随机基准:                {len(trades_random)}")

    # 退出原因分布
    if len(trades_short):
        print("\n短脉冲（无过滤）退出原因：")
        print(trades_short["exit_reason"].value_counts())
        print(f"\n第 3 根仍 H_only 占比: "
              f"{(trades_short['exit_reason']=='3rd_bar_H_only').mean():.1%}")

    # 保存交易明细
    trades_short.to_csv(OUT_DIR / "trades_short_pulse.csv", index=False)
    trades_short_filtered.to_csv(OUT_DIR / "trades_short_pulse_filtered.csv", index=False)
    trades_buyhold.to_csv(OUT_DIR / "trades_buyhold.csv", index=False)
    trades_confirmed.to_csv(OUT_DIR / "trades_confirmed.csv", index=False)

    # 绩效对比（0 成本）
    print("\n=== 绩效对比（0 成本）===")
    all_stats = []
    for trades, label in [
        (trades_short, "short_pulse"),
        (trades_short_filtered, "short_pulse_MADEV60<0"),
        (trades_buyhold, "buyhold_20"),
        (trades_confirmed, "confirmed_lag5"),
        (trades_random, "random_baseline"),
    ]:
        s = performance_stats(trades, label, cost_bp=0)
        all_stats.append(s)
    stats_df = pd.DataFrame(all_stats)
    cols = ["label", "n_trades", "win_rate", "mean_ret", "median_ret", "ci_lo", "ci_hi",
            "avg_win", "avg_loss", "profit_factor", "avg_hold_bars",
            "annual_ret_approx", "sharpe_approx", "max_drawdown"]
    print(stats_df[cols].round(4).to_string(index=False))
    stats_df.to_csv(OUT_DIR / "stage8_performance.csv", index=False)

    # 成本敏感性
    print("\n=== 成本敏感性（短脉冲无过滤 vs MADEV60<0）===")
    cost_rows = []
    for bp in COST_BPS:
        for trades, label in [
            (trades_short, "short_pulse"),
            (trades_short_filtered, "short_pulse_MADEV60<0"),
        ]:
            s = performance_stats(trades, label, cost_bp=bp)
            s["cost_bp"] = bp
            cost_rows.append(s)
    cost_df = pd.DataFrame(cost_rows)
    cost_cols = ["label", "cost_bp", "n_trades", "win_rate", "mean_ret", "ci_lo", "ci_hi",
                 "profit_factor", "annual_ret_approx"]
    print(cost_df[cost_cols].round(4).to_string(index=False))
    cost_df.to_csv(OUT_DIR / "stage8_cost_sensitivity.csv", index=False)

    # 按退出原因拆分
    print("\n=== 短脉冲按退出原因拆分 ===")
    exit_rows = []
    for reason, sub in trades_short.groupby("exit_reason"):
        s = performance_stats(sub, reason)
        exit_rows.append(s)
    exit_df = pd.DataFrame(exit_rows)
    print(exit_df[["label", "n_trades", "win_rate", "mean_ret", "median_ret",
                    "ci_lo", "ci_hi", "avg_hold_bars"]].round(4).to_string(index=False))
    exit_df.to_csv(OUT_DIR / "stage8_by_exit_reason.csv", index=False)

    # 按板块
    if "sector" in trades_short.columns:
        print("\n=== 短脉冲按板块 ===")
        sector_rows = []
        for sec, sub in trades_short.groupby("sector"):
            s = performance_stats(sub, sec)
            sector_rows.append(s)
        sec_df = pd.DataFrame(sector_rows)
        print(sec_df[["label", "n_trades", "win_rate", "mean_ret", "ci_lo", "ci_hi"]].round(4).to_string(index=False))
        sec_df.to_csv(OUT_DIR / "stage8_by_sector.csv", index=False)

    # 路径分析：max/min ret
    if len(trades_short):
        print("\n=== 短脉冲路径分析（无过滤）===")
        print(f"  平均最大有利收益: {trades_short['max_ret'].mean():.4f}")
        print(f"  平均最大不利回撤: {trades_short['min_ret'].mean():.4f}")
        print(f"  平均盈亏路径比:   {trades_short['max_ret'].mean() / max(abs(trades_short['min_ret'].mean()), 1e-6):.2f}")

    # summary
    summary = {
        "n_trades_short": int(len(trades_short)),
        "n_trades_filtered": int(len(trades_short_filtered)),
        "n_trades_buyhold": int(len(trades_buyhold)),
        "n_trades_confirmed": int(len(trades_confirmed)),
        "short_pulse_stats": all_stats[0],
        "short_filtered_stats": all_stats[1],
        "buyhold_stats": all_stats[2],
        "confirmed_stats": all_stats[3],
        "random_stats": all_stats[4],
    }
    with open(OUT_DIR / "stage8_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nStage 8 输出已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
