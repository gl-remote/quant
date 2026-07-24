"""
文件级元信息：
- 创建背景：用户提出把 skew 挪到日线级别——每合约每天一个 event，用过去
  10 天数据算 skew，看未来 3 天变化。理由：日线级别持仓 3 天，交易成本占比
  远小于 hourly，即使 IC 只有 0.03-0.05，均值差也能穿透成本。
- 用途：daily event 尺度 skew 假设验证：
  (1) skew_10d：10 天合并 volume profile 三阶偏度
  (2) skew_daily_mean_10d：过去 10 天每日 skew 的均值
  (3) skew_daily_std_10d：过去 10 天每日 skew 的波动率
  (4) skew_daily_trend_10d：过去 10 天每日 skew 的线性趋势
  (5) skew_zscore：(当日 daily_skew - 10 天均值) / 10 天 std
  (6) skew_today：当日单日 skew
  目标：ret_1d / ret_2d / ret_3d / |ret_3d| / range_3d
- 注意事项：临时研究脚本，产物在 outputs/daily_skew/；严格 causal
  （event_time = 当日收盘，特征只用 [event-2400, event] 5m bars 或
  [event_day-9, event_day] 的 daily skew）。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/workspace")
sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")

from common.contract_specs import CONTRACT_SPECS  # noqa: E402
from h1_a3_skew_pooled_ic import build_profile  # noqa: E402

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/daily_skew"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

BARS_PER_DAY = 240  # 5m bars per trading day (approximation for day + night)
LOOKBACK_DAYS = 10
FUTURE_DAYS = 3


def per_symbol_ic(df: pd.DataFrame, feat: str, tgt: str) -> tuple[float, int, float, int]:
    """pooled Spearman IC + per-symbol sign consistency."""
    x = df[feat].to_numpy()
    y = df[tgt].to_numpy()
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 100:
        return float("nan"), int(m.sum()), float("nan"), 0
    r, _ = stats.spearmanr(x[m], y[m])
    r = float(r)
    ics = []
    for sym, sub in df.groupby("symbol"):
        if len(sub) < 30:
            continue
        xs = sub[feat].to_numpy()
        ys = sub[tgt].to_numpy()
        ms = ~(np.isnan(xs) | np.isnan(ys))
        if ms.sum() < 20:
            continue
        ri, _ = stats.spearmanr(xs[ms], ys[ms])
        if ri is not None and not math.isnan(ri):
            ics.append(ri)
    if not ics:
        return r, int(m.sum()), float("nan"), 0
    ics = np.array(ics)
    same = int((np.sign(ics) == np.sign(r)).sum()) if not np.isnan(r) else 0
    return r, int(m.sum()), same / len(ics), len(ics)


def process_symbol(symbol: str) -> pd.DataFrame | None:
    path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
    if not path.exists():
        return None
    spec = CONTRACT_SPECS.get_symbol(symbol)
    if spec is None:
        return None
    tick = spec.tick
    bars = pd.read_csv(path)
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)
    bars["date"] = bars["datetime"].dt.date

    # Daily close: each date's last close
    daily = bars.groupby("date", sort=True).agg(
        close=("close", "last"),
        last_idx=("close", lambda s: s.index[-1]),  # last 5m bar idx in the day
    ).reset_index()
    daily["close"] = daily["close"].astype(float)
    daily["last_idx"] = daily["last_idx"].astype(int)

    # Per-day skew: use all bars of that day
    daily["skew_day"] = np.nan
    for i, row in daily.iterrows():
        day = row["date"]
        day_bars = bars[bars["date"] == day]
        p = build_profile(day_bars, tick)
        if p is not None:
            daily.at[i, "skew_day"] = p.skew

    # For each event day t (t >= LOOKBACK_DAYS), compute features from t-9..t (inclusive)
    # and future targets from t+1..t+FUTURE_DAYS
    records: list[dict] = []
    for i in range(LOOKBACK_DAYS, len(daily) - FUTURE_DAYS):
        row = daily.iloc[i]
        # 10-day merged skew: use bars from day t-9..t inclusive (含当天，因为 event=当天收盘)
        first_day = daily.iloc[i - LOOKBACK_DAYS + 1]["date"]
        # first_day 之前 10 天：daily.iloc[i-9..i]
        # 用这 10 天的所有 5m bars 合并算 profile
        bars_window = bars[(bars["date"] >= first_day) & (bars["date"] <= row["date"])]
        p10 = build_profile(bars_window, tick)
        if p10 is None:
            continue
        # daily skew series 过去 10 天（含当天）
        skew_series = daily.iloc[i - LOOKBACK_DAYS + 1:i + 1]["skew_day"].to_numpy()
        if np.isnan(skew_series).sum() > 3:
            continue
        skew_series = skew_series[~np.isnan(skew_series)]
        mean10 = float(np.mean(skew_series))
        std10 = float(np.std(skew_series, ddof=1)) if len(skew_series) > 1 else float("nan")
        # 简单趋势：last - first
        trend10 = float(skew_series[-1] - skew_series[0])
        # z-score
        cur_daily_skew = float(daily.iloc[i]["skew_day"])
        zscore = ((cur_daily_skew - mean10) / std10) if std10 > 0 else float("nan")
        # 未来 return
        close_now = row["close"]
        close_1d = float(daily.iloc[i + 1]["close"])
        close_2d = float(daily.iloc[i + 2]["close"])
        close_3d = float(daily.iloc[i + 3]["close"])
        ret_1d = math.log(close_1d / close_now) if close_now > 0 else np.nan
        ret_2d = math.log(close_2d / close_now) if close_now > 0 else np.nan
        ret_3d = math.log(close_3d / close_now) if close_now > 0 else np.nan
        # range_3d：未来 3 天内 max - min
        fut_closes = daily.iloc[i + 1:i + 4]["close"].to_numpy()
        range_3d = math.log(fut_closes.max() / fut_closes.min()) if fut_closes.min() > 0 else np.nan

        # Cost per side (fraction of close, roundtrip = 2×)
        slip = (spec.tick * spec.slip_tick) / close_now
        try:
            comm = spec.total_commission(close_now, 1) / (spec.size * close_now) if spec.size > 0 else 0.0
        except Exception:
            comm = 0.0
        cost_rt = 2.0 * (slip + comm)

        records.append({
            "symbol": symbol, "contract": symbol,
            "event_date": row["date"], "close_t": close_now,
            "skew_10d": p10.skew,
            "skew_today": cur_daily_skew,
            "skew_daily_mean_10d": mean10,
            "skew_daily_std_10d": std10,
            "skew_daily_trend_10d": trend10,
            "skew_zscore": zscore,
            "abs_skew_10d": abs(p10.skew),
            "abs_skew_today": abs(cur_daily_skew),
            "ret_1d": ret_1d,
            "ret_2d": ret_2d,
            "ret_3d": ret_3d,
            "abs_ret_3d": abs(ret_3d) if ret_3d is not None else np.nan,
            "range_3d": range_3d,
            "cost_rt": cost_rt,
        })
    return pd.DataFrame(records)


def main() -> None:
    print(f"CSV dir: {CSV_DIR}")
    files = sorted(CSV_DIR.glob("*.tqsdk.5m.csv"))
    print(f"Total contract files: {len(files)}")

    cache = OUT_DIR / "daily_events.csv"
    if cache.exists():
        print(f"Reusing cache: {cache}")
        long_df = pd.read_csv(cache)
        long_df["event_date"] = pd.to_datetime(long_df["event_date"]).dt.date
    else:
        parts = []
        for i, f in enumerate(files, 1):
            symbol = f.name.replace(".tqsdk.5m.csv", "")
            try:
                df = process_symbol(symbol)
            except Exception as e:
                print(f"  [{symbol}] ERROR: {e}")
                continue
            if df is not None and len(df) > 0:
                parts.append(df)
                print(f"  [{symbol}] ({i}/{len(files)}) daily events={len(df)}", flush=True)
        long_df = pd.concat(parts, ignore_index=True)
        long_df.to_csv(cache, index=False)
        print(f"Saved: {cache} rows={len(long_df)}")

    print(f"\nTotal daily events: {len(long_df)}, "
          f"symbols={long_df['symbol'].nunique()}, "
          f"contracts={long_df['contract'].nunique()}")

    # Cross-contract rank per event_date
    long_df["skew_10d_xs_rank"] = long_df.groupby("event_date")["skew_10d"].transform(
        lambda s: s.rank(pct=True) if len(s) >= 3 else np.nan
    )

    FEATURES_SIGNED = [
        "skew_10d", "skew_today", "skew_daily_mean_10d",
        "skew_daily_trend_10d", "skew_zscore", "skew_10d_xs_rank",
    ]
    FEATURES_ABS = ["abs_skew_10d", "abs_skew_today", "skew_daily_std_10d"]
    TARGETS_SIGNED = ["ret_1d", "ret_2d", "ret_3d"]
    TARGETS_ABS = ["abs_ret_3d", "range_3d"]

    print("\n=== [A] signed skew features → future signed ret ===")
    rows = []
    for feat in FEATURES_SIGNED:
        for tgt in TARGETS_SIGNED:
            r, n, cons, nsym = per_symbol_ic(long_df, feat, tgt)
            rows.append({"feature": feat, "target": tgt, "n": n, "ic": r,
                         "consistency": cons, "n_symbols": nsym})
    A_df = pd.DataFrame(rows).sort_values("ic", key=lambda x: x.abs(), ascending=False)
    print(A_df.to_string(index=False))

    print("\n=== [B] |skew| features → future magnitude ===")
    rows = []
    for feat in FEATURES_ABS:
        for tgt in TARGETS_ABS:
            r, n, cons, nsym = per_symbol_ic(long_df, feat, tgt)
            rows.append({"feature": feat, "target": tgt, "n": n, "ic": r,
                         "consistency": cons, "n_symbols": nsym})
    B_df = pd.DataFrame(rows).sort_values("ic", key=lambda x: x.abs(), ascending=False)
    print(B_df.to_string(index=False))

    all_ = pd.concat([A_df.assign(scan="signed"), B_df.assign(scan="magnitude")],
                    ignore_index=True)
    all_.to_csv(OUT_DIR / "daily_ic_all.csv", index=False)

    print("\n=== TOP 15 |IC| ===")
    top = all_.sort_values("ic", key=lambda x: x.abs(), ascending=False).head(15)
    print(top.to_string(index=False))

    # 通过门槛：|IC|>0.03 AND consistency>=0.60
    ok = all_[(all_["ic"].abs() > 0.03) & (all_["consistency"] >= 0.60)]
    print(f"\n>>> Candidates (|IC|>0.03 AND consistency>=0.60): {len(ok)}")
    if not ok.empty:
        print(ok.to_string(index=False))
        ok.to_csv(OUT_DIR / "passing_candidates.csv", index=False)

    # 对 TOP-1 做分档 mean 检验（无论是否过门）
    print("\n=== Top-1 tercile mean (per-contract rank) ===")
    top1 = all_.iloc[all_["ic"].abs().idxmax()]
    feat = top1["feature"]
    tgt = top1["target"]
    print(f"Top-1: {feat} → {tgt}, IC={top1['ic']:.4f}, consistency={top1['consistency']:.1%}")
    long_df["_r"] = long_df.groupby("contract")[feat].transform(lambda s: s.rank(pct=True))
    for name, mask in [
        ("bot_30", long_df["_r"] <= 0.30),
        ("mid_40", (long_df["_r"] > 0.30) & (long_df["_r"] < 0.70)),
        ("top_30", long_df["_r"] >= 0.70),
    ]:
        y = long_df.loc[mask, tgt].dropna()
        cost = long_df.loc[mask, "cost_rt"].mean()
        # signed target: 用 sign(ic) 决定方向
        if tgt in TARGETS_SIGNED:
            direction = np.sign(top1["ic"]) if not np.isnan(top1["ic"]) else 1
            # top 桶按 IC 方向下注: 若 IC>0，top 桶做多；若 IC<0，top 桶做空
            side = 1 if (name == "top_30" and direction > 0) or (name == "bot_30" and direction < 0) else \
                  (-1 if (name == "top_30" and direction < 0) or (name == "bot_30" and direction > 0) else 0)
            if side != 0:
                y_signed = y.to_numpy() * side - cost
                print(f"  {name} (bet side={side:+d}): n={len(y)}, "
                      f"mean_gross={y.mean() * side * 1e4:.1f}bps, "
                      f"mean_net={np.mean(y_signed) * 1e4:.1f}bps, "
                      f"cost_rt={cost*1e4:.1f}bps")
            else:
                print(f"  {name}: n={len(y)}, mean={y.mean() * 1e4:.1f}bps (中间桶, 不下注)")
        else:
            print(f"  {name}: n={len(y)}, mean={y.mean():.6f}")

    # 检查主流 signed 特征在 daily 级别的净收益差
    print("\n=== [C] Per signed feature, top-30 vs bot-30 net signed pnl ===")
    for feat in FEATURES_SIGNED:
        for tgt in TARGETS_SIGNED:
            long_df["_r"] = long_df.groupby("contract")[feat].transform(lambda s: s.rank(pct=True))
            top = long_df[long_df["_r"] >= 0.70]
            bot = long_df[long_df["_r"] <= 0.30]
            if len(top) < 100 or len(bot) < 100:
                continue
            # 假设 top 桶做多、bot 桶做空 → 两桶都是 "顺信号"
            y_top = top[tgt].dropna().mean()
            y_bot = bot[tgt].dropna().mean()
            long_short_gross = y_top - y_bot
            long_short_net = long_short_gross - top["cost_rt"].mean() - bot["cost_rt"].mean()
            print(f"  {feat} → {tgt}: top_mean={y_top*1e4:.1f}bps, "
                  f"bot_mean={y_bot*1e4:.1f}bps, L-S_gross={long_short_gross*1e4:.1f}bps, "
                  f"L-S_net={long_short_net*1e4:.1f}bps")

    print(f"\nAll outputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
