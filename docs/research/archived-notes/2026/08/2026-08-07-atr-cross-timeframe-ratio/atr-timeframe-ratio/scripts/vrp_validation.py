"""
波动率风险溢价（VRP）独立验证（向量化版）
==========================================

向量化实现，避免逐笔循环。
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
CSV_DIR = ROOT / "project_data" / "market_data" / "csv"
OUT_DIR = SCRIPT_DIR / "outputs" / "vrp_study"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BOOT_N = 500
BOOT_SEED = 42
N_SEEDS = 5
N_PER_SYMBOL = 40


def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(BOOT_SEED + 1)
    mask = ~np.isnan(values)
    values, clusters = values[mask], clusters[mask]
    if len(values) < 10:
        return np.nan, np.nan
    uniq = np.unique(clusters)
    idx_map = {c: np.where(clusters == c)[0] for c in uniq}
    stats = np.empty(BOOT_N)
    for i in range(BOOT_N):
        sampled = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_map[c] for c in sampled])
        stats[i] = values[idx].mean()
    return float(np.nanpercentile(stats, 2.5)), float(np.nanpercentile(stats, 97.5))


def classify_sector(sym: str) -> str:
    if sym.startswith("SHFE."):
        code = sym[5:]
        if code.startswith(("cu", "al", "zn", "pb", "ni", "sn", "au", "ag")):
            return "有色"
        return "能化"
    if sym.startswith("INE."):
        return "能化"
    if sym.startswith("DCE."):
        code = sym[4:]
        if code.startswith(("i", "j", "jm", "l", "v", "pp", "eg", "eb", "pg")):
            return "黑色/能化"
        return "农产品"
    if sym.startswith("CZCE."):
        return "农产品"
    if sym.startswith("GFEX."):
        return "黑色"
    return "其他"


def load_all_1h() -> dict[str, pd.DataFrame]:
    data = {}
    for f in sorted(CSV_DIR.glob("*.tqsdk.1h.csv")):
        df = pd.read_csv(f, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
        if len(df) < 100:
            continue
        sym = f.name.split(".tqsdk.1h.csv")[0]
        df["symbol"] = sym
        df["sector"] = classify_sector(sym)
        df["date"] = df["datetime"].dt.date
        df["year"] = df["datetime"].dt.year
        data[sym] = df
    return data


def simulate_trades_vectorized(
    sym_panel: pd.DataFrame,
    positions: np.ndarray,
    direction: int = 1,
    stop_loss_pct: float = 0.01,
    take_profit_pct: float | None = None,
    max_hold: int = 20,
) -> pd.DataFrame:
    """向量化模拟多笔交易。"""
    closes = sym_panel["close"].values
    highs = sym_panel["high"].values
    lows = sym_panel["low"].values
    dates = sym_panel["date"].values
    years = sym_panel["year"].values
    datetimes = sym_panel["datetime"].values
    symbol = sym_panel["symbol"].iloc[0]
    sector = sym_panel["sector"].iloc[0]

    trades = []
    for pos in positions:
        pos = int(pos)
        if pos + max_hold >= len(closes):
            continue
        entry_price = closes[pos]
        if direction > 0:
            stop_price = entry_price * (1 - stop_loss_pct)
            tp_price = entry_price * (1 + take_profit_pct) if take_profit_pct else None
        else:
            stop_price = entry_price * (1 + stop_loss_pct)
            tp_price = entry_price * (1 - take_profit_pct) if take_profit_pct else None

        exit_price = None
        exit_reason = None
        hold_bars = 0
        for k in range(1, max_hold + 1):
            idx = pos + k
            bar_high = highs[idx] if direction > 0 else lows[idx]
            bar_low = lows[idx] if direction > 0 else highs[idx]
            if bar_low <= stop_price:
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
            exit_price = closes[pos + max_hold]
            exit_reason = "hold_end"
            hold_bars = max_hold

        gross_ret = direction * (exit_price / entry_price - 1)
        trades.append({
            "symbol": symbol,
            "sector": sector,
            "entry_time": datetimes[pos],
            "gross_ret": gross_ret,
            "hold_bars": hold_bars,
            "exit_reason": exit_reason,
            "date": dates[pos],
            "year": years[pos],
        })
    return pd.DataFrame(trades)


def run_random_backtest(
    data: dict[str, pd.DataFrame],
    seed: int = 42,
    n_per_symbol: int = 40,
    direction: int = 1,
    stop_loss_pct: float = 0.01,
    take_profit_pct: float | None = None,
    max_hold: int = 20,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    all_trades = []
    for sym, df in data.items():
        valid = len(df) - max_hold - 1
        if valid < 10:
            continue
        n = min(n_per_symbol, valid)
        positions = rng.choice(valid, size=n, replace=False)
        trades = simulate_trades_vectorized(
            df, positions, direction=direction,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_hold=max_hold,
        )
        if len(trades) > 0:
            all_trades.append(trades)
    return pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()


def stats_of(trades: pd.DataFrame, cost_bp: float = 0) -> dict:
    if len(trades) == 0:
        return {"n": 0}
    rets = trades["gross_ret"].values - cost_bp / 10000.0
    n = len(rets)
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    date_str = trades["date"].astype(str).values if hasattr(trades["date"], "astype") else trades["date"].values
    ci_lo, ci_hi = cluster_bootstrap_ci(rets, date_str)
    avg_hold = float(trades["hold_bars"].mean())
    trades_per_year = 252 * 6 / avg_hold if avg_hold > 0 else 1
    std = float(np.std(rets, ddof=1)) if n > 1 else np.nan
    mean = float(np.mean(rets))
    return {
        "n": n,
        "win_rate": float((rets > 0).mean()),
        "mean_ret": mean,
        "median_ret": float(np.median(rets)),
        "std_ret": std,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "avg_win": float(np.mean(wins)) if len(wins) else np.nan,
        "avg_loss": float(np.mean(np.abs(losses))) if len(losses) else np.nan,
        "profit_factor": float(wins.sum() / np.abs(losses).sum()) if len(losses) and np.abs(losses).sum() > 0 else np.inf,
        "avg_hold": avg_hold,
        "annual_approx": mean * trades_per_year,
        "sharpe_approx": mean / std * np.sqrt(trades_per_year) if std and std > 0 else np.nan,
        "exit_sl": int((trades["exit_reason"] == "stop_loss").sum()),
        "exit_tp": int((trades["exit_reason"] == "take_profit").sum()),
        "exit_hold": int((trades["exit_reason"] == "hold_end").sum()),
    }


def main() -> None:
    print("加载所有 1h CSV...", flush=True)
    data = load_all_1h()
    print(f"加载 {len(data)} 个合约", flush=True)
    total_bars = sum(len(df) for df in data.values())
    print(f"总 {total_bars} 行", flush=True)

    # ============================================================
    # 1. 多随机种子：做多/做空/双向
    # ============================================================
    print("\n=== 1. 多随机种子方向对比 ===", flush=True)
    configs = [
        ("long_SL1%_hold20", 1, 0.01, None, 20),
        ("short_SL1%_hold20", -1, 0.01, None, 20),
        ("long_noSL_hold20", 1, 0.99, None, 20),
        ("long_SL1%_TP2%_hold20", 1, 0.01, 0.02, 20),
    ]
    seed_rows = []
    all_trades_by_config = {}
    for label, direction, sl, tp, hold in configs:
        all_trades = []
        for seed in range(N_SEEDS):
            trades = run_random_backtest(data, seed=seed, direction=direction,
                                         stop_loss_pct=sl, take_profit_pct=tp, max_hold=hold)
            trades["seed"] = seed
            all_trades.append(trades)
        all_df = pd.concat(all_trades, ignore_index=True)
        all_trades_by_config[label] = all_df
        seed_means = []
        for seed, sub in all_df.groupby("seed"):
            seed_means.append(stats_of(sub)["mean_ret"])
        overall = stats_of(all_df)
        overall["label"] = label
        overall["seed_mean"] = float(np.mean(seed_means))
        overall["seed_std"] = float(np.std(seed_means))
        overall["seed_min"] = float(np.min(seed_means))
        overall["seed_max"] = float(np.max(seed_means))
        seed_rows.append(overall)
        print(f"  {label:25s}: n={overall['n']:5d}  win={overall['win_rate']:.1%}  "
              f"ret={overall['mean_ret']:.4f}  CI=[{overall['ci_lo']:.4f},{overall['ci_hi']:.4f}]  "
              f"seeds=[{overall['seed_min']:.4f},{overall['seed_max']:.4f}]  PF={overall['profit_factor']:.2f}",
              flush=True)

    # 双向（long + short 各一半）
    for label, direction in [("both_SL1%_hold20", 0)]:
        all_trades = []
        for seed in range(N_SEEDS):
            tl = run_random_backtest(data, seed=seed, direction=1, stop_loss_pct=0.01, max_hold=20)
            ts = run_random_backtest(data, seed=seed+5000, direction=-1, stop_loss_pct=0.01, max_hold=20)
            tl["seed"] = seed
            ts["seed"] = seed
            all_trades.append(tl)
            all_trades.append(ts)
        all_df = pd.concat(all_trades, ignore_index=True)
        all_trades_by_config[label] = all_df
        seed_means = [stats_of(sub)["mean_ret"] for _, sub in all_df.groupby("seed")]
        overall = stats_of(all_df)
        overall["label"] = label
        overall["seed_mean"] = float(np.mean(seed_means))
        overall["seed_std"] = float(np.std(seed_means))
        overall["seed_min"] = float(np.min(seed_means))
        overall["seed_max"] = float(np.max(seed_means))
        seed_rows.append(overall)
        print(f"  {label:25s}: n={overall['n']:5d}  win={overall['win_rate']:.1%}  "
              f"ret={overall['mean_ret']:.4f}  CI=[{overall['ci_lo']:.4f},{overall['ci_hi']:.4f}]  "
              f"seeds=[{overall['seed_min']:.4f},{overall['seed_max']:.4f}]  PF={overall['profit_factor']:.2f}",
              flush=True)

    seed_df = pd.DataFrame(seed_rows)
    seed_df.to_csv(OUT_DIR / "vrp_direction_comparison.csv", index=False)

    # ============================================================
    # 2. 按年份
    # ============================================================
    print("\n=== 2. 按年份（做多 SL1% hold20）===", flush=True)
    long_trades = all_trades_by_config["long_SL1%_hold20"]
    year_rows = []
    for year, sub in long_trades.groupby("year"):
        s = stats_of(sub)
        s["year"] = int(year)
        year_rows.append(s)
        print(f"  {year}: n={s['n']:5d}  win={s['win_rate']:.1%}  "
              f"ret={s['mean_ret']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  PF={s['profit_factor']:.2f}",
              flush=True)
    year_df = pd.DataFrame(year_rows)
    year_df.to_csv(OUT_DIR / "vrp_by_year.csv", index=False)

    # ============================================================
    # 3. 按板块
    # ============================================================
    print("\n=== 3. 按板块 ===", flush=True)
    sector_rows = []
    for sec, sub in long_trades.groupby("sector"):
        s = stats_of(sub)
        s["sector"] = sec
        sector_rows.append(s)
        print(f"  {sec:15s}: n={s['n']:5d}  win={s['win_rate']:.1%}  "
              f"ret={s['mean_ret']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  PF={s['profit_factor']:.2f}",
              flush=True)
    pd.DataFrame(sector_rows).to_csv(OUT_DIR / "vrp_by_sector.csv", index=False)

    # ============================================================
    # 4. 参数网格
    # ============================================================
    print("\n=== 4. 参数网格 ===", flush=True)
    param_rows = []
    for sl in [0.005, 0.01, 0.015, 0.02, 0.03]:
        for hold in [5, 10, 20, 40]:
            trades = run_random_backtest(data, seed=42, direction=1,
                                         stop_loss_pct=sl, max_hold=hold)
            s = stats_of(trades)
            s["stop_loss"] = sl
            s["max_hold"] = hold
            param_rows.append(s)
    param_df = pd.DataFrame(param_rows)
    param_df.to_csv(OUT_DIR / "vrp_param_grid.csv", index=False)
    print(param_df[["stop_loss", "max_hold", "n", "win_rate", "mean_ret",
                    "ci_lo", "ci_hi", "profit_factor"]].round(4).to_string(index=False), flush=True)

    # ============================================================
    # 5. 成本敏感性
    # ============================================================
    print("\n=== 5. 成本敏感性 ===", flush=True)
    cost_rows = []
    for bp in [0, 1, 2, 3, 5, 10]:
        s = stats_of(long_trades, cost_bp=bp)
        s["cost_bp"] = bp
        cost_rows.append(s)
        print(f"  cost={bp:2d}bp: ret={s['mean_ret']:.4f}  CI=[{s['ci_lo']:.4f},{s['ci_hi']:.4f}]  PF={s['profit_factor']:.2f}",
              flush=True)
    pd.DataFrame(cost_rows).to_csv(OUT_DIR / "vrp_cost_sensitivity.csv", index=False)

    # ============================================================
    # 6. 买入持有
    # ============================================================
    print("\n=== 6. 买入持有基准 ===", flush=True)
    bh_rows = []
    for sym, df in data.items():
        if len(df) < 20:
            continue
        bh_rows.append({
            "symbol": sym, "sector": df.iloc[0]["sector"],
            "total_ret": df["close"].iloc[-1] / df["close"].iloc[0] - 1,
            "bars": len(df),
        })
    bh_df = pd.DataFrame(bh_rows)
    bh_df.to_csv(OUT_DIR / "vrp_buy_hold.csv", index=False)
    print(f"  买入持有均值: {bh_df['total_ret'].mean():.4f}")
    print(f"  买入持有中位: {bh_df['total_ret'].median():.4f}")
    print(f"  上涨合约占比: {(bh_df['total_ret']>0).mean():.1%}")

    # ============================================================
    # 7. 非重叠
    # ============================================================
    print("\n=== 7. 非重叠抽样 ===", flush=True)
    lt = long_trades.copy()
    lt["entry_date"] = pd.to_datetime(lt["entry_time"]).dt.date
    nonoverlap = lt.sort_values("entry_time").groupby(["symbol", "entry_date"]).first().reset_index()
    s_all = stats_of(long_trades)
    s_no = stats_of(nonoverlap)
    print(f"  原始: n={s_all['n']}, ret={s_all['mean_ret']:.4f}, CI=[{s_all['ci_lo']:.4f},{s_all['ci_hi']:.4f}]")
    print(f"  非重叠: n={s_no['n']}, ret={s_no['mean_ret']:.4f}, CI=[{s_no['ci_lo']:.4f},{s_no['ci_hi']:.4f}], PF={s_no['profit_factor']:.2f}")

    # ============================================================
    # 8. 退出原因
    # ============================================================
    print("\n=== 8. 退出原因 ===", flush=True)
    for reason, sub in long_trades.groupby("exit_reason"):
        s = stats_of(sub)
        print(f"  {reason:12s}: n={s['n']:5d}  win={s['win_rate']:.1%}  ret={s['mean_ret']:.4f}  hold={s['avg_hold']:.1f}",
              flush=True)

    # Summary
    summary = {
        "n_symbols": len(data),
        "total_bars": int(total_bars),
        "direction_comparison": seed_df[["label", "n", "win_rate", "mean_ret", "ci_lo", "ci_hi",
                                         "profit_factor", "seed_min", "seed_max"]].to_dict("records"),
        "by_year": year_df[["year", "n", "win_rate", "mean_ret", "ci_lo", "ci_hi"]].to_dict("records"),
        "by_sector": pd.DataFrame(sector_rows)[["sector", "n", "win_rate", "mean_ret", "ci_lo", "ci_hi"]].to_dict("records"),
        "buy_hold": {"mean": float(bh_df["total_ret"].mean()), "median": float(bh_df["total_ret"].median()),
                     "up_fraction": float((bh_df["total_ret"] > 0).mean())},
        "nonoverlap": {"n": s_no["n"], "mean_ret": s_no["mean_ret"], "ci": [s_no["ci_lo"], s_no["ci_hi"]],
                       "profit_factor": s_no["profit_factor"]},
    }
    with open(OUT_DIR / "vrp_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    long_trades.to_csv(OUT_DIR / "trades_long_SL1_hold20.csv", index=False)
    print(f"\n输出已保存到 {OUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
