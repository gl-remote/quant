"""
文件级元信息：
- 创建背景：va-asymmetry-revisit 二轮回收——H-1 一维 IC 判死后，回到
  archive va-asymmetry-composite 原策略核心：(skew × ATR × trend) 三维联合
  tier 判定 + 长持仓（6-12h）signed pnl edge。原版 daily 特征在 event_date
  未 shift(1) 泄漏；本脚本用严格 causal 的 intraday 版本重建 6 个 tier。
- 用途：构造 causal 三特征 → per-contract rolling rank → 6 tier 判定 →
  tier × horizon 的 signed pnl mean + cluster bootstrap CI + 品种保留率。
- 注意事项：临时研究脚本，产物在
  docs/workbench/va-asymmetry-revisit/outputs/c1/；符号池复用 h1。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/workspace")
sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")

from common.contract_specs import CONTRACT_SPECS  # noqa: E402
from h1b_regime_stratified import cluster_bootstrap_mean  # noqa: E402

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c1"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

LONG_PATH = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1/h1_long_events.csv"
)

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
ATR_WIN_5M = 96
TREND_WIN_5M = 96
RANK_WIN_EVENTS = 240
HORIZONS_5M = {2: 24, 4: 48, 6: 72, 8: 96, 10: 120, 12: 144}
RNG_SEED = 20260714


def enrich_intra_features(long_df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for symbol, sub in long_df.groupby("symbol", sort=False):
        try:
            bars = pd.read_csv(CSV_DIR / f"{symbol}.tqsdk.5m.csv")
        except FileNotFoundError:
            continue
        bars["datetime"] = pd.to_datetime(bars["datetime"])
        bars = bars.sort_values("datetime").reset_index(drop=True)
        bars["log_close"] = np.log(bars["close"])
        bars["ret_5m"] = bars["log_close"].diff()
        bars["abs_ret_5m"] = bars["ret_5m"].abs()
        bars["atr_intra"] = (
            bars["abs_ret_5m"].rolling(ATR_WIN_5M, min_periods=48).mean().shift(1)
        )
        bars["trend_intra"] = (
            bars["ret_5m"].rolling(TREND_WIN_5M, min_periods=48).sum().shift(1)
        )
        idx = bars.set_index("datetime")
        sub = sub.copy()
        sub["event_time"] = pd.to_datetime(sub["event_time"])
        sub["atr_intra"] = sub["event_time"].map(idx["atr_intra"])
        sub["trend_intra"] = sub["event_time"].map(idx["trend_intra"])
        out.append(sub)
    return pd.concat(out, ignore_index=True)


def add_future_returns(long_df: pd.DataFrame) -> pd.DataFrame:
    """补齐 HORIZONS_5M 中所有 h 的 ret_{h}h 列（h1 已有 2/4/6/8/12h，补 10h）。"""
    out = []
    for symbol, sub in long_df.groupby("symbol", sort=False):
        try:
            bars = pd.read_csv(CSV_DIR / f"{symbol}.tqsdk.5m.csv")
        except FileNotFoundError:
            continue
        bars["datetime"] = pd.to_datetime(bars["datetime"])
        bars = bars.sort_values("datetime").reset_index(drop=True)
        dt_to_idx = {row.datetime: i for i, row in bars.iterrows()}
        sub = sub.copy()
        sub["event_time"] = pd.to_datetime(sub["event_time"])
        for h_hr, n5m in HORIZONS_5M.items():
            col = f"ret_{h_hr}h"
            if col in sub.columns and sub[col].notna().any():
                continue
            vals = []
            for _, row in sub.iterrows():
                ei = dt_to_idx.get(row["event_time"])
                if ei is None:
                    vals.append(np.nan)
                    continue
                fi = ei + n5m
                if fi >= len(bars):
                    vals.append(np.nan)
                    continue
                cf = float(bars.iloc[fi]["close"])
                ct = float(row["close_t"])
                vals.append(math.log(cf / ct) if ct > 0 else np.nan)
            sub[col] = vals
        out.append(sub)
    return pd.concat(out, ignore_index=True)


def add_rank(df: pd.DataFrame, col: str, window: int) -> pd.DataFrame:
    """向 df 添加 <col>_rank，per-contract rolling-window rank."""
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    def _r(sub: pd.DataFrame) -> pd.Series:
        s = sub[col].reset_index(drop=True)
        return s.rolling(window, min_periods=60).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
    df[f"{col}_rank"] = df.groupby("contract", sort=False, group_keys=False).apply(_r).to_numpy()
    return df


def classify_tier(rs: float, ra: float, rt: float) -> str:
    if any(math.isnan(v) for v in (rs, ra, rt)):
        return "none"
    # long-side (data rank high = long)
    if 0.70 <= rs <= 0.91 and ra <= 0.67 and rt >= 0.75:
        return "L_seg3_lowmid_up"
    if 0.81 <= rs <= 1.0 and ra > 0.67 and rt >= 0.75:
        return "L_seg12_high_up"
    if 0.81 <= rs <= 0.91 and ra <= 0.33 and 0.20 < rt < 0.75:
        return "L_seg2_low_flat"
    # short-side (data rank low = short)
    if 0 <= rs <= 0.19 and ra > 0.67 and rt <= 0.20:
        return "S_seg12_high_dn"
    if 0.19 < rs <= 0.40 and ra > 0.67 and rt <= 0.20:
        return "S_seg34_high_dn"
    if 0.09 <= rs < 0.19 and 0.33 < ra < 0.67 and rt <= 0.20:
        return "S_seg2_mid_dn"
    return "none"


TIER_DIRECTION = {
    "L_seg3_lowmid_up": +1, "L_seg12_high_up": +1, "L_seg2_low_flat": +1,
    "S_seg12_high_dn": -1, "S_seg34_high_dn": -1, "S_seg2_mid_dn": -1,
}


def one_side_cost_frac(row) -> float:
    spec = CONTRACT_SPECS.get_symbol(row["symbol"])
    if spec is None:
        return np.nan
    price = float(row["close_t"])
    slip = (spec.tick * spec.slip_tick) / price
    try:
        comm_yuan = spec.total_commission(price, 1)
        comm = comm_yuan / (spec.size * price) if spec.size > 0 else 0.0
    except Exception:
        comm = 0.0
    return slip + comm


def main() -> None:
    print("[1/6] Loading long table …", flush=True)
    long_df = pd.read_csv(LONG_PATH)
    long_df["event_time"] = pd.to_datetime(long_df["event_time"])
    long_df["event_date"] = pd.to_datetime(long_df["event_date"]).dt.date

    print("[2/6] Enriching intraday features (atr / trend) …", flush=True)
    long_df = enrich_intra_features(long_df)
    print(f"      rows={len(long_df)}, atr_intra NaN={long_df['atr_intra'].isna().sum()}")

    print("[3/6] Adding ret_10h …", flush=True)
    long_df = add_future_returns(long_df)

    print("[4/6] Computing per-contract rolling ranks (240 events) …", flush=True)
    for col in ["A3_skew", "atr_intra", "trend_intra"]:
        long_df = add_rank(long_df, col, RANK_WIN_EVENTS)
    print(f"      rank NaN: skew={long_df['A3_skew_rank'].isna().sum()}, "
          f"atr={long_df['atr_intra_rank'].isna().sum()}, "
          f"trend={long_df['trend_intra_rank'].isna().sum()}")

    print("[5/6] Classify tier …", flush=True)
    long_df["tier"] = long_df.apply(
        lambda r: classify_tier(
            float(r["A3_skew_rank"]) if pd.notna(r["A3_skew_rank"]) else float("nan"),
            float(r["atr_intra_rank"]) if pd.notna(r["atr_intra_rank"]) else float("nan"),
            float(r["trend_intra_rank"]) if pd.notna(r["trend_intra_rank"]) else float("nan"),
        ),
        axis=1,
    )
    tier_counts = long_df["tier"].value_counts()
    print(tier_counts)
    long_df["cost_rt"] = 2.0 * long_df.apply(one_side_cost_frac, axis=1)
    long_df["ce_key"] = long_df["contract"].astype(str) + "|" + long_df["event_date"].astype(str)

    print("[6/6] Evaluating signed pnl by (tier × horizon) …", flush=True)
    rows = []
    for tier_name, sub in long_df[long_df["tier"] != "none"].groupby("tier"):
        direction = TIER_DIRECTION[tier_name]
        for h_hr in HORIZONS_5M:
            col = f"ret_{h_hr}h"
            y_gross = sub[col].to_numpy() * direction
            y_net = y_gross - sub["cost_rt"].to_numpy()
            for lbl, y in [("gross", y_gross), ("net", y_net)]:
                obs, lo, hi, p, n = cluster_bootstrap_mean(
                    y, sub["ce_key"].to_numpy()
                )
                rows.append({
                    "tier": tier_name, "direction": direction,
                    "horizon": f"ret_{h_hr}h", "cost": lbl,
                    "n_events": n, "mean": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                })
    result_df = pd.DataFrame(rows)
    result_df.to_csv(OUT_DIR / "c1_tier_horizon.csv", index=False)
    print("\n=== Causal tier × horizon signed pnl ===")
    print(result_df.to_string(index=False))

    print("\n=== Any tier×horizon with net CI_lo > 0? ===")
    winners = result_df[(result_df["cost"] == "net") & (result_df["ci_lo"] > 0) & (result_df["p_two"] < 0.05)]
    print(f"n_winners: {len(winners)}")
    if not winners.empty:
        print(winners.to_string(index=False))

    # 逐 symbol 保留率 for top-3 gross tiers/horizons
    print("\n=== Symbol retention for top-3 gross-mean cells ===")
    gross = result_df[result_df["cost"] == "gross"].sort_values("mean", ascending=False).head(6)
    print(gross.to_string(index=False))
    ret_rows = []
    for _, r in gross.iterrows():
        tier_name = r["tier"]
        h_col = r["horizon"]
        direction = TIER_DIRECTION[tier_name]
        sub = long_df[long_df["tier"] == tier_name]
        if len(sub) < 30:
            continue
        n_sym = sub["symbol"].nunique()
        pos = 0
        for sym, s2 in sub.groupby("symbol"):
            y = s2[h_col].to_numpy() * direction - s2["cost_rt"].to_numpy()
            if len(y) >= 5 and np.nanmean(y) > 0:
                pos += 1
        ret_rows.append({
            "tier": tier_name, "horizon": h_col, "n_events": int(len(sub)),
            "n_sym": int(n_sym), "n_sym_positive": pos,
            "retention": pos / n_sym if n_sym > 0 else float("nan"),
        })
    ret_df = pd.DataFrame(ret_rows)
    ret_df.to_csv(OUT_DIR / "c1_top_retention.csv", index=False)
    print(ret_df.to_string(index=False))

    # Snapshot tier assignments for downstream steps
    long_df[[
        "symbol", "contract", "event_time", "event_date", "close_t",
        "A3_skew_rank", "atr_intra_rank", "trend_intra_rank",
        "tier", "cost_rt", "ce_key",
        *[f"ret_{h}h" for h in HORIZONS_5M],
    ]].to_csv(OUT_DIR / "c1_events_with_tier.csv", index=False)
    print(f"\nAll outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
