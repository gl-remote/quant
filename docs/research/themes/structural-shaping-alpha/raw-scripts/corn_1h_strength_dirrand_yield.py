"""玉米 1h · 强信号区 + DirRandom 方向的收益上限模拟

假设：
- 能事前识别 |ν|/σ 分布的前 X%（信号强度识别 100% 准确）
- 但方向随机 50/50（DirRandom）
- 塑形容器 K_S=2.75 / K_T=3.00 / MAX_BARS=80，1h 周期
- 单边成本 c_side = 0.077 ATR（对应 §2.17.8.5 参照）

模拟：
- 对每个"前 X% 强信号段"入场时刻，随机方向进行 barrier 触达模拟
- 输出 P_win / E_gross / E_net / 夏普 / 年化 ATR / 假设仓位下的 % 收益
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
SYMBOLS = ["DCE.c2601", "DCE.c2603", "DCE.c2605"]

ATR_PERIOD = 14
K_S = 2.75
K_T = 3.00
MAX_BARS = 80
C_SIDE = 0.077          # 单边成本 ATR
STRIDE = 4
EMA_SPAN = 20
WINDOW_HOURS = 20        # 用来测量 |ν|/σ 的窗口
TOP_QUANTILES = [0.90, 0.80, 0.70, 0.50, 0.0]  # 前10%、20%、30%、50%、100%(全做)
N_MC = 200               # 每个入场点方向蒙特卡洛次数


def load_bars(sym: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean()
    df["log_ret"] = np.log(close).diff()
    return df.dropna(subset=["atr", "log_ret"]).reset_index(drop=True)


def measure_strength(df: pd.DataFrame, W: int) -> pd.DataFrame:
    """按 stride 窗口测量未来 W 小时的 |ν|/σ；返回 DataFrame(entry_idx, nu_abs, atr)。"""
    rows = []
    for i in range(0, len(df) - W - MAX_BARS, STRIDE):
        seg = df["log_ret"].iloc[i : i + W].to_numpy()
        if len(seg) < 5:
            continue
        mu_bar = float(np.mean(seg))
        sd_bar = float(np.std(seg, ddof=1))
        if sd_bar <= 0:
            continue
        atr = df["atr"].iat[i]
        if atr <= 0 or math.isnan(atr):
            continue
        rows.append(
            {"entry_idx": i, "nu_abs": abs(mu_bar) / sd_bar, "atr": atr}
        )
    return pd.DataFrame(rows)


def simulate_barrier(
    bars: pd.DataFrame, entry_idx: int, direction: int, atr: float
) -> float:
    """返回该笔 gross_atr。"""
    entry = bars["close"].iat[entry_idx]
    stop = entry - direction * K_S * atr
    take = entry + direction * K_T * atr
    exit_price = None
    max_look = min(MAX_BARS, len(bars) - entry_idx - 1)
    for step in range(1, max_look + 1):
        j = entry_idx + step
        hi, lo = bars["high"].iat[j], bars["low"].iat[j]
        if direction > 0:
            if lo <= stop:
                exit_price = stop
                break
            if hi >= take:
                exit_price = take
                break
        else:
            if hi >= stop:
                exit_price = stop
                break
            if lo <= take:
                exit_price = take
                break
    if exit_price is None:
        exit_price = bars["close"].iat[entry_idx + max_look]
    return direction * (exit_price - entry) / atr


def run_slice(strength_df: pd.DataFrame, bars: pd.DataFrame, quantile_thr: float):
    """对给定 quantile 门槛以上的入场点执行 DirRandom 蒙特卡洛。"""
    if quantile_thr <= 0:
        top = strength_df
    else:
        thr = strength_df["nu_abs"].quantile(quantile_thr)
        top = strength_df[strength_df["nu_abs"] >= thr]

    rng = np.random.default_rng(20260715)
    trades = []
    for _, row in top.iterrows():
        for _ in range(N_MC):
            direction = int(rng.choice([+1, -1]))
            g = simulate_barrier(
                bars, int(row["entry_idx"]), direction, row["atr"]
            )
            trades.append(g)
    return np.array(trades), len(top)


def analyse(sym: str, per_symbol_agg: list) -> pd.DataFrame:
    bars = load_bars(sym)
    strength = measure_strength(bars, WINDOW_HOURS)
    total_bars = len(bars)
    time_span_hours = total_bars  # 1h 一根
    print(
        f"\n[{sym}] bars={total_bars}  "
        f"[{bars['datetime'].iat[0]} .. {bars['datetime'].iat[-1]}]"
    )
    print(f"  信号候选窗口 = {len(strength)}")

    rows = []
    for q in TOP_QUANTILES:
        gross_arr, n_entries = run_slice(strength, bars, q)
        p_win = float(np.mean(gross_arr > 0))
        e_gross = float(np.mean(gross_arr))
        e_net = e_gross - 2 * C_SIDE
        std_net = float(np.std(gross_arr - 2 * C_SIDE, ddof=1))
        sharpe_per_trade = e_net / std_net if std_net > 0 else float("nan")
        rows.append(
            {
                "symbol": sym,
                "quantile": q,
                "top_pct": (1 - q) * 100 if q > 0 else 100.0,
                "n_entries": n_entries,
                "n_trades_mc": len(gross_arr),
                "P_win": p_win,
                "E_gross_ATR": e_gross,
                "E_net_ATR": e_net,
                "std_ATR": std_net,
                "sharpe_per_trade": sharpe_per_trade,
                "time_span_hours": time_span_hours,
            }
        )
    per_symbol_agg.extend(rows)
    return pd.DataFrame(rows)


def annualize(df_row: pd.Series, year_hours: float = 250 * 6.5) -> dict:
    """把 per-trade 指标折算年化。假设年化交易时间 = 250 天 × 6.5h = 1625h。
    每合约实际样本约 400h → 缩放。"""
    scale = year_hours / df_row["time_span_hours"]
    n_year = df_row["n_entries"] * scale
    total_atr = df_row["E_net_ATR"] * n_year
    ann_std = df_row["std_ATR"] * math.sqrt(n_year)
    sharpe_year = total_atr / ann_std if ann_std > 0 else float("nan")
    # 账户 % 收益：假设每笔 1% 账户风险 = K_S ATR × 头寸
    # E_net (ATR) / K_S = 收益/风险比，乘 r% = 每笔 %
    r_per_trade_pct = df_row["E_net_ATR"] / K_S  # 单笔占单位风险的比例
    ann_pct_at_r_1 = r_per_trade_pct * n_year * 1.0  # r=1% 每笔
    return {
        "n_year": n_year,
        "annual_ATR": total_atr,
        "sharpe_year": sharpe_year,
        "annual_pct_at_r1": ann_pct_at_r_1,
    }


def main() -> None:
    print(
        f"配置 K_S={K_S} K_T={K_T} RR={K_T/K_S:.2f}  "
        f"MAX_BARS={MAX_BARS} c_side={C_SIDE}  N_MC={N_MC}/入场点"
    )
    per_symbol = []
    for sym in SYMBOLS:
        df = analyse(sym, per_symbol)
        for _, row in df.iterrows():
            ann = annualize(row)
            print(
                f"  q={row['quantile']:.2f} 前{row['top_pct']:.0f}%  "
                f"n_entries={row['n_entries']:>3}  P_win={row['P_win']:.3f}  "
                f"E_gross={row['E_gross_ATR']:+.3f}  "
                f"E_net={row['E_net_ATR']:+.3f}  "
                f"Sharpe/trade={row['sharpe_per_trade']:+.3f}  "
                f"年化 ATR={ann['annual_ATR']:+.1f}  "
                f"Sharpe/年={ann['sharpe_year']:+.2f}  "
                f"年化@r=1%={ann['annual_pct_at_r1']:+.1f}%"
            )

    full = pd.DataFrame(per_symbol)
    # 合并按 quantile 平均
    print("\n\n===== 全玉米平均（3 合约合并）=====")
    for q in TOP_QUANTILES:
        sub = full[full["quantile"] == q]
        row = pd.Series(
            {
                "quantile": q,
                "top_pct": (1 - q) * 100 if q > 0 else 100.0,
                "n_entries": sub["n_entries"].sum(),
                "P_win": sub["P_win"].mean(),
                "E_gross_ATR": sub["E_gross_ATR"].mean(),
                "E_net_ATR": sub["E_net_ATR"].mean(),
                "std_ATR": sub["std_ATR"].mean(),
                "sharpe_per_trade": sub["sharpe_per_trade"].mean(),
                "time_span_hours": sub["time_span_hours"].sum(),
            }
        )
        ann = annualize(row)
        print(
            f"前{row['top_pct']:>3.0f}%: n_entries={row['n_entries']:>4}  "
            f"P_win={row['P_win']:.3f}  "
            f"E_gross={row['E_gross_ATR']:+.3f}  "
            f"E_net={row['E_net_ATR']:+.3f}  "
            f"σ={row['std_ATR']:.3f}  "
            f"Sharpe/trade={row['sharpe_per_trade']:+.3f}  "
            f"年化 ATR={ann['annual_ATR']:+.1f}  "
            f"Sharpe/年={ann['sharpe_year']:+.2f}  "
            f"年化@r=1%={ann['annual_pct_at_r1']:+.1f}%"
        )

    out_dir = REPO / "project_data" / "research" / "first_passage_boundary"
    full.to_csv(out_dir / "corn_1h_strength_dirrand_yield.csv", index=False)
    print(f"\n明细已写入 {out_dir}/corn_1h_strength_dirrand_yield.csv")


if __name__ == "__main__":
    main()
